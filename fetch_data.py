"""
Market Dashboard Data Fetcher
Pulls data from yfinance and FRED, calculates returns in local currency and USD,
and outputs structured CSVs to data/ directory.
"""

import pandas as pd
import yfinance as yf
import numpy as np
from datetime import datetime, timedelta, timezone
import os
import requests
import time

# ─────────────────────────────────────────────
# FRED API KEY — set as GitHub Secret FRED_API_KEY
# ─────────────────────────────────────────────
FRED_API_KEY = os.environ.get("FRED_API_KEY", "")
FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"

# ─────────────────────────────────────────────
# FX TICKERS (all quoted as units of foreign currency per 1 USD)
# Used to convert local returns to USD returns
# ─────────────────────────────────────────────
FX_TICKERS = {
    "GBP": "GBPUSD=X",   # GBP per USD → invert to get USD per GBP
    "EUR": "EURUSD=X",
    "JPY": "USDJPY=X",   # JPY per USD
    "CNY": "USDCNY=X",
    "INR": "USDINR=X",
    "KRW": "USDKRW=X",
    "TWD": "USDTWD=X",
}

# Currencies where the yfinance ticker is already USD/FCY (i.e. USD is numerator)
# For these we need to invert when converting local→USD
FCY_PER_USD = {"JPY", "CNY", "INR", "KRW", "TWD"}

# ─────────────────────────────────────────────
# ASSET DEFINITIONS
# Each tuple: (ticker, display_name, region, asset_class, local_currency)
# local_currency = None means already priced in USD
# ─────────────────────────────────────────────

EQUITY_INDEX = [
    ("^GSPC",     "S&P 500",                       "North America", "Equity Index",   None),
    ("^NDX",      "Nasdaq 100",                     "North America", "Equity Index",   None),
    ("^RUT",      "Russell 2000",                   "North America", "Equity Index",   None),
    ("^FTSE",     "FTSE 100",                       "UK",            "Equity Index",   "GBP"),
    ("^FTMC",     "FTSE 250",                       "UK",            "Equity Index",   "GBP"),
    ("^STOXX50E", "Euro Stoxx 50",                  "Europe",        "Equity Index",   "EUR"),
    ("^GDAXI",    "DAX 40",                         "Europe",        "Equity Index",   "EUR"),
    ("^N225",     "Nikkei 225",                     "Asia",          "Equity Index",   "JPY"),
    ("^NSEI",     "Nifty 50",                       "Asia",          "Equity Index",   "INR"),
    ("^BSESN",    "Sensex",                         "Asia",          "Equity Index",   "INR"),
    ("000001.SS", "Shanghai Composite",             "Asia",          "Equity Index",   "CNY"),
    ("399001.SZ", "Shenzhen Composite",             "Asia",          "Equity Index",   "CNY"),
]

EQUITY_ETF = [
    ("IWDA.L",    "MSCI World ETF",                 "Global",        "Equity ETF",     "GBP"),
    ("VFEM.L",    "MSCI EM ETF",                    "Global",        "Equity ETF",     "GBP"),
    ("AAXJ",      "Asia ex-Japan ETF",              "Asia",          "Equity ETF",     None),
    ("ILF",       "Latin America ETF",              "LatAm",         "Equity ETF",     None),
    ("EWY",       "South Korea ETF",                "Asia",          "Equity ETF",     None),
    ("EWT",       "Taiwan ETF",                     "Asia",          "Equity ETF",     None),
    ("NDIA.L",    "India ETF",                      "Asia",          "Equity ETF",     "GBP"),
    ("EWJ",       "Japan (TOPIX proxy) ETF",        "Asia",          "Equity ETF",     None),
]

SECTOR_ETF = [
    ("XLE",       "Sector: Energy",                 "US",            "Sector ETF",     None),
    ("XLB",       "Sector: Materials",              "US",            "Sector ETF",     None),
    ("XLI",       "Sector: Industrials",            "US",            "Sector ETF",     None),
    ("XLY",       "Sector: Consumer Discretionary", "US",            "Sector ETF",     None),
    ("XLP",       "Sector: Consumer Staples",       "US",            "Sector ETF",     None),
    ("XLV",       "Sector: Healthcare",             "US",            "Sector ETF",     None),
    ("XLF",       "Sector: Financials",             "US",            "Sector ETF",     None),
    ("XLK",       "Sector: Technology",             "US",            "Sector ETF",     None),
    ("XLU",       "Sector: Utilities",              "US",            "Sector ETF",     None),
    ("XLRE",      "Sector: Real Estate",            "US",            "Sector ETF",     None),
    ("XLC",       "Sector: Communication Services", "US",            "Sector ETF",     None),
    ("IWF",       "US Growth ETF (Russell 1000)",   "US",            "Style ETF",      None),
    ("IWFV.L",    "MSCI World Value ETF",           "Global",        "Style ETF",      "GBP"),
]

FIXED_INCOME_ETF = [
    ("AGGG.L",    "Global Agg Bond ETF",            "Global",        "Fixed Income ETF", "GBP"),
    ("SLXX.L",    "US IG Corporate Bond ETF",       "North America", "Fixed Income ETF", "GBP"),
    ("IHYU.L",    "US HY Bond ETF",                 "North America", "Fixed Income ETF", "GBP"),
    ("VDET.L",    "EM Debt USD ETF",                "Global",        "Fixed Income ETF", "GBP"),
    ("IGLT.L",    "UK Gilts ETF",                   "UK",            "Fixed Income ETF", "GBP"),
    ("IGLS.L",    "UK Short Gilts ETF",             "UK",            "Fixed Income ETF", "GBP"),
    ("EXX6.DE",   "German Bunds ETF",               "Europe",        "Fixed Income ETF", "EUR"),
    ("IGOV",      "Intl Govt Bonds ETF",            "Global",        "Fixed Income ETF", None),
    ("CNYB.L",    "Chinese Govt Bonds ETF",         "Asia",          "Fixed Income ETF", "GBP"),
]

COMMODITY = [
    ("GC=F",      "Gold",                           "Global",        "Commodity Metal",  None),
    ("SI=F",      "Silver",                         "Global",        "Commodity Metal",  None),
    ("BZ=F",      "Brent Crude",                    "Global",        "Commodity Energy", None),
    ("CL=F",      "WTI Crude Oil",                  "Global",        "Commodity Energy", None),
    ("HG=F",      "Copper",                         "Global",        "Commodity Metal",  None),
    ("ALI=F",     "Aluminium",                      "Global",        "Commodity Metal",  None),
    ("CT=F",      "Cotton",                         "Global",        "Commodity Soft",   None),
    ("KC=F",      "Coffee",                         "Global",        "Commodity Soft",   None),
    ("CMOD.L",    "Bloomberg Commodity ETF",        "Global",        "Commodity ETF",    "GBP"),
]

FX_ASSETS = [
    ("DX-Y.NYB",  "DXY Dollar Index",              "Global",        "FX",               None),
    ("GBPUSD=X",  "GBP/USD",                       "Global",        "FX",               None),
    ("EURUSD=X",  "EUR/USD",                       "Global",        "FX",               None),
    ("USDJPY=X",  "USD/JPY",                       "Global",        "FX",               None),
    ("USDCNY=X",  "USD/CNY",                       "Global",        "FX",               None),
    ("USDINR=X",  "USD/INR",                       "Global",        "FX",               None),
    ("USDKRW=X",  "USD/KRW",                       "Global",        "FX",               None),
    ("USDTWD=X",  "USD/TWD",                       "Global",        "FX",               None),
]

VOLATILITY = [
    ("^VIX",      "VIX (US Equity Vol)",           "US",            "Volatility",       None),
    ("BTC-USD",   "Bitcoin",                       "Global",        "Crypto",           None),
    ("ETH-USD",   "Ethereum",                      "Global",        "Crypto",           None),
]

# Yield tickers from yfinance (reported as basis points / 100, handled separately)
YIELD_YF = [
    ("^IRX",      "US 3-Month T-Bill",             "US",            "Yield",            None),
    ("^FVX",      "US 5Y Treasury Yield",          "US",            "Yield",            None),
    ("^TNX",      "US 10Y Treasury Yield",         "US",            "Yield",            None),
    ("^TYX",      "US 30Y Treasury Yield",         "US",            "Yield",            None),
]

# All yfinance-sourced assets (yields handled separately below)
ALL_YF_ASSETS = (
    EQUITY_INDEX + EQUITY_ETF + SECTOR_ETF +
    FIXED_INCOME_ETF + COMMODITY + FX_ASSETS + VOLATILITY
)

# Tickers treated as yields (show level + bps change, no USD conversion)
YIELD_TICKERS = {t[0] for t in YIELD_YF}

# Tickers that show absolute level change in points (not % change, not bps)
# VIX is already a volatility index expressed in points — % change is misleading
LEVEL_CHANGE_TICKERS = {"^VIX"}

# Tickers priced in pence on LSE (divide by 100 for GBP)
PENCE_TICKERS = {
    "IWDA.L", "VFEM.L", "NDIA.L",
    "IWFV.L",
    "AGGG.L", "SLXX.L", "IHYU.L", "VDET.L", "IGLT.L", "IGLS.L",
    "CNYB.L", "CMOD.L",
}

# ─────────────────────────────────────────────
# FRED SERIES DEFINITIONS
# UK 2Y Gilt removed (FRED series retired/invalid)
# China 10Y CGB removed (FRED series retired/invalid)
# ─────────────────────────────────────────────
FRED_YIELDS = {
    "US 2Y Treasury Yield":   "DGS2",
    "UK 10Y Gilt Yield":      "IRLTLT01GBM156N",
    "Germany 10Y Bund Yield": "IRLTLT01DEM156N",
    "Japan 10Y JGB Yield":    "IRLTLT01JPM156N",
}

FRED_SENTIMENT = {
    "UMich Consumer Sentiment":       "UMCSENT",
    "Conference Board Consumer Conf": "CSCICP03USM665S",
    "US Business Confidence":         "BSCICP03USM665S",
    "Euro Area Consumer Confidence":  "CSCICP03EZM665S",
    "US ISM Manufacturing PMI":       "NAPMPI",
}

# ─────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────

def get_ytd_start():
    now = datetime.now(timezone.utc)
    return datetime(now.year, 1, 1, tzinfo=timezone.utc)

PERIODS = {
    "Perf 1W":  7,
    "Perf 1M":  30,
    "Perf 3M":  90,
    "Perf 6M":  182,
    "Perf YTD": None,   # Special case
    "Perf 1Y":  365,
}

def calc_return(series, period_key, is_yield=False, is_level=False):
    """Calculate return or change for a given period key."""
    if series is None or series.empty:
        return np.nan

    last_val = series.iloc[-1]

    if period_key == "Perf YTD":
        target_date = get_ytd_start()
    else:
        days = PERIODS[period_key]
        target_date = datetime.now(timezone.utc) - timedelta(days=days)

    try:
        ts = pd.Timestamp(target_date).tz_convert("UTC").as_unit("us")
    except Exception:
        ts = pd.Timestamp(target_date, tz="UTC")

    try:
        idx = series.index.searchsorted(ts, side="left")
    except Exception:
        target_d = target_date.date()
        dates = series.index.date
        idx = next((i for i, d in enumerate(dates) if d >= target_d), len(series))

    if idx >= len(series):
        return np.nan
    start_val = series.iloc[idx]

    if pd.isna(start_val) or pd.isna(last_val):
        return np.nan

    if is_yield:
        return round((last_val - start_val) * 100, 1)
    elif is_level:
        return round(last_val - start_val, 2)
    else:
        if start_val == 0:
            return np.nan
        return round(100 * (last_val - start_val) / start_val, 2)


def fetch_yf_history(ticker, retries=3):
    """Fetch full price history from yfinance with retry logic."""
    for attempt in range(retries):
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="max")
            if hist is not None and not hist.empty:
                hist = hist[~hist.index.duplicated(keep="first")]
                series = hist["Close"]
                idx = series.index
                if idx.tzinfo is None:
                    idx = idx.tz_localize("UTC")
                else:
                    idx = idx.tz_convert("UTC")
                idx = idx.astype("datetime64[us, UTC]")
                series.index = idx
                return series
        except Exception as e:
            print(f"  [{ticker}] attempt {attempt+1} failed: {e}")
            time.sleep(2)
    return None


def fetch_fred_series(series_id, retries=3):
    """Fetch a FRED series and return as a pandas Series indexed by date."""
    if not FRED_API_KEY:
        print(f"  [FRED] No API key set — skipping {series_id}")
        return None
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "sort_order": "asc",
        "observation_start": "2000-01-01",
    }
    for attempt in range(retries):
        try:
            r = requests.get(FRED_BASE, params=params, timeout=15)
            r.raise_for_status()
            obs = r.json().get("observations", [])
            if not obs:
                return None
            df = pd.DataFrame(obs)[["date", "value"]]
            df["date"] = pd.to_datetime(df["date"], utc=True).astype("datetime64[us, UTC]")
            df["value"] = pd.to_numeric(df["value"], errors="coerce")
            df = df.dropna().set_index("date")["value"]
            return df
        except Exception as e:
            print(f"  [FRED {series_id}] attempt {attempt+1} failed: {e}")
            time.sleep(2)
    return None


# ─────────────────────────────────────────────
# MAIN DATA COLLECTION
# ─────────────────────────────────────────────

def build_fx_cache():
    """Pre-fetch all FX rate histories needed for USD conversion."""
    print("Fetching FX rates...")
    cache = {}
    for ccy, ticker in FX_TICKERS.items():
        series = fetch_yf_history(ticker)
        if series is not None:
            cache[ccy] = series
            print(f"  {ccy}: OK ({len(series)} rows)")
        else:
            print(f"  {ccy}: FAILED")
    return cache


def usd_adjusted_return(local_return_pct, ccy, period_key, fx_cache):
    """Convert a local currency % return to USD % return."""
    if ccy is None or pd.isna(local_return_pct):
        return local_return_pct

    if ccy not in fx_cache:
        return np.nan

    fx_series = fx_cache[ccy]
    fx_return = calc_return(fx_series, period_key, is_yield=False)

    if pd.isna(fx_return):
        return np.nan

    if ccy in FCY_PER_USD:
        fx_usd_return = -fx_return
    else:
        fx_usd_return = fx_return

    combined = (1 + local_return_pct / 100) * (1 + fx_usd_return / 100) - 1
    return round(combined * 100, 2)


def collect_yf_assets(fx_cache):
    """Collect all yfinance-based assets."""
    print("\nFetching yfinance assets...")
    rows = []

    all_assets = ALL_YF_ASSETS + YIELD_YF

    for asset in all_assets:
        ticker, name, region, asset_class, local_ccy = asset
        is_yield = ticker in YIELD_TICKERS
        is_level = ticker in LEVEL_CHANGE_TICKERS

        print(f"  {ticker} ({name})...")
        series = fetch_yf_history(ticker)

        if series is None or series.empty:
            print(f"    → No data")
            row = {
                "Symbol": ticker, "Name": name, "Region": region,
                "Asset Class": asset_class, "Currency": local_ccy or "USD",
                "Last Price": np.nan, "Last Date": np.nan,
            }
            for pk in PERIODS:
                row[f"Local {pk}"] = np.nan
                if not is_yield:
                    row[f"USD {pk}"] = np.nan
            rows.append(row)
            continue

        if ticker in PENCE_TICKERS:
            series = series / 100

        last_price = round(series.iloc[-1], 4)
        last_date = series.index[-1].date()

        row = {
            "Symbol": ticker, "Name": name, "Region": region,
            "Asset Class": asset_class,
            "Currency": "USD" if local_ccy is None else local_ccy,
            "Last Price": last_price, "Last Date": str(last_date),
        }

        for pk in PERIODS:
            local_ret = calc_return(series, pk, is_yield=is_yield, is_level=is_level)
            if is_yield:
                row[f"Local {pk} (bps)"] = local_ret
            else:
                row[f"Local {pk}"] = local_ret
                # Level-change tickers (e.g. VIX) are USD-denominated; no FX compounding
                row[f"USD {pk}"] = local_ret if is_level else usd_adjusted_return(local_ret, local_ccy, pk, fx_cache)

        rows.append(row)
        time.sleep(0.3)

    return rows


def collect_fred_yields():
    """Collect sovereign yields from FRED."""
    print("\nFetching FRED yields...")
    rows = []

    for name, series_id in FRED_YIELDS.items():
        print(f"  {series_id} ({name})...")
        series = fetch_fred_series(series_id)

        region = "US" if series_id == "DGS2" else "Sovereign"
        row = {
            "Symbol": series_id, "Name": name, "Region": region,
            "Asset Class": "Yield", "Currency": "Local",
            "Last Price": np.nan, "Last Date": np.nan,
        }

        if series is not None and not series.empty:
            row["Last Price"] = round(series.iloc[-1], 3)
            row["Last Date"] = str(series.index[-1].date())
            for pk in PERIODS:
                row[f"Local {pk} (bps)"] = calc_return(series, pk, is_yield=True)
        else:
            for pk in PERIODS:
                row[f"Local {pk} (bps)"] = np.nan

        rows.append(row)

    return rows


def collect_fred_sentiment():
    """Collect FRED sentiment survey data."""
    print("\nFetching FRED sentiment surveys...")
    rows = []

    for name, series_id in FRED_SENTIMENT.items():
        print(f"  {series_id} ({name})...")
        series = fetch_fred_series(series_id)

        if series is not None and not series.empty:
            latest = round(series.iloc[-1], 2)
            prior = round(series.iloc[-2], 2) if len(series) > 1 else np.nan
            chg = round(latest - prior, 2) if not pd.isna(prior) else np.nan
            last_date = str(series.index[-1].date())
        else:
            latest = prior = chg = last_date = np.nan

        rows.append({
            "Indicator": name,
            "FRED Series": series_id,
            "Latest Reading": latest,
            "Prior Reading": prior,
            "Change": chg,
            "Last Date": last_date,
        })

    return rows


def build_calculated_fields(df):
    """Add ratio-based sentiment/positioning indicators."""
    print("\nCalculating ratio fields...")

    def safe_ratio_return(num_ticker, den_ticker, period_key):
        num_row = df[df["Symbol"] == num_ticker]
        den_row = df[df["Symbol"] == den_ticker]
        if num_row.empty or den_row.empty:
            return np.nan
        col = f"Local {period_key}"
        if col not in df.columns:
            return np.nan
        n = num_row[col].values[0]
        d = den_row[col].values[0]
        if pd.isna(n) or pd.isna(d) or (1 + d / 100) == 0:
            return np.nan
        return round(((1 + n / 100) / (1 + d / 100) - 1) * 100, 2)

    ratios = [
        ("XLY",    "XLP",    "Cyclicals vs Defensives (US/Global proxy)", "Global",        "Sentiment Ratio"),
        ("XLF",    "XLU",    "Financials vs Utilities",                   "Global",        "Sentiment Ratio"),
        ("IHYU.L", "SLXX.L", "HY vs IG Credit (proxy)",                  "Global",        "Sentiment Ratio"),
        ("^FTMC",  "^FTSE",  "Small Cap vs Large Cap (UK)",               "UK",            "Sentiment Ratio"),
        ("IWF",    "IWFV.L", "Growth vs Value (proxy)",                   "Global",        "Sentiment Ratio"),
    ]

    ratio_rows = []
    for num, den, name, region, asset_class in ratios:
        row = {
            "Symbol": f"{num}/{den}", "Name": name, "Region": region,
            "Asset Class": asset_class, "Currency": "Ratio",
            "Last Price": np.nan, "Last Date": np.nan,
        }
        for pk in PERIODS:
            row[f"Local {pk}"] = safe_ratio_return(num, den, pk)
            row[f"USD {pk}"] = np.nan
        ratio_rows.append(row)

    return ratio_rows


# ─────────────────────────────────────────────
# GOOGLE SHEETS EXPORT
# ─────────────────────────────────────────────

SPREADSHEET_ID = "12nKIUGHz5euDbNQPDTVECsJBNwrceRF1ymsQrIe4_ac"

def push_to_google_sheets(df_main, df_sentiment):
    """
    Push market_data and sentiment_data dataframes to Google Sheets.
    Credentials are read from the GOOGLE_CREDENTIALS environment variable
    (set as a GitHub Actions secret containing the service account JSON).
    """
    import json
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    creds_json = os.environ.get("GOOGLE_CREDENTIALS", "")
    if not creds_json:
        print("  WARNING: GOOGLE_CREDENTIALS not set — skipping Sheets export.")
        return

    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(
        creds_dict,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    service = build("sheets", "v4", credentials=creds)
    sheets = service.spreadsheets()

    def df_to_values(df):
        """Convert dataframe to list-of-lists for Sheets API, replacing NaN with empty string."""
        header = df.columns.tolist()
        rows = df.fillna("").astype(str).values.tolist()
        return [header] + rows

    def write_sheet(tab_name, values):
        """Clear tab and write values."""
        sheets.values().clear(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{tab_name}!A1:ZZ10000"
        ).execute()

        sheets.values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{tab_name}!A1",
            valueInputOption="RAW",
            body={"values": values}
        ).execute()
        print(f"  ✓ Written {len(values)-1} rows to '{tab_name}' tab")

    # Delete the duplicate "Market Data" (space) tab if it exists.
    # This tab is not created by any code in this repo but keeps reappearing
    # (likely from a Google Apps Script or legacy manual tab). Deleting it here
    # ensures it is cleaned up on every daily run.
    try:
        meta = sheets.get(spreadsheetId=SPREADSHEET_ID).execute()
        for sheet in meta.get("sheets", []):
            if sheet["properties"]["title"] == "Market Data":
                sheets.batchUpdate(
                    spreadsheetId=SPREADSHEET_ID,
                    body={"requests": [{"deleteSheet": {"sheetId": sheet["properties"]["sheetId"]}}]}
                ).execute()
                print("  Deleted duplicate 'Market Data' tab")
                break
    except Exception as e:
        print(f"  WARNING: Could not check/delete 'Market Data' tab: {e}")

    print("\nPushing data to Google Sheets...")
    write_sheet("market_data", df_to_values(df_main))
    # sentiment_data tab deprecated: those indicators are now consolidated into
    # macro_us (US series) and macro_intl (Euro Area series).
    print("✓ Google Sheets export complete.")


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

def main():
    print("=" * 60)
    print(f"Market Dashboard Data Fetch — {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    os.makedirs("data", exist_ok=True)

    # 1. FX cache
    fx_cache = build_fx_cache()

    # 2. yfinance assets
    yf_rows = collect_yf_assets(fx_cache)

    # 3. FRED yields
    fred_yield_rows = collect_fred_yields()

    # 4. Build main dataframe
    all_rows = yf_rows + fred_yield_rows
    df_main = pd.DataFrame(all_rows)

    # 5. Calculated ratio fields (need df_main to exist first)
    ratio_rows = build_calculated_fields(df_main)
    df_ratios = pd.DataFrame(ratio_rows)
    df_main = pd.concat([df_main, df_ratios], ignore_index=True)

    # 6. Sentiment surveys (separate file, different schema)
    sentiment_rows = collect_fred_sentiment()
    df_sentiment = pd.DataFrame(sentiment_rows)

    # 7. Save outputs
    main_path = "data/market_data.csv"
    sentiment_path = "data/sentiment_data.csv"

    df_main.to_csv(main_path, index=False)
    df_sentiment.to_csv(sentiment_path, index=False)

    # 8. Push to Google Sheets
    push_to_google_sheets(df_main, df_sentiment)

    print(f"\n✓ Saved {main_path} — {len(df_main)} instruments")
    print(f"✓ Saved {sentiment_path} — {len(df_sentiment)} indicators")
    print(f"✓ Completed at {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")

    print("\n--- Asset class breakdown ---")
    if "Asset Class" in df_main.columns:
        print(df_main["Asset Class"].value_counts().to_string())


if __name__ == "__main__":
    main()

# ============================================================
# PHASE A INTEGRATION — add these lines at the very end of
# fetch_data.py, after the existing push_to_google_sheets() call
# ============================================================
#
# This is wrapped in a broad try/except so that if Phase A
# fails for any reason, it CANNOT affect the existing pipeline.
# The daily market_data and sentiment_data outputs are already
# committed before this code runs.
#
# PASTE THIS BLOCK at the bottom of fetch_data.py:

try:
    from fetch_macro_us_fred import run_phase_a
    run_phase_a()
except Exception as _phase_a_err:
    print(f"[Phase A] Non-fatal import/run error: {_phase_a_err}")
    print("[Phase A] Existing pipeline outputs are unaffected")

# ============================================================
# HISTORICAL SERIES INTEGRATION
# Add these lines at the very end of fetch_data.py, after the
# existing Phase A block (or after push_to_google_sheets() if
# Phase A hasn't been deployed yet).
#
# The historical build runs AFTER the existing daily snapshot
# is already committed and pushed, so any failure here cannot
# affect market_data.csv, sentiment_data.csv, or their tabs.
# ============================================================

try:
    from fetch_hist import run_hist
    run_hist()
except Exception as _hist_err:
    print(f"[Hist] Non-fatal import/run error: {_hist_err}")
    print("[Hist] Existing pipeline outputs are unaffected")

# ============================================================
# PHASE C — INTERNATIONAL MACRO INDICATORS
# Fetches OECD + IMF macro data for 11 major economies.
# Outputs: data/macro_intl.csv, data/macro_intl_hist.csv
#          Google Sheets tabs: macro_intl, macro_intl_hist
# ============================================================

try:
    from fetch_macro_international import run_phase_c
    run_phase_c()
except Exception as _phase_c_err:
    print(f"[Phase C] Non-fatal import/run error: {_phase_c_err}")
    print("[Phase C] Existing pipeline outputs are unaffected")

# Phase B (fetch_macro_surveys.py) has been consolidated into macro_us.
# All survey + credit condition indicators now live in fetch_macro_us_fred.py
# and are written to the macro_us / macro_us_hist tabs.
