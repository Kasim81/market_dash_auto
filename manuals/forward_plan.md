# Market Dashboard — Forward Plan

> Last updated: 2026-07-15

This is the project's forward-looking working doc for the **data pipeline only**. §0 sets the architecture rules every Claude session must read before touching data-layer code. §1 is the standalone phase / data-layer summary. §2 is the prioritised work queue. §3 captures feature roadmap items not yet on the queue. §4 holds the project chronology task. §5 cross-references `multifreq_plan.md` for the larger Phase 2 (multi-frequency) rebuild. The current code state lives in `manuals/technical_manual.md`; this doc and the technical manual are the only two contributor docs you need for **data pipeline work**.

> **Scope boundary (set 2026-05-06):** This document governs the data pipeline infrastructure only — its workflow, charting / explorer functionality, data sources, data series, multi-frequency rebuild, and operational scaffolding. It does **not** govern regime-based asset allocation work. All regime identification, indicator validation, regime-conditional portfolio construction, three-framework client implementations, backtest, and related agentic build phases live in the master plan: `../regime_AA_master_plan.docx`. If a future change touches both — e.g. the data pipeline needs to add a new source to feed a regime indicator — record the data-side work here and the regime-side work in the master plan, with a cross-reference. See `../_master_plan_drafts/responsibilities_boundary.md` for the durable record of the boundary.

---

## 0. Architecture Preferences — Claude must always follow

> **Status:** Permanent. These are non-negotiable rules adopted on 2026-04-26 after two avoidable refactors caused by hardcoding identifiers in Python instead of in CSVs. Every Claude session must read this section before touching any data-layer code.

### 0.1 The single rule

**Every identifier the pipeline fetches lives in one of the source-of-truth CSVs under `data/`. Never in Python.**

There are multiple source-of-truth CSVs — one per data source — not a single registry. The full inventory is in **§1 Data-Layer Registry**, but the active set today is:

- `data/index_library.csv` — comp pipeline tickers (~401 yfinance instruments)
- `data/macro_library_countries.csv` — 14 country codes + WB / IMF mappings
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
- `data/macro_library_bdf.csv` — every Banque de France Webstat Opendatasoft Explore v2.1 key (2026-06-09; rewritten 2026-06-10 for Opendatasoft stack; verified live 2026-07-09, §2.A A6)
- `data/macro_library_alpha_vantage.csv` — every Alpha Vantage `function|symbol|field` key (2026-06-10; scaffold landed empty, populated when storage shape settled — see §3.3)
- `data/macro_library_shiller.csv` — every Shiller `ie_data.xls` column the parser surfaces (2026-06-10)
- `data/macro_library_french.csv` — every Ken French Dartmouth ZIP file + column (2026-06-10)
- `data/macro_library_jst.csv` — every Jordà-Schularick-Taylor `<iso>|<column>` pair (2026-06-10)
- `data/macro_library_atlanta_fed.csv` — every Atlanta Fed GDPNow series identifier (2026-06-11)
- `data/macro_library_ny_fed.csv` — every NY Fed Staff Nowcast series identifier (2026-06-12)
- `data/macro_library_sec_edgar.csv` — equity fundamentals registry (ticker / metric / GAAP-tag mapping; standalone isolated phase, not part of the Phase ME macro pipeline; 2026-06-15)
- `data/macro_library_eurostat.csv` — every Eurostat dissemination-API dataset+dimension key (DG ECFIN sentiment trio at geo EA21; 2026-07-09, §2.A A12)

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
| Simple Pipeline | Library-driven ~70-instrument daily snapshot (`simple_dash` flag on `index_library.csv`); consumed downstream by `trigger.py` | `fetch_data.py` → `market_data`, `sentiment_data` | Production (frozen) |
| Comp Pipeline | Library-driven ~390-instrument snapshot + weekly history from 1950 | `fetch_data.py` + `fetch_hist.py` → `market_data_comp`, `market_data_comp_hist` | Production |
| **Phase ME — Macro-Economic** (unified) | Single raw-macro data layer covering FRED / OECD / World Bank / IMF / DB.nomics / ifo / BoE / ECB / BoJ / e-Stat / LBMA / NY Fed. Replaces retired Phase A / B / C / D. | `fetch_macro_economic.py` + `sources/{fred,oecd,worldbank,imf,dbnomics,ifo,boe,ecb,boj,estat,lbma,nasdaq_data_link,ny_fed,countries}.py` → `macro_economic`, `macro_economic_hist` | Production |
| Phase E — Macro-Market Indicators | 107 composite indicators with 156w rolling z-scores, regimes, forward regimes, cycle timing (L/C/G) | `compute_macro_market.py` → `macro_market`, `macro_market_hist` | Production |
| Phase F — Calculated Fields | Synthetic columns (mostly absorbed into Phase E) | absorbed into `compute_macro_market.py` | Mostly Done |
| Phase G — Sheets Export Audit | 7-tab inventory, protected-tab guards across all 4 writers, legacy-tab cleanup, pipeline.log auto-commit | `library_utils.py` `SHEETS_*` constants | Done |
| Phase H — Daily Integrated Audit | Three-section daily audit (fetch outcomes / static checks / value-change staleness) running on the existing daily fetch's `pipeline.log`; perpetual GitHub-Issue notification with first-line `ALL CLEAN` / `N ISSUES` summary | `data_audit.py` + `.github/workflows/update_data.yml` (post-audit step) | Done |

### Phase-by-Phase Detail

#### Simple Pipeline — Production

~70 instruments selected via the `simple_dash` flag on `index_library.csv` (SPX, NDX, sector ETFs, FX majors, FRED yields, Fear & Greed, VIX term structure). Writes to the `market_data` and `sentiment_data` tabs. Preserved indefinitely for compatibility with `trigger.py`, which runs at 06:15 London time on a local Windows machine and reads `market_data` (GID `68683176`) only. No further work planned — the simple pipeline is frozen.

#### Comp Pipeline — Production

Library-driven expansion of the simple pipeline. ~390 instruments from `data/index_library.csv`; daily snapshot (`market_data_comp`) plus weekly Friday-close history from 1990 (`market_data_comp_hist`). 18-currency FX coverage via `COMP_FX_TICKERS` / `COMP_FCY_PER_USD` in `library_utils.py`. Pence correction dynamic (`.L` suffix + median > 50). Semantic `broad_asset_class` + `units` now read from the CSV rather than computed in code. The 7-step refactoring completed the transition from hardcoded lists to library-driven dispatch.

#### Phase ME — Macro-Economic (unified) — Production

A single coordinator (`fetch_macro_economic.py`) drives a per-source-module package (`sources/`) that produces one snapshot tab (`macro_economic`) and one history tab (`macro_economic_hist`). The history tab is a wide-form Friday spine from 1947, with 15 metadata rows above the data: Column ID, Series ID, Source, Indicator, Country, Country Name, Region, Category, Subcategory, Concept, cycle_timing, Units, Frequency, Last Updated, Last Observation (per-column date of the last real raw observation — added 2026-07-08 with the bounded-fill change).

**Replaces** four legacy coordinators (all deleted from the repo, all 8 of their tabs in `SHEETS_LEGACY_TABS_TO_DELETE`):

- `fetch_macro_us_fred.py` (Phase A) — US FRED series → retired tabs `macro_us[_hist]`
- `fetch_macro_international.py` (Phase C) — OECD / World Bank / IMF multi-country → retired tabs `macro_intl[_hist]`
- `fetch_macro_dbnomics.py` (Phase D Tier 2) — Eurostat / ISM → retired tabs `macro_dbnomics[_hist]`
- `fetch_macro_ifo.py` (Phase D ifo workbook) — DE_IFO subseries → retired tabs `macro_ifo[_hist]`

Phase D's "Tier 3 FMP calendar" track was paywalled and rejected on 2026-04-23 — the FMP module is also deleted. See `manuals/technical_manual.md` §13 for the durable Phase D retrospective (prior-attempts record).

**Coverage by source:**

- **FRED** — 80+ series across yields, inflation, labour, credit, surveys, commodities, OECD-mirror business/consumer confidence; back to 1947 where available. Library: `data/macro_library_fred.csv`.
- **OECD SDMX** (`sdmx.oecd.org`) — CLI, unemployment, 3-month interbank rate across 11 economies. Library: `data/macro_library_oecd.csv`. Known structural gap: OECD does not publish CLI for EA19 or CHE — `compute_macro_market.py` uses the DEU+FRA equal-weight average as the Eurozone CLI proxy.
- **World Bank WDI** — CPI YoY across 11 economies (the single `FP.CPI.TOTL.ZG` row; `col` renamed `CPI` → `CPI_YOY` on 2026-07-07 per the CPI-definition split, now the annual tier-1 fallback behind the monthly `<C>_CPI_YOY` sources). Library: `data/macro_library_worldbank.csv`.
- **IMF DataMapper v1** — real GDP growth across 11 economies. Library: `data/macro_library_imf.csv`.
- **DB.nomics** — 18 series total: 5 ISM (Manufacturing PMI / New Orders / Services / Inventories / Prices Paid), 1 Eurostat real-economy row (`EZ_EMPLOYMENT`; the industrial-production and retail-volume rows migrated to the ECB Data Portal STBS dataflow 2026-07-08, §3.18), plus 2 Stage B T1 fallback rows (IMF/IFS for `JPN_POLICY_RATE` / `CHN_POLICY_RATE` — `DEU_IND_PROD` rerouted off DB.nomics to the IMF Data Portal SDMX 2026-07-08), plus `JPN_CORE_CPI_YOY` (OECD COICOP2018), plus `CHN_M2` (NBS M_A0D01/A0D0102 — China M2 YoY%, added 2026-06-17), plus **7 OECD COICOP2018 all-items CPI YoY rows (2026-07-07, PR #249 CPI-definition split):** `JPN_CPI_YOY` (feeds `JP_INFL1`) + CAN / CHE / FRA / ITA / NLD national CPI + DEU (HICP), plus `JPN_CPI_INDEX` (OECD COICOP2018 index measure, 2015=100 — now T1 fallback behind the e-Stat tier-0 primary, §2.A A13 resolved 2026-07-09). The 2 Eurostat HICP rows (`EA_HICP`, `EA_HICP_CORE_YOY`) were rerouted to the ECB Data Portal 2026-07-08 (§2.A A10 — Eurostat discontinued the slice; DB.nomics Eurostat provider mirror frozen since 2026-01-22). The 3 Eurostat sentiment-survey rows (`EU_ESI` / `EU_IND_CONF` / `EU_SVC_CONF`) were rerouted to the direct Eurostat dissemination API 2026-07-09 (§2.A A12 — same DB.nomics mirror freeze plus the EA20 geo slice's discontinuation). Library: `data/macro_library_dbnomics.csv`.
- **ifo Institute Excel** — 26 German business-survey series (Industry+Trade composite + Manufacturing / Services / Trade / Wholesale / Retail / Construction sub-sectors, plus Uncertainty + Cycle Tracer). History from 1991. Library: `data/macro_library_ifo.csv`.
- **BoE IADB** (Stage D, 2026-04-30) — 7 UK rates / yields series: Bank Rate (`IUDBEDR`), SONIA (`IUDSOIA`), gilt par yields S/M/L, gilt zero-coupon M/L. Library: `data/macro_library_boe.csv`.
- **ECB Data Portal** (Stage D, 2026-04-30; +2 2026-06-15; +1 2026-06-17; +2 2026-07-08) — 8 Euro-area series: Deposit Facility Rate (FM dataset), AAA yield curve 2Y / 30Y (YC dataset), CISS Composite Indicator of Systemic Stress (CISS dataset, 2026-06-15 — free EZ financial conditions substitute), CES 12-month-ahead inflation expectations median (CES dataset, 2026-06-15), EZ_M3 Euro area M3 broad money supply YoY% (BSI dataset, 2026-06-17 — replaced frozen FRED mirror MABMM301EZM189S), **EA_HICP headline + EA_HICP_CORE_YOY core (HICP dataset, 2026-07-08 — §2.A A10; the post-2026-methodology successor to the discontinued ICP dataset; feed EU_INFL1)**. Library: `data/macro_library_ecb.csv`. Closes the DE 2Y bund-yield gap and the EA deposit-rate forcing-function row.
- **BoJ Time-Series Data Search API** (Stage D, 2026-04-30; +2 2026-06-10; +5 2026-06-11; +1 2026-06-17) — 10 Japan series: Policy Rate (FM01'STRDCLUCON), Tankan Large Mfg DI (JP_TANKAN1), JP PPI (JPN_PPI), Services PPI (JPN_SPPI), plus 5 Tankan sub-DIs added 2026-06-11 for the `JP_TANKAN_SPREAD1` / `JP_TANKAN_SVC1` / `JP_TANKAN_FWD1` Phase E indicators (Large Mfg Forecast, Large Non-Mfg, Large Non-Mfg Forecast, Small Mfg, Small Non-Mfg DIs), plus JPN_M2 Japan M2 broad money supply YoY% (MD02'MAM1YAM2M2MO, 2026-06-17 — replaced frozen FRED mirror MYAGM2JPM189S). Library: `data/macro_library_boj.csv`.
- **e-Stat REST API** (Stage D, 2026-04-30; +5 2026-06-10; revised 2026-06-11; IDs corrected 2026-06-17 to match the live library) — 5 Japan series, current live IDs: JPN_IND_PROD `0004052177?cdCat01=0001000&lang=J` (METI IIP — the old `0003446463` was the Cabinet Office Composite Index, repointed by PR #208), JPN_MACH_ORDERS `0003355222?cdCat01=160&cdCat02=100` (old `0003355224` was an annual table, repointed by PR #208), JPN_RETAIL_SALES `0003138782` (confirmed 2026-06-17 to be the 2013 annual archive — wrong-table defect), JPN_HH_EXP `0002070001` (WRONG-SLICE), JPN_EWS_DI `0003348427` (WRONG-SLICE). `JPN_TERT_IND` dropped 2026-06-11 — no `getStatsData` table exists. Library: `data/macro_library_estat.csv` (source of truth). Requires `ESTAT_APP_ID` env var (injected via GitHub Actions secret).
- **Bank of Canada Valet** (2026-05-28) — 5 Canada series: policy rate (V39079), GoC 2Y/10Y benchmark bond yields, BoC CPI-median core inflation, USD/CAD reference rate. Keyless JSON. Library: `data/macro_library_boc.csv`.
- **Statistics Canada WDS** (2026-05-28) — 4 Canada series: CAN CPI (all-items, vector 41690973), unemployment rate (vector 2062815), + 2 more. Keyless POST API. Library: `data/macro_library_statcan.csv`.
- **ONS Zebedee /data API** (2026-05-28; +4 2026-06-10; +1 2026-06-11; +2 2026-06-15 PR #205; +1 2026-06-17) — 14 UK series: CPI (D7G7), CPIH (L55O), real GDP (ABMI), unemployment (MGSX), employment (LF24), AWE regular pay (KAI9), Core CPI (DKO8 → GBR_CORE_CPI_YOY, blended into UK_INFL1), Index of Production (K222), Index of Services (S2KU), Retail Sales Index (J5EK), monthly real GDP (ECY2 → GBR_GDP_MONTHLY, feeds UK_NOWCAST1), **GBR_CLAIMANT_COUNT** (BCJD), **GBR_PPI_OUTPUT** (GD6Y), **GBR_CPI** (D7BT — CPI headline index monthly, 2026-06-17; primary ONS source replacing frozen FRED `GBRCPIALLMINMEI`). Keyless. Library: `data/macro_library_ons.csv`.
- **Deutsche Bundesbank SDMX-ML** (2026-05-28) — 4 Germany series including DEU_BUND_10Y (daily, ultimate source — supersedes FRED monthly mirror) and DEU_BUND_1_2Y (genuine gap — no aggregator). Keyless. Library: `data/macro_library_bundesbank.csv`.
- **ABS Data API** (2026-05-28) — 5 Australia series: CPI (all-groups), real GDP, GDP growth QoQ, unemployment rate 15+ SA, participation rate. Keyless SDMX-CSV. Library: `data/macro_library_abs.csv`.
- **ISTAT SDMX API** (2026-05-28) — 3 Italy series: monthly unemployment rate 15-74 (dataflow 151_874) and industrial production total ex-construction (dataflow 115_333). Vintage (EDITION) resolution at fetch time. Keyless. Library: `data/macro_library_istat.csv`.
- **BLS Public Data API** (2026-05-28) — 4 US series; BLS is the ultimate source for `USA_CPI_INDEX`, `USA_CORE_CPI_INDEX`, `USA_UNEMPLOYMENT` (FRED is the automatic fallback); `USA_AVG_HOURLY_EARN` (CES0500000003) is a genuine coverage gap with no FRED-library equivalent. BLS_API_KEY optional. Library: `data/macro_library_bls.csv`.
- **INSEE BDM SDMX-ML** (2026-06-09) — 3 France series (INSEE is the ultimate/primary source; supersedes OECD/Eurostat aggregators): `FRA_BUS_CONF` (Business Climate), `FRA_UNEMPLOYMENT` (ILO quarterly), `FRA_GDP_INDEX` (chained volume SA-WDA). Keyless + optional `INSEE_API_KEY`. Library: `data/macro_library_insee.csv`.
- **Banque de France Webstat Opendatasoft Explore v2.1** (2026-06-09; migrated from legacy IBM API Connect → Opendatasoft 2026-06-10; **§2.A A6 resolved 2026-07-09**) — 2 France MFI lending-rate series (`FRA_LOAN_RATE_HOUSE`, `FRA_LOAN_RATE_NFC`). A credentialed `BDF_API_KEY` probe found every observation lives in one flat store dataset `observations` keyed by `series_key` (the per-series `mir-*` catalogue datasets are empty stubs); pinned BdF's own headline aggregate keys (`MIR1.M.FR.B.A22.A.R.A.2250U6.EUR.N` households, `MIR1.M.FR.B.A20.A.R.A.2240U6.EUR.N` NFC). Verified live 2026-07-09: 281 obs 2003-01 → 2026-05 (HOUSE 3.10%, NFC 3.54%). Library: `data/macro_library_bdf.csv` (series_id format: `observations|series_key='<key>'`).
- **Atlanta Fed GDPNow** (2026-06-11, §3.1.4) — 1 US series: `US_GDPNOW` (real-time Q/Q SAAR GDP growth nowcast, daily, 2014+). Keyless Excel download — no API key required. Library: `data/macro_library_atlanta_fed.csv`. Feeds the `US_GDPNOW1` Phase E indicator on the Growth axis.
- **New York Fed Staff Nowcast** (2026-06-12, §3.1.4) — 1 US series: `US_NYFED_NOWCAST` (weekly real-time Q/Q SAAR GDP nowcast, 2014+). Keyless Excel download from the NY Fed medialibrary CDN; rightmost-non-null per publication row tracks the current-vintage headline. Library: `data/macro_library_ny_fed.csv`. Feeds the `US_NOWCAST1` Phase E indicator — second-opinion read on US growth alongside `US_GDPNOW1`. Quiet window of ~3-5 business days between final-of-Q and initial-of-Q+1 nowcasts; `_calc_US_NOWCAST1` forward-fills across the gap.
- **IMF Data Portal SDMX** (2026-07-08, §2.A A1) — 2 China series: `CHN_CPI_YOY` (monthly all-items CPI YoY, 1994+, feeds `CN_INFL1`) and `CHN_CPI_INDEX` (2020=100, 1993+). Keyless SDMX 2.1 on `api.imf.org` — the platform that replaced `dataservices.imf.org` in the IMF's 2025 data.imf.org migration; distinct from the DataMapper API (`sources/imf.py`). Escape hatch for the frozen-OECD-MEI-mirror class: the IMF's own CPI dataset is monthly-fresh where FRED's mirror froze. Library: `data/macro_library_imf_sdmx.csv` (rows carry `plausible_min`/`plausible_max` bands for audit Section E). Smoke test: `test_imf_sdmx_smoke.py` (daily CI).

**Country registry:** `data/macro_library_countries.csv` is the single source of truth for the 14 country codes (USA, GBR, DEU, FRA, ITA, JPN, CHN, AUS, CAN, CHE, EA19, IND, NLD, GLOBAL) and their WB / IMF code mappings. `IND` was added in the 2026-04-26 supplemental refactor for the India 10Y bond yield, with empty `wb_code` / `imf_code` so it doesn't fan out into multi-country queries. `NLD` was added 2026-06-10 for the §3.12 priority-10 yields/equities coverage; `GLOBAL` carries cross-country aggregate series.

**Architecture invariant (per §0):** every fetched identifier lives in `data/macro_library_*.csv`. As of the 2026-04-26 supplemental refactor `compute_macro_market.py` contains zero direct API contact — every series the calculators read is provisioned through the unified hist.

#### Phase E — Macro-Market Indicators — Production

107 composite indicators computed from the unified `macro_economic_hist` (per §1 Phase ME) plus the comp-pipeline market data. Each indicator produces: raw value, 156-week (3-year) rolling z-score, regime classification, forward regime signal (`improving`/`stable`/`deteriorating`, with optional `[leading]` suffix), and z-score trend diagnostics (`intensifying` / `fading` / `reversing` / `stable`) against 1w, 4w, 13w lookbacks. A `cycle_timing` column (L/C/G) classifies each indicator's position in the business cycle (durable detail in `manuals/technical_manual.md` §13). Metadata is a single source of truth in `data/macro_indicator_library.csv` — no hardcoded `INDICATOR_META` dict in Python. The library carries `concept` + `subcategory` columns populated against a canonical 17-concept taxonomy (Equity, Rates / Yields, Credit / Spreads, Inflation, Sentiment / Survey, Leading Indicators, Growth, Labour, Cross-Asset, Volatility, Momentum, FX, Money / Liquidity, Housing, Manufacturing, External / Trade, Consumer); these surface in `macro_market.csv` and the explorer payload. Outputs `macro_market` (snapshot) and `macro_market_hist` (weekly history). As of the 2026-04-26 supplemental refactor Phase E contains zero direct API contact — every series the calculators read is provisioned through the unified hist; PR3 (2026-04-26) cleared the build-phase `DataFrame is highly fragmented` warnings, and the 2026-04-27 fix-forward cleared the output-phase ones plus the EU_Cr1 / `BAMLEC0A0RMEY` regression. EU_Cr1 (Euro IG spread) returns n/a until a free Euro IG corporate yield source is wired (see §1 Known Data Gaps); EU_Cr2 (Euro HY spread, reads `BAMLHE00EHYIOAS`) covers the Euro-HY regime as a separate indicator.

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
| `macro_economic_hist` | `fetch_macro_economic.py` | history (weekly) | Weekly Friday spine from 1947, 15 metadata rows above the data. |
| `macro_market` | `compute_macro_market.py` | snapshot | 107 composite indicators. |
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
- **Section C — Observation staleness.** Flags series whose last real observation is older than the per-row tolerance. Since 2026-07-08 (§2.A A15) the last-observation date is read from the hist's **"Last Observation" metadata row** (writer ground truth — a held policy rate with fresh daily observations at an unchanged value reads FRESH), falling back to the original last-*value-change* archaeology when the row/cell is absent (pre-A14 file generations, sister-only columns). Tolerances come from `data/freshness_thresholds.csv` (Daily 5d / Weekly 10d / Monthly 45d / Quarterly 120d / Annual 540d) with a per-row `freshness_override_days` override on every `data/macro_library_*.csv` (48 rows widened in the 2026-04-29 bulk pass; cluster→override mapping in `manuals/technical_manual.md` §9.8; the override also doubles as the A14 bounded-fill limit at 2×).
- **Section D — History preservation.** Per-file live/sister row counts + date ranges for the three `*_hist.csv` pairs (forward_plan §3.1.1).
- **Section E — Value plausibility** *(added 2026-06-17)*. Flags any column whose latest *committed* value falls outside a physical plausibility band — the backstop for the wrong-but-fresh-value class that Section C's staleness check can't see. Bands live in `PLAUSIBILITY_BANDS_BY_COL` (built-in, seeded with `US_GDPNOW` = [-15, 20] Q/Q SAAR %) overlaid with optional per-row `plausible_min` / `plausible_max` columns in any `macro_library_*.csv`. Born from the 2026-06-17 Atlanta Fed GDPNow regression (a ~24% nowcast shipped masked by a `continue-on-error` smoke step); building this out into a comprehensive, regularly-running credibility check is queued as §2.A item A9. **2026-07-02:** the 5 ISM diffusion rows in `macro_library_dbnomics.csv` gained a `[20, 80]` band after the DB.nomics ISM Manufacturing PMI mirror shipped ~10 for a 0-100 index across late 2025; the same bands now also drive a fetch-time guard (`sources/dbnomics.filter_plausible`) so corruption is dropped before it reaches the history, and a PR Newswire fallback (`sources/ism_prnewswire.py`) refreshes stale/guarded ISM columns from ISM's official release when `BRIGHTDATA_API_KEY` is configured.

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
| `macro_library_fred.csv` | ~113 | Phase ME | `sources/fred.py` (incl. 17 OECD MEI rows §3.12 + 14 IMF PCPS commodity rows §3.9.1, 2026-06-10; +9 regime-AA coverage rows 2026-06-15; −7 2026-06-17: 4 dead IDs dropped PR #217 + 3 frozen M2/M3 mirrors replaced PR #221; −2 2026-07-08: dead JPN_CPI_INDEX mirror dropped per §2.A A11 + frozen CHNCPIALLMINMEI replaced by IMF SDMX per §2.A A1) |
| `macro_library_oecd.csv` | 3 | Phase ME | `sources/oecd.py` |
| `macro_library_worldbank.csv` | 1 | Phase ME | `sources/worldbank.py` |
| `macro_library_imf.csv` | 1 | Phase ME | `sources/imf.py` |
| `macro_library_dbnomics.csv` | 18 | Phase ME | `sources/dbnomics.py` (incl. 2 Stage B T1 fallback rows; +ISM_MFG_INVENTORIES + ISM_MFG_PRICES 2026-06-15; +JPN_CORE_CPI_YOY 2026-06-10; +CHN_M2 NBS 2026-06-17; **+7 OECD COICOP2018 all-items CPI YoY 2026-07-07 PR #249** — JPN/CAN/CHE/FRA/ITA/NLD + DEU-HICP; −2 2026-07-08: EA_HICP + EA_HICP_CORE_YOY rerouted to ECB per §2.A A10; −1 2026-07-08: DEU_IND_PROD rerouted to IMF Data Portal SDMX; +1 2026-07-08: JPN_CPI_INDEX reinstated on the OECD index measure per §2.A A13, now demoted to T1 fallback since §2.A A13's 2026-07-09 e-Stat tier-0 upgrade; −3 2026-07-09: EU_ESI/EU_IND_CONF/EU_SVC_CONF rerouted to `sources/eurostat.py` per §2.A A12) |
| `macro_library_ifo.csv` | 26 | Phase ME | `sources/ifo.py` |
| `macro_library_boe.csv` | 7 | Phase ME (Stage D, 2026-04-30) | `sources/boe.py` (BoE IADB — Bank Rate, SONIA, gilt par/zero-coupon S/M/L) |
| `macro_library_ecb.csv` | 8 | Phase ME (Stage D, 2026-04-30; +2 2026-06-15; +1 EZ_M3 2026-06-17; +2 HICP 2026-07-08 §2.A A10) | `sources/ecb.py` (ECB Data Portal — Deposit Rate, AAA yield curve 2Y/30Y, CISS systemic stress, CES 12m inflation expectations, EZ_M3 M3 money supply, EA_HICP headline + core via the new-methodology HICP dataset) |
| `macro_library_boj.csv` | 10 | Phase ME (Stage D, 2026-04-30; +PPI/SPPI 2026-06-10; +5 Tankan sub-DIs 2026-06-11; +JPN_M2 2026-06-17) | `sources/boj.py` (BoJ Time-Series — Policy Rate, Tankan Large Mfg DI, PPI, SPPI, +5 sub-DIs: Large/Small Mfg+NMfg Forecast DIs feeding JP_TANKAN_SPREAD1/SVC1/FWD1, +JPN_M2) |
| `macro_library_estat.csv` | 4 | Phase ME (Stage D, 2026-04-30; +5 growth rows 2026-06-10; revised 2026-06-11; slices pinned + JPN_RETAIL_SALES dropped 2026-07-07 PR #250) | `sources/estat.py` (e-Stat — METI IIP + JPN_MACH_ORDERS + JPN_HH_EXP/JPN_EWS_DI slices pinned & verified live; JPN_RETAIL_SALES dropped as file-only gap; JPN_TERT_IND dropped 2026-06-11 — no getStatsData table) |
| `macro_library_nasdaqdl.csv` | 0 | Phase ME (§3.9, 2026-05-08; emptied 2026-05-09) | `sources/nasdaq_data_link.py` — scaffolding kept for any future free NDL dataset; LBMA/GOLD removed when discovered to be on NDL's paid tier |
| `macro_library_lbma.csv` | 1 | Phase ME (§3.9, 2026-05-09) | `sources/lbma.py` (LBMA prices.lbma.org.uk JSON — daily gold PM USD fix back to 1968) |
| `macro_library_boc.csv` | 5 | Phase ME (2026-05-28) | `sources/boc.py` (BoC Valet — policy rate, GoC 2Y/10Y yields, CPI-median, USD/CAD) |
| `macro_library_statcan.csv` | 4 | Phase ME (2026-05-28) | `sources/statcan.py` (StatCan WDS — CAN CPI, unemployment, + 2 more) |
| `macro_library_ons.csv` | 14 | Phase ME (2026-05-28; +Core CPI + IoP/IoS/RSI 2026-06-10; +monthly GDP 2026-06-11; +Claimant Count + PPI 2026-06-15 PR #205; +GBR_CPI 2026-06-17) | `sources/ons.py` (ONS Zebedee — GBR CPI/CPIH/Core CPI, real GDP, unemployment, employment, AWE, IoP `K222`, IoS `S2KU`, RSI `J5EK`, monthly GDP `ECY2`, GBR_CLAIMANT_COUNT `BCJD`, GBR_PPI_OUTPUT `GD6Y`, GBR_CPI `D7BT`) |
| `macro_library_bundesbank.csv` | 4 | Phase ME (2026-05-28) | `sources/bundesbank.py` (Bundesbank SDMX — DEU Bund 10Y/1-2Y yields) |
| `macro_library_abs.csv` | 5 | Phase ME (2026-05-28) | `sources/abs.py` (ABS SDMX — AUS CPI, GDP, unemployment, participation) |
| `macro_library_istat.csv` | 3 | Phase ME (2026-05-28) | `sources/istat.py` (ISTAT SDMX — ITA unemployment, industrial production) |
| `macro_library_bls.csv` | 4 | Phase ME (2026-05-28) | `sources/bls.py` (BLS — USA CPI, core CPI, unemployment, avg hourly earnings) |
| `macro_library_insee.csv` | 3 | Phase ME (2026-06-09) | `sources/insee.py` (INSEE BDM — FRA business climate, unemployment, GDP volume; keyless) |
| `macro_library_bdf.csv` | 2 | Phase ME (2026-06-09; rewritten 2026-06-10; verified live 2026-07-09 §2.A A6) | `sources/bdf.py` (BdF Webstat Opendatasoft Explore v2.1 — FRA MFI lending rates; `series_id = observations\|series_key='<key>'` format, keyed into the flat `observations` store) |
| `macro_library_eurostat.csv` | 3 | Phase ME (2026-07-09; §2.A A12) | `sources/eurostat.py` (Eurostat dissemination API — DG ECFIN sentiment trio EU_ESI/EU_IND_CONF/EU_SVC_CONF, geo EA21, tier 0) |
| `macro_library_alpha_vantage.csv` | 0 | Phase ME (2026-06-10; §3.3) | `sources/alpha_vantage.py` — scaffold + smoke; empty library pending storage-shape decision (snapshot CSV vs hist column). Free-tier 25 req/day. |
| `macro_library_shiller.csv` | 6 | Phase ME (2026-06-10; §3.13) | `sources/shiller.py` (Yale `ie_data.xls` — CAPE, S&P composite price / dividends / earnings, US CPI 1871+, 10Y long rate 1871+) |
| `macro_library_french.csv` | 6 | Phase ME (2026-06-10; §3.13) | `sources/french.py` (Dartmouth FTP ZIP — US 5-factor monthly Mkt-RF / SMB / HML / RMW / CMA + RF, 1926-07+) |
| `macro_library_jst.csv` | 39 | Phase ME (2026-06-10; §3.13; −1 2026-06-11) | `sources/jst.py` (Macrohistory R6 `.dta` — 10 priority economies × 4 columns: cpi / gdp / eq_tr / ltrate, annual; CAN_EQUITY_TR_JST dropped 2026-06-11) |
| `macro_library_atlanta_fed.csv` | 1 | Phase ME (2026-06-11; §3.1.4) | `sources/atlanta_fed.py` (Atlanta Fed GDPNow — US_GDPNOW, Q/Q SAAR GDP nowcast, daily, keyless) |
| `macro_library_ny_fed.csv` | 1 | Phase ME (2026-06-12; §3.1.4) | `sources/ny_fed.py` (NY Fed Staff Nowcast — US_NYFED_NOWCAST, weekly Q/Q SAAR GDP nowcast, keyless) |
| `macro_library_imf_sdmx.csv` | 2 | Phase ME (2026-07-08; §2.A A1) | `sources/imf_sdmx.py` (IMF Data Portal api.imf.org SDMX 2.1, keyless — CHN_CPI_YOY feeds CN_INFL1 + CHN_CPI_INDEX; distinct from the DataMapper `sources/imf.py`; rows carry plausibility bands) |
| `macro_library_sec_edgar.csv` | 68 | SEC EDGAR isolated phase (2026-06-15) | `sources/sec_edgar.py` + `fetch_data.py` (equity fundamentals — 34 tickers × 2 metrics; standalone phase, not in Phase ME macro pipeline) |
| `source_fallbacks.csv` | 10 | Phase ME (Stage B, 2026-04-30; §3.9 row added 2026-05-08; T0 swapped to LBMA 2026-05-09) | Registry of T0 / T1 / T2 / T3 chain per indicator. **No longer documentation-only as of 2026-07-03 (PR #246):** every `macro_library_*.csv` gained a `tier` column and `fetch_macro_economic.py` runs an explicit tier-aware, cadence-first, staleness-fallback runtime walker (`_select_winner` / `_dedupe_snapshot_rows`) instead of the old implicit last-writer-wins merge — see tech_manual §9.4. |
| `macro_indicator_library.csv` | 107 | Phase E | `compute_macro_market.py` (composite indicator registry) — 93 original + `GLOBAL_GOLD1` (§3.9) + 5 per-region inflation composites (`US/UK/EU/JP/CN_INFL1`, §3.1.3) + `US_INFEXP1` + **6 2026-06-11** (`EU_NOWCAST1`, `US_GDPNOW1`, `UK_NOWCAST1`, `JP_TANKAN_SPREAD1`, `JP_TANKAN_SVC1`, `JP_TANKAN_FWD1`) + **2 2026-06-12** (`US_NOWCAST1`, `JP_NOWCAST1`) + **1 2026-06-15 PR #207** (`US_ISM2` ISM New Orders minus Inventories spread) − **1 2026-07-03** (`US_PMI2` removed: exact duplicate of `US_ISM1`, both `_to_weekly_friday(ISM_MFG_NEWORD)`) |
| `reference_indicators.csv` | 206 | Reference (gap audit) | §3.1.1 cross-reference; not consumed by the runtime pipeline |

**Read order in `fetch_macro_economic.py`:** `fred → oecd → worldbank → imf → dbnomics → ifo → boe → ecb → boj → estat → nasdaqdl → lbma → boc → statcan → ons → bundesbank → abs → istat → bls → insee → bdf → alpha_vantage → shiller → french → jst → atlanta_fed → ny_fed → imf_sdmx`. Each `sources/*.py` exposes `load_library() -> list[dict]` returning the unified indicator schema (`source`, `source_id`, `col`, `name`, `country`, `category`, `subcategory`, `concept`, `cycle_timing`, `units`, `frequency`, `notes`, `sort_key`). Per column, the winning source is now chosen by the tier-aware, cadence-first, staleness-fallback merge (PR #246, 2026-07-03) rather than plain last-writer-wins — this read order only supplies the final tie-break. See `data/source_fallbacks.csv` and tech_manual §9.4.

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
| **9 stale FRED rows kept as forcing functions (2026-04-29)** | FRED OECD-mirror data has frozen for `JPN_POLICY_RATE` (2008-12), `CHN_POLICY_RATE` (2015-11), `GBR_BANK_RATE` (BOERUKM, 2016-08), `CHN_M2` (2019-08), `EA_HICP` (`EA19CPALTT01GYM`, 2023-01), `CHN_IND_PROD` (CHNPRINTO01IXPYM, 2023-11), `DEU_IND_PROD` (DEUPROINDMISMEI, 2024-03), `JPN_IND_PROD` (JPNPROINDMISMEI, 2024-03), `EA_DEPOSIT_RATE` (ECBDFR, 2025-06). Rows are kept in `macro_library_fred.csv` so the daily audit keeps them surfaced. None feed any Phase E indicator. | ✅ 8 of 9 resolved via Stage B T1 fallbacks + Stage D T2 modules (DB.nomics IMF/IFS, Eurostat, BoE IADB, ECB Data Portal, BoJ Time-Series, e-Stat). Per-indicator chain in `data/source_fallbacks.csv`; status in `manuals/technical_manual.md` §13. **`CHN_M2` resolved 2026-06-17** — sourced live from DB.nomics `NBS/M_A0D01/A0D0102` (NBS M2 YoY %, 9.0% @ 2026-02); the frozen FRED mirror `MYAGM2CNM189N` was dropped from `macro_library_fred.csv`. One accepted gap remains: `CHN_IND_PROD` (NBS has no free programmatic IP index; the M2 series exists at NBS but the industrial-production index does not). |
| **10 stale series in the 117d cluster (2026-04-29 baseline)** | `PERMIT`, `FEDFUNDS`, `CMRMTSPL`, `FRA_UNEMPLOYMENT`, `DEU_UNEMPLOYMENT`, `EU_ESI`, `EU_IND_CONF`, `EU_SVC_CONF`, `ISM_MFG_PMI`, `ISM_MFG_NEWORD` — all 117d old (last_obs 2026-01-02) at the 2026-04-28 audit. 117d for monthly publishers is too long for normal lag; suggests a real fetch or publisher issue, not benign cadence. | Deliberately **not** widened in the 2026-04-29 override pass — left at base 45d tolerance so the daily audit keeps surfacing them. **`EU_ESI`/`EU_IND_CONF`/`EU_SVC_CONF` resolved out of this cluster 2026-07-09** — rerouted off the frozen DB.nomics Eurostat mirror onto the direct Eurostat dissemination API (§2.A A12); live through 2026-06, no longer EXPIRED. Remaining 7: status to be re-checked at Stage G closeout against the latest audit; any publisher genuinely silent will be documented here as a permanent gap. |
| **Investing.com / Trading Economics / S&P Global direct / FMP economic calendar** | Evaluated and rejected: scraping fragility (Cloudflare), paid-only APIs, FMP endpoints paywalled August 2025. | Do not revisit. |
| **China PPI (industrial producer prices) — live monthly** | `CHN_PPI` leg of `CN_INFL1`. Frozen at 2022-12 at **every** free aggregator: FRED OECD-MEI mirror `CHNPIEATI01GYM`, the IMF's own Data Portal PPI dataset (2026-07 vintage confirmed ending 2022-12), and the NBS mirror on DB.nomics (an all-NA shell) — NBS stopped supplying PPI to international organizations after 2022, and NBS direct is IP-restricted/undocumented (same verdict as `CHN_IND_PROD`). | ✅ **Accepted gap 2026-07-08** (§2.A A1). FRED row kept as forcing function; the A14 bounded fill ends the dead column ~90d past 2022-12, so the composite tracks the (now live, IMF-sourced) CPI alone after that — no calculator special-casing. Re-add only if NBS resumes international supply or a free NBS-direct path appears. |
| **Japan retail sales (METI 商業動態統計) — live monthly** | `JPN_RETAIL_SALES` component of `JP_NOWCAST1`. | ✅ **Accepted gap 2026-07-07** (label-vs-data audit #1). Exhaustive credentialed `getStatsList` search found no live monthly `getStatsData` table — every 業種別商業販売額/指数 table is a vintaged archive ending 2013/2019; the live METI monthly headline is Excel/file-only (`stat_infid=000040274818`), and the OECD MEI mirror on DB.nomics is frozen at 2023-10. Broken 2013-archive registration `0003138782` dropped from `macro_library_estat.csv`; `_calc_JP_NOWCAST1` reference removed (it always ran on 3 components — IND_PROD/TANKAN1/MACH_ORDERS). Re-add only via a METI Excel-file-download fetcher (`sources/meti_jp.py`) or a live OECD-STES / DB.nomics series if one is found. |


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
- ✅ §3.11 Stage 1 — indicator-explorer pre-flight check landed in `data_audit.py::_check_missing_explorer_indicators()` (surfaces under Section B's `missing_explorer_indicators`); `KNOWN_MISSING_INDICATORS` allowlist of 5 documented gaps (EU_Cr1, AS_CN_R1, DE_ZEW1, JP_PMI1, CN_PMI2); tech_manual §9.7 documents the four-step contract.
- ✅ §3.12 OECD MEI feed — 17 FRED rows landed (7 missing-region 10Y yields IRLTLT01{US,FR,JP,CA,AU,NL,CH}M156N + 10 share-price indices SPASTT01{...}M661N). NLD added to country registry. Continuity Jan-1957 → present verifies on next daily run.
- ✅ §3.13 long-run layer — all three remaining source modules shipped end-to-end the same day: `sources/shiller.py` + library (6 rows: CAPE, S&P composite price/dividends/earnings, US CPI 1871+, 10Y long rate 1871+); `sources/french.py` + library (6 US 5-factor + RF rows back to 1926-07); `sources/jst.py` + library (40 rows = 10 priority economies × cpi/gdp/eq_tr/ltrate). IMF PCPS aggregate (`PALLFNFINDEXM`) wired via §3.9.1's 14 commodity rows. Dispatch handlers in `fetch_macro_economic.py`; three new smoke tests in the workflow. BoE Millennium remains optional / lower priority.
- ✅ §3.14 monthly z-score sampling — `data/macro_market_monthly_hist.csv` shipped via `df_hist.resample("ME").last()` in `run_phase_e`; ~320 month-end rows × ~376 cols, same wide schema as the weekly hist. Underlying 156-week z-score unchanged; existing weekly output untouched. Schema documented in tech_manual §7.
- ✅ §3.17 ALFRED vintage — capability shipped (`fetch_observations(realtime_start, realtime_end)` + `parse_observations_vintage()`). `macro_vintage_hist.csv` writer deferred until regime-AA Phase 6 specifies a series list.
- ✅ §3.3 Alpha Vantage — scaffold + smoke test landed (`sources/alpha_vantage.py`, empty `data/macro_library_alpha_vantage.csv`, `test_alpha_vantage_smoke.py`, `ALPHAVANTAGE_API_KEY` exposed in the workflow). Library population pending storage-shape decision — see `manuals/2026-06-10-alpha-vantage-evaluation.md`.
- ✅ §3.9.1 multi-commodity FRED rows — 14 IMF PCPS series landed in `data/macro_library_fred.csv` (industrial metals, energy, agriculture, livestock, aggregate `IMF_PCPS_ALL`).
- ✅ §3.1.3 follow-up — core inflation series for UK / EA / JP all shipped 2026-06-10: ONS `DKO8` → `GBR_CORE_CPI_YOY` blended into `UK_INFL1`; Eurostat `prc_hicp_manr TOT_X_NRG_FOOD` → `EA_HICP_CORE_YOY` blended into `EU_INFL1`; OECD COICOP2018 ex food + energy → `JPN_CORE_CPI_YOY` blended into `JP_INFL1`. CN documented as accepted gap (no free aggregator-mirrored core slice). All four non-US `*_INFL1` calculators now match the US headline+core blend shape (CN remains headline+PPI).
- ✅ §3.1.3 follow-up — JP PPI / Services PPI shipped via BoJ Time-Series Data Search direct (`PR01'PRCG20_2200000000` → `JPN_PPI`; `PR02'PRCS20_5200000000` → `JPN_SPPI`). DB.nomics BoJ mirror rejected as stale at 2024-04/05; BoJ direct is monthly-refreshed.
- ✅ §3.1.5 JP 2Y yield — investigation closed: BoJ confirmed not to publish JGB benchmark yields; IMF IFS path frozen at 2017-05; only remaining route is MoF Japan direct (defer). The PROVISIONAL CSV row from the initial subagent attempt was rejected; gap-doc preserved instead.
- ✅ §3.1 Stage C UK growth — 3 ONS rows shipped: `K222` → `GBR_IND_PROD`, `S2KU` → `GBR_SERV_PROD`, `J5EK` → `GBR_RETAIL_VOL`. Claimant count + BICS remain outstanding due to ONS-side methodology / dataset-path complications.
- ⏳ **§3.1 Stage C UK labour series — investigate monthly-cadence CDID variants.** The LMS labour series we wired (`LF24` employment rate, `MGSX` unemployment rate, `KAI9` AWE regular pay) are surfaced via ONS at a quarterly cadence with ~45-day post-quarter-end lag — confirmed empirically by the 2026-06-10 23:43 UTC run (ages 96-159d at run time vs the original 45d tolerance, with no fresher alternative source available: OECD MEI / Eurostat / IMF IFS / ILO are all derivative ONS data with an additional harmonisation step, so they're as-slow or slower). Freshness override bumped to 150d 2026-06-11 to suppress the false-positive STALE alerts. Follow-up daily run 2026-06-11 11:52 UTC: `GBR_EMP_RATE` still STALE at 160d (just 10d over the new 150d threshold) — left as-is for now since further bumping risks masking a genuinely missed bulletin; the STALE flag is honest signal here. **Open follow-up:** ONS's Labour Force Survey has multiple alternate CDIDs covering substantially the same underlying populations on different release cadences (e.g. `LF31` is a known monthly-cadence variant of the LF24 employment-rate cut). Worth a dedicated session to enumerate the monthly-cadence alternates for each of the three series, decide whether to swap or augment, and confirm the actual ONS publication cadence (the labour-market bulletin schedule). Could shave the labour-market lag from 150d back toward ~75d without changing sources. Not blocking regime-AA work since the current 150d tolerance is honest about the actual cadence; this is a freshness improvement, not a missing-coverage fix.
- ⏳ §3.1 Stage C JP growth — 5 PROVISIONAL e-Stat rows shipped 2026-06-10 errored "does not exist" on the first credentialed run (2026-06-11 11:52 UTC). Two follow-up discovery agents found HIGH-confidence replacement `statsDataId`s for 4 of 5: `JPN_MACH_ORDERS` (0003355224), `JPN_RETAIL_SALES` (0003138782 — flagged as possibly the 2013 archive vs current monthly; next run is the tiebreaker via `last_obs`), `JPN_HH_EXP` (0003000807), `JPN_EWS_DI` (0003348423 — national current-DI table, NOT the regional 0003348424). The 5th, **`JPN_TERT_IND`**, is **deferred**: METI's 2020-base Tertiary Industry Activity Index is published only as Excel files via e-Stat's `stat-search/files` endpoint and METI's own results page, with no queryable `getStatsData` database table. The row was dropped from `data/macro_library_estat.csv` 2026-06-11; will be re-added when a file-download fetcher or `sources/meti_jp.py` direct module exists. cdCat filter discovery for the surviving 4 rows is the next round of work after the next credentialed run confirms the IDs themselves resolve. **✅ Resolved 2026-07-07 (PR #250):** the credentialed audit pinned `JPN_HH_EXP` (`cdTab=01&cdCat01=059&cdCat02=03&cdArea=00000`) and `JPN_EWS_DI` (`cdTab=140&cdCat01=100&cdCat02=100&cdCat03=100&cdArea=00000`) via `getMetaInfo`, both verified live to 2026-05; `JPN_RETAIL_SALES` (`0003138782`) was confirmed the 2013 archive with no live monthly `getStatsData` equivalent and **dropped** as a file-only Known Data Gap (estat 5 → 4 rows). Only the file-download path for the two dropped METI series (RETAIL_SALES, TERT_IND) remains outstanding.
- ✅ BdF rewrite — `sources/bdf.py` migrated from legacy IBM API Connect to Opendatasoft Explore v2.1 (new URL, `Authorization: Apikey` header, `<dataset_id>|<odsql_where>` series_id format). `BDF_API_SECRET` retired from the workflow. Both MIR rows remain PROVISIONAL — dataset_id discovery requires a portal-credentialed runtime session.
- ✅ Explorer fix — `docs/build_html.py::build_macro_economic()` source allowlist extended from 10 to 25 names so every column from LBMA / BoC / StatCan / ONS / Bundesbank / ABS / ISTAT / BLS / INSEE / BdF / Alpha Vantage / Shiller / French / JST / Nasdaq Data Link now reaches the explorer (previously silently dropped).
- ✅ Audit coverage extended — `data_audit.py::_check_orphan_country_codes()` now walks all 22 single-country libraries (was 9); `library_sync.py::MACRO_LIBS` extended to include INSEE / BdF / Alpha Vantage / Shiller / French / JST.
- ✅ Concept taxonomy normalized — 3 off-taxonomy `concept="Rates"` cells fixed to `"Rates / Yields"` across BdF (2 MFI rate rows) and Shiller (10Y long rate row).

**Recent completed work (session 2026-06-11):**
- ✅ §3.1.4 GDP Now — 3 nowcast Phase E indicators shipped: `US_GDPNOW1` (Atlanta Fed GDPNow passthrough via new `sources/atlanta_fed.py` + `data/macro_library_atlanta_fed.csv`, 366 lines, keyless Excel download, `test_atlanta_fed_smoke.py`); `EU_NOWCAST1` (equal-weight z of `EZ_IND_PROD` + `EZ_RETAIL_VOL` + `EU_ESI` + `EU_IND_CONF` — pure Phase E, no new fetchers); `UK_NOWCAST1` (ONS monthly real GDP ECY2 → YoY%, new row `GBR_GDP_MONTHLY` in `macro_library_ons.csv` sort_key 490 freshness 75d). Brings `macro_indicator_library.csv` from 99 → 105 rows.
- ✅ §3.1 Stage E — JP Tankan sub-DIs — 5 new `macro_library_boj.csv` rows (large/small Mfg+NMfg DIs + forecast variants) and 3 Phase E indicators: `JP_TANKAN_SPREAD1` (Large-vs-Small Mfg export vs domestic cycle spread), `JP_TANKAN_SVC1` (Non-Mfg-vs-Mfg services/goods rotation), `JP_TANKAN_FWD1` (Forecast-vs-Actual quarter-ahead turning-point detector). `macro_library_boj.csv` grows from 4 → 9 rows.
- ✅ e-Stat statsDataId corrections — HIGH-confidence replacement IDs committed for 4 of 5 PROVISIONAL rows (JPN_MACH_ORDERS → 0003355224, JPN_RETAIL_SALES → 0003138782, JPN_HH_EXP → 0003000807, JPN_EWS_DI → 0003348423). `JPN_TERT_IND` dropped (no `getStatsData` table — METI publishes only as Excel file). `macro_library_estat.csv` shrinks from 6 → 5 rows. cdCat filter discovery pending next credentialed run. *(Historical 2026-06-11 entry — several of these IDs were later corrected: PR #208 repointed JPN_IND_PROD→`0004052177` and JPN_MACH_ORDERS→`0003355222` (the 06-11 IDs were wrong tables), and the live library now carries JPN_HH_EXP `0002070001` / JPN_EWS_DI `0003348427`. See the source description above and the 2026-06-17 label-vs-data audit.)*
- ✅ Shiller host order swap — `shillerdata.com` promoted to primary URL; Yale fallback retained. `sources/shiller.py` grows from 400 → 471 lines.
- ✅ French 3-Factor ZIP fix — Mkt-RF / SMB / HML / RF rows re-pointed to `F-F_Research_Data_Factors_CSV.zip` (full history from 1926-07). `sources/french.py` grows from 374 → 413 lines.
- ✅ JST CAN_EQUITY_TR_JST dropped — JST R6 contains no Canadian equity total-return series. `macro_library_jst.csv` shrinks from 40 → 39 rows.

**Recent completed work (session 2026-06-12):**
- ✅ §3.1.4 US_NOWCAST1 — `sources/ny_fed.py` (348 lines) + `data/macro_library_ny_fed.csv` (1 row) wired. Downloads the NY Fed Staff Nowcast full-history Excel workbook from the medialibrary CDN; rightmost-non-null per publication row tracks the current-vintage headline. `_calc_US_NOWCAST1` in `compute_macro_market.py` forward-fills weekly across the quiet window (~3-5 business days around BEA advance). Confirmed live in the 2026-06-12 run (`raw=2.46`, `regime='near-trend'`). Smoke test: `test_ny_fed_smoke.py` added to the daily CI smoke-tests step.
- ✅ §3.1.4 JP_NOWCAST1 — `_calc_JP_NOWCAST1` in `compute_macro_market.py` wired: equal-weight z of `JPN_IND_PROD` + `JP_TANKAN1` + `JPN_RETAIL_SALES` + `JPN_MACH_ORDERS`. No new fetchers (all inputs already in the pipeline). Confirmed live in the 2026-06-12 run (`raw=1.008`, `regime='expansion'`).
- ✅ ifo Bright Data Web Unlocker fallback — `sources/ifo.py` grows from ~390 → 579 lines (PR #194). Third-strategy fallback added: when the direct URL + landing-page strategies both fail, the fetcher routes through Bright Data Web Unlocker (`BRIGHTDATA_API_KEY` + `BRIGHTDATA_ZONE` now in workflow secrets; capped at 30 calls/run; silently skips if unset). See §5 ifo entry in `technical_manual.md`.
- ✅ ISTAT retry budget tightened — `sources/istat.py` grows from 280 → 287 lines (PR #193). `timeout` 90s→30s, `retries` 6→3; worst-case pipeline blockage per series drops from ~570s to ~97s on a fully-down gateway.
- ✅ ISTAT EDITION cache — `sources/istat.py` grows to ~395 lines (PR #202, 2026-06-15). `_read_edition_cache()` / `_write_edition_cache()` / `_wildcard_resolve_edition()` functions added; per-series SDMX EDITION code cached to `data/istat_edition_cache.csv`. Wildcard probe (`?updatedAfter=2000-01-01`) only on cache miss; cache-hit path avoids the extra network round-trip on every daily run. `data/istat_edition_cache.csv` committed by CI via `update_data.yml`.

**Recent completed work (session 2026-06-15):**
- ✅ **ECB CISS + CES** (PR #204/206) — `EZ_CISS` (Composite Indicator of Systemic Stress, CISS dataset) and `EZ_INFL_EXP_12M` (consumer 12-month inflation expectations, CES dataset) added to `data/macro_library_ecb.csv`. `macro_library_ecb.csv` grows from 3 → 6 rows (including a third series). Both series live-confirmed on next daily run.
- ✅ **ONS Claimant Count + PPI** (PR #205) — `GBR_CLAIMANT_COUNT` (BCJD, JSA + UC claimants) and `GBR_PPI_OUTPUT` (GD6Y, PPI output final prices) added to `data/macro_library_ons.csv`. `macro_library_ons.csv` grows from 11 → 13 rows.
- ✅ **ISM sub-indices** (PR #206) — `ISM_MFG_INVENTORIES` and `ISM_MFG_PRICES` added to `data/macro_library_dbnomics.csv`. `macro_library_dbnomics.csv` grows from 13 (baseline) → 17 rows. Required for `US_ISM2` calculator inputs.
- ✅ **US_ISM2 Phase E indicator** (PR #207) — `US_ISM2` (ISM New Orders minus Inventories spread — naturally leading indicator of future PMI direction) added to `data/macro_indicator_library.csv`. `macro_indicator_library.csv` grows from 107 → 108 rows. `_calc_US_ISM2` wired in `compute_macro_market.py`.
- ✅ **Bucket A FRED gaps** (PR #201) — 9 new FRED rows added to `data/macro_library_fred.csv` for regime-AA Bucket A coverage gaps (US money supply, housing, consumer-credit, productivity and related series). `macro_library_fred.csv` grows from ~113 → ~122 rows.
- ✅ **e-Stat `_parse_estat_time` parser fix** (PR #208) — corrected the 10-digit `@time` format decoding in `sources/estat.py::_parse_estat_time()`. Previous implementation read `YYYYMM0000` (month in positions 5-6, trailing zeros), which never matched live METI/Cabinet Office data; actual format is `YYYY + group(2) + MM(2) + DD(2)` where group=`00` and MM repeats in the DD position for monthly series (e.g. `2026000303` = March 2026). Function comment updated with the empirically verified format. Monthly series that had silently returned zero observations now parse correctly.
- ✅ **JPN_IND_PROD + JPN_MACH_ORDERS e-Stat re-pointing** (PR #208) — both series re-pointed to confirmed `statsDataId` values. Live data confirmed on the post-fix daily run.
- ✅ **Atlanta Fed date-parsing fix** (same session) — `sources/atlanta_fed.py` date-column parser hardened to handle the GDPNow Excel's mixed date formats (Excel serial numbers vs ISO strings); prevents `NaT` propagation on historical rows.
- ✅ **SEC EDGAR smoke test** — `test_sec_edgar_smoke.py` added to the daily CI smoke-tests step (`update_data.yml`). Verifies the EDGAR XBRL API returns ≥1 CIK and ≥1 fact for a known ticker. Keyless fair-access UA.

**Recent completed work (session 2026-06-15):**
- ✅ ISTAT EDITION cache — `sources/istat.py` grows from 287 → 395 lines. Per-series vintage (EDITION) resolution now persisted to `data/istat_edition_cache.csv` on each run; wildcard-on-miss discovery logic added to handle ISTAT SDMX endpoint edition changes without manual intervention.
- ✅ PR #205 — `UK_INFL1` headline leg fixed: re-pointed `GBR_CPI` to ONS `GBR_CPI_YOY` direct series instead of the stale FRED mirror.
- ✅ PR #208 — `JPN_IND_PROD` and `JPN_MACH_ORDERS` e-Stat table parser fixed: `_parse_estat_time` now handles `@time` attribute format; corrects the "does not exist" failure on the previous cdCat filter approach.
- ✅ `JPN_HH_EXP` (0003000807) and `JPN_EWS_DI` (0003348423) statsDataIds confirmed and committed to `macro_library_estat.csv`.
- ✅ Atlanta Fed date-parsing hardened — `sources/atlanta_fed.py` grows from 366 → 392 lines.
- ✅ SEC EDGAR equity fundamentals pilot — `sources/sec_edgar.py` (441 lines) + `data/macro_library_sec_edgar.csv` (68 rows: 34 tickers × 2 metrics) + `data/equity_fundamentals.csv`. Standalone isolated phase in `fetch_data.py`; not part of the Phase ME macro pipeline; no Google Sheets write (CSV-only output).
- ✅ Bucket A regime-AA: 9 new FRED rows added to `data/macro_library_fred.csv` for regime-AA coverage gaps (grows from ~113 → ~122 rows).
- ✅ Bucket C ECB: 2 new `data/macro_library_ecb.csv` rows — CISS systemic stress index (`CISS/D.U2.Z0Z.4F.EC.SS_CIN.IDX`) and ECB CES 12-month-ahead inflation expectations median (`CES/M.Z18.ALL.T.C1120.NUM_VAR.WM`). Library grows 3 → 5 rows.
- ✅ Bucket C DB.nomics: 2 new rows added — `ISM/inventories/in` (ISM_MFG_INVENTORIES) and `ISM/prices/in` (ISM_MFG_PRICES). Library grows 15 → 17 rows.
- ✅ Bucket D `US_ISM2` — ISM Manufacturing New Orders minus Inventories spread indicator wired in `compute_macro_market.py`. Brings `macro_indicator_library.csv` from 107 → 108 rows.
- ✅ `scripts/phase_0_coverage_check.py` — new operator utility: builds the indicator × region fill matrix and sourcing backlog for regime-AA Phase 0 diagnostics.
- ✅ Source-tier audit completed (findings now codified in the tier model — `technical_manual.md` §9.4 `_load_tier_map`/`_select_winner`) and regime-AA asks sourcing backlog distilled (`manuals/regime-aa-asks/regime-aa-sourcing-backlog.md`).

**Recent completed work (session 2026-06-17):**
- ✅ **M2/M3 trio remediation (PR #221):** EZ_M3 → ECB BSI `M.U2.Y.V.M30.X.I.U2.2300.Z01.A` (verified 2.74% @ 2026-04); JPN_M2 → BoJ `MD02'MAM1YAM2M2MO` (verified 2.5% @ 2026-05); CHN_M2 → DB.nomics `NBS/M_A0D01/A0D0102` (verified 9.0% @ 2026-02). Dropped frozen FRED mirrors `MABMM301EZM189S` / `MYAGM2JPM189S` / `MYAGM2CNM189N`. `macro_library_ecb.csv` 5 → 6 rows; `macro_library_boj.csv` 9 → 10 rows; `macro_library_dbnomics.csv` 17 → 18 rows.
- ✅ **GDPNow parser fix (commit `fe5b9c0`):** `sources/atlanta_fed.py` grows from 392 → 535 lines. Added `_find_nowcast_column()` (selects the explicit "GDP Nowcast" column by name from the headline tab, preventing misidentification of other tracking columns) and `_extract_current_quarter_series()` (reads the CurrentQtrEvolution tab for the live-quarter nowcast series). `test_atlanta_fed_parse.py` (130 lines, 9 offline regression tests) added. Data audit Section E plausibility check seeded with `US_GDPNOW = [-15, 20]` band; extensible via library-CSV `plausible_min`/`plausible_max` columns.
- ✅ **DEU_HICP_INDEX base year fix:** Bundesbank library row base-year label updated "Index 2015=100" → "Index 2025=100" (Eurostat rebased German HICP to 2025=100 in early 2026).
- ✅ **GBR_CPI repoint (PR #217 batch 1, commit `f6bd28a`):** FRED `GBRCPIALLMINMEI` frozen since 2025-03; new ONS row `col=GBR_CPI` → CDID `D7BT` added to `macro_library_ons.csv`. Library grows 13 → 14 rows. Verified live: 142.4 @ 2026-05.
- ✅ **CHN_IND_PROD units fix:** library row relabelled "Index 2015=100 (SA)" → "Index, same period prev year=100 (YoY)" to match NBS methodology (the series reports YoY % relative to the same period in the prior year, not a fixed-base level).
- ✅ **4 dead FRED IDs dropped (PR #217, closes A5):** `IRLTLT01CNM156N` (CHN 10Y), `NAHBSHF` (NAHB Housing), `MICH5YR` (UMich 5-10Y inflation exp.), `BAMLER00ICOAS` (Euro IG OAS) — all return HTTP 400 `"The series does not exist."` on FRED. Combined with the 3 M2/M3 mirrors removed by PR #221, `macro_library_fred.csv` shrinks ~122 → ~115 rows.
- ✅ **devcontainer added (commit `c99a2cd`):** `.devcontainer/devcontainer.json` committed — Python 3.11 image + Node LTS feature; `postCreateCommand` installs `requirements.txt` + `@anthropic-ai/claude-code`.
- ✅ **JST GDP nominal relabelling (PR #222, commit `fb474a7`):** all 10 `<ISO>_GDP_JST` rows in `data/macro_library_jst.csv` relabelled 'Real GDP' → 'Nominal GDP', units '(real)' → '(nominal)'. JST R6 `gdp` column is current-prices nominal GDP; empirically confirmed (USA data grew ~64× 1950→2015 — consistent with nominal, not real ~6×). `sources/jst.py` docstring updated to match.
- ✅ **Index library ticker fixes (PR #223, commit `11edd10`):** corrected ticker→instrument mappings: `NDIA.L` → `INDY` (iShares India 50 ETF, currency GBP→USD, proxy_flag cleared); `CMOD.L` → `BCOM.L` (L&G All Commodities, currency GBP→USD, proxy_flag cleared); `^SP500-6020` → `^SP500-6010` (S&P 500 Equity REITs, UNAVAILABLE→CONFIRMED); 8 EMB country rows (BR/KR/MX/ID/SA/ZA/TR/AR) → UNAVAILABLE (collision with single aggregate EMB); `SMALLCAP.NS` → UNAVAILABLE. Post-fix counts: 322 CONFIRMED, 90 UNAVAILABLE, 401 total data rows.
- ✅ **Label-vs-data audit reconciliation (PR #225, commit `65d42df`, 2026-06-18):** the label-vs-data audit was cross-checked against the live pipeline. All 15 market CRITICALs and 19/22 macro CRITICALs resolved. 3 remaining open macro CRITICALs were credential-gated: 3× e-Stat Japan series (`ESTAT_APP_ID`), 3× BLS series (`BLS_API_KEY`). **Now closed** — see PR #250 below.
- ✅ **CPI-definition split (PR #249, 2026-07-07):** fixes `JP_INFL1` (was frozen at a flat ~8.49 reading `_yoy(JPN_CPI)` off the discontinued FRED `JPNCPIALLMINMEI`). Every `<C>_CPI` column split into `<C>_CPI_INDEX` + `<C>_CPI_YOY`; +7 OECD COICOP2018 all-items monthly rows (`JPN_CPI_YOY` feeds `JP_INFL1`); World Bank `CPI` → `CPI_YOY` annual fallback. Post-fix `JP_INFL1` moves monthly = `mean(JPN_CPI_YOY, JPN_CORE_CPI_YOY)`. `US_INFL1`/`UK_INFL1` were already correct; `CN_INFL1` kept on renamed `CHN_CPI_INDEX` (no fresh monthly CN aggregator). Details in `manuals/2026-06-18-source-wiring-audit-proposal.md` (Resolution section).
- ✅ **Label-vs-data audit fully closed (PR #250, 2026-07-07):** the 6 credential-gated CRITICALs resolved with `ESTAT_APP_ID` + `BLS_API_KEY`. e-Stat `JPN_HH_EXP` / `JPN_EWS_DI` slices pinned via `getMetaInfo` (verified live to 2026-05; `JPN_HH_EXP` units corrected to nominal JPY); `JPN_RETAIL_SALES` dropped as a file-only Known Data Gap (estat 5 → 4 rows; `_calc_JP_NOWCAST1` now 3 components). BLS ×4 re-verified live keyed. No CRITICALs remain.

**Recent completed work (session 2026-07-02):**
- ✅ **ISM plausibility + press-release fallback (PR #239, commit `de5a8c2`)** — three-part fix for the DB.nomics ISM mirror shipping both implausible values (~10 on a 0-100 diffusion index) and stale prints (lagging the real release ~4-8 months):
  1. **Fetch-time plausibility guard** — `sources/dbnomics.py::filter_plausible(obs, lo, hi, col)` drops out-of-band observations before they reach the committed history, using the optional `plausible_min` / `plausible_max` columns on `macro_library_dbnomics.csv` (the 5 ISM diffusion rows carry a `[20, 80]` band). Applied via `fetch_macro_economic._guarded_dbnomics_obs`. Regression test `test_dbnomics_plausibility.py`.
  2. **`data_audit.py` Section E — value plausibility** — `section_e_plausibility()` + `load_plausibility_bands()` flag any column whose latest committed value falls outside its band as a real alert (parser / unit regression), sharing the `plausible_*` band columns with the fetch-time guard. This is the fifth audit section (A–E); advances §2.A A9.
  3. **ISM press-release fallback** — new `sources/ism_prnewswire.py` splices the current month's ISM PMI headline + sub-indexes straight from the official ISM PR Newswire releases when they are newer than the guarded mirror (5 ISM columns only), via `fetch_macro_economic._maybe_ism_fallback`. Retrieval routes through the new shared `sources/brightdata.py` Bright Data Web Unlocker client (process-wide call cap); **a clean no-op when `BRIGHTDATA_API_KEY` is unset**, so the series simply forward-fills the last plausible mirror value. Parser regression test `test_ism_prnewswire_parse.py`. Together these substantially close §2.A A4.

**Recent completed work (session 2026-07-03):**
- ✅ **Tier-aware source-precedence merge (PR #246):** makes source precedence a declared, enforced contract instead of a runtime accident — root cause of the class of bug behind the `JP_INFL1` freeze (a stale World Bank *annual* series was silently outranking the fresher monthly primary source under the old implicit last-writer-wins merge). Every `data/macro_library_*.csv` gained a `tier` column (0=national/primary/direct, 1=aggregator FRED/OECD/IMF/World Bank/DB.nomics, 2=last-resort). `fetch_macro_economic.py` gained `_load_tier_map`/`_attach_tiers` (thread tier onto every indicator) and `_select_winner` (among same-column candidates: finest cadence wins, then lowest tier, then freshest; a candidate stale by >2× its own cadence yields to a fresher one; a sole candidate always wins), applied to both the snapshot dedupe (`_dedupe_snapshot_rows`) and the history merge (refactored from streaming to collect-then-select). A measure-kind guard (`_measure_kind`) refuses to auto-resolve columns whose candidates mix index/YoY/level definitions — the runtime keeps legacy behaviour there (no guess, no regression) until the column is split by definition, which is exactly why this PR alone does **not** change what `JP_INFL1` serves (see the CPI-definition split, PR #249, above). 9-case regression suite `test_tier_merge.py`. New audit tool `build_source_inventory.py` (361 lines, keyless, reads only in-repo CSVs) cross-references every declared source against what actually won the last regen and flags `FLAG_definition_collision` (5: the `_CPI` index-vs-YoY class) and `FLAG_primary_cadence_gap` (1: `FRA_UNEMPLOYMENT` — a finer INSEE ticker could be registered); writes `manuals/source_inventory_audit.xlsx`. `data/source_fallbacks.csv`'s T0-T3 chain is no longer documentation-only as a result — see §1 Data-Layer Registry and tech_manual §9.4/§9.11.

### §2.A Broken-source & freshness backlog — immediate top of queue (2026-06-15)

Distilled from the 2026-06-15 17:48 UTC daily-audit (`data_audit.txt` Section A FRED HTTP 400 cluster + Section C EXPIRED/STALE buckets) cross-checked against the source-tier audit (findings codified in the tier model — `technical_manual.md` §9.4). PR #205 (`UK_INFL1` → ONS `GBR_CPI_YOY`) and PR #208 (`JPN_IND_PROD` / `JPN_MACH_ORDERS` → correct e-Stat tables, plus the `_parse_estat_time` parser fix) close two of the seven fake-cadence violations the audit found; the items below are what remains.

**A1. China inflation cluster (CHN_CPI_INDEX + CHN_PPI) — investigate IMF IFS replacement.** ✅ **CPI resolved / PPI formalized as accepted gap, 2026-07-08.** The "IMF direct" lead paid off, with a twist: the legacy `dataservices.imf.org` SDMX endpoint is gone (the IMF migrated to **data.imf.org / `api.imf.org` in 2025**), and the new platform carries a dedicated **`IMF.STA:CPI` dataflow that is monthly-fresh for China** — `CHN.CPI._T.YOY_PCH_PA_PT.M` verified 1.20% @ 2026-05 (history 1994-01+) and `CHN.CPI._T.IX.M` verified 104.36 @ 2026-05 (2020=100, history 1993-01+) on the 2026-07-08 vintage. Fix: new source module **`sources/imf_sdmx.py`** (keyless SDMX 2.1 CSV, distinct from the DataMapper `sources/imf.py`; uses the shared `base.fetch_with_backoff` per C3) + `data/macro_library_imf_sdmx.csv` (2 rows with plausibility bands, tier 1) wired through the coordinator, sibling tools (`library_sync` / `data_audit` / `build_source_inventory` / explorer allowlist) and a live smoke test (`test_imf_sdmx_smoke.py`, in the daily workflow). `_calc_CN_INFL1` repointed from `_yoy(CHN_CPI_INDEX)` to `CHN_CPI_YOY` (the PR #249 pattern); frozen FRED mirror `CHNCPIALLMINMEI` dropped (ledgered). Validation gate passed: composite tail moves — 0.23 → 0.72 → 0.82 → 0.23 → 1.33 → 1.03 → 1.20 vs frozen flat −0.35. **PPI is dead everywhere free**: the IMF's own PPI dataset (2026-07 vintage) also ends 2022-12 and the NBS mirror on DB.nomics is an all-NA shell — NBS stopped supplying PPI internationally after 2022; formalized in §1 Known Data Gaps, FRED row kept as forcing function. *(The interim per-series date hard-cut in `_calc_CN_INFL1` was removed the same day, superseded by the A14 bounded-fill change — dead columns now end in the data layer.)* **Watch item:** the OECD-MEI-mirror freeze pattern (this + A2 + the JPN/GBR CPI cases) now has a proven escape hatch in the IMF SDMX module — A2's ITA/NLD/IND 10Y yields may be solvable the same way (the platform has IFS/rates dataflows).

**A2. European 10Y yield cluster (ITA_BTP_10Y + NLD_DSL_10Y + IND_GOVT_10Y) — discover ECB SDW replacement.** ✅ **All three resolved 2026-07-14.** All three shared the frozen FRED `IRLTLT01*M156N` OECD-MEI family (last value-change 2026-03-06). **ITA + NLD** re-sourced to the **ECB "long-term interest rate for convergence purposes"** (the Maastricht 10Y govt benchmark — same concept as the OECD series, EU-harmonised, via the already-wired `sources/ecb.py`): `IRS/M.IT.L.L40.CI.0000.EUR.N.Z` → `ITA_BTP_10Y` and `IRS/M.NL.L.L40.CI.0000.EUR.N.Z` → `NLD_DSL_10Y`, both added to `macro_library_ecb.csv` at tier 0. Verified live through the adapter 2026-07-14: ITA 424 obs 1991-03 → 2026-06 (2026-04 = 3.818 matches the frozen FRED tail **exactly**, then 3.839 → 3.734); NLD 483 obs 1986-04 → 2026-06 (2026-04 = 3.15 matches exactly, then 3.165 → 3.077). The tier merge prefers the fresh tier-0 ECB rows; the frozen FRED rows stay as documented T1 fallbacks. IMF SDMX (the A1 escape hatch) was probed first and **rejected for these two**: `IMF.STA,MFS_IR` has Italy's govt bond yield (`S13BOND`, matched 3.82) but NLD's `S13BOND` stops at 2019, and the ECB convergence series is cleaner/fresher for both. **IND resolved** via a different route: India is absent from ECB (non-EU) and IMF `MFS_IR`, but **OECD relocated the discontinued MEI `IRLTLT01` long-term-rate series to the live STES `DF_FINMARK` ("financial markets") dataflow**, which stays current. Wired `IND_GOVT_10Y` to the OECD `DF_FINMARK` dataflow (measure `IRLT`). **Upgraded 2026-07-15 to the DIRECT OECD feed:** the pipeline already has `sources/oecd.py` (keyless SDMX-CSV against `sdmx.oecd.org`, used by `CLI`/`UNEMPLOYMENT`/`RATE_3M`), so India was re-homed there as one row in `macro_library_oecd.csv` (`series_id=GOVT_10Y`, `key={countries}.M.IRLT.PA.....`, `countries=IND` → fans out to col `IND_GOVT_10Y`, tier 1) — no new module needed. The interim DBnomics OECD mirror (wired 2026-07-14) was dropped + ledgered; direct is more resilient than the mirror. Verified live through the `sources/oecd.py` adapter 2026-07-15: 174 obs 2011-12 → 2026-05 = 7.02 (matches the frozen FRED tail exactly). Wins the tier merge over the frozen FRED fallback on freshness. **Broader re-homing note:** the same `DF_FINMARK`/`IRLT` measure could carry other frozen OECD-MEI FRED yields, but only India fits the `<COUNTRY>_GOVT_10Y` fan-out naming — the others (`ITA_BTP_10Y`, `DEU_BUND_10Y`, …) use bespoke column names and are already fixed (ECB) or lower priority. Effort spent on A2: S.

**A3. Eurostat / DB.nomics aggregator-lag cluster — verify whether tolerance settings are too tight.** Seven rows trip the EXPIRED gate but the underlying sources may not actually be dead — Eurostat publishes Eurozone aggregates with a longer lag than the implied tolerance: `EZ_EMPLOYMENT` (255d STALE), `EZ_IND_PROD` (192d STALE), `EZ_RETAIL_VOL` (192d STALE), `EA_HICP` (164d EXPIRED), `EU_ESI` / `EU_IND_CONF` / `EU_SVC_CONF` (164d EXPIRED), `EA_HICP_CORE_YOY` (164d EXPIRED). Action: cross-check Eurostat's published release calendar for each series; if our tolerance is tighter than the calendar, bump the `freshness_override_days` column to the honest cadence (the ONS LMS pattern we applied at §3.1 Stage C). If a series is genuinely past calendar — i.e. Eurostat is itself behind — escalate to source replacement. Effort: S (calendar check) → M (overrides) → L (replacement only if needed). **Update 2026-07-07: `EA_HICP` / `EA_HICP_CORE_YOY` are confirmed the "genuinely past calendar" branch, not a tolerance problem** — see A10 (✅ resolved 2026-07-08 via ECB repoint). **Update 2026-07-08:** the sentiment trio + `EZ_IND_PROD` / `EZ_RETAIL_VOL` / `EZ_EMPLOYMENT` stall is the DB.nomics Eurostat provider-mirror freeze — escalated to **A12**, not a tolerance problem either.

**A4. US ISM cluster — investigate DB.nomics publisher delay.** ✅ **Largely resolved 2026-07-02 (PR #239).** Five US ISM series went EXPIRED at the same 164d mark (`ISM/pmi/pm`, `ISM/neword/in`, `ISM/inventories/in`, `ISM/prices/in`, `ISM/nm-pmi/pm` at 283d) — the DB.nomics ISM mirror both stalled (lag ~4-8 months) and shipped implausible diffusion values. The 2026-07-02 fix adds a fetch-time plausibility guard (`[20, 80]` bands) plus an official-press-release fallback (`sources/ism_prnewswire.py` via the shared Bright Data client) that splices the current month straight from ISM's PR Newswire release when it is newer than the mirror. Fallback is credential-gated on `BRIGHTDATA_API_KEY`; when unset the series forward-fills the last plausible mirror value rather than the corrupt one. Residual option (not pursued): swap to FRED `NAPM` / `NAPMNOI` / `NAPMII` / `NAPMPI` / `NMFBAI` if the press-release fallback proves insufficient once credentialed in CI. See the 2026-07-02 completed-work entry above.

**A5. FRED persistent 400-error series — accept-as-dead or replace.** ✅ **Resolved 2026-06-17 (PR #217).** Four FRED series returned HTTP 400 every run (`BAMLER00ICOAS` Euro IG Corp OAS, `IRLTLT01CNM156N` CN 10Y, `MICH5YR` UMich 5-10y inflation expectations, `NAHBSHF` NAHB Housing). The credentialed 2026-06-17 FRED probe (audit M15) confirmed all four return `"The series does not exist."` — none is published on FRED under the registered id — and none was in hist (no `col` assigned, served no data). PR #217 **dropped all four rows** from `data/macro_library_fred.csv` rather than carry permanently-broken registrations. Residual option (not pursued): `MICH5YR` and `NAHBSHF` are real US concepts, so if a *correct, verified* FRED id is later found they can be re-added as new rows — but the registered ids here are dead, so the broken-registration item is closed. *(Original task, for the record: query the FRED API directly with `FRED_API_KEY` in the runner to confirm rename vs discontinuation vs transient — done in the audit. Effort: S.)*

**A6. BdF MIR PROVISIONAL rows (FRA_LOAN_RATE_HOUSE + FRA_LOAN_RATE_NFC) — dataset_id discovery via credentialed BdF probe.** ✅ **Resolved 2026-07-09** (credentialed `BDF_API_KEY` probe). The catalogue-enumeration plan turned out to rest on a wrong mental model: the Opendatasoft Explore v2.1 instance does **not** serve data through per-series `mir-*` datasets — those catalogue entries are empty **stubs** (`has_records: false`, `fields: []`). **Every observation across all dataflows lives in one flat store dataset, `observations` (10.1M records), keyed by a `series_key` column** (`<DATAFLOW>.<dot-key>`, e.g. `MIR1.M.FR.B.A22.A.R.A.2250U6.EUR.N`), with `time_period` / `obs_value` fields the existing parser already auto-detects. So the fetch form is `observations|series_key='<KEY>'` — no per-series dataset_id, no dimension-column walk. **Second gotcha (PR #208 wrong-slice discipline applied):** the legacy ECB-harmonised dot-keys carried in the PROVISIONAL rows (`M.FR.B.A2C.A.R.A.2250.EUR.N` / `...A2A...2240...`) **do not exist** in the BdF store; BdF publishes its own aggregate headline keys — `MIR1.M.FR.B.A22.A.R.A.2250U6.EUR.N` = "New loans for house purchase, households, annual interest rate" (households, A22 aggregate over all PFIT) and `MIR1.M.FR.B.A20.A.R.A.2240U6.EUR.N` = "New loan, non-financial corporations, annual interest rate". Both verified live through `sources/bdf.py` and the coordinator 2026-07-09: 281 obs 2003-01 → 2026-05, `FRA_LOAN_RATE_HOUSE` = 3.10%, `FRA_LOAN_RATE_NFC` = 3.54%. Library rows upgraded in `data/macro_library_bdf.csv`; `sources/bdf.py` docstring and this manual's §5 BdF entry re-documented off the "per-series dataset" assumption onto the flat `observations`-store model. The fetcher code needed no change (the `<dataset_id>|<odsql_where>` shape carries `observations` + the `series_key=` filter unmodified). Effort was S as estimated.

**A7. BoJ policy rate false-positive (JPN_POLICY_RATE).** Currently flagged EXPIRED at 17d (tolerance 5d) but BoJ has not moved the policy rate since the last decision. Daily rate series are inherently event-driven. Action: bump `freshness_override_days` on this row to ~120d to reflect the policy-decision cadence; do the same scan for `EA_DEPOSIT_RATE`, `CAN_POLICY_RATE`, `CHN_POLICY_RATE`, `GBR_BANK_RATE` (event-driven rates flagged stale because the central bank hasn't moved is honest-signal noise — set per-row overrides). Effort: S (5 CSV edits).

**A8. JPN_RETAIL_SALES calculator-orphan auto-resolution.** ✅ **Resolved 2026-07-07.** The credentialed e-Stat audit confirmed no live monthly `getStatsData` table exists for METI 商業動態統計 (all vintaged to 2013/2019; live headline is Excel-only). The broken registration was dropped and the dead `_get_col(...,'JPN_RETAIL_SALES')` reference removed from `_calc_JP_NOWCAST1`, so the Section-B orphan flag clears at the source. Retail is now a documented Known Data Gap (above). The sibling e-Stat WRONG-SLICE items were closed in the same pass: `JPN_HH_EXP` (slice pinned `cdCat01=059&cdCat02=03&cdArea=00000`, units corrected to nominal JPY) and `JPN_EWS_DI` (DI slice pinned `cdTab=140&cdCat01=100&cdCat02=100&cdCat03=100&cdArea=00000`), both verified live to 2026-05. The 4 BLS rows were re-verified live with `BLS_API_KEY`.

**A9. Build a comprehensive data-credibility check test that runs regularly.** 🟢 **Core shipped 2026-07-15; cross-series assertions are the remaining increment.** *(Raised 2026-06-17 from the Atlanta Fed GDPNow workflow-failure investigation — a ~24% `US_GDPNOW1` nowcast that no audit section and no test caught.)* Delivered this pass:
  - **Family-default plausibility bands** — `data_audit._family_default_band(units, concept, subcategory, col)` infers a WIDE physically-motivated band per series family (YoY growth, rates/yields, net-balance surveys, sentiment composites, diffusion PMIs, CPI/IP index levels, factor returns, etc.), applied under the built-in table and the per-row `plausible_min`/`plausible_max` override (`load_plausibility_bands`, precedence: family → built-in → per-row CSV). Section E coverage jumped **20 → 185 of 338 data columns** with zero per-row CSV editing; level/price/nominal families (equity TR, GDP/money levels, commodity/FX) deliberately get no static family band (they trend across orders of magnitude — per-column bands only). Bands are wide by design: the target is *gross* regressions (sign flip, ×100/÷100, wrong-column), not tight surveillance.
  - **Ran it as its own regular check** — new `test_plausibility.py` runs the full Section E check over the committed `macro_economic_hist.csv` (plus unit tests pinning the family classification) and is wired into `ci.yml`. Because CI fires on every `pull_request` **and** every push to `main` (incl. the daily data commit), a credibility regression now BLOCKS a PR and turns the daily push red — caught even when the fetch step "succeeds". This is the "scheduled test over committed CSVs" the item asked for.
  - **Escalation contract decided + documented** — Section E stays a WARNING channel in the daily fetch (never fails the build; already-fetched data still commits, operator alerted via the Issue); the HARD gate is the CI test. Split is deliberate: block PRs, flag daily pushes, don't refuse to commit already-fetched data.
  - **Findings surfaced on first run (the framework earned its keep):** `CHN_EXPORTS`/`CHN_IMPORTS` were mislabelled `units="USD Growth Rate YoY"` but carry FRED `XT*VA01CNM667S` **value levels** (~$360bn/$270bn) — relabelled to "USD (monthly value level)" *(follow-up: if YoY was intended, re-point to the `…659S` growth series)*. The 9 OECD `"normal value = 100"` confidence columns are genuinely heterogeneous (some net balances −42..26, some centred-100 like `CHN_CON_CONF` 85..127) — handled with one wide sentiment band, not a false relabel.
  - **Period-jump check shipped 2026-07-15 (A9.2)** — the "index/level whose implied period-over-period change is within bounds" assertion. `section_e_plausibility` now also returns `jumps`: for the LEVEL/PRICE families the static bands deliberately skip (currency-denominated levels, commodity prices, employment/GDP/money levels — 33 columns), a ×3+/÷3+ move between the two most recent real prints (via `load_recent_distinct_values`, which collapses the Friday-spine ffill) is flagged as a likely ×100/÷100 unit error. Strictly gated (`_is_level_price_units` + all-positive) so it never fires on returns / rates / balances / around-zero indices (which cross zero and vary). Clean on committed data; `test_plausibility.test_no_level_price_jumps` + the units-gate unit test added; report/comment renderers show a `JUMP` line.
  - **YoY-vs-index consistency shipped 2026-07-16 (A9.3)** — `section_e_plausibility` now also returns `inconsistent`: for each served `<C>_CPI_YOY` with a sibling `<C>_CPI_INDEX` (CAN/CHN/DEU/GBR/JPN pairs today), the served YoY is compared to the 12-month change implied by its own index (index point closest to −365d, `_cpi_yoy_index_consistency` + `load_full_column_series`). A >3pp divergence is flagged — the frozen-YoY-while-index-moves signature (the JP_INFL1 freeze that started A9). Tolerance is wide because committed pairs agree to <0.8pp (source/vintage + base-effect noise); `test_plausibility` gains a live-data assertion **and** a synthetic-freeze unit test proving it catches a stuck 9% YoY against a 2%-rising index. Report/comment renderers show an `INCONSISTENT` line. **A9 is now fully complete.** The only cross-series check NOT built is data-layer spread identities (`legA − legB`) — deliberately skipped because virtually all such spreads live in the calculator layer, not the data columns Section E sees.

**A10. `EU_INFL1` silently frozen since 2026-01 — Eurostat HICP source repair (P0).** ✅ **Resolved 2026-07-08.** Root cause found: **Eurostat's 2026-02-04 HICP methodological overhaul** discontinued both the old Eurostat `prc_hicp_manr` slices and the ECB `ICP` dataset (the ECB embeds this in an `OBS_COM` comment on the final ICP observations); the ECB published a successor **`HICP` dataflow** (same 6-dimension shape, `DATA_PROVIDER=4D0` replacing the old `4`, full history to 1996-12). Compounding it, **the entire DB.nomics Eurostat provider mirror is frozen — last indexed 2026-01-22** (see A12). Fix: `EA_HICP` → ECB `HICP/M.U2.N.000000.4D0.ANR` and `EA_HICP_CORE_YOY` → `HICP/M.U2.N.XEF000.4D0.ANR`, both added to `macro_library_ecb.csv` (tier 0) and verified live 2026-07-08 (headline 2.8% / core 2.4% @ 2026-06, both parsing through `sources/ecb.py` unchanged); the two dead DB.nomics rows dropped from `macro_library_dbnomics.csv` (ledgered in `removed_tickers.csv`); the frozen FRED T0 mirror `EA19CPALTT01GYM` stays as a documented fallback (the tier merge prefers the fresh tier-0 ECB row). Validation gate passed: simulated `EU_INFL1 = mean(headline, core)` month-end tail moves — 1.95 → 2.15 → 2.45 → 2.60 → 2.90 → 2.60 (Jan–Jun 2026) vs the frozen flat 2.1, with a continuous splice at Dec-2025 (2.15 new vs 2.1 old). `data/source_fallbacks.csv` EA_HICP chain updated (T1 marked DEAD, T2 = ECB LIVE). The frozen composite lands fresh on the first daily run after merge.

**A11. Freshness-honesty pass — widen overrides only where cadence justifies it (P1).** ✅ **Done 2026-07-08** (same PR as A10). Applied, per the handover doc's P1 section:
  - **OECD COICOP2018 CPI-YoY family** → `freshness_override_days=90` on all 7 PR #249 rows (`JPN/CAN/CHE/FRA/ITA/NLD/DEU_CPI_YOY`) **plus `JPN_CORE_CPI_YOY`** (same OECD ~6–8-week publication cadence) in `macro_library_dbnomics.csv`.
  - **e-Stat** `JPN_HH_EXP`, `JPN_EWS_DI` → 80d (FIES / Economy-Watchers ~5–6-week lag). **`JPN_IND_PROD` deliberately left at 60d** — 123d observed is beyond any honest cadence for the METI IIP finals table, so the STALE flag stays as live signal until the cadence question is settled.
  - **ONS** `GBR_CPI_YOY` → 90d.
  - **Event-driven policy rates** → 120d (decision cadence): `JPN_POLICY_RATE` (boj), `CAN_POLICY_RATE` (boc), `CHN_POLICY_RATE` (dbnomics — also mirror-stale; wide override honest either way), `EA_DEPOSIT_RATE` (ecb, was 30d). `GBR_BANK_RATE` already at 200d — untouched.
  - **Dead frozen mirror `JPN_CPI_INDEX` dropped** from `macro_library_fred.csv` (FRED `JPNCPIALLMINMEI`, frozen 2021-06, no consumer — grep-verified; ledgered in `removed_tickers.csv`); orphan hist column archived + pruned via `python library_sync.py --confirm` (`data/_archived_columns/macro_economic_hist__JPN_CPI_INDEX__2026-07-08.csv`). **Amended same day (operator decision): the column is reinstated, not retired** — Japan must keep a CPI index measure. Rewired 2026-07-08 to the live OECD COICOP2018 index measure (T1, verified 1955-01 → 2026-04 = 115.0, base 2015=100 confirmed) in `macro_library_dbnomics.csv`; the e-Stat tier-0 upgrade is queued as **A13** below. Only the dead FRED registration stays dropped.
  - Offline validation (no keys in the session sandbox): `data_audit.py` over the committed CSVs went **79 issues → 70** (FRESH 190→198, STALE 61→54, EXPIRED 18→16, Section B clean); the residual EA_HICP staleness clears on the first post-merge daily regen. The guardrail held: no live-composite tolerance was widened.
  - **Bonus fix (same PR):** the daily workflow's commit step never listed the three Pattern-9 `*_hist_x.csv` sister archives, so sister updates written in CI were silently discarded on the happy path (they only persisted when a push-conflict retry's `git add -A` caught them — committed sisters had drifted to 2026-04-24/2026-05-01). `update_data.yml` now adds all three explicitly; the audit's Section D subset-ALERTs self-clear on the next daily run.

**A12. DB.nomics Eurostat provider mirror frozen since 2026-01-22 — remaining stalled Eurostat rows (P1, discovered during A10).** The A10 investigation found the stall is two-layered: besides the HICP dataset discontinuation (fixed), **DB.nomics's entire Eurostat provider has not been re-converted since 2026-01-22** (`/v22/last-updates` shows `indexed_at 2026-01-22`, `converted_at null` — probably broken by the same Eurostat year-end restructuring). Every remaining Eurostat-via-DB.nomics row is therefore frozen regardless of what Eurostat itself publishes: `EU_ESI` / `EU_IND_CONF` / `EU_SVC_CONF` (2025-12; feed `EU_NOWCAST1`, which still moves on its other legs), `EZ_IND_PROD` (2025-11), `EZ_RETAIL_VOL`, `EZ_EMPLOYMENT`, and the `DEU_IND_PROD` T1 fallback (`teiis080` DE slice). **Update 2026-07-08 (§3.18): the real-economy legs are RESOLVED** — `EZ_IND_PROD` / `EZ_RETAIL_VOL` re-pointed to the ECB **STBS** dataflow (the STS successor, `DATA_PROVIDER=4D0` — found by the A10 method; note the old ECB `STS` dataflow itself froze 2025-09, so probe STBS not STS) and `DEU_IND_PROD` to IMF PI; the three dead teiis rows are dropped and ledgered. **Still open on this item: the sentiment trio (`EU_ESI`/`EU_IND_CONF`/`EU_SVC_CONF`) and `EZ_EMPLOYMENT`** — the ECB does not republish the DG ECFIN surveys, so action (1) (direct Eurostat probe from an environment that can reach `ec.europa.eu`) stands for those four. Probed and ruled out 2026-07-08: the uppercase `Eurostat/EI_BSSI_M_R2` DB.nomics dataset (staler, 2025-03), `teibs010` (same 2025-12 stall), `ei_bssi_m_r3` (does not exist). Actions, in order: (1) probe the **direct Eurostat dissemination API** for the sentiment trio + IP/retail/employment from an environment that can reach `ec.europa.eu` (the 2026-07-08 session's proxy blocked it) — the surveys are DG ECFIN products still published monthly, so fresh slices likely exist under possibly-new dataset codes; (2) if fresh, either build the small `sources/eurostat.py` direct fetcher (the API is keyless JSON-stat) or repoint to another aggregator that carries them; (3) also re-check whether DB.nomics has resumed converting Eurostat (if so, the existing rows may simply resume). Watch item: any *other* DB.nomics-provider rows (IMF/IFS `CHN_POLICY_RATE` etc.) may be subject to similar mirror lag — cross-check `converted_at` per provider when investigating A1. Effort: S (probe) → M (new fetcher).

> **✅ Sentiment trio RESOLVED 2026-07-09** (from an environment with `ec.europa.eu` egress). Two-layer stall confirmed and root-caused: (a) DB.nomics's Eurostat provider is still frozen (`/v22/last-updates?provider_code=Eurostat` returns zero docs — no resumption), AND (b) the direct `ei_bssi_m_r2` slice we were querying was **also** stalled at 2025-12 — not a restructure of the dataset, but **Bulgaria's euro adoption on 2026-01-01**: the euro-area aggregate geo code migrated `EA20` → **`EA21`**. The old `EA20` code is now labelled "Euro area – 20 countries (2023-2025)" and frozen at 2025-12; the fresh series (back-recomputed to 1980-01, current to 2026-06) lives under `EA21` = "Euro area – 21 countries (from 2026)". The dataset `ei_bssi_m_r2` and the `BS-ESI-I`/`BS-ICI-BAL`/`BS-SCI-BAL` indic codes never moved. Fix: new keyless JSON-stat fetcher **`sources/eurostat.py`** (dissemination API `.../statistics/1.0/data/<dataset>?<dims>&format=JSON`; modelled on `sources/ecb.py`, uses `sources/base.fetch_with_backoff`; parser guards against un-pinned dimensions per the PR #208 wrong-slice lesson) + new registry `data/macro_library_eurostat.csv` carrying the 3 rows at tier 0 (`ei_bssi_m_r2?indic=<CODE>&s_adj=SA&geo=EA21&freq=M`); the 3 dead DB.nomics rows dropped from `macro_library_dbnomics.csv` and ledgered in `removed_tickers.csv`. Coordinator wired (import, `load_all_indicators`, snapshot+hist dispatch, `_fetch_eurostat_{snapshot,history}`); source registered in `library_sync.py MACRO_LIBS`, `data_audit.py SOURCE_BY_LIBRARY`. **Validation gate passed** (verified live 2026-07-09): `EU_ESI` 558 obs 1980-01 → 2026-06 = 95.0 (moving: 93.3→93.7→95.0 Apr–Jun), `EU_IND_CONF` 558 obs → -7.7, `EU_SVC_CONF` 375 obs → 3.2; all three resolve through the coordinator at tier 0 with the snapshot returning 2026-06; `EU_NOWCAST1`/`EU_ESI1`/`EU_PMI1` consume by unchanged col name so their ESI/industry legs now move. **Euro-area geo watch:** the next enlargement will bump the code again (`EA22`…); when a euro-area Eurostat/ECB row goes stale, check the geo label's "(from YYYY)" suffix first. **✅ `EZ_EMPLOYMENT` resolved 2026-07-14** — the last DB.nomics-mirror Eurostat leg. Rather than the direct `sources/eurostat.py` path (which couldn't be validated without `ec.europa.eu` egress, and whose `namq_10_a10_e` EA21 aggregate isn't yet in the frozen mirror), re-sourced to the **ECB MNA** (ESA2010 national accounts) total-employment series `MNA/Q.Y.I9.W2.S1.S1._Z.EMP._Z._T._Z.PS._Z.N` via the already-wired `sources/ecb.py` — **live-validated** (no egress problem): 125 obs 1995-Q1 → 2026-Q1 = 172,759 thousand persons (fresh; the frozen mirror stopped at 2025-Q3 = 172,210). Added to `macro_library_ecb.csv` tier 0; the frozen DB.nomics `namq_10_a10_e` row dropped and ledgered in `removed_tickers.csv`. REF_AREA I9 is EA20 fixed composition (excludes Bulgaria's 2026 entry, negligible for a coincident labour gauge). **A12 is now fully closed** — no remaining Eurostat-mirror legs.

**A14. Bounded forward-fill — kill fabricated currency in the unified hist.** ✅ **Done 2026-07-08** (operator-approved design; replaces the short-lived `_calc_CN_INFL1` per-series date hard-cut, which was rejected as ticker-specific calculator treatment). Forward-fill onto the Friday spine is now bounded at **2× each series' staleness tolerance** (same registry as the audit: `freshness_thresholds.csv` + per-row `freshness_override_days` — the EXPIRED line is where fill stops), measured against raw observation dates at write time (exact — constant-valued live series like held policy rates are never touched). Beyond the bound a column is NaN: a dead series visibly ends instead of silently flatlining composites and z-scores (the JP/EU/CN_INFL1 freeze class). Three layers: writer (`_bounded_spine_fill` + new 15th **"Last Observation"** metadata row = per-column last real raw obs), sister archive (standing `trailing_bounds` invariant in `write_hist_with_archive` — scrubs pre-change fabricated cells on the first post-merge run, prevents re-entry, preserves Pattern-9 truncation history), consumers (`_to_weekly_friday` dropna-first + `_ALIGN_FFILL_LIMIT` caps on the 4 cross-series alignment helpers). All hist readers now sniff the metadata-prefix generation (`load_hist_with_archive(skiprows="auto")`, `data_audit._split_meta_and_data`) so 14- and 15-row header files coexist. Offline validation over all 107 calculators: only `EU_INFL1` and `CN_INFL1` tails changed (both intended — `CHN_PPI` alone carried 175 weeks of fabricated fill; the biggest trims were the dead CHN cluster, the 39 JST annual columns, and the frozen Eurostat-mirror set). Durable design: tech_manual §11 **Pattern 12**; regression suite `test_bounded_fill.py` in the ci.yml gate. Stepping stone to §5 multifreq (native-frequency storage, no fill at all). **Follow-ups:** planned in detail as **A15** (Section C ← Last Observation) and **A16** (comp-hist bounded fill) below — sequence A15 → A16, each its own PR, after the first post-merge daily run (which writes the 15-row header, scrubs the sisters' fabricated cells — expect loud `[sister-bound]` lines in `pipeline.log`, ~175 for `CHN_PPI` alone — and may report one-off Section D sister row-count changes before settling).

**A15. Audit Section C consumes the "Last Observation" metadata row (bounded-fill follow-up 1 — do first).** ✅ **Done 2026-07-08** — implemented exactly as planned below: `load_macro_hist()` prefers the metadata cell with archaeology fallback; dual-duty notes added to the 4 event-driven-rate override rows (boj/boc/dbnomics/ecb); 3-case regression class `SectionCLastObservationTest` in `test_bounded_fill.py` (metadata-wins incl. the held-rate case, blank-cell fallback, old-generation fallback). The metadata path activates on the first daily run that writes the 15-row header; until then the fallback preserves pre-A15 behaviour byte-for-byte. *(Original plan follows for the record.)* Replace Section C's value-change archaeology with the ground-truth per-column last-real-observation date the A14 writer now records. Why: archaeology cannot distinguish a held policy rate (real daily observations at an unchanged value) from a dead series — the false-positive class that forced A11's wide event-driven-rate overrides (`CAN_POLICY_RATE` read 249d "stale" while receiving fresh data daily). Plan: (1) `data_audit.load_macro_hist()` uses the `Last Observation` metadata cell when present and non-blank, **falling back to value-change archaeology** when blank (covers sister-only columns like intermittent `DE_IFO*`, columns absent from today's provenance, and any pre-A14 file generation); (2) keep the A11 event-driven-rate overrides — no longer needed for staleness noise but they still serve as *fill bounds* (dual duty; note it in the row notes); (3) tests: metadata-driven path, blank-cell fallback, and a constant-valued series that archaeology would misdate but the metadata row dates correctly. Non-goals: Section E untouched (it wants the latest value, not the date); ISSUE/CLEAN output format unchanged. Also an O(rows×cols) → O(1)-per-column win on the audit's CSV walk. Effort: S.

**A16. Bounded fill for `market_data_comp_hist` (bounded-fill follow-up 2).** ✅ **Done 2026-07-08** — implemented per the plan below with one design upgrade discovered during validation: the flat 21d FRED limit would have sliced the interior fill of *monthly* FRED series in the comp leg (`PIORECRUSDM` iron ore), so the limit is **inferred per series from raw observation spacing** (`_infer_fill_limit_days`: daily/weekly → 21d floor, monthly → 90d, quarterly → 240d). Shipped: shared `library_utils.bounded_spine_fill` (macro writer now imports it too); bounded `align_to_friday_spine` + FX-conversion fill; 12th "Last Observation" comp metadata row; per-column `trailing_bounds` for the comp sister; sniff-based header parsing extended to the comp readers (`build_html`, `data_audit` split detector, `library_sync._comp_archive`). Offline archaeology sim over the committed file: **zero live columns trimmed** — purely forward protection. 2 new tests in `test_bounded_fill.py` (17 total). *(Original plan follows for the record.)* The comp pipeline is only partially exposed — scoped by inspection 2026-07-08: **yfinance prices are already bounded** (`fetch_hist.py` uses `ffill(limit=5)`, 5 weeks — prior art for Pattern 12); the real gaps are (i) the **FRED leg**: `align_to_friday_spine()` (`fetch_hist.py:91`, used for the rates/spreads/OAS columns) reindexes with unbounded `method="ffill"` — a discontinued FRED series flatlines forever; and (ii) **FX conversion** (`fetch_hist.py:~404`): the FX series is forward-filled onto the full price index unbounded, so a dead FX pair would silently freeze the USD conversion of every instrument in that currency *while local prices keep moving* — worse than a flat series because the output still moves with a stale conversion baked in. Plan: (1) bound `align_to_friday_spine` with the A14 raw-observation-age approach (consider moving `_bounded_spine_fill` into `library_utils` so both writers share it); the comp hist's `Frequency` metadata is uniformly "Weekly" but the FRED legs are natively daily, so derive the bound from actual cadence (FRED daily → 2×5d) with a **~3-week floor** to survive market-holiday clusters — the floor is the one open design decision; (2) bound the FX alignment at the same daily-cadence limit (stale FX ⇒ USD variant goes NaN rather than silently mis-converting); (3) add a "Last Observation" metadata row to the comp writer (11 → 12 prefix rows — free now that every reader sniffs the header); (4) pass `trailing_bounds` to `write_hist_with_archive` for the comp sister — the ICE BofA truncation-preserved rows are *interior* (pre-window) so the trailing clear cannot touch them, but give it its own fixture test; (5) verify-not-change: `audit_writeback`/UNAVAILABLE keys off Section A's `pipeline.log` parse, not hist fill (no coupling expected); the audit's split/jump detector must tolerate NaN tails; market-fed calculators already flow through A14's bounded helpers. Validation: the A14 offline delta-report harness over all 107 calculators against committed vs bounded-simulated comp hist — deltas only on indicators fed by genuinely-dead series, listed in the PR body. Effort: M (~half of A14; the machinery exists).

**A13. `JPN_CPI_INDEX` tier-0 upgrade — wire the Statistics Bureau CPI via e-Stat.** ✅ **Resolved 2026-07-09.** The true primary — the **Statistics Bureau 2020-base CPI on e-Stat, `statsDataId 0003427113`** (消費者物価指数（2020年基準）, toukei 00200573) — is now wired at tier 0 in `macro_library_estat.csv`. Slice pinned via a credentialed `getMetaInfo` run (the PR #208 wrong-slice lesson — not committed blind): `cdTab=1` (表章項目 指数 = index measure; siblings are `2`=前月比・前年比 and `3`=前年同月比 YoY), `cdCat01=0001` (2020年基準品目 総合 = all-items headline, 790-classification item dimension), `cdArea=00000` (地域 全国 = nationwide), `lang=J` (the table is absent from the English DB). Verified live via the adapter 2026-07-09: **733 obs 1970-01 → 2026-05 = 113.5** (base 2020=100 confirmed). **Wrong-slice guard applied:** the June-2026 figure in the `getMetaInfo` time dimension is the Tokyo-ward lead cut (`cdArea=13A01`, ~1 month ahead); the national all-items series correctly ends 2026-05 (national June releases ~2026-07-19). Tier merge verified live via `_dedupe_snapshot_rows`: e-Stat (tier 0, 2026-05) wins over the OECD COICOP2018 index (now T1, tier 1, base 2015=100, 2026-04) — same `index` measure-kind, so the cadence-first/lowest-tier rule applies cleanly (no definition collision). `data/source_fallbacks.csv` chain updated (T0 e-Stat LIVE, T1 OECD, T2 dead FRED mirror); the OECD `macro_library_dbnomics.csv` row notes re-marked as the T1 fallback. BoJ was correctly ruled out (its Time-Series DB carries only producer-side prices — PR01 CGPI / PR02 SPPI / PR03 IO / PR04 FD-ID; CPI is MIC's). *Optional follow-up (not done — deferred to avoid repointing the two live OECD YoY rows without a full validation pass): the same table's `cdTab=3` YoY measure can serve `JPN_CPI_YOY` (`cdCat01=0001`) and `JPN_CORE_CPI_YOY` (ex-fresh-food-and-energy item code) at tier 0 in a future slice-pinning session.*

**A17. Re-validate the FactIQ audit's value-level findings against live `market_data_comp.csv` (2026-07-12 audit follow-up).** ✅ **Confidence-refresh done 2026-07-14** against the current file (as-of 2026-07-12, updated 2026-07-14 04:05 UTC — much fresher than the 2026-05-12 snapshot the prior passes used, so value tolerances are tighter). Representative cross-asset Tier-A sample (9 instruments spanning all 5 Tier-A classes) cross-checked against live FactIQ `get_market_data`: equity ETFs `SCHD`/`ACWI`/`IXN`/`REET` each matched FactIQ's `previous_close` **exactly** and sat inside the 52-week range; `GC=F` (~$4021, Gold spot ~$4057–4111/oz — futures-vs-spot/date basis, correct scale/units) and `CL=F` (~$79.9, WTI CL1 ~$79.6–80/bbl); `GBP/USD` 1.3362 vs FactIQ 1.33965 (0.26%, intraday); `BTC-USD` $63.8k inside the [57.8k, 126.2k] 52wk range; Treasury yields `^IRX`/`^FVX`/`^TNX`/`^TYX` = 3.73/4.36/4.61/5.10 form a correct upward 3–5% curve (`^TNX` isn't served by the market-data endpoint — the manual's par-curve check used FactIQ's Treasury *schema*, so magnitude-sanity only here). **Zero scale/sign/÷100 anomalies** — concurs with the 2026-07-13/14 full passes; the fresher file holds. Scope note: this was a representative sample, not all 89 Tier-A rows, chosen because FactIQ MCP was flapping this session and this is an explicit confidence-refresh with two prior full passes at zero anomalies. Tier-B: the top item (A18, CSI 500) was resolved this session; the other Tier-B unresolvables are unchanged. *(Original task follows for the record.)* The 2026-07-12 audit's *structural* findings were already fixed (the 4 remediation fixes via PR #265 — EMB proxy/label, dual-ticker splits, pence-gate currency fix, the new Treasury source); durable state in tech_manual §13. But the audit's **value-level** checks ran against the stale 2026-05-13 snapshot (repo as-of 2026-05-12), so re-run the Tier-A value + Tier-B promotion sweeps against the current `market_data_comp.csv` on `main` if value-level confidence is wanted. Method + tiering in `manuals/factiq_audit_working_list.csv` (per-row tier A/B/C) + tech_manual Appendix A; the full `AUDIT_REPORT.md` write-up is archived in git PR #266. The two independent 2026-07-13/14 passes fully concurred and found **no** new scale/sign/÷100 anomaly across the priced universe, so this is confidence-refresh, not a known-defect chase. Effort: S (mechanical re-run against live data). *Note: FactIQ MCP must be connected in an interactive session — not runnable from CI.*

**A18. CSI 500 (`000905.SS`) re-source candidate (2026-07-12 audit follow-up).** ✅ **Resolved 2026-07-14 — wired as an ETF proxy.** The discovery paid off with a twist: Yahoo serves the **index symbol `000905.SS` for the live quote only** (a single point — confirmed against `000300.SS`'s full 484-point 2y history vs `000905.SS`'s 1 point via the Yahoo v8 chart API), which is exactly why the auto-writeback flagged it UNAVAILABLE — the fetcher needs *history*, not a spot quote. But the **China AMC CSI 500 ETF `510500.SS`** (SSE, CNY, the largest/most-liquid CSI 500 tracker, first-trade 2013-02-06) returns the full 484-point 2y history on the same Yahoo endpoint. Fix: the `CSI 500 Index` row in `data/index_library.csv` re-wired to the ETF-proxy convention (matching `ASHR`/`CNYB.L`) — `data_source=yfinance TR`, `ticker_yfinance_tr=510500.SS`, `proxy_flag=True`, `proxy_type=ETF`, `data_start=2013-02-06`, `validation_status=CONFIRMED` (index symbol `000905.SS` dropped from the row — it has no yfinance history and, kept in the PR slot, `collect_hist_assets` would fetch it as a second instrument and re-trigger the dead-list). Net +1 CONFIRMED / −1 UNAVAILABLE. Populates on the next daily run; the 14-day auto-writeback is the safety net if `510500.SS` ever fails. FactIQ re-confirmed the underlying index priced (8275.94 CNY close, SSE, 2026-07-14). Its sibling **CSI 1000 `000852.SS` stays genuinely unpriceable** — re-verified 1-point/quote-only on Yahoo, left UNAVAILABLE. Cross-ref §3.8.5 Class 2 and §3.1.8.

**A19. `_load_tier_map()` (+ `_load_override_map()`) encoding one-liner.** ✅ **Fixed 2026-07-14.** Both `_load_tier_map()` and `_load_override_map()` in `fetch_macro_economic.py` now `open(path, newline="", encoding="utf-8")`, so a library CSV containing a non-ASCII byte (`£`/`€`/Japanese label) no longer risks `UnicodeDecodeError` on a Windows cp1252 default locale (harmless on CI's UTF-8, was latent for local Windows runs). Pre-existing bug surfaced by the FactIQ audit; the 143-test offline gate stays green.

### §2.B Regime-AA free-sourceable backlog — 15 indicators (2026-06-15)

Distilled from `manuals/regime-aa-asks/regime-aa-sourcing-backlog.md`. Regime-AA carries 162 requested indicator slots: 98 covered, 24 partial, **15 missing-sourceable** (here), 25 missing-hard (proprietary, deferred). Closing all 15 would lift regime-AA fill rate from 60% to ~69%. Grouped by where the work lands:

**Cheap wins — existing source modules (~6 hours total):**

- **B1. UK M2 Money Supply (BoE M4).** ✅ **Done 2026-07-14.** Added BoE IADB `LPMVWYH` → `GBR_M2` to `data/macro_library_boe.csv` (tier 0; `sources/boe.py` unchanged). `LPMVWYH` is the BoE's "UK estimate of the EMU **M2** aggregate" (MFI sterling + all-FX M2 liabilities, amounts outstanding, NSA) — a direct concept match for "UK M2". Verified live through the adapter 2026-07-14: 477 obs 1986-09 → 2026-05, last ≈ £3.22 trillion. **Note:** this is a **level** (£mn), unlike the ECB/BoJ/NBS YoY siblings `EZ_M3`/`JPN_M2`/`CHN_M2` — the BoE publishes the outstanding stock, not a 12-month growth rate; the growth-rate IADB code proved elusive and a YoY view is trivially derivable downstream (each money-supply coverage column is z-scored independently anyway). Documented in the row notes.
- **B2. Eurozone Building Permits (Eurostat `sts_cobp_m`).** 🟡 **Wired 2026-07-14 — direct-API fetch validates on first CI run.** Added `EZ_BUILD_PERMITS` to `data/macro_library_eurostat.csv` via the **direct** `sources/eurostat.py` (NOT the originally-planned DB.nomics path — the DB.nomics Eurostat mirror is frozen since 2026-01-22, §2.A A12). Series: `sts_cobp_m?indic_bt=BPRM_SQM&cpa2_1=CPA_F41001_41002&s_adj=SCA&unit=I21&geo=EA21&freq=M` (m² of useful floor area, all buildings, seasonally+calendar adjusted, index 2021=100). Every component validated offline 2026-07-14: the dimension tuple yields a real series in the DB.nomics frozen mirror (n=249 2005-01 → 2025-09 = 85.2); `geo=EA21` confirmed the current euro-area aggregate (the A12 Bulgaria/EA20→EA21 lesson — EA21 carries full back-recomputed history). The only step that must run on CI is the live `ec.europa.eu` fetch (egress was blocked in the wiring session — direct curl 403, Bright Data token expired); the `sources/eurostat.py` adapter itself is proven (A12 sentiment trio in prod). Sister to `EZ_IND_PROD`.
- **B3. Eurozone PPI (Eurostat `sts_inpp_m`).** 🟡 **Wired 2026-07-14 — same status as B2.** Added `EZ_PPI` to `data/macro_library_eurostat.csv` via direct `sources/eurostat.py`: `sts_inpp_m?indic_bt=PRC_PRR&nace_r2=B-E36&s_adj=NSA&unit=I21&geo=EA21&freq=M` (total industry ex-construction PPI, index 2021=100, NSA — Eurostat has no US-style "final demand" PPI, so total-industry B-E36 is the EZ headline). Dimension tuple validated via the DB.nomics frozen mirror (n=311 2000-01 → 2025-11 = 120.9); `geo=EA21` confirmed. Live `ec.europa.eu` fetch validates on the first CI run (see B2 for the egress caveat). YoY (`unit=PCH_SM`) is derivable downstream.

**Medium effort — existing modules, harder discovery (~1 day each):**

- **B4. UK 5-10y Inflation Expectations (BoE/Ipsos Inflation Attitudes Survey)** — ✅ **Done 2026-07-15.** New `sources/boe_survey.py` module (the BoE surveys are XLSX workbooks, not IADB timeseries, so they can't ride `sources/boe.py`): downloads the stable `long-run.xlsx`, locates the Q.2c "five years' time" question row and the `Median` row beneath it in the wide dates-across-columns `LONG-RUN` sheet. Series-id shape `<stem>|<sheet>|<question>|<row_label>`; slots into the C2 factory (`fetch_series_as_pandas` → `_make_source_handlers`). New `data/macro_library_boe_survey.csv` (col `GBR_INFL_EXP_5Y`, tier 0), `SourceSpec("BoE Survey", …)`, explorer-allowlist entry, and `test_boe_survey_smoke.py` (in the daily smoke step). Verified live 2026-07-15: 70 quarterly obs 2009-02 → 2026-05 = **3.9%**. (Also fixed a latent gap found en route: `Eurostat` was missing from the explorer source allowlist.) `sources/boe_survey.py` now also carries B6 with a different stem/sheet.
- **B5. Eurozone SLOOS (ECB BLS)** — `sources/ecb.py` already fetches the ECB BLS dataflow. Need to pin the canonical net-% tightening enterprises 3-month forward key — combination of `BLS_ITEM=APP`, `WFNET=B6` (backward) or `F6` (forward), `BLS_AGGR=NET`. M effort, one CSV row.
- **B6. UK SLOOS (BoE Credit Conditions Survey)** — ✅ **Done 2026-07-16.** Extended `sources/boe_survey.py` to a two-survey dispatcher: the series-id's first `|` field selects the survey (`inflation-attitudes` = B4's static file + datetime-header parse; `credit-conditions` = B6). B6's annex URL embeds the quarter, so the module **walks back from the current calendar quarter** (`_ccs_candidate_urls`, latest-first) through `fetch_with_backoff`'s mirror mode + an xlsx-magic validator — a 404 on a not-yet-published quarter fast-rotates to the previous one. Its sheet uses a sparse-year + quarter header (rows 15/16), handled by `_parse_year_quarter_across`. New row `GBR_CREDIT_AVAIL` (Corporate annex, "availability of credit… corporate sector", *Past three months* net balance; tier 0), `test_boe_survey_smoke` gains a B6 case. Verified live 2026-07-16: 77 quarterly obs 2007-Q2 → 2026-Q2. (B4's series-id gained the `inflation-attitudes|` prefix in the same change.) UK-side companion to `EZ_CREDIT_STD_ENT` on the credit cycle.

**Higher effort — new source paths (~1-2 days each):**

- **B7. UK Building Permits (MHCLG dwelling starts)** — NOT on the ONS Zebedee timeseries API; published by Ministry of Housing, Communities & Local Government separately. Either add a new `sources/mhclg.py` module or wire to the ONS CMD-datasets API (different shape from the classic timeseries). L effort.
- **B8. UK Nonfarm Payrolls (ONS PAYE RTI)** — ✅ **Done 2026-07-15.** New `sources/ons_rti.py` module for ONS document-style XLSX datasets (PAYE RTI isn't a CDID timeseries): two-step fetch — beta `/v1/data?uri=…/current` JSON → `downloads[].file` → `https://www.ons.gov.uk/file?uri=…/<file>` XLSX — then a dates-DOWN parse (month-name strings in col A, value column by header). Series-id `<dataset_uri>|<sheet>|<value_header>`; slots into the C2 factory. Wired: `macro_library_ons_rti.csv` (col `GBR_PAYROLLS`, tier 0), `SourceSpec("ONS RTI", …)`, coordinator import+handler, explorer allowlist, `test_ons_rti_smoke.py` (daily smoke step). Verified live 2026-07-15: 143 monthly obs 2014-07 → 2026-05 = **30,253,517** payrolled employees. As a positive level it's covered by the A9.2 jump check (added "person" to the level-unit markers).
- **B9. Eurozone 5y TIPS Breakeven (ECB / Eurostat HICP-linked yields)** — ❌ **No free CI-safe source (2026-07-15 investigation).** Ruled out by direct probing of `data-api.ecb.europa.eu`: enumerated all 104 ECB dataflows — none inflation-linked/breakeven; `FM`'s `CL_INSTRUMENT_FM` has interest-rate/bond/FX/credit swaps but **no inflation-swap code**; `YC` is nominal-only (`G_N_A` = government bond, nominal; no real curve → no derivable breakeven). ECB discontinued public dissemination of market inflation-linked swap rates (Bloomberg/ICAP licensing). No other pipeline source family carries a free EA 5y breakeven. **Marked unavailable** — revisit only if a new free provider appears.

  **B6/B7/B8 status (2026-07-15 investigation; each needs a dedicated build):** **B6 (UK Credit Conditions Survey)** — `sources/boe_survey.py` can carry it, but the annex URL embeds year/quarter (`ccs-<YYYY>-q<N>-annex.xlsx`, sheet `Corporate annex`), so it needs a per-quarter URL builder or landing-page link-scrape (verified 2025-Q2: corporate credit availability past-3m +7.9). **B7 (UK building permits, MHCLG table 213)** — the gov.uk Content API (`/api/content/government/statistical-data-sets/live-tables-on-house-building`) lists the current ODS/XLSX attachment (rotating hash → read from JSON each run); needs a new gov.uk-Content-API module + ODS parse (`odfpy`), and `www.gov.uk` is proxy-blocked in-sandbox (CI-only). **B8 (UK PAYE payrolls, ONS RTI)** — two-step via the ONS beta `/v1/data` alias then XLSX download (`…/current/rtisajun2026.xlsx`, sheet `1. Payrolled employees (UK)`, verified 30,253,517 @ 2026-05); PAYE isn't a CDID timeseries, so `sources/ons.py` needs an XLSX-download path (same shape as the new `boe_survey.py`). All three are tractable next-session builds; exact URLs/sheets captured here.

**Pure-derivative — calculators only on series already in the pipeline:**

- **B10–B13. Taylor Rule Gap (UK / Eurozone / Japan / China)** — ✅ **Done 2026-07-14 (approach A).** Four calculators (`UK/EU/JP/CN_TAYLOR1`) in `compute_macro_market.py` + a shared `_taylor_gap` helper + 4 rows in `macro_indicator_library.csv` (107 → 111 indicators). Formula: `gap = policy_rate − (r* + π + 0.5·(π−target) + 0.5·activity_gap_z)`, positive = policy tighter than the rule (restrictive), negative = looser. **Because the pipeline has no output-gap or neutral-rate series**, two terms are constructed: the output gap is a *standardized activity z* — rolling-z of the region's growth nowcast (`UK/EU/JP_NOWCAST1`, reused by calling the nowcast calc directly) or of `CHN_IND_PROD` for CN (no nowcast exists); and r* is a hard-coded regional assumption (UK 0.5, EZ 0.0, JP 0.0, CN 1.5; targets 2%/2%/2%/3%, CN having no formal point target). This makes them Taylor-**style** stance gauges, not bp-accurate Taylor rates — documented in the calculator header + each indicator row. Inflation legs: `GBR_CPI_YOY` / `EA_HICP` / `JPN_CPI_YOY` / `CHN_CPI_YOY` (the last now reliable post-A1 IMF SDMX). Validated end-to-end against the live unified hist 2026-07-14: UK ≈ +0.09 (neutral), EU −1.54 / JP −1.11 (both accommodative), CN −0.60 (slightly loose) — all economically sensible; the gap term degrades to 0 if a nowcast is missing. Offline gate green (no orphan indicator ids). **B14 (US Taylor) stays deferred** — it needs a genuine potential-output series, a modelling call the others sidestep via the nowcast-z proxy.
- **B14. Taylor Rule Gap (US)** — BLOCKED: needs a potential-output / output-gap series the pipeline does not carry (CBO potential GDP, or an HP/one-sided filter on real GDP). That is a modelling choice, not a simple calculator. Deferred until a potential-output input is sourced. L effort + design call.
- **B15. Global Monetary Policy Tracker** — ✅ **Done 2026-07-15.** `_calc_GL_MONPOL1` in `compute_macro_market.py` + row in `macro_indicator_library.csv` (112 indicators). Net diffusion of 3-month (13-week) policy-rate changes across the six major central banks — Fed `FEDFUNDS`, ECB `EA_DEPOSIT_RATE`, BoE `GBR_BANK_RATE`, BoJ `JPN_POLICY_RATE`, PBoC `CHN_POLICY_RATE`, BoC `CAN_POLICY_RATE`: each contributes +1 hiking / −1 cutting / 0 on hold, raw = mean in [−1, +1]. Validated end-to-end on the live unified hist 2026-07-15: n=1384 2000-01 → 2026-07, last = +0.20 (mildly net-tightening), range [−1.00 (synchronised GFC/COVID easing), +0.83 (2022 tightening)] — economically sensible. Degrades gracefully as banks drop out.

**Suggested sequencing**: B1–B3 in one session (~6 hours, biggest coverage gain per line of code) → B10–B13 Taylor cluster in a second session (pure-calculator, four indicators at once) → ECB BLS (B5) when adding the EZ credit-conditions track → discovery sessions for B4, B6, B7, B8 as separate items.

### §2.C Architecture & repo-hygiene backlog — Fable review (2026-07-07; merged into this plan 2026-07-08)

> Source: the 2026-07-07 full-repo architecture review (formerly root
> `fable recommendations.md`, deleted 2026-07-08 after this merge — original text
> in git history at that path; evidence line numbers refer to the tree at commit
> `08e7026`).
> The review's **live-data items were already absorbed into §2.A** — its 0.1 = **A10**
> (EU_INFL1 freeze), 0.2 = **A11** (freshness-honesty pass), 0.3 = **A1** (China
> cluster) — so this section carries only the *structural* track: changes that stop
> the frozen-mirror bug class from reproducing, plus repo-hygiene options. Guiding
> rule: recommend a change only where the current structure demonstrably causes
> recurring cost. Constraints taken as fixed: free public APIs only; GitHub Actions
> runtime; Sheets output stays; mixed human/Claude maintenance (readability beats
> abstraction); minimal dependency footprint.

**C1. Enforce source precedence in the history merge — retire implicit last-writer-wins.** ✅ **Done 2026-07-09** (with C2 and A11 already in, the remaining gap was the *silence*): (a) declared primary per served column = the lowest-tier registered candidate (the `tier` column `_attach_tiers` already loads; `source_fallbacks.csv` t0 stays the wiring-audit refinement); (b) enforcement confirmed already present in `_select_winner` since PR #246 — primary wins at equal cadence unless it fails the 2×-cadence staleness gate (deliberately NOT re-tuned to `freshness_thresholds.csv` tolerances in this pass: swapping the gate basis would flip winners big-bang across columns; candidate follow-up if the audit shows the cadence gate too loose); (c) **every demotion now logs loudly** — `fetch_macro_economic._demotion_event` classifies *why* the primary lost (no data / stale Nd beyond gate / finer-cadence fallback / definition collision / freshness tiebreak) and `_log_demotion` prints the `[FALLBACK] col: declared primary src/id (tier 0) demoted — reason; serving src/id (tier N, freq, last date)` line on **both** the snapshot (`_dedupe_snapshot_rows`) and history (`build_hist_df`) paths; `data_audit.py` Section A scrapes `[FALLBACK]` from `pipeline.log` and reports each event verbatim — a frozen primary is a day-one reported audit issue. Bonus fix: `test_tier_merge.py` was bare pytest-style functions that `python -m unittest` collected as **0 tests** (the CI gate never ran the precedence policy tests) — converted to `unittest.TestCase` (17 tests incl. 8 new demotion cases; offline suite 92 → 109). *Original spec follows for context.* The tier system exists (`_attach_tiers`, `_select_winner` — used for **snapshot** dedup and the collect-then-select history merge shipped in PR #246), and `data/source_fallbacks.csv` documents T0→T3 chains, but the review found the enforcement still incomplete on the history-write path and — critically — **silent**: nothing *reports* when a declared primary is demoted. This is the root cause of the dominant recurring bug class (JP_INFL1 frozen at 8.49 → PR #249; EU_INFL1 frozen 6 months → A10; CN_INFL1 on 1–3-year-stale mirrors → A1; the 2026-06-18 wiring audit's 25 collisions / 11 cadence mismatches / 14 winner≠primary / 18 ambiguous-precedence). Actions: (a) a `declared_primary` notion per served column (the wiring audit already computes this — library column or generated `data/column_owners.csv`); (b) the history-merge winner function prefers the declared primary but **demotes it when it fails a freshness/cadence guard** (reuse `freshness_thresholds.csv` + the tested `_select_winner` cadence-rank logic); (c) **log every demotion loudly** (`[FALLBACK] col=EA_HICP primary=estat stale 190d → fell back to ecb`) and surface it in `data_audit.py` Section A — a frozen primary becomes a *reported event on day one*, not a silent six-month freeze. This is the substantive core of **A9** (value-plausibility bands are the second layer). The A11 freshness overrides feed this guard — land A11 first so it starts life with honest thresholds. Does not change the library-CSV registry rule, source modules, or output schemas. Effort: M.

**C2. One source registry instead of string-ladder dispatch.** ✅ **Done 2026-07-09.** `sources/__init__.py` now carries **`SOURCE_REGISTRY`** — one `SourceSpec(label, stem, module)` table tying together each source's display label, `macro_library_<stem>.csv` filename and module name — and all four previously-duplicated mappings derive from it (`fetch_macro_economic._FILE_SOURCE`, `data_audit.SOURCE_BY_LIBRARY`, `build_source_inventory.FILE_SOURCE` — which was carrying a live drift bug, `"french": "French"` vs the loader's actual `"KenFrench"` — and `library_sync.MACRO_LIBS`). The coordinator's two 27-branch ladders collapsed to **`_SOURCE_HANDLERS`** dict lookups; the ~42 template `_fetch_<src>_{snapshot,history}` wrappers collapsed into one `_make_source_handlers(module, delay, snapshot_kwargs, sub_field_default)` factory (the five structurally-special sources — FRED us/intl, the OECD/WB/IMF fan-outs, DB.nomics with the plausibility guard + ISM fallback — keep hand-written handlers, registered in the same table; ifo stays on its batch path). An unknown source label is now a **hard startup error** (`_validate_dispatch`, called before any network work in both builders) instead of a silent `[WARN] Unknown source` skip. Net −863 lines in `fetch_macro_economic.py` (1,825+ → 1,300). Verified: 9-module offline suite green incl. new `test_source_registry.py` (registry↔CSV↔dispatch coverage, in the ci.yml gate); ECB/BoC/IMF-SDMX factory handlers exercised live through the dispatch table (snapshot + history). Registering a new source = one SourceSpec + one `_SOURCE_HANDLERS` entry. *(Original item follows for the record.)* *(review 1.2.)* `fetch_macro_economic.py` dispatches via two ~27-branch `if src == "..."` ladders backed by **54** near-identical `_fetch_<src>_{snapshot,history}` wrappers; the source-label and cadence-rank mappings are duplicated again in `build_source_inventory.py` and `library_sync.py`; matching is on exact display strings, and a typo lands in a silent `[WARN] Unknown source` skip (the tell: `data_audit.py::_check_registry_drift` exists to police this). Fix: a single `SOURCES = {label: SourceSpec(module, has_history, tier_default)}` registry in `sources/__init__.py`, mirroring the proven `_ALL_CALCULATORS` pattern. Ladders collapse to lookups, the 54 wrappers to two generic functions, the sibling tools import the same table, and an unknown label becomes a startup error. Deletes ~400–500 boilerplate lines and removes the drift class outright. Verify: byte-identical output CSVs on a re-run. Effort: M.

**C3. Consolidate retry/backoff into `sources/base.fetch_with_backoff`.** ✅ **Done 2026-07-09** (batch 1 was 2026-07-08: `ecb`, `boc`, `ons`, `bundesbank`, `abs` + `imf_sdmx` born on the helper). **Batch 2 — the engine grew four backwards-compatible parameters instead of the modules keeping bespoke loops:** `url` accepts a mirror list (each attempt walks the mirrors; any per-mirror failure rotates; a whole failed pass backs off — the shape previously copy-pasted 6×), `accept="bytes"` (workbook/ZIP downloads), `json_body` (POST — the StatCan WDS shape), `context` (log lines read "… on <series> …", preserving the exact `[FRED] HTTP <code> on <series> — skipping` format data_audit Section A scrapes), `validate` (per-response content guard: HTML-form sniff, xlsx/ZIP magic bytes, e-Stat 200-with-error-body, StatCan envelope status), and `retry_errors` (retry connection errors instead of aborting — the ISTAT/Ken-French flaky-gateway posture). Pinned by `test_fetch_backoff.py` (16 mock-HTTP tests; ci.yml gate). **Converted (11):** `fred` (context), `boj` (HTML sniff), `estat` (RESULT-block guard), `statcan` (POST), `istat` (retry_errors; the 2026-06-12 tuned budget unchanged), `boe`/`lbma` (mirror + sniff), `atlanta_fed`/`ny_fed`/`shiller` (mirror + bytes + file magic), `french` (bytes + retry_errors; per-process ZIP cache stays local). Live-verified in-session where the sandbox proxy allows: StatCan, BoE, LBMA, ISTAT, BoJ, Ken French, and Shiller — whose primary host is proxy-blocked here, so the fetch **demonstrated the mirror rotation in anger** (fell through to Yale, validated BIFF magic). **Deliberately exempt (7, each for a named reason):** `dbnomics` (Pattern-10 circuit breaker distinguishes status codes the helper flattens), `bls` (retries on the app-level `REQUEST_NOT_PROCESSED` throttle, not HTTP status), `insee`/`bdf` (key-gated 401/403 diagnostics — BdF deliberately captures the response body to tell invalid-key from not-visible from rate-limit), `alpha_vantage` (rate-limit "Note"/"Information" JSON body inspection), `ifo` (3-strategy anti-bot escalation incl. Bright Data), `nasdaq_data_link` (wraps the NDL SDK, not requests). `fetch_data.py`/`fetch_hist.py` have no hand-rolled HTTP retry loops left (yfinance SDK calls aside).

**C4. Kill the import-side-effect pipeline in `fetch_data.py`.** ✅ **Done 2026-07-08.** The four downstream blocks (`run_comp_hist()` / `run_phase_macro_economic()` / `run_phase_e()` / SEC EDGAR) moved verbatim — per-phase `try/except` isolation intact — into `run_downstream_phases()`, called from the single `if __name__ == "__main__":` guard after `main()`. `import fetch_data` is now side-effect-free (~0.5s, verified); the workflow's `python fetch_data.py` invocation is unchanged.

**C5. Gate merges with the offline test suite in CI.** ✅ **Done 2026-07-08.** `.github/workflows/ci.yml` runs the offline modules (`test_tier_merge`, `test_macro_hist_merge`, `test_library_utils_hist`, `test_dbnomics_plausibility`, `test_atlanta_fed_parse`, `test_estat_parse`, `test_ism_prnewswire_parse`, `test_bounded_fill`, `test_source_registry`, `test_library_sync`, `test_data_audit_critical`, `test_fetch_backoff` — 12 modules, 143 tests, ~6.8s; `test_bounded_fill` + `test_source_registry` joined 2026-07-08/09 alongside A14 and C2, `test_library_sync` + `test_data_audit_critical` + `test_fetch_backoff` joined 2026-07-09 alongside C6/C8/C3 batch 2) on every `pull_request` and push to `main`; smoke tests stay non-blocking in the daily run. The gate immediately earned its keep: `test_macro_hist_merge::test_tie_prefers_primary_over_aggregator` had been silently broken since PR #246 changed the tie-break from PRIMARY_SOURCES rank to declared tier (fixture now declares tiers; fixed in the same 2026-07-08 PR). **Operator follow-up: mark the `offline-tests` check as *required* in the GitHub branch-protection settings** — a workflow alone doesn't block merges.

**C6. Deduplicate `library_sync.py`.** ✅ **Done 2026-07-09.** A prior session had already extracted the generic `_run_pair` runner; this pass finished the job: the three per-pair `present`/`idxs`/`archive` helper trios collapsed into `SYNC_SPECS` (a frozen `SyncSpec` per hist↔library pair: name, hist path, expected-ids callable, id-start column) + one generic `sync(spec, confirm)` with shared `_present_ids`/`_idxs_for_id`/`_archive_orphan`; only the expected-ids derivation stays per-pair. `data_audit._check_registry_drift` now iterates `SYNC_SPECS` too (its own copy of the triple list removed), and a fourth hist pair (§5 multifreq) becomes one spec entry. **The predicted "fix applied to two of three" bug was real and got fixed by the merge:** the comp archiver learned header-sniffing on 2026-07-08 but `_macro_econ_archive` kept a hardcoded `rows[15:]`, so macro archives written after the 14→15 metadata-row growth included the "Date" header row as data — the generic archiver sniffs the data-header row (same rule as `sniff_hist_prefix_rows`) for every pair. Pinned by the new `test_library_sync.py` (7 offline tests on synthetic files in all three layouts, incl. the header-generation case; added to the ci.yml gate). *Original spec follows.* Three copy-pasted trios (`_comp_*` 76–108, `_macro_econ_*` 175–249, `_macro_mkt_*` 277–311) implement the same expected/present/orphan/archive shape per hist↔library pair. One `SyncSpec` (hist path, library loader, key column, prefix rows) + one generic `sync(spec, confirm)`; a fourth hist pair (multifreq) becomes a spec entry. This tool mutates committed history files — identical logic in three copies is where a fix applied to two of three creates a subtle data bug. Fold in the same disease in the archived-column handling. Effort: S.

**C7. Split `compute_macro_market.py` into a `calculators/` package — opportunistic only.** *(review 1.7.)* 2,550 lines / 107 `_calc_*`; the dispatch (`_ALL_CALCULATORS`) is the best pattern in the repo — the only issue is merge-conflict surface and scroll cost on the most-edited file. Mechanical move into per-region modules (`us.py`, `eu.py`, `asia.py`, `inflation.py`, `nowcast.py`) + `calculators/common.py` for shared helpers; no behaviour change; verify byte-identical `macro_market.csv`. Do it when the file next causes a real conflict or the multifreq rewrite touches it anyway. Effort: M.

**C8. One narrow hard-fail class in the audit.** ✅ **Done 2026-07-09** as `data_audit.py` **Section F — CRITICAL gate**: (a) any `SHEETS_PROTECTED_TABS` output CSV with zero data rows or zero populated value cells (value region = "Last Price" onward; identity columns would mask the regression); (b) any of the 6 hist CSVs (3 live + 3 sisters) losing >10% of rows or columns vs the committed HEAD version (`git show`; check silently skips when HEAD/git is unavailable — the gate must never false-fire). On a finding: audit exits 2 (its workflow step goes red), writes `data_audit_critical.flag`, and the `update_data.yml` commit step commits **only** `pipeline.log` + the audit reports then exits 1 — the bad data artefacts never reach main; the Issue comment leads with a 🛑 CRITICAL banner. Sections A–E stay a pure warning channel (exit 0). Spec item (c) — composite raw unchanged >k months — deliberately not implemented: C1's `[FALLBACK]` demotion reporting + Section C EXPIRED already cover that signature loudly, and multi-month freezes are sometimes upstream-legitimate (CHN_PPI). Tested by `test_data_audit_critical.py` (11 offline tests incl. a no-false-trigger check against the real repo state; in the ci.yml gate). *Original spec follows.* `data_audit.py` always exits 0 and smoke tests are non-blocking — mostly the right philosophy, but the net effect is that **nothing gates the daily commit except a crash** (the Atlanta-Fed-24%-nowcast class shipped; so would a protected column going all-NaN or a hist CSV halving). Keep the audit a warning channel but define a tiny CRITICAL class that exits nonzero and skips the *data* commit (still upload `pipeline.log`): (a) any `SHEETS_PROTECTED_TABS` output empty/all-NaN; (b) any hist CSV losing >N% of rows/columns vs the committed version; and — once C1 lands — (c) a live composite whose raw hasn't changed for >k months (the EU_INFL1 signature; C1's fallback logging may make this redundant). Deliberately hard to trigger falsely. Effort: S.

**C9. Stop committing the explorer artefacts; deploy to GitHub Pages.** ✅ **Done 2026-07-14.** `docs/indicator_explorer.html` (~14 MB) + `docs/indicator_explorer_mkt.js` (~16 MB) removed from git tracking (`git rm --cached` + `.gitignore`) and published to GitHub Pages instead. `update_data.yml`: dropped the two `git add -f docs/indicator_explorer*` lines; added a `pages_gate` step (publishes only on a healthy run — explorer freshly built, no CRITICAL flag) exposed as a job output; added Stage + `actions/upload-pages-artifact@v3` steps (co-located files + a root `index.html` redirect); added a separate `deploy-pages` job (`needs: update-data`, gated on the output, scoped `pages`/`id-token` permissions, `github-pages` environment, `actions/deploy-pages@v4`). Removes ~30 MB/day of churn. **Two operational follow-ups:** (1) one-time repo setting — **Settings → Pages → Source = "GitHub Actions"** (only the owner can do this; the deploy job no-ops until then); (2) the PR merge will show a trivial delete/modify conflict on the two explorer files (main keeps regenerating them) — resolve = keep deleted (`git rm`). Optional later: `git filter-repo` to reclaim the ~100 MiB already in history (destructive; not done). Validates on the first Actions run.

**C10. Move `pipeline.log` / `data_audit.txt` out of git history.** ✅ **Done 2026-07-14 (conservative variant).** `pipeline.log` (rewritten whole every run → permanent churn) removed from git tracking (`git rm --cached` + `.gitignore`) and uploaded as a **90-day workflow artifact** (`actions/upload-artifact@v4`, `if: always()` so a crashed run still yields the log). `data_audit.txt` is **kept in git** (small, meaningful diffs — the endorsed >90-day-forensics carve-out) and also included in the artifact for convenience; `audit_comment.md` still commits + posts to the daily Issue. Safe because `data_audit.py` Section A scrapes the **local** `pipeline.log` written during the run, never a committed cross-run copy. Merge note: like C9, `pipeline.log` will show a delete/modify conflict at merge (resolve = keep deleted). Effort: S.

**C11. Reduce hist-CSV churn — fix the writes first, then consider format.** *(review 2.3.)* The 2026-07-07 data commit (`ba51d46`) diffed **8,330 lines in `macro_economic_hist.csv` alone** (~8.2k insertions ≈ deletions): the hist files are effectively rewritten daily, which bloats history and makes "what changed today?" unanswerable from the diff. In order: (1) **make hist writes append-stable** — canonical `float_format`, stable column order, never re-emitting unchanged historical rows with re-derived values, so legitimate source revisions become *visible* diffs (do this regardless — it directly serves freshness/credibility auditing); (2) optional: move only the append-only `_hist_x` sister archives to compressed Parquet (`pyarrow`, one dependency; `_hist` heads stay CSV); (3) alternative if zero format change wanted: a machine-commit `data` branch squashed monthly. Resolve the §3.6a `keep="first"` self-heal question before (2) changes the archive format. Effort: (1) M, (2) S, (3) M.

**C12. Simple-pipeline decision path — make "is `trigger.py` alive?" falsifiable.** *(review 2.4; unblocks §3.2 Step 1.)* §3.2 has been blocked indefinitely on an unfalsifiable consumer check. Do one of: check the service account's Sheets API usage in the Google Cloud console; check whether the 06:15 London Windows scheduled task still exists/fires; or run a **canary** (timestamp cell in a non-protected corner of the tab echoed somewhere observable, or rename the tab for one day). Then either execute §3.2's retirement plan or record confirmed-live with a named consumer and re-check date. An output with an *unknown* consumer can't be changed safely and can't be deleted. Effort of deciding: S.

**C13. Staged CI workflow — optional, only with C9.** *(review 2.5.)* Split the single ~120-min job into `fetch` → `build-explorer` → `audit` jobs passing `data/` as an artifact with one final commit/deploy step. Real benefits (failure attribution, stage re-runs, no partial-state commits) but meaningful workflow complexity for a pipeline that rarely fails and is phase-isolated. Only worth doing if C9 is adopted (deploy step gets a natural home) or when the §5 multifreq migration forces workflow surgery anyway.

**Reviewed and endorsed as-is — do NOT "fix" these** *(review Part 3/4; recorded so future sessions don't churn deliberate decisions)*: the §0 data-layer registry rule (the repo's best architectural decision — everything above strengthens it); the `_ALL_CALCULATORS` registry (the model C2 copies); phase isolation (Pattern 1 — C4 relocates it without changing it); the tier-aware snapshot merge (`_select_winner` + `test_tier_merge.py` — the tested foundation C1 extends); the `_hist`/`_hist_x` sister-archive concept (Pattern 9; §3.6a self-heal question stands); stdlib `unittest` over pytest; `print` + `tee pipeline.log` logging (worth only a `[WARN]`/`[ERROR]`/`[FALLBACK]` prefix convention, which C1's demotion logging formalises); Sheets protected-tab safety + the audit-as-warning-channel philosophy (C8 is the only exception); small CSVs as committed config/state (C11 targets only the multi-MB rewritten hist files); the Phase H audit/writeback loop; the manuals system (2026-07-09 `refresh-manuals` run fixed the drifts that lived in `technical_manual.md`/`forward_plan.md` themselves: the 107-vs-108 composite-indicator count after the `US_PMI2` removal, the 1950-vs-1990 comp-pipeline history start, and the 66-vs-70 simple-pipeline instrument count — the latter also updated from "hardcoded list" to "library-driven via `simple_dash`" per tech_manual §4. Still open, in files this run doesn't touch: indicator_manual "68" vs 108 (now 107); stale multifreq copy in `multifreq_plan.md` vs §5).

**§2.C sequencing (unified with §2.A):** operational first — **A10 + A11 ✅ done 2026-07-08** (PR #255, plus the C4/C5 structural openers), **A1 ✅** (CPI via the new IMF SDMX module; PPI accepted gap) and **A14 ✅** (bounded fill, PR #256) — next the bounded-fill follow-ups **A15 → A16** (each a small self-contained PR, start after the first post-merge daily run), plus **A12** (Eurostat mirror) and **A13** (e-Stat CPI slice-pinning) when an environment with `ec.europa.eu` egress / `ESTAT_APP_ID` is available — then the remaining structural track **C3 ✅ (batch 1 2026-07-08; batch 2 + engine extensions 2026-07-09; 7 documented exemptions) → C2 ✅ (PR #260) → C1 ✅ (2026-07-09: demotion logging + Section A surfacing + the tier-merge tests actually running under unittest)** → (C9/C10 anytime) → §5 multifreq. Core structural track is done, and **C6 ✅ + C8 ✅ (2026-07-09)** followed in the same session; the only §2.C items left are C9/C10 repo weight and the opportunistic-only C7/C13. Multifreq de-risking: C2 and C1 are effective prerequisites (one registry beats two 27-branch ladders for a migration touching every source path; precedence enforcement defines the correctness contract a multi-frequency merge must preserve), and C5's test gate is what lets a migration that size proceed in reviewable steps.

### Repo file-hygiene — doc-deletion sweep (2026-07-14, PR #269 + #270)

**Done this pass.** All 3 Section-A High-confidence deletes are now executed — retired seven superseded audit/handover files across the two PRs, each with its inbound references rewired to a surviving home (grep-verified zero dangling refs; `py_compile` + `test_tier_merge.py` green; no `data/*.csv` deleted — note-field edits only):
- `manuals/2026-06-15-source-tier-audit.md` → tier model codified in `technical_manual.md` §9.4 (fixed the live `compute_macro_market.py` `_calc_UK_INFL1` docstring comment — the filename had wrapped across two lines, so it survived the original single-line grep — plus forward_plan 384/411/541).
- `manuals/2026-07-07-eu-freeze-freshness-china-handover.md` → §2.A A10/A11/A1 (dropped the A10 discovery-notes parenthetical).
- `manuals/2026-06-17-m2-units-trio-recommendation.md` → §2.B + chronology (PR #221); repointed the provenance note in the ecb/boj/dbnomics library CSVs + the regenerated snapshot.
- `manuals/2026-06-15-label-vs-data-audit.md` → closed via `technical_manual.md` §12 / §2.A (PR #225/#250).
- `AUDIT_HANDOVER_2026-06-15.md` → the audit it handed off is closed; it had no inbound references. (The original work-order wrongly assumed PR #267 had already deleted it.)
- `manuals/2026-06-15-codespace-secrets-checklist.md` (PR #270) → one-time Codespace secret-mirroring checklist; every secret is already in `technical_manual.md` §12, matching the workflow `env:` block. Only inbound ref was `label-vs-data-audit.md`, itself already deleted — no live pointer remained.
- `manuals/2026-06-18-cpi-split-codespace-spec.md` (PR #270) → one-shot CPI-definition-split work-order, executed (PR #249); resolution record lives in `2026-06-18-source-wiring-audit-proposal.md` §Resolution. 5 data-provenance refs repointed (`macro_library_worldbank.csv`, `macro_indicator_library.csv` JP_INFL1, generated `macro_economic.csv` ×3, the embedded copy in `docs/indicator_explorer.html`); zero dangling references remain.

The full analytical register + per-item resolution log lives in `file_del_candidates.md`.

**Remaining doc-hygiene work (deferred by owner decision — pick up when unblocked):**
- **B4 + C12 — regime-AA v2 handoff memos** (`manuals/2026-06-10-regime-aa-v2-pipeline-handoff.md` + `…-corrections.md`). Coupled (the corrections memo cross-references the handoff); content already reconciled into §3.12–§3.17. **Blocker:** the corrections memo is the source artefact for an outbound "file back to regime-aa" inverse-direction proposal that can't be verified from this repo — confirm it was delivered, then delete both together. **On deletion**, rewire three surviving pointers: forward_plan 550 + 1183, and the extra live pointer at `manuals/2026-06-10-alpha-vantage-evaluation.md` §7.2 (repoint to §3.12–§3.17).
- **Group E — generated `regime-aa-asks/` `.md` layer** (`regime-aa-fill-report.md`, `regime-aa-sourcing-backlog.md`, `requests/*.md` ×15, `regime-aa-indicator-coverage.md`). Owner elected to keep committing them for now. They are emitted by committed scripts (`build_fill_report.py`, `build_sourcing_backlog.py`, `scripts/phase_0_coverage_check.py --write-memos`, `build_indicator_coverage_map.py`) from `manuals/regime-aa-asks/regime-aa-indicator-coverage.csv`, so deleting a `.md` is cosmetic — the next generator run recreates it. **Durable removal = one decision:** stop committing the layer → delete the four `.md` **and** add them to `.gitignore` (or drop the `.md`-emit step in the generators), keeping the `.csv` + scripts as the source of truth; then rewire forward_plan 466 + 542 ("distilled from") to cite the coverage CSV + build script. **Never delete `regime-aa-indicator-coverage.csv`** (live machine input to the exit-code-gating `scripts/phase_0_coverage_check.py`); `regime-aa-indicator-req.md` (the hand-written requirements spec) also stays.
- **Group D — non-`.md` orphans.** `archive/generate_review_excel.py` (High-confidence orphan — pre-2026-04-08 indicator ids, no longer runnable) + its two consumers `archive/indicator_groups_review.xlsx` / `…_UPDATED.xlsx`; plus the two `manuals/*.docx` (`indicator_manual.docx`, `macro_market_cheat_sheet.docx`) which are regenerable via `manuals/build_docx.py` / `md_to_docx.py` — keep only if distributed externally, and note that dropping them makes the two builder scripts candidates too. On deleting the archive script, reword its three mentions in `technical_manual.md` (the file-tree entry + the two dev-deps notes). Owner elected no Group D deletions this pass.
- **Register retirement.** Once the above resolve, `file_del_candidates.md` (itself a completed audit artefact) becomes a deletion candidate.

**Guardrails (unchanged):** never delete `data/*.csv` (note-field edits only), `sources/*.py`, `test_*.py`, or `manuals/regime-aa-asks/regime-aa-indicator-coverage.csv`. Verify-before-delete / verify-after-delete with a `grep -rn "<basename>" --include=*.md --include=*.py --include=*.yml .` on both sides of every removal.

### Candidate next tracks (broader)

- **§2.A Broken-source & freshness backlog (current top of queue)** — concrete remediation list distilled from the 2026-06-15 17:48 UTC audit + the source-tier audit (findings codified in the tier model — `technical_manual.md` §9.4). Detailed above.
- **§2.B Regime-AA free-sourceable backlog** — the 15 indicators with confirmed free sources but not yet wired, distilled from `manuals/regime-aa-asks/regime-aa-sourcing-backlog.md`. Detailed above.
- **§2.C Architecture & repo-hygiene backlog** — the structural track from the 2026-07-07 Fable review (precedence enforcement, source registry, CI test gate, repo-weight reduction). Detailed above; sequenced jointly with §2.A in the §2.C sequencing note.
- **§3.1 Macro & Market Coverage Expansion** — unified track. Stages A / B / D / F shipped 2026-04-30; **§3.1.3 inflation composites done 2026-05-28**. **Outstanding: Stage C** (regional roll-up — UK growth via ONS, JP growth via e-Stat extension), **Stage E** (survey deep-dive against `G20_PMI_Master_Table.docx`), GDP Now wiring (§3.1.4), the §3.1.3 follow-up (core inflation series for UK/EA/JP/CN), the §3.9 follow-up (multi-commodity long-run prices), and **Stage G** closeout. Note: long-run market and macro data sources catalogued in `../longrun_assetclass_data_sources.md` (OECD MEI feed via FRED, Shiller, Ken French, IMF Primary Commodity Prices, BoE Millennium, JST) need wiring into the data pipeline as part of this expansion — driven by master plan Phase 0; data-side work plan tracked here, now detailed and status-reconciled as §3.12 (OECD MEI) and §3.13 (long-run layer) per the regime-AA v2 handoff.
- **§3.2 Retire the Simple Pipeline** — deprecation track.
- **§3.3 PE Ratio Integration** — small contained feature add.
- **§3.4 Market Index Expansion** — broadens market coverage; CSV-only additions to `index_library.csv`.
- **§3.6 Incremental Fetch Mode** — performance work for `fetch_hist.py`.
- **§3.8 Weekly Retirement Review Workflow** — closes the auto-remediation gap left by the daily audit.
- **Regime-AA v2 asks (§3.12–§3.17)** — cross-repo handoff (`manuals/2026-06-10-regime-aa-v2-pipeline-handoff.md`), status-reconciled. **CRITICAL:** §3.12 OECD MEI ingestion (✅ rows in 2026-06-10; continuity verification pending first daily run) and §3.14 monthly z-score sampling (✅ shipped 2026-06-10) — both unblock regime-AA Phase 0 / Phase 2. **HIGH:** §3.13 long-run source modules (✅ Shiller / Ken French / JST + IMF PCPS aggregate all shipped 2026-06-10; BoE Millennium optional, deferred). §3.15 / §3.16 still blocked / consumer-side. §3.17 capability ✅, writer deferred. See §3.12–§3.17 for the per-ask status.

- **FactIQ architecture-teardown ideas (optional / strategic — from the 2026-07-12 audit; full teardown in `FACTIQ_AUDIT_PLAN.md` §8.3, archived in git PR #266).** Design patterns learned from FactIQ's warehouse while it is free — not committed work (the `§8.3.x` tags below index the archived plan):
  - Port the per-source `macro_library_*.csv` + `*_hist.csv` into a single **3-table DuckDB store** (`series` / `data_points` / `dimensions`) — the audit's internal checks collapse to 5-line queries (§8.3.1). Overlaps the §5 multifreq native-frequency-storage direction.
  - **Cache-first discipline** for `fetch_data.py` / `fetch_macro_economic.py` pulls — raw response to disk before transform, so every future audit is diffable (§8.3.2). Overlaps §2.C C11.
  - A **ChartSpec-style spec layer** between pipeline and outputs before adding any new viz surface (§8.3.6).
  - Write the audit up as a repeatable **`report-patterns/data-audit.md`** playbook so it re-runs with no rediscovery (§8.3.3).

> **Note: §3.5 and §3.7 are MOVED.** Regime-based indicator labelling, ML-driven regime identification, and the regime-driven back-test / portfolio optimiser have been moved out of this document into `../regime_AA_master_plan.docx`. The stub sections at §3.5 and §3.7 below record the move and direct readers to the relevant master-plan sections.

---

## 3. New Feature Development

### 3.1 Macro & Market Coverage Expansion

**Priority:** High — provides the macro + market data foundation for the regime work owned by `../regime_AA_master_plan.docx`. Most architecture is now shipped (Stages A / B / D / F per `manuals/technical_manual.md`); §3.1 below tracks only what's outstanding.

**Status:** Active. Stages A (history-preservation safeguard), B (T1 fallback chains for 4 of 9 forcing-function rows), D (4 T2 source modules — BoE / ECB / BoJ / e-Stat), F (community-ticker review + 14 ETFs added) shipped. **Outstanding: Stages C / E / G + targeted growth/inflation expansion + GDP Now wiring.**

**Architecture context** (durable — lives in `manuals/technical_manual.md`):
- **History-preservation safeguard** — `*_hist_x.csv` sister files; `library_utils.write_hist_with_archive()` / `load_hist_with_archive()` helpers — see tech_manual §11 Pattern 9.
- **Fallback-chain registry** — `data/source_fallbacks.csv` records the T0 / T1 / T2 / T3 chain per indicator; as of 2026-07-03 (PR #246) an explicit tier-aware, cadence-first, staleness-fallback runtime walker (`_select_winner` in `fetch_macro_economic.py`) enforces the chain, replacing the old implicit last-writer-wins merge — see tech_manual §7 / §9.4.
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
| **C — Reference-baseline close-out (regional roll-up)** | **Partial — In Progress** | Close the 118 `Missing` rows in `reference_indicators.csv` where a free path exists. **`sources/ons.py` built 2026-05-28** — 9 ONS series wired (GBR_CPI_YOY, GBR_CPIH_YOY, GBR_GDP_REAL, GBR_UNEMPLOYMENT, GBR_EMP_RATE, GBR_AWE_REGPAY_YOY, **GBR_IND_PROD (K222), GBR_SERV_PROD (S2KU), GBR_RETAIL_VOL (J5EK) shipped 2026-06-10**). **GBR_CLAIMANT_COUNT (BCJD) + GBR_PPI_OUTPUT (GD6Y) shipped 2026-06-15 (PR #205)**. UK GDP, labour, monthly output indices, and claimant count are now live. Still outstanding: UK BICS Business Insights and Conditions Survey (not exposed as standard `cdid`/dataset timeseries — needs follow-up). JP growth column lifted via the e-Stat rows: as of 2026-07-07 (PR #250) `JPN_IND_PROD` / `JPN_MACH_ORDERS` / `JPN_HH_EXP` / `JPN_EWS_DI` are live with pinned/verified slices; `JPN_RETAIL_SALES` and `JPN_TERT_IND` are accepted file-only gaps (Excel-only, no `getStatsData` table). China growth mostly proprietary; accept. |
| D — On-demand T2 modules | ✅ Shipped 2026-04-30 | — (4 modules built: BoE / ECB / BoJ / e-Stat) |
| **E — Survey deep-dive** | **Outstanding** | Canonical demand-side guide is `manuals/G20_PMI_Master_Table.docx` — 33 G20 surveys with tier / publisher / frequency / free URL / API access / PMI-similarity assessment. Strategy: prioritise ◆ **Strong**-tier surveys with free API access not yet wired (BoK BSI via ECOS, IMEF via Banxico SIE, INEGI EMOE, TCMB EVDS, Argentina INDEC Open Data API, Indonesia BI API). ◇ Proxy-tier surveys covered by existing OECD BCI / Eurostat ESI / FRED routes where free; new T2 module only when the canonical source is meaningfully fresher. ○ Limited-tier surveys (Saudi headline-only, Russia post-2022) accepted as gaps. JP Tankan sub-DIs already accessible — just add rows to `macro_library_boj.csv`. **JP Tankan spread composites JP_TANKAN_SPREAD1 / JP_TANKAN_SVC1 / JP_TANKAN_FWD1 shipped 2026-06-11** on the 5 BoJ Tankan sub-DI rows wired the same day (Large-vs-Small Mfg export-vs-domestic cycle, Non-Mfg-vs-Mfg services-vs-goods rotation, Forecast-vs-Actual quarter-ahead turning-point detector). UK CBI / GfK / RICS remain proprietary — accept. CN NBS sub-data proprietary — accept. Scraper infrastructure (`sources/scraper_base.py`) only as last resort. |
| F — Community ticker catalogues | ✅ Shipped 2026-04-30 | — (14 ETFs added; report at `manuals/community_datasets_review.md`) |
| **G — Closeout** | **Outstanding** | Refresh §1 Known Data Gaps, refresh `data/source_fallbacks.csv` per-indicator mapping, refresh `manuals/macro_market_indicators_coverage.xlsx`, archive working notes. Final commit when Stage C and E close. |

#### 3.1.3 Growth + Inflation focus for regime prep

The regime work (now owned by `../regime_AA_master_plan.docx`) uses a per-region Growth × Inflation 4-quadrant frame. The regime classifier needs per-region clean reads on each axis, and the master plan's Phase 0 data-availability test will identify which regions can be supported. Current state has well-known gaps on both axes:

**Growth axis** — well-covered for US / EZ; thin for UK / JP / CN. Note: the canonical demand-side guide for *survey-based* growth indicators (PMI, business confidence, sentiment surveys) is `manuals/G20_PMI_Master_Table.docx` — see Stage E above for the prioritisation strategy.

| Region | Action | Specific targets |
|---|---|---|
| US | ✅ no action — 6/6 captured | — |
| **UK** | **✅ `sources/ons.py` wired 2026-05-28** — substantially done. GBR_GDP_REAL, GBR_UNEMPLOYMENT, GBR_EMP_RATE, GBR_AWE_REGPAY_YOY, GBR_IND_PROD (K222), GBR_SERV_PROD (S2KU), GBR_RETAIL_VOL (J5EK) live (2026-06-10). GBR_CLAIMANT_COUNT (BCJD) + GBR_PPI_OUTPUT live (2026-06-15 PR #205). Still outstanding: BICS business survey (not exposed as standard cdid/dataset timeseries). | Add BICS row to `data/macro_library_ons.csv` once a Zebedee-compatible endpoint is found. |
| **JP** | **✅ shipped via e-Stat extension 2026-06-10** — 5 rows added to `data/macro_library_estat.csv` (JPN_TERT_IND, JPN_MACH_ORDERS, JPN_RETAIL_SALES, JPN_HH_EXP, JPN_EWS_DI). All PROVISIONAL pending live verification once `ESTAT_APP_ID` is available; cdCatNN filters likely needed on first fetch. Brings JP from 3/7 → ~6/7+ on the Growth column. | — |
| EZ | ✅ no action — 6/6 captured | — |
| CN | accept gaps | NBS retail / FAI / electricity / industrial profits / property — all flagged PROPRIETARY in `reference_indicators.csv` (no free foreign API). Current 3/9 is the practical ceiling. |
| Global | optional: CPB World Trade Monitor + IP | New T3 fetcher `sources/cpb.py` (free CSV download, monthly); 2 rows. Low priority. |

**Inflation axis** — surface coverage was thin (only `US_R4` and `UK_R2` tagged `Inflation`). **Shipped 2026-05-28 via #152**: 5 per-region inflation composites + a separate inflation-expectations composite. ✅

| Indicator | Composition (all inputs already in `macro_economic_hist`) | Headline / Core | Cycle |
|---|---|---|---|
| `US_INFL1` | mean of US headline CPI YoY (`USA_CPI`) + Core PCE YoY (`PCEPILFE`) + 5y5y forward breakeven (`T5YIFR`) | **Headline + Core** blend | L |
| `UK_INFL1` | mean of UK headline CPI YoY + core CPI YoY ex-energy/food/alc/tob (`GBR_CPI_YOY` + `GBR_CORE_CPI_YOY`) | **Headline + Core** blend | L |
| `EU_INFL1` | mean of EA headline HICP YoY + core HICP YoY (`EA_HICP` + `EA_HICP_CORE_YOY`) | Headline + Core | L |
| `JP_INFL1` | mean of JP headline CPI YoY + core CPI YoY ex food&energy (`JPN_CPI_YOY` + `JPN_CORE_CPI_YOY`) | Headline + Core | L |
| `CN_INFL1` | mean of China headline CPI YoY + PPI YoY (`CHN_CPI` + `CHN_PPI`) | Headline + PPI (core still gap) | L |
| `US_INFEXP1` | z-composite of `T5YIE` + `T10YIE` + `T5YIFR` + `MICH` | Expectations (separate axis) | L (naturally leading) |

Each row's `name` field in `macro_indicator_library.csv` explicitly states *headline / core / blend* so the regime-AA consumer can't confuse a headline-only gauge with the US headline+core blend (#155).

**§3.1.3 follow-up — source core inflation series for UK / EA / JP / CN.** Only the US blend includes core (via FRED `PCEPILFE`); the other four `*_INFL1` indicators are headline-only because we don't yet have core series in the hist for those regions. Target series to wire into `macro_library_*.csv`:

| Region | Target series | Likely source | Notes |
|---|---|---|---|
| UK | ✅ shipped 2026-06-10 — ONS CPI excluding energy, food, alcohol & tobacco (CDID `DKO8`, monthly back to 1989; the original note in this table said `D7G7` but that's headline, confirmed via ONS Zebedee + search). Wired as `GBR_CORE_CPI_YOY` and blended into `UK_INFL1` alongside `GBR_CPI`. | ONS Zebedee /data endpoint via existing `sources/ons.py` | The BoE-watched UK core measure |
| EA | ✅ shipped 2026-06-10 — Eurostat HICP, overall index excluding energy/food/alcohol/tobacco (`prc_hicp_manr/M.RCH_A.TOT_X_NRG_FOOD.EA20`, 289 obs back to 2001-12; the title is broader than the row originally noted — Eurostat's `TOT_X_NRG_FOOD` is the ECB core HICP). Wired as `EA_HICP_CORE_YOY` and blended into `EU_INFL1` alongside `EA_HICP`. | DB.nomics Eurostat via existing `sources/dbnomics.py` | Standard ECB "core" definition |
| JP | ✅ shipped 2026-06-10 — OECD COICOP2018 national CPI ex-food-and-energy YoY (`OECD/DSD_PRICES_COICOP2018@DF_PRICES_C2018_N_TXCP01_NRG/JPN.M.N.CPI.PA._TXCP01_NRG.N.GY`, 844 obs back to 1956-01). FRED `JPNCPICEUNXFFMS` does **not** exist; the FRED / OECD MEI mirror (`CPGRLE01JPM659N`) is frozen at 2021-06; this fresh OECD COICOP2018 series is the cleanest aggregator-mirrored path. Note: this is "ex food + energy" (international core convention), not the BoJ's "ex fresh food" definition — to land the latter would require e-Stat credentials (`ESTAT_APP_ID`) for STATJP/CPIm series 733. Wired as `JPN_CORE_CPI_YOY` and blended into `JP_INFL1` alongside `JPN_CPI_YOY` (the fresh OECD all-items headline, PR #249). | DB.nomics OECD via existing `sources/dbnomics.py` | International core convention (ex food+energy); BoJ ex-fresh-food remains a future e-Stat-credentialed upgrade |
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

1. ✅ **Wire Atlanta Fed GDPNow** as `US_GDPNOW1` — shipped 2026-06-11 (`sources/atlanta_fed.py` 366 lines + `macro_library_atlanta_fed.csv` + Phase E indicator).
2. ✅ **Wire NY Fed Nowcast** as `US_NOWCAST1` — shipped 2026-06-12 (`sources/ny_fed.py` 348 lines + `macro_library_ny_fed.csv` + Phase E indicator; confirmed `raw=2.46 regime='near-trend'` in the 2026-06-12 daily run).
3. ✅ **UK monthly GDP** — `UK_NOWCAST1` Phase E indicator shipped 2026-06-11. Composition: weekly-Friday resample of ONS monthly real GDP (CDID ECY2, dataset MGDP — Gross Value Added Monthly Index CVM SA) converted to YoY %. Single-input passthrough — same trivial shape as `US_GDPNOW1`. Calculator `_calc_UK_NOWCAST1` registered in `_EU_CALCULATORS` alongside the other UK indicators; regime rule emits `above-trend` / `near-trend` / `contraction` on absolute YoY-% buckets calibrated to UK trend (~1.5%). New ONS library row: `GBR_GDP_MONTHLY` (sort_key 490, freshness_override 75d — matches the IoP / IoS / RSI band given the ~6-week ONS lag). Will surface in the explorer after the next daily run populates `UK_NOWCAST1_raw` in `macro_market_hist.csv`.
4. ✅ **Build EZ nowcast composite** — `EU_NOWCAST1` Phase E indicator shipped 2026-06-11. Composition: equal-weight z-scores of `EZ_IND_PROD` + `EZ_RETAIL_VOL` + `EU_ESI` (composite PMI proxy) + `EU_IND_CONF`. All inputs already wired. Pure Phase E work — no new fetchers. Calculator `_calc_EU_NOWCAST1` registered in `_EU_CALCULATORS`; regime rule emits `expansion` / `stable` / `contraction` on the composite z (≈ 0-centred). Will surface in the explorer after the next daily run populates `EU_NOWCAST1_raw` in `macro_market_hist.csv`.
5. ✅ **Build JP nowcast composite** — `JP_NOWCAST1` shipped 2026-06-12 (`_calc_JP_NOWCAST1` in `compute_macro_market.py`; equal-weight z of `JPN_IND_PROD` + `JP_TANKAN1` + `JPN_RETAIL_SALES` + `JPN_MACH_ORDERS`; confirmed `raw=1.008 regime='expansion'` in the 2026-06-12 daily run). Note: `JPN_RETAIL_SALES` and `JPN_MACH_ORDERS` are e-Stat sourced with corrected statsDataIds (still pending cdCat filter verification); the composite degrades gracefully on any absent input.
6. **Skip CN nowcast** — components mostly proprietary. Document as accepted gap.

**On the Eurocoin question:** if we don't want to maintain a CPB-style monthly download, the home-built EZ composite (item 4) is functionally equivalent for regime work. Decision deferred to implementation — start with the home-built composite (zero new dependencies); add Eurocoin later only if the composite proves noisy.

**Acceptance for §3.1.4:** ✅ all 5 nowcast composites (`US_GDPNOW1`, `US_NOWCAST1`, `UK_NOWCAST1`, `EU_NOWCAST1`, `JP_NOWCAST1`) appear in `macro_market.csv` with a clean weekly time series available to the regime classifier's Growth axis. Confirmed in the 2026-06-12 daily run. Consumer-side work lives in `../regime_AA_master_plan.docx`.

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
- ⏳ **Stage C** — `sources/ons.py` built 2026-05-28; UK GDP + 3 labour series live + 3 main monthly output indices (IoP K222, IoS S2KU, RSI J5EK) shipped 2026-06-10; GBR_CLAIMANT_COUNT (BCJD) + GBR_PPI_OUTPUT shipped 2026-06-15 (PR #205). JP growth column (3/7 → 8/7) via `sources/estat.py` extension shipped 2026-06-10 (5 PROVISIONAL statsDataIds pending live verification once `ESTAT_APP_ID` reaches the runtime). Still outstanding: UK BICS (not exposed as standard cdid/dataset timeseries). Region scorecard in `manuals/macro_market_indicators_coverage.xlsx` not yet updated.
- ✅ **Growth + Inflation focus (§3.1.3)** — 5 new per-region inflation regime composites (`US_INFL1` / `UK_INFL1` / `EU_INFL1` / `JP_INFL1` / `CN_INFL1`) + `US_INFEXP1` shipped 2026-05-28 (#152). Core inflation follow-up shipped 2026-06-10 for UK / EA / JP (`GBR_CORE_CPI_YOY` / `EA_HICP_CORE_YOY` / `JPN_CORE_CPI_YOY` blended into the regional `*_INFL1` calculators); CN core remains an accepted gap. JP PPI / Services PPI also shipped 2026-06-10 via BoJ direct (`JPN_PPI` / `JPN_SPPI`).
- ✅ **GDP Now (§3.1.4)** — all 5 nowcast composites shipped: `US_GDPNOW1` (Atlanta Fed, 2026-06-11), `EU_NOWCAST1` (2026-06-11), `UK_NOWCAST1` (2026-06-11), `US_NOWCAST1` (NY Fed Staff Nowcast, 2026-06-12), `JP_NOWCAST1` (equal-weight z of JPN_IND_PROD + JP_TANKAN1 + JPN_RETAIL_SALES + JPN_MACH_ORDERS, 2026-06-12). All confirmed computing in the 2026-06-12 daily run.
- ⏳ **Stage E** — survey deep-dive: per-country target list distilled from the demand doc; rows added via existing modules where free; documented gaps where proprietary.
- ⏳ **Stage G** — closeout: refresh `data/source_fallbacks.csv`, refresh `manuals/macro_market_indicators_coverage.xlsx`, archive working notes; this section enters `Status: Done` posture.


#### 3.1.8 Direct-wire replicable upstream sources — FactIQ source-inventory strategy

**Provenance:** distilled from the 2026-07-12 FactIQ audit (`FACTIQ_AUDIT_PLAN.md` §11 + `AUDIT_REPORT.md`, archived in git PR #266). FactIQ is an OAuth-gated MCP data-warehouse aggregator (22 upstream official sources, 25M+ series) used *interactively* to cross-check the pipeline — it is **never** a pipeline source (see the access-mechanism note below and tech_manual §14). This subsection captures the outstanding *direct-wire* roadmap: for every source FactIQ aggregates, decide whether the repo should ingest the provider **directly** (its own `sources/*.py`, like FRED/OECD/IMF) or lean on FactIQ as an interactive aggregation layer. Strategic intent (Kas): *replicate what we can replicate, then rely on FactIQ as an additional aggregator for the residue.* The repo already wires sources FactIQ does **not** carry (OECD, ECB, BoE, BoJ, Eurostat, ifo, Nasdaq DL, dbnomics, plus yfinance prices) — so repo ∪ FactIQ is broader than either alone.

**Milestone 1 — done.** `sources/treasury.py` (US Treasury daily par-yield curve, keyless `home.treasury.gov` CSV feed, per-year pagination + backoff, 13 tenors) shipped as fix #4 of the remediation (PR #265) and is the **reference template** for every direct-wire source below. Note: the FiscalData API (`api.fiscaldata.treasury.gov`) does **not** carry the daily par curve (404 — monthly averages only); the daily `home.treasury.gov` feed is the working path.

**Three-bucket model (§11):**

1. **Already covered — add series ids only:** Federal Reserve (policy/market rates, money stock, industrial production — via existing `sources/fred.py`, which *is* the Fed distribution), Department of Labor jobless claims (FRED `ICSA`/`CCSA`), FHFA house-price index (on FRED), plus **IMF** (`sources/imf.py`) and **World Bank** (`sources/worldbank.py`). No new wiring; just extend the relevant `macro_library_*.csv`.
2. **Replicate directly (clean free public API, high value):** **BEA, Census, EIA, Singapore SingStat** as genuinely-new `sources/*.py` on the `treasury.py` template; **BLS and Japan e-Stat are already wired** (`sources/bls.py`, `sources/estat.py`) so their task is *extend series coverage*, not build-new (see reconciliation below). US Treasury par-yield = done (milestone 1). SEC EDGAR optional (fundamentals — `sources/sec_edgar.py` pilot already exists as a standalone isolated phase; likely out of scope for a price/returns dashboard).
3. **Rely on FactIQ as aggregator (no clean API / high friction) — the residue:** China NBS + GACC customs, India MOSPI/RBI/DGCI&S, Korea & Taiwan customs, CBO, USDA ERS, BTS. These are exactly the sources where a direct ingester is expensive or infeasible — and (crucially) exactly the otherwise-dead regime-AA gaps below.

> **Reconciliation with what already exists (verified 2026-07-14 via `ls sources/`):** `sources/bls.py` (4 US series) and `sources/estat.py` (4 Japan series) are **already wired and in production** — do **not** frame these as new builds. For BLS the task is adding series ids to `data/macro_library_bls.csv`; for Japan e-Stat, extending `data/macro_library_estat.csv` (and the outstanding METI file-download fetcher for the two Excel-only gaps, §1 Known Data Gaps). The genuinely-new modules are **BEA, Census, EIA, SingStat**.

**Access-mechanism constraint (the hard rule):** the pipeline's Python cannot `import` FactIQ — it is an OAuth-gated MCP server, not a library — so there is **no `sources/factiq.py`**. However, a GitHub-Actions job *could* run Claude Code headlessly (`claude -p` / the Agent SDK) with FactIQ's MCP configured, and that agent could write FactIQ data into the repo's CSVs. This **agent-in-CI** path is a genuine option, distinct from a library import — but the mechanics matter (verified against the Claude Code / Agent SDK docs 2026-07-14):

- **Reusing FactIQ's *interactive* browser-OAuth token in CI is NOT supported** — Claude Code does not expose a documented way to persist/refresh that token for an unattended run, so it can silently expire mid-job with no browser to re-approve. (This is the kernel of truth behind the handover's overstated "never in CI.")
- **Three feasible paths instead**, all via the headless CLI / Agent SDK: **(A)** a **static/long-lived bearer token** passed in the MCP server's `headers` from a GitHub secret — *only if FactIQ can issue one* (a service credential / long-lived token; an open FactIQ-side question, since its plugin auth is interactive OAuth today); **(B)** a **credential-injecting proxy** run outside the agent boundary that holds the token and handles refresh (Anthropic's documented "secure deployment" pattern — most robust for unattended runs); **(C)** a **custom stdio MCP wrapper** we control that implements the OAuth-refresh logic and re-exposes FactIQ's tools.

All three still carry the same operational caveats: token refresh, the non-determinism/reliability of an LLM step inside a data pipeline, cost, FactIQ's rate limits, its free→paid risk, and its ToS (interactive access is licensed; redistributing the warehouse is not). Therefore the rule holds — **replicate any source that has a clean public API directly; reserve the FactIQ agent-in-CI path (if pursued at all) for the genuinely high-friction sources with no clean public API (China NBS/GACC, India RBI/DGCI&S, Korea/Taiwan customs)**, which are exactly the otherwise-dead regime-AA gaps below. **First feasibility gate: confirm whether FactIQ issues a static/service token (path A) or must be fronted by a proxy/wrapper (paths B/C).**

> **⚠️ ToS / redistribution gate — settle this BEFORE building anything on the agent-in-CI path.** The agent-in-CI path does not just *read* FactIQ interactively; it would **persist FactIQ's warehouse values into committed repo CSVs** that then flow to Google Sheets and the public explorer. That is redistribution, and FactIQ's terms license *interactive* access, **not** redistribution of its data. **To be explicit: we are NOT proposing to build a direct `data.stats.gov.cn` (NBS) scraper — that path stays parked as scrape-hostile / IP-restricted (§1 Known Data Gaps). The only realistic route to the live China PPI/IP is *through* FactIQ, which is exactly what makes this gate binding.** Decision order: (1) get an explicit answer from FactIQ on whether pulling series values into a downstream published product is permitted (and on what terms, given the free→paid risk); (2) only if yes, scope path A/B/C. **If FactIQ says no, the honest outcome is that these China gaps stay open — do NOT fall back to a fragile direct NBS scraper as a workaround.** The golden snapshot (`manuals/factiq_golden_*.json`; tech_manual Appendix B) is a one-off reference capture, not a licence to re-pipe the warehouse.

**FactIQ upstream source inventory (all 22 sources + the market-data layer).** Coverage/disposition per §11. *The live catalog was captured 2026-07-14 (29 schemas — see the regime-AA priorities block below for the verified China/India/customs findings). The table below is the §11 planning view; where a row's live status has been checked it is noted in the priorities block. Series-level ids still need confirming per-series before wiring, but schema-level availability is now verified, not assumed.*

| FactIQ source | Coverage | Direct route (verify at build time) | Bucket / disposition |
|---|---|---|---|
| BLS | CPI/PPI, employment, JOLTS, wages/ECI | `api.bls.gov/publicAPI/v2` (free key) | **Already wired** (`sources/bls.py`) — extend series |
| BEA | GDP, PCE, personal income | `apps.bea.gov/api` (free key) | **Replicate** (new module) |
| Census | Trade (HS-level), retail, housing, business formation | `api.census.gov` (free key) | **Replicate** (esp. HS trade — regime-AA) |
| EIA | Petroleum/gas/electricity/renewables + prices | `api.eia.gov/v2` (free key) | **Replicate** (new module) |
| US Treasury | Federal debt, **par yield curve**, TIC | `home.treasury.gov` daily CSV (keyless) | ✅ **Done** — `sources/treasury.py` (milestone 1) |
| SEC EDGAR | XBRL financials, ~1,000 US large caps | `data.sec.gov` (keyless, UA header) | Optional — `sources/sec_edgar.py` pilot exists |
| USDA ERS | Farm income, food economics | Bulk downloads / limited API | **Rely-on-FactIQ** (low value) |
| BTS | Freight, aviation, transit | Data-portal downloads | **Rely-on-FactIQ** (low value) |
| Federal Reserve | Policy/market rates, money stock, IP | via **FRED** (`sources/fred.py`) | **Covered** — add series ids |
| Department of Labor | Weekly jobless claims | FRED `ICSA`/`CCSA` | **Covered** — add series ids |
| FHFA | House Price Index | on FRED | **Covered** — add series ids |
| CBO | Budget history + 10y projections | Publication downloads, no clean API | **Rely-on-FactIQ** |
| China NBS | Macro (CPI/PPI/IP/activity) | `data.stats.gov.cn` (no clean API) | **Rely-on-FactIQ / agent-in-CI** (regime-AA) |
| China GACC | HS customs trade | No clean public API | **Rely-on-FactIQ / agent-in-CI** (regime-AA) |
| India MOSPI | CPI/WPI/IIP/GDP | `esankhyiki.mospi.gov.in` (moderate) | **Rely-on-FactIQ** (or attempt eSankhyiki) |
| India RBI | Banking, rates, forex | DBIE portal (awkward) | **Rely-on-FactIQ / agent-in-CI** (regime-AA) |
| India DGCI&S | HS customs trade | Commerce-dept portal (high friction) | **Rely-on-FactIQ / agent-in-CI** (regime-AA) |
| Japan customs | HS customs trade | via e-Stat API (moderate key) | **Replicate-possible** (`sources/estat.py` reaches e-Stat) / else FactIQ |
| Korea customs | HS customs trade | KCS / TRASS (high friction) | **Rely-on-FactIQ / agent-in-CI** (regime-AA) |
| Taiwan customs | HS customs trade | Customs portal (high friction) | **Rely-on-FactIQ / agent-in-CI** (regime-AA) |
| Singapore SingStat | National statistics | `tablebuilder` API (clean, low friction) | **Replicate** (new module) |
| IMF | International macro | via `sources/imf.py` (+`imf_sdmx.py`) | **Covered** |
| World Bank | International development/macro | via `sources/worldbank.py` | **Covered** |
| *(market-data layer)* | Equity/index/FX/commodity quotes, OHLCV, OVERVIEW | Alpha-Vantage-style API (`sources/alpha_vantage.py` scaffold exists, free ~25 req/day) | Keep **yfinance** primary; AV documented as fallback (`source_fallbacks.csv`) |

**Regime-AA gap-plugging priorities.** Ranked by value to the regime-AA Growth × Inflation / external frame, cross-referenced against this plan's own open gaps (§1 Known Data Gaps + §2.A). This is the highest-leverage reason to keep FactIQ in the toolkit at all — it uniquely aggregates the Asian NBS/customs residue that is otherwise dead for the pipeline. **✅ Verified against the live FactIQ catalog + `run_sql`/`get_market_data` on 2026-07-14 (catalog: 29 schemas incl. `china` NBS-direct, `china_customs`, `mospi`, `rbi`, `india_trade`, `korea_trade`, `japan_trade`, `taiwan_trade`, `singstat`, `imf`, `policy`).** The headline result overturns the pre-verification nuance: **FactIQ scrapes NBS directly (`data.stats.gov.cn`), so the China series are LIVE — the "dead since 2022" verdict applied only to the FRED/IMF/OECD *mirrors*, not to FactIQ.**

1. **China PPI** (§1 gap; `CHN_PPI` leg of `CN_INFL1`) and **China Industrial Production** (§1 gap; `CHN_IND_PROD`) — **✅ VERIFIED LIVE on FactIQ to 2026-05** (schema `china`, dataset `nbs`). China PPI sub-indices and monthly industrial series carry `end_time = 2026-05-01`; quarterly value-added of industry runs to Q4-2025. **This closes what the pipeline logged as accepted-dead gaps** — the frozen-2022 verdict was a property of the FRED OECD-MEI mirror / IMF PPI dataset / DB.nomics NBS shell, *not* of NBS itself, which FactIQ pulls direct. **Highest-value FactIQ win for regime-AA.** Next step: identify the exact headline all-industrial-products PPI YoY + IP YoY series ids and decide the ingestion path (agent-in-CI, since there is still no keyless NBS API for a `sources/*.py`).
2. **HS-level trade / customs indicators** (China GACC `china_customs`, India DGCI&S `india_trade`, Korea `korea_trade`, Taiwan `taiwan_trade`) — **✅ VERIFIED present** as dedicated per-country schemas (monthly imports/exports by HS commodity + partner). These are **new** External/Trade regime-AA indicators FactIQ *uniquely* aggregates (no clean public API anywhere) — highest-novelty additions to the regime frame's external axis, and the exact residue reserved for the FactIQ agent-in-CI path rather than a direct `sources/*.py`.
3. **India 10-Year yield** (§2.A A2; `IND_GOVT_10Y`) — **✅ strong candidate confirmed**: `rbi` schema carries a dedicated **Government Securities Market** dataset (`rbi-government_securities_market`) with yield curves — the India-10Y route the repo lacked a Tier-2 aggregator for. Verify the exact 10Y benchmark series id, then wire.
4. **China 10-Year government bond yield** (§1 gap; `AS_CN_R1` / the dangling `_get_col(mu, "CHN_GOVT_10Y")`) — **⚠️ still effectively a gap.** NBS (`china` schema) does **not** publish bond yields, and FactIQ has no PBoC / ChinaBond schema. The only possible route is IMF MFS (`imf` `mfs_ir` / `mfs_fmp` — "government bond yields, selected countries, monthly"), which is the *same* IMF path the repo already found frozen for China rates. Low-confidence candidate — check `imf.mfs_ir` for a live CN 10Y before assuming closable; otherwise the `CBON` ETF proxy stays.
5. **ITA / NLD 10-Year yields** (§2.A A2; `ITA_BTP_10Y` + `NLD_DSL_10Y`) — no country-specific EU sovereign-yield schema on FactIQ; only IMF MFS (`imf.mfs_ir`/`mfs_fmp`) might carry them. Lower priority (regime composites consume the aggregate `EU_R*` series, not country BTP/DSL). Verify `imf.mfs_ir` coverage for ITA/NLD before committing.
6. **Japan retail sales** (§1 gap; `JPN_RETAIL_SALES`) — **❌ NOT available via FactIQ (correction).** FactIQ carries **no Japan macro schema** — only `japan_trade` (customs). It cannot restore the `JP_NOWCAST1` retail leg; this stays a file-only gap needing the deferred `sources/meti_jp.py` Excel fetcher. *(An earlier draft of this section wrongly said FactIQ "reaches Japan e-Stat" — it does not.)*

**Bonus find (not in the original gap list): the `policy` schema.** FactIQ scores central-bank / government communications (FOMC, ECB, **PBoC**, RBI…) into chartable hawkish-dovish **stance series** (−1 dovish … +1 hawkish) per release, by topic (rate_path, inflation_outlook, labour, growth, liquidity), plus a searchable corpus. This is a **novel regime-AA sentiment/policy-stance feature** with no current pipeline equivalent — worth a dedicated evaluation for the regime frame's policy axis.

**CSI 500 re-source (cross-ref §2.A A18) — ✅ CONFIRMED:** `get_market_data(GLOBAL_QUOTE, "000905.SS")` returns **8138.14 CNY** prev-close (8275.94 close, 2026-07-14, SSE) — exactly the audit figure. The re-source candidate is real; FactIQ market-data prices it live even though the library marks it UNAVAILABLE.

**Golden-snapshot hedge + FactIQ free→paid risk (B5).** FactIQ is free "all data, no limits" *today* (2026-07-12) but may go paid — the single largest strategic risk to any FactIQ-dependent plan. The golden snapshot (`manuals/factiq_golden_2026-07-12.json` + `factiq_golden_2026-07-14_sweep.json`, embedded in tech_manual Appendix B) is the hedge captured while access was free: **keep it**, and future re-audits regress against it if live access disappears. This is also why the residue-bucket sources above are marked *rely-on-FactIQ* rather than *committed work* — the honest fallback for a genuinely-blocked source is the golden snapshot or a FRED-as-proxy series, not an assumption of perpetual free FactIQ access.

### 3.2 Retire the Simple Pipeline

**Priority:** Medium — code-cleanliness and maintenance-burden reduction. The simple pipeline is currently frozen but still adds ~70 library-driven instruments + a `sentiment_data` tab that the rest of the codebase no longer touches.
**Status:** Not started. Blocked on confirming downstream consumer usage.

**Context:** the simple pipeline is a ~70-instrument daily snapshot in `fetch_data.py`, selected via the `simple_dash` flag on `index_library.csv` (no longer a hardcoded list). It writes the protected `market_data` tab (GID `68683176`) and the `sentiment_data` tab. Its only known consumer is `trigger.py`, which runs at 06:15 London on a local Windows machine and reads `market_data` only. The comp pipeline (~390 instruments) covers a strict superset of the simple pipeline's instrument set, so the simple pipeline duplicates fetch traffic and code paths that have no other reason to exist.

**Plan:**

1. **Confirm `trigger.py` is still in active use.** Owner check: is the 06:15 Windows job still running? If retired, skip to Step 4. *(§2.C C12 makes this falsifiable: Google Cloud console Sheets-API usage for the service account, the Windows scheduled-task check, or a one-day canary — timestamp cell / tab rename. Do C12 first; it converts this blocked step into a one-session decision.)*
2. **If still in use:** decide between (a) migrating `trigger.py` to read `market_data_comp` (filter to the ~70 instruments it cares about), or (b) keeping `market_data` populated by a thin facade — `fetch_data.py` writes a subset view of `market_data_comp` after the comp run, dropping the dedicated simple-pipeline fetcher.
3. **Decide on `sentiment_data`.** Audit downstream readers: nothing in this repo references it. Confirm with the owner that it's safe to drop — if so, mark it for deletion (move to `SHEETS_LEGACY_TABS_TO_DELETE`).
4. **Delete the simple-pipeline code path.** Remove the `simple_dash`-filtered instrument selection (Fear & Greed, VIX term structure, FX majors, sector ETFs, FRED yields). Remove the simple-snapshot writer. `fetch_data.py` becomes a comp-pipeline-only module.
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

#### 3.8.5 FactIQ audit dead-ticker & coverage-gap backlog (2026-07-12)

Surfaced by the 2026-07-12 FactIQ audit (`manuals/factiq_audit_findings.csv` + `factiq_audit_working_list.csv`; tech_manual Appendix A; the §12 backlog write-up is archived in git PR #266). This is a `index_library.csv` remediation backlog and belongs to the §3.8 machinery above — it uses the **same `data/removed_tickers.csv` ledger + `data/yfinance_failure_streaks.csv` streak tracker** the weekly review already drives. Three classes:

- **Class 1 — genuinely dead (frozen ≥ 10y, serving stale values — retire, highest priority):** `^CM100` (CAC Mid 60), `^SP500-151050` (Paper & Forest Products), `^SP500-551020` (Gas Utilities). These serve *frozen stale values* today — worse than a blank because they look live.
- **Class 2 — no-output yfinance gaps (~29 rows, in library but produce no comp row):** ~26 `^SP500-xxxxxx` GICS *industry* sub-indices (yfinance discontinued the industry granularity — keep only the sector level the dashboard already gets, unless industry detail is a hard requirement), plus `000905.SS` (CSI 500) / `000852.SS` (CSI 1000), and `^VXEEM` (CBOE EM Volatility, discontinued by CBOE). Full list in `working_list.csv` where `has_output=False`.
- **Class 3 — empty output rows (47, comp row present but `Last Price` blank):** almost all foreign-listed UCITS ETF proxies — `.L`/`.DE`/`.PA`/`.JO` (e.g. `IWDA.L`, `ISF.L`, `EXSA.DE`, `C40.PA`, `STX40.JO`). Triage each into (i) fixable (wrong exchange suffix / share-class ambiguity), (ii) genuinely dead → retire, or (iii) needs a fallback source (`source_fallbacks.csv`).

**Guardrails (preserve verbatim):**
- **Do NOT hard-delete** — retire *through* the `removed_tickers.csv` ledger so history and rationale are preserved (mirror the existing `batch=STOXX600_sector` convention for the Class 2 industry sub-indices).
- The **52 `validation_status = UNAVAILABLE` rows** (Treasury/Bund/JGB yields, breakevens, SOFR, Fed funds, curve spreads, ICE BofA USD-hedged gilt/EGB families) are **curated-by-design placeholders, NOT dead** — sourced elsewhere (FRED / direct-wire per §3.1.8) or intentionally parked. **Exclude them from cleanup.**
- **Re-check against the LIVE `index_library.csv` first** — it moved ~28 lines since the audit, so anchor by ticker not line number.

**Effort:** Class 1 ~15 min (3 rows); Class 2 ~1 hr (batch retire + decide China/EM-vol re-sourcing); Class 3 ~half a day (47 rows, many resolve to a suffix correction rather than retirement).

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

### Regime-AA v2 data-pipeline asks (§3.12–§3.18)

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

> **Pipeline status (audited 2026-06-10): 🟢 SHIPPED — Shiller + Ken French + JST + IMF PCPS aggregate all wired.** All three §3.13 source modules built end-to-end on the same day: `sources/shiller.py` (Yale `ie_data.xls` parser + 6 rows: CAPE, S&P composite price/dividends/earnings, US CPI 1871+, 10Y long rate 1871+), `sources/french.py` (Dartmouth FTP ZIP-direct fetcher + 6 US 5-factor rows: Mkt-RF / SMB / HML / RMW / CMA / RF back to 1926-07), `sources/jst.py` (Macrohistory R6 .dta + 40 rows = 10 priority economies × 4 columns cpi/gdp/eq_tr/ltrate). IMF Primary Commodity Prices aggregate (`PALLFNFINDEXM`) wired in §3.9.1 with 13 per-commodity rows. Dispatch handlers added to `fetch_macro_economic.py` snapshot + history fetchers. Three new smoke tests wired into the daily workflow's primary-source smoke step (each network-gated; SKIPs when the host is unreachable from the runner). BoE Millennium remains the only §3.13 ask not yet shipped — flagged as optional / lower priority by the regime-AA handoff memo.

**Priority:** HIGH — multi-decade depth for Phase 1 regime labels (cross-validation anchors).

**Scope (one source module + library CSV each, per §0.1):**
- ✅ `sources/shiller.py` — monthly US 1871+ (S&P price/div/earnings, US CPI, long rate, CAPE) module + `data/macro_library_shiller.csv` (6 rows) + `test_shiller_smoke.py` shipped 2026-06-10. Yale `ie_data.xls` parser (decimal-year date format handled — `1871.10` = October not "1/10th of a year"); per-process cache so the workbook is downloaded once and sliced many times. Shiller `USA_CPI_SHILLER` and `USA_TREAS_10Y_SHILLER` kept as distinct cols from the modern BLS/FRED canonicals (`USA_CPI_INDEX` / `USA_TREAS_10Y`) so Shiller acts as a long-run cross-validation anchor rather than overwriting modern data.
- ✅ `sources/french.py` — US 5-factor monthly + RF back to 1926-07 shipped 2026-06-10. ZIP-direct fetch from Dartmouth FTP (`mba.tuck.dartmouth.edu`); pandas-datareader not adopted (it just wraps the same ZIP fetch). 6 library rows + `test_french_smoke.py`. Intl developed + EM factor sets documented as a deferred follow-up.
- ✅ `sources/jst.py` — Jordà-Schularick-Taylor R6 ingestion shipped 2026-06-10. Reads `.dta` directly via `pandas.read_stata`; per-process cache + composite `<iso>|<column>` series_id so the library CSV picks one (country, column) pair per row. 40 library rows = 10 priority economies (US/GB/DE/FR/JP + IT/CA/AU/NL/CH) × 4 columns (cpi, gdp, eq_tr, ltrate). Annual cadence, 730d freshness override. `test_jst_smoke.py` exercises `USA|cpi`.
- ✅ IMF PCPS aggregate — covered via §3.9.1's 14 FRED PCPS rows (13 per-commodity + `IMF_PCPS_ALL` aggregate `PALLFNFINDEXM`). Standalone `sources/imf_pcps.py` SDMX-direct module not built — FRED mirror is sufficient for the priority commodity set; revisit only if a regime-AA-needed commodity is missing from FRED.
- `sources/boe_millennium.py` *(optional, lower priority)* — BoE Millennium UK rates / CPI / GDP back to the early 1700s. Deferred per the regime-AA handoff memo.

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

### 3.18 Monthly growth backfill + quarterly GDP levels + dating audit (regime-AA-driven, HIGH — largely ✅ 2026-07-08)

> **Work order:** regime-aa memo `2026-07-08-monthly-growth-inflation-cadence`. regime-aa's Phase 1 regime labelling consumes per-region monthly growth + inflation series from `macro_economic_hist.csv`; inflation coverage was already good, but four monthly growth feeds were short (fetch-window/mirror artifacts, not source limits), FRA/CHE/NLD had no realized-activity column at all, quarterly real GDP levels existed only for FRA, and the spine dating convention differed silently between source modules. regime-aa re-runs its Fire & Ice build after this lands, dropping its hand-maintained −1-month shifts.

**Completed 2026-07-08 (this session; live columns materialise on the first post-merge daily run):**

1. **Backfill of the four short monthly growth feeds.** Root cause was A12 (DB.nomics Eurostat mirror frozen 2026-01-22) plus the teiis cubes' inherent ~13-month window — not Eurostat itself:
   - `EZ_IND_PROD` → ECB **STBS** dataflow (`STBS/M.I9.Y.PROD.NS0020.4D0.N.IX`, tier 0) — 2025-01→now became **1991-01 → 2026-04**, live again. STBS is the STS successor (STS itself froze 2025-09), `DATA_PROVIDER=4D0`, discovered by the same method as the A10 HICP fix.
   - `EZ_RETAIL_VOL` → `STBS/M.I9.Y.TOVV.2G4700.4D0.N.IX` (tier 0) — **2000-01 → 2026-05**, with a scope upgrade to headline total retail incl. fuel (old slice was non-food-ex-fuel).
   - `DEU_IND_PROD` → IMF Data Portal **PI** dataflow (`IMF.STA,PI/DEU.IND.SA_IX.M`, 2010=100 OL-linked) — **1958-01 → 2026-03**, fresh (the A1 "IMF SDMX escape hatch" watch item paying off again).
   - `JPN_IND_PROD` — live e-Stat winner keeps 2018-01+ (a source limit of the METI 2020-base table); pre-2018 depth **1953-01 → 2017-12** seeded into the sister archive from the frozen IMF PI JPN donor, ratio-spliced to the e-Stat 2020 base (ratio 1.13296, rel. std 0.33% over 2018-2019; `scripts/backfill_ind_prod_hist.py`, tech-manual Pattern 9 "curated deep-history seed").
   - The 3 dead teiis DB.nomics rows dropped + ledgered; `source_fallbacks.csv` chains updated.
2. **FRA / CHE / NLD realized-activity columns.** `FRA_IND_PROD` (INSEE idbank 010768261 tier 0, 1990-01 → 2026-05, + IMF PI T1 row; 1956-1989 seeded into the sister rebased to the INSEE 2021 base, seam step +0.03%); `NLD_IND_PROD` (IMF PI, 1956-01 → 2026-03); `CHE_IND_PROD` (IMF PI, **quarterly** — Switzerland publishes no monthly IP; 1990-Q1 → 2026-Q1 SA).
3. **Quarterly real GDP levels, FRA_GDP_INDEX pattern.** `DEU_GDP_INDEX` (1991-Q1+), `JPN_GDP_INDEX` (1994-Q1+), `ITA_GDP_INDEX` (1996-Q1+), `CHE_GDP_INDEX` (1995-Q1+), `NLD_GDP_INDEX` (1996-Q1+) via IMF QNEA `B1GQ.Q.SA.XDC.Q` (chained volume SA, national-currency units); `EA_GDP_INDEX` via ECB `MNA/Q.Y.I9.W2.S1.S1.B.B1GQ._Z._Z._Z.EUR.LR.N` (tier 0, EUR millions, 1995-Q1+). All verified fresh @ 2026-Q1 on 2026-07-08. IMF annual `NGDP_RPCH` columns untouched (deliberately-annual product).
4. **Dating convention decided + documented** — tech-manual **Pattern 13**: reference-START vs reference-END dating per module, verified empirically (`DEU_CPI_YOY` lags `DEU_HICP_YOY` by exactly +4 weeks, r=0.9976; identical 11.6% 2022 peaks one month apart). Decision: document now, re-date inside the §5 multifreq rebuild (flipping `dbnomics.parse_period_to_date` would silently move every DB.nomics column a month on the spine). Consumers shift the listed reference-end columns by −1 month; note `EA_HICP`/`EA_HICP_CORE_YOY` (A10) and `DEU_IND_PROD`/`EZ_IND_PROD`/`EZ_RETAIL_VOL` (this section) moved end → start with their repoints, so regime-aa's shifts for those five must be DROPPED.
5. **Plumbing:** `DEFAULT_HIST_START` widened to 1947-01-01 in `sources/ecb.py` (was 2000 — also deepens EA_HICP to 1996-12, EZ_M3, CISS) and `sources/imf_sdmx.py` (was 1990); `test_imf_sdmx_smoke.py` extended with PI + QNEA freshness/plausibility gates (PI JPN froze at 2023-11, so dataflow-level stalls are a live risk).

**Deferred / follow-ups:**

- **CHE monthly proxy** — KOF Economic Barometer is monthly but needs an API key and is a leading composite, not realized growth; SNB/BFS publish no monthly IP. Revisit only if regime-aa needs CHE monthly specifically (they have `CHE_IND_PROD` quarterly + `CHE_CPI_YOY` monthly).
- **Tier-0 upgrades** — Bundesbank direct for `DEU_IND_PROD`/`DEU_GDP_INDEX` (wildcard discovery returned 406 in this session's probe; needs the catalogue walk), ISTAT for `ITA_GDP_INDEX`, e-Stat/ESRI for `JPN_GDP_INDEX`. Low value while the IMF rows are fresh.
- **Deeper GDP levels** — OECD QNA linked series reach further back (DEU 1960s) than the Eurostat-benchmark starts the IMF carries; a discovery session against the OECD Data Explorer could extend the five country GDP columns. MEDIUM at best.
- **Spine re-dating to reference-start everywhere** — folded into §5 multifreq (Pattern 13 records the contract until then).
- **`EZ_EMPLOYMENT`** — still frozen on the dead DB.nomics mirror (last Eurostat leg of A12, quarterly; ECB `ENA` employment or Eurostat direct are candidates).

**Acceptance (regime-aa side):** ✅ four short feeds carry full upstream history (union view; live file fills on the next daily run) · ✅ FRA/NLD monthly + CHE quarterly realized-growth columns · ✅ quarterly real GDP levels for DEU/JPN/ITA/CHE/NLD/EA · ✅ dating convention documented per column (Pattern 13). regime-aa to re-run Fire & Ice and drop hand-maintained shifts.

---

### 3.19 Phase-1 data coverage: monthly growth & inflation per region, 1946+ scope (regime-AA-driven, HIGH — ✅ 2026-07-09)

> **Work order:** regime-aa memo `2026-07-08-monthly-growth-inflation-cadence`, **rewritten 2026-07-09** as the Phase-1 coverage list (8 items). Much of it was already delivered by §3.18 / earlier sessions; this section records the item-by-item disposition so the memo can be closed against it.

**Already delivered before this session (verified against committed hist 2026-07-09):**

- **Item 1a/1b (UK growth):** `GBR_IND_PROD` monthly **1948-01+** (ONS K222, wired 2026-06-10) and `GBR_GDP_MONTHLY` **1997-01+** (ONS ECY2, wired 2026-06-11) — both live in committed hist.
- **Item 2 (CAN):** `CAN_GDP_MONTHLY` monthly **1997-01+** (StatCan v65201210) + `CAN_EMPLOYMENT` monthly **1976-01+** (v2062811); `CAN_CPI_INDEX` reaches **1914+** upstream (1946-12+ on the committed spine). CHE/NLD/FRA growth columns delivered by §3.18.
- **Item 3 (EA19):** `EZ_IND_PROD` → **1991-01** and `EZ_RETAIL_VOL` → **2000-01** verified live via ECB STBS on 2026-07-09 (committed hist still shows 2025-01+ until the next daily regen fills it). Retail's 2000 start is an STBS series limit, not a fetch window — the deflated-turnover index simply starts there; documented as-is.
- **Item 6 (quarterly real GDP levels):** DEU/JPN/ITA/CHE/NLD (§3.18 IMF QNEA) + `EA_GDP_INDEX` (ECB MNA) + `GBR_GDP_REAL` (ONS ABMI, 1955+) + `AUS_GDP_REAL` (ABS ANA_AGG) already wired — only CAN was missing (closed below).
- **Item 7 (dating):** Pattern 13 already records the reference-start/reference-end contract (§3.18.4); option chosen was "document per-column", full re-dating deferred to §5 multifreq.

**Completed 2026-07-09 (this session; new columns materialise on the first post-merge daily run):**

1. **Item 1c — UK deep monthly inflation:** `GBR_RPI_YOY` (ONS CZBH, RPI all-items 12-month rate, monthly **1948-06+**, n=936 — the deepest monthly UK inflation rate; CPI/CPIH start 1989/1988) + companion `GBR_RPI` index level (ONS CHAW, Jan-1987=100, monthly 1987-01+ — the Zebedee monthly series starts at the index base). Both verified live 2026-07-09 (3.1% / 415.3 @ 2026-05). RPI's known formula effect (~+0.9pp vs CPI long-run; de-designated 2013) is noted in the library row — depth is the point.
2. **Item 5 — DEU pre-1997 monthly CPI:** `DEU_CPI_INDEX` ← `IMF.STA,CPI/DEU.CPI._T.IX.M` (national all-items, 2020=100, monthly **1955-01 → 2026-05**, n=857, verified live). Kills the 1996/97 floor on German inflation depth (`DEU_HICP_INDEX`/`DEU_CPI_YOY`). Discovery note: IMF.STA flows return only 1990+ unless `startPeriod` is passed — `DEFAULT_HIST_START=1947-01-01` (§3.18.5) is what makes the regen pull full depth.
3. **Item 6 (CAN gap) — quarterly real GDP level:** `CAN_GDP_INDEX` ← `IMF.STA,QNEA/CAN.B1GQ.Q.SA.XDC.Q` (chained volume SA, CAD units, **1961-Q1 → 2026-Q1**, verified live). StatCan tier-0 upgrade (table 36-10-0104) possible later.
4. **Item 4 — AUS monthly CPI + growth proxy:** `AUS_CPI_MONTHLY` ← ABS `CPI/1.10001.10.50.M` — the **complete monthly CPI** the ABS introduced with the Nov-2025 cycle (better than the memo's expected "indicator, 2022+"): live 2024-04+, with the frozen `CPI_M` indicator (2017-09 → 2025-09; froze when the complete series replaced it) ratio-spliced into the sister for 2017-09 → 2024-03 depth (`scripts/backfill_aus_cpi_monthly.py`, ratio 0.77904, drift 0.17%, seam step +0.77%; donor ledgered in `source_fallbacks.csv`). **Before 2017-09 Australia has no monthly CPI at any source — quarterly `AUS_CPI_INDEX` (1948-09+) is the documented fallback.** Growth proxy: `AUS_EMPLOYMENT` ← `LF/M3.3.1599.20.AUS.M` (employed persons total 15+ SA, monthly **1978-02+**; M3 is the total — M1 is full-time only). `AUS_UNEMPLOYMENT`/`AUS_PART_RATE` monthly 1978+ were already live.
5. **Item 7 (extension):** Pattern 13 table extended — ABS added to the reference-start family (quarterly dated at the 1st of the quarter's *last* month, like ECB), all six new columns recorded as reference-start from birth, and the AUS sister seed noted as dating-uniform across its seam.

**Deferred (unchanged or newly noted):**

- **Item 2 — CHE monthly proxy:** unchanged from §3.18 — KOF barometer needs an API key and is a sentiment composite, not realized growth; CHE stays quarterly (`CHE_IND_PROD` + `CHE_GDP_INDEX`) with monthly `CHE_CPI_YOY`. Revisit only on a specific regime-aa need (credentialed/Codespace session).
- **IMF PI `CAN.IND.SA_IX.M`** probed and rejected: frozen at 2023-10 (StatCan monthly GDP + employment are the live CAN monthly growth feeds).
- **AUS pre-2017 monthly CPI:** does not exist upstream; accepted limitation (quarterly before 2017-09, monthly-indicator-quality 2017-09→2024-03, complete monthly CPI after).
- **`EZ_RETAIL_VOL` pre-2000:** STBS carries nothing earlier for the deflated index; accepted (memo asked ~1991 "where the flow allows").
- Tier-0 upgrades and OECD-QNA deeper GDP levels: as listed under §3.18 deferred.

**Acceptance check (memo wording → status):** monthly growth ≥1 series per region at max depth — ✅ all 10 regions + EA19 (CHE quarterly, documented) · monthly inflation at max depth — ✅ GBR 1948+, DEU 1955+, AUS 2017+ (doc'd), others already deep · quarterly GDP levels for the 9 economies — ✅ all nine + EA19 · dating convention — ✅ documented per column (Pattern 13, extended) · forward_plan §3.x entry marking done-vs-deferred — ✅ this section.

---

## 4. Project Chronology

**Priority:** Low — useful project history but doesn't move the pipeline forward.
**Status:** Not started (a full generated chronology is still outstanding; the entries below are logged inline as they land).

**Recent notable entries:**
- **2026-07-12** — FactIQ data audit run (planning + report archived in git PR #266; row-level data now in `manuals/factiq_audit_*.csv`, summary in tech_manual Appendix A): full-universe ticker-by-ticker cross-check against the FactIQ warehouse, 676 findings (deduped), **4 real bugs** identified (EMB proxy/ARS-label corruption, dual-ticker currency labels, `.L` pence-gate over-conversion of EUR-quoted London lines, missing Treasury par-yield source). Golden snapshot captured while FactIQ is free (`manuals/factiq_golden_*.json`, tech_manual Appendix B).
- **2026-07-14** — FactIQ remediation merged (**PR #265**): the 4 fixes re-derived on current `main` — `sources/treasury.py` + `data/macro_library_treasury.csv` (new source, direct-wire milestone 1), pence-gate currency fix in `fetch_data.py`, EMB standalone-USD + 8 country-proxy removals and FEZ/ASHR/HYXU currency splits in `index_library.csv`.
- **2026-07-14** — Handover folder added (**PR #266**): `handover/` (FactIQ handover doc + `FACTIQ_AUDIT_PLAN.md` + `audit/` artefacts + golden snapshot).
- **2026-07-14** — FactIQ audit integrated into both manuals + China gaps re-verified against the live catalog (**PR #267**): Treasury source & the 4 fixes reconciled into the technical manual; direct-wire roadmap, full source inventory, dead-ticker backlog, agent-in-CI analysis, and the ToS/redistribution gate added to the forward plan; live verification confirmed China PPI/IP fresh to 2026-05 on FactIQ (NBS-direct) and corrected the Japan-retail-sales / China-10Y candidates. `handover/` folder retired entirely — its data artefacts relocated to `manuals/` (`factiq_audit_findings.csv`, `factiq_audit_working_list.csv`, `factiq_golden_*.json`) and its narrative folded into tech_manual Appendices A & B; scaffolding docs/scripts recoverable via PR #266.
- **2026-07-14** — Repo doc-hygiene sweep (**PR #269**): retired 5 superseded audit/handover `.md` files (`2026-06-15-source-tier-audit`, `2026-07-07-eu-freeze-freshness-china-handover`, `2026-06-17-m2-units-trio-recommendation`, `2026-06-15-label-vs-data-audit`, `AUDIT_HANDOVER_2026-06-15`), each reference-rewired to its surviving home in the manuals (tier model → tech_manual §9.4; the rest → forward_plan §2.A/§2.B/§12); no `data/*.csv` deleted (note-field edits only). Remaining deferred items (regime-AA v2 memos B4/C12, the generated `regime-aa-asks/` `.md` layer, Group D non-`.md`) are tracked in §2 "Repo file-hygiene — doc-deletion sweep"; full register + resolution log in `file_del_candidates.md`. The standalone repo-cleanup work-order was folded into this plan — §2 "Repo file-hygiene — doc-deletion sweep" plus this chronology entry — and retired.
- **2026-07-14** — Reconcile leftover youthful-gates cleanup onto main (**PR #270**): landed the 2 remaining Section-A High-confidence deletes that #269 didn't carry — `manuals/2026-06-15-codespace-secrets-checklist.md` and `manuals/2026-06-18-cpi-split-codespace-spec.md` — completing all 3 High-confidence deletes from the doc-deletion register. Repointed 5 data-provenance citations left dangling by the original branch commit (`macro_library_worldbank.csv`, `macro_indicator_library.csv` JP_INFL1, generated `macro_economic.csv` ×3, `docs/indicator_explorer.html`); re-grepped to zero dangling references. Also refreshed `multifreq_plan.md`'s stale cell-budget counts (50/302/8.4M → 91/390/8.8M) and corrected inaccurate "executed in PR #267" claims in `file_del_candidates.md` / `REPO_CLEANUP_HANDOVER.md`. Docs/data-provenance only — no code or pipeline-logic changes. §2 "Repo file-hygiene — doc-deletion sweep" updated to match.

```bash
git log --oneline --format="%ad  %s" --date=short | grep -v "Update market data + explorer"
```

Filter to significant changes (feature additions, bug fixes, schema changes, new modules). Output as either a dated chronology section in `manuals/technical_manual.md` (preferred — keeps the manual self-contained) or a standalone `manuals/chronology.md`. Update periodically as new features land.

---

## 5. Multi-Frequency Pipeline (Phase 2)

**Priority:** High impact but large effort. Detailed implementation plan in [`manuals/multifreq_plan.md`](multifreq_plan.md).
**Status:** Not started. **De-risking prerequisites (per §2.C sequencing):** C2 ✅ done 2026-07-09 (single source registry — the migration touches every source path once; one registry beats two 27-branch ladders) and C5 ✅ done 2026-07-08 (CI test gate — lets a migration this size proceed in reviewable steps) are both landed; **C1** (precedence enforcement — defines the correctness contract a multi-frequency merge must preserve) remains the one open prerequisite. Nothing in §2.C is thrown away by this migration.

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
