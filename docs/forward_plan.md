# Market Dashboard — Forward Plan

> Last updated: 2026-03-30
> Based on: Project Plan 260327.md, multifreq_plan.md, MarketDashboard_ClaudeCode_Handover.md, METADATA_REDUNDANCY_REVIEW.md

---

## Table of Contents

1. [Completed Work](#1-completed-work)
2. [Bug Fixes & Data Quality](#2-bug-fixes--data-quality)
3. [Metadata & Label Corrections](#3-metadata--label-corrections)
4. [New Feature Development](#4-new-feature-development)
5. [Multi-Frequency Pipeline (Phase 2)](#5-multi-frequency-pipeline-phase-2)
6. [Operational & Infrastructure](#6-operational--infrastructure)

---

## 1. Completed Work

### Production Phases

| Phase | Description | Status |
|---|---|---|
| Simple Pipeline | ~70 library-driven instruments — daily snapshot | Production |
| Comp Pipeline | ~390 library-driven instruments — daily snapshot + weekly history | Production |
| Phase A — US Macro (FRED) | ~43 FRED series — snapshot + weekly history | Production |
| Phase C — International Macro | OECD CLI, unemployment, CPI, GDP, rates for 11 countries | Production |
| Phase E — Macro-Market Indicators | 57 composite indicators (z-scores, regimes) | Production |

### 7-Step Refactoring (completed 2026-03-30)

| Step | Description |
|---|---|
| 1 | Added `simple_dash` boolean column to `index_library.csv` |
| 2 | Rewrote simple pipeline (`market_data`) to be library-driven |
| 3 | Removed all redundant simple-pipeline hardcoded lists; deleted `market_data_hist` |
| 4 | Replaced hardcoded `PENCE_TICKERS` with dynamic `.endsWith(".L")` + median > 50 check |
| 5 | Added `broad_asset_class` column to `index_library.csv`; removed code-computed labels |
| 6 | Added `units` column to `index_library.csv`; removed `_ac_units` / `_asc_units` dicts |
| 7 | Moved 10 sentiment ratios from `market_data_comp` to `compute_macro_market.py` (7 new indicators: US_G2b, US_G3b, US_G4b, US_I6b, US_I8, US_I9, US_I10) |

### Post-Refactoring Cleanup (completed 2026-03-30)

- Deleted 4 redundant CSVs: `market_data_hist.csv`, `sentiment_data.csv`, `macro_surveys.csv`, `macro_surveys_hist.csv`
- Cleaned up GitHub Actions workflow to remove stale git-add references
- Consolidated sort-order dicts and FX maps into `library_utils.py` (done prior to refactoring)
- Resolved all 12 items from `METADATA_REDUNDANCY_REVIEW.md`

### Previously Resolved Issues

| Issue | Resolution |
|---|---|
| `data_source == "yfinance"` filter returned zero instruments | Now uses `.isin(["yfinance PR", "yfinance TR"])` |
| PR/TR ticker logic needed updating | Both files branch on source type with dedup via `seen` set |
| `LEVEL_CHANGE_TICKERS` hardcoded | Now loaded from `data/level_change_tickers.csv` with fallback |
| Sort-order dicts duplicated across files | Consolidated in `library_utils.py` |
| FX ticker maps defined 4 times | Consolidated in `library_utils.py` (`COMP_FX_TICKERS`, `COMP_FCY_PER_USD`) |
| Region overridden to "UK"/"Japan" at runtime | No runtime override in current code |
| Vol tickers computing % return instead of point change | All 14 vol tickers now in `level_change_tickers.csv` |
| `fetch_yf_history` returning intraday bars | Series capped to exclude current UTC date |
| `calc_return` period windows drifting | Now computed relative to `series.index[-1]` |
| Wrong FRED series IDs (Richmond, KC, Philly, SLOOS) | All corrected |
| `NAPMPI` deleted from FRED | Removed from series list |

---

## 2. Bug Fixes & Data Quality

### Priority 1: Currently Broken Data Sources

These are returning no data and need investigation:

| Issue | Module | Suggested Action |
|---|---|---|
| OECD DF_FINMARK (short-term interest rates) returning zero data for all 11 countries | fetch_macro_international.py | Investigate correct SDMX query key for the new `sdmx.oecd.org` API. The dataflow ID may have changed during the July 2024 migration. Test with a direct browser query first. |
| IMF `XM` code (Eurozone GDP Growth) returning no data | fetch_macro_international.py | Investigate correct IMF DataMapper country code for Eurozone. Try `EUR`, `EMU`, `EU` as alternatives to `XM`. |
| OECD EA19 and CHE CLI missing | fetch_macro_international.py | Structural limitation — OECD doesn't publish CLI for these codes. Consider using DEU+FRA average as Eurozone proxy (already done in `compute_macro_market.py`). Document as known gap. |
| UMCSE (UMich Expectations) returning null | fetch_macro_us_fred.py | May be FRED access restriction or temporary issue. Monitor across runs. If persistent, check if series ID has changed. |

### Priority 2: Code/Metadata Mismatches

| Issue | Location | Suggested Action |
|---|---|---|
| EU_R1 metadata/code mismatch | compute_macro_market.py | `INDICATOR_META` says `log(SLXX.L / IGLT.L)` but `_calc_EU_R1` code reads FRED `IRLTLT01DEM156N` (Germany 10Y yield). Decide which formula is correct and align code + metadata. |

---

## 3. Metadata & Label Corrections

These are minor fixes to `index_library.csv` metadata that don't affect pipeline logic but improve data quality:

| Ticker | Current Value | Correct Value | Field |
|---|---|---|---|
| `^IRX` | name: "US 2Y Treasury Yield" | "US 3-Month T-Bill Yield" | `name` |
| XLE, XLB, XLI, XLK, XLV, XLF, XLU, XLP, XLY, XLRE | region: "North America" | "US" | `region` |
| `IWF` | region: "North America" | "US" | `region` |
| `^VIX` | region: "Global" | "US" | `region` |

### Excluded Indicators (Do Not Implement Without Instruction)

These were evaluated and deliberately excluded:

| Indicator | Reason | Proxy Used Instead |
|---|---|---|
| Atlanta Fed GDPNow | Web scrape only — no clean API | None |
| Fed Funds Futures implied path | CME paid subscription | None |
| Goldman Sachs FCI | Proprietary | Chicago Fed NFCI (FRED: NFCI) |
| Bloomberg FCI | Bloomberg terminal required | Chicago Fed NFCI |
| MOVE Index | Bloomberg terminal required | 30-day realised vol on ^TNX (future) |
| JP Morgan Global PMI | S&P Global licence required | Equal-weight ISM + EZ PMI + Japan PMI (future) |
| EM Currencies Index (EMFX) | JP Morgan proprietary | Basket of CNY/INR/KRW/TWD vs USD (future) |
| China 10Y yield (FRED) | Data quality issues | CNYB.L ETF as proxy |