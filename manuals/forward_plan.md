# Market Dashboard — Forward Plan

> Last updated: 2026-04-26
> Based on: [`manuals/technical_manual.md`](technical_manual.md), [`manuals/multifreq_plan.md`](multifreq_plan.md), `archive/indicator_groups_review_UPDATED.xlsx`, and the historic `Project Plan 260327.md`, `MarketDashboard_ClaudeCode_Handover.md`, `METADATA_REDUNDANCY_REVIEW.md` (deleted from working tree; retained in git history — content consolidated into `technical_manual.md` and this file).

---

## 0. Architecture Preferences — Claude must always follow

> **Status:** Permanent. These are non-negotiable rules adopted on 2026-04-26 after two avoidable refactors caused by hardcoding identifiers in Python instead of in CSVs. Every Claude session must read this section before touching any data-layer code.

### 0.1 The single rule

**Every identifier the pipeline fetches lives in a CSV under `data/`. Never in Python.**

If the change you're about to make adds, removes, renames, or substitutes a fetched identifier — the only file you should be editing is a `data/macro_library_*.csv`. If you are reaching for a string literal in a `.py` file that looks like `"INDIRLTLT01STM"`, `"BSCICP02DEM460S"`, `"ISM/pmi/pm"`, `"BAMLHE00EHYIOAS"`, etc., **stop and put it in a CSV instead.**

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

PR2 (2026-04-26) added `INDIRLTLT01STM` directly to the `series_to_fetch` literal in `compute_macro_market.py::fetch_supplemental_fred()` instead of routing the new India 10Y series through the FRED library CSV. That is precisely the drift this section now prohibits. The supplemental list itself is the next refactor target — see §2.4.

---

## Table of Contents

0. [Architecture Preferences — Claude must always follow](#0-architecture-preferences--claude-must-always-follow)
1. [Project Phase Summary (A-G)](#1-project-phase-summary-a-g)
2. [Resume Here — Priority Tasks](#2-resume-here--priority-tasks)
3. [New Feature Development](#3-new-feature-development)
4. [Multi-Frequency Pipeline (Phase 2)](#4-multi-frequency-pipeline-phase-2)

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
| Phase D — Business Survey Data | Global PMI / bank lending / business confidence across US, EZ, DE, UK, JP, CN | T1 FRED (8 series incl. new CHN_BUS_CONF) + T2 DB.nomics (Eurostat + ISM) live. T3 FMP calendar **deleted** (paywalled 2025-08). Rebuild **mostly complete** — 8 of 12 broken indicators restored via free proxies, 3 proprietary (no free source), 1 composite auto-rebuilds. | Production for 8/12 indicators. 3 proprietary (DE_ZEW1, JP_PMI1, CN_PMI2) return `Insufficient Data` — no free monthly source exists. See §2.3. |
| Phase E — Macro-Market Indicators | 91 composite indicators with 156w rolling z-scores, regimes, forward regimes, cycle timing (L/C/G) | `compute_macro_market.py` → `macro_market`, `macro_market_hist` | Production |
| Phase F — Calculated Fields | Synthetic columns: EMFX basket, EEM/IWDA, MOVE proxy, global PMI/yield curve, breadth-above-200DMA | Partially covered in `compute_macro_market.py` | Partial |
| Phase G — Sheets Export Audit | Tab inventory (9 active), protected-tab guards across all writers, legacy-tab cleanup, batch-write coverage | Single source of truth in `library_utils.py`; guards added to 3 previously-missing writers on 2026-04-21 | Mostly Done |

### Phase-by-Phase Detail

#### Simple Pipeline — Production

66 hardcoded instruments (SPX, NDX, sector ETFs, FX majors, FRED yields, Fear & Greed, VIX term structure). Writes to the `market_data` and `sentiment_data` tabs. Preserved indefinitely for compatibility with `trigger.py`, which runs at 06:15 London time on a local Windows machine and reads `market_data` (GID `68683176`) only. No further work planned — the simple pipeline is frozen.

#### Comp Pipeline — Production

Library-driven expansion of the simple pipeline. ~390 instruments from `data/index_library.csv`; daily snapshot (`market_data_comp`) plus weekly Friday-close history from 1990 (`market_data_comp_hist`). 18-currency FX coverage via `COMP_FX_TICKERS` / `COMP_FCY_PER_USD` in `library_utils.py`. Pence correction dynamic (`.L` suffix + median > 50). Semantic `broad_asset_class` + `units` now read from the CSV rather than computed in code. The 7-step refactoring completed the transition from hardcoded lists to library-driven dispatch.

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

#### Phase D — Business Survey Data — PoC Verification In Progress

Rescoped from "ISM PMI via FMP" to a broader global-survey build covering US ISM, S&P Global country PMIs (EZ/UK/JP/CN), ZEW, IFO, ECB Bank Lending Survey, Japan Tankan, and EC Economic Sentiment — the full business-survey suite a global asset allocator needs. **Decision gate resolved 2026-04-21**, PoC verification underway on branch `claude/review-project-status-5x54q`. Key findings so far:

- **Tier 1 FRED**: 8/11 candidate series confirmed on FRED. BSCICP02JPM460S (Japan) and BSCICP02CNM460S (China) don't exist on FRED — Japan/China covered by Tiers 2/3 instead. BSCICP02GBQ460S (UK quarterly) retained as fallback until FMP UK PMI verified.
- **Tier 2 DB.nomics**: Rescoped to **3 Eurostat series only**. ISM mirror was 4-8 months stale → moved to FMP Tier 3. ECB/BLS dataset returns HTTP 404 on DB.nomics (doesn't exist) → EU_BLS1 indicator dropped. BOJ Tankan absent from DB.nomics → JP_TK1 dropped (Japan now covered by JP_PMI1 only). Verified Eurostat codes use dataset `ei_bssi_m_r2` with EA20 country filter: ESI/Industry Confidence have 552 obs back to 1980, Services Confidence has 369 obs back to 1995.
- **Tier 3 FMP**: Now covers 12 calendar events — 4 ISM (moved from T2) + 8 original (EZ/UK/JP/CN/DE PMIs, ZEW, IFO). PoC pending — needs `FMP_API_KEY` runtime environment.

Indicator count reduced from 15 to 13 (dropped JP_TK1 and EU_BLS1). Full resume-here plan in section 2.3.

#### Phase E — Macro-Market Indicators — Production

91 composite indicators computed from Phase A + Phase C outputs and the comp-pipeline market data. Each indicator produces: raw value, 156-week (3-year) rolling z-score, regime classification, forward regime signal (`improving`/`stable`/`deteriorating`, with optional `[leading]` suffix), and z-score trend diagnostics (`intensifying` / `fading` / `reversing` / `stable`) against 1w, 4w, 13w lookbacks. A `cycle_timing` column (L/C/G) classifies each indicator's position in the business cycle (89 Leading, 2 Coincident, 0 Lagging — see section 3.8). Metadata is a single source of truth in `data/macro_indicator_library.csv` — no hardcoded `INDICATOR_META` dict in Python. Group / sub-group hierarchy drives the three-level sidebar in `docs/indicator_explorer.html`. Outputs `macro_market` (snapshot) and `macro_market_hist` (weekly history). Recent additions: 9 standalone country-level CLI indicators (US_CLI1 through AU_CLI1), `EU_I4` Euro HY credit spread indicator; cross-wired EU indicator calculators fixed (Stage 2).

#### Phase F — Calculated Fields — Partial

Several synthetic fields from the original handover are already covered by Phase E indicators (HY/IG ratio → `US_Cr3`; value/growth → `US_EQ_F2`; US 5-regime credit spread → `US_Cr2`; EM vs DM equity ratio → `GL_G1` as EEM/URTH; EMFX basket → `FX_EM1` as of 2026-04-21; MOVE index → already ingested as `^MOVE` and used in `US_V2`). Outstanding items:

- Global PMI proxy — equal-weight ISM + Eurozone PMI + Japan PMI (blocked on Phase D)
- Global yield curve — average of US / DE / UK / JP 10Y-2Y spreads (needs DE/UK 2Y yields + JP 2Y/10Y added to `macro_library_fred.csv`)
- Per-index breadth-above-200DMA — requires in-house computation from constituent closes; no free feed exists for `$SPXA200R`-style symbols

See section 3.3 for the audit. New indicators follow the CSV-driven pattern: write a `_calc_*` function, add to `REGIME_RULES` and the relevant `_*_CALCULATORS` dict, add a row to `macro_indicator_library.csv`.

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

## 2. Resume Here — Priority Tasks

### 2.1 Generate Dated Chronology from Git History

**Priority:** For review — provides project history context without cluttering the forward plan with completed work.
**Status:** Not started.

The git log preserves a dated record of every significant change made to the codebase. A curated chronology can be generated from commit history using:

```bash
git log --oneline --format="%ad  %s" --date=short
```

Filter to significant changes (feature additions, bug fixes, schema changes, new modules) and exclude the daily automated `Update market data + explorer` commits. Output as a dated chronology section in `technical_manual.md` or as a standalone `manuals/chronology.md`. Update periodically as new features land.

### 2.2 Update Technical Manual to Reflect Current State

**Priority:** High — the technical manual should always reflect the full working state of all code.
**Status:** Completed 2026-04-23.

Key updates applied:
- Indicator count corrected from 68 to 91 across all references
- `cycle_timing` column documented in indicator library schema
- `FMP_API_KEY` status updated from "Missing" to "Exists"
- Resolved metadata items (`^VIX`, `^MOVE` region) marked as fixed
- Operational/infrastructure content absorbed from forward plan
- Excluded indicators reference table added
- New CSV files (`reference_indicators.csv`, `macro_library_dbnomics.csv`) added to inventory

### 2.3 Phase D Rebuild — FMP Replacement Plan

**Branch:** `claude/review-project-status-5x54q` (local) — also pushed.

**Status (2026-04-23):** The original 3-tier design (FRED / DB.nomics / FMP) was completed through Tier 2. Tier 3 FMP was paywalled and the entire calendar module has been **deleted** from the repo. Rebuild is **mostly complete** — 8 of 12 broken Phase E indicators restored using free proxy sources. 3 remain proprietary with no free monthly equivalent.

**Replacement plan** (source-per-indicator detail in `manuals/pipeline_review.md` §1):

| Indicator(s) | Replacement | Status |
|---|---|---|
| US_PMI1, US_PMI2, US_SVC1 | DB.nomics ISM (`ISM/pmi/pm`, `ISM/neword`, `ISM/nm-pmi/pm`) | **Wired 2026-04-23** (commit `1667276`). Mirror may lag 4-8m. |
| DE_IFO1 | ifo Institute Excel (`ifo.de/en/ifo-time-series`, 1991+ history) | **Wired 2026-04-23** (commit `f35a0aa`). New module `fetch_macro_ifo.py`. |
| EU_PMI1 | EC Industry Confidence (`EU_IND_CONF`, DB.nomics Eurostat) | **Wired 2026-04-23.** Same 3 PMI questions (production expectations, order books, stocks). Already in `dbn`. |
| EU_PMI2 | EC Services Confidence (`EU_SVC_CONF`, DB.nomics Eurostat) | **Wired 2026-04-23.** Monthly, 1995+. Already in `dbn`. |
| UK_PMI1 | OECD BCI for UK (`GBR_BUS_CONF`, FRED `BSCICP02GBM460S`) | **Wired 2026-04-23.** Upgraded from quarterly to monthly series. CBI-survey-derived, 1977+. Already in `mi`. |
| CN_PMI1 | OECD BCI for China (`CHN_BUS_CONF`, FRED `CHNBSCICP02STSAM`) | **Wired 2026-04-23.** NBS PMI-derived, monthly, Feb 2000+. New row in `macro_library_fred.csv`. |
| GL_PMI1 | Z-score-normalised 4-region composite (ISM + EU_IND_CONF + GBR_BUS_CONF + CHN_BUS_CONF) | **Wired 2026-04-23.** Degrades gracefully — averages whatever components are available. |
| DE_ZEW1 | **PROPRIETARY** — ZEW Mannheim licences the archive | No free API. German sentiment covered by DE_IFO1 + DEU_BUS_CONF. |
| JP_PMI1 | **PROPRIETARY** — S&P Global / au Jibun Bank | No monthly free source. BoJ Tankan (quarterly) is future option. |
| CN_PMI2 | **PROPRIETARY** — S&P Global / Caixin | Chinese manufacturing covered by CN_PMI1 (OECD BCI). |

**Completed steps:**

1. ~~Add 3 DB.nomics ISM rows~~ — **done** (commit `1667276`).
2. ~~Build ifo Excel fetcher~~ — **done** (commit `f35a0aa`).
3. ~~Probe ECB RTD for ZEW~~ — **done** (commit `c3e8c5a`), confirmed absent.
4. ~~Evaluate Investing.com scraper~~ — **rejected** 2026-04-23. Fragile anti-bot protections, frequent HTML changes, and Cloudflare blocking make scraping unreliable for a nightly CI pipeline. Free proxy alternatives found instead.
5. ~~Wire EU_PMI1/2 to EC Industry/Services Confidence~~ — **done** 2026-04-23. Data already flowed via DB.nomics; calculators rewired.
6. ~~Wire UK_PMI1 to OECD BCI, add CHN_BUS_CONF, wire CN_PMI1~~ — **done** 2026-04-23.
7. ~~Rebuild GL_PMI1 as z-score composite~~ — **done** 2026-04-23.

**Remaining work (future, separate PRs):**

- **BoJ Tankan fetcher** — quarterly Large Manufacturing DI via `stat-search.boj.or.jp`. Would give JP_PMI1 a quarterly proxy. Similar architecture to `fetch_macro_ifo.py`.
- **First CI verification** — next nightly run at 03:17 UTC validates the full pipeline with all new sources.

### 2.4 Eliminate `fetch_supplemental_fred()` — CSV-ify the last hardcoded series list

**Priority:** High — this is the architecture-drift hotspot called out in §0. PR2 (commit `d183e9f`, 2026-04-26) extended the Python list literal `series_to_fetch` to add India 10Y instead of CSV-routing it. That violates §0.1 and is the immediate motivation for this refactor.
**Status:** **Done 2026-04-26.** All 5 steps below landed in the same PR. `fetch_supplemental_fred()` deleted; `_fred_fetch_full()` deleted (no callers left); 7 affected calculators rewired to `_get_col(mu, ...)`; 7 new rows in `data/macro_library_fred.csv` (the original 6 + `BAMLEC0A0RMEY` which closed the last leak inside `fetch_ecb_euro_ig_spread`); `IND` added to `data/macro_library_countries.csv` (with empty `wb_code`/`imf_code` so it does not fan out into WB/IMF queries). Phase E now contains zero direct FRED API contact — every FRED ID used by the calculators reaches them through the unified `macro_economic_hist`.

#### Where the drift lives

`compute_macro_market.py::fetch_supplemental_fred()` (~line 211–290) declares its own Python list:

```python
series_to_fetch = [
    "PIORECRUSDM", "BAMLHE00EHYIOAS",
    "INDIRLTLT01STM",                                    # added in PR2
    "IRLTLT01GBM156N", "IRLTLT01DEM156N", "IRLTLT01ITM156N",
    "DGS10", "MORTGAGE30US", "JTSJOL", "UNEMPLOY",
]
```

This list:

1. **Bypasses the unified coordinator** — it makes its own FRED API calls instead of reading from `data/macro_economic_hist.csv`, even though Phase E has already finished by the time `fetch_supplemental_fred()` runs.
2. **Duplicates 4 series** that the unified coordinator already fetches: `DGS10`, `PIORECRUSDM`, `IRLTLT01GBM156N` (col `GBR_GILT_10Y`), `IRLTLT01DEM156N` (col `DEU_BUND_10Y`). Verified 2026-04-26 against `data/macro_library_fred.csv` lines 23, 40, 42, 43 and the column headers in `macro_economic_hist.csv`.
3. **Hardcodes 6 series that aren't yet in the FRED library** — `BAMLHE00EHYIOAS`, `INDIRLTLT01STM`, `IRLTLT01ITM156N`, `MORTGAGE30US`, `JTSJOL`, `UNEMPLOY`. These are the actual leak: any future change to this set has to be made in Python, not CSV.

#### Refactor plan

**Step 1 — Add the 6 missing series to `data/macro_library_fred.csv`** (zero new Python). Suggested rows (use existing schema; pick `col` aliases that match what the calculators already look up by ID):

| `series_id` | `col` | `name` | `country` | `concept` | `cycle_timing` | Consumer |
|---|---|---|---|---|---|---|
| `BAMLHE00EHYIOAS` | (blank) | ICE BofA Euro HY Index OAS | EZ | Credit / Spreads | L | EU_I4 |
| `INDIRLTLT01STM` | `IND_GOVT_10Y` | India 10-Year Government Bond Yield (OECD) | IND | Rates / Yields | C | AS_IN_R1 |
| `IRLTLT01ITM156N` | `ITA_BTP_10Y` | Italy 10-Year BTP Yield (OECD) | ITA | Rates / Yields | C | EU_I4_BTP_BUND |
| `MORTGAGE30US` | (blank) | 30-Year Fixed Mortgage Rate | USA | Rates / Yields | L | US_I11 |
| `JTSJOL` | (blank) | JOLTS Job Openings | USA | Labour | L | US_LAB2 |
| `UNEMPLOY` | (blank) | Unemployed Persons (level) | USA | Labour | C | US_LAB2 |

After this step, every supplemental ID lives in `macro_library_fred.csv`. The next nightly run will populate them in `macro_economic_hist.csv` automatically — no Python change is needed to *fetch* them.

**Step 2 — Switch the calculators to read from the unified hist instead of `supp`**.

For each `_calc_*` that currently calls `supp.get("XYZ", …)`, change it to read the same column from the unified `macro_economic_hist` DataFrame already passed into the calculator stack. Specifically:

- `_calc_US_I11` (`MORTGAGE30US − DGS10`)
- `_calc_US_LAB2` (`JTSJOL / UNEMPLOY`)
- `_calc_EU_I3` (`IRLTLT01GBM156N − IRLTLT01DEM156N`)
- `_calc_EU_I4_BTP_BUND` (`IRLTLT01ITM156N − IRLTLT01DEM156N`)
- `_calc_AS_IN_R1` (`INDIRLTLT01STM − DGS10`)
- `_calc_AS_C1` / `_calc_AS_C2` (PIORECRUSDM)
- `_calc_EU_I4` (Euro HY OAS via BAMLHE00EHYIOAS)

The calculator-level literal (e.g. `me_hist["IND_GOVT_10Y"]`) remains in Python — that's *logic*, not registry, per §0.2.

**Step 3 — Delete `fetch_supplemental_fred()` entirely** and the `supp = fetch_supplemental_fred()` call in `main()` (currently around line 2107). Phase E becomes a pure consumer of `macro_economic_hist.csv`, with no FRED API contact in `compute_macro_market.py`.

**Step 4 — Audit for any remaining series-ID literals in `compute_macro_market.py`.** Run `grep -nE '"[A-Z][A-Z0-9_]{4,}"' compute_macro_market.py` and confirm every remaining hit is a calculator-side column lookup (i.e. matches the `col` value of a row that exists in some `data/macro_library_*.csv`). Any that don't match → either add the row, or document the gap.

**Step 5 — Confirm cycle-timing & metadata fields.** When adding the 6 rows in Step 1, fill `concept` and `cycle_timing` properly. These flow through to `macro_indicator_library.csv` consumers and the explorer UI.

#### Acceptance criteria

- `fetch_supplemental_fred()` no longer exists.
- No Python list literal of FRED IDs anywhere in `compute_macro_market.py`.
- `grep "fred.*api" compute_macro_market.py` returns nothing — all FRED contact happens in `sources/fred.py` via `fetch_macro_economic.py`.
- The 7 affected calculators produce values that match the pre-refactor branch on the same input date (regression-test against a snapshot from `macro_market_hist.csv`).
- Daily run wall-clock time decreases (~10 fewer FRED calls per run; the 4 duplicate ones in particular).

#### Sequencing

This refactor should land **before** any future PR that would otherwise add a new series to `series_to_fetch`. PR2 itself can be merged as-is (the India 10Y data is correct; only its routing is non-canonical), with this refactor immediately following as a same-week cleanup. If a PR needs another supplemental before this refactor lands, that PR must add a row to `macro_library_fred.csv` *and* extend the literal — never just the literal.


---

## 3. New Feature Development

### 3.1 Phase D — PMI / Survey Data

**Priority:** Medium-high — business survey data is the largest structural gap in the indicator suite for a global asset allocator.
**Status:** Three-tier plan finalised 2026-04-21. `FMP_API_KEY` registered. See section 3.7 for full implementation plan, target series lists, and 13 indicators.

**The gap:** ISM PMI (US), S&P Global country PMIs (EZ/UK/JP/CN), ECB Bank Lending Survey, BoJ Tankan, ZEW, IFO, EC Economic Sentiment — none currently in the pipeline. FRED removed all 22 ISM series in June 2016 (S&P Global licence pulled). S&P Global country PMIs are proprietary and only available free via calendar redistribution. ZEW, IFO, NBS have no free APIs.

**Revised approach (post-FMP death, 2026-04-23):**

| Tier | Source | Coverage | Status |
|---|---|---|---|
| 1 | FRED (rows in `macro_library_fred.csv`) | 80 series: OECD confidence, policy rates, CPI, IP, trade, labour, credit across US/UK/EZ/JP/CN | **Production — expanded 2026-04-23 (Stage 2: +27 rows)** |
| 2a | DB.nomics Eurostat | EU_ESI, EU_IND_CONF, EU_SVC_CONF, EZ_IND_PROD, EZ_RETAIL_VOL, EZ_EMPLOYMENT | **Production — expanded 2026-04-23 (Stage 2: +3 rows)** |
| 2b | DB.nomics ISM | US ISM Mfg, ISM New Orders, ISM Services (may lag 4-8m) | **Production 2026-04-23** |
| 3a | ifo Institute Excel (`fetch_macro_ifo.py`) | DE_IFO1 (1991+ monthly) | **Production 2026-04-23** |
| 3b | EC Industry/Services Confidence (DB.nomics Eurostat, already in T2a) | EU_PMI1 → EU_IND_CONF, EU_PMI2 → EU_SVC_CONF | **Production 2026-04-23** — proxy using same PMI methodology |
| 3c | OECD BCI for UK (FRED `BSCICP02GBM460S`) | UK_PMI1 → GBR_BUS_CONF (monthly, CBI-derived) | **Production 2026-04-23** — upgraded from quarterly to monthly |
| 3d | OECD BCI for China (FRED `CHNBSCICP02STSAM`) | CN_PMI1 → CHN_BUS_CONF (monthly, NBS-derived) | **Production 2026-04-23** — new FRED library row |
| 3e | Z-score composite (computed from T1-3d) | GL_PMI1 = avg(ISM, EU_IND_CONF, GBR_BUS_CONF, CHN_BUS_CONF) | **Production 2026-04-23** |
| ~~3f~~ | ~~Investing.com scrape~~ | ~~7 indicators~~ | **Rejected** 2026-04-23 — fragile anti-bot protections; free proxies found instead |
| ~~3g~~ | ~~ECB RTD API~~ | ~~DE_ZEW1~~ | **Rejected** 2026-04-23 — ZEW proprietary |
| ~~3h~~ | ~~FMP calendar~~ | ~~S&P Global PMIs + ZEW + IFO~~ | **Deleted** 2026-04-23 — endpoints paywalled Aug 2025 |

**Total output:** 13 Phase D composite indicators. 10 now live. 3 proprietary (DE_ZEW1, JP_PMI1, CN_PMI2) — no free monthly source exists; these return `Insufficient Data`. Future BoJ Tankan fetcher (quarterly) could partially address JP_PMI1.

**Full indicator-to-source mapping:** see `manuals/pipeline_review.md` §1 and §5.

### 3.2 Instrument Expansion

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

### 3.3 Calculated Fields Expansion

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

### 3.4 Sheets Export Audit (Phase G)

**Status (2026-04-21):** Most items completed — see Phase G details in section 1. The full audit found and fixed three issues: missing protected-tab guards in 3 of 4 writer modules, an inline `TABS_TO_DELETE` constant in `fetch_data.py` that drifted from the `PROTECTED_TABS` set in `fetch_hist.py`, and a narrow `A:Z` clear range in `fetch_macro_us_fred.py` that would leave stale data if the schema grew past column Z. All three fixed by consolidating the shared tab state into `library_utils.py` (`SHEETS_PROTECTED_TABS`, `SHEETS_ACTIVE_TABS`, `SHEETS_LEGACY_TABS_TO_DELETE`) and wiring every writer to it.

**Remaining (low value):**
- Record Sheets GIDs for each of the 9 active tabs in `technical_manual.md` (housekeeping; only useful if downstream consumers need stable GID links).
- Build an automated drift check: compare the tab set in the Sheet against `SHEETS_ACTIVE_TABS ∪ SHEETS_LEGACY_TABS_TO_DELETE` and flag extras. Useful only if ad-hoc tabs are being created outside the pipeline.

### 3.5 Library Manager Utility

**Priority:** Low — developer tooling.

Create `library_manager.py` — a standalone utility for maintaining `index_library.csv`:

- Validate all tickers against yfinance (flag those returning no data)
- Auto-set `validation_status = "UNAVAILABLE"` for dead tickers
- Suggest alternative tickers for unavailable instruments
- Check metadata consistency (no duplicate tickers, all required fields filled)
- Run manually (`python library_manager.py`), not as part of the daily pipeline

### 3.6 Incremental Fetch Mode (fetch_hist.py)

**Priority:** Medium — performance improvement.

Currently `fetch_hist.py` rebuilds the entire dataset from scratch on every run (~8-12 min for `run_comp_hist()`). An incremental append mode would:

1. Check the last date in the existing CSV
2. Only fetch new weekly rows since the last update
3. Append to existing data rather than full rebuild

This would reduce daily historical data runtime from ~10 minutes to seconds.

### 3.7 Expand Macro Data Library from Additional Sources

**Priority:** Medium-high — business survey data is the biggest structural gap in the indicator suite for a global asset allocator.
**Status:** Source evaluation completed 2026-04-21. **Three-tier strategy:** Tier 1 FRED additions (zero new code); Tier 2 DB.nomics primary module (ISM, ECB BLS, Tankan, Eurostat ESI); Tier 3 FMP backup for proprietary S&P Global PMIs (EZ/UK/JP/CN) that DB.nomics cannot redistribute.

The FRED API does not carry the S&P Global-licensed PMIs (ISM and all country-level S&P Global PMIs), and OECD SDMX covers only the OECD-harmonised business/consumer confidence composites. A global asset allocator needs a wider survey suite: ISM (US), S&P Global PMI (EZ/UK/JP/CN), ZEW and IFO (Germany), ECB Bank Lending Survey (Eurozone), Tankan (Japan), and EC Economic Sentiment Indicator (EU). A systematic evaluation of 8 candidate sources was conducted on 2026-04-21 focusing on breadth of global coverage.

#### Global Gap Map — What's Missing by Region

**Already on FRED (in our library):** US SLOOS (5 series), UMich Consumer Sentiment, Conference Board Consumer Confidence, OECD US Business Confidence, OECD Eurozone Consumer Confidence, 4 Regional Fed surveys (Philly, Empire, Richmond, KC), UMich 1Y inflation expectations.

**Already on FRED (not yet in library — Tier 1 instant wins):** OECD business/consumer confidence composites for DE, UK, JP, FR, IT, CN (`BSCICP02*` / `CSCICP02*` series), Dallas Fed Mfg General Business Activity (`BACTUAMFRBDAL`).

**Missing — requires new source:**

| Region | Survey | Frequency | Best Source |
|---|---|---|---|
| US | ISM Manufacturing PMI composite + sub-indices (New Orders, Employment, Prices, Production) | Monthly | DB.nomics `ISM/*` |
| US | ISM Services PMI composite + Business Activity sub-index | Monthly | DB.nomics `ISM/nm-*` |
| Eurozone | S&P Global / HCOB Manufacturing PMI | Monthly | **FMP calendar** (S&P Global proprietary — not on DB.nomics) |
| Eurozone | S&P Global / HCOB Services PMI | Monthly | **FMP calendar** |
| Eurozone | ECB Bank Lending Survey (credit standards enterprises / households) | Quarterly | DB.nomics `ECB/BLS` |
| Eurozone | EC Economic Sentiment Indicator (ESI) + sector confidence | Monthly | DB.nomics `Eurostat/teibs020` |
| Germany | ZEW Economic Sentiment | Monthly | **FMP calendar** (ZEW has no free API) |
| Germany | IFO Business Climate | Monthly | **FMP calendar** (IFO has no free API) |
| UK | S&P Global UK Manufacturing / Services PMI | Monthly | **FMP calendar** |
| Japan | BoJ Tankan Large Manufacturers / Non-Mfr DI + forecasts | Quarterly | DB.nomics `BOJ/CO` |
| Japan | au Jibun Bank Japan Manufacturing / Services PMI (S&P Global) | Monthly | **FMP calendar** |
| China | NBS Manufacturing / Non-Manufacturing PMI | Monthly | **FMP calendar** (NBS has no free API) |
| China | Caixin Manufacturing / Services PMI (S&P Global) | Monthly | **FMP calendar** |

This split drives the three-tier strategy: DB.nomics covers everything that is open-licensed (ISM, ECB, BoJ, Eurostat); FMP's calendar fills the S&P Global proprietary gap (EZ/UK/JP/CN PMIs) and the institute-published surveys (ZEW/IFO) that lack free APIs.

#### Source Evaluation (completed 2026-04-21)

| Source | Verdict | Rationale |
|---|---|---|
| **FRED** | **TIER 1 — free additions** | OECD business/consumer confidence composites for all major countries already on FRED (`BSCICP02*`, `CSCICP02*`). Dallas Fed manufacturing also on FRED. Add ~10 rows to `macro_library_fred.csv` — zero new code. |
| **DB.nomics** | **TIER 2 — primary new module** | Free REST API, no key, no rate limit. Clean time-series output (not calendar events). Covers ISM with full sub-indices, ECB BLS (20,913 series), BoJ Tankan, Eurostat ESI / sector confidence — a single module handles all open-licensed surveys. Python `dbnomics` package returns DataFrames. |
| **FMP** | **TIER 3 — backup for proprietary feeds** | `FMP_API_KEY` registered. Economic calendar is the only practical free source for S&P Global country PMIs (EZ/UK/JP/CN are proprietary — not redistributed on DB.nomics), and for institute-published surveys (ZEW/IFO/NBS) that have no free API. Calendar events need transformation to time series. 250 calls/day. |
| **ECB SDW** | **BACKUP — BLS only** | Free SDMX 2.1 REST API (`data-api.ecb.europa.eu`). Use only if DB.nomics `ECB/BLS` coverage is incomplete. |
| **Bank of Japan direct** | **BACKUP — Tankan only** | Free REST API (`stat-search.boj.or.jp`). Use only if DB.nomics `BOJ/CO` is incomplete. |
| **Eurostat direct** | **BACKUP — ESI only** | Free REST API. Use only if DB.nomics `Eurostat/*` is incomplete. |
| **UMich portal** | **DEFER** | No official API. Headline `UMCSENT` already on FRED. ICE/ICC sub-indices move in high correlation with headline. Marginal value. |
| **Trading Economics** | **SKIP** | Paid API — minimum ~$49/month. Same data available free via DB.nomics + FMP. |
| **Investing.com** | **SKIP** | `investpy` broken since 2023 (Cloudflare). Scraping violates ToS. |
| **S&P Global / ISM direct** | **SKIP** | No programmatic API. Paid institutional subscription for sub-indices. DB.nomics redistributes ISM; FMP carries S&P Global country PMIs via calendar. |

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

#### Recommended Implementation Plan — Three Tiers

**Tier 1 — FRED additions (no new code; ~10 CSV rows)**

Add rows to `data/macro_library_fred.csv` for OECD-harmonised business/consumer confidence already hosted on FRED, plus the missing Dallas Fed regional survey. Picks up on the next daily run with no module changes.

| FRED series | Label | Country | Frequency | Verification (2026-04-22) |
|---|---|---|---|---|
| `BSCICP02DEM460S` | OECD Business Confidence — Germany | DEU | Monthly | Confirmed |
| `BSCICP02GBQ460S` | OECD Business Confidence — UK | GBR | Quarterly | Confirmed — retained as fallback until FMP UK_PMI1 verified |
| `BSCICP02JPM460S` | OECD Business Confidence — Japan | JPN | Monthly | **Does not exist on FRED — dropped. Japan covered by T3 JP_PMI1.** |
| `BSCICP02FRM460S` | OECD Business Confidence — France | FRA | Monthly | Confirmed |
| `BSCICP02ITM460S` | OECD Business Confidence — Italy | ITA | Monthly | Confirmed |
| `BSCICP02CNM460S` | OECD Business Confidence — China | CHN | Monthly | **Does not exist on FRED — dropped. China covered by T3 CN_PMI1/CN_PMI2.** |
| `CSCICP02DEM460S` | OECD Consumer Confidence — Germany | DEU | Monthly | Confirmed |
| `CSCICP02GBM460S` | OECD Consumer Confidence — UK | GBR | Monthly | Confirmed |
| `CSCICP02JPM460S` | OECD Consumer Confidence — Japan | JPN | Monthly | Confirmed |
| `CSCICP02CNM460S` | OECD Consumer Confidence — China | CHN | Monthly | Confirmed |
| `BACTUAMFRBDAL` | Dallas Fed Mfg — General Business Activity | US | Monthly | Confirmed |

**Tier 2 — DB.nomics module (`fetch_macro_dbnomics.py`)**

One fetch module using the DB.nomics REST API directly (no `dbnomics` Python package — `requests` only). Series driven by `data/macro_library_dbnomics.csv`.

**Scope reduced after PoC (2026-04-22):** originally planned to cover ISM + ECB BLS + BoJ Tankan + Eurostat (12 series). Final scope: **3 Eurostat series only**.

| DB.nomics ID | Series | Frequency | Region | PoC result |
|---|---|---|---|---|
| `Eurostat/ei_bssi_m_r2/M.BS-ESI-I.SA.EA20` | EC Economic Sentiment Indicator | Monthly | EA20 | 552 obs, 1980-01 → 2025-12 |
| `Eurostat/ei_bssi_m_r2/M.BS-ICI-BAL.SA.EA20` | EC Industry Confidence | Monthly | EA20 | 552 obs, 1980-01 → 2025-12 |
| `Eurostat/ei_bssi_m_r2/M.BS-SCI-BAL.SA.EA20` | EC Services Confidence | Monthly | EA20 | 369 obs, 1995-04 → 2025-12 |

**Dropped from Tier 2 (all confirmed by PoC):**
- **ISM (4 series)** — DB.nomics ISM mirror 4-8 months stale; unusable for daily dashboard. Moved to Tier 3 FMP calendar.
- **ECB BLS (2 series)** — `ECB/BLS` dataset returns HTTP 404 on DB.nomics (doesn't exist). EU_BLS1 indicator dropped from `compute_macro_market.py`. Can revisit later via direct ECB SDW API if needed.
- **BoJ Tankan (3 series)** — Not available under any BOJ dataset on DB.nomics. JP_TK1 indicator dropped. Japan now covered by JP_PMI1 (FMP) only.
- **Original Eurostat codes** (`teibs010`/`teibs020`) — PoC found these are summary tables with only ~12 obs; switched to `ei_bssi_m_r2` which has full history.

Advantages of remaining Eurostat over FMP: clean time-series format, deep history (back to 1980), no API key, no rate limit.

**Tier 3 — FMP calendar module (`fetch_macro_fmp.py`)**

Module covering (a) the S&P Global proprietary country PMIs and institute-published German surveys, plus (b) ISM — moved here after DB.nomics mirror found to be stale. Fetches the FMP economic calendar over a rolling window, filters by event name, transforms calendar entries into a monthly time series. Uses registered `FMP_API_KEY`.

12 target events (4 ISM moved from T2 + 8 original):

| FMP calendar event | Library col | Region | Source tier notes |
|---|---|---|---|
| ISM Manufacturing PMI | `ISM_MFG_PMI` | US | Moved from T2 (DB.nomics stale) |
| ISM Manufacturing New Orders | `ISM_MFG_NEWORD` | US | Moved from T2 — may not be on FMP; drop US_PMI2 if absent |
| ISM Services PMI (Non-Mfg) | `ISM_SVC_PMI` | US | Moved from T2 |
| ISM Services Business Activity | `ISM_SVC_BUSACT` | US | Moved from T2 — may not be on FMP; drop from US_SVC1 calculator if absent |
| S&P Global / HCOB Eurozone Manufacturing PMI | `EZ_MFG_PMI` | EA | Original |
| S&P Global / HCOB Eurozone Services PMI | `EZ_SVC_PMI` | EA | Original |
| ZEW Economic Sentiment (Germany) | `DE_ZEW` | DE | Original |
| IFO Business Climate (Germany) | `DE_IFO` | DE | Original |
| S&P Global / CIPS UK Manufacturing PMI | `UK_MFG_PMI` | GB | Original — once verified, drop FRED UK quarterly fallback |
| au Jibun Bank Japan Manufacturing PMI | `JP_MFG_PMI` | JP | Original — sole Japan signal (Tankan dropped) |
| NBS China Manufacturing PMI | `CN_NBS_PMI` | CN | Original |
| Caixin China Manufacturing PMI | `CN_CAIXIN_PMI` | CN | Original |

PoC must confirm FMP carries these exact event names with ≥3 years of history. If FMP history is shallow (<3 years), use FMP for current values only and skip z-score regime classification for those indicators until sufficient history accumulates. If an ISM sub-index is absent, drop the corresponding indicator.

#### New Indicators (Phase E additions — 13 total after PoC rescope)

Final scope: 13 indicators (was 15; dropped JP_TK1 with Tankan and EU_BLS1 with ECB BLS).

| ID | Formula | Group | Source Tier |
|---|---|---|---|
| `US_PMI1` | ISM Manufacturing PMI — raw level, 156w z-score | Growth & Activity | T3 (moved from T2) |
| `US_PMI2` | ISM Mfg New Orders — raw level, 156w z-score | Growth & Activity | T3 (moved from T2) |
| `US_SVC1` | ISM Services PMI composite — raw level, 156w z-score | Growth & Activity | T3 (moved from T2) |
| `EU_PMI1` | S&P Global Eurozone Manufacturing PMI — 156w z-score | Growth & Activity | T3 |
| `EU_PMI2` | S&P Global Eurozone Services PMI — 156w z-score | Growth & Activity | T3 |
| `EU_ESI1` | EC Economic Sentiment Indicator (EA20) | Growth & Activity | T2 |
| `DE_ZEW1` | ZEW Economic Sentiment — 156w z-score | Growth & Activity | T3 |
| `DE_IFO1` | IFO Business Climate — 156w z-score | Growth & Activity | T3 |
| `UK_PMI1` | S&P Global UK Manufacturing PMI — 156w z-score | Growth & Activity | T3 |
| `JP_PMI1` | Jibun Bank Japan Manufacturing PMI — 156w z-score | Growth & Activity | T3 (sole Japan signal) |
| `CN_PMI1` | NBS China Manufacturing PMI — 156w z-score | Growth & Activity | T3 |
| `CN_PMI2` | Caixin China Manufacturing PMI — 156w z-score | Growth & Activity | T3 |
| `GL_PMI1` | Global PMI proxy — equal-weight US ISM + EZ + JP + UK + CN PMI (all-T3) | Growth & Activity | T3 |

**Dropped after PoC:** `EU_BLS1` (ECB/BLS dataset absent from DB.nomics — HTTP 404), `JP_TK1` (BoJ Tankan absent from DB.nomics).

#### Implementation Order & Progress

1. **[DONE]** Tier 1 FRED additions — rows added to `macro_library_fred.csv`. PoC (2026-04-22) confirmed 8/11 exist; BSCICP02JPM460S + BSCICP02CNM460S don't exist on FRED (dropped); BSCICP02GBQ460S kept as UK fallback.
2. **[DONE]** Tier 2 PoC — `poc_dbnomics.py` ran 4 rounds. Resolved 3 Eurostat series to `ei_bssi_m_r2` (EA20, 1980-present). Confirmed ECB/BLS absent from DB.nomics (HTTP 404), BoJ Tankan absent, ISM mirror 4-8 months stale → restructured tier scope.
3. **[DONE]** Tier 2 build — `fetch_macro_dbnomics.py` exists. Library (`macro_library_dbnomics.csv`) updated to 3 Eurostat series with verified codes. No `dbnomics` package dependency — uses `requests` directly.
4. **[PENDING]** Tier 2 end-to-end test — run `python fetch_macro_dbnomics.py` to verify 3 Eurostat series fetch + write snapshot/hist CSVs + Sheets push.
5. **[PENDING]** Tier 3 PoC — `poc_fmp_calendar.py` covers 12 target events (4 ISM + 8 original). Needs `FMP_API_KEY` runtime. Confirm event names match, history ≥3 years.
6. **[PENDING]** Tier 3 end-to-end test — run `python fetch_macro_fmp.py` to verify calendar → monthly time series + writes.
7. **[DONE]** 13 new indicators registered in `compute_macro_market.py` (calculators + REGIME_RULES + dispatcher + `macro_indicator_library.csv` rows). JP_TK1 and EU_BLS1 removed after PoC findings.
8. **[PENDING]** Full pipeline run with Sheets push — confirm all 13 Phase D indicators land in `macro_market` and `macro_market_hist`.
9. **[PENDING — conditional]** After FMP verified, drop FRED fallback BSCICP02GBQ460S if UK_PMI1 has sufficient history.
10. **[PENDING — optional]** If ECB BLS signal judged essential, build direct `fetch_macro_ecb_sdw.py` against `data-api.ecb.europa.eu` (SDMX 2.1 REST). Currently deferred — EU_BLS1 dropped.

#### Non-API Fallbacks (only if PoC fails)

If FMP's calendar turns out to have shallow history (<3 years) for key European/Asian surveys, the fallback options (in descending preference) are:

1. **DB.nomics alternative providers** — check if S&P Global PMIs are indirectly hosted (e.g. via the `Eurostat` provider's industry confidence as a composite proxy, or via country central bank providers).
2. **ZEW direct press-release scrape** — monthly release on `zew.de` has a consistent table structure. Parse once a month. Fragile but bounded risk (one small parser).
3. **IFO direct press-release scrape** — same pattern on `ifo.de`.
4. **Manual CSV update** — user downloads headline values once a month into `data/macro_manual_surveys.csv`. Last-resort option; only for 1-2 series where no free programmatic source exists.

Skip UMich portal, Trading Economics, Investing.com, and S&P Global direct entirely (see source evaluation table above).

**Dependencies:** `dbnomics` package must be added to `requirements.txt` for Tier 2. No new dependency for Tier 3 (FMP uses standard `requests`).

### 3.8 Cycle Timing Framework (L/C/G) & Indicator Coverage Expansion

**Priority:** Medium-high — foundational for regime-aware allocation and charting.
**Status:** Phase E `cycle_timing` column added (2026-04-23). Reference cross-reference complete. Gap analysis and source prioritisation documented below. HTML integration pending.

#### Overview

A reference document (`manuals/Macro Market Indicators Reference.docx`) catalogues 206 macro/market indicators across 6 regions (US, UK, Eurozone, Japan, China, Global), each classified by **cycle timing**:

- **Leading (L)** — turns 3-12 months ahead of the business cycle (blue shading `#DCE7F2` in source doc)
- **Coincident (C)** — confirms the current state of the cycle (beige shading `#E8E4D9`)
- **Lagging (G)** — confirms trends already in place; turns after the cycle (pink shading `#EDE0E0`)

These colour codes were extracted programmatically from the Word document's cell shading using `python-docx`. All 206 indicators with their L/C/G classifications, cross-reference status, and source flags are recorded in `data/reference_indicators.csv`.

#### What's Been Done

1. **`data/reference_indicators.csv` created** — 206 rows, 10 columns: `region, number, indicator, category_source, notes, cycle_timing, match_status, matched_to, source_available, flags`.
2. **`data/macro_indicator_library.csv` updated** — new `cycle_timing` column added to all 91 Phase E indicators. Result: 89 Leading, 2 Coincident, 0 Lagging. The library is overwhelmingly forward-looking by design; coincident components are `US_JOBS3` (labour composite blending L+C+G) and `US_G6` (IP + Retail Sales, both coincident).
3. **Cross-reference completed** — every one of the 206 reference indicators matched against our 4 source libraries (FRED 52 series, DB.nomics 3 series, FMP 12 events, yfinance 390 instruments) and 91 Phase E indicators.

#### Coverage Summary (206 Reference Indicators)

| Match Status | Count | Description |
|---|---|---|
| Full | 44 | Fully captured in our pipeline |
| Partial | 22 | Close proxy or related series captured |
| None | 140 | Not yet captured |

| Flag | Count | Meaning |
|---|---|---|
| PROPRIETARY | 51 | No free API available — user review needed |
| NEW_SOURCE | 54 | Requires new fetcher module (BoE, ONS, ECB SDW, BoJ, e-Stat, BIS, CPB, OFR) |
| FRED_ADD/CHECK | 29 | Zero-code addition to `macro_library_fred.csv` or needs FRED ID verification |
| FMP_CHECK | 19 | May be available on FMP economic calendar — verify in PoC |
| DBNOMICS_ADD/CHECK | 11 | Available or potentially available on DB.nomics |
| DERIVED | 4 | Computed indicator requiring multiple source series |
| BETTER_SOURCE_PREFERRED | 1 | Available as snapshot only; historic time series preferred |

#### Gap Summary by Region

| Region | Total | Full | Partial | None | Actionable Gaps | Proprietary |
|---|---|---|---|---|---|---|
| US | 37 | 19 | 2 | 16 | 14 | 4 |
| UK | 36 | 2 | 2 | 32 | 25 | 11 |
| Eurozone | 36 | 9 | 7 | 20 | 18 | 3 |
| Japan | 35 | 2 | 4 | 29 | 29 | 4 |
| China | 36 | 3 | 4 | 29 | 9 | 19 |
| Global | 26 | 9 | 3 | 14 | 4 | 9 |
| **Total** | **206** | **44** | **22** | **140** | **99** | **51** |

**Key observations:**
- **US** is best covered (57% Full/Partial). Remaining gaps are mostly FRED_ADD (zero-code CSV rows).
- **UK** and **Japan** have the largest actionable gaps (25 and 29 respectively) — these need new source modules (ONS, BoE, e-Stat, BoJ).
- **China** has the most proprietary gaps (19) — NBS data has no free foreign API. Practical coverage limited to FRED OECD mirrors + FMP PMIs.
- **Eurozone** is well-served by existing Eurostat/DB.nomics + FMP, with ECB SDW as the main new source needed.

#### Prioritised FRED Additions (Zero-Code — Add Rows to `macro_library_fred.csv`)

These 20 indicators can be captured immediately by adding rows to the existing FRED library CSV:

| Region | Indicator | FRED Series ID |
|---|---|---|
| US | Average Weekly Hours, Manufacturing | AWHMAN |
| US | Non-Defence Capital Goods Orders ex-Air | NEWORDER (verify) |
| US | Capacity Utilization | TCU |
| US | Real Personal Income less Transfers | W875RX1 |
| US | Real Personal Consumption Expenditures | PCEC96 |
| US | Manufacturing & Trade Sales | CMRMTSPL |
| US | Chicago Fed National Activity Index | CFNAI |
| US | Unit Labour Costs | ULCNFB |
| US | Average Duration of Unemployment | UEMPMEAN |
| US | Commercial & Industrial Loans Outstanding | TOTCI |
| US | Corporate Profits (NIPA) | CP or A053RC1Q027SBEA |
| US | Retail Sales Control Group | RSFSXMV |
| UK | Bank Rate (BoE) | BOEBRBS |
| Eurozone | Germany Industrial Production | DEUPROINDMISMEI |
| Eurozone | ECB Deposit Facility Rate | ECBDFR |
| Eurozone | HICP Inflation | EA19CPALTT01GYM |
| Japan | JPY REER (BIS) | RBJPBIS |
| Japan | Industrial Production | JPNPROINDMISMEI |
| Japan | BoJ Policy Rate | IRSTCB01JPM156N |
| China | PPI Inflation | CHNPPIALLMINMEI |

#### New Source Modules Needed (by indicator count)

| Source | Indicators | Key Series | Effort |
|---|---|---|---|
| **e-Stat (Japan)** | 16 | Machinery orders, housing starts, economy watchers, retail sales, tertiary industry, coincident/leading indices, labour, household spending | Medium — free API with registration; `estat-api-client` package available |
| **ONS API (UK)** | 14 | Monthly GDP, IP, retail sales, employment, wages, CPI, claimant count, productivity, BICS | Medium — beta REST API; dataset IDs known (mgdp, iop, rsi) |
| **BoJ Statistics (Japan)** | 6 | Tankan (all variants), JGB curve, M2/M3 | Low-medium — REST API; `bojpy` package wraps it |
| **BoE BOESD (UK)** | 4 | Credit conditions survey, mortgage approvals, M4 lending, UK 2Y gilt yield | Low — free interactive database with CSV download; may need scraper |
| **ECB SDW (Eurozone)** | 4 | Bank Lending Survey, M3, negotiated wages, 2Y Bund yield | Low-medium — SDMX 2.1 REST API; `sdmx1` package |
| **BIS SDMX (Global)** | 2 | Household debt/GDP, global credit impulse components | Low — SDMX API |
| **CPB (Netherlands)** | 2 | World Trade Monitor, World Industrial Production | Low — free CSV download, monthly |
| **OFR (US/Global)** | 1 | Financial Stress Index | Low — free CSV/JSON API, daily |
| **Atlanta Fed** | 1 | GDPNow | Low — JSON API, snapshot-only (append through time) |
| **Bundesbank SDMX** | 1 | Germany Factory Orders | Low — SDMX API |

**Recommended build order** (highest impact, lowest effort first):
1. FRED additions (20 series, zero code)
2. CPB + OFR (3 series, simple downloaders, high signal value)
3. ONS API (14 UK series — fills the largest single-region gap)
4. e-Stat (16 Japan series — fills the second-largest gap)
5. ECB SDW (4 EZ series — complements existing Eurostat coverage)
6. BoE BOESD (4 UK series — complements ONS)
7. BoJ Statistics (6 Japan series — complements e-Stat)
8. BIS + Bundesbank + Atlanta Fed (4 series — lower priority)

#### Proprietary Indicators (User Review)

51 indicators are flagged PROPRIETARY in `data/reference_indicators.csv`. The user should review these to determine if any can be sourced via institutional access. Key categories:

- **S&P Global Flash PMIs** (3) — subscriber-only; we capture final PMIs via FMP
- **Conference Board composites** (4) — LEI/CLI; we use OECD CLI as substitute
- **China NBS sub-data** (12) — property, FAI, retail sales, electricity; no free foreign API. Wind/CEIC/Bloomberg only
- **Baltic Dry Index** (2) — Baltic Exchange; no reliable free API or yfinance ticker
- **Sell-side cycle models** (1) — GS/BCA/TS Lombard; subscription research
- **CBI, Lloyds, Sentix, Reuters Tankan** (5) — UK/EU business surveys with no free API
- **Other** (24) — various proprietary feeds across regions

#### HTML Charting Tool Integration (Pending)

**TODO:** Ensure the `cycle_timing` (L/C/G) classification feeds through to `docs/indicator_explorer.html`. Specifically:

1. **`build_html.py`** — read `cycle_timing` from `macro_indicator_library.csv` and pass it to the JavaScript data layer.
2. **`indicator_explorer.html` / `indicator_explorer_mkt.js`** — display L/C/G badge or colour code next to each indicator in the sidebar and detail panel. Colour convention: blue for Leading, amber/beige for Coincident, pink/red for Lagging.
3. **Optional filter** — allow sidebar filtering by cycle timing (show only Leading, only Coincident, etc.).
4. **Legend** — add a small legend explaining L/C/G terminology.

This is a display-only change — no new data computation needed. The `cycle_timing` column already exists in the CSV.

### 3.9 PE Ratio Integration

**Priority:** Medium-high — valuation data is a core input for a macro-market dashboard.
**Status:** Not started.

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

---

## 4. Multi-Frequency Pipeline (Phase 2)

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

---
