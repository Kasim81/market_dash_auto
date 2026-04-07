"""
build_html.py
=============
Generates indicator_explorer.html (and companion indicator_explorer_mkt.js)
from the four _hist CSVs.  Also writes intermediate payload JSON files for
inspection.

Run from the docs/ directory (or anywhere — paths are resolved relative to
this script file):
    python3 build_html.py
"""

import json
import os
import math
import pandas as pd
from pathlib import Path

# ── paths ─────────────────────────────────────────────────────────────────────
ROOT   = Path(__file__).parent.parent
DATA   = ROOT / "data"
DOCS   = ROOT / "docs"

MACRO_MKT   = DATA / "macro_market_hist.csv"
MACRO_US    = DATA / "macro_us_hist.csv"
MACRO_INTL  = DATA / "macro_intl_hist.csv"
MKT_COMP    = DATA / "market_data_comp_hist.csv"
IND_LIB     = DATA / "macro_indicator_library.csv"

# ── indicator groups matching the manual hierarchy ────────────────────────────
INDICATOR_GROUPS = {
    "US Growth & Style": [
        "US_G1","US_G2","US_G2b","US_G3","US_G3b","US_G4","US_G4b","US_G5","US_G6",
    ],
    "US Rates & Credit": [
        "US_I1","US_I2","US_I3","US_I4","US_I5","US_I6","US_I6b",
        "US_I7","US_I8","US_I9","US_I10","US_I11","US_R1","US_R2","US_RR1",
    ],
    "US FX & Momentum": [
        "US_FX1","US_FX2","M1","M2","M3","M4","M5",
    ],
    "US Macro Fundamentals": [
        "US_LEI1","US_JOBS1","US_LAB1","US_LAB2",
        "US_GROWTH1","US_HOUS1","US_M2L1","US_ISM1",
    ],
    "Europe & UK": [
        "EU_G1","EU_G2","EU_G3","EU_G4",
        "EU_I1","EU_I2","EU_I3","EU_I4","EU_R1","EU_FX1",
    ],
    "Asia: China & India": [
        "AS_G1","AS_G2","AS_G3","AS_G4",
        "AS_I1","AS_I2","AS_FX1","AS_FX2",
    ],
    "Asia Commodities & Japan": [
        "AS_C1","AS_C2","JP_G1","JP_FX1",
    ],
    "Global & Regional": [
        "REG_CLI1","REG_CLI2","REG_CLI3","REG_CLI4","REG_CLI5",
        "REG_RISK1","REG_EM1","REG_COMM1","REG_COMM2",
    ],
}

NATURALLY_LEADING = {
    "US_ISM1","US_LAB2","US_HOUS1","US_LEI1",
    "REG_CLI1","REG_CLI2","REG_CLI3","REG_CLI4","REG_CLI5","JP_FX1",
}

# ── helpers ───────────────────────────────────────────────────────────────────

def _clean(val):
    """Convert a value to JSON-safe form: None for NaN/empty, rounded float, or string."""
    if val is None:
        return None
    if isinstance(val, float):
        if math.isnan(val) or math.isinf(val):
            return None
        return round(val, 4)
    if isinstance(val, str):
        s = val.strip()
        return None if s == "" or s.lower() in ("nan", "n/a", "none") else s
    try:
        f = float(val)
        return None if math.isnan(f) or math.isinf(f) else round(f, 4)
    except (TypeError, ValueError):
        return str(val).strip() or None


def _series_to_list(s: pd.Series) -> list:
    return [_clean(v) for v in s.tolist()]


def _date_range(dates: list, values: list) -> tuple[str | None, str | None]:
    """Return (first_non_null_date, last_non_null_date) from parallel lists."""
    first = last = None
    for d, v in zip(dates, values):
        if v is not None:
            if first is None:
                first = d
            last = d
    return first, last


def _parse_date_col(df: pd.DataFrame) -> tuple[list, pd.DataFrame]:
    """Return (date_strings_list, df_without_date_col)."""
    date_col = next(
        (c for c in df.columns if "date" in str(c).lower()),
        df.columns[0]
    )
    dates = [str(d)[:10] for d in df[date_col].tolist()]
    return dates, df.drop(columns=[date_col])


# ── 1. macro_indicator_library metadata ──────────────────────────────────────

def load_indicator_meta() -> dict:
    lib = pd.read_csv(IND_LIB)
    meta = {}
    for _, row in lib.iterrows():
        ind_id = str(row.get("id", "")).strip()
        if not ind_id:
            continue
        meta[ind_id] = {
            "region":   str(row.get("region_block", "")).strip(),
            "category": str(row.get("category", "")).strip(),
            "formula":  str(row.get("formula_using_library_names", "")).strip(),
            "interp":   str(row.get("economic_interpretation", "")).strip(),
            "regime_desc": str(row.get("regime_classification", "")).strip(),
            "leading":  ind_id in NATURALLY_LEADING,
        }
    return meta


# ── 2. macro_market_hist ──────────────────────────────────────────────────────

def build_macro_market(ind_meta: dict) -> dict:
    df = pd.read_csv(MACRO_MKT, low_memory=False)
    # drop row_id if present
    if "row_id" in df.columns:
        df = df.drop(columns=["row_id"])
    dates, df = _parse_date_col(df)

    # discover which indicator IDs are present
    present_ids = set()
    for col in df.columns:
        for suffix in ("_raw", "_zscore", "_regime", "_fwd_regime"):
            if col.endswith(suffix):
                present_ids.add(col[: -len(suffix)])

    indicators = {}
    for ind_id in present_ids:
        entry = {"meta": ind_meta.get(ind_id, {})}
        for suffix in ("raw", "zscore", "regime", "fwd_regime"):
            col = f"{ind_id}_{suffix}"
            if col in df.columns:
                entry[suffix] = _series_to_list(df[col])
            else:
                entry[suffix] = [None] * len(dates)
        # use zscore column as the data-availability reference
        ref = entry["zscore"] if any(v is not None for v in entry["zscore"]) else entry["raw"]
        first, last = _date_range(dates, ref)
        entry["first_date"] = first
        entry["last_date"]  = last
        indicators[ind_id] = entry

    # build groups — only include IDs that are present in the file
    groups = {}
    ungrouped = set(present_ids)
    for group_name, ids in INDICATOR_GROUPS.items():
        members = [i for i in ids if i in present_ids]
        if members:
            groups[group_name] = members
            ungrouped -= set(members)
    if ungrouped:
        groups["Other"] = sorted(ungrouped)

    return {"dates": dates, "indicators": indicators, "groups": groups}


# ── 3. macro_us_hist ──────────────────────────────────────────────────────────

def build_macro_us() -> dict:
    # rows 0-7 = metadata, row 8 = header, row 9+ = data
    meta_raw = pd.read_csv(MACRO_US, header=None, nrows=8, low_memory=False)
    df       = pd.read_csv(MACRO_US, skiprows=8, low_memory=False)
    if "row_id" in df.columns:
        df = df.drop(columns=["row_id"])

    # build per-column metadata from meta_raw
    # col 0 = row label, col 1 = label name, col 2+ = values per series
    meta_labels = meta_raw.iloc[:, 1].tolist()   # ['Series ID','Source','Name',...]
    col_headers = df.columns.tolist()             # includes Date

    series_meta = {}
    n_data_cols = len(col_headers) - 1           # minus Date
    for ci in range(n_data_cols):
        raw_vals = meta_raw.iloc[:, ci + 2].tolist()   # +2: skip col0 (NaN) and col1 (label)
        m = {label: str(v).strip() for label, v in zip(meta_labels, raw_vals)}
        series_id = m.get("Series ID", col_headers[ci + 1])
        series_meta[series_id] = m

    dates, df = _parse_date_col(df)

    series = {}
    for col in df.columns:
        col_s  = str(col).strip()
        vals   = _series_to_list(df[col])
        first, last = _date_range(dates, vals)
        series[col_s] = {
            "meta":       series_meta.get(col_s, {"Series ID": col_s}),
            "values":     vals,
            "first_date": first,
            "last_date":  last,
        }

    return {"dates": dates, "series": series}


# ── 4. macro_intl_hist ────────────────────────────────────────────────────────

def build_macro_intl() -> dict:
    meta_raw = pd.read_csv(MACRO_INTL, header=None, nrows=8, low_memory=False)
    df       = pd.read_csv(MACRO_INTL, skiprows=8, low_memory=False)
    if "row_id" in df.columns:
        df = df.drop(columns=["row_id"])

    meta_labels = meta_raw.iloc[:, 1].tolist()
    col_headers = df.columns.tolist()

    series_meta = {}
    n_data_cols = len(col_headers) - 1
    for ci in range(n_data_cols):
        raw_vals = meta_raw.iloc[:, ci + 2].tolist()
        m = {label: str(v).strip() for label, v in zip(meta_labels, raw_vals)}
        col_id = m.get("Column ID", col_headers[ci + 1])
        series_meta[col_id] = m

    dates, df = _parse_date_col(df)

    series = {}
    for col in df.columns:
        col_s  = str(col).strip()
        vals   = _series_to_list(df[col])
        first, last = _date_range(dates, vals)
        series[col_s] = {
            "meta":       series_meta.get(col_s, {"Column ID": col_s}),
            "values":     vals,
            "first_date": first,
            "last_date":  last,
        }

    return {"dates": dates, "series": series}


# ── 5. market_data_comp_hist ──────────────────────────────────────────────────

def build_market_comp() -> dict:
    # rows 0-10 = metadata, row 11 = headers, row 12+ = data
    meta_raw = pd.read_csv(MKT_COMP, header=None, nrows=11, low_memory=False)
    df       = pd.read_csv(MKT_COMP, skiprows=11, low_memory=False)
    if "row_id" in df.columns:
        df = df.drop(columns=["row_id"])

    meta_labels = meta_raw.iloc[:, 1].tolist()
    # ['Ticker ID','Variant','Source','Name','Broad Asset Class','Region',
    #  'Sub-Category','Currency','Units','Frequency','Last Updated']
    col_headers = df.columns.tolist()  # includes Date

    series_meta = {}
    n_data_cols = len(col_headers) - 1
    for ci in range(n_data_cols):
        raw_vals = meta_raw.iloc[:, ci + 2].tolist()
        m = {label: str(v).strip() for label, v in zip(meta_labels, raw_vals)}
        col_key = col_headers[ci + 1]   # e.g. "IWDA.L_Local"
        series_meta[col_key] = m

    dates, df = _parse_date_col(df)

    # Build groups by Broad Asset Class
    groups: dict[str, list] = {}
    series: dict = {}

    for col in df.columns:
        col_s = str(col).strip()
        m     = series_meta.get(col_s, {})
        vals  = _series_to_list(df[col])
        first, last = _date_range(dates, vals)
        asset_class = m.get("Broad Asset Class", "Other")
        groups.setdefault(asset_class, []).append(col_s)
        series[col_s] = {
            "meta":       m,
            "values":     vals,
            "first_date": first,
            "last_date":  last,
        }

    return {"dates": dates, "series": series, "groups": groups}


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    print("Loading indicator metadata...")
    ind_meta = load_indicator_meta()

    print("Building macro_market payload...")
    macro_mkt_data = build_macro_market(ind_meta)

    print("Building macro_us payload...")
    macro_us_data = build_macro_us()

    print("Building macro_intl payload...")
    macro_intl_data = build_macro_intl()

    print("Building market_comp payload...")
    mkt_comp_data = build_market_comp()

    # ── write main payload ────────────────────────────────────────────────────
    main_payload = {
        "macro_market": macro_mkt_data,
        "macro_us":     macro_us_data,
        "macro_intl":   macro_intl_data,
    }
    main_path = DOCS / "payload_main.json"
    print(f"\nWriting {main_path} ...")
    with open(main_path, "w", encoding="utf-8") as f:
        json.dump(main_payload, f, separators=(",", ":"), ensure_ascii=False)
    size_mb = main_path.stat().st_size / 1e6
    print(f"  → {size_mb:.2f} MB")

    # ── write market companion payload ────────────────────────────────────────
    mkt_path = DOCS / "payload_mkt.json"
    print(f"\nWriting {mkt_path} ...")
    with open(mkt_path, "w", encoding="utf-8") as f:
        json.dump(mkt_comp_data, f, separators=(",", ":"), ensure_ascii=False)
    size_mb = mkt_path.stat().st_size / 1e6
    print(f"  → {size_mb:.2f} MB")

    # ── build HTML ────────────────────────────────────────────────────────────
    print("\nGenerating indicator_explorer.html ...")
    build_html_file(main_payload, mkt_comp_data)

    # ── summary ───────────────────────────────────────────────────────────────
    print("\n── Summary ──────────────────────────────────────────────────────")
    print(f"macro_market indicators: {len(macro_mkt_data['indicators'])} "
          f"across {len(macro_mkt_data['groups'])} groups")
    print(f"  groups: {list(macro_mkt_data['groups'].keys())}")
    print(f"macro_us series:   {len(macro_us_data['series'])}")
    print(f"macro_intl series: {len(macro_intl_data['series'])}")
    print(f"market_comp series: {len(mkt_comp_data['series'])} "
          f"across {len(mkt_comp_data['groups'])} asset classes")
    print(f"  classes: {list(mkt_comp_data['groups'].keys())}")
    print(f"\nindicator_explorer.html : {(DOCS / 'indicator_explorer.html').stat().st_size / 1e6:.2f} MB")


# ══════════════════════════════════════════════════════════════════════════════
# HTML TEMPLATE
# Placeholders replaced by main():
#   __MAIN_DATA_JSON__   → serialised main payload  (macro_market/us/intl)
#   __MKT_DATA_JSON__    → serialised market-comp payload
# ══════════════════════════════════════════════════════════════════════════════

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Macro Indicator Explorer</title>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js" charset="utf-8"></script>
<style>
/* ── reset & base ── */
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  font-size:13px;background:#0d1117;color:#c9d1d9;height:100vh;overflow:hidden}
::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track{background:#161b22}
::-webkit-scrollbar-thumb{background:#30363d;border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:#484f58}

/* ── layout ── */
#app{display:flex;height:100vh;width:100vw}

/* ── sidebar ── */
#sidebar{
  width:320px;min-width:320px;max-width:320px;
  height:100vh;display:flex;flex-direction:column;
  background:#161b22;border-right:1px solid #30363d;
  overflow:hidden;flex-shrink:0
}
#sidebar-header{
  padding:12px 14px 8px;border-bottom:1px solid #30363d;
  flex-shrink:0
}
#sidebar-header h1{
  font-size:14px;font-weight:600;color:#f0f6fc;
  letter-spacing:.02em;margin-bottom:8px
}
#search-box{
  width:100%;padding:6px 10px;border-radius:6px;
  border:1px solid #30363d;background:#0d1117;
  color:#c9d1d9;font-size:12px;outline:none
}
#search-box:focus{border-color:#58a6ff}
#search-box::placeholder{color:#484f58}

/* ── date controls ── */
#date-controls{
  display:flex;align-items:center;gap:6px;
  padding:8px 14px;border-bottom:1px solid #30363d;
  flex-shrink:0;flex-wrap:wrap
}
#date-controls label{font-size:11px;color:#8b949e;white-space:nowrap}
.date-input{
  width:96px;padding:4px 7px;border-radius:5px;
  border:1px solid #30363d;background:#0d1117;
  color:#c9d1d9;font-size:11px;outline:none
}
.date-input:focus{border-color:#58a6ff}
#btn-apply-dates{
  padding:4px 10px;border-radius:5px;border:none;
  background:#238636;color:#fff;font-size:11px;cursor:pointer
}
#btn-apply-dates:hover{background:#2ea043}

/* ── sidebar tree ── */
#sidebar-tree{
  flex:1;overflow-y:auto;padding:4px 0 12px
}

/* ── source-level sections (top tier) ── */
.src-section{border-bottom:1px solid #21262d}
.src-header{
  display:flex;align-items:center;gap:6px;
  padding:8px 14px;cursor:pointer;user-select:none;
  background:#161b22;position:sticky;top:0;z-index:2
}
.src-header:hover{background:#1c2128}
.src-arrow{font-size:10px;color:#58a6ff;transition:transform .15s;flex-shrink:0}
.src-arrow.open{transform:rotate(90deg)}
.src-title{font-size:12px;font-weight:600;color:#f0f6fc;flex:1}
.src-count{font-size:10px;color:#8b949e;background:#21262d;
  padding:1px 5px;border-radius:10px;flex-shrink:0}
.src-body{display:none}
.src-body.open{display:block}

/* ── group sections (second tier, inside macro-market) ── */
.grp-section{padding-left:0}
.grp-header{
  display:flex;align-items:center;gap:6px;
  padding:5px 14px 5px 22px;cursor:pointer;user-select:none
}
.grp-header:hover{background:#1c2128}
.grp-arrow{font-size:9px;color:#484f58;transition:transform .15s;flex-shrink:0}
.grp-arrow.open{transform:rotate(90deg)}
.grp-title{font-size:11px;font-weight:600;color:#8b949e;flex:1;
  text-transform:uppercase;letter-spacing:.05em}
.grp-count{font-size:10px;color:#484f58;flex-shrink:0}
.grp-body{display:none}
.grp-body.open{display:block}

/* ── asset class sections (second tier, inside market data) ── */
.ac-section{}
.ac-header{
  display:flex;align-items:center;gap:6px;
  padding:5px 14px 5px 22px;cursor:pointer;user-select:none
}
.ac-header:hover{background:#1c2128}
.ac-arrow{font-size:9px;color:#484f58;transition:transform .15s;flex-shrink:0}
.ac-arrow.open{transform:rotate(90deg)}
.ac-title{font-size:11px;font-weight:600;color:#8b949e;flex:1;
  text-transform:uppercase;letter-spacing:.05em}
.ac-count{font-size:10px;color:#484f58;flex-shrink:0}
.ac-body{display:none}
.ac-body.open{display:block}

/* ── variant toggle (Local / USD) ── */
.variant-toggle{
  display:flex;gap:0;margin:4px 14px 4px 22px;
  border:1px solid #30363d;border-radius:5px;overflow:hidden;width:fit-content
}
.variant-btn{
  padding:3px 10px;font-size:10px;cursor:pointer;
  background:#0d1117;color:#8b949e;border:none;user-select:none
}
.variant-btn.active{background:#21262d;color:#58a6ff;font-weight:600}

/* ── series items ── */
.series-item{
  display:flex;align-items:center;gap:7px;
  padding:4px 14px 4px 28px;cursor:pointer
}
.series-item:hover{background:#1c2128}
.series-item.hidden{display:none}
.series-cb{
  width:13px;height:13px;accent-color:#58a6ff;
  flex-shrink:0;cursor:pointer
}
.series-label{flex:1;overflow:hidden}
.series-id{
  font-size:11px;font-weight:600;color:#f0f6fc;
  font-family:"SFMono-Regular",Consolas,monospace
}
.series-name{
  font-size:10px;color:#8b949e;white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis;max-width:220px
}
.series-leading{
  font-size:9px;color:#d29922;background:#272115;
  border:1px solid #3d2f0d;border-radius:3px;
  padding:0 4px;flex-shrink:0
}
.series-dates{
  font-size:9px;color:#484f58;white-space:nowrap;flex-shrink:0;
  font-family:"SFMono-Regular",Consolas,monospace
}
.series-dates.warn{color:#d29922}
.series-dates.error{color:#f85149}

/* ── date coverage warning panel ── */
#coverage-warn{
  margin:6px 14px 0;padding:6px 9px;border-radius:5px;
  background:#272115;border:1px solid #3d2f0d;
  font-size:11px;color:#d29922;display:none;line-height:1.5
}
#coverage-warn.has-warn{display:block}
#coverage-warn ul{margin:4px 0 0 14px;padding:0}
#coverage-warn li{font-size:10px;color:#c9d1d9;font-family:"SFMono-Regular",Consolas,monospace}

/* ── main content ── */
#main-content{
  flex:1;display:flex;flex-direction:column;
  min-width:0;height:100vh;overflow:hidden
}

/* ── toolbar ── */
#toolbar{
  display:flex;align-items:center;gap:8px;padding:8px 16px;
  border-bottom:1px solid #30363d;background:#161b22;flex-shrink:0
}
#chart-title{
  font-size:13px;color:#8b949e;font-style:italic;flex:1;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap
}
#btn-clear{
  padding:4px 10px;border-radius:5px;border:1px solid #30363d;
  background:transparent;color:#8b949e;font-size:11px;cursor:pointer
}
#btn-clear:hover{border-color:#f85149;color:#f85149}

/* ── chart area ── */
#chart-wrap{
  flex:1;min-height:0;position:relative;background:#0d1117
}
#chart-placeholder{
  position:absolute;inset:0;display:flex;flex-direction:column;
  align-items:center;justify-content:center;gap:8px;color:#484f58
}
#chart-placeholder svg{opacity:.3}
#chart-placeholder p{font-size:13px}
#plotly-chart{width:100%;height:100%;display:none}

/* ── legend panel ── */
#legend-panel{
  border-top:1px solid #30363d;background:#161b22;
  padding:0;max-height:160px;overflow-y:auto;flex-shrink:0;display:none
}
#legend-panel-inner{
  display:flex;flex-direction:column;gap:0
}
.legend-row{
  display:flex;align-items:center;gap:8px;
  padding:6px 12px;border-bottom:1px solid #21262d
}
.legend-row:last-child{border-bottom:none}
.legend-row-id{
  font-size:11px;font-weight:600;color:#f0f6fc;
  font-family:"SFMono-Regular",Consolas,monospace;min-width:100px
}
.legend-row-name{font-size:10px;color:#8b949e;flex:1;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
/* colour/style controls added in Step 4 */

/* ── regime strip ── */
#regime-strip-wrap{
  border-top:1px solid #30363d;flex-shrink:0;display:none
}
/* expanded in Step 5 */

/* ── status bar ── */
#statusbar{
  padding:3px 14px;font-size:10px;color:#484f58;
  background:#161b22;border-top:1px solid #21262d;flex-shrink:0
}
</style>
</head>
<body>
<div id="app">

<!-- ════════════════════════ SIDEBAR ════════════════════════ -->
<div id="sidebar">
  <div id="sidebar-header">
    <h1>Macro Indicator Explorer</h1>
    <input id="search-box" type="text" placeholder="Search series…" autocomplete="off">
  </div>
  <div id="date-controls">
    <label>From</label>
    <input class="date-input" id="date-from" type="text" placeholder="2015-01-01">
    <label>To</label>
    <input class="date-input" id="date-to" type="text" placeholder="today">
    <button id="btn-apply-dates">Apply</button>
  </div>
  <div id="coverage-warn"></div>
  <div id="sidebar-tree"><!-- populated by JS --></div>
</div>

<!-- ════════════════════════ MAIN ════════════════════════ -->
<div id="main-content">
  <div id="toolbar">
    <span id="chart-title">Select indicators from the sidebar to begin</span>
    <button id="btn-clear">Clear all</button>
  </div>
  <div id="chart-wrap">
    <div id="chart-placeholder">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none"
           stroke="#58a6ff" stroke-width="1.5">
        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
      </svg>
      <p>Select indicators from the sidebar to plot</p>
    </div>
    <div id="plotly-chart"></div>
  </div>
  <div id="legend-panel"><div id="legend-panel-inner"></div></div>
  <div id="regime-strip-wrap"></div>
  <div id="statusbar" id="statusbar">Ready</div>
</div>

</div><!-- #app -->

<!-- ══════════════════════════════════════════════════════════
     EMBEDDED DATA
     ══════════════════════════════════════════════════════════ -->
<script>
const MAIN_DATA = __MAIN_DATA_JSON__;
</script>
<script>
const MKT_DATA = __MKT_DATA_JSON__;
</script>

<!-- ══════════════════════════════════════════════════════════
     APPLICATION
     ══════════════════════════════════════════════════════════ -->
<script>
'use strict';

// ── state ──────────────────────────────────────────────────────────────────
const STATE = {
  active: [],          // [{source,key,indId?,metric?,label,color,style,width,axis}]
  dateFrom: null,
  dateTo:   null,
  mktVariant: 'Local', // 'Local' | 'USD'
  searchQuery: '',
};

// ── colour palette for auto-assignment ────────────────────────────────────
const PALETTE = [
  '#58a6ff','#3fb950','#f78166','#d2a8ff','#ffa657',
  '#79c0ff','#56d364','#ff7b72','#bc8cff','#e3b341',
  '#388bfd','#2ea043','#da3633','#8957e5','#bb8009',
];
let _paletteIdx = 0;
function nextColor(){ return PALETTE[_paletteIdx++ % PALETTE.length]; }

// ── helpers ────────────────────────────────────────────────────────────────
function el(tag, cls, text){
  const e = document.createElement(tag);
  if(cls)  e.className = cls;
  if(text !== undefined) e.textContent = text;
  return e;
}

function makeArrow(cls){ return el('span', cls, '▶'); }

function toggleSection(arrowEl, bodyEl){
  const open = bodyEl.classList.toggle('open');
  arrowEl.classList.toggle('open', open);
}

// ── sidebar building ───────────────────────────────────────────────────────

function buildSidebar(){
  const tree = document.getElementById('sidebar-tree');
  tree.innerHTML = '';

  // 1. Macro Market Indicators
  tree.appendChild(buildMacroMarketSection());
  // 2. US Economic Data (FRED)
  tree.appendChild(buildSimpleSection(
    'US Economic Data (FRED)',
    MAIN_DATA.macro_us.series,
    MAIN_DATA.macro_us.dates,
    'macro_us',
    s => s['Name'] || s['Series ID'] || '',
  ));
  // 3. International Data
  tree.appendChild(buildSimpleSection(
    'International Data',
    MAIN_DATA.macro_intl.series,
    MAIN_DATA.macro_intl.dates,
    'macro_intl',
    s => (s['Country'] ? s['Country'] + ' — ' : '') + (s['Indicator'] || s['Column ID'] || ''),
  ));
  // 4. Market Data
  tree.appendChild(buildMarketSection());
}

// ── Macro Market section ───────────────────────────────────────────────────
function buildMacroMarketSection(){
  const mm = MAIN_DATA.macro_market;
  const total = Object.keys(mm.indicators).length;

  const wrap = el('div','src-section');
  const hdr  = el('div','src-header');
  const arr  = makeArrow('src-arrow open');
  const ttl  = el('span','src-title','Macro Market Indicators');
  const cnt  = el('span','src-count', total);
  hdr.append(arr, ttl, cnt);
  wrap.appendChild(hdr);

  const body = el('div','src-body open');

  Object.entries(mm.groups).forEach(([groupName, ids]) => {
    body.appendChild(buildGroupSection(groupName, ids, mm.indicators));
  });

  hdr.addEventListener('click', () => toggleSection(arr, body));
  wrap.appendChild(body);
  return wrap;
}

function buildGroupSection(groupName, ids, indicators){
  const wrap = el('div','grp-section');
  const hdr  = el('div','grp-header');
  const arr  = makeArrow('grp-arrow open');
  const ttl  = el('span','grp-title', groupName);
  const cnt  = el('span','grp-count', ids.length);
  hdr.append(arr, ttl, cnt);
  wrap.appendChild(hdr);

  const body = el('div','grp-body open');
  ids.forEach(indId => {
    const ind = indicators[indId];
    if(!ind) return;
    const meta = ind.meta || {};
    const shortName = meta.category || indId;
    body.appendChild(makeSeriesItem({
      source: 'macro_market',
      key:    indId,
      id:     indId,
      name:   shortName,
      leading: meta.leading || false,
    }));
  });

  hdr.addEventListener('click', () => toggleSection(arr, body));
  wrap.appendChild(body);
  return wrap;
}

// ── Simple (FRED / intl) section ───────────────────────────────────────────
function buildSimpleSection(title, seriesMap, dates, source, nameFn){
  const keys  = Object.keys(seriesMap);
  const wrap  = el('div','src-section');
  const hdr   = el('div','src-header');
  const arr   = makeArrow('src-arrow');
  const ttl   = el('span','src-title', title);
  const cnt   = el('span','src-count', keys.length);
  hdr.append(arr, ttl, cnt);
  wrap.appendChild(hdr);

  const body = el('div','src-body');
  keys.forEach(key => {
    const s = seriesMap[key];
    const meta = s.meta || {};
    body.appendChild(makeSeriesItem({
      source,
      key,
      id:   key,
      name: nameFn(meta),
    }));
  });

  hdr.addEventListener('click', () => toggleSection(arr, body));
  wrap.appendChild(body);
  return wrap;
}

// ── Market Data section ────────────────────────────────────────────────────
function buildMarketSection(){
  const mkt   = MKT_DATA;
  const total = Object.keys(mkt.series).length;

  const wrap = el('div','src-section');
  const hdr  = el('div','src-header');
  const arr  = makeArrow('src-arrow');
  const ttl  = el('span','src-title','Market Data');
  const cnt  = el('span','src-count', total);
  hdr.append(arr, ttl, cnt);
  wrap.appendChild(hdr);

  const body = el('div','src-body');

  // variant toggle (Local / USD)
  const toggle = el('div','variant-toggle');
  ['Local','USD'].forEach(v => {
    const btn = el('button','variant-btn' + (v === STATE.mktVariant ? ' active' : ''), v);
    btn.addEventListener('click', e => {
      e.stopPropagation();
      STATE.mktVariant = v;
      document.querySelectorAll('.variant-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      refreshMarketItems();
    });
    toggle.appendChild(btn);
  });
  body.appendChild(toggle);

  // asset class sub-groups
  Object.entries(mkt.groups).forEach(([acName, keys]) => {
    body.appendChild(buildAssetClassSection(acName, keys, mkt.series));
  });

  hdr.addEventListener('click', () => toggleSection(arr, body));
  wrap.appendChild(body);
  return wrap;
}

function buildAssetClassSection(acName, allKeys, seriesMap){
  const wrap = el('div','ac-section');
  const hdr  = el('div','ac-header');
  const arr  = makeArrow('ac-arrow');
  const ttl  = el('span','ac-title', acName);
  // count shown = depends on variant, but just show total/2 since 50/50
  const cnt  = el('span','ac-count', Math.ceil(allKeys.length / 2));
  hdr.append(arr, ttl, cnt);
  wrap.appendChild(hdr);

  const body = el('div','ac-body');
  body.dataset.acname = acName;

  allKeys.forEach(key => {
    const s = seriesMap[key];
    if(!s) return;
    const meta  = s.meta || {};
    const variant = (meta['Variant'] || '').trim();
    const item = makeSeriesItem({
      source:  'market_comp',
      key,
      id:      key,
      name:    meta['Name'] || key,
      variant,
    });
    item.dataset.variant = variant;
    // show/hide based on current variant state
    if(variant && variant !== STATE.mktVariant) item.classList.add('hidden');
    body.appendChild(item);
  });

  hdr.addEventListener('click', () => toggleSection(arr, body));
  wrap.appendChild(body);
  return wrap;
}

function refreshMarketItems(){
  document.querySelectorAll('.series-item[data-variant]').forEach(item => {
    const v = item.dataset.variant;
    if(!v) return;
    item.classList.toggle('hidden', v !== STATE.mktVariant);
    // re-apply search if active
    if(STATE.searchQuery && !item.classList.contains('hidden')){
      const text = item.textContent.toLowerCase();
      item.classList.toggle('hidden', !text.includes(STATE.searchQuery));
    }
  });
}

// ── Series item factory ────────────────────────────────────────────────────
function getSeriesDateRange(source, key){
  if(source === 'macro_market'){
    const ind = MAIN_DATA.macro_market.indicators[key];
    return ind ? {first: ind.first_date, last: ind.last_date} : {};
  }
  if(source === 'macro_us'){
    const s = MAIN_DATA.macro_us.series[key];
    return s ? {first: s.first_date, last: s.last_date} : {};
  }
  if(source === 'macro_intl'){
    const s = MAIN_DATA.macro_intl.series[key];
    return s ? {first: s.first_date, last: s.last_date} : {};
  }
  if(source === 'market_comp'){
    const s = MKT_DATA.series[key];
    return s ? {first: s.first_date, last: s.last_date} : {};
  }
  return {};
}

function makeSeriesItem({source, key, id, name, leading, variant}){
  const {first, last} = getSeriesDateRange(source, key);

  const wrap = el('div','series-item');
  wrap.dataset.source  = source;
  wrap.dataset.key     = key;
  if(variant)    wrap.dataset.variant   = variant;
  if(first)      wrap.dataset.firstDate = first;
  if(last)       wrap.dataset.lastDate  = last;

  const cb = document.createElement('input');
  cb.type  = 'checkbox';
  cb.className = 'series-cb';
  cb.dataset.source = source;
  cb.dataset.key    = key;

  const labelWrap = el('div','series-label');
  const idSpan    = el('span','series-id', id);
  const nameSpan  = el('span','series-name', name);
  labelWrap.append(idSpan, nameSpan);

  wrap.append(cb, labelWrap);

  if(leading){
    const badge = el('span','series-leading','LEADING');
    wrap.appendChild(badge);
  }

  // date range badge
  if(first){
    const yr1 = first.slice(0,4);
    const yr2 = last  ? last.slice(0,4) : '…';
    const dBadge = el('span','series-dates', yr1 + '–' + yr2);
    dBadge.title = (first || '?') + ' → ' + (last || '?');
    wrap.appendChild(dBadge);
  }

  cb.addEventListener('change', () => onSeriesChecked(cb.checked, {source, key, id, name, first_date: first, last_date: last}));
  wrap.addEventListener('click', e => {
    if(e.target !== cb){ cb.checked = !cb.checked; cb.dispatchEvent(new Event('change')); }
  });

  return wrap;
}

// ── Search ─────────────────────────────────────────────────────────────────
document.getElementById('search-box').addEventListener('input', function(){
  const q = this.value.toLowerCase().trim();
  STATE.searchQuery = q;

  document.querySelectorAll('.series-item').forEach(item => {
    if(item.dataset.variant && item.dataset.variant !== STATE.mktVariant){
      item.classList.add('hidden'); return;
    }
    if(!q){ item.classList.remove('hidden'); return; }
    const text = item.textContent.toLowerCase();
    item.classList.toggle('hidden', !text.includes(q));
  });

  // hide empty group bodies (no visible children)
  document.querySelectorAll('.grp-body,.ac-body').forEach(body => {
    const anyVisible = Array.from(body.querySelectorAll('.series-item'))
      .some(i => !i.classList.contains('hidden'));
    body.closest('.grp-section,.ac-section').style.display = anyVisible ? '' : 'none';
  });

  // auto-open src sections that have matches
  if(q){
    document.querySelectorAll('.src-body').forEach(body => {
      const anyVisible = Array.from(body.querySelectorAll('.series-item'))
        .some(i => !i.classList.contains('hidden'));
      if(anyVisible){ body.classList.add('open');
        body.previousElementSibling.querySelector('.src-arrow').classList.add('open'); }
    });
  } else {
    // restore hidden groups
    document.querySelectorAll('.grp-section,.ac-section').forEach(s => s.style.display = '');
  }
});

// ── Date controls ──────────────────────────────────────────────────────────
(function initDates(){
  // default: last 10 years
  const now   = new Date();
  const tenYr = new Date(now);
  tenYr.setFullYear(tenYr.getFullYear() - 10);
  const fmt = d => d.toISOString().slice(0,10);
  document.getElementById('date-from').value = fmt(tenYr);
  document.getElementById('date-to').value   = fmt(now);
  STATE.dateFrom = fmt(tenYr);
  STATE.dateTo   = fmt(now);
})();

document.getElementById('btn-apply-dates').addEventListener('click', function(){
  const from = document.getElementById('date-from').value.trim();
  const to   = document.getElementById('date-to').value.trim();
  const dateRe = /^\d{4}-\d{2}-\d{2}$/;
  if(from && !dateRe.test(from)){ setStatus('Invalid From date (use YYYY-MM-DD)','error'); return; }
  if(to   && !dateRe.test(to))  { setStatus('Invalid To date (use YYYY-MM-DD)',  'error'); return; }
  STATE.dateFrom = from || null;
  STATE.dateTo   = to   || null;
  checkDateCoverage();
  setStatus('Date range updated — chart will refresh on next series change');
  if(STATE.active.length) renderChart();
});

// ── Clear all ──────────────────────────────────────────────────────────────
document.getElementById('btn-clear').addEventListener('click', function(){
  STATE.active = [];
  _paletteIdx  = 0;
  document.querySelectorAll('.series-cb').forEach(cb => cb.checked = false);
  updateLegendPanel();
  updateChartTitle();
  document.getElementById('chart-placeholder').style.display = 'flex';
  document.getElementById('plotly-chart').style.display = 'none';
  document.getElementById('legend-panel').style.display = 'none';
  if(typeof Plotly !== 'undefined')
    Plotly.purge(document.getElementById('plotly-chart'));
  setStatus('Ready');
});

// ── Date coverage warning ──────────────────────────────────────────────────
function checkDateCoverage(){
  const warn  = document.getElementById('coverage-warn');
  const from  = STATE.dateFrom;
  const to    = STATE.dateTo;
  const issues = [];

  STATE.active.forEach(s => {
    const msgs = [];
    if(s.first_date && from && s.first_date > from)
      msgs.push('starts ' + s.first_date + ' (after your From date)');
    if(s.last_date  && to   && s.last_date  < to)
      msgs.push('ends '   + s.last_date  + ' (before your To date)');
    if(msgs.length) issues.push({id: s.id, msgs});
  });

  // also update date badges in sidebar to highlight out-of-range series
  document.querySelectorAll('.series-dates').forEach(badge => {
    const item  = badge.closest('.series-item');
    if(!item) return;
    const first = item.dataset.firstDate;
    const last  = item.dataset.lastDate;
    badge.classList.remove('warn','error');
    if(first && from && first > from) badge.classList.add('warn');
    if(last  && to   && last  < to)   badge.classList.add('warn');
  });

  if(!issues.length){ warn.className = 'coverage-warn'; warn.innerHTML = ''; return; }

  warn.className = 'has-warn';
  let html = '⚠ Data gap for ' + issues.length + ' selected series:<ul>';
  issues.forEach(({id, msgs}) => {
    html += '<li>' + id + ' — ' + msgs.join('; ') + '</li>';
  });
  html += '</ul>';
  warn.innerHTML = html;
}

// ── Series checked callback (chart render wired in Step 3) ─────────────────
function onSeriesChecked(checked, info){
  if(checked){
    // avoid duplicates
    if(STATE.active.find(a => a.source === info.source && a.key === info.key)) return;
    STATE.active.push({
      ...info,
      color: nextColor(),
      style: 'solid',
      width: 1.5,
      axis:  (info.source === 'macro_market') ? 'left' : 'right',
      metric: (info.source === 'macro_market') ? 'zscore' : 'raw',
    });
  } else {
    STATE.active = STATE.active.filter(a => !(a.source === info.source && a.key === info.key));
  }
  checkDateCoverage();
  updateLegendPanel();
  updateChartTitle();
  renderChart();   // no-op until Step 3 wires this up
}

// ── Legend panel (styling controls wired in Step 4) ───────────────────────
function updateLegendPanel(){
  const panel = document.getElementById('legend-panel');
  const inner = document.getElementById('legend-panel-inner');
  if(!STATE.active.length){ panel.style.display = 'none'; return; }
  panel.style.display = 'block';
  inner.innerHTML = '';
  STATE.active.forEach(s => {
    const row   = el('div','legend-row');
    const idEl  = el('span','legend-row-id', s.id);
    const nmEl  = el('span','legend-row-name', s.name || '');
    idEl.style.color = s.color;
    row.append(idEl, nmEl);
    inner.appendChild(row);
  });
}

// ── Chart title ────────────────────────────────────────────────────────────
function updateChartTitle(){
  const t = document.getElementById('chart-title');
  t.textContent = STATE.active.length
    ? STATE.active.map(s => s.id).join('  ·  ')
    : 'Select indicators from the sidebar to begin';
}

// ── Chart render stub (full implementation in Step 3) ─────────────────────
function renderChart(){
  // stub — replaced in Step 3
  if(!STATE.active.length) return;
  setStatus(`${STATE.active.length} series selected — chart rendering coming in Step 3`);
}

// ── Status bar ─────────────────────────────────────────────────────────────
function setStatus(msg, level){
  const sb = document.getElementById('statusbar');
  sb.textContent = msg;
  sb.style.color = level === 'error' ? '#f85149' : '#484f58';
}

// ── Boot ───────────────────────────────────────────────────────────────────
buildSidebar();
setStatus('Ready — ' + Object.keys(MAIN_DATA.macro_market.indicators).length
  + ' indicators · ' + Object.keys(MAIN_DATA.macro_us.series).length
  + ' FRED series · ' + Object.keys(MAIN_DATA.macro_intl.series).length
  + ' intl series · ' + Object.keys(MKT_DATA.series).length + ' market series');
</script>
</body>
</html>
"""


# ── HTML generation ───────────────────────────────────────────────────────────

def build_html_file(main_payload: dict, mkt_payload: dict) -> None:
    html_path = DOCS / "indicator_explorer.html"
    js_path   = DOCS / "indicator_explorer_mkt.js"

    main_json = json.dumps(main_payload, separators=(",", ":"), ensure_ascii=False)
    mkt_json  = json.dumps(mkt_payload,  separators=(",", ":"), ensure_ascii=False)

    html = HTML_TEMPLATE
    html = html.replace("__MAIN_DATA_JSON__", main_json)
    html = html.replace("__MKT_DATA_JSON__",  mkt_json)

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    size_mb = html_path.stat().st_size / 1e6
    print(f"\nWrote {html_path}  ({size_mb:.2f} MB)")


if __name__ == "__main__":
    main()
