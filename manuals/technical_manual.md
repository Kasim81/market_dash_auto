# Market Dashboard — Technical Manual

> Last updated: 2026-04-23

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

The pipeline runs automatically every day at **03:17 UTC** via GitHub Actions (`python fetch_data.py` followed by `python docs/build_html.py`). The odd minute avoids GitHub's scheduled-run congestion at the top of the hour; the 03:17 slot ensures the run finishes before the 06:00 UK local automations that consume the data.

### Scope at a Glance

| Output | Instruments / Indicators | Frequency | Source |
|---|---|---|---|
| `market_data` | ~70 instruments (simple dashboard) | Daily snapshot | yfinance + FRED |
| `market_data_comp` | ~390 instruments from library | Daily snapshot | yfinance + FRED |
| `market_data_comp_hist` | ~390 instruments from library | Weekly history from 1950 | yfinance + FRED |
| `macro_us` | ~42 US FRED macro series | Daily snapshot | FRED API |
| `macro_us_hist` | ~42 US FRED series | Weekly history from 1947 | FRED API |
| `macro_intl` | 5 indicators x 11 countries | Daily snapshot | OECD + World Bank + IMF + FRED |
| `macro_intl_hist` | 5 indicators x 11 countries | Weekly history from 1960 | OECD + World Bank + IMF + FRED |
| `macro_market` | 91 composite indicators | Weekly snapshot | Derived from above datasets |
| `macro_market_hist` | 91 composite indicators | Weekly history from 2000 | Derived from above datasets |

### Codebase Size

7 Python modules totalling ~8,452 lines, plus 7 CSV configuration libraries and 7 CSV output files.

---

## 2. Directory Structure

```
market_dash_auto/
├── fetch_data.py                  # Master orchestrator — runs all phases (920 lines)
├── fetch_hist.py                  # Historical time series — macro_us + comp (1,062 lines)
├── fetch_macro_us_fred.py         # US FRED macro indicators + surveys (510 lines)
├── fetch_macro_international.py   # International macro — OECD / World Bank / IMF (1,426 lines)
├── compute_macro_market.py        # 91 macro-market composite indicators (1,967 lines)
├── library_utils.py               # Shared sort-order dicts, FX maps, sort key (271 lines)
├── requirements.txt               # Python dependencies
├── README.md
│
├── data/                          # CSV config libraries + pipeline output files
│   ├── index_library.csv              # Instrument master library (~390 rows, 29 columns)
│   ├── level_change_tickers.csv       # Vol tickers using absolute pt change (14 tickers)
│   ├── macro_library_fred.csv         # FRED indicator definitions (45 series)
│   ├── macro_library_oecd.csv         # OECD indicator definitions (3 indicators)
│   ├── macro_library_imf.csv          # IMF indicator definitions (1 indicator)
│   ├── macro_library_worldbank.csv    # World Bank indicator definitions (1 indicator)
│   ├── macro_indicator_library.csv    # 91 macro-market indicator definitions
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
├── docs/                          # Indicator Explorer generator
│   ├── build_html.py                  # Generates indicator_explorer.html from CSV + hist (2,296 lines)
│   ├── indicator_explorer.html        # OUTPUT — interactive chart/regime viewer
│   └── indicator_explorer_mkt.js      # OUTPUT — embedded market data JSON
│
├── manuals/                       # Documentation
│   ├── technical_manual.md            # This file
│   ├── forward_plan.md                # Forward-looking development roadmap
│   ├── indicator_manual.md            # Indicator-by-indicator reference
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
    └── update_data.yml            # GitHub Actions daily scheduler (+ builds indicator_explorer.html)
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

After `fetch_data.py` finishes, the workflow runs `python docs/build_html.py` to rebuild the Indicator Explorer (`docs/indicator_explorer.html` + `docs/indicator_explorer_mkt.js`) from the freshly updated CSVs. All updated CSVs and the two explorer files are then committed back to git (on the `main` branch) with message: `Update market data + explorer - YYYY-MM-DD HH:MM UTC`.

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

---

## 6. Google Sheets Tab Map

All tabs live in a single spreadsheet (`12nKIUGHz5euDbNQPDTVECsJBNwrceRF1ymsQrIe4_ac`).

| Tab Name | Written By | CSV Mirror | Contents |
|---|---|---|---|
| `market_data` | `fetch_data.py` | `data/market_data.csv` | ~70 simple-pipeline instruments, daily snapshot |
| `market_data_comp` | `fetch_data.py` | `data/market_data_comp.csv` | ~390 comp-pipeline instruments, daily snapshot |
| `market_data_comp_hist` | `fetch_hist.py` | `data/market_data_comp_hist.csv` | Weekly comp prices from 1950 |
| `macro_us` | `fetch_macro_us_fred.py` | `data/macro_us.csv` | ~42 US FRED series snapshot |
| `macro_us_hist` | `fetch_hist.py` | `data/macro_us_hist.csv` | Weekly FRED history from 1947 |
| `macro_intl` | `fetch_macro_international.py` | `data/macro_intl.csv` | 11-country macro snapshot |
| `macro_intl_hist` | `fetch_macro_international.py` | `data/macro_intl_hist.csv` | Weekly international history from 1960 |
| `macro_market` | `compute_macro_market.py` | `data/macro_market.csv` | 91-indicator snapshot (id, group, sub_group, category, last_date, raw, zscore, zscore_1w_ago, zscore_4w_ago, zscore_13w_ago, zscore_peak_abs_13w, zscore_trend, regime, fwd_regime, formula_note) |
| `macro_market_hist` | `compute_macro_market.py` | `data/macro_market_hist.csv` | Weekly indicator history from 2000 |

### Legacy Tabs (Auto-Deleted)

The following tabs are automatically deleted on every run by `fetch_data.py` if they exist:

| Tab | Reason |
|---|---|
| `Market Data` (with space) | Duplicate created by Apps Script; replaced by `market_data` |
| `sentiment_data` | Content consolidated into `macro_us` + `macro_intl` |
| `macro_surveys` | Content consolidated into `macro_us` |
| `macro_surveys_hist` | Content consolidated into `macro_us_hist` |
| `market_data_hist` | Simple-pipeline history removed; superseded by `market_data_comp_hist` |

### Downstream Consumer

`trigger.py` reads only `market_data` via CSV export URL:
```
https://docs.google.com/spreadsheets/d/12nKIUGHz5euDbNQPDTVECsJBNwrceRF1ymsQrIe4_ac/export?format=csv&gid=68683176
```

---

## 7. CSV File Inventory

### Configuration Libraries (input — read by Python, never overwritten)

| File | Rows | Consumed By | Purpose |
|---|---|---|---|
| `index_library.csv` | 390 | fetch_data.py, fetch_hist.py, compute_macro_market.py | Master instrument registry — tickers, metadata, data source assignments |
| `level_change_tickers.csv` | 14 | fetch_data.py | Vol/level tickers that report absolute point change, not % return |
| `macro_library_fred.csv` | 45 | fetch_macro_us_fred.py, fetch_macro_international.py | FRED series definitions (US + international) |
| `macro_library_oecd.csv` | 3 | fetch_macro_international.py | OECD indicator definitions (CLI, unemployment) |
| `macro_library_worldbank.csv` | 1 | fetch_macro_international.py | World Bank indicator definition (CPI) |
| `macro_library_imf.csv` | 1 | fetch_macro_international.py | IMF indicator definition (GDP growth) |
| `macro_indicator_library.csv` | 91 | compute_macro_market.py, docs/build_html.py | Macro-market indicator definitions (id, category, group, sub_group, naturally_leading, formula, interpretation, regime_classification, cycle_timing) |
| `macro_library_dbnomics.csv` | 3 | fetch_macro_dbnomics.py | DB.nomics/Eurostat series definitions (ESI, Industry Confidence, Services Confidence) |
| `reference_indicators.csv` | 206 | Reference only | Cross-reference of 206 macro/market indicators from reference document with L/C/G cycle timing, match status, and source flags |

### Pipeline Outputs (generated daily by Python, committed to git)

| File | Rows | Written By | Content |
|---|---|---|---|
| `market_data.csv` | ~76 | fetch_data.py | Simple-pipeline daily snapshot |
| `market_data_comp.csv` | ~360 | fetch_data.py | Comp-pipeline daily snapshot |
| `market_data_comp_hist.csv` | ~3,990 | fetch_hist.py | Weekly prices, 10 metadata prefix rows + data |
| `macro_us.csv` | ~44 | fetch_macro_us_fred.py | US FRED macro snapshot |
| `macro_us_hist.csv` | ~4,144 | fetch_hist.py | Weekly FRED history, 8 metadata prefix rows + data |
| `macro_intl.csv` | ~59 | fetch_macro_international.py | International macro snapshot |
| `macro_intl_hist.csv` | ~3,466 | fetch_macro_international.py | Weekly international history, 8 metadata prefix rows + data |
| `macro_market.csv` | ~91 | compute_macro_market.py | Macro-market indicator snapshot |
| `macro_market_hist.csv` | ~1,370 | compute_macro_market.py | Weekly indicator history |

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

### 9.1 `library_utils.py` (271 lines)

**Role:** Shared constants and helpers — single authoritative source for sort logic and FX maps.

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
| `COMP_FX_TICKERS` | dict | Currency code -> yfinance ticker (18 currencies) |
| `COMP_FCY_PER_USD` | set | Indirect-quote currencies (JPY, CNY, INR, etc.) — divide by FX rate |
| `lib_sort_key(row)` | function | Returns sort tuple from instrument dict for consistent ordering; Industry Groups/Industries sorted by GICS ticker code |

### 9.2 `fetch_data.py` (920 lines)

**Role:** Master orchestrator + both snapshot pipelines (simple + comp).

#### Key Functions

| Function | Purpose |
|---|---|
| `build_comp_fx_cache()` | Pre-fetch FX rate histories for all 18 COMP_FX_TICKERS |
| `load_simple_library()` | Read library, filter to `simple_dash=True` + `CONFIRMED` |
| `load_instrument_library()` | Read library, filter to `CONFIRMED`, sort by `lib_sort_key` |
| `collect_comp_assets(instruments, fx_cache)` | Fetch yfinance prices, compute 1W/1M/3M/6M/YTD/1Y returns in local + USD |
| `collect_simple_fred_assets()` | Fetch FRED-sourced instruments for simple pipeline |
| `collect_comp_fred_assets()` | Fetch FRED yields, spreads, OAS for comp pipeline |
| `_build_library_df(yf_rows, fred_rows)` | Combine yfinance + FRED rows into output DataFrame |
| `push_to_google_sheets(df_main, df_comp)` | Write both tabs to Sheets; delete legacy tabs |
| `main()` | Entry point — runs simple + comp pipelines, then phases A-E |

#### Key Constants

| Constant | Source | Purpose |
|---|---|---|
| `LIBRARY_PATH` | Computed | Absolute path to `data/index_library.csv` |
| `COMP_LEVEL_CHANGE_TICKERS` | `data/level_change_tickers.csv` | Vol tickers using absolute point change (with hardcoded fallback) |
| `COMP_FX_TICKERS` | `library_utils.py` | 18 FX pairs for USD conversion |
| `COMP_FCY_PER_USD` | `library_utils.py` | Indirect-quote currency set |
| `TABS_TO_DELETE` | Hardcoded set | Legacy tabs cleaned up on every run |

### 9.3 `fetch_macro_us_fred.py` (510 lines)

**Role:** Phase A — US macro FRED indicators (snapshot).

The indicator registry is loaded from `data/macro_library_fred.csv` at import time. The exported `FRED_MACRO_US` dict is imported by `fetch_hist.py` for building history.

#### Key Functions

| Function | Purpose |
|---|---|
| `_load_fred_us_library()` | Load `macro_library_fred.csv`, return US-only series as dicts |
| `fred_fetch_with_backoff(series_id, api_key)` | Fetch single FRED series with exponential backoff |
| `fetch_macro_us()` | Fetch all ~42 US FRED series, compute latest/prior/change |
| `save_csv(df)` | Save to `data/macro_us.csv` (diff-check: skip if unchanged) |
| `push_macro_us_to_sheets(df)` | Push to Google Sheets `macro_us` tab |
| `run_phase_a()` | **Entry point** — validate, fetch, save, push |

#### FRED Series Categories (42 total)

| Category | Example Series |
|---|---|
| Growth / Yield Curve | T10Y2Y, T10Y3M |
| Growth / Money Supply | M2SL |
| Growth / Leading | PERMIT |
| Growth / Labour | IC4WSA, PAYEMS, UNRATE |
| Growth / Activity | INDPRO, RSXFS |
| Growth / Credit | DRTSCILM (SLOOS C&I), STDSOTHCONS, SUBLPDRCSN |
| Financial Conditions | NFCI |
| Inflation | CPIAUCSL, CPILFESL, PCEPILFE, PPIACO, T10YIE |
| Monetary Policy | DFEDTARU, WRESBAL |
| Sentiment / Surveys | UMCSENT |
| Regional Fed | GACDFSA066MSFRBPHI (Philly), MFRBSCOMP (Richmond), KCACTMFG (Kansas City) |

### 9.4 `fetch_hist.py` (1,062 lines)

**Role:** All historical time series — `macro_us_hist` and `market_data_comp_hist`.

#### Key Functions

| Function | Purpose |
|---|---|
| `get_friday_spine(start_str, end_date)` | Generate weekly Friday DatetimeIndex |
| `align_to_friday_spine(series, spine)` | Reindex + forward-fill to Friday spine |
| `fred_fetch_series_full(series_id, start)` | Fetch complete FRED series with backoff |
| `build_macro_hist_df(spine)` | Build macro_us_hist by fetching all FRED series |
| `build_macro_meta_prefix(df)` | Build 8 metadata prefix rows for macro_us_hist |
| `run_hist()` | **Entry point A** — build + push macro_us_hist |
| `load_comp_instruments()` | Load comp instruments from library |
| `load_comp_fred_rates()` | Load FRED rate series for comp pipeline |
| `fetch_comp_fx_cache(start)` | Pre-fetch FX histories for comp USD conversion |
| `compute_comp_usd_series(local, ccy, fx_cache, fcy_per_usd)` | Convert local prices to USD |
| `fetch_comp_yfinance_history(instruments, start, fx_cache)` | Fetch all yfinance histories |
| `fetch_comp_fred_rates_history(rates, start)` | Fetch all FRED rate histories |
| `build_comp_market_hist_df(yf_data, fred_data, spine)` | Combine + align to Friday spine |
| `build_comp_market_meta_prefix(df, instruments, rates)` | Build 10 metadata prefix rows |
| `run_comp_hist()` | **Entry point B** — build + push market_data_comp_hist |

#### Key Constants

| Constant | Value | Purpose |
|---|---|---|
| `MACRO_HIST_START` | `"1947-01-01"` | Floor date for FRED macro history |
| `COMP_HIST_START` | `"1950-01-01"` | Floor date for comp market history |
| `YFINANCE_DELAY` | 0.3s | Delay between yfinance calls |
| `FRED_DELAY` | 0.6s | Delay between FRED calls |

#### Historical Output Format

- **Rows** = dates (weekly Friday close)
- **Columns** = instruments (local currency first, then USD)
- **Metadata prefix rows** (in Sheets tabs, not in CSVs): ticker ID, variant, source, name, broad asset class, region, sub-category, currency, units, frequency — then column header row, then data

### 9.5 `fetch_macro_international.py` (1,426 lines)

**Role:** Phase C — International macro for 11 economies.

#### Countries Covered

`AUS, CAN, CHE, CHN, DEU, EA19, FRA, GBR, ITA, JPN, USA`

(`EA19` = Eurozone. `CHN` and `EA19` have partial coverage.)

#### Indicators

| Indicator | Source | Frequency | Known Issues |
|---|---|---|---|
| Composite Leading Indicator (CLI) | OECD | Monthly | EA19 and CHE missing |
| Unemployment Rate | OECD | Monthly | CHN, EA19 not published |
| Short-term Interest Rate (3M) | OECD | Monthly | **Returning no data for all countries** |
| CPI Headline YoY % | World Bank | Annual | EA19 uses WB code `EMU` |
| Real GDP Growth % | IMF | Annual | EA19 (`XM` code) returning no data |

#### Key Functions

| Function | Purpose |
|---|---|
| `_load_oecd_indicators()` | Load OECD indicators from `macro_library_oecd.csv` |
| `_load_wb_indicators()` | Load World Bank indicators from `macro_library_worldbank.csv` |
| `_load_imf_indicators()` | Load IMF indicators from `macro_library_imf.csv` |
| `_load_fred_intl_indicators()` | Load international FRED series from `macro_library_fred.csv` |
| `build_snapshot(...)` | Build snapshot DataFrame (one row per country x indicator) |
| `build_history(...)` | Build history DataFrame on Friday spine |
| `run_phase_c()` | **Entry point** — validate, fetch, build snapshot + history, save + push |

#### Rate Limiting

| Source | Delay | Notes |
|---|---|---|
| OECD | 4s | Max ~20 calls/hour; module makes ~6 calls per run |
| World Bank | 1s | Generous limits |
| IMF | 1s | Full history in single call |
| FRED (intl) | 0.6s | Same as US FRED |

### 9.6 `compute_macro_market.py` (1,967 lines)

**Role:** Phase E — 91 composite macro-market indicators with z-scores, regime classifications, and forward regime signals.

All indicator metadata is loaded from `macro_indicator_library.csv` at import time — no hardcoded indicator definitions in Python. The CSV is the single source of truth for group, sub_group, category, formula description, and naturally_leading flag.

#### Indicator Families (91 total)

| Group | Sub-group(s) | IDs | Description |
|---|---|---|---|
| US | Equity - Growth | US_G1, US_G2, US_G3, US_G5, US_G4 | Cyclicals vs defensives, banks vs utilities, tech leadership, breadth |
| US | Equity - Factor | US_EQ_F1, US_EQ_F2, US_EQ_F3, US_EQ_F4 | Value/growth and size (Russell, S&P) |
| US | Rates | US_R1, US_R2, US_R3, US_R4, US_R5, US_R6 | Yield curve slopes, breakeven inflation, real yields, mortgage spread |
| US | Credit | US_Cr1, US_Cr2, US_Cr3, US_Cr4 | IG spread, HY spread (5-regime), HY-IG, HY vs Treasuries |
| US | CrossAsset - Growth | US_CA_G1 | SPY vs GOVT risk-on/off |
| US | Volatility | US_V1, US_V2 | VIX term structure, MOVE/VIX |
| US | Momentum | M1–M5 | Trend, dual momentum, HY momentum, vol-filtered |
| US | Macro / Survey | US_JOBS1, US_JOBS2, US_JOBS3, US_G6, US_HOUS1, US_M2, US_ISM1 | Labour, activity, housing, M2, ISM |
| Europe | Equity - Growth / Credit | EU_G1, EU_G2, EU_G3, EU_G4, EU_Cr1, EU_R1 | European cyclicals, credit, BTP-Bund |
| UK | Equity / Rates / Credit | UK_G1, UK_R1, UK_R2, UK_Cr1 | UK domestic, gilts, breakeven, credit |
| Japan | Equity - Growth | JP_G1 | Japan vs global equities |
| Asia | China / India | AS_CN_G1, AS_CN_G2, AS_CN_G3, AS_IN_G1, AS_CN_R1, AS_IN_R1 | Size, growth, rates |
| Global | CrossAsset / CLI | GL_CA_I1, GL_G1, GL_G2, GL_CLI1, GL_CLI2, GL_CLI5, EU_CLI1, AS_CLI1 | Risk appetite, EM vs DM, CLI differentials/breadth |
| FX & Commodities | Various | FX_CMD1–FX_CMD6, FX_CN1, FX_1, FX_2 | Copper/gold, dollar, iron ore, commodity momentum, FX momentum |

#### How Each Indicator Works

Each indicator goes through:
1. **Calculator function** (`_calc_US_G1`, etc.) — computes raw weekly series from input data
2. **Rolling z-score** — 156-week window (3 years), 52-week minimum warm-up
3. **Regime classification** — discrete label based on z-score thresholds and/or raw value thresholds (via `REGIME_RULES` lambdas)
4. **Forward regime** — slope of z-score over trailing 8 weeks classifies as "improving", "stable", or "deteriorating"; indicators flagged as `naturally_leading` in the CSV receive a "[leading]" suffix

#### Key Functions

| Function | Purpose |
|---|---|
| `_load_indicator_library()` | Load `macro_indicator_library.csv` → `INDICATOR_META`, `ALL_INDICATOR_IDS`, `NATURALLY_LEADING` |
| `load_comp_hist()` | Load `market_data_comp_hist.csv` (weekly prices) |
| `load_macro_us_hist()` | Load `macro_us_hist.csv` (skip 8 metadata rows) |
| `load_macro_intl_hist()` | Load `macro_intl_hist.csv` (skip metadata rows) |
| `fetch_supplemental_fred()` | Fetch FRED series not in macro_us_hist (iron ore, Euro HY OAS, intl yields, DGS10, etc.) |
| `fetch_ecb_euro_ig_spread()` | ECB Euro IG credit spread (with FRED fallback) |
| `fetch_fxi_prices()` | yfinance FXI (China Large-Cap ETF) |
| `_log_ratio(num, den)` | `log(num / den)` — primary indicator calculation |
| `_arith_diff(a, b)` | `a - b` — for yield curve spreads |
| `_sum_log_ratio(nums, dens)` | Average of multiple log-ratios — composite indicators |
| `_rolling_zscore(series)` | Rolling z-score (156w window, 52w min) |
| `_classify_fwd_regime(z, is_leading)` | Forward regime from trailing 8-week z-score slope |
| `compute_all_indicators(cp, mu, mi, supp)` | Orchestrate all 91 indicator calculations |
| `build_snapshot_df(results)` | One row per indicator: id, group, sub_group, category, last_date, raw, zscore, zscore_1w_ago, zscore_4w_ago, zscore_13w_ago, zscore_peak_abs_13w, zscore_trend, regime, fwd_regime, formula_note |
| `_zscore_trend_classification(z_now, z_1w, z_4w, z_13w, z_peak_abs_13w)` | Classify recent z-score trajectory as `intensifying` (rising in magnitude vs 1w/4w and near the 13-week peak), `fading` (`\|z_now\| < 0.9 × \|z_4w\|`), `reversing` (sign flip vs 4w ago from a prior `\|z\| > 0.5`), or `stable`. |
| `_sample_z(df, offset_weeks)` | Return zscore value `offset_weeks` Friday rows before the last non-null raw row (used to sample 1w/4w/13w history for trend classification). |
| `build_hist_df(results)` | One row per date × 364 columns (91 indicators × 4 values: raw, zscore, regime, fwd_regime) |
| `push_macro_to_google_sheets(df_snapshot, df_hist)` | Write `macro_market` and `macro_market_hist` tabs to Sheets |
| `run_phase_e()` | **Entry point** — load inputs, compute, save + push |

#### Key Constants

| Constant | Value | Purpose |
|---|---|---|
| `ZSCORE_WINDOW` | 156 | 3-year rolling window for z-scores (weeks) |
| `ZSCORE_MIN_PERIODS` | 52 | 1-year minimum warm-up (weeks) |
| `HIST_START` | `"2000-01-01"` | Start date for weekly spine |
| `_FWD_SLOPE_POS` | +0.15 | Weekly z-score slope threshold for "improving" |
| `_FWD_SLOPE_NEG` | -0.15 | Weekly z-score slope threshold for "deteriorating" |
| `INDICATOR_META` | dict | Maps 91 IDs to `(group, sub_group, category, formula_note)` — loaded from CSV |
| `ALL_INDICATOR_IDS` | list | Ordered indicator IDs (CSV row order) |
| `NATURALLY_LEADING` | frozenset | IDs flagged as naturally leading in the CSV |
| `REGIME_RULES` | dict | Maps 91 IDs to regime classification lambdas |
| `_US_CALCULATORS` | dict | US indicator calculator functions |
| `_EU_CALCULATORS` | dict | Europe/UK indicator calculator functions |
| `_ASIA_REGIONAL_CALCULATORS` | dict | Asia/Global/FX indicator calculator functions |
| `_ALL_CALCULATORS` | dict | Merged union of the above three dicts |

### 9.7 `docs/build_html.py` (2,296 lines)

**Role:** Generates the Indicator Explorer — an interactive HTML page for visualising macro-market indicators with regime strips, z-score overlays, and a nested sidebar.

#### Key Functions

| Function | Purpose |
|---|---|
| `load_indicator_library()` | Load `macro_indicator_library.csv` → dict keyed by ID with category, group, sub_group, formula, interpretation, regime description, leading flag, cycle_timing (L/C/G) |
| `build_macro_market(ind_meta)` | Load `macro_market_hist.csv`, extract time series per indicator |
| `build_html(ind_meta, macro_data)` | Generate complete HTML with embedded JS/CSS |

#### Notable Features

- **3-level sidebar:** group → sub_group → indicator (CSS classes `.grp-section`, `.sgrp-section`)
- **4-colour regime palette:** positive (green), negative (red), amber (gold), neutral (grey) — each maps a set of regime labels
- **Forward regime display:** `fwd_regime` shown as a coloured badge alongside current regime
- **Custom PNG snapshot:** Camera button composites chart title, Plotly chart image, legend entries, and regime colour key onto a single canvas
- **Cycle timing badges:** L/C/G badges in sidebar (blue=Leading, amber=Coincident, red=Lagging) with tooltip for full label
- **Search filter:** Live search that hides/shows group and sub-group sections dynamically

#### Output Files

- `docs/indicator_explorer.html` — self-contained HTML (committed to git)
- `docs/indicator_explorer_mkt.js` — embedded market data JSON (committed to git)

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
    from fetch_hist import run_hist
    run_hist()
except Exception as _hist_err:
    print(f"[Hist] Non-fatal import/run error: {_hist_err}")
```

If Phase C crashes, `market_data`, `market_data_comp`, and `macro_us` are already written and safe. Each phase runs independently.

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

- `macro_us_hist`: 8 prefix rows (Series ID, Source, Name, Category, Subcategory, Units, Frequency, Last Updated)
- `market_data_comp_hist`: 10 prefix rows (Ticker ID, Variant, Source, Name, Broad Asset Class, Region, Sub-Category, Currency, Units, Frequency)

The CSVs include these prefix rows. Code that reads them back must skip the appropriate number of header rows (e.g. `pd.read_csv(..., header=N)`).

### Pattern 5: Library-Driven Configuration

Both pipelines read everything from `index_library.csv` at runtime:

- Adding/removing instruments only requires editing the CSV
- `validation_status = "CONFIRMED"` is the gate — set to `"PENDING"` to disable without deleting
- `simple_dash = True/False` controls simple pipeline inclusion
- `broad_asset_class` and `units` are read from CSV, not computed in code

Similarly, FRED series definitions live in `macro_library_fred.csv`, OECD/WB/IMF definitions in their respective CSVs, and macro-market indicator definitions in `macro_indicator_library.csv`. The indicator library CSV drives both `compute_macro_market.py` (metadata, grouping, naturally_leading flag) and `docs/build_html.py` (sidebar hierarchy, category, economic interpretation, regime descriptions).

### Pattern 6: Diff-Check CSV Commits

Output CSVs are only committed to git if content actually changed. This avoids noisy daily commits on weekends when markets are closed and data hasn't changed.

### Pattern 7: Google Sheets Write Pattern

All modules follow the same pattern:

1. Ensure tab exists (create via `batchUpdate addSheet` if absent)
2. Clear entire range (`sheets.values().clear()`)
3. Write header + data (`sheets.values().update()` with `valueInputOption="USER_ENTERED"`)
4. NaN values converted to empty string before push (never write `"nan"` strings)
5. Protected tab guard: legacy tabs (`market_data`, `sentiment_data`) are never overwritten by new phases

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
| `FRED_API_KEY` | GitHub Secret | fetch_data.py, fetch_macro_us_fred.py, fetch_hist.py, fetch_macro_international.py, compute_macro_market.py |
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
python fetch_macro_us_fred.py       # Phase A only
python fetch_hist.py                # Historical only (requires FRED_MACRO_US from Phase A import)
python fetch_macro_international.py # Phase C only
python compute_macro_market.py      # Phase E only (requires hist CSVs to exist)
```

### GitHub Actions

- **Schedule:** Daily at 03:17 UTC (cron `17 3 * * *`) — the odd minute avoids GitHub's scheduled-run congestion at the top of the hour; this slot ensures the run finishes before the 06:00 UK local automations that consume the data
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
| `FMP_API_KEY` | Exists | Registered 2026-04-21; used by Phase D FMP calendar module (`fetch_macro_fmp.py`) for ISM + S&P Global PMIs |

---

## 13. Known Issues & Status

### Currently Broken / Returning No Data

| Issue | Module | Notes |
|---|---|---|
| OECD EA19 and CHE CLI missing | fetch_macro_international.py | Structural — OECD doesn't publish these |

### Recently Fixed (pending first post-fix run to confirm)

| Issue | Module | Fix |
|---|---|---|
| OECD `DF_FINMARK` short-term interest rates returned zero data | `data/macro_library_oecd.csv` | `MEASURE` code corrected from `IRST` to `IR3TIB` (3-month interbank rate) — fixed 2026-04-21 |
| IMF `XM` (Eurozone GDP Growth) returned no data | `fetch_macro_international.py` | `IMF_CODE_MAP` updated: IMF DataMapper v1 API uses `EURO` for the Euro Area — fixed 2026-04-21 |
| `UMCSE` & `UMCSC` (UMich sub-indices) returned null | `data/macro_library_fred.csv`, `data/macro_us_hist.csv` | Not valid FRED series IDs — the UMich sub-indices (Expectations, Current Conditions) are not published via FRED; only the headline `UMCSENT` is. Both removed — fixed 2026-04-21 |
| `^VIX` and `^MOVE` had blank `region` | `data/index_library.csv` | Set `region = "North America"`, `country_market = "United States"` — fixed 2026-04-21 |

### Resolved / Removed

| Issue | Resolution |
|---|---|
| EU_R1 metadata/code mismatch | Fixed during indicator groups review — CSV and code now both describe BTP-Bund spread |
| USSLIND (LEI) stale data | FRED series stuck at Feb 2020 value — Philadelphia Fed permanently discontinued the Leading Economic Index in 2025. Indicator `US_LEI1` removed; USSLIND removed from `macro_library_fred.csv` |

### Tickers Confirmed Unavailable via yfinance

| Ticker | Instrument | Reason |
|---|---|---|
| `^SXEP`, `^SXKP`, `^SX3P`, etc. | STOXX 600 sectors | yfinance doesn't serve STOXX sector index history |
| `^IVX`, `^IGX` | S&P style indices | Not served via yfinance |
| `^SML`, `^SP500-10`, `^SP500-20` | S&P size/sector | Not served via yfinance |
| `^TX60` | S&P/TSX 60 | Not served via yfinance |
| `^TOPX` | TOPIX (Japan) | Not served via yfinance |
| `IMOEX.ME`, `RTSI.ME` | Russian indices | Data through mid-2022/2024 only (sanctions) |
| `CYB` | WisdomTree Chinese Yuan ETF | Delisted Dec 2023; `CNYB.L` is replacement |
| `DX-Y.NYB` | US Dollar Index | Data only from 2008 |

### Metadata / Label Issues

Status verified against `data/index_library.csv` on 2026-04-23.

| Ticker | Previously Flagged | Current State | Action |
|---|---|---|---|
| `^IRX` | Labeled "US 2Y Treasury Yield" | `name = "US 3-Month Treasury Yield"` | Already fixed |
| `^VIX` | Region "Global" | `region = "North America"`, `country_market = "United States"` | Fixed 2026-04-21 |
| `^MOVE` | Region blank | `region = "North America"`, `country_market = "United States"` | Fixed 2026-04-21 |
| XLE, XLB, XLI, XLK, XLV, XLF, XLU, XLP, XLY, XLRE, IWF | Region "North America" | Unchanged | No change — owner decision: "North America" groups US & Canada deliberately |

### Remaining Redundancy Items

These are lower-severity structural issues documented in `METADATA_REDUNDANCY_REVIEW.md` (2026-03-20). Items 1, 2, 5, 6, 7, 9 have been resolved. Remaining:

| # | Issue | Current State |
|---|---|---|
| 3 | Simple pipeline instrument list was hardcoded 3x | Resolved — now library-driven via `simple_dash` column |
| 4 | `PENCE_TICKERS` hardcoded set | Resolved — replaced with dynamic `.endsWith(".L")` + median check |
| 8 | "Broad Asset Class" computed in code | Resolved — now read from `broad_asset_class` CSV column |
| 10 | Ratio/spread definitions hardcoded in comp pipeline | Resolved — moved to `compute_macro_market.py` as indicator functions |
| 11 | `_ac_units` mapping hardcoded | Resolved — now read from `units` CSV column |
| 12 | `build_market_meta_prefix()` used hardcoded lists | Resolved — metadata now read from instrument dicts populated from library |

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

### Google Sheets

- **CDN caching:** GitHub raw CSV URLs cache aggressively. Always use the Sheets export URL with `gid=` parameter for up-to-date data.
- **Legacy tab cleanup:** `SHEETS_LEGACY_TABS_TO_DELETE` in `library_utils.py` drives automatic removal of deprecated tabs (`Market Data`, `sentiment_data`, `macro_surveys`, `macro_surveys_hist`, `market_data_hist`) on every run.
- **Spreadsheet ID:** `12nKIUGHz5euDbNQPDTVECsJBNwrceRF1ymsQrIe4_ac` — hardcoded in all 5 modules that write to Sheets.

### Downstream Consumer: trigger.py

`trigger.py` runs at 06:15 London time on a local Windows machine (`C:\Users\kasim\ClaudeWorkflow\`). It reads only the `market_data` tab (via Sheets CSV export, GID `68683176`). No other tabs are consumed. Changes to macro, history, or indicator tabs do not affect the downstream consumer.

### index_library.csv Maintenance

The library is built and maintained via a separate Claude project at `C:\Users\kasim\OneDrive\Claude\Index Library\build_library.ipynb`. See the `TECHNICAL_MANUAL.md` in that folder for the library build process. To add a new instrument without the library builder, add a row to `data/index_library.csv` with `validation_status = "CONFIRMED"`, verify the ticker, set `base_currency`, and optionally set `simple_dash = True`. Changes take effect on the next pipeline run.

---

*End of Technical Manual*
