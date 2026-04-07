"""
build_html.py
=============
Generates two data payload files from the four _hist CSVs:
  - payload_main.json   (~4 MB)  : macro_market_hist + macro_us_hist + macro_intl_hist
  - payload_mkt.json    (~20 MB) : market_data_comp_hist (all 712 series)

Run from the docs/ directory:
    python3 build_html.py

After Step 1 inspection these payloads are embedded into the final HTML in Step 6.
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
        col_s = str(col).strip()
        series[col_s] = {
            "meta":   series_meta.get(col_s, {"Series ID": col_s}),
            "values": _series_to_list(df[col]),
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
        col_s = str(col).strip()
        series[col_s] = {
            "meta":   series_meta.get(col_s, {"Column ID": col_s}),
            "values": _series_to_list(df[col]),
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
        m = series_meta.get(col_s, {})
        asset_class = m.get("Broad Asset Class", "Other")
        groups.setdefault(asset_class, []).append(col_s)
        series[col_s] = {
            "meta":   m,
            "values": _series_to_list(df[col]),
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
    print(f"\npayload_main.json : {(DOCS / 'payload_main.json').stat().st_size / 1e6:.2f} MB")
    print(f"payload_mkt.json  : {(DOCS / 'payload_mkt.json').stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
