# Market Dashboard — Technical Manual

> Last updated: 2026-04-28

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
| `macro_market` | 92 composite indicators | Daily snapshot | Derived from above datasets |
| `macro_market_hist` | 92 composite indicators | Weekly history from 2000 | Derived from above datasets |

### Codebase Size

7 top-level Python modules (incl. `data_audit.py`) + 8-module `sources/` package + `docs/build_html.py`, totalling ~9,400 lines. Configuration: 9 input CSV libraries (1 instrument library + 7 raw-source libraries + 1 composite-indicator library) + `reference_indicators.csv` for the cycle-timing cross-reference + `freshness_thresholds.csv` for the §2.6 audit. Output: 7 data CSVs (one per active Sheets tab) + `pipeline.log` + `data_audit.txt` + `audit_comment.md`.

---

## 2. Directory Structure

```
market_dash_auto/
├── fetch_data.py                  # Master orchestrator — runs all phases (888 lines)
├── fetch_hist.py                  # Comp-pipeline weekly history (769 lines)
├── fetch_macro_economic.py        # Unified raw-macro coordinator (733 lines)
├── compute_macro_market.py        # 92 macro-market composite indicators (2,103 lines)
├── library_utils.py               # Shared sort-order dicts, FX maps, sort key, SHEETS_* tab sets, INDICATOR_CONCEPT_ORDER (347 lines)
├── data_audit.py                  # Daily integrated audit — fetch outcomes + static checks + staleness + registry drift (§2.6 v2; ~666 lines)
├── data_audit.txt                 # OUTPUT — full sorted audit report (regenerated each run)
├── audit_comment.md               # OUTPUT — GitHub Issue comment body posted to perpetual `daily-audit` Issue
├── audit_writeback.py             # Daily writeback half of the audit loop — flips dead-ticker validation_status to UNAVAILABLE after 14d streak (§3.1 sub-track 3; ~230 lines)
├── library_sync.py                # Operator-gated hist↔library prune utility — archives orphan columns then drops them; covers 3 pairs (comp / macro_economic / macro_market) (~363 lines)
├── pipeline.log                   # Captured stdout+stderr of the most recent run (committed by CI)
├── requirements.txt               # Python dependencies
├── README.md
│
├── sources/                       # Per-source raw-macro fetchers (called by fetch_macro_economic.py)
│   ├── __init__.py
│   ├── base.py                        # Shared HTTP/Sheets/CSV plumbing (220 lines)
│   ├── countries.py                   # 12-country code registry (54 lines)
│   ├── fred.py                        # FRED REST API fetcher (370 lines)
│   ├── oecd.py                        # OECD SDMX REST API fetcher (191 lines)
│   ├── worldbank.py                   # World Bank WDI fetcher (193 lines)
│   ├── imf.py                         # IMF DataMapper v1 fetcher (153 lines)
│   ├── dbnomics.py                    # DB.nomics REST API fetcher (180 lines)
│   └── ifo.py                         # ifo Institute Excel-workbook fetcher (344 lines)
│
├── data/                          # CSV config libraries + pipeline output files
│   ├── index_library.csv              # Instrument master library (~390 rows, 29 columns)
│   ├── level_change_tickers.csv       # Vol tickers using absolute pt change (14 tickers)
│   │
│   ├── # Raw-macro source libraries (one per provider, registry-only):
│   ├── macro_library_countries.csv    # 12 country codes + WB/IMF code mappings
│   ├── macro_library_fred.csv         # FRED series IDs (~85 rows)
│   ├── macro_library_oecd.csv         # OECD SDMX dataflow + dimension keys
│   ├── macro_library_worldbank.csv    # World Bank WDI indicator codes
│   ├── macro_library_imf.csv          # IMF DataMapper indicator codes
│   ├── macro_library_dbnomics.csv     # DB.nomics series paths (9 rows)
│   ├── macro_library_ifo.csv          # ifo workbook sheet/column locations (26 rows)
│   │
│   ├── # Phase E composite-indicator registry:
│   ├── macro_indicator_library.csv    # 92 macro-market indicator definitions
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
│   └── macro_market_hist.csv          # OUTPUT — macro-market indicator weekly history
│
├── docs/                          # Indicator Explorer generator
│   ├── build_html.py                  # Generates indicator_explorer.html from CSV + hist (2,683 lines)
│   ├── indicator_explorer.html        # OUTPUT — interactive chart/regime viewer
│   └── indicator_explorer_mkt.js      # OUTPUT — embedded market data JSON
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
│                                                  Internally fans out to sources/{fred,oecd,worldbank,imf,dbnomics,ifo}.py
│                                                  driven by data/macro_library_*.csv per §0 of forward_plan.md
│
└─ [try] run_phase_e()                          ← compute_macro_market  → macro_market + macro_market_hist
                                                   Reads macro_economic_hist + market_data_comp_hist;
                                                   computes 92 composite indicators (z-score, regime, fwd_regime).
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
- **Used for:** ~85 series across yields, inflation, labour, credit, surveys, commodities, OECD-mirror business/consumer confidence; back to 1947 where available. Library: `data/macro_library_fred.csv`.
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
- **Used for:** Open-licensed series not on FRED — currently 9 series: 3 Eurostat economic-sentiment surveys (`EU_ESI`, `EU_IND_CONF`, `EU_SVC_CONF`), 3 ISM series (`ISM_MFG_PMI`, `ISM_MFG_NEWORD`, `ISM_SVC_PMI`), 3 Eurostat real-economy series (`EZ_IND_PROD`, `EZ_RETAIL_VOL`, `EZ_EMPLOYMENT`). Library: `data/macro_library_dbnomics.csv`.
- **Rate limit:** No published cap; pipeline uses a small inter-call delay
- **Fetcher:** `sources/dbnomics.py`

### ifo Institute Excel Workbook

- **URL:** Direct download of the monthly ifo Geschäftsklimaindex Excel workbook from `ifo.de`
- **Auth:** None required
- **Used for:** 26 German business-survey series — Industry+Trade composite plus Manufacturing / Services / Trade / Wholesale / Retail / Construction sub-sectors, plus Uncertainty + Cycle Tracer. History from 1991. Library: `data/macro_library_ifo.csv` (registers each series by sheet index + Excel column).
- **Fetcher:** `sources/ifo.py` (validates the workbook via magic-byte check before parsing)

### Google Sheets API v4

- **Auth:** Service account JSON in `GOOGLE_CREDENTIALS` environment variable (GitHub Secret)
- **Spreadsheet ID:** `12nKIUGHz5euDbNQPDTVECsJBNwrceRF1ymsQrIe4_ac`
- **Write method:** `spreadsheets().values().update()` with `valueInputOption="USER_ENTERED"`
- **Scopes:** `https://www.googleapis.com/auth/spreadsheets`
- **Tab safety:** every writer checks `library_utils.SHEETS_PROTECTED_TABS` before writing; `library_utils.SHEETS_LEGACY_TABS_TO_DELETE` is swept on every run.

### ECB Data Portal

- **URL:** `https://data-api.ecb.europa.eu/service/data` (replaced retired `sdw-wsrest.ecb.europa.eu` host on PR2, 2026-04-26)
- **Auth:** None required
- **Used for:** Euro area AAA govt 10Y yield (YC dataset, key `B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y`) consumed by `fetch_ecb_euro_ig_spread()` in `compute_macro_market.py`. The series is too deeply nested to live in `macro_library_*.csv`, so the SDMX call is inline.
- **Rate limit:** 2s delay between calls
- **Status:** the ECB AAA govt-yield half is wired; the corresponding Euro IG corporate yield half is currently unsourced (see `forward_plan.md` §1 Known Data Gaps), so EU_Cr1 returns n/a until a free corp-yield source is found.

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
| `macro_market` | `compute_macro_market.py` | `data/macro_market.csv` | 92-indicator snapshot (id, group, sub_group, concept, subcategory, category, last_date, raw, zscore, zscore_1w_ago, zscore_4w_ago, zscore_13w_ago, zscore_peak_abs_13w, zscore_trend, regime, fwd_regime, formula_note). `concept` + `subcategory` added 2026-04-28 (§2.4) — drives the explorer's By-Concept sidebar view. |
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
| `index_library.csv` | ~387 | fetch_data.py, fetch_hist.py, compute_macro_market.py | Master instrument registry — tickers, metadata, data source assignments, `simple_dash` flag. 22 dead yfinance tickers retired across 4 batches in §3.1 sub-track 4 (2026-04-28); see `data/removed_tickers.csv` for the per-ticker disposition. |
| `level_change_tickers.csv` | 14 | fetch_data.py | Vol/level tickers that report absolute point change, not % return |
| `macro_library_countries.csv` | 12 | sources/countries.py, docs/build_html.py | 12 country codes (USA, GBR, DEU, FRA, ITA, JPN, CHN, AUS, CAN, CHE, EA19, IND) + canonical / WB / IMF code mappings. Also drives the explorer's "Economic Data" By-Country sidebar grouping + country-filter dropdown (§2.5 v2). |
| `macro_library_fred.csv` | ~82 | sources/fred.py | FRED series IDs (US + international, including 6 supplementals from the 2026-04-26 refactor). 2026-04-27: `BAMLEC0A0RMEY` removed. 2026-04-29: `RSFSXMV` + `CHNPIEATI01GYM` (CHN_PPI) added; bogus `CHNPPIALLMINMEI` corrected to `CHNPIEATI01GYM`; 3 OECD-mirror confidence rows removed (`CSCICP03USM665S` / `BSCICP03USM665S` / `CSCICP03EZM665S`). |
| `macro_library_oecd.csv` | 3 | sources/oecd.py | OECD SDMX dataflow + dimension keys (CLI, unemployment, 3-month rate) |
| `macro_library_worldbank.csv` | 1 | sources/worldbank.py | World Bank WDI indicator codes (CPI YoY) |
| `macro_library_imf.csv` | 1 | sources/imf.py | IMF DataMapper indicator codes (real GDP growth) |
| `macro_library_dbnomics.csv` | 9 | sources/dbnomics.py | DB.nomics series paths (Eurostat ESI/ICI/SCI, ISM PMIs, EZ IP/Retail/Employment) |
| `macro_library_ifo.csv` | 26 | sources/ifo.py | ifo workbook sheet/column locations for the 26 German business-survey series |
| `macro_indicator_library.csv` | 92 | compute_macro_market.py, docs/build_html.py | Phase E composite-indicator registry (id, category, group, sub_group, **concept**, **subcategory**, naturally_leading, formula, interpretation, regime_classification, cycle_timing). `concept` + `subcategory` added 2026-04-28 (§2.4) — populated for all 92 indicators using the canonical 17-concept taxonomy (Equity, Rates / Yields, Credit / Spreads, Inflation, Sentiment / Survey, Leading Indicators, Growth, Labour, Consumer, Housing, Manufacturing, External / Trade, Money / Liquidity, Cross-Asset, FX, Volatility, Momentum). |
| `reference_indicators.csv` | 206 | Reference only (gap audit) | Cross-reference of 206 macro/market indicators from `Macro Market Indicators Reference.docx` with L/C/G cycle timing, match status, and source flags. Not consumed by the runtime pipeline — used to drive `forward_plan.md` §3.4 coverage analysis. |
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
| `macro_market.csv` | ~92 | compute_macro_market.py | Macro-market indicator snapshot |
| `macro_market_hist.csv` | ~1,370 | compute_macro_market.py | Weekly indicator history |
| `pipeline.log` | n/a | GitHub Actions | Captured stdout+stderr of the most recent run (committed by the `if: always()` step in `update_data.yml` — useful for diagnosing failures without needing to download artefacts) |
| `data_audit.txt` | n/a | `data_audit.py` (CI) | Full sorted §2.6 v2 audit report (fetch outcomes + static checks + value-change staleness + registry drift). Regenerated each daily run. |
| `audit_comment.md` | n/a | `data_audit.py` + `audit_writeback.py` (CI) | Markdown body posted to the perpetual `daily-audit` GitHub Issue. First line is the one-sentence ALL CLEAN / N ISSUES summary. `audit_writeback.py` appends a one-line note when streaks are active or rows are flipped to UNAVAILABLE. |
| `data/_archived_columns/*.csv` | per-orphan | `library_sync.py --confirm` | Per-orphan-column historical archives. Filename: `<hist_basename>__<column_id>__<YYYY-MM-DD>.csv`. Created when a row is removed from a library CSV and the operator runs `library_sync.py --confirm` to prune the now-orphan hist column. Preserves full historical observations for future reference. |

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

### 9.1 `library_utils.py` (347 lines)

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

### 9.2 `fetch_data.py` (888 lines)

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

### 9.3 `fetch_hist.py` (769 lines)

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

### 9.4 `fetch_macro_economic.py` (733 lines)

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

Inside `load_all_indicators()`: `countries → fred → oecd → worldbank → imf → dbnomics → ifo`. Each `sources/*.py` exposes `load_library() -> list[dict]` returning the unified indicator schema.

### 9.5 `sources/` package (8 modules, ~1,705 lines total)

**Role:** Per-source data providers. Each submodule exposes a small, consistent interface (library loader + snapshot fetcher + history fetcher) with **no CSV or Sheets side effects** — those live in `fetch_macro_economic.py`.

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

#### 9.5.3 `sources/fred.py` (370 lines)

| Function | Purpose |
|---|---|
| `_load_raw()` | Read `data/macro_library_fred.csv` raw |
| `load_us_library()` / `load_us_library_as_list()` | US-only series (no `country` set) |
| `load_intl_library()` | International series (with `country` set) |
| `validate_series(...)` | Pre-flight check that a FRED series ID resolves |
| `fetch_observations(series_id, …)` | FRED REST call with backoff |
| `parse_observations(data)` | FRED JSON → `list[(date, float)]` |
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

#### 9.5.8 `sources/ifo.py` (344 lines)

| Function | Purpose |
|---|---|
| `load_library()` | Read `data/macro_library_ifo.csv` |
| `_iter_recent_yyyymm(months_back)` / `_candidate_urls()` | Build candidate ifo workbook URLs (latest publication month + fallback months) |
| `_try_download_xlsx(session, url)` | Download + magic-byte validate the workbook (`PK\\x03\\x04` zip header) |
| `resolve_workbook()` / `resolve_workbook_url()` / `download_workbook(url)` | Top-level workbook acquisition with retry across candidate URLs |
| `parse_workbook(xlsx_bytes, indicators)` | Extract every registered series via its `(sheet_index, excel_col)` from `macro_library_ifo.csv` into a wide DataFrame |

### 9.6 `compute_macro_market.py` (2,103 lines)

**Role:** Phase E — 92 composite macro-market indicators with z-scores, regime classifications, forward regime signals, and z-score trend diagnostics.

All indicator metadata is loaded from `macro_indicator_library.csv` at import time — no hardcoded indicator definitions in Python. The CSV is the single source of truth for `id`, `category`, `group`, `sub_group`, `naturally_leading`, `formula_using_library_names`, `economic_interpretation`, `regime_classification`, and `cycle_timing`.

As of the 2026-04-26 supplemental refactor (commit `48c8c1c`) and the 2026-04-27 EU_Cr1 fix-forward, **this module contains zero direct API contact for FRED**. Every FRED series the calculators read is provisioned through the unified `macro_economic_hist` (built by `fetch_macro_economic.py`) and looked up by column name via `_get_col(mu, "<col>")`. The only direct API contact remaining is `fetch_ecb_euro_ig_spread()` (ECB Data Portal — too deeply nested to live in `macro_library_*.csv`) and `fetch_fxi_prices()` (yfinance FXI denominator for `AS_G1`).

#### Indicator Families (92 total)

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

EU_Cr1 currently returns `n/a` until a free Euro IG corporate yield source is wired (see `forward_plan.md` §1 Known Data Gaps); EU_Cr2 (added 2026-04-27) covers the Euro HY regime separately by reading `BAMLHE00EHYIOAS` from the unified hist.

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
| `compute_all_indicators(cp, mu, mi, supp, dbn)` | Orchestrate all 92 indicator calculations under one try/except per indicator |
| `_zscore_trend_classification(z_now, z_1w, z_4w, z_13w, z_peak_abs_13w)` | Classify recent z-score trajectory as `intensifying` (rising in magnitude vs 1w/4w and near the 13-week peak), `fading` (`\|z_now\| < 0.9 × \|z_4w\|`), `reversing` (sign flip vs 4w ago from a prior `\|z\| > 0.5`), or `stable`. |
| `_sample_z(df, offset_weeks)` | Return zscore value `offset_weeks` Friday rows before the last non-null raw row (used to sample 1w/4w/13w history for trend classification). |
| `build_snapshot_df(results)` | One row per indicator: id, group, sub_group, category, last_date, raw, zscore, zscore_1w_ago, zscore_4w_ago, zscore_13w_ago, zscore_peak_abs_13w, zscore_trend, regime, fwd_regime, formula_note |
| `build_hist_df(results)` | One row per date × ~368 columns (92 indicators × 4 values: raw, zscore, regime, fwd_regime). `pd.concat(...).copy()` defragments the wide frame to silence pandas `PerformanceWarning`s in the downstream `reset_index()`. |
| `push_macro_to_google_sheets(df_snapshot, df_hist)` | Write `macro_market` and `macro_market_hist` tabs to Sheets (checks `SHEETS_PROTECTED_TABS`) |
| `run_phase_e()` | **Entry point** — load inputs, compute, save + push |

#### Key Constants

| Constant | Value | Purpose |
|---|---|---|
| `ZSCORE_WINDOW` | 156 | 3-year rolling window for z-scores (weeks) |
| `ZSCORE_MIN_PERIODS` | 52 | 1-year minimum warm-up (weeks) |
| `HIST_START` | `"2000-01-01"` | Start date for the weekly indicator history |
| `_FWD_SLOPE_POS` | +0.15 | Weekly z-score slope threshold for `improving` |
| `_FWD_SLOPE_NEG` | -0.15 | Weekly z-score slope threshold for `deteriorating` |
| `ECB_BASE_URL` | `https://data-api.ecb.europa.eu/service/data` | ECB Data Portal SDMX REST endpoint |
| `INDICATOR_META` | dict | Maps 92 IDs to `(group, sub_group, category, formula_note, concept, subcategory)` — 6-tuple loaded from CSV. `concept` and `subcategory` were added 2026-04-28 (§2.4) and propagate into the `macro_market.csv` snapshot output. |
| `ALL_INDICATOR_IDS` | list | Ordered indicator IDs (CSV row order) |
| `NATURALLY_LEADING` | frozenset | IDs flagged as naturally leading in the CSV |
| `REGIME_RULES` | dict | Maps 92 IDs to regime classification lambdas |
| `_US_CALCULATORS` | dict | US indicator calculator functions |
| `_EU_CALCULATORS` | dict | Europe/UK indicator calculator functions (incl. EU_Cr2) |
| `_ASIA_REGIONAL_CALCULATORS` | dict | Asia/Global/FX indicator calculator functions |
| `_PHASE_D_CALCULATORS` | dict | Survey-derived indicators (ISM, ifo, Eurostat) — historical naming, all now read from the unified hist |
| `_ALL_CALCULATORS` | dict | Merged union of the above four dicts |

### 9.7 `docs/build_html.py` (2,683 lines)

**Role:** Generates the Indicator Explorer — an interactive HTML page for visualising macro-market indicators with regime strips, z-score overlays, and a 3-section sidebar. Reads the freshly-written CSVs at the end of each pipeline run.

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
| `build_macro_economic()` | Single combined payload spanning every raw-macro source (FRED + OECD + WB + IMF + DB.nomics + ifo). Replaces the three retired `build_macro_us` / `build_macro_intl` / `build_macro_survey` builders. |
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

### 9.8 `data_audit.py` (~666 lines)

**Role:** Daily integrated audit that consolidates every "what could go wrong" signal into a single committed report + a GitHub Issue comment that triggers user notification email. Replaces the v1 `freshness_audit.py` (deleted 2026-04-28). See §2.6 of `forward_plan.md` for the design rescope rationale.

Runs as a CI step at the end of `update_data.yml`; never fails the build (warning channel, not gate).

#### Three audit sections

| Section | Purpose | Mechanism |
|---|---|---|
| **A — Fetch outcomes** | Catch broken FRED IDs, dead yfinance tickers, persistent HTTP errors | Scrape `pipeline.log` post-run for known per-series patterns (`HTTP <code> on X — skipping`, `possibly delisted`, `Quote not found for symbol: X`, `Period 'max' is invalid`). Retried-then-recovered transients are filtered out by only matching the `— skipping` suffix. yfinance suspects are cross-checked against the latest non-empty row of `market_data_comp_hist.csv` to filter transient warnings. |
| **B — Static checks** | Catch registry / code drift before it shows up at runtime | Local sanity checks: orphan country codes (every code referenced in `fred` / `oecd` / `dbnomics` / `ifo` libraries exists in `macro_library_countries.csv`); indicator-id uniqueness; calculator registration (every `id` in `macro_indicator_library.csv` is registered as `"<id>": _calc_…` in `compute_macro_market.py`); `_get_col(...)` column existence (every literal in the calculator code resolves to a column in `macro_economic_hist.csv`); **registry drift across all 3 hist↔library pairs** — every column in `market_data_comp_hist.csv` / `macro_economic_hist.csv` / `macro_market_hist.csv` must trace back to a row in its source-of-truth library; orphans report `(run: python library_sync.py --confirm)` for the operator. The drift check imports the expected/present helpers from `library_sync.py` so column-derivation rules (PR/TR fields, OECD/WB/IMF country fan-outs, indicator suffixes) live in one place. |
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
| `section_b_static_checks()` | Run the 4 sub-checks (orphan countries / duplicate ids / missing calculators / missing columns) |
| `section_c_staleness()` | Bucket every series into FRESH / STALE / EXPIRED |
| `render_report(sections)` | Build the plaintext `data_audit.txt` |
| `render_comment(sections)` | Build the GitHub Issue Markdown `audit_comment.md` with first-line summary |
| `main()` | Orchestrate; always returns exit code 0 (warning channel) |

### 9.9 `library_sync.py` (~363 lines)

**Role:** Operator-gated companion to `data_audit.py`'s Section B `registry_drift` check (forward_plan §0 / §3.1). The library CSVs are the source of truth for what the pipeline fetches; this utility keeps the hist files aligned with them after a library row has been edited or removed.

Default mode is dry-run; pass `--confirm` to apply. The `removed_tickers.csv` ledger is **not** updated by this script — that ledger records human edits to source-of-truth library CSVs; this script is the downstream sync action.

#### Three hist↔library pairs

| Pair | Source-of-truth | Hist file | Column-derivation rule |
|---|---|---|---|
| **comp** | `index_library.csv` (PR/TR + ticker_fred_* fields) | `market_data_comp_hist.csv` | row 0 ("Ticker ID") cols 2+; each base ticker appears twice (`_Local` + `_USD`) |
| **macro_economic** | union of `macro_library_{fred,oecd,worldbank,imf,dbnomics,ifo}.csv` | `macro_economic_hist.csv` | FRED/DB.nomics/ifo: `col` (or `series_id` fallback); OECD: `f"{country}_{series_id}"` per `oecd_countries`; WB/IMF: `f"{country}_{col}"` × every code in `macro_library_countries.csv` |
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
| ECB | 2s | 2s, 4s, 8s, 16s, 32s | 5 |

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
| `BLS_API_KEY` | Missing | Not currently needed — may be needed for future BLS integration |
| `FMP_API_KEY` | Exists, reserved for future use | Registered 2026-04-21. **Phase D FMP calendar module deleted 2026-04-23** — economic calendar endpoint paywalled on free tier (`/v3/economic_calendar` → HTTP 403, `/stable/economic-calendar` → HTTP 402). Secret retained for planned PE-ratio integration via `/stable/ratios` endpoint (still free; see `forward_plan.md` §3.9). Survey indicators that the FMP route was originally meant to carry now flow through DB.nomics + ifo via the unified hist (see `forward_plan.md` §3.7 for the source-evaluation verdicts). |

---

## 13. Known Issues & Status

### Data Gaps — see `forward_plan.md` §1

The canonical record of series unavailable from any free source we accept (China 10Y, Euro IG corporate yield, OECD CLI for EA19/CHE, ZEW, JP_PMI1 [au Jibun Bank PMI], CN_PMI2 [Caixin], NAPMOI, CHN_PPI, plus rejected paid sources) lives in **`forward_plan.md` §1 "Known Data Gaps"**. That table is the single source of truth — do not duplicate here. `compute_macro_market.py` calculators silently degrade to `n/a` for any indicator whose underlying series is in the gap list (currently `EU_Cr1`, `AS_CN_R1`, `DE_ZEW1`, `JP_PMI1`, `CN_PMI2`).

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
| Atlanta Fed GDPNow | Web scrape only — no clean API | None |
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
