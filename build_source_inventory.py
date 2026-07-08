#!/usr/bin/env python3
"""
build_source_inventory.py
=========================
Static audit of the data pipeline's source->indicator wiring. Produces an Excel
workbook mapping every served indicator to ALL the sources that declare it
(primary + fallbacks), what actually won at the last regen, and structural flags
(source collisions, cadence/units mismatches, served != declared primary).

NO network / API keys required — reads only the in-repo CSV libraries + the last
regen outputs. Run: python3 build_source_inventory.py
"""
from __future__ import annotations
import csv, os, re, glob, datetime
from collections import defaultdict
import pandas as pd

DATA = "data"
OUT = "manuals/source_inventory_audit.xlsx"

# ---- filename -> canonical source label (matches the loaders' "source") ----
FILE_SOURCE = {
    "abs": "ABS", "alpha_vantage": "Alpha Vantage", "atlanta_fed": "AtlantaFed",
    "bdf": "Banque de France", "bls": "BLS", "boc": "BoC", "boe": "BoE",
    "boj": "BoJ", "bundesbank": "Bundesbank", "dbnomics": "DB.nomics", "ecb": "ECB",
    "estat": "e-Stat", "fred": "FRED", "french": "French", "ifo": "ifo", "imf": "IMF",
    "insee": "INSEE", "istat": "ISTAT", "jst": "JST", "lbma": "LBMA",
    "nasdaqdl": "Nasdaq Data Link", "ny_fed": "NYFed", "oecd": "OECD", "ons": "ONS",
    "shiller": "Shiller", "statcan": "StatCan", "worldbank": "World Bank",
    "imf_sdmx": "IMF SDMX",
}
FANOUT = {"World Bank", "OECD", "IMF"}
SKIP_FILES = {"countries", "sec_edgar"}  # not macro sources / different schema

_CAD_ORDER = {"daily": 0, "business daily": 0, "weekly": 1, "monthly": 2,
              "quarterly": 3, "annual": 4, "annually": 4, "yearly": 4}
def _cad_rank(freq): return _CAD_ORDER.get((freq or "").strip().lower(), 5)
def _kind(units):
    u = (units or "").lower()
    if any(k in u for k in ("%", "percent", "change", "year-on-year", "yoy", "growth")): return "rate"
    if "index" in u: return "index"
    if any(k in u for k in ("per annum", "yield", "basis point")): return "rate"
    return "level"

# ---- country prefixes for fan-out matching ----
ctry = list(csv.DictReader(open(f"{DATA}/macro_library_countries.csv")))
COUNTRIES = [r["code"] for r in ctry if r["code"] != "GLOBAL"]
PREFIXES = set(COUNTRIES) | {"EA19", "EA20", "EA", "EU"}

# ---- served macro (authoritative winners, last regen) ----
served = {}
for r in csv.DictReader(open(f"{DATA}/macro_economic.csv")):
    served[r["Col"]] = r
SERVED_COLS = set(served)

def fanout_cols(template):
    return [f"{c}_{template}" for c in COUNTRIES] + [f"{c}_{template}" for c in ("EA19","EA20","EA","EU")]

# ---- load every macro library registration, expand fan-outs ----
# reg: served_col -> list of dicts(source, series_id, units, frequency, sort_key, name, concept, category, subcategory, cycle_timing, country, file)
reg = defaultdict(list)
all_decl_cols = set()
for path in sorted(glob.glob(f"{DATA}/macro_library_*.csv")):
    stem = os.path.basename(path)[len("macro_library_"):-4]
    if stem in SKIP_FILES:
        continue
    source = FILE_SOURCE.get(stem, stem)
    for row in csv.DictReader(open(path)):
        sid = (row.get("series_id") or "").strip()
        col = (row.get("col") or "").strip()
        meta = dict(
            source=source, series_id=sid,
            units=(row.get("units") or "").strip(),
            frequency=(row.get("frequency") or "").strip(),
            sort_key=float(row.get("sort_key") or 0) if (row.get("sort_key") or "").strip() else 0.0,
            name=(row.get("name") or "").strip(),
            concept=(row.get("concept") or "").strip(),
            category=(row.get("category") or "").strip(),
            subcategory=(row.get("subcategory") or "").strip(),
            cycle_timing=(row.get("cycle_timing") or "").strip(),
            country=(row.get("country") or "").strip(),
            notes=(row.get("notes") or "").strip(),
            tier=int(row.get("tier") or 0) if (row.get("tier") or "").strip() else 0,
            file=stem,
        )
        # resolve served column candidate(s)
        if source == "OECD":
            tmpl = sid  # OECD col == series_id
            cs = [f"{c}_{tmpl}" for c in (row.get("oecd_countries") or "").split("+") if c.strip()]
        elif source in ("World Bank", "IMF"):
            base = col or sid
            if base in SERVED_COLS:           # already a full col (e.g. global series)
                cs = [base]
            else:
                cs = [c for c in fanout_cols(base) if c in SERVED_COLS] or [base]
        else:
            cs = [col or sid]
        for c in cs:
            reg[c].append(meta)
            all_decl_cols.add(c)

# ---- source_fallbacks.csv -> explicit precedence chains ----
fb = {}
for r in csv.DictReader(open(f"{DATA}/source_fallbacks.csv")):
    chain = []
    for t in ("t0", "t1", "t2", "t3"):
        s, i = (r.get(f"{t}_source") or "").strip(), (r.get(f"{t}_id") or "").strip()
        if s or i:
            chain.append((s, i))
    fb[r["indicator_id"].strip()] = dict(chain=chain, status=(r.get("t1_status") or "").strip(),
                                         latest=(r.get("t1_latest") or "").strip(),
                                         notes=(r.get("notes") or "").strip())

SRC_NORM = {"fred": "FRED", "dbnomics": "DB.nomics", "oecd": "OECD", "imf": "IMF",
            "boj": "BoJ", "ecb": "ECB", "boe": "BoE", "lbma": "LBMA", "nasdaqdl": "Nasdaq Data Link",
            "estat": "e-Stat", "bundesbank": "Bundesbank", "pboc": "PBoC", "nbs": "NBS"}
def norm(s): return SRC_NORM.get(s, s)

# ---- build macro indicator rows ----
def si(s, i): return f"{s}/{i}" if (s or i) else ""

macro_rows = []
universe = sorted(SERVED_COLS | all_decl_cols | set(fb))
for col in universe:
    decl = reg.get(col, [])
    # dedup declared by (source, series_id)
    seen, decl_u = set(), []
    for d in decl:
        k = (d["source"], d["series_id"])
        if k not in seen:
            seen.add(k); decl_u.append(d)
    sv = served.get(col)
    fbc = fb.get(col)
    freqs = {d["frequency"] for d in decl_u if d["frequency"]}
    units = {d["units"] for d in decl_u if d["units"]}
    # declared primary
    if fbc and fbc["chain"]:
        prim = si(norm(fbc["chain"][0][0]), fbc["chain"][0][1])
        prim_basis = "source_fallbacks t0"
    elif len(decl_u) == 1:
        prim = si(decl_u[0]["source"], decl_u[0]["series_id"]); prim_basis = "sole declared"
    elif len(decl_u) > 1:
        prim = "AMBIGUOUS"; prim_basis = f"{len(decl_u)} sources, no source_fallbacks entry"
    else:
        prim = ""; prim_basis = ""
    # fallback chain columns
    fbs = []
    if fbc:
        for s, i in fbc["chain"][1:]:
            fbs.append(si(norm(s), i))
    # any declared not represented in primary/fallback -> append as "other declared"
    listed = set()
    if fbc:
        for s, i in fbc["chain"]:
            listed.add((norm(s), i))
    for d in decl_u:
        if (d["source"], d["series_id"]) not in listed:
            tag = si(d["source"], d["series_id"])
            if tag not in fbs and tag != prim:
                fbs.append(tag)
    fbs += [""] * (4 - len(fbs))
    served_si = si(sv["Source"], sv["Series ID"]) if sv else ""
    # flags
    collision = len({(d["source"], d["series_id"]) for d in decl_u}) > 1
    cad_mis = len(freqs) > 1
    unit_mis = len(units) > 1
    served_ne_prim = bool(sv and prim and prim != "AMBIGUOUS" and served_si != prim)
    # definition collision: declared candidates disagree on measure-kind
    kinds = {_kind(d["units"]) for d in decl_u if d["units"]}
    def_coll = len(kinds) > 1
    # primary-cadence-gap: the finest-cadence candidate is an aggregator (tier>0)
    # while a tier-0/national source exists at a COARSER cadence → we've likely
    # registered the wrong (coarse) national ticker (per the 2026-06-18 rule).
    prim_cad_gap = ""
    if len(decl_u) > 1 and not def_coll:
        finest = min(_cad_rank(d["frequency"]) for d in decl_u)
        fine_cands = [d for d in decl_u if _cad_rank(d["frequency"]) == finest]
        coarser_primary = [d for d in decl_u if d["tier"] == 0 and _cad_rank(d["frequency"]) > finest]
        if all(d["tier"] > 0 for d in fine_cands) and coarser_primary:
            prim_cad_gap = "Y"
    # metadata: prefer served, else first declared
    md = sv or (decl_u[0] if decl_u else {})
    def g(key_sv, key_md): return (sv.get(key_sv) if sv else "") or (md.get(key_md, "") if isinstance(md, dict) else "")
    macro_rows.append(dict(
        Indicator=col,
        Name=(sv["Indicator"] if sv else (decl_u[0]["name"] if decl_u else "")),
        Concept=g("Concept", "concept"),
        Category=g("Category", "category"),
        Subcategory=g("Subcategory", "subcategory"),
        Country=(sv["Country"] if sv else ""),
        Region=(sv["Region"] if sv else ""),
        Cycle_timing=g("cycle_timing", "cycle_timing"),
        Served_units=(sv["Units"] if sv else ""),
        Served_cadence=(sv["Frequency"] if sv else ""),
        Served_last_period=(sv["Last Period"] if sv else ""),
        Declared_primary=prim,
        Primary_basis=prim_basis,
        Fallback_1=fbs[0], Fallback_2=fbs[1], Fallback_3=fbs[2], Fallback_4=fbs[3],
        Actually_served=served_si,
        Num_declared_sources=len(decl_u),
        FLAG_collision=("Y" if collision else ""),
        FLAG_definition_collision=("Y" if def_coll else ""),
        FLAG_cadence_mismatch=("Y" if cad_mis else ""),
        FLAG_units_mismatch=("Y" if unit_mis else ""),
        FLAG_primary_cadence_gap=prim_cad_gap,
        FLAG_served_ne_primary=("Y" if served_ne_prim else ""),
        FLAG_not_served=("Y" if col not in SERVED_COLS else ""),
        Declared_cadences=" | ".join(sorted(freqs)),
        Declared_units=" | ".join(sorted(units)),
        All_declared="; ".join(f"{d['source']}/{d['series_id']}[{d['frequency']}|{d['units']}|t{d['tier']}]" for d in decl_u),
        Fallback_notes=(fbc["notes"] if fbc else ""),
    ))

macro_df = pd.DataFrame(macro_rows)

# ---- composites ----
comp_rows = []
served_cadence = {c: served[c]["Frequency"] for c in served}
for r in csv.DictReader(open(f"{DATA}/macro_indicator_library.csv")):
    formula = r.get("formula_using_library_names", "")
    toks = set(re.findall(r"[A-Z][A-Z0-9_]{2,}", formula))
    comp = [t for t in toks if t in SERVED_COLS]
    cads = {served_cadence.get(c, "?") for c in comp}
    comp_collision = [c for c in comp if macro_df.loc[macro_df.Indicator == c, "FLAG_collision"].eq("Y").any()]
    comp_rows.append(dict(
        Composite_id=r.get("id", ""),
        Concept=r.get("concept", ""),
        Category=r.get("category", ""),
        Group=r.get("group", ""),
        Subcategory=r.get("subcategory", ""),
        Cycle_timing=r.get("cycle_timing", ""),
        Resolved_macro_components=", ".join(sorted(comp)),
        Component_cadences="; ".join(f"{c}={served_cadence.get(c,'?')}" for c in sorted(comp)),
        FLAG_mixed_cadence=("Y" if len(cads) > 1 else ""),
        FLAG_component_collision=("Y" if comp_collision else ""),
        Colliding_components=", ".join(comp_collision),
        Formula=formula,
    ))
comp_df = pd.DataFrame(comp_rows)

# ---- market ----
TCOLS = [("ticker_yfinance_pr","yfinance PR"),("ticker_yfinance_tr","yfinance TR"),
         ("ticker_investiny","investiny"),("ticker_fred_tr","FRED TR"),("ticker_fred_yield","FRED yield"),
         ("ticker_fred_oas","FRED OAS"),("ticker_fred_spread","FRED spread"),("ticker_fred_duration","FRED dur")]
mkt = list(csv.DictReader(open(f"{DATA}/index_library.csv")))
# served symbols
served_sym = set()
for f in ("market_data.csv","market_data_comp.csv"):
    p = f"{DATA}/{f}"
    if os.path.exists(p):
        for r in csv.DictReader(open(p)):
            s = (r.get("Symbol") or r.get("Ticker") or "").strip()
            if s: served_sym.add(s)
# ticker -> count of library rows (shared-ticker collision)
tk_count = defaultdict(int)
for r in mkt:
    for tc, _ in TCOLS:
        v = (r.get(tc) or "").strip()
        if v: tk_count[v] += 1
mkt_rows = []
for r in mkt:
    chain = [(lbl, (r.get(tc) or "").strip()) for tc, lbl in TCOLS if (r.get(tc) or "").strip()]
    prim = f"{chain[0][0]}/{chain[0][1]}" if chain else ""
    fbs = [f"{l}/{t}" for l, t in chain[1:]]
    fbs += [""] * (3 - len(fbs))
    tickers = [t for _, t in chain]
    shared = any(tk_count[t] > 1 for t in tickers)
    served_ok = any(t in served_sym for t in tickers)
    mkt_rows.append(dict(
        Instrument=r.get("name",""),
        Broad_asset_class=r.get("broad_asset_class",""),
        Asset_subclass=r.get("asset_subclass",""),
        Region=r.get("region",""),
        Country_market=r.get("country_market",""),
        Sector_style=r.get("sector_style",""),
        Currency=r.get("base_currency",""),
        Units=r.get("units",""),
        Data_source=r.get("data_source",""),
        Validation=r.get("validation_status",""),
        Proxy=r.get("proxy_flag",""),
        Declared_primary=prim,
        Fallback_1=fbs[0], Fallback_2=fbs[1], Fallback_3=fbs[2],
        FLAG_shared_ticker=("Y" if shared else ""),
        Shared_tickers=", ".join(sorted({t for t in tickers if tk_count[t] > 1})),
        FLAG_in_served=("" if served_ok else "not-served"),
        Data_start=r.get("data_start",""),
        Simple_dash=r.get("simple_dash",""),
    ))
mkt_df = pd.DataFrame(mkt_rows)

# ---- collisions action list ----
coll = macro_df[(macro_df.FLAG_collision=="Y")|(macro_df.FLAG_cadence_mismatch=="Y")|
                (macro_df.FLAG_units_mismatch=="Y")|(macro_df.FLAG_served_ne_primary=="Y")|
                (macro_df.FLAG_definition_collision=="Y")|(macro_df.FLAG_primary_cadence_gap=="Y")].copy()
coll.insert(0, "Type", "macro")
cc = comp_df[comp_df.FLAG_mixed_cadence=="Y"][["Composite_id","Concept","Component_cadences","Colliding_components"]].copy()
mc = mkt_df[mkt_df.FLAG_shared_ticker=="Y"][["Instrument","Declared_primary","Shared_tickers"]].copy()

# ---- README ----
readme = pd.DataFrame({
 "Source-Inventory Audit": [
  f"Generated {datetime.date.today()} by build_source_inventory.py (static; no API calls).",
  "",
  "PURPOSE: map every served indicator to ALL sources that declare it (primary + fallbacks),",
  "what actually won at the last regen, and structural flags. Built to catch the JP_INFL1",
  "class of bug: two sources feeding one served column with different cadence/definition.",
  "",
  "SHEETS:",
  " - Macro indicators: one row per served (Country,Col). Declared_primary vs Actually_served.",
  " - Composites: macro_indicator_library blends; FLAG_mixed_cadence = inputs of differing cadence.",
  " - Market instruments: index_library ticker chains; FLAG_shared_ticker = one ticker, many rows.",
  " - Collisions: filtered action list (the rows that need a decision).",
  "",
  "KEY FLAGS:",
  " FLAG_collision        = >1 distinct source/series_id declared for one served column.",
  " FLAG_cadence_mismatch = declared sources disagree on frequency (e.g. Annual vs Monthly).",
  " FLAG_units_mismatch   = declared sources disagree on units.",
  " FLAG_served_ne_primary= the source that won the last regen != declared primary.",
  " Declared_primary=AMBIGUOUS => >1 source, no source_fallbacks.csv entry to set precedence.",
  "",
  "COUNTS:",
  f" macro served cols: {len(SERVED_COLS)} | macro rows in table: {len(macro_df)}",
  f" collisions: {(macro_df.FLAG_collision=='Y').sum()} | cadence-mismatch: {(macro_df.FLAG_cadence_mismatch=='Y').sum()}"
  f" | served!=primary: {(macro_df.FLAG_served_ne_primary=='Y').sum()} | AMBIGUOUS primary: {(macro_df.Declared_primary=='AMBIGUOUS').sum()}",
  f" composites mixed-cadence: {(comp_df.FLAG_mixed_cadence=='Y').sum()} of {len(comp_df)}",
  f" market shared-ticker rows: {(mkt_df.FLAG_shared_ticker=='Y').sum()} of {len(mkt_df)}",
 ]})

os.makedirs("manuals", exist_ok=True)
sheets = [("README", readme), ("Macro indicators", macro_df), ("Composites", comp_df),
          ("Market instruments", mkt_df), ("Collisions-macro", coll),
          ("Collisions-composite", cc), ("Collisions-market", mc)]
with pd.ExcelWriter(OUT, engine="xlsxwriter") as xl:
    book = xl.book
    hdr = book.add_format({"bold": True, "bg_color": "#1F3864", "font_color": "white", "border": 1})
    flag = book.add_format({"bg_color": "#FCE4D6"})
    for name, df in sheets:
        df.to_excel(xl, sheet_name=name, index=False)
        ws = xl.sheets[name]
        nrow, ncol = len(df), len(df.columns)
        for i, c in enumerate(df.columns):
            ws.write(0, i, c, hdr)
            body = int(df[c].astype(str).str.len().max()) if nrow else 0
            ws.set_column(i, i, min(max(len(str(c)) + 2, body + 1), 60))
        if name != "README":
            ws.freeze_panes(1, 0)
            if nrow and ncol:
                ws.autofilter(0, 0, nrow, ncol - 1)
        # highlight FLAG_* columns that are set
        for i, c in enumerate(df.columns):
            if str(c).startswith("FLAG_"):
                for r in range(nrow):
                    if str(df.iloc[r, i]).strip():
                        ws.write(r + 1, i, df.iloc[r, i], flag)

print("wrote", OUT)
print("macro rows:", len(macro_df), "| collisions:", (macro_df.FLAG_collision=="Y").sum(),
      "| cadence-mismatch:", (macro_df.FLAG_cadence_mismatch=="Y").sum(),
      "| served!=primary:", (macro_df.FLAG_served_ne_primary=="Y").sum(),
      "| AMBIGUOUS:", (macro_df.Declared_primary=="AMBIGUOUS").sum())
print("composites mixed-cadence:", (comp_df.FLAG_mixed_cadence=="Y").sum())
print("market shared-ticker:", (mkt_df.FLAG_shared_ticker=="Y").sum())
