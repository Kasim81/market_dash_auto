"""
sources/treasury.py
===================
US Treasury "Daily Treasury Par Yield Curve Rates" source module.

The par-yield curve is the cleanest independent macro cross-check the repo
has (the audit matched repo ^TNX/^TYX/^FVX against Treasury par to <0.5bp),
and FACTIQ_AUDIT_PLAN.md §11 names it the HIGH-PRIORITY direct-wire. It is
keyless and CI-friendly, so — per the plan's core constraint — we wire the
Treasury feed's OWN public endpoint directly rather than routing through
FactIQ.

WHY DIRECT, NOT VIA FACTIQ (read FACTIQ_AUDIT_PLAN.md §11):
    FactIQ's data is only reachable through its OAuth-gated MCP inside a
    Claude/Codex agent session — there is NO API key a headless GitHub
    Actions run can use, and the pipeline runs headless in CI. So every
    "replicate" bucket source (this one included) must call the upstream
    provider's own keyless public API. Do NOT call FactIQ from pipeline code.

FEED (verified live 2026-07-12, keyless, no User-Agent required):
    https://home.treasury.gov/resource-center/data-chart-center/
        interest-rates/daily-treasury-rates.csv/<YEAR>/all
        ?type=daily_treasury_yield_curve&field_tdr_date_value=<YEAR>

    Returns one CSV per calendar year. Header:
        Date,"1 Mo","1.5 Month","2 Mo","3 Mo","4 Mo","6 Mo",
             "1 Yr","2 Yr","3 Yr","5 Yr","7 Yr","10 Yr","20 Yr","30 Yr"
    Rows are MM/DD/YYYY business days, newest first. Data begins 1990.
    The set of tenor columns VARIES BY YEAR (2 Mo added 2018, 4 Mo added
    2022, 20 Yr dropped 1987-1993 & reintroduced 2020, etc.) — so the parser
    is robust to missing tenors: an absent column or an empty cell simply
    yields NaN for that tenor/date.

Indicator definitions live in data/macro_library_treasury.csv (one row per
tenor). Tenor -> feed-column mapping is authoritative HERE in TENOR_LABELS.

This module is side-effect-free (no CSV writing, no Sheets push) and mirrors
the sources/boe.py public shape: load_library() + fetch_series_as_pandas().

────────────────────────────────────────────────────────────────────────────
INTEGRATION SNIPPET (do NOT apply yet — for human review before wiring).
`treasury.fetch_series_as_pandas(series_id, start=, col_name=)` matches the
BoE signature exactly, so the coordinator wiring is identical to the BoE
wiring already in fetch_macro_economic.py. Add these four hooks:

  1. Top imports, beside the other `from sources import ... as ..._src` lines:
         from sources import treasury as treasury_src

  2. In load_all_indicators():
         indicators.extend(treasury_src.load_library())

  3. In build_snapshot_df()'s dispatch chain (copy the BoE branch/helper):
         elif src == "Treasury":
             got = _fetch_treasury_snapshot(indic, fetched_at)
     with a helper identical to _fetch_boe_snapshot but calling
     treasury_src.fetch_series_as_pandas (add TREASURY_DELAY = 0.6).

  4. In _history_for_indicator() (copy the BoE branch/helper):
         if src == "Treasury":
             return _fetch_treasury_history(indic)
     with a helper identical to _fetch_boe_history.
────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import io
import pathlib
from datetime import date, datetime

import pandas as pd

from sources.base import fetch_with_backoff


_LIBRARY_CSV = pathlib.Path(__file__).parent.parent / "data" / "macro_library_treasury.csv"

# Base of the per-year CSV endpoint. `{year}` is substituted twice (path + param).
FEED_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/"
    "interest-rates/daily-treasury-rates.csv/{year}/all"
)

# The par-yield curve begins in 1990 on this feed; earlier years return empty.
FEED_FIRST_YEAR = 1990
DEFAULT_HIST_START = "1990-01-01"

# Canonical library series_id  ->  exact CSV header label the feed uses.
# This is the single authoritative place mapping our tenor tokens to the
# provider's column names; macro_library_treasury.csv's `series_id` values
# must match these keys. The 1.5-Month tenor the feed also publishes is
# intentionally NOT tracked (not part of the standard constant-maturity set).
TENOR_LABELS: dict[str, str] = {
    "UST1MO":  "1 Mo",
    "UST2MO":  "2 Mo",
    "UST3MO":  "3 Mo",
    "UST4MO":  "4 Mo",
    "UST6MO":  "6 Mo",
    "UST1YR":  "1 Yr",
    "UST2YR":  "2 Yr",
    "UST3YR":  "3 Yr",
    "UST5YR":  "5 Yr",
    "UST7YR":  "7 Yr",
    "UST10YR": "10 Yr",
    "UST20YR": "20 Yr",
    "UST30YR": "30 Yr",
}

# Module-level cache: the full assembled wide DataFrame (all tenors, all
# years) is fetched once per run, then sliced per tenor by the coordinator's
# 13 calls. Mirrors the ifo workbook cache in fetch_macro_economic.py.
_CURVE_CACHE: pd.DataFrame | None = None


# ---------------------------------------------------------------------------
# LIBRARY LOADER
# ---------------------------------------------------------------------------

def load_library() -> list[dict]:
    """Load Treasury par-yield tenor definitions from macro_library_treasury.csv."""
    if not _LIBRARY_CSV.exists():
        return []
    df = pd.read_csv(_LIBRARY_CSV, dtype=str, keep_default_na=False)
    df["sort_key"] = pd.to_numeric(df["sort_key"], errors="coerce").fillna(0)
    df = df.sort_values("sort_key")
    result = []
    for _, row in df.iterrows():
        result.append({
            "source":       "Treasury",
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
# PER-YEAR FETCH
# ---------------------------------------------------------------------------

def fetch_year_csv(
    year: int,
    retries: int = 5,
    backoff_base: int = 2,
    timeout: int = 30,
) -> str | None:
    """
    Fetch the raw daily par-yield CSV for one calendar year via the shared
    backoff helper. Returns the raw CSV body, or None on failure.
    """
    url = FEED_URL.format(year=year)
    params = {
        "type": "daily_treasury_yield_curve",
        "field_tdr_date_value": str(year),
        "page": "",
    }
    text = fetch_with_backoff(
        url, params=params, label=f"Treasury/{year}", accept_csv=True,
        retries=retries, backoff_base=backoff_base, timeout=timeout,
    )
    if not isinstance(text, str):
        return None
    return text


# ---------------------------------------------------------------------------
# CSV PARSING
# ---------------------------------------------------------------------------

def parse_year_csv(text: str, year: int | None = None) -> pd.DataFrame:
    """
    Parse one year's CSV into a date-indexed DataFrame whose columns are the
    canonical tenor tokens (keys of TENOR_LABELS). Missing tenors → absent
    column; empty cells → NaN. Returns an empty DataFrame on any problem.
    """
    if not text or not text.strip():
        return pd.DataFrame()
    # Guard against an HTML error page slipping through.
    if text.lstrip()[:14].lower().startswith("<!doctype html") or \
       text.lstrip()[:5].lower() == "<html":
        return pd.DataFrame()

    try:
        raw = pd.read_csv(io.StringIO(text))
    except Exception as e:
        print(f"  [Treasury/{year}] CSV parse failed: {e}")
        return pd.DataFrame()

    if raw.empty or "Date" not in raw.columns:
        return pd.DataFrame()

    # Parse the Date column (feed uses MM/DD/YYYY).
    idx = pd.to_datetime(raw["Date"], format="%m/%d/%Y", errors="coerce")
    raw = raw.loc[idx.notna()].copy()
    idx = idx[idx.notna()]

    out = pd.DataFrame(index=pd.DatetimeIndex(idx.values))
    # Map each canonical tenor whose feed-label column is present this year.
    label_to_token = {label: token for token, label in TENOR_LABELS.items()}
    for col in raw.columns:
        token = label_to_token.get(str(col).strip())
        if token is None:
            continue  # Date column, 1.5 Month, or an unknown future tenor.
        out[token] = pd.to_numeric(raw[col].values, errors="coerce")

    out = out.sort_index()
    # Drop duplicate dates if any (keep last).
    out = out[~out.index.duplicated(keep="last")]
    return out


# ---------------------------------------------------------------------------
# FULL-HISTORY ASSEMBLY (cached)
# ---------------------------------------------------------------------------

def fetch_all_tenors(
    start: str = DEFAULT_HIST_START,
    end_year: int | None = None,
    use_cache: bool = True,
    _fetcher=fetch_year_csv,
) -> pd.DataFrame:
    """
    Fetch and assemble the full daily par-yield history (all tenors) into a
    single date-indexed wide DataFrame, one column per canonical tenor token.

    Fetched once and cached at module level so the coordinator's 13 per-tenor
    calls reuse one network pass. `_fetcher` is injectable purely for testing
    (e.g. to feed pre-downloaded bytes); production uses fetch_year_csv.
    """
    global _CURVE_CACHE
    if use_cache and _CURVE_CACHE is not None:
        return _CURVE_CACHE

    try:
        start_year = datetime.strptime(start, "%Y-%m-%d").year
    except ValueError:
        start_year = FEED_FIRST_YEAR
    start_year = max(start_year, FEED_FIRST_YEAR)
    end_year = end_year or date.today().year

    frames: list[pd.DataFrame] = []
    for year in range(start_year, end_year + 1):
        text = _fetcher(year)
        if text is None:
            print(f"  [Treasury/{year}] no data (fetch failed) — skipping year")
            continue
        df = parse_year_csv(text, year)
        if not df.empty:
            frames.append(df)

    if not frames:
        curve = pd.DataFrame(columns=list(TENOR_LABELS.keys()))
    else:
        curve = pd.concat(frames, axis=0).sort_index()
        curve = curve[~curve.index.duplicated(keep="last")]
        # Preserve canonical tenor order for readability.
        curve = curve.reindex(
            columns=[t for t in TENOR_LABELS if t in curve.columns]
        )

    if use_cache:
        _CURVE_CACHE = curve
    return curve


def clear_cache() -> None:
    """Reset the module-level curve cache (mainly for tests)."""
    global _CURVE_CACHE
    _CURVE_CACHE = None


# ---------------------------------------------------------------------------
# PER-TENOR ACCESSOR (matches sources/boe.py signature)
# ---------------------------------------------------------------------------

def fetch_series_as_pandas(
    series_id: str,
    start: str = DEFAULT_HIST_START,
    col_name: str | None = None,
) -> pd.Series | None:
    """
    Return one tenor as a date-indexed pd.Series (NaNs dropped), or None if
    the tenor is unknown / has no data. `series_id` is a canonical tenor
    token (a key of TENOR_LABELS). Signature mirrors boe.fetch_series_as_pandas
    so the coordinator wiring is a copy of the BoE branch.
    """
    if series_id not in TENOR_LABELS:
        print(f"  [Treasury] unknown tenor id {series_id!r} — skipping")
        return None
    curve = fetch_all_tenors(start=start)
    if curve.empty or series_id not in curve.columns:
        return None
    s = curve[series_id].dropna()
    if s.empty:
        return None
    s = s[s.index >= pd.Timestamp(start)] if start else s
    if s.empty:
        return None
    s.name = col_name or series_id
    return s


# ---------------------------------------------------------------------------
# SELF-TEST
# ---------------------------------------------------------------------------

def _self_test() -> None:
    """
    Fetch the live feed, print the latest date + a few tenors, and sanity-check
    that the 10-Year par yield is in a plausible 0-10% range.

    NOTE on running this locally: the module fetches with normal TLS
    verification (correct for CI, where certs are valid). If your local machine
    sits behind a TLS-intercepting proxy, verified HTTPS will fail here even
    though the feed is fine — that is an environment artifact, not a feed
    problem. In that case, run fetch_all_tenors(_fetcher=<verify=False loader>)
    for a local-only demonstration (see the injectable `_fetcher` hook).
    """
    print("Treasury par-yield self-test — fetching live feed ...")
    curve = fetch_all_tenors(start="2024-01-01")
    if curve.empty:
        print("  FAIL: no data returned (network blocked or feed changed?).")
        return

    latest_date = curve.index.max()
    latest = curve.loc[latest_date]
    print(f"  Latest curve date: {latest_date.date()}")
    for token in ("UST3MO", "UST2YR", "UST10YR", "UST30YR"):
        if token in curve.columns:
            print(f"    {TENOR_LABELS[token]:>6} ({token}): {latest.get(token)}")

    ten = fetch_series_as_pandas("UST10YR", start="2024-01-01", col_name="USA_UST_10YR")
    if ten is None or ten.empty:
        print("  FAIL: 10Y series empty.")
        return
    ten_latest = float(ten.iloc[-1])
    ok = 0.0 <= ten_latest <= 10.0
    print(f"  10Y latest = {ten_latest:.2f}%  → sanity 0-10%: {'PASS' if ok else 'FAIL'}")
    print(f"  10Y series span: {ten.index.min().date()} .. {ten.index.max().date()} "
          f"({len(ten)} obs)")


if __name__ == "__main__":
    _self_test()
