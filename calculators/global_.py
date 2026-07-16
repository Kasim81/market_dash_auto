"""calculators.global_ — Global / cross-region Phase E calculators (C7 split).

Each `_calc_*` returns a raw pd.Series; regime/z-score assignment
happens downstream in compute_macro_market.make_result."""

from __future__ import annotations

import numpy as np
import pandas as pd
from datetime import datetime, timezone

from calculators.common import *  # noqa: F401,F403 (helpers + constants)


def _calc_GL_CA_I1(cp, **_):
    """Commodities vs Bonds: log(DBC / GOVT) — inflation vs deflation signal."""
    return _log_ratio(_p(cp, "DBC"), _p(cp, "GOVT"))


def _calc_GL_CLI1(mi, **_):
    """
    US vs Eurozone growth differential: USA_CLI − avg(DEU_CLI, FRA_CLI).
    Positive → US momentum outpacing Europe; negative → Europe catching up or leading.
    EA19 composite not available in OECD pull; DEU+FRA equal-weight used as proxy.
    """
    usa = _to_weekly_friday(_get_col(mi, "USA_CLI"))
    deu = _to_weekly_friday(_get_col(mi, "DEU_CLI"))
    fra = _to_weekly_friday(_get_col(mi, "FRA_CLI"))
    eu_avg = pd.concat([deu, fra], axis=1).mean(axis=1)
    eu_avg = _to_weekly_friday(eu_avg)
    return _arith_diff(usa, eu_avg)


def _calc_GL_CLI2(mi, **_):
    """
    US vs China growth differential: USA_CLI − CHN_CLI.
    Positive → US cycle outpacing China; negative → China leading.
    """
    usa = _to_weekly_friday(_get_col(mi, "USA_CLI"))
    chn = _to_weekly_friday(_get_col(mi, "CHN_CLI"))
    return _arith_diff(usa, chn)


def _calc_CA_CLI1(mi, **_): return _to_weekly_friday(_get_col(mi, "CAN_CLI"))


def _calc_AU_CLI1(mi, **_): return _to_weekly_friday(_get_col(mi, "AUS_CLI"))


def _calc_GL_CLI5(mi, **_):
    """
    Global growth breadth (diffusion): fraction of 9 countries where
    CLI > 100 AND CLI > CLI_6M_ago (i.e. above trend AND improving).
    Countries: USA, DEU, FRA, GBR, ITA, JPN, CHN, AUS, CAN.
    Raw = 0.0–1.0 fraction; >= 0.7 = broad expansion, < 0.4 = contracting.
    """
    cols = ["USA_CLI", "DEU_CLI", "FRA_CLI", "GBR_CLI", "ITA_CLI",
            "JPN_CLI", "CHN_CLI", "AUS_CLI", "CAN_CLI"]
    series_list = []
    for c in cols:
        try:
            s = _to_weekly_friday(_get_col(mi, c))
            lag26 = s.shift(26)
            above = ((s > 100) & (s > lag26)).astype(float)
            series_list.append(above)
        except Exception:
            pass  # skip countries not available in this pull
    if not series_list:
        return pd.Series(dtype=float)
    return pd.concat(series_list, axis=1).mean(axis=1)


def _calc_GL_G2(cp, **_):
    """
    Global multi-asset risk appetite: log(ACWI / GOVT).
    ACWI = iShares MSCI All Country World ETF; GOVT = US Treasury bond ETF.
    Positive → global capital flowing into equities over bonds (risk-on).
    Broader than US_I8 (SPY/GOVT) because ACWI includes all DM+EM equity markets.
    """
    return _log_ratio(_p(cp, "ACWI"), _p(cp, "GOVT"))


def _calc_GL_G1(cp, **_):
    """
    EM vs DM equity relative cycle: log(EEM / URTH).
    Positive → emerging markets outperforming MSCI World (requires: weak USD +
    positive EM growth differentials + commodity support).
    Complements US_FX1 (EEM/DXY) by isolating the equity relative vs the FX channel.
    """
    return _log_ratio(_p(cp, "EEM", usd=True), _p(cp, "URTH"))


def _calc_GLOBAL_GOLD1(mu, **_):
    """
    LBMA gold PM fix (USD/oz) — long-run daily gold benchmark from 1968.

    Source column GOLD_USD_PM is provisioned by sources/lbma.py from the
    `gold_pm` row in data/macro_library_lbma.csv (LBMA daily PM auction fix),
    replacing FRED's discontinued GOLDPMGBD228NLBM. Returned as the raw price
    level — the framework's 156-week rolling z-score handles the regime
    classification.
    """
    return _to_weekly_friday(_get_col(mu, "GOLD_USD_PM"))


def _calc_GL_PMI1(dbn, mi, **_):
    """Equal-weight global manufacturing survey composite.
    Z-score-normalises each component individually (different scales),
    then averages available z-scores. Degrades gracefully when components
    are missing — uses whatever is available."""
    components = [
        _to_weekly_friday(_get_col(dbn, "ISM_MFG_PMI")),
        _to_weekly_friday(_get_col(dbn, "EU_IND_CONF")),
        _to_weekly_friday(_get_col(mi, "GBR_BUS_CONF")),
        _to_weekly_friday(_get_col(mi, "CHN_BUS_CONF")),
    ]
    zscores = []
    for s in components:
        if s is not None and not s.empty:
            zscores.append(_rolling_zscore(s))
    if not zscores:
        return pd.Series(dtype=float)
    combined = pd.concat(zscores, axis=1).mean(axis=1)
    return combined


def _calc_GL_MONPOL1(mu, **_):
    """Global Monetary Policy Tracker (§2.B B15): net diffusion of 3-month
    policy-rate changes across the six major central banks — Fed (FEDFUNDS),
    ECB (EA_DEPOSIT_RATE), BoE (GBR_BANK_RATE), BoJ (JPN_POLICY_RATE), PBoC
    (CHN_POLICY_RATE), BoC (CAN_POLICY_RATE). Each bank contributes +1 if its
    policy rate is higher than ~3 months (13 weeks) ago (hiking), −1 if lower
    (cutting), 0 if unchanged; the raw output is the mean across the banks with
    data, in [−1, +1]. > 0 = net global tightening cycle; < 0 = net global
    easing; ≈ 0 = mixed / on hold. Degrades gracefully as banks drop out."""
    cols = ["FEDFUNDS", "EA_DEPOSIT_RATE", "GBR_BANK_RATE",
            "JPN_POLICY_RATE", "CHN_POLICY_RATE", "CAN_POLICY_RATE"]
    signs = []
    for c in cols:
        s = _to_weekly_friday(_get_col(mu, c))
        if s is None or s.empty:
            continue
        signs.append(np.sign(s - s.shift(13)))   # 13 weeks ≈ one quarter
    if not signs:
        return pd.Series(dtype=float)
    return pd.concat(signs, axis=1).mean(axis=1)


__all__ = [
    '_calc_GL_CA_I1',
    '_calc_GL_CLI1',
    '_calc_GL_CLI2',
    '_calc_CA_CLI1',
    '_calc_AU_CLI1',
    '_calc_GL_CLI5',
    '_calc_GL_G2',
    '_calc_GL_G1',
    '_calc_GLOBAL_GOLD1',
    '_calc_GL_PMI1',
    '_calc_GL_MONPOL1',
]
