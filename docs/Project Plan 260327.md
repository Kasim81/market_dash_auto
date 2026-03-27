# Market Dashboard Auto — Project Plan & Technical Review

**Date:** 2026-03-27
**Repository:** github.com/Kasim81/market_dash_auto
**Pipeline:** Daily 06:00 UTC via GitHub Actions

---

## 1. Project Overview

Market Dashboard Auto is a fully automated daily data pipeline that fetches market prices, macro-economic indicators, and sentiment data from free public APIs and writes results to:

- **Google Sheets** (primary human-readable output)
- **CSV files** in `data/` (machine-readable, committed to git by GitHub Actions)

The pipeline runs `python fetch_data.py` once per day. Each phase is wrapped in an independent `try/except` so failures are isolated — a problem in any later phase cannot affect earlier phases.

---

## 2. Repository Structure

```
market_dash_auto/
├── fetch_data.py                  # Master orchestrator — runs all phases (1,160 lines)
├── fetch_hist.py                  # Historical time series — market + macro_us + comp (1,718 lines)
├── fetch_macro_us_fred.py         # US FRED macro indicators + surveys (510 lines)
├── fetch_macro_international.py   # International macro — OECD / World Bank / IMF (1,426 lines)
├── compute_macro_market.py        # 50 macro-market composite indicators (1,647 lines)
├── library_utils.py               # Shared sort-order dicts and sort key function (210 lines)
├── requirements.txt               # Python dependencies
├── README.md
│
├── data/                          # All CSV data files and indicator libraries
│   ├── index_library.csv              # Instrument master library (~302 rows)
│   ├── level_change_tickers.csv       # Vol tickers using absolute pt change
│   ├── macro_library_fred.csv         # FRED indicator definitions
│   ├── macro_library_oecd.csv         # OECD indicator definitions
│   ├── macro_library_imf.csv          # IMF indicator definitions
│   ├── macro_library_worldbank.csv    # World Bank indicator definitions
│   ├── macro_indicator_library.csv    # 50 macro-market indicator definitions
│   ├── market_data.csv                # Daily snapshot — 66 simple-pipeline instruments
│   ├── market_data_comp.csv           # Daily snapshot — ~302 comp-pipeline instruments
│   ├── market_data_hist.csv           # Weekly history from 2000 — simple instruments
│   ├── market_data_comp_hist.csv      # Weekly history from 1950 — comp instruments
│   ├── sentiment_data.csv             # Fear & Greed, put/call, VIX term structure
│   ├── macro_us.csv                   # US FRED macro snapshot (43 series)
│   ├── macro_us_hist.csv              # US FRED macro weekly history from 1947
│   ├── macro_intl.csv                 # International macro snapshot (11 countries)
│   ├── macro_intl_hist.csv            # International macro weekly history
│   ├── macro_surveys.csv              # Regional Fed + survey snapshot
│   └── macro_surveys_hist.csv         # Regional Fed + survey weekly history
│
├── docs/                          # Documentation
│   ├── MarketDashboard_ClaudeCode_Handover.md
│   ├── TECHNICAL_MANUAL.md
│   ├── METADATA_REDUNDANCY_REVIEW.md
│   └── multifreq_plan.md
│
└── .github/workflows/
    └── update_data.yml            # GitHub Actions daily scheduler
```

**Total codebase:** ~6,670 lines of Python across 6 modules.

---

## 3. Pipeline Architecture

### 3.1 Execution Flow

`fetch_data.py` is the master orchestrator. GitHub Actions calls it once per day. Internally it runs a sequential chain of `try/except` blocks:

```
fetch_data.py main()
│
├─ Phase 0: Simple Pipeline (hardcoded 66 instruments)
│   ├─ build_fx_cache()
│   ├─ collect_yf_assets()          → yfinance prices + returns
│   ├─ collect_fred_yields()        → FRED yield data
│   ├─ build_calculated_fields()    → ratios (XLY/XLP, HY/IG, etc.)
│   └─ push to Sheets: market_data, sentiment_data
│
├─ Phase A: Comp Pipeline (from index_library.csv)
│   ├─ load_instrument_library()    → ~302 instruments
│   ├─ collect_comp_assets()        → yfinance bulk download
│   ├─ collect_comp_fred_assets()   → FRED yields/spreads
│   └─ push to Sheets: market_data_comp
│
├─ Phase B: Historical (simple + comp + macro)
│   ├─ fetch_hist.build_market_hist_df()      → market_data_hist
│   ├─ fetch_hist.build_macro_hist_df()       → macro_us_hist
│   └─ fetch_hist.run_comp_hist()             → market_data_comp_hist
│
├─ Phase C: US FRED Macro
│   ├─ fetch_macro_us_fred.run_macro_us()     → macro_us + macro_us_hist
│   └─ fetch_macro_us_fred.run_macro_surveys()→ macro_surveys + macro_surveys_hist
│
├─ Phase D: International Macro
│   ├─ fetch_macro_international.run_intl()   → macro_intl + macro_intl_hist
│   └─ Sources: OECD (CLI, unemployment), World Bank (CPI, GDP), IMF (GDP), FRED (yields, confidence)
│
└─ Phase E: Macro-Market Indicators
    ├─ compute_macro_market.run_phase_e()
    └─ 50 composite indicators (raw + z-score + regime) → macro_market + macro_market_hist
```

### 3.2 Two Parallel Pipelines

The project maintains two parallel instrument pipelines:

| | Simple Pipeline | Comp Pipeline |
|---|---|---|
| **Instruments** | 66 hardcoded in Python | ~302 from `index_library.csv` |
| **Snapshot tab** | `market_data` | `market_data_comp` |
| **History tab** | `market_data_hist` | `market_data_comp_hist` |
| **FX coverage** | 7 currencies | 18 currencies |
| **Sort order** | Hardcoded dicts | Same dicts (duplicated) |
| **Pence correction** | Hardcoded `PENCE_TICKERS` set | Dynamic `.endswith(".L")` + median check |

The simple pipeline exists for backward compatibility with `trigger.py` (a local Windows script that reads `market_data` and `sentiment_data` tabs). The comp pipeline is the expanded, library-driven replacement.

### 3.3 Data Sources

| Source | API Key | Coverage |
|---|---|---|
| yfinance | None | All market prices, FX, ETFs, yields (302 instruments) |
| FRED API | `FRED_API_KEY` | US macro (43 series), surveys (10 series), international yields/confidence |
| OECD | None (direct REST) | CLI, unemployment for 9 countries |
| World Bank | None (direct REST) | CPI, GDP growth for 11 countries |
| IMF | None (direct REST) | GDP growth for 11 countries |

### 3.4 Google Sheets Output

| Tab | Written By | Content |
|---|---|---|
| `market_data` | fetch_data.py | 66-instrument daily snapshot |
| `market_data_comp` | fetch_data.py | ~302-instrument daily snapshot |
| `sentiment_data` | fetch_data.py | Fear & Greed, VIX term structure |
| `market_data_hist` | fetch_hist.py | Weekly prices from 2000 |
| `market_data_comp_hist` | fetch_hist.py | Weekly prices from 1950 |
| `macro_us` | fetch_macro_us_fred.py | 43 FRED series snapshot |
| `macro_us_hist` | fetch_macro_us_fred.py | Weekly FRED history from 1947 |
| `macro_intl` | fetch_macro_international.py | 11-country macro snapshot |
| `macro_intl_hist` | fetch_macro_international.py | Weekly international history |
| `macro_surveys` | fetch_macro_us_fred.py | Regional Fed + survey snapshot |
| `macro_surveys_hist` | fetch_macro_us_fred.py | Weekly survey history |
| `macro_market` | compute_macro_market.py | 50-indicator snapshot |
| `macro_market_hist` | compute_macro_market.py | Weekly indicator history |

---

## 4. Indicator Libraries (CSV-Driven Configuration)

The project uses CSV files as indicator registries so new series can be added without touching Python code:

| Library File | Records | Consumed By |
|---|---|---|
| `data/index_library.csv` | ~302 instruments | fetch_data.py, fetch_hist.py |
| `data/macro_library_fred.csv` | ~43 US + international FRED series | fetch_macro_us_fred.py, fetch_macro_international.py |
| `data/macro_library_oecd.csv` | ~10 OECD indicators | fetch_macro_international.py |
| `data/macro_library_imf.csv` | ~5 IMF indicators | fetch_macro_international.py |
| `data/macro_library_worldbank.csv` | ~5 World Bank indicators | fetch_macro_international.py |
| `data/macro_indicator_library.csv` | 50 macro-market indicators | compute_macro_market.py (reference only; definitions hardcoded) |
| `data/level_change_tickers.csv` | ~9 vol tickers | fetch_data.py |

---

## 5. Key Design Patterns

- **Per-series try/except** — one fetch failure never kills the pipeline run
- **Phase isolation** — each phase is wrapped in its own try/except in fetch_data.py
- **Rate limiting** — yfinance: 0.3s delay; FRED: 0.6s delay with exponential backoff
- **LSE pence correction** — `.endswith(".L")` + median price > 50 check
- **USD return compounding** — `(1 + local_return) * (1 + fx_return) - 1`
- **Sheets protected tabs** — hard-refuse writes to `market_data` and `sentiment_data` from new phases
- **Batch writes** — 10,000 rows per Sheets API call
- **NaN handling** — NaN converted to empty string before Sheets push
- **Diff-check commits** — only commit CSVs if content actually changed

---

## 6. Known Issues

### 6.1 Breaking Issues

1. **`data_source` filter broken** (`fetch_data.py:784`, `fetch_hist.py:1297`) — The comp pipeline filters on `data_source == "yfinance"` but `index_library.csv` now uses `"yfinance PR"` / `"yfinance TR"`. This causes the comp pipeline to return zero yfinance instruments. The filter needs to be updated to `str.startswith("yfinance")` or `.isin(["yfinance PR", "yfinance TR"])`.

2. **PR/TR ticker logic** (`fetch_data.py:816-843`, `fetch_hist.py:1325-1342`) — Rows with `data_source = "yfinance TR"` have no `ticker_yfinance_pr` value. Once the filter in item 1 is fixed, this logic must also be reviewed.

### 6.2 Redundancy Issues

- Instrument lists hardcoded 3x (fetch_data.py, fetch_hist.py, index_library.csv) with inconsistent metadata
- FX ticker maps defined 4 times across 2 files
- Sort-order dicts duplicated identically in fetch_data.py and fetch_hist.py
- Region overridden to "UK"/"Japan" in code, contradicting library values
- "Broad Asset Class" label computed in code rather than read from library

See `docs/METADATA_REDUNDANCY_REVIEW.md` for the full catalogue (12 items).

### 6.3 Operational Issues

- `macro_market.csv` and `macro_market_hist.csv` were missing from the GitHub Actions git-add list (now fixed in this commit)
- GitHub Actions auto-pauses after 60 days of no pushes
- Google Sheets CDN caching — always use Sheets export URL, not GitHub raw URL

---

## 7. Completed Phases

| Phase | Description | Status | Delivered |
|---|---|---|---|
| Simple Pipeline | 66 hardcoded instruments — snapshot + history | **Production** | market_data, market_data_hist, sentiment_data |
| Phase A — Comp Pipeline | ~302 library-driven instruments — snapshot + history | **Production** | market_data_comp, market_data_comp_hist |
| Phase B — US Macro (FRED) | 43 FRED series — snapshot + history | **Production** | macro_us, macro_us_hist |
| Phase B.2 — Surveys | Regional Fed, UMich sub-indices, ISM-related — snapshot + history | **Production** | macro_surveys, macro_surveys_hist |
| Phase C — International Macro | OECD CLI, unemployment, CPI, GDP, rates for 11 countries | **Production** | macro_intl, macro_intl_hist |
| Phase E — Macro-Market Indicators | 50 composite indicators (z-scores, regimes) | **Production** | macro_market, macro_market_hist |

---

## 8. Next Phases

### 8.1 Priority 1: Fix Breaking `data_source` Filter

**Impact:** High — comp pipeline silently returns zero yfinance instruments.
**Effort:** Small (2 lines of code + testing).
**Action:** Update the `data_source == "yfinance"` filter in `fetch_data.py` and `fetch_hist.py` to match the new `"yfinance PR"` / `"yfinance TR"` values in `index_library.csv`. Also review the PR/TR ticker column logic.

### 8.2 Priority 2: Code Consolidation (Redundancy Cleanup)

**Impact:** Medium — reduces maintenance burden and metadata drift.
**Effort:** Medium.
**Actions:**
- Move shared FX maps, sort-order dicts, and pence logic into `library_utils.py`
- Decide whether to drive the simple pipeline from `index_library.csv` (via a boolean flag column) or keep it hardcoded
- Resolve region overrides — update library to use "UK" / "Japan" directly, or document the runtime override as intentional
- Add `units`, `level_change`, and `broad_asset_class` columns to `index_library.csv` to eliminate hardcoded mappings

### 8.3 Priority 3: Phase D — FMP PMI Data

**Impact:** Low-medium — regional Fed surveys are already covered via FRED in macro_surveys.
**Status:** Not started. `FMP_API_KEY` secret not registered.
**Decision needed:** Review whether ISM Manufacturing PMI and ISM Services PMI are available via FRED directly. If so, FMP may be unnecessary. If not, register for a free FMP API key and implement `fetch_pmi.py`.

### 8.4 Priority 4: Instrument Expansion

**Impact:** Medium — broadens market coverage.
**Status:** Blocked on owner decision.
**Action:** Kasim to confirm target ETF list (Europe sector ETFs, EM regional ETFs, UK style ETFs, Asia/Japan coverage). Once confirmed, add rows to `index_library.csv` — no new Python modules needed.

### 8.5 Priority 5: Multi-Frequency Pipeline (Phase 2)

**Impact:** High — unlocks daily granularity for market data and native frequency for macro data.
**Status:** Detailed plan exists in `docs/multifreq_plan.md`. No implementation yet.
**Key changes:**
- Replace weekly Friday spine with ragged column format (each series gets its own date column)
- Market data: daily from 1990 (not weekly)
- Macro data: stored at native frequency (monthly, quarterly, annual) — no artificial forward-fill
- New alignment utilities in `library_utils.py` for on-demand cross-frequency joins
- All 50 macro-market indicator functions updated to consume ragged data
- Cell budget: ~8.4M / 10M Google Sheets limit — tight but feasible

**Risks:**
- Sheets cell budget is tight (8.4M/10M). Future tickers may require dropping `_Local` columns for USD-base instruments
- 50 indicator functions need updating and cross-validation against weekly branch output
- Z-score window equivalence: 260 weekly != 1300 daily (trading vs calendar days)

### 8.6 Priority 6: Calculated Fields (Phase F)

Many of these are already implemented in `compute_macro_market.py`. Remaining items:

| Field | Status |
|---|---|
| HY/IG ratio | Likely covered by macro-market indicators |
| EMFX basket (CNY, INR, KRW, TWD) | Not yet implemented |
| EEM/IWDA ratio | Not yet implemented |
| MOVE proxy (30-day realised vol on ^TNX) | Not yet implemented |
| Global PMI proxy | Not yet implemented |
| Global yield curve (avg of US/DE/UK/JP 10Y-2Y) | Not yet implemented |

**Action:** Audit the 50 indicators in `compute_macro_market.py` against this list to confirm coverage before building duplicates.

### 8.7 Priority 7: Sheets Export Audit (Phase G)

- Verify all 13 tabs are pushed correctly by the relevant modules
- Confirm tab names match exactly (lowercase with underscores)
- Record GIDs for all new tabs
- Confirm batch write logic (10,000 rows per call) is used for large tabs
- Confirm protected-tab guard blocks writes to `market_data` and `sentiment_data`

---

## 9. Environment & Secrets

| Secret | Used For | Status |
|---|---|---|
| `FRED_API_KEY` | All FRED API calls | Exists |
| `GOOGLE_CREDENTIALS` | Google Sheets push (service account JSON) | Exists |
| `BLS_API_KEY` | BLS nonfarm payrolls detail | Missing — may not be needed if FRED coverage is sufficient |
| `FMP_API_KEY` | ISM/PMI data via FMP | Missing — needed only if Phase D proceeds |

**Python version:** 3.11 (set in `update_data.yml`)
**Dependencies:** yfinance, pandas, numpy, requests, google-auth, google-api-python-client
