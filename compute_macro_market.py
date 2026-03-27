"""
compute_macro_market.py
=======================
Phase E — Macro-Market Indicators
Market Dashboard Expansion

WHAT THIS MODULE DOES
---------------------
Computes 50 macro-market composite indicators defined in
macromarket/macro_indicator_library.csv as weekly time series.

For each indicator three values are produced per date:
  raw     — the ratio, spread, growth rate, level or composite as defined
  zscore  — rolling normalisation (see Z-SCORE CONFIGURATION section below)
  regime  — discrete string classification based on z-score / level thresholds

Outputs:
  data/macro_market.csv       — snapshot: one row per indicator (50 rows)
  data/macro_market_hist.csv  — full weekly history (dates × 150 columns)
  Google Sheets 'macro_market'       — snapshot tab
  Google Sheets 'macro_market_hist'  — history tab

INPUT FILES (must exist — produced by earlier pipeline phases)
--------------------------------------------------------------
  data/market_data_comp_hist.csv  — weekly prices, 300+ instruments (Phase B/CompHist)
  data/macro_us_hist.csv          — weekly FRED macro series            (Phase A)
  data/macro_intl_hist.csv        — OECD CLI + macro, ffilled to weekly (Phase C)

SUPPLEMENTAL DATA FETCHED HERE (not in the hist files above)
------------------------------------------------------------
  FRED : PIORECRUSDM, BAMLHE00EHYIOAS, IRLTLT01CNM156N, IRLTLT01INM156N,
         IRLTLT01GBM156N, IRLTLT01DEM156N, DGS10
  ECB  : Euro area AAA govt yield + Euro IG corporate yield → EU_I1 spread
         (falls back to FRED BAMLHE00EHYIOAS if ECB unavailable)
  yfinance: FXI (iShares China Large-Cap ETF) for AS_G1 denominator

DESIGN PRINCIPLES
-----------------
· Self-contained. Zero changes to any existing pipeline file except the
  Phase E block appended to fetch_data.py.
· One try/except per indicator — one failure never kills the whole run.
· If input hist CSVs are absent the module logs a clear error and exits.
· Sheets tabs 'macro_market' + 'macro_market_hist' are created if absent;
  no other tabs are touched.
· Same credentials pattern (GOOGLE_CREDENTIALS env var) as all other phases.

STANDALONE USAGE
----------------
    python compute_macro_market.py

CALLED FROM fetch_data.py
--------------------------
    try:
        from compute_macro_market import run_phase_e
        run_phase_e()
    except Exception as _e_err:
        print(f"[Phase E] Non-fatal error: {_e_err}")
"""

import os
import time
import json
import requests
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# CONFIG — credentials, sheet IDs, output paths
# ---------------------------------------------------------------------------

FRED_API_KEY             = os.environ.get("FRED_API_KEY", "")
GOOGLE_CREDENTIALS_JSON  = os.environ.get("GOOGLE_CREDENTIALS", "")

SHEET_ID     = "12nKIUGHz5euDbNQPDTVECsJBNwrceRF1ymsQrIe4_ac"
SNAPSHOT_TAB = "macro_market"
HIST_TAB     = "macro_market_hist"
SNAPSHOT_CSV = "data/macro_market.csv"
HIST_CSV     = "data/macro_market_hist.csv"

# Input CSV paths (produced by earlier phases)
COMP_HIST_CSV      = "data/market_data_comp_hist.csv"
MACRO_US_HIST_CSV  = "data/macro_us_hist.csv"
MACRO_INTL_HIST_CSV = "data/macro_intl_hist.csv"

# FRED API settings — mirrors fetch_macro_us_fred.py
FRED_BASE_URL      = "https://api.stlouisfed.org/fred/series/observations"
FRED_REQUEST_DELAY = 0.6    # seconds between calls — ~100 req/min, under 120 limit
FRED_BACKOFF_BASE  = 2      # exponential backoff base (seconds)
FRED_MAX_RETRIES   = 5

# ECB Statistical Data Warehouse REST API
ECB_BASE_URL       = "https://sdw-wsrest.ecb.europa.eu/service/data"
ECB_REQUEST_DELAY  = 2.0    # seconds between ECB calls

# yfinance delay between calls (matches existing pipeline)
YF_REQUEST_DELAY   = 0.3

# History start — weekly spine floor
HIST_START = "2000-01-01"

# ===========================================================================
# Z-SCORE CONFIGURATION
# ---------------------------------------------------------------------------
# ZSCORE_WINDOW      : number of weekly observations in the rolling window.
#                      260 = 5 years (5 × 52 weeks). Increase for more stable
#                      / slower-reacting signals; decrease for more responsive.
#
# ZSCORE_MIN_PERIODS : minimum observations before a z-score is emitted.
#                      52 = 1-year warm-up period. Rows before this threshold
#                      receive NaN z-scores.
#
# To switch to a full-history (expanding-window) z-score, change:
#   ZSCORE_WINDOW = None
# pandas rolling(window=None, min_periods=...) becomes an expanding window.
# ===========================================================================
ZSCORE_WINDOW      = 260    # 5-year rolling window (weeks)
ZSCORE_MIN_PERIODS = 52     # 1-year minimum warm-up (weeks)

# ---------------------------------------------------------------------------
# INDICATOR METADATA  (id → region_block, category, formula_note)
# Matches macromarket/macro_indicator_library.csv
# ---------------------------------------------------------------------------
INDICATOR_META = {
    # US & Neighbours — Growth
    "US_G1":     ("US & Neighbours", "Growth / cyclicals vs defensives",
                  "log(XLY / XLP)"),
    "US_G2":     ("US & Neighbours", "Growth / broader cyclicals vs defensives",
                  "log((XLI+XLF) / (XLU+XLP))"),
    "US_G3":     ("US & Neighbours", "Size cycle",
                  "log(IWM / IWB)"),
    "US_G4":     ("US & Neighbours", "Style / value vs growth",
                  "log(IWD / IWF)"),
    # US & Neighbours — Rates & Credit
    "US_I1":     ("US & Neighbours", "Yield-curve slope 10Y-3M",
                  "T10Y3M (FRED direct)"),
    "US_I2":     ("US & Neighbours", "HY credit spread",
                  "BAMLH0A0HYM2 (US HY OAS, FRED)"),
    "US_I3":     ("US & Neighbours", "Commodities vs bonds",
                  "log(DBC / GOVT)"),
    "US_I4":     ("US & Neighbours", "IG credit spread",
                  "BAMLC0A0CM (US IG OAS, FRED)"),
    "US_I5":     ("US & Neighbours", "HY-IG differential",
                  "BAMLH0A0HYM2 - BAMLC0A0CM"),
    "US_I6":     ("US & Neighbours", "Yield-curve slope 2s10s",
                  "T10Y2Y (FRED direct)"),
    "US_I7":     ("US & Neighbours", "10Y breakeven inflation",
                  "T10YIE (FRED direct)"),
    # US & Neighbours — Volatility
    "US_R1":     ("US & Neighbours", "Vol term structure (equity)",
                  "VIX3M - VIX (arithmetic spread)"),
    "US_R2":     ("US & Neighbours", "Rates vs equity vol",
                  "log(MOVE / VIX)"),
    # US & Neighbours — Real rates & FX
    "US_RR1":    ("US & Neighbours", "Real rates / valuation",
                  "DFII10 (TIPS 10Y real yield, FRED direct)"),
    "US_FX1":    ("US & Neighbours", "Dollar vs EM & commodities",
                  "log(EEM / DX-Y.NYB)"),
    "US_FX2":    ("US & Neighbours", "Copper vs gold",
                  "log(HG=F / GC=F)"),
    # US & Neighbours — Momentum
    "M1":        ("US & Neighbours", "Momentum – US equities trend",
                  "(S&P500 - 40wk SMA) / 40wk SMA"),
    "M2":        ("US & Neighbours", "Momentum – multi-asset trend",
                  "fraction of {SPY,URTH,GOVT,REET,DBC} above 40wk SMA"),
    "M3":        ("US & Neighbours", "Momentum – dual momentum equity/bond",
                  "max(SPY_12m, URTH_12m) - SHY_12m"),
    "M4":        ("US & Neighbours", "Momentum – US HY vs Treasuries",
                  "(HY_TR_index - 40wk SMA) / 40wk SMA"),
    "M5":        ("US & Neighbours", "Momentum – vol-filtered equity",
                  "VIX 10wk MA - VIX 30wk MA"),
    # US & Neighbours — Leading / Macro
    "US_LEI1":   ("US & Neighbours", "Growth / Leading indicators",
                  "USSLIND 6M annualised % change"),
    "US_JOBS1":  ("US & Neighbours", "Labour market / Leading",
                  "IC4WSA YoY % change"),
    "US_LAB1":   ("US & Neighbours", "Labour market composite",
                  "avg_z[ inv(UNRATE), PAYEMS_YoY, inv(IC4WSA) ]"),
    "US_GROWTH1":("US & Neighbours", "Real activity / Growth",
                  "avg_z[ INDPRO_YoY, RSXFS_YoY ]"),
    "US_HOUS1":  ("US & Neighbours", "Housing / Construction",
                  "PERMIT 12M % change"),
    "US_M2L1":   ("US & Neighbours", "Liquidity",
                  "M2SL YoY % change"),
    # Europe & UK
    "EU_G1":     ("Europe & UK", "Growth / cyclicals vs defensives (Europe)",
                  "log((EXH4.DE+EXV1.DE+EXV3.DE) / (EXH9.DE+EXH3.DE))"),
    "EU_G2":     ("Europe & UK", "UK domestic vs global",
                  "log(FTMC / FTSE100)"),
    "EU_G3":     ("Europe & UK", "Eurozone vs US leadership",
                  "log(EuroStoxx50_USD / SPY_USD)"),
    "EU_I1":     ("Europe & UK", "Euro credit vs govts",
                  "ECB Euro IG yield - Euro AAA govt yield (BAMLHE00EHYIOAS fallback)"),
    "EU_I2":     ("Europe & UK", "UK real-yield / inflation proxy",
                  "log(INXG.L / IGLT.L) — IL vs nominal gilt ETF ratio"),
    "EU_I3":     ("Europe & UK", "UK–Germany gilt-bund spread",
                  "IRLTLT01GBM156N - IRLTLT01DEM156N (FRED)"),
    "EU_R1":     ("Europe & UK", "UK credit conditions",
                  "log(SLXX.L / IGLT.L)"),
    "EU_FX1":    ("Europe & UK", "EUR vs European cyclicals",
                  "composite_z(log(EURUSD), log(EXH4.DE/EXH9.DE))"),
    # Asia (China-centred)
    "AS_G1":     ("Asia (China-centred)", "China size / domestic cycle",
                  "log(ASHR / FXI) — CSI 300 ETF / China Large-Cap ETF proxy"),
    "AS_G2":     ("Asia (China-centred)", "China vs global DM",
                  "log(000001.SS_USD / URTH_USD)"),
    "AS_G3":     ("Asia (China-centred)", "India domestic growth breadth",
                  "avg log-ratio: NiftyMid100/Nifty50 + NiftySmall100/Nifty50"),
    "AS_I1":     ("Asia (China-centred)", "China rates vs US",
                  "IRLTLT01CNM156N - DGS10 (FRED)"),
    "AS_I2":     ("Asia (China-centred)", "India govts vs US Treasuries",
                  "IRLTLT01INM156N - DGS10 (FRED)"),
    "AS_FX1":    ("Asia (China-centred)", "USD vs CNY",
                  "CNY=X level z-score"),
    "AS_FX2":    ("Asia (China-centred)", "USD vs INR",
                  "INR=X level z-score"),
    "AS_C1":     ("Asia (China-centred)", "China infrastructure proxy",
                  "log(PIORECRUSDM / HG=F)"),
    "AS_C2":     ("Asia (China-centred)", "China vs global commodities",
                  "log(PIORECRUSDM / DBC)"),
    # Global / Regional — CLI
    "REG_CLI1":  ("Global / Regional", "Regional growth diff: US vs Eurozone",
                  "USA_CLI - avg(DEU_CLI, FRA_CLI)  [EA19 not in OECD file]"),
    "REG_CLI2":  ("Global / Regional", "Regional growth diff: US vs China",
                  "USA_CLI - CHN_CLI"),
    "REG_CLI3":  ("Global / Regional", "Europe block CLI state",
                  "avg(DEU_CLI, FRA_CLI, GBR_CLI, ITA_CLI)"),
    "REG_CLI4":  ("Global / Regional", "Asia CLI state",
                  "avg(CHN_CLI, JPN_CLI, AUS_CLI)"),
    "REG_CLI5":  ("Global / Regional", "Global growth breadth",
                  "% of 9 countries where CLI>100 AND CLI>CLI_6M_ago"),
}

# Ordered list of all 50 indicator IDs (defines output column order)
ALL_INDICATOR_IDS = list(INDICATOR_META.keys())


# ===========================================================================
# SUPPLEMENTAL DATA FETCHERS
# ===========================================================================

def _fred_fetch_full(series_id: str, obs_start: str = "2000-01-01") -> pd.Series:
    """
    Fetch full history of a single FRED series from obs_start to present.
    Returns a pd.Series with DatetimeIndex, or an empty Series on failure.
    Applies exponential backoff on HTTP 429 / 5xx — mirrors fetch_hist.py.
    """
    if not FRED_API_KEY:
        print(f"  [FRED] WARNING: FRED_API_KEY not set — skipping {series_id}")
        return pd.Series(dtype=float, name=series_id)

    params = {
        "series_id":         series_id,
        "api_key":           FRED_API_KEY,
        "file_type":         "json",
        "sort_order":        "asc",
        "observation_start": obs_start,
    }
    for attempt in range(FRED_MAX_RETRIES):
        try:
            resp = requests.get(FRED_BASE_URL, params=params, timeout=20)
            if resp.status_code == 200:
                obs = resp.json().get("observations", [])
                dates, vals = [], []
                for o in obs:
                    if o.get("value") not in (".", "", None):
                        try:
                            dates.append(pd.to_datetime(o["date"]))
                            vals.append(float(o["value"]))
                        except (ValueError, KeyError):
                            continue
                if not dates:
                    return pd.Series(dtype=float, name=series_id)
                s = pd.Series(vals, index=dates, name=series_id)
                return s[~s.index.duplicated(keep="first")].sort_index()
            elif resp.status_code in (429, 500, 502, 503):
                wait = FRED_BACKOFF_BASE ** (attempt + 1)
                print(f"  [FRED] {resp.status_code} on {series_id} — "
                      f"backing off {wait}s (attempt {attempt+1}/{FRED_MAX_RETRIES})")
                time.sleep(wait)
            else:
                print(f"  [FRED] HTTP {resp.status_code} on {series_id} — skipping")
                return pd.Series(dtype=float, name=series_id)
        except Exception as exc:
            print(f"  [FRED] Error on {series_id}: {exc} — skipping")
            return pd.Series(dtype=float, name=series_id)
    print(f"  [FRED] All {FRED_MAX_RETRIES} retries exhausted for {series_id}")
    return pd.Series(dtype=float, name=series_id)


def fetch_supplemental_fred() -> dict:
    """
    Fetch FRED series required for macro_market indicators that are NOT
    already present in macro_us_hist.csv.

    Series fetched:
      PIORECRUSDM      — Iron Ore price (World Bank monthly, via FRED) [AS_C1, AS_C2]
      BAMLHE00EHYIOAS  — ICE BofA Euro HY OAS (EU_I1 primary / fallback)
      IRLTLT01CNM156N  — China 10Y govt bond yield (OECD via FRED) [AS_I1]
      IRLTLT01INM156N  — India 10Y govt bond yield (OECD via FRED) [AS_I2]
      IRLTLT01GBM156N  — UK 10Y Gilt yield (OECD via FRED) [EU_I2, EU_I3]
      IRLTLT01DEM156N  — Germany 10Y Bund yield (OECD via FRED) [EU_I3]
      DGS10            — US 10Y Treasury yield (daily, FRED) [AS_I1, AS_I2]

    Returns dict keyed by FRED series ID, values are pd.Series.
    """
    series_to_fetch = [
        "PIORECRUSDM",
        "BAMLHE00EHYIOAS",
        "IRLTLT01CNM156N",
        "IRLTLT01INM156N",
        "IRLTLT01GBM156N",
        "IRLTLT01DEM156N",
        "DGS10",
    ]
    result = {}
    print(f"\nFetching {len(series_to_fetch)} supplemental FRED series...")
    for sid in series_to_fetch:
        print(f"  {sid}...")
        s = _fred_fetch_full(sid)
        if not s.empty:
            print(f"    → {len(s)} obs  {s.index[0].date()} → {s.index[-1].date()}")
        else:
            print(f"    → no data")
        result[sid] = s
        time.sleep(FRED_REQUEST_DELAY)
    return result


def fetch_ecb_euro_ig_spread() -> pd.Series:
    """
    Attempt to fetch Euro IG corporate bond spread from the ECB SDW REST API.

    Strategy (in order):
      1. Fetch ECB AAA euro-area govt 10Y yield (YC dataset — well-documented).
      2. Fetch Euro IG corporate yield from FRED series BAMLEC0A0RMEY if it exists.
         (ICE BofA Euro Corporate Index Effective Yield — may or may not be on FRED.)
      3. Compute spread = corp_yield - govt_yield.
      4. Fallback: return BAMLHE00EHYIOAS (Euro HY OAS) fetched fresh from FRED
         as a directional credit-stress proxy — noted in INDICATOR_META for EU_I1.

    Returns pd.Series with monthly DatetimeIndex; caller resamples to weekly.
    """
    headers = {"Accept": "text/csv"}

    # --- Step 1: ECB AAA euro-area 10Y govt yield (YC dataset) ---
    govt_yield = pd.Series(dtype=float)
    ecb_yc_key = "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y"
    ecb_url = (
        f"{ECB_BASE_URL}/YC/{ecb_yc_key}"
        f"?format=csvdata&startPeriod=2000-01&detail=dataonly"
    )
    try:
        resp = requests.get(ecb_url, headers=headers, timeout=25)
        time.sleep(ECB_REQUEST_DELAY)
        if resp.status_code == 200 and resp.text.strip():
            from io import StringIO
            df_ecb = pd.read_csv(StringIO(resp.text))
            if "OBS_VALUE" in df_ecb.columns and "TIME_PERIOD" in df_ecb.columns:
                df_ecb["_dt"] = pd.to_datetime(
                    df_ecb["TIME_PERIOD"], format="%Y-%m", errors="coerce"
                )
                df_ecb = df_ecb.dropna(subset=["_dt", "OBS_VALUE"])
                govt_yield = pd.Series(
                    pd.to_numeric(df_ecb["OBS_VALUE"], errors="coerce").values,
                    index=df_ecb["_dt"].values,
                    name="ECB_EUR_GOVT_10Y",
                ).dropna().sort_index()
                print(f"  [ECB] AAA euro govt yield: {len(govt_yield)} monthly obs")
        else:
            print(f"  [ECB] YC dataset HTTP {resp.status_code} — skipping govt yield")
    except Exception as exc:
        print(f"  [ECB] YC fetch error: {exc}")
        time.sleep(ECB_REQUEST_DELAY)

    # --- Step 2: FRED Euro IG corporate effective yield ---
    corp_yield = pd.Series(dtype=float)
    if not govt_yield.empty:
        print("  [ECB→FRED] Trying BAMLEC0A0RMEY for Euro IG corp yield...")
        time.sleep(FRED_REQUEST_DELAY)
        corp_yield = _fred_fetch_full("BAMLEC0A0RMEY")
        if not corp_yield.empty:
            print(f"    → {len(corp_yield)} obs (Euro IG effective yield)")

    # --- Step 3: Compute spread if both are available ---
    if not govt_yield.empty and not corp_yield.empty:
        govt_m = govt_yield.resample("ME").last()
        corp_m = corp_yield.resample("ME").last()
        spread = (corp_m - govt_m).dropna()
        spread.name = "EU_I1_spread"
        print(f"  [ECB] EU_I1 IG spread computed: {len(spread)} monthly obs")
        return spread

    # --- Step 4: Fallback to Euro HY OAS (BAMLHE00EHYIOAS) ---
    print("  [ECB] Falling back to BAMLHE00EHYIOAS (Euro HY OAS) for EU_I1")
    time.sleep(FRED_REQUEST_DELAY)
    fallback = _fred_fetch_full("BAMLHE00EHYIOAS")
    fallback.name = "EU_I1_spread"
    return fallback


def fetch_fxi_prices() -> pd.Series:
    """
    Fetch FXI (iShares China Large-Cap ETF) weekly price history via yfinance.
    FXI is not in index_library.csv so is fetched directly here.
    Used as denominator for AS_G1 (small/large China proxy: ASHR / FXI).

    Returns pd.Series with DatetimeIndex (daily Close), or empty Series on failure.
    """
    print("  [yfinance] Fetching FXI (China Large-Cap ETF)...")
    try:
        raw = yf.download(
            "FXI",
            start=HIST_START,
            auto_adjust=True,
            progress=False,
            threads=False,
        )
        time.sleep(YF_REQUEST_DELAY)
        if raw.empty:
            print("    → no data")
            return pd.Series(dtype=float, name="FXI")
        close = raw["Close"].squeeze()
        close.name = "FXI"
        close.index = pd.to_datetime(close.index)
        close = close.dropna().sort_index()
        print(f"    → {len(close)} daily obs  "
              f"{close.index[0].date()} → {close.index[-1].date()}")
        return close
    except Exception as exc:
        print(f"    → FXI fetch error: {exc}")
        return pd.Series(dtype=float, name="FXI")


# ===========================================================================
# UTILITY FUNCTIONS
# ===========================================================================

def _to_weekly_friday(series: pd.Series) -> pd.Series:
    """
    Resample an arbitrary-frequency series to weekly Friday close.
    Uses last observation in the week then forward-fills gaps (for monthly data).
    """
    if series.empty:
        return series
    return series.resample("W-FRI").last().ffill()


def _rolling_zscore(series: pd.Series) -> pd.Series:
    """
    Apply a rolling z-score normalisation to a weekly price/level series.

    Window and min_periods are controlled by the module-level constants:
      ZSCORE_WINDOW      — rolling window in weeks (default 260 = 5 years)
      ZSCORE_MIN_PERIODS — minimum observations before emitting a value (default 52)

    To change to a full-history expanding z-score set ZSCORE_WINDOW = None.
    See the Z-SCORE CONFIGURATION section at the top of this file.
    """
    roll = series.rolling(window=ZSCORE_WINDOW, min_periods=ZSCORE_MIN_PERIODS)
    mu   = roll.mean()
    sig  = roll.std().replace(0, np.nan)
    return (series - mu) / sig


def _get_col(df: pd.DataFrame, col: str) -> pd.Series:
    """
    Safely extract a column from a DataFrame.
    Returns an empty Series with the df index if the column is absent,
    so callers never receive a KeyError — they just get NaN-filled results.
    """
    if col in df.columns:
        return df[col].copy()
    return pd.Series(dtype=float, index=df.index, name=col)


def _p(df_comp: pd.DataFrame, ticker: str, usd: bool = False) -> pd.Series:
    """
    Extract a price series from the comp_hist DataFrame.
    Variant is 'USD' when usd=True, otherwise 'Local'.
    Falls back to the other variant if the requested one is empty/absent.
    """
    variant  = "USD" if usd else "Local"
    fallback = "Local" if usd else "USD"
    col      = f"{ticker}_{variant}"
    fb_col   = f"{ticker}_{fallback}"
    s = _get_col(df_comp, col).dropna()
    if s.empty:
        s = _get_col(df_comp, fb_col).dropna()
    return s


def _log_ratio(num: pd.Series, den: pd.Series) -> pd.Series:
    """
    Compute log(num / den) on the aligned intersection of both series.
    Returns an empty Series if either input is empty or denominator is zero.
    """
    aligned = pd.concat([num, den], axis=1).ffill().dropna()
    if aligned.empty or aligned.shape[1] < 2:
        return pd.Series(dtype=float)
    n = aligned.iloc[:, 0]
    d = aligned.iloc[:, 1].replace(0, np.nan)
    return np.log(n / d).dropna()


def _arith_diff(a: pd.Series, b: pd.Series) -> pd.Series:
    """Arithmetic difference a - b on aligned intersection."""
    aligned = pd.concat([a, b], axis=1).ffill().dropna()
    if aligned.empty or aligned.shape[1] < 2:
        return pd.Series(dtype=float)
    return (aligned.iloc[:, 0] - aligned.iloc[:, 1]).dropna()


def _sum_log_ratio(nums: list, dens: list) -> pd.Series:
    """
    log(sum(num_prices) / sum(den_prices)) on aligned intersection.
    nums / dens are lists of pd.Series already extracted from comp_hist.
    """
    all_s = nums + dens
    aligned = pd.concat(all_s, axis=1).ffill().dropna()
    if aligned.empty or aligned.shape[1] < len(nums) + len(dens):
        return pd.Series(dtype=float)
    num_sum = aligned.iloc[:, :len(nums)].sum(axis=1)
    den_sum = aligned.iloc[:, len(nums):].sum(axis=1)
    den_sum = den_sum.replace(0, np.nan)
    return np.log(num_sum / den_sum).dropna()


def _yoy(series: pd.Series, freq: int = 52) -> pd.Series:
    """
    Year-over-year percentage change for a weekly series.
    freq=52 for weekly; uses shift(52) → one year back.
    Returns 100 * (x / x_1y_ago - 1).
    """
    prior = series.shift(freq)
    return (100.0 * (series / prior.replace(0, np.nan) - 1)).dropna()


def _annualised_change(series: pd.Series, periods: int = 6) -> pd.Series:
    """
    Annualised percentage change over `periods` months of a monthly series.
    Used for US_LEI1 (USSLIND 6-month annualised change).
    Formula: ((x / x_n_periods_ago) ^ (12/periods) - 1) * 100
    """
    prior = series.shift(periods)
    ratio = series / prior.replace(0, np.nan)
    return (100.0 * (ratio ** (12.0 / periods) - 1)).dropna()


def _z_of_series(series: pd.Series) -> pd.Series:
    """
    Compute the rolling z-score of a series (convenience wrapper).
    Used internally when building composite z-score indicators.
    """
    weekly = _to_weekly_friday(series)
    return _rolling_zscore(weekly)


def make_result(raw: pd.Series, ind_id: str) -> pd.DataFrame:
    """
    Given a raw indicator series, compute z-score and regime, returning a
    3-column DataFrame: raw | zscore | regime, indexed by weekly Friday dates.
    """
    if raw is None or (isinstance(raw, pd.Series) and raw.empty):
        return pd.DataFrame(columns=["raw", "zscore", "regime"])
    raw_w = _to_weekly_friday(raw)
    raw_w = raw_w[raw_w.index >= HIST_START]
    z     = _rolling_zscore(raw_w)
    regime_vals = []
    for rv, zv in zip(raw_w, z):
        try:
            regime_vals.append(_assign_regime(ind_id, float(rv), float(zv)))
        except Exception:
            regime_vals.append("n/a")
    return pd.DataFrame(
        {"raw": raw_w, "zscore": z, "regime": regime_vals},
        index=raw_w.index,
    )


# ===========================================================================
# REGIME CLASSIFICATION
# ===========================================================================
# Each entry is a lambda(raw_value, zscore) → regime_string.
# raw and zscore may be NaN — the lambda must guard against this.
# Thresholds follow macromarket/macro_indicator_library.csv.
# ===========================================================================

def _r(raw, z, pos_z, neg_z, pos_label, neg_label, neutral="neutral"):
    """
    Standard 3-bucket regime based purely on z-score.
    z > pos_z → pos_label; z < neg_z → neg_label; else → neutral.
    """
    if np.isnan(z):
        return "n/a"
    if z > pos_z:
        return pos_label
    if z < neg_z:
        return neg_label
    return neutral


REGIME_RULES = {
    # US Growth
    "US_G1":  lambda r, z: _r(r, z,  1, -1, "pro-growth",       "defensive"),
    "US_G2":  lambda r, z: _r(r, z,  1, -1, "risk-on",          "late-cycle"),
    "US_G3":  lambda r, z: _r(r, z,  1, -1, "small-cap-lead",   "large-cap-safety"),
    "US_G4":  lambda r, z: _r(r, z,  1, -1, "value-regime",     "growth-regime", "mixed"),
    # US Rates & Credit — some use level-based rules combined with z-score
    "US_I1":  lambda r, z: (
        "recession-watch" if (not np.isnan(r) and r < 0)
        else _r(r, z, 1, -1, "early-cycle", "late-cycle", "mid-cycle")
    ),
    "US_I2":  lambda r, z: (
        "stress"  if (not np.isnan(r) and r > 700) or (not np.isnan(z) and z > 1.5)
        else ("frothy" if not np.isnan(z) and z < -1 and not np.isnan(r) and r < 400
              else "normal")
    ),
    "US_I3":  lambda r, z: _r(r, z,  1, -1, "reflation",        "growth-scare",  "balanced"),
    "US_I4":  lambda r, z: (
        "IG-stress" if (not np.isnan(r) and r > 200) or (not np.isnan(z) and z > 1.5)
        else ("frothy" if not np.isnan(z) and z < -1 else "normal")
    ),
    "US_I5":  lambda r, z: _r(r, z,  1, -1, "quality-spread",   "complacent"),
    "US_I6":  lambda r, z: (
        "inverted" if (not np.isnan(r) and r < 0)
        else ("steep" if not np.isnan(r) and r > 0.5 and not np.isnan(z) and z > 1
              else ("flat" if not np.isnan(z) and z < -1 else "normal"))
    ),
    "US_I7":  lambda r, z: _r(r, z,  1, -1, "high-inflation-exp", "disinflation"),
    # Volatility
    "US_R1":  lambda r, z: (
        "stress" if not np.isnan(r) and r < 0
        else ("complacency" if not np.isnan(z) and z < -1 else "normal")
    ),
    "US_R2":  lambda r, z: _r(r, z,  1, -1, "macro-uncertainty", "calm"),
    # Real rates / FX
    "US_RR1": lambda r, z: _r(r, z,  1, -1, "high-real-rates",  "low-real-rates"),
    "US_FX1": lambda r, z: _r(r, z,  1, -1, "weak-USD",         "strong-USD"),
    "US_FX2": lambda r, z: _r(r, z,  1, -1, "global-growth",    "recession-watch"),
    # Momentum — raw value encodes the signal directly (not a ratio)
    "M1":     lambda r, z: ("risk-on" if not np.isnan(r) and r > 0 else "risk-off"),
    "M2":     lambda r, z: (
        "risk-on"  if not np.isnan(r) and r >= 0.6
        else ("defensive" if not np.isnan(r) and r < 0.4 else "neutral")
    ),
    "M3":     lambda r, z: ("equity-regime" if not np.isnan(r) and r > 0 else "bond-regime"),
    "M4":     lambda r, z: ("carry" if not np.isnan(r) and r > 0 else "stress"),
    "M5":     lambda r, z: ("equity-friendly" if not np.isnan(r) and r < 0 else "defensive"),
    # US Macro
    "US_LEI1": lambda r, z: (
        "recession-risk" if not np.isnan(r) and r < -4.3 and not np.isnan(z) and z < -1.5
        else ("late-cycle" if not np.isnan(r) and r < 0 else "expansion")
    ),
    "US_JOBS1":  lambda r, z: _r(r, z,  1, -1, "labour-deteriorating", "overheating", "stable"),
    "US_LAB1":   lambda r, z: _r(r, z,  1, -1, "strong-labour",        "weak-labour",  "mid-cycle"),
    "US_GROWTH1":lambda r, z: _r(r, z,  1, -1, "strong-growth",        "weak-growth"),
    "US_HOUS1":  lambda r, z: _r(r, z,  1, -1, "housing-expanding",    "housing-contracting"),
    "US_M2L1":   lambda r, z: _r(r, z,  1, -1, "abundant-liquidity",   "tight-liquidity"),
    # Europe
    "EU_G1":  lambda r, z: _r(r, z,  1, -1, "pro-growth-EU",    "defensive-EU"),
    "EU_G2":  lambda r, z: _r(r, z,  1, -1, "UK-domestic-strong","global-preferred"),
    "EU_G3":  lambda r, z: _r(r, z,  1, -1, "EU-outperform",    "US-dominance"),
    "EU_I1":  lambda r, z: _r(r, z,  1, -1, "EU-credit-tight",  "EU-easy"),
    "EU_I2":  lambda r, z: _r(r, z,  1, -1, "high-UK-infl-exp", "disinflation"),
    "EU_I3":  lambda r, z: _r(r, z,  1, -1, "UK-premium",       "EU-stress"),
    "EU_R1":  lambda r, z: _r(r, z,  1, -1, "credit-appetite",  "flight-to-quality"),
    "EU_FX1": lambda r, z: _r(r, z,  1, -1, "EU-macro-friendly","EU-strain"),
    # Asia
    "AS_G1":  lambda r, z: _r(r, z,  1, -1, "mid-cap-lead",     "large-cap-safety"),
    "AS_G2":  lambda r, z: _r(r, z,  1, -1, "China-outperform", "China-cautious"),
    "AS_G3":  lambda r, z: _r(r, z,  1, -1, "India-domestic-strong","large-cap-safety"),
    "AS_I1":  lambda r, z: _r(r, z,  1, -1, "China-bonds-outperform","China-underperform"),
    "AS_I2":  lambda r, z: _r(r, z,  1, -1, "India-carry-attractive","India-underperform"),
    "AS_FX1": lambda r, z: _r(r, z,  1, -1, "CNY-weak",         "CNY-strong"),
    "AS_FX2": lambda r, z: _r(r, z,  1, -1, "INR-weak",         "INR-strong"),
    "AS_C1":  lambda r, z: _r(r, z,  1, -1, "China-infra-optimism","China-demand-disappoint"),
    "AS_C2":  lambda r, z: _r(r, z,  1, -1, "China-commodity-lead","global-commodity-lead"),
    # Regional CLI
    "REG_CLI1": lambda r, z: _r(r, z,  1, -1, "US-leads-EU",    "EU-leads-US"),
    "REG_CLI2": lambda r, z: _r(r, z,  1, -1, "US-leads-China", "China-leads-US"),
    "REG_CLI3": lambda r, z: _r(r, z,  1, -1, "EU-above-trend", "EU-below-trend",  "near-trend"),
    "REG_CLI4": lambda r, z: _r(r, z,  1, -1, "Asia-above-trend","Asia-below-trend","near-trend"),
    # REG_CLI5 uses raw breadth value, not z-score
    "REG_CLI5": lambda r, z: (
        "broad-expansion" if not np.isnan(r) and r >= 0.7
        else ("contracting" if not np.isnan(r) and r < 0.4 else "mixed")
    ),
}


def _assign_regime(ind_id: str, raw: float, z: float) -> str:
    """
    Apply the indicator-specific regime rule.
    Returns 'n/a' for unknown indicators or if the rule raises an exception.
    """
    rule = REGIME_RULES.get(ind_id)
    if rule is None:
        return "n/a"
    try:
        return rule(raw, z)
    except Exception:
        return "n/a"


# ===========================================================================
# DATA LOADERS
# ===========================================================================

def load_comp_hist() -> pd.DataFrame:
    """
    Load market_data_comp_hist.csv into a wide DataFrame of weekly prices.

    File structure (written by fetch_hist.py run_comp_hist):
      Rows 0–10  : 11 metadata rows (Ticker ID, Variant, Source, Name, etc.)
      Row  11    : flat column header — 'row_id', 'Date', 'ACWI_Local', ...
      Row  12+   : weekly price data

    Column naming convention: '{TICKER}_{Variant}' e.g. 'XLY_Local', 'XLY_USD'.
    Returns DataFrame with DatetimeIndex (weekly Fridays) and ticker columns.
    """
    if not os.path.exists(COMP_HIST_CSV):
        raise FileNotFoundError(
            f"Missing {COMP_HIST_CSV} — run fetch_hist.py (run_comp_hist) first."
        )
    df = pd.read_csv(COMP_HIST_CSV, skiprows=11, index_col="Date", low_memory=False)
    df.index = pd.to_datetime(df.index, errors="coerce")
    df = df[df.index.notna()].sort_index()
    if "row_id" in df.columns:
        df = df.drop(columns=["row_id"])
    df = df.apply(pd.to_numeric, errors="coerce")
    # Keep only data from HIST_START onwards to limit memory
    df = df[df.index >= HIST_START]
    print(f"  [load] comp_hist: {df.shape[0]} rows × {df.shape[1]} cols "
          f"({df.index[0].date()} → {df.index[-1].date()})")
    return df


def load_macro_us_hist() -> pd.DataFrame:
    """
    Load macro_us_hist.csv into a wide DataFrame of weekly FRED series.

    File structure (written by fetch_hist.py run_hist):
      Rows 0–7  : 8 metadata rows (Series ID, Source, Name, Category, etc.)
      Row  8    : flat column header — 'row_id', 'Date', 'T10Y2Y', ...
      Row  9+   : weekly data (monthly/quarterly series forward-filled)

    Returns DataFrame with DatetimeIndex (weekly Fridays) and FRED ID columns.
    """
    if not os.path.exists(MACRO_US_HIST_CSV):
        raise FileNotFoundError(
            f"Missing {MACRO_US_HIST_CSV} — run fetch_hist.py (run_hist) first."
        )
    df = pd.read_csv(MACRO_US_HIST_CSV, skiprows=8, index_col="Date", low_memory=False)
    df.index = pd.to_datetime(df.index, errors="coerce")
    df = df[df.index.notna()].sort_index()
    if "row_id" in df.columns:
        df = df.drop(columns=["row_id"])
    df = df.apply(pd.to_numeric, errors="coerce")
    df = df[df.index >= HIST_START]
    print(f"  [load] macro_us_hist: {df.shape[0]} rows × {df.shape[1]} cols "
          f"({df.index[0].date()} → {df.index[-1].date()})")
    return df


def load_macro_intl_hist() -> pd.DataFrame:
    """
    Load macro_intl_hist.csv into a wide DataFrame of weekly international series.

    File structure (written by fetch_macro_international.py):
      Rows 0–7  : 8 metadata rows (Column ID, Source Code, Source, Indicator, etc.)
      Row  8    : flat column header — 'row_id', 'Date', 'FRA_CLI', ...
      Row  9+   : weekly data (monthly data forward-filled)

    CLI columns available: AUS, CAN, CHN, DEU, FRA, GBR, ITA, JPN, USA.
    Note: EA19_CLI is NOT present in the current OECD pull; DEU+FRA avg is
    used as a Eurozone proxy where EA19 is specified in the indicator formula.

    Returns DataFrame with DatetimeIndex (weekly Fridays) and column ID columns.
    """
    if not os.path.exists(MACRO_INTL_HIST_CSV):
        raise FileNotFoundError(
            f"Missing {MACRO_INTL_HIST_CSV} — run fetch_macro_international.py first."
        )
    df = pd.read_csv(MACRO_INTL_HIST_CSV, skiprows=8, index_col="Date", low_memory=False)
    df.index = pd.to_datetime(df.index, errors="coerce")
    df = df[df.index.notna()].sort_index()
    if "row_id" in df.columns:
        df = df.drop(columns=["row_id"])
    df = df.apply(pd.to_numeric, errors="coerce")
    df = df[df.index >= HIST_START]
    print(f"  [load] macro_intl_hist: {df.shape[0]} rows × {df.shape[1]} cols "
          f"({df.index[0].date()} → {df.index[-1].date()})")
    return df


# ===========================================================================
# INDICATOR CALCULATORS — US & NEIGHBOURS  (27 indicators)
#
# Each function signature: _calc_XXX(cp, mu, mi, supp) → pd.Series (raw values)
#   cp   = load_comp_hist()       wide DataFrame of market prices
#   mu   = load_macro_us_hist()   wide DataFrame of US FRED series
#   mi   = load_macro_intl_hist() wide DataFrame of international CLI series
#   supp = fetch_supplemental_fred() dict of extra FRED Series
# Only the args actually needed are used; **_ absorbs the rest.
# ===========================================================================

# ---------------------------------------------------------------------------
# GROWTH / RISK APPETITE  (US_G1–G4)
# ---------------------------------------------------------------------------

def _calc_US_G1(cp, **_):
    """Consumer Discretionary vs Staples: log(XLY / XLP)."""
    return _log_ratio(_p(cp, "XLY"), _p(cp, "XLP"))


def _calc_US_G2(cp, **_):
    """Cyclicals vs Defensives: log((XLI+XLF) / (XLU+XLP))."""
    return _sum_log_ratio(
        [_p(cp, "XLI"), _p(cp, "XLF")],
        [_p(cp, "XLU"), _p(cp, "XLP")],
    )


def _calc_US_G3(cp, **_):
    """Small Cap vs Large Cap: log(IWM / IWB)."""
    return _log_ratio(_p(cp, "IWM"), _p(cp, "IWB"))


def _calc_US_G4(cp, **_):
    """Value vs Growth: log(IWD / IWF)."""
    return _log_ratio(_p(cp, "IWD"), _p(cp, "IWF"))


# ---------------------------------------------------------------------------
# CREDIT / FINANCIAL CONDITIONS  (US_I1–I7)
# ---------------------------------------------------------------------------

def _calc_US_I1(mu, **_):
    """10Y–3M yield-curve spread (bps), direct from FRED T10Y3M."""
    return _to_weekly_friday(_get_col(mu, "T10Y3M"))


def _calc_US_I2(mu, **_):
    """US HY OAS spread (bps), direct from FRED BAMLH0A0HYM2."""
    return _to_weekly_friday(_get_col(mu, "BAMLH0A0HYM2"))


def _calc_US_I3(cp, **_):
    """Commodities vs Bonds: log(DBC / GOVT) — inflation vs deflation signal."""
    return _log_ratio(_p(cp, "DBC"), _p(cp, "GOVT"))


def _calc_US_I4(mu, **_):
    """US IG OAS spread (bps), direct from FRED BAMLC0A0CM."""
    return _to_weekly_friday(_get_col(mu, "BAMLC0A0CM"))


def _calc_US_I5(mu, **_):
    """HY–IG spread differential: BAMLH0A0HYM2 − BAMLC0A0CM."""
    return _arith_diff(
        _to_weekly_friday(_get_col(mu, "BAMLH0A0HYM2")),
        _to_weekly_friday(_get_col(mu, "BAMLC0A0CM")),
    )


def _calc_US_I6(mu, **_):
    """10Y–2Y yield curve: direct from FRED T10Y2Y."""
    return _to_weekly_friday(_get_col(mu, "T10Y2Y"))


def _calc_US_I7(mu, **_):
    """10Y breakeven inflation: direct from FRED T10YIE."""
    return _to_weekly_friday(_get_col(mu, "T10YIE"))


# ---------------------------------------------------------------------------
# RISK / VOLATILITY REGIME  (US_R1–R2)
# ---------------------------------------------------------------------------

def _calc_US_R1(cp, **_):
    """VIX term structure: ^VIX3M − ^VIX (bps; positive = contango = calm)."""
    return _arith_diff(_p(cp, "^VIX3M"), _p(cp, "^VIX"))


def _calc_US_R2(cp, **_):
    """Cross-asset vol: log(^MOVE / ^VIX) — bond vol relative to equity vol."""
    return _log_ratio(_p(cp, "^MOVE"), _p(cp, "^VIX"))


# ---------------------------------------------------------------------------
# REAL RATES  (US_RR1)
# ---------------------------------------------------------------------------

def _calc_US_RR1(mu, **_):
    """10Y TIPS real yield: direct from FRED DFII10."""
    return _to_weekly_friday(_get_col(mu, "DFII10"))


# ---------------------------------------------------------------------------
# FX / COMMODITIES  (US_FX1–FX2)
# ---------------------------------------------------------------------------

def _calc_US_FX1(cp, **_):
    """EM vs DXY: log(EEM_USD / DX-Y.NYB) — EM risk appetite vs dollar."""
    return _log_ratio(_p(cp, "EEM", usd=True), _p(cp, "DX-Y.NYB"))


def _calc_US_FX2(cp, **_):
    """Copper vs Gold: log(HG=F / GC=F) — industrial demand vs safe-haven."""
    return _log_ratio(_p(cp, "HG=F"), _p(cp, "GC=F"))


# ---------------------------------------------------------------------------
# MOMENTUM / TREND  (M1–M5)
# ---------------------------------------------------------------------------

def _calc_M1(cp, **_):
    """
    S&P 500 vs 40-week SMA momentum filter.
    Raw = log(SPY / SMA_40w); z-score drives regime.
    """
    spy = _to_weekly_friday(_p(cp, "SPY"))
    sma40 = spy.rolling(40, min_periods=20).mean()
    return _log_ratio(spy, sma40)


def _calc_M2(cp, **_):
    """
    Faber 5-asset TAA: count of assets above their 40-week SMA.
    Assets: SPY, EEM, DBC, GOVT, GC=F.  Raw = count (0–5).
    """
    assets = ["SPY", "EEM", "DBC", "GOVT", "GC=F"]
    scores = []
    for ticker in assets:
        px = _to_weekly_friday(_p(cp, ticker))
        sma = px.rolling(40, min_periods=20).mean()
        above = (px > sma).astype(float)
        scores.append(above)
    combined = pd.concat(scores, axis=1).sum(axis=1)
    # Align index to a common weekly spine
    combined = _to_weekly_friday(combined)
    return combined


def _calc_M3(cp, **_):
    """
    Dual momentum: log(SPY / EEM) 26-week momentum differential.
    Positive → US outperforming EM on a 6-month look-back.
    """
    spy = _to_weekly_friday(_p(cp, "SPY"))
    eem = _to_weekly_friday(_p(cp, "EEM", usd=True))
    spy_mom = spy / spy.shift(26) - 1
    eem_mom = eem / eem.shift(26) - 1
    return spy_mom.subtract(eem_mom).dropna()


def _calc_M4(cp, mu, **_):
    """
    HY credit trend + spread override.
    Raw = log(BAMLHYH0A0HYM2TRIV / 40wk SMA), overridden to -1 when
    HY OAS (BAMLH0A0HYM2) > 600 bps (stress flag).
    """
    hy_tr = _to_weekly_friday(_p(cp, "BAMLHYH0A0HYM2TRIV"))
    sma40 = hy_tr.rolling(40, min_periods=20).mean()
    raw = _log_ratio(hy_tr, sma40)
    # Spread override: if OAS > 600 bps treat as risk-off regardless of trend
    oas = _to_weekly_friday(_get_col(mu, "BAMLH0A0HYM2"))
    oas, raw = oas.align(raw, join="inner")
    raw = raw.where(oas <= 600, other=-1.0)
    return raw


def _calc_M5(cp, **_):
    """
    VIX moving-average cross: log(VIX_10w_SMA / VIX_30w_SMA).
    Negative (short MA < long MA) → vol falling → risk-on.
    """
    vix = _to_weekly_friday(_p(cp, "^VIX"))
    ma10 = vix.rolling(10, min_periods=5).mean()
    ma30 = vix.rolling(30, min_periods=15).mean()
    return _log_ratio(ma10, ma30)


# ---------------------------------------------------------------------------
# US MACRO FUNDAMENTALS  (US_LEI1, US_JOBS1, US_LAB1, US_GROWTH1,
#                          US_HOUS1, US_M2L1)
# ---------------------------------------------------------------------------

def _calc_US_LEI1(mu, **_):
    """
    Conference Board LEI 6-month annualised change: USSLIND.
    Raw = annualised % change over last 6 months (26 weekly periods).
    """
    lei = _to_weekly_friday(_get_col(mu, "USSLIND"))
    return _annualised_change(lei, periods=26)


def _calc_US_JOBS1(mu, **_):
    """Initial Claims YoY: IC4WSA year-on-year % change (inverted — rising = bad)."""
    ic = _to_weekly_friday(_get_col(mu, "IC4WSA"))
    return _yoy(ic)


def _calc_US_LAB1(mu, **_):
    """
    Labour market composite z-score.
    Components: UNRATE (inverted), PAYEMS YoY, IC4WSA YoY (inverted).
    Equal-weight average of the three rolling z-scores.
    """
    unrate  = _to_weekly_friday(_get_col(mu, "UNRATE"))
    payems  = _to_weekly_friday(_get_col(mu, "PAYEMS"))
    claims  = _to_weekly_friday(_get_col(mu, "IC4WSA"))

    z_unrate  = _rolling_zscore(unrate)   * -1   # invert: low = good
    z_payems  = _rolling_zscore(_yoy(payems))
    z_claims  = _rolling_zscore(_yoy(claims)) * -1  # invert: rising = bad

    composite = pd.concat([z_unrate, z_payems, z_claims], axis=1).mean(axis=1)
    return composite


def _calc_US_GROWTH1(mu, **_):
    """
    US Growth composite: equal-weight z-score of INDPRO YoY and RSXFS YoY.
    """
    indpro = _to_weekly_friday(_get_col(mu, "INDPRO"))
    rsxfs  = _to_weekly_friday(_get_col(mu, "RSXFS"))

    z_indpro = _rolling_zscore(_yoy(indpro))
    z_rsxfs  = _rolling_zscore(_yoy(rsxfs))

    composite = pd.concat([z_indpro, z_rsxfs], axis=1).mean(axis=1)
    return composite


def _calc_US_HOUS1(mu, **_):
    """Housing permits YoY: PERMIT year-on-year % change."""
    permit = _to_weekly_friday(_get_col(mu, "PERMIT"))
    return _yoy(permit)


def _calc_US_M2L1(mu, **_):
    """M2 liquidity YoY: M2SL year-on-year % change."""
    m2 = _to_weekly_friday(_get_col(mu, "M2SL"))
    return _yoy(m2)


# ---------------------------------------------------------------------------
# DISPATCHER — US & NEIGHBOURS
# ---------------------------------------------------------------------------

_US_CALCULATORS = {
    "US_G1":      _calc_US_G1,
    "US_G2":      _calc_US_G2,
    "US_G3":      _calc_US_G3,
    "US_G4":      _calc_US_G4,
    "US_I1":      _calc_US_I1,
    "US_I2":      _calc_US_I2,
    "US_I3":      _calc_US_I3,
    "US_I4":      _calc_US_I4,
    "US_I5":      _calc_US_I5,
    "US_I6":      _calc_US_I6,
    "US_I7":      _calc_US_I7,
    "US_R1":      _calc_US_R1,
    "US_R2":      _calc_US_R2,
    "US_RR1":     _calc_US_RR1,
    "US_FX1":     _calc_US_FX1,
    "US_FX2":     _calc_US_FX2,
    "M1":         _calc_M1,
    "M2":         _calc_M2,
    "M3":         _calc_M3,
    "M4":         _calc_M4,
    "M5":         _calc_M5,
    "US_LEI1":    _calc_US_LEI1,
    "US_JOBS1":   _calc_US_JOBS1,
    "US_LAB1":    _calc_US_LAB1,
    "US_GROWTH1": _calc_US_GROWTH1,
    "US_HOUS1":   _calc_US_HOUS1,
    "US_M2L1":    _calc_US_M2L1,
}


# ===========================================================================
# INDICATOR CALCULATORS — EUROPE  (8 indicators)
# ===========================================================================

# ---------------------------------------------------------------------------
# EU GROWTH / RISK APPETITE  (EU_G1–G3)
# ---------------------------------------------------------------------------

def _calc_EU_G1(cp, **_):
    """
    Euro Stoxx 50 vs FTSE 100: log(^STOXX50E / ^FTSE) — EU cyclical vs UK defensive.
    Both in local currency; ratio reflects relative risk appetite.
    """
    return _log_ratio(_p(cp, "^STOXX50E"), _p(cp, "^FTSE"))


def _calc_EU_G2(cp, **_):
    """
    STOXX 600 Cyclicals vs Defensives:
    log((Industrials_TR + Consumer_Disc_TR) / (Health_TR + Utilities_TR))
    STOXX 600 sector ETFs: EXH4.DE (Industrials), EXV3.DE (Consumer Disc),
                           EXV1.DE (Health Care), EXH9.DE (Utilities).
    """
    return _sum_log_ratio(
        [_p(cp, "EXH4.DE"), _p(cp, "EXV3.DE")],
        [_p(cp, "EXV1.DE"), _p(cp, "EXH9.DE")],
    )


def _calc_EU_G3(cp, **_):
    """
    FTSE 250 vs FTSE 100: log(^FTMC / ^FTSE) — UK mid/small vs large-cap.
    Proxy for domestic UK growth appetite.
    """
    return _log_ratio(_p(cp, "^FTMC"), _p(cp, "^FTSE"))


# ---------------------------------------------------------------------------
# EU FINANCIAL CONDITIONS  (EU_I1–I3)
# ---------------------------------------------------------------------------

def _calc_EU_I1(supp, **_):
    """
    Euro IG spread: Euro IG corporate yield minus ECB AAA govt yield.
    Fetched via fetch_ecb_euro_ig_spread() stored in supp['euro_ig_spread'].
    Falls back to FRED BAMLHE00EHYIOAS if ECB unavailable.
    """
    s = supp.get("euro_ig_spread")
    if s is None or s.empty:
        # Fallback: use BAMLHE00EHYIOAS (Euro HY) as rough proxy
        s = supp.get("BAMLHE00EHYIOAS", pd.Series(dtype=float))
    return _to_weekly_friday(s)


def _calc_EU_I2(supp, **_):
    """
    Euro HY OAS (bps): FRED BAMLHE00EHYIOAS — ICE BofA Euro High Yield OAS.
    """
    s = supp.get("BAMLHE00EHYIOAS", pd.Series(dtype=float))
    return _to_weekly_friday(s)


def _calc_EU_I3(cp, **_):
    """
    UK credit conditions: log(SLXX.L / IGLT.L) — UK IG Corp vs Gilt.
    Widening spread (SLXX underperforming) → tighter conditions.
    """
    return _log_ratio(_p(cp, "SLXX.L"), _p(cp, "IGLT.L"))


# ---------------------------------------------------------------------------
# EU RATES  (EU_R1)
# ---------------------------------------------------------------------------

def _calc_EU_R1(supp, **_):
    """
    Germany 10Y yield: FRED IRLTLT01DEM156N (monthly, forward-filled weekly).
    Raw = yield level in %.
    """
    s = supp.get("IRLTLT01DEM156N", pd.Series(dtype=float))
    return _to_weekly_friday(s)


# ---------------------------------------------------------------------------
# EU FX  (EU_FX1)
# ---------------------------------------------------------------------------

def _calc_EU_FX1(cp, **_):
    """
    EUR/USD level z-score.
    Raw = EURUSD=X spot rate; z-score driven by ZSCORE_WINDOW rolling window.
    """
    return _to_weekly_friday(_p(cp, "EURUSD=X"))


# ---------------------------------------------------------------------------
# DISPATCHER — EUROPE
# ---------------------------------------------------------------------------

_EU_CALCULATORS = {
    "EU_G1":  _calc_EU_G1,
    "EU_G2":  _calc_EU_G2,
    "EU_G3":  _calc_EU_G3,
    "EU_I1":  _calc_EU_I1,
    "EU_I2":  _calc_EU_I2,
    "EU_I3":  _calc_EU_I3,
    "EU_R1":  _calc_EU_R1,
    "EU_FX1": _calc_EU_FX1,
}


# ===========================================================================
# INDICATOR CALCULATORS — ASIA & REGIONAL  (15 indicators)
# ===========================================================================

# ---------------------------------------------------------------------------
# ASIA GROWTH / RISK APPETITE  (AS_G1–G3)
# ---------------------------------------------------------------------------

def _calc_AS_G1(cp, supp, **_):
    """
    China small vs large cap: log(ASHR / FXI).
    ASHR = CSI 300 ETF (large-cap proxy); FXI = iShares China Large-Cap ETF.
    Note: CSI 500 (000905.SS) is unavailable on yfinance; ASHR/FXI is the
    agreed small/large proxy.  FXI prices are in supp['fxi'].
    """
    ashr = _to_weekly_friday(_p(cp, "ASHR"))
    fxi  = supp.get("fxi", pd.Series(dtype=float))
    fxi  = _to_weekly_friday(fxi)
    return _log_ratio(ashr, fxi)


def _calc_AS_G2(cp, **_):
    """
    India mid vs large cap: log(^CRSMID / ^NSEI).
    ^CRSMID = Nifty Midcap 100; ^NSEI = Nifty 50.
    """
    return _log_ratio(_p(cp, "^CRSMID"), _p(cp, "^NSEI"))


def _calc_AS_G3(cp, **_):
    """
    Japan: TOPIX (^N225 proxy) — z-score of log returns used as risk gauge.
    Raw = log(000001.SS / URTH) i.e. Shanghai Comp vs World equity.
    Captures Chinese equity risk appetite relative to global.
    """
    return _log_ratio(_p(cp, "000001.SS"), _p(cp, "URTH", usd=True))


# ---------------------------------------------------------------------------
# ASIA FINANCIAL CONDITIONS  (AS_I1–I2)
# ---------------------------------------------------------------------------

def _calc_AS_I1(supp, **_):
    """
    China 10Y govt yield: FRED IRLTLT01CNM156N (monthly, forward-filled).
    Raw = yield level in %.
    """
    s = supp.get("IRLTLT01CNM156N", pd.Series(dtype=float))
    return _to_weekly_friday(s)


def _calc_AS_I2(supp, **_):
    """
    India 10Y govt yield: FRED IRLTLT01INM156N (monthly, forward-filled).
    Raw = yield level in %.
    """
    s = supp.get("IRLTLT01INM156N", pd.Series(dtype=float))
    return _to_weekly_friday(s)


# ---------------------------------------------------------------------------
# ASIA FX  (AS_FX1–FX2)
# ---------------------------------------------------------------------------

def _calc_AS_FX1(cp, **_):
    """
    CNY/USD spot rate (indirect quote — 1 USD = X CNY): CNY=X.
    Raw = CNY per USD; rising = CNY weakness.
    """
    return _to_weekly_friday(_p(cp, "CNY=X"))


def _calc_AS_FX2(cp, **_):
    """
    INR/USD spot rate (indirect quote — 1 USD = X INR): INR=X.
    Raw = INR per USD; rising = INR weakness.
    """
    return _to_weekly_friday(_p(cp, "INR=X"))


# ---------------------------------------------------------------------------
# ASIA COMMODITIES  (AS_C1–C2)
# ---------------------------------------------------------------------------

def _calc_AS_C1(supp, **_):
    """
    Iron ore price (USD/tonne): FRED PIORECRUSDM (monthly, forward-filled).
    Raw = price level; z-score reflects steel demand cycle.
    """
    s = supp.get("PIORECRUSDM", pd.Series(dtype=float))
    return _to_weekly_friday(s)


def _calc_AS_C2(cp, **_):
    """
    Copper/Gold ratio: log(HG=F / GC=F) — same as US_FX2, EM-demand lens.
    Captures Asian industrial cycle vs safe-haven demand.
    """
    return _log_ratio(_p(cp, "HG=F"), _p(cp, "GC=F"))


# ---------------------------------------------------------------------------
# REGIONAL CLI COMPOSITES  (REG_CLI1–CLI5)
# ---------------------------------------------------------------------------

def _calc_REG_CLI1(mi, **_):
    """
    US OECD CLI: USA_CLI from macro_intl_hist. Raw = CLI level.
    """
    return _to_weekly_friday(_get_col(mi, "USA_CLI"))


def _calc_REG_CLI2(mi, **_):
    """
    Eurozone CLI proxy: average of DEU_CLI and FRA_CLI.
    Note: EA19_CLI is absent from the OECD pull; DEU+FRA average is used.
    """
    deu = _to_weekly_friday(_get_col(mi, "DEU_CLI"))
    fra = _to_weekly_friday(_get_col(mi, "FRA_CLI"))
    combined = pd.concat([deu, fra], axis=1).mean(axis=1)
    return _to_weekly_friday(combined)


def _calc_REG_CLI3(mi, **_):
    """
    Japan OECD CLI: JPN_CLI from macro_intl_hist. Raw = CLI level.
    """
    return _to_weekly_friday(_get_col(mi, "JPN_CLI"))


def _calc_REG_CLI4(mi, **_):
    """
    China OECD CLI: CHN_CLI from macro_intl_hist. Raw = CLI level.
    """
    return _to_weekly_friday(_get_col(mi, "CHN_CLI"))


def _calc_REG_CLI5(mi, **_):
    """
    Global CLI composite: equal-weight average of USA, DEU, FRA, JPN, CHN CLIs.
    Broad leading indicator of global economic momentum.
    """
    cols = ["USA_CLI", "DEU_CLI", "FRA_CLI", "JPN_CLI", "CHN_CLI"]
    series_list = [_to_weekly_friday(_get_col(mi, c)) for c in cols]
    combined = pd.concat(series_list, axis=1).mean(axis=1)
    return _to_weekly_friday(combined)


# ---------------------------------------------------------------------------
# DISPATCHER — ASIA & REGIONAL
# ---------------------------------------------------------------------------

_ASIA_REGIONAL_CALCULATORS = {
    "AS_G1":    _calc_AS_G1,
    "AS_G2":    _calc_AS_G2,
    "AS_G3":    _calc_AS_G3,
    "AS_I1":    _calc_AS_I1,
    "AS_I2":    _calc_AS_I2,
    "AS_FX1":   _calc_AS_FX1,
    "AS_FX2":   _calc_AS_FX2,
    "AS_C1":    _calc_AS_C1,
    "AS_C2":    _calc_AS_C2,
    "REG_CLI1": _calc_REG_CLI1,
    "REG_CLI2": _calc_REG_CLI2,
    "REG_CLI3": _calc_REG_CLI3,
    "REG_CLI4": _calc_REG_CLI4,
    "REG_CLI5": _calc_REG_CLI5,
}

# Master dispatcher — union of all regional dicts
_ALL_CALCULATORS = {
    **_US_CALCULATORS,
    **_EU_CALCULATORS,
    **_ASIA_REGIONAL_CALCULATORS,
}


# ===========================================================================
# MAIN COMPUTATION ENGINE
# ===========================================================================

def compute_all_indicators(cp, mu, mi, supp) -> dict:
    """
    Run every indicator calculator and return a dict:
        { ind_id: pd.DataFrame(columns=['raw','zscore','regime']) }

    One try/except per indicator so a single failure never kills the run.

    Args:
        cp   : comp_hist DataFrame   (weekly prices)
        mu   : macro_us DataFrame    (weekly FRED US series)
        mi   : macro_intl DataFrame  (weekly CLI + international series)
        supp : dict of supplemental Series from FRED / ECB / yfinance

    Returns:
        dict mapping indicator id → DataFrame with columns [raw, zscore, regime]
    """
    results = {}
    for ind_id in ALL_INDICATOR_IDS:
        calc_fn = _ALL_CALCULATORS.get(ind_id)
        if calc_fn is None:
            print(f"  [compute] WARNING: no calculator for {ind_id} — skipping")
            continue
        try:
            raw_series = calc_fn(cp=cp, mu=mu, mi=mi, supp=supp)
            df = make_result(raw_series, ind_id)
            results[ind_id] = df
            last_date = df.index[-1].date() if not df.empty else "n/a"
            last_raw  = round(df["raw"].iloc[-1], 4) if not df.empty else "n/a"
            last_z    = round(df["zscore"].iloc[-1], 2) if not df.empty else "n/a"
            last_reg  = df["regime"].iloc[-1] if not df.empty else "n/a"
            print(f"  [compute] {ind_id}: raw={last_raw}  z={last_z}  "
                  f"regime='{last_reg}'  ({last_date})")
        except Exception as exc:
            print(f"  [compute] ERROR in {ind_id}: {exc}")
            results[ind_id] = pd.DataFrame(columns=["raw", "zscore", "regime"])
    return results


# ===========================================================================
# OUTPUT BUILDERS
# ===========================================================================

def build_snapshot_df(results: dict) -> pd.DataFrame:
    """
    Build the snapshot DataFrame (one row per indicator, latest values only).

    Columns:
        id, region_block, category, last_date,
        raw, zscore, regime, formula_note

    Rows are in ALL_INDICATOR_IDS order (same as macro_indicator_library.csv).
    """
    rows = []
    for ind_id in ALL_INDICATOR_IDS:
        meta = INDICATOR_META.get(ind_id, ("", "", ""))
        region_block, category, formula_note = meta
        df = results.get(ind_id, pd.DataFrame(columns=["raw", "zscore", "regime"]))
        if df.empty or df["raw"].dropna().empty:
            rows.append({
                "id":           ind_id,
                "region_block": region_block,
                "category":     category,
                "last_date":    "",
                "raw":          "",
                "zscore":       "",
                "regime":       "Insufficient Data",
                "formula_note": formula_note,
            })
        else:
            last = df.dropna(subset=["raw"]).iloc[-1]
            rows.append({
                "id":           ind_id,
                "region_block": region_block,
                "category":     category,
                "last_date":    str(last.name.date()),
                "raw":          round(last["raw"],    6),
                "zscore":       round(last["zscore"], 4) if pd.notna(last["zscore"]) else "",
                "regime":       last["regime"],
                "formula_note": formula_note,
            })
    return pd.DataFrame(rows)


def build_hist_df(results: dict) -> pd.DataFrame:
    """
    Build the history DataFrame: weekly dates × (50 × 3) = 150 columns.

    Column naming convention: {id}_raw, {id}_zscore, {id}_regime
    Index: DatetimeIndex of weekly Fridays.
    """
    frames = {}
    for ind_id in ALL_INDICATOR_IDS:
        df = results.get(ind_id, pd.DataFrame(columns=["raw", "zscore", "regime"]))
        if df.empty:
            continue
        frames[f"{ind_id}_raw"]    = df["raw"]
        frames[f"{ind_id}_zscore"] = df["zscore"]
        frames[f"{ind_id}_regime"] = df["regime"]

    if not frames:
        return pd.DataFrame()

    hist = pd.concat(frames, axis=1)
    hist.index.name = "Date"
    hist = hist.sort_index()
    return hist


# ===========================================================================
# GOOGLE SHEETS PUSH
# ===========================================================================

def push_macro_to_google_sheets(df_snapshot: pd.DataFrame, df_hist: pd.DataFrame):
    """
    Push macro_market snapshot and macro_market_hist to Google Sheets.

    Credentials from GOOGLE_CREDENTIALS env var (service account JSON string).
    Tabs 'macro_market' and 'macro_market_hist' are created if absent; no other
    tabs are touched.

    Mirrors the push_to_google_sheets() pattern in fetch_data.py exactly.
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
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    service = build("sheets", "v4", credentials=creds)
    sheets  = service.spreadsheets()

    def _sv(v):
        """Serialise one cell value for the Sheets API."""
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

    def df_to_values(df: pd.DataFrame) -> list:
        """Convert DataFrame to list-of-lists (header + rows) for the API."""
        header = df.columns.tolist()
        rows   = [[_sv(v) for v in row] for row in df.itertuples(index=False)]
        return [header] + rows

    def ensure_tab_exists(tab_name: str):
        meta     = sheets.get(spreadsheetId=SHEET_ID).execute()
        existing = {s["properties"]["title"] for s in meta.get("sheets", [])}
        if tab_name not in existing:
            sheets.batchUpdate(
                spreadsheetId=SHEET_ID,
                body={"requests": [{"addSheet": {"properties": {"title": tab_name}}}]},
            ).execute()
            print(f"  Created new tab '{tab_name}'")

    def write_sheet(tab_name: str, df: pd.DataFrame):
        """Ensure tab exists, clear it, then write the DataFrame."""
        ensure_tab_exists(tab_name)
        sheets.values().clear(
            spreadsheetId=SHEET_ID,
            range=f"{tab_name}!A1:ZZ10000",
        ).execute()
        values = df_to_values(df)
        sheets.values().update(
            spreadsheetId=SHEET_ID,
            range=f"{tab_name}!A1",
            valueInputOption="USER_ENTERED",
            body={"values": values},
        ).execute()
        print(f"  [sheets] Written {len(values)-1} rows to '{tab_name}'")

    write_sheet(SNAPSHOT_TAB, df_snapshot)
    write_sheet(HIST_TAB,     df_hist.reset_index())  # include Date column


# ===========================================================================
# PHASE E ENTRY POINT
# ===========================================================================

def run_phase_e():
    """
    Phase E — Macro-Market Indicators.

    Orchestrates the full pipeline:
      1. Load input hist CSVs (market + FRED US + international CLI)
      2. Fetch supplemental data (FRED, ECB, yfinance)
      3. Compute all 50 indicators
      4. Build snapshot and history DataFrames
      5. Save to CSV files
      6. Push to Google Sheets
    """
    print("\n=== Phase E: Macro-Market Indicators ===")

    # ------------------------------------------------------------------
    # 1. Load input files
    # ------------------------------------------------------------------
    print("  Loading input CSVs …")
    cp = load_comp_hist()
    mu = load_macro_us_hist()
    mi = load_macro_intl_hist()

    # ------------------------------------------------------------------
    # 2. Fetch supplemental data
    # ------------------------------------------------------------------
    print("  Fetching supplemental FRED series …")
    supp = fetch_supplemental_fred()

    print("  Fetching Euro IG spread (ECB / FRED fallback) …")
    supp["euro_ig_spread"] = fetch_ecb_euro_ig_spread()

    print("  Fetching FXI prices (yfinance) …")
    supp["fxi"] = fetch_fxi_prices()

    # ------------------------------------------------------------------
    # 3. Compute all indicators
    # ------------------------------------------------------------------
    print("  Computing indicators …")
    results = compute_all_indicators(cp, mu, mi, supp)

    # ------------------------------------------------------------------
    # 4. Build output DataFrames
    # ------------------------------------------------------------------
    print("  Building output frames …")
    df_snapshot = build_snapshot_df(results)
    df_hist     = build_hist_df(results)

    print(f"  Snapshot: {df_snapshot.shape[0]} indicators")
    print(f"  History : {df_hist.shape[0]} weekly rows × {df_hist.shape[1]} cols")

    # ------------------------------------------------------------------
    # 5. Save to CSV
    # ------------------------------------------------------------------
    os.makedirs("data", exist_ok=True)

    df_snapshot.to_csv(SNAPSHOT_CSV, index=False)
    print(f"  Saved {SNAPSHOT_CSV}")

    df_hist.reset_index().to_csv(HIST_CSV, index=False)
    print(f"  Saved {HIST_CSV}")

    # ------------------------------------------------------------------
    # 6. Push to Google Sheets
    # ------------------------------------------------------------------
    print("  Pushing to Google Sheets …")
    try:
        push_macro_to_google_sheets(df_snapshot, df_hist)
    except Exception as sheets_err:
        print(f"  WARNING: Sheets push failed — {sheets_err}")

    print("=== Phase E complete ===\n")


# ===========================================================================
# STANDALONE EXECUTION
# ===========================================================================

if __name__ == "__main__":
    run_phase_e()
