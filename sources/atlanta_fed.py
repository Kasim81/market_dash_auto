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
updated Jun 09 2026") lives in two complementary places, and the parser reads
BOTH (see `_is_headline_sheet` for the tab allowlist):

  - TrackingArchives / TrackingDeepArchives — one row per forecast publication
    date with an explicit `GDP Nowcast` column. We select THAT column by name
    (`_find_nowcast_column`). These tabs only run through the *last quarter's*
    BEA advance release, so on their own they lag the in-flight quarter.
  - CurrentQtrEvolution — the live, in-flight-quarter evolution that has NOT yet
    rolled into TrackingArchives. Laid out as repeated `(Date, Major Releases,
    GDP*)` column blocks; `_extract_current_quarter_series` pairs each `Date*`
    column with the `GDP*` column sharing its suffix. This is where the
    most-recent nowcast (the homepage headline) actually is.

Series from all headline tabs are concatenated and de-duplicated keeping the
most recent observation per publication date, with the current-quarter tab
ordered last so it wins any date collision.

  ⚠ Two load-bearing rules, both learned from a 2026-06 regression:

  1. SELECT THE `GDP Nowcast` COLUMN BY NAME, never "rightmost non-null cell on
     the row". The Tracking tabs carry ~30 columns; to the right of `GDP Nowcast`
     sit Final Sales, Advance Estimate, Days-until-advance and Forecast Error.
     Once the BEA advance publishes, a rightmost-non-null pick grabs
     `Forecast Error` — which is how a ~0.75 forecast-error briefly shipped as
     the headline. The rightmost-non-null path survives only as a last-resort
     fallback for an unknown future layout (`_extract_headline_series_from_sheet`
     step 3).
  2. The tab allowlist is load-bearing, not cosmetic. The workbook also carries
     ~20 subcomponent / contribution / model-internal tabs (Consumption,
     Equipment, …, StateLocal, Contributions, ChangeInContributions, Factor*,
     PseudoRT*, Table/TableCont). Several have a Date column, so an "enumerate
     every sheet" strategy ingested them too — and a trailing subcomponent tab
     (e.g. StateLocal) overwrote the true headline for the most-recent dates,
     shipping a bogus ~24% US_GDPNOW1 nowcast (real value ~3.3%). Allowlist >
     denylist because the workbook gains new component/quarter tabs over time;
     naming the few tabs we trust is the only stable rule.

Wired §3.1.4 (2026-06-11) as the first §3.1.4 nowcast fetcher — EU_NOWCAST1
shipped earlier this session as a Phase E composite of already-wired inputs.
"""

from __future__ import annotations

import io
import pathlib
import re

import pandas as pd

from sources.base import fetch_with_backoff

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

# Per-quarter live-tab pattern — future-proofing in case the Atlanta Fed ever
# splits the in-flight quarter into its own tab. Matches a year+quarter token
# once whitespace / ":" / "_" / "-" separators are stripped, e.g. "2026Q2",
# "2026:Q2", "2026 Q2", "Q2 2026", "Q2-2026".
_QUARTER_TAB_RE = re.compile(r"^(?:(?:19|20)\d{2}q[1-4]|q[1-4](?:19|20)\d{2})$")


def _is_headline_sheet(name: str) -> bool:
    """True only for tabs carrying the headline GDPNow point estimate keyed by
    forecast publication date — TrackingArchives (2014:Q2→), TrackingDeepArchives
    (2011:Q3–2014:Q1), the CurrentQtrEvolution live-quarter tab, and any future
    per-quarter live tab.

    Everything else in the workbook is excluded by omission: subcomponent
    forecasts (Consumption/Equipment/…/StateLocal), contribution-to-growth tabs
    (Contributions/ChangeInContributions/ContribArchives), model internals
    (Factor*/PseudoRT*/ChartCalculation) and the display tables (Table/TableCont).
    Note "TrackRecord" (the model-vs-BEA scorecard) does NOT match the
    "tracking" prefix, so it is correctly excluded."""
    low = str(name).strip().lower()
    if low.startswith("tracking"):              # TrackingArchives / TrackingDeepArchives
        return True
    compact = re.sub(r"[\s:_\-]", "", low)      # "2026:Q2" / "Q2 2026" → "2026q2" / "q22026"
    if compact == "currentqtrevolution":        # live in-flight-quarter nowcast
        return True
    return bool(_QUARTER_TAB_RE.fullmatch(compact))


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
    # §2.C C3 (2026-07-09): shared retry engine in mirror mode with
    # accept="bytes"; the validate hook keeps the xlsx magic-byte sniff
    # (an HTML error page or truncated body moves to the next mirror).
    def _reject(body: bytes) -> str | None:
        if not body:
            return "empty body"
        if not body.startswith(_XLSX_MAGIC):
            head = body[:32].replace(b"\n", b" ")
            return f"not an xlsx — first 32 bytes: {head!r}"
        return None

    body = fetch_with_backoff(
        list(GDPNOW_XLSX_HOSTS), label="AtlantaFed", accept="bytes",
        retries=retries, timeout=timeout, headers=_HEADERS, validate=_reject,
    )
    if body is not None:
        print(f"    [AtlantaFed] resolved xlsx ({len(body):,} bytes)")
    return body


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

_TS_MIN = pd.Timestamp("1900-01-01")
_TS_MAX = pd.Timestamp("2200-12-31")


def _safe_to_datetime(series: pd.Series) -> pd.Series:
    """`pd.to_datetime(s, errors='coerce')` hardened against the pandas 2.x
    edge where `dateutil` produces a Python datetime with a year outside
    pandas' ~[1677, 2262] nanosecond Timestamp range — the bulk coerce path
    can either surface `OutOfBoundsDatetime` instead of NaT (newer ns-default
    builds) or pass it through as an out-of-range Timestamp that blows up
    later at DatetimeIndex construction (older builds with wider resolution).
    The Atlanta Fed GDPTracking xlsx contains a junk row at year 6703 that
    hits exactly this case. Belt-and-braces: try/except around the bulk
    coerce, fall back to per-element parsing on failure, then post-filter
    anything outside [1900, 2200] to NaT."""
    try:
        parsed = pd.to_datetime(series, errors="coerce")
    except (pd.errors.OutOfBoundsDatetime, ValueError, TypeError):
        parsed = series.apply(lambda v: pd.to_datetime(v, errors="coerce"))
    if parsed.dtype.kind == "M":
        out_of_range = (parsed < _TS_MIN) | (parsed > _TS_MAX)
        if out_of_range.any():
            parsed = parsed.mask(out_of_range, pd.NaT)
    return parsed


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
            parsed = _safe_to_datetime(col)
        except Exception:
            continue
        if parsed.notna().sum() >= max(5, int(len(col) * 0.5)):
            return c
    return None


# Plausibility guardrail — the GDPNow point estimate has historically ranged
# ~-35% (2020-Q2 pandemic) to ~+35% (2020-Q3 rebound). Anything outside
# [-50, +50] is almost certainly a cell that isn't a growth-rate reading at all
# (e.g. a contribution-to-growth subcomponent that snuck through). Filter rather
# than fail so a single anomalous row doesn't poison the whole series.
_PLAUSIBLE_LO, _PLAUSIBLE_HI = -50.0, 50.0


def _clamp_plausible(s: pd.Series) -> pd.Series:
    return s[(s >= _PLAUSIBLE_LO) & (s <= _PLAUSIBLE_HI)]


def _find_nowcast_column(df: pd.DataFrame) -> str | None:
    """Locate the explicit headline GDPNow column in a tracking sheet.

    The TrackingArchives / TrackingDeepArchives tabs carry a dedicated
    ``GDP Nowcast`` column — that, not the rightmost cell on the row, is the
    headline point estimate. The columns to its right (Final Sales, Advance
    Estimate, Days until advance estimate, Forecast Error) are post-hoc /
    evaluation fields; a rightmost-non-null pick grabs ``Forecast Error`` once
    the BEA advance is published, which is how a ~0.75 forecast-error once
    shipped as the headline nowcast."""
    for c in df.columns:
        n = re.sub(r"[\s_]", "", str(c).strip().lower())
        if n in ("gdpnowcast", "gdpnow"):
            return c
    return None


def _extract_current_quarter_series(df: pd.DataFrame) -> pd.Series | None:
    """Parse the ``CurrentQtrEvolution`` tab — the live, in-flight-quarter
    nowcast that has NOT yet rolled into TrackingArchives (which ends at the
    prior quarter's advance release).

    Layout: repeated ``(Date, Major Releases, GDP*)`` column blocks laid out
    side by side (pandas de-duplicates the repeated headers to ``Date.1`` /
    ``GDP*.1`` / …). Each block is a slice of the same quarter's evolution by
    publication date; ``GDP*`` is the nowcast. We pair every ``Date*`` column
    with the ``GDP*`` column sharing its suffix and union the observations.
    Returns None when the sheet is not this layout (no ``Date`` + ``GDP*``
    column pair), so non-CurrentQtrEvolution tabs fall through untouched."""
    def _base(name: object) -> str:
        return re.sub(r"\.\d+$", "", str(name)).strip().lower()

    def _suffix(name: object) -> str:
        m = re.search(r"\.(\d+)$", str(name))
        return m.group(1) if m else ""

    date_cols = [c for c in df.columns if _base(c) == "date"]
    val_by_suffix = {_suffix(c): c for c in df.columns if _base(c) in ("gdp*", "gdp")}
    if not date_cols or not val_by_suffix:
        return None

    pieces: list[pd.Series] = []
    for dc in date_cols:
        vc = val_by_suffix.get(_suffix(dc))
        if vc is None:
            continue
        dates = _safe_to_datetime(df[dc])
        values = pd.to_numeric(df[vc], errors="coerce")
        mask = dates.notna() & values.notna()
        if mask.any():
            pieces.append(pd.Series(
                values[mask].values, index=pd.DatetimeIndex(dates[mask].values)
            ))
    if not pieces:
        return None
    s = pd.concat(pieces)
    s = s[~s.index.duplicated(keep="last")].sort_index()
    s = _clamp_plausible(s)
    return s if not s.empty else None


def _extract_headline_series_from_sheet(df: pd.DataFrame) -> pd.Series | None:
    """From one headline sheet, build a (publication_date -> GDPNow) Series.

    Three layouts, tried in order:
      1. CurrentQtrEvolution — paired ``Date``/``GDP*`` blocks (live quarter).
      2. TrackingArchives / TrackingDeepArchives — a row per publication date
         with an explicit ``GDP Nowcast`` column; select THAT column by name
         (never rightmost-non-null, which grabs ``Forecast Error``).
      3. Fallback — rightmost non-null numeric on the row, only for an unknown
         future layout carrying neither marker. Gated to allowlisted tabs so a
         stray subcomponent column can't poison the series."""
    # 1) Live current-quarter tab (paired Date/GDP* blocks).
    cq = _extract_current_quarter_series(df)
    if cq is not None:
        return cq

    date_col = _find_date_column(df)
    if date_col is None:
        return None
    dates = _safe_to_datetime(df[date_col])
    valid = dates.notna()
    if not valid.any():
        return None
    df2 = df.loc[valid].copy()
    dates = dates.loc[valid]

    # 2) Explicit headline column (Tracking archives).
    nowcast_col = _find_nowcast_column(df2)
    if nowcast_col is not None:
        values = pd.to_numeric(df2[nowcast_col], errors="coerce")
        s = pd.Series(values.values, index=pd.DatetimeIndex(dates.values)).dropna()
        s = _clamp_plausible(s)
        return s if not s.empty else None

    # 3) Fallback: rightmost non-null numeric per row. Candidate value columns
    # are everything except the date column; non-numeric columns (notes, etc.)
    # silently fall out, and all-NaN columns are dropped so trailing metadata
    # doesn't skew the rightmost pick.
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
    s = pd.Series(values.values, index=pd.DatetimeIndex(dates.values)).dropna()
    s = _clamp_plausible(s)
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

    archive_pieces: list[pd.Series] = []
    current_pieces: list[pd.Series] = []
    sheets_used: list[str] = []
    skipped: list[str] = []
    for sheet in xf.sheet_names:
        if not _is_headline_sheet(sheet):
            skipped.append(sheet)
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
        compact = re.sub(r"[\s:_\-]", "", str(sheet).strip().lower())
        if compact == "currentqtrevolution":
            current_pieces.append(s)
        else:
            archive_pieces.append(s)
        sheets_used.append(sheet)

    if skipped:
        print(f"    [AtlantaFed] skipped non-headline tabs: {skipped}")
    # Archives first, current-quarter tab last: on a duplicate publication date
    # the live current-quarter reading must supersede the archived one.
    pieces = archive_pieces + current_pieces
    if not pieces:
        print(
            f"    [AtlantaFed] no usable headline tracking sheets found in "
            f"workbook (sheets seen: {xf.sheet_names}) — the headline-tab "
            f"allowlist (_is_headline_sheet) may need updating for a workbook "
            f"layout change"
        )
        return None

    print(f"    [AtlantaFed] parsed {len(pieces)} sheet(s): {sheets_used}")
    combined = pd.concat(pieces)
    # Same publication date can appear in two sheets (e.g. a current-quarter
    # tab overlaps a TrackingArchives row that closed out). Keep the last
    # one — pieces are ordered so the current-quarter tab supersedes.
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
