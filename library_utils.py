"""
library_utils.py
================
Shared constants and helpers for the pipeline.

Contains:
  - Sort order dicts (asset class, region, subclass, sector, etc.)
  - INDICATOR_GROUP_ORDER / INDICATOR_SUB_GROUP_ORDER — display order for
    macro-market indicator groups and sub-groups (used by build_html.py,
    compute_macro_market.py, and any future consumers)
  - lib_sort_key() — sort key function for index_library.csv rows
  - COMP_FX_TICKERS — single authoritative currency → yfinance ticker map
  - COMP_FCY_PER_USD — set of indirect-quote currencies (1 USD = X FCY)

Imported by fetch_data.py, fetch_hist.py, build_html.py, and
compute_macro_market.py.  Do NOT duplicate these definitions elsewhere.
"""

# ---------------------------------------------------------------------------
# ASSET CLASS GROUP ORDER
# ---------------------------------------------------------------------------

ASSET_CLASS_GROUP = {
    "Equity":       1,
    "Fixed Income": 2,
    "Spread":       3,   # OAS / credit spread series (bps)
    "Rates":        3,   # yield series (bps) — same visual group as Spread
    "FX":           4,
    "Commodity":    5,
    "Crypto":       6,
    "Volatility":   7,
}

# ---------------------------------------------------------------------------
# REGION ORDER
# ---------------------------------------------------------------------------

REGION_ORDER = {
    "Global":               1,
    "Global ex-US/Canada":  1,
    "North America":        2,
    "UK":                   3,   # UK sits between NA and EU
    "Europe":               4,
    "Japan":                5,   # Japan sits between EU and EM
    "Emerging Markets":     6,
    "Asia Pacific":         7,
    "Asia ex Japan":        7,
    "Middle East & Africa": 8,
    "Latin America":        9,
}

# ---------------------------------------------------------------------------
# SUBCLASS ORDER MAPS
# ---------------------------------------------------------------------------

EQUITY_SUBCLASS_ORDER = {
    "Equity Broad":              1,
    "Equity Large Cap":          2,
    "Equity Large Cap (Value)":  2,
    "Equity Large Cap (Growth)": 2,
    "Equity Mid Cap":            3,
    "Equity Mid Cap (Growth)":   3,
    "Equity Mid Cap (Value)":    3,
    "Equity Small Cap":          4,
    "Equity Small Cap (Growth)": 4,
    "Equity Small Cap (Value)":  4,
    "Equity Sector":             5,
    "Equity Industry Group":     6,
    "Equity Industry":           7,
    "Factor":                    8,
    "Equity Factor":             8,
}

SECTOR_ORDER = {
    "Blend": 0, "Value": 1, "Growth": 2,
    "Consumer Staples": 10, "Health Care": 11, "Utilities": 12,
    "Industrials": 13, "Energy": 14, "Communication Services": 15,
    "Information Technology": 16, "Consumer Discretionary": 17,
    "Materials": 18, "Financials": 19, "Real Estate": 20,
    "Mega-Cap Tech / Growth": 30, "Equal Weight": 31,
    "Momentum": 32, "Dividend Growth": 33, "Quality": 34,
    "Dividend/Quality": 35, "Low Volatility": 36,
    "Dividend/Income": 37, "Broad Market": 38,
}

FI_SUBCLASS_ORDER = {
    "Bond Aggregate":              1,
    "Global Aggregate":            1,
    "Govt Bond":                   2,
    "Government":                  2,
    "Government Short":            2,
    "Government Inflation-Linked": 3,
    "Inflation-Linked":            3,
    "EM Bond":                     4,
    "Emerging Market Debt":        4,
    "Corp IG":                     5,
    "Corp HY":                     6,
    "Credit Spread":               7,
}

MATURITY_ORDER = {
    "Broad": 1, "Short (1-3yr)": 2, "Long (10yr+)": 3,
}

COMMODITY_GROUP_ORDER = {
    "Energy": 1, "Precious Metals": 2, "Industrial Metals": 3,
    "Agriculture": 4, "Livestock": 5, "Broad": 6,
    "Commodity": 7,
}

VOL_SUBCLASS_ORDER = {
    "Equity Volatility": 1, "Tail Risk": 2,
    "Fixed Income Volatility": 3, "Commodity Volatility": 4,
}

RATES_SUBCLASS_ORDER = {
    "Government Yield": 1, "Breakeven Inflation": 2,
    "Credit Spread": 3, "Policy Rate": 4, "Yield Curve": 5,
}

SPREAD_SUBCLASS_ORDER = {
    "Corp IG": 1, "Credit Spread": 2, "Corp HY": 3,
}

# ---------------------------------------------------------------------------
# INDICATOR GROUP / SUB-GROUP ORDER
# Controls display order in build_html.py (indicator explorer sidebar)
# and any future consumers.  Follows the same pattern as ASSET_CLASS_GROUP,
# REGION_ORDER, etc.
# ---------------------------------------------------------------------------

INDICATOR_GROUP_ORDER = {
    "US":               1,
    "UK":               2,
    "Europe":           3,
    "Japan":            4,
    "Asia":             5,
    "Global":           6,
    "FX & Commodities": 7,
}

INDICATOR_SUB_GROUP_ORDER = {
    # ── US ──
    "Equity - Growth":          1,
    "Equity - Factor (Style)":  2,
    "Equity - Factor (Size)":   3,
    "CrossAsset - Growth":      4,
    "CrossAsset - Inflation":   5,
    "Credit":                   6,
    "Rates - Growth":           7,
    "Rates - Inflation":        8,
    "Rates":                    9,
    "Volatility":              10,
    "Macro":                   11,
    "Macro - Survey":          12,
    "Mmtm - Equity":           13,
    "Mmtm - CrossAsset":       14,
    "Mmtm - Credit":           15,
    "Mmtm - Volatility":       16,
    # ── UK ──  (shared labels reuse the same sort key above)
    # ── Europe ──
    "CLI":                     17,
    # ── Asia ──
    "China - Equity (Growth)":        18,
    "China - Equity - Factor (Size)": 19,
    "China - Rates":                  20,
    "India - Equity - Factor (Size)": 21,
    "India - Rates":                  22,
    # ── FX & Commodities ──
    "China - FX Mmtm":         23,
    "India - FX Mmtm":         24,
    "Japan - FX Mmtm":         25,
    "Growth (China infra)":    26,
    "Growth (China broad)":    27,
    "Growth Mmtm":             28,
    "Inflation":               29,
}

# Sort order for the new "By Concept" sidebar view (§2.5).  Mirrors the canonical
# 17-concept taxonomy from forward_plan.md §2.4 step 1; ordered roughly by
# typical macro-strategist navigation priority (asset-class lenses first,
# then forward-looking signals, then real-economy aggregates, then financial
# plumbing and signal-construction concepts).
INDICATOR_CONCEPT_ORDER = {
    # Asset-class lenses
    "Equity":              1,
    "Rates / Yields":      2,
    "Credit / Spreads":    3,
    "Inflation":           4,
    # Forward-looking
    "Sentiment / Survey":  5,
    "Leading Indicators":  6,
    # Real economy
    "Growth":              7,
    "Labour":              8,
    "Consumer":            9,
    "Housing":            10,
    "Manufacturing":      11,
    "External / Trade":   12,
    # Financial / signal-construction
    "Money / Liquidity":  13,
    "Cross-Asset":        14,
    "FX":                 15,
    "Volatility":         16,
    "Momentum":           17,
}

# ---------------------------------------------------------------------------
# SORT KEY FUNCTION
# ---------------------------------------------------------------------------

def lib_sort_key(row) -> tuple:
    """Sort key for a raw index_library.csv row (works with both dict and Series)."""
    ac      = str(row.get("asset_class", ""))
    asc     = str(row.get("asset_subclass", ""))
    region  = str(row.get("region", ""))
    sector  = str(row.get("sector_style", ""))
    mat     = str(row.get("maturity_focus", ""))
    cg      = str(row.get("commodity_group", ""))
    name    = str(row.get("name", ""))

    g = ASSET_CLASS_GROUP.get(ac, 99)
    r = REGION_ORDER.get(region, 50)

    if ac == "Equity":
        s   = EQUITY_SUBCLASS_ORDER.get(asc, 50)
        sec = SECTOR_ORDER.get(sector, 50)
        # Industry Groups and Industries: sort by ticker (GICS code) instead of name
        if asc in ("Equity Industry Group", "Equity Industry"):
            ticker = str(row.get("ticker_yfinance_pr", "") or "")
            return (g, r, s, sec, ticker)
        return (g, r, s, sec, name)

    if ac == "Fixed Income":
        s = FI_SUBCLASS_ORDER.get(asc, 50)
        m = MATURITY_ORDER.get(mat, 50)
        return (g, r, s, m, name)

    if ac in ("Spread", "Rates"):
        s = SPREAD_SUBCLASS_ORDER.get(asc, RATES_SUBCLASS_ORDER.get(asc, 50))
        return (g, r, s, name)

    if ac == "FX":
        s = 1 if "Index" in asc else 2
        return (g, 0, s, name)

    if ac == "Commodity":
        cgn = COMMODITY_GROUP_ORDER.get(cg, 50)
        return (g, 0, cgn, name)

    if ac == "Crypto":
        return (g, 0, 0, name)

    if ac == "Volatility":
        s = VOL_SUBCLASS_ORDER.get(asc, 50)
        return (g, 0, s, name)

    return (g, r, 0, name)


# ---------------------------------------------------------------------------
# FX TICKER MAP  (single authoritative definition)
#
# Convention:
#   Direct quotes  (1 FCY = X USD) → NOT in COMP_FCY_PER_USD → multiply to get USD
#   Indirect quotes (1 USD = X FCY) → IN COMP_FCY_PER_USD → divide to get USD
#
# USX (US cents, e.g. agricultural futures) is handled separately in the
# fetch functions: divide by 100 then treat as USD — no FX entry needed.
# ---------------------------------------------------------------------------

COMP_FX_TICKERS = {
    # Direct quotes
    "GBP": "GBPUSD=X",
    "EUR": "EURUSD=X",
    "AUD": "AUDUSD=X",
    # Indirect quotes
    "JPY": "USDJPY=X",
    "CNY": "CNY=X",
    "INR": "INR=X",
    "KRW": "KRW=X",
    "TWD": "TWD=X",
    "CAD": "USDCAD=X",
    "BRL": "USDBRL=X",
    "HKD": "USDHKD=X",
    "MXN": "USDMXN=X",
    "IDR": "USDIDR=X",
    "RUB": "USDRUB=X",
    "SAR": "USDSAR=X",
    "ZAR": "USDZAR=X",
    "TRY": "USDTRY=X",
    "ARS": "USDARS=X",
}

# Indirect-quote currencies: 1 USD = X FCY → divide price by FX rate to get USD
COMP_FCY_PER_USD = {
    "JPY", "CNY", "INR", "KRW", "TWD",
    "CAD", "BRL", "HKD", "MXN", "IDR",
    "RUB", "SAR", "ZAR", "TRY", "ARS",
}


# ---------------------------------------------------------------------------
# GOOGLE SHEETS TAB MANAGEMENT
# ---------------------------------------------------------------------------
# Single source of truth for Sheets-side tab state. Every writer module in the
# pipeline imports and uses these constants.
# ---------------------------------------------------------------------------

# Tabs that must NEVER be overwritten by pipeline code. `market_data` is the
# simple-pipeline output consumed by the downstream `trigger.py`; `sentiment_data`
# is a legacy tab kept in the deletion set but guarded against writes in case
# any lingering caller tries to push to it.
SHEETS_PROTECTED_TABS = frozenset({"market_data", "sentiment_data"})

# Tabs that are actively written by the pipeline. Used by Phase G audits and
# by the legacy-tab cleanup to know which titles are "in-use".
SHEETS_ACTIVE_TABS = frozenset({
    "market_data",           # fetch_data.py (simple pipeline)
    "market_data_comp",      # fetch_data.py (comp pipeline snapshot)
    "market_data_comp_hist", # fetch_hist.py (weekly comp history)
    "macro_market",          # compute_macro_market.py
    "macro_market_hist",     # compute_macro_market.py
    "macro_economic",        # fetch_macro_economic.py (unified snapshot)
    "macro_economic_hist",   # fetch_macro_economic.py (unified history)
})

# Legacy tabs to delete on every run. These were outputs of older phases that
# have been consolidated or superseded; an Apps Script on the Sheet side may
# recreate some, so we sweep them unconditionally.
SHEETS_LEGACY_TABS_TO_DELETE = frozenset({
    "Market Data",         # space-variant duplicate of market_data
    "sentiment_data",      # consolidated into macro_us + macro_intl
    "macro_surveys",       # consolidated into macro_us
    "macro_surveys_hist",  # consolidated into macro_us_hist
    "market_data_hist",    # replaced by market_data_comp_hist
    # Stage 2 retirement (S2.C13) — replaced by macro_economic /
    # macro_economic_hist:
    "macro_us",
    "macro_us_hist",
    "macro_intl",
    "macro_intl_hist",
    "macro_dbnomics",
    "macro_dbnomics_hist",
    "macro_ifo",
    "macro_ifo_hist",
})


# ---------------------------------------------------------------------------
# HISTORY PRESERVATION (forward_plan §3.1.1 — Stage A)
# ---------------------------------------------------------------------------
# Source-side history can shrink retroactively (e.g. April 2026 ICE Data demand
# that FRED truncate ICE BofA series to a rolling 3-year window). For every
# `*_hist.csv` we maintain, a sister `*_hist_x.csv` ("x" = "extended") preserves
# any rows that would otherwise be lost. The sister is append-only.
#
# Detection is per-column floor advancement (not row-count change): a rolling
# window keeps row count constant while the earliest date walks forward. For
# each column where the new fetch's earliest non-null date is later than the
# locally-stored earliest non-null date, the rows about to disappear are routed
# to the sister CSV before the live CSV is overwritten.
#
# Read paths use load_hist_with_archive() to transparently union live + sister.

import os as _hp_os
import pandas as _hp_pd


def _sister_path(path):
    """Return the *_hist_x.csv sister path for a given *_hist.csv path."""
    if not path.endswith("_hist.csv"):
        raise ValueError(
            f"{path!r} does not follow the *_hist.csv naming convention; "
            "history-preservation helpers only operate on *_hist.csv files."
        )
    return path[: -len("_hist.csv")] + "_hist_x.csv"


def _write_hist_payload(path, df, prefix_rows, date_col):
    """Write `df` to `path`, prepending `prefix_rows` metadata if provided.

    Mirrors the existing `fetch_hist.save_csv()` / `fetch_macro_economic.save_hist_csv()`
    file shape: N prefix rows, then a single header row, then the data rows.
    The Date column is formatted as YYYY-MM-DD strings.
    """
    _hp_os.makedirs(_hp_os.path.dirname(path) or ".", exist_ok=True)

    out = df.copy()
    if date_col in out.columns:
        out[date_col] = _hp_pd.to_datetime(out[date_col]).dt.strftime("%Y-%m-%d")

    if prefix_rows:
        import csv as _csv
        import io as _io
        buf = _io.StringIO()
        _csv.writer(buf, lineterminator="\n").writerows(prefix_rows)
        with open(path, "w", encoding="utf-8") as f:
            f.write(buf.getvalue())
            out.to_csv(f, index=False)
    else:
        out.to_csv(path, index=False)


def _append_archive_rows(sister_path, new_archive_df, prefix_rows, date_col):
    """Append rows to the sister CSV, deduplicating by `date_col` (existing wins)."""
    n_prefix = len(prefix_rows) if prefix_rows else 0

    if _hp_os.path.exists(sister_path):
        existing = _hp_pd.read_csv(sister_path, skiprows=n_prefix, low_memory=False)
        if date_col in existing.columns:
            existing[date_col] = _hp_pd.to_datetime(existing[date_col], errors="coerce")
            existing = existing[existing[date_col].notna()]
        # Concat existing first so dedup keeps the older copy on overlap.
        combined = _hp_pd.concat([existing, new_archive_df], ignore_index=True)
    else:
        combined = new_archive_df.copy()

    combined = combined.drop_duplicates(subset=[date_col], keep="first")
    combined = combined.sort_values(date_col).reset_index(drop=True)
    _write_hist_payload(sister_path, combined, prefix_rows, date_col)


def write_hist_with_archive(df, path, prefix_rows=None, date_col="Date"):
    """Write a *_hist.csv preserving any rows that would otherwise be lost.

    Per-column floor-advancement detection: for each column shared between the
    new `df` and the existing live file, if `new.earliest_nonnull_date` > the
    same column's `local.earliest_nonnull_date`, the rows in the live file with
    `date < new.earliest_nonnull_date` AND that column non-null are appended to
    the sister `<path>_x.csv` (deduplicated by date) before the live file is
    rewritten with `df`.

    Parameters
    ----------
    df : pd.DataFrame
        New data to write. Must carry `date_col` either as a column or as the
        DatetimeIndex name.
    path : str
        Live destination path; must end in `_hist.csv`.
    prefix_rows : list[list[str]] or None
        Optional metadata prefix rows written before the header (matches the
        existing fetch_hist.save_csv / fetch_macro_economic.save_hist_csv shape).
    date_col : str
        Date column name. Defaults to "Date".
    """
    # Normalise df → Date as a regular column.
    if isinstance(df.index, _hp_pd.DatetimeIndex) and df.index.name == date_col:
        new_df = df.reset_index()
    else:
        new_df = df.copy()
    new_df[date_col] = _hp_pd.to_datetime(new_df[date_col], errors="coerce")
    new_df = new_df[new_df[date_col].notna()]

    n_prefix = len(prefix_rows) if prefix_rows else 0
    sister = _sister_path(path)

    # Read existing live for the shrinkage check.
    if _hp_os.path.exists(path):
        old_df = _hp_pd.read_csv(path, skiprows=n_prefix, low_memory=False)
        if date_col in old_df.columns:
            old_df[date_col] = _hp_pd.to_datetime(old_df[date_col], errors="coerce")
            old_df = old_df[old_df[date_col].notna()].reset_index(drop=True)

            # Per-column floor comparison.
            archive_row_idx = set()
            shared_cols = [c for c in new_df.columns
                           if c in old_df.columns and c != date_col]
            for col in shared_cols:
                old_nn = old_df[old_df[col].notna()]
                new_nn = new_df[new_df[col].notna()]
                if old_nn.empty or new_nn.empty:
                    continue
                old_min = old_nn[date_col].min()
                new_min = new_nn[date_col].min()
                if new_min > old_min:
                    # Old rows that will lose this column on the new write.
                    mask = (old_df[date_col] < new_min) & old_df[col].notna()
                    archive_row_idx.update(old_df.index[mask].tolist())

            if archive_row_idx:
                archive_df = old_df.loc[sorted(archive_row_idx)].copy()
                _append_archive_rows(sister, archive_df, prefix_rows, date_col)

    # Write the live file.
    _write_hist_payload(path, new_df, prefix_rows, date_col)


def load_hist_with_archive(path, **read_csv_kwargs):
    """Load a *_hist.csv transparently unioned with its *_hist_x.csv sister.

    Behaves as a drop-in replacement for `pd.read_csv(path, **kwargs)`. If a
    sister file exists, its rows are unioned with the live rows; on overlap
    of dates, the live row wins. Returns a single DataFrame with the same
    schema as the live file.

    Date axis detection: if the resulting DataFrame has a DatetimeIndex, dedup
    on the index; otherwise dedup on a 'Date' column if present; otherwise
    return the simple concat. Result is sorted ascending by date.
    """
    live = _hp_pd.read_csv(path, low_memory=False, **read_csv_kwargs)
    sister = _sister_path(path)
    if not _hp_os.path.exists(sister):
        return live

    try:
        archive = _hp_pd.read_csv(sister, low_memory=False, **read_csv_kwargs)
    except Exception as exc:
        print(f"  [load_hist_with_archive] WARN reading sister {sister}: {exc}")
        return live

    combined = _hp_pd.concat([live, archive])

    if isinstance(combined.index, _hp_pd.DatetimeIndex):
        combined = combined[~combined.index.duplicated(keep="first")]
        return combined.sort_index()
    if "Date" in combined.columns:
        return (combined
                .drop_duplicates(subset=["Date"], keep="first")
                .sort_values("Date")
                .reset_index(drop=True))
    return combined.drop_duplicates(keep="first").reset_index(drop=True)

