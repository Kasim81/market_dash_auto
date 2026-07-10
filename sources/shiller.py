"""
sources/shiller.py
==================
Robert Shiller's long-run US market dataset — S&P 500 composite price,
dividends, earnings, US CPI, long rate, and the Cyclically Adjusted P/E
Ratio (CAPE), back to 1871. Monthly cadence.

Canonical primary source: shillerdata.com (Shiller's commercial site;
hosted on the GoDaddy wsimg.com blob CDN). The Yale mirror at
http://www.econ.yale.edu/~shiller/data/ie_data.xls was the canonical
primary URL for ~20 years but went stale October 2023 — kept as a
fallback in case Yale catches up some day.

Updated quarterly-ish by Shiller himself. The xls workbook carries:
  - A "Data" sheet with the long-run series
  - 7 pre-header rows of titles + sub-headers; row 8 is the column header
  - A Date column in decimal-year format ("1871.01", "1871.02", ..., "1871.12")
  - Per-column series: S&P Composite Price (P), Dividend (D), Earnings (E),
    CPI, Long Interest Rate (GS10), Real Price, Real Dividend, Real
    Earnings, and CAPE.

Fallback mirrors (regime-AA Phase 0c memo §3.11):
  - https://shillerdata.com/ (Shiller's commercial homepage; serves the same
    xls — the actual download URL is on img1.wsimg.com behind a blob path,
    discovered by scraping the homepage 2026-06-10)
  - https://datahub.io/core/s-and-p-500/r/data.csv (community CSV mirror,
    subset of columns)
  - https://posix4e.github.io/shiller_wrapper_data/data.json — referenced
    in the handoff memo but the GitHub Pages site returns 404 as of
    2026-06-10; not wired here until/unless it comes back.

Indicator definitions live in data/macro_library_shiller.csv. Each row's
`series_id` is the source column header from the "Data" sheet (e.g.
"CAPE", "S&P Comp. P", "Dividend D", "Earnings E", "CPI",
"Long Interest Rate GS10").

Date column quirk: the Shiller "Date" column stores decimal years where
the fractional part is the two-digit month — "1871.01" is January 1871
and "1871.10" is October 1871 (NOT the first decile of the year). As
floats these round-trip distinctly because 0.01 and 0.10 are different
IEEE-754 numbers, so `month = round((val - year) * 100)` recovers the
intended month. When the workbook is delivered with cell values stored
as strings instead of numbers (some mirror conversions do this), we
honour the string convention from the prompt: "1871.1" → January,
"1871.10" → October — single-digit fractional means single-digit month;
two-digit fractional means two-digit month (no padding logic).

The downloaded workbook is cached per process (read once, slice many —
same shape as sources/ifo.py::_resolve_workbook_impl()), so a fetch loop
that pulls CAPE + CPI + Long Rate from the same library only hits Yale
once.

Wired §3.13 (2026-06-10) — parser populated + library rows added in the
same commit. The library load is still a no-op when the CSV is empty,
matching the macro_library_nasdaqdl.csv precedent.
"""

from __future__ import annotations

import io
import pathlib

import pandas as pd

from sources.base import fetch_with_backoff

_LIBRARY_CSV = pathlib.Path(__file__).parent.parent / "data" / "macro_library_shiller.csv"

# Primary URL: shillerdata.com / wsimg.com blob CDN. This is Shiller's own
# commercial site, which he updates actively. The xls is ~1MB. The Yale
# academic mirror at econ.yale.edu/~shiller/data/ie_data.xls was the
# canonical primary URL for ~20 years, but 2026-06-11 investigation found
# Yale has gone stale since October 2023 (the 2026-06-10 23:43 UTC daily run
# downloaded Yale's copy and the most-recent CAPE observation was 2023-10).
# shillerdata.com still publishes fresh — the `?ver=` query string is a
# Unix-epoch-milliseconds re-upload tag (1780495520681 ≈ 2026-06-04).
SHILLER_XLS_URL = (
    "https://img1.wsimg.com/blobby/go/e5e77e0b-59d1-44d9-ab25-4763ac982e53/"
    "downloads/c9b8cf0f-f01a-49f5-9ea5-d19443390ab2/ie_data.xls?ver=1780495520681"
)

# Fallback hosts. Order is intentional (revised 2026-06-11):
#   1. shillerdata.com / wsimg.com blob CDN — Shiller's actively-maintained
#      commercial site. The actual file lives on GoDaddy's wsimg.com blob
#      store; the homepage at https://shillerdata.com/ does not serve
#      /ie_data.xls directly. The blob path was scraped from the "Download"
#      link on the homepage; the `?ver=` query string changes when Shiller
#      re-uploads — re-scrape https://shillerdata.com/ if this path 404s in
#      the future.
#   2. Yale (econ.yale.edu/~shiller/data/ie_data.xls) — historical mirror,
#      kept as a fallback only. Was the canonical primary for ~20 years
#      but went stale October 2023 per the 2026-06-10 23:43 UTC daily run.
#      If Yale catches back up some day the fallback will silently start
#      working again; until then, the parser will get stale data here.
#   3. (Community JSON / datahub CSV mirrors are reachable via different
#      code paths — they're not the same .xls download, so they're handled
#      separately by upstream code if/when this module is extended.)
SHILLER_XLS_HOSTS = [
    "https://img1.wsimg.com/blobby/go/e5e77e0b-59d1-44d9-ab25-4763ac982e53/downloads/c9b8cf0f-f01a-49f5-9ea5-d19443390ab2/ie_data.xls?ver=1780495520681",
    "http://www.econ.yale.edu/~shiller/data/ie_data.xls",
]

# Browser-like UA — Yale's webserver 403s the default python-requests UA.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "application/vnd.ms-excel,application/vnd.openxmlformats-"
        "officedocument.spreadsheetml.sheet,application/octet-stream,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# First bytes of file magic. Shiller distributions historically ship a
# genuine BIFF binary .xls (OLE2 compound file) — that's the current Yale
# delivery as of 2026-06-10. Some mirrors transcode to xlsx (ZIP archive)
# but keep the .xls extension. We dispatch by magic: openpyxl for xlsx,
# xlrd (<2.0; 2.0 dropped .xls support) for BIFF.
_XLSX_MAGIC = b"PK\x03\x04"
_BIFF_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # OLE2 compound file (legacy .xls)

# The "Data" sheet in ie_data.xls has 7 pre-header rows of title +
# attribution text; row 8 is the column-name header. Verified against the
# workbook structure documented on Shiller's homepage and in multiple
# community readers (econdb, posix4e/shiller_wrapper_data). If a future
# Shiller release shifts the header row, the parser surfaces a clear error
# from the "Date column not found" branch in _parse_data_sheet.
_DATA_SHEET_NAME = "Data"
_DATA_HEADER_ROW = 7  # 0-indexed; pandas header= parameter


# ---------------------------------------------------------------------------
# LIBRARY LOADER
# ---------------------------------------------------------------------------

def load_library() -> list[dict]:
    """Load Shiller indicator definitions from macro_library_shiller.csv.

    Returns [] when the library is empty/absent."""
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
            "source":       "Shiller",
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

# Process-level caches. Cache the parsed DataFrame too so a fetch loop that
# pulls 6 columns from the same workbook does one download + one parse.
_WORKBOOK_BYTES_CACHE: bytes | None = None
_WORKBOOK_BYTES_TRIED: bool = False
_DATA_FRAME_CACHE: pd.DataFrame | None = None


def _download_workbook(timeout: int = 30, retries: int = 2) -> bytes | None:
    """Download ie_data.xls from the canonical Yale URL with mirror fallback.

    Returns the raw bytes (xlsx-with-.xls-extension in modern releases) or
    None on hard failure. Logs every attempt for pipeline.log capture.
    Cached per process via _resolve_workbook_bytes()."""
    # §2.C C3 (2026-07-09): shared retry engine in mirror mode with
    # accept="bytes"; the validate hook keeps the file-magic sniff (modern
    # releases are xlsx-with-.xls-extension, older mirrors true BIFF .xls).
    def _reject(body: bytes) -> str | None:
        if not body:
            return "empty body"
        if not (body.startswith(_XLSX_MAGIC) or body.startswith(_BIFF_MAGIC)):
            head = body[:32].replace(b"\n", b" ")
            return f"unrecognised file magic — first 32 bytes: {head!r}"
        return None

    body = fetch_with_backoff(
        list(SHILLER_XLS_HOSTS), label="Shiller", accept="bytes",
        retries=retries, timeout=timeout, headers=_HEADERS, validate=_reject,
    )
    if body is not None:
        kind = "xlsx" if body.startswith(_XLSX_MAGIC) else "BIFF .xls"
        print(f"    [Shiller] resolved {kind} ({len(body):,} bytes)")
    return body


def _resolve_workbook_bytes() -> bytes | None:
    """Cached wrapper around _download_workbook — runs once per process.

    On failure, caches the None result so a subsequent series fetch in the
    same run doesn't re-hit a dead endpoint."""
    global _WORKBOOK_BYTES_CACHE, _WORKBOOK_BYTES_TRIED
    if _WORKBOOK_BYTES_TRIED:
        return _WORKBOOK_BYTES_CACHE
    _WORKBOOK_BYTES_CACHE = _download_workbook()
    _WORKBOOK_BYTES_TRIED = True
    return _WORKBOOK_BYTES_CACHE


# ---------------------------------------------------------------------------
# DECIMAL-YEAR DATE PARSER
# ---------------------------------------------------------------------------

def _parse_shiller_date(raw) -> pd.Timestamp | None:
    """Parse one Shiller decimal-year cell to a month-end Timestamp.

    Accepts either:
      - float / int (Excel native): "1871.01" stored as 1871.01,
        "1871.10" stored as 1871.10. Distinguishable because the
        fractional parts are different IEEE-754 numbers; recover month
        via `round((val - year) * 100)`.
      - string: honours the prompt convention — "1871.1" → January
        (single-digit fractional = single-digit month), "1871.10" →
        October (two-digit fractional = two-digit month). No padding
        guesswork; the string already tells us the intent.

    Anchors the date at month-end so the index aligns with the rest of
    the pipeline's monthly-cadence series (e.g. ifo, BLS).
    """
    if raw is None:
        return None
    # Empty-cell sentinels.
    if isinstance(raw, float) and pd.isna(raw):
        return None
    # String path — honour the string's literal width.
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return None
        if "." not in s:
            # Year-only (unlikely for Shiller, but tolerate).
            try:
                year = int(s)
            except ValueError:
                return None
            month = 12  # treat as end-of-year
        else:
            ystr, mstr = s.split(".", 1)
            try:
                year = int(ystr)
                # "1" → Jan, "10" → Oct, "12" → Dec. Single-digit
                # fractional is a single-digit month per the documented
                # convention; no auto-padding.
                month = int(mstr)
            except ValueError:
                return None
    else:
        # Numeric path — float or int.
        try:
            val = float(raw)
        except (TypeError, ValueError):
            return None
        if pd.isna(val):
            return None
        year = int(val)
        frac = val - year
        # frac for .01 is ~0.01, for .10 is ~0.10, for .12 is ~0.12.
        # Multiply by 100 and round to nearest int — handles the float
        # noise on 0.01-style values cleanly.
        month = int(round(frac * 100))
        # Sanity: if the workbook ever ships YYYY.M-as-fraction (eg.
        # 1871.5 meaning mid-year), this would mis-recover. Shiller has
        # never done that, but trap the out-of-range case.
        if month == 0:
            # `1871.0` exactly → treat as January.
            month = 1
    if not (1 <= month <= 12):
        return None
    if year < 1700 or year > 2200:
        return None
    return pd.Timestamp(year=year, month=month, day=1) + pd.offsets.MonthEnd(0)


# ---------------------------------------------------------------------------
# WORKBOOK PARSER
# ---------------------------------------------------------------------------

def _read_biff_sheet_with_xlrd(
    xlsx_bytes: bytes,
    sheet_name: str,
    header_row: int,
) -> pd.DataFrame | None:
    """Read one sheet of a legacy BIFF .xls workbook via xlrd directly,
    bypassing pandas (modern pandas — 2.0+ — refuses to use xlrd<2.0
    through `pd.read_excel`, but xlrd<2.0 is the only release that can
    still read .xls). We read the raw cells via xlrd and assemble the
    DataFrame ourselves to keep the dispatch transparent."""
    try:
        import xlrd  # type: ignore
    except ImportError as e:
        print(f"    [Shiller] xlrd not installed; cannot read BIFF .xls ({e})")
        return None
    try:
        book = xlrd.open_workbook(file_contents=xlsx_bytes)
        sheet = book.sheet_by_name(sheet_name)
    except Exception as e:
        print(f"    [Shiller] xlrd open/sheet failed: {type(e).__name__}: {e}")
        return None
    if sheet.nrows <= header_row:
        print(
            f"    [Shiller] sheet {sheet_name!r} has {sheet.nrows} rows; "
            f"header row {header_row} is out of range"
        )
        return None
    header = [sheet.cell_value(header_row, c) for c in range(sheet.ncols)]
    rows = [
        [sheet.cell_value(r, c) for c in range(sheet.ncols)]
        for r in range(header_row + 1, sheet.nrows)
    ]
    return pd.DataFrame(rows, columns=header)


def _parse_data_sheet(xlsx_bytes: bytes) -> pd.DataFrame | None:
    """Parse the "Data" sheet of ie_data.xls(x) into a date-indexed
    DataFrame whose columns are the Shiller header names (e.g. "CAPE",
    "S&P Comp. P", "Dividend D", ...). Returns None on parse failure.

    Dispatches by file magic: BIFF (legacy OLE2 .xls — Yale's current
    delivery) goes through xlrd directly (modern pandas refuses to use
    xlrd<2.0, but xlrd<2.0 is the only release that can read .xls);
    xlsx (ZIP) goes through openpyxl via pandas as normal.

    Cached at the wrapper level (_resolve_data_frame); this function is
    pure and re-callable but the cache means it only runs once per
    process."""
    if xlsx_bytes.startswith(_BIFF_MAGIC):
        df = _read_biff_sheet_with_xlrd(
            xlsx_bytes, _DATA_SHEET_NAME, _DATA_HEADER_ROW
        )
        if df is None:
            return None
    elif xlsx_bytes.startswith(_XLSX_MAGIC):
        try:
            df = pd.read_excel(
                io.BytesIO(xlsx_bytes),
                sheet_name=_DATA_SHEET_NAME,
                header=_DATA_HEADER_ROW,
                engine="openpyxl",
            )
        except Exception as e:
            print(f"    [Shiller] read_excel (openpyxl) failed: {type(e).__name__}: {e}")
            return None
    else:
        head = xlsx_bytes[:32].replace(b"\n", b" ")
        print(f"    [Shiller] unrecognised workbook magic: {head!r}")
        return None

    if df.empty:
        print("    [Shiller] Data sheet parsed as empty")
        return None

    # Normalise the column index — strip whitespace, drop unnamed
    # spillover columns that openpyxl manufactures for empty header cells.
    df.columns = [str(c).strip() for c in df.columns]
    df = df.loc[:, [c for c in df.columns if c and not c.startswith("Unnamed")]]

    # Locate the Date column. Shiller's header is exactly "Date".
    if "Date" not in df.columns:
        print(
            f"    [Shiller] 'Date' column not found in Data sheet. "
            f"Columns seen: {list(df.columns)[:12]}..."
        )
        return None

    dates = df["Date"].map(_parse_shiller_date)
    valid_mask = dates.notna()
    if not valid_mask.any():
        print("    [Shiller] no rows produced a valid Date — parser may be wrong")
        return None

    df = df.loc[valid_mask].copy()
    df.index = pd.DatetimeIndex(dates.loc[valid_mask].tolist())
    df = df.drop(columns=["Date"])
    df = df[~df.index.duplicated(keep="first")].sort_index()
    return df


def _resolve_data_frame() -> pd.DataFrame | None:
    """Cached: download + parse the Data sheet exactly once per process."""
    global _DATA_FRAME_CACHE
    if _DATA_FRAME_CACHE is not None:
        return _DATA_FRAME_CACHE
    body = _resolve_workbook_bytes()
    if body is None:
        return None
    parsed = _parse_data_sheet(body)
    if parsed is not None:
        _DATA_FRAME_CACHE = parsed
    return parsed


# ---------------------------------------------------------------------------
# SERIES FETCH
# ---------------------------------------------------------------------------

def fetch_series_as_pandas(
    series_id: str,
    col_name: str | None = None,
) -> pd.Series | None:
    """Fetch one Shiller series and return a date-indexed pd.Series, or None.

    series_id : header from the Data sheet, e.g. "CAPE", "S&P Comp. P",
                "Dividend D", "Earnings E", "CPI", "Long Interest Rate GS10".
    col_name  : optional name for the returned Series (default = series_id).

    Returns None on download / parse failure (logged to stdout for
    pipeline.log capture)."""
    df = _resolve_data_frame()
    if df is None:
        return None
    if series_id not in df.columns:
        # Tolerate trivial whitespace mismatches and try a normalised
        # lookup before giving up.
        norm = {c.strip(): c for c in df.columns}
        if series_id.strip() in norm:
            series_id = norm[series_id.strip()]
        else:
            print(
                f"    [Shiller] column {series_id!r} not in Data sheet. "
                f"Available: {list(df.columns)[:18]}"
            )
            return None
    s = pd.to_numeric(df[series_id], errors="coerce").dropna()
    if s.empty:
        print(f"    [Shiller] {series_id} parsed 0 numeric observations")
        return None
    s.name = col_name or series_id
    return s
