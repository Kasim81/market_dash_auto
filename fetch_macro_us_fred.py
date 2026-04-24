"""
fetch_macro_us_fred.py
======================
Phase A — US Macro Indicators via FRED API
Market Dashboard Expansion

DESIGN PRINCIPLES
-----------------
- Completely self-contained. Zero imports from or changes to fetch_data.py.
- Safe to run independently or called from fetch_data.py at the end of the
  existing script with a single function call: run_phase_a()
- If this module errors for any reason, it logs the error and exits cleanly
  without touching market_data.csv, sentiment_data.csv, or any existing
  Google Sheets tabs.
- Outputs: data/macro_us.csv  +  Google Sheets tab 'macro_us'

FRED RATE LIMITS
----------------
FRED enforces 120 requests/minute per API key. We are fetching ~25 series.
Safety measures applied:
  1. 0.6s delay between every FRED request (100 req/min maximum throughput)
  2. Exponential backoff on HTTP 429 or 5xx: waits 2s, 4s, 8s, 16s, 32s
  3. Per-series try/except so one failure never kills the whole run
  4. Total series count is well under 100, so daily budget is never an issue

GOOGLE SHEETS
-------------
Writes to a NEW tab named 'macro_us'. Does NOT touch 'market_data' or
'sentiment_data' tabs. Uses the same GOOGLE_CREDENTIALS secret already
configured in GitHub Actions.

USAGE
-----
Standalone test:
    python fetch_macro_us_fred.py

Called from fetch_data.py (add at the very end, after existing code):
    try:
        from fetch_macro_us_fred import run_phase_a
        run_phase_a()
    except Exception as e:
        print(f"[Phase A] Non-fatal error: {e}")
"""

import os
import time
import json
import pandas as pd
from datetime import datetime, timezone

from sources.base import get_sheets_service, push_df_to_sheets
from sources import fred as fred_src

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

FRED_API_KEY = os.environ.get("FRED_API_KEY", "")
GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS", "")

SHEET_ID = "12nKIUGHz5euDbNQPDTVECsJBNwrceRF1ymsQrIe4_ac"
TAB_NAME = "macro_us"
OUTPUT_CSV = "data/macro_us.csv"

# Delay between FRED requests (seconds). 0.6s = max 100 req/min, well under
# the 120 req/min limit, giving a 20-request safety buffer.
FRED_REQUEST_DELAY = 0.6

# ---------------------------------------------------------------------------
# LIBRARY LOADER
# ---------------------------------------------------------------------------
# US macro indicators are defined in macro_library_fred.csv (rows where the
# country column is blank).  Add or remove indicators by editing that CSV —
# no Python changes required.
#
# FRED_MACRO_US and FRED_MACRO_US_FREQ are populated from the CSV at import
# time and kept as module-level exports for backward-compatibility with
# fetch_hist.py, which imports them directly.

FRED_MACRO_US, FRED_MACRO_US_FREQ = fred_src.load_us_library()


# ---------------------------------------------------------------------------
# LIBRARY VALIDATION
# ---------------------------------------------------------------------------

def _validate_fred_library() -> list:
    """Validate every US series_id in FRED_MACRO_US against the FRED API."""
    indicators = [
        {"series_id": sid, "name": meta[0]}
        for sid, meta in FRED_MACRO_US.items()
    ]
    return fred_src.validate_series(indicators, FRED_API_KEY, label_prefix="Validation")


# ---------------------------------------------------------------------------
# BUILD macro_us DATAFRAME
# ---------------------------------------------------------------------------

def fetch_macro_us() -> pd.DataFrame:
    """
    Fetch all US macro FRED series and return a DataFrame ready for CSV/Sheets.
    Each row = one indicator.
    """
    if not FRED_API_KEY:
        print("[Phase A] FRED_API_KEY not set — skipping macro US fetch")
        return pd.DataFrame()

    rows = []
    total = len(FRED_MACRO_US)

    print(f"\nFetching {total} US macro series from FRED...")

    for i, (series_id, meta) in enumerate(FRED_MACRO_US.items(), start=1):
        name, category, subcategory, units, notes = meta
        print(f"  [{i}/{total}] {series_id} ({name})...")

        latest_val, prior_val, latest_date = fred_src.fetch_latest_prior(
            series_id, FRED_API_KEY, lookback_start="2015-01-01", limit=24
        )

        if latest_val is None:
            print(f"    → No data returned")
            change = None
        else:
            change = round(latest_val - prior_val, 4) if prior_val is not None else None
            print(f"    → Latest: {latest_val}  Prior: {prior_val}  "
                  f"Date: {latest_date}")

        rows.append({
            "Series ID":        series_id,
            "Indicator":        name,
            "Country":          "US",
            "Region":           "North America",
            "Category":         category,
            "Subcategory":      subcategory,
            "Units":            units,
            "Frequency":        FRED_MACRO_US_FREQ.get(series_id, ""),
            "Latest Value":     latest_val,
            "Prior Value":      prior_val,
            "Change":           change,
            "Last Date":        latest_date,
            "Source":           "FRED",
            "Notes":            notes,
            "Fetched At":       datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        })

        # Rate-limit delay after every request (except the last)
        if i < total:
            time.sleep(FRED_REQUEST_DELAY)

    df = pd.DataFrame(rows)
    print(f"\n[Phase A] Fetched {len(df)} US macro indicators")
    return df


# ---------------------------------------------------------------------------
# SAVE TO CSV
# ---------------------------------------------------------------------------

def save_csv(df: pd.DataFrame) -> None:
    """Save macro_us DataFrame to data/macro_us.csv."""
    os.makedirs("data", exist_ok=True)

    # Only write if content has changed (mirrors existing fetch_data.py behaviour)
    if os.path.exists(OUTPUT_CSV):
        try:
            existing = pd.read_csv(OUTPUT_CSV)
            # Compare on value columns only (ignore Fetched At timestamp)
            cols = ["Series ID", "Latest Value", "Prior Value", "Change", "Last Date"]
            if (existing[cols].equals(df[cols])):
                print(f"[Phase A] CSV unchanged — skipping write to {OUTPUT_CSV}")
                return
        except Exception:
            pass  # If comparison fails, just overwrite

    df.to_csv(OUTPUT_CSV, index=False)
    print(f"[Phase A] Written {len(df)} rows to {OUTPUT_CSV}")


# ---------------------------------------------------------------------------
# PUSH TO GOOGLE SHEETS
# ---------------------------------------------------------------------------

def push_macro_us_to_sheets(df: pd.DataFrame) -> None:
    """
    Push macro_us DataFrame to a Google Sheets tab named 'macro_us'.
    Creates the tab if it doesn't exist.
    Does NOT touch 'market_data' or 'sentiment_data' tabs.
    """
    try:
        push_df_to_sheets(
            get_sheets_service(GOOGLE_CREDENTIALS_JSON),
            SHEET_ID,
            TAB_NAME,
            df,
            label="Phase A",
        )

    except json.JSONDecodeError as e:
        print(f"[Phase A] GOOGLE_CREDENTIALS JSON parse error: {e} — skipping Sheets push")
    except Exception as e:
        print(f"[Phase A] Google Sheets push failed: {e} — skipping Sheets push")


# ---------------------------------------------------------------------------
# MAIN ENTRY POINT
# ---------------------------------------------------------------------------

def run_phase_a() -> None:
    """
    Full Phase A run. Safe to call from fetch_data.py or standalone.
    All errors are caught internally — will never raise to the caller.
    """
    print("\n" + "="*60)
    print("Phase A — US Macro Indicators (FRED)")
    print("="*60)

    start = time.time()

    try:
        warnings = _validate_fred_library()
        if warnings:
            print("\n" + "!" * 60)
            print("MACRO LIBRARY VALIDATION — ACTION REQUIRED:")
            for w in warnings:
                print(f"  [WARN] {w}")
            print("!" * 60 + "\n")

        df = fetch_macro_us()

        if df.empty:
            print("[Phase A] No data fetched — exiting cleanly")
            return

        df.insert(0, "row_id", range(1, len(df) + 1))
        save_csv(df)
        push_macro_us_to_sheets(df)

        elapsed = round(time.time() - start, 1)
        print(f"\n[Phase A] Completed in {elapsed}s")

    except Exception as e:
        elapsed = round(time.time() - start, 1)
        print(f"\n[Phase A] Unexpected error after {elapsed}s: {e}")
        print("[Phase A] Existing pipeline data is unaffected")


if __name__ == "__main__":
    run_phase_a()
