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
    ("EWJ",       "Japan (TOPIX proxy) ETF",        "Asia",          "Equity ETF",     None),  # USD-listed, tracks MSCI Japan
]

SECTOR_ETF = [
    ("XLE",       "Sector: Energy",                 "Global",        "Equity Sector",  None),
    ("XLB",       "Sector: Materials",              "Global",        "Equity Sector",  None),
    ("XLI",       "Sector: Industrials",            "Global",        "Equity Sector",  None),
    ("XLY",       "Sector: Consumer Discretionary", "Global",        "Equity Sector",  None),
    ("XLP",       "Sector: Consumer Staples",       "Global",        "Equity Sector",  None),
    ("XLV",       "Sector: Healthcare",             "Global",        "Equity Sector",  None),
    ("XLF",       "Sector: Financials",             "Global",        "Equity Sector",  None),
    ("XLK",       "Sector: Technology",             "Global",        "Equity Sector",  None),
    ("XLU",       "Sector: Utilities",              "Global",        "Equity Sector",  None),
    ("XLRE",      "Sector: Real Estate",            "Global",        "Equity Sector",  None),
    ("XLC",       "Sector: Communication Services", "Global",        "Equity Sector",  None),
    ("IWF",       "US Growth ETF (Russell 1000)",   "North America", "Equity Factor",  None),
    ("IWFV.L",    "MSCI World Value ETF",           "Global",        "Equity Factor",  "GBP"),
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
    ("^VIX",      "VIX (US Equity Vol)",           "Global",        "Volatility",       None),
    ("BTC-USD",   "Bitcoin",                       "Global",        "Crypto",           None),
    ("ETH-USD",   "Ethereum",                      "Global",        "Crypto",           None),
]

# Yield tickers from yfinance (reported as basis points / 100, handled separately)
YIELD_YF = [
    ("^IRX",      "US 2Y Treasury Yield",          "North America", "Yield",            None),
    ("^FVX",      "US 5Y Treasury Yield",          "North America", "Yield",            None),
    ("^TNX",      "US 10Y Treasury Yield",         "North America", "Yield",            None),
    ("^TYX",      "US 30Y Treasury Yield",         "North America", "Yield",            None),
]

# All yfinance-sourced assets (yields handled separately below)
ALL_YF_ASSETS = (
    EQUITY_INDEX + EQUITY_ETF + SECTOR_ETF +
    FIXED_INCOME_ETF + COMMODITY + FX_ASSETS + VOLATILITY
)

# Tickers treated as yields (show level + bps change, no USD conversion)
YIELD_TICKERS = {t[0] for t in YIELD_YF}

# Tickers priced in pence on LSE (divide by 100 for GBP)
PENCE_TICKERS = {
    "IWDA.L", "VFEM.L", "NDIA.L",
    "IWFV.L",
    "AGGG.L", "SLXX.L", "IHYU.L", "VDET.L", "IGLT.L", "IGLS.L",
    "CNYB.L", "CMOD.L",
}

# ─────────────────────────────────────────────
# FRED SERIES DEFINITIONS
# ─────────────────────────────────────────────
FRED_YIELDS = {
    "UK 2Y Gilt Yield":       "IUDSGT02",          # corrected series ID
    "UK 10Y Gilt Yield":      "IRLTLT01GBM156N",
    "Germany 10Y Bund Yield": "IRLTLT01DEM156N",
    "Japan 10Y JGB Yield":    "IRLTLT01JPM156N",
    "China 10Y CGB Yield":    "CHNGDPNQD",         # Lagged proxy — known gap
}

FRED_SENTIMENT = {
    "UMich Consumer Sentiment":       "UMCSENT",
    "Conference Board Consumer Conf": "CSCICP03USM665S",
    "US Business Confidence":         "BSCICP03USM665S",
    "Euro Area Consumer Confidence":  "CSCICP03EZM665S",
    "US ISM Manufacturing PMI":       "NAPM",
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

def calc_return(series, period_key, is_yield=False):
    """Calculate return or change for a given period key.

    Series index must be tz-aware UTC with microsecond resolution
    (as normalised by fetch_yf_history / fetch_fred_series).
    """
    if series is None or series.empty:
        return np.nan

    last_val = series.iloc[-1]

    if period_key == "Perf YTD":
        target_date = get_ytd_start()
    else:
        days = PERIODS[period_key]
        target_date = datetime.now(timezone.utc) - timedelta(days=days)

    # Cast target_date to pandas Timestamp with matching resolution so
    # searchsorted never triggers the np_datetime convert_reso ValueError.
    try:
        ts = pd.Timestamp(target_date).tz_convert("UTC").as_unit("us")
    except Exception:
        ts = pd.Timestamp(target_date, tz="UTC")

    try:
        idx = series.index.searchsorted(ts, side="left")
    except Exception:
        # Fallback: compare as plain dates
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
    else:
        if start_val == 0:
            return np.nan
        return round(100 * (last_val - start_val) / start_val, 2)


def fetch_yf_history(ticker, retries=3):
    """Fetch full price history from yfinance with retry logic.
    Returns a Series with a tz-aware UTC index normalised to microsecond
    resolution to avoid pandas np_datetime convert_reso errors.
    """
    for attempt in range(retries):
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="max")
            if hist is not None and not hist.empty:
                hist = hist[~hist.index.duplicated(keep="first")]
                series = hist["Close"]
                # Normalise index: ensure UTC, then cast to microseconds.
                # yfinance sometimes returns nanosecond-resolution timestamps
                # which cause ValueError in pandas searchsorted comparisons.
                idx = series.index
                if idx.tzinfo is None:
                    idx = idx.tz_localize("UTC")
                else:
                    idx = idx.tz_convert("UTC")
                # Cast to microsecond precision to avoid lossless-conversion errors
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
    """
    Convert a local currency % return to USD % return.
    local_return_pct: already computed % return in local currency
    ccy: 3-letter currency code
    """
    if ccy is None or pd.isna(local_return_pct):
        return local_return_pct  # Already USD or no data

    if ccy not in fx_cache:
        return np.nan

    fx_series = fx_cache[ccy]
    fx_return = calc_return(fx_series, period_key, is_yield=False)

    if pd.isna(fx_return):
        return np.nan

    # For CCY/USD pairs (GBP, EUR): fx_return is already % change in USD value of the currency
    # For USD/FCY pairs (JPY, CNY etc.): a rise means USD strengthened → negative for USD investor
    if ccy in FCY_PER_USD:
        fx_usd_return = -fx_return  # Invert: if USD/JPY rises, JPY weakened
    else:
        fx_usd_return = fx_return

    # Combine: (1 + local_return) * (1 + fx_return) - 1
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

        # Pence to pounds adjustment
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
            local_ret = calc_return(series, pk, is_yield=is_yield)
            if is_yield:
                row[f"Local {pk} (bps)"] = local_ret
            else:
                row[f"Local {pk}"] = local_ret
                row[f"USD {pk}"] = usd_adjusted_return(local_ret, local_ccy, pk, fx_cache)

        rows.append(row)
        time.sleep(0.3)  # Rate limiting

    return rows


def collect_fred_yields():
    """Collect sovereign yields from FRED."""
    print("\nFetching FRED yields...")
    rows = []

    for name, series_id in FRED_YIELDS.items():
        print(f"  {series_id} ({name})...")
        series = fetch_fred_series(series_id)

        row = {
            "Symbol": series_id, "Name": name, "Region": "Sovereign",
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
        """Return % change in ratio of two tickers."""
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
        # Relative return: (1+n)/(1+d) - 1
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
            row[f"USD {pk}"] = np.nan  # Ratios not FX-adjusted
        ratio_rows.append(row)

    return ratio_rows


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
    # Normalise columns — yield rows use bps columns, others use % columns
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

    print(f"\n✓ Saved {main_path} — {len(df_main)} instruments")
    print(f"✓ Saved {sentiment_path} — {len(df_sentiment)} indicators")
    print(f"✓ Completed at {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")

    # Print summary
    print("\n--- Asset class breakdown ---")
    if "Asset Class" in df_main.columns:
        print(df_main["Asset Class"].value_counts().to_string())


if __name__ == "__main__":
    main()
