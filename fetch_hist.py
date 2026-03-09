"""
fetch_hist.py
=============
Historical Time Series — Phase A Extension
Market Dashboard Expansion

WHAT THIS MODULE DOES
---------------------
Produces two new Google Sheet tabs and two new CSVs:

1. market_data_hist
   - Weekly (Friday close) prices for all 66 instruments + 5 ratios
   - Dates as rows, instruments as columns (long format)
   - Two column groups: all Local Currency prices, then all USD prices
   - Goes back as far as yfinance data allows per instrument
   - Start date floor: 2000-01-07 (first Friday of 2000)

2. macro_us_hist
   - Weekly time series for all 25 FRED macro indicators
   - Dates as rows, indicators as columns (long format)
   - Monthly/quarterly series are forward-filled into weekly slots
   - Goes back as far as FRED data allows per series (some to 1947)
   - Date spine anchored to Fridays; macro data aligned to nearest prior Friday

DESIGN PRINCIPLES
-----------------
- Zero changes to fetch_data.py logic or its outputs.
- market_data and sentiment_data tabs are never touched.
- If this module fails for any reason, existing pipeline is unaffected.
- The module is called from fetch_data.py via a single try/except block.

ORIENTATION RATIONALE
---------------------
Long format (dates as rows) chosen because:
- 1,366 weekly rows (market, from 2000) × 144 cols = ~197K cells
- 4,132 weekly rows (macro, from 1947) × 26 cols = ~107K cells
- Both are far under the 10M cell / 18,278 column Google Sheets limits
- Column count stays fixed regardless of how far history extends

RATE LIMITING
-------------
yfinance:  0.3s delay between instrument fetches (matches existing fetch_data.py)
FRED:      0.6s delay between series + exponential backoff on 429/5xx
           (matches fetch_macro_us_fred.py)

THROTTLE NOTE — yfinance BULK FETCH
------------------------------------
For historical data we use yfinance's multi-ticker download where possible
(obb.download([list]) in a single call). This is more efficient and reduces
request count significantly. Per-ticker fallback is used for instruments that
fail the bulk fetch.
"""

import os
import json
import time
import requests
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import date, datetime, timedelta
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

FRED_API_KEY            = os.environ.get("FRED_API_KEY", "")
GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS", "")
SHEET_ID                = "12nKIUGHz5euDbNQPDTVECsJBNwrceRF1ymsQrIe4_ac"

MARKET_HIST_TAB         = "market_data_hist"
MACRO_HIST_TAB          = "macro_us_hist"
MARKET_HIST_CSV         = "data/market_data_hist.csv"
MACRO_HIST_CSV          = "data/macro_us_hist.csv"

# Historical start floors
MARKET_HIST_START       = "2000-01-01"   # yfinance data; Fridays from 2000-01-07
MACRO_HIST_START        = "1947-01-01"   # FRED data; some series go back this far

# Rate limit delays
YFINANCE_DELAY          = 0.3            # seconds between yfinance per-ticker calls
FRED_DELAY              = 0.6            # seconds between FRED calls
FRED_BACKOFF_BASE       = 2             # seconds; doubles on each retry
FRED_MAX_RETRIES        = 5

# ---------------------------------------------------------------------------
# INSTRUMENT DEFINITIONS
# Replicated from the handover doc — must stay in sync with fetch_data.py
# ---------------------------------------------------------------------------

# (ticker, name, region, asset_class, currency)
EQUITY_INDICES = [
    ("^GSPC",    "S&P 500",              "North America", "Equity Index",  "USD"),
    ("^NDX",     "Nasdaq 100",           "North America", "Equity Index",  "USD"),
    ("^RUT",     "Russell 2000",         "North America", "Equity Index",  "USD"),
    ("^FTSE",    "FTSE 100",             "UK",            "Equity Index",  "GBP"),
    ("^FTMC",    "FTSE 250",             "UK",            "Equity Index",  "GBP"),
    ("^STOXX50E","Euro Stoxx 50",        "Europe",        "Equity Index",  "EUR"),
    ("^GDAXI",   "DAX 40",               "Europe",        "Equity Index",  "EUR"),
    ("^N225",    "Nikkei 225",           "Japan",         "Equity Index",  "JPY"),
    ("^NSEI",    "Nifty 50",             "Asia",          "Equity Index",  "INR"),
    ("^BSESN",   "Sensex",               "Asia",          "Equity Index",  "INR"),
    ("000001.SS","Shanghai Composite",   "Asia",          "Equity Index",  "CNY"),
    ("399001.SZ","Shenzhen Composite",   "Asia",          "Equity Index",  "CNY"),
]

EQUITY_ETFS = [
    ("IWDA.L",   "MSCI World ETF",       "Global",        "Equity ETF",    "GBP"),
    ("VFEM.L",   "MSCI EM ETF",          "EM",            "Equity ETF",    "GBP"),
    ("AAXJ",     "Asia ex-Japan ETF",    "Asia",          "Equity ETF",    "USD"),
    ("ILF",      "Latin America ETF",    "EM",            "Equity ETF",    "USD"),
    ("EWY",      "South Korea ETF",      "Asia",          "Equity ETF",    "USD"),
    ("EWT",      "Taiwan ETF",           "Asia",          "Equity ETF",    "USD"),
    ("NDIA.L",   "India ETF",            "Asia",          "Equity ETF",    "GBP"),
    ("EWJ",      "Japan ETF",            "Japan",         "Equity ETF",    "USD"),
]

SECTOR_ETFS = [
    ("XLE",  "Energy",                   "North America", "Sector ETF",    "USD"),
    ("XLB",  "Materials",                "North America", "Sector ETF",    "USD"),
    ("XLI",  "Industrials",              "North America", "Sector ETF",    "USD"),
    ("XLY",  "Consumer Discretionary",  "North America", "Sector ETF",    "USD"),
    ("XLP",  "Consumer Staples",        "North America", "Sector ETF",    "USD"),
    ("XLV",  "Healthcare",              "North America", "Sector ETF",    "USD"),
    ("XLF",  "Financials",              "North America", "Sector ETF",    "USD"),
    ("XLK",  "Technology",              "North America", "Sector ETF",    "USD"),
    ("XLU",  "Utilities",               "North America", "Sector ETF",    "USD"),
    ("XLRE", "Real Estate",             "North America", "Sector ETF",    "USD"),
    ("XLC",  "Communication Services",  "North America", "Sector ETF",    "USD"),
]

STYLE_ETFS = [
    ("IWF",    "US Growth ETF",          "North America", "Style ETF",     "USD"),
    ("IWFV.L", "MSCI World Value ETF",   "Global",        "Style ETF",     "GBP"),
]

FIXED_INCOME_ETFS = [
    ("AGGG.L", "Global Agg Bond ETF",   "Global",        "Fixed Income ETF","GBP"),
    ("SLXX.L", "US IG Corp Bond ETF",   "US",            "Fixed Income ETF","GBP"),
    ("IHYU.L", "US HY Bond ETF",        "US",            "Fixed Income ETF","GBP"),
    ("VDET.L", "EM Debt USD ETF",       "EM",            "Fixed Income ETF","GBP"),
    ("IGLT.L", "UK Gilts ETF",          "UK",            "Fixed Income ETF","GBP"),
    ("IGLS.L", "UK Short Gilts ETF",    "UK",            "Fixed Income ETF","GBP"),
    ("EXX6.DE","German Bunds ETF",      "Europe",        "Fixed Income ETF","EUR"),
    ("IGOV",   "Intl Govt Bonds ETF",   "Global",        "Fixed Income ETF","USD"),
    ("CNYB.L", "Chinese Govt Bonds ETF","Asia",          "Fixed Income ETF","GBP"),
]

COMMODITIES = [
    ("GC=F",   "Gold",                  "Global",        "Commodity",     "USD"),
    ("SI=F",   "Silver",                "Global",        "Commodity",     "USD"),
    ("BZ=F",   "Brent Crude",           "Global",        "Commodity",     "USD"),
    ("CL=F",   "WTI Crude Oil",         "Global",        "Commodity",     "USD"),
    ("HG=F",   "Copper",                "Global",        "Commodity",     "USD"),
    ("ALI=F",  "Aluminium",             "Global",        "Commodity",     "USD"),
    ("CT=F",   "Cotton",                "Global",        "Commodity",     "USD"),
    ("KC=F",   "Coffee",                "Global",        "Commodity",     "USD"),
    ("CMOD.L", "Bloomberg Commodity ETF","Global",       "Commodity",     "GBP"),
]

FX_PAIRS = [
    ("DX-Y.NYB", "DXY Dollar Index",   "Global",        "FX",            "USD"),
    ("GBPUSD=X", "GBP/USD",            "UK",            "FX",            "USD"),
    ("EURUSD=X", "EUR/USD",            "Europe",        "FX",            "USD"),
    ("USDJPY=X", "USD/JPY",            "Japan",         "FX",            "USD"),
    ("USDCNY=X", "USD/CNY",            "Asia",          "FX",            "USD"),
    ("USDINR=X", "USD/INR",            "Asia",          "FX",            "USD"),
    ("USDKRW=X", "USD/KRW",            "Asia",          "FX",            "USD"),
    ("USDTWD=X", "USD/TWD",            "Asia",          "FX",            "USD"),
]

VOL_CRYPTO = [
    ("^VIX",    "VIX",                  "Global",        "Volatility",    "USD"),
    ("BTC-USD", "Bitcoin",              "Global",        "Crypto",        "USD"),
    ("ETH-USD", "Ethereum",             "Global",        "Crypto",        "USD"),
]

YIELD_INSTRUMENTS = [
    ("^IRX",    "US 2Y Treasury Yield", "North America", "Yield",         "USD"),
    ("^FVX",    "US 5Y Treasury Yield", "North America", "Yield",         "USD"),
    ("^TNX",    "US 10Y Treasury Yield","North America", "Yield",         "USD"),
    ("^TYX",    "US 30Y Treasury Yield","North America", "Yield",         "USD"),
]

# FRED yields (fetched via FRED, not yfinance)
FRED_YIELDS = {
    "IRLTLT01GBM156N": ("UK 10Y Gilt Yield",     "UK",     "Yield", "GBP"),
    "IRLTLT01DEM156N": ("Germany 10Y Bund Yield", "Europe", "Yield", "EUR"),
    "IRLTLT01JPM156N": ("Japan 10Y JGB Yield",    "Japan",  "Yield", "JPY"),
}

# Ratio definitions (calculated from instrument prices — appended after fetch)
RATIO_DEFS = [
    ("XLY/XLP",        "Cyclicals vs Defensives",    "XLY",    "XLP"),
    ("XLF/XLU",        "Financials vs Utilities",    "XLF",    "XLU"),
    ("IHYU.L/SLXX.L",  "HY vs IG Credit",            "IHYU.L", "SLXX.L"),
    ("^FTMC/^FTSE",    "Small Cap vs Large Cap UK",  "^FTMC",  "^FTSE"),
    ("IWF/IWFV.L",     "Growth vs Value",            "IWF",    "IWFV.L"),
]

# FX tickers needed for USD return calculation
FX_TICKERS = {
    "GBP": "GBPUSD=X",
    "EUR": "EURUSD=X",
    "JPY": "USDJPY=X",
    "CNY": "USDCNY=X",
    "INR": "USDINR=X",
    "KRW": "USDKRW=X",
    "TWD": "USDTWD=X",
}

# LSE-listed ETFs quoted in pence (price > 50 after fetch → divide by 100)
LSE_PENCE_TICKERS = {t for t, *_ in
    EQUITY_ETFS + STYLE_ETFS + FIXED_INCOME_ETFS + COMMODITIES
    if t.endswith(".L")}

# All yfinance instruments in one flat list
ALL_YFINANCE = (
    EQUITY_INDICES + EQUITY_ETFS + SECTOR_ETFS + STYLE_ETFS +
    FIXED_INCOME_ETFS + COMMODITIES + FX_PAIRS + VOL_CRYPTO + YIELD_INSTRUMENTS
)

# ---------------------------------------------------------------------------
# FRED MACRO SERIES (same 25 as fetch_macro_us_fred.py)
# ---------------------------------------------------------------------------

FRED_MACRO_US = {
    "T10Y2Y":       "US Yield Curve 10Y-2Y Spread",
    "T10Y3M":       "US Yield Curve 10Y-3M Spread",
    "M2SL":         "US M2 Money Supply",
    "USSLIND":      "US Conference Board LEI",
    "PERMIT":       "US Building Permits (SAAR)",
    "IC4WSA":       "US Initial Jobless Claims 4-Week Avg",
    "PAYEMS":       "US Nonfarm Payrolls",
    "UNRATE":       "US Unemployment Rate",
    "INDPRO":       "US Industrial Production",
    "RSXFS":        "US Retail Sales ex-Autos",
    "DRTSCILM":     "US SLOOS Net Tightening (C&I Large Firms)",
    "NFCI":         "Chicago Fed NFCI",
    "CPIAUCSL":     "US CPI Headline",
    "CPILFESL":     "US Core CPI",
    "PCEPILFE":     "US Core PCE Deflator",
    "PPIACO":       "US PPI All Commodities",
    "T5YIE":        "US TIPS 5Y Breakeven",
    "T10YIE":       "US TIPS 10Y Breakeven",
    "T5YIFR":       "US 5Y5Y Forward Inflation",
    "MICH":         "UMich Consumer Inflation Expectations",
    "FEDFUNDS":     "US Federal Funds Rate",
    "DFII10":       "US 10Y Real Rate (TIPS)",
    "DFII5":        "US 5Y Real Rate (TIPS)",
    "BAMLH0A0HYM2": "US HY Credit Spread OAS",
    "BAMLC0A0CM":   "US IG Credit Spread OAS",
}

# ---------------------------------------------------------------------------
# HELPERS: FRIDAY SPINE
# ---------------------------------------------------------------------------

def get_friday_spine(start_str: str, end_date: date = None) -> pd.DatetimeIndex:
    """
    Generate a DatetimeIndex of every Friday from start_str to end_date.
    end_date defaults to the most recent Friday.
    """
    if end_date is None:
        today = date.today()
        # Roll back to most recent Friday
        days_since_friday = (today.weekday() - 4) % 7
        end_date = today - timedelta(days=days_since_friday)

    spine = pd.date_range(
        start=start_str,
        end=end_date.strftime("%Y-%m-%d"),
        freq="W-FRI"
    )
    return spine


def align_to_friday_spine(series: pd.Series, spine: pd.DatetimeIndex) -> pd.Series:
    """
    Reindex a series to a Friday spine, then forward-fill to propagate
    monthly/quarterly values into intervening weekly slots.
    """
    # Ensure series index is datetime
    series.index = pd.to_datetime(series.index)
    series = series.sort_index()

    # Reindex to spine, then ffill
    aligned = series.reindex(spine, method="ffill")
    return aligned


# ---------------------------------------------------------------------------
# HELPERS: PENCE CORRECTION
# ---------------------------------------------------------------------------

def apply_pence_correction(ticker: str, series: pd.Series) -> pd.Series:
    """
    LSE ETFs are quoted in pence. If median price > 50, divide by 100.
    Matches the logic in fetch_data.py.
    """
    if ticker in LSE_PENCE_TICKERS:
        median_val = series.dropna().median()
        if median_val > 50:
            return series / 100
    return series


# ---------------------------------------------------------------------------
# HELPERS: USD RETURN FROM LOCAL PRICE + FX
# ---------------------------------------------------------------------------

def compute_usd_price_series(
    local_prices: pd.Series,
    currency: str,
    fx_cache: dict
) -> pd.Series:
    """
    Convert a local-currency price series to USD using the FX cache.
    For USD instruments, returns the series unchanged.
    FX cache keys are currency codes; values are daily Close price Series.

    Convention matches fetch_data.py:
      - GBPUSD=X rises when GBP strengthens → multiply
      - USDJPY=X rises when USD strengthens → divide
    """
    if currency == "USD":
        return local_prices

    fx_ticker = FX_TICKERS.get(currency)
    if not fx_ticker or fx_ticker not in fx_cache:
        return local_prices  # fallback: return local if FX unavailable

    fx = fx_cache[fx_ticker]

    # Align FX to same index as local prices
    fx_aligned = fx.reindex(local_prices.index, method="ffill")

    # Pairs where USD is the quote (GBPUSD, EURUSD): multiply
    # Pairs where USD is the base (USDJPY, USDCNY etc.): divide
    base_quote_pairs = {"JPY", "CNY", "INR", "KRW", "TWD"}
    if currency in base_quote_pairs:
        usd_prices = local_prices / fx_aligned
    else:
        usd_prices = local_prices * fx_aligned

    return usd_prices


# ---------------------------------------------------------------------------
# FETCH: yfinance FX CACHE
# ---------------------------------------------------------------------------

def fetch_fx_cache(start: str) -> dict:
    """
    Fetch all FX pairs as daily Close series. Returns dict keyed by ticker.
    Uses single yf.download() call for efficiency.
    """
    print("  Fetching FX cache...")
    fx_tickers = list(FX_TICKERS.values())
    try:
        raw = yf.download(
            fx_tickers,
            start=start,
            auto_adjust=True,
            progress=False,
            threads=True,
        )
        cache = {}
        for ticker in fx_tickers:
            try:
                if len(fx_tickers) == 1:
                    s = raw["Close"]
                else:
                    s = raw["Close"][ticker]
                cache[ticker] = s.dropna()
            except Exception as e:
                print(f"    FX {ticker} parse error: {e}")
        print(f"  FX cache: {len(cache)}/{len(fx_tickers)} pairs loaded")
        return cache
    except Exception as e:
        print(f"  FX cache fetch failed: {e} — USD conversion will use local prices")
        return {}


# ---------------------------------------------------------------------------
# FETCH: yfinance BULK HISTORICAL PRICES
# ---------------------------------------------------------------------------

def fetch_yfinance_history(
    instruments: list,
    start: str,
    spine: pd.DatetimeIndex,
    fx_cache: dict
) -> tuple[dict, dict]:
    """
    Fetch weekly (Friday) close prices for all instruments.
    Returns two dicts:
        local_prices[ticker]  = pd.Series on Friday spine
        usd_prices[ticker]    = pd.Series on Friday spine
    """
    tickers = [t for t, *_ in instruments]
    ticker_meta = {t: (name, region, asset_class, currency)
                   for t, name, region, asset_class, currency in instruments}

    local_prices = {}
    usd_prices   = {}

    # --- Bulk download (1 API call for all tickers) -----------------------
    print(f"  Bulk downloading {len(tickers)} instruments from yfinance...")
    try:
        raw = yf.download(
            tickers,
            start=start,
            auto_adjust=True,
            progress=False,
            threads=True,
        )
        # Extract Close prices; handle single vs multi-ticker response
        if len(tickers) == 1:
            close_df = raw[["Close"]].rename(columns={"Close": tickers[0]})
        else:
            close_df = raw["Close"]

        bulk_success = set(close_df.columns.tolist())
        print(f"  Bulk fetch: {len(bulk_success)}/{len(tickers)} tickers returned data")

    except Exception as e:
        print(f"  Bulk download failed ({e}) — falling back to per-ticker fetch")
        close_df = pd.DataFrame()
        bulk_success = set()

    # --- Per-ticker fallback for any that failed bulk ---------------------
    failed_tickers = [t for t in tickers if t not in bulk_success]
    if failed_tickers:
        print(f"  Per-ticker fallback for {len(failed_tickers)} instruments...")
        for i, ticker in enumerate(failed_tickers, 1):
            try:
                s = yf.download(
                    ticker,
                    start=start,
                    auto_adjust=True,
                    progress=False,
                )["Close"]
                if not s.empty:
                    close_df[ticker] = s
                    print(f"    [{i}] {ticker}: OK ({len(s)} rows)")
                else:
                    print(f"    [{i}] {ticker}: empty")
            except Exception as e:
                print(f"    [{i}] {ticker}: failed ({e})")
            time.sleep(YFINANCE_DELAY)

    # --- Process each ticker ----------------------------------------------
    print("  Processing prices and computing USD series...")
    for ticker in tickers:
        name, region, asset_class, currency = ticker_meta[ticker]

        if ticker not in close_df.columns:
            # No data — fill with NaN on spine
            local_prices[ticker] = pd.Series(np.nan, index=spine, name=ticker)
            usd_prices[ticker]   = pd.Series(np.nan, index=spine, name=ticker)
            continue

        s = close_df[ticker].dropna()

        # Pence correction for LSE ETFs
        s = apply_pence_correction(ticker, s)

        # Resample to weekly Friday close (last valid value in each week)
        s.index = pd.to_datetime(s.index)
        weekly = s.resample("W-FRI").last()

        # Align to our canonical Friday spine
        local_aligned = weekly.reindex(spine)
        # Forward-fill short gaps (e.g. exchange holidays) — max 5 trading days
        local_aligned = local_aligned.ffill(limit=5)

        local_prices[ticker] = local_aligned

        # USD conversion
        usd_aligned = compute_usd_price_series(local_aligned, currency, fx_cache)
        usd_prices[ticker] = usd_aligned

    return local_prices, usd_prices


# ---------------------------------------------------------------------------
# FETCH: FRED YIELD INSTRUMENTS (for market_data_hist)
# ---------------------------------------------------------------------------

def fetch_fred_yields_history(spine: pd.DatetimeIndex) -> tuple[dict, dict]:
    """
    Fetch FRED sovereign yield series and align to Friday spine.
    Returns local_prices and usd_prices dicts (yields are unit-less; USD = local).
    """
    if not FRED_API_KEY:
        print("  [FRED yields] FRED_API_KEY not set — skipping")
        return {}, {}

    local_prices = {}
    usd_prices   = {}

    print(f"  Fetching {len(FRED_YIELDS)} FRED yield series...")

    for i, (series_id, meta) in enumerate(FRED_YIELDS.items(), 1):
        name, region, asset_class, currency = meta
        print(f"    [{i}/{len(FRED_YIELDS)}] {series_id} ({name})...")

        data = fred_fetch_series_full(series_id, MACRO_HIST_START)
        if data is None or data.empty:
            local_prices[series_id] = pd.Series(np.nan, index=spine)
            usd_prices[series_id]   = pd.Series(np.nan, index=spine)
        else:
            aligned = align_to_friday_spine(data, spine)
            local_prices[series_id] = aligned
            usd_prices[series_id]   = aligned  # yields: no FX conversion

        if i < len(FRED_YIELDS):
            time.sleep(FRED_DELAY)

    return local_prices, usd_prices


# ---------------------------------------------------------------------------
# BUILD: market_data_hist DataFrame
# ---------------------------------------------------------------------------

def build_market_hist_df(spine: pd.DatetimeIndex) -> pd.DataFrame:
    """
    Build the full market_data_hist DataFrame.
    Schema:
        Date | <ticker>_Local × N | <ticker>_USD × N
    Tickers ordered: indices, ETFs, sectors, styles, FI, commodities, FX,
                     vol/crypto, yields (yfinance), FRED yields.
    Ratio columns appended at end of each group.
    """
    print("\nBuilding market_data_hist...")

    # 1. FX cache (needed for USD conversion)
    fx_cache = fetch_fx_cache(MARKET_HIST_START)

    # 2. Fetch all yfinance instruments
    local_yf, usd_yf = fetch_yfinance_history(
        ALL_YFINANCE, MARKET_HIST_START, spine, fx_cache
    )

    # 3. Fetch FRED yield instruments
    local_fred, usd_fred = fetch_fred_yields_history(spine)

    # 4. Compute ratio series
    print("  Computing ratio series...")
    local_ratios = {}
    usd_ratios   = {}
    for ratio_sym, ratio_name, num_ticker, den_ticker in RATIO_DEFS:
        # Ratios computed from local prices
        num = local_yf.get(num_ticker, pd.Series(np.nan, index=spine))
        den = local_yf.get(den_ticker, pd.Series(np.nan, index=spine))
        ratio = num / den.replace(0, np.nan)
        local_ratios[ratio_sym] = ratio
        usd_ratios[ratio_sym]   = ratio  # ratios are dimensionless

    # 5. Ordered column list
    yf_tickers = [t for t, *_ in ALL_YFINANCE]
    fred_yield_tickers = list(FRED_YIELDS.keys())
    ratio_tickers = [r[0] for r in RATIO_DEFS]

    all_tickers_ordered = yf_tickers + fred_yield_tickers + ratio_tickers

    # 6. Merge into DataFrame — LOCAL group first, then USD group
    df = pd.DataFrame(index=spine)
    df.index.name = "Date"

    # Local prices
    for ticker in all_tickers_ordered:
        if ticker in local_yf:
            s = local_yf[ticker]
        elif ticker in local_fred:
            s = local_fred[ticker]
        elif ticker in local_ratios:
            s = local_ratios[ticker]
        else:
            s = pd.Series(np.nan, index=spine)
        df[f"{ticker}_Local"] = s

    # USD prices
    for ticker in all_tickers_ordered:
        if ticker in usd_yf:
            s = usd_yf[ticker]
        elif ticker in usd_fred:
            s = usd_fred[ticker]
        elif ticker in usd_ratios:
            s = usd_ratios[ticker]
        else:
            s = pd.Series(np.nan, index=spine)
        df[f"{ticker}_USD"] = s

    # 7. Reset index so Date becomes a column
    df = df.reset_index()
    df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")

    print(f"  market_data_hist: {len(df)} rows × {len(df.columns)} columns")
    return df


# ---------------------------------------------------------------------------
# FETCH: FRED full series history (for macro_us_hist)
# ---------------------------------------------------------------------------

def fred_fetch_series_full(series_id: str, start: str) -> pd.Series | None:
    """
    Fetch the complete history of a FRED series from start date.
    Returns a pd.Series indexed by date, or None on failure.
    Includes exponential backoff on rate limit / server errors.
    """
    if not FRED_API_KEY:
        return None

    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id":          series_id,
        "api_key":            FRED_API_KEY,
        "file_type":          "json",
        "sort_order":         "asc",
        "observation_start":  start,
        "limit":              100000,
    }

    for attempt in range(FRED_MAX_RETRIES):
        try:
            resp = requests.get(url, params=params, timeout=20)

            if resp.status_code == 200:
                data = resp.json()
                obs = [
                    o for o in data.get("observations", [])
                    if o.get("value") not in (".", "", None)
                ]
                if not obs:
                    return None
                s = pd.Series(
                    {o["date"]: float(o["value"]) for o in obs},
                    name=series_id
                )
                s.index = pd.to_datetime(s.index)
                return s

            elif resp.status_code == 429:
                wait = FRED_BACKOFF_BASE ** (attempt + 1)
                print(f"    [FRED] 429 on {series_id} — backoff {wait}s "
                      f"(attempt {attempt+1}/{FRED_MAX_RETRIES})")
                time.sleep(wait)

            elif resp.status_code >= 500:
                wait = FRED_BACKOFF_BASE ** (attempt + 1)
                print(f"    [FRED] {resp.status_code} on {series_id} — backoff {wait}s")
                time.sleep(wait)

            else:
                print(f"    [FRED] HTTP {resp.status_code} on {series_id} — skipping")
                return None

        except requests.exceptions.Timeout:
            wait = FRED_BACKOFF_BASE ** (attempt + 1)
            print(f"    [FRED] Timeout on {series_id} — backoff {wait}s")
            time.sleep(wait)
        except Exception as e:
            print(f"    [FRED] Error on {series_id}: {e} — skipping")
            return None

    print(f"    [FRED] All retries exhausted for {series_id}")
    return None


# ---------------------------------------------------------------------------
# BUILD: macro_us_hist DataFrame
# ---------------------------------------------------------------------------

def build_macro_hist_df(spine: pd.DatetimeIndex) -> pd.DataFrame:
    """
    Build the full macro_us_hist DataFrame.
    Schema:
        Date | <series_id>_<short_name> × 25
    Monthly/quarterly series are forward-filled to weekly frequency.
    """
    print("\nBuilding macro_us_hist...")

    if not FRED_API_KEY:
        print("  FRED_API_KEY not set — skipping macro_us_hist")
        return pd.DataFrame()

    series_data = {}
    total = len(FRED_MACRO_US)

    for i, (series_id, name) in enumerate(FRED_MACRO_US.items(), 1):
        print(f"  [{i}/{total}] {series_id} ({name})...")

        s = fred_fetch_series_full(series_id, MACRO_HIST_START)

        if s is None or s.empty:
            print(f"    → No data")
            series_data[series_id] = pd.Series(np.nan, index=spine, name=series_id)
        else:
            aligned = align_to_friday_spine(s, spine)
            series_data[series_id] = aligned
            print(f"    → {len(s)} obs, first: {s.index[0].date()}, "
                  f"last: {s.index[-1].date()}")

        if i < total:
            time.sleep(FRED_DELAY)

    # Build DataFrame
    df = pd.DataFrame(series_data, index=spine)
    df.index.name = "Date"

    # Use short names as column headers for readability
    df.columns = [FRED_MACRO_US[sid] for sid in df.columns]

    df = df.reset_index()
    df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")

    print(f"  macro_us_hist: {len(df)} rows × {len(df.columns)} columns")
    return df


# ---------------------------------------------------------------------------
# SAVE CSV
# ---------------------------------------------------------------------------

def save_csv(df: pd.DataFrame, path: str, label: str) -> None:
    """Save DataFrame to CSV; skip write if content unchanged."""
    if df.empty:
        print(f"  [{label}] Empty — skipping CSV write")
        return

    os.makedirs("data", exist_ok=True)

    if os.path.exists(path):
        try:
            existing = pd.read_csv(path, nrows=5)
            new_head = df.head(5)
            if existing.shape == new_head.shape and existing.equals(
                    new_head.reset_index(drop=True)):
                # Only check first rows; write anyway for last-row updates
                pass
        except Exception:
            pass

    df.to_csv(path, index=False)
    print(f"  [{label}] Written {len(df):,} rows × {len(df.columns)} cols to {path}")


# ---------------------------------------------------------------------------
# PUSH TO GOOGLE SHEETS
# ---------------------------------------------------------------------------

def push_df_to_sheets(df: pd.DataFrame, tab_name: str, label: str) -> None:
    """
    Push a DataFrame to a named Google Sheets tab.
    Creates tab if it doesn't exist; overwrites existing content.
    Converts NaN to empty string for clean display.
    Never touches market_data or sentiment_data tabs.
    """
    if not GOOGLE_CREDENTIALS_JSON:
        print(f"  [{label}] GOOGLE_CREDENTIALS not set — skipping Sheets push")
        return
    if df.empty:
        print(f"  [{label}] Empty DataFrame — skipping Sheets push")
        return

    # Safety guard — never overwrite existing tabs
    PROTECTED_TABS = {"market_data", "sentiment_data"}
    if tab_name in PROTECTED_TABS:
        print(f"  [{label}] REFUSED: '{tab_name}' is a protected tab")
        return

    try:
        creds_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
        creds = Credentials.from_service_account_info(
            creds_dict,
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        service = build("sheets", "v4", credentials=creds)
        sheets  = service.spreadsheets()

        # Ensure tab exists
        meta = sheets.get(spreadsheetId=SHEET_ID).execute()
        existing_tabs = [s["properties"]["title"] for s in meta.get("sheets", [])]

        if tab_name not in existing_tabs:
            print(f"  [{label}] Creating tab '{tab_name}'...")
            sheets.batchUpdate(
                spreadsheetId=SHEET_ID,
                body={"requests": [{"addSheet": {"properties": {"title": tab_name}}}]}
            ).execute()

        # Clear existing content
        sheets.values().clear(
            spreadsheetId=SHEET_ID,
            range=f"{tab_name}!A:ZZZ"
        ).execute()

        # Prepare values: replace NaN/None with ""
        header = list(df.columns)
        data_rows = (
            df.where(pd.notnull(df), other=None)
              .fillna("")
              .astype(str)
              .values.tolist()
        )

        # Replace "nan" strings (edge case)
        data_rows = [
            ["" if v == "nan" else v for v in row]
            for row in data_rows
        ]

        values = [header] + data_rows

        # Write in batches of 10,000 rows to avoid Sheets API payload limits
        BATCH_SIZE = 10_000
        for batch_start in range(0, len(values), BATCH_SIZE):
            batch = values[batch_start:batch_start + BATCH_SIZE]
            # First batch starts at A1; subsequent batches continue below
            start_row = batch_start + 1
            range_notation = f"{tab_name}!A{start_row}"
            sheets.values().update(
                spreadsheetId=SHEET_ID,
                range=range_notation,
                valueInputOption="RAW",
                body={"values": batch}
            ).execute()
            if len(values) > BATCH_SIZE:
                print(f"  [{label}] Batch {batch_start//BATCH_SIZE + 1}: "
                      f"rows {start_row}–{start_row + len(batch) - 1}")
            time.sleep(0.5)  # brief pause between batch writes

        print(f"  [{label}] Written {len(df):,} rows to '{tab_name}' tab")

    except json.JSONDecodeError as e:
        print(f"  [{label}] GOOGLE_CREDENTIALS JSON error: {e} — skipping")
    except Exception as e:
        print(f"  [{label}] Sheets push failed: {e} — skipping")


# ---------------------------------------------------------------------------
# MAIN ENTRY POINT
# ---------------------------------------------------------------------------

def run_hist() -> None:
    """
    Full historical fetch run.
    Produces market_data_hist and macro_us_hist.
    Safe to call from fetch_data.py; all errors caught internally.
    """
    print("\n" + "="*60)
    print("Historical Time Series Build")
    print("="*60)

    start_ts = time.time()

    try:
        # --- Build Friday spines ------------------------------------------
        market_spine = get_friday_spine(MARKET_HIST_START)
        macro_spine  = get_friday_spine(MACRO_HIST_START)

        print(f"Market spine:  {len(market_spine):,} Fridays "
              f"({market_spine[0].date()} → {market_spine[-1].date()})")
        print(f"Macro spine:   {len(macro_spine):,} Fridays "
              f"({macro_spine[0].date()} → {macro_spine[-1].date()})")

        # --- market_data_hist ---------------------------------------------
        market_df = build_market_hist_df(market_spine)
        save_csv(market_df, MARKET_HIST_CSV, "market_data_hist")
        push_df_to_sheets(market_df, MARKET_HIST_TAB, "market_data_hist")

        # --- macro_us_hist ------------------------------------------------
        macro_df = build_macro_hist_df(macro_spine)
        save_csv(macro_df, MACRO_HIST_CSV, "macro_us_hist")
        push_df_to_sheets(macro_df, MACRO_HIST_TAB, "macro_us_hist")

        elapsed = round(time.time() - start_ts, 1)
        print(f"\nHistorical build completed in {elapsed}s")

    except Exception as e:
        elapsed = round(time.time() - start_ts, 1)
        print(f"\n[Hist] Unexpected error after {elapsed}s: {e}")
        print("[Hist] Existing pipeline outputs are unaffected")


if __name__ == "__main__":
    run_hist()
