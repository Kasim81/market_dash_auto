"""
compute_macro_market.py
=======================
Phase E — Macro-Market Indicators
Market Dashboard Expansion

WHAT THIS MODULE DOES
---------------------
Computes 50 macro-market composite indicators defined in
data/macro_indicator_library.csv as weekly time series.

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

SUPPLEMENTAL DATA FETCHED HERE (not in the unified macro_economic_hist)
-----------------------------------------------------------------------
  ECB  : Euro area AAA govt 10Y yield (data-api.ecb.europa.eu YC dataset).
         Paired with a Euro IG corporate yield to compute EU_Cr1's IG
         spread.  The corporate-yield half is currently unsourced (FRED
         BAMLEC0A0RMEY 400s; see forward_plan.md §1 Known Data Gaps), so
         EU_Cr1 returns n/a until a free source is wired in.  EU_Cr2
         (Euro HY spread) is a separate indicator reading BAMLHE00EHYIOAS
         from the unified hist — there is no HY-for-IG fallback.
  yfinance: FXI (iShares China Large-Cap ETF) for AS_G1 denominator.

  All other FRED, OECD, WB, IMF, DB.nomics and ifo series flow through the
  unified macro_economic_hist via fetch_macro_economic.py — the calculators
  read them via _get_col(mu, "<col>") (see §0 of forward_plan.md).

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

from library_utils import write_hist_with_archive, load_hist_with_archive

# --- C7: calculators split into the calculators/ package ---
from calculators.common import (
    _to_weekly_friday, _rolling_zscore, _get_col, _p, _log_ratio,
    _arith_diff, _sum_log_ratio, _yoy, _taylor_gap,
    ZSCORE_WINDOW, ZSCORE_MIN_PERIODS, _ALIGN_FFILL_LIMIT,
)
from calculators.us import *        # noqa: F401,F403
from calculators.europe import *    # noqa: F401,F403
from calculators.uk import *        # noqa: F401,F403
from calculators.japan import *     # noqa: F401,F403
from calculators.asia import *      # noqa: F401,F403
from calculators.fx import *        # noqa: F401,F403
from calculators.monetary import *  # noqa: F401,F403
from calculators.global_ import *   # noqa: F401,F403

# ---------------------------------------------------------------------------
# CONFIG — credentials, sheet IDs, output paths
# ---------------------------------------------------------------------------

GOOGLE_CREDENTIALS_JSON  = os.environ.get("GOOGLE_CREDENTIALS", "")

SHEET_ID     = "12nKIUGHz5euDbNQPDTVECsJBNwrceRF1ymsQrIe4_ac"
SNAPSHOT_TAB = "macro_market"
HIST_TAB     = "macro_market_hist"
SNAPSHOT_CSV = "data/macro_market.csv"
HIST_CSV     = "data/macro_market_hist.csv"
# §3.14 — month-end-sampled view of the weekly 156-week z-score hist for the
# regime-AA Phase 3 Layer-1 monthly engine. Same column schema as macro_market_hist
# (<id>_raw / _zscore / _regime / _fwd_regime), but the index is month-end dates
# and each cell is the last weekly Friday value within that month. The
# underlying ZSCORE_WINDOW stays 156 weeks — this is sampling, not a new
# z-score definition (per forward_plan.md §3.14 corrections memo).
MONTHLY_HIST_CSV = "data/macro_market_monthly_hist.csv"

# Input CSV paths (produced by earlier phases)
COMP_HIST_CSV       = "data/market_data_comp_hist.csv"
MACRO_ECONOMIC_HIST_CSV = "data/macro_economic_hist.csv"

# ECB Data Portal REST API (replaced sdw-wsrest after Sept 2023 retirement).
# Path prefix /service/data/<dataflow>/<key> and format=csvdata are unchanged.
ECB_BASE_URL       = "https://data-api.ecb.europa.eu/service/data"
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

# ---------------------------------------------------------------------------
# INDICATOR METADATA — loaded from data/macro_indicator_library.csv
# ---------------------------------------------------------------------------
IND_LIB_CSV = os.path.join(os.path.dirname(__file__), "data", "macro_indicator_library.csv")


def _load_indicator_library():
    """Load indicator metadata from macro_indicator_library.csv.

    Returns:
        ind_meta : dict  {id: (group, sub_group, category, formula, concept, subcategory)}
        all_ids  : list  ordered indicator IDs (CSV row order)
        naturally_leading : frozenset  IDs flagged as naturally leading
    """
    lib = pd.read_csv(IND_LIB_CSV)
    ind_meta = {}
    all_ids = []
    leading = set()
    for _, row in lib.iterrows():
        ind_id = str(row.get("id", "")).strip()
        if not ind_id:
            continue
        group       = str(row.get("group", "")).strip()
        sub_group   = str(row.get("sub_group", "")).strip()
        category    = str(row.get("category", "")).strip()
        formula     = str(row.get("formula_using_library_names", "")).strip()
        concept     = str(row.get("concept", "")).strip()
        subcategory = str(row.get("subcategory", "")).strip()
        ind_meta[ind_id] = (group, sub_group, category, formula, concept, subcategory)
        all_ids.append(ind_id)
        if str(row.get("naturally_leading", "")).strip().upper() == "TRUE":
            leading.add(ind_id)
    return ind_meta, all_ids, frozenset(leading)


INDICATOR_META, ALL_INDICATOR_IDS, NATURALLY_LEADING = _load_indicator_library()


# ===========================================================================
# SUPPLEMENTAL DATA FETCHERS
#
# Phase E no longer fetches FRED series directly — every FRED ID lives in
# data/macro_library_fred.csv and reaches the calculators via `mu` (the
# unified macro_economic_hist).  Only ECB SDW (deeply nested SDMX key) and
# yfinance FXI remain here as supplementals, both keyed in `supp`.
# ===========================================================================


def fetch_ecb_euro_ig_spread(mu: pd.DataFrame) -> pd.Series:
    """
    Compute the Euro IG corporate bond spread.

    Strategy (in order):
      1. Fetch ECB AAA euro-area govt 10Y yield (YC dataset — well-documented).
         This series is too deeply nested to live in macro_library_fred.csv as
         a single ID; the SDMX call happens here.
      2. Read the Euro IG corporate effective yield from the unified
         macro_economic_hist via `mu`.  This source is currently unwired —
         FRED `BAMLEC0A0RMEY` was probed and 400s on every call, so the row
         was removed (see forward_plan.md §1 Known Data Gaps).  When a free
         historical Euro IG corporate yield source is identified, register
         it in `data/macro_library_*.csv` (per §0) and update the column
         name read below.
      3. Compute spread = corp_yield - govt_yield.

    On failure return empty — _calc_EU_Cr1 returns NaN (no HY fallback;
    Euro HY is its own indicator, EU_Cr2).

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
                # ECB YC dataset returns daily TIME_PERIOD (YYYY-MM-DD); let
                # pandas infer to handle either daily or monthly cadence.
                df_ecb["_dt"] = pd.to_datetime(
                    df_ecb["TIME_PERIOD"], errors="coerce"
                )
                df_ecb = df_ecb.dropna(subset=["_dt", "OBS_VALUE"])
                govt_yield = pd.Series(
                    pd.to_numeric(df_ecb["OBS_VALUE"], errors="coerce").values,
                    index=df_ecb["_dt"].values,
                    name="ECB_EUR_GOVT_10Y",
                ).dropna().sort_index()
                print(f"  [ECB] AAA euro govt yield: {len(govt_yield)} obs")
        else:
            print(f"  [ECB] YC dataset HTTP {resp.status_code} — skipping govt yield")
    except Exception as exc:
        print(f"  [ECB] YC fetch error: {exc}")
        time.sleep(ECB_REQUEST_DELAY)

    # --- Step 2: Euro IG corporate effective yield via the unified hist ---
    # No source currently registered — see forward_plan.md §1 Known Data Gaps.
    # The lookup below is a placeholder ready to receive the future column
    # name once a free historical Euro IG corporate yield is wired in.
    corp_yield = pd.Series(dtype=float)
    if not govt_yield.empty:
        # corp_yield = _get_col(mu, "<future_eu_ig_corp_yield_col>").dropna()
        pass

    # --- Step 3: Compute spread if both are available ---
    if not govt_yield.empty and not corp_yield.empty:
        govt_m = govt_yield.resample("ME").last()
        corp_m = corp_yield.resample("ME").last()
        spread = (corp_m - govt_m).dropna()
        spread.name = "EU_I1_spread"
        print(f"  [ECB] EU_I1 IG spread computed: {len(spread)} monthly obs")
        return spread

    # On failure return empty — _calc_EU_Cr1 returns NaN (no HY fallback;
    # Euro HY is its own indicator, EU_Cr2).
    print("  [ECB] EU_I1 spread unavailable — EU_Cr1 will return n/a "
          "(corp-yield source unwired; see forward_plan.md §1 Known Data Gaps)")
    return pd.Series(dtype=float, name="EU_I1_spread")


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


# Cross-series alignment fill cap (weekly rows, ~one quarter). Aligning
# mixed-cadence legs on a union index needs some forward-fill, but an
# unbounded one lets a dead leg extend to a live leg's end — the same
# fabrication the hist writer's bounded fill removes (2026-07-08).


def _annualised_change(series: pd.Series, periods: int = 6) -> pd.Series:
    """
    Annualised percentage change over `periods` months of a monthly series.
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
    Given a raw indicator series, compute z-score, regime, and forward regime,
    returning a 4-column DataFrame: raw | zscore | regime | fwd_regime,
    indexed by weekly Friday dates.

    fwd_regime encodes the 1-2 month forward trajectory:
      - 'improving / stable / deteriorating' based on 8-week z-score slope
      - '[leading]' suffix for naturally-leading indicators
    """
    if raw is None or (isinstance(raw, pd.Series) and raw.empty):
        return pd.DataFrame(columns=["raw", "zscore", "regime", "fwd_regime"])
    raw_w = _to_weekly_friday(raw)
    raw_w = raw_w[raw_w.index >= HIST_START]
    z           = _rolling_zscore(raw_w)
    z_slope     = z.diff(8) / 8          # weekly rate of z-score change over 8 weeks
    regime_vals     = []
    fwd_regime_vals = []
    for rv, zv, sv in zip(raw_w, z, z_slope):
        try:
            regime_vals.append(_assign_regime(ind_id, float(rv), float(zv)))
        except Exception:
            regime_vals.append("n/a")
        try:
            fwd_regime_vals.append(_assign_fwd_regime(ind_id, float(sv)))
        except Exception:
            fwd_regime_vals.append("n/a")
    return pd.DataFrame(
        {"raw": raw_w, "zscore": z, "regime": regime_vals, "fwd_regime": fwd_regime_vals},
        index=raw_w.index,
    )


# ===========================================================================
# REGIME CLASSIFICATION
# ===========================================================================
# Each entry is a lambda(raw_value, zscore) → regime_string.
# raw and zscore may be NaN — the lambda must guard against this.
# Thresholds follow data/macro_indicator_library.csv.
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


def _infl_regime(r, z):
    """Target-relative inflation regime on the raw YoY % level (most G10
    central banks target ~2%). Shared by US/UK/EU/JP inflation composites."""
    if np.isnan(r):
        return "n/a"
    if r > 4:
        return "high-inflation"
    if r > 2.5:
        return "above-target"
    if r >= 1.5:
        return "on-target"
    if r >= 0:
        return "below-target"
    return "deflation"


REGIME_RULES = {
    # US Growth
    "US_G1":  lambda r, z: _r(r, z,  1, -1, "pro-growth",       "defensive"),
    "US_G2":  lambda r, z: _r(r, z,  1, -1, "risk-on",          "late-cycle"),
    "US_G3": lambda r, z: _r(r, z,  1, -1, "risk-on",          "defensive"),
    "US_EQ_F3":  lambda r, z: _r(r, z,  1, -1, "small-cap-lead",   "large-cap-safety"),
    "US_EQ_F4": lambda r, z: _r(r, z,  1, -1, "small-cap-lead",   "large-cap-safety"),
    "US_EQ_F1":  lambda r, z: _r(r, z,  1, -1, "value-regime",     "growth-regime", "mixed"),
    "US_EQ_F2": lambda r, z: _r(r, z,  1, -1, "value-regime",     "growth-regime", "mixed"),
    # US Rates & Credit — some use level-based rules combined with z-score
    "US_R1":  lambda r, z: (
        "recession-watch" if (not np.isnan(r) and r < 0)
        else _r(r, z, 1, -1, "early-cycle", "late-cycle", "mid-cycle")
    ),
    "US_Cr2":  lambda r, z: (
        "opportunity" if (not np.isnan(r) and r > 800) or (not np.isnan(z) and z > 2)
        else ("stress" if not np.isnan(z) and z > 1 and not np.isnan(r) and r > 500
              else ("frothy" if not np.isnan(r) and r < 300 and not np.isnan(z) and z < -1
                    else ("complacent" if not np.isnan(r) and r < 400 and not np.isnan(z) and z < -0.5
                          else "normal")))
    ),
    "GL_CA_I1":  lambda r, z: _r(r, z,  1, -1, "reflation",        "growth-scare",  "balanced"),
    "US_Cr1":  lambda r, z: (
        "IG-stress" if (not np.isnan(r) and r > 200) or (not np.isnan(z) and z > 1.5)
        else ("frothy" if not np.isnan(z) and z < -1 else "normal")
    ),
    "US_Cr3":  lambda r, z: _r(r, z,  1, -1, "quality-spread",   "complacent"),
    "US_R2":  lambda r, z: (
        "inverted" if (not np.isnan(r) and r < 0)
        else ("steep" if not np.isnan(r) and r > 0.5 and not np.isnan(z) and z > 1
              else ("flat" if not np.isnan(z) and z < -1 else "normal"))
    ),
    "US_R3": lambda r, z: (
        "inverted" if (not np.isnan(r) and r < 0)
        else ("steep" if not np.isnan(r) and r > 0.5 and not np.isnan(z) and z > 1
              else ("flat" if not np.isnan(z) and z < -1 else "normal"))
    ),
    "US_R4":  lambda r, z: _r(r, z,  1, -1, "high-inflation-exp", "disinflation"),
    "US_CA_G1":  lambda r, z: _r(r, z,  1, -1, "risk-on",          "risk-off"),
    "US_Cr4": lambda r, z: _r(r, z,  1, -1, "credit-appetite",  "flight-to-quality"),
    # Volatility
    "US_V1":  lambda r, z: (
        "stress" if not np.isnan(r) and r < 0
        else ("complacency" if not np.isnan(z) and z < -1 else "normal")
    ),
    "US_V2":  lambda r, z: _r(r, z,  1, -1, "macro-uncertainty", "calm"),
    # Real rates / FX
    "US_R5": lambda r, z: _r(r, z,  1, -1, "high-real-rates",  "low-real-rates"),
    "FX_CMD2": lambda r, z: _r(r, z,  1, -1, "weak-USD",         "strong-USD"),
    "FX_CMD1": lambda r, z: _r(r, z,  1, -1, "global-growth",    "recession-watch"),
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
    "US_JOBS1":  lambda r, z: _r(r, z,  1, -1, "labour-deteriorating", "overheating", "stable"),
    "US_JOBS3":   lambda r, z: _r(r, z,  1, -1, "strong-labour",        "weak-labour",  "mid-cycle"),
    "US_G6":lambda r, z: _r(r, z,  1, -1, "strong-growth",        "weak-growth"),
    "US_HOUS1":  lambda r, z: _r(r, z,  1, -1, "housing-expanding",    "housing-contracting"),
    "US_M2":   lambda r, z: _r(r, z,  1, -1, "abundant-liquidity",   "tight-liquidity"),
    "US_G5":     lambda r, z: _r(r, z,  1, -1, "tech-led",             "defensive-rotation"),
    "US_G4":     lambda r, z: _r(r, z,  1, -1, "broad-rally",          "narrow-concentrated"),
    "US_ISM1":   lambda r, z: (
        "expansion"   if not np.isnan(r) and r > 52
        else ("contraction" if not np.isnan(r) and r < 48 else "neutral")
    ),
    "US_ISM2":   lambda r, z: (
        "orders-outpacing"    if not np.isnan(r) and r > 2
        else ("inventory-overhang" if not np.isnan(r) and r < -2 else "balanced")
    ),
    "US_R6":    lambda r, z: _r(r, z,  1, -1, "mortgage-stress",      "housing-easy"),
    "US_JOBS2":   lambda r, z: _r(r, z,  1, -1, "labour-tight",         "labour-slack"),
    # Europe
    "EU_G3":  lambda r, z: _r(r, z,  1, -1, "pro-growth-EU",    "defensive-EU"),
    "UK_G1":  lambda r, z: _r(r, z,  1, -1, "UK-domestic-strong","global-preferred"),
    "EU_G2":  lambda r, z: _r(r, z,  1, -1, "EU-outperform",    "US-dominance"),
    "EU_Cr1":  lambda r, z: _r(r, z,  1, -1, "EU-credit-tight",  "EU-easy"),
    "EU_Cr2":  lambda r, z: _r(r, z,  1, -1, "EU-HY-stress",     "EU-HY-easy"),
    "UK_R2":  lambda r, z: _r(r, z,  1, -1, "high-UK-infl-exp", "disinflation"),
    "UK_R1":  lambda r, z: _r(r, z,  1, -1, "UK-premium",       "EU-stress"),
    "UK_Cr1":  lambda r, z: _r(r, z,  1, -1, "credit-appetite",  "flight-to-quality"),
    "EU_G4": lambda r, z: _r(r, z,  1, -1, "EU-macro-friendly","EU-strain"),
    "EU_R1":  lambda r, z: (
        "peripheral-stress" if (not np.isnan(r) and r > 2.5) or (not np.isnan(z) and z > 1.5)
        else ("compressed" if not np.isnan(z) and z < -1 else "normal")
    ),
    "EU_G1":  lambda r, z: _r(r, z,  1, -1, "eurozone-outperform", "eurozone-underperform"),
    # Japan
    "JP_G1":  lambda r, z: _r(r, z,  1, -1, "japan-outperform",    "japan-underperform"),
    "FX_2": lambda r, z: (
        "carry-unwind" if not np.isnan(z) and z < -1
        else ("carry-on" if not np.isnan(z) and z > 0.5 else "neutral")
    ),
    # Asia
    "AS_CN_G3":  lambda r, z: _r(r, z,  1, -1, "mid-cap-lead",     "large-cap-safety"),
    "AS_CN_G2":  lambda r, z: _r(r, z,  1, -1, "China-outperform", "China-cautious"),
    "AS_IN_G1":  lambda r, z: _r(r, z,  1, -1, "India-domestic-strong","large-cap-safety"),
    "AS_CN_R1":  lambda r, z: _r(r, z,  1, -1, "China-bonds-outperform","China-underperform"),
    "AS_IN_R1":  lambda r, z: _r(r, z,  1, -1, "India-carry-attractive","India-underperform"),
    "FX_CN1": lambda r, z: _r(r, z,  1, -1, "CNY-strengthening", "CNY-weakening"),
    "FX_1": lambda r, z: _r(r, z,  1, -1, "INR-strengthening", "INR-weakening"),
    "FX_EM1": lambda r, z: _r(r, z,  1, -1, "EMFX-strengthening", "EMFX-weakening"),
    "FX_CMD5":  lambda r, z: _r(r, z,  1, -1, "China-infra-optimism","China-demand-disappoint"),
    "FX_CMD4":  lambda r, z: _r(r, z,  1, -1, "China-commodity-lead","global-commodity-lead"),
    "AS_CN_G1":  lambda r, z: _r(r, z,  1, -1, "China-outperform-EM", "China-underperform-EM"),
    # Regional CLI
    "GL_CLI1": lambda r, z: _r(r, z,  1, -1, "US-leads-EU",    "EU-leads-US"),
    "GL_CLI2": lambda r, z: _r(r, z,  1, -1, "US-leads-China", "China-leads-US"),
    "EU_CLI1": lambda r, z: _r(r, z,  1, -1, "EU-above-trend", "EU-below-trend",  "near-trend"),
    "AS_CLI1": lambda r, z: _r(r, z,  1, -1, "Asia-above-trend","Asia-below-trend","near-trend"),
    # Standalone country CLIs (OECD amplitude-adjusted, long-run avg = 100)
    "US_CLI1": lambda r, z: _r(r, z,  1, -1, "US-above-trend",        "US-below-trend",        "near-trend"),
    "CA_CLI1": lambda r, z: _r(r, z,  1, -1, "Canada-above-trend",    "Canada-below-trend",    "near-trend"),
    "DE_CLI1": lambda r, z: _r(r, z,  1, -1, "Germany-above-trend",   "Germany-below-trend",   "near-trend"),
    "FR_CLI1": lambda r, z: _r(r, z,  1, -1, "France-above-trend",    "France-below-trend",    "near-trend"),
    "UK_CLI1": lambda r, z: _r(r, z,  1, -1, "UK-above-trend",        "UK-below-trend",        "near-trend"),
    "IT_CLI1": lambda r, z: _r(r, z,  1, -1, "Italy-above-trend",     "Italy-below-trend",     "near-trend"),
    "JP_CLI1": lambda r, z: _r(r, z,  1, -1, "Japan-above-trend",     "Japan-below-trend",     "near-trend"),
    "CN_CLI1": lambda r, z: _r(r, z,  1, -1, "China-above-trend",     "China-below-trend",     "near-trend"),
    "AU_CLI1": lambda r, z: _r(r, z,  1, -1, "Australia-above-trend", "Australia-below-trend", "near-trend"),
    # REG_CLI5 uses raw breadth value, not z-score
    "GL_CLI5": lambda r, z: (
        "broad-expansion" if not np.isnan(r) and r >= 0.7
        else ("contracting" if not np.isnan(r) and r < 0.4 else "mixed")
    ),
    # Global multi-asset & commodity
    "GL_G2": lambda r, z: _r(r, z,  1, -1, "risk-on",            "risk-off"),
    "GL_G1":   lambda r, z: _r(r, z,  1, -1, "em-outperform",      "dm-outperform"),
    "FX_CMD6": lambda r, z: _r(r, z,  1, -1, "commodity-bull",     "commodity-bear"),
    "FX_CMD3": lambda r, z: _r(r, z,  1, -1, "growth-inflation",   "deflation-risk"),
    # Phase D — Business Survey indicators
    "US_PMI1": lambda r, z: (
        "expansion"   if not np.isnan(r) and r > 52
        else ("contraction" if not np.isnan(r) and r < 48 else "neutral")
    ),
    "US_SVC1": lambda r, z: (
        "expansion"   if not np.isnan(r) and r > 52
        else ("contraction" if not np.isnan(r) and r < 48 else "neutral")
    ),
    "EU_PMI1": lambda r, z: (
        "expansion"   if not np.isnan(r) and r > 52
        else ("contraction" if not np.isnan(r) and r < 48 else "neutral")
    ),
    "EU_PMI2": lambda r, z: (
        "expansion"   if not np.isnan(r) and r > 52
        else ("contraction" if not np.isnan(r) and r < 48 else "neutral")
    ),
    "EU_ESI1": lambda r, z: _r(r, z,  1, -1, "above-avg-sentiment","below-avg-sentiment"),
    "DE_ZEW1": lambda r, z: _r(r, z,  1, -1, "optimistic",         "pessimistic"),
    "DE_IFO1": lambda r, z: _r(r, z,  1, -1, "above-avg-climate",  "below-avg-climate"),
    "UK_PMI1": lambda r, z: (
        "expansion"   if not np.isnan(r) and r > 52
        else ("contraction" if not np.isnan(r) and r < 48 else "neutral")
    ),
    "JP_PMI1": lambda r, z: (
        "expansion"   if not np.isnan(r) and r > 52
        else ("contraction" if not np.isnan(r) and r < 48 else "neutral")
    ),
    "CN_PMI1": lambda r, z: (
        "expansion"   if not np.isnan(r) and r > 50.5
        else ("contraction" if not np.isnan(r) and r < 49.5 else "neutral")
    ),
    "CN_PMI2": lambda r, z: (
        "expansion"   if not np.isnan(r) and r > 51
        else ("contraction" if not np.isnan(r) and r < 49 else "neutral")
    ),
    "GL_PMI1": lambda r, z: (
        "global-expansion" if not np.isnan(r) and r > 51
        else ("global-contraction" if not np.isnan(r) and r < 49 else "neutral")
    ),
    # Long-run gold price (LBMA PM fix, USD/oz). Z-scored on 156w window —
    # high z = safe-haven / inflation hedge bid; low z = risk-on / disinflation.
    "GLOBAL_GOLD1": lambda r, z: _r(r, z, 1, -1, "safe-haven-bid", "risk-on-gold"),
    # §3.1.2 Stage E — BoJ Tankan spread composites (shipped 2026-06-11).
    # All three z-thresholded at ±1 on the 156w window via the standard _r helper.
    "JP_TANKAN_SPREAD1": lambda r, z: _r(r, z, 1, -1, "export-led-cycle", "domestic-demand-cycle"),
    "JP_TANKAN_SVC1":    lambda r, z: _r(r, z, 1, -1, "services-led",     "mfg-led",               "balanced"),
    "JP_TANKAN_FWD1":    lambda r, z: _r(r, z, 1, -1, "improving",        "deteriorating"),
    # Inflation composites (§3.1.3) — target-relative buckets on the raw YoY %.
    "US_INFL1":  _infl_regime,
    "UK_INFL1":  _infl_regime,
    "EU_INFL1":  _infl_regime,
    "JP_INFL1":  _infl_regime,
    # China: no hard target, deflation-prone → reflation / stable / deflation-risk.
    "CN_INFL1":  lambda r, z: (
        "n/a" if np.isnan(r)
        else ("reflation" if r > 3 else ("deflation-risk" if r < 0 else "stable"))
    ),
    # Inflation expectations: raw is the composite z (≈0-centred), so threshold on r.
    "US_INFEXP1": lambda r, z: (
        "n/a" if np.isnan(r)
        else ("rising-expectations" if r > 1
              else ("falling-expectations" if r < -1 else "anchored"))
    ),
    # §3.1.4 EZ nowcast: raw is composite z of 4 real-economy + sentiment series.
    "EU_NOWCAST1": lambda r, z: (
        "n/a" if np.isnan(r)
        else ("expansion" if r > 1
              else ("contraction" if r < -1 else "stable"))
    ),
    # §3.1.4 JP nowcast: raw is composite z of IP / Tankan / Retail Sales /
    # Machinery Orders. Same level-based bucket as EU_NOWCAST1 since both
    # are z-composites on a 156w window.
    "JP_NOWCAST1": lambda r, z: (
        "n/a" if np.isnan(r)
        else ("expansion" if r > 1
              else ("contraction" if r < -1 else "stable"))
    ),
    # §3.1.4 US GDPNow real GDP growth nowcast (Q/Q SAAR %). Thresholds are
    # absolute growth-rate levels, not z-scores — > 2.5 = above-trend (US
    # trend GDP is ~1.8-2% real); < 0 = recession nowcast; in-between is
    # mid-cycle / neutral. Same level-based pattern as US_ISM1 / US_PMI1.
    "US_GDPNOW1": lambda r, z: (
        "n/a" if np.isnan(r)
        else ("above-trend" if r > 2.5
              else ("recession-nowcast" if r < 0 else "near-trend"))
    ),
    # §3.1.4 NY Fed Staff Nowcast — US real GDP growth (Q/Q SAAR %). Same
    # absolute-level thresholds as US_GDPNOW1 (US trend GDP ~1.8-2% real):
    # > 2.5 above-trend, < 0 recession nowcast, else near-trend. Second-
    # opinion read alongside US_GDPNOW1.
    "US_NOWCAST1": lambda r, z: (
        "n/a" if np.isnan(r)
        else ("above-trend" if r > 2.5
              else ("recession-nowcast" if r < 0 else "near-trend"))
    ),
    # §3.1.4 UK monthly real GDP nowcast (YoY %). Thresholds are absolute
    # growth-rate levels — > 2.5 = above-trend (UK trend GDP is ~1.5% real);
    # < 0 = contraction; in-between is near-trend. Same level-based pattern
    # as US_GDPNOW1, calibrated to UK trend.
    "UK_NOWCAST1": lambda r, z: (
        "n/a" if np.isnan(r)
        else ("above-trend" if r > 2.5
              else ("contraction" if r < 0 else "near-trend"))
    ),
}


# ---------------------------------------------------------------------------
# Forward regime system
# ---------------------------------------------------------------------------
# NATURALLY_LEADING is loaded from macro_indicator_library.csv at module init
# (see _load_indicator_library above).  These indicators' current reading
# already reflects conditions 1-3 months ahead; their fwd_regime is labelled
# "[leading]" to distinguish from trajectory-based fwd_regime of lagging ones.

# z-slope thresholds for forward trajectory classification
_FWD_SLOPE_POS = +0.15   # weekly z-score change per week (improving if above)
_FWD_SLOPE_NEG = -0.15   # (deteriorating if below)


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


def _assign_fwd_regime(ind_id: str, z_slope: float) -> str:
    """
    Compute the forward regime trajectory label (1-2 month outlook).

    For naturally-leading indicators, the current regime reading IS already a
    forward-looking signal; we append '[leading]' to mark this.

    For all other indicators, the z-score slope (rate of change over 8 weeks)
    determines whether the signal is improving, stable, or deteriorating.

    Returns one of: 'improving', 'stable', 'deteriorating',
                    'improving [leading]', 'stable [leading]', 'deteriorating [leading]',
                    'n/a'
    """
    if np.isnan(z_slope):
        return "n/a" + (" [leading]" if ind_id in NATURALLY_LEADING else "")
    suffix = " [leading]" if ind_id in NATURALLY_LEADING else ""
    if z_slope > _FWD_SLOPE_POS:
        return "improving" + suffix
    if z_slope < _FWD_SLOPE_NEG:
        return "deteriorating" + suffix
    return "stable" + suffix


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
    df = load_hist_with_archive(COMP_HIST_CSV, skiprows="auto", index_col="Date")
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


def load_macro_economic_hist() -> pd.DataFrame:
    """
    Load the unified macro_economic_hist.csv into a single wide DataFrame
    holding every raw economic data series (FRED + OECD + WB + IMF +
    DB.nomics + ifo) under their canonical column names.

    Written by fetch_macro_economic.py.  File layout:
      Rows 0–13 : 14 metadata rows (Column ID, Series ID, Source,
                  Indicator, Country, Country Name, Region, Category,
                  Subcategory, Concept, cycle_timing, Units, Frequency,
                  Last Updated)
      Row 14    : flat header — 'Date', <col_1>, <col_2>, ...
      Row 15+   : weekly Friday data (1947-01-03 onwards)

    Replaces the three separate load_macro_us_hist / load_macro_intl_hist
    / load_macro_dbnomics_hist calls.  The indicator calculators still
    use `mu` / `mi` / `dbn` handles — run_phase_e aliases all three to
    this single DataFrame so _get_col(...) lookups work unchanged.
    """
    if not os.path.exists(MACRO_ECONOMIC_HIST_CSV):
        raise FileNotFoundError(
            f"Missing {MACRO_ECONOMIC_HIST_CSV} — "
            "run fetch_macro_economic.py first."
        )
    df = load_hist_with_archive(
        MACRO_ECONOMIC_HIST_CSV,
        skiprows="auto",
        index_col="Date",
    )
    df.index = pd.to_datetime(df.index, errors="coerce")
    df = df[df.index.notna()].sort_index()
    df = df.apply(pd.to_numeric, errors="coerce")
    df = df[df.index >= HIST_START]
    print(
        f"  [load] macro_economic_hist: {df.shape[0]} rows × "
        f"{df.shape[1]} cols ({df.index[0].date()} → {df.index[-1].date()})"
    )
    return df


# ===========================================================================
# INDICATOR CALCULATORS — US & NEIGHBOURS  (27 indicators)
#
# Each function signature: _calc_XXX(cp, mu, mi, supp, dbn) → pd.Series
#   cp   = load_comp_hist()               wide DataFrame of market prices
#   mu   = mi = dbn = load_macro_economic_hist()
#                                         single wide DataFrame of every raw
#                                         economic series keyed by canonical
#                                         column name (FRED / OECD / WB / IMF
#                                         / DB.nomics / ifo).  The three
#                                         aliases mu/mi/dbn are kept so the
#                                         calculator signatures don't change.
#   supp = {"euro_ig_spread": ..., "fxi": ...}
#                                         small dict of supplementals that are
#                                         NOT in macro_economic_hist (ECB SDW
#                                         spread + yfinance FXI).  Every FRED
#                                         series is reached via `mu` instead.
# Only the args actually needed are used; **_ absorbs the rest.
# ===========================================================================

# ---------------------------------------------------------------------------
# GROWTH / RISK APPETITE  (US_G1–G4)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# CREDIT / FINANCIAL CONDITIONS  (US_I1–I10)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# RISK / VOLATILITY REGIME  (US_R1–R2)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# REAL RATES  (US_RR1)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# FX / COMMODITIES  (US_FX1–FX2)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# MOMENTUM / TREND  (M1–M5)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# US MACRO FUNDAMENTALS  (US_JOBS1, US_JOBS2, US_JOBS3, US_G6, US_GROWTH1,
#                          US_HOUS1, US_M2, US_ISM1)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# DISPATCHER — US & NEIGHBOURS
# ---------------------------------------------------------------------------

_US_CALCULATORS = {
    "US_G1":      _calc_US_G1,
    "US_G2":      _calc_US_G2,
    "US_G3":     _calc_US_G3,
    "US_EQ_F3":      _calc_US_EQ_F3,
    "US_EQ_F4":     _calc_US_EQ_F4,
    "US_EQ_F1":      _calc_US_EQ_F1,
    "US_EQ_F2":     _calc_US_EQ_F2,
    "US_R1":      _calc_US_R1,
    "US_Cr2":      _calc_US_Cr2,
    "GL_CA_I1":      _calc_GL_CA_I1,
    "US_Cr1":      _calc_US_Cr1,
    "US_Cr3":      _calc_US_Cr3,
    "US_R2":      _calc_US_R2,
    "US_R3":     _calc_US_R3,
    "US_R4":      _calc_US_R4,
    "US_CA_G1":      _calc_US_CA_G1,
    "US_Cr4":     _calc_US_Cr4,
    "US_V1":      _calc_US_V1,
    "US_V2":      _calc_US_V2,
    "US_R5":     _calc_US_R5,
    "FX_CMD2":     _calc_FX_CMD2,
    "FX_CMD1":     _calc_FX_CMD1,
    "M1":         _calc_M1,
    "M2":         _calc_M2,
    "M3":         _calc_M3,
    "M4":         _calc_M4,
    "M5":         _calc_M5,
    "US_JOBS1":   _calc_US_JOBS1,
    "US_JOBS3":    _calc_US_JOBS3,
    "US_G6": _calc_US_G6,
    "US_HOUS1":   _calc_US_HOUS1,
    "US_M2":    _calc_US_M2,
    "US_G5":      _calc_US_G5,
    "US_G4":      _calc_US_G4,
    "US_ISM1":    _calc_US_ISM1,
    "US_ISM2":    _calc_US_ISM2,
    "US_R6":     _calc_US_R6,
    "US_JOBS2":    _calc_US_JOBS2,
}


# ===========================================================================
# INDICATOR CALCULATORS — EUROPE  (8 indicators)
# ===========================================================================

# ---------------------------------------------------------------------------
# EU GROWTH / RISK APPETITE  (EU_G1–G3)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# EU FINANCIAL CONDITIONS  (EU_I1–I3)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# EU CREDIT / RATES  (EU_R1)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# EU FX / MACRO COMPOSITE  (EU_FX1)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# DISPATCHER — EUROPE
# ---------------------------------------------------------------------------

_EU_CALCULATORS = {
    "EU_G3":  _calc_EU_G3,
    "UK_G1":  _calc_UK_G1,
    "EU_G2":  _calc_EU_G2,
    "EU_Cr1":  _calc_EU_Cr1,
    "EU_Cr2":  _calc_EU_Cr2,
    "UK_R2":  _calc_UK_R2,
    "UK_R1":  _calc_UK_R1,
    "UK_Cr1":  _calc_UK_Cr1,
    "EU_G4": _calc_EU_G4,
    "EU_R1":  _calc_EU_R1,
    "EU_G1":  _calc_EU_G1,
    "JP_G1":  _calc_JP_G1,
    "FX_2": _calc_FX_2,
    # EU_NOWCAST1 / UK_NOWCAST1 registrations live in _NOWCAST_CALCULATORS
    # (declared after the calculator functions to avoid a forward reference
    # at module-import time — both calculator funcs are defined ~500 lines
    # below this dispatcher dict).
}


# ===========================================================================
# INDICATOR CALCULATORS — ASIA & REGIONAL  (15 indicators)
# ===========================================================================

# ---------------------------------------------------------------------------
# ASIA GROWTH / RISK APPETITE  (AS_G1–G3)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# ASIA FINANCIAL CONDITIONS  (AS_I1–I2)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# ASIA FX  (AS_FX1–FX2)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# ASIA COMMODITIES  (AS_C1–C2)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# REGIONAL CLI COMPOSITES  (REG_CLI1–CLI5)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# STANDALONE COUNTRY CLIs  (OECD amplitude-adjusted, long-run avg = 100)
# ---------------------------------------------------------------------------
# Each calculator simply returns the country's CLI series resampled to weekly
# Fridays; `make_result` handles z-scoring and regime/fwd_regime assignment.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# JP TANKAN SPREAD COMPOSITES (§3.1.2 Stage E, shipped 2026-06-11)
#
# Built on the 5 BoJ Tankan sub-DI rows wired in commit a88205f. Each is a
# quarterly Tankan-derived spread resampled to the weekly-Friday spine and
# forward-filled within each quarter by _to_weekly_friday. All three inputs
# are business-conditions DIs (range typically -50..+50, zero neutral); the
# spread therefore inherits that range, and the framework's 156w rolling
# z-score handles regime classification.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# DISPATCHER — ASIA & REGIONAL
# ---------------------------------------------------------------------------

_ASIA_REGIONAL_CALCULATORS = {
    "AS_CN_G3":    _calc_AS_CN_G3,
    "AS_CN_G2":    _calc_AS_CN_G2,
    "AS_IN_G1":    _calc_AS_IN_G1,
    "AS_CN_R1":    _calc_AS_CN_R1,
    "AS_IN_R1":    _calc_AS_IN_R1,
    "FX_CN1":   _calc_FX_CN1,
    "FX_1":   _calc_FX_1,
    "FX_EM1":   _calc_FX_EM1,
    "FX_CMD5":    _calc_FX_CMD5,
    "FX_CMD4":    _calc_FX_CMD4,
    "AS_CN_G1":    _calc_AS_CN_G1,
    "GL_CLI1": _calc_GL_CLI1,
    "GL_CLI2": _calc_GL_CLI2,
    "EU_CLI1":  _calc_EU_CLI1,
    "AS_CLI1":  _calc_AS_CLI1,
    "GL_CLI5":  _calc_GL_CLI5,
    "US_CLI1":  _calc_US_CLI1,
    "CA_CLI1":  _calc_CA_CLI1,
    "DE_CLI1":  _calc_DE_CLI1,
    "FR_CLI1":  _calc_FR_CLI1,
    "UK_CLI1":  _calc_UK_CLI1,
    "IT_CLI1":  _calc_IT_CLI1,
    "JP_CLI1":  _calc_JP_CLI1,
    "CN_CLI1":  _calc_CN_CLI1,
    "AU_CLI1":  _calc_AU_CLI1,
    "GL_G2": _calc_GL_G2,
    "GL_G1":   _calc_GL_G1,
    "FX_CMD6": _calc_FX_CMD6,
    "FX_CMD3": _calc_FX_CMD3,
    "GLOBAL_GOLD1": _calc_GLOBAL_GOLD1,
    # §3.1.2 Stage E — BoJ Tankan spread composites (shipped 2026-06-11)
    "JP_TANKAN_SPREAD1": _calc_JP_TANKAN_SPREAD1,
    "JP_TANKAN_SVC1":    _calc_JP_TANKAN_SVC1,
    "JP_TANKAN_FWD1":    _calc_JP_TANKAN_FWD1,
    # §3.1.4 Phase E JP nowcast composite (shipped 2026-06-11)
    "JP_NOWCAST1":       _calc_JP_NOWCAST1,
}

# ===========================================================================
# INDICATOR CALCULATORS — PHASE D SURVEYS
#
# Column names match the col field in the corresponding library CSV.
# Source mapping (post-FMP rebuild, 2026-04-23):
#   US_PMI1/PMI2/SVC1 → DB.nomics ISM (macro_library_dbnomics.csv)
#   EU_ESI1           → DB.nomics Eurostat (macro_library_dbnomics.csv)
#   EU_PMI1           → EC Industry Confidence (EU_IND_CONF, DB.nomics Eurostat)
#   EU_PMI2           → EC Services Confidence (EU_SVC_CONF, DB.nomics Eurostat)
#   DE_IFO1           → ifo Institute Excel (fetch_macro_ifo.py)
#   UK_PMI1           → OECD BCI for UK (GBR_BUS_CONF, FRED BSCICP02GBM460S)
#   CN_PMI1           → OECD BCI for China (CHN_BUS_CONF, FRED CHNBSCICP02STSAM)
#   GL_PMI1           → z-score composite of ISM + EU_IND_CONF + GBR + CHN BCI
#   DE_ZEW1           → PROPRIETARY (ZEW Mannheim)
#   JP_PMI1           → PROPRIETARY (S&P Global); BoJ Tankan (quarterly) future
#   CN_PMI2           → PROPRIETARY (S&P Global / Caixin)
# ===========================================================================

# --- US ISM (DB.nomics — mirror may lag 4-8 months) ---


# US_PMI2 (ISM New Orders) was removed 2026-07-03: it duplicated US_ISM1 exactly
# (both _to_weekly_friday(ISM_MFG_NEWORD)). New Orders is kept as US_ISM1, which
# pairs with the US_ISM2 New-Orders-minus-Inventories spread.


# --- Eurozone (DB.nomics Eurostat) ---


# --- PMI proxies (free survey equivalents) ---


# --- Global composite ---


# ===========================================================================
# INDICATOR CALCULATORS — INFLATION (§3.1.3)
#
# Per-region inflation composites for the regime classifier's Inflation axis.
# All inputs come from the unified macro_economic_hist via the `mu` handle.
# The per-region *_CPI / EA_HICP columns are already stored as YoY % (not
# index levels), so the regional gauges read directly as a target-relative
# inflation level; US blends in core PCE YoY + the 5y5y forward breakeven.
# US_INFEXP1 is a z-score composite of differently-scaled expectations series
# (z-score each, then average — same pattern as GL_PMI1).
# ===========================================================================


_INFLATION_CALCULATORS = {
    "US_INFL1":   _calc_US_INFL1,
    "UK_INFL1":   _calc_UK_INFL1,
    "EU_INFL1":   _calc_EU_INFL1,
    "JP_INFL1":   _calc_JP_INFL1,
    "CN_INFL1":   _calc_CN_INFL1,
    "US_INFEXP1": _calc_US_INFEXP1,
}


# ===========================================================================
# NOWCAST CALCULATORS (§3.1.4) — real-time GDP-growth nowcasts
#
# Each one feeds the regime classifier's Growth axis. Composite shape is
# deliberately trivial when there's exactly one input — the value of the
# composite layer is the regime-rule mapping (see REGIME_RULES above), not
# averaging multiple already-noisy nowcasts. EU_NOWCAST1 (Phase E composite
# of EZ industrial production / retail / ESI / industrial confidence) lives
# in the European calculators block.
# ===========================================================================


_NOWCAST_CALCULATORS = {
    "US_GDPNOW1":  _calc_US_GDPNOW1,
    "US_NOWCAST1": _calc_US_NOWCAST1,
    # EU_NOWCAST1 / UK_NOWCAST1 declared here (not in _EU_CALCULATORS) so the
    # forward reference to their calculator functions resolves — the dispatcher
    # dict gets evaluated at module-import time, and both calculators are
    # defined hundreds of lines after _EU_CALCULATORS but well before this
    # dict. Functionally equivalent: _ALL_CALCULATORS merges every regional
    # dict, so the indicator id ↔ calculator mapping is unchanged.
    "EU_NOWCAST1": _calc_EU_NOWCAST1,
    "UK_NOWCAST1": _calc_UK_NOWCAST1,
}


_PHASE_D_CALCULATORS = {
    "US_PMI1":  _calc_US_PMI1,
    "US_SVC1":  _calc_US_SVC1,
    "EU_PMI1":  _calc_EU_PMI1,
    "EU_PMI2":  _calc_EU_PMI2,
    "EU_ESI1":  _calc_EU_ESI1,
    "DE_ZEW1":  _calc_DE_ZEW1,
    "DE_IFO1":  _calc_DE_IFO1,
    "UK_PMI1":  _calc_UK_PMI1,
    "JP_PMI1":  _calc_JP_PMI1,
    "CN_PMI1":  _calc_CN_PMI1,
    "CN_PMI2":  _calc_CN_PMI2,
    "GL_PMI1":  _calc_GL_PMI1,
}


# ===========================================================================
# INDICATOR CALCULATORS — TAYLOR RULE (§2.B B10-B13)
#
# Taylor-rule policy-stance gap for UK / EZ / JP / CN. The pipeline carries a
# policy rate and an inflation YoY per region but no output-gap or neutral-rate
# series, so two terms are constructed rather than read:
#   • the output gap is a *standardized activity gap* — the rolling z of the
#     region's growth nowcast (UK/EU/JP_NOWCAST1), or of CHN_IND_PROD for CN
#     which has no nowcast composite. Being a z (unitless, ~0-centred) not a
#     literal % output gap, the 0.5 weight makes this a Taylor-STYLE stance
#     gauge — direction + magnitude of policy vs. a rule — NOT a bp-accurate
#     Taylor rate.
#   • the neutral real rate r* is a hard-coded regional assumption (below).
#
#   taylor_implied = r* + pi + 0.5*(pi - target) + 0.5*activity_gap_z
#   gap            = policy_rate - taylor_implied
#     gap > 0  → policy tighter than the rule prescribes (restrictive / hawkish)
#     gap < 0  → policy looser than the rule prescribes (accommodative / dovish)
#
# r* / target assumptions (documented, adjustable in one place here):
#   UK  r*=0.5  target=2.0      EZ  r*=0.0  target=2.0
#   JP  r*=0.0  target=2.0      CN  r*=1.5  target=3.0 (PBoC has no formal point
#                                          target; ~3% CPI anchor as reference)
# If the output-gap nowcast is missing the gap term drops to 0 and the rule
# degrades to its inflation legs (graceful, same discipline as the composites).
# ===========================================================================


_TAYLOR_CALCULATORS = {
    "UK_TAYLOR1": _calc_UK_TAYLOR1,
    "EU_TAYLOR1": _calc_EU_TAYLOR1,
    "JP_TAYLOR1": _calc_JP_TAYLOR1,
    "CN_TAYLOR1": _calc_CN_TAYLOR1,
}


_GLOBAL_CALCULATORS = {
    "GL_MONPOL1": _calc_GL_MONPOL1,
}


# Master dispatcher — union of all regional dicts
_ALL_CALCULATORS = {
    **_US_CALCULATORS,
    **_EU_CALCULATORS,
    **_ASIA_REGIONAL_CALCULATORS,
    **_PHASE_D_CALCULATORS,
    **_INFLATION_CALCULATORS,
    **_NOWCAST_CALCULATORS,
    **_TAYLOR_CALCULATORS,
    **_GLOBAL_CALCULATORS,
}


# ===========================================================================
# MAIN COMPUTATION ENGINE
# ===========================================================================

def compute_all_indicators(cp, mu, mi, supp, dbn=None) -> dict:
    """
    Run every indicator calculator and return a dict:
        { ind_id: pd.DataFrame(columns=['raw','zscore','regime']) }

    One try/except per indicator so a single failure never kills the run.

    Args:
        cp   : comp_hist DataFrame   (weekly prices)
        mu   : macro_us DataFrame    (weekly FRED US series)
        mi   : macro_intl DataFrame  (weekly CLI + international series)
        supp : dict of supplemental Series from FRED / ECB / yfinance
        dbn  : macro_dbnomics_hist DataFrame (Phase D surveys, optional)

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
            raw_series = calc_fn(cp=cp, mu=mu, mi=mi, supp=supp,
                                    dbn=dbn if dbn is not None else pd.DataFrame())
            df = make_result(raw_series, ind_id)
            results[ind_id] = df
            last_date = df.index[-1].date() if not df.empty else "n/a"
            last_raw  = round(df["raw"].iloc[-1], 4) if not df.empty else "n/a"
            last_z    = round(df["zscore"].iloc[-1], 2) if not df.empty else "n/a"
            last_reg  = df["regime"].iloc[-1] if not df.empty else "n/a"
            last_fwd  = df["fwd_regime"].iloc[-1] if not df.empty else "n/a"
            print(f"  [compute] {ind_id}: raw={last_raw}  z={last_z}  "
                  f"regime='{last_reg}'  fwd='{last_fwd}'  ({last_date})")
        except Exception as exc:
            print(f"  [compute] ERROR in {ind_id}: {exc}")
            results[ind_id] = pd.DataFrame(columns=["raw", "zscore", "regime", "fwd_regime"])
    return results


# ===========================================================================
# OUTPUT BUILDERS
# ===========================================================================

def _zscore_trend_classification(z_now, z_1w, z_4w, z_13w, z_peak_abs_13w):
    """
    Classify the z-score trajectory into one of:
        intensifying : |z| rising vs both 1w and 4w ago, near the 13w peak
        fading       : |z| falling from recent peak (|z_now| < 0.9 * |z_4w|)
        reversing    : sign flipped vs 4w ago from a non-trivial prior level
        stable       : none of the above

    All inputs may be NaN; return "" when the current z-score is missing.
    """
    if z_now is None or pd.isna(z_now):
        return ""
    az = abs(z_now)
    a4 = abs(z_4w) if (z_4w is not None and pd.notna(z_4w)) else None
    a1 = abs(z_1w) if (z_1w is not None and pd.notna(z_1w)) else None
    # reversing: sign flip from a meaningful prior reading
    if (z_4w is not None and pd.notna(z_4w) and abs(z_4w) > 0.5
            and ((z_now >= 0) != (z_4w >= 0))):
        return "reversing"
    # fading: clear drop from 4w ago
    if a4 is not None and az < 0.9 * a4:
        return "fading"
    # intensifying: rising vs both 1w and 4w and close to 13w peak
    if (a1 is not None and a4 is not None
            and az > a1 and az > a4
            and z_peak_abs_13w is not None and pd.notna(z_peak_abs_13w)
            and az >= 0.95 * z_peak_abs_13w):
        return "intensifying"
    return "stable"


def _sample_z(df: pd.DataFrame, offset_weeks: int):
    """
    Return zscore value from `offset_weeks` weekly rows before the last
    non-null raw row, or NaN if unavailable. Data is weekly Friday frequency.
    """
    non_null = df.dropna(subset=["raw"])
    if non_null.empty or len(non_null) <= offset_weeks:
        return float("nan")
    return non_null["zscore"].iloc[-1 - offset_weeks]


def build_snapshot_df(results: dict) -> pd.DataFrame:
    """
    Build the snapshot DataFrame (one row per indicator, latest values only).

    Columns:
        id, group, sub_group, category, last_date,
        raw, zscore, zscore_1w_ago, zscore_4w_ago, zscore_13w_ago,
        zscore_peak_abs_13w, zscore_trend,
        regime, fwd_regime, formula_note

    Rows are in ALL_INDICATOR_IDS order (same as macro_indicator_library.csv).
    fwd_regime encodes the 1-2 month forward trajectory based on z-score slope.
    zscore_trend classifies recent z-score trajectory: intensifying, stable,
    fading, or reversing. See _zscore_trend_classification for definitions.
    """
    rows = []
    _empty_cols = ["raw", "zscore", "regime", "fwd_regime"]
    for ind_id in ALL_INDICATOR_IDS:
        meta = INDICATOR_META.get(ind_id, ("", "", "", "", "", ""))
        group, sub_group, category, formula_note, concept, subcategory = meta
        df = results.get(ind_id, pd.DataFrame(columns=_empty_cols))
        if df.empty or df["raw"].dropna().empty:
            rows.append({
                "id":                  ind_id,
                "group":               group,
                "sub_group":           sub_group,
                "concept":             concept,
                "subcategory":         subcategory,
                "category":            category,
                "last_date":           "",
                "raw":                 "",
                "zscore":              "",
                "zscore_1w_ago":       "",
                "zscore_4w_ago":       "",
                "zscore_13w_ago":      "",
                "zscore_peak_abs_13w": "",
                "zscore_trend":        "",
                "regime":              "Insufficient Data",
                "fwd_regime":          "n/a",
                "formula_note":        formula_note,
            })
        else:
            non_null = df.dropna(subset=["raw"])
            last = non_null.iloc[-1]
            z_now  = last["zscore"] if pd.notna(last["zscore"]) else float("nan")
            z_1w   = _sample_z(df, 1)
            z_4w   = _sample_z(df, 4)
            z_13w  = _sample_z(df, 13)
            last_13 = non_null["zscore"].iloc[-13:].dropna()
            z_peak_abs_13w = last_13.abs().max() if not last_13.empty else float("nan")
            trend = _zscore_trend_classification(z_now, z_1w, z_4w, z_13w, z_peak_abs_13w)
            rows.append({
                "id":                  ind_id,
                "group":               group,
                "sub_group":           sub_group,
                "concept":             concept,
                "subcategory":         subcategory,
                "category":            category,
                "last_date":           str(last.name.date()),
                "raw":                 round(last["raw"], 6),
                "zscore":              round(z_now, 4) if pd.notna(z_now) else "",
                "zscore_1w_ago":       round(z_1w, 4)  if pd.notna(z_1w)  else "",
                "zscore_4w_ago":       round(z_4w, 4)  if pd.notna(z_4w)  else "",
                "zscore_13w_ago":      round(z_13w, 4) if pd.notna(z_13w) else "",
                "zscore_peak_abs_13w": round(z_peak_abs_13w, 4) if pd.notna(z_peak_abs_13w) else "",
                "zscore_trend":        trend,
                "regime":              last["regime"],
                "fwd_regime":          last.get("fwd_regime", "n/a"),
                "formula_note":        formula_note,
            })
    return pd.DataFrame(rows)


def build_hist_df(results: dict) -> pd.DataFrame:
    """
    Build the history DataFrame: weekly dates × (N × 4) columns.

    Column naming convention:
        {id}_raw, {id}_zscore, {id}_regime, {id}_fwd_regime
    Index: DatetimeIndex of weekly Fridays.
    """
    frames = {}
    _empty_cols = ["raw", "zscore", "regime", "fwd_regime"]
    for ind_id in ALL_INDICATOR_IDS:
        df = results.get(ind_id, pd.DataFrame(columns=_empty_cols))
        if df.empty:
            continue
        frames[f"{ind_id}_raw"]        = df["raw"]
        frames[f"{ind_id}_zscore"]     = df["zscore"]
        frames[f"{ind_id}_regime"]     = df["regime"]
        frames[f"{ind_id}_fwd_regime"] = df.get("fwd_regime", pd.Series(dtype=str))

    if not frames:
        return pd.DataFrame()

    # .copy() defragments the block layout; without it the downstream
    # reset_index() in run_phase_e raises pandas PerformanceWarning.
    hist = pd.concat(frames, axis=1).copy()
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
    """
    from sources.base import get_sheets_service, push_df_to_sheets

    service = get_sheets_service(os.environ.get("GOOGLE_CREDENTIALS", ""))
    if service is None:
        print("  WARNING: GOOGLE_CREDENTIALS not set — skipping Sheets export.")
        return

    push_df_to_sheets(service, SHEET_ID, SNAPSHOT_TAB, df_snapshot, label="sheets")
    push_df_to_sheets(service, SHEET_ID, HIST_TAB, df_hist.reset_index(), label="sheets")


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
    # Stage 2 unified loader: one CSV holds every raw economic series
    # (FRED / OECD / WB / IMF / DB.nomics / ifo) keyed by canonical
    # column name.  mu / mi / dbn are the same DataFrame — calculators
    # look up columns by name via _get_col, so which handle they use is
    # irrelevant.  Missing columns return NaN-filled Series so a failed
    # fetch silently degrades instead of raising KeyError.
    me = load_macro_economic_hist()
    mu = me
    mi = me
    dbn = me

    # ------------------------------------------------------------------
    # 2. Fetch supplemental data
    #
    # `supp` carries only series that are NOT in the unified macro_economic_hist
    # (ECB SDW euro IG spread + yfinance FXI prices).  Every FRED series the
    # calculators need now lives in data/macro_library_fred.csv and reaches the
    # calculators via `mu` — see §0 of manuals/forward_plan.md and the §2.4
    # refactor that retired fetch_supplemental_fred() (2026-04-26).
    # ------------------------------------------------------------------
    supp: dict = {}

    print("  Fetching Euro IG spread (ECB SDW + unified hist) …")
    supp["euro_ig_spread"] = fetch_ecb_euro_ig_spread(mu)

    print("  Fetching FXI prices (yfinance) …")
    supp["fxi"] = fetch_fxi_prices()

    # ------------------------------------------------------------------
    # 3. Compute all indicators
    # ------------------------------------------------------------------
    print("  Computing indicators …")
    results = compute_all_indicators(cp, mu, mi, supp, dbn=dbn)

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

    write_hist_with_archive(df_hist.reset_index(), HIST_CSV)
    print(f"  Saved {HIST_CSV}")

    # §3.14 — month-end-sampled hist for regime-AA's monthly seam test.
    # `.resample('ME').last()` keeps the latest weekly Friday observation in each
    # month for every column (numeric raw/zscore and string regime/fwd_regime
    # alike), which is the natural month-end snapshot the Phase 3 Layer-1 engine
    # consumes alongside the weekly Indicator Explorer feed.
    df_hist_monthly = df_hist.resample("ME").last()
    df_hist_monthly.index.name = "Date"
    write_hist_with_archive(df_hist_monthly.reset_index(), MONTHLY_HIST_CSV)
    print(
        f"  Saved {MONTHLY_HIST_CSV}: {df_hist_monthly.shape[0]} month-end rows"
        f" × {df_hist_monthly.shape[1]} cols"
    )

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
