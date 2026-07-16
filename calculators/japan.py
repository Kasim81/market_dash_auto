"""calculators.japan — Japan Phase E calculators (C7 split).

Each `_calc_*` returns a raw pd.Series; regime/z-score assignment
happens downstream in compute_macro_market.make_result."""

from __future__ import annotations

import numpy as np
import pandas as pd
from datetime import datetime, timezone

from calculators.common import *  # noqa: F401,F403 (helpers + constants)


def _calc_JP_G1(cp, **_):
    """
    Japan vs global equities: log(EWJ / URTH).
    Japan outperforms when: JPY weakens (exporter earnings), BOJ stays dovish,
    or China reflates (Japan supply-chain benefit).
    """
    return _log_ratio(_p(cp, "EWJ"), _p(cp, "URTH"))


def _calc_JP_CLI1(mi, **_): return _to_weekly_friday(_get_col(mi, "JPN_CLI"))


def _calc_JP_TANKAN_SPREAD1(mu, **_):
    """Tankan Large-Mfg minus Small-Mfg Business Conditions DI spread.
    The canonical Japan domestic-vs-export-cycle signal: Large enterprises
    are dominated by exporters (cycle reflects global demand); Small
    enterprises track domestic demand. Widening Large > Small = export-led
    cycle (yen-driven, global-cycle-driven); narrowing or Small > Large =
    domestic-demand-led (consumption / fiscal stimulus driven).

    Resampled to weekly Friday from quarterly Tankan releases."""
    large = _to_weekly_friday(_get_col(mu, "JP_TANKAN1"))
    small = _to_weekly_friday(_get_col(mu, "JP_TANKAN_SMFG"))
    if large is None or large.empty or small is None or small.empty:
        return pd.Series(dtype=float)
    return large - small


def _calc_JP_TANKAN_SVC1(mu, **_):
    """Tankan Large Non-Mfg minus Large Mfg Business Conditions DI spread.
    Positive spread = services-led economy (typical mature-expansion,
    consumption-cycle-driven); negative spread = mfg-led (investment-cycle
    or external-demand-driven). Captures the goods-vs-services rotation
    that drives regime classification on the BoJ's main framework."""
    nmfg = _to_weekly_friday(_get_col(mu, "JP_TANKAN_LNFG"))
    mfg = _to_weekly_friday(_get_col(mu, "JP_TANKAN1"))
    if nmfg is None or nmfg.empty or mfg is None or mfg.empty:
        return pd.Series(dtype=float)
    return nmfg - mfg


def _calc_JP_NOWCAST1(mu, **_):
    """Equal-weight Japan real-time growth nowcast (§3.1.4).
    Z-score-normalises each real-economy + survey component on its own
    156-week window, then averages available z-scores. Inputs:
      - JPN_IND_PROD     (e-Stat METI Indices of Industrial Production)
      - JP_TANKAN1       (BoJ Tankan Large-Mfg Business Conditions DI)
      - JPN_MACH_ORDERS  (e-Stat Cabinet Office Machinery Orders)
    Same z-composite shape as EU_NOWCAST1 / GL_PMI1 — raw output is the
    composite z (≈ 0-centred). Degrades gracefully if a component is
    missing. JPN_RETAIL_SALES was dropped 2026-07-07: the METI Current
    Survey of Commerce (商業動態統計) live monthly headline is Excel/file-only
    and not exposed via the e-Stat getStatsData API (every DB table is a
    vintaged archive ending 2013/2019; the OECD MEI mirror is frozen at
    2023-10) — see label-vs-data audit #1 and forward_plan Known Data Gaps.
    Flagged as the Phase E composite for §3.1.4 JP nowcast."""
    components = [
        _to_weekly_friday(_get_col(mu, "JPN_IND_PROD")),
        _to_weekly_friday(_get_col(mu, "JP_TANKAN1")),
        _to_weekly_friday(_get_col(mu, "JPN_MACH_ORDERS")),
    ]
    zscores = []
    for s in components:
        if s is not None and not s.empty:
            zscores.append(_rolling_zscore(s))
    if not zscores:
        return pd.Series(dtype=float)
    return pd.concat(zscores, axis=1).mean(axis=1)


def _calc_JP_TANKAN_FWD1(mu, **_):
    """Tankan Large Mfg Forecast DI minus Actual DI. Quarter-ahead
    leading-indicator signal: the forecast captures next-quarter
    expectations, actual captures this-quarter conditions. Widening
    positive = optimism (cycle turning up); negative = expected
    deterioration (cycle turning down). Among the cleanest quarterly
    turning-point detectors for JP."""
    fwd = _to_weekly_friday(_get_col(mu, "JP_TANKAN_LMFG_FCST"))
    actual = _to_weekly_friday(_get_col(mu, "JP_TANKAN1"))
    if fwd is None or fwd.empty or actual is None or actual.empty:
        return pd.Series(dtype=float)
    return fwd - actual


def _calc_JP_PMI1(**_):
    """Japan Manufacturing PMI — PROPRIETARY (S&P Global / au Jibun Bank).
    No monthly free source on FRED or DB.nomics. BoJ Tankan (quarterly)
    is the best free alternative; requires dedicated fetcher (future work)."""
    return pd.Series(dtype=float)


def _calc_JP_INFL1(mu, **_):
    """Japan inflation: mean of headline CPI YoY and core CPI YoY (both %).
    Headline = JPN_CPI_YOY (OECD COICOP2018 national all-items CPI growth
    over 1 year — already YoY %, monthly); core = JPN_CORE_CPI_YOY (OECD
    COICOP2018 ex-food-and-energy — already YoY %). Re-pointed 2026-07-07
    off the old `_yoy(JPN_CPI index)` path: FRED `JPNCPIALLMINMEI` was
    discontinued (dead since 2022-04), which had frozen this composite at a
    flat ~8.49. Both components are now fresh monthly OECD YoY. Falls back to
    headline-only if core is absent."""
    head = _to_weekly_friday(_get_col(mu, "JPN_CPI_YOY"))        # OECD all-items — already YoY %
    core = _to_weekly_friday(_get_col(mu, "JPN_CORE_CPI_YOY"))    # already YoY %
    parts = [s for s in (head, core) if s is not None and not s.empty]
    if not parts:
        return pd.Series(dtype=float)
    return pd.concat(parts, axis=1).mean(axis=1)


def _calc_JP_TAYLOR1(mu=None, **_):
    gap = _rolling_zscore(_calc_JP_NOWCAST1(mu=mu))
    return _taylor_gap(_get_col(mu, "JPN_POLICY_RATE"), _get_col(mu, "JPN_CPI_YOY"),
                       gap, r_star=0.0, target=2.0)


__all__ = [
    '_calc_JP_G1',
    '_calc_JP_CLI1',
    '_calc_JP_TANKAN_SPREAD1',
    '_calc_JP_TANKAN_SVC1',
    '_calc_JP_NOWCAST1',
    '_calc_JP_TANKAN_FWD1',
    '_calc_JP_PMI1',
    '_calc_JP_INFL1',
    '_calc_JP_TAYLOR1',
]
