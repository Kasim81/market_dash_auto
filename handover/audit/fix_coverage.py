"""Recompute coverage findings correctly: a library row is covered if ANY of its
ticker columns (pr/tr/fred*) appears as a comp Symbol. The pipeline emits up to 2
output rows per library row (PR index-level + TR ETF)."""
import pandas as pd, os
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA=os.path.join(ROOT,"data"); AUD=os.path.join(ROOT,"audit")
lib=pd.read_csv(os.path.join(DATA,"index_library.csv"))
comp=pd.read_csv(os.path.join(DATA,"market_data_comp.csv"))
compsyms=set(comp.Symbol.astype(str))
tcols=["ticker_yfinance_pr","ticker_yfinance_tr","ticker_fred_tr","ticker_fred_yield","ticker_fred_oas","ticker_fred_spread","ticker_fred_duration"]
def tickers(r): return [str(r[c]) for c in tcols if pd.notna(r[c])]
def covered(r): return any(t in compsyms for t in tickers(r))
lib["covered"]=lib.apply(covered,axis=1)

# true missing: non-UNAVAILABLE library rows with no output row at all
missing=lib[(lib.data_source!="UNAVAILABLE") & (~lib.covered)]
# true orphan comp rows: Symbol not any lib ticker
alltix=set()
for _,r in lib.iterrows(): alltix|=set(tickers(r))
orphan=[s for s in compsyms if s not in alltix]

f=pd.read_csv(os.path.join(AUD,"findings.csv"))
# drop the flawed coverage rows
f=f[~f.check_id.isin(["MATCH_LIB_NO_OUTPUT","MATCH_OUTPUT_NO_LIB"])].copy()
newrows=[]
for _,r in missing.iterrows():
    newrows.append(dict(ticker=(tickers(r)[0] if tickers(r) else r["name"]),name=r["name"],tier="",
        check_type="coverage",check_id="MATCH_LIB_NO_OUTPUT",repo_value="in library",factiq_value="no comp row",
        as_of_repo="",as_of_factiq="",delta="",tolerance="",severity="HIGH",verdict="FLAG(HIGH)",
        notes=f"Library row ({r['data_source']}, validation={r['validation_status']}) has no output row (checked all ticker columns)"))
for s in orphan:
    nm=comp[comp.Symbol==s].iloc[0]["Name"]
    newrows.append(dict(ticker=s,name=nm,tier="?",check_type="coverage",check_id="MATCH_OUTPUT_NO_LIB",
        repo_value="no library row",factiq_value="in comp",as_of_repo="",as_of_factiq="",delta="",tolerance="",
        severity="HIGH",verdict="FLAG(HIGH)",notes="Output row matches no library ticker column"))
f2=pd.concat([f,pd.DataFrame(newrows)],ignore_index=True)
f2.to_csv(os.path.join(AUD,"findings.csv"),index=False)

# fix working_list has_output
wl=pd.read_csv(os.path.join(AUD,"working_list.csv"))
lib_key=lib.set_index("name")["covered"]
wl["has_output"]=wl["name"].map(lib_key).fillna(False)
wl.to_csv(os.path.join(AUD,"working_list.csv"),index=False)

print("true missing library rows (non-UNAVAILABLE, no output):",len(missing))
print(missing[["name","data_source","validation_status"]].to_string())
print("true orphan comp rows:",len(orphan),orphan)
print("total findings now:",len(f2))
print("coverage of non-UNAVAILABLE lib rows:",lib[(lib.data_source!='UNAVAILABLE')].covered.sum(),"/",(lib.data_source!='UNAVAILABLE').sum())
