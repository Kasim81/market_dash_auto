# Market Dashboard — Technical Manual

> Last updated: 2026-03-30

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

---

## 1. Project Overview

Market Dashboard Auto is a fully automated daily data pipeline that fetches market prices, macro-economic indicators, and composite sentiment/regime signals from free public APIs. Outputs go to:

- **Google Sheets** (primary human-readable output, spreadsheet ID: `12nKIUGHz5euDbNQPDTVECsJBNwrceRF1ymsQrIe4_ac`)
- **CSV files** in `data/` (machine-readable; committed to git by GitHub Actions)

The pipeline runs automatically every day at **06:00 UTC** via GitHub Actions (`python fetch_data.py`).

### Scope at a Glance

| Output | Instruments / Indicators | Frequency | Source |
|---|---|---|---|
| `market_data` | ~70 instruments (simple dashboard) | Daily snapshot | yfinance + FRED |
| `market_data_comp` | ~390 instruments from library | Daily snapshot | yfinance + FRED |
| `market_data_comp_hist` | ~390 instruments from library | Weekly history from 1950 | yfinance + FRED |
| `macro_us` | ~43 US FRED macro series | Daily snapshot | FRED API |
| `macro_us_hist` | ~43 US FRED series | Weekly history from 1947 | FRED API |
| `macro_intl` | 5 indicators x 11 countries | Daily snapshot | OECD + World Bank + IMF + FRED |
| `macro_intl_hist` | 5 indicators x 11 countries | Weekly history from 1960 | OECD + World Bank + IMF + FRED |
| `macro_market` | 57 composite indicators | Weekly snapshot | Derived from above datasets |
| `macro_market_hist` | 57 composite indicators | Weekly history from 2000 | Derived from above datasets |

### Codebase Size

6 Python modules totalling ~5,845 lines, plus 7 CSV configuration libraries and 7 CSV output files.

---

## 2. Directory Structure

```
market_dash_auto/
├── fetch_data.py                  # Master orchestrator — runs all phases (920 lines)
├── fetch_hist.py                  # Historical time series — macro_us + comp (1,062 lines)
├── fetch_macro_us_fred.py         # US FRED macro indicators + surveys (510 lines)
├── fetch_macro_international.py   # International macro — OECD / World Bank / IMF (1,426 lines)
├── compute_macro_market.py        # 57 macro-market composite indicators (1,717 lines)
├── library_utils.py               # Shared sort-order dicts, FX maps, sort key (210 lines)
├── requirements.txt               # Python dependencies
├── README.md
│
├── data/                          # CSV config libraries + pipeline output files
│   ├── index_library.csv              # Instrument master library (~390 rows, 29 columns)
│   ├── level_change_tickers.csv       # Vol tickers using absolute pt change (14 tickers)
│   ├── macro_library_fred.csv         # FRED indicator definitions (46 series)
│   ├── macro_library_oecd.csv         # OECD indicator definitions (3 indicators)
│   ├── macro_library_imf.csv          # IMF indicator definitions (1 indicator)
│   ├── macro_library_worldbank.csv    # World Bank indicator definitions (1 indicator)
│   ├── macro_indicator_library.csv    # 57 macro-market indicator definitions
│   ├── market_data.csv                # OUTPUT — simple-pipeline daily snapshot
│   ├── market_data_comp.csv           # OUTPUT — comp-pipeline daily snapshot
│   ├── market_data_comp_hist.csv      # OUTPUT — comp-pipeline weekly history
│   ├── macro_us.csv                   # OUTPUT — US FRED macro snapshot
│   ├── macro_us_hist.csv              # OUTPUT — US FRED macro weekly history
│   ├── macro_intl.csv                 # OUTPUT — international macro snapshot
│   ├── macro_intl_hist.csv            # OUTPUT — international macro weekly history
│   ├── macro_market.csv               # OUTPUT — macro-market indicator snapshot
│   └── macro_market_hist.csv          # OUTPUT — macro-market indicator weekly history
│
├── docs/                          # Documentation
│   ├── technical_manual.md            # This file
│   └── forward_plan.md                # Forward-looking development roadmap
│
└── .github/workflows/
    └── update_data.yml            # GitHub Actions daily scheduler
```

---

## 3. Execution Flow

GitHub Actions runs `python fetch_data.py` once per day. The file is structured as a sequential chain of `try/except` blocks so that **each phase is fully independent** — a failure in any later phase cannot affect earlier phases.

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
│   │   └─ Deletes legacy tabs: Market Data, sentiment_data, macro_surveys, etc.
│   │
│   └─ (end of main)
│
├─ [try] run_phase_a()                          ← fetch_macro_us_fred → macro_us
│
├─ [try] run_hist()                             ← fetch_hist → macro_us_hist
│
├─ [try] run_phase_c()                          ← fetch_macro_international → macro_intl + macro_intl_hist
│
├─ [try] run_comp_hist()                        ← fetch_hist → market_data_comp_hist
│
└─ [try] run_phase_e()                          ← compute_macro_market → macro_market + macro_market_hist
```

After the Python run, the workflow commits all updated CSVs back to git (on the `main` branch) with message: `Update market data - YYYY-MM-DD HH:MM UTC`.

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

Both pipelines are now library-driven. The simple pipeline reads from `index_library.csv` using the `simple_dash` boolean column to select its subset. Both share the same `collect_comp_assets()` function and FX cache.

### Downstream Consumer

`trigger.py` (a local Windows script at `C:\Users\kasim\ClaudeWorkflow\`) runs at 06:15 London time and reads only the `market_data` tab. History and macro tabs are for manual analysis only.

---

## 5. Data Sources & APIs

### yfinance

- **Library:** `yfinance` Python package (no API key)
- **Used for:** Price history for ~390 instruments (equities, ETFs, FX, commodities, crypto, volatility)
- **Rate limiting:** 0.3s delay between per-ticker fetches
- **Known issues:**
  - Some official index tickers return empty history (STOXX 600 sectors, S&P style indices, TOPIX)
  - Russian tickers have data through mid-2022/mid-2024 only (sanctions)
  - UK `.L` tickers report prices in pence (GBp) — corrected via median > 50 heuristic

### FRED API

- **URL:** `https://api.stlouisfed.org/fred/series/observations`
- **Auth:** `FRED_API_KEY` environment variable (GitHub Secret)
- **Used for:** US macro series (~43), treasury yields, credit spreads, OAS, international yields/confidence indicators
- **Rate limit:** 120 requests/minute per key; pipeline uses 0.6s delay (~100 req/min)
- **Backoff:** Exponential on 429/5xx — 2s, 4s, 8s, 16s, 32s (max 5 retries)

### OECD SDMX REST API

- **URL:** `https://sdmx.oecd.org/public/rest/` (new API, migrated July 2024)
- **Auth:** None required
- **Used for:** Composite Leading Indicator (CLI), Unemployment Rate for 9+ countries
- **Format:** `format=csv`
- **Rate limit:** ~20 calls/hour
- **Known issues:** DF_FINMARK (short-term interest rates) returning no data; EA19 and CHE CLI missing

### World Bank Open Data API

- **URL:** `https://api.worldbank.org/v2/country/{code}/indicator/{indicator}`
- **Auth:** None required
- **Used for:** Annual CPI YoY % (`FP.CPI.TOTL.ZG`) for 11 economies
- **Note:** Eurozone uses code `EMU` (not `EA19`)

### IMF DataMapper REST API

- **URL:** `https://imf.org/external/datamapper/api/`
- **Auth:** None required
- **Used for:** Real GDP Growth % (annual WEO, includes projections)
- **Known issues:** `XM` code (Eurozone) returning no data

### Google Sheets API v4

- **Auth:** Service account JSON in `GOOGLE_CREDENTIALS` environment variable (GitHub Secret)
- **Spreadsheet ID:** `12nKIUGHz5euDbNQPDTVECsJBNwrceRF1ymsQrIe4_ac`
- **Write method:** `spreadsheets().values().update()` with `valueInputOption="USER_ENTERED"`
- **Scopes:** `https://www.googleapis.com/auth/spreadsheets`

### ECB Statistical Data Warehouse

- **URL:** `https://sdw-wsrest.ecb.europa.eu/service/data`
- **Auth:** None required
- **Used for:** Euro IG credit spread (AAA govt 10Y yield) in `compute_macro_market.py`
- **Rate limit:** 2s delay between calls
