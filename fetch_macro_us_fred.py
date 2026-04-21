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
import requests
import pandas as pd
from datetime import datetime, date, timezone
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from library_utils import SHEETS_PROTECTED_TABS

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

FRED_API_KEY = os.environ.get("FRED_API_KEY", "")
GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS", "")

SHEET_ID = "12nKIUGHz5euDbNQPDTVECsJBNwrceRF1ymsQrIe4_ac"
TAB_NAME = "macro_us"
OUTPUT_CSV = "data/macro_us.csv"

FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

# Delay between FRED requests (seconds). 0.6s = max 100 req/min, well under
# the 120 req/min limit, giving a 20-request safety buffer.
FRED_REQUEST_DELAY = 0.6

# Exponential backoff settings
BACKOFF_BASE = 2        # seconds for first retry
BACKOFF_MAX_RETRIES = 5

# ---------------------------------------------------------------------------
# LIBRARY LOADER
# ---------------------------------------------------------------------------
# US macro indicators are defined in macro_library_fred.csv (rows where the
# country column is blank).  Add or remove indicators by editing that CSV —
# no Python changes required.
#
# FRED_MACRO_US and FRED_MACRO_US_FREQ are built from the CSV at import time
# and kept as module-level exports for backward-compatibility with
# fetch_hist.py, which imports them directly.

import pathlib as _pl

_FRED_LIBRARY_CSV = _pl.Path(__file__).parent / "data" / "macro_library_fred.csv"


def _load_fred_us_library() -> tuple[dict, dict]:
    """
    Read macro_library_fred.csv and return (FRED_MACRO_US, FRED_MACRO_US_FREQ).

    FRED_MACRO_US      : {series_id: (name, category, subcategory, units, notes)}
    FRED_MACRO_US_FREQ : {series_id: frequency_string}

    Only rows with a blank country column are included (US scope).
    Row order in the CSV controls display order in the macro_us sheet.
    """
    try:
        df = pd.read_csv(_FRED_LIBRARY_CSV, dtype=str, keep_default_na=False)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"macro_library_fred.csv not found at {_FRED_LIBRARY_CSV}. "
            "Restore the file before running."
        )

    df["sort_key"] = pd.to_numeric(df["sort_key"], errors="coerce").fillna(0)
    us = df[df["country"].str.strip() == ""].sort_values("sort_key")

    macro_us = {
        row["series_id"]: (
            row["name"],
            row["category"],
            row["subcategory"],
            row["units"],
            row["notes"],
        )
        for _, row in us.iterrows()
    }
    freq_map = {
        row["series_id"]: row["frequency"]
        for _, row in us.iterrows()
    }
    return macro_us, freq_map


# Module-level exports — same dict structure as before, now sourced from CSV.
# fetch_hist.py imports these directly so names and formats must not change.
FRED_MACRO_US, FRED_MACRO_US_FREQ = _load_fred_us_library()


# ---------------------------------------------------------------------------
# LIBRARY VALIDATION
# ---------------------------------------------------------------------------

FRED_SERIES_URL = "https://api.stlouisfed.org/fred/series"


def _validate_fred_library() -> list:
    """
    Validate every series_id in FRED_MACRO_US against the FRED API.

    For each series:
      - Confirms the series_id exists in FRED (warns if not found or HTTP 400)
      - Prints the CSV name alongside the official FRED title for spot-checking

    Returns a list of warning strings (empty = all series found).
    Skipped silently if FRED_API_KEY is not set.
    """
    if not FRED_API_KEY:
        print("  [Validation] FRED_API_KEY not set — skipping library validation")
        return []

    indicators = [
        {"series_id": sid, "name": meta[0]}
        for sid, meta in FRED_MACRO_US.items()
    ]
    warnings = []
    total = len(indicators)
    print(f"\nValidating {total} series in macro_library_fred.csv against FRED API...")

    for i, indic in enumerate(indicators, 1):
        sid = indic["series_id"]
        try:
            resp = requests.get(
                FRED_SERIES_URL,
                params={"series_id": sid, "api_key": FRED_API_KEY, "file_type": "json"},
                timeout=10,
            )
            time.sleep(0.3)

            if resp.status_code == 200:
                seriess = resp.json().get("seriess", [])
                if seriess:
                    official = seriess[0]["title"]
                    print(f"  [{i}/{total}] {sid}")
                    print(f"    csv : {indic['name']}")
                    print(f"    fred: {official}")
                else:
                    warnings.append(
                        f"FRED '{sid}' returned no metadata — verify series_id "
                        f"in macro_library_fred.csv  (csv name: '{indic['name']}')"
                    )
            elif resp.status_code == 400:
                warnings.append(
                    f"FRED '{sid}' not found (HTTP 400) — check series_id "
                    f"in macro_library_fred.csv  (csv name: '{indic['name']}')"
                )
            else:
                print(f"  [SKIP] {sid}: HTTP {resp.status_code} — cannot validate")

        except Exception as e:
            print(f"  [SKIP] {sid}: validation error — {e}")

    return warnings


# (indicator definitions moved to macro_library_fred.csv)


# ---------------------------------------------------------------------------
# RATE-LIMIT-SAFE FRED FETCH
# ---------------------------------------------------------------------------

def fred_fetch_with_backoff(series_id: str, api_key: str) -> dict | None:
    """
    Fetch a FRED series with exponential backoff on rate limit / server errors.
    Returns the parsed JSON response dict, or None on failure.
    """
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 24,          # last 24 observations (2 years of monthly data)
        "observation_start": "2015-01-01",
    }

    for attempt in range(BACKOFF_MAX_RETRIES):
        try:
            resp = requests.get(FRED_BASE_URL, params=params, timeout=15)

            if resp.status_code == 200:
                return resp.json()

            elif resp.status_code == 429:
                wait = BACKOFF_BASE ** (attempt + 1)
                print(f"  [FRED] Rate limited on {series_id}. "
                      f"Backing off {wait}s (attempt {attempt+1}/{BACKOFF_MAX_RETRIES})")
                time.sleep(wait)

            elif resp.status_code >= 500:
                wait = BACKOFF_BASE ** (attempt + 1)
                print(f"  [FRED] Server error {resp.status_code} on {series_id}. "
                      f"Backing off {wait}s (attempt {attempt+1}/{BACKOFF_MAX_RETRIES})")
                time.sleep(wait)

            else:
                print(f"  [FRED] HTTP {resp.status_code} on {series_id} — skipping")
                return None

        except requests.exceptions.Timeout:
            wait = BACKOFF_BASE ** (attempt + 1)
            print(f"  [FRED] Timeout on {series_id}. "
                  f"Backing off {wait}s (attempt {attempt+1}/{BACKOFF_MAX_RETRIES})")
            time.sleep(wait)

        except requests.exceptions.RequestException as e:
            print(f"  [FRED] Request error on {series_id}: {e} — skipping")
            return None

    print(f"  [FRED] All {BACKOFF_MAX_RETRIES} attempts failed for {series_id} — skipping")
    return None


# ---------------------------------------------------------------------------
# PARSE FRED RESPONSE → LATEST + PRIOR READING
# ---------------------------------------------------------------------------

def parse_fred_observations(data: dict) -> tuple:
    """
    Extract the latest and prior non-null observations from a FRED response.
    Returns (latest_value, prior_value, latest_date) or (None, None, None).
    """
    if not data or "observations" not in data:
        return None, None, None

    obs = [
        o for o in data["observations"]
        if o.get("value") not in (".", "", None)
    ]

    if not obs:
        return None, None, None

    # FRED returns desc order when sort_order=desc
    latest = obs[0]
    prior = obs[1] if len(obs) > 1 else None

    try:
        latest_val = float(latest["value"])
    except (ValueError, TypeError):
        return None, None, None

    try:
        prior_val = float(prior["value"]) if prior else None
    except (ValueError, TypeError):
        prior_val = None

    latest_date = latest.get("date", "")
    return latest_val, prior_val, latest_date


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

        data = fred_fetch_with_backoff(series_id, FRED_API_KEY)
        latest_val, prior_val, latest_date = parse_fred_observations(data)

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
    if not GOOGLE_CREDENTIALS_JSON:
        print("[Phase A] GOOGLE_CREDENTIALS not set — skipping Sheets push")
        return

    if df.empty:
        print("[Phase A] Empty DataFrame — skipping Sheets push")
        return

    if TAB_NAME in SHEETS_PROTECTED_TABS:
        print(f"[Phase A] REFUSED: '{TAB_NAME}' is a protected tab")
        return

    try:
        creds_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
        creds = Credentials.from_service_account_info(
            creds_dict,
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        service = build("sheets", "v4", credentials=creds)
        sheets = service.spreadsheets()

        # --- Ensure tab exists -------------------------------------------
        meta = sheets.get(spreadsheetId=SHEET_ID).execute()
        existing_tabs = [s["properties"]["title"] for s in meta.get("sheets", [])]

        if TAB_NAME not in existing_tabs:
            print(f"[Phase A] Creating new tab '{TAB_NAME}'...")
            body = {
                "requests": [{
                    "addSheet": {
                        "properties": {"title": TAB_NAME}
                    }
                }]
            }
            sheets.batchUpdate(spreadsheetId=SHEET_ID, body=body).execute()
            print(f"[Phase A] Tab '{TAB_NAME}' created")
        else:
            print(f"[Phase A] Tab '{TAB_NAME}' already exists — will overwrite")

        # --- Write data ---------------------------------------------------
        def _sv(v):
            if v is None:
                return ""
            try:
                if pd.isna(v):
                    return ""
            except (TypeError, ValueError):
                pass
            if isinstance(v, (int, float)):
                return float(v)
            return str(v)

        header = list(df.columns)
        data_rows = [[_sv(v) for v in row] for row in df.itertuples(index=False)]
        values = [header] + data_rows

        range_notation = f"{TAB_NAME}!A1"

        # Clear existing content first
        sheets.values().clear(
            spreadsheetId=SHEET_ID,
            range=f"{TAB_NAME}!A:ZZ"
        ).execute()

        # Write new content
        sheets.values().update(
            spreadsheetId=SHEET_ID,
            range=range_notation,
            valueInputOption="USER_ENTERED",
            body={"values": values}
        ).execute()

        print(f"[Phase A] Written {len(df)} rows to '{TAB_NAME}' tab in Google Sheets")

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
