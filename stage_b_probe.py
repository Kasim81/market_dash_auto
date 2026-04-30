#!/usr/bin/env python3
"""Stage B sub-step B.1 — probe candidate T1 sources for the 9 forcing-function rows.

Run from the repo root:
    python3 stage_b_probe.py

Requires FRED_API_KEY in env for the FRED reroute probes.
Each row prints: kind / series_id / ok / latest_obs_date / latest_value.

Paste the output verbatim back to Claude — used to author
data/source_fallbacks.csv with confirmed-working endpoints.
"""
import os
import sys

# Make the repo's sources/ importable (works whether you run from repo root
# or anywhere — adjust if your path differs).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sources import dbnomics as dbn
from sources import fred as fred_src

FRED_API_KEY = os.environ.get("FRED_API_KEY", "")

# Each entry: (indicator_id, T0 description, [(kind, series_id), ...])
# Multiple candidates per row let us pick the freshest valid endpoint.
PROBES = [
    ("JPN_POLICY_RATE", "FRED IRSTCB01JPM156N (frozen 2008-12)", [
        ("dbnomics", "OECD/MEI/JPN.IR3TIB.M"),
        ("dbnomics", "BIS/WS_LRPR_D/Q.JP"),
        ("dbnomics", "BIS/WS_LRPR_M/M.JP"),
        ("dbnomics", "BOJ/PR_2/PR01_TREND"),
    ]),
    ("CHN_POLICY_RATE", "FRED IRSTCB01CNM156N (frozen 2015-11)", [
        ("dbnomics", "OECD/MEI/CHN.IR3TIB.M"),
        ("dbnomics", "BIS/WS_LRPR_D/Q.CN"),
        ("dbnomics", "BIS/WS_LRPR_M/M.CN"),
    ]),
    ("GBR_BANK_RATE", "FRED BOERUKM (frozen 2016-08)", [
        ("fred", "BOEBRBS"),
        ("fred", "INTGSTGBM193N"),
        ("dbnomics", "BIS/WS_LRPR_D/Q.GB"),
        ("dbnomics", "BIS/WS_LRPR_M/M.GB"),
    ]),
    ("CHN_M2", "FRED MYAGM2CNM189N (frozen 2019-08)", [
        ("dbnomics", "OECD/KEI/MA.CHN.M.M.GY"),
        ("dbnomics", "OECD/MEI/CHN.MABMM301.GY.M"),
        ("dbnomics", "OECD/KEI/MABMM301.CHN.GY.M"),
    ]),
    ("EA_HICP", "FRED EA19CPALTT01GYM (frozen 2023-01)", [
        ("dbnomics", "Eurostat/prc_hicp_manr/M.RCH_A.CP00.EA20"),
        ("dbnomics", "Eurostat/prc_hicp_manr/M.RCH_A.CP00.EA"),
        ("dbnomics", "Eurostat/prc_hicp_manr/M.RCH_A.CP00.EA19"),
        ("dbnomics", "ECB/ICP/M.U2.N.000000.4.ANR"),
    ]),
    ("CHN_IND_PROD", "FRED CHNPRINTO01IXPYM (frozen 2023-11)", [
        ("dbnomics", "OECD/MEI/CHN.PRINTO01.IXOBSA.M"),
        ("dbnomics", "OECD/KEI/CHN.PRINTO01.GP.M"),
        ("dbnomics", "OECD/MEI/CHN.PRINTO01.GY.M"),
    ]),
    ("DEU_IND_PROD", "FRED DEUPROINDMISMEI (frozen 2024-03)", [
        ("dbnomics", "Eurostat/sts_inpr_m/M.PROD.B-D.SCA.I21.DE"),
        ("dbnomics", "Eurostat/teiis080/M.PRD.B-D.I21_SCA.DE"),
        ("dbnomics", "OECD/MEI/DEU.PRINTO01.IXOBSA.M"),
        ("dbnomics", "BBK/BBSTC.M.DE.Y.PRO_VOL.B0000.X.X.000.X"),
    ]),
    ("JPN_IND_PROD", "FRED JPNPROINDMISMEI (frozen 2024-03)", [
        ("dbnomics", "OECD/MEI/JPN.PRINTO01.IXOBSA.M"),
        ("dbnomics", "OECD/KEI/JPN.PRINTO01.GP.M"),
        ("dbnomics", "OECD/MEI/JPN.PRINTO01.GY.M"),
    ]),
    ("EA_DEPOSIT_RATE", "FRED ECBDFR (frozen 2025-06)", [
        ("dbnomics", "ECB/FM/D.U2.EUR.4F.KR.DFR.LEV"),
        ("dbnomics", "ECB/FM/B.U2.EUR.4F.KR.DFR.LEV"),
        ("dbnomics", "ECB/FM/M.U2.EUR.4F.KR.DFR.LEV"),
    ]),
]


def probe_dbnomics(series_id):
    try:
        doc = dbn.fetch_series(series_id)
        if doc is None:
            return False, "(no doc)", ""
        obs = dbn.parse_observations(doc)
        if not obs:
            return False, "(no obs)", ""
        non_null = [(p, v) for p, v in obs if v is not None]
        if not non_null:
            return False, "(all null)", ""
        last_period, last_value = non_null[-1]
        return True, str(last_period), f"{last_value}"
    except Exception as e:
        return False, f"ERR:{type(e).__name__}", str(e)[:40]


def probe_fred(series_id):
    if not FRED_API_KEY:
        return False, "(no FRED_API_KEY)", ""
    try:
        s = fred_src.fetch_series_as_pandas(series_id, FRED_API_KEY, start="2020-01-01")
        if s is None or s.empty:
            return False, "(empty)", ""
        s = s.dropna()
        if s.empty:
            return False, "(all null)", ""
        return True, str(s.index[-1].date()), f"{s.iloc[-1]}"
    except Exception as e:
        return False, f"ERR:{type(e).__name__}", str(e)[:40]


def main():
    print(f"Stage B probe — running {sum(len(c) for _,_,c in PROBES)} candidate endpoints")
    print(f"FRED key present: {bool(FRED_API_KEY)}")
    print()
    print(f"{'kind':10s} {'series_id':55s} {'ok':4s} {'latest':14s} value")
    print("-" * 110)
    for indicator_id, t0_desc, candidates in PROBES:
        print(f"\n# {indicator_id} (T0: {t0_desc})")
        for kind, sid in candidates:
            if kind == "dbnomics":
                ok, latest, val = probe_dbnomics(sid)
            elif kind == "fred":
                ok, latest, val = probe_fred(sid)
            else:
                continue
            mark = "OK" if ok else "no"
            print(f"{kind:10s} {sid:55s} {mark:4s} {latest:14s} {val[:30]}")


if __name__ == "__main__":
    main()
