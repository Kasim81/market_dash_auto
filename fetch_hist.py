"""
fetch_hist.py
=============
Historical Time Series Module
Market Dashboard Expansion

WHAT THIS MODULE DOES
---------------------
Produces Google Sheet tabs and CSVs for historical time series:

1. macro_us_hist
   - Weekly time series for all 25 FRED macro indicators
   - Dates as rows, indicators as columns (long format)
   - Monthly/quarterly series are forward-filled into weekly slots
   - Goes back as far as FRED data allows per series (some to 1947)
   - Date spine anchored to Fridays; macro data aligned to nearest prior Friday

2. market_data_comp_hist
   - Weekly (Friday close) prices for all instruments from index_library.csv
   - Built by run_comp_hist()

DESIGN PRINCIPLES
-----------------
- If this module fails for any reason, existing pipeline is unaffected.
- The module is called from fetch_data.py via a single try/except block.

RATE LIMITING
-------------
yfinance:  0.3s delay between instrument fetches (matches existing fetch_data.py)
FRED:      0.6s delay between series + exponential backoff on 429/5xx
           (matches fetch_macro_us_fred.py)
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

from library_utils import (
    COMP_FX_TICKERS,
    COMP_FCY_PER_USD,
    lib_sort_key as _comp_inst_sort_key,
)

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

FRED_API_KEY            = os.environ.get("FRED_API_KEY", "")
GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS", "")
SHEET_ID                = "12nKIUGHz5euDbNQPDTVECsJBNwrceRF1ymsQrIe4_ac"

MACRO_HIST_TAB          = "macro_us_hist"
MACRO_HIST_CSV          = "data/macro_us_hist.csv"

# Historical start floors
MACRO_HIST_START        = "1947-01-01"   # FRED data; some series go back this far

# Rate limit delays
YFINANCE_DELAY          = 0.3            # seconds between yfinance per-ticker calls
FRED_DELAY              = 0.6            # seconds between FRED calls
FRED_BACKOFF_BASE       = 2             # seconds; doubles on each retry
FRED_MAX_RETRIES        = 5

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
    Produces macro_us_hist.
    Safe to call from fetch_data.py; all errors caught internally.
    """
    print("\n" + "="*60)
    print("Historical Time Series Build")
    print("="*60)

    start_ts = time.time()

    try:
        # --- Build Friday spine -------------------------------------------
        macro_spine  = get_friday_spine(MACRO_HIST_START)

        print(f"Macro spine:   {len(macro_spine):,} Fridays "
              f"({macro_spine[0].date()} → {macro_spine[-1].date()})")

        # --- macro_us_hist ------------------------------------------------
        macro_df = build_macro_hist_df(macro_spine)
        macro_meta = build_macro_meta_prefix(macro_df)
        macro_df.insert(0, "row_id", range(1, len(macro_df) + 1))
        macro_meta = [[""] + row for row in macro_meta]
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

LIBRARY_PATH_HIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "index_library.csv")

# ---------------------------------------------------------------------------
# COMP HIST: SORT ORDER + FX MAPS
# All sort dicts and the sort key function are imported from library_utils.
# COMP_FX_TICKERS and COMP_FCY_PER_USD are also imported from library_utils.
# ---------------------------------------------------------------------------

# Aliases used by load_comp_fred_rates() sort logic
COMP_FX_TICKERS_HIST   = COMP_FX_TICKERS      # single authoritative map
COMP_FCY_PER_USD_HIST  = COMP_FCY_PER_USD      # single authoritative set


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
        df["data_source"].isin(["yfinance PR", "yfinance TR"]) &
        (df["validation_status"] == "CONFIRMED")
    ].copy()

    # Sort rows by desired display order
    df["_sort_key"] = df.apply(_comp_inst_sort_key, axis=1)
    df = df.sort_values("_sort_key").drop(columns=["_sort_key"])

    instruments = []
    seen = set()

    def _clean(val):
        s = str(val).strip()
        return None if s in ("nan", "", "N/A") else s

    for _, row in df.iterrows():
        name        = str(row.get("name", "")).strip()
        region      = str(row.get("region", "")).strip()
        asset_class = str(row.get("asset_class", "")).strip()
        asset_sub   = str(row.get("asset_subclass", "")).strip()
        currency    = str(row.get("base_currency", "USD")).strip()
        src         = str(row.get("data_source", "")).strip()
        if not currency or currency in ("nan", "N/A"):
            currency = "USD"
        # USX = US cents → treat as USD after ÷100 correction
        is_usx = (currency == "USX")
        if is_usx:
            currency = "USD"

        def _entry(ticker, ticker_type):
            return {
                "ticker": ticker, "name": name, "region": region,
                "asset_class": asset_class, "asset_subclass": asset_sub,
                "currency": currency, "ticker_type": ticker_type,
                "pence": ticker.endswith(".L"), "usx": is_usx,
            }

        pr = _clean(row.get("ticker_yfinance_pr"))
        tr = _clean(row.get("ticker_yfinance_tr"))

        if src == "yfinance PR":
            if pr and pr not in seen:
                instruments.append(_entry(pr, "PR"))
                seen.add(pr)
            if tr and tr not in seen:
                instruments.append(_entry(tr, "TR"))
                seen.add(tr)
        elif src == "yfinance TR":
            if tr and tr not in seen:
                instruments.append(_entry(tr, "TR"))
                seen.add(tr)

    return instruments


def load_comp_fred_rates() -> list:
    """
    Read index_library.csv and return all confirmed FRED series.
    Ticker column priority: ticker_fred_oas > ticker_fred_tr > ticker_fred_yield.
    Each dict: {series_id, name, region, asset_class, asset_subclass, is_yield}
      is_yield=True  → bps change (OAS or yield series)
      is_yield=False → % return (total return index)
    """
    df = pd.read_csv(LIBRARY_PATH_HIST)
    fred_rows = df[
        (df["data_source"] == "FRED") &
        (df["validation_status"] == "CONFIRMED")
    ].copy()

    fred_rows["_s"] = fred_rows.apply(_comp_inst_sort_key, axis=1)
    fred_rows = fred_rows.sort_values("_s").drop(columns=["_s"])

    fred_rates = []
    seen = set()

    def _val(v):
        s = str(v).strip()
        return None if s in ("nan", "N/A", "") else s

    for _, row in fred_rows.iterrows():
        oas_id   = _val(row.get("ticker_fred_oas"))
        tr_id    = _val(row.get("ticker_fred_tr"))
        yield_id = _val(row.get("ticker_fred_yield"))

        if oas_id:
            series_id = oas_id
            is_yield  = True
        elif tr_id:
            series_id = tr_id
            is_yield  = False
        elif yield_id:
            series_id = yield_id
            is_yield  = True
        else:
            continue

        if series_id in seen:
            continue
        fred_rates.append({
            "series_id":      series_id,
            "name":           str(row.get("name", series_id)).strip(),
            "region":         str(row.get("region", "")).strip(),
            "asset_class":    str(row.get("asset_class", "")).strip(),
            "asset_subclass": str(row.get("asset_subclass", "")).strip(),
            "is_yield":       is_yield,
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
    Convert local-currency prices to USD using COMP_FX_TICKERS_HIST.
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
        # USX correction: agricultural futures quoted in US cents → convert to USD
        elif inst.get("usx", False):
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
        comp_df.insert(0, "row_id", range(1, len(comp_df) + 1))
        comp_meta = [[""] + row for row in comp_meta]

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
