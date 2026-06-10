# Market Dashboard — Forward Plan

> Last updated: 2026-06-10

This is the project's forward-looking working doc for the **data pipeline only**. §0 sets the architecture rules every Claude session must read before touching data-layer code. §1 is the standalone phase / data-layer summary. §2 is the prioritised work queue. §3 captures feature roadmap items not yet on the queue. §4 holds the project chronology task. §5 cross-references `multifreq_plan.md` for the larger Phase 2 (multi-frequency) rebuild. The current code state lives in `manuals/technical_manual.md`; this doc and the technical manual are the only two contributor docs you need for **data pipeline work**.

> **Scope boundary (set 2026-05-06):** This document governs the data pipeline infrastructure only — its workflow, charting / explorer functionality, data sources, data series, multi-frequency rebuild, and operational scaffolding. It does **not** govern regime-based asset allocation work. All regime identification, indicator validation, regime-conditional portfolio construction, three-framework client implementations, backtest, and related agentic build phases live in the master plan: `../regime_AA_master_plan.docx`. If a future change touches both — e.g. the data pipeline needs to add a new source to feed a regime indicator — record the data-side work here and the regime-side work in the master plan, with a cross-reference. See `../_master_plan_drafts/responsibilities_boundary.md` for the durable record of the boundary.

---

## 0. Architecture Preferences — Claude must always follow

> **Status:** Permanent. These are non-negotiable rules adopted on 2026-04-26 after two avoidable refactors caused by hardcoding identifiers in Python instead of in CSVs. Every Claude session must read this section before touching any data-layer code.

### 0.1 The single rule

**Every identifier the pipeline fetches lives in one of the source-of-truth CSVs under `data/`. Never in Python.**

There are multiple source-of-truth CSVs — one per data source — not a single registry. The full inventory is in **§1 Data-Layer Registry**, but the active set today is:

- `data/index_library.csv` — comp pipeline tickers (~401 yfinance instruments)
- `data/macro_library_countries.csv` — 12 country codes + WB / IMF mappings
- `data/macro_library_fred.csv` — every FRED series ID
- `data/macro_library_oecd.csv` — every OECD SDMX dataflow / dimension key
- `data/macro_library_worldbank.csv` — every WB WDI indicator code
- `data/macro_library_imf.csv` — every IMF DataMapper indicator code
- `data/macro_library_dbnomics.csv` — every DB.nomics series path
- `data/macro_library_ifo.csv` — every ifo workbook sheet/column location
- `data/macro_library_boe.csv` — every BoE IADB series code (Stage D, 2026-04-30)
- `data/macro_library_ecb.csv` — every ECB Data Portal SDMX key (Stage D, 2026-04-30)
- `data/macro_library_boj.csv` — every BoJ Time-Series API code (Stage D, 2026-04-30)
- `data/macro_library_estat.csv` — every e-Stat statsDataId (Stage D, 2026-04-30)
- `data/source_fallbacks.csv` — T0 / T1 / T2 / T3 fallback chain per indicator (Stage B, 2026-04-30)
- `data/macro_indicator_library.csv` — every Phase E composite indicator
- `data/macro_library_boc.csv` — every BoC Valet series name (2026-05-28)
- `data/macro_library_statcan.csv` — every StatCan WDS vector ID (2026-05-28)
- `data/macro_library_ons.csv` — every ONS CDID taxonomy path (2026-05-28)
- `data/macro_library_bundesbank.csv` — every Bundesbank SDMX key (2026-05-28)
- `data/macro_library_abs.csv` — every ABS SDMX-CSV key (2026-05-28)
- `data/macro_library_istat.csv` — every ISTAT SDMX key (2026-05-28)
- `data/macro_library_bls.csv` — every BLS series ID (2026-05-28)
- `data/macro_library_insee.csv` — every INSEE BDM idbank (2026-06-09)
- `data/macro_library_bdf.csv` — every Banque de France Webstat Opendatasoft Explore v2.1 key (2026-06-09; rewritten 2026-06-10 for Opendatasoft stack; PROVISIONAL)

If the change you're about to make adds, removes, renames, or substitutes a fetched identifier — the only file you should be editing is the appropriate `data/macro_library_*.csv` (or `index_library.csv` / `macro_indicator_library.csv` depending on what you're changing). If you are reaching for a string literal in a `.py` file that looks like `"INDIRLTLT01STM"`, `"BSCICP02DEM460S"`, `"ISM/pmi/pm"`, `"BAMLHE00EHYIOAS"`, etc., **stop and put it in the relevant CSV instead.**

### 0.2 What counts as an "identifier"

In scope (must be CSV):

- FRED series IDs (e.g. `DGS10`, `MORTGAGE30US`)
- DB.nomics series paths (e.g. `ISM/pmi/pm`, `Eurostat/ei_bssi_m_r2/M.BS-ESI-I.SA.EA20`)
- OECD SDMX dataflow + dimension keys
- World Bank / IMF indicator codes
- ifo Excel sheet/column locations (already in `macro_library_ifo.csv`)
- yfinance tickers (already in `index_library.csv`)
- Any URL fragment that selects a specific dataset / series

Out of scope (may stay in Python):

- **Calculator wiring** — which calculator consumes which series. `supp.get("INDIRLTLT01STM")` inside `_calc_AS_IN_R1` is *logic*, not registry. The series being available is registry; the calculator's choice to consume it is logic. Keep the literal name in the calculator only because the calculator needs to look it up by name in the data dict it received.
- API base URLs and provider constants (`FRED_API_BASE`, `ECB_BASE_URL`)
- Computation parameters (z-score windows, regime thresholds)
- Column-name conventions and shared schema

### 0.3 Pre-commit checklist (Claude runs this before every commit that touches `.py` files)

1. **Grep for new string literals that look like data IDs.** Run `git diff --cached -U0 | grep -E '"[A-Z][A-Z0-9_]{3,}"'` on staged Python files. For each hit ask: *is this a fetched identifier?* If yes, the change belongs in a CSV.
2. **Grep for any new list literals named `*_to_fetch`, `*_series`, `*_indicators`, etc.** in staged `.py` files. Any such list is a registry and must be CSV-driven, not a Python literal.
3. **If a CSV row is being added/removed/changed, confirm there is no parallel Python literal that needs the same edit.** A CSV-driven loader is the only acceptable consumer of the registry.
4. **If a calculator consumes a new series, confirm the series is provisioned by the unified coordinator** (`fetch_macro_economic.py` → `macro_economic_hist.csv`), not by an ad-hoc fetcher in `compute_macro_market.py`. Calculators read from the unified data dict; they do not initiate fetches.

### 0.4 If a refactor is needed mid-task

If you discover the right place to add the identifier doesn't yet have CSV plumbing (e.g. a Python literal you'd otherwise extend), **stop and document the structural fix in this `forward_plan.md`** rather than perpetuating the drift. Adding one more line to a Python list is a 30-second debt that costs hours later. The decision-tree is:

- *Identifier already CSV-routed?* → edit the CSV. Done.
- *Identifier currently in a Python literal?* → either (a) refactor the literal into a CSV in the same PR, or (b) add a "Required refactor" entry under §2 and surface it to the user before merging the workaround. Never silently extend the literal.

### 0.5 Why this matters

Two refactors have already had to chase hardcoded identifiers out of the code:

- Stage 1 (2026-04-22): `INDICATOR_META` dict in `compute_macro_market.py` → `macro_indicator_library.csv`.
- Stage 2 (2026-04-23): per-source coordinators (FRED / OECD / WB / IMF / DB.nomics / ifo) → unified `macro_economic` snapshot driven by 6 CSVs.

PR2 (2026-04-26) added `INDIRLTLT01STM` directly to the `series_to_fetch` literal in `compute_macro_market.py::fetch_supplemental_fred()` instead of routing the new India 10Y series through the FRED library CSV. That is precisely the drift this section now prohibits. The supplemental list was the next refactor target — done 2026-04-26 (see §2 priority queue intro for the completion record).

---

## Table of Contents

0. [Architecture Preferences — Claude must always follow](#0-architecture-preferences--claude-must-always-follow)
1. [Project Phase Summary](#1-project-phase-summary)
2. [Resume Here — Priority Tasks](#2-resume-here--priority-tasks)
3. [New Feature Development](#3-new-feature-development)
4. [Project Chronology](#4-project-chronology)
5. [Multi-Frequency Pipeline (Phase 2)](#5-multi-frequency-pipeline-phase-2)

---
## 1. Project Phase Summary

> **Why this section lives in forward_plan and not technical_manual:** §1 Project Phase Summary and §1 Data-Layer Registry below are intentionally kept here as ongoing reminders for both the user and Claude — they anchor the architectural shape of what's been built so future feature work in §3 starts from the right baseline. Even though most rows are marked `Done` / `Production`, do **not** migrate this content to `technical_manual.md`; the technical manual is the canonical implementation reference, this is the planning anchor. (If you're a future Claude wondering "should I move this?" — no. The user and previous Claude already considered it.)

The project evolved from a single hardcoded pipeline into the current 6-phase architecture. Each runtime phase is wrapped in its own `try/except` so a failure in a later phase cannot affect earlier outputs. Phase A (US Macro / FRED), Phase B (Surveys), Phase C (International Macro) and Phase D (Business Survey Data) were consolidated into a single Phase ME on 2026-04-23 — see the Phase ME description below for details.

| Phase | Scope | Module(s) → Tab(s) | Status |
|---|---|---|---|
| Simple Pipeline | Original 66-instrument daily snapshot; consumed downstream by `trigger.py` | `fetch_data.py` → `market_data`, `sentiment_data` | Production (frozen) |
| Comp Pipeline | Library-driven ~390-instrument snapshot + weekly history from 1990 | `fetch_data.py` + `fetch_hist.py` → `market_data_comp`, `market_data_comp_hist` | Production |
| **Phase ME — Macro-Economic** (unified) | Single raw-macro data layer covering FRED / OECD / World Bank / IMF / DB.nomics / ifo / BoE / ECB / BoJ / e-Stat / LBMA. Replaces retired Phase A / B / C / D. | `fetch_macro_economic.py` + `sources/{fred,oecd,worldbank,imf,dbnomics,ifo,boe,ecb,boj,estat,lbma,nasdaq_data_link,countries}.py` → `macro_economic`, `macro_economic_hist` | Production |
| Phase E — Macro-Market Indicators | 99 composite indicators with 156w rolling z-scores, regimes, forward regimes, cycle timing (L/C/G) | `compute_macro_market.py` → `macro_market`, `macro_market_hist` | Production |
| Phase F — Calculated Fields | Synthetic columns (mostly absorbed into Phase E) | absorbed into `compute_macro_market.py` | Mostly Done |
| Phase G — Sheets Export Audit | 7-tab inventory, protected-tab guards across all 4 writers, legacy-tab cleanup, pipeline.log auto-commit | `library_utils.py` `SHEETS_*` constants | Done |
| Phase H — Daily Integrated Audit | Three-section daily audit (fetch outcomes / static checks / value-change staleness) running on the existing daily fetch's `pipeline.log`; perpetual GitHub-Issue notification with first-line `ALL CLEAN` / `N ISSUES` summary | `data_audit.py` + `.github/workflows/update_data.yml` (post-audit step) | Done |

### Phase-by-Phase Detail

#### Simple Pipeline — Production

66 hardcoded instruments (SPX, NDX, sector ETFs, FX majors, FRED yields, Fear & Greed, VIX term structure). Writes to the `market_data` and `sentiment_data` tabs. Preserved indefinitely for compatibility with `trigger.py`, which runs at 06:15 London time on a local Windows machine and reads `market_data` (GID `68683176`) only. No further work planned — the simple pipeline is frozen.

#### Comp Pipeline — Production

Library-driven expansion of the simple pipeline. ~390 instruments from `data/index_library.csv`; daily snapshot (`market_data_comp`) plus weekly Friday-close history from 1990 (`market_data_comp_hist`). 18-currency FX coverage via `COMP_FX_TICKERS` / `COMP_FCY_PER_USD` in `library_utils.py`. Pence correction dynamic (`.L` suffix + median > 50). Semantic `broad_asset_class` + `units` now read from the CSV rather than computed in code. The 7-step refactoring completed the transition from hardcoded lists to library-driven dispatch.

#### Phase ME — Macro-Economic (unified) — Production

A single coordinator (`fetch_macro_economic.py`) drives a per-source-module package (`sources/`) that produces one snapshot tab (`macro_economic`) and one history tab (`macro_economic_hist`). The history tab is a wide-form Friday spine from 1947, with 14 metadata rows above the data: Column ID, Series ID, Source, Indicator, Country, Country Name, Region, Category, Subcategory, Concept, cycle_timing, Units, Frequency, Last Updated.

**Replaces** four legacy coordinators (all deleted from the repo, all 8 of their tabs in `SHEETS_LEGACY_TABS_TO_DELETE`):

- `fetch_macro_us_fred.py` (Phase A) — US FRED series → retired tabs `macro_us[_hist]`
- `fetch_macro_international.py` (Phase C) — OECD / World Bank / IMF multi-country → retired tabs `macro_intl[_hist]`
- `fetch_macro_dbnomics.py` (Phase D Tier 2) — Eurostat / ISM → retired tabs `macro_dbnomics[_hist]`
- `fetch_macro_ifo.py` (Phase D ifo workbook) — DE_IFO subseries → retired tabs `macro_ifo[_hist]`

Phase D's "Tier 3 FMP calendar" track was paywalled and rejected on 2026-04-23 — the FMP module is also deleted. See `manuals/technical_manual.md` §13 for the durable Phase D retrospective (prior-attempts record).

**Coverage by source:**

- **FRED** — 80+ series across yields, inflation, labour, credit, surveys, commodities, OECD-mirror business/consumer confidence; back to 1947 where available. Library: `data/macro_library_fred.csv`.
- **OECD SDMX** (`sdmx.oecd.org`) — CLI, unemployment, 3-month interbank rate across 11 economies. Library: `data/macro_library_oecd.csv`. Known structural gap: OECD does not publish CLI for EA19 or CHE — `compute_macro_market.py` uses the DEU+FRA equal-weight average as the Eurozone CLI proxy.
- **World Bank WDI** — CPI YoY across 11 economies. Library: `data/macro_library_worldbank.csv`.
- **IMF DataMapper v1** — real GDP growth across 11 economies. Library: `data/macro_library_imf.csv`.
- **DB.nomics** — 13 series total: 3 Eurostat survey (EU_ESI / EU_IND_CONF / EU_SVC_CONF), 3 ISM (Manufacturing / New Orders / Services), 3 Eurostat real-economy (industrial production / retail volume / employment), plus 4 Stage B T1 fallback rows (IMF/IFS for `GBR_BANK_RATE` and `EA_HICP`; Eurostat for `DEU_IND_PROD` etc.). Library: `data/macro_library_dbnomics.csv`.
- **ifo Institute Excel** — 26 German business-survey series (Industry+Trade composite + Manufacturing / Services / Trade / Wholesale / Retail / Construction sub-sectors, plus Uncertainty + Cycle Tracer). History from 1991. Library: `data/macro_library_ifo.csv`.
- **BoE IADB** (Stage D, 2026-04-30) — 7 UK rates / yields series: Bank Rate (`IUDBEDR`), SONIA (`IUDSOIA`), gilt par yields S/M/L, gilt zero-coupon M/L. Library: `data/macro_library_boe.csv`.
- **ECB Data Portal** (Stage D, 2026-04-30) — 3 Euro-area rates / yields series: Deposit Facility Rate (FM dataset), AAA yield curve 2Y / 30Y (YC dataset). Library: `data/macro_library_ecb.csv`. Closes the DE 2Y bund-yield gap and the EA deposit-rate forcing-function row.
- **BoJ Time-Series Data Search API** (Stage D, 2026-04-30) — 2 Japan series: Policy Rate (FM01'STRDCLUCON) replacing the frozen FRED OECD-mirror row, and Tankan Large Manufacturer Business Conditions DI (CO'TK99F1000601GCQ01000) used as `JP_TANKAN1` to substitute for the proprietary au Jibun Bank Manufacturing PMI. Library: `data/macro_library_boj.csv`.
- **e-Stat REST API** (Stage D, 2026-04-30) — 1 Japan series: METI Indices of Industrial Production (statsDataId `0003446463`), replacing the frozen FRED OECD-mirror row. Library: `data/macro_library_estat.csv`. Requires `ESTAT_APP_ID` env var (injected via GitHub Actions secret).
- **Bank of Canada Valet** (2026-05-28) — 5 Canada series: policy rate (V39079), GoC 2Y/10Y benchmark bond yields, BoC CPI-median core inflation, USD/CAD reference rate. Keyless JSON. Library: `data/macro_library_boc.csv`.
- **Statistics Canada WDS** (2026-05-28) — 4 Canada series: CAN CPI (all-items, vector 41690973), unemployment rate (vector 2062815), + 2 more. Keyless POST API. Library: `data/macro_library_statcan.csv`.
- **ONS Zebedee /data API** (2026-05-28) — 6 UK series: CPI annual rate (D7G7), CPIH (L55O), real GDP (ABMI), unemployment rate (MGSX), employment rate (LF24), AWE regular pay growth (KAI9). Keyless. Partially closes the UK growth column (GBR_GDP_REAL wired). Library: `data/macro_library_ons.csv`.
- **Deutsche Bundesbank SDMX-ML** (2026-05-28) — 4 Germany series including DEU_BUND_10Y (daily, ultimate source — supersedes FRED monthly mirror) and DEU_BUND_1_2Y (genuine gap — no aggregator). Keyless. Library: `data/macro_library_bundesbank.csv`.
- **ABS Data API** (2026-05-28) — 5 Australia series: CPI (all-groups), real GDP, GDP growth QoQ, unemployment rate 15+ SA, participation rate. Keyless SDMX-CSV. Library: `data/macro_library_abs.csv`.
- **ISTAT SDMX API** (2026-05-28) — 3 Italy series: monthly unemployment rate 15-74 (dataflow 151_874) and industrial production total ex-construction (dataflow 115_333). Vintage (EDITION) resolution at fetch time. Keyless. Library: `data/macro_library_istat.csv`.
- **BLS Public Data API** (2026-05-28) — 4 US series; BLS is the ultimate source for `USA_CPI_INDEX`, `USA_CORE_CPI_INDEX`, `USA_UNEMPLOYMENT` (FRED is the automatic fallback); `USA_AVG_HOURLY_EARN` (CES0500000003) is a genuine coverage gap with no FRED-library equivalent. BLS_API_KEY optional. Library: `data/macro_library_bls.csv`.
- **INSEE BDM SDMX-ML** (2026-06-09) — 3 France series (INSEE is the ultimate/primary source; supersedes OECD/Eurostat aggregators): `FRA_BUS_CONF` (Business Climate), `FRA_UNEMPLOYMENT` (ILO quarterly), `FRA_GDP_INDEX` (chained volume SA-WDA). Keyless + optional `INSEE_API_KEY`. Library: `data/macro_library_insee.csv`.
- **Banque de France Webstat Opendatasoft Explore v2.1** (2026-06-09; migrated from legacy IBM API Connect → Opendatasoft 2026-06-10) — 2 France MFI lending-rate series (`FRA_LOAN_RATE_HOUSE`, `FRA_LOAN_RATE_NFC`). **PROVISIONAL** — the public catalogue exposes only the archived-reports dataset; the MIR dataset_id + ODSQL filter must be discovered on the first credentialed run. Library: `data/macro_library_bdf.csv` (series_id format: `<dataset_id>|<odsql_where>`, with the legacy SDMX dot-keys preserved in-line under `PROVISIONAL|legacy_sdmx_key=...`).

**Country registry:** `data/macro_library_countries.csv` is the single source of truth for the 12 country codes (USA, GBR, DEU, FRA, ITA, JPN, CHN, AUS, CAN, CHE, EA19, IND) and their WB / IMF code mappings. `IND` was added in the 2026-04-26 supplemental refactor for the India 10Y bond yield, with empty `wb_code` / `imf_code` so it doesn't fan out into multi-country queries.

**Architecture invariant (per §0):** every fetched identifier lives in `data/macro_library_*.csv`. As of the 2026-04-26 supplemental refactor `compute_macro_market.py` contains zero direct API contact — every series the calculators read is provisioned through the unified hist.

#### Phase E — Macro-Market Indicators — Production

92 composite indicators computed from the unified `macro_economic_hist` (per §1 Phase ME) plus the comp-pipeline market data. Each indicator produces: raw value, 156-week (3-year) rolling z-score, regime classification, forward regime signal (`improving`/`stable`/`deteriorating`, with optional `[leading]` suffix), and z-score trend diagnostics (`intensifying` / `fading` / `reversing` / `stable`) against 1w, 4w, 13w lookbacks. A `cycle_timing` column (L/C/G) classifies each indicator's position in the business cycle (90 Leading, 2 Coincident, 0 Lagging — durable detail in `manuals/technical_manual.md` §13). Metadata is a single source of truth in `data/macro_indicator_library.csv` — no hardcoded `INDICATOR_META` dict in Python. The library carries `concept` + `subcategory` columns populated against a canonical 17-concept taxonomy (Equity, Rates / Yields, Credit / Spreads, Inflation, Sentiment / Survey, Leading Indicators, Growth, Labour, Cross-Asset, Volatility, Momentum, FX, Money / Liquidity, Housing, Manufacturing, External / Trade, Consumer); these surface in `macro_market.csv` and the explorer payload. Outputs `macro_market` (snapshot) and `macro_market_hist` (weekly history). As of the 2026-04-26 supplemental refactor Phase E contains zero direct API contact — every series the calculators read is provisioned through the unified hist; PR3 (2026-04-26) cleared the build-phase `DataFrame is highly fragmented` warnings, and the 2026-04-27 fix-forward cleared the output-phase ones plus the EU_Cr1 / `BAMLEC0A0RMEY` regression. EU_Cr1 (Euro IG spread) returns n/a until a free Euro IG corporate yield source is wired (see §1 Known Data Gaps); EU_Cr2 (Euro HY spread, reads `BAMLHE00EHYIOAS`) covers the Euro-HY regime as a separate indicator.

`docs/indicator_explorer.html` (built by `docs/build_html.py`) renders the library through a three-section sidebar — **Macro Market Indicators** (Phase E composites, By Region ↔ By Concept toggle), **Economic Data** (every raw-macro source merged, By Country ↔ By Concept toggle), **Market Data** (yfinance comp pipeline, Local ↔ USD variant). Filter pipeline supports text search, market-data variant, L/C/G cycle-timing chips, and country dropdown. Country list is read from `data/macro_library_countries.csv` (no hardcoded JS literal — per §0).

#### Phase F — Calculated Fields — Partial

Several synthetic fields originally scoped under Phase F have been absorbed into Phase E indicators (HY/IG ratio → `US_Cr3`; value/growth → `US_EQ_F2`; US 5-regime credit spread → `US_Cr2`; EM vs DM equity ratio → `GL_G1` as EEM/URTH; EMFX basket → `FX_EM1` as of 2026-04-21; MOVE index → already ingested as `^MOVE` and used in `US_V2`; Global PMI proxy → `GL_PMI1`).

Remaining outstanding calculated fields (global yield curve composite + per-index breadth-above-200DMA) are tracked in §3.1.5. New indicators follow the CSV-driven pattern: write a `_calc_*` function, add to `REGIME_RULES` and the relevant `_*_CALCULATORS` dict, add a row to `macro_indicator_library.csv`.

#### Phase G — Sheets Export Audit — Done (2026-04-21, refreshed 2026-04-26)

Active tab inventory (all 7 tabs, all lowercase-underscore, all production):

| Tab | Writer module | Snapshot/History | Notes |
|---|---|---|---|
| `market_data` | `fetch_data.py` | snapshot | Simple pipeline; consumed by downstream `trigger.py`. **Protected.** |
| `market_data_comp` | `fetch_data.py` | snapshot | Comp pipeline (~390 instruments). |
| `market_data_comp_hist` | `fetch_hist.py` | history (weekly) | Weekly Friday-close prices from 1990. |
| `macro_economic` | `fetch_macro_economic.py` | snapshot | Unified raw macro layer: FRED + OECD + WB + IMF + DB.nomics + ifo. |
| `macro_economic_hist` | `fetch_macro_economic.py` | history (weekly) | Weekly Friday spine from 1947, 14 metadata rows above the data. |
| `macro_market` | `compute_macro_market.py` | snapshot | 92 composite indicators. |
| `macro_market_hist` | `compute_macro_market.py` | history (weekly) | Weekly indicator history. |

`SHEETS_LEGACY_TABS_TO_DELETE` (in `library_utils.py`) sweeps 8 retired tabs from the pre-Stage-2 architecture on every run: `macro_us[_hist]`, `macro_intl[_hist]`, `macro_dbnomics[_hist]`, `macro_ifo[_hist]`. All 4 active writer modules check `SHEETS_PROTECTED_TABS` before writing.

Audit findings fixed on 2026-04-21 / 2026-04-23:

- **Protected-tab guard was missing** in three writer modules. All four writers (`fetch_data.py`, `fetch_hist.py`, `fetch_macro_economic.py`, `compute_macro_market.py`) now check `SHEETS_PROTECTED_TABS` before writing.
- **Single source of truth for tab state**: `library_utils.py` exports `SHEETS_PROTECTED_TABS`, `SHEETS_ACTIVE_TABS`, and `SHEETS_LEGACY_TABS_TO_DELETE` as `frozenset`s.
- **Clear-range widened** from `A:Z` (26 cols) to `A:ZZ` (702 cols) on the macro writers to handle wider schemas.
- **Pipeline log auto-commit** (PR1, 2026-04-25): the GitHub Actions workflow now pipes both Python steps through `tee pipeline.log` with `set -o pipefail` and commits `pipeline.log` to the repo on every run via an `if: always()` step. Useful for diagnosing failures without needing to download artifacts.

Outstanding (low value): record Sheets GIDs for each active tab in `manuals/technical_manual.md`; build an automated "tab drift" audit that flags tabs in the Sheet but not in `SHEETS_ACTIVE_TABS ∪ SHEETS_LEGACY_TABS_TO_DELETE`.

Batch writes (10k rows/call) are only implemented in `fetch_hist.py` — the largest tab (`market_data_comp_hist`, ~9,000 rows) sits within the Sheets API's single-call payload limit at current column count, so no other writer has hit a batching need yet. Revisit if column count grows significantly.

#### Phase H — Daily Integrated Audit + Writeback — Done (2026-04-28; writeback added 2026-04-29)

`data_audit.py` runs as the post-fetch / post-build step in the daily GitHub Actions workflow. Three sections produced into `data_audit.txt` (full report) + `audit_comment.md` (Markdown for the GitHub Issue comment):

- **Section A — Fetch outcomes.** Scrapes `pipeline.log` for yfinance dead tickers (cross-checked against `market_data_comp_hist.csv` to filter transient warnings) and FRED final failures (only the `— skipping` suffix; retried-then-recovered errors are filtered out).
- **Section B — Static checks.** Country-code orphans, indicator-id uniqueness, calculator registration, `_get_col(...)` column existence on the unified hist, **and registry drift across all 3 hist↔library pairs** (comp / macro_economic / macro_market) — orphan column reports tell the operator to run `python library_sync.py --confirm`. The drift check imports `library_sync`'s expected/present helpers so column-derivation rules live in one place.
- **Section C — Value-change staleness.** Walks every column of `macro_economic_hist.csv` and flags series whose last *value change* is older than the per-row tolerance. Tolerances come from `data/freshness_thresholds.csv` (Daily 5d / Weekly 10d / Monthly 45d / Quarterly 120d / Annual 540d) with a per-row `freshness_override_days` override on every `data/macro_library_*.csv` (48 rows widened in the 2026-04-29 bulk pass; cluster→override mapping in `manuals/technical_manual.md` §9.8).

`audit_writeback.py` runs immediately after `data_audit.py` (added 2026-04-29). Parses Section A's `YFINANCE_DEAD` list, maintains `data/yfinance_failure_streaks.csv` (per-ticker dead-list streak counter), and flips `validation_status` from `CONFIRMED` to `UNAVAILABLE` on any row whose streak hits N=14 consecutive days. Manual override wins — re-setting `CONFIRMED` after a real fix restarts the streak naturally. Appends a one-line summary to `audit_comment.md` so the GitHub Issue comment captures today's writeback actions.

`library_sync.py` is the operator-gated companion to the registry-drift check — covers 3 hist↔library pairs, archives orphan columns to `data/_archived_columns/<hist_basename>__<column_id>__<date>.csv` before dropping them. Default mode is dry-run.

A "Post daily audit to perpetual GitHub Issue" workflow step then posts `audit_comment.md` to a `daily-audit`-labelled GitHub Issue every day. The first line of the comment is the one-sentence ISSUE/CLEAN summary; collapsible detail follows. GitHub's native notification email gives the daily heartbeat without any SMTP secrets.

The audit's first-run baseline (2026-04-28: 75 stale + 22 dead + 1 schema issue) was fully worked down 2026-04-29; durable outcomes are recorded in `manuals/technical_manual.md` (§7 / §9.8 / §13) with ongoing forcing-function gaps captured in §1 Known Data Gaps below.

### Data-Layer Registry (single source of truth — per §0)

These CSVs in `data/` are the single source of truth for everything the pipeline fetches or computes. Adding / removing / renaming a series = edit the relevant CSV. Never a Python literal (per §0.1).

| File | Rows | Owner | Used by |
|---|---|---|---|
| `index_library.csv` | ~401 | Comp pipeline | `fetch_data.py`, `fetch_hist.py` |
| `macro_library_countries.csv` | 12 | Phase ME | `sources/countries.py` (canonical / WB / IMF code mappings) |
| `macro_library_fred.csv` | ~82 | Phase ME | `sources/fred.py` |
| `macro_library_oecd.csv` | 3 | Phase ME | `sources/oecd.py` |
| `macro_library_worldbank.csv` | 1 | Phase ME | `sources/worldbank.py` |
| `macro_library_imf.csv` | 1 | Phase ME | `sources/imf.py` |
| `macro_library_dbnomics.csv` | 13 | Phase ME | `sources/dbnomics.py` (incl. 4 Stage B T1 fallback rows) |
| `macro_library_ifo.csv` | 26 | Phase ME | `sources/ifo.py` |
| `macro_library_boe.csv` | 7 | Phase ME (Stage D, 2026-04-30) | `sources/boe.py` (BoE IADB — Bank Rate, SONIA, gilt par/zero-coupon S/M/L) |
| `macro_library_ecb.csv` | 3 | Phase ME (Stage D, 2026-04-30) | `sources/ecb.py` (ECB Data Portal — Deposit Rate, AAA yield curve 2Y/30Y) |
| `macro_library_boj.csv` | 2 | Phase ME (Stage D, 2026-04-30) | `sources/boj.py` (BoJ Time-Series — Policy Rate, Tankan Large Mfg DI) |
| `macro_library_estat.csv` | 1 | Phase ME (Stage D, 2026-04-30) | `sources/estat.py` (e-Stat — METI IIP) |
| `macro_library_nasdaqdl.csv` | 0 | Phase ME (§3.9, 2026-05-08; emptied 2026-05-09) | `sources/nasdaq_data_link.py` — scaffolding kept for any future free NDL dataset; LBMA/GOLD removed when discovered to be on NDL's paid tier |
| `macro_library_lbma.csv` | 1 | Phase ME (§3.9, 2026-05-09) | `sources/lbma.py` (LBMA prices.lbma.org.uk JSON — daily gold PM USD fix back to 1968) |
| `macro_library_boc.csv` | 5 | Phase ME (2026-05-28) | `sources/boc.py` (BoC Valet — policy rate, GoC 2Y/10Y yields, CPI-median, USD/CAD) |
| `macro_library_statcan.csv` | 4 | Phase ME (2026-05-28) | `sources/statcan.py` (StatCan WDS — CAN CPI, unemployment, + 2 more) |
| `macro_library_ons.csv` | 6 | Phase ME (2026-05-28) | `sources/ons.py` (ONS Zebedee — GBR CPI/CPIH, real GDP, unemployment, employment, AWE) |
| `macro_library_bundesbank.csv` | 4 | Phase ME (2026-05-28) | `sources/bundesbank.py` (Bundesbank SDMX — DEU Bund 10Y/1-2Y yields) |
| `macro_library_abs.csv` | 5 | Phase ME (2026-05-28) | `sources/abs.py` (ABS SDMX — AUS CPI, GDP, unemployment, participation) |
| `macro_library_istat.csv` | 3 | Phase ME (2026-05-28) | `sources/istat.py` (ISTAT SDMX — ITA unemployment, industrial production) |
| `macro_library_bls.csv` | 4 | Phase ME (2026-05-28) | `sources/bls.py` (BLS — USA CPI, core CPI, unemployment, avg hourly earnings) |
| `macro_library_insee.csv` | 3 | Phase ME (2026-06-09) | `sources/insee.py` (INSEE BDM — FRA business climate, unemployment, GDP volume; keyless) |
| `macro_library_bdf.csv` | 2 | Phase ME (2026-06-09; rewritten 2026-06-10; PROVISIONAL) | `sources/bdf.py` (BdF Webstat Opendatasoft Explore v2.1 — FRA MFI lending rates; BDF_API_KEY missing; dataset_id + ODSQL filter to be discovered on first credentialed run) |
| `source_fallbacks.csv` | 10 | Phase ME (Stage B, 2026-04-30; §3.9 row added 2026-05-08; T0 swapped to LBMA 2026-05-09) | Documentation-only registry of T0 / T1 / T2 / T3 chain per indicator (runtime walker not yet built; effect is implicit via `_collect_all_indicators` ordering) |
| `macro_indicator_library.csv` | 99 | Phase E | `compute_macro_market.py` (composite indicator registry) — 93 original + `GLOBAL_GOLD1` (§3.9) + 5 per-region inflation composites (`US/UK/EU/JP/CN_INFL1`, §3.1.3) + `US_INFEXP1` |
| `reference_indicators.csv` | 206 | Reference (gap audit) | §3.1.1 cross-reference; not consumed by the runtime pipeline |

**Read order in `fetch_macro_economic.py`:** `fred → oecd → worldbank → imf → dbnomics → ifo → boe → ecb → boj → estat → nasdaqdl → lbma → boc → statcan → ons → bundesbank → abs → istat → bls → insee → bdf`. Each `sources/*.py` exposes `load_library() -> list[dict]` returning the unified indicator schema (`source`, `source_id`, `col`, `name`, `country`, `category`, `subcategory`, `concept`, `cycle_timing`, `units`, `frequency`, `notes`, `sort_key`). Last writer wins per column — this is the implicit fallback mechanism documented in `data/source_fallbacks.csv`.

**Library validity** is now covered by Phase H — the daily integrated audit captures HTTP errors + dead tickers + schema-drift static checks + history-preservation row counts (Section D, added 2026-04-30) during the existing fetch (no separate probe needed).

### Known Data Gaps (consolidated, refreshed 2026-05-02)

These are cases where a planned series is unavailable from any free source we accept. Documented here so they aren't re-investigated repeatedly.

| Gap | Impact | Resolution |
|---|---|---|
| **China 10-Year government bond yield** | `AS_CN_R1` (China–US 10Y spread) returns NaN against a direct CN 10Y series. FRED carries only the short-term `IR3TTS01CNM156N`; OECD MEI long-term-rate has no CN series. The dangling `_get_col(mu, "CHN_GOVT_10Y")` reference in `_calc_AS_CN_R1` is deliberate (self-wires the day a source lands) and is allow-listed in `data_audit.py::KNOWN_MISSING_COLUMNS` so the static check doesn't churn. | Partial proxy in place via Stage F: `CBON` (VanEck CN Govt + Policy-Bank Bond ETF) added to `index_library.csv` — distribution yield acts as a tradable proxy for the regime model. Direct yield series remains an open path; details in §3.1.6. |
| **ifo workbook download failing (2026-05-08 → 2026-05-27)** | All 26 ifo `DE_*` series stopped landing in `macro_economic_hist.csv` for ~3 weeks; `DE_IFO` showed in the daily audit as a missing-column failure. `sources/ifo.py` was trying `secure/timeseries/gsk-d-<ym>.xlsx` (German at secure) and `<YYYY-MM>/gsk-e-<ym>.xlsx` (English at dated folder), both of which returned a 3038-byte HTML page. The diagnostic probe (`scripts/ifo_probe.py`, run from CI 2026-05-27) settled the cause: not anti-bot — the **English file under `secure/timeseries/gsk-e-<ym>.xlsx`** is the live path, and our code wasn't trying that combination. ifo additionally throttles intermittently with the same 3038-byte HTML for files that exist. | ✅ **Resolved 2026-05-27.** Fixed in two PRs: (1) **#150 URL correction** — `_candidate_urls()` switched to `secure/timeseries/gsk-e-<YYYYMM>.xlsx` (English, secure path) across current + prior 3 months, with `gsk-d` as a last-resort fallback; (2) **#151 fail-fast** — `_try_download_xlsx` retries with backoff, `_resolve_workbook_impl()` is cached process-level (success *and* failure), per-request timeout 15s + retries 2 → ifo's worst-case time bounded to ~3 min instead of ~60 min. The 04:53 UTC 2026-05-28 daily run validated the full path: month-walked from May (throttled) to April (`gsk-e-202604.xlsx`, 97,859 bytes — real xlsx), parsed all 26 `DE_*` columns, audit `missing_columns` clean. DB.nomics ifo-provider fallback **confirmed dead** during investigation (DB.nomics carries no ifo series). Durable fix lives in `manuals/technical_manual.md` §5 (ifo source) + §11 Pattern 10 (fail-fast network sources). |
| **Euro IG corporate effective yield** (target series: ICE BofA Euro Corporate Index Effective Yield) | `EU_Cr1` (Euro IG spread = corp yield − ECB AAA 10Y govt yield) returns NaN against a direct corp-yield series. FRED `BAMLEC0A0RMEY` 400s on every call; ECB SDW publishes no free aggregate Euro IG yield; iBoxx EUR Corporate is paywalled. | Partial proxy in place via Stage F: `IEAC.L` (iShares EUR IG Corp Bond ETF) added to `index_library.csv` — distribution yield acts as a tradable proxy. ECB AAA 10Y govt-yield half is already wired in `fetch_ecb_euro_ig_spread()`. Direct corp-yield paths (ECB MIR composite cost of borrowing; Bundesbank SDMX corporate-bond yields) tracked in §3.1.6. EU_Cr1 returns n/a until a direct series is wired; EU_Cr2 (Euro HY) remains its own indicator. |
| **`BSCICP02JPM460S` / `BSCICP02CNM460S`** (OECD Business Confidence — Japan / China on FRED) | Don't exist on FRED. | Japan covered by `JP_PMI1` (proprietary, returns Insufficient Data); China covered by `CHNBSCICP02STSAM` (different ID). |
| **`DE_ZEW1`** (ZEW Economic Sentiment) | Returns Insufficient Data. ZEW Mannheim licences the archive; no free API. | Substitute: German sentiment is covered by `DE_IFO1` + `DEU_BUS_CONF`. |
| **`JP_PMI1`** (au Jibun Bank Japan Manufacturing PMI) | Returns Insufficient Data. S&P Global proprietary, no monthly free source. | ✅ Functionally resolved 2026-04-30 — `JP_TANKAN1` (BoJ Tankan Large Mfg Business Conditions DI) wired via `sources/boj.py` substitutes for the proprietary PMI. See `manuals/technical_manual.md` §5 BoJ section. |
| **`CN_PMI2`** (Caixin China Manufacturing PMI) | Returns Insufficient Data. S&P Global proprietary. | Substitute: Chinese manufacturing is covered by `CN_PMI1` (OECD BCI for China). |
| **OECD CLI for EA19 / CHE** | Not published by OECD. | `compute_macro_market.py` uses DEU+FRA equal-weight as the Eurozone CLI proxy. |
| **`NAPMOI`** (FRED ISM new orders) | Retired by FRED in April 2026 (HTTP 400 from late April onwards). | `US_ISM1` reads `ISM_MFG_NEWORD` from DB.nomics via the unified hist (PR2, 2026-04-26). |
| **9 stale FRED rows kept as forcing functions (2026-04-29)** | FRED OECD-mirror data has frozen for `JPN_POLICY_RATE` (2008-12), `CHN_POLICY_RATE` (2015-11), `GBR_BANK_RATE` (BOERUKM, 2016-08), `CHN_M2` (2019-08), `EA_HICP` (`EA19CPALTT01GYM`, 2023-01), `CHN_IND_PROD` (CHNPRINTO01IXPYM, 2023-11), `DEU_IND_PROD` (DEUPROINDMISMEI, 2024-03), `JPN_IND_PROD` (JPNPROINDMISMEI, 2024-03), `EA_DEPOSIT_RATE` (ECBDFR, 2025-06). Rows are kept in `macro_library_fred.csv` so the daily audit keeps them surfaced. None feed any Phase E indicator. | ✅ 7 of 9 resolved via Stage B T1 fallbacks + Stage D T2 modules (DB.nomics IMF/IFS, Eurostat, BoE IADB, ECB Data Portal, BoJ Time-Series, e-Stat). Per-indicator chain in `data/source_fallbacks.csv`; status in `manuals/technical_manual.md` §13. Two remain accepted gaps: `CHN_M2` and `CHN_IND_PROD` (NBS/PBoC have no free programmatic source). |
| **10 stale series in the 117d cluster (2026-04-29 baseline)** | `PERMIT`, `FEDFUNDS`, `CMRMTSPL`, `FRA_UNEMPLOYMENT`, `DEU_UNEMPLOYMENT`, `EU_ESI`, `EU_IND_CONF`, `EU_SVC_CONF`, `ISM_MFG_PMI`, `ISM_MFG_NEWORD` — all 117d old (last_obs 2026-01-02) at the 2026-04-28 audit. 117d for monthly publishers is too long for normal lag; suggests a real fetch or publisher issue, not benign cadence. | Deliberately **not** widened in the 2026-04-29 override pass — left at base 45d tolerance so the daily audit keeps surfacing them. Status to be re-checked at Stage G closeout against the latest audit; any publisher genuinely silent will be documented here as a permanent gap. |
| **Investing.com / Trading Economics / S&P Global direct / FMP economic calendar** | Evaluated and rejected: scraping fragility (Cloudflare), paid-only APIs, FMP endpoints paywalled August 2025. | Do not revisit. |


---

## 2. Resume Here — Priority Tasks

**Active priority is open.** The audit-remediation backlog (sub-tracks 1–4) closed 2026-04-29; durable outcomes live in `manuals/technical_manual.md` (§7, §9.8 cluster reference, §9.9 library_sync, §9.10 audit_writeback, §13 ticker dispositions, §14 daily flow) and ongoing forcing-function gaps live in §1 Known Data Gaps.

**Recent completed work (session 2026-05-27/28):**
- ✅ §3.9 LBMA gold long-run series — `GOLD_USD_PM` raw series 1968-04 → present in `macro_economic_hist`; `GLOBAL_GOLD1` Phase E composite live (safe-haven-bid regime).
- ✅ §3.1.3 inflation composites — 5 per-region (`US/UK/EU/JP/CN_INFL1`) + `US_INFEXP1` shipped via #152.
- ✅ ifo workbook outage resolved — see §1 Known Data Gaps row.
- ✅ DB.nomics fail-fast / circuit breaker (#154) — outage no longer stalls the pipeline ~1hr.
- ✅ 1306.T 10:1 split back-adjustment (#148) + generic data-audit split detector (#155).
- ✅ Sister-CSV writer Option B (forward extension); open `keep="first"` self-heal question tracked in §3.6a.

**Recent completed work (session 2026-05-28 / 2026-06-09):**
- ✅ 7 keyless source adapters (PR #157, 2026-05-28): `sources/boc.py`, `sources/statcan.py`, `sources/ons.py`, `sources/bundesbank.py`, `sources/abs.py`, `sources/istat.py` (6 keyless), plus `sources/bls.py` (BLS_API_KEY optional). 36 new series rows across 7 libraries.
- ✅ `sources/insee.py` (PR #160/161, 2026-06-09) — 3 French macro series (business climate, unemployment, GDP volume) via INSEE BDM keyless SDMX. Supersedes OECD/Eurostat as primary source for France.
- ✅ `sources/bdf.py` (PR #161, 2026-06-09) — Banque de France Webstat scaffolding + 2 provisional MFI lending-rate rows. PROVISIONAL — BDF_API_KEY not yet in GitHub Secrets; series keys unverified. Added to prod but skips gracefully.
- ✅ Primary-source smoke tests (2026-06-09) — `test_bls_smoke.py`, `test_insee_smoke.py`, `test_bdf_smoke.py`; new non-blocking CI step runs daily and appends to `pipeline.log`.

**Near-term follow-up — BdF Webstat migration (post-mortem 2026-06-10, rewrite shipped 2026-06-10):**
- ✅ First credentialed `workflow_dispatch` run completed 2026-06-10 (run id `27271070256`) returned **HTTP 401 `"Invalid client id or secret"`** on both `MIR1/...` series. Root cause identified the same day: Banque de France had already migrated Webstat from the legacy IBM API Connect stack (`api.webstat.banque-france.fr/webstat-fr/v1`, SDMX-JSON, `X-IBM-Client-Id` + `X-IBM-Client-Secret`) to an Opendatasoft Explore v2.1 instance (`webstat.banque-france.fr/api/explore/v2.1/`, records JSON, single `Authorization: Apikey <key>` header). The user's portal showed a single Apikey (no Application, no Client Secret), confirming registration on the new portal.
- ✅ `sources/bdf.py` rewritten end-to-end against the Opendatasoft Explore v2.1 stack (2026-06-10). New series-id format: `<dataset_id>|<odsql_where>` in a single library column. Public Python API unchanged (`load_library()`, `fetch_series_as_pandas(series_id, col_name=None)`). `BDF_API_SECRET` removed from `.github/workflows/update_data.yml`. Smoke test and technical-manual §5 + §9.5.21 entries updated.
- 🟡 **PROVISIONAL outstanding:** the public Opendatasoft v2.1 catalogue (anonymous probe) exposes only one dataset (`tableaux_rapports_preetablis` = archived-reports metadata); the 37k+ time series including the MIR (monetary financial institution interest rate) dataset are gated behind the developer-portal login. Both library rows still carry `series_id = 'PROVISIONAL|legacy_sdmx_key=<dot-key>'` to preserve the original SDMX targeting (`M.FR.B.A2C.A.R.A.2250.EUR.N` for households, `M.FR.B.A2A.A.R.A.2240.EUR.N` for NFCs). Next credentialed session: query `/catalog/datasets?q=MFI+interest+rates`, walk the resulting dataset schema, translate the SDMX dot-keys into ODSQL `where=` predicates, and commit the upgraded CSV. The fetcher already detects `dataset_id == 'PROVISIONAL'` and skips with a loud warning; the smoke test skips PROVISIONAL rows individually so CI stays green until they're upgraded.

**Recent completed work (session 2026-06-10):**
- ✅ §3.12 OECD MEI feed — 17 FRED rows landed (7 missing-region 10Y yields IRLTLT01{US,FR,JP,CA,AU,NL,CH}M156N + 10 share-price indices SPASTT01{...}M661N). NLD added to country registry. Continuity Jan-1957 → present verifies on next daily run.
- ✅ §3.14 monthly z-score sampling — `data/macro_market_monthly_hist.csv` shipped via `df_hist.resample("ME").last()` in `run_phase_e`; ~320 month-end rows × ~376 cols, same wide schema as the weekly hist. Underlying 156-week z-score unchanged; existing weekly output untouched. Schema documented in tech_manual §7.

Candidate next tracks:
- **§3.1 Macro & Market Coverage Expansion** — unified track. Stages A / B / D / F shipped 2026-04-30; **§3.1.3 inflation composites done 2026-05-28**. **Outstanding: Stage C** (regional roll-up — UK growth via ONS, JP growth via e-Stat extension), **Stage E** (survey deep-dive against `G20_PMI_Master_Table.docx`), GDP Now wiring (§3.1.4), the §3.1.3 follow-up (core inflation series for UK/EA/JP/CN), the §3.9 follow-up (multi-commodity long-run prices), and **Stage G** closeout. Note: long-run market and macro data sources catalogued in `../longrun_assetclass_data_sources.md` (OECD MEI feed via FRED, Shiller, Ken French, IMF Primary Commodity Prices, BoE Millennium, JST) need wiring into the data pipeline as part of this expansion — driven by master plan Phase 0; data-side work plan tracked here, now detailed and status-reconciled as §3.12 (OECD MEI) and §3.13 (long-run layer) per the regime-AA v2 handoff.
- **§3.2 Retire the Simple Pipeline** — deprecation track.
- **§3.3 PE Ratio Integration** — small contained feature add.
- **§3.4 Market Index Expansion** — broadens market coverage; CSV-only additions to `index_library.csv`.
- **§3.6 Incremental Fetch Mode** — performance work for `fetch_hist.py`.
- **§3.8 Weekly Retirement Review Workflow** — closes the auto-remediation gap left by the daily audit.
- **Regime-AA v2 asks (§3.12–§3.17)** — cross-repo handoff (`manuals/2026-06-10-regime-aa-v2-pipeline-handoff.md`), status-reconciled. **CRITICAL:** §3.12 OECD MEI ingestion (🟡 partial — FRED CSV rows) and §3.14 monthly z-score sampling (🟡 partial — window already exists, needs month-end output) gate regime-AA Phase 0 / Phase 2. **HIGH:** §3.13 long-run source modules. See §3.12–§3.17 for the per-ask status.

> **Note: §3.5 and §3.7 are MOVED.** Regime-based indicator labelling, ML-driven regime identification, and the regime-driven back-test / portfolio optimiser have been moved out of this document into `../regime_AA_master_plan.docx`. The stub sections at §3.5 and §3.7 below record the move and direct readers to the relevant master-plan sections.

---

## 3. New Feature Development

### 3.1 Macro & Market Coverage Expansion

**Priority:** High — provides the macro + market data foundation for the regime work owned by `../regime_AA_master_plan.docx`. Most architecture is now shipped (Stages A / B / D / F per `manuals/technical_manual.md`); §3.1 below tracks only what's outstanding.

**Status:** Active. Stages A (history-preservation safeguard), B (T1 fallback chains for 4 of 9 forcing-function rows), D (4 T2 source modules — BoE / ECB / BoJ / e-Stat), F (community-ticker review + 14 ETFs added) shipped. **Outstanding: Stages C / E / G + targeted growth/inflation expansion + GDP Now wiring.**

**Architecture context** (durable — lives in `manuals/technical_manual.md`):
- **History-preservation safeguard** — `*_hist_x.csv` sister files; `library_utils.write_hist_with_archive()` / `load_hist_with_archive()` helpers — see tech_manual §11 Pattern 9.
- **Fallback-chain registry** — `data/source_fallbacks.csv` records the T0 / T1 / T2 / T3 chain per indicator; runtime walker is implicit (later sources overwrite earlier sources at the column level via `_collect_all_indicators` ordering) — see tech_manual §7.
- **Source verdicts (consolidated catalogue)** — see tech_manual §5 Data Sources & APIs. The full G20-catalogue source list with PRIMARY-LIVE / TIER1 / TIER2 / SKIP-PAID statuses lives there.
- **Per-indicator source mapping (FMP-rebuild + partial-coverage tables)** — durable reference; see tech_manual §13 Known Issues for current state of the 9 forcing-function rows.
- **Cycle-timing classification (L/C/G)** — every Phase E indicator carries a `cycle_timing` column in `data/macro_indicator_library.csv` (verified 92/92 populated; 90 L / 2 C / 0 G).
- **Prior attempts (do not re-relearn)** — see tech_manual §13: FMP economic calendar (paywalled), Investing.com scraper (Cloudflare/ToS), ZEW (paid archive), Caixin (paid), ICE BofA truncation (architectural fix).

**Reference files anchor the work:**
- `manuals/Macro Market Indicators Reference.docx` — demand: 206 indicators across 6 regions with L/C/G classification.
- `manuals/G20_Free_API_Catalogue_v2.docx` — supply: aggregators + direct sources for macro statistics.
- `manuals/Market_Data_Free_API_Catalogue.docx` — supply: market-data sources (yields, FX, commodities, ETF proxies).
- `manuals/G20_PMI_Master_Table.docx` — supply: PMI / business-survey master reference for all G20 economies. 33 surveys catalogued with tier (◆ Strong / ◇ Proxy / ○ Limited), publisher, frequency, free URL, API access, and similarities/differences vs S&P Global PMI methodology. **Canonical demand-side guide for §3.1.2 Stage E (survey deep-dive).**
- `manuals/BOJ_api_manual_en.pdf` + `manuals/BOJ_api_tool.xlsx` — BoJ Time-Series API spec (used to wire `sources/boj.py`).
- `manuals/macro_market_indicators_coverage.xlsx` — current sourcing status per the 206-row demand baseline (post Stage F; refreshed 2026-05-01).
- `data/reference_indicators.csv` — the 206-row ledger (match_status / matched_to / flags).

#### 3.1.1 Coverage today vs reference baseline (post Stage B + D + F)

Refreshed 2026-05-01. Per-region snapshot:

| Region | Total | Full | Partial | Missing | % Captured |
|---|---|---|---|---|---|
| US | 37 | 28 | 2 | 7 | 78% |
| UK | 36 | 3 | 2 | 31 | 11% |
| Eurozone | 36 | 12 | 8 | 16 | 44% |
| Japan | 35 | 6 | 3 | 26 | 21% |
| China | 36 | 8 | 4 | 24 | 28% |
| Global | 26 | 9 | 3 | 14 | 40% |
| **Total** | **206** | **66** | **22** | **118** | **37%** |

**Coverage by demand-doc concept × region** (focus on regime-relevant axes):

| Concept | US | UK | EZ | JP | CN | Global | Total |
|---|---|---|---|---|---|---|---|
| Inflation (CPI / PPI / HICP / breakevens) | 2/2 | 1/1 | 1/1 | 1/3 | 2/2 | 0/0 | 7/9 |
| Growth (GDP / IP / retail / employment / capex) | 6/6 | **0/8** | 6/6 | 3/7 | 3/9 | 0/1 | 18/37 |
| Rates / Yields | 3/3 | 2/2 | 3/3 | 1/2 | 2/2 | — | 11/12 |
| Credit / Spreads | 4/5 | 0/4 | 0/4 | 0/1 | 0/4 | 1/3 | 5/21 |
| Sentiment / Survey | 2/6 | 1/9 | 7/11 | 1/9 | 1/7 | 1/2 | 13/44 |
| Labour | 6/6 | 0/6 | 2/5 | 1/3 | 1/2 | — | 10/22 |

**Two regional standouts** — both relevant to upcoming regime work:

- **UK is the largest single-region gap at 11% Full** (3/36). The UK growth column at **0/8** is particularly stark — most NEW_SOURCE:ONS rows from `reference_indicators.csv` are still unwired.
- **Phase E inflation indicators are sparse**: only 2 in `data/macro_indicator_library.csv` (US_R4, UK_R2) tagged with the `Inflation` concept. Acceptable for the current dashboard but undersized for a Growth × Inflation regime classifier.

Per-indicator detail — name / source / status / comment for every reference row — lives at `manuals/macro_market_indicators_coverage.xlsx` (3 sheets: reference_206, region_summary, concept_x_region).

#### 3.1.2 Outstanding stages

Stage definitions are in `manuals/technical_manual.md` §11 Pattern 9 (architecture) and §13 (status). Tabular summary of remaining work:

| Stage | Status | Scope of remaining work |
|---|---|---|
| A — History-preservation | ✅ Shipped 2026-04-30 | — |
| B — T1 fallback chains | ✅ Shipped 2026-04-30 | — (4 of 9 forcing-function rows resolved at T1; the other 5 either fall through to Stage D T2 modules or are accepted gaps) |
| **C — Reference-baseline close-out (regional roll-up)** | **Partial — In Progress** | Close the 118 `Missing` rows in `reference_indicators.csv` where a free path exists. **`sources/ons.py` built 2026-05-28** — 9 ONS series wired (GBR_CPI_YOY, GBR_CPIH_YOY, GBR_GDP_REAL, GBR_UNEMPLOYMENT, GBR_EMP_RATE, GBR_AWE_REGPAY_YOY, **GBR_IND_PROD (K222), GBR_SERV_PROD (S2KU), GBR_RETAIL_VOL (J5EK) shipped 2026-06-10**). UK GDP, the 3 labour series, and the 3 main monthly output indices (production / services / retail) now live. Still outstanding: UK claimant count (canonical `BCJD`/`BCJE` series frozen at 2017-01 after ONS-side methodology migration to Universal Credit unification; the current ONS dataset path isn't surfacing UK-aggregate timeseries via Zebedee — needs follow-up), UK BICS Business Insights and Conditions Survey (not exposed as standard `cdid`/dataset timeseries — needs follow-up). JP growth column lifted from 3/7 → 8/7 via the 5 PROVISIONAL e-Stat rows shipped 2026-06-10 (JPN_TERT_IND, JPN_MACH_ORDERS, JPN_RETAIL_SALES, JPN_HH_EXP, JPN_EWS_DI; statsDataIds need live verification once `ESTAT_APP_ID` is in the runtime). China growth mostly proprietary; accept. |
| D — On-demand T2 modules | ✅ Shipped 2026-04-30 | — (4 modules built: BoE / ECB / BoJ / e-Stat) |
| **E — Survey deep-dive** | **Outstanding** | Canonical demand-side guide is `manuals/G20_PMI_Master_Table.docx` — 33 G20 surveys with tier / publisher / frequency / free URL / API access / PMI-similarity assessment. Strategy: prioritise ◆ **Strong**-tier surveys with free API access not yet wired (BoK BSI via ECOS, IMEF via Banxico SIE, INEGI EMOE, TCMB EVDS, Argentina INDEC Open Data API, Indonesia BI API). ◇ Proxy-tier surveys covered by existing OECD BCI / Eurostat ESI / FRED routes where free; new T2 module only when the canonical source is meaningfully fresher. ○ Limited-tier surveys (Saudi headline-only, Russia post-2022) accepted as gaps. JP Tankan sub-DIs already accessible — just add rows to `macro_library_boj.csv`. UK CBI / GfK / RICS remain proprietary — accept. CN NBS sub-data proprietary — accept. Scraper infrastructure (`sources/scraper_base.py`) only as last resort. |
| F — Community ticker catalogues | ✅ Shipped 2026-04-30 | — (14 ETFs added; report at `manuals/community_datasets_review.md`) |
| **G — Closeout** | **Outstanding** | Refresh §1 Known Data Gaps, refresh `data/source_fallbacks.csv` per-indicator mapping, refresh `manuals/macro_market_indicators_coverage.xlsx`, archive working notes. Final commit when Stage C and E close. |

#### 3.1.3 Growth + Inflation focus for regime prep

The regime work (now owned by `../regime_AA_master_plan.docx`) uses a per-region Growth × Inflation 4-quadrant frame. The regime classifier needs per-region clean reads on each axis, and the master plan's Phase 0 data-availability test will identify which regions can be supported. Current state has well-known gaps on both axes:

**Growth axis** — well-covered for US / EZ; thin for UK / JP / CN. Note: the canonical demand-side guide for *survey-based* growth indicators (PMI, business confidence, sentiment surveys) is `manuals/G20_PMI_Master_Table.docx` — see Stage E above for the prioritisation strategy.

| Region | Action | Specific targets |
|---|---|---|
| US | ✅ no action — 6/6 captured | — |
| **UK** | **✅ `sources/ons.py` wired 2026-05-28** — partially done. GBR_GDP_REAL, GBR_UNEMPLOYMENT, GBR_EMP_RATE, GBR_AWE_REGPAY_YOY live. Still outstanding: IoP, Retail Sales Index, Index of Services, claimant count, BICS business survey (~5 more rows to close the column fully). | Add remaining rows to `data/macro_library_ons.csv`. |
| **JP** | **✅ shipped via e-Stat extension 2026-06-10** — 5 rows added to `data/macro_library_estat.csv` (JPN_TERT_IND, JPN_MACH_ORDERS, JPN_RETAIL_SALES, JPN_HH_EXP, JPN_EWS_DI). All PROVISIONAL pending live verification once `ESTAT_APP_ID` is available; cdCatNN filters likely needed on first fetch. Brings JP from 3/7 → ~6/7+ on the Growth column. | — |
| EZ | ✅ no action — 6/6 captured | — |
| CN | accept gaps | NBS retail / FAI / electricity / industrial profits / property — all flagged PROPRIETARY in `reference_indicators.csv` (no free foreign API). Current 3/9 is the practical ceiling. |
| Global | optional: CPB World Trade Monitor + IP | New T3 fetcher `sources/cpb.py` (free CSV download, monthly); 2 rows. Low priority. |

**Inflation axis** — surface coverage was thin (only `US_R4` and `UK_R2` tagged `Inflation`). **Shipped 2026-05-28 via #152**: 5 per-region inflation composites + a separate inflation-expectations composite. ✅

| Indicator | Composition (all inputs already in `macro_economic_hist`) | Headline / Core | Cycle |
|---|---|---|---|
| `US_INFL1` | mean of US headline CPI YoY (`USA_CPI`) + Core PCE YoY (`PCEPILFE`) + 5y5y forward breakeven (`T5YIFR`) | **Headline + Core** blend | L |
| `UK_INFL1` | UK headline CPI YoY (`GBR_CPI`) | Headline only | L |
| `EU_INFL1` | mean of EA headline HICP YoY + core HICP YoY (`EA_HICP` + `EA_HICP_CORE_YOY`) | Headline + Core | L |
| `JP_INFL1` | mean of JP headline CPI YoY + core CPI YoY ex food&energy (`JPN_CPI` + `JPN_CORE_CPI_YOY`) | Headline + Core | L |
| `CN_INFL1` | mean of China headline CPI YoY + PPI YoY (`CHN_CPI` + `CHN_PPI`) | Headline + PPI (core still gap) | L |
| `US_INFEXP1` | z-composite of `T5YIE` + `T10YIE` + `T5YIFR` + `MICH` | Expectations (separate axis) | L (naturally leading) |

Each row's `name` field in `macro_indicator_library.csv` explicitly states *headline / core / blend* so the regime-AA consumer can't confuse a headline-only gauge with the US headline+core blend (#155).

**§3.1.3 follow-up — source core inflation series for UK / EA / JP / CN.** Only the US blend includes core (via FRED `PCEPILFE`); the other four `*_INFL1` indicators are headline-only because we don't yet have core series in the hist for those regions. Target series to wire into `macro_library_*.csv`:

| Region | Target series | Likely source | Notes |
|---|---|---|---|
| UK | ✅ shipped 2026-06-10 — ONS CPI excluding energy, food, alcohol & tobacco (CDID `DKO8`, monthly back to 1989; the original note in this table said `D7G7` but that's headline, confirmed via ONS Zebedee + search). Wired as `GBR_CORE_CPI_YOY` and blended into `UK_INFL1` alongside `GBR_CPI`. | ONS Zebedee /data endpoint via existing `sources/ons.py` | The BoE-watched UK core measure |
| EA | ✅ shipped 2026-06-10 — Eurostat HICP, overall index excluding energy/food/alcohol/tobacco (`prc_hicp_manr/M.RCH_A.TOT_X_NRG_FOOD.EA20`, 289 obs back to 2001-12; the title is broader than the row originally noted — Eurostat's `TOT_X_NRG_FOOD` is the ECB core HICP). Wired as `EA_HICP_CORE_YOY` and blended into `EU_INFL1` alongside `EA_HICP`. | DB.nomics Eurostat via existing `sources/dbnomics.py` | Standard ECB "core" definition |
| JP | ✅ shipped 2026-06-10 — OECD COICOP2018 national CPI ex-food-and-energy YoY (`OECD/DSD_PRICES_COICOP2018@DF_PRICES_C2018_N_TXCP01_NRG/JPN.M.N.CPI.PA._TXCP01_NRG.N.GY`, 844 obs back to 1956-01). FRED `JPNCPICEUNXFFMS` does **not** exist; the FRED / OECD MEI mirror (`CPGRLE01JPM659N`) is frozen at 2021-06; this fresh OECD COICOP2018 series is the cleanest aggregator-mirrored path. Note: this is "ex food + energy" (international core convention), not the BoJ's "ex fresh food" definition — to land the latter would require e-Stat credentials (`ESTAT_APP_ID`) for STATJP/CPIm series 733. Wired as `JPN_CORE_CPI_YOY` and blended into `JP_INFL1` alongside `JPN_CPI`. | DB.nomics OECD via existing `sources/dbnomics.py` | International core convention (ex food+energy); BoJ ex-fresh-food remains a future e-Stat-credentialed upgrade |
| CN | ❌ accepted gap 2026-06-10 — no free aggregator-mirrored core CPI for China. Probed: IMF/CPI has only 15 CN monthly series (no ex-food-and-energy slice); OECD COICOP2018 N_TXCP01_NRG dataset returns 0 docs for `REF_AREA=CHN`; DB.nomics NBS provider tree has no "excluding food and energy" CPI category (only by-COICOP-group price indices). Direct NBS scrape would need a new source module — deferred. `CN_INFL1` remains headline-CPI + PPI blend; NBS Core CPI to be revisited if a free path appears. | (no free path today) | NBS publishes monthly but aggregator coverage is empty; revisit periodically |

Once those land, fold them into the per-region `*_INFL1` calculators as a second `Core CPI YoY` component (averaged with the headline) so each regional gauge becomes a headline + core blend like `US_INFL1` already is.

**Other underlying-data fills** required:

- ✅ **JP PPI / Services PPI** shipped 2026-06-10 via BoJ Time-Series Data Search direct (`sources/boj.py`, the keyless BoJ-publisher route). Series codes verified live against the BoJ `getMetadata` endpoint: `PR01'PRCG20_2200000000` → `JPN_PPI` (Producer Price Index All Commodities, 2020 base, monthly back to 1960-01, last 2026-05) and `PR02'PRCS20_5200000000` → `JPN_SPPI` (Services Producer Price Index All Items, 2020 base, monthly back to 1985-01, last 2026-04). DB.nomics' BoJ mirror was investigated and found to be stale at 2024-04/05 (~2-year lag, unrefreshed aggregator); BoJ direct is the right choice and what our existing `sources/boj.py` module is purpose-built for.
- ✅ ~~**Inflation expectations integration** — `T5YIE`, `T10YIE`, `T5YIFR`, `MICH` … Surface as `US_INFEXP1` (composite) so the regime model can use them.~~ Done 2026-05-28 (#152).

#### 3.1.4 GDP Now indices and proxies

**Concept.** GDP itself is reported quarterly with material lag (e.g. US Q1 advance estimate ~30 days after quarter-end). "Nowcasts" use higher-frequency components to give a real-time GDP estimate that updates daily/weekly. For regime work the value is significant: the regime classifier's Growth axis benefits from a "current-quarter GDP estimate" rather than waiting for the official release.

**Available free sources:**

| Source | Region | Cadence | Access | Notes |
|---|---|---|---|---|
| Atlanta Fed GDPNow | US | Daily | JSON / CSV / Excel via `https://www.atlantafed.org/cqer/research/gdpnow` | Published since 2014. Standalone reference on the Growth axis. |
| NY Fed Nowcast | US | Weekly | Published as PDF/JSON via `https://www.newyorkfed.org/research/policy/nowcast` | Lower update frequency than GDPNow but uses Bayesian dynamic-factor model — valuable as a second opinion. |
| ONS monthly UK GDP | UK | Monthly | ONS API (already a Stage C target — `sources/ons.py` to be built) | Functional UK nowcast in disguise — monthly real-GDP index, ~6 weeks lag. |
| Eurocoin (CEPR) | Eurozone | Monthly | Static download from `https://eurocoin.cepr.org/` | €-coin indicator of euro-area GDP; well-established academic series. |
| Cabinet Office Japan | Japan | Monthly | Indirect — published as monthly composite indices on the Cabinet Office site. No clean nowcast aggregator. | Components fetchable via e-Stat. Build composite ourselves. |
| (none free) | China | — | Components mostly NBS / PBoC proprietary | Accept gap. |

**Plan — outstanding work:**

1. **Wire Atlanta Fed GDPNow** as `US_GDPNOW1` — `sources/atlanta_fed.py` (~30 lines, simple JSON/CSV fetcher) + row in `macro_library_atlanta_fed.csv` + Phase E indicator. Direct first-class Phase E indicator on the Growth axis.
2. **Wire NY Fed Nowcast** as `US_NOWCAST1` (same pattern, possibly into `sources/atlanta_fed.py` as it's tiny — or a separate `sources/nyfed.py`).
3. **UK monthly GDP** — flows through naturally once Stage C wires `sources/ons.py`. Surface as `UK_NOWCAST1` Phase E indicator.
4. **Build EZ nowcast composite** — `EU_NOWCAST1` Phase E indicator. Composition: equal-weight z-scores of `EZ_IND_PROD` + `EZ_RETAIL_VOL` + `EU_ESI` (composite PMI proxy) + `EU_IND_CONF`. All inputs already wired. Pure Phase E work — no new fetchers.
5. **Build JP nowcast composite** — `JP_NOWCAST1` after Stage C e-Stat extension. Composition: equal-weight z-scores of `JPN_IND_PROD` + `JP_TANKAN1` (Tankan DI) + JP retail sales + JP machinery orders.
6. **Skip CN nowcast** — components mostly proprietary. Document as accepted gap.

**On the Eurocoin question:** if we don't want to maintain a CPB-style monthly download, the home-built EZ composite (item 4) is functionally equivalent for regime work. Decision deferred to implementation — start with the home-built composite (zero new dependencies); add Eurocoin later only if the composite proves noisy.

**Acceptance for §3.1.4:** all 4 nowcast composites (`US_GDPNOW1`, `US_NOWCAST1`, `UK_NOWCAST1`, `EU_NOWCAST1`, `JP_NOWCAST1`) appear in `macro_market.csv` with a clean weekly time series available to the regime classifier's Growth axis (consumer-side work in `../regime_AA_master_plan.docx`).

#### 3.1.5 Outstanding calculated fields

| Field | Status | Plan |
|---|---|---|
| Global yield curve composite (10Y-2Y average across US / DE / UK / JP) | Partial | US 10Y-2Y ✓ via FRED. DE 2Y wired Stage F (`EZ_GOVT_2Y`). UK has S/M/L par-yield buckets — need specific 2Y/10Y mapping (BoE yield-curve files; deferred — see §3.1.6). JP 2Y — **no free aggregator source found, defer**. Investigation 2026-06-10: BoJ Time-Series Data Search returns HTTP 400 on the speculative `IR01'IRTBLG02Y` code; metadata sweep of FM02 / FM05 / FM06 / IR01 / OT confirmed BoJ does not publish JGB benchmark yields (only call / repo / CP / CD rates and JGB issuance / trading volumes). DB.nomics probe: OECD MEI / OECD FINMARK have no Japan 2Y on this aggregator path; IMF IFS `M.JP.FIGB_PA` exists but is frozen since 2017-05 and isn't tenor-specific. **Only remaining path is MoF Japan's "JGB Interest Rate" daily CSV** — would need a new `sources/mof_japan.py` T2 module. Defer until regime-AA explicitly needs the JP leg of the global slope composite; under YCC the JP 2Y has been pinned near zero so the leg's contribution to a 4-country average is modest. |
| % stocks above 200-day MA — per-index breadth | Not implemented | Compute in-house from constituent daily closes. Candidate indices: S&P 500 (`US_EQ_B1`), Nasdaq 100, Russell 1000, FTSE 100. Adds ~500-1000 daily yfinance pulls per index. Defer until regime work has shape — may not be needed. |

(Other previously-listed calculated fields are now closed — HY/IG ratio = `US_Cr3`, EMFX basket = `FX_EM1`, EEM/IWDA = `GL_G1`, MOVE = `^MOVE`, Global PMI proxy = `GL_PMI1`.)

#### 3.1.6 Deferred specific items

Each of these has a clear path forward but isn't a Stage C/E/G blocker. Pulled out to a single list so they don't stay buried inside the stage tables.

| Item | Why deferred | When to revisit |
|---|---|---|
| **ECB MIR — Composite Cost of Borrowing for NFCs** | Closes the Euro corporate borrowing-rate gap (proxy for `EU_Cr1` corp-yield half). ECB MIR series-code pattern needs probing — multi-dimensional dataset; canonical CCBI series ID isn't in either G20 or Market_Data catalogue. | When regime model wants explicit Euro corp credit spread vs the `IEAC.L` ETF total-return proxy that's currently doing the job. |
| **BoE per-tenor gilt yields (2Y / 5Y / 10Y / 30Y)** | Today we have S/M/L par-yield buckets (`GBR_GILT_S/M/L`) and zero-coupon M/L from BoE IADB. Specific tenor breakdowns require fetching the BoE yield-curve spreadsheet files (separate fetcher; spreadsheet parsing). | If the master plan's regime work specifically needs UK 10Y-2Y slope rather than the S/M/L proxy. |
| **`sources/bundesbank.py`** | Germany Bundesbank publishes corporate bond yield indices by rating — closes the Euro IG corp yield gap properly. New T2 module (~80-100 lines, SDMX 2.1). | When ECB MIR proves insufficient and / or regime work needs true bond yields rather than borrowing rates. |
| **iShares STOXX Europe 600 sector ETF naming verification** | 19 sector ETFs (`EXV1`-`EXV9`, `EXH1`-`EXH9`, `EXSI`) all probed live in Stage F but cross-reference revealed the 7 already in `index_library.csv` have inconsistent ticker→sector labels (e.g. `EXH1.DE` labelled "Energy" in our library but listed as "Automobiles" by iShares). Without authoritative mapping I risk mislabelling new rows. | One-off Chrome lookup against ishares.com/de to confirm the 11-sector breakdown, then bulk-add. |
| **Refactor `fetch_ecb_euro_ig_spread()` in `compute_macro_market.py`** | Legacy inline ECB call (precedes `sources/ecb.py`). Functional but architecturally inconsistent — should route through the new module so all ECB calls share one code path. | Low-priority hygiene — schedule for Stage G closeout. |
| **22 retired yfinance tickers** | The original §3.1 plan envisioned a community-catalogue cross-check for these. Most were retired because the underlying instrument disappeared (`^TX60` etc.); community catalogues unlikely to surface live replacements for instruments that no longer trade. | Defer permanently unless the master plan's regime work specifically flags a need for a retired instrument's exposure. |
| **Kaggle "Yahoo Finance Tickers" catalogue (100k+ tickers)** | Mostly individual equities; out of scope for our index/ETF/aggregate focus. Account/API-key required. | If the master plan's regime work flags a need for individual-stock data — unlikely given the macro focus. |

#### 3.1.7 Acceptance

Outstanding-work-only acceptance criteria for §3.1 closure:

- ✅ Stage A — history-preservation safeguard live with audit hook (`section_d_history_preservation` in `data_audit.py`).
- ✅ Stage B — 4 of 9 forcing-function rows resolved at T1; the other 5 either route through Stage D T2 modules or are accepted gaps.
- ✅ Stage D — 4 T2 modules built (BoE / ECB / BoJ / e-Stat) and exercising in CI without regression.
- ✅ Stage F — community-ticker review shipped (`manuals/community_datasets_review.md`); 14 ETF additions in `index_library.csv`.
- ⏳ **Stage C** — `sources/ons.py` built 2026-05-28; UK GDP + 3 labour series live + 3 main monthly output indices (IoP K222, IoS S2KU, RSI J5EK) shipped 2026-06-10. JP growth column (3/7 → 8/7) via `sources/estat.py` extension shipped 2026-06-10 (5 PROVISIONAL statsDataIds pending live verification once `ESTAT_APP_ID` reaches the runtime). Still outstanding: UK claimant count + BICS (both have ONS-side complications — see Stage C table row for detail). Region scorecard in `manuals/macro_market_indicators_coverage.xlsx` not yet updated.
- ✅ **Growth + Inflation focus (§3.1.3)** — 5 new per-region inflation regime composites (`US_INFL1` / `UK_INFL1` / `EU_INFL1` / `JP_INFL1` / `CN_INFL1`) + `US_INFEXP1` shipped 2026-05-28 (#152). **Follow-up**: source core CPI series for UK/EA/JP/CN to upgrade those gauges to headline+core blends like `US_INFL1`; JP PPI / Services PPI also outstanding via e-Stat.
- ⏳ **GDP Now (§3.1.4)** — `US_GDPNOW1` + `US_NOWCAST1` via Atlanta Fed / NY Fed; `UK_NOWCAST1` via ONS monthly GDP; `EU_NOWCAST1` + `JP_NOWCAST1` as Phase E composites.
- ⏳ **Stage E** — survey deep-dive: per-country target list distilled from the demand doc; rows added via existing modules where free; documented gaps where proprietary.
- ⏳ **Stage G** — closeout: refresh `data/source_fallbacks.csv`, refresh `manuals/macro_market_indicators_coverage.xlsx`, archive working notes; this section enters `Status: Done` posture.


### 3.2 Retire the Simple Pipeline

**Priority:** Medium — code-cleanliness and maintenance-burden reduction. The simple pipeline is currently frozen but still adds ~66 hardcoded instruments + a `sentiment_data` tab that the rest of the codebase no longer touches.
**Status:** Not started. Blocked on confirming downstream consumer usage.

**Context:** the simple pipeline is the original 66-instrument daily snapshot in `fetch_data.py`. It writes the protected `market_data` tab (GID `68683176`) and the `sentiment_data` tab. Its only known consumer is `trigger.py`, which runs at 06:15 London on a local Windows machine and reads `market_data` only. The comp pipeline (~390 instruments) covers a strict superset of the simple pipeline's instrument set, so the simple pipeline duplicates fetch traffic and code paths that have no other reason to exist.

**Plan:**

1. **Confirm `trigger.py` is still in active use.** Owner check: is the 06:15 Windows job still running? If retired, skip to Step 4.
2. **If still in use:** decide between (a) migrating `trigger.py` to read `market_data_comp` (filter to the 66 instruments it cares about), or (b) keeping `market_data` populated by a thin facade — `fetch_data.py` writes a subset view of `market_data_comp` after the comp run, dropping the dedicated simple-pipeline fetcher.
3. **Decide on `sentiment_data`.** Audit downstream readers: nothing in this repo references it. Confirm with the owner that it's safe to drop — if so, mark it for deletion (move to `SHEETS_LEGACY_TABS_TO_DELETE`).
4. **Delete the simple-pipeline code path.** Remove the 66-instrument hardcoded list (Fear & Greed, VIX term structure, FX majors, sector ETFs, FRED yields). Remove the simple-snapshot writer. `fetch_data.py` becomes a comp-pipeline-only module.
5. **Update `library_utils.py`.** Drop `market_data` from `SHEETS_PROTECTED_TABS` if the tab is being retired (or keep protected if Step 2(b) facade is adopted). Remove `sentiment_data` from `SHEETS_PROTECTED_TABS` and add to `SHEETS_LEGACY_TABS_TO_DELETE`.
6. **Update `manuals/technical_manual.md`** — drop the "Simple Pipeline" sub-section in §1 / §4 and the related tab descriptions.

**Acceptance:**

- `fetch_data.py` no longer carries a separate simple-pipeline code path.
- `market_data` either deleted or thin-facade-driven from `market_data_comp` (per Step 2 outcome).
- `sentiment_data` retired (in `SHEETS_LEGACY_TABS_TO_DELETE`).
- Daily run wall-clock time decreases by the simple-pipeline budget (~30-60 seconds of yfinance / FRED calls eliminated).
- `trigger.py` continues to function (if still in use) or is acknowledged as retired.

### 3.3 PE Ratio Integration

**Priority:** Medium-high — valuation data is a core input for a macro-market dashboard.
**Status:** Capability shipped 2026-06-10. Alpha Vantage scaffold + smoke test landed (`sources/alpha_vantage.py` with `fetch_overview()` + `get_pe_ratios()`, `data/macro_library_alpha_vantage.csv` empty schema, `test_alpha_vantage_smoke.py` exercising `OVERVIEW` for `SPY`; smoke step in `update_data.yml` extended to expose `ALPHAVANTAGE_API_KEY` and run the new test). Free-tier quota is 25 requests/day so a per-ticker daily pull is feasible for the ~5-row major-index ETF set (SPY/QQQ/IWM/EFA/EEM) once we settle on the storage shape — likely a new `data/equity_pe_snapshot.csv` rather than mixing snapshot-only PE/forward-PE values into the time-series `macro_economic_hist`. Population + writer remain outstanding pending that schema decision. Historical PE / CAPE (multpl.com / shillerdata) is a separate track — see §3.13.

**Objective:** Integrate price-to-earnings (PE) ratio data for major indices (S&P 500, Nasdaq 100, FTSE 100, Euro Stoxx 50, Nikkei 225, MSCI EM, etc.) and/or individual equity markets. PE ratios provide valuation context for equity regime signals and can feed forward-PE-based composite indicators in Phase E.

**Data categories to source:**
- **Trailing PE (TTM)** — based on reported earnings over the trailing 12 months
- **Forward PE** — based on consensus analyst estimates (more forward-looking; leading indicator)
- **CAPE / Shiller PE** — cyclically adjusted PE (10-year real earnings); useful as long-run valuation anchor
- **Sector PE breakdowns** — per-sector PE for S&P 500 / other major indices

**Candidate free sources (prioritised):**

| Source | Coverage | Access | Notes |
|---|---|---|---|
| **yfinance** | Trailing PE for individual tickers and ETFs (via `info["trailingPE"]`, `info["forwardPE"]`) | Free, already in pipeline | Snapshot only — no historical time series. Good for daily current PE but not PE history. |
| **FMP `/stable/ratios`** | TTM and forward PE for individual stocks and ETFs | API key (already have) | Historic annual/quarterly ratios available. Check if index-level PE aggregates are exposed. |
| **FRED** | Shiller CAPE (`CAPE10`? — verify) | Free | May not exist as a direct FRED series. Robert Shiller's dataset is available as a free Excel download from his Yale page. |
| **multpl.com** | S&P 500 PE, Shiller PE, earnings yield | Free website, no API | Would require scraping — fragile. |
| **Barclays / Bloomberg** | Forward PE, sector breakdowns | Proprietary | Not freely available |

**Potential Phase E indicators:**
- `US_V3` or similar — S&P 500 forward PE z-score (valuation regime)
- `GL_V1` — cross-region PE spread (US vs EM, US vs Europe)
- CAPE-based long-run valuation signal

**Action:** Investigate which free sources provide historical PE time series (not just snapshots). yfinance is already integrated but lacks history. FMP ratios endpoint should be tested alongside the calendar endpoint probe. Shiller CAPE dataset is a reliable free download. Design the integration path (new fetch module vs extension of existing comp pipeline) based on what source data is available.

### 3.4 Market Index Expansion

**Priority:** Medium — broadens market coverage.

Categories to consider:

- Europe sector ETFs (`.DE`, EUR-denominated)
- EM regional ETFs
- UK style ETFs
- Asia/Japan additional coverage

Add rows to `index_library.csv` — no new Python modules needed. For each new instrument:
1. Verify ticker returns data via `python -c "import yfinance as yf; print(yf.Ticker('TICKER').history(period='5d'))"`
2. Set correct `base_currency` (required for FX conversion)
3. Set `validation_status = "CONFIRMED"`
4. For `.L` tickers: pence correction is automatic (no code change needed)
5. For new currencies: add to `COMP_FX_TICKERS` and `COMP_FCY_PER_USD` in `library_utils.py`

### 3.5 Regime-Based Indicator Labelling & ML-Driven Regime Identification — MOVED

> **Moved 2026-05-06 to `../regime_AA_master_plan.docx` Section 8B (Indicator Validation Framework) and Section 17 Phase 1 / Phase 2 of the Master Forward Plan.**
>
> This section previously held the work plan for: (a) historical regime label production, (b) per-indicator regime-identification reliability scoring across the Phase E indicator library, (c) the ML-driven regime classifier producing the live regime status output. All of that work now lives in the regime AA master plan, which treats the data pipeline (raw layer + Phase E composites) as one of several candidate inputs to a per-region regime engine — alongside the structured indicator library in Section 5 of the master plan.
>
> What this means for the data pipeline:
>
> - The data pipeline's job is to keep producing the inputs (raw macro series, market data, the 92 composite indicators with their z-scores, regime classifications, forward-regime signals, and L/C/G tags) on its current daily cadence. Quality, freshness, and registry hygiene remain in scope here.
> - The regime engine that *consumes* those inputs and produces a per-region regime call is owned by the master plan. So is the validation methodology that decides which candidate indicators (the 92 Phase E composites among them) earn a place in the production engine.
> - The `macro_market.csv` snapshot already carries each indicator's own per-indicator regime classification (the literature-derived discrete label). That stays. The new "regime-identification reliability score" and the ensemble production regime call are downstream artefacts owned by the master plan.
> - If the master plan's validation work surfaces a need for a new raw input or a new composite that the pipeline should produce, the request comes back here as a §3 entry — but the analytical decision on what to add lives in the master plan.
>
> See `../_master_plan_drafts/responsibilities_boundary.md` for the durable scope record.

**Priority (data-pipeline residual):** None. All regime work here moved to the master plan.
**Status:** Closed in this document.

### 3.6 Incremental Fetch Mode (fetch_hist.py)

**Priority:** Medium — performance improvement.

Currently `fetch_hist.py` rebuilds the entire dataset from scratch on every run (~8-12 min for `run_comp_hist()`). An incremental append mode would:

1. Check the last date in the existing CSV
2. Only fetch new weekly rows since the last update
3. Append to existing data rather than full rebuild

This would reduce daily historical data runtime from ~10 minutes to seconds.

### 3.6a Missing-split handling + sister-CSV self-heal (open design question)

**Priority:** Medium — data-quality robustness. Partially shipped 2026-05-27.

**Context.** yfinance back-adjusts splits via `auto_adjust=True`, but only for splits in Yahoo's corporate-actions feed, which is patchy for some non-US listings. `1306.T` (NEXT FUNDS TOPIX ETF) did a 10-for-1 split (record date 2026-03-31, effective 2026-04-01, ex-rights 2026-03-30 under Japan's T+2 settlement) that Yahoo never recorded, so the raw price dropped 3827→386.6 and every return window straddling it showed ≈ −89%.

**Shipped (2026-05-27):**
- `data/manual_splits.csv` — source-of-truth override (ticker, ex_date, ratio), per §0.
- `library_utils.apply_manual_splits()` — called by `fetch_data.py` and `fetch_hist.py` on the raw yfinance series, so live snapshot + history self-correct on the next rebuild.
- `scripts/backadjust_hist_splits.py` — idempotent one-time corrector for committed `*_hist.csv` + sister `*_hist_x.csv` (ran for `1306.T`).
- `data_audit.py::_check_unadjusted_splits()` — flags any *new* unexplained ~10x weekly jump in `market_data_comp_hist.csv` (suppresses rows registered in `manual_splits.csv`).

**Open design question — sister CSV cannot self-heal.** `library_utils._append_archive_rows()` dedups by date with `keep="first"`, so once a date's value is stored in a `*_hist_x.csv` sister it is **never** overwritten by a later corrected value. Consequences:
- A bad value (stale price, unadjusted split, source revision) frozen in the sister stays wrong forever.
- Today this is masked because `load_hist_with_archive()` does `live.combine_first(sister)` — live wins wherever live is non-null, and live (full rebuild) covers all in-range dates. The sister's stale value only surfaces if live ever *drops* that date (the sister's whole reason to exist — rolling-window truncation like ICE BofA).
- So a corrected series + a stale sister = a latent landmine: correct today, silently wrong the day live's window rolls past it.

We worked around it for `1306.T` by correcting the sister in place via the back-adjust script. The standing question is whether to change the merge/dedup so the sister can self-heal — options:
1. **Prefer-fresher dedup** — when live and sister disagree on an overlapping date and live is non-null, update the sister to live's value. Risk: defeats the preservation guarantee for genuine rolling-window drops where live's later value is the *truncated* (wrong) one.
2. **Versioned/keyed preservation** — sister stores (date, value, captured_at); a corrected capture supersedes an older one. More plumbing.
3. **Periodic sister rebuild** — drop + repopulate sister from the longest-available live each run; loses nothing while live covers the range, but forfeits preservation for dates already truncated from live.
4. **Status quo + manual corrector** — keep `keep="first"`, rely on `scripts/backadjust_hist_splits.py` for one-off corrections. Simplest; needs operator discipline.

Decision deferred — it interacts with the Stage A preservation contract and needs care. Not a blocker; `1306.T` is corrected and the audit guard catches future cases.

### 3.7 Regime-Driven Back-Test & Portfolio Optimisation — MOVED

> **Moved 2026-05-06 to `../regime_AA_master_plan.docx` Section 6 (Portfolio Construction), Section 16 (Three Regime-Based Frameworks: Parallel Client Implementations), and Section 17 Phase 4 / Phase 5 / Phase 6 of the Master Forward Plan.**
>
> This section previously held the work plan for: (a) the asset-class universe and tilt-rules scaffolding for the regime-tilted portfolio, (b) the back-test engine producing a historical performance record vs benchmark, (c) regime-conditional portfolio optimisation. All of that work now lives in the regime AA master plan, which (i) treats the portfolio construction as three parallel client implementations (Framework A for multi-asset benchmark mandates, Framework B for total-return mandates using the rg-ERC dynamic benchmark of Bouyé and Teiletche, Framework C for absolute-return mandates), and (ii) treats the asset universe as a downstream design decision driven by the per-region data availability test in master plan Phase 0.
>
> What this means for the data pipeline:
>
> - The data pipeline's job is to keep producing the asset return data on its current cadence — `market_data_comp_hist.csv` + FRED bond-index series + the long-run market-price layer (OECD MEI feed, Shiller, Ken French, IMF Primary Commodity Prices, JST, BoE Millennium) once that layer is wired in. Schema, freshness, and registry hygiene remain in scope here.
> - The portfolio engine that *consumes* the asset return data and produces the three-framework client portfolios is owned by the master plan.
> - If the master plan's portfolio work surfaces a need for a new asset return series or a new corporate-action-adjusted reference series, the request comes back here as a §3 entry — but the analytical decision on what to add lives in the master plan.
>
> See `../_master_plan_drafts/responsibilities_boundary.md` for the durable scope record.

**Priority (data-pipeline residual):** None. All portfolio / back-test work here moved to the master plan.
**Status:** Closed in this document.

### 3.8 Weekly Retirement Review Workflow

**Priority:** High — closes the auto-remediation gap left by the daily audit. Today, every issue surfaced by `data_audit.py` is re-surfaced every day forever (with the single exception of yfinance dead tickers, which `audit_writeback.py` auto-flips after 14 days without operator review). This subsection replaces that auto-flip with a weekly human-in-the-loop review that covers every audit category — including composite-indicator dependents that the current daily flow doesn't surface at all.

**Status:** Not started. Daily `audit_writeback.py` continues running until step 4 of the plan ships.

**Objective:** Each Friday, generate a retirement-candidate report listing series / tickers / composites whose health flags have persisted long enough to warrant action. Report lands as a committed `.md` file (so Claude can read it) AND as a comment on a perpetual GitHub Issue (so the owner gets an email notification). We review together over the weekend, record decisions in a committed CSV, and apply them via a supervised `retire.py` tool at a convenient time.

#### 3.8.1 Components

1. **Candidate detector — `weekly_retirement_audit.py`**
   - Categories covered:
     - **yfinance dead-streak** — replaces `audit_writeback.py`'s daily auto-flip.
     - **Macro source series — EXPIRED** for ≥ N consecutive runs (per-frequency threshold; see 3.8.3).
     - **Macro source series — STALE** for ≥ N consecutive runs (more conservative threshold).
     - **Persistent fetch errors** — FRED / OECD / DBnomics HTTP failures lasting ≥ N consecutive runs.
     - **Missing `_get_col` columns** — references in `compute_macro_market.py` with no source column.
     - **Composite-indicator dependents** — for each retirement candidate above, walk every `_calc_*` in `compute_macro_market.py` and surface every macro market indicator that consumes the candidate via `_get_col`. Report includes cycle-timing (L/C/G) and flags any z-score-based composites (which forward-fill can quietly poison for 26+ weeks before the output visibly drifts).
     - **Composite standalone health** — macro market indicator outputs whose own input chain is fully fresh but whose value (or z-score) has been flat for N weeks. Suggests a calculator-side bug or degenerate input combo. Surfaced separately from "input retired" candidates.
   - **Streak persistence:** generalises `data/yfinance_failure_streaks.csv` into a single `data/audit_streaks.csv` keyed by `(category, identifier)` so the same streak-counting logic powers every category.
   - **Threshold model:** reuses `data/freshness_thresholds.csv`. Retirement-candidate threshold = **2 × per-frequency tolerance** uniform across all frequencies (operator-overridable per row via the existing `freshness_override_days` column). Aligns with the existing `EXPIRED` boundary in `data_audit.py:classify_age` so a series only enters the weekly retirement queue once it is unambiguously past `STALE` and into `EXPIRED` territory.
   - **Alternative-source suggestions:** emitted only if the candidate alternative has been pre-verified — i.e. there's a corresponding row in `data/source_fallbacks.csv` whose tier-N source is known to carry the column. **No guessing.**

2. **Report delivery**
   - **Committed file:** `weekly_retirement_report.md` at repo root (overwritten weekly; git history retains old reports — Claude reads the latest).
   - **GitHub Issue:** perpetual `Weekly Retirement Proposals` issue, labelled `weekly-retirement`, comment posted on every run.
   - **Email-notification fix:** comment body opens with `@kasim81` mention to force a notification regardless of watch settings (default `GITHUB_TOKEN` posts as `github-actions[bot]`, which GitHub silently filters). Belt-and-braces: issue is also assigned to `@kasim81` on creation. The same `@kasim81` mention is added to the daily audit comment (`audit_comment.md`) so the daily notifications start firing as well.
   - **Layout per candidate:** identifier, source, last successful obs, days-on-list, dependent macro market indicators (with cycle-timing tags), pre-verified alternative source if any, one-line rationale.

3. **Decision sink — `data/retirement_decisions.csv`**
   - Schema: `decision_date, category, identifier, decision, rationale, alternative_used, applied_date`
   - `decision ∈ {retire, keep, defer, replace_with_alternative}`
   - Committed to repo so we have a permanent historic record of every decision and when it was applied.
   - Edited collaboratively after each weekly review (PR or direct push).

4. **Application tool — `retire.py`**
   - Reads pending rows from `data/retirement_decisions.csv` (decision recorded, `applied_date` blank).
   - **Per-category retirement = archive, not delete:**
     - **yfinance ticker** → archive `index_library.csv` row to `data/retired_index_library.csv` (final behaviour — flip-status vs full-archive — to be agreed at implementation, per Q7).
     - **Macro source series** → archive row from its `data/macro_library_*.csv` to `data/retired_macro_library.csv`. Subsequent fetches skip it.
     - **Macro market indicator** → archive row from `data/macro_indicator_library.csv` to `data/retired_macro_indicator_library.csv`. Calculator dispatch entry is also commented out / removed.
     - **`_get_col` reference** → out of scope for `retire.py`; reported as a code change requiring a manual edit of `compute_macro_market.py`.
   - Writes back the `applied_date` column on every processed row.
   - **Supervised only:** invoked as `python retire.py [--dry-run]`. Never automated. Operator commits the resulting changes.

5. **Schedule**
   - `.github/workflows/weekly_retirement_review.yml`, cron `23 1 * * 5` (Friday 01:23 UTC) so the report lands with the operator on Friday morning UK and gives the weekend for review before Monday.

6. **Replace `audit_writeback.py`**
   - Once the weekly workflow is shipping reports reliably, remove `audit_writeback.py` from `update_data.yml` and archive the file. Its dead-streak logic is absorbed into `weekly_retirement_audit.py` via the generalised `audit_streaks.csv`.

#### 3.8.2 Plan / stages

1. **Stage 1 — Detector + report renderer.** Build `weekly_retirement_audit.py` covering all 7 categories; ship behind `workflow_dispatch` first so we can iterate on the markdown layout without committing to a cron.
2. **Stage 2 — Schedule + delivery.** Wire `weekly_retirement_review.yml` (Friday cron + perpetual issue post + `@kasim81` mention + assignee). Add `@kasim81` mention to the existing daily `audit_comment.md` as a side-fix.
3. **Stage 3 — Decision sink.** Create `data/retirement_decisions.csv` with the schema above; first weekly run produces a report whose identifiers we manually add as `decision=defer` rows to seed the file.
4. **Stage 4 — Application tool.** Build `retire.py`. Agree per-category retirement semantics first (see "Open implementation-time decisions" below), then implement; gate behind `--dry-run` until satisfied with the first end-to-end run.
5. **Stage 5 — Decommission `audit_writeback.py`.** Remove from `update_data.yml`, archive the file, migrate any active streaks from `yfinance_failure_streaks.csv` into `audit_streaks.csv`.
6. **Stage 6 — Doc closeout.** Add §15 "Weekly retirement review" to `manuals/technical_manual.md` (durable architecture reference); update §1 Known Data Gaps to point at retired-source archive locations.

#### 3.8.3 Open implementation-time decisions

- **yfinance retirement semantics:** archive-and-remove vs. flip-`validation_status`-to-UNAVAILABLE vs. both. Today's `audit_writeback.py` does flip-only.
- **Composite standalone-health threshold:** what counts as "flat"? Variance < ε over N weeks? z-score abs(value) constant across N weekly samples? Pick at Stage 1 and tune.
- **Alternative-source verification process:** who runs the pre-test, and where do verified alternatives live (extend `data/source_fallbacks.csv` or a dedicated `data/verified_alternatives.csv`)?
- **Composite retirement vs. patching:** if a macro market indicator's only retired input has a verified alternative, default behaviour = swap input automatically, or always require operator decision?

#### 3.8.4 Acceptance

- `weekly_retirement_report.md` lands in repo every Friday morning UK with all 7 categories covered.
- Perpetual `Weekly Retirement Proposals` GitHub Issue receives a comment per run; owner receives an email notification (verified by Issue 1's first comment).
- `retire.py --dry-run` correctly enumerates pending decisions and the changes it would apply for every category.
- `audit_writeback.py` removed from daily workflow; `data/audit_streaks.csv` carries every active streak.
- `data/retirement_decisions.csv` carries a full historic record of every decision and application date.
- Daily audit comment (`audit_comment.md`) carries `@kasim81` mention so the operator receives email notifications for daily audits.

### 3.9 Long-run commodity prices — LBMA gold (regime-AA-driven)

**Priority:** Medium-High — closes the daily long-run gold gap for the regime AA `commodity_return` pillar. Surfaced by regime AA Phase 0c Step 3 verification (2026-05-08): FRED's LBMA gold AM and PM fix series (`GOLDAMGBD228NLBM`, `GOLDPMGBD228NLBM`) confirmed discontinued in 2017 when the LBMA changed methodology; no FRED replacement exists.

**Status:** ✅ **Done 2026-05-28** for gold; multi-commodity extension outstanding (see §3.9.1 below). Replumbed onto LBMA's own JSON feed at `prices.lbma.org.uk` after the initial Nasdaq Data Link wiring (2026-05-08) hit a 403 on `LBMA/GOLD` (dataset moved to NDL's paid tier). Module `sources/lbma.py` + library `data/macro_library_lbma.csv` carries `GOLD_USD_PM` (3,035 weekly points 1968-04-05 → present); Phase E `GLOBAL_GOLD1` indicator live with `safe-haven-bid` regime. The NDL scaffolding (`sources/nasdaq_data_link.py`, empty `data/macro_library_nasdaqdl.csv`, `requirements.txt` line, `NASDAQ_DATA_LINK_API_KEY` workflow secret) is retained for any future free NDL dataset.

> **Important note on indicator-spine cap.** `GOLD_USD_PM` reaches 1968-04-05 in the **raw layer** (`macro_economic_hist.csv`), but `GLOBAL_GOLD1` in `macro_market.csv` / `macro_market_hist.csv` and the explorer **starts only 2000-01-07**, because `compute_macro_market.py::HIST_START = "2000-01-01"` truncates every Phase E indicator. For the regime AA `commodity_return` pillar (the whole reason §3.9 fetched 1968+), consume the **raw `GOLD_USD_PM` column** directly from the hist rather than the capped indicator. Lowering `HIST_START` would extend all 99 indicators back further but has a large blast radius (Sheets cell budget, 156w z-score window assumptions, every indicator's input availability) — do not change casually.

**Driver:** `../regime-aa` Phase 0c — the per-region availability matrix (test plan §4) needs a daily long-run gold series. LBMA publishes the canonical fix daily back to 1968 via the same auction process FRED used to mirror.

**Scope:**

- New T0 source module `sources/lbma.py` reading `https://prices.lbma.org.uk/json/<series>.json` (no API key, public JSON).
- New library `data/macro_library_lbma.csv` per §0.1 architecture rule (every LBMA series stem + currency lives in CSV, never in Python).
- Sister-file safeguard applied per Stage A (`*_hist_x.csv`).
- First series: `gold_pm` — daily PM auction fix USD/GBP/EUR, 1968+. Maps to `GOLD_USD_PM` (raw) and `GLOBAL_GOLD1` (Phase E composite).
- Register in `data/source_fallbacks.csv` as T0 for `GOLD_USD_PM`; T1 = Nasdaq Data Link `LBMA/GOLD` (now paid, kept as documented fallback rather than runtime path).
- The Nasdaq Data Link scaffolding from the 2026-05-08 attempt remains in place but with an empty library — it stays available for any future free NDL dataset.

**Future expansion** — see **§3.9.1 below** for the full multi-commodity long-run plan (silver / copper / aluminium / oil / nat gas / agricultural softs / livestock).

**Acceptance:**

- `sources/lbma.py` fetches `gold_pm` end-to-end via the daily run; `GOLD_USD_PM` populated in `macro_economic_hist.csv` back to 1968-04-01.
- `GLOBAL_GOLD1` Phase E composite resolves with raw / zscore / regime in `macro_market.csv` and `macro_market_hist.csv`.
- Sister-file `*_hist_x.csv` keeps pace with live (Option B writer; `library_utils.write_hist_with_archive()`).
- Cross-repo confirmation: the regime AA repo's Phase 0c availability matrix records the gold row sourced from `market_dash_auto` rather than FRED.

**Related cross-repo work** (in `regime-aa`, not this repo): the Phase 0c verifier `src/data_ingestion/verify_fred_us_native.py` documents the FRED gold gap. Original commit `1256ab2` (on the `feature/verify-fred-us-native` branch) pointed at NDL `LBMA/GOLD` as the long-run path; that pointer should be updated to LBMA direct now that NDL is paid.

#### 3.9.1 Multi-commodity long-run extension (regime-AA-driven follow-up)

**Priority:** Medium-High — extends §3.9 from gold-only to the broader `commodity_return` set the regime AA work needs.

**Status:** FRED rows landed 2026-06-10. 14 IMF Primary Commodity Prices series added to `data/macro_library_fred.csv` (sort_keys 530-543) covering Industrial Metals (`COPPER_USD`, `ALUM_USD`), Energy (`WTI_USD`, `BRENT_USD`, `NATGAS_HH_USD`), Agriculture (`WHEAT_USD`, `CORN_USD`, `SOYBEAN_USD`, `COFFEE_ARABICA_USD`, `SUGAR_USD`, `COTTON_USD`), Livestock (`BEEF_USD`, `PORK_USD`), and the canonical aggregate (`IMF_PCPS_ALL` via `PALLFNFINDEXM`). Concept `Cross-Asset`, country `GLOBAL`, cycle L — matching the existing `GOLD_USD_PM` precedent. Next daily run pulls them into `macro_economic_hist.csv`. Phase E `GLOBAL_*1` composites (per individual commodity) remain optional — regime-AA can consume the raw `*_USD` columns directly per the §3.9 indicator-spine note.

**Targets** (all should reach ≥ 1990, most ≥ 1980 or earlier):

| Commodity | Likely source | Cadence | Notes |
|---|---|---|---|
| **Silver** | LBMA `silver.json` (extend `sources/lbma.py`) | Daily | Same module + a row in `macro_library_lbma.csv`. Back to ~1968 |
| **Platinum** | LBMA `platinum_pm.json` / `platinum_am.json` | Daily | Same module + rows |
| **Palladium** | LBMA `palladium_pm.json` / `palladium_am.json` | Daily | Same module + rows |
| **Copper** | FRED `PCOPPUSDM` (IMF Primary Commodity Prices mirror) | Monthly | Just rows in `macro_library_fred.csv` |
| **Aluminium** | FRED `PALUMUSDM` | Monthly | Same |
| **Iron ore** | FRED `PIORECRUSDM` (already wired as a comp-pipeline FRED rate) — promote to indicator-library Phase E | Monthly | No new fetch needed |
| **Brent / WTI crude oil** | FRED `WTISPLC` (WTI spot, 1986+); for Brent monthly, FRED `POILBREUSDM` | Daily / Monthly | Mix of daily WTI + monthly Brent works for regime use |
| **Natural gas** | FRED `PNGASUSUSDM` (Henry Hub) | Monthly | |
| **Wheat** | FRED `PWHEAMTUSDM` | Monthly | |
| **Corn** | FRED `PMAIZMTUSDM` | Monthly | |
| **Soybeans** | FRED `PSOYBUSDM` | Monthly | |
| **Coffee (Arabica)** | FRED `PCOFFOTMUSDM` | Monthly | |
| **Sugar** | FRED `PSUGAISAUSDM` | Monthly | |
| **Cotton** | FRED `PCOTTINDUSDM` | Monthly | |
| **Beef / Cattle** | FRED `PBEEFUSDM` (IMF mirror) | Monthly | |
| **Lean hogs / Swine** | FRED `PPORKUSDM` (IMF mirror) | Monthly | |

**Why FRED for most of them:** the IMF Primary Commodity Prices System publishes the canonical long-run monthly series (~1980+ in most cases, some longer); FRED mirrors them under stable `P*USDM` codes. We already have FRED wired and the per-row pattern works — net work is **CSV rows in `data/macro_library_fred.csv`**, no new module.

**Why LBMA for the precious metals:** `sources/lbma.py` already exists; extending it to silver / platinum / palladium is a few CSV rows (existing `gold_pm` + new `silver`, `platinum_pm`, `palladium_pm`, `gold_am` etc.) — the parser handles the same JSON shape across all of them. Daily granularity preserved.

**Scope of work:**

1. Extend `data/macro_library_lbma.csv`: add `silver`, `platinum_pm`, `palladium_pm` (+ optionally the AM variants for symmetry). 3–6 rows.
2. Extend `data/macro_library_fred.csv`: add the 13 FRED Primary Commodity Prices rows above. Each row needs canonical `col` names (e.g. `COPPER_USD`, `BRENT_USD`, `WHEAT_USD`).
3. Add Phase E composites if the regime work wants them (`GLOBAL_OIL1`, `GLOBAL_COPPER1`, etc.) — optional; the regime AA consumer can also read the raw `*_USD` columns directly (as recommended for gold).
4. Update `data/source_fallbacks.csv` with T0 entries for each commodity.
5. Verify the comp-pipeline `GC=F` / `SI=F` / etc. yfinance futures don't conflict semantically — they're separate (futures vs spot/index) and serve a different role (daily, 2000+ only); these new long-run series sit alongside.

**Cross-reference:** `../longrun_assetclass_data_sources.md` lists IMF Primary Commodity Prices among the long-run sources Phase 0 of the master plan needs.

---

### 3.10 ifo World Economic Survey — Euro Area historical backfill

**Priority:** Medium — adds a long-run quarterly Euro-area sentiment series the regime AA work can use as a long-history Growth-axis input.

**Status:** Not started.

**Background.** During the 2026-05-27 ifo diagnostic (`scripts/ifo_probe.py` Test 1, the known-good control) we confirmed ifo serves a standalone workbook **"ifo Economic Climate for the Euro Area (1990–2019)"** at:

```
https://www.ifo.de/sites/default/files/2019-10/wes-euro-e-2019q4.xlsx
```

This is the **WES-Euro** workbook — the Euro-area subset of ifo's World Economic Survey (a quarterly survey of ~1,000 economists across ~120 countries, producing the World Economic Climate index). Different dataset from the monthly Geschäftsklima we already capture as `DE_IFO*` — WES is quarterly, cross-country (here: Euro-area aggregate), and the time-series spans 1990Q1 → 2019Q4 in this workbook.

**Important caveat:** the file name and the upload path (`2019-10/`) indicate the workbook ended at **2019Q4** — ifo presumably folded the standalone WES-Euro publication into the main WES product after that point. So this is a **historical backfill** (1990Q1–2019Q4), not a live source. To extend beyond 2019 the operator needs to identify and wire ifo's current WES publication path (open question).

**Scope:**

1. **Backfill, one-time:** add a new fetcher target — a new mini-source or an extension of `sources/ifo.py` — that downloads the 2019Q4 workbook, parses the quarterly Euro-area Economic Climate index series (and the Situation / Expectations sub-components if cleanly available), and emits them as columns in `macro_economic_hist.csv`. Names: `EA_WES_CLIMATE`, optionally `EA_WES_SIT` / `EA_WES_EXP`. The historical workbook is static so this is a one-shot fetch — once the values are committed, no need to re-fetch unless the file ever updates.
2. **Library row** in `data/macro_library_ifo.csv` (or a new `data/macro_library_ifo_wes.csv` if the parser shape diverges enough). Series ID `wes-euro-e-2019q4` (or generic `wes_euro_climate`), `col = EA_WES_CLIMATE`, frequency Quarterly, country EA19, concept Sentiment / Survey, cycle L.
3. **Source-of-truth caveat documented:** mark in the row's `notes` that this series **ends 2019-Q4** with no current update path; future runs should detect and respect that (don't trigger a staleness alarm — extend the row's `freshness_override_days` or use a "frozen" flag).
4. **Open follow-up:** identify and wire the **current** WES-Euro publication (post-2019). Likely paths to investigate: a different ifo URL (the modern WES might publish quarterly as part of the main WES report — PDF/Excel attachment), or via DB.nomics if any aggregator picked it up (probe shows DB.nomics has no `ifo` provider though, so likely a direct ifo.de path), or via the European Commission's Joint Harmonised Programme (which Eurostat publishes — `Eurostat/ei_bssi_*` already in our DB.nomics layer covers some of the same ground). Document the result in a §3.10 follow-up.

**Acceptance:**

- `EA_WES_CLIMATE` (and any sub-component columns) populated in `macro_economic_hist.csv` for 1990Q1 → 2019Q4 (≈120 quarterly points).
- A row in the relevant `macro_library_*.csv` registers the series per §0.
- The frozen-end-date is documented in the row's `notes` AND, ideally, the row carries a `freshness_override_days` large enough to suppress audit staleness on the permanently-stuck-at-2019 series — OR the staleness check is extended to recognise an explicit "frozen" flag.
- Cross-reference from §1 Known Data Gaps acknowledging the post-2019 update path is open.

### 3.11 Indicator Explorer integration audit

**Priority:** Medium — documents the integration contract so future indicator additions surface correctly in the explorer + dashboard. Surfaced when the 2026-05-28 inflation composites didn't appear in the explorer (cause: timing — the daily run that would have computed them hadn't yet executed; explorer is correctly CSV/hist-driven).

**Status:** Stage 1 shipped 2026-06-10. Tech-manual §9.7 already documents the four-step contract; pre-flight audit check landed as `data_audit.py::_check_missing_explorer_indicators()` (surfaces any `macro_indicator_library` row without a matching `<id>_raw` column in `macro_market_hist.csv` under Section B's `missing_explorer_indicators`). 5 permanent input-gap indicators (EU_Cr1, AS_CN_R1, DE_ZEW1, JP_PMI1, CN_PMI2) allowlisted via `KNOWN_MISSING_INDICATORS` per §1 Known Data Gaps; local audit run is clean. Outstanding: explorer dry-run mode (item 4 below) is optional and deferred unless a CI gate is needed.

**Context.** `docs/build_html.py` builds the explorer by:

1. Reading **`data/macro_indicator_library.csv`** for metadata (group, sub_group, concept, subcategory, descriptions, regime classifications). The `_load_indicator_library()` helper at the top of the file.
2. Reading **`data/macro_market_hist.csv`** for time-series data. It discovers `present_ids` by scanning hist column names ending in `_raw` / `_zscore` / `_regime` / `_fwd_regime` (lines 126–132 of `build_macro_market`).

**The contract that makes a new indicator appear:**

- (a) A row in `macro_indicator_library.csv` with a unique `id`, populated `group` / `sub_group` / `concept` / `subcategory` (otherwise it lands in the `ungrouped` bucket).
- (b) A calculator registered in one of the `_*_CALCULATORS` dicts in `compute_macro_market.py`.
- (c) An entry in `REGIME_RULES`.
- (d) A **completed daily run after (a)/(b)/(c) merged** — without this, `macro_market_hist.csv` lacks the `<id>_raw`/`_zscore`/etc. columns and the explorer's `present_ids` discovery skips the indicator.

If any of (a)–(d) is missing the indicator silently doesn't appear. (d) is the easiest to overlook — the merge succeeds but the indicator is invisible until the next pipeline run.

**Scope of the audit task:**

1. **Document the four-step contract** in `manuals/technical_manual.md` §9.7 (`docs/build_html.py`) so future indicator adds have a checklist.
2. **Add a pre-flight check** to either the daily audit (`data_audit.py`) or `library_sync.py`: for every indicator in `macro_indicator_library.csv`, verify the corresponding `<id>_raw` column exists in `macro_market_hist.csv` (after the daily run). Surface any indicator that's in the library but not in the hist as a new audit finding. Same shape as the existing `missing_columns` / `missing_calculators` / `registry_drift` checks under Section B.
3. **Documented retroactive verification** — once today's daily run completes (or a manual `workflow_dispatch` is triggered), confirm the 6 new inflation composites (`US/UK/EU/JP/CN_INFL1`, `US_INFEXP1`) appear in the explorer's Macro Market Indicators tree under their groups (US, UK, Eurozone, Japan, Asia) with cycle L tags.
4. **Optional: explorer dry-run mode.** A flag to run `docs/build_html.py` against the current state and emit a manifest of indicators it would render (without writing HTML) — useful for CI to validate that any committed change to `macro_indicator_library.csv` will surface as expected.

**Acceptance:**

- Tech manual §9.7 explains the four-step contract.
- The audit / library_sync gains a check that flags any `macro_indicator_library` row without a matching `<id>_raw` column in `macro_market_hist.csv`, with a remediation hint ("trigger an `update_data` run").
- Manual verification: the 6 new inflation composites + `GLOBAL_GOLD1` appear in `docs/indicator_explorer.html` under their expected nodes after the next daily run.

### Regime-AA v2 data-pipeline asks (§3.12–§3.17)

> **Provenance & reconciliation.** These six sub-sections are the reconciled landing of the cross-repo handoff memo `manuals/2026-06-10-regime-aa-v2-pipeline-handoff.md` (filed from `regime-aa`, master-plan v2). The memo numbered them §3.10–§3.15; they are **renumbered §3.12–§3.17** here because §3.10 (ifo backfill) and §3.11 (Indicator Explorer audit) already exist. Each carries a **Pipeline status (audited 2026-06-10)** line reconciling the ask against the live code, with cross-links to existing tracks so already-done work is not re-scheduled. Factual corrections to the memo were captured for the source project in `manuals/2026-06-10-regime-aa-v2-pipeline-handoff-corrections.md` (to be filed back to regime-aa as an inverse-direction proposal).

### 3.12 OECD MEI feed — verification + ingestion (regime-AA-driven, CRITICAL)

> **Pipeline status (audited 2026-06-10; rows landed same day): 🟢 ROWS IN, CONTINUITY VERIFICATION PENDING.** 10Y sovereign yields in the OECD-MEI-via-FRED form `IRLTLT01{ISO}M156N` are now registered for all 10 priority regions — pre-existing GB/DE/IT/IND, plus US/FR/JP/CA/AU/NL/CH added as `data/macro_library_fred.csv` sort_keys 500-506 (cols `USA_TREAS_10Y`, `FRA_OAT_10Y`, `JPN_JGB_10Y`, `CAN_GOV_10Y` shared with BoC daily for fallback extension, `AUS_ACGB_10Y`, `NLD_DSL_10Y`, `CHE_GOVT_10Y`). Equity share-price indices `SPASTT01{ISO}M661N` registered for all 10 regions as sort_keys 510-519 (cols `<ISO3>_EQUITY_MEI`). `NLD` added to `data/macro_library_countries.csv`. Next-day daily run will pull the series; **continuity Jan-1957 → present is to be verified from the resulting `macro_economic_hist.csv`** (regime-AA-side `verify_fred_oecd.py` is the final acceptance gate).

**Priority:** CRITICAL — gates regime-AA Phase 0→1; the per-region equity + yield inputs feed regime labels (Phase 1) and the Layer-1 pillar score (Phase 3).

**Scope:**
- ✅ Registered monthly equity indices `SPASTT01{ISO}M661N` and 10Y yields `IRLTLT01{ISO}M156N` for US, GB, DE, FR, JP, IT, CA, AU, NL, CH as rows in `data/macro_library_fred.csv` (7 missing-region yields + 10 equities; 17 rows total). `NLD` added to country registry.
- ⏳ Confirm continuity Jan-1957 → current month per (series, region) from the next daily run; document any breaks / methodology changes in §1 Known Data Gaps.
- ⏳ Sister-file safeguard (`*_hist_x.csv`) automatic via `library_utils.write_hist_with_archive()`; land in `macro_economic_hist.csv` / `macro_market_hist.csv`; daily cadence.

**Acceptance:** `verify_fred_oecd.py` (regime-aa) returns `retrievable = True` for all priority-five pairs; ≥ 800 monthly obs from 1957-01 for US/UK/DE/FR/JP equities; rows present in the hist outputs and pass the daily audit.

**regime-aa refs:** `src/data_ingestion/verify_fred_oecd.py`, `scripts/run_phase_0_availability.py`. Memo §3.10.

### 3.13 Long-run historical data layer (regime-AA-driven, HIGH)

> **Pipeline status (audited 2026-06-10): 🟡 PARTIAL — Shiller scaffolded.** Shiller module + library schema landed (commit below); xls parser intentionally stubbed until Yale `ie_data.xls` layout is verified against a live download (sandbox 403s the URL — verification needs a credentialed CI run or a local copy). No `french / imf_pcps / jst / boe_millennium` modules yet. IMF Primary Commodity Prices is only partly present as scattered per-commodity FRED rows (iron ore, copper, …); the **aggregate index `PALLFNFINDEXM` is not wired**. Shiller CAPE is already a *planned* item in §3.3, and this exact long-run source set is already catalogued in the §3.1 note (`../longrun_assetclass_data_sources.md`). Net remaining: four new source modules, de-duped against §3.1 / §3.3 / §3.9.

**Priority:** HIGH — multi-decade depth for Phase 1 regime labels (cross-validation anchors).

**Scope (one source module + library CSV each, per §0.1):**
- ✅ `sources/shiller.py` — monthly US 1871+ (S&P price/div/earnings, US CPI, long rate, CAPE) module + `data/macro_library_shiller.csv` schema shipped 2026-06-10 (scaffold; library rows + xls parser implementation deferred). Yale `ie_data.xls` as canonical primary; verify layout on next credentialed CI run before populating library rows.
- `sources/french.py` — Ken French factors (US 5-factor + RF 1926+, intl developed 1990+, EM 2000+) via `pandas-datareader` famafrench, direct-ZIP fallback.
- `sources/imf_pcps.py` — confirm FRED-mirror coverage of aggregate indices; add SDMX-direct fetch for per-commodity series not on FRED.
- `sources/jst.py` — Jordà-Schularick-Taylor (18 economies × ~10 series × 1870+, annual) via `macrohistory.net` Stata download.
- `sources/boe_millennium.py` *(optional, lower priority)* — BoE Millennium UK rates / CPI / GDP back to the early 1700s.

**Acceptance:** each module fetches end-to-end on the scheduled run; new `data/macro_library_*.csv` pass the daily audit; regime-aa verifiers (`verify_shiller / french / imf_pcps / jst.py`) can read the produced CSVs.

**regime-aa refs:** Phase 0 test plan §3 Sources 3–6. Memo §3.11. Cross-link: §3.1, §3.3, §3.9.

### 3.14 Monthly z-score sampling alongside daily (regime-AA-driven, CRITICAL — see correction)

> **Pipeline status (audited 2026-06-10; shipped same day): 🟢 SHIPPED.** Confirmed memo error: the pipeline already uses a 156-week (3-year) rolling z-score on the weekly Friday spine (`ZSCORE_WINDOW = 156`, `ZSCORE_MIN_PERIODS = 52`) — not a "daily 252-day" one. Genuine gap was month-end *sampling* + a flat per-(indicator, region) monthly table. Shipped as `data/macro_market_monthly_hist.csv` via `df_hist.resample("ME").last()` in `compute_macro_market.py::run_phase_e` — same wide schema as `macro_market_hist.csv` (`<id>_raw` / `_zscore` / `_regime` / `_fwd_regime`), one row per month-end, each cell = the latest weekly Friday value within that month. ~320 rows × ~376 cols back to 2000-01-31. Sister-file `_x.csv` follows the existing preservation contract. Existing weekly output unchanged.

**Priority:** CRITICAL — Phase 2 validation + Phase 3 engine consume the monthly standardisation.

**Scope:**
- ✅ Emit a month-end-sampled z-score as a flat per-(indicator, region) table — `macro_market_monthly_hist.csv`. The schema choice (separate file vs `z_score_monthly` column) settled on a separate file for cleanest downstream import.
- ✅ Retain the daily/weekly z-score unchanged for the Indicator Explorer (weekly `macro_market_hist.csv` writer untouched).
- ✅ Documented in `manuals/technical_manual.md` §7 file inventory for stable downstream import.

**Acceptance:** monthly z-scores at every month-end back to series support; regime-AA Phase 3 Layer-1 reads them without further transform; existing daily output unchanged. ✅ all three satisfied.

**regime-aa refs:** master plan §3.0 (v2 horizon), §3.5.2 (normalisation). Memo §3.12.

### 3.15 Monthly per-asset EWMA features — Layer 2 (regime-AA-driven, HIGH if Layer 2)

> **Pipeline status (audited 2026-06-10; re-confirmed same day): ❌ NEW — blocked on input.** Not in the pipeline. Cannot be fully specified until regime-AA fixes its **Phase-4 regional asset universe** (~40–75 assets) and the per-region 3-month risk-free list. Defer entirely if Phase 3 settles on macro-only Layer 1. No in-session work today — gate remains the regime-AA universe decision.

**Priority:** HIGH (conditional on Layer 2 being built).

**Scope:** per asset — monthly excess return `r_t = R_t − r_f,t/12`; EWMA features at halflives {3, 6, 12} months (downside deviation, EWMA mean, Sortino-style ratio); 8-feature vector standardised vs a rolling 60-month mean/sd → `asset_jm_features_monthly.csv (asset_id, region, date, log_dd_3m, log_dd_12m, ar_3m, ar_6m, ar_12m, sr_3m, sr_6m, sr_12m)`. Plus per-region monthly cross-asset macro features (2y yield Δ, curve slope, slope Δ, VIX log-Δ, 36-month equity-bond corr) → `macro_features_monthly.csv`.

**Acceptance:** 8-feature monthly vector per universe asset from its earliest month-end; cross-asset macro features per region to 1957 (where source supports); regime-AA Phase 3 Layer 2 reads the CSVs directly.

**regime-aa refs:** master plan §3.1.1 (JM features), §3.2.2 (GBDT macro features). Memo §3.13.

### 3.16 Monthly seam-test extension (regime-AA-driven, MEDIUM)

> **Pipeline status (audited 2026-06-10): ❌ NEW — mostly consumer-side.** The daily seam test (`seam_test.py`, 92 indicators) lives in regime-AA and passed 2026-05-07. Pipeline-side work is only to ensure the §3.14 / §3.15 monthly CSVs publish on a cadence the seam test can read. Gated on §3.14 / §3.15.

**Scope / Acceptance:** confirm the monthly CSVs publish on schedule; regime-AA extends `seam_test.py` to report daily + monthly seam counts in `data/outputs/seam_test/summary.csv`. Memo §3.14.

### 3.17 ALFRED vintage-data exposure (regime-AA-driven, LOW)

> **Pipeline status (audited 2026-06-10): 🟡 CAPABILITY IN, WRITER DEFERRED.** `sources/fred.py::fetch_observations()` now accepts optional `realtime_start` / `realtime_end` parameters; new `parse_observations_vintage()` helper surfaces the FRED ALFRED rows as `(observation_date, vintage_date, value)` tuples. The default (both None) is unchanged — the daily pipeline keeps using revised data, no risk of regression. The `macro_vintage_hist.csv` writer is **deferred** until regime-AA Phase 6 specifies which series + realtime windows to materialise; building a wide vintage table without a known consumer just creates dead bytes.

**Priority:** LOW — Phase 6 backtest fidelity (vintage-data-neglect mitigation); not blocking earlier phases.

**Scope:**
- ✅ Add an optional ALFRED vintage mode to the FRED module (`realtime_start` / `realtime_end`).
- ✅ `parse_observations_vintage()` helper.
- ⏳ `macro_vintage_hist.csv (series_id, observation_date, vintage_date, value)` writer — deferred pending regime-AA Phase 6's per-series list (NBER recession flag, GDP advance vs revised, CPI revisions, …). Document ALFRED's US-centric / sparse-non-US coverage limits at the same time.

**Acceptance:** vintage retrievable for ≥ the NBER recession indicator + US CPI back to the ALFRED record start; regime-AA Phase 6 can opt in per series with the limits documented. Capability satisfied — full acceptance (vintage CSV materialised) waits for Phase 6.

**regime-aa refs:** master plan §9.1 (vintage-data neglect), §17.8 (Phase 6). Memo §3.15.

---

## 4. Project Chronology

**Priority:** Low — useful project history but doesn't move the pipeline forward.
**Status:** Not started.

```bash
git log --oneline --format="%ad  %s" --date=short | grep -v "Update market data + explorer"
```

Filter to significant changes (feature additions, bug fixes, schema changes, new modules). Output as either a dated chronology section in `manuals/technical_manual.md` (preferred — keeps the manual self-contained) or a standalone `manuals/chronology.md`. Update periodically as new features land.

---

## 5. Multi-Frequency Pipeline (Phase 2)

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
| `macro_economic_hist` | ~150 (FRED + OECD + WB + IMF + DB.nomics + ifo) x 2 + 14 metadata rows | ~430 (monthly stored at native cadence) | ~130K |
| `macro_market_hist` | 91 indicators × ~4 cols = ~365 (keep weekly) | ~1,300 | ~475K |
| Snapshots | small | small | ~10K |
| **Total** | | | **~8.8M** |

Google Sheets limit is 10M cells. Headroom is tight. Future optimisation: drop `_Local` columns for USD-base tickers (saves ~150 columns).

### Implementation Steps

1. **Add alignment utilities to `library_utils.py`:** `load_ragged_series()`, `align_series()`, `detect_frequency()`, `freq_aware_shift()`
2. **Convert `fetch_hist.py` to ragged output:** Replace spine-aligned builders with per-ticker ragged output
3. **Convert `fetch_macro_economic.py` to native frequency:** Each `sources/*.py` module yields series at native cadence (FRED daily/weekly, OECD monthly, WB/IMF annual, ifo monthly, DB.nomics monthly); the unified hist becomes ragged rather than Friday-spine forward-filled.
4. **Update `compute_macro_market.py`:** All 91 indicator calculator functions updated to consume ragged data via alignment utilities
5. **Validate:** Compare indicator values between weekly and ragged branches for overlapping Friday dates

### Risks

1. **Sheets cell budget tight (8.8M/10M)** — if more tickers added, may need to drop `_Local` for USD-base instruments or split tabs
2. **91 indicator functions to update** — each must be tested individually against weekly branch output
3. **Z-score window equivalence** — 156 weekly != 780 daily (trading vs calendar days); verify regime classifications match
4. **Cherry-pick conflicts** — hist/compute changes won't merge cleanly between branches; manual adaptation needed

---

---
