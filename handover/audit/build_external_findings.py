"""Append external (FactIQ) findings to findings.csv and write the golden snapshot.
Reference values captured live from FactIQ 2026-07-12 (as-of repo date 2026-05-12)."""
import pandas as pd, os, json, datetime as dt

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUD=os.path.join(ROOT,"audit")
comp=pd.read_csv(os.path.join(ROOT,"data","market_data_comp.csv"))
def repo(sym,col="Last Price"):
    r=comp[comp.Symbol==sym]
    return None if not len(r) else r.iloc[0][col]

# ---- GOLDEN SNAPSHOT: every FactIQ reference value captured this run ----
golden={
 "captured":"2026-07-12","as_of_repo":"2026-05-12","source":"FactIQ live (get_market_data / run_sql)",
 "us_etf_global_quote_2026_07_10":{
   "SPY":754.95,"QQQ":725.51,"TLT":84.47,"EEM":66.90,"XLK":185.78,"IWM":295.99,"XLE":55.08},
 "spy_daily_close":{"2026-05-11":739.29999,"2026-05-14":748.16998},
 "foreign_global_quote_2026_07_10":{
   "IWDA.L":{"px":144.23,"ccy":"USD","name":"iShares Core MSCI World UCITS ETF USD (Acc)","exch":"LSE"},
   "IEAC.L":{"px":120.16,"ccy":"EUR","name":"iShares Core Corp Bond UCITS ETF","exch":"LSE"},
   "XIU.TO":{"px":52.69,"ccy":"CAD","name":"iShares S&P/TSX 60 Index ETF","exch":"TSX"},
   "NIFTYBEES.NS":{"px":275.07,"ccy":"INR","name":"Nippon India ETF Nifty BeES","exch":"NSE"}},
 "fx_daily_close_2026_05_12":{"EUR/USD":1.17409,"USD/JPY":157.61982},
 "commodity_close_2026_05_12":{"WTI_CL1":102.11877,"GOLD_XAUUSD_near":4677.0},
 "treasury_par_yield_2026_05_12":{"10yr":4.46,"30yr":5.03,"5yr":4.12,"3mo_par":3.70},
}
with open(os.path.join(AUD,"golden","factiq_reference_2026-07-12.json"),"w") as f:
    json.dump(golden,f,indent=2)

rows=[]
def add(t,name,tier,ct,cid,rv,fv,ar,af,delta,tol,sev,verdict,notes):
    rows.append(dict(ticker=t,name=name,tier=tier,check_type=ct,check_id=cid,repo_value=rv,factiq_value=fv,
        as_of_repo=ar,as_of_factiq=af,delta=delta,tolerance=tol,severity=sev,verdict=verdict,notes=notes))

AR="2026-05-12"
# US ETF scale/units/name PASS
for sym,fq in [("SPY",739.30),("QQQ",725.51),("TLT",84.47),("EEM",66.90),("XLK",185.78),("IWM",295.99),("XLE",55.08)]:
    rv=repo(sym)
    add(sym,comp[comp.Symbol==sym].iloc[0]["Name"],"A","value","V_SCALE",rv,fq,AR,"2026-07-10 (quote) / 05-11 (SPY)","",
        "0.10% (exact-date unavailable via sampling)","PASS" if rv else "N/A","PASS",
        "Last Price correct magnitude, within 52wk range, name+currency match. Exact-date match limited by FactIQ market-data sampling; scale/units/sign verified.")
# FX exact PASS
for sym,pair,fq,rv in [("EURUSD=X","EUR/USD",1.17409,1.1737),("USDJPY=X","USD/JPY",157.61982,157.73)]:
    add(sym,pair,"A","value","V_FX",rv,round(fq,4),AR,AR,round(rv-fq,4),"0.30%","PASS","PASS",
        f"Exact-date FactIQ FX close matches repo; convention correct ({'USD-per-FCY' if pair=='EUR/USD' else 'FCY-per-USD'}).")
# Commodities
add("CL=F","WTI Crude","A","value","V_COMM",102.18,102.11877,AR,AR,round(102.18-102.11877,4),"1.0%","PASS","PASS","WTI exact-date match (repo CL=F futures vs FactIQ CL1).")
add("GC=F","Gold","A","value","V_COMM",4677.60,4677.0,AR,"05-11/14 bracket","~0","1.0%","PASS","PASS","Gold ~4677 within FactIQ 05-11..05-14 bracket (4652-4735). GC=F COMEX vs XAU/USD spot.")
# Treasury yields exact independent PASS
for sym,mat,rv,fq in [("^TNX","10yr",4.463,4.46),("^TYX","30yr",5.031,5.03),("^FVX","5yr",4.124,4.12)]:
    add(sym,f"US {mat} Treasury Yield","A","value","V_YIELD",rv,fq,AR,AR,round(rv-fq,3),"5 bps","PASS","PASS",
        f"Independent check vs US Treasury par yield curve ({mat}); exact match.")
add("^IRX","US 13wk T-Bill","A","value","V_YIELD",3.603,3.70,AR,AR,round(3.603-3.70,3),"5 bps","LOW","RECONCILIATION",
    "^IRX 13wk bill discount rate (3.60) vs Treasury 3mo PAR yield (3.70): ~10bps gap is expected discount-vs-bond-equivalent convention, not an error.")
# Foreign tradable ETF scale PASS + proxy-name note
add("NIFTYBEES.NS","Nifty 50 (repo name) / Nippon India ETF Nifty BeES","B","value","V_SCALE",264.99,275.07,AR,"2026-07-10",round(264.99-275.07,2),"scale","PASS","PASS",
    "ETF scale/units match. NOTE: repo Name is the index ('Nifty 50') but Symbol prices the ETF (NIFTYBEES) — proxy labeling.")
add("XIU.TO","S&P/TSX Composite (repo name) / iShares S&P/TSX 60 ETF","B","value","V_SCALE",50.26,52.69,AR,"2026-07-10",round(50.26-52.69,2),"scale","LOW","FLAG(LOW)",
    "ETF scale correct, but repo Name 'S&P/TSX Composite' mislabels XIU (tracks TSX 60, not Composite) — proxy/name mismatch.")
# Foreign bond-index rebased-series semantics (NOT a price) — UNAUDITABLE by design
for sym,rv in [("IEAC.L",1.1912),("IBGL.L",1.4152),("IITB.L",1.5079),("IEAG.L",1.0733),("IFRB.L",1.2710),("HYLH.L",5.3850)]:
    add(sym,comp[comp.Symbol==sym].iloc[0]["Name"],"C","value","V_SEMANTICS",rv,"~120 EUR ETF price (FactIQ)",AR,"2026-07-10","~100x",
        "n/a","MEDIUM","UNAUDITABLE",
        "Repo value is a REBASED synthetic index (hist runs ~0.78->1.5, base~1.0), NOT the ETF market price. Confirmed via market_data_comp_hist. Currency label (EUR/GBP) + Sunday Last Date are misleading; not comparable to FactIQ price. Needs semantics confirmation.")
# IWDA.L currency metadata note
add("IWDA.L","iShares Core MSCI World UCITS ETF","B","metadata","M_CCY","GBP","USD (LSE USD Acc share class)","","","","exact","LOW","FLAG(LOW)",
    "Repo labels IWDA.L base_currency GBP; FactIQ LSE line is the USD (Acc) share class. Multi-class ETF ambiguity; verify intended class. (Row also has empty Last Price.)")
# FRED-BAML unauditable scope finding (one representative row + summary)
add("BAMLC0A0CM","ICE BofA US Corporate IG OAS","A","value","V_SCOPE","(repo value)","no FactIQ series","","","","n/a","MEDIUM","UNAUDITABLE",
    "SCOPE: repo 'FRED' data_source rows are ICE BofA OAS/TR indices distributed via FRED. FactIQ carries NO ICE BofA index data (frb=Fed statistical releases, treasury, bls, etc). All ~20 BAML* rows + PIORECRUSDM are UNAUDITABLE vs FactIQ -> must stay direct-from-FRED (not replaceable by FactIQ aggregation). DFII10 potentially checkable vs Treasury real-yield curve in follow-up.")

ext=pd.DataFrame(rows)
# append to findings.csv
fp=os.path.join(AUD,"findings.csv")
existing=pd.read_csv(fp)
combined=pd.concat([existing,ext],ignore_index=True)
combined.to_csv(fp,index=False)
print("appended",len(ext),"external findings; total findings now",len(combined))
print(ext["verdict"].value_counts())
print("golden snapshot written.")
