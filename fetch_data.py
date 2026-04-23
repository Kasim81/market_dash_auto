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

from library_utils import (
    ASSET_CLASS_GROUP as _LIB_ASSET_CLASS_GROUP,
    REGION_ORDER as _LIB_REGION_ORDER,
    COMP_FX_TICKERS,
    COMP_FCY_PER_USD,
    SHEETS_LEGACY_TABS_TO_DELETE,
    lib_sort_key as _lib_sort_key,
)

# ─────────────────────────────────────────────
# FRED API KEY — set as GitHub Secret FRED_API_KEY
# ─────────────────────────────────────────────
FRED_API_KEY = os.environ.get("FRED_API_KEY", "")
FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"

# ─────────────────────────────────────────────
# COMPREHENSIVE LIBRARY — constants
# ─────────────────────────────────────────────

LIBRARY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "index_library.csv")

# Level-change tickers (absolute point change, not % change) — read from CSV
# so the list can be maintained without touching this file.
_LEVEL_CHANGE_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "level_change_tickers.csv")
try:
    COMP_LEVEL_CHANGE_TICKERS = set(pd.read_csv(_LEVEL_CHANGE_CSV)["ticker"].dropna().str.strip())
except Exception:
    COMP_LEVEL_CHANGE_TICKERS = {"^VIX", "^VIX9D", "^VIX3M", "^VVIX", "^SKEW",
                                  "^VXEFA", "^VXEEM", "^GVZ", "^OVX"}
    print("WARNING: could not load level_change_tickers.csv — using built-in fallback")


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

    as_of = series.index[-1]
    last_val = series.iloc[-1]

    if period_key == "Perf YTD":
        target_date = pd.Timestamp(as_of.year, 1, 1, tz="UTC")
    else:
        days = PERIODS[period_key]
        target_date = as_of - timedelta(days=days)

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
    """Fetch full price history from yfinance with retry logic.

    Tries period='max' first.  Some tickers (e.g. certain Chinese indices,
    Russian markets, newer CBOE indices) only allow short look-back windows
    via the period parameter, so if period='max' returns empty we fall back
    to start='2000-01-01'.
    """
    def _process(hist):
        if hist is None or hist.empty or "Close" not in hist.columns:
            return None
        hist = hist[~hist.index.duplicated(keep="first")]
        series = hist["Close"]
        idx = series.index
        if idx.tzinfo is None:
            idx = idx.tz_localize("UTC")
        else:
            idx = idx.tz_convert("UTC")
        idx = idx.astype("datetime64[us, UTC]")
        series.index = idx
        return series if not series.empty else None

    for attempt in range(retries):
        try:
            t = yf.Ticker(ticker)
            series = _process(t.history(period="max", auto_adjust=True))
            if series is None:
                # Fallback for tickers that restrict period= to short windows
                series = _process(t.history(start="2000-01-01", auto_adjust=True))
            if series is not None:
                cutoff = pd.Timestamp(datetime.now(timezone.utc).date()).tz_localize("UTC").as_unit("us")
                series = series[series.index < cutoff]
                return series if not series.empty else None
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


def usd_adjusted_return(local_return_pct, ccy, period_key, fx_cache, fcy_per_usd=None):
    """Convert a local currency % return to USD % return.

    fcy_per_usd: set of currencies where the FX ticker is quoted as USD/FCY
                 (i.e. 1 USD = X FCY, so we invert).  Defaults to COMP_FCY_PER_USD.
    """
    if fcy_per_usd is None:
        fcy_per_usd = COMP_FCY_PER_USD

    if ccy is None or pd.isna(local_return_pct):
        return local_return_pct

    if ccy not in fx_cache:
        return np.nan

    fx_series = fx_cache[ccy]
    fx_return = calc_return(fx_series, period_key, is_yield=False)

    if pd.isna(fx_return):
        return np.nan

    if ccy in fcy_per_usd:
        fx_usd_return = -fx_return
    else:
        fx_usd_return = fx_return

    combined = (1 + local_return_pct / 100) * (1 + fx_usd_return / 100) - 1
    return round(combined * 100, 2)




# ─────────────────────────────────────────────
# COMPREHENSIVE LIBRARY — data collection
# ─────────────────────────────────────────────

def build_comp_fx_cache():
    """Pre-fetch FX rate histories for all currencies in the comprehensive library."""
    print("Fetching comprehensive FX rates...")
    cache = {}
    for ccy, ticker in COMP_FX_TICKERS.items():
        series = fetch_yf_history(ticker)
        if series is not None:
            cache[ccy] = series
            print(f"  {ccy} ({ticker}): OK ({len(series)} rows)")
        else:
            print(f"  {ccy} ({ticker}): FAILED — USD conversion unavailable for {ccy} assets")
    return cache


def load_simple_library():
    """Read index_library.csv filtered on simple_dash == True.

    Returns instruments in the same dict format as load_instrument_library()
    but only the single ticker each simple-pipeline row actually uses:
      - yfinance PR rows → PR ticker (or TR ticker if PR absent)
      - yfinance TR rows → TR ticker only
      - FRED/UNAVAILABLE rows → handled separately via collect_simple_fred_assets()

    The simple pipeline's display order matches the library sort order.
    """
    df = pd.read_csv(LIBRARY_PATH)
    simple = df[
        (df["simple_dash"] == True) &
        (df["data_source"].isin(["yfinance PR", "yfinance TR"])) &
        (df["validation_status"] == "CONFIRMED")
    ].copy()

    simple["_sort"] = simple.apply(_lib_sort_key, axis=1)
    simple = simple.sort_values("_sort").drop(columns=["_sort"])

    instruments = []
    seen = set()

    def _clean(val):
        s = str(val).strip()
        return None if s in ("nan", "", "N/A") else s

    for _, row in simple.iterrows():
        name            = str(row["name"]).strip()
        region          = str(row["region"]).strip()
        asset_cls_raw   = str(row["asset_class"]).strip()
        broad_ac        = str(row.get("broad_asset_class", asset_cls_raw)).strip()
        asset_cls       = str(row["asset_subclass"]).strip()
        ccy             = str(row["base_currency"]).strip()
        src             = str(row["data_source"]).strip()
        if ccy in ("nan", "", "N/A"):
            ccy = "USD"
        if ccy == "USX":
            ccy = "USD"

        pr = _clean(row["ticker_yfinance_pr"])
        tr = _clean(row["ticker_yfinance_tr"])

        def _entry(ticker, ticker_type):
            return {
                "ticker":            ticker,
                "name":              name,
                "region":            region,
                "asset_class":       asset_cls,
                "asset_class_raw":   asset_cls_raw,
                "broad_asset_class": broad_ac,
                "currency":          ccy,
                "ticker_type":       ticker_type,
                "pence":             ticker.endswith(".L"),
                "usx":               str(row["base_currency"]).strip() == "USX",
            }

        if src == "yfinance PR":
            # For PR rows, use the TR ticker if available (ETF/fund),
            # otherwise use the PR ticker (index)
            if tr and tr not in seen:
                instruments.append(_entry(tr, "Total Return (ETF)"))
                seen.add(tr)
            elif pr and pr not in seen:
                instruments.append(_entry(pr, "Price Return (Index)"))
                seen.add(pr)
        elif src == "yfinance TR":
            if tr and tr not in seen:
                instruments.append(_entry(tr, "Total Return (ETF)"))
                seen.add(tr)

    print(f"  Simple library loaded: {len(instruments)} instruments "
          f"({sum(1 for i in instruments if i['ticker_type'].startswith('Price'))} PR, "
          f"{sum(1 for i in instruments if i['ticker_type'].startswith('Total'))} TR)")
    return instruments


def collect_simple_fred_assets():
    """Collect FRED-sourced instruments for market_data (simple_dash == True only).

    Uses the same pattern as collect_comp_fred_assets() but filters to
    simple_dash rows.
    """
    df = pd.read_csv(LIBRARY_PATH)
    fred_rows = df[
        (df["simple_dash"] == True) &
        (df["data_source"].isin(["FRED", "UNAVAILABLE"])) &
        (df["validation_status"] == "CONFIRMED")
    ].copy()

    if fred_rows.empty:
        return []

    fred_rows["_s"] = fred_rows.apply(_lib_sort_key, axis=1)
    fred_rows = fred_rows.sort_values("_s").drop(columns=["_s"])

    print(f"\nFetching simple FRED series ({len(fred_rows)} rows)...")
    rows = []

    def _val(v):
        s = str(v).strip()
        return None if s in ("nan", "N/A", "") else s

    for _, lib_row in fred_rows.iterrows():
        name          = str(lib_row["name"]).strip()
        region        = str(lib_row.get("region", "Global")).strip()
        if region in ("nan", "", "N/A"):
            region = "Global"
        asset_cls_raw = str(lib_row["asset_class"]).strip()
        broad_ac      = str(lib_row.get("broad_asset_class", asset_cls_raw)).strip()
        asset_sub     = str(lib_row.get("asset_subclass", "")).strip()

        oas_id   = _val(lib_row.get("ticker_fred_oas"))
        tr_id    = _val(lib_row.get("ticker_fred_tr"))
        yield_id = _val(lib_row.get("ticker_fred_yield"))

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

        print(f"  {series_id} ({name[:45]})...")
        series = fetch_fred_series(series_id)

        row = {
            "Symbol":            series_id,
            "Name":              name,
            "Ticker Type":       "FRED",
            "Region":            region,
            "Broad Asset Class": broad_ac,
            "Sub-Category":      asset_sub,
            "Currency":          "USD",
            "Last Price":        np.nan,
            "Last Date":         np.nan,
            "_sort_group":       _LIB_ASSET_CLASS_GROUP.get(asset_cls_raw, 99),
        }

        if series is not None and not series.empty:
            row["Last Price"] = round(series.iloc[-1], 4)
            row["Last Date"]  = str(series.index[-1].date())
            for pk in PERIODS:
                if is_yield:
                    row[f"Local {pk} (bps)"] = calc_return(series, pk, is_yield=True)
                else:
                    row[f"Local {pk}"] = calc_return(series, pk, is_yield=False)
                    row[f"USD {pk}"]   = row[f"Local {pk}"]
        else:
            for pk in PERIODS:
                if is_yield:
                    row[f"Local {pk} (bps)"] = np.nan
                else:
                    row[f"Local {pk}"] = np.nan
                    row[f"USD {pk}"]   = np.nan

        rows.append(row)

    return rows


def load_instrument_library():
    """Read index_library.csv and return a flat list of instrument dicts.

    data_source values handled:
      "yfinance PR" — row has a ticker_yfinance_pr; may also have ticker_yfinance_tr
                      → create a PR entry and, if present, a TR entry
      "yfinance TR" — row has only ticker_yfinance_tr (no PR ticker)
                      → create a TR entry only

    Tickers are deduplicated — if the same ticker appears more than once
    (e.g. a shared ETF proxy) only the first occurrence is kept.
    """
    df = pd.read_csv(LIBRARY_PATH)
    confirmed_yf = df[
        df["data_source"].isin(["yfinance PR", "yfinance TR"]) &
        (df["validation_status"] == "CONFIRMED")
    ].copy()

    # Sort rows into display group order before building instrument list
    confirmed_yf["_sort"] = confirmed_yf.apply(_lib_sort_key, axis=1)
    confirmed_yf = confirmed_yf.sort_values("_sort").drop(columns=["_sort"])

    instruments = []
    seen = set()

    def _clean(val):
        s = str(val).strip()
        return None if s in ("nan", "", "N/A") else s

    for _, row in confirmed_yf.iterrows():
        name            = str(row["name"]).strip()
        region          = str(row["region"]).strip()
        asset_cls_raw   = str(row["asset_class"]).strip()
        broad_ac        = str(row.get("broad_asset_class", asset_cls_raw)).strip()
        asset_cls       = str(row["asset_subclass"]).strip()
        ccy             = str(row["base_currency"]).strip()
        src             = str(row["data_source"]).strip()
        if ccy in ("nan", "", "N/A"):
            ccy = "USD"
        # USX = US cents (agricultural futures) → treat as USD after ÷100 correction
        if ccy == "USX":
            ccy = "USD"

        pr = _clean(row["ticker_yfinance_pr"])
        tr = _clean(row["ticker_yfinance_tr"])

        def _entry(ticker, ticker_type):
            return {
                "ticker":            ticker,
                "name":              name,
                "region":            region,
                "asset_class":       asset_cls,
                "asset_class_raw":   asset_cls_raw,
                "broad_asset_class": broad_ac,
                "currency":          ccy,
                "ticker_type":       ticker_type,
                "pence":             ticker.endswith(".L"),
                "usx":               str(row["base_currency"]).strip() == "USX",
            }

        if src == "yfinance PR":
            if pr and pr not in seen:
                instruments.append(_entry(pr, "Price Return (Index)"))
                seen.add(pr)
            if tr and tr not in seen:
                instruments.append(_entry(tr, "Total Return (ETF)"))
                seen.add(tr)
        elif src == "yfinance TR":
            if tr and tr not in seen:
                instruments.append(_entry(tr, "Total Return (ETF)"))
                seen.add(tr)

    print(f"  Library loaded: {len(instruments)} unique instruments "
          f"({sum(1 for i in instruments if i['ticker_type'].startswith('Price'))} PR, "
          f"{sum(1 for i in instruments if i['ticker_type'].startswith('Total'))} TR)")
    return instruments


def collect_comp_assets(instruments, comp_fx_cache):
    """Fetch prices and compute returns for every instrument in the library.

    Fetch prices and compute returns for every instrument, using the
    comprehensive FX cache and level-change set.  Adds a 'Ticker Type' column.
    """
    print(f"\nFetching comp library ({len(instruments)} instruments)...")
    rows = []

    for inst in instruments:
        ticker      = inst["ticker"]
        name        = inst["name"]
        region      = inst["region"]
        asset_class = inst["asset_class"]      # asset_subclass (granular)
        asset_class_raw = inst.get("asset_class_raw", asset_class)  # raw asset_class for sort/logic
        broad_ac    = inst.get("broad_asset_class", asset_class_raw)  # display label
        ccy         = inst["currency"]
        ticker_type = inst["ticker_type"]
        is_pence    = inst["pence"]
        is_usx      = inst.get("usx", False)
        # Rates and Spread asset classes are expressed as bps changes
        is_yield    = asset_class_raw in ("Rates", "Spread")
        is_level    = ticker in COMP_LEVEL_CHANGE_TICKERS
        # USX and USD instruments need no FX conversion
        local_ccy   = None if ccy == "USD" else ccy

        print(f"  [{ticker_type[:2]}] {ticker} ({name[:40]})...")
        series = fetch_yf_history(ticker)

        row = {
            "Symbol":            ticker,
            "Name":              name,
            "Ticker Type":       ticker_type,
            "Region":            region,
            "Broad Asset Class": broad_ac,
            "Sub-Category":      asset_class,
            "Currency":          ccy,
            "Last Price":        np.nan,
            "Last Date":         np.nan,
            "_sort_group":       _LIB_ASSET_CLASS_GROUP.get(asset_class_raw, 99),
        }

        if series is None or series.empty:
            print(f"    → No data")
            for pk in PERIODS:
                if is_yield or is_level:
                    row[f"Local {pk} (bps)"] = np.nan
                else:
                    row[f"Local {pk}"] = np.nan
                    row[f"USD {pk}"] = np.nan
            rows.append(row)
            time.sleep(0.3)
            continue

        if is_pence:
            median_val = series.dropna().median()
            if pd.notna(median_val) and median_val > 50:
                series = series / 100
        elif is_usx:
            # Agricultural futures quoted in US cents — convert to USD
            series = series / 100

        row["Last Price"] = round(series.iloc[-1], 4)
        row["Last Date"]  = str(series.index[-1].date())

        for pk in PERIODS:
            local_ret = calc_return(series, pk, is_yield=is_yield, is_level=is_level)
            if is_yield or is_level:
                row[f"Local {pk} (bps)"] = local_ret
            else:
                row[f"Local {pk}"] = local_ret
                if local_ccy is None:
                    row[f"USD {pk}"] = local_ret
                else:
                    row[f"USD {pk}"] = usd_adjusted_return(
                        local_ret, local_ccy, pk, comp_fx_cache,
                        fcy_per_usd=COMP_FCY_PER_USD,
                    )

        rows.append(row)
        time.sleep(0.3)

    return rows


def collect_comp_fred_assets():
    """Collect all FRED-sourced instruments from the library for market_data_comp.

    Handles three series types determined by which ticker column is populated:
      ticker_fred_oas  → Spread/OAS series   → bps change (is_yield=True)
      ticker_fred_yield → Yield series        → bps change (is_yield=True)
      ticker_fred_tr   → Total return index   → % return  (is_yield=False)

    Asset class is read directly from the library.
    """
    df = pd.read_csv(LIBRARY_PATH)
    fred_rows = df[
        (df["data_source"] == "FRED") &
        (df["validation_status"] == "CONFIRMED")
    ].copy()

    fred_rows["_s"] = fred_rows.apply(_lib_sort_key, axis=1)
    fred_rows = fred_rows.sort_values("_s").drop(columns=["_s"])

    print(f"\nFetching comp FRED series ({len(fred_rows)} rows)...")
    rows = []

    def _val(v):
        s = str(v).strip()
        return None if s in ("nan", "N/A", "") else s

    for _, lib_row in fred_rows.iterrows():
        name          = str(lib_row["name"]).strip()
        region        = str(lib_row.get("region", "Global")).strip()
        if region in ("nan", "", "N/A"):
            region = "Global"
        asset_cls_raw = str(lib_row["asset_class"]).strip()
        broad_ac      = str(lib_row.get("broad_asset_class", asset_cls_raw)).strip()
        asset_sub     = str(lib_row.get("asset_subclass", "")).strip()

        # Determine which FRED ticker to use — priority: OAS > TR > yield
        oas_id   = _val(lib_row.get("ticker_fred_oas"))
        tr_id    = _val(lib_row.get("ticker_fred_tr"))
        yield_id = _val(lib_row.get("ticker_fred_yield"))

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
            continue  # no usable ticker

        print(f"  {series_id} ({name[:45]})...")
        series = fetch_fred_series(series_id)

        row = {
            "Symbol":            series_id,
            "Name":              name,
            "Ticker Type":       "FRED",
            "Region":            region,
            "Broad Asset Class": broad_ac,
            "Sub-Category":      asset_sub,
            "Currency":          "USD",
            "Last Price":        np.nan,
            "Last Date":         np.nan,
            "_sort_group":       _LIB_ASSET_CLASS_GROUP.get(asset_cls_raw, 99),
        }

        if series is not None and not series.empty:
            row["Last Price"] = round(series.iloc[-1], 4)
            row["Last Date"]  = str(series.index[-1].date())
            for pk in PERIODS:
                if is_yield:
                    row[f"Local {pk} (bps)"] = calc_return(series, pk, is_yield=True)
                else:
                    row[f"Local {pk}"] = calc_return(series, pk, is_yield=False)
                    row[f"USD {pk}"]   = row[f"Local {pk}"]
        else:
            for pk in PERIODS:
                if is_yield:
                    row[f"Local {pk} (bps)"] = np.nan
                else:
                    row[f"Local {pk}"] = np.nan
                    row[f"USD {pk}"]   = np.nan

        rows.append(row)

    return rows


# ─────────────────────────────────────────────
# GOOGLE SHEETS EXPORT
# ─────────────────────────────────────────────

SPREADSHEET_ID = "12nKIUGHz5euDbNQPDTVECsJBNwrceRF1ymsQrIe4_ac"

def push_to_google_sheets(df_main, df_comp=None):
    """
    Push market_data (and optionally market_data_comp) to Google Sheets.
    Credentials are read from the GOOGLE_CREDENTIALS environment variable
    (set as a GitHub Actions secret containing the service account JSON).
    df_comp: optional DataFrame for the market_data_comp tab.
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

    def _sv(v):
        """Serialize one cell: keep numbers as float, dates/strings as str, NaN as ''."""
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

    def df_to_values(df):
        """Convert dataframe to list-of-lists for Sheets API, preserving numeric types."""
        header = df.columns.tolist()
        rows = [[_sv(v) for v in row] for row in df.itertuples(index=False)]
        return [header] + rows

    def ensure_tab_exists(tab_name):
        """Create the sheet tab if it does not already exist."""
        meta = sheets.get(spreadsheetId=SPREADSHEET_ID).execute()
        existing = {s["properties"]["title"] for s in meta.get("sheets", [])}
        if tab_name not in existing:
            sheets.batchUpdate(
                spreadsheetId=SPREADSHEET_ID,
                body={"requests": [{"addSheet": {"properties": {"title": tab_name}}}]},
            ).execute()
            print(f"  Created new tab '{tab_name}'")

    def write_sheet(tab_name, values):
        """Ensure tab exists, clear it, and write values."""
        ensure_tab_exists(tab_name)
        sheets.values().clear(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{tab_name}!A1:ZZ10000"
        ).execute()

        sheets.values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{tab_name}!A1",
            valueInputOption="USER_ENTERED",
            body={"values": values}
        ).execute()
        print(f"  ✓ Written {len(values)-1} rows to '{tab_name}' tab")

    # Remove legacy / deprecated tabs on every run — list sourced from
    # library_utils.SHEETS_LEGACY_TABS_TO_DELETE (single source of truth).
    try:
        meta = sheets.get(spreadsheetId=SPREADSHEET_ID).execute()
        delete_requests = []
        for sheet in meta.get("sheets", []):
            title = sheet["properties"]["title"]
            if title in SHEETS_LEGACY_TABS_TO_DELETE:
                delete_requests.append(
                    {"deleteSheet": {"sheetId": sheet["properties"]["sheetId"]}}
                )
                print(f"  Queued deletion of legacy tab '{title}'")
        if delete_requests:
            sheets.batchUpdate(
                spreadsheetId=SPREADSHEET_ID,
                body={"requests": delete_requests}
            ).execute()
            print(f"  Deleted {len(delete_requests)} legacy tab(s)")
    except Exception as e:
        print(f"  WARNING: Could not clean up legacy tabs: {e}")

    print("\nPushing data to Google Sheets...")
    write_sheet("market_data", df_to_values(df_main))

    if df_comp is not None and not df_comp.empty:
        write_sheet("market_data_comp", df_to_values(df_comp))

    print("✓ Google Sheets export complete.")


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

def _build_library_df(yf_rows, fred_rows):
    """Assemble a library-driven DataFrame from yfinance + FRED row lists.

    Common helper for both market_data and market_data_comp pipelines.
    Sorts by _sort_group, enforces standard column order, adds row_id.
    """
    all_rows = yf_rows + fred_rows
    all_rows.sort(key=lambda r: r.get("_sort_group", 99))
    df = pd.DataFrame([
        {k: v for k, v in r.items() if k != "_sort_group"}
        for r in all_rows
    ])
    _leading = ["Symbol", "Name", "Ticker Type", "Broad Asset Class", "Region", "Sub-Category"]
    _rest = [c for c in df.columns if c not in _leading]
    df = df[_leading + _rest]
    df.insert(0, "row_id", range(1, len(df) + 1))
    return df


def main():
    print("=" * 60)
    print(f"Market Dashboard Data Fetch — {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    os.makedirs("data", exist_ok=True)

    # ── FX cache (shared by both pipelines) ──────────────────────────────
    fx_cache = build_comp_fx_cache()

    # ── market_data (simple dashboard — simple_dash == True) ─────────────
    print("\n" + "=" * 60)
    print("SIMPLE DASHBOARD (market_data)")
    print("=" * 60)
    simple_instruments = load_simple_library()
    simple_yf_rows     = collect_comp_assets(simple_instruments, fx_cache)
    simple_fred_rows   = collect_simple_fred_assets()
    df_main = _build_library_df(simple_yf_rows, simple_fred_rows)

    main_path = "data/market_data.csv"
    df_main.to_csv(main_path, index=False)
    print(f"\n✓ Saved {main_path} — {len(df_main)} instruments")

    # ── market_data_comp (full library) ──────────────────────────────────
    df_comp = None
    try:
        print("\n" + "=" * 60)
        print("COMPREHENSIVE LIBRARY (market_data_comp)")
        print("=" * 60)
        comp_instruments = load_instrument_library()
        comp_yf_rows     = collect_comp_assets(comp_instruments, fx_cache)
        comp_fred_rows   = collect_comp_fred_assets()
        df_comp = _build_library_df(comp_yf_rows, comp_fred_rows)

        comp_path = "data/market_data_comp.csv"
        df_comp.to_csv(comp_path, index=False)
        print(f"\n✓ Saved {comp_path} — {len(df_comp)} instruments")
        print("\n--- Comp asset class breakdown ---")
        if "Sub-Category" in df_comp.columns:
            print(df_comp["Sub-Category"].value_counts().to_string())
    except Exception as e:
        print(f"\nWARNING: Comprehensive library collection failed: {e}")
        print("  market_data will still be pushed; market_data_comp will be skipped.")
        df_comp = None

    # ── Push to Google Sheets ────────────────────────────────────────────
    push_to_google_sheets(df_main, df_comp=df_comp)

    print(f"\n✓ Completed at {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")

    print("\n--- market_data asset class breakdown ---")
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

# ============================================================
# COMPREHENSIVE HISTORICAL SERIES
# Builds market_data_comp_hist tab + CSV using all instruments
# from index_library.csv.  Start date: 1950-01-01.
# Runs after run_hist() so any failure cannot affect earlier
# pipeline outputs.
# ============================================================

try:
    from fetch_hist import run_comp_hist
    run_comp_hist()
except Exception as _comp_hist_err:
    print(f"[CompHist] Non-fatal import/run error: {_comp_hist_err}")
    print("[CompHist] Existing pipeline outputs are unaffected")

# ============================================================
# PHASE D (TIER 2) — BUSINESS SURVEY DATA (DB.NOMICS)
# Fetches ISM, ECB BLS, Eurostat ESI, BOJ Tankan from DB.nomics.
# Outputs: data/macro_dbnomics.csv, data/macro_dbnomics_hist.csv
#          Google Sheets tabs: macro_dbnomics, macro_dbnomics_hist
# Runs before Phase E so indicators can consume the history.
# ============================================================

try:
    from fetch_macro_dbnomics import run_phase_d
    run_phase_d()
except Exception as _phase_d_err:
    print(f"[Phase D] Non-fatal import/run error: {_phase_d_err}")
    print("[Phase D] Existing pipeline outputs are unaffected")

# ============================================================
# PHASE D (TIER 3) — PROPRIETARY PMI / SURVEY DATA (FMP)
# Fetches S&P Global PMIs (EZ/UK/JP/CN), ZEW, IFO, NBS, Caixin
# from the FMP economic calendar.
# Outputs: data/macro_fmp.csv, data/macro_fmp_hist.csv
#          Google Sheets tabs: macro_fmp, macro_fmp_hist
# ============================================================

try:
    from fetch_macro_fmp import run_phase_d_fmp
    run_phase_d_fmp()
except Exception as _phase_d_fmp_err:
    print(f"[Phase D FMP] Non-fatal import/run error: {_phase_d_fmp_err}")
    print("[Phase D FMP] Existing pipeline outputs are unaffected")
    try:
        import pathlib as _pl
        _pl.Path("data/fmp_debug.txt").write_text(
            f"FMP IMPORT/RUN ERROR: {_phase_d_fmp_err}\n")
    except Exception:
        pass

# ============================================================
# PHASE E — MACRO-MARKET INDICATORS
# Computes 50 composite macro-market indicators as weekly
# time series with rolling z-scores and regime classifications.
# Outputs: data/macro_market.csv, data/macro_market_hist.csv
#          Google Sheets tabs: macro_market, macro_market_hist
# Runs last so all upstream hist CSVs are guaranteed to exist.
# ============================================================

try:
    from compute_macro_market import run_phase_e
    run_phase_e()
except Exception as _phase_e_err:
    print(f"[Phase E] Non-fatal import/run error: {_phase_e_err}")
    print("[Phase E] Existing pipeline outputs are unaffected")
