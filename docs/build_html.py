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
import sys
import pandas as pd
from pathlib import Path

# ── paths ─────────────────────────────────────────────────────────────────────
ROOT   = Path(__file__).parent.parent
DATA   = ROOT / "data"
DOCS   = ROOT / "docs"

# Allow importing library_utils from the repo root
sys.path.insert(0, str(ROOT))
from library_utils import INDICATOR_GROUP_ORDER, INDICATOR_SUB_GROUP_ORDER

MACRO_MKT   = DATA / "macro_market_hist.csv"
MACRO_US    = DATA / "macro_us_hist.csv"
MACRO_INTL  = DATA / "macro_intl_hist.csv"
MKT_COMP    = DATA / "market_data_comp_hist.csv"
IND_LIB     = DATA / "macro_indicator_library.csv"

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
    """Load indicator metadata from macro_indicator_library.csv.

    Returns dict keyed by indicator ID with metadata, group, sub_group,
    and naturally_leading flag — all driven by the CSV (source of truth).
    """
    lib = pd.read_csv(IND_LIB)
    meta = {}
    for _, row in lib.iterrows():
        ind_id = str(row.get("id", "")).strip()
        if not ind_id:
            continue
        meta[ind_id] = {
            "category":    str(row.get("category", "")).strip(),
            "group":       str(row.get("group", "")).strip(),
            "sub_group":   str(row.get("sub_group", "")).strip(),
            "formula":     str(row.get("formula_using_library_names", "")).strip(),
            "interp":      str(row.get("economic_interpretation", "")).strip(),
            "regime_desc": str(row.get("regime_classification", "")).strip(),
            "leading":     str(row.get("naturally_leading", "")).strip().upper() == "TRUE",
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
        for suffix in ("_fwd_regime", "_raw", "_zscore", "_regime"):
            if col.endswith(suffix):
                present_ids.add(col[: -len(suffix)])
                break

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

    # build groups and sub_groups from CSV metadata, sorted by library_utils order
    raw_groups: dict[str, dict[str, list]] = {}  # group → sub_group → [ids]
    ungrouped = set(present_ids)
    for ind_id in present_ids:
        m = ind_meta.get(ind_id, {})
        g  = m.get("group", "")
        sg = m.get("sub_group", "")
        if g:
            raw_groups.setdefault(g, {}).setdefault(sg, []).append(ind_id)
            ungrouped.discard(ind_id)

    # sort groups by INDICATOR_GROUP_ORDER, sub_groups by INDICATOR_SUB_GROUP_ORDER
    groups = {}
    for g in sorted(raw_groups,
                    key=lambda g: INDICATOR_GROUP_ORDER.get(g, 99)):
        sub_groups = {}
        for sg in sorted(raw_groups[g],
                         key=lambda sg: INDICATOR_SUB_GROUP_ORDER.get(sg, 99)):
            sub_groups[sg] = sorted(raw_groups[g][sg])
        groups[g] = sub_groups

    if ungrouped:
        groups["Other"] = {"Ungrouped": sorted(ungrouped)}

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

    # ── assemble payloads ─────────────────────────────────────────────────────
    main_payload = {
        "macro_market": macro_mkt_data,
        "macro_us":     macro_us_data,
        "macro_intl":   macro_intl_data,
    }

    # ── write output files ────────────────────────────────────────────────────
    print("\nWriting output files...")
    build_html_file(main_payload, mkt_comp_data)

    # ── summary ───────────────────────────────────────────────────────────────
    print("\n── Summary ──────────────────────────────────────────────────────")
    print(f"macro_market : {len(macro_mkt_data['indicators'])} indicators "
          f"across {len(macro_mkt_data['groups'])} groups")
    print(f"macro_us     : {len(macro_us_data['series'])} FRED series")
    print(f"macro_intl   : {len(macro_intl_data['series'])} intl series")
    print(f"market_comp  : {len(mkt_comp_data['series'])} series "
          f"across {len(mkt_comp_data['groups'])} asset classes")
    print(f"  asset classes: {list(mkt_comp_data['groups'].keys())}")
    html_mb = (DOCS / 'indicator_explorer.html').stat().st_size / 1e6
    js_mb   = (DOCS / 'indicator_explorer_mkt.js').stat().st_size / 1e6
    print(f"\nTotal output: {html_mb + js_mb:.2f} MB  "
          f"({html_mb:.2f} MB HTML + {js_mb:.2f} MB companion JS)")


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

/* ── sub-group sections (third tier, inside macro-market groups) ── */
.sgrp-section{padding-left:0}
.sgrp-header{
  display:flex;align-items:center;gap:6px;
  padding:4px 14px 4px 36px;cursor:pointer;user-select:none
}
.sgrp-header:hover{background:#1c2128}
.sgrp-arrow{font-size:8px;color:#484f58;transition:transform .15s;flex-shrink:0}
.sgrp-arrow.open{transform:rotate(90deg)}
.sgrp-title{font-size:10.5px;font-weight:500;color:#768390;flex:1;
  letter-spacing:.03em}
.sgrp-count{font-size:9px;color:#484f58;flex-shrink:0}
.sgrp-body{display:none}
.sgrp-body.open{display:block}
.sgrp-body .series-item{padding-left:48px}

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
  font-size:13px;color:#c9d1d9;font-style:italic;flex:1;
  background:transparent;border:none;outline:none;
  min-width:0;
  border-bottom:1px solid transparent;
  padding:2px 4px;border-radius:3px;
}
#chart-title:hover{border-bottom-color:#30363d}
#chart-title:focus{border-bottom-color:#58a6ff;font-style:normal;color:#f0f6fc}
#btn-clear{
  padding:4px 10px;border-radius:5px;border:1px solid #30363d;
  background:transparent;color:#8b949e;font-size:11px;cursor:pointer
}
#btn-clear:hover{border-color:#f85149;color:#f85149}
/* ── font size controls ── */
#font-controls{
  display:flex;align-items:center;gap:10px;flex-shrink:0
}
.font-ctrl-group{
  display:flex;align-items:center;gap:3px;
  font-size:9px;color:#484f58;white-space:nowrap
}
.font-ctrl-group label{color:#484f58;font-size:9px}
.font-btn{
  width:16px;height:16px;border-radius:3px;border:1px solid #30363d;
  background:transparent;color:#8b949e;font-size:11px;cursor:pointer;
  display:flex;align-items:center;justify-content:center;line-height:1;padding:0
}
.font-btn:hover{border-color:#58a6ff;color:#58a6ff}
.font-val{
  min-width:18px;text-align:center;font-size:9px;
  color:#8b949e;font-family:"SFMono-Regular",Consolas,monospace
}

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

/* ── legend panel — absolute overlay at bottom of chart area ── */
#legend-panel{
  position:absolute;bottom:0;left:0;right:0;z-index:10;
  background:#161b22;
  border-top:1px solid #30363d;
  padding:0;overflow-y:auto;display:none;
  max-height:40vh
}
#legend-panel-header{
  display:flex;align-items:center;justify-content:space-between;
  padding:3px 10px;border-bottom:1px solid #21262d;
  background:#161b22;position:sticky;top:0;z-index:1
}
#legend-panel-title{font-size:9px;color:#484f58;text-transform:uppercase;letter-spacing:.06em}
#btn-detail-toggle{
  font-size:9px;color:#8b949e;background:none;border:1px solid #30363d;
  border-radius:3px;padding:1px 6px;cursor:pointer
}
#btn-detail-toggle:hover{color:#58a6ff;border-color:#58a6ff}
#legend-panel-inner{ display:flex;flex-direction:column;gap:0 }
/* inline regime strip inside legend */
.inline-strip-row{
  display:flex;align-items:center;
  background:#0d1117;padding:2px 0;
  border-top:1px solid #21262d
}
.inline-strip-row .strip-label{color:#484f58}
.inline-strip-row .strip-canvas-wrap{flex:1;position:relative;overflow:hidden}
.inline-strip-row .strip-canvas{display:block;width:100%;height:12px}
.inline-strip-fwd .strip-canvas{height:8px}
.inline-strip-fwd .strip-label{font-style:italic}
.legend-row{
  display:flex;align-items:center;gap:7px;
  padding:5px 10px;border-bottom:1px solid #21262d;
  min-height:36px
}
.legend-row:last-child{border-bottom:none}

/* colour swatch button */
.leg-color{
  width:20px;height:20px;border-radius:4px;border:2px solid #30363d;
  cursor:pointer;padding:0;background:none;flex-shrink:0;
  display:flex;align-items:center;justify-content:center
}

/* ID label */
.legend-row-id{
  font-size:11px;font-weight:600;color:#f0f6fc;
  font-family:"SFMono-Regular",Consolas,monospace;
  min-width:90px;max-width:90px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap
}
/* name + detail area */
.legend-row-info{flex:1;min-width:0;display:flex;flex-direction:column;gap:1px}
.legend-row-name{
  font-size:10px;color:#8b949e;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap
}
.legend-row-formula{
  font-size:9px;color:#484f58;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-style:italic
}

/* metric toggle (zscore / raw) */
.leg-metric{
  display:flex;border:1px solid #30363d;border-radius:4px;overflow:hidden;flex-shrink:0
}
.leg-metric button{
  font-size:9px;padding:2px 6px;background:transparent;
  border:none;color:#8b949e;cursor:pointer;line-height:1.4
}
.leg-metric button.active{background:#1f6feb;color:#f0f6fc}

/* axis toggle (L / R) */
.leg-axis{
  display:flex;border:1px solid #30363d;border-radius:4px;overflow:hidden;flex-shrink:0
}
.leg-axis button{
  font-size:9px;padding:2px 7px;background:transparent;
  border:none;color:#8b949e;cursor:pointer;line-height:1.4
}
.leg-axis button.active{background:#388bfd;color:#f0f6fc}

/* style dropdown */
.leg-style{
  font-size:9px;background:#21262d;color:#c9d1d9;
  border:1px solid #30363d;border-radius:4px;padding:2px 4px;
  cursor:pointer;flex-shrink:0
}

/* width control */
.leg-width{
  display:flex;align-items:center;gap:3px;flex-shrink:0
}
.leg-width input[type=range]{
  width:52px;height:3px;accent-color:#58a6ff;cursor:pointer
}
.leg-width-val{font-size:9px;color:#8b949e;min-width:20px;text-align:right}

/* delete button */
.leg-del{
  background:none;border:none;color:#484f58;cursor:pointer;
  font-size:14px;line-height:1;padding:0 2px;flex-shrink:0
}
.leg-del:hover{color:#f85149}

/* ── regime strip (standalone wrap — now unused, strips are inline in legend) ── */
#regime-strip-wrap{ display:none !important }
.strip-row{
  display:flex;align-items:center;margin-bottom:2px
}
.strip-close-btn{
  width:14px;height:14px;flex-shrink:0;
  background:none;border:none;color:#484f58;cursor:pointer;
  font-size:12px;line-height:1;padding:0;margin:0 3px 0 4px;
  display:flex;align-items:center;justify-content:center
}
.strip-close-btn:hover{color:#f85149}
.strip-label{
  font-size:9px;color:#8b949e;white-space:nowrap;
  font-family:"SFMono-Regular",Consolas,monospace;
  width:60px;text-align:right;padding-right:6px;flex-shrink:0
}
.strip-canvas-wrap{flex:1;position:relative;overflow:hidden}
.strip-canvas{display:block;width:100%;height:14px}
.strip-fwd .strip-canvas{height:9px}
.strip-fwd .strip-label{color:#484f58;font-style:italic}
#regime-color-key{
  display:flex;flex-wrap:wrap;gap:6px 14px;
  padding:4px 66px;margin-top:2px;border-top:1px solid #21262d
}
.key-item{display:flex;align-items:center;gap:4px;font-size:9px;color:#8b949e}
.key-swatch{width:12px;height:12px;border-radius:2px;flex-shrink:0}

/* regime + fwd toggle buttons in legend row */
.leg-strip-btns{display:flex;gap:3px;flex-shrink:0}
.leg-strip-btn{
  font-size:9px;padding:2px 5px;
  background:transparent;border:1px solid #30363d;
  border-radius:3px;color:#8b949e;cursor:pointer;line-height:1.4
}
.leg-strip-btn.active{background:#1f3a5c;color:#79c0ff;border-color:#388bfd}

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
    <input id="chart-title" type="text" value="Select indicators from the sidebar to begin" spellcheck="false">
    <div id="font-controls">
      <div class="font-ctrl-group">
        <label>Tick</label>
        <button class="font-btn" data-target="tick" data-delta="-1">−</button>
        <span class="font-val" id="fv-tick">18</span>
        <button class="font-btn" data-target="tick" data-delta="1">+</button>
      </div>
      <div class="font-ctrl-group">
        <label>Title</label>
        <button class="font-btn" data-target="axisTitle" data-delta="-1">−</button>
        <span class="font-val" id="fv-axisTitle">18</span>
        <button class="font-btn" data-target="axisTitle" data-delta="1">+</button>
      </div>
      <div class="font-ctrl-group">
        <label>Legend</label>
        <button class="font-btn" data-target="legend" data-delta="-1">−</button>
        <span class="font-val" id="fv-legend">18</span>
        <button class="font-btn" data-target="legend" data-delta="1">+</button>
      </div>
    </div>
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
    <div id="legend-panel">
      <div id="legend-panel-header">
        <span id="legend-panel-title">Series</span>
        <button id="btn-detail-toggle" title="Show/hide indicator descriptions">Detail ▾</button>
      </div>
      <div id="legend-panel-inner"></div>
    </div>
  </div>
  <div id="regime-strip-wrap">
    <div id="regime-strip-inner"></div>
    <div id="regime-color-key"></div>
  </div>
  <div id="statusbar" id="statusbar">Ready</div>
</div>

</div><!-- #app -->

<!-- ══════════════════════════════════════════════════════════
     EMBEDDED DATA — main payload (macro_market / us / intl)
     ══════════════════════════════════════════════════════════ -->
<script>
const MAIN_DATA = __MAIN_DATA_JSON__;
</script>
<!-- Market-data companion file (~16 MB, loaded from same directory) -->
<script src="indicator_explorer_mkt.js"></script>

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
  fontSize: {tick: 18, axisTitle: 18, legend: 18},
  legendHeight: 0,
  showDetail: true,   // global toggle for legend formula rows
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

  Object.entries(mm.groups).forEach(([groupName, subGroups]) => {
    body.appendChild(buildGroupSection(groupName, subGroups, mm.indicators));
  });

  hdr.addEventListener('click', () => toggleSection(arr, body));
  wrap.appendChild(body);
  return wrap;
}

function buildGroupSection(groupName, subGroups, indicators){
  // subGroups = { sub_group_name: [indicator_ids], ... }
  const totalIds = Object.values(subGroups).reduce((n, ids) => n + ids.length, 0);

  const wrap = el('div','grp-section');
  const hdr  = el('div','grp-header');
  const arr  = makeArrow('grp-arrow open');
  const ttl  = el('span','grp-title', groupName);
  const cnt  = el('span','grp-count', totalIds);
  hdr.append(arr, ttl, cnt);
  wrap.appendChild(hdr);

  const body = el('div','grp-body open');

  Object.entries(subGroups).forEach(([sgName, ids]) => {
    body.appendChild(buildSubGroupSection(sgName, ids, indicators));
  });

  hdr.addEventListener('click', () => toggleSection(arr, body));
  wrap.appendChild(body);
  return wrap;
}

function buildSubGroupSection(sgName, ids, indicators){
  const wrap = el('div','sgrp-section');
  const hdr  = el('div','sgrp-header');
  const arr  = makeArrow('sgrp-arrow open');
  const ttl  = el('span','sgrp-title', sgName);
  const cnt  = el('span','sgrp-count', ids.length);
  hdr.append(arr, ttl, cnt);
  wrap.appendChild(hdr);

  const body = el('div','sgrp-body open');
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

  // hide empty sub-group sections (no visible children)
  document.querySelectorAll('.sgrp-body').forEach(body => {
    const anyVisible = Array.from(body.querySelectorAll('.series-item'))
      .some(i => !i.classList.contains('hidden'));
    body.closest('.sgrp-section').style.display = anyVisible ? '' : 'none';
  });

  // hide empty group / asset-class bodies (no visible children)
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
    // restore hidden groups and sub-groups
    document.querySelectorAll('.grp-section,.sgrp-section,.ac-section').forEach(s => s.style.display = '');
  }
});

// ── Date controls ──────────────────────────────────────────────────────────
(function initDates(){
  // default: last 5 years
  const now    = new Date();
  const fiveYr = new Date(now);
  fiveYr.setFullYear(fiveYr.getFullYear() - 5);
  const fmt = d => d.toISOString().slice(0,10);
  document.getElementById('date-from').value = fmt(fiveYr);
  document.getElementById('date-to').value   = fmt(now);
  STATE.dateFrom = fmt(fiveYr);
  STATE.dateTo   = fmt(now);
})();

function applyDates(){
  const from = document.getElementById('date-from').value.trim();
  const to   = document.getElementById('date-to').value.trim();
  const dateRe = /^\d{4}-\d{2}-\d{2}$/;
  if(from && !dateRe.test(from)){ setStatus('Invalid From date (use YYYY-MM-DD)','error'); return; }
  if(to   && !dateRe.test(to))  { setStatus('Invalid To date (use YYYY-MM-DD)',  'error'); return; }
  STATE.dateFrom = from || null;
  STATE.dateTo   = to   || null;
  checkDateCoverage();
  if(STATE.active.length) renderChart();
}
document.getElementById('btn-apply-dates').addEventListener('click', applyDates);
['date-from','date-to'].forEach(id =>
  document.getElementById(id).addEventListener('keydown', e => { if(e.key === 'Enter') applyDates(); })
);

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
  document.getElementById('regime-strip-wrap').style.display = 'none';
  document.getElementById('regime-strip-inner').innerHTML = '';
  document.getElementById('coverage-warn').className = '';
  document.getElementById('coverage-warn').innerHTML = '';
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

// ── Swatch colour picker ───────────────────────────────────────────────────
const SWATCHES = [
  '#f85149','#ff7b72','#ffa657','#e3b341','#f0f6fc',
  '#ff6b9d','#d2a8ff','#c9d1d9','#8b949e','#58a6ff',
  '#79c0ff','#56d364','#3fb950','#1f6feb','#388bfd',
  '#a5f3c9','#39d353','#ffd700','#ff8c00','#ff4500',
  '#da3633','#b22222','#8b0000','#6a0dad','#4b0082',
  '#0066cc','#0099cc','#00b4d8','#00c896','#00e676',
  '#66ff99','#ccff33','#ffee58','#ffab40','#ff6d00',
  '#ff1744','#d500f9','#651fff','#2979ff','#00b0ff',
  '#00e5ff','#1de9b6','#76ff03','#c6ff00','#ffffff',
];

let _swatchPicker = null;
function showSwatchPicker(anchor, current, onPick){
  // close any existing picker
  if(_swatchPicker){ _swatchPicker.remove(); _swatchPicker = null; }
  const picker = document.createElement('div');
  picker.style.cssText = [
    'position:fixed;z-index:9999;background:#161b22;',
    'border:1px solid #30363d;border-radius:6px;padding:8px;',
    'display:grid;grid-template-columns:repeat(9,18px);gap:4px;',
    'box-shadow:0 8px 24px rgba(0,0,0,.6)',
  ].join('');
  SWATCHES.forEach(hex => {
    const sw = document.createElement('div');
    sw.style.cssText = `width:18px;height:18px;border-radius:3px;background:${hex};cursor:pointer;`;
    sw.style.outline = hex === current ? '2px solid #fff' : 'none';
    sw.addEventListener('click', e => {
      e.stopPropagation();
      onPick(hex);
      picker.remove(); _swatchPicker = null;
    });
    picker.appendChild(sw);
  });
  // smart positioning: flip above the anchor when near the bottom of the viewport
  document.body.appendChild(picker);
  const r  = anchor.getBoundingClientRect();
  const ph = picker.offsetHeight || 220;
  const pw = picker.offsetWidth  || 210;
  const top  = (r.bottom + 4 + ph > window.innerHeight) ? r.top - ph - 4 : r.bottom + 4;
  const left = Math.min(Math.max(4, r.left), window.innerWidth - pw - 4);
  picker.style.top  = Math.max(4, top) + 'px';
  picker.style.left = left + 'px';
  _swatchPicker = picker;
  // close on outside click
  const closeOutside = e => { if(!picker.contains(e.target)){ picker.remove(); _swatchPicker = null; document.removeEventListener('click', closeOutside); } };
  setTimeout(() => document.addEventListener('click', closeOutside), 0);
}

// ── CSS for leg-color (remove old input[type=color] rule) ─────────────────

// ══════════════════════════════════════════════════════════════════════
// STEP 4 — PER-SERIES LEGEND CONTROLS
// ══════════════════════════════════════════════════════════════════════

function getSeriesDetail(s){
  // Returns {fullName, detail} for the legend info rows
  if(s.source === 'macro_market'){
    const ind = MAIN_DATA.macro_market.indicators[s.key];
    const m   = ind?.meta || {};
    return { fullName: m.category || s.key, detail: m.formula || m.interp || '' };
  }
  if(s.source === 'macro_us'){
    const ser = MAIN_DATA.macro_us.series[s.key];
    const m   = ser?.meta || {};
    return { fullName: m['Name'] || m['Indicator'] || s.key,
             detail: [m['Units'], m['Subcategory']].filter(Boolean).join(' · ') };
  }
  if(s.source === 'macro_intl'){
    const ser = MAIN_DATA.macro_intl.series[s.key];
    const m   = ser?.meta || {};
    const country = m['Country'] || '';
    const ind2    = m['Indicator'] || s.key;
    return { fullName: country ? `${country} — ${ind2}` : ind2,
             detail: [m['Units'], m['Subcategory']].filter(Boolean).join(' · ') };
  }
  if(s.source === 'market_comp'){
    const ser = MKT_DATA.series[s.key];
    const m   = ser?.meta || {};
    return { fullName: m['Name'] || s.key,
             detail: [m['Asset Class'], m['Subcategory'] || m['Region']].filter(Boolean).join(' · ') };
  }
  return { fullName: s.key, detail: '' };
}

let INLINE_STRIPS = [];   // [{canvas, dates, values}] rebuilt each updateLegendPanel call

function updateLegendPanel(){
  const panel = document.getElementById('legend-panel');
  const inner = document.getElementById('legend-panel-inner');
  if(!STATE.active.length){
    panel.style.display = 'none';
    STATE.legendHeight = 0;
    return;
  }
  panel.style.display = 'block';
  inner.innerHTML = '';
  INLINE_STRIPS = [];   // will be repopulated below

  STATE.active.forEach((s, idx) => {
    const row = el('div','legend-row');
    row.dataset.idx = idx;

    // ── colour picker (swatch grid) ───────────────────────────────
    const colorBtn = el('div','leg-color');
    colorBtn.style.backgroundColor = s.color;
    colorBtn.title = 'Pick colour';
    colorBtn.addEventListener('click', e => {
      e.stopPropagation();
      showSwatchPicker(colorBtn, s.color, newColor => {
        s.color = newColor;
        colorBtn.style.backgroundColor = newColor;
        idEl.style.color = newColor;
        renderChart();
      });
    });

    // ── ID + info (name + formula) ─────────────────────────────────
    const { fullName, detail } = getSeriesDetail(s);
    const idEl = el('span','legend-row-id', s.id);
    idEl.style.color = s.color;
    idEl.style.fontSize = STATE.fontSize.legend + 'px';
    idEl.title = s.id;
    const infoWrap = el('div','legend-row-info');
    const nmEl = el('span','legend-row-name', fullName);
    nmEl.title = fullName;
    nmEl.style.fontSize = (STATE.fontSize.legend - 1) + 'px';
    infoWrap.appendChild(nmEl);
    if(detail){
      const fmEl = el('span','legend-row-formula', detail);
      fmEl.title = detail;
      fmEl.style.fontSize = (STATE.fontSize.legend - 2) + 'px';
      fmEl.style.display = STATE.showDetail ? '' : 'none';
      infoWrap.appendChild(fmEl);
    }

    // ── metric toggle (zscore / raw) — only for macro_market ──────
    let metricToggle = null;
    if(s.source === 'macro_market'){
      metricToggle = el('div','leg-metric');
      ['zscore','raw'].forEach(m => {
        const btn = el('button', null, m);
        if(s.metric === m) btn.classList.add('active');
        btn.addEventListener('click', () => {
          s.metric = m;
          metricToggle.querySelectorAll('button').forEach(b =>
            b.classList.toggle('active', b.textContent === m));
          renderChart();
        });
        metricToggle.appendChild(btn);
      });
    }

    // ── axis toggle (L1 / L2 / R1 / R2) ─────────────────────────
    const AXES = [{val:'left',label:'L1'},{val:'left2',label:'L2'},
                  {val:'right',label:'R1'},{val:'right2',label:'R2'}];
    const axisToggle = el('div','leg-axis');
    AXES.forEach(({val, label}) => {
      const btn = el('button', null, label);
      btn.title = {left:'Left axis (L1)',left2:'Left axis 2 (L2)',
                   right:'Right axis (R1)',right2:'Right axis 2 (R2)'}[val];
      if(s.axis === val) btn.classList.add('active');
      btn.addEventListener('click', () => {
        s.axis = val;
        axisToggle.querySelectorAll('button').forEach(b =>
          b.classList.toggle('active', b.textContent === label));
        renderChart();
      });
      axisToggle.appendChild(btn);
    });

    // ── line style dropdown ───────────────────────────────────────
    const styleEl = document.createElement('select');
    styleEl.className = 'leg-style';
    styleEl.title = 'Line style';
    ['solid','dashed','dotted','dash-dot'].forEach(st => {
      const opt = document.createElement('option');
      opt.value = st; opt.textContent = st;
      if(s.style === st) opt.selected = true;
      styleEl.appendChild(opt);
    });
    styleEl.addEventListener('change', () => {
      s.style = styleEl.value;
      renderChart();
    });

    // ── line width slider ─────────────────────────────────────────
    const widthWrap = el('div','leg-width');
    const widthSlider = document.createElement('input');
    widthSlider.type  = 'range';
    widthSlider.min   = '0.5';
    widthSlider.max   = '4';
    widthSlider.step  = '0.5';
    widthSlider.value = s.width;
    widthSlider.title = 'Line width';
    const widthVal = el('span','leg-width-val', s.width + 'px');
    widthSlider.addEventListener('input', () => {
      s.width = parseFloat(widthSlider.value);
      widthVal.textContent = s.width + 'px';
      renderChart();
    });
    widthWrap.append(widthSlider, widthVal);

    // ── delete button ─────────────────────────────────────────────
    const delBtn = el('button','leg-del','✕');
    delBtn.title = 'Remove series';
    delBtn.addEventListener('click', () => {
      // uncheck sidebar checkbox
      const cb = document.querySelector(
        `.series-cb[data-source="${s.source}"][data-key="${CSS.escape(s.key)}"]`
      );
      if(cb){ cb.checked = false; }
      STATE.active = STATE.active.filter((_,i) => i !== idx);
      checkDateCoverage();
      updateLegendPanel();
      updateChartTitle();
      renderChart();
    });

    // ── regime strip toggles (macro_market only) ──────────────────
    let stripBtns = null;
    if(s.source === 'macro_market'){
      if(s.showRegime === undefined) s.showRegime = false;
      if(s.showFwd    === undefined) s.showFwd    = false;
      stripBtns = el('div','leg-strip-btns');

      const rBtn = el('button','leg-strip-btn','R');
      rBtn.title = 'Toggle regime strip';
      if(s.showRegime) rBtn.classList.add('active');
      rBtn.addEventListener('click', () => {
        s.showRegime = !s.showRegime;
        updateLegendPanel();
      });

      const fBtn = el('button','leg-strip-btn','F');
      fBtn.title = 'Toggle fwd_regime strip';
      if(s.showFwd) fBtn.classList.add('active');
      fBtn.addEventListener('click', () => {
        s.showFwd = !s.showFwd;
        updateLegendPanel();
      });

      stripBtns.append(rBtn, fBtn);
    }

    // ── assemble row ──────────────────────────────────────────────
    row.append(colorBtn, idEl, infoWrap);
    if(metricToggle) row.appendChild(metricToggle);
    row.append(axisToggle, styleEl, widthWrap);
    if(stripBtns) row.appendChild(stripBtns);
    row.appendChild(delBtn);
    inner.appendChild(row);

    // ── inline regime strips (directly below this legend row) ─────
    if(s.source === 'macro_market' && (s.showRegime || s.showFwd)){
      const ind = MAIN_DATA.macro_market.indicators[s.key];
      if(ind){
        const mmDates = MAIN_DATA.macro_market.dates;
        const from = STATE.dateFrom, to = STATE.dateTo;
        const filtIdx   = mmDates.map((_,i)=>i).filter(i => {
          const d = mmDates[i];
          return (!from || d >= from) && (!to || d <= to);
        });
        const filtDates = filtIdx.map(i => mmDates[i]);

        const addStripRow = (values, labelText, extraClass) => {
          const srow = el('div', 'inline-strip-row' + (extraClass ? ' ' + extraClass : ''));
          const closeB = el('button','strip-close-btn','×');
          closeB.title = 'Remove strip';
          closeB.addEventListener('click', () => {
            if(extraClass === 'inline-strip-fwd') s.showFwd = false;
            else s.showRegime = false;
            updateLegendPanel();
          });
          const lbl = el('span','strip-label', labelText);
          lbl.style.color = s.color;
          const cwrap = el('div','strip-canvas-wrap');
          const cv = document.createElement('canvas');
          cv.className = 'strip-canvas';
          cwrap.appendChild(cv);
          srow.append(closeB, lbl, cwrap);
          inner.appendChild(srow);
          INLINE_STRIPS.push({canvas: cv, dates: filtDates, values});
        };

        if(s.showRegime){
          addStripRow(filtIdx.map(i => ind.regime[i] ?? null), s.id, '');
        }
        if(s.showFwd){
          addStripRow(filtIdx.map(i => (ind.fwd_regime||[])[i] ?? null), s.id + ' fwd', 'inline-strip-fwd');
        }
      }
    }
  });

  // redraw strip canvases; margin is handled by renderChart().then() rAF
  // but also update it here for cases where chart is already rendered
  // (e.g. toggling a strip row without adding/removing a series)
  requestAnimationFrame(() => {
    redrawInlineStrips();
    if(document.getElementById('plotly-chart').data){
      updateChartMargin();
    }
  });
}

// ── Chart title ────────────────────────────────────────────────────────────
function seriesFriendlyLabel(s){
  if(s.source === 'macro_market'){
    const ind = MAIN_DATA.macro_market.indicators[s.key];
    const cat = ind?.meta?.category || s.key;
    return cat.replace(/^[^/]+\/\s*/,'').replace(/\s*\(.*\)/,'').trim() || s.key;
  }
  if(s.source === 'macro_us'){
    const ser = MAIN_DATA.macro_us.series[s.key];
    return ser?.meta?.Name || s.key;
  }
  if(s.source === 'macro_intl'){
    const ser = MAIN_DATA.macro_intl.series[s.key];
    const country = ser?.meta?.Country || '';
    const ind2    = ser?.meta?.Indicator || s.key;
    return country ? `${country} ${ind2}` : ind2;
  }
  if(s.source === 'market_comp'){
    const ser = MKT_DATA.series[s.key];
    return ser?.meta?.Name || s.key;
  }
  return s.key;
}

function updateChartTitle(){
  const t = document.getElementById('chart-title');
  if(document.activeElement === t) return; // don't overwrite while user is typing
  t.value = STATE.active.length
    ? STATE.active.map(s => `${s.id}: ${seriesFriendlyLabel(s)}`).join('  ·  ')
    : 'Select indicators from the sidebar to begin';
}

// ══════════════════════════════════════════════════════════════════════
// STEP 3 — PLOTLY CHART RENDERING ENGINE
// ══════════════════════════════════════════════════════════════════════

// ── line-dash mapping ─────────────────────────────────────────────────
const DASH_MAP = {solid:'solid', dashed:'dash', dotted:'dot', 'dash-dot':'dashdot'};

// ── extract & date-filter data for one active series entry ────────────
function getSeriesData(s){
  let srcDates, values, raw=[], zscore=[], regime=[], fwd_regime=[];

  if(s.source === 'macro_market'){
    const ind = MAIN_DATA.macro_market.indicators[s.key];
    if(!ind) return null;
    srcDates   = MAIN_DATA.macro_market.dates;
    const metric = s.metric || 'zscore';
    values     = ind[metric] || [];
    raw        = ind.raw        || [];
    zscore     = ind.zscore     || [];
    regime     = ind.regime     || [];
    fwd_regime = ind.fwd_regime || [];
  } else if(s.source === 'macro_us'){
    const ser = MAIN_DATA.macro_us.series[s.key];
    if(!ser) return null;
    srcDates = MAIN_DATA.macro_us.dates;
    values   = ser.values;
  } else if(s.source === 'macro_intl'){
    const ser = MAIN_DATA.macro_intl.series[s.key];
    if(!ser) return null;
    srcDates = MAIN_DATA.macro_intl.dates;
    values   = ser.values;
  } else if(s.source === 'market_comp'){
    const ser = MKT_DATA.series[s.key];
    if(!ser) return null;
    srcDates = MKT_DATA.dates;
    values   = ser.values;
  } else { return null; }

  // apply date range filter
  const from = STATE.dateFrom, to = STATE.dateTo;
  const fd=[], fv=[], fr=[], fz=[], freg=[], ffwd=[];
  srcDates.forEach((d,i) => {
    if(from && d < from) return;
    if(to   && d > to)   return;
    fd.push(d);
    fv.push(values[i]   ?? null);
    fr.push(raw[i]        ?? null);
    fz.push(zscore[i]     ?? null);
    freg.push(regime[i]   ?? null);
    ffwd.push(fwd_regime[i] ?? null);
  });

  return {dates:fd, values:fv, raw:fr, zscore:fz, regime:freg, fwd_regime:ffwd};
}

// ── build a single Plotly trace ───────────────────────────────────────
function buildTrace(s){
  const d = getSeriesData(s);
  if(!d || !d.dates.length) return null;

  const isMacro   = s.source === 'macro_market';
  const AXIS_MAP  = {left:'y', right:'y2', left2:'y3', right2:'y4'};
  const yaxis     = AXIS_MAP[s.axis] || 'y';
  const dashStyle = DASH_MAP[s.style] || 'solid';

  // customdata: [raw, zscore, regime, fwd_regime] for macro; [value] otherwise
  let customdata, hovertemplate;
  if(isMacro){
    customdata = d.dates.map((_,i) => [d.raw[i], d.zscore[i], d.regime[i], d.fwd_regime[i]]);
    hovertemplate =
      '<b>' + s.id + '</b><br>' +
      'Raw: %{customdata[0]}<br>' +
      'Z-Score: %{customdata[1]:.3f}<br>' +
      'Regime: %{customdata[2]}<br>' +
      'Fwd: %{customdata[3]}' +
      '<extra></extra>';
  } else {
    customdata = d.values.map(v => [v]);
    hovertemplate =
      '<b>' + s.id + '</b><br>' +
      '%{x}<br>Value: %{customdata[0]:.4f}' +
      '<extra></extra>';
  }

  return {
    x:            d.dates,
    y:            d.values,
    name:         s.id,
    type:         'scatter',
    mode:         'lines',
    connectgaps:  false,
    line:         {color: s.color, dash: dashStyle, width: s.width},
    yaxis,
    customdata,
    hovertemplate,
    showlegend:   false,
  };
}

// ── z-score reference lines (±1, ±2) ─────────────────────────────────
function zRefShapes(){
  const levels = [{v:1,dash:'dot'},{v:-1,dash:'dot'},{v:2,dash:'dot'},{v:-2,dash:'dot'}];
  return levels.map(({v,dash}) => ({
    type:'line', xref:'paper', yref:'y',
    x0:0, x1:1, y0:v, y1:v,
    line:{color:'#30363d', width:1, dash},
  }));
}

// ── redraw all inline strip canvases (called after layout changes) ────
function redrawInlineStrips(){
  const geo = getXGeometry();
  if(!geo || !INLINE_STRIPS.length) return;
  INLINE_STRIPS.forEach(({canvas, dates, values}) =>
    drawStripCanvas(canvas, dates, values, geo)
  );
}

// ── adjust Plotly margins (bottom for legend, l/r for outer axes) ────
function updateChartMargin(){
  const panel = document.getElementById('legend-panel');
  const div   = document.getElementById('plotly-chart');
  if(!div || !div.data || !panel) return;
  const lh      = (panel.style.display !== 'none') ? panel.getBoundingClientRect().height : 0;
  const hasL2   = STATE.active.some(s => s.axis === 'left2');
  const hasR2   = STATE.active.some(s => s.axis === 'right2');
  const hasR    = STATE.active.some(s => s.axis === 'right');
  Plotly.relayout(div, {
    'margin.b': lh + 44,
    'margin.l': hasL2 ? 110 : 60,
    'margin.r': hasR2 ? 110 : (hasR ? 70 : 20),
  });
}

// ── main render function ──────────────────────────────────────────────
function renderChart(){
  if(!STATE.active.length){
    document.getElementById('chart-placeholder').style.display = 'flex';
    document.getElementById('plotly-chart').style.display      = 'none';
    return;
  }

  const chartDiv   = document.getElementById('plotly-chart');
  const placeholder= document.getElementById('chart-placeholder');

  const traces = STATE.active.map(buildTrace).filter(Boolean);
  if(!traces.length){
    setStatus('No data in selected date range', 'error'); return;
  }

  const hasLeft   = STATE.active.some(s => s.axis === 'left');
  const hasRight  = STATE.active.some(s => s.axis === 'right');
  const hasLeft2  = STATE.active.some(s => s.axis === 'left2');
  const hasRight2 = STATE.active.some(s => s.axis === 'right2');

  // axis titles: friendly name (ID) for each series
  const axisLabel = s => {
    const friendly = seriesFriendlyLabel(s);
    const metric   = (s.source === 'macro_market' && s.metric === 'zscore') ? ' z-score' : '';
    return `${friendly}${metric} (${s.id})`;
  };
  const leftLabels   = STATE.active.filter(s => s.axis === 'left').map(axisLabel).slice(0,2);
  const rightLabels  = STATE.active.filter(s => s.axis === 'right').map(axisLabel).slice(0,2);
  const left2Labels  = STATE.active.filter(s => s.axis === 'left2').map(axisLabel).slice(0,2);
  const right2Labels = STATE.active.filter(s => s.axis === 'right2').map(axisLabel).slice(0,2);

  // dynamic margins & domain: separate L1/L2 and R1/R2 so tick labels don't overlap
  const mL = hasLeft2  ? 110 : 60;
  const mR = hasRight2 ? 110 : (hasRight ? 70 : 20);
  // xaxis.domain pushes the plot area inward; outer axes sit in the freed space
  const domainL = hasLeft2  ? 0.10 : 0;
  const domainR = hasRight2 ? 0.90 : 1;

  // legend height measured synchronously (forces layout flush before Plotly.react)
  const legendH = (()=>{ const p=document.getElementById('legend-panel'); return (p && p.style.display!=='none') ? (p.offsetHeight||0) : 0; })();

  const layout = {
    paper_bgcolor: '#0d1117',
    plot_bgcolor:  '#0d1117',
    font:  {color:'#c9d1d9', family:'-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif', size:11},
    margin:{t:24, r:mR, b:legendH + 44, l:mL},
    hovermode: 'x unified',
    hoverlabel:{bgcolor:'#161b22', bordercolor:'#30363d', font:{size:11, color:'#c9d1d9'}},
    xaxis:{
      type:'date', domain:[domainL, domainR],
      gridcolor:'#21262d', linecolor:'#30363d',
      tickfont:{color:'#8b949e', size:STATE.fontSize.tick},
      range: [STATE.dateFrom, STATE.dateTo].filter(Boolean),
      showspikes: true, spikecolor:'#484f58', spikethickness:1,
    },
    // yaxis / yaxis2 are always visible=true so overlay axes (yaxis3/4) have a
    // stable reference frame. Visual elements are hidden when no series use them.
    yaxis:{
      title: hasLeft ? leftLabels.join(' / ') : '',
      gridcolor:'#21262d', linecolor:'#30363d',
      tickfont:{color:'#8b949e', size:STATE.fontSize.tick},
      zeroline:hasLeft, zerolinecolor:'#484f58', zerolinewidth:1,
      titlefont:{color:'#8b949e', size:STATE.fontSize.axisTitle},
      showticklabels: hasLeft, showline: hasLeft,
      showgrid: hasLeft,   // grid from L1 only when it has data
      visible: true,
    },
    yaxis2:{
      title: hasRight ? rightLabels.join(' / ') : '',
      overlaying:'y', side:'right',
      gridcolor:'#21262d', linecolor:'#30363d',
      tickfont:{color:'#8b949e', size:STATE.fontSize.tick},
      showgrid:false, showticklabels: hasRight, showline: hasRight,
      titlefont:{color:'#8b949e', size:STATE.fontSize.axisTitle},
      visible: true,
    },
    yaxis3:{
      title: hasLeft2 ? left2Labels.join(' / ') : '',
      overlaying:'y', side:'left', anchor:'free', position:0,
      tickfont:{color:'#8b949e', size:STATE.fontSize.tick},
      // show gridlines from L2 only when L1 has no series
      showgrid: hasLeft2 && !hasLeft,
      gridcolor:'#21262d',
      showticklabels: hasLeft2, showline: hasLeft2,
      titlefont:{color:'#8b949e', size:STATE.fontSize.axisTitle},
      zeroline:false, visible: true,
    },
    yaxis4:{
      title: hasRight2 ? right2Labels.join(' / ') : '',
      overlaying:'y', side:'right', anchor:'free', position:1,
      tickfont:{color:'#8b949e', size:STATE.fontSize.tick},
      showgrid:false, showticklabels: hasRight2, showline: hasRight2,
      titlefont:{color:'#8b949e', size:STATE.fontSize.axisTitle},
      zeroline:false, visible: true,
    },
    shapes: hasLeft ? zRefShapes() : [],
    modebar:{bgcolor:'transparent', color:'#484f58', activecolor:'#58a6ff'},
    dragmode:'zoom',
  };

  const config = {
    responsive:   true,
    displaylogo:  false,
    modeBarButtonsToRemove: ['select2d','lasso2d','autoScale2d','toImage'],
    modeBarButtonsToAdd: [{
      name: 'Download as PNG',
      icon: Plotly.Icons.camera,
      click: () => downloadFullSnapshot(),
    }],
  };

  placeholder.style.display = 'none';
  chartDiv.style.display     = 'block';

  Plotly.react(chartDiv, traces, layout, config)
    .then(() => {
      requestAnimationFrame(redrawInlineStrips);
      // redraw strips on zoom / pan
      chartDiv.removeAllListeners && chartDiv.removeAllListeners('plotly_relayout');
      chartDiv.on('plotly_relayout', () => redrawInlineStrips());
    })
    .catch(err => setStatus('Chart error: ' + err.message, 'error'));

  const n = traces.length;
  const pts = traces.reduce((s,t) => s + (t.x ? t.x.length : 0), 0);
  setStatus(`${n} series · ${pts.toLocaleString()} data points · range ${STATE.dateFrom||'all'} → ${STATE.dateTo||'all'}`);
}

// ── Full snapshot (title + chart + legend + regime strips) ────────────
function downloadFullSnapshot(){
  const scale = 2;
  const chartDiv = document.getElementById('plotly-chart');
  if(!chartDiv) return;

  Plotly.toImage(chartDiv, {format:'png', scale, width: chartDiv.offsetWidth, height: chartDiv.offsetHeight})
    .then(plotDataUrl => {
      const plotImg = new Image();
      plotImg.onload = () => {
        const W = plotImg.width;
        const titleH   = 40 * scale;
        const legendH  = buildLegendHeight() * scale;
        const stripH   = buildStripHeight() * scale;
        const totalH   = titleH + plotImg.height + legendH + stripH;

        const c = document.createElement('canvas');
        c.width  = W;
        c.height = totalH;
        const ctx = c.getContext('2d');

        // background
        ctx.fillStyle = '#0d1117';
        ctx.fillRect(0, 0, W, totalH);

        // title
        const titleText = document.getElementById('chart-title').value || '';
        ctx.fillStyle = '#c9d1d9';
        ctx.font = `${14 * scale}px -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, sans-serif`;
        ctx.textBaseline = 'middle';
        ctx.fillText(titleText, 12 * scale, titleH / 2);

        // plot image
        ctx.drawImage(plotImg, 0, titleH);

        // legend
        let yOff = titleH + plotImg.height;
        const active = STATE.active;
        if(active.length){
          ctx.font = `${11 * scale}px -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, sans-serif`;
          const lineH = 18 * scale;
          const pad = 12 * scale;
          active.forEach(s => {
            const {fullName} = getSeriesDetail(s);
            ctx.fillStyle = s.color;
            ctx.fillRect(pad, yOff + 4*scale, 10*scale, 10*scale);
            ctx.fillStyle = '#c9d1d9';
            ctx.fillText(`${s.id} — ${fullName}`, pad + 14*scale, yOff + lineH/2);
            yOff += lineH;
          });
        }

        // regime color key
        const keyEl = document.getElementById('regime-color-key');
        if(keyEl && keyEl.style.display !== 'none'){
          yOff += 4 * scale;
          ctx.font = `${10 * scale}px -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, sans-serif`;
          let xOff = 12 * scale;
          keyEl.querySelectorAll('.key-item').forEach(item => {
            const swatch = item.querySelector('.key-swatch');
            const label  = item.textContent.trim();
            const swatchColor = swatch ? swatch.style.background : '#1c2128';
            ctx.fillStyle = swatchColor;
            ctx.fillRect(xOff, yOff + 2*scale, 8*scale, 8*scale);
            ctx.fillStyle = '#8b949e';
            const textW = ctx.measureText(label).width;
            ctx.fillText(label, xOff + 10*scale, yOff + 7*scale);
            xOff += 10*scale + textW + 12*scale;
            if(xOff > W - 50*scale){ xOff = 12*scale; yOff += 14*scale; }
          });
        }

        // download
        const a = document.createElement('a');
        a.download = 'macro_chart.png';
        a.href = c.toDataURL('image/png');
        a.click();
      };
      plotImg.src = plotDataUrl;
    });
}

function buildLegendHeight(){
  const n = STATE.active.length;
  const keyEl = document.getElementById('regime-color-key');
  const keyH = (keyEl && keyEl.style.display !== 'none') ? 20 : 0;
  return n * 18 + keyH + 8;
}

function buildStripHeight(){
  return 0; // strips are overlay canvases, captured via the plot image
}

// ══════════════════════════════════════════════════════════════════════
// STEP 5 — REGIME STRIP ENGINE
// ══════════════════════════════════════════════════════════════════════

// ── semantic colour mapping ───────────────────────────────────────────
const REGIME_PALETTE = {
  // explicit label overrides (substring match, checked in order)
  positive: [
    'pro-growth','risk-on','carry-on','bull','expansion','broad-expansion',
    'overperform','outperform','above-trend','vol-compressing','trend-up',
    'us-equity-regime','global-equity-regime','carry-regime','labour-strong',
    'labour-tight','china-carry-attractive','india-carry-attractive',
    'weak-usd','commodity-bull','growth-inflation','ism-expansion',
    'housing-expanding','abundant','strong','improving','leading',
    'cny-strengthening','inr-strengthening','japan-outperform',
    'eurozone-outperform','eu-above','asia-above','china-outperform',
    'em-outperform','global-risk-on','uk-domestic','uk-credit-appetite',
    'china-domestic','india-domestic','opportunity',
  ],
  negative: [
    'defensive','stress','contraction','risk-off','carry-unwind','bear',
    'frothy',
    'below-trend','vol-expanding','trend-down','bond-regime','labour-weak',
    'labour-slack','unattractive','recession','commodity-bear','deflation',
    'ism-contraction','housing-contracting','tight-liquidity','deteriorating',
    'cny-weakening','inr-weakening','japan-underperform','eurozone-underperform',
    'eu-below','asia-below','china-underperform','em-outperform',
    'global-risk-off','peripheral-stress','uk-risk','flight-to-quality',
    'high-real-rates','dm-outperform','carry-unattractive',
    'strong-usd','eu-leads','china-leads',
  ],
  neutral: [
    'neutral','balanced','mixed','normal','near-trend','stable',
    'ism-neutral','labour-balanced',
  ],
  amber: [
    'complacent','caution','elevated','late-cycle',
  ],
};

// Fill colours (dark-theme friendly, semi-transparent feel via hex)
const STRIP_COLORS = {
  positive: '#1a4731',   // dark green
  negative: '#4a1515',   // dark red
  amber:    '#4a3a15',   // dark amber/yellow
  neutral:  '#1c2128',   // mid grey
  na:       '#161b22',   // near-background
};

function regimeCategory(label){
  if(!label || label === 'null') return 'na';
  const l = label.toLowerCase();
  for(const kw of REGIME_PALETTE.positive){ if(l.includes(kw)) return 'positive'; }
  for(const kw of REGIME_PALETTE.negative){ if(l.includes(kw)) return 'negative'; }
  for(const kw of REGIME_PALETTE.amber)   { if(l.includes(kw)) return 'amber';    }
  for(const kw of REGIME_PALETTE.neutral) { if(l.includes(kw)) return 'neutral';  }
  return 'neutral';
}
function regimeColor(label){ return STRIP_COLORS[regimeCategory(label)]; }

// ── get Plotly axis pixel geometry ───────────────────────────────────
function getXGeometry(){
  const div = document.getElementById('plotly-chart');
  if(!div || !div._fullLayout) return null;
  const fl  = div._fullLayout;
  const xa  = fl.xaxis;
  if(!xa || !xa.range) return null;
  return {
    t0:    new Date(xa.range[0]).getTime(),
    t1:    new Date(xa.range[1]).getTime(),
    left:  fl.margin.l,
    right: fl.margin.r,
    totalW: fl.width,
  };
}

function dateToFrac(dateStr, geo){
  const t = new Date(dateStr).getTime();
  return (t - geo.t0) / (geo.t1 - geo.t0);
}

// ── draw one strip canvas ─────────────────────────────────────────────
function drawStripCanvas(canvas, dates, labels, geo){
  const plotW = geo.totalW - geo.left - geo.right;
  const dpr   = window.devicePixelRatio || 1;
  const cssW  = canvas.parentElement.clientWidth;
  const cssH  = canvas.offsetHeight || 14;
  canvas.width  = cssW * dpr;
  canvas.height = cssH * dpr;
  canvas.style.width  = cssW + 'px';
  canvas.style.height = cssH + 'px';

  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, cssW, cssH);

  // The strip spans the full cssW; the plot area starts at geo.left px
  // from the left of the Plotly chart div, which is the same left offset
  // we need to apply to the strip canvas.
  const stripPlotW = cssW - geo.left - geo.right;
  if(stripPlotW <= 0) return;

  dates.forEach((d, i) => {
    const frac0 = dateToFrac(d, geo);
    const frac1 = i < dates.length - 1 ? dateToFrac(dates[i+1], geo) : 1.0;
    if(frac1 < 0 || frac0 > 1) return;
    const x0 = geo.left + Math.max(0, frac0) * stripPlotW;
    const x1 = geo.left + Math.min(1, frac1) * stripPlotW;
    if(x1 <= x0) return;
    ctx.fillStyle = regimeColor(labels[i]);
    ctx.fillRect(x0, 0, x1 - x0, cssH);
  });

  // faint border between plot area and margins
  ctx.fillStyle = '#0d1117';
  ctx.fillRect(0,        0, geo.left,      cssH);
  ctx.fillRect(cssW - geo.right, 0, geo.right, cssH);
}

// ── build or update the color key ────────────────────────────────────
function updateColorKey(){
  const key = document.getElementById('regime-color-key');
  if(!key) return;
  const seenLabels = new Set();
  STATE.active.forEach(s => {
    if(s.source !== 'macro_market' || (!s.showRegime && !s.showFwd)) return;
    const ind = MAIN_DATA.macro_market.indicators[s.key];
    if(!ind) return;
    (ind.regime || []).forEach(r => { if(r) seenLabels.add(r); });
    (ind.fwd_regime || []).forEach(r => { if(r && !r.includes('n/a')) seenLabels.add(r); });
  });

  key.innerHTML = '';
  if(!seenLabels.size){ key.style.display = 'none'; return; }
  key.style.display = 'flex';

  // group by category for a clean legend
  const byCat = {positive:[], negative:[], amber:[], neutral:[]};
  seenLabels.forEach(lbl => {
    const cat = regimeCategory(lbl);
    if(cat !== 'na' && byCat[cat]) byCat[cat].push(lbl);
  });

  ['positive','negative','amber','neutral'].forEach(cat => {
    if(!byCat[cat].length) return;
    const catDiv = el('div','key-cat');
    catDiv.style.cssText = 'display:flex;flex-wrap:wrap;gap:4px 10px;';
    byCat[cat].forEach(lbl => {
      const item   = el('div','key-item');
      const swatch = el('div','key-swatch');
      swatch.style.background = STRIP_COLORS[cat];
      swatch.style.border     = '1px solid #30363d';
      item.append(swatch, document.createTextNode(lbl));
      catDiv.appendChild(item);
    });
    key.appendChild(catDiv);
  });
}

// ── main strip render ─────────────────────────────────────────────────
function renderStrips(){
  const wrap  = document.getElementById('regime-strip-wrap');
  const inner = document.getElementById('regime-strip-inner');
  if(!inner) return;

  const geo = getXGeometry();
  const stripSeries = STATE.active.filter(
    s => s.source === 'macro_market' && (s.showRegime || s.showFwd)
  );

  if(!geo || !stripSeries.length){
    wrap.style.display = 'none';
    inner.innerHTML    = '';
    return;
  }

  wrap.style.display  = 'block';
  inner.innerHTML     = '';

  const mmDates = MAIN_DATA.macro_market.dates;
  // filter dates to current date range (same logic as getSeriesData)
  const from = STATE.dateFrom, to = STATE.dateTo;
  const filtIdx = mmDates.map((_,i)=>i).filter(i => {
    const d = mmDates[i];
    return (!from || d >= from) && (!to || d <= to);
  });
  const filtDates = filtIdx.map(i => mmDates[i]);

  stripSeries.forEach(s => {
    const ind = MAIN_DATA.macro_market.indicators[s.key];
    if(!ind) return;

    // regime row
    if(s.showRegime){
      const regimes = filtIdx.map(i => ind.regime[i] ?? null);
      const row = el('div','strip-row');
      const closeR = el('button','strip-close-btn','×');
      closeR.title = 'Remove regime strip';
      closeR.addEventListener('click', () => {
        s.showRegime = false;
        updateLegendPanel();
        renderStrips();
      });
      const lbl = el('span','strip-label', s.id);
      lbl.style.color = s.color;
      const wrap2 = el('div','strip-canvas-wrap');
      const cv    = document.createElement('canvas');
      cv.className = 'strip-canvas';
      wrap2.appendChild(cv);
      row.append(closeR, lbl, wrap2);
      inner.appendChild(row);
      // defer drawing until layout is settled
      requestAnimationFrame(() => drawStripCanvas(cv, filtDates, regimes, geo));
    }

    // fwd_regime row
    if(s.showFwd){
      const fwds = filtIdx.map(i => (ind.fwd_regime || [])[i] ?? null);
      const row2 = el('div','strip-row strip-fwd');
      const closeF = el('button','strip-close-btn','×');
      closeF.title = 'Remove fwd regime strip';
      closeF.addEventListener('click', () => {
        s.showFwd = false;
        updateLegendPanel();
        renderStrips();
      });
      const lbl2 = el('span','strip-label', s.id + ' fwd');
      const wrap3 = el('div','strip-canvas-wrap');
      const cv2   = document.createElement('canvas');
      cv2.className = 'strip-canvas';
      wrap3.appendChild(cv2);
      row2.append(closeF, lbl2, wrap3);
      inner.appendChild(row2);
      requestAnimationFrame(() => drawStripCanvas(cv2, filtDates, fwds, geo));
    }
  });

  updateColorKey();
}

// ── Status bar ─────────────────────────────────────────────────────────────
function setStatus(msg, level){
  const sb = document.getElementById('statusbar');
  sb.textContent = msg;
  sb.style.color = level === 'error' ? '#f85149' : '#484f58';
}

// ── Font size controls ──────────────────────────────────────────────────────
document.getElementById('font-controls').addEventListener('click', e => {
  const btn = e.target.closest('.font-btn');
  if(!btn) return;
  const target = btn.dataset.target;
  const delta  = parseInt(btn.dataset.delta);
  STATE.fontSize[target] = Math.max(8, Math.min(28, (STATE.fontSize[target] || 18) + delta));
  document.getElementById('fv-' + target).textContent = STATE.fontSize[target];
  // apply legend font size via CSS
  document.querySelectorAll('.legend-row-id').forEach(el => el.style.fontSize = STATE.fontSize.legend + 'px');
  document.querySelectorAll('.legend-row-name').forEach(el => el.style.fontSize = (STATE.fontSize.legend - 1) + 'px');
  document.querySelectorAll('.legend-row-formula').forEach(el => el.style.fontSize = (STATE.fontSize.legend - 2) + 'px');
  if(STATE.active.length) renderChart();
});

// ── Detail toggle ──────────────────────────────────────────────────────────
document.getElementById('btn-detail-toggle').addEventListener('click', () => {
  STATE.showDetail = !STATE.showDetail;
  const btn = document.getElementById('btn-detail-toggle');
  btn.textContent = STATE.showDetail ? 'Detail ▾' : 'Detail ▸';
  document.querySelectorAll('.legend-row-formula').forEach(el => {
    el.style.display = STATE.showDetail ? '' : 'none';
  });
  requestAnimationFrame(() => updateChartMargin());
});

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

    # ── main HTML: embed main payload inline ──────────────────────────────────
    main_json = json.dumps(main_payload, separators=(",", ":"), ensure_ascii=False)
    html = HTML_TEMPLATE.replace("__MAIN_DATA_JSON__", main_json)

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    html_mb = html_path.stat().st_size / 1e6
    print(f"  indicator_explorer.html  : {html_mb:.2f} MB")

    # ── companion JS file: market-comp data as a const global ─────────────────
    mkt_json = json.dumps(mkt_payload, separators=(",", ":"), ensure_ascii=False)
    js_content = (
        "// Auto-generated by build_html.py — do not edit manually.\n"
        "// Market data companion for indicator_explorer.html\n"
        f"const MKT_DATA = {mkt_json};\n"
    )
    with open(js_path, "w", encoding="utf-8") as f:
        f.write(js_content)

    js_mb = js_path.stat().st_size / 1e6
    print(f"  indicator_explorer_mkt.js: {js_mb:.2f} MB")


if __name__ == "__main__":
    main()
