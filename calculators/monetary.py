"""calculators.monetary — Monetary (M-series) Phase E calculators (C7 split).

Each `_calc_*` returns a raw pd.Series; regime/z-score assignment
happens downstream in compute_macro_market.make_result."""

from __future__ import annotations

import numpy as np
import pandas as pd
from datetime import datetime, timezone

from calculators.common import *  # noqa: F401,F403 (helpers + constants)


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
    Multi-asset trend breadth: fraction of {SPY,URTH,GOVT,REET,DBC} above 40wk SMA.
    Raw = fraction (0.0–1.0).  ≥0.6 → risk-on, <0.4 → defensive.
    """
    assets = ["SPY", "URTH", "GOVT", "REET", "DBC"]
    scores = []
    for ticker in assets:
        px = _to_weekly_friday(_p(cp, ticker))
        sma = px.rolling(40, min_periods=20).mean()
        above = (px > sma).astype(float)
        scores.append(above)
    combined = pd.concat(scores, axis=1).mean(axis=1)
    return combined


def _calc_M3(cp, **_):
    """
    Antonacci Dual Momentum: max(SPY_12m, URTH_12m) - SHY_12m.
    Positive → equity regime; negative → bond regime.
    """
    spy  = _to_weekly_friday(_p(cp, "SPY"))
    urth = _to_weekly_friday(_p(cp, "URTH"))
    shy  = _to_weekly_friday(_p(cp, "SHY"))
    spy_12m  = spy  / spy.shift(52)  - 1
    urth_12m = urth / urth.shift(52) - 1
    shy_12m  = shy  / shy.shift(52)  - 1
    rel_mom = pd.concat([spy_12m, urth_12m], axis=1).max(axis=1)
    return rel_mom.subtract(shy_12m).dropna()


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
    VIX vol-regime filter: log(VIX_13w_SMA / VIX_52w_SMA).
    Negative (3-month MA < 12-month MA) → vol trending down → equity-friendly.
    Positive (3-month MA > 12-month MA) → vol expanding → defensive.
    52-week anchor ensures the signal reflects sustained regime shifts
    rather than short-term spikes.
    """
    vix = _to_weekly_friday(_p(cp, "^VIX"))
    ma13 = vix.rolling(13, min_periods=7).mean()
    ma52 = vix.rolling(52, min_periods=26).mean()
    return _log_ratio(ma13, ma52)


__all__ = [
    '_calc_M1',
    '_calc_M2',
    '_calc_M3',
    '_calc_M4',
    '_calc_M5',
]
