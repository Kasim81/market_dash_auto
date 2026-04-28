# Market Dashboard — Forward Plan

> Last updated: 2026-04-28

This is the project's forward-looking working doc. §0 sets the architecture rules every Claude session must read before touching data-layer code. §1 is the standalone phase / data-layer summary. §2 is the prioritised work queue. §3 captures feature roadmap items not yet on the queue. §4 cross-references `multifreq_plan.md` for the larger Phase 2 (multi-frequency) rebuild. The current code state lives in `manuals/technical_manual.md`; this doc and the technical manual are the only two contributor docs you need.

---

## 0. Architecture Preferences — Claude must always follow

> **Status:** Permanent. These are non-negotiable rules adopted on 2026-04-26 after two avoidable refactors caused by hardcoding identifiers in Python instead of in CSVs. Every Claude session must read this section before touching any data-layer code.

### 0.1 The single rule

**Every identifier the pipeline fetches lives in one of the source-of-truth CSVs under `data/`. Never in Python.**

There are multiple source-of-truth CSVs — one per data source — not a single registry. The full inventory is in **§1 Data-Layer Registry**, but the active set today is:

- `data/index_library.csv` — comp pipeline tickers (~390 yfinance instruments)
- `data/macro_library_countries.csv` — 12 country codes + WB / IMF mappings
- `data/macro_library_fred.csv` — every FRED series ID
- `data/macro_library_oecd.csv` — every OECD SDMX dataflow / dimension key
- `data/macro_library_worldbank.csv` — every WB WDI indicator code
- `data/macro_library_imf.csv` — every IMF DataMapper indicator code
- `data/macro_library_dbnomics.csv` — every DB.nomics series path
- `data/macro_library_ifo.csv` — every ifo workbook sheet/column location
- `data/macro_indicator_library.csv` — every Phase E composite indicator

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
4. [Multi-Frequency Pipeline (Phase 2)](#4-multi-frequency-pipeline-phase-2)

---
## 1. Project Phase Summary

The project evolved from a single hardcoded pipeline into the current 6-phase architecture. Each runtime phase is wrapped in its own `try/except` so a failure in a later phase cannot affect earlier outputs. Phase A (US Macro / FRED), Phase B (Surveys), Phase C (International Macro) and Phase D (Business Survey Data) were consolidated into a single Phase ME on 2026-04-23 — see the Phase ME description below for details.

| Phase | Scope | Module(s) → Tab(s) | Status |
|---|---|---|---|
| Simple Pipeline | Original 66-instrument daily snapshot; consumed downstream by `trigger.py` | `fetch_data.py` → `market_data`, `sentiment_data` | Production (frozen) |
| Comp Pipeline | Library-driven ~390-instrument snapshot + weekly history from 1990 | `fetch_data.py` + `fetch_hist.py` → `market_data_comp`, `market_data_comp_hist` | Production |
| **Phase ME — Macro-Economic** (unified) | Single raw-macro data layer covering FRED / OECD / World Bank / IMF / DB.nomics / ifo. Replaces retired Phase A / B / C / D. | `fetch_macro_economic.py` + `sources/{fred,oecd,worldbank,imf,dbnomics,ifo,countries}.py` → `macro_economic`, `macro_economic_hist` | Production |
| Phase E — Macro-Market Indicators | 92 composite indicators with 156w rolling z-scores, regimes, forward regimes, cycle timing (L/C/G) | `compute_macro_market.py` → `macro_market`, `macro_market_hist` | Production |
| Phase F — Calculated Fields | Synthetic columns (mostly absorbed into Phase E) | absorbed into `compute_macro_market.py` | Mostly Done |
| Phase G — Sheets Export Audit | 7-tab inventory, protected-tab guards across all 4 writers, legacy-tab cleanup, pipeline.log auto-commit | `library_utils.py` `SHEETS_*` constants | Done |

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

Phase D's "Tier 3 FMP calendar" track was paywalled and rejected on 2026-04-23 — the FMP module is also deleted. See §3.1 for the Phase D retrospective.

**Coverage by source:**

- **FRED** — 80+ series across yields, inflation, labour, credit, surveys, commodities, OECD-mirror business/consumer confidence; back to 1947 where available. Library: `data/macro_library_fred.csv`.
- **OECD SDMX** (`sdmx.oecd.org`) — CLI, unemployment, 3-month interbank rate across 11 economies. Library: `data/macro_library_oecd.csv`. Known structural gap: OECD does not publish CLI for EA19 or CHE — `compute_macro_market.py` uses the DEU+FRA equal-weight average as the Eurozone CLI proxy.
- **World Bank WDI** — CPI YoY across 11 economies. Library: `data/macro_library_worldbank.csv`.
- **IMF DataMapper v1** — real GDP growth across 11 economies. Library: `data/macro_library_imf.csv`.
- **DB.nomics** — 3 Eurostat survey series (EU_ESI / EU_IND_CONF / EU_SVC_CONF), 3 ISM series (Manufacturing / New Orders / Services), 3 Eurostat real-economy series (industrial production / retail volume / employment). Library: `data/macro_library_dbnomics.csv`.
- **ifo Institute Excel** — 26 German business-survey series (Industry+Trade composite + Manufacturing / Services / Trade / Wholesale / Retail / Construction sub-sectors, plus Uncertainty + Cycle Tracer). History from 1991. Library: `data/macro_library_ifo.csv`.

**Country registry:** `data/macro_library_countries.csv` is the single source of truth for the 12 country codes (USA, GBR, DEU, FRA, ITA, JPN, CHN, AUS, CAN, CHE, EA19, IND) and their WB / IMF code mappings. `IND` was added in the 2026-04-26 supplemental refactor for the India 10Y bond yield, with empty `wb_code` / `imf_code` so it doesn't fan out into multi-country queries.

**Architecture invariant (per §0):** every fetched identifier lives in `data/macro_library_*.csv`. As of the 2026-04-26 supplemental refactor `compute_macro_market.py` contains zero direct API contact — every series the calculators read is provisioned through the unified hist.

#### Phase E — Macro-Market Indicators — Production

92 composite indicators computed from the unified `macro_economic_hist` (per §1 Phase ME) plus the comp-pipeline market data. Each indicator produces: raw value, 156-week (3-year) rolling z-score, regime classification, forward regime signal (`improving`/`stable`/`deteriorating`, with optional `[leading]` suffix), and z-score trend diagnostics (`intensifying` / `fading` / `reversing` / `stable`) against 1w, 4w, 13w lookbacks. A `cycle_timing` column (L/C/G) classifies each indicator's position in the business cycle (90 Leading, 2 Coincident, 0 Lagging — see §3.3). Metadata is a single source of truth in `data/macro_indicator_library.csv` — no hardcoded `INDICATOR_META` dict in Python. Currently the region-based group / sub-group hierarchy drives the three-level sidebar in `docs/indicator_explorer.html`; §2.5 will add a concept-based browse path that mirrors the unified macro-library taxonomy (Rates / Yields, Inflation, Labour, Credit / Spreads, Sentiment / Survey, etc.) so related indicators across regions can be viewed together. Outputs `macro_market` (snapshot) and `macro_market_hist` (weekly history). As of the 2026-04-26 supplemental refactor Phase E contains zero direct API contact — every series the calculators read is provisioned through the unified hist; PR3 (2026-04-26) cleared the build-phase `DataFrame is highly fragmented` warnings, and the 2026-04-27 fix-forward (this PR) cleared the remaining two output-phase ones plus the EU_Cr1 / `BAMLEC0A0RMEY` regression. EU_Cr1 (Euro IG spread) returns n/a until a free Euro IG corporate yield source is wired (see §1 Known Data Gaps); a new EU_Cr2 (Euro HY spread, reads `BAMLHE00EHYIOAS`) covers the Euro-HY regime as a separate indicator.

#### Phase F — Calculated Fields — Partial

Several synthetic fields originally scoped under Phase F have been absorbed into Phase E indicators (HY/IG ratio → `US_Cr3`; value/growth → `US_EQ_F2`; US 5-regime credit spread → `US_Cr2`; EM vs DM equity ratio → `GL_G1` as EEM/URTH; EMFX basket → `FX_EM1` as of 2026-04-21; MOVE index → already ingested as `^MOVE` and used in `US_V2`). Outstanding items:

- Global PMI proxy — equal-weight ISM + Eurozone PMI + Japan PMI (blocked on Phase D)
- Global yield curve — average of US / DE / UK / JP 10Y-2Y spreads (needs DE/UK 2Y yields + JP 2Y/10Y added to `macro_library_fred.csv`)
- Per-index breadth-above-200DMA — requires in-house computation from constituent closes; no free feed exists for `$SPXA200R`-style symbols

See section 3.3 for the audit. New indicators follow the CSV-driven pattern: write a `_calc_*` function, add to `REGIME_RULES` and the relevant `_*_CALCULATORS` dict, add a row to `macro_indicator_library.csv`.

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

Outstanding (low value): record Sheets GIDs for each active tab in `manuals/technical_manual.md` (covered by §2.2 below); build an automated "tab drift" audit that flags tabs in the Sheet but not in `SHEETS_ACTIVE_TABS ∪ SHEETS_LEGACY_TABS_TO_DELETE`.

Batch writes (10k rows/call) are only implemented in `fetch_hist.py` — the largest tab (`market_data_comp_hist`, ~9,000 rows) sits within the Sheets API's single-call payload limit at current column count, so no other writer has hit a batching need yet. Revisit if column count grows significantly.

### Data-Layer Registry (single source of truth — per §0)

These 10 CSVs in `data/` are the single source of truth for everything the pipeline fetches or computes. Adding / removing / renaming a series = edit the relevant CSV. Never a Python literal (per §0.1).

| File | Rows | Owner | Used by |
|---|---|---|---|
| `index_library.csv` | ~390 | Comp pipeline | `fetch_data.py`, `fetch_hist.py` |
| `macro_library_countries.csv` | 12 | Phase ME | `sources/countries.py` (canonical / WB / IMF code mappings) |
| `macro_library_fred.csv` | ~85 | Phase ME | `sources/fred.py` |
| `macro_library_oecd.csv` | varies | Phase ME | `sources/oecd.py` |
| `macro_library_worldbank.csv` | varies | Phase ME | `sources/worldbank.py` |
| `macro_library_imf.csv` | varies | Phase ME | `sources/imf.py` |
| `macro_library_dbnomics.csv` | 9 | Phase ME | `sources/dbnomics.py` |
| `macro_library_ifo.csv` | 26 | Phase ME | `sources/ifo.py` |
| `macro_indicator_library.csv` | 91 | Phase E | `compute_macro_market.py` (composite indicator registry) |
| `reference_indicators.csv` | 206 | Reference (gap audit) | §3.3 cross-reference; not consumed by the runtime pipeline |

**Read order in `fetch_macro_economic.py`:** `countries → fred → oecd → worldbank → imf → dbnomics → ifo`. Each `sources/*.py` exposes `load_library() -> list[dict]` returning the unified indicator schema (`source`, `source_id`, `col`, `name`, `country`, `category`, `subcategory`, `concept`, `cycle_timing`, `units`, `frequency`, `notes`, `sort_key`).

**Library Manager (planned, §2.7):** a standalone `library_manager.py` will validate every CSV — verify FRED IDs against the FRED API, probe OECD dataflows + DB.nomics paths, sanity-check ifo sheet positions, and lint `index_library.csv` tickers against yfinance.

### Known Data Gaps (consolidated, 2026-04-26)

These are cases where a planned series is unavailable from any free source we accept. Documented here so they aren't re-investigated repeatedly.

| Gap | Impact | Resolution |
|---|---|---|
| **China 10-Year government bond yield** | `AS_CN_R1` (China–US 10Y spread) returns NaN. FRED only carries the short-term `IR3TTS01CNM156N`; the OECD MEI long-term-rate dataset has no CN series. | Future: route a CN 10Y series via DB.nomics (PBoC / ChinaBond mirror) into the unified hist as `CHN_GOVT_10Y` — calculator already reads that column name. |
| **Euro IG corporate effective yield** (target series: ICE BofA Euro Corporate Index Effective Yield) | `EU_Cr1` (Euro IG spread = corp yield − ECB AAA 10Y govt yield) returns NaN. FRED `BAMLEC0A0RMEY` was probed but 400s on every call; ECB SDW does not publish a free aggregate Euro IG yield series; iBoxx EUR Corporate is paywalled. | Future: investigate (a) DB.nomics ECB MIR (bank lending rates to non-financial corps — different instrument but free + monthly + long history), (b) iShares EUR IG Corp Bond ETF (`IEAC.L` / `LQDE.L`) distribution-yield proxy via yfinance, or (c) Bundesbank SDMX corporate-bond yield series. ECB AAA 10Y govt-yield half is already wired in `fetch_ecb_euro_ig_spread()` — only the corp-yield half needs sourcing. EU_Cr1 returns n/a until then; no HY substitute (Euro HY is its own indicator, EU_Cr2). |
| **`BSCICP02JPM460S` / `BSCICP02CNM460S`** (OECD Business Confidence — Japan / China on FRED) | Don't exist on FRED. | Japan covered by `JP_PMI1` (proprietary, returns Insufficient Data); China covered by `CHNBSCICP02STSAM` (different ID). |
| **`DE_ZEW1`** (ZEW Economic Sentiment) | Returns Insufficient Data. ZEW Mannheim licences the archive; no free API. | Substitute: German sentiment is covered by `DE_IFO1` + `DEU_BUS_CONF`. |
| **`JP_PMI1`** (au Jibun Bank Japan Manufacturing PMI) | Returns Insufficient Data. S&P Global proprietary, no monthly free source. | Future partial fix: BoJ Tankan quarterly DI via direct fetcher — covered as a concrete first new-source target in §3.1 (comprehensive surveys sub-project). |
| **`CN_PMI2`** (Caixin China Manufacturing PMI) | Returns Insufficient Data. S&P Global proprietary. | Substitute: Chinese manufacturing is covered by `CN_PMI1` (OECD BCI for China). |
| **OECD CLI for EA19 / CHE** | Not published by OECD. | `compute_macro_market.py` uses DEU+FRA equal-weight as the Eurozone CLI proxy. |
| **`NAPMOI`** (FRED ISM new orders) | Retired by FRED in April 2026 (HTTP 400 from late April onwards). | `US_ISM1` reads `ISM_MFG_NEWORD` from DB.nomics via the unified hist (PR2, 2026-04-26). |
| **`CHN_PPI`** (FRED `CHNPPIALLMINMEI`) | Retired by FRED. | Removed from `macro_library_fred.csv` (PR1, 2026-04-25); no Phase E indicator currently depends on it. |
| **Investing.com / Trading Economics / S&P Global direct / FMP economic calendar** | Evaluated and rejected: scraping fragility (Cloudflare), paid-only APIs, FMP endpoints paywalled August 2025. | Do not revisit. |


---

## 2. Resume Here — Priority Tasks

This is the priority queue distilled from the 2026-04-22 → 2026-04-26 work cluster (sources/ refactor → unified Phase ME → architecture-preference rules → supplemental-FRED CSV-ification → fragmentation cleanup). Items are listed in execution order; each is self-contained with its own acceptance criteria.

Completed work that previously lived in this section:

- ~~§2.4 (old) — Eliminate `fetch_supplemental_fred()`~~ — done 2026-04-26 (commit `48c8c1c`); see §1 Phase E description.
- ~~§2.2 (old) — Update technical manual~~ — was marked complete 2026-04-23 but has since gone stale; relisted as **§2.2 below** with a full review-and-update scope.
- ~~§2.3 (old) — Phase D Rebuild — FMP Replacement Plan~~ — done 2026-04-23 (Phase D consolidated into Phase ME, FMP rejected); the BoJ Tankan follow-up was tracked at §2.8 then absorbed into **§3.1** (the comprehensive surveys sub-project) on 2026-04-28.
- ~~§2.1 (old) — Generate dated chronology from git history~~ — relisted as **§2.9 below** at low priority.

### 2.1 Verify the merged stack on the next nightly CI run

**Priority:** Immediate (no work needed; just read tomorrow's `pipeline.log`).
**Status:** Done 2026-04-27 — verified against the 06:09 UTC run; three regressions caught and fixed-forward in the same session (this PR). Outcome below.

Four PRs merged in the 24h window 2026-04-25 → 2026-04-26 — the 2026-04-27 run was the first time they all executed together:

| PR | Commit | Verifies |
|---|---|---|
| PR1 (pipeline.log capture + remove CHN_PPI) | `3a0957d` | ✅ The log itself is the artefact. |
| PR2 (ECB endpoint + 3 FRED 400s) | `d183e9f` | ✅ ECB host migrated; `INDIRLTLT01STM` returns India 10Y data; old `IRLTLT01CNM156N` no longer attempted. ⚠ ECB YC date parser was using `format="%Y-%m"` against the daily `YYYY-MM-DD` returns → 0 obs parsed; fixed in this PR. |
| (Old §2.4) supplemental refactor — CSV-ify supplementals | `48c8c1c` | ✅ 6 of 7 new FRED columns present in `macro_economic_hist.csv` (`JTSJOL`, `UNEMPLOY`, `MORTGAGE30US`, `BAMLHE00EHYIOAS`, `IND_GOVT_10Y`, `ITA_BTP_10Y`); 7 of 8 rewired calculators produce sensible values (`AS_CN_R1` stays NaN per the documented China-10Y gap). ⚠ `BAMLEC0A0RMEY` returns FRED HTTP 400 — series not in the FRED database; row removed in this PR (see §1 Known Data Gaps); EU_Cr1 now returns n/a (no HY fallback — Euro HY split into new indicator EU_Cr2). |
| PR3 (DataFrame fragmentation refactor) | `9999e0d` | ✅ Build-phase warnings cleared. ⚠ Two residual warnings remained at the output-phase `df_hist.reset_index()` calls; cleared in this PR by adding `.copy()` after `pd.concat` in `build_hist_df()`. |

**Outcome:** all three fix-forward items landed in this PR alongside the new EU_Cr2 indicator (Euro HY spread, reads `BAMLHE00EHYIOAS`). Verify the next nightly run shows zero `PerformanceWarning`s, no `BAMLEC0A0RMEY` in the log, ECB YC obs count > 0, EU_Cr2 produces sensible values, and EU_Cr1 reports n/a cleanly.

### 2.2 Refresh `manuals/technical_manual.md` to current reality

**Priority:** High — the technical manual is the canonical reference.
**Status:** Done 2026-04-27 — section-by-section refresh landed in 8 commits on `claude/review-forward-plan-rQ2x9` (PR #98, merged 2026-04-28). Outcome below.

| Step | Commit | Scope |
|---|---|---|
| 1 | (audit only) | Stale-reference punch list |
| 2 | `8cea51e` | §1-§4 architecture (Scope, Directory Structure, Execution Flow, Two Pipelines) |
| 3 | `5a4017b` | §5-§7 data layer (Data Sources & APIs, Tab Map, CSV Inventory) |
| 4 | `d49bc21` | §9 part A — retire stale module entries + add `fetch_macro_economic.py` and `sources/` package |
| (interleaved) | `49bd676` | Schedule change 03:17 → 00:34 UTC |
| 5 | `b947447` | §9 part B — refresh surviving module entries (line counts + drift) |
| 6 | `b464402` | §10-§13 — Patterns, Env Setup, Known Issues restructure |
| 7 | `6bcfc8b` | §14 + ToC + cross-ref pointer to `forward_plan.md` §0 + final grep |
| 8 | `5faa679` | `file_del_candidates.md` at the repo root (audit-only, 6 candidates surfaced) |

**Acceptance verified:** every grep against `technical_manual.md` for retired module names (`fetch_macro_us_fred.py`, `fetch_macro_international.py`, `fetch_macro_dbnomics.py`, `fetch_macro_ifo.py`), retired entry points (`run_phase_a`, `run_phase_c`, `run_hist`), and retired tabs (`macro_us[_hist]`, `macro_intl[_hist]`, `macro_dbnomics[_hist]`, `macro_ifo[_hist]`) returns only intentional historical-context hits in the retirement narratives. Indicator count (92) consistent across all 9 places it appears. All 14 ToC anchors valid. Tab inventory matches `library_utils.py::SHEETS_ACTIVE_TABS`; CSV inventory matches the §1 Data-Layer Registry.

### 2.3 Rewrite `forward_plan.md` to be self-contained (drop external doc dependencies)

**Priority:** High — collapses the active contributor doc set to three (`technical_manual.md`, `forward_plan.md`, `multifreq_plan.md`).
**Status:** Done 2026-04-28 — landed in 4 commits on `claude/review-forward-plan-rQ2x9`. Outcome below.

| Step | Commit | Scope |
|---|---|---|
| 1 | (audit only) | External-doc reference punch list across `forward_plan.md` and `technical_manual.md` |
| 2 | `09073ea` | Drop "Based on:" attribution line; replace with self-contained intro paragraph; reword §3.3 Phase F handover phrasing; verify §1 paragraphs are standalone |
| 3 | `4e1e092` | Integrate `manuals/pipeline_review.md` content into new **§3.7.1 Per-Indicator Source Mapping** (12-row Phase D / FMP-rebuild table + 29-row partial-coverage / proxy table); delete the source file; rewire two §3.x cross-references |
| 4 | this commit | Mark §2.2 + §2.3 Done in-place; final cross-reference grep + zero stale-reference verification |

**Acceptance verified:**

- Zero references in `forward_plan.md` to "Project Plan 260327", "MarketDashboard_ClaudeCode_Handover", "METADATA_REDUNDANCY_REVIEW", "indicator_groups_review_UPDATED.xlsx", "the original handover", or "the historic …" outside of this completion ledger.
- `manuals/pipeline_review.md` deleted (commit `4e1e092`); durable content lives in §3.3.1 of this doc.
- The active contributor doc set is now exactly three: `forward_plan.md`, `technical_manual.md`, `multifreq_plan.md`.
- The §3.3.1 per-indicator source mapping supports the §3.1 comprehensive-surveys sub-project (BoJ Tankan, ONS, e-Stat, etc.) and any other future source-build work without needing to consult an external doc.

### 2.4 Add `concept` (and `subcategory`) columns to `macro_indicator_library.csv`

**Priority:** High — precondition for §2.5 (the indicator-explorer mirror) and structurally aligns the composite registry with the unified raw-series taxonomy.
**Status:** Done 2026-04-28 — landed in 3 commits on `claude/review-forward-plan-rQ2x9`. Outcome below.

| Step | Commit | Scope |
|---|---|---|
| 1 | (audit only) | Survey existing per-source taxonomy; propose canonical 17-concept list (12 inherited from raw-source libraries + 5 new for indicator-level composites: Equity, Cross-Asset, Volatility, Momentum, FX); user signed off including the breakeven-inflation correction (US_R4 + UK_R2 → Inflation, not Rates / Yields) |
| 2 | `d71e42d` | Add `concept` + `subcategory` columns to `data/macro_indicator_library.csv` between `sub_group` and `naturally_leading`; populate all 92 rows |
| 3 | `9a48118` | Wire `compute_macro_market.py::_load_indicator_library()` (extend `INDICATOR_META` tuple to 6 elements); `build_snapshot_df()` emits two new columns in `macro_market.csv`; `docs/build_html.py::load_indicator_meta()` returns the new keys so the explorer JS payload's `meta` dict carries them per indicator |

**Concept distribution across the 92 indicators** (14 of the 17 canonical concepts are in active use; Manufacturing / External-Trade / Consumer reserved for future indicators):

| Concept | Count | Concept | Count |
|---|---|---|---|
| Equity | 20 | FX | 4 |
| Sentiment / Survey | 14 | Labour | 3 |
| Leading Indicators | 14 | Growth | 3 |
| Rates / Yields | 8 | Inflation | 2 |
| Credit / Spreads | 7 | Volatility | 2 |
| Cross-Asset | 6 | Housing | 2 |
| Momentum | 6 | Money / Liquidity | 1 |

**Acceptance verified:**

- Every row in `macro_indicator_library.csv` has a non-empty `concept` value (zero missing across all 92 rows).
- Per `forward_plan.md` §0: zero Python literals contain a concept-string list — every concept value is in the CSV.
- The single `INDICATOR_META` consumer (`build_snapshot_df`) is updated to the new 6-tuple shape.
- `_load_indicator_library()` and `docs/build_html.py::load_indicator_meta()` both surface the new fields.
- §2.5 is now unblocked — the data is in place; only the explorer-side rendering remains.

### 2.5 Mirror the unified macro library structure in `docs/indicator_explorer.html`

**Priority:** High — user-flagged. Absorbed the previously-pending §3.8 "HTML Charting Tool Integration" item.
**Status:** Done 2026-04-28 — landed in 7 commits, then restructured in a follow-up 3-commit pass after merge feedback (the original v1 added a region/concept toggle within the existing source-based sidebar layout but didn't merge the three raw-macro sections; v2 collapses them into a single "Economic Data" section).

**v1 — initial implementation:**

| Step | Commit | Scope |
|---|---|---|
| 1 | `d8d1e45` | Normalise concept values across raw-source libraries — `Labor Market` → `Labour` (8 rows), `Credit` → `Credit / Spreads` (11 rows), OECD CLI series `Growth` → `Leading Indicators` (1 row) |
| 2 | `5fee5e8` | Server-side payload — new `INDICATOR_CONCEPT_ORDER` in `library_utils.py`; `build_macro_market` emits a parallel `groupsByConcept` tree alongside the existing region-based `groups` |
| 3 | `ce796bd` | L/C/G cycle-timing badges in every macro section — `buildSimpleSection` now passes `cycle: meta.cycle_timing`; G colour palette adjusted from red to pink (`#ff7eb6`) to match the spec |
| 4 | `cd84536` | View-mode toggle ("By Region" ↔ "By Concept") + alternate sidebar trees — covers Phase E composites (server-supplied `groupsByConcept`) and raw-macro sections (client-side regrouping via `meta.concept`/`subcategory`); checkbox state preserved across toggles |
| 5 | `5758d57` | L/C/G filter chips + country dropdown — unified `applySidebarFilters()` evaluates search + variant + cycle + country in one pass; country dropdown auto-populated from data |
| 6 | `c42d3ca` | Inline `L = Leading · C = Coincident · G = Lagging` legend beneath the cycle-filter chips |
| 7 | `d8acb73` | Mark §2.5 Done; drop source-filter mention from spec (parked) |

**v2 — restructure after merge feedback:**

| Step | Commit | Scope |
|---|---|---|
| R1 | `529b7d6` | Server payload — new `load_countries()` reader (single source of truth: `data/macro_library_countries.csv`); new `build_macro_economic()` combiner spanning every raw-macro source |
| R2 | `e38b619` | JS rework — replace 3 `buildSimpleSection` calls with 1 `buildEconomicDataSection`; By Region groups by Country (registry order via `MAIN_DATA.countries`), By Concept groups by concept → subcategory; drop the hardcoded `COUNTRY_CODES` JS literal (a §0 violation introduced by step 5); drop `build_macro_us` / `build_macro_intl` / `build_macro_survey` and `buildSimpleSection`; consolidate three legacy chart-rendering source dispatches into one `macro_economic` branch each |
| R3 | this commit | Mark §2.5 v2 Done; record what changed |

**Final sidebar layout (post v2):**
1. **Macro Market Indicators** — Phase E composites; By Region / By Concept toggle.
2. **Economic Data** — every raw-macro source merged (FRED + OECD + WB + IMF + DB.nomics + ifo); By Region groups by Country (12 codes from the registry), By Concept groups by concept → subcategory.
3. **Market Data** — yfinance comp pipeline (unchanged).

**Source filter parked.** The original spec mentioned a "source" filter (FRED / OECD / WB / IMF / DB.nomics / ifo) under the "By Concept" view. Parked during step 0 — Phase E composites read from multiple raw sources, making single-source attribution brittle. The L/C/G + country filters cover the most useful axes. If a future need surfaces, the per-series `meta.Source` is preserved and the filter is small to add.

**Architecture-rule fix recorded:** v1 step 5 introduced a hardcoded `COUNTRY_CODES = ['AUS','CAN', ...]` JS literal — a §0 violation (registry duplicated in Python instead of read from the CSV). v2 step R2 replaced it with `MAIN_DATA.countries.map(c => c.code)` driven by `data/macro_library_countries.csv`.

**Acceptance verified:** the explorer renders three top-level sections (Macro Market Indicators / Economic Data / Market Data); the "Economic Data" section's By Region view shows 12 country buckets in registry order; the By Concept view shows the canonical concepts (Rates / Inflation / Labour / etc.); cycle-timing and country filters work; existing region-based view of Macro Market Indicators is preserved.

### 2.6 Per-ticker data-freshness audit

**Priority:** High — multiple indicators have silently been forward-filling stale data for months without any flag. Live examples discovered post §2.5 v2 merge: `BSCICP03USM665S` (US Business Confidence, OECD via FRED) and `CSCICP03USM665S` (US Consumer Confidence, OECD via FRED) both stopped updating in January 2024; the unified hist's Friday spine forward-filled them for 16+ months before the staleness was visible. Any indicator built on these series has been computing on dead data without any pipeline-level warning.
**Status:** Not started.

**Goal:** every fetched series gets a per-run freshness check; the daily run logs (and ideally fails loudly on) any series that hasn't seen a fresh observation within an expected-cadence-aware tolerance window. Catches publisher discontinuations, retired series, and OECD-mirror-via-FRED freezes (the actual driver of the 2024-Jan staleness) before they corrupt downstream indicators.

**Plan:**

1. **Threshold table.** Per-frequency staleness tolerance (defaults below; per-row override allowed via a new `freshness_override_days` column in the relevant `data/macro_library_*.csv` file when a known publisher delay justifies a wider window):

   | Frequency | Default tolerance |
   |---|---|
   | Daily | 5 days |
   | Weekly | 10 days |
   | Monthly | 45 days |
   | Quarterly | 120 days |
   | Annual | 540 days |

   The `frequency` column already exists in every `data/macro_library_*.csv`; the override column is new.

2. **Standalone audit script — `freshness_audit.py`** (repo root). Reads every `data/macro_library_*.csv` library, looks up each series's last non-null observation in `data/macro_economic_hist.csv` (or `data/market_data_comp_hist.csv` for yfinance instruments), compares against today's date, and emits a sorted report grouped by status (FRESH / STALE / EXPIRED). Output: `freshness_audit.txt` plus a non-zero exit code if any STALE/EXPIRED row is found. Runnable ad-hoc.

3. **Daily CI step.** A small `if: always()` block at the end of `update_data.yml` runs `python freshness_audit.py` and pipes its output into `pipeline.log`. Exit code is captured but not fatal (workflow already handles non-fatal phase errors); the output makes the staleness visible in the committed log.

4. **Output format.** One line per stale series:
   ```
   STALE  monthly   BSCICP03USM665S   last_obs=2024-01-01   age=460d   tolerance=45d   indicators_affected=US_BUS_CONF
   ```
   The `indicators_affected` column is computed by reverse-lookup against the §3.3.1 per-indicator source mapping (which now lives in `forward_plan.md` per §2.3).

5. **Quick wins to expect from the first run.** Beyond the two examples above, expect to surface several OECD-mirror-via-FRED series that froze when OECD discontinued or renamed legacy MEI vintages. The first run is the audit; the second wave is fix-forward (route to alternative sources or remove from the library).

**Acceptance:** `python freshness_audit.py` runs cleanly on a current data snapshot and produces the report; CI step fires on every daily run with output committed in `pipeline.log`; `BSCICP03USM665S` and `CSCICP03USM665S` are explicitly named in the first STALE batch (verifying the rule fires).

### 2.7 Expand `library_manager.py` scope to validate every `data/macro_library_*.csv`

**Priority:** Medium — durable defence against future drift. Subsumes the old §3.5 (which scoped only `index_library.csv`).
**Status:** Not started.

The 7 source library CSVs are now the registry; a validator that runs locally (or weekly in CI) catches dead identifiers before they show up as runtime fetch failures. Per-source checks:

- `index_library.csv` — yfinance ticker liveness, currency present, `validation_status` consistent (this is the one §3.5 originally specified; absorbs §2.8 below).
- `macro_library_fred.csv` — FRED `/series?series_id=…` returns a valid record for every row; `country` is a known code in `macro_library_countries.csv`.
- `macro_library_oecd.csv` — every row's `oecd_key_template` resolves to a non-empty SDMX response with the listed `oecd_countries`.
- `macro_library_worldbank.csv` — WB WDI `/indicator/{wb_id}` returns a valid record.
- `macro_library_imf.csv` — IMF DataMapper indicator + entity codes are valid.
- `macro_library_dbnomics.csv` — DB.nomics `/series/{path}` returns ≥ 1 observation.
- `macro_library_ifo.csv` — `sheet_index` and `excel_col` resolve in the latest cached workbook.
- `macro_library_countries.csv` — every code referenced from a source library exists here; no orphan rows.
- `macro_indicator_library.csv` — every `id` is unique; every `id` is registered as a calculator in `compute_macro_market.py::_*_CALCULATORS`; every series referenced via `_get_col(...)` in a calculator exists as a column in `macro_economic_hist.csv`.

Output: a single `library_audit.txt` report with per-row pass/fail. Not part of the daily pipeline — run manually or via a separate weekly workflow.

**Acceptance:** running `python library_manager.py` on a clean repo prints "all libraries valid" or a precise list of bad rows with the specific failure mode for each.

### 2.8 Audit yfinance tickers in `index_library.csv`

**Priority:** Low — folded into §2.7. Listed separately here only because it was on the previous session's todo list as "PR4".
**Status:** Not started; will land as part of §2.7's `library_manager.py` build.

Validate ~390 tickers, flag dead/renamed ones, auto-mark `validation_status = "UNAVAILABLE"`, suggest replacements where obvious. No standalone PR — implementation is the `index_library.csv` arm of §2.7.

### 2.9 Generate a dated chronology from git history

**Priority:** Low — useful project history but doesn't move the pipeline forward.
**Status:** Not started; carried forward from the old §2.1.

```bash
git log --oneline --format="%ad  %s" --date=short | grep -v "Update market data + explorer"
```

Filter to significant changes (feature additions, bug fixes, schema changes, new modules). Output as either a dated chronology section in `manuals/technical_manual.md` (preferred — keeps the manual self-contained) or a standalone `manuals/chronology.md`. Update periodically as new features land.


---

## 3. New Feature Development

### 3.1 Comprehensive Business + Consumer Survey Data — sub-project

**Priority:** High — surveys are some of the most powerful leading-indicator data we can carry, but coverage today is patchy and several of the highest-signal series are proprietary or unreliable. Promote to a dedicated multi-stage sub-project rather than a series of one-off fetcher additions; absorbs the previously-pending BoJ Tankan work.
**Status:** Not started as a unified sub-project. Multiple isolated attempts to date — see "Prior attempts" below.

**Goal:** for each of the 12 countries / regions in `data/macro_library_countries.csv`, build a comprehensive set of business-confidence and consumer-confidence survey series (manufacturing PMI, services PMI, EC/OECD-equivalent business + consumer confidence balances, country-specific sentiment indices like ifo / Tankan / ZEW / GfK / Westpac / NBS). Where free, reliable, monthly+ frequency sources exist — wire them in. Where they don't — design a robust scraper or accept the gap with a documented proxy.

#### Why this is its own sub-project (not just N more `sources/*.py` modules)

- Surveys are inherently a "find-the-best-available-source-per-region" problem rather than a single-API integration. Each country has different free data infrastructure (FRED OECD-mirror for one, Eurostat for another, scraping for a third).
- We've already attempted partial coverage via FRED, DB.nomics, ifo Excel, and an Investing.com scraper PoC (rejected). Those attempts are recorded under "Prior attempts" — the lessons are durable; we don't want to re-relearn them.
- The signal value is high enough that scraper infrastructure is justified if no API exists. Any scraper here lives in `sources/` and follows the existing fetcher pattern; the freshness audit (§2.6) gives us the safety net to detect when a scraped source breaks.
- Target enumeration needs domain expertise — which surveys are worth carrying for each region. That conversation is best held offline (user + chat/cowork co-research), with the output of that work feeding the implementation queue here.

#### Target survey list — TBD via a separate user-led research job

The starting reference is **`manuals/Macro Market Indicators Reference.docx`**, which catalogues 206 macro/market indicators including most major regional surveys. The first concrete output of this sub-project is a per-country target list distilled from that doc + ad-hoc research, recorded as a CSV at `data/survey_targets.csv` (or appended as a `survey_target=TRUE` column on the existing `data/reference_indicators.csv`).

Worked example (US):
- ISM Manufacturing PMI ✓ (`ISM_MFG_PMI`, DB.nomics) — already wired
- ISM Services PMI ✓ (`ISM_SVC_PMI`, DB.nomics) — already wired
- ISM Manufacturing New Orders ✓ (`ISM_MFG_NEWORD`, DB.nomics) — already wired
- UMich Consumer Sentiment headline ✓ (`UMCSENT`, FRED) — already wired
- UMich Consumer Sentiment sub-indices (Expectations / Current Conditions) — **proprietary**, no free path identified; investigate paid feeds vs scrape vs accept gap
- Conference Board Consumer Confidence ✓ (`CSCICP03USM665S`, FRED OECD-mirror) — **CURRENTLY STALE** (frozen Jan 2024 per §2.6)
- Conference Board CEO Confidence — proprietary
- NFIB Small Business Optimism — TBD source check
- Empire State + Philly Fed + Dallas Fed regional surveys ✓ (FRED) — already wired

Same exercise needed for GBR, DEU, FRA, ITA, JPN, CHN, AUS, CAN, CHE, EA19, IND.

#### Plan (post-target-list)

Once the per-country target list exists:

1. **Source classification.** For each target, classify as `LIVE` / `FREE_API_AVAILABLE` / `SCRAPER_REQUIRED` / `PROPRIETARY`. Drives prioritised work order.
2. **`FREE_API_AVAILABLE` work.** Add rows to existing `data/macro_library_*.csv` files where the source already has a fetcher (`fred`, `dbnomics`, `oecd`, etc.). Highest ROI per hour.
3. **New source modules.** For sources with no existing fetcher (e.g. ONS, BoE, e-Stat, BoJ — see also the merged §3.3 below), build a `sources/<name>.py` module + matching `data/macro_library_<name>.csv` registry following the existing pattern (per §0 of this doc).
4. **Scraper infrastructure (if needed).** If a high-value target is only available via website scraping, build a single shared scraping framework in `sources/scraper_base.py` (rate limiting, retry, magic-byte / HTML-shape validation, Cloudflare-detection heuristics) before writing any per-site scraper. The Investing.com PoC's lessons (Cloudflare fragility, JS challenges, ToS concerns — recorded below) inform what to avoid.
5. **BoJ Tankan as concrete first new-source target.** The largest single confirmed gap is `JP_PMI1` (au Jibun Bank Mfg PMI, S&P Global proprietary). BoJ Tankan Large Manufacturers DI is the canonical free Japan business-survey signal — quarterly, range −100…+100, published via `stat-search.boj.or.jp`. DB.nomics mirror was verified empty during Phase D PoC. Implementation pattern: build `sources/boj.py` + `data/macro_library_boj.csv` along the same lines as `sources/ifo.py` (workbook / flat-file fetch with magic-byte validation); update `_calc_JP_PMI1` to use Tankan DI z-scored and resampled to the weekly Friday spine when the proprietary monthly PMI is unavailable.
6. **Acceptance per country.** Defined per the target list. Minimum bar: the country's "PMI-equivalent" (manufacturing OR composite business confidence) and "consumer-confidence" series are both LIVE and feeding at least one Phase E composite indicator.

#### Prior attempts (durable record, not to be re-relearned)

- **FMP economic calendar (Phase D Tier 3, 2026-04 PoC).** Rejected 2026-04-23 — endpoints paywalled (`/v3/economic_calendar` returns HTTP 403, `/stable/economic-calendar` returns HTTP 402) on the free tier. FMP module deleted. See §3.3 source verdicts.
- **Investing.com scraper (Phase D, 2026-04 PoC).** Rejected — fragile anti-bot protections (Cloudflare, JS challenges), frequent HTML changes, rate limiting unsuitable for nightly CI. Lessons inform any future scraper: prefer official APIs; if scraping is unavoidable, target sites without aggressive bot mitigation.
- **OECD / FRED OECD-mirror coverage.** Successfully wired ~9 country business-confidence series, but vintages frozen unpredictably — see the §2.6 freshness audit; `BSCICP03USM665S` and `CSCICP03USM665S` are confirmed examples where the OECD-mirror-via-FRED route silently went stale in Jan 2024.
- **Eurostat via DB.nomics.** ~3 EZ surveys live (`EU_ESI`, `EU_IND_CONF`, `EU_SVC_CONF`); reliable, monthly, well-maintained. Pattern to replicate where possible.
- **ifo Institute Excel-workbook scrape.** Successful pattern for German business-survey data — 26 series live via `sources/ifo.py`. Reproducible for other workbook-only publishers.
- **ZEW Mannheim sentiment (DE_ZEW1).** No free historical API — ZEW licences the archive. Confirmed proprietary 2026-04-23. Marked as a permanent gap unless a paid-feed decision is taken.
- **Caixin China Manufacturing PMI (CN_PMI2).** S&P Global proprietary. No free monthly source identified. Chinese manufacturing covered by `CN_PMI1` (OECD BCI for China) as proxy.

#### Phase D retrospective (historical context)

Phase D — the original "PMI / Survey Data" coordinator — was retired into Phase ME on 2026-04-23 (see §1 Phase ME). The Phase D pipeline scaffold is gone; what remains is a body of survey series wired through `sources/{fred,oecd,worldbank,imf,dbnomics,ifo}.py` as part of the unified `macro_economic_hist`. 10 of the original 13 Phase D indicators are LIVE; 3 proprietary holdouts (`DE_ZEW1`, `JP_PMI1`, `CN_PMI2`) return `Insufficient Data` and are documented in §1 Known Data Gaps.

**Source-per-indicator detail:** see §3.3.1 below for the FMP-rebuild resolution table and the partial-coverage / proxy / upgrade-path catalogue.

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

### 3.3 Indicator Coverage & Source Expansion

This section catalogues forward-looking work on indicator coverage: source verdicts, the gap between current coverage and the `Macro Market Indicators Reference.docx` baseline, the prioritised FRED additions, the new source modules needed, and the per-indicator source mapping. Replaces and merges the old §3.3 (Calculated Fields Expansion), §3.7 (Source Evaluation Retrospective), and §3.8 (Cycle Timing & Coverage Expansion). The largest single source-expansion track — comprehensive business + consumer surveys — has its own dedicated sub-project at §3.1; this section holds everything else.

#### Outstanding calculated fields

Several calculated fields proposed historically are not yet implemented. Some may already be covered by the 92 macro-market indicators — audit before building duplicates.

| Field | Formula | Status |
|---|---|---|
| HY/IG ratio | BAMLH0A0HYM2 / BAMLC0A0CM | Covered by US_Cr3 (HY-IG spread) |
| EMFX basket | Equal-weight CNY, INR, KRW, TWD vs USD (inverted so rising = EM FX strengthening) | Implemented 2026-04-21 as `FX_EM1` |
| EEM/IWDA ratio | EEM / URTH (MSCI World ETF in USD — functional equivalent of IWDA.L after FX adjustment) | Covered by `GL_G1` |
| MOVE proxy | 30-day realised vol on ^TNX | Not needed — `^MOVE` ticker itself is in the comp pipeline (used in `US_V2`) |
| Global PMI proxy | Equal-weight ISM + Eurozone PMI + Japan PMI | Implemented 2026-04-23 as `GL_PMI1` (4-region z-score composite) |
| Global yield curve | Average of US/DE/UK/JP 10Y-2Y spreads | Not yet implemented (US/DE/UK 10Y available; needs 2Y for DE/UK + full JP curve via §3.3 New Source Modules) |
| % stocks above 200-day MA | Per-index breadth: fraction of constituents with close > 200-day SMA. Not exposed by yfinance as a field and no free FRED/OECD feed exists; StockCharts symbols (`$SPXA200R`, `$NYA200R`, `$NDXA200R`) are proprietary. Compute in-house from constituent daily closes. Candidate indices: S&P 500 (highest signal-to-cost), Nasdaq 100, Russell 1000, FTSE 100. Naming: `US_EQ_B1` / `US_EQ_B2` etc. ("Equity - Breadth"). Adds ~500-1000 extra daily yfinance pulls per index. | Not yet implemented |

New indicators follow the CSV-driven pattern: write a `_calc_*` function, add to `REGIME_RULES` and the relevant `_*_CALCULATORS` dict, add a row to `macro_indicator_library.csv` (with `concept` + `subcategory` per §2.4 + cycle-timing per below).

#### Cycle-timing classification (L/C/G)

The `Macro Market Indicators Reference.docx` source doc catalogues 206 macro/market indicators across 6 regions (US / UK / Eurozone / Japan / China / Global), each classified by cycle timing: **Leading** (L, blue shading `#DCE7F2` — turns 3-12 months ahead of the cycle), **Coincident** (C, beige `#E8E4D9` — confirms current state), **Lagging** (G, pink `#EDE0E0` — confirms trends already in place; turns after the cycle). Colour codes were extracted programmatically from the Word document via `python-docx` and the full 206-row list lives at `data/reference_indicators.csv`.

The `cycle_timing` column was added to `data/macro_indicator_library.csv` for all 92 Phase E indicators in Stage 2 (2026-04-23). Result: **90 Leading, 2 Coincident, 0 Lagging** — the library is overwhelmingly forward-looking by design; the two coincident components are `US_JOBS3` (labour composite blending L+C+G) and `US_G6` (IP + Retail Sales). The L/C/G badges + filter are surfaced in the explorer per §2.5.

#### Source verdicts (binding)

Outcome of the 2026-04 source-evaluation cycle. Verdicts are durable — do not re-investigate without new evidence.

| Source | Verdict | Rationale |
|---|---|---|
| **FRED** | Primary US + OECD-mirror series | Adding rows to `data/macro_library_fred.csv` is zero-code. |
| **DB.nomics** | Primary for open-licensed series | Free REST, no key, no rate limit. Carries Eurostat survey + ISM + (some) BoJ. |
| **OECD SDMX** | Primary for OECD harmonised series | Multi-country fan-out; CLI / unemployment / 3-month rate. |
| **World Bank WDI** | Primary for cross-country annual macro | CPI YoY, etc. |
| **IMF DataMapper** | Primary for cross-country GDP growth | Annual real GDP growth. |
| **ifo Institute Excel** | Primary for German business surveys | Direct workbook scrape via `sources/ifo.py`; 26 series, 1991+. |
| **ECB Data Portal** (`data-api.ecb.europa.eu`) | Backup — used inline for Euro IG yield-curve point | SDMX 2.1 REST. Migrated from old `sdw-wsrest` host (PR2, 2026-04-26). |
| **Bank of Japan** (`stat-search.boj.or.jp`) | Future — see §3.1 | DB.nomics mirror is empty for Tankan; absorbed into the comprehensive surveys sub-project. |
| **UMich portal** | Defer | No official API; headline `UMCSENT` already on FRED; sub-indices high-correlated. |
| **FMP economic calendar** | Rejected (paywalled Aug 2025) | All endpoints behind paid tier. Module deleted. |
| **Trading Economics** | Skip | Paid only. Same data via DB.nomics + FRED. |
| **Investing.com** | Skip | `investpy` broken since 2023 (Cloudflare); scraping violates ToS. |
| **S&P Global / ISM direct** | Skip | No programmatic API; paid institutional subscription for sub-indices. ISM redistributed by DB.nomics. |

#### Coverage today vs the 206-row reference baseline

Cross-reference of every reference indicator from `Macro Market Indicators Reference.docx` against our pipeline (last refreshed 2026-04). Full list at `data/reference_indicators.csv` (206 rows × 10 cols).

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
| DBNOMICS_ADD/CHECK | 11 | Available or potentially available on DB.nomics |
| DERIVED | 4 | Computed indicator requiring multiple source series |
| BETTER_SOURCE_PREFERRED | 1 | Available as snapshot only; historic time series preferred |

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
- **UK** and **Japan** have the largest actionable gaps (25 and 29 respectively) — these need new source modules (ONS, BoE, e-Stat, BoJ — see "New source modules needed" below).
- **China** has the most proprietary gaps (19) — NBS data has no free foreign API. Practical coverage is limited to FRED OECD mirrors (`CHN_BUS_CONF`, `CHN_CON_CONF`).
- **Eurozone** is well-served by existing Eurostat / DB.nomics, with ECB SDW as the main new source needed.

#### Prioritised FRED additions (zero-code — add rows to `macro_library_fred.csv`)

These 20 indicators can be captured immediately by adding rows to the existing FRED library CSV. No code changes — `sources/fred.py` picks them up automatically.

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

#### New source modules needed (ranked by indicator count)

Some of these overlap with the §3.1 surveys sub-project (BoJ Statistics specifically — covered there). The rest are non-survey targets.

| Source | Indicators | Key Series | Effort |
|---|---|---|---|
| **e-Stat (Japan)** | 16 | Machinery orders, housing starts, economy watchers, retail sales, tertiary industry, coincident/leading indices, labour, household spending | Medium — free API with registration; `estat-api-client` package available |
| **ONS API (UK)** | 14 | Monthly GDP, IP, retail sales, employment, wages, CPI, claimant count, productivity, BICS | Medium — beta REST API; dataset IDs known (mgdp, iop, rsi) |
| **BoJ Statistics (Japan)** | 6 | Tankan (all variants), JGB curve, M2/M3 — see §3.1 | Low-medium — REST API; `bojpy` package wraps it |
| **BoE BOESD (UK)** | 4 | Credit conditions survey, mortgage approvals, M4 lending, UK 2Y gilt yield | Low — free interactive database with CSV download; may need scraper |
| **ECB SDW (Eurozone)** | 4 | Bank Lending Survey, M3, negotiated wages, 2Y Bund yield | Low-medium — SDMX 2.1 REST API; `sdmx1` package |
| **BIS SDMX (Global)** | 2 | Household debt/GDP, global credit impulse components | Low — SDMX API |
| **CPB (Netherlands)** | 2 | World Trade Monitor, World Industrial Production | Low — free CSV download, monthly |
| **OFR (US/Global)** | 1 | Financial Stress Index | Low — free CSV/JSON API, daily |
| **Atlanta Fed** | 1 | GDPNow | Low — JSON API, snapshot-only (append through time) |
| **Bundesbank SDMX** | 1 | Germany Factory Orders | Low — SDMX API |

**Recommended build order** (highest impact, lowest effort first):
1. FRED additions (20 series, zero code — see table above)
2. CPB + OFR (3 series, simple downloaders, high signal value)
3. ONS API (14 UK series — fills the largest single-region gap)
4. e-Stat (16 Japan series — fills the second-largest gap)
5. ECB SDW (4 EZ series — complements existing Eurostat coverage)
6. BoE BOESD (4 UK series — complements ONS)
7. BoJ Statistics (6 Japan series — overlaps with §3.1 surveys; build there)
8. BIS + Bundesbank + Atlanta Fed (4 series — lower priority)

#### Proprietary indicators (user review)

51 indicators in `data/reference_indicators.csv` are flagged PROPRIETARY. The user should review these to determine if any can be sourced via institutional access. Key categories:

- **S&P Global Flash PMIs** (3) — subscriber-only; we do **not** capture them (FMP route rejected). Coverage falls back to OECD BCI mirrors on FRED where available.
- **Conference Board composites** (4) — LEI/CLI; we use OECD CLI as substitute.
- **China NBS sub-data** (12) — property, FAI, retail sales, electricity; no free foreign API. Wind/CEIC/Bloomberg only.
- **Baltic Dry Index** (2) — Baltic Exchange; no reliable free API or yfinance ticker.
- **Sell-side cycle models** (1) — GS/BCA/TS Lombard; subscription research.
- **CBI, Lloyds, Sentix, Reuters Tankan** (5) — UK/EU business surveys with no free API. Some may be revisitable via the §3.1 surveys sub-project's scraper-infrastructure track.
- **Other** (24) — various proprietary feeds across regions.

#### 3.3.1 Per-Indicator Source Mapping

Inverse of the source-verdicts table above: for each Phase E composite that depends on a survey or proxy series, this section records the raw source it currently consumes and any upgrade path. Use it when:

- **Adding a new source** (e.g. BoJ Tankan or ONS UK series — see §3.1) — find which indicators currently depend on alternatives that the new source would replace.
- **Diagnosing why an indicator returns n/a** — trace the calculator back to the missing input.
- **Deciding whether a series can be retired** — find every indicator that reads it.

##### Survey / PMI indicators wired during the Phase D / FMP rebuild (2026-04-21 → 2026-04-23)

12 Phase E indicators were originally scoped against the FMP economic calendar. After FMP's free tier paywalled in Aug 2025 (verified 2026-04-22), the table below records the resolution. 9 are LIVE through free proxies; 3 remain proprietary (no free monthly source exists).

| Phase E ID | Description | Resolution | Status |
|---|---|---|---|
| `US_PMI1` | ISM Manufacturing PMI | DB.nomics `ISM/pmi/pm` (column `ISM_MFG_PMI`) | LIVE |
| `US_PMI2` / `US_ISM1` | ISM Manufacturing New Orders | DB.nomics `ISM/neword/in` (column `ISM_MFG_NEWORD`) — rerouted from FRED `NAPMOI` after FRED retired the series in April 2026 | LIVE |
| `US_SVC1` | ISM Services PMI | DB.nomics `ISM/nm-pmi/pm` (column `ISM_SVC_PMI`) | LIVE |
| `DE_IFO1` | ifo Business Climate | ifo Excel workbook (`sources/ifo.py`) | LIVE |
| `EU_PMI1` | EZ Manufacturing PMI | EC Industry Confidence (column `EU_IND_CONF`, DB.nomics Eurostat) — same 3 PMI questions as a proxy | LIVE (proxy) |
| `EU_PMI2` | EZ Services PMI | EC Services Confidence (column `EU_SVC_CONF`, DB.nomics Eurostat) | LIVE (proxy) |
| `UK_PMI1` | UK Manufacturing PMI | OECD BCI for UK (FRED `BSCICP02GBM460S`, column `GBR_BUS_CONF`) | LIVE (proxy, monthly) |
| `CN_PMI1` | China NBS Manufacturing PMI | OECD BCI for China (FRED `CHNBSCICP02STSAM`, column `CHN_BUS_CONF`) | LIVE (proxy) |
| `GL_PMI1` | Global PMI | Z-score-normalised 4-region composite (`ISM_MFG_PMI` + `EU_IND_CONF` + `GBR_BUS_CONF` + `CHN_BUS_CONF`) | LIVE (auto-rebuilds from components) |
| `DE_ZEW1` | ZEW Economic Sentiment | **Proprietary** — ZEW Mannheim licences archive | n/a — covered by `DE_IFO1` + `DEU_BUS_CONF` |
| `JP_PMI1` | au Jibun Bank Japan Mfg PMI | **Proprietary** — S&P Global, no monthly free source | n/a — BoJ Tankan quarterly is the future option (§3.1) |
| `CN_PMI2` | Caixin China Mfg PMI | **Proprietary** — S&P Global / Caixin | n/a — Chinese manufacturing covered by `CN_PMI1` |

##### Partial-coverage indicators (proxy in use, upgrade paths noted)

These reference indicators have partial coverage today via adjacent / standardised proxies. Rows marked **Done** landed in Stage 2 (2026-04-23); rows without a date are still actionable upgrades. Items flagged "no upgrade" are either functional matches (proxy is fine) or genuinely blocked.

| Region | Indicator | Current source | Upgrade path / status |
|---|---|---|---|
| US | UMich Consumer Sentiment — Expectations sub-index | `UMCSENT` headline only | No free path — sub-index is UMich portal only |
| US | Retail Sales (Control Group) | `RSXFS` (ex-Autos) | FRED `RSFSXMV` — zero-code row addition (listed in Prioritised FRED Additions above) |
| UK | UK Gilt Curve (10Y-2Y) | 10Y only via FRED | Add UK 2Y via BoE BOESD (New Source Modules above) |
| UK | UK CPI Inflation | FRED `GBRCPIALLMINMEI` (monthly) | **Done** — Stage 2, 2026-04-23 (was World Bank annual) |
| Eurozone | EC Consumer Confidence | FRED OECD proxy | Functional match — no upgrade |
| Eurozone | INSEE Business Climate | FRED OECD proxy | Functional match — no upgrade |
| Eurozone | ISTAT Business Confidence | FRED OECD proxy | Functional match — no upgrade |
| Eurozone | Bund Curve (10Y-2Y) | 10Y only via FRED | Add DE 2Y via ECB SDW / Bundesbank (New Source Modules above) |
| Eurozone | Eurozone GDP | IMF annual | Eurostat quarterly via DB.nomics |
| Eurozone | Euro Area Unemployment | OECD monthly | Functional match — no upgrade |
| Eurozone | HICP Inflation | FRED `EA19CPALTT01GYM` (monthly) | **Done** — Stage 2, 2026-04-23 (was World Bank annual) |
| Eurozone | Industrial Production | DB.nomics Eurostat (column `EZ_IND_PROD`) | **Done** — Stage 2, 2026-04-23 |
| Eurozone | Retail Sales | DB.nomics Eurostat (column `EZ_RETAIL_VOL`) | **Done** — Stage 2, 2026-04-23 |
| Eurozone | Employment | DB.nomics Eurostat (column `EZ_EMPLOYMENT`, quarterly) | **Done** — Stage 2, 2026-04-23 |
| Eurozone | Euro IG corporate bond yield (component of `EU_Cr1` IG spread) | None — FRED `BAMLEC0A0RMEY` invalid; row removed 2026-04-27 | See §1 Known Data Gaps for candidate sources (DB.nomics ECB MIR / iShares EUR IG ETF proxy / Bundesbank SDMX). EU_Cr1 returns n/a until wired |
| Japan | Consumer Confidence Index | FRED OECD proxy | Functional match — no upgrade |
| Japan | Real GDP | IMF annual | e-Stat quarterly (New Source Modules above) |
| Japan | Unemployment Rate | OECD monthly | Functional match — no upgrade |
| Japan | Core CPI | FRED `JPNCPIALLMINMEI` (monthly) | **Done** — Stage 2, 2026-04-23 (was World Bank annual) |
| Japan | Mfg PMI (`JP_PMI1`) | None (proprietary; n/a) | BoJ Tankan quarterly DI (§3.1) |
| China | Sovereign Curve (10Y-2Y) | 10Y only via FRED (currently NaN — China 10Y itself unsourced) | 2Y is proprietary (ChinaBond/Wind) — accept the gap |
| China | China 10Y govt bond yield | None — FRED carries only short-term `IR3TTS01CNM156N` | Future: DB.nomics PBoC mirror (see §1 Known Data Gaps) |
| China | Real GDP | IMF annual | Direct PBoC scrape — accept gap (Wind/CEIC otherwise) |
| China | CPI Inflation | FRED `CHNCPIALLMINMEI` (monthly) | **Done** — Stage 2, 2026-04-23 (was World Bank annual) |
| China | Industrial Production | FRED `CHNPRINTO01IXPYM` (monthly) | **Done** — Stage 2, 2026-04-23 |
| China | Urban Surveyed Unemployment | OECD monthly | Functional match — no upgrade |
| Global | Global Mfg PMI | `GL_PMI1` 4-region composite (above) | True JPM Global PMI is proprietary — keep proxy |
| Global | Bloomberg Commodity Index | `DBC` ETF proxy | BCOM itself proprietary — keep DBC |
| Global | Goldman Sachs FCI | `NFCI` (Chicago Fed) substitute | GS FCI proprietary — keep NFCI |

### 3.4 Sheets Export Audit (Phase G)

**Status (2026-04-21):** Most items completed — see Phase G details in section 1. The full audit found and fixed three issues: missing protected-tab guards in 3 of 4 writer modules, an inline `TABS_TO_DELETE` constant in `fetch_data.py` that drifted from the `PROTECTED_TABS` set in `fetch_hist.py`, and a narrow `A:Z` clear range in `fetch_macro_us_fred.py` that would leave stale data if the schema grew past column Z. All three fixed by consolidating the shared tab state into `library_utils.py` (`SHEETS_PROTECTED_TABS`, `SHEETS_ACTIVE_TABS`, `SHEETS_LEGACY_TABS_TO_DELETE`) and wiring every writer to it.

**Remaining (low value):**
- Record Sheets GIDs for each of the 9 active tabs in `technical_manual.md` (housekeeping; only useful if downstream consumers need stable GID links).
- Build an automated drift check: compare the tab set in the Sheet against `SHEETS_ACTIVE_TABS ∪ SHEETS_LEGACY_TABS_TO_DELETE` and flag extras. Useful only if ad-hoc tabs are being created outside the pipeline.

### 3.5 Library Manager Utility

**Priority:** Low — developer tooling. **Scope expanded** in §2.7: the original `index_library.csv`-only design has been generalised to validate every `data/macro_library_*.csv` plus `macro_indicator_library.csv`. See §2.7 for the current scope and acceptance criteria; the original `index_library.csv` checks below are retained as the yfinance-arm of that broader plan.

Create `library_manager.py` — a standalone utility. For the `index_library.csv` arm specifically:

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

### 3.7 PE Ratio Integration

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

### 3.8 Retire the Simple Pipeline

**Priority:** Medium — code-cleanliness and maintenance-burden reduction. The simple pipeline is currently frozen but still adds ~66 hardcoded instruments + a `sentiment_data` tab that the rest of the codebase no longer touches.
**Status:** Not started. Blocked on confirming downstream consumer usage.

**Context:** the simple pipeline is the original 66-instrument daily snapshot in `fetch_data.py`. It writes the protected `market_data` tab (GID `68683176`) and the `sentiment_data` tab. Its only known consumer is `trigger.py`, which runs at 06:15 London on a local Windows machine and reads `market_data` only. The comp pipeline (~390 instruments) covers a strict superset of the simple pipeline's instrument set, so the simple pipeline duplicates fetch traffic and code paths that have no other reason to exist.

**Plan:**

1. **Confirm `trigger.py` is still in active use.** Owner check: is the 06:15 Windows job still running? If retired, skip to Step 4.
2. **If still in use:** decide between (a) migrating `trigger.py` to read `market_data_comp` (filter to the 66 instruments it cares about), or (b) keeping `market_data` populated by a thin facade — `fetch_data.py` writes a subset view of `market_data_comp` after the comp run, dropping the dedicated simple-pipeline fetcher.
3. **Decide on `sentiment_data`.** Audit downstream readers: nothing in this repo references it. Confirm with the owner that it's safe to drop — if so, mark it for deletion (move to `SHEETS_LEGACY_TABS_TO_DELETE`).
4. **Delete the simple-pipeline code path.** Remove the 66-instrument hardcoded list (Fear & Greed, VIX term structure, FX majors, sector ETFs, FRED yields). Remove the simple-snapshot writer. `fetch_data.py` becomes a comp-pipeline-only module.
5. **Update `library_utils.py`.** Drop `market_data` from `SHEETS_PROTECTED_TABS` if the tab is being retired (or keep protected if Step 2(b) facade is adopted). Remove `sentiment_data` from `SHEETS_PROTECTED_TABS` and add to `SHEETS_LEGACY_TABS_TO_DELETE`.
6. **Update `manuals/technical_manual.md`** alongside §2.2 — drop the "Simple Pipeline" sub-section in §1 / §4 and the related tab descriptions.

**Acceptance:**

- `fetch_data.py` no longer carries a separate simple-pipeline code path.
- `market_data` either deleted or thin-facade-driven from `market_data_comp` (per Step 2 outcome).
- `sentiment_data` retired (in `SHEETS_LEGACY_TABS_TO_DELETE`).
- Daily run wall-clock time decreases by the simple-pipeline budget (~30-60 seconds of yfinance / FRED calls eliminated).
- `trigger.py` continues to function (if still in use) or is acknowledged as retired.

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
