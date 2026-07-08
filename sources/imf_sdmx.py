"""
sources/imf_sdmx.py
===================
IMF Data Portal source module (api.imf.org — the platform that replaced
dataservices.imf.org / SDMX_JSON.svc when the IMF migrated to data.imf.org
in 2025).

SDMX 2.1 over REST. No registration, no API key. Series addressed by
``<flowRef>/<key>`` where flowRef is ``<agency>,<flow>`` and the key is a
dot-separated SDMX dimension tuple, e.g.
``IMF.STA,CPI/CHN.CPI._T.YOY_PCH_PA_PT.M`` (China, national CPI,
all-items, year-over-year % change, monthly).

Distinct from ``sources/imf.py``, which speaks the separate DataMapper v1
API (annual WEO aggregates) — the two IMF APIs share nothing but the
publisher, so they are separate modules with separate libraries.

CSV responses use TIME_PERIOD values like ``2026-M05`` (monthly),
``2026-Q1`` (quarterly) or ``2026`` (annual) — ``_parse_period`` handles
all three.

Indicator definitions live in ``data/macro_library_imf_sdmx.csv``.

Wired 2026-07-08 (forward_plan §2.A A1) to resolve the China inflation
cluster: the FRED OECD-MEI mirrors CHNCPIALLMINMEI / CHNPIEATI01GYM froze
in 2025-04 / 2022-12, OECD COICOP2018 has no CHN coverage, and the IMF IFS
mirror on DB.nomics lags ~1 year — but the IMF's own CPI dataset is
monthly-fresh for China (verified 2026-05 obs on the 2026-07-08 vintage).
"""

from __future__ import annotations

import csv
import io
import pathlib
import time
from datetime import date

import pandas as pd

from sources.base import fetch_with_backoff

_DATA_DIR = pathlib.Path(__file__).resolve().parent.parent / "data"
_LIBRARY_CSV = _DATA_DIR / "macro_library_imf_sdmx.csv"

IMF_SDMX_BASE = "https://api.imf.org/external/sdmx/2.1/data"
DEFAULT_HIST_START = "1990-01-01"
IMF_SDMX_DELAY = 1.0  # polite inter-call delay (no published rate limit)


# ---------------------------------------------------------------------------
# LIBRARY LOADER
# ---------------------------------------------------------------------------

def load_library() -> list[dict]:
    """Load IMF SDMX indicator definitions from macro_library_imf_sdmx.csv."""
    if not _LIBRARY_CSV.exists():
        return []
    df = pd.read_csv(_LIBRARY_CSV, dtype=str, keep_default_na=False)
    df["sort_key"] = pd.to_numeric(df["sort_key"], errors="coerce").fillna(0)
    df = df.sort_values("sort_key")
    result = []
    for _, row in df.iterrows():
        result.append({
            "source":       "IMF SDMX",
            "source_id":    row["series_id"].strip(),
            "col":          row["col"].strip(),
            "name":         row["name"].strip(),
            "country":      row.get("country", "").strip(),
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
# SERIES FETCH
# ---------------------------------------------------------------------------

def fetch_series(
    series_id: str,
    start: str = DEFAULT_HIST_START,
    timeout: int = 40,
    retries: int = 3,
    last_n: int | None = None,
) -> str | None:
    """Fetch a single IMF series as raw SDMX-CSV text.

    series_id: '<agency>,<flow>/<key>' — e.g.
               'IMF.STA,CPI/CHN.CPI._T.YOY_PCH_PA_PT.M'.
    last_n:    if set, request only the latest n observations (snapshot).
    Returns CSV body (UTF-8) or None on failure.
    """
    if "/" not in series_id or "," not in series_id.split("/", 1)[0]:
        print(f"    [IMF SDMX] invalid series_id {series_id!r} "
              f"(expected '<AGENCY>,<FLOW>/<KEY>')")
        return None

    params = {"startPeriod": start[:4]}
    if last_n is not None and last_n > 0:
        params["lastNObservations"] = str(last_n)
    text = fetch_with_backoff(
        f"{IMF_SDMX_BASE}/{series_id}",
        params=params,
        label="IMF SDMX",
        accept_csv=True,
        retries=retries,
        timeout=timeout,
        headers={"Accept": "application/vnd.sdmx.data+csv"},
    )
    return text if isinstance(text, str) and text.strip() else None


def parse_csv(text: str, series_id: str) -> list[tuple[date, float]]:
    """Parse IMF SDMX-CSV → sorted list of (date, value) tuples.

    The response carries one row per observation with TIME_PERIOD and
    OBS_VALUE columns plus ~40 metadata columns (long quoted description
    fields — must be parsed with a real CSV reader, never split on ',').
    Rows with an empty OBS_VALUE are skipped.
    """
    out: list[tuple[date, float]] = []
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        d = _parse_period((row.get("TIME_PERIOD") or "").strip())
        raw = (row.get("OBS_VALUE") or "").strip()
        if d is None or not raw:
            continue
        try:
            out.append((d, float(raw)))
        except ValueError:
            continue
    out.sort(key=lambda t: t[0])
    return out


def _parse_period(p: str) -> date | None:
    """'2026-M05' → 2026-05-01; '2026-Q2' → 2026-04-01; '2026' → 2026-01-01."""
    if not p:
        return None
    try:
        if "-M" in p:
            y, m = p.split("-M")
            return date(int(y), int(m), 1)
        if "-Q" in p:
            y, q = p.split("-Q")
            return date(int(y), (int(q) - 1) * 3 + 1, 1)
        if len(p) == 4 and p.isdigit():
            return date(int(p), 1, 1)
        # fall back to ISO forms the API may emit for daily/monthly
        return date.fromisoformat(p[:10]) if len(p) >= 10 else \
            date(int(p[:4]), int(p[5:7]), 1)
    except (ValueError, IndexError):
        return None


def fetch_series_as_pandas(
    series_id: str,
    col_name: str | None = None,
    start: str = DEFAULT_HIST_START,
    last_n: int | None = None,
) -> pd.Series | None:
    """Fetch + parse one series into a pandas Series. Dates are stamped at
    the period start (same convention as sources/ecb.py); the Friday-spine
    resample in fetch_macro_economic handles alignment."""
    text = fetch_series(series_id, start=start, last_n=last_n)
    if text is None:
        return None
    obs = parse_csv(text, series_id)
    if not obs:
        return None
    idx = pd.to_datetime([d for d, _ in obs])
    s = pd.Series([v for _, v in obs], index=idx, name=col_name or series_id)
    return s[~s.index.duplicated(keep="last")].sort_index()
