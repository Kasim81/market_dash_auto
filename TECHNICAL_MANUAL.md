# Market Dashboard — Technical Manual

> Last updated: 2026-03-17

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Directory Structure](#2-directory-structure)
3. [Execution Flow](#3-execution-flow)
4. [Two Pipelines: Simple vs Comp](#4-two-pipelines-simple-vs-comp)
5. [Module Reference](#5-module-reference)
   - [fetch_data.py](#51-fetch_datapy)
   - [fetch_hist.py](#52-fetch_histpy)
   - [fetch_macro_us_fred.py](#53-fetch_macro_us_fredpy)
   - [fetch_macro_international.py](#54-fetch_macro_internationalpy)
6. [Data Sources & APIs](#6-data-sources--apis)
7. [Google Sheets Tab Map](#7-google-sheets-tab-map)
8. [index_library.csv — Schema & Source of Truth](#8-index_librarycsv--schema--source-of-truth)
9. [FX Conversion Logic](#9-fx-conversion-logic)
10. [Key Design Patterns](#10-key-design-patterns)
11. [Environment Setup](#11-environment-setup)
12. [Known Issues & Status](#12-known-issues--status)
13. [Future Roadmap](#13-future-roadmap)

---

## 1. Project Overview

This project is a fully automated daily market dashboard. It fetches price, macro, and sentiment data from multiple free public APIs and writes the results to:

- **Google Sheets** (primary human-readable output, spreadsheet ID: `12nKIUGHz5euDbNQPDTVECsJBNwrceRF1ymsQrIe4_ac`)
- **CSV files** in `data/` (machine-readable; also committed to the git repo by GitHub Actions)

The pipeline runs automatically every day at **06:00 UTC** via GitHub Actions.

### Scope

| Output Tab | Instruments | Frequency | Source |
|---|---|---|---|
| `market_data` | ~66 hardcoded instruments | Daily snapshot | yfinance + FRED |
| `market_data_comp` | ~302 instruments from library | Daily snapshot | yfinance + FRED |
| `sentiment_data` | Fear & Greed, put/call, VIX term structure | Daily snapshot | yfinance |
| `macro_us` | ~25 US FRED macro series | Daily snapshot | FRED API |
| `market_data_hist` | ~66 instruments | Weekly history from 2000 | yfinance + FRED |
| `macro_us_hist` | ~25 US FRED series | Weekly history from 1947 | FRED API |
| `macro_intl` | 5 indicators × 11 countries | Daily snapshot | OECD + World Bank + IMF |
| `macro_intl_hist` | 5 indicators × 11 countries | Weekly history from 2000 | OECD + World Bank + IMF |
| `macro_surveys` | Regional Fed, ISM-related surveys | Daily snapshot | FRED API |
| `macro_surveys_hist` | Same as above | Weekly history | FRED API |
| `market_data_comp_hist` | ~302 instruments from library | Weekly history from 1950 | yfinance |

---

## 2. Directory Structure

```
market_dash_auto/
├── fetch_data.py               # Master orchestrator — runs all phases
├── fetch_hist.py               # Historical time series (market + macro_us + comp_hist)
├── fetch_macro_us_fred.py      # Phase A — US FRED macro indicators
├── fetch_macro_international.py # Phase C — International macro (OECD / World Bank / IMF)
├── index_library.csv           # Instrument master library (~302 rows)
├── requirements.txt            # Python dependencies
├── TECHNICAL_MANUAL.md         # This file
├── MarketDashboard_ClaudeCode_Handover.md  # AI assistant handover notes
├── data/
│   ├── market_data.csv
│   ├── market_data_comp.csv
│   ├── market_data_hist.csv
│   ├── market_data_comp_hist.csv
│   ├── macro_us.csv
│   ├── macro_us_hist.csv
│   ├── macro_intl.csv
│   ├── macro_intl_hist.csv
│   ├── macro_surveys.csv
│   ├── macro_surveys_hist.csv
│   └── sentiment_data.csv
└── .github/
    └── workflows/
        └── update_data.yml     # GitHub Actions daily scheduler
```

---

## 3. Execution Flow

GitHub Actions runs `python fetch_data.py` once per day. The file is structured as a sequential chain of `try/except` blocks so that **each phase is fully independent** — a failure in any later phase cannot affect earlier phases.

```
fetch_data.py
│
├─ main()                              ← Simple pipeline (always runs)
│   ├─ build_fx_cache()
│   ├─ collect_yf_assets()
│   ├─ collect_fred_yields()
│   ├─ build_calculated_fields()
│   ├─ [try] load_instrument_library()  ← Comp pipeline (fails safe)
│   │       collect_comp_assets()
│   │       collect_comp_fred_assets()
│   │       build_calculated_fields_comp()
│   └─ push_to_google_sheets()         ← Writes market_data + market_data_comp
│
├─ [try] from fetch_macro_us_fred import run_phase_a
│         run_phase_a()                ← Writes macro_us + macro_us hist
│
├─ [try] from fetch_hist import run_hist
│         run_hist()                   ← Writes market_data_hist + macro_us_hist
│
├─ [try] from fetch_macro_international import run_phase_c
│         run_phase_c()                ← Writes macro_intl + macro_intl_hist
│
└─ [try] from fetch_hist import run_comp_hist
          run_comp_hist()              ← Writes market_data_comp_hist
```

After the Python run, the workflow commits all updated CSVs back to git (on the `main` branch).

---

## 4. Two Pipelines: Simple vs Comp

### Simple Pipeline (`market_data`)

- Instrument list is **hardcoded inside `fetch_data.py`**
- ~66 instruments across equities, fixed income, FX, commodities, crypto, volatility
- Includes calculated ratio rows (XLY/XLP, HYG/LQD, etc.)
- FX tickers: `GBPUSD=X`, `EURUSD=X`, `USDJPY=X`, `USDCNY=X`, `USDINR=X`, `USDKRW=X`, `USDTWD=X`
- Output columns: `Symbol | Name | Ticker Type | Asset Class | Region | Currency | Last Price | Last Date | Return 1D | Return 1W | Return 1M | Return 3M | Return 6M | Return YTD | Return 1Y`
- Returns are computed in **both local currency and USD**

### Comp Pipeline (`market_data_comp`)

- Instrument list comes from **`index_library.csv`** — this is the single source of truth
- ~302 instruments covering every major global asset class
- Filtered to rows with `validation_status == "CONFIRMED"` at load time
- Uses a **broader FX cache** covering 18 currency pairs
- Output columns add: `Broad Asset Class | Sub-Category` (derived from `asset_class` + `asset_subclass` in library)
- Sorted by asset class → region → sector/style for consistent tab order

### Key Difference

The Simple pipeline is **never modified** unless Kasim explicitly approves. The Comp pipeline is the expandable, library-driven version. Both pipelines write their outputs independently to Google Sheets.

---

## 5. Module Reference

### 5.1 `fetch_data.py`

**Lines:** ~1,272
**Role:** Master orchestrator + both snapshot pipelines

#### Key Constants

| Constant | Purpose |
|---|---|
| `FRED_API_KEY` | Read from `FRED_API_KEY` env var |
| `LIBRARY_PATH` | Absolute path to `index_library.csv` |
| `FX_TICKERS` | 7 FX pairs for simple pipeline |
| `COMP_FX_TICKERS` | 18 FX pairs for comp pipeline |
| `COMP_FCY_PER_USD` | Set of indirect-quote currencies (invert for USD conversion) |
| `COMP_LEVEL_CHANGE_TICKERS` | Vol indices that use point change, not % change |
| `_LIB_ASSET_CLASS_GROUP` | Sort order for comp output by asset class |

#### Key Functions

| Function | What it does |
|---|---|
| `build_fx_cache()` | Downloads all 7 FX spot prices via yfinance |
| `build_comp_fx_cache()` | Downloads all 18 FX spot prices for comp pipeline |
| `collect_yf_assets(fx_cache)` | Loops hardcoded instrument list, fetches price + returns via yfinance |
| `collect_fred_yields()` | Fetches ~5 FRED yield series for simple pipeline |
| `build_calculated_fields(df)` | Computes ratio rows (XLY/XLP etc.) from existing prices |
| `load_instrument_library()` | Reads `index_library.csv`, filters to CONFIRMED rows, sorts |
| `collect_comp_assets(instruments, fx_cache)` | Same as `collect_yf_assets` but for comp library |
| `collect_comp_fred_assets()` | Fetches 25 FRED Rates series referenced in library |
| `build_calculated_fields_comp(df)` | Same as `build_calculated_fields` but for comp dataframe |
| `push_to_google_sheets(df_main, df_comp)` | Writes both tabs to Google Sheets via Sheets API v4 |
| `main()` | Entry point — runs simple + comp pipelines |

#### FRED Yield Series (simple pipeline)

These are hardcoded directly in `collect_fred_yields()`:
- `DGS2` — US 2Y Treasury
- `DGS10` — US 10Y Treasury
- `DGS30` — US 30Y Treasury
- `BAMLH0A0HYM2EY` — US HY Credit Yield
- `BAMLC0A0CM` — US IG Credit Spread (OAS)

#### Google Sheets Write Pattern

```python
service.spreadsheets().values().update(
    spreadsheetId=SHEET_ID,
    range=f"'{tab_name}'!A1",
    valueInputOption="USER_ENTERED",   # ← important: Sheets parses numbers/dates
    body={"values": rows}
).execute()
```

`valueInputOption="USER_ENTERED"` means Sheets will auto-parse `"1480.29"` as a number, dates as dates, etc.

---

### 5.2 `fetch_hist.py`

**Lines:** ~1,873
**Role:** All historical time series — market_data_hist, macro_us_hist, market_data_comp_hist

This module has **its own hardcoded instrument lists** (EQUITY_INDICES, EQUITY_ETFS, FX_PAIRS, COMMODITIES, CRYPTO, VOLATILITY, BONDS, FRED_YIELDS, RATIOS). These are **separate from fetch_data.py** and must be kept in sync manually.

#### Key Constants

| Constant | What it defines |
|---|---|
| `MARKET_HIST_START` | `"2000-01-01"` — floor date for all market history |
| `MACRO_HIST_START` | `"1947-01-01"` — floor date for all FRED macro history |
| `COMP_HIST_START` | `"1950-01-01"` — floor date for comp library history |
| `FRIDAY_SPINE` | Weekly Friday date index built once and reused everywhere |

#### Output Format

- **Rows** = dates (weekly Friday close)
- **Columns** = instruments
- Column order: `[all Local Currency columns] + [all USD columns]`
- Metadata prefix rows (10 rows above the Date header): Source, Name, Category, Subcategory, Units, Frequency, Last Updated, blank, blank, then the column header row

#### Key Functions

| Function | What it does |
|---|---|
| `build_friday_spine(start, end)` | Builds weekly Friday DatetimeIndex |
| `fetch_yf_history(ticker, start)` | Downloads full price history via yfinance `t.history()` |
| `compute_usd_price_series(local, currency, start)` | Fetches FX history and converts local prices to USD |
| `push_df_to_sheets(df, tab_name, label, prefix_rows)` | Writes df to a Sheets tab with optional metadata prefix rows |
| `run_hist()` | Builds market_data_hist + macro_us_hist and writes both |
| `run_comp_hist()` | Reads index_library.csv, builds market_data_comp_hist |

#### FX Conversion in Historical Mode

`compute_usd_price_series()` (lines 314–348):
1. Fetches full daily FX history from yfinance from `MARKET_HIST_START`
2. Aligns FX series to the weekly Friday spine using `fx.reindex(local_prices.index, method="ffill")`
3. Applies element-wise multiplication or division per date based on quote convention

Each Friday's USD price uses **that Friday's exchange rate** (or the nearest prior trading day's rate via forward-fill). This is correct — no look-ahead bias.

#### pence correction

LSE `.L` tickers: if the median of the raw price series is > 50, the entire series is divided by 100. This handles the yfinance convention of reporting UK prices in pence (GBp) rather than pounds (GBP). The threshold of 50 is a heuristic — works for all current library instruments.

#### Metadata Prefix Rows

Ten rows are written above the date header in each Sheets tab:
```
Row 1:  Source
Row 2:  Name
Row 3:  Category
Row 4:  Subcategory
Row 5:  Units
Row 6:  Frequency
Row 7:  Last Updated
Row 8:  (blank)
Row 9:  (blank)
Row 10: Date    <column names>    ← this is the actual header row
Row 11+: data
```

The `Date` column header in row 10 is what separates metadata from data. Code that reads back these CSVs must skip the first 9 rows (or handle the metadata rows explicitly).

---

### 5.3 `fetch_macro_us_fred.py`

**Lines:** ~704
**Role:** Phase A — US macro FRED indicators (snapshot + history)

This module is **the single source of truth for all US FRED macro series**. Both the snapshot (`macro_us`) and the history (`macro_us_hist`) are driven by the `FRED_MACRO_US` dict defined in this file. `fetch_hist.py` imports `FRED_MACRO_US` directly from this module.

#### FRED_MACRO_US Dict Format

```python
FRED_MACRO_US = {
    "SERIES_ID": (
        "Human-readable name",
        "Category",        # Growth | Inflation | Financial Conditions | Monetary Policy
        "Subcategory",     # e.g. "Labour Market", "CPI", "Credit Cycle"
        "Units string",
        "Interpretation notes"
    ),
    ...
}
```

#### Current Series (25 total)

| Category | Series ID | Name |
|---|---|---|
| Growth / Yield Curve | `T10Y2Y` | 10Y-2Y Spread |
| Growth / Yield Curve | `T10Y3M` | 10Y-3M Spread |
| Growth / Money Supply | `M2SL` | M2 Money Supply |
| Growth / Leading | `USSLIND` | Conference Board LEI |
| Growth / Leading | `PERMIT` | Building Permits |
| Growth / Labour | `IC4WSA` | Initial Claims 4W Avg |
| Growth / Labour | `PAYEMS` | Nonfarm Payrolls |
| Growth / Labour | `UNRATE` | Unemployment Rate |
| Growth / Activity | `INDPRO` | Industrial Production |
| Growth / Activity | `RSXFS` | Retail Sales ex-Autos |
| Growth / Credit | `DRTSCILM` | SLOOS C&I Large Firms |
| Growth / Credit | `STDSOTHCONS` | SLOOS Consumer (non-CC) |
| Growth / Credit | `SUBLPDRCSN` | SLOOS CRE Nonfarm Nonres |
| Fin Cond / Composite | `NFCI` | Chicago Fed NFCI |
| Inflation / CPI | `CPIAUCSL` | CPI Headline |
| Inflation / CPI | `CPILFESL` | Core CPI |
| Inflation / PCE | `PCEPILFE` | Core PCE Deflator |
| Inflation / PPI | `PPIACO` | PPI All Commodities |
| Inflation / Breakeven | `T10YIE` | 10Y Breakeven Inflation |
| Mon. Policy | `DFEDTARU` | Fed Funds Rate Target Upper |
| Mon. Policy | `WRESBAL` | Fed Reserve Balances (reserves) |
| UMich | `UMCSENT` | UMich Consumer Sentiment |
| UMich | `UMCSC` | UMich Current Conditions |
| UMich | `UMCSE` | UMich Expectations |
| Regional Fed | `GACDFSA066MSFRBPHI` | Philly Fed Manufacturing Activity |
| Regional Fed | `MFRBSCOMP` | Richmond Fed Composite |
| Regional Fed | `KCACTMFG` | Kansas City Fed Manufacturing |

> **Note on naming conventions:** Regional Fed series use completely different ID patterns:
> - Philadelphia: `GACDFSA066MSFRBPHI` (prefix `GACDFSA066MSFRB` + `PHI`)
> - Richmond: `MFRBSCOMP` (completely different format)
> - Kansas City: `KCACTMFG` (completely different format)
> Never assume they follow the same pattern.

#### FRED Rate Limiting

- 0.6s delay between requests (max ~100 req/min; FRED limit is 120/min)
- Exponential backoff on 429/5xx: 2s → 4s → 8s → 16s → 32s
- Per-series try/except (one failure never kills the whole run)

---

### 5.4 `fetch_macro_international.py`

**Lines:** ~1,281
**Role:** Phase C — International macro for 11 economies

#### Countries Covered

`AUS, CAN, CHE, CHN, DEU, EA19, FRA, GBR, ITA, JPN, USA`

Note: `EA19` = Eurozone. `CHN` and `EA19` have partial coverage (OECD doesn't publish LFS unemployment for these areas).

#### Indicators

| Indicator | Source | API | Frequency | Known Issues |
|---|---|---|---|---|
| Composite Leading Indicator (CLI) | OECD | `sdmx.oecd.org` DF_CLI | Monthly | EA19 and CHE missing from OECD |
| Unemployment Rate | OECD | `sdmx.oecd.org` DF_IALFS_UNE_M | Monthly | CHN, EA19 not published |
| Short-term Interest Rate (3M) | OECD | `sdmx.oecd.org` DF_FINMARK | Monthly | **Currently returning no data for all countries** |
| CPI Headline YoY % | World Bank | `api.worldbank.org` FP.CPI.TOTL.ZG | Annual | EA19 uses World Bank code `EMU` |
| Real GDP Growth % | IMF | `imf.org` DataMapper | Annual + projections | EA19 (`XM` code) returning no data |

#### OECD API Migration Note

The legacy `stats.oecd.org` SDMX-JSON API was deprecated June/July 2024. This module uses the **new** `sdmx.oecd.org` REST API with `format=csv`. New dataflow IDs:
- CLI: `OECD.SDD.STES,DSD_STES@DF_CLI,4.1`
- Unemployment: `OECD.SDD.TPS,DSD_LFS@DF_IALFS_UNE_M,1.0`
- Rates: `OECD.SDD.STES,DSD_STES@DF_FINMARK,4.0`

#### Rate Limiting

- OECD: max 20 calls/hour; module makes at most 6 calls per run (3 snapshot + 3 history)
- Exponential backoff: 2s → 4s → 8s → 16s → 32s

---

## 6. Data Sources & APIs

### yfinance

- **Library:** `yfinance` Python package
- **Used for:** Price history (`.history()`), no `.info` calls
- **Rate limiting:** 0.3s delay between per-ticker fetches in simple pipeline; bulk download (`yf.download([list])`) used in hist pipeline where possible
- **Known issues:**
  - Some official index tickers (STOXX sectors: `^SXEP` etc., S&P style: `^IVX`, TOPIX: `^TOPX`) return empty history
  - Russian tickers (`IMOEX.ME`, `RTSI.ME`) have data through mid-2022/mid-2024 due to sanctions
  - UK `.L` tickers report prices in pence — apply ÷100 correction when median > 50

### FRED API

- **URL:** `https://api.stlouisfed.org/fred/series/observations`
- **Auth:** `FRED_API_KEY` environment variable (GitHub Secret)
- **Used for:** US macro series, treasury yields, credit spreads, OAS
- **Rate limit:** 120 requests/minute per key

### OECD SDMX REST API

- **URL:** `https://sdmx.oecd.org/public/rest/`
- **Auth:** None required
- **Used for:** CLI, Unemployment Rate, Short-term Interest Rate for 11 economies
- **Format:** `format=csv` (new API as of July 2024)
- **Rate limit:** ~20 calls/hour

### World Bank Open Data API

- **URL:** `https://api.worldbank.org/v2/country/{code}/indicator/{indicator}`
- **Auth:** None required
- **Used for:** Annual CPI YoY % (`FP.CPI.TOTL.ZG`) for 11 economies
- **Note:** Eurozone uses code `EMU` (not `EA19`)

### IMF DataMapper REST API

- **URL:** `https://imf.org/external/datamapper/api/`
- **Auth:** None required
- **Used for:** Real GDP Growth % (annual WEO, includes projections)
- **Note:** Full history returned in a single call

### Google Sheets API v4

- **Auth:** Service account JSON in `GOOGLE_CREDENTIALS` environment variable (GitHub Secret)
- **Spreadsheet ID:** `12nKIUGHz5euDbNQPDTVECsJBNwrceRF1ymsQrIe4_ac`
- **Write method:** `spreadsheets().values().update()` with `valueInputOption="USER_ENTERED"`
- **Scopes:** `https://www.googleapis.com/auth/spreadsheets`

---

## 7. Google Sheets Tab Map

| Tab Name | Written By | CSV Mirror | Contents |
|---|---|---|---|
| `market_data` | `fetch_data.py` | `data/market_data.csv` | ~66 instruments, daily snapshot |
| `market_data_comp` | `fetch_data.py` | `data/market_data_comp.csv` | ~302 instruments, daily snapshot |
| `sentiment_data` | `fetch_data.py` | `data/sentiment_data.csv` | Fear & Greed, VIX term structure, put/call |
| `macro_us` | `fetch_macro_us_fred.py` | `data/macro_us.csv` | ~25 US FRED series snapshot |
| `market_data_hist` | `fetch_hist.py` | `data/market_data_hist.csv` | Weekly history from 2000 |
| `macro_us_hist` | `fetch_hist.py` | `data/macro_us_hist.csv` | Weekly FRED history from 1947 |
| `macro_intl` | `fetch_macro_international.py` | `data/macro_intl.csv` | Intl macro snapshot |
| `macro_intl_hist` | `fetch_macro_international.py` | `data/macro_intl_hist.csv` | Intl macro weekly history |
| `macro_surveys` | (Phase B — see notes) | `data/macro_surveys.csv` | Regional Fed + credit surveys snapshot |
| `macro_surveys_hist` | (Phase B — see notes) | `data/macro_surveys_hist.csv` | Survey series weekly history |
| `market_data_comp_hist` | `fetch_hist.py` | `data/market_data_comp_hist.csv` | Comp library weekly history from 1950 |

> **Note:** `trigger.py` (the Sheets-reading downstream process) reads only `market_data` and `sentiment_data`. None of the hist tabs are consumed by trigger.py.

---

## 8. `index_library.csv` — Schema & Source of Truth

The library has ~302 rows and 26 columns. It is the **single source of truth** for the Comp pipeline — all instruments, metadata, and data source assignments live here.

### Column Schema

| Column | Type | Description |
|---|---|---|
| `name` | string | Human-readable instrument name |
| `asset_class` | enum | Equity, Fixed Income, Rates, FX, Commodity, Crypto, Volatility |
| `asset_subclass` | string | e.g. "Equity Broad", "Govt Bond", "Corp HY" |
| `region` | string | Global, North America, US, Europe, etc. |
| `country_market` | string | Specific country (e.g. "United States", "Japan") |
| `sector_style` | string | Sector or style tag (e.g. "Energy", "Growth", "Blend") |
| `market_cap_focus` | string | Large, Mid, Small, Broad |
| `maturity_focus` | string | Short (1-3yr), Long (10yr+), Broad |
| `credit_quality` | string | Investment Grade, High Yield |
| `commodity_group` | string | Energy, Precious Metals, Agriculture, etc. |
| `base_currency` | string | ISO currency code (USD, GBP, EUR, JPY, …) |
| `hedged` | bool | True if currency-hedged variant |
| `hedge_currency` | string | Target hedge currency |
| `proxy_flag` | bool | True if this is a proxy for an unavailable primary |
| `proxy_type` | string | ETF, Total Return, etc. |
| `data_source` | enum | `yfinance`, `fred`, `oecd`, `worldbank`, `imf` |
| `validation_status` | enum | `CONFIRMED`, `PENDING`, `UNAVAILABLE` |
| `ticker_yfinance_pr` | string | yfinance price return ticker |
| `ticker_yfinance_tr` | string | yfinance total return ticker (ETF proxy) |
| `ticker_investiny` | string | (reserved, not currently used) |
| `ticker_fred_tr` | string | FRED total return index series ID |
| `ticker_fred_yield` | string | FRED yield series ID |
| `ticker_fred_oas` | string | FRED OAS spread series ID |
| `ticker_fred_spread` | string | FRED spread series ID |
| `ticker_fred_duration` | string | FRED duration series ID |
| `data_start` | date | Earliest reliable data date for this instrument |

### How the Comp Pipeline Uses the Library

1. `load_instrument_library()` in `fetch_data.py` reads the CSV and filters to `validation_status == "CONFIRMED"`
2. Rows with `data_source == "yfinance"` are fetched via `collect_comp_assets()`
3. Rows with `data_source == "fred"` and a `ticker_fred_yield` are fetched via `collect_comp_fred_assets()`
4. The sort order in Google Sheets follows `_lib_sort_key()` which uses the `_LIB_ASSET_CLASS_GROUP`, `_LIB_REGION_ORDER`, and related constants

### Library Maintenance

**Important:** Any changes to instrument metadata (name, region, asset class, currency) must be made in `index_library.csv`. Do **not** hardcode overrides in the Python files. Changes to the library take effect on the next pipeline run.

To add a new instrument:
1. Add a row to `index_library.csv` with `validation_status = "CONFIRMED"`
2. Verify the `ticker_yfinance_pr` works: `python -c "import yfinance as yf; t = yf.Ticker('TICKER'); print(t.history(period='5d'))"`
3. Set appropriate `base_currency` — the comp pipeline needs this for FX conversion

---

## 9. FX Conversion Logic

### Snapshot (fetch_data.py)

For each instrument row, USD return is computed as:
```
USD_return = (1 + Local_return) * (1 + FX_return) - 1
```

where `FX_return` is the spot FX change over the same period. For indirect-quote currencies (JPY, CNY, etc.), the FX rate is inverted before applying.

### Historical (fetch_hist.py)

`compute_usd_price_series(local_prices, currency, start)`:
1. Downloads full daily FX history via `yf.download(fx_ticker, start=start)`
2. Reindexes to the weekly Friday spine with `method="ffill"` (forward-fill)
3. Applies: `usd_prices = local_prices * fx_prices` (for direct quotes like EUR/USD)
4. Or: `usd_prices = local_prices / fx_prices` (for indirect quotes like USD/JPY)

This is correct — no look-ahead bias, each date uses that date's rate.

### Currency Convention Reference

| Currency | yfinance Ticker | Convention | Invert? |
|---|---|---|---|
| GBP | `GBPUSD=X` | 1 GBP = X USD | No |
| EUR | `EURUSD=X` | 1 EUR = X USD | No |
| AUD | `AUDUSD=X` | 1 AUD = X USD | No |
| JPY | `USDJPY=X` | 1 USD = X JPY | Yes |
| CNY | `CNY=X` | 1 USD = X CNY | Yes |
| INR | `INR=X` | 1 USD = X INR | Yes |
| CAD | `USDCAD=X` | 1 USD = X CAD | Yes |
| HKD | `USDHKD=X` | 1 USD = X HKD | Yes |

---

## 10. Key Design Patterns

### Pattern 1: Fail-Safe Chaining

Every phase after `main()` is wrapped in `try/except` at the module level:
```python
try:
    from fetch_hist import run_hist
    run_hist()
except Exception as e:
    print(f"[Hist] Non-fatal error: {e}")
```
This means: if Phase C crashes, `market_data`, `market_data_comp`, `macro_us`, and `market_data_hist` are already written and safe.

### Pattern 2: Per-Series Try/Except

Inside each module, every individual series/ticker fetch is also wrapped:
```python
for series_id, (name, ...) in FRED_MACRO_US.items():
    try:
        data = fetch_fred_series(series_id)
        ...
    except Exception as e:
        print(f"  WARNING: {series_id} failed: {e}")
        continue
```
One bad FRED series never kills the rest of the macro_us output.

### Pattern 3: Friday Spine

All historical data is aligned to a weekly Friday date index. Monthly and quarterly series are forward-filled into the Friday slots. This ensures all series share a common date axis, enabling cross-series analysis in Sheets without any date alignment complexity.

### Pattern 4: Metadata Prefix Rows in Sheets

History tabs in Google Sheets have 10 metadata rows above the actual data:
```
Row 1-9:  metadata (Source, Name, Category, Units, etc.)
Row 10:   "Date | ticker1 | ticker2 | ..."   ← column header
Row 11+:  data rows
```
CSVs do NOT have these rows — they start with the column header on row 1. This keeps CSVs machine-readable while giving the Sheets tabs human-readable context.

### Pattern 5: index_library.csv as Source of Truth

The Comp pipeline reads everything from `index_library.csv` at runtime. There are no hardcoded instrument lists for the comp output. This means:
- Adding/removing instruments only requires editing the CSV
- The Python code never needs to change for instrument additions
- `validation_status = "CONFIRMED"` is the gate — set to `"PENDING"` to disable an instrument without deleting it

---

## 11. Environment Setup

### Required Environment Variables

| Variable | Where Set | Used By |
|---|---|---|
| `FRED_API_KEY` | GitHub Secret | `fetch_data.py`, `fetch_macro_us_fred.py`, `fetch_hist.py` |
| `GOOGLE_CREDENTIALS` | GitHub Secret | All modules that write to Sheets |

`GOOGLE_CREDENTIALS` must be a JSON string of a Google service account key with editor access to the target spreadsheet.

### Python Dependencies (`requirements.txt`)

```
yfinance
pandas
numpy
requests
google-auth
google-api-python-client
```

### Running Locally

```bash
export FRED_API_KEY="your_key_here"
export GOOGLE_CREDENTIALS='{"type": "service_account", ...}'
python fetch_data.py
```

Individual modules can also be run standalone:
```bash
python fetch_macro_us_fred.py
python fetch_hist.py
python fetch_macro_international.py
```

### GitHub Actions Trigger

- **Automatic:** Daily at 06:00 UTC (cron `0 6 * * *`)
- **Manual:** "workflow_dispatch" — trigger from GitHub UI → Actions tab → "Update Market Data" → "Run workflow"

After each run, the workflow auto-commits all updated CSVs back to the `main` branch with commit message: `Update market data - YYYY-MM-DD HH:MM UTC`

---

## 12. Known Issues & Status

### Currently Broken / Returning No Data

| Issue | Module | Status |
|---|---|---|
| OECD DF_FINMARK (Short-term Interest Rate) returning zero data for all 11 countries | `fetch_macro_international.py` | **Not fixed** — query key needs investigation |
| IMF `XM` code (Eurozone GDP Growth) returning no data | `fetch_macro_international.py` | **Not fixed** — IMF code may have changed |
| OECD EA19 and CHE CLI missing (OECD doesn't publish these area codes) | `fetch_macro_international.py` | **Structural** — no fix available |
| UMCSE (UMich Expectations) returning null | `fetch_macro_us_fred.py` | **Monitor** — may be FRED temporary issue or access restriction |

### Tickers Confirmed Unavailable via yfinance

These tickers exist in `index_library.csv` but yfinance serves no historical data for them:

| Ticker | Instrument | Reason |
|---|---|---|
| `^SXEP`, `^SXKP`, `^SX3P`, `^SX4P`, `^SX6P`, `^SX7P`, `^SX8P`, `^SXMP`, `^SXDP`, `^SXOP`, `^SXRP`, `^SXTP` | STOXX 600 sectors | yfinance doesn't serve official STOXX sector index history |
| `^IVX`, `^IGX` | S&P style indices | Not served via yfinance |
| `^SML`, `^SP500-10`, `^SP500-20` | S&P size/sector | Not served via yfinance |
| `^TX60` | S&P/TSX 60 | Not served via yfinance |
| `^TOPX` | TOPIX (Japan) | Not served via yfinance |
| `IMOEX.ME`, `RTSI.ME` | Russian indices | Data available only through mid-2022/mid-2024 due to sanctions |
| `CYB` | WisdomTree Chinese Yuan ETF | Delisted December 2023; `CNYB.L` is active replacement already in library |
| `DX-Y.NYB` | US Dollar Index | Only has data from 2008-03-28, not from 2000 |

### Recently Fixed

| Issue | Fix Applied | Commit |
|---|---|---|
| Wrong FRED series ID for Richmond Fed (`GACDISA066MSFRBRIC`) | Replaced with `MFRBSCOMP` | Done |
| Wrong FRED series ID for Kansas City Fed (`GACDISA066MSFRBKC`) | Replaced with `KCACTMFG` | Done |
| Wrong FRED series ID for Philadelphia Fed (`GACDISA066MSFRBPHI`) | Replaced with `GACDFSA066MSFRBPHI` | Done |
| Wrong FRED series ID for SLOOS Consumer (`DRTSCLNG`) | Replaced with `STDSOTHCONS` | Done |
| Wrong FRED series ID for SLOOS CRE (`DRTSCRE`) | Replaced with `SUBLPDRCSN` | Done |
| `NAPMPI` (ISM Manufacturing PMI) deleted from FRED in 2016 | Series removed from `FRED_MACRO_US` | Done |

### Metadata / Label Issues

| Ticker | Issue | Recommended Fix |
|---|---|---|
| `^IRX` | Currently labeled "US 2Y Treasury Yield" but `^IRX` is the 13-week T-bill (3-month) | Rename to "US 3-Month T-Bill" OR swap to a true 2Y ticker |
| XLE, XLB, XLI etc. (SPDR sector ETFs) | Region labeled "North America" | Should be "US" — these track S&P 500 sectors (US-only) |
| `IWF` | Region labeled "North America" | Should be "US" — iShares Russell 1000 Growth (US-only) |
| `^VIX` | Region labeled "Global" | Should be "US" — measures S&P 500 implied vol |

---

## 13. Future Roadmap

> Items below are planned but not yet implemented. Order reflects logical dependency chain.

### Phase B — Additional US Macro (already partially integrated)

Survey and credit condition indicators are already consolidated into `fetch_macro_us_fred.py`. The `macro_surveys` tab exists but its content may overlap with `macro_us`.

### Phase D — ISM/PMI Survey Data

Before using FMP, check these FRED series first:
- `NAPMPI` — **Deleted from FRED in 2016; not available**
- `NMFCI`, `NMFBAI` — ISM Non-Manufacturing (Services) — check FRED availability
- Philly Fed components — many available on FRED
- Empire State: check FRED coverage

If covered by FRED → implement using existing FRED fetch pattern, no new API key needed.

### Phase C Fixes Needed

1. **OECD DF_FINMARK** — investigate correct query key for short-term interest rates
2. **IMF EA19 GDP** — investigate correct country code for Eurozone in DataMapper
3. **Replace OpenBB with direct APIs** — all Phase C data is available via OECD/ECB/IMF REST APIs with no package dependencies

Alternative free APIs for future Phase C expansion:
- **ECB Statistical Data Warehouse:** `https://data-api.ecb.europa.eu/` — no key
- **OECD SDMX-JSON:** `https://sdmx.oecd.org/public/rest/` — no key
- **IMF DataMapper:** `https://imf.org/external/datamapper/api/` — no key

### Phase E — Instrument Expansion

Expand `index_library.csv` with additional instruments. This is an **owner decision** — confirm full target list with Kasim before building. Do not implement until list is finalized to avoid rework.

### Phase F — Global PMI Composite

Build a cross-country PMI composite (ISM + Eurozone + Japan PMI). Depends on Phase D being complete first.

### index_library.csv as Complete Single Source of Truth

Create `library_manager.py` — a standalone utility whose only job is maintaining `index_library.csv`. It would:
- Validate all tickers against yfinance
- Flag tickers with no data (auto-set `validation_status = "UNAVAILABLE"`)
- Suggest alternative tickers for unavailable instruments
- Ensure metadata consistency (no duplicate tickers, all required fields filled)
- Run as a manual tool (`python library_manager.py`) not as part of the daily pipeline

### Incremental Fetch Mode (fetch_hist.py)

Currently `fetch_hist.py` rebuilds the entire dataset from scratch on every run (8–12 min). An incremental append mode would:
1. Check the last date in the existing CSV
2. Only fetch new weekly rows since the last update
3. Append to existing data rather than full rebuild

This would reduce the daily run time for historical data from ~10 minutes to seconds.

---

*End of Technical Manual*
