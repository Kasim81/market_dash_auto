# Metadata Redundancy Review

> Status: **Review only — no code changes made**
> Date: 2026-03-20

This document catalogues every place in the codebase where code does more than simply reading a value from `index_library.csv`. Items are categorised by severity: **Breaking** (will cause a bug with the updated library), **Redundant** (duplicated or re-derived data that already exists in the library), and **Structural** (design patterns worth revisiting but not inherently wrong).

---

## 1. BREAKING — `data_source` filter is now wrong

**Files:** `fetch_data.py:784`, `fetch_hist.py:1297`

The code filters the library to yfinance instruments using:
```python
df["data_source"] == "yfinance"          # fetch_data.py:784
df["data_source"] == "yfinance"          # fetch_hist.py:1297
```

The **updated** `index_library.csv` changed `data_source` values:

| Old value | New value |
|---|---|
| `yfinance` | `yfinance PR` |
| (no separate TR concept) | `yfinance TR` |
| `fred` | `FRED` |
| — | `UNAVAILABLE` |

**Effect:** Both `load_instrument_library()` (fetch_data.py) and `load_comp_instruments()` (fetch_hist.py) will return **zero instruments** because no rows match `== "yfinance"` any more. The comp pipeline runs silently with an empty instrument list. The `FRED` filter in `collect_comp_fred_assets()` (line 947) and `load_comp_fred_rates()` (line 1358) happens to still work because the capitalisation now matches.

**Decision needed:** Decide how to filter. Options:
- Filter on `data_source.str.startswith("yfinance")`
- Filter on `data_source.isin(["yfinance PR", "yfinance TR"])`
- Add a boolean column `use_pr` / `use_tr` to the library

---

## 2. BREAKING — `ticker_yfinance_pr` logic in `load_comp_instruments()` needs revisiting

**File:** `fetch_hist.py:1326-1342`

`load_comp_instruments()` reads both `ticker_yfinance_pr` and `ticker_yfinance_tr` from every row — it creates two instrument entries (PR + TR) for a row that has both.

With the new library, rows with `data_source = "yfinance TR"` have **no** `ticker_yfinance_pr` value, only a `ticker_yfinance_tr`. If the `data_source` filter is fixed (item 1 above), this function would still work correctly for those rows — but **only if** the `data_source` filter is broadened to include `"yfinance TR"` rows.

The function in `fetch_data.py:load_instrument_library()` has the same pattern (lines 816–843).

---

## 3. REDUNDANT — Entire Simple Pipeline instrument list is hardcoded (does not use library)

**Files:** `fetch_data.py:219–308`, `fetch_hist.py:94–202`

The simple pipeline (`market_data` tab) has its own **completely hardcoded** instrument lists, duplicating metadata that already lives in `index_library.csv`. These include display names, regions, asset classes, and currencies:

### fetch_data.py hardcoded lists (lines 219–308)

| Constant | Instruments | Library column overlap |
|---|---|---|
| `EQUITY_INDEX` | 12 equity indices | `name`, `region`, `asset_class`, `base_currency` |
| `EQUITY_ETF` | 8 equity ETFs | same |
| `SECTOR_ETF` | 13 sector/style ETFs | same |
| `FIXED_INCOME_ETF` | 9 fixed income ETFs | same |
| `COMMODITY` | 9 commodities | same |
| `FX_ASSETS` | 8 FX pairs | same |
| `VOLATILITY` | 3 vol/crypto | same |
| `YIELD_YF` | 4 yfinance yields | same |
| `FRED_YIELDS` | 4 FRED yield series | name from library; series ID from library |

### fetch_hist.py hardcoded lists (lines 94–202)

Exact same instruments as above, under different constant names (`EQUITY_INDICES`, `EQUITY_ETFS`, etc.) with **slightly different metadata**:

- `VFEM.L` region: `"Global"` in fetch_data.py vs `"EM"` in fetch_hist.py
- `ILF` region: `"LatAm"` in fetch_data.py vs `"EM"` in fetch_hist.py
- `^N225` region: `"Asia"` in fetch_data.py vs `"Japan"` in fetch_hist.py
- `SLXX.L`, `IHYU.L`, `VDET.L` region: `"North America"/"Global"` in fetch_data.py vs `"US"/"EM"` in fetch_hist.py

The same instruments appear three times in total: once in `index_library.csv`, once in `fetch_data.py`, and once in `fetch_hist.py`.

### fetch_hist.py FRED_YIELDS dict (line 188–193)

```python
FRED_YIELDS = {
    "DGS2":              ("US 2Y Treasury Yield",  "US",     "Yield", "USD"),
    "IRLTLT01GBM156N":   ("UK 10Y Gilt Yield",     "UK",     "Yield", "GBP"),
    "IRLTLT01DEM156N":   ("Germany 10Y Bund Yield","Europe", "Yield", "EUR"),
    "IRLTLT01JPM156N":   ("Japan 10Y JGB Yield",   "Japan",  "Yield", "JPY"),
}
```

These series IDs and names are already in `index_library.csv` (Rates rows with `data_source = "FRED"`). This is a separate hardcoded copy.

---

## 4. REDUNDANT — `PENCE_TICKERS` hardcoded set

**File:** `fetch_data.py:323–329`

```python
PENCE_TICKERS = {
    "IWDA.L", "VFEM.L", "NDIA.L",
    "IWFV.L",
    "AGGG.L", "SLXX.L", "IHYU.L", "VDET.L", "IGLT.L", "IGLS.L",
    "CNYB.L", "CMOD.L",
}
```

Used in `collect_yf_assets()` (simple pipeline only). In the comp pipeline (`fetch_hist.py:1537`) and comp hist pipeline, the pence correction uses `ticker.endswith(".L")` + median check instead, which is more robust and requires no maintained list.

The `index_library.csv` doesn't have a pence flag column, but a robust check on `.endswith(".L")` plus a median price heuristic is already the better approach and used in the comp path. The simple pipeline's hardcoded set is inconsistent with the comp pipeline approach.

---

## 5. REDUNDANT — `LEVEL_CHANGE_TICKERS` / `COMP_LEVEL_CHANGE_TICKERS` hardcoded sets

**Files:** `fetch_data.py:321`, `fetch_data.py:78–81`

```python
LEVEL_CHANGE_TICKERS = {"^VIX"}                                   # simple pipeline
COMP_LEVEL_CHANGE_TICKERS = {"^VIX", "^VIX9D", "^VIX3M", ...}    # comp pipeline
```

These sets identify vol indices that should show absolute point change, not % change. There is no corresponding field in `index_library.csv` to indicate this behaviour. Any new volatility ticker added to the library would silently get % change treatment unless the Python set is manually updated.

---

## 6. REDUNDANT — Sort order dictionaries duplicated in both files

**Files:** `fetch_data.py:90–210`, `fetch_hist.py:1089–1192`

The following sort-order dictionaries are **identical in content** but defined twice (different variable names):

| fetch_data.py name | fetch_hist.py name |
|---|---|
| `_LIB_ASSET_CLASS_GROUP` | `_ASSET_CLASS_GROUP` |
| `_LIB_REGION_ORDER` | `_REGION_ORDER` |
| `_LIB_EQUITY_SUBCLASS_ORDER` | `_EQUITY_SUBCLASS_ORDER` |
| `_LIB_SECTOR_ORDER` | `_SECTOR_ORDER` |
| `_LIB_FI_SUBCLASS_ORDER` | `_FI_SUBCLASS_ORDER` |
| `_LIB_MATURITY_ORDER` | `_MATURITY_ORDER` |
| `_LIB_COMMODITY_GROUP_ORDER` | `_COMMODITY_GROUP_ORDER` |
| `_LIB_VOL_SUBCLASS_ORDER` | `_VOL_SUBCLASS_ORDER` |
| `_LIB_RATES_SUBCLASS_ORDER` | `_RATES_SUBCLASS_ORDER` |

And correspondingly, the sort key functions `_lib_sort_key()` (fetch_data.py:167) and `_comp_inst_sort_key()` (fetch_hist.py:1195) are **logic-identical** — same conditions, same structure.

These are maintained in parallel. Any change to sort order must be applied in both files.

---

## 7. REDUNDANT — FX ticker maps duplicated three times

**Files:** `fetch_data.py:25–37`, `fetch_data.py:47–75`, `fetch_hist.py:205–218`, `fetch_hist.py:1244–1270`

| Constant | File | Purpose |
|---|---|---|
| `FX_TICKERS` (7 currencies) | fetch_data.py:25 | Simple pipeline snapshot FX |
| `FCY_PER_USD` (5 currencies) | fetch_data.py:37 | Simple pipeline inversion flags |
| `COMP_FX_TICKERS` (18 currencies) | fetch_data.py:47 | Comp pipeline snapshot FX |
| `COMP_FCY_PER_USD` (15 currencies) | fetch_data.py:71 | Comp pipeline inversion flags |
| `FX_TICKERS` (7 currencies) | fetch_hist.py:205 | Simple hist FX |
| `base_quote_pairs` (5 currencies) | fetch_hist.py:333 | Simple hist inversion flags (inline set) |
| `COMP_FX_TICKERS_HIST` (18 currencies) | fetch_hist.py:1244 | Comp hist FX |
| `COMP_FCY_PER_USD_HIST` (15 currencies) | fetch_hist.py:1266 | Comp hist inversion flags |

The currency codes come from `base_currency` in the library, but the mapping from currency code → yfinance ticker string must be defined somewhere in code. These are correctly not in the library. However, the same maps are defined 4 separate times (2 in fetch_data.py, 2 in fetch_hist.py) where consolidation to one shared location would reduce maintenance burden.

---

## 8. REDUNDANT — "Broad Asset Class" derived by code, not read from library

**File:** `fetch_data.py:876–883` (inside `collect_comp_assets()`)

```python
broad_ac = (
    "Macro-Market Indicators" if asset_class_raw == "Volatility"
    else asset_class_raw if asset_class_raw in ("FX", "Crypto")
    else "Commodities" if asset_class_raw == "Commodity"
    else "Bonds" if asset_class_raw == "Fixed Income"
    else "Equity" if asset_class_raw == "Equity"
    else asset_class_raw
)
```

And again at `fetch_data.py:975` for FRED rows:
```python
broad_ac = "Spreads" if asset_subclass == "Credit Spread" else "Bonds"
```

And in `fetch_hist.py:772–784` (`build_market_meta_prefix()`):
```python
_broad_ac_map = {
    "Equity Index": "Equity", "Equity ETF": "Equity", ...
    "Volatility": "Macro-Market Indicators", ...
}
```

The "Broad Asset Class" label shown in the `market_data_comp` tab is computed from `asset_class` using Python logic rather than read from a library column. This means the label can silently differ from what is in the library. The library has `asset_class` (e.g. "Equity", "Fixed Income", "Volatility") but no separate "display group" column.

---

## 9. REDUNDANT — Region override for UK and Japan applied in code

**Files:** `fetch_data.py:809–814`, `fetch_hist.py:1318–1323`

```python
# Both files contain this logic:
if asset_cls_raw in ("Equity", "Fixed Income"):
    if country == "United Kingdom":
        region = "UK"
    elif country == "Japan":
        region = "Japan"
```

This overrides the `region` value from the library for UK and Japan instruments in the Equity and Fixed Income classes. The library has `region = "Europe"` for UK instruments and `region = "Asia Pacific"` for Japanese instruments, but the code changes these to `"UK"` and `"Japan"` at runtime.

This is a display preference baked into code. It creates divergence between the `region` value stored in the library and the `region` value written to the output sheets.

---

## 10. STRUCTURAL — Ratio/spread definitions are entirely hardcoded

**Files:** `fetch_data.py:622–641` (simple), `fetch_data.py:691–706` (comp), `fetch_hist.py:196–201`

The calculated ratio rows (XLY/XLP, HY/IG, etc.) and the yield curve spread row (TNX−DGS2) are defined entirely in Python with hardcoded names, regions, and asset class labels. They do not come from `index_library.csv` in any way.

**Simple pipeline ratios (fetch_data.py:622):**
```python
ratios = [
    ("XLY", "XLP", "Cyclicals vs Defensives (US/Global proxy)", "Global", "Sentiment Ratio"),
    ("XLF", "XLU", "Financials vs Utilities", "Global", "Sentiment Ratio"),
    ...
]
```

**Comp pipeline ratios (fetch_data.py:691):**
```python
ratios = [
    ("SPY", "GOVT", "Risk-On vs Risk-Off (Equities vs Treasuries)", "North America", "Sentiment Ratio"),
    ("XLY", "XLP", "Cyclicals vs Defensives", "North America", "Sentiment Ratio"),
    ...
]
```

These are synthetic instruments that don't have a natural home in a ticker-based library. Whether to add them to the library (as a "ratio" or "calculated" row type) is a design decision.

---

## 11. STRUCTURAL — `units` and `_ac_units` mapping hardcoded in hist metadata

**File:** `fetch_hist.py:757–768`

```python
_ac_units = {
    "Equity Index": "Index",
    "Equity ETF":   "Price",
    "Sector ETF":   "Price",
    ...
    "Yield":        "% pa",
    "Ratio":        "Ratio",
}
```

The "Units" row in the `market_data_hist` metadata prefix is derived by mapping the hardcoded asset class strings to units labels. There is no `units` column in `index_library.csv`. If a new asset class type is added to the library, it won't have a units label until this dict is updated.

---

## 12. STRUCTURAL — `RATIO_DEFS` and `build_market_meta_prefix()` use hardcoded instrument metadata

**File:** `fetch_hist.py:196–201`, `fetch_hist.py:742–750`

The hist build has its own `RATIO_DEFS` list (line 196) that defines calculated ratio columns for `market_data_hist`. The metadata prefix builder `build_market_meta_prefix()` then pulls names, regions, and asset classes from `ALL_YFINANCE` (the hardcoded list), `FRED_YIELDS` (hardcoded), and `RATIO_DEFS` — not from the library.

This means the metadata rows in the `market_data_hist` Sheets tab are derived entirely from the hardcoded lists, not from `index_library.csv`.

---

## Summary Table

| # | Location | Nature | Severity |
|---|---|---|---|
| 1 | `fetch_data.py:784`, `fetch_hist.py:1297` | `data_source == "yfinance"` filter broken by library update | **BREAKING** |
| 2 | `fetch_data.py:816–843`, `fetch_hist.py:1325–1342` | PR/TR ticker logic needs revisiting alongside item 1 | **BREAKING** |
| 3 | `fetch_data.py:219–308`, `fetch_hist.py:94–202` | Entire simple pipeline instrument list hardcoded (names, regions, currencies, asset classes) | Redundant |
| 4 | `fetch_data.py:323–329` | `PENCE_TICKERS` hardcoded set (not needed for comp path; comp path uses `.endswith(".L")`) | Redundant |
| 5 | `fetch_data.py:78–81`, `fetch_data.py:321` | `LEVEL_CHANGE_TICKERS` / `COMP_LEVEL_CHANGE_TICKERS` not in library | Redundant |
| 6 | `fetch_data.py:90–210`, `fetch_hist.py:1089–1192` | Sort order dicts and sort key functions duplicated 1:1 across both files | Redundant |
| 7 | `fetch_data.py:25–75`, `fetch_hist.py:205–218`, `fetch_hist.py:1244–1270` | FX ticker maps + inversion flag sets defined 4 times across 2 files | Redundant |
| 8 | `fetch_data.py:876–883`, `fetch_data.py:975`, `fetch_hist.py:772–784` | "Broad Asset Class" label computed in code, not read from library | Redundant |
| 9 | `fetch_data.py:809–814`, `fetch_hist.py:1318–1323` | Region overridden to "UK"/"Japan" in code, contradicting library values | Redundant |
| 10 | `fetch_data.py:622–641`, `fetch_data.py:691–706`, `fetch_hist.py:196–201` | Ratio/spread definitions entirely hardcoded, not from library | Structural |
| 11 | `fetch_hist.py:757–768` | `_ac_units` mapping from asset class → units string, not in library | Structural |
| 12 | `fetch_hist.py:742–750` | `build_market_meta_prefix()` sources all metadata from hardcoded lists, not library | Structural |

---

## Priority for next session

Suggested order based on impact:

1. **Fix items 1 & 2 immediately** — the comp pipeline is silently producing no yfinance instrument data with the updated library. The `data_source` filter is the gating issue.

2. **Decide on simple pipeline fate (item 3)** — either:
   - Keep simple pipeline as-is (hardcoded, separate, always run first)
   - Drive simple pipeline from library too (requires agreement on which rows are "simple pipeline" — could be a boolean flag column in library)

3. **Consolidate FX maps (item 7)** — low risk, reduces double-maintenance

4. **Resolve region overrides (item 9)** — decide if "UK" / "Japan" should be added as `region` values in the library directly, or whether the override stays in code

5. **Items 4–6, 8** — lower priority cleanup once instrument lists are stable
