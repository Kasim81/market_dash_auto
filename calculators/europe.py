"""calculators.europe — Europe (EU/DE/IT/FR) Phase E calculators (C7 split).

Each `_calc_*` returns a raw pd.Series; regime/z-score assignment
happens downstream in compute_macro_market.make_result."""

from __future__ import annotations

import numpy as np
import pandas as pd
from datetime import datetime, timezone

from calculators.common import *  # noqa: F401,F403 (helpers + constants)


def _calc_EU_G3(cp, **_):
    """
    STOXX 600 Cyclicals vs Defensives (Europe):
    log((Industrials + Banks + Technology) / (Utilities + Consumer Staples))
    Uses iShares STOXX 600 sector TR ETFs — all EUR-denominated on Xetra:
      EXH4.DE = Industrials  EXV1.DE = Banks  EXV3.DE = Technology
      EXH9.DE = Utilities    EXH3.DE = Consumer Staples
    """
    return _sum_log_ratio(
        [_p(cp, "EXH4.DE"), _p(cp, "EXV1.DE"), _p(cp, "EXV3.DE")],
        [_p(cp, "EXH9.DE"), _p(cp, "EXH3.DE")],
    )


def _calc_EU_G2(cp, **_):
    """
    Eurozone vs US equity leadership: log(FEZ / SPY).
    FEZ = iShares Euro Stoxx 50 ETF (USD-denominated); SPY = S&P 500 ETF.
    Both in USD — ratio is purely relative fundamental/sentiment, no FX noise.
    Rising → Eurozone equity outperformance; signals improving EU growth outlook.
    """
    return _log_ratio(_p(cp, "FEZ"), _p(cp, "SPY"))


def _calc_EU_Cr1(supp, mu, **_):
    """
    Euro IG spread: Euro IG corporate yield minus ECB AAA govt yield.

    EU_Cr1 explicitly tracks the Euro investment-grade spread, so it returns
    only the genuine IG spread or empty — no HY substitute (Euro HY is a
    separate regime, captured by EU_Cr2).

    Source: fetch_ecb_euro_ig_spread() stored in supp['euro_ig_spread'].
    The Euro IG corporate yield component is currently unsourced — see
    forward_plan.md §1 Known Data Gaps. Until a free historical source is
    wired in, EU_Cr1 returns an empty Series (regime 'n/a').
    """
    s = supp.get("euro_ig_spread")
    if s is None or s.empty:
        return pd.Series(dtype=float)
    return _to_weekly_friday(s)


def _calc_EU_Cr2(mu, **_):
    """Euro HY OAS, direct from FRED BAMLHE00EHYIOAS (Percent)."""
    return _to_weekly_friday(_get_col(mu, "BAMLHE00EHYIOAS"))


def _calc_EU_G4(cp, **_):
    """
    EUR macro composite: equal-weight z-score of EUR strength + EU cyclical tilt.
    Component 1: log(EURUSD=X)           — EUR/USD spot level
    Component 2: log(EXH4.DE / EXH9.DE) — EU Industrials vs Utilities (risk tilt)
    Both components are individually z-scored then averaged.
    Rising composite → EUR strengthening AND European cyclicals leading defensives.
    """
    log_eurusd  = np.log(_to_weekly_friday(_p(cp, "EURUSD=X")).replace(0, np.nan))
    log_cyc_def = _log_ratio(_p(cp, "EXH4.DE"), _p(cp, "EXH9.DE"))
    z1 = _rolling_zscore(log_eurusd)
    z2 = _rolling_zscore(log_cyc_def)
    composite = pd.concat([z1, z2], axis=1).mean(axis=1)
    # Return the composite z-score series; make_result will z-score it again,
    # so we return the raw composite directly (before final standardisation)
    return composite


def _calc_EU_R1(mu, **_):
    """
    BTP-Bund peripheral sovereign stress: ITA_BTP_10Y − DEU_BUND_10Y
    (FRED IRLTLT01ITM156N / IRLTLT01DEM156N via the unified
    macro_economic_hist).  Spread > 2.5% = peripheral stress; z > +1.5
    = historically elevated risk premium.  Key gauge of ECB credibility
    and Eurozone fiscal tail risk.
    """
    ita = _to_weekly_friday(_get_col(mu, "ITA_BTP_10Y"))
    deu = _to_weekly_friday(_get_col(mu, "DEU_BUND_10Y"))
    return _arith_diff(ita, deu)


def _calc_EU_G1(cp, **_):
    """
    Eurozone vs global equities: log(EZU / URTH).
    Positive → Eurozone outperforming MSCI World; driven by EUR, ECB posture, China trade.
    """
    return _log_ratio(_p(cp, "EZU"), _p(cp, "URTH"))


def _calc_EU_CLI1(mi, **_):
    """
    Europe block CLI: equal-weight average of DEU_CLI, FRA_CLI, GBR_CLI.
    Above 100 = Europe running above long-run trend; below 100 = below trend.
    ITA_CLI excluded as not consistently available in pull.
    """
    cols = ["DEU_CLI", "FRA_CLI", "GBR_CLI"]
    series_list = [_to_weekly_friday(_get_col(mi, c)) for c in cols]
    return _to_weekly_friday(pd.concat(series_list, axis=1).mean(axis=1))


def _calc_DE_CLI1(mi, **_): return _to_weekly_friday(_get_col(mi, "DEU_CLI"))


def _calc_FR_CLI1(mi, **_): return _to_weekly_friday(_get_col(mi, "FRA_CLI"))


def _calc_IT_CLI1(mi, **_): return _to_weekly_friday(_get_col(mi, "ITA_CLI"))


def _calc_EU_ESI1(dbn, **_):
    """EC Economic Sentiment Indicator (EA) — raw level, 156w z-score. Source: DB.nomics Eurostat."""
    return _to_weekly_friday(_get_col(dbn, "EU_ESI"))


def _calc_EU_PMI1(dbn, **_):
    """Eurozone Manufacturing survey proxy — EC Industry Confidence (ICI).
    Same 3 PMI questions (production expectations, order books, stocks).
    Source: DB.nomics Eurostat ei_bssi_m_r2."""
    return _to_weekly_friday(_get_col(dbn, "EU_IND_CONF"))


def _calc_EU_PMI2(dbn, **_):
    """Eurozone Services survey proxy — EC Services Confidence.
    Source: DB.nomics Eurostat ei_bssi_m_r2."""
    return _to_weekly_friday(_get_col(dbn, "EU_SVC_CONF"))


def _calc_DE_ZEW1(**_):
    """ZEW Economic Sentiment — PROPRIETARY (ZEW Mannheim).
    No free API/redistribution. German business sentiment covered by
    DE_IFO1 (ifo) and DEU_BUS_CONF (OECD BCI via FRED)."""
    return pd.Series(dtype=float)


def _calc_DE_IFO1(dbn, **_):
    """IFO Business Climate (Germany, 2015=100, SA) — raw level, 156w z-score.
    Source: ifo Institute Excel (ifo.de/en/ifo-time-series)."""
    return _to_weekly_friday(_get_col(dbn, "DE_IFO"))


def _calc_EU_NOWCAST1(dbn, **_):
    """Equal-weight Eurozone real-time growth nowcast (§3.1.4).
    Z-score-normalises each of four real-economy + sentiment components
    on their own 156-week window, then averages available z-scores. Inputs:
      - EZ_IND_PROD     (ECB STBS industrial production index)
      - EZ_RETAIL_VOL   (ECB STBS deflated retail turnover index)
      - EU_ESI          (EC Economic Sentiment Indicator)
      - EU_IND_CONF     (EC Industrial Confidence Indicator)
    Same z-composite shape as GL_PMI1 / US_INFEXP1 — raw output is the
    composite z (≈ 0-centred). Degrades gracefully if a component is
    missing. Equivalent to a home-built Eurocoin proxy at zero new
    dependencies; flagged as the Phase E composite for §3.1.4 EZ
    nowcast per forward_plan.md."""
    components = [
        _to_weekly_friday(_get_col(dbn, "EZ_IND_PROD")),
        _to_weekly_friday(_get_col(dbn, "EZ_RETAIL_VOL")),
        _to_weekly_friday(_get_col(dbn, "EU_ESI")),
        _to_weekly_friday(_get_col(dbn, "EU_IND_CONF")),
    ]
    zscores = []
    for s in components:
        if s is not None and not s.empty:
            zscores.append(_rolling_zscore(s))
    if not zscores:
        return pd.Series(dtype=float)
    return pd.concat(zscores, axis=1).mean(axis=1)


def _calc_EU_INFL1(mu, **_):
    """Euro-area inflation: mean of headline HICP YoY and core HICP YoY
    (both already %). Headline = EA_HICP (ECB Data Portal `HICP` dataset
    all-items annual rate — already YoY %); core = EA_HICP_CORE_YOY (same
    dataset, ex energy/food — the standard ECB core HICP YoY definition).
    Falls back to headline-only if core is absent."""
    head = _to_weekly_friday(_get_col(mu, "EA_HICP"))             # already YoY %
    core = _to_weekly_friday(_get_col(mu, "EA_HICP_CORE_YOY"))    # already YoY %
    parts = [s for s in (head, core) if s is not None and not s.empty]
    if not parts:
        return pd.Series(dtype=float)
    return pd.concat(parts, axis=1).mean(axis=1)


def _calc_EU_TAYLOR1(mu=None, dbn=None, **_):
    gap = _rolling_zscore(_calc_EU_NOWCAST1(dbn=dbn if dbn is not None else mu))
    return _taylor_gap(_get_col(mu, "EA_DEPOSIT_RATE"), _get_col(mu, "EA_HICP"),
                       gap, r_star=0.0, target=2.0)


__all__ = [
    '_calc_EU_G3',
    '_calc_EU_G2',
    '_calc_EU_Cr1',
    '_calc_EU_Cr2',
    '_calc_EU_G4',
    '_calc_EU_R1',
    '_calc_EU_G1',
    '_calc_EU_CLI1',
    '_calc_DE_CLI1',
    '_calc_FR_CLI1',
    '_calc_IT_CLI1',
    '_calc_EU_ESI1',
    '_calc_EU_PMI1',
    '_calc_EU_PMI2',
    '_calc_DE_ZEW1',
    '_calc_DE_IFO1',
    '_calc_EU_NOWCAST1',
    '_calc_EU_INFL1',
    '_calc_EU_TAYLOR1',
]
