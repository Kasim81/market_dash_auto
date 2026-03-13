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
# FRED SERIES DEFINITIONS
# ---------------------------------------------------------------------------
# Format:
#   series_id: (name, category, subcategory, units, notes)
#
# All series are US-only. International data is Phase C (OpenBB/OECD/IMF).
#
# Categories align with the Indicator Library:
#   Growth | Inflation | Financial Conditions | Monetary Policy

FRED_MACRO_US = {

    # ---- GROWTH: Yield Curve -----------------------------------------------
    "T10Y2Y": (
        "US Yield Curve 10Y-2Y Spread",
        "Growth", "Yield Curve",
        "Percentage Points",
        "Inversion (negative) has preceded every US recession 6-18m in advance"
    ),
    "T10Y3M": (
        "US Yield Curve 10Y-3M Spread",
        "Growth", "Yield Curve",
        "Percentage Points",
        "Campbell & Shiller preferred recession predictor; stronger near-term signal"
    ),

    # ---- GROWTH: Money Supply ----------------------------------------------
    "M2SL": (
        "US M2 Money Supply",
        "Growth", "Money Supply",
        "Billions USD (SA)",
        "YoY growth leads nominal GDP by 12-18m; negative YoY = deflation risk"
    ),

    # ---- GROWTH: Leading Indicators ----------------------------------------
    "USSLIND": (
        "US Conference Board Leading Economic Index (LEI)",
        "Growth", "Leading Indicators",
        "Index 2016=100",
        "3 consecutive monthly declines in 6m diffusion index = recession signal"
    ),
    "PERMIT": (
        "US Building Permits (SAAR)",
        "Growth", "Leading Indicators",
        "Thousands of Units (SAAR)",
        "Leads housing starts 1-2m; YoY negative = construction contraction"
    ),

    # ---- GROWTH: Labour Market ---------------------------------------------
    "IC4WSA": (
        "US Initial Jobless Claims 4-Week Average",
        "Growth", "Labour Market",
        "Thousands of Persons (SA)",
        "Sustained rise above 300k signals labour market deterioration"
    ),
    "PAYEMS": (
        "US Nonfarm Payrolls MoM Change",
        "Growth", "Labour Market",
        "Thousands of Persons (SA)",
        "3m avg >200k = solid expansion; <100k = slowdown; negative = recession"
    ),
    "UNRATE": (
        "US Unemployment Rate",
        "Growth", "Labour Market",
        "Percent (SA)",
        "Sahm Rule: 0.5pp rise in 3m average vs prior 12m low = recession signal"
    ),

    # ---- GROWTH: Activity --------------------------------------------------
    "INDPRO": (
        "US Industrial Production Index",
        "Growth", "Real Activity",
        "Index 2017=100 (SA)",
        "YoY negative = recession signal; companion to manufacturing PMI"
    ),
    "RSXFS": (
        "US Retail Sales ex-Autos MoM",
        "Growth", "Real Activity",
        "Millions USD (SA)",
        "Consumer spending momentum; YoY real negative = recessionary signal"
    ),

    # ---- GROWTH: Credit Cycle ----------------------------------------------
    "DRTSCILM": (
        "US SLOOS Net % Banks Tightening C&I Lending Standards (Large Firms)",
        "Growth", "Credit Cycle",
        "Net Percent (SA)",
        "Net tightening >20% has preceded every recession; 6-12m lead time"
    ),

    # ---- GROWTH: Financial Conditions --------------------------------------
    "NFCI": (
        "Chicago Fed National Financial Conditions Index (NFCI)",
        "Financial Conditions", "Composite",
        "Index",
        "Negative = easier than avg; positive and rising = tightening; leads growth 3-6m"
    ),

    # ---- INFLATION: CPI & PCE ----------------------------------------------
    "CPIAUCSL": (
        "US CPI Headline",
        "Inflation", "CPI",
        "Index 1982-84=100 (SA)",
        "Primary public inflation benchmark; >5% YoY = high-inflation regime"
    ),
    "CPILFESL": (
        "US Core CPI (ex Food & Energy)",
        "Inflation", "CPI",
        "Index 1982-84=100 (SA)",
        "Strips transitory commodity effects; sticky >3% = overheating signal"
    ),
    "PCEPILFE": (
        "US Core PCE Deflator",
        "Inflation", "PCE",
        "Index 2017=100 (SA)",
        "Fed's preferred inflation measure; Fed 2% target refers to this series"
    ),
    "PPIACO": (
        "US PPI All Commodities",
        "Inflation", "PPI",
        "Index 1982=100 (NSA)",
        "Leads CPI by 2-3m; acceleration = leading indicator of consumer price pressure"
    ),

    # ---- INFLATION: Breakevens & Expectations ------------------------------
    "T5YIE": (
        "US TIPS 5Y Breakeven Inflation Rate",
        "Inflation", "Breakevens",
        "Percent",
        "Market-implied 5yr avg inflation; level >3% = inflation concern"
    ),
    "T10YIE": (
        "US TIPS 10Y Breakeven Inflation Rate",
        "Inflation", "Breakevens",
        "Percent",
        "Most widely watched breakeven; rising 5Y vs 10Y = near-term inflation concerns"
    ),
    "T5YIFR": (
        "US 5Y5Y Forward Inflation Swap Rate",
        "Inflation", "Breakevens",
        "Percent",
        "Market-implied inflation years 5-10; measures whether long-run expectations anchored"
    ),
    "MICH": (
        "UMich Consumer Inflation Expectations 1Y",
        "Inflation", "Survey",
        "Percent",
        "Consumer-based; Fed watches closely; rise >3.5% would be policy alarm"
    ),

    # ---- MONETARY POLICY ---------------------------------------------------
    "FEDFUNDS": (
        "US Federal Funds Rate (Effective)",
        "Monetary Policy", "Policy Rate",
        "Percent (SA)",
        "Foundational Tier 1 indicator; direction and pace determine regime trajectory"
    ),
    "DFII10": (
        "US 10Y Real Interest Rate (TIPS)",
        "Monetary Policy", "Real Rates",
        "Percent",
        "Real rates >2% historically associated with growth decel and recession risk"
    ),
    "DFII5": (
        "US 5Y Real Interest Rate (TIPS)",
        "Monetary Policy", "Real Rates",
        "Percent",
        "Short-end real rate; rising = tightening financial conditions for risk assets"
    ),

    # ---- FINANCIAL CONDITIONS: Credit Spreads (market proxies) ------------
    # Note: ICE BofA spread indices are on FRED (BAMLH0A0HYM2 etc.)
    "BAMLH0A0HYM2": (
        "US HY Credit Spread OAS (ICE BofA)",
        "Financial Conditions", "Credit Spreads",
        "Percent",
        ">600bps = severe stress; >800bps = crisis; tightening from stress = risk-on"
    ),
    "BAMLC0A0CM": (
        "US IG Credit Spread OAS (ICE BofA)",
        "Financial Conditions", "Credit Spreads",
        "Percent",
        ">200bps historically coincides with recessions; IG-HY ratio = risk appetite"
    ),

    # ---- FINANCIAL CONDITIONS: SLOOS Extended (was in macro_surveys) ------
    # DRTSCILM (C&I Large/Medium) is already above; these add the full breakdown.
    "DRTSCIS": (
        "SLOOS: Net Tightening — C&I Loans, Small Firms",
        "Financial Conditions", "Credit Conditions",
        "Net Percent",
        "Companion to DRTSCILM (large firms). Divergence = dual-speed credit cycle."
    ),
    "DRTSCLCC": (
        "SLOOS: Net Tightening — Credit Card Loans",
        "Financial Conditions", "Credit Conditions",
        "Net Percent",
        "Consumer credit availability. Tightening leads consumer spending slowdown."
    ),
    "DRTSCLNG": (
        "SLOOS: Net Tightening — Consumer Loans (Non-Credit Card)",
        "Financial Conditions", "Credit Conditions",
        "Net Percent",
        "Auto, student and personal loans. Broadens consumer credit picture."
    ),
    "DRTSCRE": (
        "SLOOS: Net Tightening — Commercial Real Estate",
        "Financial Conditions", "Credit Conditions",
        "Net Percent",
        "CRE credit cycle; leads commercial property stress by 2-4 quarters."
    ),

    # ---- SURVEY: Consumer Sentiment (was in sentiment_data) ---------------
    "UMCSENT": (
        "UMich Consumer Sentiment (Overall)",
        "Survey", "Consumer Sentiment",
        "Index (1966 Q1 = 100)",
        "Headline consumer confidence; below 70 historically correlated with recessions."
    ),
    "UMCSI": (
        "UMich: Index of Current Economic Conditions",
        "Survey", "Consumer Sentiment",
        "Index (1966 Q1 = 100)",
        "Reflects assessment of present situation. Divergence from expectations = inflection signal."
    ),
    "UMCSE": (
        "UMich: Index of Consumer Expectations",
        "Survey", "Consumer Sentiment",
        "Index (1966 Q1 = 100)",
        "Forward-looking sub-index. Used in composite LEI."
    ),
    "CSCICP03USM665S": (
        "Conference Board Consumer Confidence (US)",
        "Survey", "Consumer Sentiment",
        "Index (2015 = 100)",
        "Business-sourced survey; leading indicator for consumer spending and employment."
    ),
    "BSCICP03USM665S": (
        "US Business Confidence",
        "Survey", "Business Sentiment",
        "Composite indicator (normal value = 100)",
        "OECD business confidence for US; companion to consumer confidence."
    ),

    # ---- SURVEY: PMI (was in sentiment_data) ------------------------------
    "NAPMPI": (
        "US ISM Manufacturing PMI",
        "Survey", "PMI",
        "Diffusion Index (50 = expansion/contraction threshold)",
        "Leading indicator for manufacturing activity and new orders; above 50 = expansion."
    ),

    # ---- SURVEY: Regional Fed Manufacturing (was in macro_surveys) --------
    "GACDISA066MSFRBPHI": (
        "Philadelphia Fed: Mfg Business Conditions (General Activity)",
        "Survey", "Regional Fed",
        "Diffusion Index",
        "One of the earliest monthly US mfg surveys; leads ISM by ~1 week."
    ),
    "GACDISA066MSFRBNY": (
        "Empire State (NY Fed): Mfg Business Conditions",
        "Survey", "Regional Fed",
        "Diffusion Index",
        "First regional Fed mfg survey released each month. Closely watched ISM preview."
    ),
    "GACDISA066MSFRBRIC": (
        "Richmond Fed: Mfg Business Conditions (Composite Index)",
        "Survey", "Regional Fed",
        "Diffusion Index",
        "Mid-Atlantic manufacturing survey. Covers VA, MD, DC, NC, SC, WV."
    ),
    "GACDISA066MSFRBKC": (
        "Kansas City Fed: Mfg Business Conditions (Composite Index)",
        "Survey", "Regional Fed",
        "Diffusion Index",
        "Tenth Federal Reserve District. Covers OK, KS, NE, CO, WY, NM, MO."
    ),
}

# ---------------------------------------------------------------------------
# FRED SERIES NATIVE FREQUENCIES
# ---------------------------------------------------------------------------
# Separate from FRED_MACRO_US to avoid breaking existing tuple destructuring.
# Used by both the macro_us snapshot tab and by fetch_hist.py for macro_us_hist.
# In macro_us_hist all series are forward-filled to weekly; the hist metadata
# rows display "Weekly (from <native> ffill)" to make this explicit.

FRED_MACRO_US_FREQ = {
    # Daily series (FRED publishes business-daily; aligned to Friday close)
    "T10Y2Y":             "Daily",
    "T10Y3M":             "Daily",
    "T5YIE":              "Daily",
    "T10YIE":             "Daily",
    "T5YIFR":             "Daily",
    "DFII10":             "Daily",
    "DFII5":              "Daily",
    "BAMLH0A0HYM2":       "Daily",
    "BAMLC0A0CM":         "Daily",
    # Weekly series
    "IC4WSA":             "Weekly",
    "NFCI":               "Weekly",
    # Monthly series
    "M2SL":               "Monthly",
    "USSLIND":            "Monthly",
    "PERMIT":             "Monthly",
    "PAYEMS":             "Monthly",
    "UNRATE":             "Monthly",
    "INDPRO":             "Monthly",
    "RSXFS":              "Monthly",
    "CPIAUCSL":           "Monthly",
    "CPILFESL":           "Monthly",
    "PCEPILFE":           "Monthly",
    "PPIACO":             "Monthly",
    "MICH":               "Monthly",
    "FEDFUNDS":           "Monthly",
    "UMCSENT":            "Monthly",
    "UMCSI":              "Monthly",
    "UMCSE":              "Monthly",
    "CSCICP03USM665S":    "Monthly",
    "BSCICP03USM665S":    "Monthly",
    "NAPMPI":             "Monthly",
    "GACDISA066MSFRBPHI": "Monthly",
    "GACDISA066MSFRBNY":  "Monthly",
    "GACDISA066MSFRBRIC": "Monthly",
    "GACDISA066MSFRBKC":  "Monthly",
    # Quarterly series (SLOOS surveys)
    "DRTSCILM":           "Quarterly",
    "DRTSCIS":            "Quarterly",
    "DRTSCLCC":           "Quarterly",
    "DRTSCLNG":           "Quarterly",
    "DRTSCRE":            "Quarterly",
}


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
            range=f"{TAB_NAME}!A:Z"
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
        df = fetch_macro_us()

        if df.empty:
            print("[Phase A] No data fetched — exiting cleanly")
            return

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
