"""
sources/atlanta_fed.py
======================
Atlanta Fed GDPNow — real-time US Q-over-Q annualised real GDP growth
nowcast. The Atlanta Fed publishes the full forecast history as a single
Excel workbook on the GDPNow homepage.

Canonical primary source: the "GDPNow Model Data and Historical Forecasts"
workbook linked from https://www.atlantafed.org/cqer/research/gdpnow.
Two equivalent hosted paths exist (verified by scraping the homepage
2026-06-11):

  - https://www.atlantafed.org/-/media/Project/Atlanta/FRBA/Documents/
    cqer/researchcq/gdpnow/GDPTrackingModelDataAndForecasts.xlsx
  - https://www.frbatlanta.org/-/media/Documents/cqer/researchcq/gdpnow/
    GDPTrackingModelDataAndForecasts.xlsx (the homepage's "ReadMe" /
    historical-forecasts link target — wires through the same CDN)

Updated 5-10 times per quarter on weekdays following key data releases
(ISM, FT900, Retail Trade, Wholesale Trade, Construction, Housing Starts,
Durable Goods, Personal Income & Outlays, IP, Existing-Home Sales).
There's no clean fixed cadence — it's release-driven within a quarter and
silent between quarterly-tracking windows. We resample to weekly-Friday at
the calculator (compute_macro_market._calc_US_GDPNOW1) and forward-fill
between updates; this module returns the irregular raw observations.

Workbook layout (per the homepage's "How can I access historical
forecasts from the GDPNow model?" FAQ — 2026-06-11):
  - ReadMe              — column glossary + tab index
  - TrackingDeepArchives — 2011:Q3–2014:Q1 forecasts (pre-live model)
  - TrackingArchives     — 2014:Q2-onwards through the last "advance"
                           release; one row per forecast publication date,
                           one column per quarter being tracked.
  - TrackRecord          — final-nowcast vs BEA-advance comparison
  - (Per-quarter live tabs may also be present for the in-flight quarter.)

The headline GDPNow point estimate the homepage cites (e.g. "3.3% — 2026:Q2,
updated Jun 09 2026") is the most-recent non-null cell on a forecast-date
row in the TrackingArchives/Tracking tabs. Parser strategy: enumerate every
sheet, find ones with a `Date` (or `ForecastDate`) column whose values are
parseable timestamps, take the rightmost non-null GDPNow value per row as
that publication-date's headline nowcast, concatenate across all sheets,
de-duplicate keeping the most recent observation.

Wired §3.1.4 (2026-06-11) as the first §3.1.4 nowcast fetcher — EU_NOWCAST1
shipped earlier this session as a Phase E composite of already-wired inputs.
"""

from __future__ import annotations

import io
import pathlib
import time

import pandas as pd
import requests

_LIBRARY_CSV = pathlib.Path(__file__).parent.parent / "data" / "macro_library_atlanta_fed.csv"

# Canonical URLs — verified 2026-06-11 by scraping the GDPNow homepage.
# Both paths serve the same xlsx via the FRBA media CDN; we try them in
# order so a future path rename only needs one mirror updated to keep the
# pipeline alive.
GDPNOW_XLSX_HOSTS = [
    "https://www.atlantafed.org/-/media/Project/Atlanta/FRBA/Documents/cqer/researchcq/gdpnow/GDPTrackingModelDataAndForecasts.xlsx",
    "https://www.frbatlanta.org/-/media/Documents/cqer/researchcq/gdpnow/GDPTrackingModelDataAndForecasts.xlsx",
]

# Browser-like UA — the FRBA CDN 403s the default python-requests UA on
# repeated hits.
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

# Tabs that are explicitly NOT forecast-by-date series — we skip them.
# (Cheap robustness against a future tab being added that happens to have a
# Date column but isn't a vintage track.)
_SKIP_SHEETS = {"ReadMe", "TrackRecord", "Factor", "Glossary"}


# ---------------------------------------------------------------------------
# LIBRARY LOADER
# ---------------------------------------------------------------------------

def load_library() -> list[dict]:
    """Load Atlanta Fed indicator definitions from macro_library_atlanta_fed.csv."""
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
            "source":       "AtlantaFed",
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
    """Download the GDPNow xlsx from the canonical FRBA URL with mirror fallback.

    Returns the raw bytes or None on hard failure. Logs every attempt for
    pipeline.log capture. Cached per process via _resolve_workbook_bytes()."""
    last_exc: Exception | None = None
    for attempt in range(retries):
        for host in GDPNOW_XLSX_HOSTS:
            try:
                resp = requests.get(host, headers=_HEADERS, timeout=timeout)
                if resp.status_code != 200:
                    print(f"    [AtlantaFed HTTP {resp.status_code}] {host}")
                    continue
                body = resp.content
                if not body:
                    print(f"    [AtlantaFed] {host}: empty body")
                    continue
                if not body.startswith(_XLSX_MAGIC):
                    head = body[:32].replace(b"\n", b" ")
                    print(
                        f"    [AtlantaFed] {host}: not an xlsx — "
                        f"first 32 bytes: {head!r}"
                    )
                    continue
                print(
                    f"    [AtlantaFed] resolved xlsx ({len(body):,} bytes) via {host}"
                )
                return body
            except requests.Timeout:
                print(f"    [AtlantaFed timeout] {host}")
                last_exc = TimeoutError(f"timeout on {host}")
                continue
            except requests.RequestException as e:
                print(f"    [AtlantaFed request error] {host}: {e}")
                last_exc = e
                continue
        wait = 2 ** attempt
        if attempt + 1 < retries:
            print(f"    [AtlantaFed] all hosts failed — backing off {wait}s")
            time.sleep(wait)
    print(
        f"    [AtlantaFed FAIL] {retries} attempts × {len(GDPNOW_XLSX_HOSTS)} host(s) "
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
    """Locate the publication-date column in a tracking sheet.

    The Atlanta Fed labels it variously across tabs — `Date`, `Forecast Date`,
    `ForecastDate`, `Vintage`, sometimes a leading unnamed column. We accept
    any column whose name (case-insensitive, whitespace-stripped) starts with
    'date', 'forecast date', 'vintage', or whose values parse > 50% as
    timestamps."""
    # Header-name pass first — cheap and unambiguous when it works.
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
    """From one tracking sheet, build a (publication_date -> latest GDPNow)
    Series.

    Each row is one forecast publication. Columns to the right of the Date
    column hold the GDPNow point estimate for whichever quarter was being
    tracked at the time. The "headline" value cited on the homepage is the
    rightmost non-null numeric cell on that row — i.e. the latest tracked
    quarter's forecast as of the publication date. Pre-live quarters fill
    one column at a time, so the rightmost-non-null rule recovers the
    correct vintage without needing per-quarter column mapping (which would
    break every time the workbook adds a new quarter)."""
    date_col = _find_date_column(df)
    if date_col is None:
        return None
    dates = pd.to_datetime(df[date_col], errors="coerce")
    valid = dates.notna()
    if not valid.any():
        return None
    df2 = df.loc[valid].copy()
    dates = dates.loc[valid]

    # Candidate value columns: everything except the date column. Coerce
    # to numeric; non-numeric columns (notes, etc.) silently fall out.
    value_cols = [c for c in df2.columns if c != date_col]
    if not value_cols:
        return None
    numeric = df2[value_cols].apply(pd.to_numeric, errors="coerce")
    # Drop columns that are entirely NaN — they don't carry signal and
    # confuse the rightmost-non-null pick when the sheet has trailing
    # metadata columns.
    numeric = numeric.dropna(axis=1, how="all")
    if numeric.empty:
        return None

    # Rightmost non-null per row.
    def _row_last(row):
        nonnull = row.dropna()
        if nonnull.empty:
            return float("nan")
        return float(nonnull.iloc[-1])

    values = numeric.apply(_row_last, axis=1)
    s = pd.Series(values.values, index=pd.DatetimeIndex(dates.values))
    s = s.dropna()
    # Plausibility guardrail — the GDPNow point estimate has historically
    # ranged ~-35% (2020-Q2 pandemic) to ~+35% (2020-Q3 rebound). Anything
    # outside [-50, +50] is almost certainly a cell that isn't a growth-rate
    # reading at all (e.g. a contribution-to-growth subcomponent that
    # snuck through). Filter rather than fail so a single anomalous row
    # doesn't poison the whole series.
    s = s[(s >= -50.0) & (s <= 50.0)]
    return s if not s.empty else None


def _parse_workbook(xlsx_bytes: bytes) -> pd.Series | None:
    """Parse every plausible tracking sheet, concatenate the headline
    series, de-duplicate keeping the most recent observation per
    publication date.

    Returns None on hard parse failure (no usable sheet)."""
    try:
        xf = pd.ExcelFile(io.BytesIO(xlsx_bytes), engine="openpyxl")
    except Exception as e:
        print(f"    [AtlantaFed] ExcelFile open failed: {type(e).__name__}: {e}")
        return None

    pieces: list[pd.Series] = []
    sheets_used: list[str] = []
    for sheet in xf.sheet_names:
        if sheet in _SKIP_SHEETS:
            continue
        try:
            df = xf.parse(sheet)
        except Exception as e:
            print(f"    [AtlantaFed] sheet {sheet!r} read failed: {e}")
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
            f"    [AtlantaFed] no usable tracking sheets found in workbook "
            f"(sheets seen: {xf.sheet_names})"
        )
        return None

    print(f"    [AtlantaFed] parsed {len(pieces)} sheet(s): {sheets_used}")
    combined = pd.concat(pieces)
    # Same publication date can appear in two sheets (e.g. a current-quarter
    # tab overlaps a TrackingArchives row that closed out). Keep the last
    # one — the workbook is written so the later tab supersedes.
    combined = combined[~combined.index.duplicated(keep="last")].sort_index()
    return combined


# ---------------------------------------------------------------------------
# SERIES FETCH
# ---------------------------------------------------------------------------

def fetch_series_as_pandas(
    series_id: str,
    col_name: str | None = None,
) -> pd.Series | None:
    """Fetch the GDPNow headline nowcast series, return a date-indexed pd.Series.

    series_id : currently only `gdpnow_us_qoq_saar` is wired. Other ids are
                accepted but log a clear "unknown series" line and return None
                — leaves room to add subcomponent columns later without
                breaking the existing wiring.
    col_name  : optional name for the returned Series (default = series_id).

    Returns None on download / parse failure (logged to stdout for
    pipeline.log capture)."""
    sid = series_id.strip()
    if sid != "gdpnow_us_qoq_saar":
        print(
            f"    [AtlantaFed] unknown series_id {sid!r} — only "
            f"'gdpnow_us_qoq_saar' is wired today"
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
