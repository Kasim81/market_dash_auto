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
from datetime import date, datetime, timedelta, timezone
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
MARKET_HIST_START       = "1980-01-01"   # yfinance data; ETF columns NaN before launch date
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
    ("XLE",  "Energy",                   "US",            "Sector ETF",    "USD"),
    ("XLB",  "Materials",                "US",            "Sector ETF",    "USD"),
    ("XLI",  "Industrials",              "US",            "Sector ETF",    "USD"),
    ("XLY",  "Consumer Discretionary",  "US",            "Sector ETF",    "USD"),
    ("XLP",  "Consumer Staples",        "US",            "Sector ETF",    "USD"),
    ("XLV",  "Healthcare",              "US",            "Sector ETF",    "USD"),
    ("XLF",  "Financials",              "US",            "Sector ETF",    "USD"),
    ("XLK",  "Technology",              "US",            "Sector ETF",    "USD"),
    ("XLU",  "Utilities",               "US",            "Sector ETF",    "USD"),
    ("XLRE", "Real Estate",             "US",            "Sector ETF",    "USD"),
    ("XLC",  "Communication Services",  "US",            "Sector ETF",    "USD"),
]

STYLE_ETFS = [
    ("IWF",    "US Growth ETF",          "US",            "Style ETF",     "USD"),
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
    ("^VIX",    "VIX",                  "US",            "Volatility",    "USD"),
    ("BTC-USD", "Bitcoin",              "Global",        "Crypto",        "USD"),
    ("ETH-USD", "Ethereum",             "Global",        "Crypto",        "USD"),
]

YIELD_INSTRUMENTS = [
    ("^IRX",    "US 3-Month T-Bill",    "US",            "Yield",         "USD"),
    ("^FVX",    "US 5Y Treasury Yield", "US",            "Yield",         "USD"),
    ("^TNX",    "US 10Y Treasury Yield","US",            "Yield",         "USD"),
    ("^TYX",    "US 30Y Treasury Yield","US",            "Yield",         "USD"),
]

# FRED yields (fetched via FRED, not yfinance)
FRED_YIELDS = {
    "DGS2":              ("US 2Y Treasury Yield",  "US",     "Yield", "USD"),
    "IRLTLT01GBM156N":   ("UK 10Y Gilt Yield",     "UK",     "Yield", "GBP"),
    "IRLTLT01DEM156N":   ("Germany 10Y Bund Yield", "Europe", "Yield", "EUR"),
    "IRLTLT01JPM156N":   ("Japan 10Y JGB Yield",    "Japan",  "Yield", "JPY"),
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
# FRED MACRO SERIES — imported from fetch_macro_us_fred.py (single source of truth)
# ---------------------------------------------------------------------------

from fetch_macro_us_fred import FRED_MACRO_US as _FRED_MACRO_US_FULL
from fetch_macro_us_fred import FRED_MACRO_US_FREQ as _FRED_MACRO_US_FREQ

# Derive lookup dicts used in metadata prefix rows
FRED_MACRO_US_NAMES   = {k: v[0] for k, v in _FRED_MACRO_US_FULL.items()}
FRED_MACRO_US_CATS    = {k: v[1] for k, v in _FRED_MACRO_US_FULL.items()}
FRED_MACRO_US_SUBCATS = {k: v[2] for k, v in _FRED_MACRO_US_FULL.items()}
FRED_MACRO_US_UNITS   = {k: v[3] for k, v in _FRED_MACRO_US_FULL.items()}
FRED_MACRO_US_FREQ    = _FRED_MACRO_US_FREQ

# Map native FRED frequency → display string for hist tab (forward-filled to weekly)
_FREQ_TO_HIST_LABEL = {
    "Daily":     "Weekly (daily → ffill)",
    "Weekly":    "Weekly",
    "Monthly":   "Weekly (monthly → ffill)",
    "Quarterly": "Weekly (quarterly → ffill)",
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
                    if isinstance(s, pd.DataFrame):
                        s = s.iloc[:, 0]
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
        # Extract Close prices. In yfinance 1.x, raw["Close"] always returns a
        # DataFrame (MultiIndex default). In 0.2.x, single-ticker returns a Series.
        close_df = raw["Close"]
        if isinstance(close_df, pd.Series):
            close_df = close_df.to_frame(tickers[0])

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
                # yfinance 1.x returns a DataFrame for single-ticker downloads
                if isinstance(s, pd.DataFrame):
                    s = s.iloc[:, 0]
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
    total = len(_FRED_MACRO_US_FULL)

    for i, (series_id, meta) in enumerate(_FRED_MACRO_US_FULL.items(), 1):
        name = meta[0]
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

    # Build DataFrame — keep FRED series IDs as column headers;
    # human-readable names appear in the metadata prefix rows (row 1 = Name, row 2 = Category)
    df = pd.DataFrame(series_data, index=spine)
    df.index.name = "Date"

    df = df.reset_index()
    df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")

    print(f"  macro_us_hist: {len(df)} rows × {len(df.columns)} columns")
    return df


# ---------------------------------------------------------------------------
# SAVE CSV
# ---------------------------------------------------------------------------

def build_market_meta_prefix(df: pd.DataFrame) -> list:
    """
    Build metadata rows for market_data_hist.  Row order (label in col A):
      1. Ticker ID    — raw ticker without _Local/_USD suffix
      2. Variant      — "Local" or "USD"
      3. Source       — "yfinance", "FRED", or "Calculated"
      4. Name         — instrument display name
      5. Region       — geographic region
      6. Asset Class  — instrument type
      7. Currency     — original instrument currency (or "USD" for _USD columns)
      8. Units        — Index / Price / Rate / % pa / Ratio
      9. Frequency    — all weekly (Friday close or ffill)
     10. Last Updated — UTC timestamp of this run
    """
    run_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Build lookup: base_ticker -> (name, region, asset_class, local_currency)
    meta = {}
    for ticker, name, region, asset_class, currency in ALL_YFINANCE:
        meta[ticker] = (name, region, asset_class, currency)
    for series_id, (name, region, asset_class, currency) in FRED_YIELDS.items():
        meta[series_id] = (name, region, asset_class, currency)
    for ratio_id, ratio_name, num, den in RATIO_DEFS:
        num_meta = meta.get(num, ("", "Global", "Ratio", "Ratio"))
        meta[ratio_id] = (ratio_name, num_meta[1], "Ratio", "Ratio")

    # Source lookup: FRED yields and calculated ratios differ from yfinance
    fred_yield_ids = set(FRED_YIELDS.keys())
    ratio_ids      = {r[0] for r in RATIO_DEFS}

    # Asset-class → units mapping
    _ac_units = {
        "Equity Index":      "Index",
        "Equity ETF":        "Price",
        "Sector ETF":        "Price",
        "Style ETF":         "Price",
        "Fixed Income ETF":  "Price",
        "Commodity":         "Price",
        "FX":                "Rate",
        "Volatility":        "Index",
        "Crypto":            "Price",
        "Yield":             "% pa",
        "Ratio":             "Ratio",
    }

    # Broad Asset Class mapping (from granular asset_class → broad group label)
    _broad_ac_map = {
        "Equity Index":      "Equity",
        "Equity ETF":        "Equity",
        "Sector ETF":        "Equity",
        "Style ETF":         "Equity",
        "Fixed Income ETF":  "Bonds",
        "Commodity":         "Commodities",
        "FX":                "FX",
        "Volatility":        "Macro-Market Indicators",
        "Crypto":            "Crypto",
        "Yield":             "Bonds",
        "Ratio":             "Macro-Market Indicators",
    }

    ticker_id_row        = ["Ticker ID"]
    variant_row          = ["Variant"]
    source_row           = ["Source"]
    name_row             = ["Name"]
    region_row           = ["Region"]
    broad_asset_cls_row  = ["Broad Asset Class"]
    asset_class_row      = ["Sub-Category"]
    currency_row         = ["Currency"]
    units_row            = ["Units"]
    frequency_row        = ["Frequency"]
    updated_row          = ["Last Updated"]

    for col in df.columns:
        if col == "Date":
            continue

        if col.endswith("_Local"):
            base    = col[:-6]
            variant = "Local"
            is_usd  = False
        elif col.endswith("_USD"):
            base    = col[:-4]
            variant = "USD"
            is_usd  = True
        else:
            base    = col
            variant = ""
            is_usd  = False

        m          = meta.get(base, (base, "", "", ""))
        asset_cls  = m[2]
        broad_ac   = _broad_ac_map.get(asset_cls, asset_cls)

        if base in fred_yield_ids:
            source = "FRED"
        elif base in ratio_ids:
            source = "Calculated"
        else:
            source = "yfinance"

        ticker_id_row.append(base)
        variant_row.append(variant)
        source_row.append(source)
        name_row.append(m[0])
        region_row.append(m[1])
        broad_asset_cls_row.append(broad_ac)
        asset_class_row.append(asset_cls)
        currency_row.append("USD" if is_usd else m[3])
        units_row.append(_ac_units.get(asset_cls, ""))
        frequency_row.append("Weekly")
        updated_row.append(run_ts)

    return [
        ticker_id_row, variant_row, source_row,
        name_row, broad_asset_cls_row, region_row, asset_class_row, currency_row,
        units_row, frequency_row, updated_row,
    ]


def build_macro_meta_prefix(df: pd.DataFrame) -> list:
    """
    Build metadata rows for macro_us_hist.  Row order (label in col A):
      1. Series ID   — FRED series identifier (= column name)
      2. Source      — "FRED" for all
      3. Name        — full indicator name
      4. Category    — Growth / Inflation / Monetary Policy / Financial Conditions / Survey
      5. Subcategory — finer grouping within category
      6. Units       — units string from FRED_MACRO_US
      7. Frequency   — "Weekly (daily → ffill)", "Weekly (monthly → ffill)", etc.
      8. Last Updated — UTC timestamp of this run
    """
    run_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    series_id_row  = ["Series ID"]
    source_row     = ["Source"]
    name_row       = ["Name"]
    category_row   = ["Category"]
    subcat_row     = ["Subcategory"]
    units_row      = ["Units"]
    frequency_row  = ["Frequency"]
    updated_row    = ["Last Updated"]

    for col in df.columns:
        if col == "Date":
            continue
        native_freq = FRED_MACRO_US_FREQ.get(col, "")
        hist_freq   = _FREQ_TO_HIST_LABEL.get(native_freq, native_freq)

        series_id_row.append(col)
        source_row.append("FRED")
        name_row.append(FRED_MACRO_US_NAMES.get(col, col))
        category_row.append(FRED_MACRO_US_CATS.get(col, ""))
        subcat_row.append(FRED_MACRO_US_SUBCATS.get(col, ""))
        units_row.append(FRED_MACRO_US_UNITS.get(col, ""))
        frequency_row.append(hist_freq)
        updated_row.append(run_ts)

    return [
        series_id_row, source_row,
        name_row, category_row, subcat_row,
        units_row, frequency_row, updated_row,
    ]


def save_csv(df: pd.DataFrame, path: str, label: str,
             prefix_rows: list = None) -> None:
    """
    Save DataFrame to CSV.
    If prefix_rows is provided, those rows are written before the header+data
    so metadata (Name, Region, etc.) appears at the top of the file.
    Read back with pd.read_csv(path, header=len(prefix_rows)) to skip them.
    """
    if df.empty:
        print(f"  [{label}] Empty — skipping CSV write")
        return

    os.makedirs("data", exist_ok=True)

    if prefix_rows:
        import csv, io
        buf = io.StringIO()
        csv.writer(buf, lineterminator="\n").writerows(prefix_rows)
        with open(path, "w", encoding="utf-8") as f:
            f.write(buf.getvalue())
            df.to_csv(f, index=False)
    else:
        df.to_csv(path, index=False)

    n_meta = len(prefix_rows) if prefix_rows else 0
    print(f"  [{label}] Written {n_meta} metadata rows + {len(df):,} data rows "
          f"× {len(df.columns)} cols to {path}")


# ---------------------------------------------------------------------------
# PUSH TO GOOGLE SHEETS
# ---------------------------------------------------------------------------

def push_df_to_sheets(df: pd.DataFrame, tab_name: str, label: str,
                      prefix_rows: list = None) -> None:
    """
    Push a DataFrame to a named Google Sheets tab.
    Creates tab if it doesn't exist; overwrites existing content.
    Converts NaN to empty string for clean display.
    Never touches market_data or sentiment_data tabs.

    If prefix_rows is provided, those rows are prepended before the header+data
    so metadata (Name, Region, etc.) appears at the top of the sheet.
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

        # Prepare values: keep numeric types as float, dates/strings as str, NaN as ""
        def _sv(v):
            if v is None:
                return ""
            try:
                if pd.isna(v):
                    return ""
            except (TypeError, ValueError):
                pass
            if isinstance(v, (int, float, np.integer, np.floating)):
                return float(v)
            return str(v)

        header = list(df.columns)
        data_rows = [[_sv(v) for v in row] for row in df.itertuples(index=False)]

        values = (prefix_rows if prefix_rows else []) + [header] + data_rows

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
                valueInputOption="USER_ENTERED",
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
        market_meta = build_market_meta_prefix(market_df)
        save_csv(market_df, MARKET_HIST_CSV, "market_data_hist",
                 prefix_rows=market_meta)
        push_df_to_sheets(market_df, MARKET_HIST_TAB, "market_data_hist",
                          prefix_rows=market_meta)

        # --- macro_us_hist ------------------------------------------------
        macro_df = build_macro_hist_df(macro_spine)
        macro_meta = build_macro_meta_prefix(macro_df)
        save_csv(macro_df, MACRO_HIST_CSV, "macro_us_hist",
                 prefix_rows=macro_meta)
        push_df_to_sheets(macro_df, MACRO_HIST_TAB, "macro_us_hist",
                          prefix_rows=macro_meta)

        elapsed = round(time.time() - start_ts, 1)
        print(f"\nHistorical build completed in {elapsed}s")

    except Exception as e:
        elapsed = round(time.time() - start_ts, 1)
        print(f"\n[Hist] Unexpected error after {elapsed}s: {e}")
        print("[Hist] Existing pipeline outputs are unaffected")


# ---------------------------------------------------------------------------
# COMP HIST CONSTANTS
# ---------------------------------------------------------------------------

COMP_HIST_TAB   = "market_data_comp_hist"
COMP_HIST_CSV   = "data/market_data_comp_hist.csv"
COMP_HIST_START = "1950-01-01"

LIBRARY_PATH_HIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index_library.csv")

# ---------------------------------------------------------------------------
# COMP HIST: SORT-ORDER MAPS
# Instruments in the sheet are ordered:
#   1. Equities (region → subclass → sector/style)
#   2. Fixed Income / Bond Returns (region → subclass → maturity)
#   3. Rates / Bond Yields & Credit Spreads  (FRED; subclass → region)
#   4. FX / Currencies
#   5. Commodities & Crypto
#   6. Macro-Market Indicators (Volatility indices)
# ---------------------------------------------------------------------------

_ASSET_CLASS_GROUP = {
    "Equity":       1,
    "Fixed Income": 2,
    "Rates":        3,   # FRED only — handled in load_comp_fred_rates()
    "FX":           4,
    "Commodity":    5,
    "Crypto":       6,
    "Volatility":   7,
}

_REGION_ORDER = {
    "Global":               1,
    "Global ex-US/Canada":  1,   # grouped with Global
    "North America":        2,
    # UK (country_market == "United Kingdom") assigned rank 3 in sort key below
    "Europe":               4,   # non-UK Europe
    # Japan (country_market == "Japan") assigned rank 5 in sort key below
    "Emerging Markets":     6,
    "Asia Pacific":         7,   # non-Japan APAC
    "Middle East & Africa": 8,
    "Latin America":        9,
}

_EQUITY_SUBCLASS_ORDER = {
    "Equity Broad":              1,
    "Equity Large Cap":          2,
    "Equity Mid Cap":            3,
    "Equity Mid Cap (Growth)":   3,
    "Equity Mid Cap (Value)":    3,
    "Equity Small Cap":          4,
    "Equity Small Cap (Growth)": 4,
    "Equity Small Cap (Value)":  4,
    "Equity Sector":             5,
    "Equity Industry Group":     6,
    "Equity Factor":             7,
}

# Equity sector order (GICS standard) + style factors at end
_SECTOR_ORDER = {
    "Blend":                          0,
    "Value":                          1,
    "Growth":                         2,
    "Energy":                        10,
    "Materials":                     11,
    "Industrials":                   12,
    "Consumer Discretionary":        13,
    "Consumer Staples":              14,
    "Health Care":                   15,
    "Financials":                    16,
    "Information Technology":        17,
    "Communication Services":        18,
    "Utilities":                     19,
    "Real Estate":                   20,
    # Factor styles
    "Mega-Cap Tech / Growth":        30,
    "Equal Weight":                  31,
    "Momentum":                      32,
    "Dividend Growth":               33,
    "Quality":                       34,
    "Dividend/Quality":              35,
    "Low Volatility":                36,
    "Dividend/Income":               37,
    "Broad Market":                  38,
}

_FI_SUBCLASS_ORDER = {
    "Global Aggregate":    1,
    "Govt Bond":           2,
    "Government":          2,
    "Government Short":    2,
    "Inflation-Linked":    3,
    "Corp IG":             4,
    "Corp HY":             5,
}

_MATURITY_ORDER = {
    "Broad":          1,
    "Short (1-3yr)":  2,
    "Long (10yr+)":   3,
}

_COMMODITY_GROUP_ORDER = {
    "Energy":            1,
    "Precious Metals":   2,
    "Industrial Metals": 3,
    "Agriculture":       4,
    "Livestock":         5,
    "Broad":             6,
}

_VOL_SUBCLASS_ORDER = {
    "Equity Volatility":          1,
    "Tail Risk":                  2,
    "Fixed Income Volatility":    3,
    "Commodity Volatility":       4,
}

_RATES_SUBCLASS_ORDER = {
    "Government Yield":       1,
    "Breakeven Inflation":    2,
    "Credit Spread":          3,
    "Policy Rate":            4,
    "Yield Curve":            5,
}


def _comp_inst_sort_key(row: pd.Series) -> tuple:
    """Return a sort tuple for a library CSV row (instrument)."""
    ac       = str(row.get("asset_class", ""))
    asc      = str(row.get("asset_subclass", ""))
    region   = str(row.get("region", ""))
    country  = str(row.get("country_market", ""))
    sector   = str(row.get("sector_style", ""))
    maturity = str(row.get("maturity_focus", ""))
    cg       = str(row.get("commodity_group", ""))
    name     = str(row.get("name", ""))

    g = _ASSET_CLASS_GROUP.get(ac, 99)
    r = _REGION_ORDER.get(region, 50)
    # UK sits between NA (2) and EU (4)
    if region == "Europe" and country == "United Kingdom":
        r = 3
    # Japan sits between EU (4) and EM (6)
    if region == "Asia Pacific" and country == "Japan":
        r = 5

    if ac == "Equity":
        s   = _EQUITY_SUBCLASS_ORDER.get(asc, 50)
        sec = _SECTOR_ORDER.get(sector, 50)
        return (g, r, s, sec, name)

    if ac == "Fixed Income":
        s   = _FI_SUBCLASS_ORDER.get(asc, 50)
        mat = _MATURITY_ORDER.get(maturity, 50)
        return (g, r, s, mat, name)

    if ac == "FX":
        s = 1 if "Index" in asc else 2
        return (g, 0, s, name)

    if ac == "Commodity":
        s  = 1 if asc == "Commodity" else 2
        cg_n = _COMMODITY_GROUP_ORDER.get(cg, 50)
        return (g, 0, s, cg_n, name)

    if ac == "Crypto":
        return (g, 0, 0, name)

    if ac == "Volatility":
        s = _VOL_SUBCLASS_ORDER.get(asc, 50)
        return (g, 0, s, name)

    return (g, r, 0, name)

# FX pairs covering all currencies in the comprehensive library
COMP_FX_TICKERS_HIST = {
    "GBP": "GBPUSD=X",
    "EUR": "EURUSD=X",
    "AUD": "AUDUSD=X",
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

# Indirect-quote currencies (1 USD = X FCY): divide to get USD
COMP_FCY_PER_USD_HIST = {
    "JPY", "CNY", "INR", "KRW", "TWD",
    "CAD", "BRL", "HKD", "MXN", "IDR",
    "RUB", "SAR", "ZAR", "TRY", "ARS",
}


# ---------------------------------------------------------------------------
# COMP HIST: LOAD INSTRUMENTS FROM LIBRARY
# ---------------------------------------------------------------------------

def load_comp_instruments() -> list:
    """
    Read index_library.csv and return a list of instrument dicts, sorted by:
      Group 1: Equities   — region → subclass → sector/style → name
      Group 2: Fixed Income — region → subclass → maturity → name
      Group 3: FX          — subclass → name
      Group 4: Commodities — subclass → commodity_group → name
      Group 5: Crypto      — name
      Group 6: Volatility (Macro-Market Indicators) — subclass → name

    For instruments with both PR and TR tickers, the PR row comes first,
    followed immediately by the TR row. Deduplicates by ticker so shared
    proxy ETFs (e.g. BNDX appearing for many hedged bond indices) appear
    only once (first occurrence wins).

    Each dict: {ticker, name, region, asset_class, asset_subclass,
                currency, ticker_type, pence}
    """
    df = pd.read_csv(LIBRARY_PATH_HIST)
    df = df[
        (df["data_source"] == "yfinance") &
        (df["validation_status"] == "CONFIRMED")
    ].copy()

    # Sort rows by desired display order
    df["_sort_key"] = df.apply(_comp_inst_sort_key, axis=1)
    df = df.sort_values("_sort_key").drop(columns=["_sort_key"])

    instruments = []
    seen = set()

    for _, row in df.iterrows():
        name        = str(row.get("name", "")).strip()
        region      = str(row.get("region", "")).strip()
        asset_class = str(row.get("asset_class", "")).strip()
        asset_sub   = str(row.get("asset_subclass", "")).strip()
        currency    = str(row.get("base_currency", "USD")).strip()
        country     = str(row.get("country_market", "")).strip()
        if not currency or currency == "nan":
            currency = "USD"

        # Give UK and Japan instruments a specific region label for Equity/Fixed Income
        if asset_class in ("Equity", "Fixed Income"):
            if country == "United Kingdom":
                region = "UK"
            elif country == "Japan":
                region = "Japan"

        pr = str(row.get("ticker_yfinance_pr", "")).strip()
        if pr and pr != "nan" and pr not in seen:
            instruments.append({
                "ticker": pr, "name": name, "region": region,
                "asset_class": asset_class, "asset_subclass": asset_sub,
                "currency": currency,
                "ticker_type": "PR", "pence": pr.endswith(".L"),
            })
            seen.add(pr)

        tr = str(row.get("ticker_yfinance_tr", "")).strip()
        if tr and tr != "nan" and tr not in seen:
            instruments.append({
                "ticker": tr, "name": name, "region": region,
                "asset_class": asset_class, "asset_subclass": asset_sub,
                "currency": currency,
                "ticker_type": "TR", "pence": tr.endswith(".L"),
            })
            seen.add(tr)

    return instruments


def load_comp_fred_rates() -> list:
    """
    Read index_library.csv and return FRED Rates series sorted by:
      Government Yields → Credit Spreads → Breakeven Inflation →
      Yield Curve → Policy Rate
    Each dict: {series_id, name, region, asset_class, asset_subclass}
    """
    df = pd.read_csv(LIBRARY_PATH_HIST)
    rates_rows = df[
        (df["data_source"] == "FRED") &
        (df["validation_status"] == "CONFIRMED") &
        (df["asset_class"] == "Rates")
    ].copy()

    rates_rows["_s"] = rates_rows["asset_subclass"].map(_RATES_SUBCLASS_ORDER).fillna(99)
    rates_rows["_r"] = rates_rows["region"].map(_REGION_ORDER).fillna(50)
    rates_rows = rates_rows.sort_values(["_s", "_r", "name"]).drop(columns=["_s", "_r"])

    fred_rates = []
    seen = set()

    for _, row in rates_rows.iterrows():
        series_id = str(row.get("ticker_fred_tr", "")).strip()
        if not series_id or series_id == "nan" or series_id in seen:
            continue
        fred_rates.append({
            "series_id":      series_id,
            "name":           str(row.get("name", series_id)).strip(),
            "region":         str(row.get("region", "")).strip(),
            "asset_class":    str(row.get("asset_class", "Rates")).strip(),
            "asset_subclass": str(row.get("asset_subclass", "")).strip(),
        })
        seen.add(series_id)

    return fred_rates


# ---------------------------------------------------------------------------
# COMP HIST: FX CACHE
# ---------------------------------------------------------------------------

def fetch_comp_fx_cache(start: str) -> dict:
    """
    Fetch all comprehensive FX pairs as daily Close series.
    Bulk download first; per-ticker fallback for any failures.
    """
    print("  Fetching comprehensive FX cache...")
    all_tickers = list(COMP_FX_TICKERS_HIST.values())
    cache = {}

    try:
        raw = yf.download(
            all_tickers, start=start,
            auto_adjust=True, progress=False, threads=True,
        )
        close = raw["Close"]
        if isinstance(close, pd.Series):
            close = close.to_frame(all_tickers[0])
        for ticker in all_tickers:
            if ticker in close.columns:
                s = close[ticker].dropna()
                if not s.empty:
                    cache[ticker] = s
    except Exception as e:
        print(f"    FX bulk fetch failed ({e}) — per-ticker fallback")

    missing = [t for t in all_tickers if t not in cache]
    for ticker in missing:
        try:
            s = yf.download(ticker, start=start, auto_adjust=True, progress=False)["Close"]
            if isinstance(s, pd.DataFrame):
                s = s.iloc[:, 0]
            if not s.empty:
                cache[ticker] = s.dropna()
        except Exception as e:
            print(f"    FX {ticker} failed: {e}")
        time.sleep(YFINANCE_DELAY)

    print(f"  Comp FX cache: {len(cache)}/{len(all_tickers)} pairs loaded")
    return cache


# ---------------------------------------------------------------------------
# COMP HIST: USD CONVERSION
# ---------------------------------------------------------------------------

def compute_comp_usd_series(
    local_prices: pd.Series,
    currency: str,
    fx_cache: dict,
) -> pd.Series:
    """
    Convert local-currency price series to USD using the comprehensive FX cache.
    Same logic as compute_usd_price_series() but uses COMP_FX_TICKERS_HIST.
    """
    if not currency or currency == "USD":
        return local_prices

    fx_ticker = COMP_FX_TICKERS_HIST.get(currency)
    if not fx_ticker or fx_ticker not in fx_cache:
        return local_prices

    fx = fx_cache[fx_ticker]
    fx_aligned = fx.reindex(local_prices.index, method="ffill")

    if currency in COMP_FCY_PER_USD_HIST:
        return local_prices / fx_aligned
    else:
        return local_prices * fx_aligned


# ---------------------------------------------------------------------------
# COMP HIST: FETCH yfinance BULK HISTORY
# ---------------------------------------------------------------------------

def fetch_comp_yfinance_history(
    instruments: list,
    start: str,
    spine: pd.DatetimeIndex,
    fx_cache: dict,
) -> tuple[dict, dict]:
    """
    Fetch weekly (Friday) close prices for all comp instruments.
    Bulk download in chunks of 100; per-ticker fallback for failures.
    Returns (local_prices, usd_prices) dicts keyed by ticker.
    """
    tickers     = [inst["ticker"] for inst in instruments]
    ticker_meta = {inst["ticker"]: inst for inst in instruments}
    close_df    = pd.DataFrame()

    CHUNK = 100
    chunks = [tickers[i:i + CHUNK] for i in range(0, len(tickers), CHUNK)]
    print(f"  Bulk downloading {len(tickers)} instruments in {len(chunks)} chunks...")

    for ci, chunk in enumerate(chunks, 1):
        print(f"  Chunk {ci}/{len(chunks)} ({len(chunk)} tickers)...")
        try:
            raw = yf.download(
                chunk, start=start,
                auto_adjust=True, progress=False, threads=True,
            )
            close_raw = raw["Close"]
            if isinstance(close_raw, pd.Series):
                close_raw = close_raw.to_frame(chunk[0])
            for ticker in chunk:
                if ticker in close_raw.columns:
                    s = close_raw[ticker].dropna()
                    if not s.empty:
                        close_df[ticker] = s
        except Exception as e:
            print(f"    Chunk {ci} failed ({e})")
        time.sleep(YFINANCE_DELAY)

    failed = [t for t in tickers if t not in close_df.columns]
    if failed:
        print(f"  Per-ticker fallback for {len(failed)} instruments...")
        for i, ticker in enumerate(failed, 1):
            try:
                s = yf.download(
                    ticker, start=start,
                    auto_adjust=True, progress=False,
                )["Close"]
                if isinstance(s, pd.DataFrame):
                    s = s.iloc[:, 0]
                if not s.empty:
                    close_df[ticker] = s
                    print(f"    [{i}] {ticker}: OK ({len(s)} rows)")
                else:
                    print(f"    [{i}] {ticker}: empty")
            except Exception as e:
                print(f"    [{i}] {ticker}: failed ({e})")
            time.sleep(YFINANCE_DELAY)

    print("  Processing prices and computing USD series...")
    local_prices = {}
    usd_prices   = {}

    for ticker in tickers:
        inst     = ticker_meta[ticker]
        currency = inst["currency"] or "USD"

        if ticker not in close_df.columns:
            local_prices[ticker] = pd.Series(np.nan, index=spine, name=ticker)
            usd_prices[ticker]   = pd.Series(np.nan, index=spine, name=ticker)
            continue

        s = close_df[ticker].dropna()

        # Pence correction for LSE-listed instruments
        if ticker.endswith(".L"):
            median_val = s.dropna().median()
            if pd.notna(median_val) and median_val > 50:
                s = s / 100

        s.index = pd.to_datetime(s.index)
        weekly        = s.resample("W-FRI").last()
        local_aligned = weekly.reindex(spine).ffill(limit=5)

        local_prices[ticker] = local_aligned
        usd_prices[ticker]   = compute_comp_usd_series(local_aligned, currency, fx_cache)

    return local_prices, usd_prices


# ---------------------------------------------------------------------------
# COMP HIST: FETCH FRED RATES HISTORY
# ---------------------------------------------------------------------------

def fetch_comp_fred_rates_history(
    fred_rates: list,
    spine: pd.DatetimeIndex,
) -> tuple[dict, dict]:
    """
    Fetch all FRED Rates series and align to Friday spine.
    Rate series: USD = Local (no FX conversion needed).
    """
    if not FRED_API_KEY:
        print("  [FRED rates] FRED_API_KEY not set — skipping")
        return {}, {}

    local_prices = {}
    usd_prices   = {}
    total = len(fred_rates)

    print(f"  Fetching {total} FRED Rates series...")
    for i, fr in enumerate(fred_rates, 1):
        sid = fr["series_id"]
        print(f"    [{i}/{total}] {sid} ({fr['name']})...")
        data = fred_fetch_series_full(sid, COMP_HIST_START)
        if data is None or data.empty:
            local_prices[sid] = pd.Series(np.nan, index=spine)
            usd_prices[sid]   = pd.Series(np.nan, index=spine)
        else:
            aligned          = align_to_friday_spine(data, spine)
            local_prices[sid] = aligned
            usd_prices[sid]   = aligned   # rates: no FX conversion
        if i < total:
            time.sleep(FRED_DELAY)

    return local_prices, usd_prices


# ---------------------------------------------------------------------------
# COMP HIST: BUILD DATAFRAME
# ---------------------------------------------------------------------------

def build_comp_market_hist_df(
    spine: pd.DatetimeIndex,
    instruments: list,
    fred_rates: list,
    local_yf: dict,
    usd_yf: dict,
    local_fr: dict,
    usd_fr: dict,
) -> pd.DataFrame:
    """
    Assemble the market_data_comp_hist DataFrame.
    Schema: Date | <ticker>_Local × N | <ticker>_USD × N
    """
    yf_tickers  = [inst["ticker"] for inst in instruments]
    fred_ids    = [fr["series_id"] for fr in fred_rates]
    inst_meta   = {inst["ticker"]: inst for inst in instruments}

    # Split yfinance tickers at the FX group boundary so that FRED Rates
    # (bond yields & credit spreads) appear right after yfinance yield
    # tickers — preserving the user-visible group order:
    #   Equities → Fixed Income → Bond Yields & Spreads → FX → Commodities
    #   → Crypto → Macro-Market Indicators
    _pre_fx_classes  = {"Equity", "Fixed Income", "Rates"}
    yf_pre_fx    = [t for t in yf_tickers if inst_meta[t]["asset_class"] in _pre_fx_classes]
    yf_post_rates = [t for t in yf_tickers if inst_meta[t]["asset_class"] not in _pre_fx_classes]
    all_ordered  = yf_pre_fx + fred_ids + yf_post_rates

    df = pd.DataFrame(index=spine)
    df.index.name = "Date"

    for ticker in all_ordered:
        if ticker in local_yf:
            s = local_yf[ticker]
        elif ticker in local_fr:
            s = local_fr[ticker]
        else:
            s = pd.Series(np.nan, index=spine)
        df[f"{ticker}_Local"] = s

    for ticker in all_ordered:
        if ticker in usd_yf:
            s = usd_yf[ticker]
        elif ticker in usd_fr:
            s = usd_fr[ticker]
        else:
            s = pd.Series(np.nan, index=spine)
        df[f"{ticker}_USD"] = s

    df = df.reset_index()
    df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")

    print(f"  market_data_comp_hist: {len(df)} rows × {len(df.columns)} columns")
    return df


# ---------------------------------------------------------------------------
# COMP HIST: METADATA PREFIX
# ---------------------------------------------------------------------------

def build_comp_market_meta_prefix(
    df: pd.DataFrame,
    instruments: list,
    fred_rates: list,
) -> list:
    """
    Build 10-row metadata prefix for market_data_comp_hist.
    Row order: Ticker ID, Variant, Source, Name, Region,
               Asset Class, Currency, Units, Frequency, Last Updated
    """
    run_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    yf_meta = {inst["ticker"]: inst for inst in instruments}
    fr_meta = {fr["series_id"]: fr for fr in fred_rates}

    # Display label for Asset Class row — Volatility renamed to align with
    # user-facing group label "Macro-Market Indicators"
    _ac_display = {
        "Volatility": "Macro-Market Indicators",
    }

    # Units by asset class (library values)
    _ac_units = {
        "Equity":          "Index / Price",
        "Fixed Income":    "Price",
        "FX":              "Rate",
        "Commodity":       "Price",
        "Crypto":          "Price",
        "Volatility":      "Index",
        "Rates":           "% pa",
    }

    # More granular units by asset_subclass override
    _asc_units = {
        "Equity Broad":              "Index",
        "Equity Large Cap":          "Index",
        "Equity Mid Cap":            "Index",
        "Equity Mid Cap (Growth)":   "Index",
        "Equity Mid Cap (Value)":    "Index",
        "Equity Small Cap":          "Index",
        "Equity Small Cap (Growth)": "Index",
        "Equity Small Cap (Value)":  "Index",
        "Equity Sector":             "Index",
        "Equity Industry Group":     "Index",
        "Equity Factor":             "Price",
        "Govt Bond":                 "Index",
        "Government":                "Price",
        "Government Short":          "Price",
        "Global Aggregate":          "Price",
        "Corp IG":                   "Index / Price",
        "Corp HY":                   "Index / Price",
        "Inflation-Linked":          "Index / Price",
        "Currency Index":            "Index",
        "FX Spot Rate":              "Rate",
        "Commodity":                 "Price",
        "Commodity Sub-Index":       "Price",
        "Bitcoin":                   "Price",
        "Ethereum":                  "Price",
        "Equity Volatility":         "Index",
        "Fixed Income Volatility":   "Index",
        "Commodity Volatility":      "Index",
        "Tail Risk":                 "Index",
        "Government Yield":          "% pa",
        "Credit Spread":             "bps",
        "Breakeven Inflation":       "% pa",
        "Yield Curve":               "bps",
        "Policy Rate":               "% pa",
    }

    # Broad Asset Class derivation from raw asset_class + asset_subclass
    def _broad_ac(asset_cls: str, asset_sub: str) -> str:
        if asset_cls == "Equity":
            return "Equity"
        if asset_cls == "Fixed Income":
            return "Bonds"
        if asset_cls == "FX":
            return "FX"
        if asset_cls == "Commodity":
            return "Commodities"
        if asset_cls == "Crypto":
            return "Crypto"
        if asset_cls == "Volatility":
            return "Macro-Market Indicators"
        if asset_cls == "Rates":
            return "Spreads" if asset_sub == "Credit Spread" else "Bonds"
        return asset_cls

    ticker_id_row        = ["Ticker ID"]
    variant_row          = ["Variant"]
    source_row           = ["Source"]
    name_row             = ["Name"]
    region_row           = ["Region"]
    broad_asset_cls_row  = ["Broad Asset Class"]
    asset_class_row      = ["Sub-Category"]
    currency_row         = ["Currency"]
    units_row            = ["Units"]
    frequency_row        = ["Frequency"]
    updated_row          = ["Last Updated"]

    for col in df.columns:
        if col == "Date":
            continue

        if col.endswith("_Local"):
            base, variant, is_usd = col[:-6], "Local", False
        elif col.endswith("_USD"):
            base, variant, is_usd = col[:-4], "USD", True
        else:
            base, variant, is_usd = col, "", False

        if base in yf_meta:
            inst      = yf_meta[base]
            source    = f"yfinance {inst['ticker_type']}"
            name      = inst["name"]
            region    = inst["region"]
            asset_cls = inst["asset_class"]
            asset_sub = inst.get("asset_subclass", "")
            local_ccy = inst["currency"] or "USD"
        elif base in fr_meta:
            fr_row    = fr_meta[base]
            source    = "FRED"
            name      = fr_row["name"]
            region    = fr_row["region"]
            asset_cls = fr_row["asset_class"]
            asset_sub = fr_row.get("asset_subclass", "")
            local_ccy = "USD"
        else:
            source = name = region = asset_cls = asset_sub = ""
            local_ccy = "USD"

        display_ac = _ac_display.get(asset_cls, asset_cls)
        broad_ac   = _broad_ac(asset_cls, asset_sub)
        units      = _asc_units.get(asset_sub) or _ac_units.get(asset_cls, "")

        ticker_id_row.append(base)
        variant_row.append(variant)
        source_row.append(source)
        name_row.append(name)
        region_row.append(region)
        broad_asset_cls_row.append(broad_ac)
        asset_class_row.append(display_ac)
        currency_row.append("USD" if is_usd else local_ccy)
        units_row.append(units)
        frequency_row.append("Weekly")
        updated_row.append(run_ts)

    return [
        ticker_id_row, variant_row, source_row,
        name_row, broad_asset_cls_row, region_row, asset_class_row, currency_row,
        units_row, frequency_row, updated_row,
    ]


# ---------------------------------------------------------------------------
# COMP HIST: MAIN ENTRY POINT
# ---------------------------------------------------------------------------

def run_comp_hist() -> None:
    """
    Full historical fetch for market_data_comp_hist.
    Produces the market_data_comp_hist Google Sheet tab and CSV.
    Safe to call from fetch_data.py; all errors caught internally.
    """
    print("\n" + "=" * 60)
    print("Comprehensive Historical Time Series Build")
    print("=" * 60)

    start_ts = time.time()

    try:
        # 1. Friday spine from 1950
        comp_spine = get_friday_spine(COMP_HIST_START)
        print(f"Comp spine: {len(comp_spine):,} Fridays "
              f"({comp_spine[0].date()} → {comp_spine[-1].date()})")

        # 2. Load instruments and FRED rates from library
        instruments = load_comp_instruments()
        fred_rates  = load_comp_fred_rates()
        print(f"Loaded {len(instruments)} yfinance instruments, "
              f"{len(fred_rates)} FRED Rates series")

        # 3. FX cache
        comp_fx_cache = fetch_comp_fx_cache(COMP_HIST_START)

        # 4. yfinance history
        local_yf, usd_yf = fetch_comp_yfinance_history(
            instruments, COMP_HIST_START, comp_spine, comp_fx_cache
        )

        # 5. FRED rates history
        local_fr, usd_fr = fetch_comp_fred_rates_history(fred_rates, comp_spine)

        # 6. Build DataFrame
        print("\nAssembling market_data_comp_hist DataFrame...")
        comp_df = build_comp_market_hist_df(
            comp_spine, instruments, fred_rates,
            local_yf, usd_yf, local_fr, usd_fr,
        )

        # 7. Metadata prefix
        comp_meta = build_comp_market_meta_prefix(comp_df, instruments, fred_rates)

        # 8. Save CSV
        save_csv(comp_df, COMP_HIST_CSV, "market_data_comp_hist",
                 prefix_rows=comp_meta)

        # 9. Push to Google Sheets
        push_df_to_sheets(comp_df, COMP_HIST_TAB, "market_data_comp_hist",
                          prefix_rows=comp_meta)

        elapsed = round(time.time() - start_ts, 1)
        print(f"\nComp historical build completed in {elapsed}s")

    except Exception as e:
        elapsed = round(time.time() - start_ts, 1)
        print(f"\n[CompHist] Unexpected error after {elapsed}s: {e}")
        print("[CompHist] Existing pipeline outputs are unaffected")


if __name__ == "__main__":
    run_hist()
