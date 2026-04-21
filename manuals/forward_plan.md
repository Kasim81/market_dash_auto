# Market Dashboard — Forward Plan

> Last updated: 2026-04-21
> Based on: Project Plan 260327.md, multifreq_plan.md, MarketDashboard_ClaudeCode_Handover.md, METADATA_REDUNDANCY_REVIEW.md, indicator_groups_review_UPDATED.xlsx

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
| Phase E — Macro-Market Indicators | 68 composite indicators (z-scores, regimes, fwd_regimes) | Production |

### 7-Step Refactoring (completed 2026-03-30)

| Step | Description |
|---|---|
| 1 | Added `simple_dash` boolean column to `index_library.csv` |
| 2 | Rewrote simple pipeline (`market_data`) to be library-driven |
| 3 | Removed all redundant simple-pipeline hardcoded lists; deleted `market_data_hist` |
| 4 | Replaced hardcoded `PENCE_TICKERS` with dynamic `.endsWith(".L")` + median > 50 check |
| 5 | Added `broad_asset_class` column to `index_library.csv`; removed code-computed labels |
| 6 | Added `units` column to `index_library.csv`; removed `_ac_units` / `_asc_units` dicts |
| 7 | Moved 10 sentiment ratios from `market_data_comp` to `compute_macro_market.py` (7 new indicators — IDs subsequently renamed during indicator groups review) |

### Post-Refactoring Cleanup (completed 2026-03-30)

- Deleted 4 redundant CSVs: `market_data_hist.csv`, `sentiment_data.csv`, `macro_surveys.csv`, `macro_surveys_hist.csv`
- Cleaned up GitHub Actions workflow to remove stale git-add references
- Consolidated sort-order dicts and FX maps into `library_utils.py` (done prior to refactoring)
- Resolved all 12 items from `METADATA_REDUNDANCY_REVIEW.md`

### Z-Score Trend Classification in Snapshot (completed 2026-04-20)

| Change | Detail |
|---|---|
| Snapshot columns added | `macro_market` / `data/macro_market.csv` now include `zscore_1w_ago`, `zscore_4w_ago`, `zscore_13w_ago`, `zscore_peak_abs_13w`, and `zscore_trend` |
| Trend labels | `intensifying` (\|z\| rising vs 1w and 4w ago and within 5% of the 13-week peak), `fading` (\|z_now\| < 0.9 × \|z_4w\|), `reversing` (sign flip vs 4w ago from a prior \|z\| > 0.5), `stable` (none of the above) |
| Implementation | `_zscore_trend_classification()` and `_sample_z()` helpers in `compute_macro_market.py`; `build_snapshot_df()` extended accordingly |
| Consumer impact | `macro_market_hist` schema is unchanged, so `build_html.py` (which reads the history CSV) required no update; anything reading the snapshot CSV/tab must accept the new columns |

### GitHub Actions Schedule + Indicator Explorer Build (completed 2026-04-20)

| Change | Detail |
|---|---|
| Schedule shift | Daily cron moved from `0 6 * * *` (06:00 UTC) to `17 3 * * *` (03:17 UTC) to escape GitHub's top-of-hour congestion while still finishing before the 06:00 UK local automations |
| Explorer rebuild step | Workflow now runs `cd docs && python build_html.py` after `fetch_data.py`; commits `docs/indicator_explorer.html` and `docs/indicator_explorer_mkt.js` alongside the CSVs |
| Commit message | Changed from `Update market data - ...` to `Update market data + explorer - ...` |

### Indicator Groups Review & CSV-Driven Migration (completed 2026-04-08)

| Change | Detail |
|---|---|
| Indicator ID rename | All 68 indicators renamed from internal codes (e.g. `US_I1`→`US_G1`, `US_I5`→`US_Cr2`) to semantic IDs reflecting group/function |
| CSV single source of truth | `macro_indicator_library.csv` now drives all metadata — no hardcoded `INDICATOR_META` or `NATURALLY_LEADING` in Python |
| Group/sub_group hierarchy | Added `group` and `sub_group` columns to CSV; `build_html.py` sidebar uses 3-level nesting (group → sub_group → indicator) |
| `region_block` removed | Legacy column dropped from CSV and Sheets snapshot; replaced by `group`/`sub_group` |
| Sheets snapshot updated | `macro_market` tab now outputs `id, group, sub_group, category, last_date, raw, zscore, regime, fwd_regime, formula_note` |
| Z-score window | Changed from 260 weeks (5yr) to 156 weeks (3yr) for faster regime responsiveness |
| US_G3 ticker | Switched from XLF (broad financials) to ^SP500-4010 (Banks industry group) for purer credit-cycle signal |
| US_EQ_F2 inverted | Now Value/Growth (IVE/IVW) to match US_EQ_F1 convention — positive z = value regime |
| US_Cr2 5-regime | New framework: opportunity (>800bps), stress (>500bps), normal, complacent (<400bps), frothy (<300bps) |
| Amber palette | New 4th regime color category for complacent/caution/elevated/late-cycle labels |
| US_LEI1 removed | USSLIND permanently discontinued by Philadelphia Fed in 2025 |
| PNG snapshot | Custom download composites chart title, Plotly image, legend, and regime color key onto a single canvas |
| Sort orders | Sectors now follow custom ordering (Consumer Staples first); Industry Groups and Industries sorted by GICS ticker code |
| Forward regime system | `fwd_regime` column added: improving/stable/deteriorating with optional [leading] suffix |

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

*All issues resolved.* EU_R1 metadata/code mismatch fixed during indicator groups review — CSV and code now both describe BTP-Bund spread (IRLTLT01ITM156N − IRLTLT01DEM156N).

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

---

## 4. New Feature Development

### 4.1 Phase D — PMI / Survey Data

**Priority:** Low-medium — regional Fed surveys are already covered via FRED in `macro_us`.
**Status:** Not started. `FMP_API_KEY` secret not registered.

**Decision needed:** Check whether ISM Manufacturing PMI and ISM Services PMI are available via FRED directly. If so, FMP may be unnecessary — add them to `macro_library_fred.csv` and the existing FRED fetch pattern handles the rest. If not, register for a free FMP API key and implement a new module.

FRED series to check first:
- `NAPM` — ISM Manufacturing PMI (may have replaced `NAPMPI`)
- `NMFCI`, `NMFBAI` — ISM Non-Manufacturing (Services)
- Empire State Manufacturing: check FRED coverage
- Philly Fed components: many available on FRED

### 4.2 Instrument Expansion

**Priority:** Medium — broadens market coverage.
**Status:** Blocked on owner decision.
**Action:** Kasim to confirm target instrument list before implementation. Categories to consider:

- Europe sector ETFs (`.DE`, EUR-denominated)
- EM regional ETFs
- UK style ETFs
- Asia/Japan additional coverage

Once confirmed, add rows to `index_library.csv` — no new Python modules needed. For each new instrument:
1. Verify ticker returns data via `python -c "import yfinance as yf; print(yf.Ticker('TICKER').history(period='5d'))"`
2. Set correct `base_currency` (required for FX conversion)
3. Set `validation_status = "CONFIRMED"`
4. For `.L` tickers: pence correction is automatic (no code change needed)
5. For new currencies: add to `COMP_FX_TICKERS` and `COMP_FCY_PER_USD` in `library_utils.py`

### 4.3 Calculated Fields Expansion

Several calculated fields were proposed but not yet implemented. Some may already be covered by the 68 macro-market indicators — audit before building duplicates.

| Field | Formula | Status |
|---|---|---|
| HY/IG ratio | BAMLH0A0HYM2 / BAMLC0A0CM | Covered by US_Cr3 (HY-IG spread) |
| EMFX basket | Equal-weight CNY, INR, KRW, TWD vs USD | Not yet implemented |
| EEM/IWDA ratio | EEM / IWDA.L (FX-adjusted) | Not yet implemented |
| MOVE proxy | 30-day realised vol on ^TNX | Not yet implemented |
| Global PMI proxy | Equal-weight ISM + Eurozone PMI + Japan PMI | Depends on Phase D |
| Global yield curve | Average of US/DE/UK/JP 10Y-2Y spreads | Not yet implemented |

**Action:** Audit the 68 indicators in `compute_macro_market.py` against this list to confirm coverage before building. New indicators follow the CSV-driven pattern: write a `_calc_*` function, add to `REGIME_RULES` and the relevant `_*_CALCULATORS` dict, add a row to `macro_indicator_library.csv`. No hardcoded metadata needed — everything is read from the CSV at runtime.

### 4.4 Sheets Export Audit (Phase G)

**Priority:** Low — housekeeping.

- Verify all active tabs are pushed correctly by the relevant modules
- Confirm tab names match exactly (lowercase with underscores)
- Record GIDs for all tabs created since the handover
- Confirm batch write logic (10,000 rows per call) is used for large tabs
- Confirm protected-tab guard blocks writes to `market_data` and `sentiment_data`
- Verify legacy tab deletion (`TABS_TO_DELETE` in fetch_data.py) is working

### 4.5 Library Manager Utility

**Priority:** Low — developer tooling.

Create `library_manager.py` — a standalone utility for maintaining `index_library.csv`:

- Validate all tickers against yfinance (flag those returning no data)
- Auto-set `validation_status = "UNAVAILABLE"` for dead tickers
- Suggest alternative tickers for unavailable instruments
- Check metadata consistency (no duplicate tickers, all required fields filled)
- Run manually (`python library_manager.py`), not as part of the daily pipeline

### 4.6 Incremental Fetch Mode (fetch_hist.py)

**Priority:** Medium — performance improvement.

Currently `fetch_hist.py` rebuilds the entire dataset from scratch on every run (~8-12 min for `run_comp_hist()`). An incremental append mode would:

1. Check the last date in the existing CSV
2. Only fetch new weekly rows since the last update
3. Append to existing data rather than full rebuild

This would reduce daily historical data runtime from ~10 minutes to seconds.

---

## 5. Multi-Frequency Pipeline (Phase 2)

**Priority:** High impact but large effort. Detailed plan exists in `multifreq_plan.md`.
**Status:** Not started.

### Objective

Replace the weekly Friday spine with native-frequency storage using ragged columns — each series gets its own date column + value column(s). This eliminates wasted cells from forward-filling monthly/quarterly data to weekly, and provides genuine daily granularity for market prices.

### Design: Ragged Column Format

```
Date_SPY  | SPY_Local | SPY_USD | Date_UNRATE | UNRATE  | ...
1990-01-02| 35.2      | 35.2    | 1990-01-01  | 5.4     |
1990-01-03| 35.5      | 35.5    | 1990-02-01  | 5.3     |
1990-01-04| 35.1      | 35.1    | 1990-03-01  | 5.2     |
...       | ...       | ...     | (ends here) |         |
```

- Market data: daily from 1990 (not weekly)
- Macro data: stored at native frequency (monthly, quarterly, annual) — no forward-fill
- `macro_market_hist` stays weekly — resample final indicators to W-FRI for output

### Cell Budget

| Tab | Columns | Max Rows | Cells |
|---|---|---|---|
| `market_data_comp_hist` | 390 x 3 = ~906 | ~9,000 | ~8.15M |
| `macro_us_hist` | 43 x 2 = ~86 | ~430 (monthly) | ~37K |
| `macro_intl_hist` | 56 x 2 = ~112 | ~430 | ~48K |
| `macro_market_hist` | 150 (keep weekly) | ~1,300 | ~195K |
| Snapshots | small | small | ~10K |
| **Total** | | | **~8.4M** |

Google Sheets limit is 10M cells. Headroom is tight. Future optimisation: drop `_Local` columns for USD-base tickers (saves ~150 columns).

### Implementation Steps

1. **Add alignment utilities to `library_utils.py`:** `load_ragged_series()`, `align_series()`, `detect_frequency()`, `freq_aware_shift()`
2. **Convert `fetch_hist.py` to ragged output:** Replace spine-aligned builders with per-ticker ragged output
3. **Convert `fetch_macro_international.py` to native frequency:** Store OECD monthly and WB/IMF annual at their natural cadence
4. **Update `compute_macro_market.py`:** All 68 indicator calculator functions updated to consume ragged data via alignment utilities
5. **Validate:** Compare indicator values between weekly and ragged branches for overlapping Friday dates

### Risks

1. **Sheets cell budget tight (8.4M/10M)** — if more tickers added, may need to drop `_Local` for USD-base instruments or split tabs
2. **68 indicator functions to update** — each must be tested individually against weekly branch output
3. **Z-score window equivalence** — 156 weekly != 780 daily (trading vs calendar days); verify regime classifications match
4. **Cherry-pick conflicts** — hist/compute changes won't merge cleanly between branches; manual adaptation needed

---

## 6. Operational & Infrastructure

### GitHub Actions

- **60-day inactivity pause:** GitHub Actions auto-pauses workflows after 60 days of no pushes to the repo. The daily pipeline produces commits, so this is not currently an issue, but will trigger if the pipeline fails for an extended period. Fix: push a trivial commit or re-enable from the Actions tab.
- **Run timeout:** Currently set to 120 minutes. Monitor if incremental fetch mode (section 4.6) reduces this.

### Google Sheets

- **CDN caching:** GitHub raw CSV URLs cache aggressively. Always use the Sheets export URL with `gid=` parameter for up-to-date data.
- **Legacy tab cleanup:** `TABS_TO_DELETE` in `fetch_data.py` automatically removes deprecated tabs (`Market Data`, `sentiment_data`, `macro_surveys`, `macro_surveys_hist`, `market_data_hist`) on every run. These will stop appearing once the Sheets-side Apps Script (if any) stops recreating them.
- **Spreadsheet ID:** `12nKIUGHz5euDbNQPDTVECsJBNwrceRF1ymsQrIe4_ac` — hardcoded in all 5 modules that write to Sheets.

### Downstream Consumer: trigger.py

`trigger.py` runs at 06:15 London time on a local Windows machine (`C:\Users\kasim\ClaudeWorkflow\`). It reads only:
- `market_data` tab (via Sheets CSV export, GID `68683176`)

No other tabs are consumed by trigger.py. Changes to macro, history, or indicator tabs do not affect the downstream consumer.

### index_library.csv Maintenance

The library is the single source of truth for all instrument metadata. It is built and maintained via a separate Claude project located at `C:\Users\kasim\OneDrive\Claude\Index Library\build_library.ipynb`. See the `TECHNICAL_MANUAL.md` in that folder for the library build process.

To add a new instrument without the library builder:
1. Add a row to `data/index_library.csv` with `validation_status = "CONFIRMED"`
2. Verify the ticker works: `python -c "import yfinance as yf; print(yf.Ticker('TICKER').history(period='5d'))"`
3. Set `base_currency` correctly — required for FX conversion
4. Set `simple_dash = True` if it should appear in the simple dashboard
5. Changes take effect on the next pipeline run — no Python code changes needed

---

*End of Forward Plan*