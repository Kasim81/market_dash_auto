"""calculators.us — United States Phase E calculators (C7 split).

Each `_calc_*` returns a raw pd.Series; regime/z-score assignment
happens downstream in compute_macro_market.make_result."""

from __future__ import annotations

import numpy as np
import pandas as pd
from datetime import datetime, timezone

from calculators.common import *  # noqa: F401,F403 (helpers + constants)


def _calc_US_G1(cp, **_):
    """Consumer Discretionary vs Staples: log(XLY / XLP)."""
    return _log_ratio(_p(cp, "XLY"), _p(cp, "XLP"))


def _calc_US_G2(cp, **_):
    """Cyclicals vs Defensives: log((XLI+XLF) / (XLU+XLP))."""
    return _sum_log_ratio(
        [_p(cp, "XLI"), _p(cp, "XLF")],
        [_p(cp, "XLU"), _p(cp, "XLP")],
    )


def _calc_US_EQ_F3(cp, **_):
    """Small Cap vs Large Cap: log(IWM / IWB)."""
    return _log_ratio(_p(cp, "IWM"), _p(cp, "IWB"))


def _calc_US_G3(cp, **_):
    """Banks vs Utilities: log(^SP500-4010 / XLU)."""
    return _log_ratio(_p(cp, "^SP500-4010"), _p(cp, "XLU"))


def _calc_US_EQ_F4(cp, **_):
    """Small Cap vs Large Cap (S&P proxy): log(IWM / SPY)."""
    return _log_ratio(_p(cp, "IWM"), _p(cp, "SPY"))


def _calc_US_EQ_F1(cp, **_):
    """Value vs Growth: log(IWD / IWF)."""
    return _log_ratio(_p(cp, "IWD"), _p(cp, "IWF"))


def _calc_US_EQ_F2(cp, **_):
    """Value vs Growth (S&P 500): log(IVE / IVW)."""
    return _log_ratio(_p(cp, "IVE"), _p(cp, "IVW"))


def _calc_US_R1(mu, **_):
    """10Y–3M yield-curve spread (bps), direct from FRED T10Y3M."""
    return _to_weekly_friday(_get_col(mu, "T10Y3M"))


def _calc_US_Cr2(mu, **_):
    """US HY OAS spread (bps), direct from FRED BAMLH0A0HYM2."""
    return _to_weekly_friday(_get_col(mu, "BAMLH0A0HYM2"))


def _calc_US_Cr1(mu, **_):
    """US IG OAS spread (bps), direct from FRED BAMLC0A0CM."""
    return _to_weekly_friday(_get_col(mu, "BAMLC0A0CM"))


def _calc_US_Cr3(mu, **_):
    """HY–IG spread differential: BAMLH0A0HYM2 − BAMLC0A0CM."""
    return _arith_diff(
        _to_weekly_friday(_get_col(mu, "BAMLH0A0HYM2")),
        _to_weekly_friday(_get_col(mu, "BAMLC0A0CM")),
    )


def _calc_US_R2(mu, **_):
    """10Y–2Y yield curve: direct from FRED T10Y2Y."""
    return _to_weekly_friday(_get_col(mu, "T10Y2Y"))


def _calc_US_R3(cp, mu, **_):
    """10Y-2Y yield curve from market prices: ^TNX (yfinance) minus DGS2 (FRED).
    Both are in % pa; result is in percentage points."""
    tnx = _to_weekly_friday(_p(cp, "^TNX"))
    dgs2 = _to_weekly_friday(_get_col(mu, "DGS2"))
    return _arith_diff(tnx, dgs2)


def _calc_US_R4(mu, **_):
    """10Y breakeven inflation: direct from FRED T10YIE."""
    return _to_weekly_friday(_get_col(mu, "T10YIE"))


def _calc_US_CA_G1(cp, **_):
    """Risk-On vs Risk-Off: log(SPY / GOVT)."""
    return _log_ratio(_p(cp, "SPY"), _p(cp, "GOVT"))


def _calc_US_Cr4(cp, **_):
    """HY vs Treasuries (credit risk): log(IHYU.L / GOVT)."""
    return _log_ratio(_p(cp, "IHYU.L"), _p(cp, "GOVT"))


def _calc_US_V1(cp, **_):
    """VIX term structure: ^VIX3M − ^VIX (bps; positive = contango = calm)."""
    return _arith_diff(_p(cp, "^VIX3M"), _p(cp, "^VIX"))


def _calc_US_V2(cp, **_):
    """Cross-asset vol: log(^MOVE / ^VIX) — bond vol relative to equity vol."""
    return _log_ratio(_p(cp, "^MOVE"), _p(cp, "^VIX"))


def _calc_US_R5(mu, **_):
    """10Y TIPS real yield: direct from FRED DFII10."""
    return _to_weekly_friday(_get_col(mu, "DFII10"))


def _calc_US_JOBS1(mu, **_):
    """Initial Claims YoY: IC4WSA year-on-year % change (inverted — rising = bad)."""
    ic = _to_weekly_friday(_get_col(mu, "IC4WSA"))
    return _yoy(ic)


def _calc_US_JOBS3(mu, **_):
    """
    Labour market composite z-score.
    Components: USA_UNEMPLOYMENT (inverted), PAYEMS YoY, IC4WSA YoY (inverted).
    Equal-weight average of the three rolling z-scores.
    """
    unrate  = _to_weekly_friday(_get_col(mu, "USA_UNEMPLOYMENT"))
    payems  = _to_weekly_friday(_get_col(mu, "PAYEMS"))
    claims  = _to_weekly_friday(_get_col(mu, "IC4WSA"))

    z_unrate  = _rolling_zscore(unrate)   * -1   # invert: low = good
    z_payems  = _rolling_zscore(_yoy(payems))
    z_claims  = _rolling_zscore(_yoy(claims)) * -1  # invert: rising = bad

    composite = pd.concat([z_unrate, z_payems, z_claims], axis=1).mean(axis=1)
    return composite


def _calc_US_G6(mu, **_):
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


def _calc_US_M2(mu, **_):
    """M2 liquidity YoY: M2SL year-on-year % change."""
    m2 = _to_weekly_friday(_get_col(mu, "M2SL"))
    return _yoy(m2)


def _calc_US_G5(cp, **_):
    """
    Technology leadership: log(QQQ / SPY).
    Positive → growth/tech leading broad market; negative → defensive rotation.
    """
    return _log_ratio(_p(cp, "QQQ"), _p(cp, "SPY"))


def _calc_US_G4(cp, **_):
    """
    Market breadth: log(RSP / SPY) — S&P 500 equal-weight vs cap-weight.
    Positive → broad participation; negative → rally concentrated in mega-caps.
    """
    return _log_ratio(_p(cp, "RSP"), _p(cp, "SPY"))


def _calc_US_ISM1(dbn, **_):
    """
    ISM Manufacturing New Orders Index — level form, forward-filled to
    weekly.  Level > 52 = expansion, < 48 = contraction.  Naturally
    leads activity by ~6 weeks.

    Source: DB.nomics ISM/neword (column ISM_MFG_NEWORD on the unified
    macro_economic_hist).  Replaces the retired FRED series NAPMOI
    that returned HTTP 400 from late April 2026 onward.
    """
    return _to_weekly_friday(_get_col(dbn, "ISM_MFG_NEWORD"))


def _calc_US_ISM2(dbn, **_):
    """
    ISM Manufacturing New Orders minus Inventories spread — level form,
    forward-filled to weekly.  When new orders outpace inventory build the
    spread is positive, a powerful leading signal of future PMI direction
    that typically leads the headline ISM by 2-3 months; a negative spread
    flags an inventory overhang and slowing orders.

    Sources: DB.nomics ISM/neword (ISM_MFG_NEWORD) and ISM/inventories
    (ISM_MFG_INVENTORIES) on the unified macro_economic_hist.
    """
    neword = _to_weekly_friday(_get_col(dbn, "ISM_MFG_NEWORD"))
    inv    = _to_weekly_friday(_get_col(dbn, "ISM_MFG_INVENTORIES"))
    return _arith_diff(neword, inv)


def _calc_US_R6(mu, **_):
    """
    Mortgage affordability / credit stress: MORTGAGE30US − DGS10.
    Wider spread = lender risk aversion / tight housing credit; leads housing activity.
    """
    mort = _to_weekly_friday(_get_col(mu, "MORTGAGE30US"))
    us10 = _to_weekly_friday(_get_col(mu, "DGS10"))
    return _arith_diff(mort, us10)


def _calc_US_JOBS2(mu, **_):
    """
    JOLTS labour market tightness: JTSJOL / UNEMPLOY (openings per unemployed person).
    Ratio > 1 = more openings than unemployed → wage pressure; leads CPI by ~2 months.
    """
    openings   = _to_weekly_friday(_get_col(mu, "JTSJOL"))
    unemployed = _to_weekly_friday(_get_col(mu, "UNEMPLOY"))
    ratio = openings / unemployed.replace(0, np.nan)
    return ratio


def _calc_US_CLI1(mi, **_): return _to_weekly_friday(_get_col(mi, "USA_CLI"))


def _calc_US_PMI1(dbn, **_):
    """ISM Manufacturing PMI composite — raw level, 156w z-score. Source: DB.nomics ISM/pmi."""
    return _to_weekly_friday(_get_col(dbn, "ISM_MFG_PMI"))


def _calc_US_SVC1(dbn, **_):
    """ISM Services PMI composite — raw level, 156w z-score. Source: DB.nomics ISM/nm-pmi."""
    return _to_weekly_friday(_get_col(dbn, "ISM_SVC_PMI"))


def _calc_US_INFL1(mu, **_):
    """US inflation gauge: mean of headline CPI YoY, core PCE YoY, and the
    5y5y-forward breakeven (all %), so the regime reads as a target-relative
    level. Degrades gracefully if a component is missing.

    `USA_CPI_INDEX` is the BLS/FRED CPI level (1982-84=100); we convert to
    YoY% here. The old code looked for `USA_CPI` which doesn't actually
    exist as a column — fixed 2026-06-10 so the calculator now uses all
    three components instead of silently dropping the headline."""
    cpi = _yoy(_to_weekly_friday(_get_col(mu, "USA_CPI_INDEX")))  # BLS/FRED CPI level → YoY %
    pce = _yoy(_to_weekly_friday(_get_col(mu, "PCEPILFE")))       # core PCE index → YoY %
    fwd = _to_weekly_friday(_get_col(mu, "T5YIFR"))               # 5y5y fwd %, level
    parts = [s for s in (cpi, pce, fwd) if s is not None and not s.empty]
    if not parts:
        return pd.Series(dtype=float)
    return pd.concat(parts, axis=1).mean(axis=1)


def _calc_US_INFEXP1(mu, **_):
    """US inflation-expectations composite: z-score-normalised average of the
    5y & 10y breakevens, the 5y5y forward, and Michigan 1y expectations.
    Components are on different scales so each is z-scored before averaging;
    the returned series is the composite z (≈0-centred)."""
    comps = [
        _to_weekly_friday(_get_col(mu, "T5YIE")),
        _to_weekly_friday(_get_col(mu, "T10YIE")),
        _to_weekly_friday(_get_col(mu, "T5YIFR")),
        _to_weekly_friday(_get_col(mu, "MICH")),
    ]
    zs = [_rolling_zscore(s) for s in comps if s is not None and not s.empty]
    if not zs:
        return pd.Series(dtype=float)
    return pd.concat(zs, axis=1).mean(axis=1)


def _calc_US_GDPNOW1(mu, **_):
    """Atlanta Fed GDPNow headline nowcast — US real GDP growth, Q/Q SAAR %.

    Single-input passthrough: take `US_GDPNOW` (irregular within-quarter
    publication-date observations from the Atlanta Fed xlsx), resample to
    weekly Friday, forward-fill across the quiet windows. The forward-fill
    is appropriate here because the published vintage *is* the model's
    current best estimate until the next update; between releases the
    nowcast is "the most recent reading", not "missing". Same trivial shape
    as the original _calc_UK_INFL1 (headline-only)."""
    return _to_weekly_friday(_get_col(mu, "US_GDPNOW"))


def _calc_US_NOWCAST1(mu, **_):
    """New York Fed Staff Nowcast headline — US real GDP growth, Q/Q SAAR %.

    Single-input passthrough: take `US_NYFED_NOWCAST` (weekly Friday
    publication-date observations from the NY Fed xlsx), resample to weekly
    Friday, forward-fill across the model's quiet windows around BEA's
    advance estimate. Same trivial shape as _calc_US_GDPNOW1 — provides the
    second-opinion read on US growth alongside Atlanta Fed GDPNow."""
    return _to_weekly_friday(_get_col(mu, "US_NYFED_NOWCAST"))


__all__ = [
    '_calc_US_G1',
    '_calc_US_G2',
    '_calc_US_EQ_F3',
    '_calc_US_G3',
    '_calc_US_EQ_F4',
    '_calc_US_EQ_F1',
    '_calc_US_EQ_F2',
    '_calc_US_R1',
    '_calc_US_Cr2',
    '_calc_US_Cr1',
    '_calc_US_Cr3',
    '_calc_US_R2',
    '_calc_US_R3',
    '_calc_US_R4',
    '_calc_US_CA_G1',
    '_calc_US_Cr4',
    '_calc_US_V1',
    '_calc_US_V2',
    '_calc_US_R5',
    '_calc_US_JOBS1',
    '_calc_US_JOBS3',
    '_calc_US_G6',
    '_calc_US_HOUS1',
    '_calc_US_M2',
    '_calc_US_G5',
    '_calc_US_G4',
    '_calc_US_ISM1',
    '_calc_US_ISM2',
    '_calc_US_R6',
    '_calc_US_JOBS2',
    '_calc_US_CLI1',
    '_calc_US_PMI1',
    '_calc_US_SVC1',
    '_calc_US_INFL1',
    '_calc_US_INFEXP1',
    '_calc_US_GDPNOW1',
    '_calc_US_NOWCAST1',
]
