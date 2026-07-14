"""Phase 0: build working_list.csv, tiering, and internal checks M1-M9 + freshness.
Zero FactIQ calls. Run from repo root."""
import pandas as pd, numpy as np, os, datetime as dt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
AUD  = os.path.join(ROOT, "audit")
TODAY = dt.date(2026, 7, 12)

lib  = pd.read_csv(os.path.join(DATA, "index_library.csv"))
comp = pd.read_csv(os.path.join(DATA, "market_data_comp.csv"))
simple = pd.read_csv(os.path.join(DATA, "market_data.csv"))
levels = pd.read_csv(os.path.join(DATA, "level_change_tickers.csv"))["ticker"].tolist()
FRESH = {"Daily":5,"Weekly":10,"Monthly":45,"Quarterly":120,"Annual":540}

findings = []
def add(ticker, name, tier, check_type, check_id, repo, fq, asof_r, asof_f, delta, tol, sev, verdict, notes):
    findings.append(dict(ticker=ticker, name=name, tier=tier, check_type=check_type, check_id=check_id,
        repo_value=repo, factiq_value=fq, as_of_repo=asof_r, as_of_factiq=asof_f, delta=delta,
        tolerance=tol, severity=sev, verdict=verdict, notes=notes))

# ---- derive audit_symbol ----
def audit_symbol(r):
    ds = r["data_source"]
    if ds == "yfinance PR": return r.get("ticker_yfinance_pr")
    if ds == "yfinance TR": return r.get("ticker_yfinance_tr")
    if ds == "FRED":
        for c in ["ticker_fred_tr","ticker_fred_yield","ticker_fred_oas","ticker_fred_spread","ticker_fred_duration"]:
            if pd.notna(r.get(c)): return r.get(c)
        return None
    return None  # UNAVAILABLE
lib["audit_symbol"] = lib.apply(audit_symbol, axis=1)

# ---- flags ----
lib["is_level"] = lib["audit_symbol"].isin(levels) | lib["ticker_yfinance_pr"].isin(levels)
def is_yield(r):
    if r["asset_class"] in ("Rates","Spread"): return True
    if r["data_source"]=="FRED" and (pd.notna(r.get("ticker_fred_yield")) or pd.notna(r.get("ticker_fred_oas")) or pd.notna(r.get("ticker_fred_spread"))):
        return True
    return False
lib["is_yield"] = lib.apply(is_yield, axis=1)
def sym_str(r): return str(r["audit_symbol"]) if pd.notna(r["audit_symbol"]) else ""
lib["pence"] = lib.apply(lambda r: sym_str(r).endswith(".L"), axis=1)

# ---- tier ----
def tier(r):
    ds = r["data_source"]
    if ds == "UNAVAILABLE": return "C"
    if ds == "FRED": return "A"
    sym = sym_str(r)
    ac = r["asset_class"]
    if ac in ("Rates","Spread"): return "A"
    # index-level tickers -> C
    if sym.startswith("^"): return "C"
    if r["is_level"]: return "C"
    # exchange-suffixed -> B
    if any(sym.endswith(sfx) for sfx in [".L",".AS",".DE",".NS",".PA",".MI",".SW",".HK",".T",".TO",".AX",".SS",".SZ",".KS",".TW",".BR",".MC",".ST",".HE",".OL",".CO",".VI",".LS",".IR"]):
        return "B"
    if r["region"] not in ("North America","United States","US","Global") and sym and not sym.startswith("^"):
        # non-US listed but plain ticker (ADR) -> A if looks US-listed else B
        return "B"
    if ac in ("Commodity","FX"): return "A"
    # plain US ticker / ETF
    return "A"
lib["tier"] = lib.apply(tier, axis=1)

# ---- join to comp on Symbol==audit_symbol ----
comp2 = comp.copy()
comp2["_sym"] = comp2["Symbol"].astype(str)
lib["_sym"] = lib["audit_symbol"].astype(str)
merged = lib.merge(comp2, left_on="_sym", right_on="_sym", how="left", suffixes=("","_comp"))

# rows in library with a symbol but no comp output row
lib_no_out = merged[(lib["data_source"]!="UNAVAILABLE") & (merged["row_id"].isna()) & (lib["audit_symbol"].notna())]
# comp rows with no library row
lib_syms = set(lib["_sym"])
comp_orphan = comp2[~comp2["_sym"].isin(lib_syms)]

for _, r in lib_no_out.iterrows():
    add(r["audit_symbol"], r["name"], r["tier"], "coverage", "MATCH_LIB_NO_OUTPUT", "in library", "no comp row",
        "", "", "", "", "HIGH", "FLAG(HIGH)", f"Library row ({r['data_source']}) has no output row in market_data_comp.csv")
for _, r in comp_orphan.iterrows():
    add(r["Symbol"], r["Name"], "?", "coverage", "MATCH_OUTPUT_NO_LIB", "no library row", "in comp",
        "", "", "", "", "HIGH", "FLAG(HIGH)", "Output row has no matching library row (audit_symbol)")

# ---- M1: ticker cols match data_source ----
for _, r in lib.iterrows():
    ds=r["data_source"]; ok=True; note=""
    if ds=="yfinance PR" and pd.isna(r["ticker_yfinance_pr"]): ok=False; note="yfinance PR but ticker_yfinance_pr empty"
    if ds=="yfinance TR" and pd.isna(r["ticker_yfinance_tr"]): ok=False; note="yfinance TR but ticker_yfinance_tr empty"
    if ds=="FRED" and r["audit_symbol"] is None: ok=False; note="FRED but no ticker_fred_* populated"
    if not ok:
        add(r["audit_symbol"], r["name"], r["tier"], "metadata","M1","","","","","","", "HIGH","FLAG(HIGH)",note)

# ---- M2: validation_status ----
for _, r in lib.iterrows():
    if r["validation_status"]!="CONFIRMED":
        add(r["audit_symbol"], r["name"], r["tier"], "metadata","M2", r["validation_status"],"CONFIRMED","","","","", "LOW","FLAG(LOW)",
            f"validation_status={r['validation_status']} (data_source={r['data_source']})")

# ---- M5: USD==Local when base USD (on merged rows with values) ----
windows=["1W","1M","3M","6M","YTD","1Y"]
for _, r in merged.iterrows():
    if pd.isna(r.get("row_id")): continue
    if r["base_currency"]=="USD":
        for w in windows:
            lp=r.get(f"Local Perf {w}"); up=r.get(f"USD Perf {w}")
            if pd.notna(lp) and pd.notna(up) and abs(lp-up)>1e-6:
                add(r["Symbol"], r["name"], r["tier"], "metadata","M5", lp, up,"","", round(lp-up,6),"exact","HIGH","FLAG(HIGH)",
                    f"base USD but Local Perf {w} != USD Perf {w}")
                break

# ---- M6: bps arithmetic for yields ----
for _, r in merged.iterrows():
    if pd.isna(r.get("row_id")): continue
    if not r["is_yield"]: continue
    for w in windows:
        lp=r.get(f"Local Perf {w}"); bps=r.get(f"Local Perf {w} (bps)")
        if pd.notna(lp) and pd.notna(bps):
            expect=lp*100
            if abs(expect-bps)>1.0:  # >1 bps rounding tolerance
                add(r["Symbol"], r["name"], r["tier"], "metadata","M6", lp, bps,"","", round(bps-expect,2),"1 bps","MEDIUM","FLAG(MEDIUM)",
                    f"bps mismatch {w}: Local Perf={lp} -> expect {expect:.1f} bps, got {bps}")
                break

# ---- M8: subset consistency simple_dash rows in market_data.csv ----
simple_syms=set(simple["Symbol"].astype(str))
valcols=["Last Price"]+[f"Local Perf {w}" for w in windows]+[f"USD Perf {w}" for w in windows]
for _, r in lib.iterrows():
    if r.get("simple_dash")==True and r["data_source"]!="UNAVAILABLE":
        sym=str(r["audit_symbol"])
        if sym not in simple_syms:
            add(sym, r["name"], r["tier"], "consistency","M8","in comp/simple_dash","absent from market_data.csv","","","","","MEDIUM","FLAG(MEDIUM)",
                "simple_dash=True but not present in market_data.csv")
        else:
            cr=comp2[comp2["_sym"]==sym]; sr=simple[simple["Symbol"].astype(str)==sym]
            if len(cr) and len(sr):
                for vc in valcols:
                    a=cr.iloc[0].get(vc); b=sr.iloc[0].get(vc)
                    if pd.notna(a) and pd.notna(b) and abs(a-b)>1e-6:
                        add(sym, r["name"], r["tier"],"consistency","M8",a,b,"","",round(a-b,6),"exact","MEDIUM","FLAG(MEDIUM)",
                            f"{vc} differs between market_data.csv and market_data_comp.csv"); break

# ---- Freshness (local) ----
# frequency guess: Rates/FRED daily; commodities daily; equities daily; monthly for some FRED
def freq_of(r):
    if r["units"]=="Index" and r["data_source"].startswith("yfinance"): return "Daily"
    if r["data_source"]=="FRED":
        if str(r["audit_symbol"]).startswith("PIOR") or "USDM" in str(r["audit_symbol"]): return "Monthly"
        return "Daily"
    return "Daily"
for _, r in merged.iterrows():
    if pd.isna(r.get("row_id")): continue
    ld=r.get("Last Date")
    if pd.isna(ld): continue
    try: lastd=pd.to_datetime(ld).date()
    except: continue
    gap=(TODAY-lastd).days
    thr=FRESH[freq_of(r)]
    if gap>thr:
        sev="HIGH" if gap>2*thr else "MEDIUM"
        add(r["Symbol"], r["name"], r["tier"],"freshness","F1", str(lastd), str(TODAY), "", "", gap, thr, sev,
            f"FLAG({sev})", f"stale {gap}d vs {freq_of(r)} threshold {thr}d")

# ---- comp rows with empty Last Price (dead output) ----
for _, r in comp2.iterrows():
    if pd.isna(r.get("Last Price")):
        add(r["Symbol"], r["Name"], "?", "coverage","EMPTY_OUTPUT","", "no Last Price","","","","","MEDIUM","FLAG(MEDIUM)",
            f"comp row present but Last Price empty (Last Date {r.get('Last Date')})")

# ---- save ----
keep=["name","asset_class","broad_asset_class","region","country_market","base_currency","hedged","units",
      "data_source","validation_status","audit_symbol","is_level","is_yield","pence","tier","simple_dash"]
wl=lib[keep].copy()
wl["has_output"]=wl["audit_symbol"].astype(str).isin(comp2["_sym"])
wl.to_csv(os.path.join(AUD,"working_list.csv"), index=False)

fdf=pd.DataFrame(findings)
fdf.to_csv(os.path.join(AUD,"findings.csv"), index=False)

print("=== working_list tier counts ===")
print(wl["tier"].value_counts())
print("=== has_output by tier ===")
print(wl.groupby("tier")["has_output"].agg(["sum","count"]))
print("=== comp rows with Last Price present ===", comp2["Last Price"].notna().sum(),"/",len(comp2))
print("=== findings by check_id ===")
print(fdf["check_id"].value_counts())
print("=== findings by severity ===")
print(fdf["severity"].value_counts())
print("lib_no_output:",len(lib_no_out)," comp_orphan:",len(comp_orphan))
print("TOTAL findings phase0:",len(fdf))
