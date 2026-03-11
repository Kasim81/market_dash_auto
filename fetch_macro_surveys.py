"""
fetch_macro_surveys.py
======================
Phase B — Survey & Credit Condition Indicators
Market Dashboard Expansion

SOURCES
-------
All data via FRED API (FRED_API_KEY already configured).
No additional API keys required for the series below.

  SLOOS Extended Detail (Quarterly)
    Expands the single DRTSCILM series in macro_us with the full
    loan-category breakdown from the Senior Loan Officer Opinion Survey.

  UMich Consumer Sentiment Sub-Indices (Monthly)
    UMCSENT (headline) is already in macro_us. This module adds the
    current-conditions and expectations sub-indices.

  Regional Fed Manufacturing Surveys (Monthly)
    Philly Fed Business Outlook Survey and Empire State Manufacturing
    Survey — both published monthly by their respective Reserve Banks
    and available on FRED.

DEFERRED (awaiting API keys)
  BLS_API_KEY  — BLS nonfarm payrolls detail (Phase B extension)
  FMP_API_KEY  — ISM Manufacturing/Services PMI (Phase D)

DESIGN PRINCIPLES
-----------------
Identical to Phase A (fetch_macro_us_fred.py):
  - Completely self-contained. Zero side effects on existing pipeline.
  - Per-series try/except — one bad series never kills the run.
  - 0.6s FRED request delay + exponential backoff on 429/5xx.
  - Diff-check before CSV write to avoid noisy weekend commits.
  - Graceful skip if FRED_API_KEY or GOOGLE_CREDENTIALS absent.

OUTPUTS
-------
  data/macro_surveys.csv          Snapshot: latest + prior reading per indicator
  data/macro_surveys_hist.csv     History: Friday-spine from 2000-01-07, forward-filled
  Google Sheets tab: macro_surveys
  Google Sheets tab: macro_surveys_hist

USAGE
-----
Standalone:
    python fetch_macro_surveys.py

Called from fetch_data.py:
    try:
        from fetch_macro_surveys import run_phase_b
        run_phase_b()
    except Exception as e:
        print(f"[Phase B] Non-fatal error: {e}")
"""

import io
import os
import time
import json
import requests
import pandas as pd
from datetime import datetime

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

FRED_API_KEY           = os.environ.get("FRED_API_KEY", "")
GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS", "")

SHEET_ID               = "12nKIUGHz5euDbNQPDTVECsJBNwrceRF1ymsQrIe4_ac"
TAB_SNAPSHOT           = "macro_surveys"
TAB_HIST               = "macro_surveys_hist"
CSV_SNAPSHOT           = "data/macro_surveys.csv"
CSV_HIST               = "data/macro_surveys_hist.csv"

FRED_BASE_URL          = "https://api.stlouisfed.org/fred/series/observations"
FRED_REQUEST_DELAY     = 0.6        # seconds between requests
BACKOFF_BASE           = 2          # seconds for first retry
BACKOFF_MAX_RETRIES    = 5

HIST_START             = "2000-01-01"
HIST_END               = datetime.utcnow().strftime("%Y-%m-%d")

# ---------------------------------------------------------------------------
# SURVEY SERIES DEFINITIONS
# ---------------------------------------------------------------------------
# Format: series_id → (display_name, category, subcategory, units, notes)
#
# Series marked [verify] had IDs confirmed against FRED naming conventions
# but could not be live-tested in this environment — they will silently
# produce empty rows if the ID has changed.

SURVEY_SERIES = {

    # ── SLOOS Extended Detail (Quarterly) ───────────────────────────────────
    # DRTSCILM (C&I Large/Medium) is already in macro_us; omitted here.
    # These add the remaining loan-category breakdown.

    "DRTSCIS": (
        "SLOOS: Net Tightening — C&I Loans, Small Firms",
        "Credit Conditions", "SLOOS",
        "Net Percent",
        "Companion to DRTSCILM (large firms). Divergence = dual-speed credit cycle.",
    ),
    "DRTSCLCC": (
        "SLOOS: Net Tightening — Credit Card Loans",
        "Credit Conditions", "SLOOS",
        "Net Percent",
        "Consumer credit availability. Tightening leads consumer spending slowdown.",
    ),
    "DRTSCLNG": (
        "SLOOS: Net Tightening — Consumer Loans (Non-Credit Card)",
        "Credit Conditions", "SLOOS",
        "Net Percent",
        "Auto, student and personal loans. Broadens consumer credit picture.",
    ),
    "DRTSCRE": (
        "SLOOS: Net Tightening — Commercial Real Estate",
        "Credit Conditions", "SLOOS",
        "Net Percent",
        "CRE credit cycle; leads commercial property stress by 2-4 quarters.",
    ),

    # ── UMich Consumer Sentiment Sub-Indices (Monthly) ──────────────────────
    # UMCSENT (overall headline) is already in macro_us and sentiment_data.

    "UMCSI": (
        "UMich: Index of Current Economic Conditions",
        "Survey", "Consumer Sentiment",
        "Index (1966 Q1 = 100)",
        "Reflects assessment of present situation. Divergence from expectations = inflection signal.",
    ),
    "UMCSE": (
        "UMich: Index of Consumer Expectations",
        "Survey", "Consumer Sentiment",
        "Index (1966 Q1 = 100)",
        "Forward-looking sub-index. Fed Reserve conference board uses this in composite LEI.",
    ),

    # ── Regional Fed Manufacturing Surveys (Monthly) ────────────────────────

    "GACDISA066MSFRBPHI": (
        "Philadelphia Fed: Mfg Business Conditions (General Activity)",
        "Survey", "Regional Fed",
        "Diffusion Index",
        "One of the earliest monthly US mfg surveys. Positive = expansion; leads ISM by ~1 week.",
    ),
    "GACDISA066MSFRBNY": (
        "Empire State (NY Fed): Mfg Business Conditions (General Activity)",
        "Survey", "Regional Fed",
        "Diffusion Index",
        "First regional Fed mfg survey released each month. Closely watched ISM preview.",
    ),
    "GACDISA066MSFRBRIC": (
        "Richmond Fed: Mfg Business Conditions (Composite Index)",
        "Survey", "Regional Fed",
        "Diffusion Index",
        "Mid-Atlantic manufacturing survey. Covers VA, MD, DC, NC, SC, WV.",
    ),
    "GACDISA066MSFRBKC": (
        "Kansas City Fed: Mfg Business Conditions (Composite Index)",
        "Survey", "Regional Fed",
        "Diffusion Index",
        "Tenth Federal Reserve District. Covers OK, KS, NE, CO, WY, NM, MO.",
    ),
}

# ---------------------------------------------------------------------------
# FRED FETCH WITH BACKOFF
# ---------------------------------------------------------------------------

def _fred_fetch(series_id: str, observation_start: str = "2015-01-01",
                limit: int = 24, sort_order: str = "desc") -> dict | None:
    """Fetch a FRED series with exponential backoff. Returns JSON dict or None."""
    params = {
        "series_id":        series_id,
        "api_key":          FRED_API_KEY,
        "file_type":        "json",
        "sort_order":       sort_order,
        "observation_start": observation_start,
    }
    if limit:
        params["limit"] = limit

    for attempt in range(BACKOFF_MAX_RETRIES):
        try:
            resp = requests.get(FRED_BASE_URL, params=params, timeout=15)

            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code in (429, 500, 502, 503, 504):
                wait = BACKOFF_BASE ** (attempt + 1)
                print(f"  [FRED] HTTP {resp.status_code} on {series_id} — "
                      f"backing off {wait}s (attempt {attempt+1}/{BACKOFF_MAX_RETRIES})")
                time.sleep(wait)
            else:
                print(f"  [FRED] HTTP {resp.status_code} on {series_id} — skipping")
                return None

        except requests.exceptions.Timeout:
            wait = BACKOFF_BASE ** (attempt + 1)
            print(f"  [FRED] Timeout on {series_id} — "
                  f"backing off {wait}s (attempt {attempt+1}/{BACKOFF_MAX_RETRIES})")
            time.sleep(wait)
        except requests.exceptions.RequestException as e:
            print(f"  [FRED] Request error on {series_id}: {e} — skipping")
            return None

    print(f"  [FRED] All {BACKOFF_MAX_RETRIES} attempts failed for {series_id} — skipping")
    return None


def _parse_snapshot(data: dict) -> tuple:
    """
    Extract latest + prior non-null observations from a FRED response (desc order).
    Returns (latest_value, prior_value, latest_date) or (None, None, None).
    """
    if not data or "observations" not in data:
        return None, None, None

    obs = [o for o in data["observations"] if o.get("value") not in (".", "", None)]
    if not obs:
        return None, None, None

    latest = obs[0]
    prior  = obs[1] if len(obs) > 1 else None

    try:
        latest_val = float(latest["value"])
    except (ValueError, TypeError):
        return None, None, None

    try:
        prior_val = float(prior["value"]) if prior else None
    except (ValueError, TypeError):
        prior_val = None

    return latest_val, prior_val, latest.get("date", "")


def _parse_history(data: dict) -> pd.Series | None:
    """
    Convert a FRED JSON response (asc order) to a DatetimeIndex pd.Series.
    Returns None if data is empty or unusable.
    """
    if not data or "observations" not in data:
        return None

    obs = [o for o in data["observations"] if o.get("value") not in (".", "", None)]
    if not obs:
        return None

    dates  = pd.to_datetime([o["date"] for o in obs], utc=True)
    values = pd.to_numeric([o["value"] for o in obs], errors="coerce")
    s = pd.Series(values, index=dates, dtype=float).dropna()
    return s if not s.empty else None


# ---------------------------------------------------------------------------
# BUILD SNAPSHOT DATAFRAME
# ---------------------------------------------------------------------------

def fetch_snapshot() -> pd.DataFrame:
    """Fetch latest reading for all survey series. Returns snapshot DataFrame."""
    if not FRED_API_KEY:
        print("[Phase B] FRED_API_KEY not set — skipping survey fetch")
        return pd.DataFrame()

    rows  = []
    total = len(SURVEY_SERIES)
    print(f"\nFetching {total} survey series from FRED (snapshot)...")

    for i, (series_id, meta) in enumerate(SURVEY_SERIES.items(), start=1):
        name, category, subcategory, units, notes = meta
        print(f"  [{i}/{total}] {series_id} ({name[:55]})...")

        try:
            data = _fred_fetch(series_id, observation_start="2015-01-01",
                               limit=24, sort_order="desc")
            latest_val, prior_val, latest_date = _parse_snapshot(data)

            if latest_val is None:
                print(f"    → No data (series may be inactive or ID needs verification)")
                change = None
            else:
                change = round(latest_val - prior_val, 4) if prior_val is not None else None
                print(f"    → Latest: {latest_val}  Prior: {prior_val}  Date: {latest_date}")

        except Exception as e:
            print(f"    → Error: {e}")
            latest_val = prior_val = change = latest_date = None

        rows.append({
            "Series ID":    series_id,
            "Indicator":    name,
            "Category":     category,
            "Subcategory":  subcategory,
            "Units":        units,
            "Latest Value": latest_val,
            "Prior Value":  prior_val,
            "Change":       change,
            "Last Date":    latest_date,
            "Source":       "FRED",
            "Notes":        notes,
            "Fetched At":   datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        })

        if i < total:
            time.sleep(FRED_REQUEST_DELAY)

    df = pd.DataFrame(rows)
    print(f"\n[Phase B] Snapshot: {df['Latest Value'].notna().sum()}/{total} series returned data")
    return df


# ---------------------------------------------------------------------------
# BUILD HISTORY DATAFRAME (Friday-spine, forward-filled)
# ---------------------------------------------------------------------------

def fetch_history() -> pd.DataFrame:
    """
    Fetch full history for all survey series.
    Returns a wide DataFrame with Date as rows and series_id as columns,
    resampled to a weekly Friday spine and forward-filled (matching the
    pattern used by macro_intl_hist and macro_us_hist).
    """
    if not FRED_API_KEY:
        return pd.DataFrame()

    total = len(SURVEY_SERIES)
    print(f"\nFetching {total} survey series from FRED (history from {HIST_START})...")

    series_dict = {}

    for i, series_id in enumerate(SURVEY_SERIES.keys(), start=1):
        name = SURVEY_SERIES[series_id][0]
        print(f"  [{i}/{total}] {series_id}...")

        try:
            data = _fred_fetch(series_id, observation_start=HIST_START,
                               limit=None, sort_order="asc")
            s = _parse_history(data)

            if s is not None:
                series_dict[series_id] = s
                print(f"    → {len(s)} observations "
                      f"({s.index[0].date()} to {s.index[-1].date()})")
            else:
                print(f"    → No data")

        except Exception as e:
            print(f"    → Error: {e}")

        if i < total:
            time.sleep(FRED_REQUEST_DELAY)

    if not series_dict:
        print("[Phase B] No historical data retrieved")
        return pd.DataFrame()

    # Combine into wide DataFrame
    df_wide = pd.DataFrame(series_dict)

    # Build Friday-spine covering all dates
    friday_spine = pd.date_range(
        start=HIST_START,
        end=HIST_END,
        freq="W-FRI",
        tz="UTC",
    )

    # Reindex to Friday-spine, forward-fill (monthly/quarterly → weekly)
    df_hist = (
        df_wide
        .reindex(df_wide.index.union(friday_spine))
        .sort_index()
        .ffill()
        .reindex(friday_spine)
    )

    df_hist.index.name = "Date"
    df_hist = df_hist.reset_index()
    df_hist["Date"] = df_hist["Date"].dt.strftime("%Y-%m-%d")

    print(f"\n[Phase B] History: {df_hist.shape[0]} weekly rows × "
          f"{df_hist.shape[1]-1} series columns")
    return df_hist


# ---------------------------------------------------------------------------
# CSV SAVE (with diff-check)
# ---------------------------------------------------------------------------

def _save_csv(df: pd.DataFrame, path: str, label: str) -> None:
    """Write DataFrame to CSV, skipping if content unchanged (avoids noisy commits)."""
    os.makedirs("data", exist_ok=True)

    if df.empty:
        print(f"[Phase B] {label}: empty DataFrame — skipping CSV write")
        return

    if os.path.exists(path):
        try:
            existing = pd.read_csv(path)
            if existing.shape == df.shape and (existing == df.fillna("")).all(axis=None).all():
                print(f"[Phase B] {label}: unchanged — skipping write to {path}")
                return
        except Exception:
            pass

    df.to_csv(path, index=False)
    print(f"[Phase B] {label}: written {len(df)} rows to {path}")


# ---------------------------------------------------------------------------
# GOOGLE SHEETS PUSH
# ---------------------------------------------------------------------------

def _get_sheets_client():
    """Build and return an authenticated Google Sheets service.spreadsheets() object."""
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    creds_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
    creds = Credentials.from_service_account_info(
        creds_dict,
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    service = build("sheets", "v4", credentials=creds)
    return service.spreadsheets()


def _ensure_tab(sheets, tab_name: str) -> None:
    """Create the tab if it doesn't already exist."""
    meta     = sheets.get(spreadsheetId=SHEET_ID).execute()
    existing = [s["properties"]["title"] for s in meta.get("sheets", [])]
    if tab_name not in existing:
        print(f"[Phase B] Creating new tab '{tab_name}'...")
        body = {"requests": [{"addSheet": {"properties": {"title": tab_name}}}]}
        sheets.batchUpdate(spreadsheetId=SHEET_ID, body=body).execute()
        print(f"[Phase B] Tab '{tab_name}' created")
    else:
        print(f"[Phase B] Tab '{tab_name}' exists — will overwrite")


def _write_tab(sheets, tab_name: str, df: pd.DataFrame) -> None:
    """Clear tab and write DataFrame (header + rows). Batches at 10,000 rows per call."""
    header    = list(df.columns)
    data_rows = df.fillna("").astype(str).values.tolist()
    all_rows  = [header] + data_rows

    # Clear existing content
    sheets.values().clear(
        spreadsheetId=SHEET_ID,
        range=f"{tab_name}!A:ZZ",
    ).execute()

    # Write in batches of 10,000 rows to stay within API payload limits
    BATCH = 10_000
    for start in range(0, len(all_rows), BATCH):
        chunk = all_rows[start:start + BATCH]
        range_ref = f"{tab_name}!A{start + 1}"
        sheets.values().update(
            spreadsheetId=SHEET_ID,
            range=range_ref,
            valueInputOption="RAW",
            body={"values": chunk},
        ).execute()

    print(f"[Phase B] Written {len(data_rows)} rows to '{tab_name}' tab")


def push_to_sheets(df_snapshot: pd.DataFrame, df_hist: pd.DataFrame) -> None:
    """Push snapshot and history DataFrames to Google Sheets."""
    if not GOOGLE_CREDENTIALS_JSON:
        print("[Phase B] GOOGLE_CREDENTIALS not set — skipping Sheets push")
        return

    try:
        sheets = _get_sheets_client()

        for tab_name, df in [(TAB_SNAPSHOT, df_snapshot), (TAB_HIST, df_hist)]:
            if df.empty:
                print(f"[Phase B] {tab_name}: empty — skipping Sheets push")
                continue
            _ensure_tab(sheets, tab_name)
            _write_tab(sheets, tab_name, df)

        print("[Phase B] Google Sheets push complete")

    except json.JSONDecodeError as e:
        print(f"[Phase B] GOOGLE_CREDENTIALS JSON parse error: {e} — skipping Sheets push")
    except Exception as e:
        print(f"[Phase B] Sheets push failed: {e} — skipping Sheets push")


# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------

def run_phase_b() -> None:
    """
    Full Phase B run. Safe to call from fetch_data.py or standalone.
    All errors caught internally — will never raise to caller.
    """
    print("\n" + "=" * 60)
    print("Phase B — Survey & Credit Condition Indicators (FRED)")
    print("=" * 60)

    start = time.time()

    try:
        df_snapshot = fetch_snapshot()
        df_hist     = fetch_history()

        _save_csv(df_snapshot, CSV_SNAPSHOT, "snapshot")
        _save_csv(df_hist,     CSV_HIST,     "history")

        push_to_sheets(df_snapshot, df_hist)

        elapsed = round(time.time() - start, 1)
        print(f"\n[Phase B] Completed in {elapsed}s")

    except Exception as e:
        elapsed = round(time.time() - start, 1)
        print(f"\n[Phase B] Unexpected error after {elapsed}s: {e}")
        print("[Phase B] Existing pipeline data is unaffected")


if __name__ == "__main__":
    run_phase_b()
