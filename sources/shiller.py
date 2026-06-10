"""
sources/shiller.py
==================
Robert Shiller's long-run US market dataset — S&P 500 composite price,
dividends, earnings, US CPI, long rate, and the Cyclically Adjusted P/E
Ratio (CAPE), back to 1871. Monthly cadence.

Canonical primary source: Yale economics homepage,
    http://www.econ.yale.edu/~shiller/data/ie_data.xls

Updated quarterly-ish by Shiller himself. The xls workbook carries:
  - A "Data" sheet with the long-run series
  - Pre-header rows of titles + sub-headers
  - A Date column in decimal-year format ("1871.01", "1871.02", ...)
  - Per-column series: S&P Composite Price (P), Dividend (D), Earnings (E),
    CPI, Long Interest Rate (GS10), Real Price, Real Dividend, Real
    Earnings, and CAPE.

Indicator definitions live in data/macro_library_shiller.csv. Each row's
`series_id` is the source column header (or a stable alias the loader
maps to a header). The library is currently scaffold-only — populating
rows + wiring fetch dispatch in fetch_macro_economic.py is the §3.13
follow-up tracked in forward_plan.md.

Wired §3.13 (2026-06-10) — module + library schema only. The xls parser
is intentionally a stub returning None until the workbook layout is
verified against a live download (sandbox blocks Yale with 403, so the
verification needs to happen on a credentialed CI run or a local copy).
Driven by regime AA Phase 0 long-run availability + master plan §6
portfolio construction.
"""

from __future__ import annotations

import pathlib

import pandas as pd

_LIBRARY_CSV = pathlib.Path(__file__).parent.parent / "data" / "macro_library_shiller.csv"

# Canonical Yale URL. Static — Shiller's homepage hasn't moved in 20+ years.
# The xls is ~1MB; pull weekly at most once the parser is verified.
SHILLER_XLS_URL = "http://www.econ.yale.edu/~shiller/data/ie_data.xls"

# Browser-like UA — Yale's webserver 403s the default python-requests UA.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/vnd.ms-excel,application/octet-stream,*/*;q=0.8",
}


# ---------------------------------------------------------------------------
# LIBRARY LOADER
# ---------------------------------------------------------------------------

def load_library() -> list[dict]:
    """Load Shiller indicator definitions from macro_library_shiller.csv.

    Returns [] when the library is empty/absent (scaffold state today).
    Populate the CSV once the xls parser below is verified."""
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
# SERIES FETCH — stub (parser unimplemented; see module docstring)
# ---------------------------------------------------------------------------

def fetch_series_as_pandas(
    series_id: str,
    col_name: str | None = None,
) -> pd.Series | None:
    """Fetch one Shiller series and return a date-indexed pd.Series, or None.

    Stub — the xls parser is intentionally unimplemented until the
    ie_data.xls sheet layout is verified against a live download. Returns
    None + a one-line warning so fetch_macro_economic's dispatch loop
    handles it the same way as any other source returning no data, and
    the daily audit will flag any library rows that reference Shiller.

    See module docstring for the implementation plan."""
    print(
        f"    [Shiller] {series_id} — parser not yet wired (§3.13 follow-up); "
        f"returning None"
    )
    return None
