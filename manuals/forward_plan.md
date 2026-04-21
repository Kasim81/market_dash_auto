# Market Dashboard — Forward Plan

> Last updated: 2026-04-21
> Based on: [`manuals/technical_manual.md`](technical_manual.md), [`manuals/multifreq_plan.md`](multifreq_plan.md), `archive/indicator_groups_review_UPDATED.xlsx`, and the historic `Project Plan 260327.md`, `MarketDashboard_ClaudeCode_Handover.md`, `METADATA_REDUNDANCY_REVIEW.md` (deleted from working tree; retained in git history — content consolidated into `technical_manual.md` and this file).

---

## Table of Contents

1. [Project Phase Summary (A-G)](#1-project-phase-summary-a-g)
2. [Completed Work](#2-completed-work)
3. [Bug Fixes & Data Quality](#3-bug-fixes--data-quality)
4. [Metadata & Label Corrections](#4-metadata--label-corrections)
5. [New Feature Development](#5-new-feature-development)
6. [Multi-Frequency Pipeline (Phase 2)](#6-multi-frequency-pipeline-phase-2)
7. [Operational & Infrastructure](#7-operational--infrastructure)

---

## 1. Project Phase Summary (A-G)

The project evolved from a single hardcoded pipeline into a sequence of lettered phases (A-G). Phase labels follow the convention used in `fetch_data.py` and `manuals/technical_manual.md`. Each runtime phase is wrapped in its own `try/except` so a failure in a later phase cannot affect earlier outputs.

| Phase | Scope | Module(s) / Tab(s) | Status |
|---|---|---|---|
| Simple Pipeline | Original 66-instrument daily snapshot; consumed downstream by `trigger.py` | `fetch_data.py` → `market_data`, `sentiment_data` | Production |
| Comp Pipeline | Library-driven ~390-instrument snapshot + weekly history from 1990 | `fetch_data.py`, `fetch_hist.py` → `market_data_comp`, `market_data_comp_hist` | Production |
| Phase A — US Macro (FRED) | 43 FRED series (yields, inflation, labour, credit, surveys). Snapshot + weekly history from 1947. | `fetch_macro_us_fred.py` → `macro_us`, `macro_us_hist` | Production |
| Phase B — Surveys | Planned standalone surveys module (SLOOS, regional Fed, UMich sub-indices) | Consolidated into Phase A (`macro_us`) | Consolidated |
| Phase C — International Macro | OECD CLI / unemployment / short rates + World Bank CPI + IMF GDP for 11 economies | `fetch_macro_international.py` → `macro_intl`, `macro_intl_hist` | Production |
| Phase D — PMI / FMP | ISM Manufacturing & Services PMI; additional regional Fed survey sub-indices | FMP required (FRED removed ISM data in 2016) | Decision gate resolved; `FMP_API_KEY` registered; DB.nomics recommended as primary source (see 5.7) |
| Phase E — Macro-Market Indicators | 68 composite indicators with 156w rolling z-scores, regimes, forward regimes | `compute_macro_market.py` → `macro_market`, `macro_market_hist` | Production |
| Phase F — Calculated Fields | Synthetic columns: EMFX basket, EEM/IWDA, MOVE proxy, global PMI/yield curve, breadth-above-200DMA | Partially covered in `compute_macro_market.py` | Partial |
| Phase G — Sheets Export Audit | Tab inventory (9 active), protected-tab guards across all writers, legacy-tab cleanup, batch-write coverage | Single source of truth in `library_utils.py`; guards added to 3 previously-missing writers on 2026-04-21 | Mostly Done |

### Phase-by-Phase Detail

#### Simple Pipeline — Production

66 hardcoded instruments (SPX, NDX, sector ETFs, FX majors, FRED yields, Fear & Greed, VIX term structure). Writes to the `market_data` and `sentiment_data` tabs. Preserved indefinitely for compatibility with `trigger.py`, which runs at 06:15 London time on a local Windows machine and reads `market_data` (GID `68683176`) only. No further work planned — the simple pipeline is frozen.

#### Comp Pipeline — Production

Library-driven expansion of the simple pipeline. ~390 instruments from `data/index_library.csv`; daily snapshot (`market_data_comp`) plus weekly Friday-close history from 1990 (`market_data_comp_hist`). 18-currency FX coverage via `COMP_FX_TICKERS` / `COMP_FCY_PER_USD` in `library_utils.py`. Pence correction dynamic (`.L` suffix + median > 50). Semantic `broad_asset_class` + `units` now read from the CSV rather than computed in code. The 7-step refactoring (section 2) completed the transition from hardcoded lists to library-driven dispatch.

#### Phase A — US Macro (FRED) — Production

43 FRED series covering growth (yield curve, M2, building permits, claims, payrolls, unemployment, INDPRO, retail sales), inflation (CPI, core CPI, core PCE, PPI, TIPS breakevens, MICH), monetary policy (Fed funds, 2Y/10Y Treasury, real rates), financial conditions (HY / IG spreads, IG yield, NFCI, SLOOS), survey data (UMich, Conference Board, regional Feds), and commodities (iron ore). Snapshot updated daily; weekly history forward-filled to the Friday spine back to 1947. Series list entirely in `data/macro_library_fred.csv` — no Python changes needed to add or remove series. Recent: `UMCSE` and `UMCSC` (UMich sub-indices, not valid FRED series IDs) removed; `BAMLC0A0CMEY`, `BAMLCC0A0CMTRIV`, `PIORECRUSDM`, `IRLTLT01GBM156N`, `IRLTLT01DEM156N` added.

#### Phase B — Surveys — Consolidated

The original handover planned a dedicated `fetch_macro_surveys.py` module for SLOOS detail, regional Fed surveys, and UMich sub-indices. All in-scope series are now carried by the FRED library and written to the `macro_us` / `macro_us_hist` tabs. Phase B has been explicitly closed in `fetch_data.py` with the comment: *"Phase B (fetch_macro_surveys.py) has been consolidated into macro_us."* Superseded by Phase A; no separate module will be built.

#### Phase C — International Macro — Production

Covers 11 economies: USA, CAN, GBR, DEU, FRA, ITA, JPN, CHN, AUS, CHE, and EA19 (Eurozone). Three library CSVs (`macro_library_oecd.csv`, `macro_library_worldbank.csv`, `macro_library_imf.csv`) drive the fetch. Sources:

- **OECD SDMX** (`sdmx.oecd.org`) — CLI, unemployment, 3-month interbank rate
- **World Bank WDI** — CPI YoY
- **IMF DataMapper v1** — real GDP growth

Outputs to `macro_intl` (snapshot) and `macro_intl_hist` (weekly Friday spine, forward-filled from native monthly/quarterly/annual cadence). Recent fixes (2026-04-21): OECD 3-month rate MEASURE code corrected from `IRST` to `IR3TIB` on `DSD_STES@DF_FINMARK`; IMF Euro Area entity code corrected from `XM` to `EURO`. Known structural gap: OECD does not publish CLI for EA19 or CHE — `compute_macro_market.py` uses the DEU+FRA average as the Eurozone CLI proxy.

#### Phase D — PMI / FMP — Decision Gate Resolved; Ready to Implement

Intended to fill two gaps: ISM Manufacturing PMI and ISM Services PMI composites (S&P Global licence-gated on FRED), and additional regional Fed survey sub-indices not published via FRED. **Decision gate resolved 2026-04-21:** ISM data has been unavailable via FRED since June 2016 (licensing pulled; all 22 series deleted from FRED APIs). `FMP_API_KEY` registered in GitHub Secrets on 2026-04-21. **Source evaluation completed 2026-04-21:** DB.nomics hosts ISM as a first-class provider (free API, no key, full sub-indices) and is recommended as primary source. FMP retained as backup. Implementation will be via a single `fetch_macro_dbnomics.py` module that also covers ECB Bank Lending Survey and Japan Tankan — effectively merging Phase D with the broader "additional sources" effort in section 5.7.

#### Phase E — Macro-Market Indicators — Production

68 composite indicators computed from Phase A + Phase C outputs and the comp-pipeline market data. Each indicator produces: raw value, 156-week (3-year) rolling z-score, regime classification, forward regime signal (`improving`/`stable`/`deteriorating`, with optional `[leading]` suffix), and z-score trend diagnostics (`intensifying` / `fading` / `reversing` / `stable`) against 1w, 4w, 13w lookbacks. Metadata is a single source of truth in `data/macro_indicator_library.csv` — no hardcoded `INDICATOR_META` dict in Python. Group / sub-group hierarchy drives the three-level sidebar in `docs/indicator_explorer.html`. Outputs `macro_market` (snapshot) and `macro_market_hist` (weekly history). Recent additions: 9 standalone country-level CLI indicators (US_CLI1 through AU_CLI1), `EU_I4` Euro HY credit spread indicator; cross-wired EU indicator calculators fixed (Stage 2).

#### Phase F — Calculated Fields — Partial

Several synthetic fields from the original handover are already covered by Phase E indicators (HY/IG ratio → `US_Cr3`; value/growth → `US_EQ_F2`; US 5-regime credit spread → `US_Cr2`; EM vs DM equity ratio → `GL_G1` as EEM/URTH; EMFX basket → `FX_EM1` as of 2026-04-21; MOVE index → already ingested as `^MOVE` and used in `US_V2`). Outstanding items:

- Global PMI proxy — equal-weight ISM + Eurozone PMI + Japan PMI (blocked on Phase D)
- Global yield curve — average of US / DE / UK / JP 10Y-2Y spreads (needs DE/UK 2Y yields + JP 2Y/10Y added to `macro_library_fred.csv`)
- Per-index breadth-above-200DMA — requires in-house computation from constituent closes; no free feed exists for `$SPXA200R`-style symbols

See section 5.3 for the audit. New indicators follow the CSV-driven pattern: write a `_calc_*` function, add to `REGIME_RULES` and the relevant `_*_CALCULATORS` dict, add a row to `macro_indicator_library.csv`.

#### Phase G — Sheets Export Audit — Mostly Done (2026-04-21)

Tab inventory (all 9 active tabs, all lowercase-underscore, all production):

| Tab | Writer module | Snapshot/History | Notes |
|---|---|---|---|
| `market_data` | `fetch_data.py` | snapshot | Simple pipeline; consumed by downstream `trigger.py`. **Protected.** |
| `market_data_comp` | `fetch_data.py` | snapshot | Comp pipeline (~390 instruments). |
| `market_data_comp_hist` | `fetch_hist.py` | history (weekly) | Weekly Friday-close prices from 1990. |
| `macro_us` | `fetch_macro_us_fred.py` | snapshot | 43 FRED series. |
| `macro_us_hist` | `fetch_hist.py` | history (weekly) | Weekly Friday FRED history from 1947. |
| `macro_intl` | `fetch_macro_international.py` | snapshot | 11-country macro. |
| `macro_intl_hist` | `fetch_macro_international.py` | history (weekly) | Weekly Friday international macro. |
| `macro_market` | `compute_macro_market.py` | snapshot | 68 composite indicators. |
| `macro_market_hist` | `compute_macro_market.py` | history (weekly) | Weekly indicator history. |

Audit findings fixed on 2026-04-21:

- **Protected-tab guard was missing** in three writer modules (`fetch_macro_us_fred.py`, `fetch_macro_international.py`, `compute_macro_market.py`). All three now check against the shared `SHEETS_PROTECTED_TABS` constant in `library_utils.py`. Previously only `fetch_hist.py` had a guard (with its own local copy of the list).
- **Single source of truth for tab state**: `library_utils.py` now exports `SHEETS_PROTECTED_TABS`, `SHEETS_ACTIVE_TABS`, and `SHEETS_LEGACY_TABS_TO_DELETE` as `frozenset`s. `fetch_data.py` uses the shared legacy-delete list instead of its own inline set.
- **Clear-range bug**: `fetch_macro_us_fred.py` cleared only `A:Z` (26 columns) before writing — would leave stale data if the schema grew beyond column Z. Widened to `A:ZZ` (702 columns) to match the other writers.

Outstanding (low value): record Sheets GIDs for each tab in `technical_manual.md`; build an automated "tab drift" audit that flags tabs in the Sheet but not in `SHEETS_ACTIVE_TABS ∪ SHEETS_LEGACY_TABS_TO_DELETE`.

Batch writes (10k rows/call) are only implemented in `fetch_hist.py` — the largest tab (`market_data_comp_hist`, ~9,000 rows) sits within the Sheets API's single-call payload limit at current column count, so no other writer has hit a batching need yet. Revisit if column count grows significantly.

---

## 2. Completed Work

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

### OECD CLI Standalone Country Indicators (completed 2026-04-20)

| Change | Detail |
|---|---|
| 9 new Phase E indicators | `US_CLI1`, `CA_CLI1`, `DE_CLI1`, `FR_CLI1`, `UK_CLI1`, `IT_CLI1`, `JP_CLI1`, `CN_CLI1`, `AU_CLI1` — one standalone CLI indicator per OECD-available country |
| Data source | Reads each country's `*_CLI` column from `macro_intl` (populated by `fetch_macro_international.py`) |
| Regime classification | Above/below-trend regimes via the existing z-score rules; `naturally_leading = True` |
| Rationale | Restores a direct country-level leading-indicator view after the USSLIND (FRED) discontinuation. Commit `52b38cb`. |

### Bug Fix Sprint (completed 2026-04-21, merged via PR #64 / #65)

| Stage | Issue | Fix |
|---|---|---|
| Stage 1 | `^VIX` / `^MOVE` `region` was blank; earlier audit proposed "US" | Owner decision: set `region = "North America"`, `country_market = "United States"` to match XLE/XLB/etc. convention. `data/index_library.csv` updated. |
| Stage 2 | Several EU indicator calculators in `compute_macro_market.py` were cross-wired to wrong country series | All EU indicators re-mapped to correct OECD series; verified end-to-end. |
| Stage 2+ | Missing Euro HY credit spread indicator | `EU_I4` added — Euro HY credit spread equivalent of `US_Cr2`. |
| Stage 3 | `UMCSE` / `UMCSC` (UMich sub-indices) returned null from FRED | Confirmed not valid FRED series IDs — FRED carries only the headline `UMCSENT`. Both removed from `data/macro_library_fred.csv` and corresponding columns dropped from `data/macro_us_hist.csv`. Future work to restore via UMich portal tracked under section 5.7. |
| Stage 4 | IMF Euro Area real GDP returning no data | `XM` replaced with `EURO` in `IMF_CODE_MAP` in `fetch_macro_international.py` — IMF DataMapper v1 uses `EURO` (see `imf.org/external/datamapper/profile/EURO`). |
| Stage 5 | OECD `DF_FINMARK` short-term interest rates returning zero data | MEASURE code corrected from `IRST` to `IR3TIB` (3-month interbank) on `DSD_STES@DF_FINMARK` in `data/macro_library_oecd.csv`. `IRSTCI` (call money) and `IRLT` (long-term) are the other valid codes. |

### Phase D Decision Gate Resolved (completed 2026-04-21)

| Finding | Detail |
|---|---|
| FRED cannot carry ISM PMI | Confirmed via FRED's own 2016 announcement: all 22 ISM series (Manufacturing + Non-Manufacturing Reports on Business) were deleted for licensing reasons and have not been restored. `NAPM`, `NAPMPI`, `NMFCI`, `NMFBAI`, `NMFNOI` are all discontinued. |
| Path forward | FMP (Financial Modeling Prep, free tier 250 calls/day) — carries ISM composites + sub-indices under its own licence. Requires `FMP_API_KEY` registration + new `fetch_macro_fmp.py` module + `data/macro_library_fmp.csv`. See section 5.1 for the full plan. |
| Unblocks | Phase F "Global PMI proxy" (equal-weight ISM + Eurozone PMI + Japan PMI) once both ISM and EZ/JP PMI are available. |

### Phase G — Sheets Export Audit (completed 2026-04-21)

| Change | Detail |
|---|---|
| Shared tab-state constants in `library_utils.py` | Added `SHEETS_PROTECTED_TABS`, `SHEETS_ACTIVE_TABS`, `SHEETS_LEGACY_TABS_TO_DELETE` as `frozenset`s — single source of truth for tab state across all 5 writer modules. |
| Protected-tab guards added | `fetch_macro_us_fred.py`, `fetch_macro_international.py`, `compute_macro_market.py` now each check against `SHEETS_PROTECTED_TABS` before writing. Previously only `fetch_hist.py` had a guard (with its own local set). |
| `fetch_data.py` legacy-tab list consolidated | Replaced the inline `TABS_TO_DELETE` set with the shared `SHEETS_LEGACY_TABS_TO_DELETE` import. |
| `fetch_hist.py` local set removed | Replaced local `PROTECTED_TABS = {...}` with the shared import. |
| Clear-range bug | `fetch_macro_us_fred.py` cleared only `A:Z` (26 columns) before writing — would leave stale data if schema grew past column Z. Widened to `A:ZZ`. |
| Tab inventory documented | 9 active tabs catalogued in section 1 Phase G (writer module, snapshot vs history, protected status). |

### Phase D Source Evaluation — Business Survey Data (completed 2026-04-21)

| Change | Detail |
|---|---|
| 8 candidate sources evaluated | DB.nomics, FMP, ECB SDW, Bank of Japan, UMich portal, Trading Economics, Investing.com, S&P Global/ISM direct. Focus: ISM PMI, Eurozone PMI, bank lending surveys, Tankan. |
| **DB.nomics recommended as primary** | Free API, no key. ISM hosted as first-class provider with full manufacturing + services sub-indices. ECB BLS (20,913 series) and BoJ Tankan also available via same API. One module covers all three gaps. |
| FMP retained as backup | `FMP_API_KEY` registered. Economic calendar carries ISM events. Use only if DB.nomics ISM freshness is >2 months stale. |
| 3 sources skipped | Trading Economics (paid, ~$49+/month), Investing.com (broken — Cloudflare since 2023), S&P Global/ISM direct (no API). |
| UMich portal deferred | No official API; ICE/ICC correlate highly with FRED headline `UMCSENT`. Low marginal value. |
| Implementation plan written | Section 5.7 updated with 8 target series, 5 new indicators, step-by-step build plan, FMP fallback path. |

### Phase F Progress — EMFX Basket Added & Prior Items Audited (completed 2026-04-21)

| Change | Detail |
|---|---|
| New indicator `FX_EM1` | Equal-weight EMFX basket momentum (CNY, INR, KRW, TWD). Each `FX=X` quote is indirect (FCY per USD); basket uses `-log(FX)` so RISING basket = EM currencies strengthening vs USD. Raw = `basket − 26wk SMA`. Regime: z > +1 = EMFX-strengthening; z < -1 = EMFX-weakening. |
| Phase F audit | EEM/IWDA ratio found already covered by `GL_G1` (EEM / URTH in USD — MSCI World USD-denominated ETF is the functional equivalent of IWDA.L after FX). No new indicator needed. |
| MOVE proxy confirmed unnecessary | `^MOVE` is already ingested via the comp pipeline and used in `US_V2` (cross-asset volatility). |

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

## 3. Bug Fixes & Data Quality

### Priority 1: Currently Broken Data Sources

| Issue | Module | Status / Action |
|---|---|---|
| OECD `DF_FINMARK` (short-term interest rates) returning zero data for all 11 countries | fetch_macro_international.py | **Fixed 2026-04-21.** The SDMX `MEASURE` code for the 3-month interbank rate on `DSD_STES@DF_FINMARK` is `IR3TIB`, not `IRST`. Key template in `macro_library_oecd.csv` updated to `{countries}.M.IR3TIB.PA.....`. First daily run will confirm. |
| IMF `XM` code (Eurozone GDP Growth) returning no data | fetch_macro_international.py | **Fixed 2026-04-21.** IMF DataMapper v1 API uses entity code `EURO` for the Euro Area (see `imf.org/external/datamapper/profile/EURO`); the legacy `XM` code is no longer served. `IMF_CODE_MAP` updated. |
| OECD EA19 and CHE CLI missing | fetch_macro_international.py | Structural limitation — OECD doesn't publish CLI for these codes. Consider using DEU+FRA average as Eurozone proxy (already done in `compute_macro_market.py`). Document as known gap. |
| ~~UMCSE & UMCSC (UMich sub-indices) returning null~~ | Resolved — removed | `UMCSE` and `UMCSC` are not valid FRED series IDs. The UMich sub-indices (Expectations, Current Conditions) are not available via the FRED API; only the headline `UMCSENT` is. Both removed from `macro_library_fred.csv` and `macro_us_hist.csv`. |

### Priority 2: Code/Metadata Mismatches

*All issues resolved.* EU_R1 metadata/code mismatch fixed during indicator groups review — CSV and code now both describe BTP-Bund spread (IRLTLT01ITM156N − IRLTLT01DEM156N).

---

## 4. Metadata & Label Corrections

Status of the label items previously flagged in `METADATA_REDUNDANCY_REVIEW.md` against the current `data/index_library.csv` (verified 2026-04-21):

| Ticker | Proposed Fix | Current Library State | Action |
|---|---|---|---|
| `^IRX` | name → "US 3-Month T-Bill Yield" | `name = "US 3-Month Treasury Yield"` | **Already fixed.** Wording is a close equivalent — no change needed. |
| `^VIX` | region → blank fill | `region = "North America"`, `country_market = "United States"` | **Fixed 2026-04-21.** Owner chose "North America" (groups US & Canada intentionally) rather than a new "US" key. |
| `^MOVE` | region → blank fill | `region = "North America"`, `country_market = "United States"` | **Fixed 2026-04-21.** Same treatment as `^VIX`. |
| XLE, XLB, XLI, XLK, XLV, XLF, XLU, XLP, XLY, XLRE | region → "US" (earlier audit proposal) | `region = "North America"` | **No change — owner decision.** "North America" groups US & Canada deliberately. A dedicated "US" key is not planned. |
| `IWF` | region → "US" (earlier audit proposal) | `region = "North America"` | **No change — owner decision.** Same as above. |

### Excluded Indicators (Do Not Implement Without Instruction)

These were evaluated and deliberately excluded:

| Indicator | Reason | Proxy Used Instead |
|---|---|---|
| Atlanta Fed GDPNow | Web scrape only — no clean API | None |
| Fed Funds Futures implied path | CME paid subscription | None |
| Goldman Sachs FCI | Proprietary | Chicago Fed NFCI (FRED: NFCI) |
| Bloomberg FCI | Bloomberg terminal required | Chicago Fed NFCI |
| MOVE Index | Bloomberg terminal required | 30-day realised vol on ^TNX (future) |
| JP Morgan Global PMI | S&P Global licence required | Equal-weight ISM + EZ PMI + Japan PMI — ISM via DB.nomics (section 5.7) |
| EM Currencies Index (EMFX) | JP Morgan proprietary | Implemented as `FX_EM1` — basket of CNY/INR/KRW/TWD vs USD |
| China 10Y yield (FRED) | Data quality issues | CNYB.L ETF as proxy |

---

## 5. New Feature Development

### 5.1 Phase D — PMI / Survey Data

**Priority:** Medium — ISM PMI is the single biggest gap in the indicator suite.
**Status:** Decision gate resolved 2026-04-21 — **FRED is not a viable source for ISM PMI.** `FMP_API_KEY` registered in GitHub Secrets 2026-04-21. Source evaluation completed 2026-04-21 — **DB.nomics is the recommended primary source** (see section 5.7 for full research). FMP retained as backup.

**Decision gate resolution:** ISM (Institute for Supply Management) data has not been available via FRED since **June 2016**, when all 22 series from the Manufacturing and Non-Manufacturing ISM Reports on Business were deleted from FRED's database, Excel add-in, APIs, and all other services for licensing reasons. Series like `NAPM`, `NAPMPI`, `NMFCI`, `NMFBAI`, `NMFNOI` are either fully removed or flagged discontinued. The licensing agreement is between ISM and S&P Global / Markit and has not been restored.

FRED *does* still carry:
- Regional Fed surveys (Philadelphia, Empire State / New York, Richmond, Kansas City, Dallas) — **already in `macro_library_fred.csv`**.
- OECD Composite Leading Indicators (different licence) — covered in Phase C.
- `MANEMP` and other manufacturing employment / output series — covered in Phase A.

**Conclusion — FRED cannot close the ISM PMI gap.** DB.nomics hosts ISM as a first-class provider with full manufacturing and services sub-indices via a free API (no key required). FMP (250 calls/day, key registered) is the backup if DB.nomics freshness proves insufficient.

**Action — implement via DB.nomics (see section 5.7 for details):**
1. Build `fetch_macro_dbnomics.py` — single new module covering ISM + ECB BLS + Japan Tankan.
2. Drive series list from `data/macro_library_dbnomics.csv`.
3. Priority ISM series: Manufacturing PMI composite (`ISM/pmi/pm`), Manufacturing New Orders (`ISM/new-orders/pm`), Services PMI composite (`ISM/nm-pmi/pm`), Services Business Activity (`ISM/nm-business/pm`).
4. Register new indicators in `compute_macro_market.py` via the standard 4-point pattern.
5. If DB.nomics ISM data is stale (>2 months behind), fall back to FMP economic calendar endpoint with the registered `FMP_API_KEY`.

### 5.2 Instrument Expansion

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

### 5.3 Calculated Fields Expansion

Several calculated fields were proposed but not yet implemented. Some may already be covered by the 68 macro-market indicators — audit before building duplicates.

| Field | Formula | Status |
|---|---|---|
| HY/IG ratio | BAMLH0A0HYM2 / BAMLC0A0CM | Covered by US_Cr3 (HY-IG spread) |
| EMFX basket | Equal-weight CNY, INR, KRW, TWD vs USD (inverted so rising = EM FX strengthening) | Implemented 2026-04-21 as `FX_EM1` |
| EEM/IWDA ratio | EEM / URTH (MSCI World ETF in USD — functional equivalent of IWDA.L after FX adjustment) | Covered by `GL_G1` |
| MOVE proxy | 30-day realised vol on ^TNX | Not needed — `^MOVE` ticker itself is in the comp pipeline (used in `US_V2`) |
| Global PMI proxy | Equal-weight ISM + Eurozone PMI + Japan PMI | Depends on Phase D |
| Global yield curve | Average of US/DE/UK/JP 10Y-2Y spreads | Not yet implemented (US/DE/UK 10Y available; needs 2Y for DE/UK + full JP curve) |
| % stocks above 200-day MA | Per-index breadth: fraction of constituents with close > 200-day SMA. Not exposed by yfinance as a field and no free FRED/OECD feed exists; StockCharts symbols (`$SPXA200R`, `$NYA200R`, `$NDXA200R`) are proprietary. Compute in-house from constituent daily closes. Candidate indices: S&P 500 (highest signal-to-cost), Nasdaq 100, Russell 1000, FTSE 100. Naming: `US_EQ_B1` / `US_EQ_B2` etc. ("Equity - Breadth"). Adds ~500-1000 extra daily yfinance pulls per index. | Not yet implemented |

**Action:** Audit the 68 indicators in `compute_macro_market.py` against this list to confirm coverage before building. New indicators follow the CSV-driven pattern: write a `_calc_*` function, add to `REGIME_RULES` and the relevant `_*_CALCULATORS` dict, add a row to `macro_indicator_library.csv`. No hardcoded metadata needed — everything is read from the CSV at runtime.

### 5.4 Sheets Export Audit (Phase G)

**Status (2026-04-21):** Most items completed — see Phase G details in section 1. The full audit found and fixed three issues: missing protected-tab guards in 3 of 4 writer modules, an inline `TABS_TO_DELETE` constant in `fetch_data.py` that drifted from the `PROTECTED_TABS` set in `fetch_hist.py`, and a narrow `A:Z` clear range in `fetch_macro_us_fred.py` that would leave stale data if the schema grew past column Z. All three fixed by consolidating the shared tab state into `library_utils.py` (`SHEETS_PROTECTED_TABS`, `SHEETS_ACTIVE_TABS`, `SHEETS_LEGACY_TABS_TO_DELETE`) and wiring every writer to it.

**Remaining (low value):**
- Record Sheets GIDs for each of the 9 active tabs in `technical_manual.md` (housekeeping; only useful if downstream consumers need stable GID links).
- Build an automated drift check: compare the tab set in the Sheet against `SHEETS_ACTIVE_TABS ∪ SHEETS_LEGACY_TABS_TO_DELETE` and flag extras. Useful only if ad-hoc tabs are being created outside the pipeline.

### 5.5 Library Manager Utility

**Priority:** Low — developer tooling.

Create `library_manager.py` — a standalone utility for maintaining `index_library.csv`:

- Validate all tickers against yfinance (flag those returning no data)
- Auto-set `validation_status = "UNAVAILABLE"` for dead tickers
- Suggest alternative tickers for unavailable instruments
- Check metadata consistency (no duplicate tickers, all required fields filled)
- Run manually (`python library_manager.py`), not as part of the daily pipeline

### 5.6 Incremental Fetch Mode (fetch_hist.py)

**Priority:** Medium — performance improvement.

Currently `fetch_hist.py` rebuilds the entire dataset from scratch on every run (~8-12 min for `run_comp_hist()`). An incremental append mode would:

1. Check the last date in the existing CSV
2. Only fetch new weekly rows since the last update
3. Append to existing data rather than full rebuild

This would reduce daily historical data runtime from ~10 minutes to seconds.

### 5.7 Expand Macro Data Library from Additional Sources

**Priority:** Medium-high — ISM PMI is the single biggest gap; ECB BLS and Tankan are the next two.
**Status:** Source evaluation completed 2026-04-21. DB.nomics recommended as primary source. FMP as backup for ISM only.

The FRED API does not carry several high-value survey series (ISM PMI composites, UMich sub-indices), and OECD / IMF SDMX endpoints are fragile. A systematic evaluation of 8 candidate data sources was conducted on 2026-04-21, focusing specifically on business survey data (ISM PMI, Eurozone PMI, bank lending surveys, Tankan).

#### Source Evaluation (completed 2026-04-21)

| Source | Verdict | Rationale |
|---|---|---|
| **DB.nomics** | **PRIMARY — use** | Free REST API, no key. ISM is a first-class provider with full manufacturing + services PMI sub-indices. ECB BLS (20,913 series) and BoJ Tankan also available. Python package `dbnomics` on PyPI returns DataFrames. One module covers all three gaps. |
| **FMP** | **BACKUP — ISM only** | `FMP_API_KEY` registered. Economic calendar endpoint (`/api/v3/economic_calendar`) carries ISM events with actual/previous/estimate. Calendar-format data needs transformation to time series. 250 calls/day free tier is sufficient. Use only if DB.nomics ISM freshness proves insufficient. |
| **ECB SDW** | **BACKUP — BLS only** | Free SDMX 2.1 REST API (`data-api.ecb.europa.eu`). BLS dataset (`ECB_BLS1`) has 20,913 series. Use only if DB.nomics ECB/BLS coverage is incomplete. We already handle SDMX for OECD in `fetch_macro_international.py`. |
| **Bank of Japan** | **BACKUP — Tankan only** | Free REST API (`stat-search.boj.or.jp`). Database code "CO" for Tankan. Python package `bojpy` available. Use only if DB.nomics BOJ/CO coverage is incomplete. |
| **UMich portal** | **DEFER** | CSV/XLSX downloads from `data.sca.isr.umich.edu/tables.php` — no official API. Headline `UMCSENT` already on FRED. ICE/ICC sub-indices move in high correlation with headline. Fragile HTTP parsing needed. Marginal value. |
| **Trading Economics** | **SKIP** | Paid API — minimum ~$49/month for basic tier, $249+/month for full. No genuinely free tier. Same data available via DB.nomics for free. |
| **Investing.com** | **SKIP** | `investpy` broken since 2023 (Cloudflare protection). `investiny` is a partial workaround but unreliable. Scraping violates ToS. No official API. |
| **S&P Global / ISM direct** | **SKIP** | No programmatic API. Headline values in press releases only. Sub-indices require paid institutional subscription. DB.nomics already redistributes the same data. |

#### Detailed Findings per Source

**DB.nomics (`api.db.nomics.world`)**
- Provider `ISM` hosts both Manufacturing and Non-Manufacturing (Services) ISM datasets as separate dataset codes. Confirmed available:
  - Manufacturing PMI composite: `ISM/pmi/pm`
  - Non-Manufacturing/Services PMI composite: `ISM/nm-pmi/pm`
  - Manufacturing sub-indices: inventories (`ISM/inventories`), customers' inventories (`ISM/cusinv`), prices, new-orders, production, employment, supplier deliveries, exports, imports, backlog
  - Non-Manufacturing sub-indices: prices (`ISM/nm-prices`), inventories (`ISM/nm-inventories`), business activity, new orders, employment
- Provider `ECB` dataset `BLS` (Bank Lending Survey Statistics): 20,913 series. Covers credit standards for enterprises and households, demand conditions, lending margins. Quarterly, ~2003–present. Dimensions: frequency, reference area, bank selection, BLS item.
- Provider `BOJ` exists — Tankan data expected under dataset code `CO` (same as official BoJ API).
- API: `dbnomics.fetch_series('ISM', 'pmi', 'pm')` → pandas DataFrame. No API key, no rate limit documented.
- Last ISM data retrieval: January 7, 2026. **Risk: data may lag by 1-3 months.** Must verify freshness during proof-of-concept.

**FMP (`financialmodelingprep.com`)**
- Economic Calendar endpoint: `GET /api/v3/economic_calendar?from=YYYY-MM-DD&to=YYYY-MM-DD&apikey=KEY` — returns JSON with fields: event name, country, date (UTC), actual, previous, estimate, impact.
- Economic Indicators endpoint: `GET /stable/economic-indicators?country=US&apikey=KEY` — broader macro data (GDP, CPI, unemployment).
- ISM PMI: carried as economic calendar events ("ISM Manufacturing PMI", "ISM Services PMI") with actual/previous/estimate values. This is event-style data, not a dedicated time-series endpoint — needs transformation to build a monthly time series from calendar entries.
- Free tier: 250 calls/day. Sufficient for ~5-10 ISM series fetched daily.
- `FMP_API_KEY` already in GitHub Secrets as of 2026-04-21.

**ECB SDW → ECB Data Portal API (`data-api.ecb.europa.eu`)**
- SDMX 2.1 REST API. Migrated from old `sdw-wsrest.ecb.europa.eu` address (redirects ended Oct 2025 — use new URL).
- BLS dataset key structure: `BLS.{freq}.{ref_area}.{bank_selection}.{bls_item}.{maturity_category}.{currency_denomination}.{collateralisation}.{...}` — deeply nested.
- Python: `sdmx1` package (already used by similar projects). `import sdmx; ecb = sdmx.Client("ECB"); data = ecb.data("BLS", key={...})`.
- Also covers: consumer/business confidence (ESI/BCI), €STR, HICP, monetary aggregates.
- Data quality: official source, highest reliability for Euro area data.

**Bank of Japan (`stat-search.boj.or.jp`)**
- REST API with 3 operation modes documented in `api_manual_en.pdf`. Database code "CO" for Tankan.
- Tankan Large Manufacturers DI: quarterly (March, June, September, December). Range: -100 to +100 (% favorable − % unfavorable). Latest: DI = 17 (March 2026).
- Flat file downloads also available — predefined Tankan files updated on release day (~10:00 JST).
- Python: `bojpy` package wraps the API.
- Also on DB.nomics as provider `BOJ` — prefer DB.nomics to avoid building a separate BoJ module.

**UMich Surveys of Consumers (`data.sca.isr.umich.edu`)**
- Data: ICS (headline — already `UMCSENT` on FRED), ICE (Index of Consumer Expectations), ICC (Index of Current Conditions), 1Y/5Y inflation expectations, buying-conditions sub-indices.
- Access: CSV/XLSX files downloadable from `data.sca.isr.umich.edu/tables.php`. No official REST API.
- Publication delay: ~1 month. Preliminary release mid-month, final release end-of-month.
- Sub-index correlation: ICE and ICC move in high correlation with ICS headline — marginal signal value.
- Implementation cost: requires HTML parsing to locate download URLs (fragile), or hardcoded direct URLs that break when site layout changes.

#### Recommended Implementation Plan

**Phase D implementation — single `fetch_macro_dbnomics.py` module:**

Build one new fetch module that uses the `dbnomics` Python package to pull business survey data from three providers in a single pipeline step. Series list driven by `data/macro_library_dbnomics.csv`.

**Target series (8 series across 3 providers):**

| DB.nomics ID | Series | Frequency | Use Case |
|---|---|---|---|
| `ISM/pmi/pm` | ISM Manufacturing PMI composite | Monthly | Core gap — Phase D primary target |
| `ISM/new-orders/pm` | ISM Manufacturing New Orders | Monthly | Leading sub-index — new orders lead the composite |
| `ISM/nm-pmi/pm` | ISM Services PMI composite | Monthly | Core gap — services sector breadth |
| `ISM/nm-business/pm` | ISM Services Business Activity | Monthly | Leading sub-index for services |
| `ECB/BLS/<credit-std-enterprises>` | ECB BLS — Credit standards, enterprises | Quarterly | Euro area credit conditions — fills Eurozone gap |
| `ECB/BLS/<credit-std-households>` | ECB BLS — Credit standards, households | Quarterly | Euro area household lending conditions |
| `BOJ/CO/<large-mfr-di>` | Tankan Large Manufacturers DI | Quarterly | Japan business sentiment — fills Japan survey gap |
| `BOJ/CO/<large-mfr-forecast>` | Tankan Large Manufacturers Forecast DI | Quarterly | Forward-looking business sentiment |

**Exact series keys for ECB/BLS and BOJ/CO need proof-of-concept verification** — the dimension codes are complex (especially BLS which has 10+ dimensions). The PoC step below will resolve these.

**New indicators to register in `compute_macro_market.py` (5 new indicators):**

| ID | Formula | Group |
|---|---|---|
| `US_PMI1` | ISM Manufacturing PMI — raw level, z-score on 156w rolling | Growth & Activity |
| `US_PMI2` | ISM Manufacturing New Orders − Inventories (proxy for orders momentum) | Growth & Activity |
| `US_SVC1` | ISM Services PMI composite — raw level, z-score on 156w rolling | Growth & Activity |
| `EU_BLS1` | ECB BLS credit standards for enterprises (net %, inverted so tightening = negative) | Credit & Lending |
| `JP_TK1` | Tankan Large Manufacturers DI — raw level, z-score on 156w rolling | Growth & Activity |

**Implementation steps:**

1. **Proof-of-concept** (first): Write a standalone script `poc_dbnomics.py` that fetches all 8 target series via `dbnomics.fetch_series()`, verifies data freshness (most recent observation date), prints schema, and saves sample CSVs. Resolve exact ECB/BLS and BOJ/CO series keys. Do not commit to infrastructure until PoC confirms all series are reachable and reasonably fresh (<3 months lag). **If ISM data on DB.nomics is stale, fall back to FMP economic calendar for ISM only.**
2. **Build `fetch_macro_dbnomics.py`** mirroring the FRED fetch pattern: per-series `try/except`, exponential backoff, CSV library driven. Output: `data/macro_dbnomics.csv` (snapshot) + `data/macro_dbnomics_hist.csv` (weekly Friday spine, forward-filled from monthly/quarterly native frequency).
3. **Build `data/macro_library_dbnomics.csv`** with columns matching `macro_library_fred.csv` schema: `series_id`, `provider`, `dataset`, `series_code`, `name`, `frequency`, `units`, `seasonal_adjustment`.
4. **Register in `fetch_data.py`** as a new phase (Phase D) with its own `try/except` block, after Phase C and before Phase E.
5. **Register 5 new indicators** in `compute_macro_market.py` via the standard 4-point pattern.
6. **Unblocks Phase F "Global PMI proxy"** — once `US_PMI1` is live, build the equal-weight ISM + Eurozone PMI + Japan PMI composite (Eurozone PMI via DB.nomics S&P Global/Markit if available, otherwise ECB confidence surveys as proxy).

**FMP backup path (only if DB.nomics ISM is stale):**

If proof-of-concept reveals DB.nomics ISM data lags by >2 months:
1. Build `fetch_macro_fmp.py` — fetches ISM events from FMP economic calendar.
2. Transform calendar events (actual/previous/estimate per release date) into a monthly time series.
3. Drive from `data/macro_library_fmp.csv`.
4. Keep DB.nomics for ECB BLS + Tankan (these are quarterly, so 1-3 month lag is acceptable).

**Dependency: `dbnomics` package must be added to `requirements.txt`.**

---

## 6. Multi-Frequency Pipeline (Phase 2)

**Priority:** High impact but large effort. Detailed implementation plan in [`manuals/multifreq_plan.md`](multifreq_plan.md).
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

## 7. Operational & Infrastructure

### GitHub Actions

- **60-day inactivity pause:** GitHub Actions auto-pauses workflows after 60 days of no pushes to the repo. The daily pipeline produces commits, so this is not currently an issue, but will trigger if the pipeline fails for an extended period. Fix: push a trivial commit or re-enable from the Actions tab.
- **Run timeout:** Currently set to 120 minutes. Monitor if incremental fetch mode (section 5.6) reduces this.

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