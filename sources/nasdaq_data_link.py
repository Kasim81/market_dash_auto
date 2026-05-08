"""
sources/nasdaq_data_link.py
===========================
Nasdaq Data Link (formerly Quandl) source module.

Indicator definitions live in data/macro_library_nasdaqdl.csv.

Wired §3.9 (2026-05-08) to add a long-run daily gold series — LBMA/GOLD —
after FRED's GOLDAMGBD228NLBM / GOLDPMGBD228NLBM were discontinued in 2017
when LBMA changed its methodology. Driven by the regime AA Phase 0c
long-run availability requirement.

Schema note — `sub_field`:
  Many Nasdaq Data Link series return multi-column DataFrames. LBMA/GOLD
  for example exposes USD/GBP/EUR x AM/PM in six columns. The library CSV
  carries a `sub_field` column that names the DataFrame column to extract.
  When `sub_field` is blank the first numeric column is used.

Auth:
  Reads NASDAQ_DATA_LINK_API_KEY from the environment. If absent the
  fetch attempts an anonymous call which Nasdaq Data Link rate-limits
  aggressively — production runs must inject the key via the workflow
  secret of the same name.
"""

from __future__ import annotations

import os
import pathlib
import time
from datetime import datetime

import pandas as pd

try:
    import nasdaqdatalink
except ImportError:
    nasdaqdatalink = None


_LIBRARY_CSV = pathlib.Path(__file__).parent.parent / "data" / "macro_library_nasdaqdl.csv"
DEFAULT_HIST_START = "1968-01-01"  # LBMA/GOLD goes back to 1968-04-01
_API_KEY_ENV = "NASDAQ_DATA_LINK_API_KEY"


def _configure_api_key() -> bool:
    """Set the global API key on the nasdaqdatalink module from env. Returns True if set."""
    if nasdaqdatalink is None:
        return False
    key = os.environ.get(_API_KEY_ENV, "").strip()
    if key:
        nasdaqdatalink.ApiConfig.api_key = key
        return True
    return False


# ---------------------------------------------------------------------------
# LIBRARY LOADER
# ---------------------------------------------------------------------------

def load_library() -> list[dict]:
    """Load Nasdaq Data Link indicator definitions from macro_library_nasdaqdl.csv."""
    if not _LIBRARY_CSV.exists():
        return []
    df = pd.read_csv(_LIBRARY_CSV, dtype=str, keep_default_na=False)
    df["sort_key"] = pd.to_numeric(df["sort_key"], errors="coerce").fillna(0)
    df = df.sort_values("sort_key")
    result = []
    for _, row in df.iterrows():
        result.append({
            "source":       "Nasdaq Data Link",
            "source_id":    row["series_id"].strip(),
            "col":          row["col"].strip(),
            "name":         row["name"].strip(),
            "country":      row.get("country", "").strip() or "GLOBAL",
            "category":     row["category"].strip(),
            "subcategory":  row["subcategory"].strip(),
            "concept":      row.get("concept", "").strip(),
            "cycle_timing": row.get("cycle_timing", "").strip(),
            "units":        row["units"].strip(),
            "frequency":    row["frequency"].strip(),
            "notes":        row.get("notes", "").strip(),
            "sort_key":     float(row["sort_key"]),
            "series_id":    row["series_id"].strip(),
            "sub_field":    row.get("sub_field", "").strip(),
        })
    return result


# ---------------------------------------------------------------------------
# SERIES FETCH
# ---------------------------------------------------------------------------

def fetch_series_as_pandas(
    series_id: str,
    sub_field: str = "",
    start: str = DEFAULT_HIST_START,
    col_name: str | None = None,
    retries: int = 3,
) -> pd.Series | None:
    """Fetch one Nasdaq Data Link series and return a date-indexed pd.Series.

    series_id : Nasdaq Data Link path, e.g. 'LBMA/GOLD'.
    sub_field : DataFrame column to extract. Blank → first numeric column.
    start     : ISO 'YYYY-MM-DD'; passed to nasdaqdatalink.get(start_date=...).
    col_name  : optional name for the returned Series (default = source_id).

    Returns None on failure (logged to stdout for pipeline.log capture).
    """
    if nasdaqdatalink is None:
        print(f"    [NDL] nasdaq-data-link package not installed — cannot fetch {series_id}")
        return None
    has_key = _configure_api_key()
    if not has_key:
        print(f"    [NDL] {_API_KEY_ENV} not set — calls will be rate-limited")

    try:
        start_dt = datetime.strptime(start, "%Y-%m-%d").date()
    except ValueError:
        start_dt = datetime.strptime(DEFAULT_HIST_START, "%Y-%m-%d").date()

    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            df = nasdaqdatalink.get(series_id, start_date=start_dt.isoformat())
            break
        except Exception as e:  # noqa: BLE001 — NDL throws several types
            last_exc = e
            wait = 2 ** attempt
            print(f"    [NDL HTTP/error] {series_id} attempt {attempt + 1}/{retries}: "
                  f"{type(e).__name__}: {str(e)[:160]}")
            if attempt + 1 < retries:
                time.sleep(wait)
    else:
        print(f"    [NDL FAIL] {series_id} — {retries} attempts exhausted ({last_exc})")
        return None

    if df is None or df.empty:
        print(f"    [NDL] {series_id} returned empty frame")
        return None

    # Resolve which column to extract.
    cols = list(df.columns)
    if sub_field:
        # Allow case-insensitive match because NDL column names sometimes
        # surface with subtle whitespace / case differences.
        match = next((c for c in cols if c.strip().lower() == sub_field.strip().lower()), None)
        if match is None:
            print(f"    [NDL] sub_field {sub_field!r} not in {series_id} columns "
                  f"{cols} — falling back to first numeric")
            chosen = None
        else:
            chosen = match
    else:
        chosen = None

    if chosen is None:
        # Pick the first numeric column.
        for c in cols:
            if pd.api.types.is_numeric_dtype(df[c]):
                chosen = c
                break
    if chosen is None:
        print(f"    [NDL] no numeric column in {series_id} response (columns={cols})")
        return None

    s = df[chosen].dropna()
    if s.empty:
        return None
    s.index = pd.to_datetime(s.index)
    s = s.sort_index()
    s.name = col_name or series_id
    return s
