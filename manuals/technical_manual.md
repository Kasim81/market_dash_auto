# Market Dashboard — Technical Manual

> Last updated: 2026-06-16

This manual is the authoritative record of the **current code state** — modules, data flow, schemas, operational behaviour. It is paired with two forward-looking documents:

- **`forward_plan.md`** — the phase summary, the architecture rules (`§0`), the priority queue (`§2`), and feature roadmap (`§3`). Read `forward_plan.md` §0 before touching any data-layer code: it codifies the rule that every fetched identifier must live in `data/macro_library_*.csv` rather than in Python.
- **`forward_plan.md` §1 "Known Data Gaps"** is the single source of truth for series unavailable from any free source (CN 10Y, EU IG corp yield, ZEW, JP_PMI1, CN_PMI2, OECD CLI for EA19/CHE, etc.) — see §13 of this manual for the pointer.
- **`multifreq_plan.md`** — detailed Phase 2 (multi-frequency / ragged-column) implementation plan, kept independent because of its size.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Directory Structure](#2-directory-structure)
3. [Execution Flow](#3-execution-flow)
4. [Two Pipelines: Simple vs Comp](#4-two-pipelines-simple-vs-comp)
5. [Data Sources & APIs](#5-data-sources--apis)
6. [Google Sheets Tab Map](#6-google-sheets-tab-map)
7. [CSV File Inventory](#7-csv-file-inventory)
8. [index_library.csv — Schema & Source of Truth](#8-index_librarycsv--schema--source-of-truth)
9. [Module Reference](#9-module-reference)
10. [FX Conversion Logic](#10-fx-conversion-logic)
11. [Key Design Patterns](#11-key-design-patterns)
12. [Environment Setup](#12-environment-setup)
13. [Known Issues & Status](#13-known-issues--status)
14. [Operational Notes](#14-operational-notes)

---

## 1. Project Overview

Market Dashboard Auto is a fully automated daily data pipeline that fetches market prices, macro-economic indicators, and composite sentiment/regime signals from free public APIs. Outputs go to:

- **Google Sheets** (primary human-readable output, spreadsheet ID: `12nKIUGHz5euDbNQPDTVECsJBNwrceRF1ymsQrIe4_ac`)
- **CSV files** in `data/` (machine-readable; committed to git by GitHub Actions)

The pipeline runs automatically every day at **00:34 UTC** via GitHub Actions (`python fetch_data.py` followed by `python docs/build_html.py`). The odd minute avoids GitHub's scheduled-run congestion at the top of the hour; the 00:34 slot ensures the run finishes well before the 06:00 UK local automations that consume the data.

### Scope at a Glance

| Output | Instruments / Indicators | Frequency | Source |
|---|---|---|---|
| `market_data` | ~70 instruments (simple dashboard) | Daily snapshot | yfinance + FRED |
| `market_data_comp` | ~390 instruments from library | Daily snapshot | yfinance + FRED |
| `market_data_comp_hist` | ~390 instruments from library | Weekly history from 1950 | yfinance + FRED |
| `macro_economic` | ~150 raw macro series across 12 economies | Daily snapshot (long-form) | FRED + OECD + World Bank + IMF + DB.nomics + ifo |
| `macro_economic_hist` | ~150 raw macro series | Weekly Friday-spine history from 1947 | FRED + OECD + World Bank + IMF + DB.nomics + ifo |
| `macro_market` | 108 composite indicators | Daily snapshot | Derived from above datasets |
| `macro_market_hist` | 108 composite indicators | Weekly history from 2000 | Derived from above datasets |

### Codebase Size

8 top-level Python modules (incl. `data_audit.py`) + 30-module `sources/` package (1 scaffolding-only NDL, 1 scaffolding-only Alpha Vantage, 1 standalone SEC EDGAR equity-fundamentals feed) + `docs/build_html.py` + `scripts/` utilities, totalling ~19,600 lines. Configuration: 31 input CSV libraries (1 instrument library + 28 raw-source libraries + 1 composite-indicator library + `manual_splits.csv`) + `reference_indicators.csv` for the cycle-timing cross-reference + `freshness_thresholds.csv` for the §2.6 audit + `source_fallbacks.csv` for the T0–T3 fallback chain. Output: 7 daily-tab CSVs + `macro_market_monthly_hist.csv` (regime-AA Phase 3 input) + `equity_fundamentals.csv` (SEC EDGAR revenue/EPS history) + `pipeline.log` + `data_audit.txt` + `audit_comment.md`.

---

## 2. Directory Structure

```
market_dash_auto/
├── fetch_data.py                  # Master orchestrator — runs all phases (998 lines)
├── fetch_hist.py                  # Comp-pipeline weekly history (781 lines)
├── fetch_macro_economic.py        # Unified raw-macro coordinator (1,488 lines)
├── compute_macro_market.py        # 108 macro-market composite indicators + monthly-hist writer (2,546 lines)
├── library_utils.py               # Shared sort-order dicts, FX maps, sort key, SHEETS_* tab sets, INDICATOR_CONCEPT_ORDER (627 lines)
├── data_audit.py                  # Daily integrated audit — fetch outcomes + static checks + staleness + registry drift + §3.11 explorer pre-flight (§2.6 v2; 1,188 lines)
├── data_audit.txt                 # OUTPUT — full sorted audit report (regenerated each run)
├── audit_comment.md               # OUTPUT — GitHub Issue comment body posted to perpetual `daily-audit` Issue
├── audit_writeback.py             # Daily writeback half of the audit loop — flips dead-ticker validation_status to UNAVAILABLE after 14d streak (§3.1 sub-track 3; ~230 lines)
├── library_sync.py                # Operator-gated hist↔library prune utility — archives orphan columns then drops them; covers 3 pairs (comp / macro_economic / macro_market) (~396 lines). `MACRO_LIBS` covers all 25 single-source registries (was 21 pre-2026-06-10).
├── pipeline.log                   # Captured stdout+stderr of the most recent run (committed by CI)
├── requirements.txt               # Python dependencies
├── README.md
│
├── sources/                       # Per-source raw-macro fetchers (called by fetch_macro_economic.py)
│   ├── __init__.py
│   ├── base.py                        # Shared HTTP/Sheets/CSV plumbing (220 lines)
│   ├── countries.py                   # 12-country code registry (54 lines)
│   ├── fred.py                        # FRED REST API fetcher (423 lines)
│   ├── oecd.py                        # OECD SDMX REST API fetcher (191 lines)
│   ├── worldbank.py                   # World Bank WDI fetcher (193 lines)
│   ├── imf.py                         # IMF DataMapper v1 fetcher (153 lines)
│   ├── dbnomics.py                    # DB.nomics REST API fetcher with fail-fast circuit breaker (~245 lines)
│   ├── ifo.py                         # ifo Institute Excel-workbook fetcher with retry + cache + month-walk + Bright Data fallback (579 lines)
│   ├── boe.py                         # Bank of England IADB CSV fetcher (264 lines)
│   ├── ecb.py                         # ECB Data Portal SDMX fetcher
│   ├── boj.py                         # Bank of Japan Time-Series API fetcher (320 lines)
│   ├── estat.py                       # e-Stat (Japan Statistics Bureau) REST API fetcher (336 lines)
│   ├── lbma.py                        # LBMA precious-metals JSON fetcher (prices.lbma.org.uk) — §3.9
│   ├── nasdaq_data_link.py            # Nasdaq Data Link scaffolding (empty after LBMA/GOLD went paid-tier — §3.9)
│   ├── boc.py                         # Bank of Canada Valet API fetcher — keyless JSON (183 lines)
│   ├── statcan.py                     # Statistics Canada WDS fetcher — keyless POST API (201 lines)
│   ├── ons.py                         # ONS Zebedee /data API fetcher — keyless JSON (218 lines)
│   ├── bundesbank.py                  # Deutsche Bundesbank SDMX-ML fetcher — keyless (218 lines)
│   ├── abs.py                         # Australian Bureau of Statistics SDMX-CSV fetcher — keyless (206 lines)
│   ├── istat.py                       # ISTAT (Italy) SDMX-CSV fetcher with vintage (EDITION) resolution and per-series EDITION cache (395 lines)
│   ├── bls.py                         # US Bureau of Labor Statistics Public Data API fetcher — BLS_API_KEY optional (284 lines)
│   ├── insee.py                       # INSEE BDM SDMX-ML fetcher — keyless + optional INSEE_API_KEY (231 lines)
│   ├── bdf.py                         # Banque de France Webstat Opendatasoft Explore v2.1 fetcher — BDF_API_KEY required (352 lines, migrated 2026-06-10)
│   ├── alpha_vantage.py               # Alpha Vantage OVERVIEW fundamentals scaffolding — ALPHAVANTAGE_API_KEY optional; library empty pending shape decision (180 lines, §3.3)
│   ├── shiller.py                     # Yale ie_data.xls long-run S&P composite / CPI / 10Y / CAPE parser (471 lines, §3.13)
│   ├── french.py                      # Ken French Data Library ZIP-direct factor reader (413 lines, §3.13)
│   ├── jst.py                         # Jordà-Schularick-Taylor Macrohistory R6 .dta loader (301 lines, §3.13)
│   ├── atlanta_fed.py                 # Atlanta Fed GDPNow real-time US Q/Q SAAR GDP nowcast — keyless Excel download (392 lines, §3.1.4)
│   ├── ny_fed.py                      # New York Fed Staff Nowcast — real-time US Q/Q SAAR GDP nowcast — keyless Excel download (348 lines, §3.1.4)
│   └── sec_edgar.py                   # SEC EDGAR companyfacts equity fundamentals (revenue + diluted EPS, Q+A) — keyless, fair-access UA (≈420 lines, 2026-06-15)
│
├── data/                          # CSV config libraries + pipeline output files
│   ├── index_library.csv              # Instrument master library (~390 rows, 29 columns)
│   ├── level_change_tickers.csv       # Vol tickers using absolute pt change (14 tickers)
│   │
│   ├── # Raw-macro source libraries (one per provider, registry-only):
│   ├── macro_library_countries.csv    # 14 country codes + WB/IMF code mappings (NLD added 2026-06-10 for the §3.12 priority-10)
│   ├── macro_library_fred.csv         # FRED series IDs (~122 rows; OECD MEI yields + share-price indices + IMF PCPS commodities added 2026-06-10; +9 regime-AA coverage rows 2026-06-15)
│   ├── macro_library_oecd.csv         # OECD SDMX dataflow + dimension keys
│   ├── macro_library_worldbank.csv    # World Bank WDI indicator codes
│   ├── macro_library_imf.csv          # IMF DataMapper indicator codes
│   ├── macro_library_dbnomics.csv     # DB.nomics series paths (~13 rows)
│   ├── macro_library_ifo.csv          # ifo workbook sheet/column locations (26 rows)
│   ├── macro_library_boe.csv          # BoE IADB series codes (7 rows)
│   ├── macro_library_ecb.csv          # ECB Data Portal SDMX keys (3 rows)
│   ├── macro_library_boj.csv          # BoJ Time-Series API codes (9 rows)
│   ├── macro_library_estat.csv        # e-Stat statsDataIds (5 rows)
│   ├── macro_library_lbma.csv         # LBMA JSON series stems + currency (1 row → gold_pm)
│   ├── macro_library_nasdaqdl.csv     # Header-only — NDL scaffolding (no live rows after LBMA/GOLD went paid)
│   ├── macro_library_boc.csv          # BoC Valet series names (5 rows: CAN policy rate, GoC bond yields, CPI-median, USD/CAD)
│   ├── macro_library_statcan.csv      # StatCan WDS vector IDs (4 rows: CAN CPI, unemployment, GDP, employment)
│   ├── macro_library_ons.csv          # ONS CDID taxonomy paths (11 rows: GBR CPI/CPIH/Core CPI, real GDP, unemployment, employment, AWE, IoP, IoS, RSI, monthly GDP)
│   ├── macro_library_bundesbank.csv   # Bundesbank SDMX keys (4 rows: DEU 10Y/short bund yields + 2 more)
│   ├── macro_library_abs.csv          # ABS SDMX keys (5 rows: AUS CPI, real GDP, GDP growth, unemployment, participation rate)
│   ├── macro_library_istat.csv        # ISTAT SDMX keys (3 rows: ITA unemployment, industrial production)
│   ├── macro_library_bls.csv          # BLS series IDs (4 rows: USA CPI headline, core CPI, unemployment, avg hourly earnings)
│   ├── macro_library_insee.csv        # INSEE BDM idbanks (3 rows: FRA business climate, unemployment, GDP volume)
│   ├── macro_library_bdf.csv          # BdF Webstat Opendatasoft Explore v2.1 keys (2 rows: FRA MFI lending rates — PROVISIONAL — dataset_id|odsql_where format)
│   ├── macro_library_alpha_vantage.csv # Header-only — Alpha Vantage OVERVIEW scaffolding (§3.3, population deferred)
│   ├── macro_library_shiller.csv      # Yale ie_data.xls column headers (6 rows: CAPE, S&P composite price/dividend/earnings, US CPI 1871+, 10Y long rate 1871+)
│   ├── macro_library_french.csv       # Ken French ZIP-stem|column keys (6 rows: US 5-factor Mkt-RF/SMB/HML/RMW/CMA + 1m RF)
│   ├── macro_library_jst.csv          # JST Macrohistory R6 <iso>|<column> keys (39 rows: 10 priority economies × cpi/gdp/eq_tr/ltrate; CAN eq_tr dropped 2026-06-11)
│   ├── macro_library_atlanta_fed.csv  # Atlanta Fed GDPNow series (1 row: US_GDPNOW — US Real GDP Q/Q SAAR nowcast, daily)
│   ├── macro_library_ny_fed.csv       # NY Fed Nowcast series (1 row: US_NYFED_NOWCAST — US Real GDP Q/Q SAAR nowcast, weekly)
│   └── macro_library_sec_edgar.csv    # SEC EDGAR fundamentals (68 rows: 34 US pure-plays × revenue+EPS; ticker,cik,metric,gaap_tags,col,name,sort_key)
│   │
│   ├── source_fallbacks.csv           # Per-indicator T0/T1/T2/T3 fallback chain (Stage B + §3.9)
│   ├── manual_splits.csv              # Yahoo-missing split overrides (ticker, ex_date, ratio) — §11 Pattern 11
│   │
│   ├── # Phase E composite-indicator registry:
│   ├── macro_indicator_library.csv    # 108 macro-market indicator definitions
│   ├── reference_indicators.csv       # 206-row L/C/G cycle-timing cross-reference
│   │
│   ├── # Audit infrastructure (§2.6 v2 + §3.1):
│   ├── freshness_thresholds.csv       # Per-frequency staleness defaults (Daily 5d / Weekly 10d / Monthly 45d / Quarterly 120d / Annual 540d)
│   ├── removed_tickers.csv            # Single-ledger record of every library change — removals (action=removed), reroutes (action=rerouted), additions (action=added). Schema: date_removed, action, ticker, ticker_field, library_name, source_csv, reason, audit_run_date, replacement_status, target_identifier, notes
│   ├── yfinance_failure_streaks.csv   # Per-ticker dead-list streak counter consumed by audit_writeback.py (forward_plan §3.1 sub-track 3). Schema: ticker, first_seen_dead, last_seen_dead, consecutive_fail_days
│   ├── _archived_columns/             # Orphan-column archives produced by library_sync.py — preserves historical observations when a library row is removed. Filename: <hist_basename>__<column_id>__<YYYY-MM-DD>.csv
│   │
│   ├── # Pipeline outputs (regenerated each run, committed to git):
│   ├── market_data.csv                # OUTPUT — simple-pipeline daily snapshot
│   ├── market_data_comp.csv           # OUTPUT — comp-pipeline daily snapshot
│   ├── market_data_comp_hist.csv      # OUTPUT — comp-pipeline weekly history
│   ├── macro_economic.csv             # OUTPUT — unified raw-macro snapshot (long-form)
│   ├── macro_economic_hist.csv        # OUTPUT — unified raw-macro weekly history (wide-form, 14 metadata rows)
│   ├── macro_market.csv               # OUTPUT — macro-market indicator snapshot
│   ├── macro_market_hist.csv          # OUTPUT — macro-market indicator weekly history
│   ├── macro_market_monthly_hist.csv  # OUTPUT — month-end-sampled view of macro_market_hist (regime-AA Phase 3 input, §3.14)
│   └── equity_fundamentals.csv        # OUTPUT — SEC EDGAR revenue + diluted EPS history (long/tidy, idempotent-merge; isolated phase in fetch_data.py)
│
├── docs/                          # Indicator Explorer generator
│   ├── build_html.py                  # Generates indicator_explorer.html from CSV + hist (2,921 lines)
│   ├── indicator_explorer.html        # OUTPUT — interactive chart/regime viewer
│   └── indicator_explorer_mkt.js      # OUTPUT — embedded market data JSON
│
├── scripts/                       # Operator utilities (not in the daily run)
│   ├── backadjust_hist_splits.py      # One-off back-adjustment of committed hist + sister CSVs for splits in manual_splits.csv (§11 Pattern 11; idempotent)
│   └── phase_0_coverage_check.py      # Phase 0 regime-AA coverage diagnostic — builds the indicator × region fill matrix and sourcing backlog (2026-06-15)
│
├── manuals/                       # Documentation
│   ├── technical_manual.md            # This file — the authoritative record of current code state
│   ├── forward_plan.md                # Phase summary, architecture rules (§0), priority queue (§2), feature roadmap (§3)
│   ├── multifreq_plan.md              # Detailed Phase 2 (multi-frequency / ragged-column) implementation plan
│   ├── indicator_manual.md            # Indicator-by-indicator reference (user-facing)
│   ├── indicator_manual.docx          # Rendered Word version (built via build_docx.py)
│   ├── macro_market_cheat_sheet.md    # Regime/threshold quick-reference companion
│   ├── macro_market_cheat_sheet.docx  # Rendered Word version (built via md_to_docx.py)
│   ├── build_docx.py                  # Converts indicator_manual.md → .docx
│   └── md_to_docx.py                  # Generic markdown → .docx converter (default: cheat sheet)
│
├── archive/                       # Historical / one-off artefacts kept for reference
│   ├── generate_review_excel.py       # Pre-2026-04-08 indicator-review workbook generator (stale IDs)
│   ├── indicator_groups_review.xlsx   # Input workbook used during the 2026-04 groups review
│   └── indicator_groups_review_UPDATED.xlsx  # Output of that review — drove macro_indicator_library.csv
│
└── .github/workflows/
    └── update_data.yml            # GitHub Actions daily scheduler (00:34 UTC); pipes both runs through `tee pipeline.log`; runs `data_audit.py`; posts the audit to the perpetual `daily-audit` GitHub Issue; commits the log + audit + data CSVs
```

---

## 3. Execution Flow

GitHub Actions runs `python fetch_data.py` once per day. The file is structured as `main()` (simple + comp pipelines + Sheets push) followed by three module-level `try/except` blocks that import and run the downstream phases. Each block is fully independent — a failure anywhere downstream cannot affect tabs already written.

```
fetch_data.py
│
├─ main()
│   ├─ build_comp_fx_cache()                    ← Pre-fetch all 18 FX pairs
│   │
│   ├─ Simple Pipeline
│   │   ├─ load_simple_library()                ← ~70 instruments (simple_dash=True)
│   │   ├─ collect_comp_assets(simple_insts)    ← yfinance prices + returns
│   │   ├─ collect_simple_fred_assets()         ← FRED yields for simple set
│   │   └─ _build_library_df()                  ← Combine into DataFrame
│   │
│   ├─ Comp Pipeline
│   │   ├─ load_instrument_library()            ← ~390 instruments from library
│   │   ├─ collect_comp_assets(comp_insts)      ← yfinance prices + returns
│   │   ├─ collect_comp_fred_assets()           ← FRED yields/spreads/OAS
│   │   └─ _build_library_df()                  ← Combine into DataFrame
│   │
│   ├─ push_to_google_sheets(df_main, df_comp)  ← Writes market_data + market_data_comp
│   │   └─ Sweeps every tab in SHEETS_LEGACY_TABS_TO_DELETE
│   │       (8 retired macro tabs + 4 retired simple-pipeline tabs)
│   │
│   └─ (end of main)
│
├─ [try] run_comp_hist()                        ← fetch_hist            → market_data_comp_hist
│
├─ [try] run_phase_macro_economic()             ← fetch_macro_economic  → macro_economic + macro_economic_hist
│                                                  (Phase ME — unified raw-macro layer)
│                                                  Internally fans out to sources/{fred,oecd,worldbank,imf,dbnomics,ifo,
│                                                  boe,ecb,boj,estat,lbma,boc,statcan,ons,bundesbank,abs,istat,bls,insee,bdf,
│                                                  alpha_vantage,shiller,french,jst,atlanta_fed,ny_fed}.py
│                                                  driven by data/macro_library_*.csv per §0 of forward_plan.md
│
└─ [try] run_phase_e()                          ← compute_macro_market  → macro_market + macro_market_hist
                                                   Reads macro_economic_hist + market_data_comp_hist;
                                                   computes 108 composite indicators (z-score, regime, fwd_regime).
```

The retired Phase A (`fetch_macro_us_fred.py` → `macro_us[_hist]`), Phase C (`fetch_macro_international.py` → `macro_intl[_hist]`), Phase D Tier 2 (`fetch_macro_dbnomics.py` → `macro_dbnomics[_hist]`) and Phase D ifo (`fetch_macro_ifo.py` → `macro_ifo[_hist]`) coordinators were consolidated into Phase ME on 2026-04-23. All four modules and their 8 tabs have been deleted; the tab names live on in `SHEETS_LEGACY_TABS_TO_DELETE` so the daily run sweeps them on the Sheet side.

After `fetch_data.py` finishes, the workflow runs `python docs/build_html.py` to rebuild the Indicator Explorer (`docs/indicator_explorer.html` + `docs/indicator_explorer_mkt.js`) from the freshly updated CSVs. Both Python steps are piped through `tee pipeline.log` with `set -o pipefail`; an `if: always()` step then commits all updated CSVs, the two explorer files, **and `pipeline.log`** back to git (on the `main` branch) with message: `Update market data + explorer - YYYY-MM-DD HH:MM UTC`. Logging always lands even if a phase crashes.

---

## 4. Two Pipelines: Simple vs Comp

The project maintains two parallel instrument pipelines:

| | Simple Pipeline | Comp Pipeline |
|---|---|---|
| **Instrument source** | `index_library.csv` filtered on `simple_dash=True` | `index_library.csv` (all CONFIRMED rows) |
| **Instrument count** | ~70 | ~390 |
| **Snapshot tab** | `market_data` | `market_data_comp` |
| **History tab** | *(none — removed)* | `market_data_comp_hist` |
| **FX coverage** | Same 18-currency cache | Same 18-currency cache |
| **Sort order** | `lib_sort_key()` from `library_utils.py` | `lib_sort_key()` from `library_utils.py` |
| **Pence correction** | Dynamic `.endswith(".L")` + median > 50 check | Same |

Both pipelines are now library-driven. The simple pipeline reads from `index_library.csv` using the `simple_dash` boolean column to select its subset. Both share the same `collect_comp_assets()` function and FX cache. The simple pipeline is preserved for `trigger.py` (see below) but is slated for retirement — see `forward_plan.md` §3.10.

### Downstream Consumer

`trigger.py` (a local Windows script at `C:\Users\kasim\ClaudeWorkflow\`) runs at 06:15 London time and reads only the `market_data` tab. History and macro tabs are for manual analysis only.

---

## 5. Data Sources & APIs

Every fetched identifier lives in a `data/macro_library_*.csv` file (the "Data-Layer Registry" — see `forward_plan.md` §0 / §1). The Python fetchers below read those CSVs at runtime; nothing is hardcoded.

### yfinance

- **Library:** `yfinance` Python package (no API key)
- **Used for:** Price history for ~390 instruments (equities, ETFs, FX, commodities, crypto, volatility) defined in `data/index_library.csv`
- **Rate limiting:** 0.3s delay between per-ticker fetches
- **Known issues:**
  - Some official index tickers return empty history (STOXX 600 sectors, S&P style indices, TOPIX)
  - Russian tickers have data through mid-2022/mid-2024 only (sanctions)
  - UK `.L` tickers report prices in pence (GBp) — corrected via `.endswith(".L")` + median > 50 heuristic

### FRED API

- **URL:** `https://api.stlouisfed.org/fred/series/observations`
- **Auth:** `FRED_API_KEY` environment variable (GitHub Secret)
- **Used for:** ~122 series across yields, inflation, labour, credit, surveys, commodities, OECD-mirror business/consumer confidence, OECD MEI long-rate yields, share-price reference indices, and IMF PCPS commodity prices; back to 1947 where available. Library: `data/macro_library_fred.csv`.
- **Rate limit:** 120 requests/minute per key; pipeline uses 0.6s delay (~100 req/min)
- **Backoff:** Exponential on 429/5xx — 2s, 4s, 8s, 16s, 32s (max 5 retries)
- **Fetcher:** `sources/fred.py` (called by `fetch_macro_economic.py`)

### OECD SDMX REST API

- **URL:** `https://sdmx.oecd.org/public/rest/` (new API, migrated July 2024)
- **Auth:** None required
- **Used for:** Composite Leading Indicator (CLI), Unemployment Rate, 3-month interbank rate across 11 economies. Library: `data/macro_library_oecd.csv`.
- **Format:** `format=csv`
- **Rate limit:** ~20 calls/hour
- **Known structural gap:** OECD does not publish CLI for EA19 or CHE — `compute_macro_market.py` uses the DEU+FRA equal-weight average as the Eurozone CLI proxy.
- **Fetcher:** `sources/oecd.py`

### World Bank Open Data API

- **URL:** `https://api.worldbank.org/v2/country/{code}/indicator/{indicator}`
- **Auth:** None required
- **Used for:** Annual CPI YoY % across 11 economies (per the country registry). Library: `data/macro_library_worldbank.csv`.
- **Note:** Eurozone uses code `EMU` (mapped from canonical `EA19` via `data/macro_library_countries.csv`).
- **Fetcher:** `sources/worldbank.py`

### IMF DataMapper REST API

- **URL:** `https://imf.org/external/datamapper/api/`
- **Auth:** None required
- **Used for:** Real GDP Growth % (annual WEO, includes projections) across 11 economies. Library: `data/macro_library_imf.csv`.
- **Note:** Eurozone code is `EURO` (mapped from `EA19` via `data/macro_library_countries.csv`).
- **Fetcher:** `sources/imf.py`

### DB.nomics REST API

- **URL:** `https://api.db.nomics.world/v22/series/{path}`
- **Auth:** None required
- **Used for:** Open-licensed series not on FRED — currently ~13 series: 3 Eurostat economic-sentiment surveys (`EU_ESI`, `EU_IND_CONF`, `EU_SVC_CONF`), 3 ISM series (`ISM_MFG_PMI`, `ISM_MFG_NEWORD`, `ISM_SVC_PMI`), 3 Eurostat real-economy series (`EZ_IND_PROD`, `EZ_RETAIL_VOL`, `EZ_EMPLOYMENT`), plus 4 Stage-B T1 fallback rows (IMF/IFS, Eurostat). Library: `data/macro_library_dbnomics.csv`.
- **Rate limit:** No published cap; pipeline uses a small inter-call delay
- **Reliability hardening:** `fetch_series` uses a **fail-fast budget + process-level circuit breaker** (§11 Pattern 10) — `timeout=12s`, `retries=2`, and after **3 consecutive hard failures** (timeouts, 5xx exhaustion, or connection errors) the rest of this run's DB.nomics calls short-circuit instantly. Caps a full DB.nomics API outage at ~80 sec instead of ~65 min. Successful (or any server-responding) calls reset the consecutive-failure counter, so isolated blips don't trip it. State persists across snapshot + history passes.
- **Fetcher:** `sources/dbnomics.py`

### LBMA — `prices.lbma.org.uk` JSON

- **URL:** `https://prices.lbma.org.uk/json/{series}.json` (one file per metal × fix-window — e.g. `gold_pm.json`, `gold_am.json`, `silver.json`, `platinum_pm.json`, `palladium_am.json`, etc.)
- **Auth:** None required, no rate limit
- **Used for:** LBMA Gold Price PM Fix in USD (`GOLD_USD_PM` ← `gold_pm`, USD column). Daily series back to **1968-04-05**. Replaces FRED's discontinued `GOLDAMGBD228NLBM` / `GOLDPMGBD228NLBM` (LBMA changed methodology in 2017). Library: `data/macro_library_lbma.csv`.
- **Schema:** library CSV carries a `sub_field` column naming the currency to extract (`USD` / `GBP` / `EUR`). LBMA JSON returns a 3-element `v` array per date; the parser maps `sub_field` to the array index. EUR slot is `0.0` for pre-1999 dates — treated as missing.
- **Status:** Wired §3.9 (2026-05-09); see `manuals/forward_plan.md` §3.9.1 for the multi-commodity extension plan (silver / platinum / palladium via the same module, plus FRED IMF Primary Commodity Prices mirrors for the wider commodity set).
- **Fetcher:** `sources/lbma.py`

### Nasdaq Data Link (scaffolding — empty)

- **URL:** `https://data.nasdaq.com/api/v3/datasets/...` via the `nasdaq-data-link` Python library
- **Auth:** `NASDAQ_DATA_LINK_API_KEY` GitHub Secret (provisioned but currently unused — registry is empty)
- **History:** Initially wired §3.9 on 2026-05-08 with `LBMA/GOLD`; discovered same day that LBMA datasets had moved to NDL's paid tier (403 on free key). Replumbed to LBMA-direct (`sources/lbma.py`). The NDL **module + library + dependency + secret are intentionally retained** as scaffolding so any future free NDL dataset (e.g. an alternative commodity index) becomes a CSV-row addition with no code work. `data/macro_library_nasdaqdl.csv` has the schema header but no live rows.
- **Fetcher:** `sources/nasdaq_data_link.py`

### ifo Institute Excel Workbook

- **URL:** `https://www.ifo.de/sites/default/files/secure/timeseries/gsk-e-<YYYYMM>.xlsx` (English at the secure-timeseries path — current correct URL per §3.9-era diagnostic on 2026-05-27). The English file is the one our parser's column/sheet map is calibrated against; German (`gsk-d-`) is tried only as a last-resort fallback.
- **Auth:** None required
- **Used for:** 26 German business-survey series — Industry+Trade composite plus Manufacturing / Services / Trade / Wholesale / Retail / Construction sub-sectors, plus Uncertainty + Cycle Tracer. History from 1991. Library: `data/macro_library_ifo.csv` (registers each series by sheet index + Excel column).
- **Quirks:** ifo intermittently serves a 3038-byte HTML challenge page for files that *do* exist (verified via `scripts/ifo_probe.py`). The fetcher treats a non-xlsx body as a *retryable throttle*, not a hard miss.
- **Reliability hardening:** `_resolve_workbook_impl()` is **process-level cached** (success *and* failure) so snapshot + history share one network call; `_try_download_xlsx` has `timeout=15s` + `retries=2`; `_candidate_urls()` walks the current month + 3 prior months for `gsk-e-` then falls back to `gsk-d-` for 2 most-recent months. Worst-case ifo time bounded to ~3 min. See §11 Pattern 10 for the shared fail-fast pattern.
- **Bright Data Web Unlocker fallback (2026-06-12):** when the direct-URL and landing-page strategies both fail (HTML challenge persists across all candidate URLs), the fetcher escalates to a third strategy: routing the download through the Bright Data Web Unlocker proxy. Activated only when `BRIGHTDATA_API_KEY` is set in the environment; capped at 30 calls per run (`_MAX_BRIGHTDATA_CALLS_PER_RUN`) to stay within the free-tier 5,000 requests/month budget. When the secret is absent the third strategy skips silently and ifo degrades to blank rows (the existing behaviour). `BRIGHTDATA_ZONE` defaults to `"web_unlocker1"` if unset.
- **Fetcher:** `sources/ifo.py` (579 lines; validates the workbook via magic-byte check `PK\x03\x04` before parsing).

#### Diagnosing future ifo outages

If `DE_IFO*` columns ever go missing again, the four-step contract is:
1. Pull `pipeline.log` and grep `[ifo]` lines — look for `Direct-URL resolve + validated:` (good) vs `3038 bytes (ct='text/html...) not xlsx` (URL or throttle).
2. If the URL pattern changed, `scripts/ifo_probe.py` (kept in repo as a reusable diagnostic) can be re-run via the `ifo_probe` workflow to enumerate live download links from the landing pages.
3. If it's a sustained 3038-HTML throttle, the cache + retry should already bound it. If the anti-bot challenge persists for several consecutive runs, consider enabling the Bright Data Web Unlocker fallback (`BRIGHTDATA_API_KEY` in the workflow secrets) — the fetcher will automatically route through it before the 3038-byte response is accepted as a permanent miss.
4. Last resort: substitute `DE_IFO1` via the OECD German BCI (`DEU_BUS_CONF`) we already fetch — same survey methodology, different aggregator.

### US Bureau of Labor Statistics — BLS Public Data API (2026-05-28)

- **URL:** `https://api.bls.gov/publicAPI/v2/timeseries/data/` (POST, v2 with key) / `https://api.bls.gov/publicAPI/v1/timeseries/data/<seriesid>` (GET, keyless v1)
- **Auth:** `BLS_API_KEY` optional — without a key the v1 keyless endpoint serves a ~3-year rolling window; with a free registration key the v2 endpoint gives 500 queries/day, 50 series/query, and 20-year history. Pipeline currently operates keyless for the 4 registered series (recent window sufficient for freshness; history is provided by FRED fallback columns).
- **Used for:** 4 US series that share canonical columns with FRED — `USA_CPI_INDEX` (CUSR0000SA0 — CPI-U SA), `USA_CORE_CPI_INDEX` (CUSR0000SA0L1E — Core CPI SA), `USA_UNEMPLOYMENT` (LNS14000000), `USA_AVG_HOURLY_EARN` (CES0500000003 — average hourly earnings total private SA; genuine coverage gap with no FRED-library equivalent). BLS is the **ultimate (primary) source**; FRED is the automatic fallback. Library: `data/macro_library_bls.csv`.
- **Fetcher:** `sources/bls.py` (284 lines). Smoke test: `test_bls_smoke.py` (daily CI step).

### Bank of Canada — Valet API (2026-05-28)

- **URL:** `https://www.bankofcanada.ca/valet/observations/<seriesNames>/json` with `?recent=<n>` or `?start_date=YYYY-MM-DD`
- **Auth:** None required. Free, keyless JSON API.
- **Used for:** 5 Canada series: Policy Rate (`CAN_POLICY_RATE` ← V39079), GoC 2Y benchmark yield (`CAN_GOV_2Y` ← BD.CDN.2YR.DQ.YLD), GoC 10Y benchmark yield (`CAN_GOV_10Y` ← BD.CDN.10YR.DQ.YLD), BoC CPI-median core inflation (`CAN_CPI_MEDIAN`), USD/CAD reference rate (`CAN_USDCAD`). Library: `data/macro_library_boc.csv`.
- **Fetcher:** `sources/boc.py` (183 lines). Response shape: `{"observations": [{"d": "YYYY-MM-DD", "<series>": {"v": "<value>"}}, ...]}`.

### Statistics Canada — Web Data Service (2026-05-28)

- **URL:** `POST https://www150.statcan.gc.ca/t1/wds/rest/getDataFromVectorsAndLatestNPeriods` (latest N periods) or GET for full history
- **Auth:** None required. Free, keyless JSON API.
- **Used for:** 4 Canada series: `CAN_CPI` (vector 41690973 — all-items CPI), `CAN_UNEMPLOYMENT` (vector 2062815 — LFS rate), plus 2 more. Library: `data/macro_library_statcan.csv`.
- **Series ID convention:** numeric vector ID (with or without leading `v`).
- **Fetcher:** `sources/statcan.py` (201 lines).

### UK Office for National Statistics — ONS Zebedee API (2026-05-28)

- **URL:** `https://api.beta.ons.gov.uk/v1/data?uri=<taxonomy-path>/timeseries/<cdid>/<dataset>` (the legacy `api.ons.gov.uk` host was decommissioned 2024-11-25)
- **Auth:** None required. Free, keyless JSON API.
- **Used for:** 6 UK series: `GBR_CPI_YOY` (D7G7 — CPI annual rate), `GBR_CPIH_YOY` (L55O — CPIH annual rate), `GBR_GDP_REAL` (ABMI — real GDP chain volume), `GBR_UNEMPLOYMENT` (MGSX — unemployment rate 16+), `GBR_EMP_RATE` (LF24 — employment rate 16-64), `GBR_AWE_REGPAY_YOY` (KAI9 — average weekly earnings regular pay YoY). Library: `data/macro_library_ons.csv`.
- **Series ID convention:** website taxonomy URI of the timeseries (e.g. `economy/inflationandpriceindices/timeseries/d7g7/mm23`). The module picks the finest non-empty frequency array from the response (months > quarters > years).
- **Fetcher:** `sources/ons.py` (218 lines).

### Deutsche Bundesbank — SDMX REST API (2026-05-28)

- **URL:** `https://api.statistiken.bundesbank.de/rest/data/<flow>/<key>?lastNObservations=<n>`
- **Auth:** None required. SDMX-ML only (JSON/CSV return HTTP 406).
- **Used for:** 4 Germany series: `DEU_BUND_10Y` (BBSIS daily yield residual maturity 9-10y — daily, ultimate source vs FRED monthly mirror), `DEU_BUND_1_2Y` (1-2y residual maturity — genuine gap, no aggregator equivalent), plus 2 more. Library: `data/macro_library_bundesbank.csv`.
- **Series ID convention:** `<flow>/<key>` where the key is the full dot-separated SDMX dimension tuple (all 15 dimensions for BBSIS required — a shorter key returns HTTP 404).
- **Fetcher:** `sources/bundesbank.py` (218 lines).

### Australian Bureau of Statistics — ABS Data API (2026-05-28)

- **URL:** `https://data.api.abs.gov.au/rest/data/<flow>/<key>?lastNObservations=<n>` (SDMX-CSV; JSON returns HTTP 406)
- **Auth:** None required.
- **Used for:** 5 Australia series: `AUS_CPI` (CPI all-groups index), `AUS_GDP_REAL` (chain volume GDP), `AUS_GDP_GROWTH` (QoQ % change), `AUS_UNEMPLOYMENT` (LF unemployment rate 15+ SA), `AUS_PART_RATE` (participation rate 15+ SA). Library: `data/macro_library_abs.csv`.
- **Fetcher:** `sources/abs.py` (206 lines). CSV shape identical to ECB Data Portal (TIME_PERIOD + OBS_VALUE columns).

### ISTAT — Italy Statistics Bureau SDMX API (2026-05-28)

- **URL:** `https://esploradati.istat.it/SDMXWS/rest/data/<flow>/<key>?lastNObservations=<n>` (SDMX-CSV)
- **Auth:** None required. **Note:** ISTAT gateway is flaky and frequently returns transient HTTP 503. The module retries, but the retry budget was tightened 2026-06-12 (timeout 90s→30s, retries 6→3) to cap worst-case pipeline blockage at ~97s per series instead of ~570s.
- **Used for:** 3 Italy series: `ITA_UNEMPLOYMENT` (dataflow 151_874 — monthly unemployment rate 15-74), `ITA_IND_PROD` (dataflow 115_333 — industrial production total ex-construction, base 2021). Library: `data/macro_library_istat.csv`.
- **Vintage (EDITION) handling:** many ISTAT dataflows carry an EDITION dimension for release vintages. Leave the trailing slot empty in the series ID (trailing dot) — the module resolves the *latest* edition (the vintage with the most recent observation) at fetch time.
- **Fetcher:** `sources/istat.py` (287 lines).

### INSEE BDM — Banque de Données Macroéconomiques (2026-06-09)

- **URL:** `https://api.insee.fr/series/BDM/V1/data/<dataset>/<key>` (SDMX-ML)
- **Auth:** Keyless — the BDM API is open. An optional `INSEE_API_KEY` (Bearer token from the INSEE portal) can be set as an env var; the module sends it if present but does not require it. Series ID convention: `<dataset>/<key>` or `SERIES_BDM/<idbank>` for a bare idbank lookup.
- **Used for:** 3 France series (INSEE is the **ultimate/primary** source, superseding OECD/Eurostat aggregators): `FRA_BUS_CONF` (idbank 001565530 — Business Climate all-sectors, normalised mean=100), `FRA_UNEMPLOYMENT` (idbank 001688527 — ILO unemployment rate, Quarterly), `FRA_GDP_INDEX` (idbank 011794860 — GDP chained volume SA-WDA, base 2020). All 3 verified live keyless 2026-06. Library: `data/macro_library_insee.csv`.
- **Fetcher:** `sources/insee.py` (231 lines). Parses both SDMX-ML generic-data (`<ObsDimension>/<ObsValue>`) and structure-specific (`TIME_PERIOD=`/`OBS_VALUE=` attributes) shapes. Smoke test: `test_insee_smoke.py` (daily CI step).

### Banque de France — Webstat API (Opendatasoft Explore v2.1, migrated 2026-06-10) — PROVISIONAL

- **URL:** `https://webstat.banque-france.fr/api/explore/v2.1/catalog/datasets/<dataset_id>/records?where=<ODSQL>&limit=100&offset=N` (records JSON per Opendatasoft conventions: `{"total_count": N, "results": [{...}]}`)
- **Auth:** `BDF_API_KEY` required (single `Authorization: Apikey <key>` header — the legacy IBM API Connect Client Id + Client Secret pair was retired with the migration). Without a key the module logs a warning and skips all BdF series gracefully. Register on the developer portal at `https://webstat.banque-france.fr/` (Login → API).
- **Used for:** 2 France MFI lending-rate series — `FRA_LOAN_RATE_HOUSE` (legacy SDMX key `M.FR.B.A2C.A.R.A.2250.EUR.N` — new loans to households for house purchase) and `FRA_LOAN_RATE_NFC` (legacy SDMX key `M.FR.B.A2A.A.R.A.2240.EUR.N` — new loans to non-financial corporations). Library: `data/macro_library_bdf.csv`.
- **Series-id convention:** `<dataset_id>|<odsql_where>` — single library column carries both halves separated by `|`. Records that decompose into `dataset_id == 'PROVISIONAL'` are flagged and skipped by the fetcher with a loud warning.
- **Status:** **PROVISIONAL / UNVERIFIED** — the public Opendatasoft catalogue exposes only one dataset (`tableaux_rapports_preetablis` = archived report attachments); the 37k+ time series including the MIR dataset are gated behind the developer-portal login. The two rows in `macro_library_bdf.csv` carry their original legacy SDMX dot-keys in the `series_id` field as `PROVISIONAL|legacy_sdmx_key=...` annotations so the next credentialed session can translate them in-place. Confirmation requires a real `BDF_API_KEY` in the runtime to query `/catalog/datasets?q=MFI+interest+rates` and walk the resulting dataset schema.
- **Migration history (2026-06-10, commit `e0b3e4c`):** the legacy IBM API Connect stack (`api.webstat.banque-france.fr/webstat-fr/v1`, SDMX-JSON, `X-IBM-Client-Id` + `X-IBM-Client-Secret`) was deprecated; the first credentialed run on 2026-06-10 (run id `27271070256`) returned HTTP 401 `"Invalid client id or secret"`, traced to BdF having already migrated to the Opendatasoft stack. `BDF_API_SECRET` was removed from `.github/workflows/update_data.yml` in the same commit. See §13 for the issue summary.
- **Fetcher:** `sources/bdf.py` (352 lines). Smoke test: `test_bdf_smoke.py` (daily CI step — skips when `BDF_API_KEY` is unset, and PROVISIONAL rows skip individually so the test stays green until the rows are upgraded to real `<dataset_id>|<odsql>` form).

### Alpha Vantage — OVERVIEW fundamentals (2026-06-10) — SCAFFOLDING

- **URL:** `https://www.alphavantage.co/query?function=OVERVIEW&symbol=<SYM>&apikey=<key>` (JSON snapshot — PE, forward PE, PEG, dividend yield, EPS, book value)
- **Auth:** `ALPHAVANTAGE_API_KEY` optional. Without a key the module no-ops gracefully (same posture as `sources/bdf.py`). Free tier is 25 requests/day — too thin for a daily fan-out across the comp library, so population of `data/macro_library_alpha_vantage.csv` is deferred per the §3.3 evaluation memo (`manuals/alpha_vantage_evaluation.md`).
- **Used for:** snapshot fundamentals for the §3.3 PE-ratio integration. Library presently header-only; the smoke test pings SPY once per CI run to confirm the OVERVIEW endpoint still resolves and detects the "Note: API rate limit" body shape.
- **Rate-limit detection:** any response carrying a `Note` field (free-tier daily cap) or an empty `Symbol` is treated as a non-data response and surfaced through the audit channel.
- **Fetcher:** `sources/alpha_vantage.py` (180 lines). Smoke test: `test_alpha_vantage_smoke.py` (daily CI step — skips when the key is unset).

### Robert Shiller — Yale `ie_data.xls` long-run dataset (2026-06-10)

- **URL:** `http://www.shillerdata.com/data/ie_data.xls` (primary host, 2026-06-11 update); Yale `http://www.econ.yale.edu/~shiller/data/ie_data.xls` is the fallback. Excel workbook; the "Data" sheet has 7 pre-header rows, header on row 8, monthly observations from Jan 1871.
- **Auth:** None required.
- **Used for:** 6 US monthly series — Shiller CAPE (`USA_CAPE`), S&P 500 Composite Price (`USA_SP500_SHILLER`), dividends (`USA_SP500_DIV_SHILLER`), earnings (`USA_SP500_EPS_SHILLER`), US CPI 1871+ (`USA_CPI_SHILLER`), US 10Y long rate 1871+ (`USA_TREAS_10Y_SHILLER`). Library: `data/macro_library_shiller.csv`. **Role:** confirmatory pre-1950 cross-validation anchor per the regime-AA v2 §3.13 handoff memo — column names are deliberately distinct from the modern BLS/FRED canonicals (`USA_CPI_INDEX`, `USA_TREAS_10Y`) so the long-run rows don't shadow the production columns.
- **Date-column quirk:** Shiller's "Date" column is decimal-year format where the fractional part is the month — `1871.10` is October 1871, **not** the first decile. The parser does `month = round((val - year) * 100)`; when the workbook serialises as strings the convention `"1871.1" → January, "1871.10" → October` is preserved (no zero-padding rewrite).
- **Caching:** the downloaded workbook is process-cached (success + failure) — a fan-out that pulls CAPE + CPI + 10Y from the same library only hits Yale once. Same shape as `sources/ifo.py::_resolve_workbook_impl()`.
- **Fetcher:** `sources/shiller.py` (471 lines). Smoke test: `test_shiller_smoke.py` (daily CI step — SKIPs when shillerdata.com and the Yale fallback are unreachable from the runner, which is expected in the local sandbox).

### Kenneth French — Dartmouth Tuck Data Library (2026-06-10)

- **URL:** ZIP-direct against `https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/<zip_stem>_CSV.zip` (e.g. `F-F_Research_Data_5_Factors_2x3_CSV.zip`). Each ZIP unpacks to a single CSV containing a monthly block followed by an annual block; we extract the monthly block only.
- **Auth:** None required. The Dartmouth FTP occasionally 403s bare-UA requests; the module sends browser-like headers (same shape as `sources/ifo.py`).
- **Used for:** 6 US monthly factor returns from 1926-07 onwards — `Mkt-RF`, `SMB`, `HML`, `RMW`, `CMA`, plus the 1-month T-bill `RF`. Mapped to columns `USA_FF_MKT_RF`, `USA_FF_SMB`, `USA_FF_HML`, `USA_FF_RMW`, `USA_FF_CMA`, `USA_FF_RF`. Library: `data/macro_library_french.csv`. **Role:** regime-AA Phase 0 long-run factor requirement. International (Developed_5_Factors) + emerging (Emerging_5_Factors) extensions deferred as follow-up.
- **Series-ID convention:** `<zip_stem>|<column>` so one library row picks exactly one column out of one ZIP (the parser strips the ZIP only once per process and slices per registered column).
- **Caching:** `_resolve_zip()` does the HTTP fetch + `zipfile.ZipFile` open once per process and reuses the result for every column the registry asks for.
- **Fetcher:** `sources/french.py` (413 lines). **2026-06-11 fix:** `Mkt-RF`, `SMB`, `HML`, and `RF` rows in `macro_library_french.csv` were re-pointed to the **3-Factor ZIP** (`F-F_Research_Data_Factors_CSV.zip`) which carries data from 1926-07, rather than the 5-Factor ZIP which starts only 1963-07 — this extends the Mkt-RF / HML history by ~37 years. Smoke test: `test_french_smoke.py` (daily CI step — SKIPs when Dartmouth is unreachable from the runner).

### Jordà-Schularick-Taylor Macrohistory (2026-06-10)

- **URL:** Single Stata-format download from `https://www.macrohistory.net/database/` (current release as of 2026-06: R6, `JSTdatasetR6.dta`). The file is small (~5 MB compressed, ~50 MB in memory) so the whole DataFrame is process-cached and sliced per indicator.
- **Auth:** None required. `www.macrohistory.net` is on the pipeline allow-list; the sandbox edge sometimes still returns `host_not_allowed` 403s. The smoke test SKIPs cleanly in that case.
- **Used for:** 40 annual rows = 10 priority economies (USA, GBR, DEU, FRA, ITA, JPN, NLD, CAN, AUS, CHE) × 4 columns (`cpi`, `gdp`, `eq_tr` equity total return, `ltrate` long-term rate). 1870+ depth. Library: `data/macro_library_jst.csv`. **Role:** confirmatory pre-1950 cross-validation anchor per the §3.13 handoff memo — not a regime-engine primary input. Column names like `USA_CPI_JST` / `GBR_GDP_JST` deliberately don't shadow the modern aggregator canonicals.
- **Series-ID convention:** `<iso>|<column>`, e.g. `USA|cpi`, `GBR|gdp`. The fetcher splits on `|` to slice the (country, column) cell out of the cached wide-format DataFrame.
- **Read engine:** `pandas.read_stata` — no `pyreadstat` dependency.
- **Fetcher:** `sources/jst.py` (301 lines). Smoke test: `test_jst_smoke.py` (daily CI step — SKIPs when `macrohistory.net` is unreachable).

### Atlanta Fed GDPNow (2026-06-11)

- **URL:** `https://www.atlantafed.org/cqer/research/gdpnow` (landing page); the module downloads the Excel workbook `GDPTrackingModelDataAndForecasts.xlsx` directly from the Atlanta Fed website and caches it process-level. Keyless — no API key required.
- **Auth:** None required.
- **Used for:** 1 US series — `US_GDPNOW` (real-time Q/Q SAAR GDP growth nowcast). Published daily on business days from 2014 onwards when a new nowcast round runs. Library: `data/macro_library_atlanta_fed.csv`.
- **Freshness override:** 14 days (the nowcast doesn't update on weekends or holidays, and between Fed reserve windows the model may hold for several business days).
- **Role:** First-class Phase E indicator `US_GDPNOW1` on the Growth axis — provides a real-time GDP estimate that updates daily/weekly rather than waiting for the official quarterly release (~30-day lag).
- **Fetcher:** `sources/atlanta_fed.py` (392 lines). Key functions: `load_library()`, `_download_workbook()`, `_resolve_workbook_bytes()` (process-cached — one download per run), `fetch_series_as_pandas(series_id, col_name, ...)`. Smoke test: `test_atlanta_fed_smoke.py` (daily CI step).

### New York Fed Staff Nowcast (2026-06-12)

- **URL:** NY Fed medialibrary CDN — the module downloads `New_Nowcast_Data_2002_present.xlsx` from `https://www.newyorkfed.org/medialibrary/media/research/policy/nowcast/` and caches it process-level. Keyless — no API key required.
- **Auth:** None required.
- **Used for:** 1 US series — `US_NYFED_NOWCAST` (real-time Q/Q SAAR GDP growth nowcast, weekly, 2002+). Published each Friday during tracking quarters (silent for ~3-5 business days around BEA's advance estimate). Library: `data/macro_library_ny_fed.csv`.
- **Freshness override:** 14 days (consistent with `US_GDPNOW`, which also skips weekends, holidays, and inter-vintage quiet windows).
- **Role:** Second-opinion read on US Growth alongside `US_GDPNOW1` — the NY Fed model uses a Bayesian dynamic-factor approach vs. Atlanta Fed's bridge-equation model; cross-confirmation between the two is a stronger signal than either alone. Feeds the `US_NOWCAST1` Phase E indicator on the Growth axis.
- **Series parsing:** rightmost non-null value per publication row (each row = one vintage date, columns = model vintages); forward-filled across quiet windows in `_calc_US_NOWCAST1`.
- **Fetcher:** `sources/ny_fed.py` (348 lines). Smoke test: `test_ny_fed_smoke.py` (daily CI step — SKIPs when the medialibrary CDN is unreachable).

### SEC EDGAR — `companyfacts` equity fundamentals (2026-06-15)

- **URLs:** `https://www.sec.gov/files/company_tickers.json` (ticker → CIK map, cached locally with a 7-day TTL under `data/.sec_edgar_cache/`, gitignored) and `https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json` (one document per company carrying every reported XBRL fact). **Keyless and free** — EDGAR requires no API key.
- **Auth / fair-access (MANDATORY):** the SEC's fair-access policy requires every request to carry a descriptive `User-Agent` naming the caller plus a contact email — without it EDGAR returns HTTP 403. `sources/sec_edgar.py` sets `User-Agent: market_dash_auto/1.0 (<contact>)` (contact overridable via the `SEC_EDGAR_CONTACT` env var) and throttles process-wide to ≤10 req/s (`_MIN_INTERVAL = 0.15s`). Backoff on 429/5xx is delegated to `base.fetch_with_backoff` (extended 2026-06-15 with an optional `headers=` argument — backward-compatible; existing callers unaffected).
- **Used for:** revenue + diluted-EPS multi-year history for the US-filer pilot pure-plays in `data/macro_library_sec_edgar.csv` (34 tickers: NVDA, AVGO, QCOM, INTC, IBM, MSFT, GOOGL, PLTR, NOW, CRM, CRWD, RXRX, SDGR, IONQ, EQIX, DLR, VRT, ETN, CEG, VST, TLN, GEV, LNG, XOM, LMT, MP, FCX, ALB, MRNA, NTLA, MRK, VRSK, CB, RNR; 68 rows = revenue + EPS each). Per-ticker revenue tag priority: insurers (CB, RNR) and energy names (XOM, LNG) lead with us-gaap `Revenues`; all others lead with `RevenueFromContractWithCustomerExcludingAssessedTax`. The adapter unions every listed tag, so order only decides the winner on overlapping periods. Non-US issuers (TSM, ASML, SAP, BNTX, RIO, …) and private names are **out of scope** for EDGAR (they file 20-F / don't file us-gaap XBRL facts; sourced elsewhere via yfinance).
- **Tag handling:** revenue tries the us-gaap tags `RevenueFromContractWithCustomerExcludingAssessedTax → Revenues → SalesRevenueNet` in priority order; EPS tries `EarningsPerShareDiluted → EarningsPerShareBasic`. All listed tags are **unioned** to recover the longest history (companies switch concepts over time, e.g. the ASC-606 revenue cut-over), but where one fiscal period is reported under multiple tags the higher-priority tag wins, and within a tag a **restated period keeps the latest-filed value**. Period type is classified by XBRL duration — ~3 months → `Q`, ~12 months → `A` — dropping the 6-/9-month year-to-date cumulative stubs.
- **Output:** `data/equity_fundamentals.csv` — long/tidy, one row per (ticker, metric, fiscal period). Columns: `ticker, metric (revenue|eps), period_end, period_type (Q|A), value, unit, fy, fp, form (10-K/10-Q), source="SEC EDGAR", retrieved (UTC date)`. Written by an **isolated phase** at the foot of `fetch_data.py` (its own `try/except`, after the macro/market phases) with an idempotent merge keyed on `(ticker, metric, period_end, period_type)`: unchanged periods keep their original `retrieved` (no churn), restated/new periods take the fresh value, and periods missing from a given run (e.g. EDGAR unreachable for one ticker) are preserved — a transient miss never deletes history. The library write side-effect lives in the coordinator (`fetch_data.py`), keeping `sources/sec_edgar.py` side-effect-free like every other source module.
- **Keyless posture / graceful no-op:** an empty/absent library, an unreachable endpoint (incl. the sandbox-egress `403 Host not in allowlist`), or a missing tag all degrade to a zero-row no-op that leaves the existing CSV untouched — same posture as `sources/alpha_vantage.py` and `sources/bdf.py`. Because it is a per-company financial-statement feed on a 10-Q/10-K cadence (not a Friday-spine macro series), it is **not** wired into the unified `macro_economic` feed, `data_audit.py`'s `SOURCE_BY_LIBRARY`, or `library_sync.py`; it stands alone in `equity_fundamentals.csv`.
- **Fetcher:** `sources/sec_edgar.py` (≈420 lines). Key functions: `load_library()`, `resolve_cik(ticker)`, `fetch_companyfacts(cik)`, `extract_metric(facts, gaap_tags)`, `build_fundamentals_df(rows=None)`. Smoke test: `test_sec_edgar_smoke.py` (daily CI step — network-gated, resolves NVDA's CIK then asserts non-empty revenue + EPS series and the tidy schema; SKIPs when EDGAR is unreachable).

### Google Sheets API v4

- **Auth:** Service account JSON in `GOOGLE_CREDENTIALS` environment variable (GitHub Secret)
- **Spreadsheet ID:** `12nKIUGHz5euDbNQPDTVECsJBNwrceRF1ymsQrIe4_ac`
- **Write method:** `spreadsheets().values().update()` with `valueInputOption="USER_ENTERED"`
- **Scopes:** `https://www.googleapis.com/auth/spreadsheets`
- **Tab safety:** every writer checks `library_utils.SHEETS_PROTECTED_TABS` before writing; `library_utils.SHEETS_LEGACY_TABS_TO_DELETE` is swept on every run.

### ECB Data Portal

- **URL:** `https://data-api.ecb.europa.eu/service/data` (replaced retired `sdw-wsrest.ecb.europa.eu` host on PR2, 2026-04-26)
- **Auth:** None required. SDMX 2.1 over REST.
- **Used for (inline):** Euro area AAA govt 10Y yield (YC dataset, key `B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y`) consumed by `fetch_ecb_euro_ig_spread()` in `compute_macro_market.py`.
- **Used for (registry-driven, via `sources/ecb.py`):** ECB Deposit Facility Rate (`EA_DEPOSIT_RATE` ← `FM/D.U2.EUR.4F.KR.DFR.LEV`), AAA euro yield curve points (`EZ_GOVT_2Y` ← `YC/...SR_2Y`, `EZ_GOVT_30Y` ← `YC/...SR_30Y`), ECB Composite Indicator of Systemic Stress (`EZ_CISS` ← `CISS/D.U2.Z0Z.4F.EC.SS_CIN.IDX` — daily systemic-stress composite 0–1, verified live 2026-06-15), ECB Consumer Expectations Survey 12M inflation expectations (`EZ_INFL_EXP_12M` ← `CES/M.Z18.ALL.T.C1120.NUM_VAR.WM` — monthly weighted median, verified live 2026-06-15). Library: `data/macro_library_ecb.csv` (5 rows).
- **Rate limit:** 2s delay; 60s timeout; `lastNObservations=N` on snapshot calls to keep responses small.
- **Fetcher:** `sources/ecb.py` (registry path) + inline call in `compute_macro_market.py` (legacy YC call — refactor TODO).

### Bank of England — IADB

- **URL:** `https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp` (with fallback to legacy `fromshowcolumns.asp`)
- **Auth:** None required. CSV download with multi-row title preamble.
- **Used for:** UK Bank Rate (`GBR_BANK_RATE` ← `IUDBEDR`), SONIA (`GBR_SONIA` ← `IUDSOIA`), gilt par/zero-coupon yields S/M/L (`GBR_GILT_S/M/L` ← `IUDSNPY/IUDMNPY/IUDLNPY`, `GBR_GILT_MZ/LZ` ← `IUDMNZC/IUDLNZC`). Library: `data/macro_library_boe.csv`.
- **Quirks:** WAF blocks default `python-requests` User-Agent → module sends a Chrome-like UA; multi-line title preamble is dynamically skipped via "DATE" header detection.
- **Known gap:** BoE IADB does not publish UK corporate bond yield indices — those have to come via ETF proxy (`SLXX.L` in `index_library.csv`) or a future Bundesbank module.
- **Fetcher:** `sources/boe.py` (Stage D).

### Bank of Japan — Time-Series Data Search

- **URL:** `https://www.stat-search.boj.or.jp/api/v1/getDataCode?<params>` (programmatic API launched February 2026)
- **Auth:** None required. Documentation: `manuals/BOJ_api_manual_en.pdf`.
- **Used for:** 9 Japan series — BoJ Policy Rate (`JPN_POLICY_RATE` ← `FM01'STRDCLUCON`, T2 backup to DB.nomics IMF/IFS T1), Tankan Large Manufacturers Business Conditions DI (`JP_TANKAN1` ← `CO'TK99F1000601GCQ01000`), JP PPI (`JPN_PPI` ← `PR01'PRCG20_2200000000`), Services PPI (`JPN_SPPI` ← `PR02'PRCS20_5200000000`), and 5 Tankan sub-DIs added 2026-06-11 for the `JP_TANKAN_SPREAD1` / `JP_TANKAN_SVC1` / `JP_TANKAN_FWD1` Phase E indicators: Large Mfg Forecast DI (`JP_TANKAN_LMFG_FCST`), Large Non-Mfg DI (`JP_TANKAN_LNFG`), Large Non-Mfg Forecast DI (`JP_TANKAN_LNFG_FCST`), Small Mfg DI (`JP_TANKAN_SMFG`), Small Non-Mfg DI (`JP_TANKAN_SNFG`). Library: `data/macro_library_boj.csv`.
- **Series-code format:** the search-screen presents codes as `<DB>'<series_code>` (e.g. `FM01'STRDCLUCON`); the API takes them split — `_split_series_id` handles this internally.
- **Response shape:** CSV with metadata preamble (STATUS / MESSAGEID / PARAMETER lines) + one row per observation with 8 columns (SERIES_CODE / NAME / UNIT / FREQUENCY / CATEGORY / LAST_UPDATE / SURVEY_DATES / VALUES). `parse_csv` finds the SERIES_CODE header dynamically and reads SURVEY_DATES (YYYYMMDD) + VALUES.
- **Fetcher:** `sources/boj.py` (Stage D).

### e-Stat — Statistics Bureau of Japan

- **URL:** `https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData`
- **Auth:** Free App ID required (registered, exposed as `ESTAT_APP_ID` GitHub Secret)
- **Used for:** METI Indices of Industrial Production (`JPN_IND_PROD` ← `statsDataId 0003446463`). 71 years of monthly data (1955→present). Library: `data/macro_library_estat.csv`.
- **Series-id convention:** `<statsDataId>` for single-series tables; `<statsDataId>?cdCat01=XXX&cdCat02=YYY` for multi-dim tables — the part after `?` is appended verbatim as additional API parameters.
- **Response shape:** deeply-nested JSON. `parse_response` extracts `GET_STATS_DATA → STATISTICAL_DATA → DATA_INF → VALUE` list of `{"@time": "YYYYMMDD", "$": "value"}`; `_parse_estat_time` handles the 10-digit period encoding (annual / monthly / daily).
- **Fetcher:** `sources/estat.py` (Stage D).

---

### Anti-bot fetching tier

A handful of upstream sources serve anti-bot challenge HTML instead of the expected payload when fetched from a vanilla `requests` client (notably ifo.de's `gsk-{d,e}-YYYYMM.xlsx` workbook URLs — see §11 Pattern 10 and the ifo §5 entry above). The pipeline's policy when this happens:

1. **First try direct.** Every source still attempts a plain `requests.get()` first. If the upstream lifts its anti-bot policy, we don't pay for a routed call.
2. **Production tier — Bright Data Web Unlocker** (free tier: 5,000 requests/month). When the direct call returns HTML for a binary URL, the fetcher routes the request through Bright Data's Web Unlocker REST API. Credentials: `BRIGHTDATA_API_KEY` GitHub Secret. A per-run budget cap inside the source module prevents a misbehaving retry loop from draining the monthly cap in one workflow run. The free tier covers `scrape_as_markdown`/`scrape_batch` (Web Unlocker) and `search_engine`/`search_engine_batch` (SERP); `ask_brightdata_assistant` is paid-tier and is **not** to be used.
3. **Dev / fallback tier — Stealth Browser skill** (not currently installed). [`zippoxer/claude-skills`](https://github.com/zippoxer/claude-skills) provides a Claude Code skill built on the `nodriver` library that drives a real Chrome via CDP with anti-detect hardening — solves Cloudflare Turnstile, persists session state across calls, handles multi-step interactive flows. Strengths: free, open-source, downloads binaries natively. Weaknesses: heavier install footprint (Chrome + Python deps), so not currently wired into CI. If we ever exceed Bright Data's free-tier cap, or hit a site Web Unlocker can't crack, install to `~/.claude/skills/` for exploratory work and consider wiring as a CI fallback at that point.

---

## 6. Google Sheets Tab Map

All tabs live in a single spreadsheet (`12nKIUGHz5euDbNQPDTVECsJBNwrceRF1ymsQrIe4_ac`). Active and legacy tab sets are defined as `frozenset`s in `library_utils.py` (`SHEETS_PROTECTED_TABS`, `SHEETS_ACTIVE_TABS`, `SHEETS_LEGACY_TABS_TO_DELETE`); all four writer modules import these constants instead of hardcoding tab names.

### Active Tabs (7)

| Tab Name | Written By | CSV Mirror | Contents |
|---|---|---|---|
| `market_data` | `fetch_data.py` | `data/market_data.csv` | ~70 simple-pipeline instruments, daily snapshot. **Protected** — consumed by downstream `trigger.py`. |
| `market_data_comp` | `fetch_data.py` | `data/market_data_comp.csv` | ~390 comp-pipeline instruments, daily snapshot |
| `market_data_comp_hist` | `fetch_hist.py` | `data/market_data_comp_hist.csv` | Weekly comp prices from 1950 |
| `macro_economic` | `fetch_macro_economic.py` | `data/macro_economic.csv` | Unified raw-macro snapshot (long-form) — every series from FRED + OECD + WB + IMF + DB.nomics + ifo, one row per series with metadata |
| `macro_economic_hist` | `fetch_macro_economic.py` | `data/macro_economic_hist.csv` | Wide-form weekly Friday-spine history from 1947, with **14 metadata rows** above the data: Column ID, Series ID, Source, Indicator, Country, Country Name, Region, Category, Subcategory, Concept, cycle_timing, Units, Frequency, Last Updated |
| `macro_market` | `compute_macro_market.py` | `data/macro_market.csv` | 108-indicator snapshot (id, group, sub_group, concept, subcategory, category, last_date, raw, zscore, zscore_1w_ago, zscore_4w_ago, zscore_13w_ago, zscore_peak_abs_13w, zscore_trend, regime, fwd_regime, formula_note). `concept` + `subcategory` added 2026-04-28 (§2.4) — drives the explorer's By-Concept sidebar view. |
| `macro_market_hist` | `compute_macro_market.py` | `data/macro_market_hist.csv` | Weekly indicator history from 2000 |

### Legacy Tabs (Auto-Deleted)

`SHEETS_LEGACY_TABS_TO_DELETE` (in `library_utils.py`) is swept on every run by `fetch_data.py`. Currently 12 tab titles:

| Tab | Reason |
|---|---|
| `Market Data` (with space) | Duplicate created by Apps Script; replaced by `market_data` |
| `sentiment_data` | Retired simple-pipeline output (also still in `SHEETS_PROTECTED_TABS` so it is never overwritten by a writer) |
| `macro_surveys`, `macro_surveys_hist` | Retired pre-Phase ME survey tabs |
| `market_data_hist` | Simple-pipeline history removed; superseded by `market_data_comp_hist` |
| `macro_us`, `macro_us_hist` | Retired Phase A tabs — consolidated into `macro_economic[_hist]` (Stage 2, 2026-04-23) |
| `macro_intl`, `macro_intl_hist` | Retired Phase C tabs — consolidated into `macro_economic[_hist]` |
| `macro_dbnomics`, `macro_dbnomics_hist` | Retired Phase D Tier 2 tabs — consolidated into `macro_economic[_hist]` |
| `macro_ifo`, `macro_ifo_hist` | Retired Phase D ifo tabs — consolidated into `macro_economic[_hist]` |

### Downstream Consumer

`trigger.py` reads only `market_data` via CSV export URL:
```
https://docs.google.com/spreadsheets/d/12nKIUGHz5euDbNQPDTVECsJBNwrceRF1ymsQrIe4_ac/export?format=csv&gid=68683176
```

---

## 7. CSV File Inventory

### Configuration Libraries (input — read by Python, never overwritten)

These are the "Data-Layer Registry" — every fetched identifier in the pipeline lives here, never in Python. Adding / removing / renaming a series = edit one of these CSVs (see `forward_plan.md` §0).

| File | Rows | Consumed By | Purpose |
|---|---|---|---|
| `index_library.csv` | ~401 | fetch_data.py, fetch_hist.py, compute_macro_market.py | Master instrument registry — tickers, metadata, data source assignments, `simple_dash` flag. 22 dead yfinance tickers retired across 4 batches in §3.1 sub-track 4 (2026-04-28); see `data/removed_tickers.csv` for the per-ticker disposition. **Stage F (2026-05-01) added 14 instruments:** 5 fixed-income (IEAC.L Euro IG corp, CBON CN govt bond, IUKD.L UK Dividend, VGOV.L UK Gilt, IBGM.L Eur Govt 7-10yr) + 9 equity (EWZ/EWW/INDA/EZA/TUR/EIS/MCHI/FXI/DXJ — EM regional + Japan hedged). |
| `level_change_tickers.csv` | 14 | fetch_data.py | Vol/level tickers that report absolute point change, not % return |
| `macro_library_countries.csv` | 14 | sources/countries.py, docs/build_html.py | 14 country codes (USA, GBR, DEU, FRA, ITA, JPN, CHN, AUS, CAN, CHE, EA19, IND, NLD, GLOBAL) + canonical / WB / IMF code mappings. NLD added 2026-06-10 to bring the regime-AA §3.12 priority-10 yields/equities row complete. Also drives the explorer's "Economic Data" By-Country sidebar grouping + country-filter dropdown (§2.5 v2). |
| `macro_library_fred.csv` | ~122 | sources/fred.py | FRED series IDs (US + international, including 6 supplementals from the 2026-04-26 refactor). 2026-04-27: `BAMLEC0A0RMEY` removed. 2026-04-29: `RSFSXMV` + `CHNPIEATI01GYM` (CHN_PPI) added; bogus `CHNPPIALLMINMEI` corrected to `CHNPIEATI01GYM`; 3 OECD-mirror confidence rows removed. **2026-06-10 §3.12 OECD MEI batch (+17):** 7 long-rate yields `IRLTLT01<ISO>M156N` for USA/FRA/JPN/CAN/AUS/NLD/CHE + 10 share-price reference indices `SPASTT01<ISO>M661N` for the priority-10. **2026-06-10 §3.9.1 commodity batch (+14):** IMF PCPS rows — copper, aluminum, WTI, Brent, nat gas, wheat, corn, soybeans, coffee, sugar, cotton, beef, pork, plus the aggregate `PALLFNFINDEXM`. **2026-06-15 regime-AA bucket A (+9):** new rows for regime-AA coverage gaps identified in the source-tier audit. |
| `macro_library_oecd.csv` | 3 | sources/oecd.py | OECD SDMX dataflow + dimension keys (CLI, unemployment, 3-month rate) |
| `macro_library_worldbank.csv` | 1 | sources/worldbank.py | World Bank WDI indicator codes (CPI YoY) |
| `macro_library_imf.csv` | 1 | sources/imf.py | IMF DataMapper indicator codes (real GDP growth) |
| `macro_library_dbnomics.csv` | 17 | sources/dbnomics.py | DB.nomics series paths. **Stage B (2026-04-30) added 4 T1 fallback rows** for the 9 forcing-function FRED rows: `IMF/IFS/M.JP.FPOLM_PA` (JPN_POLICY_RATE), `IMF/IFS/M.CN.FPOLM_PA` (CHN_POLICY_RATE), `Eurostat/prc_hicp_manr/M.RCH_A.CP00.EA20` (EA_HICP), `Eurostat/teiis080/M.PRD.B-D.I21_SCA.DE` (DEU_IND_PROD). Existing 9: 3 Eurostat surveys, 3 ISM PMIs, 3 Eurostat real-economy. **2026-06-10 §3.1.3 follow-up (+2):** `Eurostat/prc_hicp_manr/M.RCH_A.TOT_X_NRG_FOOD.EA20` (EA_HICP_CORE_YOY) + `OECD/DSD_PRICES_COICOP2018@DF_PRICES_C2018_N_TXCP01_NRG/JPN.M.N.CPI.PA._TXCP01_NRG.N.GY` (JPN_CORE_CPI_YOY) — feed the blended `EU_INFL1` / `JP_INFL1` calculators. **2026-06-15 Bucket C (+2):** `ISM/inventories/in` (ISM_MFG_INVENTORIES) + `ISM/prices/in` (ISM_MFG_PRICES) — enable the `US_ISM2` New Orders minus Inventories spread indicator. |
| `macro_library_ifo.csv` | 26 | sources/ifo.py | ifo workbook sheet/column locations for the 26 German business-survey series |
| `macro_library_boe.csv` | 7 | sources/boe.py | **NEW 2026-04-30 (Stage D + Stage F follow-on).** BoE IADB series codes for UK rates: `IUDBEDR` Bank Rate, `IUDSOIA` SONIA, `IUDSNPY` / `IUDMNPY` / `IUDLNPY` gilt par yield S/M/L, `IUDMNZC` / `IUDLNZC` zero-coupon M/L. |
| `macro_library_ecb.csv` | 5 | sources/ecb.py | **NEW 2026-04-30 (Stage D + Stage F follow-on); +2 2026-06-15.** ECB Data Portal direct (registry path, distinct from the inline YC call in `compute_macro_market.py`): `FM/D.U2.EUR.4F.KR.DFR.LEV` (EA_DEPOSIT_RATE), `YC/...SR_2Y` (EZ_GOVT_2Y), `YC/...SR_30Y` (EZ_GOVT_30Y). **2026-06-15 (+2 Bucket C):** `CISS/D.U2.Z0Z.4F.EC.SS_CIN.IDX` (EZ_CISS — ECB Composite Indicator of Systemic Stress, daily 0–1 index), `CES/M.Z18.ALL.T.C1120.NUM_VAR.WM` (EZ_INFL_EXP_12M — ECB CES 12M-ahead inflation expectations, monthly weighted median). |
| `macro_library_boj.csv` | 9 | sources/boj.py | **NEW 2026-04-30 (Stage D); +2 2026-06-10; +5 2026-06-11.** BoJ Time-Series codes (search-screen format with `<DB>'<code>` apostrophe separator): `FM01'STRDCLUCON` (JPN_POLICY_RATE T2 backup), `CO'TK99F1000601GCQ01000` (JP_TANKAN1 — Tankan Large Mfg Business Conditions DI), `PR01'PRCG20_2200000000` (JPN_PPI), `PR02'PRCS20_5200000000` (JPN_SPPI). **2026-06-11 (+5 Tankan sub-DIs):** Large Mfg Forecast DI (JP_TANKAN_LMFG_FCST), Large Non-Mfg DI (JP_TANKAN_LNFG), Large Non-Mfg Forecast DI (JP_TANKAN_LNFG_FCST), Small Mfg DI (JP_TANKAN_SMFG), Small Non-Mfg DI (JP_TANKAN_SNFG) — feed the JP_TANKAN_SPREAD1 / JP_TANKAN_SVC1 / JP_TANKAN_FWD1 Phase E indicators. |
| `macro_library_estat.csv` | 5 | sources/estat.py | **NEW 2026-04-30 (Stage D); +5 2026-06-10; revised 2026-06-11.** e-Stat statsDataIds. Verified live: `0003446463` (JPN_IND_PROD — METI IIP). PROVISIONAL (high-confidence IDs, not yet credentialed-verified): `0003355224` (JPN_MACH_ORDERS — Cabinet Office Machinery Orders, replaces original 0003193087 which returned "does not exist"), `0003138782` (JPN_RETAIL_SALES — METI Current Survey of Commerce, replaces 0003285601; next run verifies if this is the live monthly or the 2013 archive), `0003000807` (JPN_HH_EXP — MIC Family Income and Expenditure, replaces 0002070010), `0003348423` (JPN_EWS_DI — Economy Watchers Survey national current-DI, replaces 0003065691; national table, NOT the regional 0003348424). **2026-06-11 drop:** `JPN_TERT_IND` (METI Tertiary Industry Activity) removed — no `getStatsData` table exists; METI publishes only via Excel file download. Re-add when a file-download fetcher or `sources/meti_jp.py` module exists. |
| `macro_library_lbma.csv` | 1 | sources/lbma.py | **NEW 2026-05-09 (§3.9).** LBMA precious-metal fix series. Schema includes `sub_field` (USD/GBP/EUR) for currency selection from the JSON `v` array. Row: `gold_pm` → `GOLD_USD_PM` (LBMA Gold PM Fix, USD/oz, daily 1968-04-05 → present). Extension targets in §3.9.1: `silver`, `platinum_pm`, `palladium_pm`. |
| `macro_library_nasdaqdl.csv` | 0 | sources/nasdaq_data_link.py | Header-only — NDL scaffolding kept after LBMA/GOLD went paid-tier in May 2026. Available for any future free NDL dataset. |
| `macro_library_boc.csv` | 5 | sources/boc.py | **NEW 2026-05-28.** Bank of Canada Valet series: CAN policy rate (V39079), GoC 2Y/10Y benchmark yields, BoC CPI-median core inflation, USD/CAD reference rate. Keyless. |
| `macro_library_statcan.csv` | 4 | sources/statcan.py | **NEW 2026-05-28.** Statistics Canada WDS vector IDs: CAN CPI (all-items), unemployment rate, + 2 more. Keyless POST API. |
| `macro_library_ons.csv` | 11 | sources/ons.py | **NEW 2026-05-28; +4 2026-06-10; +1 2026-06-11.** ONS CDID taxonomy paths via Zebedee /data API. Existing 6: GBR CPI annual rate (D7G7), CPIH (L55O), real GDP (ABMI), unemployment rate (MGSX), employment rate (LF24), AWE regular pay growth (KAI9). **2026-06-10 §3.1.3 follow-up + Stage C close-out:** core CPI (DKO8 → GBR_CORE_CPI_YOY — blended into UK_INFL1), Index of Production B-E SA (K222 → GBR_IND_PROD), Index of Services (S2KU → GBR_SERV_PROD), Retail Sales Index volume (J5EK → GBR_RETAIL_VOL). All 4 verified live 2026-06-10. **2026-06-11 §3.1.4:** monthly real GDP index (ECY2 dataset MGDP → GBR_GDP_MONTHLY — feeds UK_NOWCAST1 Phase E indicator; 351 monthly obs back to 1997-01, freshness_override 75d). Keyless. |
| `macro_library_bundesbank.csv` | 4 | sources/bundesbank.py | **NEW 2026-05-28.** Bundesbank SDMX-ML BBSIS dimension keys: DEU Bund 10Y daily yield (ultimate source vs FRED monthly mirror), DEU Bund 1-2Y (genuine gap — no aggregator equivalent), + 2 more. Keyless. |
| `macro_library_abs.csv` | 5 | sources/abs.py | **NEW 2026-05-28.** ABS SDMX-CSV keys: AUS CPI (all-groups), real GDP, GDP growth (QoQ), unemployment rate (15+ SA), participation rate (15+ SA). Keyless. |
| `macro_library_istat.csv` | 3 | sources/istat.py | **NEW 2026-05-28.** ISTAT SDMX keys: ITA monthly unemployment rate 15-74 (dataflow 151_874), industrial production total ex-construction base 2021 (dataflow 115_333). Vintage (EDITION) slot left empty — module resolves latest at fetch time. Keyless. |
| `macro_library_bls.csv` | 4 | sources/bls.py | **NEW 2026-05-28/29.** BLS Public Data API series IDs: `USA_CPI_INDEX` (CUSR0000SA0), `USA_CORE_CPI_INDEX` (CUSR0000SA0L1E), `USA_UNEMPLOYMENT` (LNS14000000), `USA_AVG_HOURLY_EARN` (CES0500000003 — genuine coverage gap, no FRED-library equivalent). BLS is the ultimate source; FRED is the automatic fallback for the first three. BLS_API_KEY optional. |
| `macro_library_insee.csv` | 3 | sources/insee.py | **NEW 2026-06-09.** INSEE BDM idbanks (SERIES_BDM/ prefix): `FRA_BUS_CONF` (001565530 — Business Climate), `FRA_UNEMPLOYMENT` (001688527 — ILO unemployment rate Quarterly), `FRA_GDP_INDEX` (011794860 — GDP chained volume SA-WDA). INSEE is the ultimate source; supersedes OECD/Eurostat. Keyless (optional INSEE_API_KEY). |
| `macro_library_bdf.csv` | 2 | sources/bdf.py | **NEW 2026-06-09; rewritten 2026-06-10 for Opendatasoft Explore v2.1. PROVISIONAL.** Banque de France Webstat keys in `<dataset_id>|<odsql_where>` form: `FRA_LOAN_RATE_HOUSE`, `FRA_LOAN_RATE_NFC` (MFI lending rates). Both rows still PROVISIONAL — dataset_id + ODSQL filter to be discovered on the first credentialed run (the public catalogue exposes only an archived-reports dataset). The legacy SDMX dot-keys are preserved in-line as `PROVISIONAL|legacy_sdmx_key=...` to feed the next-session lookup. |
| `macro_library_alpha_vantage.csv` | 0 | sources/alpha_vantage.py | **NEW 2026-06-10 (§3.3 scaffolding).** Header-only. Alpha Vantage OVERVIEW endpoint serves snapshot PE / forward PE / PEG / dividend yield / EPS / book value via `?function=OVERVIEW&symbol=<SYM>`. Free-tier cap (25 req/day) is too thin for a daily comp fan-out; population deferred per `manuals/alpha_vantage_evaluation.md`. The schema header is in place so the day the storage shape lands, only CSV rows need to be added. |
| `macro_library_shiller.csv` | 6 | sources/shiller.py | **NEW 2026-06-10 (§3.13).** Yale `ie_data.xls` column headers: `CAPE` → USA_CAPE, `S&P Comp. P` → USA_SP500_SHILLER, `Dividend D` → USA_SP500_DIV_SHILLER, `Earnings E` → USA_SP500_EPS_SHILLER, `CPI` → USA_CPI_SHILLER, `Long Interest Rate GS10` → USA_TREAS_10Y_SHILLER. Monthly from 1871. Distinct from the modern BLS/FRED canonicals — confirmatory pre-1950 cross-validation anchor for regime-AA Phase 0c. |
| `macro_library_french.csv` | 6 | sources/french.py | **NEW 2026-06-10 (§3.13).** Ken French Data Library `<zip_stem>|<column>` keys against `F-F_Research_Data_5_Factors_2x3_CSV.zip`: Mkt-RF / SMB / HML / RMW / CMA + 1-month T-bill RF. US 5-factor monthly returns from 1926-07 (RMW + CMA from 1963-07). Mapped to columns USA_FF_MKT_RF / USA_FF_SMB / USA_FF_HML / USA_FF_RMW / USA_FF_CMA / USA_FF_RF. International (Developed_5_Factors) + emerging (Emerging_5_Factors) extensions deferred. |
| `macro_library_jst.csv` | 39 | sources/jst.py | **NEW 2026-06-10 (§3.13); −1 2026-06-11.** JST Macrohistory R6 `<iso>|<column>` keys: 10 priority economies (USA, GBR, DEU, FRA, ITA, JPN, NLD, CAN, AUS, CHE) × 4 columns (`cpi` / `gdp` / `eq_tr` / `ltrate`). Annual cadence, 1870+ depth. **2026-06-11:** CAN_EQUITY_TR_JST row dropped (JST R6 does not carry a Canadian equity total-return series). Column names like USA_CPI_JST / GBR_GDP_JST deliberately don't shadow modern canonicals — confirmatory pre-1950 cross-validation anchor for regime-AA Phase 0c. |
| `macro_library_atlanta_fed.csv` | 1 | sources/atlanta_fed.py | **NEW 2026-06-11 (§3.1.4).** Atlanta Fed GDPNow series. Single row: `gdpnow_us_qoq_saar` → `US_GDPNOW` (Atlanta Fed GDPNow — US Real GDP Growth Q/Q SAAR, daily, 2014+; freshness_override 14d). Keyless — no API key required. |
| `macro_library_ny_fed.csv` | 1 | sources/ny_fed.py | **NEW 2026-06-12 (§3.1.4).** NY Fed Staff Nowcast series. Single row: `ny_fed_nowcast_us_qoq_saar` → `US_NYFED_NOWCAST` (New York Fed Staff Nowcast — US Real GDP Growth Q/Q SAAR, weekly, 2002+; freshness_override 14d). Keyless — no API key required. |
| `macro_library_sec_edgar.csv` | 68 | fetch_data.py (SEC EDGAR isolated phase) | **NEW 2026-06-15.** SEC EDGAR equity-fundamentals registry. 68 rows = 34 US-filer pure-plays × 2 metrics (revenue + diluted EPS). Schema: `ticker, cik, metric, gaap_tags, col, name, sort_key`. Not wired into the unified Phase ME pipeline — consumed only by the isolated `sec_edgar` phase in `fetch_data.py`; output written to `data/equity_fundamentals.csv`. Keyless (fair-access UA required). |
| `manual_splits.csv` | 1 | library_utils.apply_manual_splits + scripts/backadjust_hist_splits.py | **NEW 2026-05-27 (§3.6a Pattern 11).** Stock-split overrides for Yahoo's missing corporate-actions feed. Schema: `ticker, ex_date, ratio, notes`. Current row: `1306.T 2026-03-30 10` (NEXT FUNDS TOPIX ETF 10:1 split — ex-rights = record date 2026-03-31 minus 1 business day under Japan's T+2). |
| `source_fallbacks.csv` | 10 | (documentation only — runtime walker not yet built) | **NEW 2026-04-30 (Stage B); GOLD_USD_PM row added §3.9 2026-05-08.** Canonical record of the §3.1.2 architectural fallback chain per indicator. Columns: `indicator_id, t0_source, t0_id, t1_source, t1_id, t2_source, t2_id, t3_source, t3_id, t1_status, t1_latest, notes`. v1 is a documentation artefact + future hook for explicit chain-walking logic; today the fallback effect is achieved implicitly via `_collect_all_indicators` ordering (later sources overwrite earlier sources at the column level). |
| `macro_indicator_library.csv` | 108 | compute_macro_market.py, docs/build_html.py | Phase E composite-indicator registry (id, category, group, sub_group, **concept**, **subcategory**, naturally_leading, formula, interpretation, regime_classification, cycle_timing). `concept` + `subcategory` added 2026-04-28 (§2.4); 16 indicators added since original 92: **`GLOBAL_GOLD1`** (§3.9 LBMA gold), **`US_INFL1`/`UK_INFL1`/`EU_INFL1`/`JP_INFL1`/`CN_INFL1`** (§3.1.3 per-region inflation regimes), **`US_INFEXP1`** (z-composite inflation expectations). **2026-06-11 (+6):** `EU_NOWCAST1`, `US_GDPNOW1`, `UK_NOWCAST1`, `JP_TANKAN_SPREAD1`, `JP_TANKAN_SVC1`, `JP_TANKAN_FWD1`. **2026-06-12 (+2):** `US_NOWCAST1` (NY Fed Staff Nowcast passthrough → `US_NYFED_NOWCAST`), `JP_NOWCAST1` (equal-weight z of `JPN_IND_PROD` + `JP_TANKAN1` + `JPN_RETAIL_SALES` + `JPN_MACH_ORDERS`). **2026-06-15 (+1):** `US_ISM2` (ISM New Orders minus Inventories spread — leads headline PMI by 2-3 months). Canonical 17-concept taxonomy: Equity, Rates / Yields, Credit / Spreads, Inflation, Sentiment / Survey, Leading Indicators, Growth, Labour, Consumer, Housing, Manufacturing, External / Trade, Money / Liquidity, Cross-Asset, FX, Volatility, Momentum. |
| `reference_indicators.csv` | 206 | Reference only (gap audit) | Cross-reference of 206 macro/market indicators from `Macro Market Indicators Reference.docx` with L/C/G cycle timing, match status, and source flags. Not consumed by the runtime pipeline — used to drive `forward_plan.md` §3.1 coverage analysis. Detail mirror at `manuals/macro_market_indicators_coverage.xlsx`. |
| `freshness_thresholds.csv` | 5 | `data_audit.py` | Per-frequency staleness tolerance (Daily 5d / Weekly 10d / Monthly 45d / Quarterly 120d / Annual 540d) used by §2.6's daily integrated audit. Per-row override available via the `freshness_override_days` column on every `macro_library_*.csv` (added 2026-04-28). 48 rows widened in the §3.1 sub-track 2 bulk pass (2026-04-29). |
| `removed_tickers.csv` | grows | Maintained by hand + `audit_writeback.py` | Single-source ledger of every library change — removals (`action=removed`), reroutes (`action=rerouted`), additions (`action=added`). Schema: `date_removed, action, ticker, ticker_field, library_name, source_csv, reason, audit_run_date, replacement_status, target_identifier, notes`. Schema extended 2026-04-29 (`action` + `target_identifier` columns). |
| `yfinance_failure_streaks.csv` | grows | `audit_writeback.py` | Per-ticker dead-list streak counter (forward_plan §3.1 sub-track 3). Schema: `ticker, first_seen_dead, last_seen_dead, consecutive_fail_days`. Tickers drop out when streak breaks; streaks ≥ 14 trigger `validation_status=UNAVAILABLE`. |

### Pipeline Outputs (generated daily by Python, committed to git)

| File | Rows | Written By | Content |
|---|---|---|---|
| `market_data.csv` | ~70 | fetch_data.py | Simple-pipeline daily snapshot |
| `market_data_comp.csv` | ~360 | fetch_data.py | Comp-pipeline daily snapshot |
| `market_data_comp_hist.csv` | ~3,990 | fetch_hist.py | Weekly prices, 10 metadata prefix rows + data |
| `macro_economic.csv` | ~170 | fetch_macro_economic.py | Unified raw-macro snapshot (long-form) — one row per series with metadata |
| `macro_economic_hist.csv` | ~4,150 | fetch_macro_economic.py | Wide-form weekly Friday-spine history from 1947, **14 metadata prefix rows + data** |
| `macro_market.csv` | ~108 | compute_macro_market.py | Macro-market indicator snapshot |
| `macro_market_hist.csv` | ~1,370 | compute_macro_market.py | Weekly indicator history |
| `macro_market_monthly_hist.csv` | ~320 | compute_macro_market.py | **NEW 2026-06-10 (forward_plan §3.14).** Month-end-sampled view of `macro_market_hist.csv`. Same wide schema (`<id>_raw` / `_zscore` / `_regime` / `_fwd_regime` per indicator), one row per month-end, each cell = the latest weekly Friday observation within that month. Produced via `df_hist.resample("ME").last()` after the weekly write — sampling only, the underlying 156-week z-score window is unchanged. Sister-file `_x.csv` follows the standard preservation contract. Stable schema for regime-AA Phase 3 Layer-1 monthly engine consumption. |
| `equity_fundamentals.csv` | grows w/ history | fetch_data.py (SEC EDGAR phase) | **NEW 2026-06-15.** Long/tidy SEC EDGAR revenue + diluted-EPS history for the 34 US-filer pilot pure-plays. One row per (ticker, metric, fiscal period): `ticker, metric (revenue\|eps), period_end, period_type (Q\|A), value, unit, fy, fp, form, source="SEC EDGAR", retrieved`. Idempotent-merge keyed on `(ticker, metric, period_end, period_type)` — unchanged periods keep their `retrieved`, restated/new periods take the fresh value, old periods preserved on a transient miss. Isolated phase; keyless (SEC fair-access UA + ≤10 req/s). |
| `pipeline.log` | n/a | GitHub Actions | Captured stdout+stderr of the most recent run (committed by the `if: always()` step in `update_data.yml` — useful for diagnosing failures without needing to download artefacts) |
| `data_audit.txt` | n/a | `data_audit.py` (CI) | Full sorted §2.6 v2 audit report (fetch outcomes + static checks + value-change staleness + registry drift). Regenerated each daily run. |
| `audit_comment.md` | n/a | `data_audit.py` + `audit_writeback.py` (CI) | Markdown body posted to the perpetual `daily-audit` GitHub Issue. First line is the one-sentence ALL CLEAN / N ISSUES summary. `audit_writeback.py` appends a one-line note when streaks are active or rows are flipped to UNAVAILABLE. |
| `data/_archived_columns/*.csv` | per-orphan | `library_sync.py --confirm` | Per-orphan-column historical archives. Filename: `<hist_basename>__<column_id>__<YYYY-MM-DD>.csv`. Created when a row is removed from a library CSV and the operator runs `library_sync.py --confirm` to prune the now-orphan hist column. Preserves full historical observations for future reference. |
| `*_hist_x.csv` (sister files) | per-`_hist.csv` | `library_utils.write_hist_with_archive()` | **NEW 2026-04-30 (Stage A).** "Extended" sister to every `*_hist.csv` writer-output. Captures rows that would otherwise be lost when source-side history truncates retroactively (e.g. ICE BofA on FRED becoming a rolling 3-yr window from April 2026). Append-only; never shrinks. Read paths transparently union `*_hist.csv` ∪ `*_hist_x.csv` via `load_hist_with_archive()`. See §11 Pattern 9. |

---

## 8. `index_library.csv` — Schema & Source of Truth

The library has ~390 rows and 29 columns. It is the **single source of truth** for both pipelines — all instruments, metadata, and data source assignments live here.

### Column Schema

| Column | Type | Description |
|---|---|---|
| `name` | string | Human-readable instrument name |
| `asset_class` | enum | Equity, Fixed Income, Rates, Spread, FX, Commodity, Crypto, Volatility |
| `broad_asset_class` | string | Display grouping for Sheets output (Equity, Bonds, Commodities, FX, etc.) |
| `units` | string | Display units (Index, Price, % pa, bps, Ratio, etc.) |
| `asset_subclass` | string | e.g. "Equity Broad", "Govt Bond", "Corp HY", "Credit Spread" |
| `region` | string | Global, North America, Europe, Japan, Asia Pacific, EM, etc. |
| `country_market` | string | Specific country (e.g. "United States", "Japan") |
| `sector_style` | string | Sector or style tag (e.g. "Energy", "Growth", "Blend") |
| `market_cap_focus` | string | Large, Mid, Small, Broad |
| `maturity_focus` | string | Short (1-3yr), Long (10yr+), Broad |
| `credit_quality` | string | Investment Grade, High Yield |
| `commodity_group` | string | Energy, Precious Metals, Agriculture, etc. |
| `base_currency` | string | ISO currency code (USD, GBP, EUR, JPY, ...) |
| `hedged` | bool | True if currency-hedged variant |
| `hedge_currency` | string | Target hedge currency |
| `proxy_flag` | bool | True if this is a proxy for an unavailable primary |
| `proxy_type` | string | ETF, Total Return, etc. |
| `data_source` | enum | `yfinance PR`, `yfinance TR`, `FRED` |
| `validation_status` | enum | `CONFIRMED`, `PENDING`, `UNAVAILABLE` |
| `ticker_yfinance_pr` | string | yfinance price return ticker (index) |
| `ticker_yfinance_tr` | string | yfinance total return ticker (ETF proxy) |
| `ticker_investiny` | string | Reserved — not currently used |
| `ticker_fred_tr` | string | FRED total return index series ID |
| `ticker_fred_yield` | string | FRED yield series ID |
| `ticker_fred_oas` | string | FRED OAS spread series ID |
| `ticker_fred_spread` | string | FRED spread series ID |
| `ticker_fred_duration` | string | FRED duration series ID |
| `data_start` | date | Earliest reliable data date for this instrument |
| `simple_dash` | bool | True = included in the simple pipeline (~70 instruments) |

### How the Pipelines Use the Library

1. **Simple pipeline:** `load_simple_library()` reads the CSV and filters to `simple_dash == True` AND `validation_status == "CONFIRMED"`
2. **Comp pipeline:** `load_instrument_library()` reads the CSV and filters to `validation_status == "CONFIRMED"` (all confirmed rows)
3. Rows with `data_source` starting with `yfinance` are fetched via `collect_comp_assets()`
4. Rows with FRED ticker columns populated are fetched via `collect_comp_fred_assets()` / `collect_comp_fred_rates()`
5. Sort order follows `lib_sort_key()` from `library_utils.py`

### Adding a New Instrument

1. Add a row to `index_library.csv` with `validation_status = "CONFIRMED"`
2. Set `data_source` to `yfinance PR` or `yfinance TR`
3. Verify the ticker works: `python -c "import yfinance as yf; t = yf.Ticker('TICKER'); print(t.history(period='5d'))"`
4. Set `base_currency` — needed for FX conversion to USD
5. Set `broad_asset_class` and `units` — used for display in Sheets
6. Optionally set `simple_dash = True` to include in the simple dashboard

### Library Maintenance

`index_library.csv` is itself built by a separate Claude project at `C:\Users\kasim\OneDrive\Claude\Index Library\build_library.ipynb`. Any changes to instrument metadata should be made in the CSV, not hardcoded in Python.

---

## 9. Module Reference

### 9.1 `library_utils.py` (627 lines)

**Role:** Shared constants and helpers — single authoritative source for sort logic, FX maps, and the Sheets tab-state frozensets used by every writer.

| Export | Type | Purpose |
|---|---|---|
| `ASSET_CLASS_GROUP` | dict | Maps asset classes to sort order (1-7) |
| `REGION_ORDER` | dict | Maps regions to sort order (1-9) |
| `EQUITY_SUBCLASS_ORDER` | dict | Sort order for equity subcategories |
| `SECTOR_ORDER` | dict | Custom sector sort order (Consumer Staples first, Real Estate last) |
| `FI_SUBCLASS_ORDER` | dict | Sort order for fixed income subcategories |
| `MATURITY_ORDER` | dict | Sort order for bond maturities |
| `COMMODITY_GROUP_ORDER` | dict | Sort order for commodity groups |
| `VOL_SUBCLASS_ORDER` | dict | Sort order for volatility subcategories |
| `RATES_SUBCLASS_ORDER` | dict | Sort order for rates subcategories |
| `SPREAD_SUBCLASS_ORDER` | dict | Sort order for spread subcategories |
| `INDICATOR_GROUP_ORDER` | dict | Sort order for macro-market indicator groups (US, UK, Europe, …) |
| `INDICATOR_SUB_GROUP_ORDER` | dict | Sort order for macro-market indicator sub-groups |
| `INDICATOR_CONCEPT_ORDER` | dict | Sort order for the 17-concept canonical taxonomy used by the §2.5 By-Concept sidebar view (Equity, Rates / Yields, Credit / Spreads, …). Mirrored by `CONCEPT_ORDER` in `docs/build_html.py`'s embedded JS. |
| `COMP_FX_TICKERS` | dict | Currency code → yfinance ticker (18 currencies) |
| `COMP_FCY_PER_USD` | set | Indirect-quote currencies (JPY, CNY, INR, etc.) — divide by FX rate |
| `lib_sort_key(row)` | function | Returns sort tuple from instrument dict for consistent ordering; Industry Groups/Industries sorted by GICS ticker code |
| `SHEETS_PROTECTED_TABS` | frozenset | Tabs that no writer is allowed to overwrite (`market_data`, `sentiment_data`). All four writer modules check this before writing. |
| `SHEETS_ACTIVE_TABS` | frozenset | The 7 tabs the pipeline actively writes today (`market_data`, `market_data_comp`, `market_data_comp_hist`, `macro_economic`, `macro_economic_hist`, `macro_market`, `macro_market_hist`). |
| `SHEETS_LEGACY_TABS_TO_DELETE` | frozenset | The 12 retired tab titles swept on every run (4 pre-Stage-2 simple-pipeline tabs + 8 Stage-2-retired macro tabs). |
| `write_hist_with_archive(df, path, prefix_rows=None, date_col="Date")` | function | **NEW 2026-04-30 (Stage A).** History-preservation writer. Per-column floor-advancement detection: for each column where the new fetch's earliest non-null date is later than the locally-stored earliest non-null date, the rows about to disappear are appended to `<path>_x.csv` (sister, deduped by date) before the live file is rewritten with the new (truncated) window. Used by every `*_hist.csv` writer (`fetch_data.py`, `fetch_hist.py`, `fetch_macro_economic.py`, `compute_macro_market.py`). See §11 Pattern 9. |
| `load_hist_with_archive(path, **read_csv_kwargs)` | function | **NEW 2026-04-30 (Stage A).** History-preservation reader. Drop-in replacement for `pd.read_csv(path, ...)` that transparently unions live + sister via `combine_first` semantics — live wins on cells where it has a non-null value, sister fills cells where live is NaN. Used by `compute_macro_market.py` Phase E calculators and `docs/build_html.py` payload builders. |

### 9.2 `fetch_data.py` (998 lines)

**Role:** Master orchestrator + both snapshot pipelines (simple + comp). After `main()` finishes, three module-level `try/except` blocks chain in `fetch_hist.run_comp_hist`, `fetch_macro_economic.run_phase_macro_economic`, and `compute_macro_market.run_phase_e` (see §3 Execution Flow).

#### Key Functions

| Function | Purpose |
|---|---|
| `get_ytd_start()` | Compute the YTD start date used by `calc_return` |
| `calc_return(series, period_key, is_yield, is_level)` | Compute 1W/1M/3M/6M/YTD/1Y returns or absolute point changes |
| `fetch_yf_history(ticker, retries)` | Single yfinance ticker fetch with retry |
| `fetch_fred_series(series_id, retries)` | Single FRED series fetch with retry |
| `usd_adjusted_return(local_return_pct, ccy, period_key, fx_cache, fcy_per_usd)` | Adjust a local-currency return for FX move over the same window |
| `build_comp_fx_cache()` | Pre-fetch FX rate histories for all 18 `COMP_FX_TICKERS` |
| `load_simple_library()` | Read library, filter to `simple_dash=True` + `CONFIRMED` |
| `load_instrument_library()` | Read library, filter to `CONFIRMED`, sort by `lib_sort_key` |
| `collect_comp_assets(instruments, fx_cache)` | Fetch yfinance prices, compute 1W/1M/3M/6M/YTD/1Y returns in local + USD |
| `collect_simple_fred_assets()` | Fetch FRED-sourced instruments for the simple pipeline |
| `collect_comp_fred_assets()` | Fetch FRED yields, spreads, OAS for the comp pipeline |
| `_build_library_df(yf_rows, fred_rows)` | Combine yfinance + FRED rows into output DataFrame |
| `push_to_google_sheets(df_main, df_comp)` | Write `market_data` + `market_data_comp`; sweep `SHEETS_LEGACY_TABS_TO_DELETE`; check `SHEETS_PROTECTED_TABS` before each write |
| `main()` | Entry point — runs simple + comp pipelines and the Sheets push |

#### Key Constants

| Constant | Source | Purpose |
|---|---|---|
| `LIBRARY_PATH` | Computed | Absolute path to `data/index_library.csv` |
| `COMP_LEVEL_CHANGE_TICKERS` | `data/level_change_tickers.csv` | Vol tickers using absolute point change (with hardcoded fallback) |
| `COMP_FX_TICKERS` | `library_utils.py` | 18 FX pairs for USD conversion |
| `COMP_FCY_PER_USD` | `library_utils.py` | Indirect-quote currency set |
| `SHEETS_LEGACY_TABS_TO_DELETE` | `library_utils.py` | Legacy tab titles swept on every run (the previous module-local `TABS_TO_DELETE` set was consolidated into `library_utils.py` during the Phase G audit) |

### 9.3 `fetch_hist.py` (781 lines)

**Role:** Comp-pipeline weekly history — `market_data_comp_hist` only. The macro history (`macro_economic_hist`) is now built by `fetch_macro_economic.py` (see §9.4); the `run_hist()` / `build_macro_hist_df` / `MACRO_HIST_START` plumbing that used to live here was retired with `fetch_macro_us_fred.py` in the Stage 2 unification.

#### Key Functions

| Function | Purpose |
|---|---|
| `get_friday_spine(start_str, end_date)` | Generate weekly Friday DatetimeIndex |
| `align_to_friday_spine(series, spine)` | Reindex + forward-fill to the Friday spine |
| `fred_fetch_series_full(series_id, start)` | Fetch complete FRED series with backoff (used for the comp pipeline's FRED rates) |
| `save_csv(df, path, label, …)` | Diff-checked CSV writer (skip if unchanged) |
| `push_df_to_sheets(df, tab_name, label, …)` | Sheets writer with `SHEETS_PROTECTED_TABS` guard |
| `load_comp_instruments()` | Load comp instruments from `data/index_library.csv` |
| `load_comp_fred_rates()` | Load FRED rate series for the comp pipeline |
| `fetch_comp_fx_cache(start)` | Pre-fetch FX histories for comp USD conversion |
| `compute_comp_usd_series(local, ccy, fx_cache, fcy_per_usd)` | Convert local prices to USD |
| `fetch_comp_yfinance_history(instruments, start, fx_cache)` | Fetch all yfinance histories |
| `fetch_comp_fred_rates_history(rates, start)` | Fetch all FRED rate histories |
| `build_comp_market_hist_df(yf_data, fred_data, spine)` | Combine yfinance + FRED histories and align to the Friday spine |
| `build_comp_market_meta_prefix(df, instruments, rates)` | Build the 10 metadata prefix rows above the data |
| `run_comp_hist()` | **Entry point** — build + push `market_data_comp_hist` |

#### Key Constants

| Constant | Value | Purpose |
|---|---|---|
| `COMP_HIST_START` | `"1950-01-01"` | Floor date for comp market history |
| `YFINANCE_DELAY` | 0.3s | Delay between yfinance calls |
| `FRED_DELAY` | 0.6s | Delay between FRED calls |

#### Historical Output Format

- **Rows** = dates (weekly Friday close)
- **Columns** = instruments (local currency first, then USD)
- **Metadata prefix rows** (in Sheets tabs, not in CSVs): ticker ID, variant, source, name, broad asset class, region, sub-category, currency, units, frequency — then column header row, then data

### 9.4 `fetch_macro_economic.py` (1,488 lines)

**Role:** Phase ME — unified raw-macro coordinator. Replaces the four retired per-source coordinators (Phase A `fetch_macro_us_fred.py`, Phase C `fetch_macro_international.py`, Phase D Tier 2 `fetch_macro_dbnomics.py`, Phase D ifo `fetch_macro_ifo.py`) and produces one snapshot tab (`macro_economic`) plus one history tab (`macro_economic_hist`).

The module loads every indicator definition from the per-source CSVs at import time via `load_all_indicators()`, then dispatches snapshot and history fetches to the matching `sources/*.py` module based on each indicator's `source` field. There is **no direct API contact in this module** — every HTTP/Excel call lives in `sources/`.

#### Key Functions

| Function | Purpose |
|---|---|
| `load_all_indicators()` | Read every `data/macro_library_*.csv` via the `sources/*.py` loaders, return a unified `list[dict]` of indicator definitions in the canonical schema (`source`, `source_id`, `col`, `name`, `country`, `category`, `subcategory`, `concept`, `cycle_timing`, `units`, `frequency`, `notes`, `sort_key`) |
| `summarize(indicators)` | Print a per-source / per-country breakdown for log diagnostics |
| `_make_row(...)` / `_blank_row(...)` | Construct a single long-form snapshot row with the unified metadata schema |
| `_fetch_fred_us_snapshot(indic, …)` / `_fetch_fred_intl_snapshot(...)` | FRED snapshot dispatchers (US-only and country-fan-out variants) |
| `_fan_out_snapshot(...)` / `_fan_out_history(...)` | Generic country-fan-out — call the source's fetcher once per country in the indicator's country list |
| `_fetch_oecd_snapshot(...)` / `_fetch_wb_snapshot(...)` / `_fetch_imf_snapshot(...)` / `_fetch_dbnomics_snapshot(...)` | One-line dispatchers to the corresponding `sources/*.py` |
| `_fetch_shiller_snapshot(...)` / `_fetch_french_snapshot(...)` / `_fetch_jst_snapshot(...)` | §3.13 long-run dispatchers — read `indic["source_id"]` (`<sheet>/<col>` for Shiller, `<zip_stem>|<col>` for French, `<iso>|<col>` for JST) and route to the per-source `fetch_series_as_pandas`. Process-cached at the source-module level. |
| `_fetch_ifo_snapshot_batch(...)` | Batch ifo fetch (one workbook download per run, then per-series column extraction) |
| `build_snapshot_df(indicators)` | Build the long-form `macro_economic` DataFrame (one row per series with full metadata) |
| `save_snapshot_csv(df)` | Write `data/macro_economic.csv` (diff-check skip) |
| `_obs_list_to_series(obs, col)` | Convert raw `(date, value)` observations into a named pandas Series |
| `_fetch_*_history(indic)` family | History fetchers per source — return `dict[col_name, pd.Series]` |
| `_get_ifo_monthly_df(...)` / `_fetch_ifo_history(...)` | Cached ifo workbook + per-series history extraction |
| `_history_for_indicator(...)` | Generic per-indicator history dispatch (handles fan-out vs single-country) |
| `build_hist_df(indicators)` | Build the wide-form `macro_economic_hist` DataFrame on the weekly Friday spine from 1947 |
| `_build_hist_metadata_rows(...)` | Construct the 14 metadata prefix rows above the data (Column ID / Series ID / Source / Indicator / Country / Country Name / Region / Category / Subcategory / Concept / cycle_timing / Units / Frequency / Last Updated) |
| `push_snapshot_to_sheets(df)` / `push_hist_to_sheets(df, indicators)` | Sheets writers — both check `library_utils.SHEETS_PROTECTED_TABS` before writing |
| `run_phase_macro_economic()` | **Entry point** — load every library, fetch snapshot + history for all sources, save CSVs, push to Sheets |

#### Read order

Inside `load_all_indicators()`: `countries → fred → oecd → worldbank → imf → dbnomics → ifo → boe → ecb → boj → estat → nasdaqdl → lbma → boc → statcan → ons → bundesbank → abs → istat → bls → insee → bdf → alpha_vantage → shiller → french → jst → atlanta_fed → ny_fed`. Each `sources/*.py` exposes `load_library() -> list[dict]` returning the unified indicator schema.

### 9.5 `sources/` package (30 modules — 2 scaffolding-only, ~8,416 lines total)

**Role:** Per-source data providers. Each submodule exposes a small, consistent interface (library loader + snapshot fetcher + history fetcher) with **no CSV or Sheets side effects** — those live in `fetch_macro_economic.py`. The 4 Stage-D modules (`boe.py`, `ecb.py`, `boj.py`, `estat.py`) were added 2026-04-30. The 2 §3.9 modules (`lbma.py`, `nasdaq_data_link.py`) were added 2026-05-08/09 — `lbma.py` is live (gold daily 1968+); `nasdaq_data_link.py` is intentionally retained as empty scaffolding after LBMA/GOLD went paid-tier on NDL (see §5 NDL entry). 7 keyless source adapters (`boc.py`, `statcan.py`, `ons.py`, `bundesbank.py`, `abs.py`, `istat.py`, and `bls.py`) were added 2026-05-28 for Canada, UK, Australia, Italy, and US primary-source overrides. 2 further French-source modules (`insee.py`, `bdf.py`) were added 2026-06-09 (`bdf.py` was rewritten for the Opendatasoft Explore v2.1 stack on 2026-06-10). 4 more modules landed 2026-06-10: `alpha_vantage.py` (§3.3 PE-ratio snapshot scaffold) and the §3.13 long-run trio `shiller.py` / `french.py` / `jst.py`. **2026-06-11:** `atlanta_fed.py` — Atlanta Fed GDPNow keyless Excel download (§3.1.4 GDP Now wiring; 366 lines; feeds `US_GDPNOW1` Phase E indicator); `ny_fed.py` — New York Fed Staff Nowcast keyless Excel download (§3.1.4; 348 lines; feeds `US_NOWCAST1` Phase E indicator). **2026-06-12:** `ifo.py` grows from ~390 → 579 lines (Bright Data Web Unlocker added as a 3rd-strategy fallback for persistent anti-bot challenges — see §5 ifo entry). `istat.py` grows from 280 → 287 lines (retry budget tightened: timeout 90→30s, retries 6→3). **2026-06-15:** `istat.py` grows further from 287 → 395 lines (per-series EDITION cache added — writes `data/istat_edition_cache.csv` on each run; wildcard-on-miss dataset discovery logic added to handle ISTAT API SDMX endpoint changes).

**Coordinator read order in `fetch_macro_economic.py::load_all_indicators()`**: `fred → oecd → worldbank → imf → dbnomics → ifo → boe → ecb → boj → estat → nasdaqdl → lbma → boc → statcan → ons → bundesbank → abs → istat → bls → insee → bdf → alpha_vantage → shiller → french → jst → atlanta_fed → ny_fed`. Each `sources/*.py` exposes `load_library() → list[dict]` returning the unified indicator schema. Last writer wins per `col` — this is the implicit fallback mechanism documented in `data/source_fallbacks.csv`.

#### 9.5.1 `sources/base.py` (220 lines)

Shared plumbing used by every fetcher and coordinator.

| Function | Purpose |
|---|---|
| `last_friday_on_or_before(d)` | Snap a date to the most recent Friday |
| `build_friday_spine(start, end)` | Weekly Friday DatetimeIndex from `start` to the last Friday on/before `end` |
| `fetch_with_backoff(url, …)` | Generic HTTP GET with exponential backoff (2s, 4s, 8s, 16s, 32s — max 5 retries) on 429/5xx |
| `get_sheets_service(credentials_json)` | Build a Google Sheets API v4 service from a service-account JSON string |
| `sv(v)` | Sheets-safe value coercion (NaN → empty string, ints stay ints, etc.) |
| `push_df_to_sheets(service, sheet_id, tab, df, label)` | DataFrame → Sheets writer with `SHEETS_PROTECTED_TABS` guard, automatic clear-range, batched writes |
| `ensure_tab(service, sheet_id, tab_name, label)` | Create the tab if it doesn't exist |

#### 9.5.2 `sources/countries.py` (54 lines)

Single source of truth for the 12 country codes and their per-source mappings, driven by `data/macro_library_countries.csv`.

| Function | Purpose |
|---|---|
| `load_countries()` | Return tuples of country dicts (canonical / WB / IMF / OECD code metadata) |
| `country_meta()` | `dict[code, (country_name, region)]` for snapshot row enrichment |
| `wb_code_map()` / `imf_code_map()` | Per-source code mapping (e.g. `EA19 → EMU` for World Bank, `EA19 → EURO` for IMF) |
| `wb_countries_query_string()` | Pre-built WB API country list (`USA;GBR;DEU;…`) for fan-out |

#### 9.5.3 `sources/fred.py` (423 lines)

| Function | Purpose |
|---|---|
| `_load_raw()` | Read `data/macro_library_fred.csv` raw |
| `load_us_library()` / `load_us_library_as_list()` | US-only series (no `country` set) |
| `load_intl_library()` | International series (with `country` set) |
| `validate_series(...)` | Pre-flight check that a FRED series ID resolves |
| `fetch_observations(series_id, realtime_start=None, realtime_end=None, …)` | FRED REST call with backoff. **ALFRED vintage mode (§3.17, 2026-06-10):** when `realtime_start` / `realtime_end` are passed the API returns the data **as it appeared on that vintage date** — required for any retrospective regime back-test that needs to use only the data available at the time. |
| `parse_observations(data)` | FRED JSON → `list[(date, float)]` |
| `parse_observations_vintage(data)` | ALFRED vintage parser — each row carries `realtime_start` / `realtime_end`; returns `list[(date, vintage_date, value)]` so a back-test can reconstruct the exact data snapshot for any past `as_of` date. |
| `fetch_latest_prior(series_id, …)` | Snapshot helper — return latest + prior + change |
| `fetch_series_as_pandas(series_id, start)` | Full series → pandas Series |
| `parse_monthly_by_country(…)` | OECD-via-FRED naming-convention parser |

#### 9.5.4 `sources/oecd.py` (191 lines)

| Function | Purpose |
|---|---|
| `load_library()` | Read `data/macro_library_oecd.csv` |
| `parse_csv(text, label)` | OECD SDMX `format=csv` response → `dict` |
| `_fetch(url, …)` | Generic OECD GET with backoff and the 4s rate-limit delay |
| `fetch_snapshot(indic, …)` | Snapshot fetch for one indicator (latest + prior) |
| `fetch_history(indic, country)` | Full history for a single country slot |

#### 9.5.5 `sources/worldbank.py` (193 lines)

| Function | Purpose |
|---|---|
| `load_library()` | Read `data/macro_library_worldbank.csv` |
| `validate_library(...)` | Pre-flight check that each WDI indicator code resolves |
| `parse_response(data, label)` | WB JSON v2 → `dict` |
| `_fetch(url, …)` | Generic WB GET |
| `fetch_snapshot(indic, …)` / `fetch_history(indic, country)` | Snapshot + per-country history |

#### 9.5.6 `sources/imf.py` (153 lines)

| Function | Purpose |
|---|---|
| `load_library()` | Read `data/macro_library_imf.csv` |
| `validate_library(...)` | Pre-flight check |
| `parse_response(data, indicator, label)` | IMF DataMapper v1 JSON → `dict` |
| `fetch_indicator(indicator, …)` | Single-call full-history fetch (IMF returns whole panels in one shot) |

#### 9.5.7 `sources/dbnomics.py` (180 lines)

| Function | Purpose |
|---|---|
| `load_library()` | Read `data/macro_library_dbnomics.csv` |
| `fetch_series(series_path, …)` | DB.nomics REST call |
| `parse_observations(doc)` | DB.nomics JSON → `list[(date, float)]` |
| `parse_period_to_date(period)` | Handles annual / quarterly / monthly / daily DB.nomics period strings |
| `obs_to_series(obs, col_name)` | `list[(date, float)]` → named pandas Series |

#### 9.5.8 `sources/ifo.py` (579 lines; Bright Data fallback added 2026-06-12)

| Function | Purpose |
|---|---|
| `load_library()` | Read `data/macro_library_ifo.csv` |
| `_iter_recent_yyyymm(months_back)` / `_candidate_urls()` | Build candidate ifo workbook URLs (latest publication month + fallback months) |
| `_try_download_xlsx(session, url)` | Download + magic-byte validate the workbook (`PK\\x03\\x04` zip header) |
| `_brightdata_creds()` | Return `(api_key, zone)` from env vars `BRIGHTDATA_API_KEY` / `BRIGHTDATA_ZONE`, or `None` if unset |
| `_fetch_via_brightdata(url, zone, api_key, timeout)` | Route the xlsx download through Bright Data Web Unlocker proxy (3rd-strategy fallback); enforces `_MAX_BRIGHTDATA_CALLS_PER_RUN` budget |
| `resolve_workbook()` / `resolve_workbook_url()` / `download_workbook(url)` | Top-level workbook acquisition: (1) direct URL, (2) landing-page scrape, (3) Bright Data fallback if creds available |
| `parse_workbook(xlsx_bytes, indicators)` | Extract every registered series via its `(sheet_index, excel_col)` from `macro_library_ifo.csv` into a wide DataFrame |

#### 9.5.9 `sources/boe.py` (~210 lines, Stage D)

Bank of England Interactive Statistical Database (IADB) fetcher. Direct CSV download with multi-line title preamble.

| Function | Purpose |
|---|---|
| `load_library()` | Read `data/macro_library_boe.csv` |
| `fetch_series(series_code, start, ...)` | GET against `_iadb-fromshowcolumns.asp` (with fallback to legacy `fromshowcolumns.asp`); HTML form responses rejected |
| `parse_csv(text, series_code)` | Detect "DATE" header row dynamically (skips the title preamble) and parse `(date, value)` tuples; multi-format date parser |
| `fetch_series_as_pandas(series_code, ...)` | Convenience wrapper returning a date-indexed `pd.Series` |

Uses a Chrome-like User-Agent — IADB's WAF blocks the default `python-requests` UA.

#### 9.5.10 `sources/ecb.py` (~210 lines, Stage D)

ECB Data Portal fetcher. SDMX 2.1 over REST. Distinct from the legacy inline ECB call in `compute_macro_market.py::fetch_ecb_euro_ig_spread()` (which is not yet refactored through this module).

| Function | Purpose |
|---|---|
| `load_library()` | Read `data/macro_library_ecb.csv` |
| `fetch_series(series_id, start, ..., last_n=None)` | GET against `https://data-api.ecb.europa.eu/service/data`. `series_id` is `<DATASET>/<KEY>`. `last_n` optionally appends `&lastNObservations=N` for fast snapshot calls (used at snapshot time to avoid timeout on cold ECB cache). |
| `parse_csv(text, series_id)` | Read TIME_PERIOD + OBS_VALUE columns; dimension columns ignored |
| `_parse_period(p)` | Daily / monthly / quarterly / annual ECB period parser |
| `fetch_series_as_pandas(series_id, ..., last_n=None)` | Convenience wrapper |

60s default timeout (FM dataset is sometimes slow on first hit).

#### 9.5.11 `sources/boj.py` (~270 lines, Stage D)

Bank of Japan Time-Series Data Search fetcher. Programmatic API launched February 2026.

| Function | Purpose |
|---|---|
| `load_library()` | Read `data/macro_library_boj.csv` |
| `_split_series_id(series_id)` | Split search-screen format `<DB>'<series_code>` into (db, code) per the BoJ API requirement |
| `fetch_series(series_id, ...)` | GET against `https://www.stat-search.boj.or.jp/api/v1/getDataCode` with split db + code |
| `parse_csv(text, series_id)` | Detect SERIES_CODE header row; read SURVEY_DATES + VALUES columns |
| `_parse_period(p)` | Handles BoJ's YYYYMMDD daily / YYYYMM monthly / YYYYQQ quarterly / YYYYHN half-year encodings |
| `fetch_series_as_pandas(series_id, ...)` | Convenience wrapper |

Diagnostic dump on parse failure logs the first 15 lines of response — surfaces schema changes proactively.

#### 9.5.12 `sources/estat.py` (~250 lines, Stage D)

Statistics Bureau of Japan e-Stat fetcher. JSON REST API; reads `ESTAT_APP_ID` from env (GitHub Secret).

| Function | Purpose |
|---|---|
| `load_library()` | Read `data/macro_library_estat.csv` |
| `_split_series_id(series_id)` | Parse `<statsDataId>?cdCat01=XX&cdCat02=YY` form into (stats_data_id, extras_dict) for multi-dim tables |
| `fetch_series(series_id, ...)` | GET against `https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData`; injects `appId`; checks `RESULT.STATUS` in the JSON for API-side errors |
| `parse_response(doc, series_id)` | Walk `GET_STATS_DATA → STATISTICAL_DATA → DATA_INF → VALUE`; dedup overlapping (date, value) tuples |
| `_parse_estat_time(t)` | Parse e-Stat's 10-digit `@time` encoding (trailing zeros indicate period type: annual / monthly / daily) |
| `fetch_series_as_pandas(series_id, ...)` | Convenience wrapper |

Falls back gracefully if `ESTAT_APP_ID` env var is missing.

#### 9.5.13 `sources/boc.py` (183 lines, 2026-05-28)

Bank of Canada Valet API fetcher. Keyless JSON. Series names are Valet identifiers (e.g. `V39079`).

| Function | Purpose |
|---|---|
| `load_library()` | Read `data/macro_library_boc.csv` |
| `fetch_series(series_name, recent, start_date, ...)` | GET against the Valet observations endpoint; uses `recent=N` for snapshot, `start_date=` for history |
| `parse_json(doc, series_name)` | Extract `(date, value)` tuples from the `observations` array |
| `fetch_series_as_pandas(series_name, ...)` | Convenience wrapper |

#### 9.5.14 `sources/statcan.py` (201 lines, 2026-05-28)

Statistics Canada WDS POST API fetcher. Keyless. Vector IDs are numeric (e.g. `41690973`).

| Function | Purpose |
|---|---|
| `load_library()` | Read `data/macro_library_statcan.csv` |
| `fetch_series(vector_id, latest_n, ...)` | POST to `getDataFromVectorsAndLatestNPeriods` |
| `parse_json(doc, vector_id)` | Extract `(refPer, value)` tuples from the `vectorDataPoint` array |
| `fetch_series_as_pandas(vector_id, ...)` | Convenience wrapper |

#### 9.5.15 `sources/ons.py` (218 lines, 2026-05-28)

UK ONS Zebedee /data API fetcher. Keyless JSON. The legacy `api.ons.gov.uk` host was decommissioned 2024-11-25.

| Function | Purpose |
|---|---|
| `load_library()` | Read `data/macro_library_ons.csv` |
| `fetch_series(series_id, ...)` | GET against `https://api.beta.ons.gov.uk/v1/data?uri=<series_id>` |
| `parse_json(doc, series_id)` | Pick finest non-empty frequency array (months > quarters > years); parse period strings to dates |
| `fetch_series_as_pandas(series_id, ...)` | Convenience wrapper |

#### 9.5.16 `sources/bundesbank.py` (218 lines, 2026-05-28)

Deutsche Bundesbank SDMX-ML REST API fetcher. Keyless. All dimension values required in the key (JSON/CSV return HTTP 406).

| Function | Purpose |
|---|---|
| `load_library()` | Read `data/macro_library_bundesbank.csv` |
| `fetch_series(series_id, last_n, ...)` | GET against `https://api.statistiken.bundesbank.de/rest/data/<flow>/<key>` |
| `parse_xml(text, series_id)` | SDMX generic-data XML → `list[(date, float)]` |
| `fetch_series_as_pandas(series_id, ...)` | Convenience wrapper |

#### 9.5.17 `sources/abs.py` (206 lines, 2026-05-28)

Australian Bureau of Statistics SDMX-CSV API fetcher. Keyless. Same CSV shape as the ECB Data Portal (TIME_PERIOD + OBS_VALUE columns).

| Function | Purpose |
|---|---|
| `load_library()` | Read `data/macro_library_abs.csv` |
| `fetch_series(series_id, last_n, ...)` | GET against `https://data.api.abs.gov.au/rest/data/<flow>/<key>` with `Accept: text/csv` |
| `parse_csv(text, series_id)` | Read TIME_PERIOD + OBS_VALUE columns |
| `fetch_series_as_pandas(series_id, ...)` | Convenience wrapper |

#### 9.5.18 `sources/istat.py` (287 lines, 2026-05-28; retry budget tightened 2026-06-12)

ISTAT (Italy) SDMX-CSV API fetcher. Keyless; retry budget tightened 2026-06-12 (timeout 90→30s, retries 6→3) to bound worst-case blockage at ~97s instead of ~570s per series when ISTAT is fully down.

| Function | Purpose |
|---|---|
| `load_library()` | Read `data/macro_library_istat.csv` |
| `_resolve_edition(series_id, ...)` | For dataflows with a trailing-dot EDITION slot, enumerate available vintages and return the latest (most recent observation) |
| `fetch_series(series_id, last_n, ...)` | GET against `https://esploradati.istat.it/SDMXWS/rest/data/<flow>/<key>`; calls `_resolve_edition` if series_id ends with `.` |
| `parse_csv(text, series_id)` | Read TIME_PERIOD + OBS_VALUE columns |
| `fetch_series_as_pandas(series_id, ...)` | Convenience wrapper |

#### 9.5.19 `sources/bls.py` (284 lines, 2026-05-28)

US Bureau of Labor Statistics Public Data API fetcher. `BLS_API_KEY` optional — v1 endpoint is keyless (recent window); v2 endpoint (full history, up to 19-year spans) requires a free registration key.

| Function | Purpose |
|---|---|
| `load_library()` | Read `data/macro_library_bls.csv` |
| `fetch_series(series_id, recent, ...)` | v1 GET (keyless) or v2 POST (with key) based on `BLS_API_KEY` env var |
| `parse_json(doc, series_id)` | Extract `(year+period, value)` tuples from the BLS response; maps period codes (`M01`–`M12`) to end-of-month dates |
| `fetch_series_as_pandas(series_id, ...)` | Convenience wrapper; `recent=True` → keyless v1 recent window |

#### 9.5.20 `sources/insee.py` (231 lines, 2026-06-09)

INSEE BDM (Banque de Données Macroéconomiques) SDMX-ML fetcher. Keyless; optional `INSEE_API_KEY` as Bearer token.

| Function | Purpose |
|---|---|
| `load_library()` | Read `data/macro_library_insee.csv` |
| `fetch_series(series_id, ...)` | GET against `https://api.insee.fr/series/BDM/V1/data/<series_id>`; sends `INSEE_API_KEY` as Bearer if set |
| `parse_xml(text, series_id)` | SDMX-ML namespace-agnostic parser: handles both generic-data and structure-specific `Obs` element shapes |
| `_parse_period(p)` | Handles daily `YYYY-MM-DD`, monthly `YYYY-MM`, quarterly `YYYY-Qn`, annual `YYYY` |
| `fetch_series_as_pandas(series_id, ...)` | Convenience wrapper |

#### 9.5.21 `sources/bdf.py` (Opendatasoft Explore v2.1, rewritten 2026-06-10) — PROVISIONAL

Banque de France Webstat Opendatasoft records-JSON fetcher. `BDF_API_KEY` required (sent as `Authorization: Apikey <key>`); no companion secret. Without a key the module skips gracefully — gaps surface in the daily audit. Migrated from the legacy IBM API Connect stack on 2026-06-10 — see §5 BdF entry for the migration post-mortem.

| Function | Purpose |
|---|---|
| `load_library()` | Read `data/macro_library_bdf.csv` (public API unchanged from the legacy module) |
| `fetch_series(series_id, ...)` | GET against `https://webstat.banque-france.fr/api/explore/v2.1/catalog/datasets/<dataset_id>/records?where=<odsql>&limit=100&offset=N`; pages until `total_count` is reached; skips with a warning if no key or if the row is PROVISIONAL |
| `_split_series_id(series_id)` | Split `<dataset_id>|<odsql_where>` into its two halves |
| `parse_records(records, series_id)` | Opendatasoft records-JSON parser: heuristically detects time field (`time_period` / `date` / `period` / …) and value field (`obs_value` / `value` / …) from the first record, so the same parser works across BdF's heterogeneous Opendatasoft schemas |
| `_parse_period(p)` | Handles daily `YYYY-MM-DD` + ISO datetime, monthly `YYYY-MM`, quarterly `YYYY-Qn`, annual `YYYY` |
| `fetch_series_as_pandas(series_id, ...)` | Convenience wrapper (public API unchanged) |

Status: both library rows still carry `series_id = 'PROVISIONAL|legacy_sdmx_key=...'` because the public catalogue (anonymous probe) exposes only one dataset (`tableaux_rapports_preetablis`). Once `BDF_API_KEY` is in the runtime: discover the MIR dataset_id via `/catalog/datasets?q=MFI+interest+rates`, walk the schema, translate the two legacy SDMX dot-keys into `<dataset_id>|<odsql_where>` form, and commit the upgraded CSV.

#### 9.5.22 `sources/alpha_vantage.py` (180 lines, 2026-06-10) — scaffolding

Alpha Vantage OVERVIEW snapshot fetcher for §3.3 (PE ratio integration). Library is header-only — population deferred per `manuals/alpha_vantage_evaluation.md` because the free-tier 25 req/day cap is too thin for a daily comp fan-out.

| Function | Purpose |
|---|---|
| `load_library()` | Read `data/macro_library_alpha_vantage.csv` (returns `[]` when only the header row is present) |
| `fetch_overview(symbol, ...)` | GET against `https://www.alphavantage.co/query?function=OVERVIEW&symbol=<SYM>`; treats a response carrying `Note` (free-tier rate-limit body) or an empty `Symbol` as a non-data response |
| `fetch_series_as_pandas(series_id, ...)` | Convenience wrapper that returns a one-row snapshot Series for the registered field |

Auth: `ALPHAVANTAGE_API_KEY` optional — no-op if absent (same posture as `sources/bdf.py`).

#### 9.5.23 `sources/shiller.py` (471 lines, 2026-06-10; host order updated 2026-06-11)

Yale `ie_data.xls` long-run S&P composite / CPI / 10Y / CAPE parser. Wired §3.13. **2026-06-11:** `shillerdata.com` is now the primary download host; Yale (`econ.yale.edu`) is the fallback (`_resolve_workbook_impl` tries shillerdata.com first).

| Function | Purpose |
|---|---|
| `load_library()` | Read `data/macro_library_shiller.csv` |
| `_resolve_workbook_impl(url, ...)` / `_resolve_workbook()` | Process-cached download of `ie_data.xls` (success *and* failure) so a fan-out across CAPE + CPI + 10Y only hits Yale once |
| `_decode_decimal_year(val)` | Parse Shiller's decimal-year Date column: integer = year, fractional = month per the `1871.10 → October` convention (NOT `0.10 = decile`). Handles both float and string serialisations. |
| `fetch_series_as_pandas(series_id, col_name, ...)` | Slice the "Data" sheet by the registered column header (e.g. `"CAPE"`, `"S&P Comp. P"`, `"Long Interest Rate GS10"`) and return a date-indexed `pd.Series` |

The module tries `shillerdata.com` first, then the Yale fallback, then the other mirrors (`datahub.io`, `posix4e.github.io`). The sandbox edge sometimes blocks all hosts — the smoke test SKIPs cleanly in that case.

#### 9.5.24 `sources/french.py` (413 lines, 2026-06-10; 3-Factor ZIP fix 2026-06-11)

Kenneth French Data Library ZIP-direct fetcher. Wired §3.13.

| Function | Purpose |
|---|---|
| `load_library()` | Read `data/macro_library_french.csv` |
| `_resolve_zip(zip_stem)` | Process-cached `requests.get` + `zipfile.ZipFile` open with browser-like headers (the Dartmouth FTP 403s bare-UA requests). One fetch + one open per ZIP per process. |
| `_extract_monthly_block(csv_bytes)` | Each French CSV contains a monthly block followed by an annual block separated by an `Annual Factors` boundary; extract the monthly block only |
| `fetch_series_as_pandas(series_id, col_name, ...)` | Split `<zip_stem>|<col>`, resolve the cached ZIP, slice the named column, return a month-end `pd.Series` |

No `pandas-datareader` dependency — would just wrap the same HTTP call. Sandbox edge sometimes returns `Host not allowed` 403 until `mba.tuck.dartmouth.edu` is on the runner's allow-list; smoke test SKIPs in that case.

#### 9.5.25 `sources/jst.py` (301 lines, 2026-06-10)

Jordà-Schularick-Taylor Macrohistory R6 `.dta` loader. Wired §3.13.

| Function | Purpose |
|---|---|
| `load_library()` | Read `data/macro_library_jst.csv` |
| `_resolve_dataset()` | Process-cached download of `JSTdatasetR6.dta` via `requests`, then `pandas.read_stata` into a wide-format DataFrame indexed by `(year, iso)`. ~5 MB compressed / ~50 MB in memory. |
| `_split_series_id(series_id)` | Parse `<iso>|<column>` into the (country, column) tuple to slice from the cached DataFrame |
| `fetch_series_as_pandas(series_id, col_name, ...)` | Slice the (iso, column) cell, return an annual `pd.Series` indexed by year-end dates |

`www.macrohistory.net` is on the pipeline allow-list but some CI hosts and the local sandbox still receive `host_not_allowed` 403s — smoke test SKIPs cleanly in that case.

#### 9.5.26 `sources/atlanta_fed.py` (366 lines, 2026-06-11)

Atlanta Fed GDPNow real-time US GDP nowcast fetcher. Keyless — downloads `GDPTrackingModelDataAndForecasts.xlsx` from the Atlanta Fed website. Wired §3.1.4.

| Function | Purpose |
|---|---|
| `load_library()` | Read `data/macro_library_atlanta_fed.csv` |
| `_download_workbook(url, ...)` | HTTP GET with retry + magic-byte validation (`PK\x03\x04`) |
| `_resolve_workbook_bytes()` | Process-cached workbook download — one fetch per process (same shape as `sources/ifo.py` / `sources/shiller.py`) |
| `fetch_series_as_pandas(series_id, col_name, ...)` | Locate the GDPNow tracking column in the workbook, return a date-indexed `pd.Series` |

Smoke test: `test_atlanta_fed_smoke.py` (daily CI step — SKIPs when the Atlanta Fed host is unreachable from the runner).

#### 9.5.27 `sources/ny_fed.py` (348 lines, 2026-06-11)

New York Fed Staff Nowcast keyless Excel fetcher. Downloads the full forecast-history workbook from the NY Fed medialibrary CDN path. Wired §3.1.4 as the second US nowcast source alongside the Atlanta Fed GDPNow.

| Function | Purpose |
|---|---|
| `load_library()` | Read `data/macro_library_ny_fed.csv` |
| `_download_workbook(timeout, retries)` | HTTP GET with retry + magic-byte validation (`PK\x03\x04`) + browser-like UA (the medialibrary 403s default python-requests UA) |
| `_resolve_workbook_bytes()` | Process-cached workbook download — one fetch per process (same shape as `sources/ifo.py` / `sources/shiller.py`) |
| `_find_date_column(df)` | Locate the publication-date column in a forecast sheet by name (case-insensitive `date`/`vintage`/`forecast date`) or value-shape heuristic |
| `_extract_headline_series_from_sheet(df)` | From one forecast sheet, build a `(publication_date → rightmost-non-null numeric)` Series — the "rightmost non-null" value tracks the current-vintage nowcast across multi-quarter columns |
| `_parse_workbook(xlsx_bytes)` | Parse every plausible forecast sheet, concatenate, deduplicate by date (keep last), plausibility-filter to [−50, +50] % SAAR |
| `fetch_series_as_pandas(series_id, col_name)` | Top-level entry point; currently only `nyfed_nowcast_us_qoq_saar` is wired (matches the single library row) |

Smoke test: `test_ny_fed_smoke.py` (daily CI step — SKIPs when the NY Fed medialibrary host is unreachable from the runner).

### 9.6 `compute_macro_market.py` (2,546 lines)

**Role:** Phase E — 108 composite macro-market indicators with z-scores, regime classifications, forward regime signals, and z-score trend diagnostics. Also writes the month-end-sampled `macro_market_monthly_hist.csv` consumed by regime-AA Phase 3 (§3.14).

All indicator metadata is loaded from `macro_indicator_library.csv` at import time — no hardcoded indicator definitions in Python. The CSV is the single source of truth for `id`, `category`, `group`, `sub_group`, `naturally_leading`, `formula_using_library_names`, `economic_interpretation`, `regime_classification`, and `cycle_timing`.

As of the 2026-04-26 supplemental refactor (commit `48c8c1c`) and the 2026-04-27 EU_Cr1 fix-forward, **this module contains zero direct API contact for FRED**. Every FRED series the calculators read is provisioned through the unified `macro_economic_hist` (built by `fetch_macro_economic.py`) and looked up by column name via `_get_col(mu, "<col>")`. The only direct API contact remaining is `fetch_ecb_euro_ig_spread()` (ECB Data Portal — too deeply nested to live in `macro_library_*.csv`) and `fetch_fxi_prices()` (yfinance FXI denominator for `AS_G1`).

#### Indicator Families (105 total)

| Group | Sub-group(s) | IDs | Description |
|---|---|---|---|
| US | Equity - Growth | US_G1, US_G2, US_G3, US_G5, US_G4 | Cyclicals vs defensives, banks vs utilities, tech leadership, breadth |
| US | Equity - Factor | US_EQ_F1, US_EQ_F2, US_EQ_F3, US_EQ_F4 | Value/growth and size (Russell, S&P) |
| US | Rates | US_R1, US_R2, US_R3, US_R4, US_R5, US_R6 | Yield curve slopes, breakeven inflation, real yields, mortgage spread |
| US | Credit | US_Cr1, US_Cr2, US_Cr3, US_Cr4 | IG spread, HY spread (5-regime), HY-IG, HY vs Treasuries |
| US | CrossAsset - Growth | US_CA_G1 | SPY vs GOVT risk-on/off |
| US | Volatility | US_V1, US_V2 | VIX term structure, MOVE/VIX |
| US | Momentum | M1-M5 | Trend, dual momentum, HY momentum, vol-filtered |
| US | Macro / Survey | US_JOBS1, US_JOBS2, US_JOBS3, US_G6, US_HOUS1, US_M2, US_ISM1 | Labour, activity, housing, M2, ISM |
| Europe / UK | Equity / Rates / Credit | EU_G1, EU_G2, EU_G3, EU_G4, EU_Cr1, EU_Cr2, EU_R1, UK_G1, UK_R1, UK_R2, UK_Cr1 | European cyclicals, EU IG/HY credit, BTP-Bund, UK domestic, gilts, breakeven, GBP credit |
| Japan | Equity - Growth | JP_G1 | Japan vs global equities |
| Asia | China / India | AS_CN_G1, AS_CN_G2, AS_CN_G3, AS_IN_G1, AS_CN_R1, AS_IN_R1 | Size, growth, rates |
| Global | CrossAsset / CLI | GL_CA_I1, GL_G1, GL_G2, GL_CLI1, GL_CLI2, GL_CLI5, EU_CLI1, AS_CLI1 | Risk appetite, EM vs DM, CLI differentials/breadth |
| FX & Commodities | Various | FX_CMD1-FX_CMD6, FX_CN1, FX_1, FX_2 | Copper/gold, dollar, iron ore, commodity momentum, FX momentum |
| Inflation | Per-region | US_INFL1, UK_INFL1, EU_INFL1, JP_INFL1, CN_INFL1, US_INFEXP1 | Regional inflation regimes + US expectations composite |
| Growth / Nowcast | Nowcasts | EU_NOWCAST1, US_GDPNOW1, US_NOWCAST1, UK_NOWCAST1, JP_NOWCAST1 | Real-time GDP proxies (shipped 2026-06-11) |
| Japan / Survey | Tankan spreads | JP_TANKAN_SPREAD1, JP_TANKAN_SVC1, JP_TANKAN_FWD1 | Tankan sub-DI composite regime indicators (shipped 2026-06-11) |

EU_Cr1 currently returns `n/a` until a free Euro IG corporate yield source is wired (see `forward_plan.md` §1 Known Data Gaps); EU_Cr2 (added 2026-04-27) covers the Euro HY regime separately by reading `BAMLHE00EHYIOAS` from the unified hist.

**Blended INFL1 calculators (2026-06-10 §3.1.3 follow-up):** `_calc_UK_INFL1`, `_calc_EU_INFL1`, and `_calc_JP_INFL1` now blend headline + core CPI (mean of `GBR_CPI` + `GBR_CORE_CPI_YOY`; `EA_HICP` + `EA_HICP_CORE_YOY`; `JPN_CPI` + `JPN_CORE_CPI_YOY`) — matches the shape of `_calc_US_INFL1`. Each falls back gracefully to headline-only if the core component is absent on a given week. `_calc_CN_INFL1` continues to use CPI + PPI since China runs no hard inflation target and is deflation-prone.

#### How Each Indicator Works

Each indicator goes through:
1. **Calculator function** (`_calc_US_G1`, etc.) — computes raw weekly Series from input data via `_get_col(mu, …)` for macro series and `_p(cp, …)` for prices.
2. **Rolling z-score** — 156-week window (3 years), 52-week minimum warm-up.
3. **Regime classification** — discrete label based on z-score thresholds and/or raw-value thresholds (via `REGIME_RULES` lambdas keyed by indicator id).
4. **Forward regime** — slope of z-score over trailing 8 weeks classifies as `improving` / `stable` / `deteriorating`; indicators flagged as `naturally_leading` in the CSV receive a `[leading]` suffix.
5. **Z-score trend** — separate diagnostic against 1w / 4w / 13w lookbacks: `intensifying`, `fading`, `reversing`, or `stable`.

#### Key Functions

| Function | Purpose |
|---|---|
| `_load_indicator_library()` | Load `macro_indicator_library.csv` → `INDICATOR_META`, `ALL_INDICATOR_IDS`, `NATURALLY_LEADING` |
| `load_comp_hist()` | Load `market_data_comp_hist.csv` (weekly prices) |
| `load_macro_economic_hist()` | Load `macro_economic_hist.csv` (skip 14 metadata rows) — replaces the retired `load_macro_us_hist()` / `load_macro_intl_hist()` pair |
| `fetch_ecb_euro_ig_spread(mu)` | ECB AAA euro govt 10Y yield → Euro IG spread placeholder (see EU_Cr1 docstring; corp-yield half currently unwired) |
| `fetch_fxi_prices()` | yfinance FXI (China Large-Cap ETF) for `AS_G1` denominator |
| `_to_weekly_friday(series)` | Resample any cadence to the weekly Friday spine |
| `_rolling_zscore(series)` | Rolling z-score (156w window, 52w min) |
| `_get_col(df, col)` | Tolerant column lookup against the unified hist (returns NaN-filled Series on miss) |
| `_p(df_comp, ticker, usd)` | Comp-pipeline price lookup (local or USD-adjusted) |
| `_log_ratio(num, den)` | `log(num / den)` — primary indicator calculation |
| `_arith_diff(a, b)` | `a - b` — for yield-curve and spread differences |
| `_sum_log_ratio(nums, dens)` | Average of multiple log-ratios — composite indicators |
| `_yoy(series, freq)` / `_annualised_change(series, periods)` / `_z_of_series(series)` | Common transforms used by the calculators |
| `_r(raw, z, pos_z, neg_z, pos_label, neg_label, neutral)` | Standard 3-bucket regime helper used by most `REGIME_RULES` lambdas |
| `_assign_regime(ind_id, raw, z)` / `_assign_fwd_regime(ind_id, z_slope)` | Apply the regime rule and the forward-regime classification for one indicator |
| `make_result(raw, ind_id)` | Wrap a raw weekly Series into the per-indicator DataFrame (`raw`, `zscore`, `regime`, `fwd_regime`) |
| `compute_all_indicators(cp, mu, mi, supp, dbn)` | Orchestrate all 108 indicator calculations under one try/except per indicator |
| `_zscore_trend_classification(z_now, z_1w, z_4w, z_13w, z_peak_abs_13w)` | Classify recent z-score trajectory as `intensifying` (rising in magnitude vs 1w/4w and near the 13-week peak), `fading` (`\|z_now\| < 0.9 × \|z_4w\|`), `reversing` (sign flip vs 4w ago from a prior `\|z\| > 0.5`), or `stable`. |
| `_sample_z(df, offset_weeks)` | Return zscore value `offset_weeks` Friday rows before the last non-null raw row (used to sample 1w/4w/13w history for trend classification). |
| `build_snapshot_df(results)` | One row per indicator: id, group, sub_group, category, last_date, raw, zscore, zscore_1w_ago, zscore_4w_ago, zscore_13w_ago, zscore_peak_abs_13w, zscore_trend, regime, fwd_regime, formula_note |
| `build_hist_df(results)` | One row per date × ~432 columns (108 indicators × 4 values: raw, zscore, regime, fwd_regime). `pd.concat(...).copy()` defragments the wide frame to silence pandas `PerformanceWarning`s in the downstream `reset_index()`. |
| `push_macro_to_google_sheets(df_snapshot, df_hist)` | Write `macro_market` and `macro_market_hist` tabs to Sheets (checks `SHEETS_PROTECTED_TABS`) |
| `run_phase_e()` | **Entry point** — load inputs, compute, save + push. **2026-06-10 (§3.14):** after the weekly hist is written, additionally writes a month-end-sampled view via `df_hist.resample("ME").last()` into `MONTHLY_HIST_CSV` (`data/macro_market_monthly_hist.csv`). Sampling only — the underlying 156-week z-score window in `_rolling_zscore` is unchanged. Sister-file `_x.csv` follows the standard preservation contract via `write_hist_with_archive`. Stable schema for regime-AA Phase 3 Layer-1 monthly engine consumption. |

#### Key Constants

| Constant | Value | Purpose |
|---|---|---|
| `ZSCORE_WINDOW` | 156 | 3-year rolling window for z-scores (weeks) |
| `ZSCORE_MIN_PERIODS` | 52 | 1-year minimum warm-up (weeks) |
| `HIST_START` | `"2000-01-01"` | Start date for the weekly indicator history |
| `MONTHLY_HIST_CSV` | `"data/macro_market_monthly_hist.csv"` | Output path for the §3.14 month-end-sampled view written by `run_phase_e()` |
| `_FWD_SLOPE_POS` | +0.15 | Weekly z-score slope threshold for `improving` |
| `_FWD_SLOPE_NEG` | -0.15 | Weekly z-score slope threshold for `deteriorating` |
| `ECB_BASE_URL` | `https://data-api.ecb.europa.eu/service/data` | ECB Data Portal SDMX REST endpoint |
| `INDICATOR_META` | dict | Maps 105 IDs to `(group, sub_group, category, formula_note, concept, subcategory)` — 6-tuple loaded from CSV. `concept` and `subcategory` were added 2026-04-28 (§2.4) and propagate into the `macro_market.csv` snapshot output. |
| `ALL_INDICATOR_IDS` | list | Ordered indicator IDs (CSV row order) |
| `NATURALLY_LEADING` | frozenset | IDs flagged as naturally leading in the CSV |
| `REGIME_RULES` | dict | Maps 105 IDs to regime classification lambdas |
| `_US_CALCULATORS` | dict | US indicator calculator functions |
| `_EU_CALCULATORS` | dict | Europe/UK indicator calculator functions (incl. EU_Cr2) |
| `_ASIA_REGIONAL_CALCULATORS` | dict | Asia/Global/FX indicator calculator functions |
| `_PHASE_D_CALCULATORS` | dict | Survey-derived indicators (ISM, ifo, Eurostat) — historical naming, all now read from the unified hist |
| `_ALL_CALCULATORS` | dict | Merged union of the above four dicts |

### 9.7 `docs/build_html.py` (2,921 lines)

**Role:** Generates the Indicator Explorer — an interactive HTML page for visualising macro-market indicators with regime strips, z-score overlays, and a 3-section sidebar. Reads the freshly-written CSVs at the end of each pipeline run.

#### What it takes for a new indicator to appear in the explorer

Surfaced when the 2026-05-28 inflation composites were merged but didn't immediately show in the explorer (cause: timing — the daily run hadn't computed them yet). The contract is **four-step, AND condition** — miss any one and the indicator is silently absent:

1. **Library row** in `data/macro_indicator_library.csv` with a unique `id`, populated `group` / `sub_group` / `concept` / `subcategory`. (`_load_indicator_library()` reads this.) Indicators missing `group` land in the `ungrouped` bucket and don't render.
2. **Calculator** in one of the `_*_CALCULATORS` dicts in `compute_macro_market.py`, returning a weekly value Series. (`compute_all_indicators()` iterates `ALL_INDICATOR_IDS`, derived from the library CSV row order — so this *must* exist or the daily run logs a warning and skips.)
3. **Regime rule** in `REGIME_RULES` (a `lambda r, z` returning a label string).
4. **At least one daily run after (1)/(2)/(3) merged.** Without this, `data/macro_market_hist.csv` lacks the `<id>_raw` / `_zscore` / `_regime` / `_fwd_regime` columns, and the explorer's `present_ids` discovery — `build_macro_market()` at lines ~120-150, which scans hist column suffixes — skips the indicator entirely.

Step 4 is the most overlooked: PR #152 (the 6 inflation composites) merged at 13:02 UTC; the most recent daily run was 05:04 UTC the same day; so the next daily run was the one that populated the hist with `US_INFL1_raw` / etc. The fix wasn't a code change — just waiting for (or triggering) the next run.

**Diagnostic check** for "I added an indicator and it's not in the explorer": `python3 -c "import csv; hdr=next(csv.reader(open('data/macro_market_hist.csv'))); print([c for c in hdr if 'YOUR_ID' in c])"`. If empty → step 4 hasn't happened. If non-empty but still absent in the explorer → step 1's metadata is incomplete (likely missing `group`).

**Audit pre-flight** (forward_plan §3.11 Stage 1, shipped 2026-06-10): `data_audit.py::_check_missing_explorer_indicators()` surfaces step-4 silent skips as a `missing_explorer_indicators` row under Section B static checks. Permanent gaps (5 indicators whose underlying input has no free source — EU_Cr1, AS_CN_R1, DE_ZEW1, JP_PMI1, CN_PMI2, all documented in §1 Known Data Gaps) are allowlisted via `KNOWN_MISSING_INDICATORS` so they don't pollute the daily noise.

**Sidebar layout (post §2.5 v2 restructure, 2026-04-28):** three top-level sections —
1. **Macro Market Indicators** — Phase E composites; toggleable between By Region (default, the existing region grouping) and By Concept (concept → subcategory).
2. **Economic Data** — every raw-macro source merged into one section (FRED + OECD + WB + IMF + DB.nomics + ifo); toggleable between By Region (groups by Country in registry order from `data/macro_library_countries.csv`) and By Concept.
3. **Market Data** — yfinance comp-pipeline price series (Local / USD variant toggle preserved).

#### Key Functions

| Function | Purpose |
|---|---|
| `_clean(val)` / `_series_to_list(s)` / `_date_range(dates, values)` / `_parse_date_col(df)` | Internal helpers for value coercion and date-axis construction |
| `load_indicator_meta()` | Load `macro_indicator_library.csv` → dict keyed by id with category, group, sub_group, **concept, subcategory**, formula, interpretation, regime description, leading flag, cycle_timing (L/C/G) |
| `load_countries()` | Read `data/macro_library_countries.csv` and surface the 12-row registry (code + name + region) into `MAIN_DATA.countries`. Drives the By-Country sidebar grouping + the country-filter dropdown ordering. (§0 of forward_plan.md: country list lives in the CSV, never in JS.) |
| `build_macro_market(ind_meta)` | Load `macro_market_hist.csv`; emits `groups` (region tree) + `groupsByConcept` (concept tree) for the toggleable sidebar |
| `_load_unified_hist_once()` | Cache the unified `macro_economic_hist` DataFrame + per-column metadata (read once, reused). Adds lowercase `concept` / `subcategory` aliases so JS uses one key style across both Phase E and raw-macro payloads. |
| `_build_payload(keep_column)` | Generic payload builder that filters the cached unified hist by a per-column predicate |
| `build_macro_economic()` | Single combined payload spanning every raw-macro source. **2026-06-10:** the source allowlist (the `m.get("Source") in {...}` predicate inside `_build_payload`) was extended to 25 names — the canonical aggregators (FRED, OECD, World Bank, IMF, DB.nomics), the direct national / central-bank fetchers (BoE, ECB, BoJ, e-Stat, ifo, BoC, StatCan, ONS, Bundesbank, ABS, ISTAT, BLS, INSEE, Banque de France), the commodity/market refs (LBMA, Nasdaq Data Link, Alpha Vantage), and the §3.13 long-run sources (Shiller, KenFrench, JST). Missing a source here silently drops every column from that source from the Economic Data tree even though the data is correctly populated in `macro_economic_hist.csv` — the fix-forward for the long-run trio landed in the same commit that wired the sources. |
| `build_market_comp()` | Load `market_data_comp_hist.csv`, build the comp-pipeline market-data payload |
| `build_html_file(main_payload, mkt_payload)` | Render `HTML_TEMPLATE` against the assembled payloads and write `docs/indicator_explorer.html` + `docs/indicator_explorer_mkt.js` |
| `main()` | Orchestrate: load metadata + countries → build all payloads → emit files |

#### Notable Features

- **3-section sidebar with two view modes:** Macro Market Indicators / Economic Data / Market Data. The first two sections support a By Region ↔ By Concept toggle; switching is instant and preserves the user's checked-state for plotted series.
- **Multi-level grouping:** Phase E composites use group → sub_group → indicator; Economic Data uses country → indicator (By Region) or concept → subcategory → indicator (By Concept).
- **4-colour regime palette:** positive (green), negative (red), amber (gold), neutral (grey) — each maps a set of regime labels.
- **Forward regime display:** `fwd_regime` shown as a coloured badge alongside current regime.
- **Custom PNG snapshot:** Camera button composites chart title, Plotly chart image, legend entries, and regime colour key onto a single canvas.
- **Cycle-timing badges:** L/C/G badges next to every indicator in both Macro Market Indicators and Economic Data sections (colour: blue=Leading, amber=Coincident, pink=Lagging — matches the source-doc shading from `manuals/Macro Market Indicators Reference.docx`).
- **Filter pipeline:** unified `applySidebarFilters()` evaluates four filters per item — search, market-data variant, L/C/G chips, country dropdown — and runs section-collapse logic so empty groups hide. Country dropdown is auto-populated from `MAIN_DATA.countries` (the registry, per §0 of forward_plan.md).
- **Inline L/C/G legend** beneath the cycle-filter chips: `L = Leading · C = Coincident · G = Lagging`.

#### Output Files

- `docs/indicator_explorer.html` — self-contained HTML (committed to git)
- `docs/indicator_explorer_mkt.js` — embedded market data JSON (committed to git)

### 9.8 `data_audit.py` (1,188 lines)

**Role:** Daily integrated audit that consolidates every "what could go wrong" signal into a single committed report + a GitHub Issue comment that triggers user notification email. Replaces the v1 `freshness_audit.py` (deleted 2026-04-28). See §2.6 of `forward_plan.md` for the design rescope rationale.

Runs as a CI step at the end of `update_data.yml`; never fails the build (warning channel, not gate).

#### Three audit sections

| Section | Purpose | Mechanism |
|---|---|---|
| **A — Fetch outcomes** | Catch broken FRED IDs, dead yfinance tickers, persistent HTTP errors | Scrape `pipeline.log` post-run for known per-series patterns (`HTTP <code> on X — skipping`, `possibly delisted`, `Quote not found for symbol: X`, `Period 'max' is invalid`). Retried-then-recovered transients are filtered out by only matching the `— skipping` suffix. yfinance suspects are cross-checked against the latest non-empty row of `market_data_comp_hist.csv` to filter transient warnings. |
| **B — Static checks** | Catch registry / code drift before it shows up at runtime | Local sanity checks: orphan country codes (every code referenced across **all 22 single-country macro-library CSVs** — fred / dbnomics / ifo / boe / ecb / boj / estat / nasdaqdl / lbma / boc / statcan / ons / bundesbank / abs / istat / bls / insee / bdf / alpha_vantage / shiller / french / jst — exists in `macro_library_countries.csv`; was 9 pre-2026-06-10); indicator-id uniqueness; calculator registration (every `id` in `macro_indicator_library.csv` is registered in one of the `_*_CALCULATORS` dicts in `compute_macro_market.py`); **`_check_missing_explorer_indicators()`** — every `id` in `macro_indicator_library.csv` must have a matching `<id>_raw` column in `macro_market_hist.csv` or it's silently absent from the explorer (§3.11 Stage 1 pre-flight, shipped 2026-06-10). Permanent gaps allowlisted via `KNOWN_MISSING_INDICATORS` (currently `{EU_Cr1, AS_CN_R1, DE_ZEW1, JP_PMI1, CN_PMI2}` — each traced to §1 Known Data Gaps). `_get_col(...)` column existence (every literal in the calculator code resolves to a column in `macro_economic_hist.csv`) — with the `KNOWN_MISSING_COLUMNS` allowlist for documented permanent gaps (currently `{CHN_GOVT_10Y}` — see §13); **registry drift across all 3 hist↔library pairs** — every column in `market_data_comp_hist.csv` / `macro_economic_hist.csv` / `macro_market_hist.csv` must trace back to a row in its source-of-truth library; orphans report `(run: python library_sync.py --confirm)` for the operator; **unadjusted-split detection** — `_check_unadjusted_splits()` scans `market_data_comp_hist.csv` for sustained week-over-week jumps matching clean integer-fraction split ratios (1/N for N=2..20 plus 3:2, 4:3, 5:4, 5:2, 5:3 + inverses, ±1% tolerance) that persist within ±15% over 4 weeks and aren't already registered in `data/manual_splits.csv`. Ratio-agnostic — catches 2:1, 3:2, 4:3, 5:4, 10:1, etc. forward and reverse. Indices (`^*` tickers) skipped because they don't split. See §11 Pattern 11. |
| **C — Value-change staleness** | Catch silent publisher freezes that the Friday-spine forward-fill would otherwise mask | For each column in the unified hist, find the last *value-change* date (not just last non-null cell — forward-fill makes that wrong). Compare age against per-frequency tolerance from `data/freshness_thresholds.csv` plus per-row `freshness_override_days` overrides. Classify FRESH / STALE (1×–2×) / EXPIRED (>2× or no obs). |

#### Outputs

- `data_audit.txt` — full sorted plaintext report grouped by section + status.
- `audit_comment.md` — Markdown body posted to the perpetual `daily-audit`-labelled GitHub Issue. First line is the one-sentence summary:
  - `## Daily audit — 2026-04-28 — **ALL CLEAN**`
  - `## Daily audit — 2026-04-28 — **100 ISSUES** (24 fetch errors, 1 static-check failure, 75 stale series)`
  - Detail follows in collapsible `<details>` blocks; rows capped at 30-50 per category for readability (full detail in `data_audit.txt`).

#### Key Functions

| Function | Purpose |
|---|---|
| `load_thresholds()` | Read `data/freshness_thresholds.csv` → `{frequency: days}` dict |
| `load_overrides()` | Walk every per-source library CSV; collect per-row `freshness_override_days` → `{(source, series_id): days}` |
| `load_macro_hist()` | Read `data/macro_economic_hist.csv`; for each column, find last value-change date (walks forward through non-null cells, tracks date when value differs from previous) |
| `classify_age(age, threshold)` | FRESH / STALE / EXPIRED per the 1× / 2× tolerance bands |
| `section_a_fetch_outcomes()` | Scrape `pipeline.log` + cross-check against `market_data_comp_hist.csv` |
| `_yfinance_truly_dead(suspects)` | Filter yfinance suspects: keep only those without data in the latest comp-hist row |
| `section_b_static_checks()` | Run the 6 sub-checks (orphan countries / duplicate ids / missing calculators / missing explorer indicators / missing `_get_col` columns / registry drift) |
| `_check_missing_explorer_indicators()` | **NEW 2026-06-10 (§3.11 Stage 1).** Read every `id` from `macro_indicator_library.csv`, scan the header row of `macro_market_hist.csv` for `<id>_raw` columns, report any unmatched id that isn't in `KNOWN_MISSING_INDICATORS`. Closes the silent skip described in §9.7's four-step "what it takes to appear in the explorer" contract — when an indicator merges but no daily run has happened yet, or the calculator silently returned empty, the hist won't carry the column and the explorer drops the indicator without warning. The audit now surfaces it as a `missing_explorer_indicators` row. |
| `section_c_staleness()` | Bucket every series into FRESH / STALE / EXPIRED |
| `section_d_history_preservation()` | **NEW 2026-04-30 (Stage A).** Per-`*_hist.csv` row counts for live + sister + union, plus date ranges. ALERTs on (a) ICE-BofA-bearing file with no sister, (b) sister rows being a strict subset of live (writer regression). Surfaced in `audit_comment.md` so anomalies appear in the daily GitHub Issue notification. |
| `render_report(sections)` | Build the plaintext `data_audit.txt` |
| `render_comment(sections)` | Build the GitHub Issue Markdown `audit_comment.md` with first-line summary |
| `main()` | Orchestrate; always returns exit code 0 (warning channel) |

#### `freshness_override_days` cluster reference (2026-04-29 bulk pass)

48 library rows were updated in a single bulk pass (commit `ab08e5d`) to absorb normal publisher cadence. The cluster→override mapping below is the durable record of what value was chosen and why:

| Cluster (audit age) | Override | Affected source(s) | Rows | Rationale |
|---|---|---|---|---|
| Weekly OAS (12d) | 14d | FRED (NFCI, TOTCI) | 2 | Slack over Friday-spine alignment |
| Monthly 54d cluster | 75d | FRED + OECD | 32 | Canonical 30-50d publisher cadence + 1.5 cycles |
| Monthly 82d cluster | 90d | FRED + OECD | 9 | Up to 2 normal cycles |
| Monthly 144d (Eurostat / China trade) | 150d | FRED + DB.nomics | 2 | Real publisher lag absorbed |
| Monthly 235d (ISM Services) | 60d | DB.nomics | 1 | DB.nomics mirror normal cadence; series stays EXPIRED at 235d as forcing function |
| Quarterly 208d | 180d | FRED + DB.nomics | 3 | 1 full quarter slack on top of base 120d |

OECD multi-country fan-out conflicts (one library row → many fanned-out columns) resolved per row:
- `OECD UNEMPLOYMENT` → 75d (canonical normal cadence; GBR/DEU/FRA at 117–145d stay surfaced as STALE forcing functions)
- `OECD RATE_3M` → 90d (covers EA19 at 82d and GBR at 54d)

The 117d cluster (PERMIT, FEDFUNDS, CMRMTSPL, FRA/DEU_UNEMPLOYMENT, EU_ESI/IND/SVC_CONF, ISM_MFG_PMI/NEWORD) was deliberately **not** widened — 117d for monthly publishers is too long for normal lag; widening would mask a real fetch or publisher issue. Those 10 series remain EXPIRED as forcing functions.

### 9.9 `library_sync.py` (~396 lines)

**Role:** Operator-gated companion to `data_audit.py`'s Section B `registry_drift` check (forward_plan §0 / §3.1). The library CSVs are the source of truth for what the pipeline fetches; this utility keeps the hist files aligned with them after a library row has been edited or removed.

Default mode is dry-run; pass `--confirm` to apply. The `removed_tickers.csv` ledger is **not** updated by this script — that ledger records human edits to source-of-truth library CSVs; this script is the downstream sync action.

#### Three hist↔library pairs

| Pair | Source-of-truth | Hist file | Column-derivation rule |
|---|---|---|---|
| **comp** | `index_library.csv` (PR/TR + ticker_fred_* fields) | `market_data_comp_hist.csv` | row 0 ("Ticker ID") cols 2+; each base ticker appears twice (`_Local` + `_USD`) |
| **macro_economic** | union of all 25 `macro_library_*.csv` registered in `MACRO_LIBS` (fred, oecd, worldbank, imf, dbnomics, ifo, boe, ecb, boj, estat, nasdaqdl, lbma, boc, statcan, ons, bundesbank, abs, istat, bls, insee, bdf, alpha_vantage, shiller, french, jst — coverage extended 2026-06-10 to match `data_audit.py`'s walk and prevent registry-drift false positives on the new sources) | `macro_economic_hist.csv` | FRED/DB.nomics/ifo etc.: `col` (or `series_id` fallback); OECD: `f"{country}_{series_id}"` per `oecd_countries`; WB/IMF: `f"{country}_{col}"` × every code in `macro_library_countries.csv` |
| **macro_market** | `macro_indicator_library.csv` (`id` column) | `macro_market_hist.csv` | each `id` produces 4 columns: `<id>_raw`, `<id>_zscore`, `<id>_regime`, `<id>_fwd_regime` |

For each orphan column, the existing data is archived to `data/_archived_columns/<hist_basename>__<column_id>__<YYYY-MM-DD>.csv` (preserving full historical observations) before the column is dropped from the live hist file.

#### Key functions

| Function | Purpose |
|---|---|
| `sync_comp(confirm)`, `sync_macro_economic(confirm)`, `sync_macro_market(confirm)` | Per-pair drivers; return orphan count |
| `_run_pair(...)` | Generic engine: read hist rows, compute orphan set, archive each orphan, drop columns, rewrite |
| `_<pair>_expected()` | Compute the expected column-id set from the relevant library CSVs |
| `_<pair>_present(rows)` | Extract the present column-id set from the hist rows |
| `_<pair>_idxs_for_orphan(rows, id)` | Locate every CSV column index that belongs to the orphan id |
| `_<pair>_archive(rows, id, idxs)` | Write the per-orphan archive file |

### 9.10 `audit_writeback.py` (~230 lines)

**Role:** Writeback half of the daily-audit loop (forward_plan §3.1 sub-track 3). `data_audit.py` *reports* dead yfinance tickers but does not edit `index_library.csv`; this utility maintains a per-ticker dead-list streak counter and flips `validation_status` from `CONFIRMED` to `UNAVAILABLE` after **N=14** consecutive days on the dead list.

Runs as a CI step between `data_audit.py` and the GitHub Issue comment post, so the comment surfaces today's writeback actions.

#### Inputs / outputs

| File | Role |
|---|---|
| `data_audit.txt` (read) | Section A `YFINANCE_DEAD` list parsed via regex |
| `data/index_library.csv` (read+write) | Current `validation_status` consulted; flipped when a streak crosses the threshold |
| `data/yfinance_failure_streaks.csv` (read+write) | 4-column streak file: `ticker, first_seen_dead, last_seen_dead, consecutive_fail_days` |
| `audit_comment.md` (append) | One-line summary appended so the daily Issue comment captures actions |

#### Semantics

- **Dead today + status=CONFIRMED** → streak++ (or =1 if new). At 14: flip to UNAVAILABLE, drop from streak file on next run.
- **Dead today + status=UNAVAILABLE** → no-op (already flagged); drop any stray streak entry.
- **Not dead today** → drop from streak file (streak broken).
- **Manual override** (operator re-sets CONFIRMED on a previously-flagged row) → next dead-day starts a fresh streak from 1.

Pass `--dry-run` for report-only.

---

## 10. FX Conversion Logic

### Snapshot (fetch_data.py)

For each instrument row, the USD return is computed as:

```
USD_return = (1 + Local_return) * (1 + FX_return) - 1
```

where `FX_return` is the spot FX change over the same period. For indirect-quote currencies (JPY, CNY, etc. — listed in `COMP_FCY_PER_USD`), the FX rate is inverted before applying.

### Historical (fetch_hist.py)

`compute_comp_usd_series(local_series, ccy, fx_cache, fcy_per_usd)`:

1. Looks up FX history from the pre-fetched `fx_cache`
2. Aligns FX series to the instrument's date index with forward-fill
3. For direct-quote currencies (GBP, EUR, AUD): `usd_price = local_price * fx_rate`
4. For indirect-quote currencies (JPY, CNY, INR, etc.): `usd_price = local_price / fx_rate`

Each Friday's USD price uses **that Friday's exchange rate** (or the nearest prior trading day's rate via forward-fill). No look-ahead bias.

### Currency Convention Reference

| Currency | yfinance Ticker | Convention | In `COMP_FCY_PER_USD`? |
|---|---|---|---|
| GBP | `GBPUSD=X` | 1 GBP = X USD | No (multiply) |
| EUR | `EURUSD=X` | 1 EUR = X USD | No (multiply) |
| AUD | `AUDUSD=X` | 1 AUD = X USD | No (multiply) |
| JPY | `USDJPY=X` | 1 USD = X JPY | Yes (divide) |
| CNY | `CNY=X` | 1 USD = X CNY | Yes (divide) |
| INR | `INR=X` | 1 USD = X INR | Yes (divide) |
| CAD | `USDCAD=X` | 1 USD = X CAD | Yes (divide) |
| KRW | `USDKRW=X` | 1 USD = X KRW | Yes (divide) |
| HKD | `USDHKD=X` | 1 USD = X HKD | Yes (divide) |
| BRL | `USDBRL=X` | 1 USD = X BRL | Yes (divide) |
| TWD | `USDTWD=X` | 1 USD = X TWD | Yes (divide) |
| MXN | `USDMXN=X` | 1 USD = X MXN | Yes (divide) |
| ZAR | `USDZAR=X` | 1 USD = X ZAR | Yes (divide) |
| TRY | `USDTRY=X` | 1 USD = X TRY | Yes (divide) |
| IDR | `USDIDR=X` | 1 USD = X IDR | Yes (divide) |
| RUB | `USDRUB=X` | 1 USD = X RUB | Yes (divide) |
| SAR | `USDSAR=X` | 1 USD = X SAR | Yes (divide) |

The full mapping is defined once in `library_utils.py` as `COMP_FX_TICKERS` (18 entries) and `COMP_FCY_PER_USD` (15 entries), imported by all modules.

### LSE Pence Correction

UK `.L` tickers may report prices in pence (GBp) rather than pounds (GBP). The correction is applied dynamically:

```python
if ticker.endswith(".L"):
    median_val = series.dropna().median()
    if pd.notna(median_val) and median_val > 50:
        series = series / 100
```

This is used in both `collect_comp_assets()` (fetch_data.py) and `fetch_comp_yfinance_history()` (fetch_hist.py). No hardcoded pence ticker list is needed.

---

## 11. Key Design Patterns

### Pattern 1: Phase Isolation (Fail-Safe Chaining)

Every phase after `main()` is wrapped in `try/except` at the module level:

```python
try:
    from fetch_macro_economic import run_phase_macro_economic
    run_phase_macro_economic()
except Exception as _me_err:
    print(f"[macro_economic] Non-fatal error: {_me_err}")
```

If `run_phase_macro_economic` crashes, `market_data`, `market_data_comp`, and `market_data_comp_hist` are already written and safe. Each phase runs independently — see §3 Execution Flow for the full chain.

### Pattern 2: Per-Series Try/Except

Inside each module, every individual ticker/series fetch is also wrapped:

```python
for series_id in SERIES_LIST:
    try:
        data = fetch_series(series_id)
        ...
    except Exception as e:
        print(f"  WARNING: {series_id} failed: {e}")
        continue
```

One bad ticker or FRED series never kills the rest of the output.

### Pattern 3: Friday Spine

All historical data is aligned to a weekly Friday date index. Monthly and quarterly series are forward-filled into the Friday slots. This ensures all series share a common date axis, enabling cross-series analysis without date alignment complexity.

### Pattern 4: Metadata Prefix Rows

History tabs in Google Sheets have metadata rows above the data:

- `macro_economic_hist`: 14 prefix rows (Column ID, Series ID, Source, Indicator, Country, Country Name, Region, Category, Subcategory, Concept, cycle_timing, Units, Frequency, Last Updated)
- `market_data_comp_hist`: 10 prefix rows (Ticker ID, Variant, Source, Name, Broad Asset Class, Region, Sub-Category, Currency, Units, Frequency)

The CSVs include these prefix rows. Code that reads them back must skip the appropriate number of header rows (e.g. `pd.read_csv(..., header=N)` or `df.iloc[N:]`).

### Pattern 5: Library-Driven Configuration

Both pipelines read everything from `index_library.csv` at runtime:

- Adding/removing instruments only requires editing the CSV
- `validation_status = "CONFIRMED"` is the gate — set to `"PENDING"` to disable without deleting
- `simple_dash = True/False` controls simple pipeline inclusion
- `broad_asset_class` and `units` are read from CSV, not computed in code

Similarly, every fetched macro identifier lives in one of the per-source library CSVs (`macro_library_countries.csv`, `_fred.csv`, `_oecd.csv`, `_worldbank.csv`, `_imf.csv`, `_dbnomics.csv`, `_ifo.csv`) — see §7 CSV File Inventory and `forward_plan.md` §0 for the architecture rules. Macro-market composite indicator definitions live in `macro_indicator_library.csv`, which drives both `compute_macro_market.py` (metadata, grouping, naturally_leading flag, cycle_timing) and `docs/build_html.py` (sidebar hierarchy, category, economic interpretation, regime descriptions).

### Pattern 6: Diff-Check CSV Commits

Output CSVs are only committed to git if content actually changed. This avoids noisy daily commits on weekends when markets are closed and data hasn't changed.

### Pattern 7: Google Sheets Write Pattern

All modules follow the same pattern:

1. **Protected-tab guard:** before any other call, the writer checks that the target tab is **not** in `library_utils.SHEETS_PROTECTED_TABS` (`market_data`, `sentiment_data`) — those are owned by the simple pipeline and downstream `trigger.py` and must never be overwritten by another phase.
2. Ensure tab exists (create via `batchUpdate addSheet` if absent)
3. Clear entire range (`sheets.values().clear()` over `A:ZZ`)
4. Write header + data (`sheets.values().update()` with `valueInputOption="USER_ENTERED"`)
5. NaN values converted to empty string before push (never write `"nan"` strings)
6. After every snapshot run, `fetch_data.py::push_to_google_sheets` sweeps every title in `SHEETS_LEGACY_TABS_TO_DELETE` so retired tabs cannot accumulate

### Pattern 8: Rate Limiting with Exponential Backoff

All API calls include configurable delays and exponential backoff on 429/5xx:

| Source | Base Delay | Backoff | Max Retries |
|---|---|---|---|
| yfinance | 0.3s | — | 3 |
| FRED | 0.6s | 2s, 4s, 8s, 16s, 32s | 5 |
| OECD | 4s | 2s, 4s, 8s, 16s, 32s | 5 |
| World Bank | 1s | 2s, 4s, 8s, 16s, 32s | 5 |
| IMF | 1s | 2s, 4s, 8s, 16s, 32s | 5 |
| ECB | 0.6s | 2s, 4s, 8s, 16s | 3 |
| BoE | 0.6s | 2s, 4s, 8s, 16s | 3 |
| BoJ | 0.6s | 2s, 4s, 8s, 16s | 3 |
| e-Stat | 0.6s | 2s, 4s, 8s, 16s | 3 |

### Pattern 9: History Preservation Under Source Truncation (Stage A, 2026-04-30; Option B forward-extension 2026-05-08)

Source-side history can shrink retroactively — for example, ICE Data demanded that FRED truncate redistributed ICE BofA series (`BAMLH0A0HYM2`, `BAMLC0A0CM`, `BAMLHE00EHYIOAS`, etc.) to a rolling 3-year window from April 2026, irreversibly losing 20+ years of pre-2023 spread data on FRED's side. Without intervention, the next nightly fetch would overwrite local history with the truncated window.

**Architecture (per `forward_plan.md` §3.1.1):**

For every `data/<file>_hist.csv` the pipeline writes, there is a sister `data/<file>_hist_x.csv`. The sister is append-only — once a row enters, it stays — and is intended to be a **true append-only superset** of every date ever observed in live, so a future shrinkage event has a complete archive to draw from.

**Two write rules** (both applied on every `write_hist_with_archive()` call):

1. **Shrinkage archive** (the original Stage A rule, 2026-04-30). Per-column floor advancement, NOT row-count change. A rolling-window source can keep row count constant while the earliest non-null date walks forward each cycle. For each column shared between the new fetch and the existing live file, if `new.earliest_nonnull_date > local.earliest_nonnull_date`, the rows in `[local_earliest, new_earliest)` with that column non-null are appended to the sister CSV before the live CSV is rewritten.
2. **Forward extension** (Option B, added 2026-05-08). Every date in the incoming `new_df` that isn't already in the sister is also appended. Without this, a sister written once at bootstrap drifts into a strict subset of live and provides no preservation value going forward — the daily audit's "strict subset" check kept firing for ~10 days before Option B landed because the bootstrap sister was static while live walked weekly.

Together, **the sister tracks live's full historical reach over time** and additionally retains values for any date a column subsequently loses.

**Read-back semantics**: `library_utils.load_hist_with_archive()` is a drop-in replacement for `pd.read_csv` that transparently unions live + sister via `pd.combine_first`. Live wins on cells where it has a non-null value; sister fills cells where live is NaN. This gives Phase E indicator calculators (`compute_macro_market.py`) and the dashboard payload (`docs/build_html.py`) the full historical depth even when the source has truncated.

**Open design question — sister CSV cannot self-heal under `keep="first"` dedup.** `library_utils._append_archive_rows()` deduplicates by date with `keep="first"`, so once a value is in the sister it is **never** overwritten by a later corrected one. Consequences:

- A bad value frozen in the sister (e.g. an unadjusted-split price, a stale source revision) stays wrong forever.
- Today this is masked because `load_hist_with_archive()` lets live win wherever live is non-null, and live (full rebuild) covers all in-range dates. The sister's stale value only surfaces if live ever *drops* that date — which is precisely when the sister matters (rolling-window truncation).
- So a corrected series + stale sister = a latent landmine: correct today, silently wrong the day live's window rolls past it.

We worked around this for `1306.T` via `scripts/backadjust_hist_splits.py` (Pattern 11). The standing question — whether to change the merge/dedup so the sister can self-heal — has four candidate resolutions documented in `forward_plan.md` §3.6a (prefer-fresher dedup, versioned preservation, periodic sister rebuild, status quo + manual corrector). **Decision is deliberately deferred** because it interacts with the Stage A preservation guarantee. Don't pick one without re-reading §3.6a.

**Writer migration**: every `*_hist.csv` writer goes through `library_utils.write_hist_with_archive()`:

- `compute_macro_market.py` (Phase E hist writer)
- `fetch_hist.py` (`save_csv()` routes `*_hist.csv` paths through the helper)
- `fetch_macro_economic.py` (`save_hist_csv()`)

**Audit hook**: `data_audit.py::section_d_history_preservation()` surfaces per-file row counts (live + sister + union) and date ranges in the daily audit. The Option-B forward-extension fix retired the previously chronic "sister rows are a strict subset of live" ALERT.

**Out of scope**: this rule preserves history we already have. It does not back-fill history we never captured (a separate research task — would require paid ICE Data or alternative archive).

---

### Pattern 10: Fail-Fast Network Source (2026-05-27)

The pipeline fetches from ~12 external APIs, each with its own reliability profile. When any one source goes unresponsive (DNS hang, slow-loris timeout, throttling without a 429), an unbounded retry budget can stall the whole daily run for an hour or more. We hit this twice in succession:

- **ifo (2026-05-27 evening)**: the new retry logic (`retries=3 × timeout=60s + exponential backoff × 10 candidate URLs × 2 calls = up to ~60 min`) plus block-buffered stdout through `tee` left the run apparently frozen with no `[ifo]` output.
- **DB.nomics (later that night)**: API outage; 13 series × `retries=4 × timeout=30s + 2/4/8/16s backoff` × snapshot + history = ~65 min grinding through timeouts.

Both stalled the entire pipeline (DB.nomics sits mid-order in the macro coordinator, blocking ifo/BoE/ECB/BoJ/e-Stat/LBMA + the hist build, compute, audit). The lesson: a non-critical source must **fail fast**, not block the run.

**The pattern (applied in `sources/ifo.py` + `sources/dbnomics.py`):**

1. **Tight per-request budget**: `timeout` = 10–15s, `retries` = 2 (the previous 3–4 + 30–60s timeouts compounded badly under outage).
2. **Process-level circuit breaker**: track consecutive hard failures (timeouts, 5xx exhaustion, connection errors). After **N=3** consecutive failures, set a module-level "tripped" flag; subsequent calls return immediately without touching the network. A successful (or any server-responding) call resets the counter, so isolated blips don't trip it — only a sustained outage does. State persists across snapshot + history passes so a down API is contacted at most ~3 times per run.
3. **Cached resolve / fetch** where the same network work is reused. `sources/ifo.py::resolve_workbook()` caches *both* success and failure at module scope, so the snapshot batch and the history builder share one fetch (and one failure if it fails).
4. **Unbuffered output**: the GitHub Actions workflow sets `PYTHONUNBUFFERED=1` so the live Actions log + `pipeline.log` reflect progress in real time. The ifo stall was *also* a diagnosability bug — without unbuffered output we couldn't see which source the pipeline was actually stuck on.

**Worst-case bounds (`outage scenario`):**

| Source | Old budget | New budget | Speedup |
|---|---|---|---|
| ifo (single resolve) | ~30 min (10 URLs × 3 attempts × 60s) | ~3 min (6 URLs × 2 × 15s) | 10× |
| ifo full run (snapshot + history) | ~60 min | ~3 min (cached → 1 resolve) | 20× |
| DB.nomics full run | ~65 min | ~80 sec (3 fails → trip → instant skips) | 50× |

**When to apply**: every multi-call network source in `sources/*.py` is a candidate. Today only ifo + DB.nomics have it. Generalising to OECD / WB / IMF / BoE / ECB / BoJ / e-Stat / LBMA is tracked as a forward-plan follow-up — apply on first incident or pre-emptively if a source becomes flaky.

**Snippet to copy** (paraphrased from `sources/dbnomics.py`):

```python
_CONSEC_FAILURES = 0
_BREAKER_TRIPPED = False
_BREAKER_THRESHOLD = 3

def _register_failure():
    global _CONSEC_FAILURES, _BREAKER_TRIPPED
    _CONSEC_FAILURES += 1
    if _CONSEC_FAILURES >= _BREAKER_THRESHOLD and not _BREAKER_TRIPPED:
        _BREAKER_TRIPPED = True
        print(f"    [<source> BREAKER OPEN] {_CONSEC_FAILURES} consecutive failures — "
              f"skipping remaining <source> fetches this run (API appears unreachable)")

def _reset_failures():
    global _CONSEC_FAILURES
    _CONSEC_FAILURES = 0

def fetch_series(series_id, retries=2, timeout=12):
    if _BREAKER_TRIPPED:
        return None
    # ... attempt with retries, calling _reset_failures() on any server response,
    # _register_failure() on timeout/5xx exhaustion or connection error.
```

---

### Pattern 11: Manual Split Override for Yahoo-Missing Corporate Actions (2026-05-27)

Yahoo Finance back-adjusts prices for splits / dividends via `auto_adjust=True`, but only for events in its corporate-actions feed. That feed is patchy for some non-US listings — notably Tokyo-listed ETFs. The first known case: **`1306.T`** (NEXT FUNDS TOPIX ETF) did a **10:1 split** on ex-rights date **2026-03-30** (record date 2026-03-31; under Japan's T+2 settlement the ex-rights date is one business day before the record date) that Yahoo never recorded. The raw price dropped 3,827 → 386.6, and every return window straddling the split was wrong by ≈90%.

**The pattern (CSV-driven, per §0):**

`data/manual_splits.csv` is the source-of-truth override. Schema:

```
ticker,ex_date,ratio,notes
1306.T,2026-03-30,10,NEXT FUNDS TOPIX ETF 10-for-1 share split. Record date 2026-03-31; ...
```

`ratio` is the split multiplier (10 = "10-for-1"; the new share count is `old × ratio`, the new price is `old / ratio`). Pre-`ex_date` prices are divided by `ratio` to make the series continuous.

**Two parts to the implementation:**

1. **Runtime — `library_utils.apply_manual_splits(series, ticker)`**. Called by `fetch_data.py::fetch_yf_history` (snapshot) and `fetch_hist.py::fetch_comp_yfinance_history` (history) on the raw yfinance series. Handles tz-aware *and* tz-naive indices; no-op for tickers without an override. The snapshot's return windows are computed off the corrected series, and the next history rebuild writes the corrected series to `market_data_comp_hist.csv` automatically.
2. **One-off — `scripts/backadjust_hist_splits.py`**. Corrects **already-committed** `*_hist.csv` *and* the `*_hist_x.csv` sister in place, because **the sister can't self-heal** (Pattern 9's `keep="first"` dedup never overwrites stored values — a corrected runtime value in `new_df` is silently lost when it hits the sister). Idempotent: re-reads the boundary ratio before applying and skips if the series is already adjusted. Run manually after adding a new row to `manual_splits.csv`.

**Audit guard — `data_audit.py::_check_unadjusted_splits()`** (Section B): scans `market_data_comp_hist.csv` for sustained week-over-week jumps that *aren't* already in `manual_splits.csv` and look like an unadjusted split (clean integer-fraction ratio + holds within ±15% over 4 weeks + non-index ticker). Generic detector covers any split ratio (2:1, 3:2, 4:3, 5:4, 10:1, …, forward + reverse) — not just 10:1. See §9.8 for the detector logic.

**Diagnosing a future case (operator runbook):**

1. **Daily audit flags it** under `unadjusted_splits` with the ratio, dates, and persistence — that's the cue.
2. **Find the real ex-rights date** from the exchange notice. Note the country's settlement convention (e.g. Japan T+2: ex-rights = record date − 1 business day; US T+1 since 2024: ex-rights = record date).
3. **Add a row to `data/manual_splits.csv`** with that ex-rights date and the integer ratio.
4. **Run `python scripts/backadjust_hist_splits.py`** to correct committed live + sister CSVs immediately.
5. **Commit** the new row + the corrected CSVs. Next daily run will produce a continuous series from then on (runtime `apply_manual_splits` handles fresh fetches automatically).

---

## 12. Environment Setup

### Required Environment Variables

| Variable | Where Set | Used By |
|---|---|---|
| `FRED_API_KEY` | GitHub Secret | `fetch_data.py`, `fetch_hist.py`, `sources/fred.py` (called by `fetch_macro_economic.py`) |
| `GOOGLE_CREDENTIALS` | GitHub Secret | All modules that write to Sheets |

`GOOGLE_CREDENTIALS` must be a JSON string of a Google service account key with editor access to the target spreadsheet.

### Python Dependencies (`requirements.txt`)

```
yfinance>=0.2.51
pandas
numpy
requests
google-auth
google-api-python-client
# dev-only: used by manuals/build_docx.py, manuals/md_to_docx.py, archive/generate_review_excel.py
python-docx
openpyxl
```

The last two (`python-docx`, `openpyxl`) are not touched by the daily GitHub Actions pipeline — they support the local documentation build (`manuals/build_docx.py`, `manuals/md_to_docx.py`) and the one-off indicator-review workbook generator in `archive/generate_review_excel.py` (kept for historical reference; uses pre-2026-04-08 indicator IDs and is no longer runnable against the current library without a rewrite).

### Running Locally

```bash
export FRED_API_KEY="your_key_here"
export GOOGLE_CREDENTIALS='{"type": "service_account", ...}'
python fetch_data.py
```

Individual modules can also be run standalone:

```bash
python fetch_hist.py                # Comp-pipeline weekly history only (run_comp_hist)
python fetch_macro_economic.py      # Phase ME only — unified raw-macro snapshot + history
python compute_macro_market.py      # Phase E only (requires market_data_comp_hist + macro_economic_hist to exist)
python docs/build_html.py           # Indicator Explorer rebuild only (requires every CSV above)
```

### GitHub Actions

- **Schedule:** Daily at 00:34 UTC (cron `34 0 * * *`) — the odd minute avoids GitHub's scheduled-run congestion at the top of the hour; this slot ensures the run finishes well before the 06:00 UK local automations that consume the data
- **Manual trigger:** workflow_dispatch — GitHub UI > Actions > "Update Market Data" > "Run workflow"
- **Python version:** 3.11
- **Timeout:** 120 minutes
- **Steps:** (1) `git pull --rebase`, (2) `python fetch_data.py`, (3) `cd docs && python build_html.py`, (4) commit + push
- **Post-run:** Auto-commits updated CSVs plus `docs/indicator_explorer.html` and `docs/indicator_explorer_mkt.js` to `main` branch with message `Update market data + explorer - YYYY-MM-DD HH:MM UTC`

### GitHub Secrets

| Secret | Status | Purpose |
|---|---|---|
| `FRED_API_KEY` | Exists | All FRED API calls |
| `GOOGLE_CREDENTIALS` | Exists | Google Sheets push (service account JSON) |
| `ESTAT_APP_ID` | Exists | e-Stat REST API (`sources/estat.py`) — Japan Statistics Bureau |
| `NASDAQ_DATA_LINK_API_KEY` | Exists, currently unused | Wired §3.9 (2026-05-08) when `LBMA/GOLD` was on the NDL free tier; same-day NDL moved LBMA to paid tier, so gold was replumbed to LBMA-direct (`sources/lbma.py`). Secret is retained as live scaffolding so any future free NDL dataset becomes a CSV-row addition. |
| `BLS_API_KEY` | Exists (optional) | `sources/bls.py` (2026-05-28). BLS Public Data API v2 registration key — unlocks 500 queries/day, 50 series/query, 20-year history spans. Without it the pipeline falls back to the keyless v1 endpoint (recent window only; sufficient for freshness; FRED provides the historical depth). |
| `BDF_API_KEY` | **Missing** — needed | `sources/bdf.py` (Opendatasoft Explore v2.1 stack — migrated 2026-06-10). Sent as `Authorization: Apikey <key>`. Without it all BdF series skip gracefully; `macro_library_bdf.csv` rows will remain unvalidated PROVISIONAL. Obtain from `https://webstat.banque-france.fr/` (Login → API). |
| `ALPHAVANTAGE_API_KEY` | Optional, scaffolding-only | `sources/alpha_vantage.py` (§3.3, 2026-06-10). Free-tier OVERVIEW endpoint key. Without it the module no-ops gracefully. Currently consumed only by `test_alpha_vantage_smoke.py` — the library is header-only pending the storage-shape decision documented in `manuals/alpha_vantage_evaluation.md`. |
| `BRIGHTDATA_API_KEY` | Optional | `sources/ifo.py` (2026-06-12). Bright Data Web Unlocker API key. When set, enables the 3rd-strategy anti-bot fallback for ifo workbook downloads (direct URL + landing-page scrape both failed). Per-run budget capped at 30 calls. Free tier = 5,000 requests/month. If unset, ifo skips the Bright Data path silently and degrades to blank rows on a sustained HTML challenge. |
| `BRIGHTDATA_ZONE` | Optional | `sources/ifo.py` (2026-06-12). Bright Data zone name; defaults to `"web_unlocker1"` when unset. |
| `BDF_API_SECRET` | **Retired** 2026-06-10 | Removed from the workflow env block with the BdF migration from the legacy IBM API Connect SDMX-JSON stack to the Opendatasoft Explore v2.1 stack. The new stack uses a single `Apikey` header — no companion secret. |
| `FMP_API_KEY` | Exists, reserved for future use | Registered 2026-04-21. **Phase D FMP calendar module deleted 2026-04-23** — economic calendar endpoint paywalled on free tier (`/v3/economic_calendar` → HTTP 403, `/stable/economic-calendar` → HTTP 402). Secret retained for planned PE-ratio integration via `/stable/ratios` endpoint (still free; see `forward_plan.md` §3.3). |

### Workflow-level configuration

- **`PYTHONUNBUFFERED=1`** (set in `.github/workflows/update_data.yml` env block, 2026-05-27). Block-buffered stdout through `tee pipeline.log` previously masked which step a long run was actually on (the ifo stall investigation). Unbuffered output ensures the live Actions log + the committed `pipeline.log` reflect progress in real time. Cost: zero; preserve this permanently.
- **Primary-source smoke tests step (2026-06-09, extended 2026-06-10/11/12).** A `if: always()` + `continue-on-error: true` CI step runs `python -m unittest test_bls_smoke test_insee_smoke test_bdf_smoke test_alpha_vantage_smoke test_shiller_smoke test_french_smoke test_jst_smoke test_atlanta_fed_smoke test_ny_fed_smoke -v` and tees output into `pipeline.log`. Each test skips gracefully when the source endpoint is unreachable — a transient outage never blocks the daily commit. A genuine regression (e.g. a changed BLS response schema) surfaces as a loud warning in the daily audit Issue. BLS_API_KEY is optional; INSEE needs no key; BdF is expected to skip until the secret is provisioned; ALPHAVANTAGE_API_KEY is optional; the §3.13 long-run trio (Shiller / Ken French / JST) SKIPs cleanly when the sandbox edge blocks the Yale / Dartmouth / Macrohistory hosts (these reach the production runner but not the local dev sandbox). `test_ny_fed_smoke` SKIPs when the NY Fed medialibrary CDN is unreachable.

---

## 13. Known Issues & Status

### Data Gaps — see `forward_plan.md` §1

The canonical record of series unavailable from any free source we accept lives in **`forward_plan.md` §1 "Known Data Gaps"**. That table is the single source of truth — do not duplicate here.

**Material movement post-Stage-B + Stage-D (2026-04-30)**:

- ✅ `JPN_POLICY_RATE`, `CHN_POLICY_RATE`, `EA_HICP`, `DEU_IND_PROD` — Stage B T1 fallbacks wired (DB.nomics IMF/IFS + Eurostat). FRED forcing-function rows kept as audit alarms; T1 carries the data.
- ✅ `GBR_BANK_RATE`, `EA_DEPOSIT_RATE`, `JPN_IND_PROD`, `JP_TANKAN1` — Stage D T2 modules built (BoE IADB, ECB Data Portal, e-Stat, BoJ Time-Series). 51-71 yrs of fresh data flowing.
- ✅ ICE BofA truncation (April 2026) — handled architecturally via Stage A history-preservation safeguard (§11 Pattern 9). Pre-truncation history preserved in `*_hist_x.csv` sister files.
- ✅ DE 2Y bund yield — closed via ECB YC `EZ_GOVT_2Y` (Stage F follow-on).
- ✅ Long-run gold (§3.9, 2026-05-09) — `sources/lbma.py` + `data/macro_library_lbma.csv` → `GOLD_USD_PM` daily 1968-04-05 → present in `macro_economic_hist`. `GLOBAL_GOLD1` Phase E composite live. Replaced FRED's discontinued `GOLDPMGBD228NLBM` and superseded the brief Nasdaq Data Link routing (LBMA went paid-tier).
- ✅ Per-region inflation regimes (§3.1.3, 2026-05-28) — 5 `*_INFL1` indicators (US headline+core blend; UK/EA/JP/CN headline-only with follow-up to source core series) + `US_INFEXP1` (z-composite of breakevens + Michigan exp). Brings indicator-library to 99 rows.
- ✅ ifo workbook outage (2026-05-08 → 2026-05-27) — URL pattern corrected to `secure/timeseries/gsk-e-<YYYYMM>.xlsx` (PR #150) + fail-fast budget + cached resolve (PR #151). Validated 2026-05-28 — all 26 `DE_*` columns populated. See §5 ifo entry and §11 Pattern 10.
- ✅ DB.nomics fail-fast (2026-05-27, PR #154) — circuit breaker caps a full DB.nomics API outage at ~80 sec instead of ~65 min. See §5 DB.nomics entry and §11 Pattern 10.
- ✅ §3.12 OECD MEI long-rate + share-price batch (2026-06-10) — 17 FRED rows (7 `IRLTLT01<ISO>M156N` 10Y yields filling the regime-AA priority-10 yield matrix + 10 `SPASTT01<ISO>M661N` share-price indices). NLD added to `macro_library_countries.csv` to keep the country registry complete.
- ✅ §3.9.1 multi-commodity (2026-06-10) — 14 IMF Primary Commodity Prices rows on FRED (industrial metals, energy, agriculture + the aggregate `PALLFNFINDEXM`). All Cross-Asset / Leading.
- ✅ §3.13 long-run cross-validation anchors (2026-06-10) — Shiller / Ken French / JST modules + libraries wired (6 + 6 + 40 rows). Column names deliberately don't shadow the modern canonicals; intended as regime-AA Phase 0c pre-1950 cross-validation, not as primary regime-engine input.
- ✅ §3.14 monthly z-score sampling (2026-06-10) — `macro_market_monthly_hist.csv` written month-end from the weekly Friday hist via `df_hist.resample("ME").last()`. Schema-stable input for regime-AA Phase 3 Layer-1.
- ✅ §3.11 Stage 1 explorer pre-flight (2026-06-10) — `data_audit.py::_check_missing_explorer_indicators()` closes the silent-skip gap where a freshly-merged indicator without a daily run still didn't appear in the explorer.
- ✅ §3.17 ALFRED vintage mode (2026-06-10) — `sources/fred.py::fetch_observations` now accepts `realtime_start` / `realtime_end`; `parse_observations_vintage()` returns `(date, vintage_date, value)` tuples for back-tests that must use only data available at each `as_of`.
- ✅ §3.1.3 inflation-axis core blend (2026-06-10) — `_calc_UK_INFL1` / `_calc_EU_INFL1` / `_calc_JP_INFL1` now blend headline + core (ONS DKO8 / Eurostat TOT_X_NRG_FOOD.EA20 / OECD COICOP2018 TXCP01_NRG). Same blend shape as US_INFL1. CN_INFL1 retains CPI + PPI (no hard target).
- ✅ §3.1.3 Growth axis — 5 e-Stat JPN rows (`JPN_TERT_IND`, `JPN_MACH_ORDERS`, `JPN_RETAIL_SALES`, `JPN_HH_EXP`, `JPN_EWS_DI`) + 3 ONS UK rows (`GBR_IND_PROD`, `GBR_SERV_PROD`, `GBR_RETAIL_VOL`). JPN rows are PROVISIONAL until first credentialed e-Stat run reveals the `cdCatNN` slice; UK rows verified live 2026-06-10.
- ✅ §3.1.3 BoJ inflation extension — JPN_PPI + JPN_SPPI registered in `macro_library_boj.csv` (search-screen codes `PR01'PRCG20_2200000000` / `PR02'PRCS20_5200000000`); both verified live against BoJ Time-Series Data Search.
- ✅ `1306.T` 10:1 split back-adjustment (§3.6a, 2026-05-27) — `data/manual_splits.csv` + `library_utils.apply_manual_splits()` + `scripts/backadjust_hist_splits.py` cleaned up the bogus ≈ −89% return windows. New `_check_unadjusted_splits()` audit guard prevents recurrence for any split ratio. See §11 Pattern 11.
- ✅ §3.1.4 nowcasts (2026-06-11) — `EU_NOWCAST1` (equal-weight z of EZ IP / retail / ESI / industrial confidence), `US_GDPNOW1` (Atlanta Fed GDPNow passthrough via new `sources/atlanta_fed.py` + `data/macro_library_atlanta_fed.csv`), `UK_NOWCAST1` (ONS monthly real GDP ECY2 → YoY%; new `GBR_GDP_MONTHLY` row in `macro_library_ons.csv`). All 3 shipped as Phase E indicators. Brings composite indicator library to 105 rows.
- ✅ `US_NOWCAST1` (NY Fed Staff Nowcast, 2026-06-11) — `sources/ny_fed.py` (348 lines) + `data/macro_library_ny_fed.csv` (1 row: `nyfed_nowcast_us_qoq_saar`) + `_calc_US_NOWCAST1` in `compute_macro_market.py`. Downloads the full forecast-history workbook from the NY Fed medialibrary CDN; rightmost-non-null per publication row tracks the current-vintage headline. Confirmed computing in the 2026-06-12 daily run (`raw=2.46`, `regime='near-trend'`). Smoke test: `test_ny_fed_smoke.py`.
- ✅ `JP_NOWCAST1` (Japan nowcast composite, 2026-06-11) — `_calc_JP_NOWCAST1` in `compute_macro_market.py`: equal-weight z of `JPN_IND_PROD` + `JP_TANKAN1` + `JPN_RETAIL_SALES` + `JPN_MACH_ORDERS`. No new fetchers — pure Phase E. Confirmed computing in the 2026-06-12 daily run (`raw=1.008`, `regime='expansion'`).
- ✅ ifo Bright Data recovery (2026-06-12) — `sources/ifo.py` grows from ~390 → 579 lines (PR #194). Third-strategy fallback added: when ifo.de's HTML challenge persists across all direct + landing-page candidate URLs, the fetcher routes through the Bright Data Web Unlocker proxy (`BRIGHTDATA_API_KEY` + `BRIGHTDATA_ZONE` secrets; 30-call-per-run budget; degrades silently if unset). See §5 ifo entry and §12 secrets table.
- ✅ ISTAT retry budget tightened (2026-06-12) — `sources/istat.py` grows from 280 → 287 lines (PR #193). `timeout` reduced 90→30s, `retries` reduced 6→3. Worst-case ISTAT blockage per series drops from ~570s to ~97s on a fully-down gateway.
- ✅ §3.1 Stage E — JP Tankan sub-DIs (2026-06-11) — 5 new `macro_library_boj.csv` rows (JP_TANKAN_LMFG_FCST / JP_TANKAN_LNFG / JP_TANKAN_LNFG_FCST / JP_TANKAN_SMFG / JP_TANKAN_SNFG) and 3 Phase E indicators wired (`JP_TANKAN_SPREAD1` / `JP_TANKAN_SVC1` / `JP_TANKAN_FWD1`). Library grows from 4 → 9 BoJ rows.
- ✅ e-Stat statsDataId corrections (2026-06-11) — original PROVISIONAL IDs for JPN_MACH_ORDERS / JPN_RETAIL_SALES / JPN_HH_EXP / JPN_EWS_DI all returned "does not exist" on first credentialed run. HIGH-confidence replacements discovered via catalogue search and substituted in `macro_library_estat.csv`. `JPN_TERT_IND` dropped (no `getStatsData` table; METI publishes only as Excel file). Library shrinks from 6 → 5 rows. cdCat filters still pending next credentialed run.
- ✅ Shiller host order swap (2026-06-11) — `shillerdata.com` promoted to primary URL; Yale fallback retained. `sources/shiller.py` line count grows from 400 → 471.
- ✅ French 3-Factor ZIP fix (2026-06-11) — Mkt-RF / SMB / HML / RF rows in `macro_library_french.csv` re-pointed to `F-F_Research_Data_Factors_CSV.zip` (full history from 1926-07) instead of the 5-Factor ZIP (which starts 1963-07). `sources/french.py` line count grows from 374 → 413.
- ✅ CAN_EQUITY_TR_JST dropped (2026-06-11) — JST R6 does not carry a Canadian equity total-return series. `macro_library_jst.csv` shrinks from 40 → 39 rows.
- 🔁 BdF (`sources/bdf.py`) — migrated 2026-06-10 from the legacy IBM API Connect SDMX-JSON stack (`api.webstat.banque-france.fr/webstat-fr/v1`, `X-IBM-Client-Id` + `X-IBM-Client-Secret`) to the Opendatasoft Explore v2.1 stack (`webstat.banque-france.fr/api/explore/v2.1`, single `Authorization: Apikey` header). The legacy stack was already deprecated by BdF when the first credentialed run hit it (HTTP 401 `"Invalid client id or secret"`, run id `27271070256`). Both `FRA_LOAN_RATE_*` rows remain PROVISIONAL until a credentialed runtime can query `/catalog/datasets?q=MFI+interest+rates` and translate the legacy SDMX dot-keys into `<dataset_id>|<odsql>` form. `BDF_API_SECRET` retired with the migration. See §5 BdF entry.
- ⏸ `JPN_JGB_2Y` (Japan 2Y govt yield) — accepted gap as of 2026-06-10. BoJ Time-Series Data Search does **not** publish JGB benchmark yields (the metadata sweep of `FM02 / FM05 / FM06 / IR01 / OT` confirmed only call / repo / CP / CD rates and JGB issuance / trading volumes are served); a speculative `IR01'IRTBLG02Y` probe 400d; OECD MEI / DB.nomics IFS paths have no JP 2Y; IMF IFS `M.JP.FIGB_PA` is frozen since 2017-05 and not tenor-specific. The only remaining path is MoF Japan's "JGB Interest Rate" daily CSV, which would need a new `sources/mof_japan.py` T2 module. Deferred until regime-AA needs the JP leg of the global slope composite — under YCC the JP 2Y has been pinned near zero, so the leg's contribution to a 4-country average is modest. The PROVISIONAL `JPN_JGB_2Y` library row was removed in commit `696a1eb`.
- ⏸ `EU_Cr1` (Euro IG corporate yield) — partial: ETF proxy `IEAC.L` added to `index_library.csv`. True yield series still unsourced; ECB MIR / Bundesbank corporate yield indices remain candidates for follow-on probe.
- ⏸ `AS_CN_R1` (China 10Y govt yield) — partial: ETF proxy `CBON` added; calculator reference `_get_col(mu, "CHN_GOVT_10Y")` retained and **allow-listed** in `data_audit.py::KNOWN_MISSING_COLUMNS` so the static-check doesn't churn while the column self-wires the day a free source lands. Yield itself still proprietary.
- ❌ `CHN_M2`, `CHN_IND_PROD` (and other NBS/PBoC sub-series), `JP_PMI1` source replacement (now functionally covered by `JP_TANKAN1`), `DE_ZEW1`, `CN_PMI2` — accepted gaps (no free programmatic source).

`compute_macro_market.py` calculators silently degrade to `n/a` for any indicator whose underlying series is in the gap list. The `data/source_fallbacks.csv` registry documents the canonical chain per indicator including planned T2 modules where the chain is open.

### Tickers Confirmed Unavailable via yfinance

**The 22 dead yfinance tickers from the 2026-04-28 audit baseline have been triaged** in §3.1 sub-track 4 (see `forward_plan.md`). Per-ticker dispositions are recorded in `data/removed_tickers.csv`. Three categories of action were applied: 17 PR-blanks where the row's TR ETF proxy was retained, 2 TR-blanks where the PR index ticker was retained, 3 full row removals where neither side was usable. The legacy table below is preserved as historical context — none of these tickers is on the live audit's dead list anymore.

| Ticker | Instrument | Disposition (2026-04-28) |
|---|---|---|
| `^SX3P` `^SX4P` `^SX6P` `^SX7E` `^SX8P` `^SXDP` `^SXEP` `^SXKP` `^SXNP` | STOXX 600 sectors | PR blanked; SPDR sector UCITS ETFs (`EXH1.DE`, `EXH3.DE`, `EXH4.DE`, `EXH9.DE`, `EXI5.DE`, `EXV1.DE`, `EXV2.DE`, `EXV3.DE`, `EXV4.DE`) retained as TR |
| `^TX60`, `^TSXV`, `^TOPX` | S&P/TSX 60, S&P/TSX SmallCap, TOPIX | PR blanked; `XIU.TO`, `XCS.TO`, `1306.T` retained as TR |
| `^SP500V`, `^SP500G`, `^RMCCV`, `^RMCCG` | S&P 500 Value/Growth, Russell Mid-Cap Value/Growth | PR blanked; `IVE`, `IVW`, `IWS`, `IWP` retained as TR |
| `^CNXSC` | Nifty Smallcap 100 | PR blanked; `SMALLCAP.NS` retained as TR |
| `ISFA.L`, `SENSEXBEES.NS` | FTSE All-Share TR, BSE Sensex TR | TR blanked; PR index tickers `^FTAS`, `^BSESN` retained |
| `^SP500-253020`, `^SP500-351030`, `^SP500-601010` | S&P 500 sub-industry rows | Full row removal — no TR proxy and no calculator dependency |

Going forward, the daily `audit_writeback.py` runs N=14 consecutive days of dead-list streaks before flipping `validation_status` to `UNAVAILABLE` automatically (forward_plan §3.1 sub-track 3). Manual override always wins — re-setting `CONFIRMED` after a real fix restarts the streak. Other historical-context items still relevant:

| Ticker | Instrument | Notes |
|---|---|---|
| `IMOEX.ME`, `RTSI.ME` | Russian indices | Data through mid-2022/2024 only (sanctions) |
| `CYB` | WisdomTree Chinese Yuan ETF | Delisted Dec 2023; `CNYB.L` is replacement |
| `DX-Y.NYB` | US Dollar Index | Data only from 2008 |

### Metadata / Label Issues — currently clean

Last full audit against `data/index_library.csv`: 2026-04-21. The previously-flagged items below are all resolved; included here as historical record.

| Ticker | Previously Flagged | Current State |
|---|---|---|
| `^IRX` | Labeled "US 2Y Treasury Yield" | `name = "US 3-Month Treasury Yield"` |
| `^VIX` | Region "Global" | `region = "North America"`, `country_market = "United States"` |
| `^MOVE` | Region blank | `region = "North America"`, `country_market = "United States"` |
| XLE, XLB, XLI, XLK, XLV, XLF, XLU, XLP, XLY, XLRE, IWF | Region "North America" | Unchanged — owner decision: "North America" groups US & Canada deliberately |

### Past Refactors (Resolved)

These items previously tracked active refactoring debt and have all landed. Kept as a brief history; for the broader stage-by-stage rebuild record see `forward_plan.md` §1 (Phase summaries) and §2 priority queue (Completed work block).

| Issue | Resolution |
|---|---|
| Simple-pipeline instrument list hardcoded in three places | Library-driven via `simple_dash` column |
| `PENCE_TICKERS` hardcoded set | Replaced with dynamic `.endswith(".L")` + median > 50 check |
| `broad_asset_class` and `units` computed in code | Read from CSV columns |
| Hardcoded ratio/spread definitions in the comp pipeline | Moved to `compute_macro_market.py` as indicator calculators |
| `build_market_meta_prefix()` used hardcoded lists | Metadata read from instrument dicts populated from library |
| `EU_R1` metadata/code mismatch | CSV and code now both describe BTP-Bund spread |
| `USSLIND` (Philly Fed LEI) stuck at Feb 2020 | Philly Fed discontinued the LEI in 2025; indicator `US_LEI1` removed; series removed from `macro_library_fred.csv` |
| `UMCSE` / `UMCSC` (UMich sub-indices) returned null | UMich sub-indices not published via FRED; both removed; only the headline `UMCSENT` retained |
| OECD `DF_FINMARK` short-term-rate `MEASURE` code wrong | Corrected from `IRST` to `IR3TIB` (3-month interbank rate) in `data/macro_library_oecd.csv` |
| IMF `XM` (Eurozone GDP Growth) returned no data | Eurozone code corrected to `EURO` in `data/macro_library_countries.csv` (IMF DataMapper v1 convention) |
| `INDICATOR_META` Python dict in `compute_macro_market.py` | Moved to `data/macro_indicator_library.csv` (Stage 1, 2026-04-22) |
| Per-source coordinators (`fetch_macro_us_fred.py`, `fetch_macro_international.py`, `fetch_macro_dbnomics.py`, `fetch_macro_ifo.py`) | Consolidated into `fetch_macro_economic.py` + `sources/` package (Stage 2, 2026-04-23) |
| `fetch_supplemental_fred()` Python literal of FRED IDs | Last 7 supplementals moved into `data/macro_library_fred.csv` (2026-04-26); `compute_macro_market.py` now contains zero direct FRED API contact |
| `BAMLEC0A0RMEY` returning persistent FRED HTTP 400 | Series not in the FRED database; row removed; EU_Cr1 returns n/a; new EU_Cr2 covers Euro HY separately (2026-04-27) |
| ECB SDW host retired | Migrated to `data-api.ecb.europa.eu` (PR2, 2026-04-26); date parser fixed for daily YC returns (2026-04-27) |
| 60+ pandas `PerformanceWarning: DataFrame is highly fragmented` per run | `pd.concat(...).copy()` defragmentation in `compute_macro_market.build_hist_df` and the per-source builders (PR3, 2026-04-26 + 2026-04-27 fix-forward) |

### Excluded Indicators (Do Not Implement Without Instruction)

These were evaluated during the Phase D source evaluation and deliberately excluded:

| Indicator | Reason | Proxy Used Instead |
|---|---|---|
| Fed Funds Futures implied path | CME paid subscription | None |
| Goldman Sachs FCI | Proprietary | Chicago Fed NFCI (FRED: NFCI) |
| Bloomberg FCI | Bloomberg terminal required | Chicago Fed NFCI |
| MOVE Index | Bloomberg terminal required | 30-day realised vol on ^TNX (future) |
| JP Morgan Global PMI | S&P Global licence required | Equal-weight ISM + EZ PMI + Japan PMI (Phase D) |
| EM Currencies Index (EMFX) | JP Morgan proprietary | Implemented as `FX_EM1` — basket of CNY/INR/KRW/TWD vs USD |
| China 10Y yield (FRED) | Data quality issues | CNYB.L ETF as proxy |

---

## 14. Operational Notes

### GitHub Actions

- **60-day inactivity pause:** GitHub Actions auto-pauses workflows after 60 days of no pushes to the repo. The daily pipeline produces commits, so this is not currently an issue, but will trigger if the pipeline fails for an extended period. Fix: push a trivial commit or re-enable from the Actions tab.
- **Run timeout:** Currently set to 120 minutes.
- **Pipeline log capture (PR1, 2026-04-25):** the workflow pipes both Python steps through `tee pipeline.log` with `set -o pipefail`; an `if: always()` step then commits `pipeline.log` to the repo on every run alongside the data CSVs and explorer files. Useful for diagnosing failures without needing to download artefacts. The committed log is the artefact the §2.1 verification reads.
- **Permissions:** the workflow has `contents: write` (for git push) plus `issues: write` (added 2026-04-28 for the §2.6 v2 audit-comment posting). No SMTP secrets are required — the daily audit notification uses GitHub's native issue-notification email.

### Daily audit notification flow (§2.6 v2 + §3.1 sub-track 3)

The §2.6 v2 daily audit posts to a perpetual GitHub Issue rather than emailing via SMTP. The §3.1 sub-track 3 writeback adds a registry-update half between the audit and the post. Mechanism:

- **Audit step.** `python data_audit.py` runs after fetch + explorer rebuild. Section A: fetch outcomes from `pipeline.log` scrape. Section B: static checks against the registry CSVs *plus registry drift across all 3 hist↔library pairs* (the drift check imports library_sync helpers — orphan column reports include `(run: python library_sync.py --confirm)`). Section C: value-change staleness against the unified hist. Outputs `data_audit.txt` (full report) + `audit_comment.md` (Issue-comment body with one-line ALL CLEAN / N ISSUES summary).
- **Writeback step.** `python audit_writeback.py` runs immediately after the audit. Parses `data_audit.txt` Section A for `YFINANCE_DEAD` entries, updates `data/yfinance_failure_streaks.csv`, and flips `validation_status` to `UNAVAILABLE` on any row whose streak hits N=14. Appends a one-line summary to `audit_comment.md` so the Issue comment surfaces today's writeback actions. Manual override always wins — re-setting `CONFIRMED` after a real fix restarts the streak naturally on the next FRESH cycle.
- **Posting step.** Uses the pre-installed `gh` CLI:
  1. Ensure a `daily-audit` label exists (`gh label create daily-audit ...`, idempotent).
  2. Find the open issue with that label, or create it on first run with title "Daily Audit Log".
  3. Post `audit_comment.md` as a comment on the issue: `gh issue comment $ISSUE_NUM --body-file audit_comment.md`.
- **Commit step.** The existing "Commit and push if changed" step (`if: always()`) explicitly `git add -f`s `pipeline.log`, `data_audit.txt`, `audit_comment.md`, all data CSVs, the explorer files, plus `data/yfinance_failure_streaks.csv` and `data/index_library.csv` so writeback edits land alongside the daily fetch outputs.
- **User notification.** GitHub's native notification settings email watchers when an issue gains a comment — so the daily comment triggers the alert with no extra infrastructure.
- **Self-healing on overgrowth.** If the comment thread becomes unwieldy, close the issue manually — the next daily run will create a fresh one and resume posting there.
- **First-line summary format.** `audit_comment.md`'s first line is always one of:
  - `## Daily audit — YYYY-MM-DD — **ALL CLEAN**`
  - `## Daily audit — YYYY-MM-DD — **N ISSUES** (X fetch errors, Y static-check failures, Z stale series)`
- **Build-gate behaviour.** Both audit and writeback steps are non-fatal (`exit 0` always); a stale series doesn't fail the workflow. The pipeline is purely a warning channel.

### Google Sheets

- **CDN caching:** GitHub raw CSV URLs cache aggressively. Always use the Sheets export URL with `gid=` parameter for up-to-date data.
- **Tab-state frozensets:** `library_utils.py` exports `SHEETS_PROTECTED_TABS`, `SHEETS_ACTIVE_TABS`, and `SHEETS_LEGACY_TABS_TO_DELETE` (see §6 Tab Map and §9.1). The legacy set is swept on every run by `fetch_data.py::push_to_google_sheets`; the protected set is checked by every writer before any update. To retire a tab, move its title from `SHEETS_ACTIVE_TABS` to `SHEETS_LEGACY_TABS_TO_DELETE` — the next run cleans it up.
- **Spreadsheet ID:** `12nKIUGHz5euDbNQPDTVECsJBNwrceRF1ymsQrIe4_ac` — hardcoded in all 4 active writer modules (`fetch_data.py`, `fetch_hist.py`, `fetch_macro_economic.py`, `compute_macro_market.py`).

### Downstream Consumer: trigger.py

`trigger.py` runs at 06:15 London time on a local Windows machine (`C:\Users\kasim\ClaudeWorkflow\`). It reads only the `market_data` tab (via Sheets CSV export, GID `68683176`). No other tabs are consumed. Changes to macro, history, or indicator tabs do not affect the downstream consumer.

### index_library.csv Maintenance

The library is built and maintained via a separate Claude project at `C:\Users\kasim\OneDrive\Claude\Index Library\build_library.ipynb`. See the `TECHNICAL_MANUAL.md` in that folder for the library build process. To add a new instrument without the library builder, add a row to `data/index_library.csv` with `validation_status = "CONFIRMED"`, verify the ticker, set `base_currency`, and optionally set `simple_dash = True`. Changes take effect on the next pipeline run.

---

*End of Technical Manual*
