"""
sources/ny_fed.py
=================
New York Fed Staff Nowcast — real-time US Q-over-Q annualised real GDP
growth nowcast. The Federal Reserve Bank of New York publishes the full
forecast history as a single Excel workbook on the Staff Nowcast
homepage.

Canonical primary source: the "Download Data" workbook linked from
https://www.newyorkfed.org/research/policy/nowcast. The stable CDN path
(verified 2026-06-11 by SERP-resolving the page's Downloads section):

  - https://www.newyorkfed.org/medialibrary/Research/Interactives/Data/
    NowCast/Downloads/New-York-Fed-Staff-Nowcast_download_data.xlsx

The site itself is heavily JS-rendered (the page returns 403 to
unauthenticated header-less GETs) — but the medialibrary path serving the
xlsx is a plain static asset and stable across the 2.0 model relaunch
(Almuzara, Liberty Street Economics 2023-09-08) and subsequent vintages.

Updated weekly — the New York Fed publishes a new nowcast each Friday
during quarters they're tracking (and silent between the model's final
nowcast of Q and the initial nowcast of Q+1, a window of ~3-5 business
days around BEA's advance estimate). We declare frequency=Weekly and
forward-fill across the quiet windows at the calculator
(compute_macro_market._calc_US_NOWCAST1).

Workbook layout (per the file's own header rows — confirmed 2026-06-11):
  - One headline forecast tab (Date column + per-quarter forecast value
    columns), one row per Friday publication date.
  - A second tab for nowcast-news decomposition (data releases driving
    the weekly revision) — not used here; we want the headline only.

Parser strategy mirrors sources/atlanta_fed.py:
  - Enumerate every sheet; pick ones with a Date column whose values are
    parseable timestamps.
  - On each such sheet, the rightmost non-null numeric cell on a row is
    the headline nowcast for that publication date (the per-quarter
    columns fill leftmost-first, so rightmost-non-null tracks the
    currently-tracked vintage).
  - Concatenate across sheets, dedupe by date keeping the most recent
    observation. Plausibility-filter to [-50, +50] % SAAR.

Wired §3.1.4 (2026-06-11) as the second §3.1.4 nowcast fetcher — provides
the US_NOWCAST1 second-opinion read on US growth alongside US_GDPNOW1
(Atlanta Fed GDPNow), which shipped earlier today.
"""

from __future__ import annotations

import io
import pathlib
import time

import pandas as pd
import requests

_LIBRARY_CSV = pathlib.Path(__file__).parent.parent / "data" / "macro_library_ny_fed.csv"

# Canonical URL — verified 2026-06-11 by SERP-resolving the Staff Nowcast
# homepage's Downloads section. The medialibrary path is the same static
# asset linked from the page's "Download Data" button.
NYFED_XLSX_HOSTS = [
    "https://www.newyorkfed.org/medialibrary/Research/Interactives/Data/NowCast/Downloads/New-York-Fed-Staff-Nowcast_download_data.xlsx",
]

# Browser-like UA — the NY Fed medialibrary 403s default python-requests
# UA strings, same pattern as the Atlanta Fed CDN.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,"
        "application/vnd.ms-excel,application/octet-stream,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# File magic — xlsx is a ZIP (PK\x03\x04).
_XLSX_MAGIC = b"PK\x03\x04"

# Tabs explicitly NOT forecast-by-date series — skip them.
_SKIP_SHEETS = {"ReadMe", "Disclaimer", "Notes", "Glossary", "News", "Decomposition"}


# ---------------------------------------------------------------------------
# LIBRARY LOADER
# ---------------------------------------------------------------------------

def load_library() -> list[dict]:
    """Load NY Fed indicator definitions from macro_library_ny_fed.csv."""
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
            "source":       "NYFed",
            "source_id":    row["series_id"].strip(),
            "col":          row["col"].strip(),
            "name":         row["name"].strip(),
            "country":      row.get("country", "").strip() or "USA",
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
# WORKBOOK DOWNLOAD + CACHE
# ---------------------------------------------------------------------------

_WORKBOOK_BYTES_CACHE: bytes | None = None
_WORKBOOK_BYTES_TRIED: bool = False
_PARSED_SERIES_CACHE: dict[str, pd.Series] = {}


def _download_workbook(timeout: int = 45, retries: int = 2) -> bytes | None:
    """Download the NY Fed Nowcast xlsx from the canonical medialibrary URL.

    Returns the raw bytes or None on hard failure. Logs every attempt for
    pipeline.log capture. Cached per process via _resolve_workbook_bytes()."""
    last_exc: Exception | None = None
    for attempt in range(retries):
        for host in NYFED_XLSX_HOSTS:
            try:
                resp = requests.get(host, headers=_HEADERS, timeout=timeout)
                if resp.status_code != 200:
                    print(f"    [NYFed HTTP {resp.status_code}] {host}")
                    continue
                body = resp.content
                if not body:
                    print(f"    [NYFed] {host}: empty body")
                    continue
                if not body.startswith(_XLSX_MAGIC):
                    head = body[:32].replace(b"\n", b" ")
                    print(
                        f"    [NYFed] {host}: not an xlsx — "
                        f"first 32 bytes: {head!r}"
                    )
                    continue
                print(
                    f"    [NYFed] resolved xlsx ({len(body):,} bytes) via {host}"
                )
                return body
            except requests.Timeout:
                print(f"    [NYFed timeout] {host}")
                last_exc = TimeoutError(f"timeout on {host}")
                continue
            except requests.RequestException as e:
                print(f"    [NYFed request error] {host}: {e}")
                last_exc = e
                continue
        wait = 2 ** attempt
        if attempt + 1 < retries:
            print(f"    [NYFed] all hosts failed — backing off {wait}s")
            time.sleep(wait)
    print(
        f"    [NYFed FAIL] {retries} attempts × {len(NYFED_XLSX_HOSTS)} host(s) "
        f"exhausted ({last_exc})"
    )
    return None


def _resolve_workbook_bytes() -> bytes | None:
    """Cached wrapper around _download_workbook — runs once per process."""
    global _WORKBOOK_BYTES_CACHE, _WORKBOOK_BYTES_TRIED
    if _WORKBOOK_BYTES_TRIED:
        return _WORKBOOK_BYTES_CACHE
    _WORKBOOK_BYTES_CACHE = _download_workbook()
    _WORKBOOK_BYTES_TRIED = True
    return _WORKBOOK_BYTES_CACHE


# ---------------------------------------------------------------------------
# WORKBOOK PARSER
# ---------------------------------------------------------------------------

def _find_date_column(df: pd.DataFrame) -> str | None:
    """Locate the publication-date column in a forecast sheet.

    The NY Fed workbook labels it `Date` on the headline tab; we accept any
    column whose name (case-insensitive, whitespace-stripped) starts with
    'date', 'forecast date', 'vintage', or whose values parse > 50% as
    timestamps. Same logic as sources/atlanta_fed.py — Atlanta uses the
    same family of labels."""
    for c in df.columns:
        name = str(c).strip().lower()
        if name in ("date", "forecast date", "forecastdate", "vintage"):
            return c
        if name.startswith("forecast date") or name.startswith("date "):
            return c
    # Value-shape pass — pick the first column with > 50% parseable dates.
    for c in df.columns:
        col = df[c]
        if col.dtype.kind in ("i", "f", "u"):
            continue
        try:
            parsed = pd.to_datetime(col, errors="coerce")
        except Exception:
            continue
        if parsed.notna().sum() >= max(5, int(len(col) * 0.5)):
            return c
    return None


def _extract_headline_series_from_sheet(df: pd.DataFrame) -> pd.Series | None:
    """From one forecast sheet, build a (publication_date -> latest nowcast)
    Series.

    Each row is one weekly publication. Columns to the right of the Date
    column hold the nowcast point estimate for whichever quarter was being
    tracked at the time. The "headline" value the homepage cites is the
    rightmost non-null numeric cell on that row — i.e. the latest tracked
    quarter's forecast as of the publication date. Same rightmost-non-null
    pattern as sources/atlanta_fed.py."""
    date_col = _find_date_column(df)
    if date_col is None:
        return None
    dates = pd.to_datetime(df[date_col], errors="coerce")
    valid = dates.notna()
    if not valid.any():
        return None
    df2 = df.loc[valid].copy()
    dates = dates.loc[valid]

    value_cols = [c for c in df2.columns if c != date_col]
    if not value_cols:
        return None
    numeric = df2[value_cols].apply(pd.to_numeric, errors="coerce")
    numeric = numeric.dropna(axis=1, how="all")
    if numeric.empty:
        return None

    def _row_last(row):
        nonnull = row.dropna()
        if nonnull.empty:
            return float("nan")
        return float(nonnull.iloc[-1])

    values = numeric.apply(_row_last, axis=1)
    s = pd.Series(values.values, index=pd.DatetimeIndex(dates.values))
    s = s.dropna()
    # Plausibility guardrail — same [-50, +50] % SAAR window as Atlanta Fed.
    # The 2020-Q2 pandemic print was historically ~-35%, 2020-Q3 rebound
    # ~+35%; anything outside this range is almost certainly a cell that
    # isn't a growth-rate reading at all.
    s = s[(s >= -50.0) & (s <= 50.0)]
    return s if not s.empty else None


def _parse_workbook(xlsx_bytes: bytes) -> pd.Series | None:
    """Parse every plausible forecast sheet, concatenate the headline
    series, dedupe by date keeping the most recent observation per
    publication date.

    Returns None on hard parse failure (no usable sheet)."""
    try:
        xf = pd.ExcelFile(io.BytesIO(xlsx_bytes), engine="openpyxl")
    except Exception as e:
        print(f"    [NYFed] ExcelFile open failed: {type(e).__name__}: {e}")
        return None

    pieces: list[pd.Series] = []
    sheets_used: list[str] = []
    for sheet in xf.sheet_names:
        if sheet in _SKIP_SHEETS:
            continue
        try:
            df = xf.parse(sheet)
        except Exception as e:
            print(f"    [NYFed] sheet {sheet!r} read failed: {e}")
            continue
        if df is None or df.empty:
            continue
        s = _extract_headline_series_from_sheet(df)
        if s is None or s.empty:
            continue
        pieces.append(s)
        sheets_used.append(sheet)

    if not pieces:
        print(
            f"    [NYFed] no usable forecast sheets found in workbook "
            f"(sheets seen: {xf.sheet_names})"
        )
        return None

    print(f"    [NYFed] parsed {len(pieces)} sheet(s): {sheets_used}")
    combined = pd.concat(pieces)
    combined = combined[~combined.index.duplicated(keep="last")].sort_index()
    return combined


# ---------------------------------------------------------------------------
# SERIES FETCH
# ---------------------------------------------------------------------------

def fetch_series_as_pandas(
    series_id: str,
    col_name: str | None = None,
) -> pd.Series | None:
    """Fetch the NY Fed Nowcast headline series, return a date-indexed pd.Series.

    series_id : currently only `nyfed_nowcast_us_qoq_saar` is wired. Other
                ids are accepted but log a clear "unknown series" line and
                return None — leaves room to add subcomponent / news-impact
                columns later without breaking the existing wiring.
    col_name  : optional name for the returned Series (default = series_id).

    Returns None on download / parse failure (logged to stdout for
    pipeline.log capture)."""
    sid = series_id.strip()
    if sid != "nyfed_nowcast_us_qoq_saar":
        print(
            f"    [NYFed] unknown series_id {sid!r} — only "
            f"'nyfed_nowcast_us_qoq_saar' is wired today"
        )
        return None

    if sid in _PARSED_SERIES_CACHE:
        s = _PARSED_SERIES_CACHE[sid].copy()
        s.name = col_name or sid
        return s

    body = _resolve_workbook_bytes()
    if body is None:
        return None
    s = _parse_workbook(body)
    if s is None:
        return None
    _PARSED_SERIES_CACHE[sid] = s
    out = s.copy()
    out.name = col_name or sid
    return out
