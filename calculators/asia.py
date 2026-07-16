"""calculators.asia — Asia (China / cross-Asia) Phase E calculators (C7 split).

Each `_calc_*` returns a raw pd.Series; regime/z-score assignment
happens downstream in compute_macro_market.make_result."""

from __future__ import annotations

import numpy as np
import pandas as pd
from datetime import datetime, timezone

from calculators.common import *  # noqa: F401,F403 (helpers + constants)


def _calc_AS_CN_G3(cp, supp, **_):
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


def _calc_AS_CN_G2(cp, **_):
    """
    India mid vs large cap: log(^CRSMID / ^NSEI).
    ^CRSMID = Nifty Midcap 100; ^NSEI = Nifty 50.
    """
    return _log_ratio(_p(cp, "^CRSMID"), _p(cp, "^NSEI"))


def _calc_AS_IN_G1(cp, **_):
    """
    Japan: TOPIX (^N225 proxy) — z-score of log returns used as risk gauge.
    Raw = log(000001.SS / URTH) i.e. Shanghai Comp vs World equity.
    Captures Chinese equity risk appetite relative to global.
    """
    return _log_ratio(_p(cp, "000001.SS"), _p(cp, "URTH", usd=True))


def _calc_AS_CN_R1(mu, **_):
    """
    China 10Y yield spread vs US 10Y: CHN_GOVT_10Y − DGS10.
    Positive spread → Chinese bonds offer premium over US Treasuries;
    rising spread → capital-flow support for CNY and EM risk appetite.

    Currently returns NaN.  FRED does not host an OECD-compiled CN
    long-term rate (only the short-term IR3TTS01CNM156N), and the OECD
    MEI long-term-rate dataset doesn't carry a China series.  To
    restore this indicator, add a CHN_GOVT_10Y row to one of the
    macro_library_*.csv files (likely DB.nomics — PBoC / ChinaBond /
    Investing.com mirror) so it flows through the unified
    macro_economic_hist; this calculator then picks it up automatically.
    """
    chn = _to_weekly_friday(_get_col(mu, "CHN_GOVT_10Y"))
    us  = _to_weekly_friday(_get_col(mu, "DGS10"))
    return _arith_diff(chn, us)


def _calc_AS_IN_R1(mu, **_):
    """
    India 10Y yield spread vs US 10Y: IND_GOVT_10Y − DGS10
    (FRED INDIRLTLT01STM / DGS10 via the unified macro_economic_hist).
    Positive spread → Indian bonds offer carry over US Treasuries;
    rising spread widens EM carry opportunity (but also flags INR risk).

    Note: FRED uses an inverted naming convention for India
    (INDIRLTLT01STM, not IRLTLT01INM156N), so the macro_library_fred.csv
    row uses the canonical INDIRLTLT01STM series_id with col=IND_GOVT_10Y.
    """
    ind = _to_weekly_friday(_get_col(mu, "IND_GOVT_10Y"))
    us  = _to_weekly_friday(_get_col(mu, "DGS10"))
    return _arith_diff(ind, us)


def _calc_AS_CLI1(mi, **_):
    """
    Asia block CLI: equal-weight average of CHN_CLI, JPN_CLI, AUS_CLI.
    Above 100 = Asia running above long-run trend; below 100 = below trend.
    """
    cols = ["CHN_CLI", "JPN_CLI", "AUS_CLI"]
    series_list = [_to_weekly_friday(_get_col(mi, c)) for c in cols]
    return _to_weekly_friday(pd.concat(series_list, axis=1).mean(axis=1))


def _calc_CN_CLI1(mi, **_): return _to_weekly_friday(_get_col(mi, "CHN_CLI"))


def _calc_AS_CN_G1(cp, **_):
    """
    China vs broad EM divergence: log(FXI / EEM).
    Positive → China large-caps outperforming broad EM (policy support, credit easing).
    Strong signal for commodity-currency pairs (AUD, BRL, CLP) and EM risk appetite.
    """
    return _log_ratio(_p(cp, "FXI"), _p(cp, "EEM", usd=True))


def _calc_CN_PMI1(mi, **_):
    """China Manufacturing survey proxy — OECD BCI (NBS PMI components, monthly).
    100 = long-run average. Source: FRED CHNBSCICP02STSAM."""
    return _to_weekly_friday(_get_col(mi, "CHN_BUS_CONF"))


def _calc_CN_PMI2(**_):
    """Caixin China Manufacturing PMI — PROPRIETARY (S&P Global / Caixin).
    Chinese manufacturing covered by CN_PMI1 (OECD BCI from NBS components)."""
    return pd.Series(dtype=float)


def _calc_CN_INFL1(mu, **_):
    """China inflation: mean of CPI YoY and PPI YoY (both %).
    Headline = CHN_CPI_YOY (IMF Data Portal CPI dataset — monthly national
    all-items YoY %, repointed 2026-07-08 per §2.A A1; previously derived
    via `_yoy(CHN_CPI_INDEX)` from the FRED mirror that froze 2025-04).
    PPI = CHN_PPI (FRED `CHNPIEATI01GYM` — YoY %, frozen at 2022-12 by NBS
    upstream: China stopped supplying PPI to every international aggregator,
    so the PPI leg contributes history only and the composite tracks CPI
    alone after the bounded-fill window past 2022-12 — see §1 Known Data
    Gaps. The hist's bounded fill (2026-07-08) ends the dead column
    instead of forward-filling it to the present, and the mean skips the
    missing leg — no per-series handling needed here)."""
    cpi = _to_weekly_friday(_get_col(mu, "CHN_CPI_YOY"))          # already YoY %
    ppi = _to_weekly_friday(_get_col(mu, "CHN_PPI"))              # already YoY %
    parts = [s for s in (cpi, ppi) if s is not None and not s.empty]
    if not parts:
        return pd.Series(dtype=float)
    return pd.concat(parts, axis=1).mean(axis=1)


def _calc_CN_TAYLOR1(mu=None, **_):
    # CN has no nowcast composite — use the z of industrial-production YoY.
    gap = _rolling_zscore(_to_weekly_friday(_get_col(mu, "CHN_IND_PROD")))
    return _taylor_gap(_get_col(mu, "CHN_POLICY_RATE"), _get_col(mu, "CHN_CPI_YOY"),
                       gap, r_star=1.5, target=3.0)


__all__ = [
    '_calc_AS_CN_G3',
    '_calc_AS_CN_G2',
    '_calc_AS_IN_G1',
    '_calc_AS_CN_R1',
    '_calc_AS_IN_R1',
    '_calc_AS_CLI1',
    '_calc_CN_CLI1',
    '_calc_AS_CN_G1',
    '_calc_CN_PMI1',
    '_calc_CN_PMI2',
    '_calc_CN_INFL1',
    '_calc_CN_TAYLOR1',
]
