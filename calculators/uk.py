"""calculators.uk — United Kingdom Phase E calculators (C7 split).

Each `_calc_*` returns a raw pd.Series; regime/z-score assignment
happens downstream in compute_macro_market.make_result."""

from __future__ import annotations

import numpy as np
import pandas as pd
from datetime import datetime, timezone

from calculators.common import *  # noqa: F401,F403 (helpers + constants)


def _calc_UK_G1(cp, **_):
    """
    UK domestic vs global: log(^FTMC / ^FTSE).
    FTSE 250 is predominantly domestic UK-revenue companies; FTSE 100 is
    ~70% overseas earnings. Rising ratio → domestic UK confidence recovering.
    """
    return _log_ratio(_p(cp, "^FTMC"), _p(cp, "^FTSE"))


def _calc_UK_R2(cp, **_):
    """
    UK inflation expectations proxy: log(INXG.L / IGLT.L).
    INXG.L = iShares UK IL Gilt ETF (inflation-linked); IGLT.L = nominal gilt ETF.
    Rising ratio → market pricing higher long-run UK inflation; falling → disinflation.
    """
    return _log_ratio(_p(cp, "INXG.L"), _p(cp, "IGLT.L"))


def _calc_UK_R1(mu, **_):
    """
    UK–Germany gilt-bund yield spread: GBR_GILT_10Y − DEU_BUND_10Y
    (FRED IRLTLT01GBM156N / IRLTLT01DEM156N, monthly OECD series,
    forward-filled to weekly via the unified macro_economic_hist).
    Rising spread → UK-specific risk premium rising (fiscal/political/inflation premium).
    """
    uk = _to_weekly_friday(_get_col(mu, "GBR_GILT_10Y"))
    de = _to_weekly_friday(_get_col(mu, "DEU_BUND_10Y"))
    return _arith_diff(uk, de)


def _calc_UK_Cr1(cp, **_):
    """
    UK credit conditions: log(SLXX.L / IGLT.L).
    SLXX.L = iShares GBP Corporate Bond ETF; IGLT.L = UK Gilt ETF.
    Rising ratio → credit spreads tightening, risk appetite improving in UK.
    """
    return _log_ratio(_p(cp, "SLXX.L"), _p(cp, "IGLT.L"))


def _calc_UK_CLI1(mi, **_): return _to_weekly_friday(_get_col(mi, "GBR_CLI"))


def _calc_UK_PMI1(mi, **_):
    """UK Manufacturing survey proxy — OECD Business Confidence (monthly).
    CBI-survey-derived composite, 100 = long-run average.
    Source: FRED BSCICP02GBM460S."""
    return _to_weekly_friday(_get_col(mi, "GBR_BUS_CONF"))


def _calc_UK_NOWCAST1(mu, **_):
    """UK growth nowcast (§3.1.4): ONS monthly real GDP (GBR_GDP_MONTHLY,
    ONS CDID ECY2 — Gross Value Added Monthly Index CVM SA) resampled to
    weekly Friday and converted to YoY %. ONS publishes monthly with ~6
    week lag — the cleanest UK nowcast at zero new fetcher cost since
    sources/ons.py is already wired.

    Single-input passthrough composite — same trivial shape as
    _calc_US_GDPNOW1; the value of the composite layer is the regime-rule
    mapping (see REGIME_RULES above), not averaging multiple already-noisy
    nowcasts. YoY conversion gives a clean economic-growth-rate output so
    the level-based regime thresholds (>2.5 above-trend, <0 contraction)
    sit on absolute growth-level buckets calibrated to UK trend (~1.5%)."""
    monthly_index = _to_weekly_friday(_get_col(mu, "GBR_GDP_MONTHLY"))
    if monthly_index is None or monthly_index.empty:
        return pd.Series(dtype=float)
    return _yoy(monthly_index)


def _calc_UK_INFL1(mu, **_):
    """UK inflation: mean of headline CPI YoY and core CPI YoY (both %).
    Headline = GBR_CPI_YOY (ONS D7G7 — All-Items annual rate, already YoY %);
    core = GBR_CORE_CPI_YOY (ONS DKO8 — already YoY % ex energy / food /
    alcohol / tobacco). Same blend shape as US_INFL1, now sourced wholly from
    ONS (Tier 1). Re-pointed off the frozen FRED `GBRCPIALLMINMEI` OECD-MEI
    mirror (last value-change 2025-03) — see the source-tier model in
    technical_manual.md §9.4. Falls back to headline-only if core is absent."""
    head = _to_weekly_friday(_get_col(mu, "GBR_CPI_YOY"))        # ONS D7G7 — already YoY %
    core = _to_weekly_friday(_get_col(mu, "GBR_CORE_CPI_YOY"))    # already YoY %
    parts = [s for s in (head, core) if s is not None and not s.empty]
    if not parts:
        return pd.Series(dtype=float)
    return pd.concat(parts, axis=1).mean(axis=1)


def _calc_UK_TAYLOR1(mu=None, **_):
    gap = _rolling_zscore(_calc_UK_NOWCAST1(mu=mu))
    return _taylor_gap(_get_col(mu, "GBR_BANK_RATE"), _get_col(mu, "GBR_CPI_YOY"),
                       gap, r_star=0.5, target=2.0)


__all__ = [
    '_calc_UK_G1',
    '_calc_UK_R2',
    '_calc_UK_R1',
    '_calc_UK_Cr1',
    '_calc_UK_CLI1',
    '_calc_UK_PMI1',
    '_calc_UK_NOWCAST1',
    '_calc_UK_INFL1',
    '_calc_UK_TAYLOR1',
]
