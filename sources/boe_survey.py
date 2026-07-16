"""
sources/boe_survey.py
=====================
Bank of England *survey* spreadsheet source (§2.B B4).

The BoE publishes several quarterly surveys as XLSX workbooks — NOT as IADB
time-series codes — so they can't ride ``sources/boe.py`` (which speaks the IADB
CSV endpoint). This module downloads one such workbook and pulls a single
labelled row out of its wide (dates-across-columns) layout.

Series-id convention (a single library column):

    ``<xlsx_stem>|<sheet>|<question_substr>|<row_label>``

  * ``xlsx_stem``      — file under the inflation-attitudes-survey media dir,
                         e.g. ``long-run.xlsx``.
  * ``sheet``          — worksheet name, e.g. ``LONG-RUN``.
  * ``question_substr``— case-insensitive substring identifying the QUESTION
                         header row in column A (e.g. ``five years``).
  * ``row_label``      — the label (column A) of the wanted row BELOW that
                         question, e.g. ``Median``.

The parser locates the date header row (the row whose cells across the columns
are datetimes), then the question row, then the first ``row_label`` row after
it, and reads every populated (date, value) pair. Modelled on the download +
wide-parse shape of ``sources/atlanta_fed.py``; retries via the shared
``sources.base.fetch_with_backoff`` engine (§2.C C3).

Indicator definitions live in ``data/macro_library_boe_survey.csv``.
"""

from __future__ import annotations

import datetime as _dt
import io
import pathlib

import openpyxl
import pandas as pd

from sources.base import fetch_with_backoff

_LIBRARY_CSV = pathlib.Path(__file__).parent.parent / "data" / "macro_library_boe_survey.csv"
# The inflation-attitudes-survey workbooks live under this stable media dir;
# other BoE survey dirs can be added as a second path prefix if needed.
_BOE_MEDIA_BASE = "https://www.bankofengland.co.uk/-/media/boe/files/inflation-attitudes-survey"
DEFAULT_HIST_START = "1999-01-01"


# ---------------------------------------------------------------------------
# LIBRARY LOADER
# ---------------------------------------------------------------------------

def load_library() -> list[dict]:
    """Load BoE-survey indicator definitions from macro_library_boe_survey.csv.
    Returns [] when the library is empty/absent (scaffold state)."""
    if not _LIBRARY_CSV.exists():
        return []
    df = pd.read_csv(_LIBRARY_CSV, dtype=str, keep_default_na=False)
    if df.empty:
        return []
    df["sort_key"] = pd.to_numeric(df["sort_key"], errors="coerce").fillna(0)
    df = df.sort_values("sort_key")
    result = []
    for _, row in df.iterrows():
        result.append({
            "source":       "BoE Survey",
            "source_id":    row["series_id"].strip(),
            "col":          row["col"].strip(),
            "name":         row["name"].strip(),
            "country":      row.get("country", "").strip() or "GBR",
            "category":     row["category"].strip(),
            "subcategory":  row["subcategory"].strip(),
            "concept":      row.get("concept", "").strip(),
            "cycle_timing": row.get("cycle_timing", "").strip(),
            "units":        row["units"].strip(),
            "frequency":    row["frequency"].strip(),
            "notes":        row.get("notes", "").strip(),
            "sort_key":     float(row["sort_key"]),
            "series_id":    row["series_id"].strip(),
        })
    return result


# ---------------------------------------------------------------------------
# WORKBOOK FETCH + PARSE
# ---------------------------------------------------------------------------

def _download_workbook(stem: str, timeout: int = 45, retries: int = 3) -> bytes | None:
    raw = fetch_with_backoff(
        f"{_BOE_MEDIA_BASE}/{stem}",
        label=f"BoE Survey {stem}",
        accept="bytes",
        retries=retries,
        timeout=timeout,
        headers={"User-Agent": "Mozilla/5.0 (compatible; market-dash/1.0)"},
    )
    return raw if isinstance(raw, (bytes, bytearray)) else None


def _find_date_row(ws) -> int | None:
    """The date header row is the topmost row with >=3 datetime cells."""
    for r in range(1, min(ws.max_row, 40) + 1):
        n = sum(1 for c in range(2, ws.max_column + 1)
                if isinstance(ws.cell(r, c).value, _dt.datetime))
        if n >= 3:
            return r
    return None


def parse_workbook(raw: bytes, series_id: str) -> pd.Series | None:
    """Parse ``<stem>|<sheet>|<question_substr>|<row_label>`` out of the wide
    BoE survey workbook → date-indexed pd.Series (period start), or None."""
    try:
        _, sheet, question_substr, row_label = series_id.split("|", 3)
    except ValueError:
        print(f"    [BoE Survey] bad series_id {series_id!r} "
              f"(expected '<stem>|<sheet>|<question>|<row_label>')")
        return None
    try:
        wb = openpyxl.load_workbook(io.BytesIO(raw), data_only=True, read_only=True)
    except Exception as e:                       # noqa: BLE001
        print(f"    [BoE Survey] workbook open failed for {series_id}: {e}")
        return None
    if sheet not in wb.sheetnames:
        print(f"    [BoE Survey] sheet {sheet!r} absent (have {wb.sheetnames})")
        return None
    ws = wb[sheet]

    date_row = _find_date_row(ws)
    if date_row is None:
        print(f"    [BoE Survey] no date header row in {sheet}")
        return None

    q_lower = question_substr.strip().lower()
    lbl_lower = row_label.strip().lower()
    q_row = None
    target_row = None
    for r in range(1, ws.max_row + 1):
        a = ws.cell(r, 1).value
        if a is None:
            continue
        a_str = str(a).strip().lower()
        if q_row is None:
            if q_lower in a_str:
                q_row = r
            continue
        # after the question row, take the first matching label row
        if a_str == lbl_lower or a_str.startswith(lbl_lower):
            target_row = r
            break
    if target_row is None:
        print(f"    [BoE Survey] '{row_label}' not found after question "
              f"'{question_substr}' in {sheet}")
        return None

    obs: dict[pd.Timestamp, float] = {}
    for c in range(2, ws.max_column + 1):
        d = ws.cell(date_row, c).value
        v = ws.cell(target_row, c).value
        if not isinstance(d, _dt.datetime) or v is None:
            continue
        try:
            obs[pd.Timestamp(d.date())] = float(v)
        except (ValueError, TypeError):
            continue
    if not obs:
        return None
    return pd.Series(obs).sort_index()


def fetch_series_as_pandas(
    series_id: str,
    col_name: str | None = None,
    start: str = DEFAULT_HIST_START,
) -> pd.Series | None:
    """Download + parse one BoE-survey series. Signature matches the coordinator's
    ``_make_source_handlers`` factory (§2.C C2)."""
    stem = series_id.split("|", 1)[0]
    raw = _download_workbook(stem)
    if raw is None:
        return None
    s = parse_workbook(raw, series_id)
    if s is None or s.empty:
        return None
    s.name = col_name or series_id
    return s
