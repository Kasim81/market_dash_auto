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

from library_utils import (
    COMP_FX_TICKERS,
    COMP_FCY_PER_USD,
    lib_sort_key as _comp_inst_sort_key,
    write_hist_with_archive,
)
from sources.base import (
    get_sheets_service,
    push_df_to_sheets as _base_push,
)
from sources import fred as fred_src

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

FRED_API_KEY            = os.environ.get("FRED_API_KEY", "")
GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS", "")
SHEET_ID                = "12nKIUGHz5euDbNQPDTVECsJBNwrceRF1ymsQrIe4_ac"

# Rate limit delays
YFINANCE_DELAY          = 0.3            # seconds between yfinance per-ticker calls
FRED_DELAY              = 0.6            # seconds between FRED calls (comp_hist FRED rates)

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
    """Fetch full FRED series history from `start` via sources.fred."""
    return fred_src.fetch_series_as_pandas(series_id, FRED_API_KEY, start=start)



def save_csv(df: pd.DataFrame, path: str, label: str,
             prefix_rows: list = None) -> None:
    """
    Save DataFrame to CSV.
    If prefix_rows is provided, those rows are written before the header+data
    so metadata (Name, Region, etc.) appears at the top of the file.
    Read back with pd.read_csv(path, header=len(prefix_rows)) to skip them.

    For *_hist.csv paths, routes through library_utils.write_hist_with_archive()
    which preserves any rows that would otherwise be lost to source-side
    floor advancement (per forward_plan §3.1.1).
    """
    if df.empty:
        print(f"  [{label}] Empty — skipping CSV write")
        return

    if path.endswith("_hist.csv"):
        write_hist_with_archive(df, path, prefix_rows=prefix_rows)
    else:
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
    """Thin wrapper around sources.base.push_df_to_sheets with this module's creds/SHEET_ID."""
    try:
        _base_push(
            get_sheets_service(GOOGLE_CREDENTIALS_JSON),
            SHEET_ID,
            tab_name,
            df,
            label=label,
            prefix_rows=prefix_rows,
        )
    except json.JSONDecodeError as e:
        print(f"  [{label}] GOOGLE_CREDENTIALS JSON error: {e} — skipping")
    except Exception as e:
        print(f"  [{label}] Sheets push failed: {e} — skipping")


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
        broad_ac    = str(row.get("broad_asset_class", asset_class)).strip()
        asset_sub   = str(row.get("asset_subclass", "")).strip()
        units       = str(row.get("units", "")).strip()
        if units in ("nan", ""):
            units = ""
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
                "asset_class": asset_class, "broad_asset_class": broad_ac,
                "asset_subclass": asset_sub, "units": units,
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
        ac_raw = str(row.get("asset_class", "")).strip()
        fred_rates.append({
            "series_id":        series_id,
            "name":             str(row.get("name", series_id)).strip(),
            "region":           str(row.get("region", "")).strip(),
            "asset_class":      ac_raw,
            "broad_asset_class": str(row.get("broad_asset_class", ac_raw)).strip(),
            "asset_subclass":   str(row.get("asset_subclass", "")).strip(),
            "units":            str(row.get("units", "")).strip(),
            "is_yield":         is_yield,
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

    # Collect per-ticker close series in a dict, then assemble the wide
    # DataFrame in one pd.concat at the end.  Avoids ~390 single-column
    # inserts that fragment the block manager and trigger PerformanceWarnings.
    close_series: dict[str, pd.Series] = {}

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
                        close_series[ticker] = s
        except Exception as e:
            print(f"    Chunk {ci} failed ({e})")
        time.sleep(YFINANCE_DELAY)

    failed = [t for t in tickers if t not in close_series]
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
                    close_series[ticker] = s
                    print(f"    [{i}] {ticker}: OK ({len(s)} rows)")
                else:
                    print(f"    [{i}] {ticker}: empty")
            except Exception as e:
                print(f"    [{i}] {ticker}: failed ({e})")
            time.sleep(YFINANCE_DELAY)

    close_df = pd.concat(close_series, axis=1) if close_series else pd.DataFrame()

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

    # Collect every column into a dict keyed by final column name, then
    # build the wide DataFrame in a single pd.DataFrame() call.  Per-column
    # assignment in a 780-iteration loop fragments the block manager.
    columns: dict[str, pd.Series] = {}

    for ticker in all_ordered:
        if ticker in local_yf:
            s = local_yf[ticker]
        elif ticker in local_fr:
            s = local_fr[ticker]
        else:
            s = pd.Series(np.nan, index=spine)
        columns[f"{ticker}_Local"] = s

    for ticker in all_ordered:
        if ticker in usd_yf:
            s = usd_yf[ticker]
        elif ticker in usd_fr:
            s = usd_fr[ticker]
        else:
            s = pd.Series(np.nan, index=spine)
        columns[f"{ticker}_USD"] = s

    df = pd.DataFrame(columns, index=spine)
    df.index.name = "Date"
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
            broad_ac  = inst.get("broad_asset_class", asset_cls)
            asset_sub = inst.get("asset_subclass", "")
            units     = inst.get("units", "")
            local_ccy = inst["currency"] or "USD"
        elif base in fr_meta:
            fr_row    = fr_meta[base]
            source    = "FRED"
            name      = fr_row["name"]
            region    = fr_row["region"]
            asset_cls = fr_row["asset_class"]
            broad_ac  = fr_row.get("broad_asset_class", asset_cls)
            asset_sub = fr_row.get("asset_subclass", "")
            units     = fr_row.get("units", "")
            local_ccy = "USD"
        else:
            source = name = region = asset_cls = broad_ac = asset_sub = units = ""
            local_ccy = "USD"

        display_ac = _ac_display.get(asset_cls, asset_cls)

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
    run_comp_hist()
