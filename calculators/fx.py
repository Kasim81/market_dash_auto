"""calculators.fx — FX Phase E calculators (C7 split).

Each `_calc_*` returns a raw pd.Series; regime/z-score assignment
happens downstream in compute_macro_market.make_result."""

from __future__ import annotations

import numpy as np
import pandas as pd
from datetime import datetime, timezone

from calculators.common import *  # noqa: F401,F403 (helpers + constants)


def _calc_FX_CMD2(cp, **_):
    """EM vs DXY: log(EEM_USD / DX-Y.NYB) — EM risk appetite vs dollar."""
    return _log_ratio(_p(cp, "EEM", usd=True), _p(cp, "DX-Y.NYB"))


def _calc_FX_CMD1(cp, **_):
    """Copper vs Gold: log(HG=F / GC=F) — industrial demand vs safe-haven."""
    return _log_ratio(_p(cp, "HG=F"), _p(cp, "GC=F"))


def _calc_FX_2(cp, **_):
    """
    JPY carry trade signal: USDJPY=X 26-week log momentum.
    Positive z → yen weakening → carry trade ON.
    Negative z (< -1) → rapid yen strength → carry unwind risk (systemic risk-off signal).
    """
    usdjpy = _to_weekly_friday(_p(cp, "USDJPY=X"))
    return np.log(usdjpy / usdjpy.shift(26).replace(0, np.nan))


def _calc_FX_CN1(cp, **_):
    """
    CNY directional momentum: log(CNY=X / 26wk SMA).
    CNY=X = USD per CNY (higher = CNY stronger).
    Positive momentum → CNY strengthening (China macro-friendly);
    negative momentum → CNY weakening (capital outflow pressure).
    """
    cny = _to_weekly_friday(_p(cp, "CNY=X"))
    sma26 = cny.rolling(26, min_periods=13).mean()
    return np.log(cny / sma26.replace(0, np.nan))


def _calc_FX_1(cp, **_):
    """
    INR directional momentum: log(INR=X / 26wk SMA).
    INR=X = USD per INR (higher = INR stronger).
    Positive momentum → INR strengthening (India macro-friendly);
    negative momentum → INR weakening (inflation/current-account pressure).
    """
    inr = _to_weekly_friday(_p(cp, "INR=X"))
    sma26 = inr.rolling(26, min_periods=13).mean()
    return np.log(inr / sma26.replace(0, np.nan))


def _calc_FX_EM1(cp, **_):
    """
    EMFX basket momentum: equal-weight CNY, INR, KRW, TWD vs USD.
    Each FX=X quote is indirect (FCY per USD). Invert via -log so a
    RISING basket corresponds to the EM currencies collectively
    STRENGTHENING vs USD. Raw = basket − 26wk SMA (already in log space).
    Positive → EMFX strengthening (EM-risk-on, weak-USD, capital inflows).
    """
    tickers = ["CNY=X", "INR=X", "KRW=X", "TWD=X"]
    legs = []
    for t in tickers:
        s = _to_weekly_friday(_p(cp, t)).dropna()
        if s.empty:
            continue
        legs.append(-np.log(s.replace(0, np.nan)))
    if not legs:
        return pd.Series(dtype=float)
    basket = pd.concat(legs, axis=1).ffill(limit=_ALIGN_FFILL_LIMIT).dropna().mean(axis=1)
    sma26 = basket.rolling(26, min_periods=13).mean()
    return (basket - sma26).dropna()


def _calc_FX_CMD5(mu, **_):
    """
    Iron ore price (USD/tonne): FRED PIORECRUSDM (monthly, forward-filled
    to weekly via the unified macro_economic_hist).  Raw = price level;
    z-score reflects steel demand cycle.
    """
    return _to_weekly_friday(_get_col(mu, "PIORECRUSDM"))


def _calc_FX_CMD4(cp, **_):
    """
    Copper/Gold ratio: log(HG=F / GC=F) — same as US_FX2, EM-demand lens.
    Captures Asian industrial cycle vs safe-haven demand.
    """
    return _log_ratio(_p(cp, "HG=F"), _p(cp, "GC=F"))


def _calc_FX_CMD6(cp, **_):
    """
    Global commodity cycle: DBC 12-month log return.
    Positive z → commodities in a multi-month bull cycle; leads EM equity outperformance
    and commodity-exporting equity markets (AUS, BRA, SA, CA) by 8-12 weeks.
    """
    dbc = _to_weekly_friday(_p(cp, "DBC"))
    return np.log(dbc / dbc.shift(52).replace(0, np.nan))


def _calc_FX_CMD3(cp, **_):
    """
    Oil vs gold inflation regime: log(CL=F / GC=F).
    Positive → oil outpacing gold = growth-driven inflation (bullish cyclicals).
    Negative → gold outpacing oil = deflation scare or safe-haven demand (risk-off).
    Separates growth-driven inflation from fear-driven safe-haven flows.
    """
    return _log_ratio(_p(cp, "CL=F"), _p(cp, "GC=F"))


__all__ = [
    '_calc_FX_CMD2',
    '_calc_FX_CMD1',
    '_calc_FX_2',
    '_calc_FX_CN1',
    '_calc_FX_1',
    '_calc_FX_EM1',
    '_calc_FX_CMD5',
    '_calc_FX_CMD4',
    '_calc_FX_CMD6',
    '_calc_FX_CMD3',
]
