# Market Dashboard — Forward Plan

> Last updated: 2026-04-28

This is the project's forward-looking working doc. §0 sets the architecture rules every Claude session must read before touching data-layer code. §1 is the standalone phase / data-layer summary. §2 is the prioritised work queue. §3 captures feature roadmap items not yet on the queue. §4 holds the project chronology task. §5 cross-references `multifreq_plan.md` for the larger Phase 2 (multi-frequency) rebuild. The current code state lives in `manuals/technical_manual.md`; this doc and the technical manual are the only two contributor docs you need.

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
4. [Project Chronology](#4-project-chronology)
5. [Multi-Frequency Pipeline (Phase 2)](#5-multi-frequency-pipeline-phase-2)

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

Phase D's "Tier 3 FMP calendar" track was paywalled and rejected on 2026-04-23 — the FMP module is also deleted. See §3.2 for the Phase D retrospective.

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

92 composite indicators computed from the unified `macro_economic_hist` (per §1 Phase ME) plus the comp-pipeline market data. Each indicator produces: raw value, 156-week (3-year) rolling z-score, regime classification, forward regime signal (`improving`/`stable`/`deteriorating`, with optional `[leading]` suffix), and z-score trend diagnostics (`intensifying` / `fading` / `reversing` / `stable`) against 1w, 4w, 13w lookbacks. A `cycle_timing` column (L/C/G) classifies each indicator's position in the business cycle (90 Leading, 2 Coincident, 0 Lagging — see §3.4). Metadata is a single source of truth in `data/macro_indicator_library.csv` — no hardcoded `INDICATOR_META` dict in Python. The library carries `concept` + `subcategory` columns populated against a canonical 17-concept taxonomy (Equity, Rates / Yields, Credit / Spreads, Inflation, Sentiment / Survey, Leading Indicators, Growth, Labour, Cross-Asset, Volatility, Momentum, FX, Money / Liquidity, Housing, Manufacturing, External / Trade, Consumer); these surface in `macro_market.csv` and the explorer payload. Outputs `macro_market` (snapshot) and `macro_market_hist` (weekly history). As of the 2026-04-26 supplemental refactor Phase E contains zero direct API contact — every series the calculators read is provisioned through the unified hist; PR3 (2026-04-26) cleared the build-phase `DataFrame is highly fragmented` warnings, and the 2026-04-27 fix-forward cleared the output-phase ones plus the EU_Cr1 / `BAMLEC0A0RMEY` regression. EU_Cr1 (Euro IG spread) returns n/a until a free Euro IG corporate yield source is wired (see §1 Known Data Gaps); EU_Cr2 (Euro HY spread, reads `BAMLHE00EHYIOAS`) covers the Euro-HY regime as a separate indicator.

`docs/indicator_explorer.html` (built by `docs/build_html.py`) renders the library through a three-section sidebar — **Macro Market Indicators** (Phase E composites, By Region ↔ By Concept toggle), **Economic Data** (every raw-macro source merged, By Country ↔ By Concept toggle), **Market Data** (yfinance comp pipeline, Local ↔ USD variant). Filter pipeline supports text search, market-data variant, L/C/G cycle-timing chips, and country dropdown. Country list is read from `data/macro_library_countries.csv` (no hardcoded JS literal — per §0).

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

Outstanding (low value): record Sheets GIDs for each active tab in `manuals/technical_manual.md`; build an automated "tab drift" audit that flags tabs in the Sheet but not in `SHEETS_ACTIVE_TABS ∪ SHEETS_LEGACY_TABS_TO_DELETE`.

Batch writes (10k rows/call) are only implemented in `fetch_hist.py` — the largest tab (`market_data_comp_hist`, ~9,000 rows) sits within the Sheets API's single-call payload limit at current column count, so no other writer has hit a batching need yet. Revisit if column count grows significantly.

#### Phase H — Daily Integrated Audit — Done (2026-04-28)

`data_audit.py` runs as the post-fetch / post-build step in the daily GitHub Actions workflow. Three sections produced into `data_audit.txt` (full report) + `audit_comment.md` (Markdown for the GitHub Issue comment):

- **Section A — Fetch outcomes.** Scrapes `pipeline.log` for yfinance dead tickers (cross-checked against `market_data_comp_hist.csv` to filter transient warnings) and FRED final failures (only the `— skipping` suffix; retried-then-recovered errors are filtered out).
- **Section B — Static checks.** Country-code orphans, indicator-id uniqueness, calculator registration, `_get_col(...)` column existence on the unified hist.
- **Section C — Value-change staleness.** Walks every column of `macro_economic_hist.csv` and flags series whose last *value change* is older than the per-row tolerance. Tolerances come from `data/freshness_thresholds.csv` (Daily 5d / Weekly 10d / Monthly 45d / Quarterly 120d / Annual 540d) with a per-row `freshness_override_days` override on every `data/macro_library_*.csv`.

A "Post daily audit to perpetual GitHub Issue" workflow step posts `audit_comment.md` to a `daily-audit`-labelled GitHub Issue every day. The first line of the comment is the one-sentence ISSUE/CLEAN summary; collapsible detail follows. GitHub's native notification email gives the daily heartbeat without any SMTP secrets.

Acceptance findings from the first run (2026-04-28) are the open backlog at §3.1.

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
| `reference_indicators.csv` | 206 | Reference (gap audit) | §3.4 cross-reference; not consumed by the runtime pipeline |

**Read order in `fetch_macro_economic.py`:** `countries → fred → oecd → worldbank → imf → dbnomics → ifo`. Each `sources/*.py` exposes `load_library() -> list[dict]` returning the unified indicator schema (`source`, `source_id`, `col`, `name`, `country`, `category`, `subcategory`, `concept`, `cycle_timing`, `units`, `frequency`, `notes`, `sort_key`).

**Library validity** is now covered by Phase H — the daily integrated audit captures HTTP errors + dead tickers + schema-drift static checks during the existing fetch (no separate probe needed).

### Known Data Gaps (consolidated, 2026-04-26)

These are cases where a planned series is unavailable from any free source we accept. Documented here so they aren't re-investigated repeatedly.

| Gap | Impact | Resolution |
|---|---|---|
| **China 10-Year government bond yield** | `AS_CN_R1` (China–US 10Y spread) returns NaN. FRED only carries the short-term `IR3TTS01CNM156N`; the OECD MEI long-term-rate dataset has no CN series. | Future: route a CN 10Y series via DB.nomics (PBoC / ChinaBond mirror) into the unified hist as `CHN_GOVT_10Y` — calculator already reads that column name. |
| **Euro IG corporate effective yield** (target series: ICE BofA Euro Corporate Index Effective Yield) | `EU_Cr1` (Euro IG spread = corp yield − ECB AAA 10Y govt yield) returns NaN. FRED `BAMLEC0A0RMEY` was probed but 400s on every call; ECB SDW does not publish a free aggregate Euro IG yield series; iBoxx EUR Corporate is paywalled. | Future: investigate (a) DB.nomics ECB MIR (bank lending rates to non-financial corps — different instrument but free + monthly + long history), (b) iShares EUR IG Corp Bond ETF (`IEAC.L` / `LQDE.L`) distribution-yield proxy via yfinance, or (c) Bundesbank SDMX corporate-bond yield series. ECB AAA 10Y govt-yield half is already wired in `fetch_ecb_euro_ig_spread()` — only the corp-yield half needs sourcing. EU_Cr1 returns n/a until then; no HY substitute (Euro HY is its own indicator, EU_Cr2). |
| **`BSCICP02JPM460S` / `BSCICP02CNM460S`** (OECD Business Confidence — Japan / China on FRED) | Don't exist on FRED. | Japan covered by `JP_PMI1` (proprietary, returns Insufficient Data); China covered by `CHNBSCICP02STSAM` (different ID). |
| **`DE_ZEW1`** (ZEW Economic Sentiment) | Returns Insufficient Data. ZEW Mannheim licences the archive; no free API. | Substitute: German sentiment is covered by `DE_IFO1` + `DEU_BUS_CONF`. |
| **`JP_PMI1`** (au Jibun Bank Japan Manufacturing PMI) | Returns Insufficient Data. S&P Global proprietary, no monthly free source. | Future partial fix: BoJ Tankan quarterly DI via direct fetcher — covered as a concrete first new-source target in §3.2 (comprehensive surveys sub-project). |
| **`CN_PMI2`** (Caixin China Manufacturing PMI) | Returns Insufficient Data. S&P Global proprietary. | Substitute: Chinese manufacturing is covered by `CN_PMI1` (OECD BCI for China). |
| **OECD CLI for EA19 / CHE** | Not published by OECD. | `compute_macro_market.py` uses DEU+FRA equal-weight as the Eurozone CLI proxy. |
| **`NAPMOI`** (FRED ISM new orders) | Retired by FRED in April 2026 (HTTP 400 from late April onwards). | `US_ISM1` reads `ISM_MFG_NEWORD` from DB.nomics via the unified hist (PR2, 2026-04-26). |
| **`CHN_PPI`** (FRED `CHNPPIALLMINMEI`) | Retired by FRED. | Removed from `macro_library_fred.csv` (PR1, 2026-04-25); no Phase E indicator currently depends on it. |
| **Investing.com / Trading Economics / S&P Global direct / FMP economic calendar** | Evaluated and rejected: scraping fragility (Cloudflare), paid-only APIs, FMP endpoints paywalled August 2025. | Do not revisit. |


---

## 2. Resume Here — Priority Tasks

The 2026-04-22 → 2026-04-28 work cluster (sources/ refactor → unified Phase ME → architecture-preference rules → supplemental-FRED CSV-ification → fragmentation cleanup → concept/subcategory taxonomy → indicator-explorer restructure → daily integrated audit) has been delivered end-to-end; durable outcomes are documented in §1 Phase Summary and `manuals/technical_manual.md`.

**Active priority is §3.1** — act on the audit findings (29 EXPIRED series, 22 dead yfinance tickers, 1 broken `_get_col` reference). Until that backlog is worked down, the daily audit issue (§1 Phase H) will continue to surface the same flags.

---

## 3. New Feature Development

### 3.1 Act on audit findings — remediation backlog

**Priority:** High — Phase H's daily integrated audit (see §1) now surfaces every broken / stale / dead-ticker case in a single committed log, but the audit *reports*; it doesn't *fix*. This section is the rolling remediation backlog. Until each finding is triaged, the audit comment on the perpetual `daily-audit` GitHub Issue will continue to flag the same failures.
**Status:** Backlog open. First-run baseline captured 2026-04-28 — counts are the starting state.

**First-run baseline (2026-04-28):**

- Section A (fetch outcomes): **22 truly-dead yfinance tickers**, 0 persistent FRED HTTP errors, a handful of informational ECB/fallback notices.
- Section B (static checks): **1 issue** — `_get_col(...,'CHN_GOVT_10Y')` referenced in `_calc_AS_CN_R1` but column absent from the unified hist (matches the documented China-10Y data gap in §1; not actionable until a free CN 10Y source is found).
- Section C (value-change staleness): **29 EXPIRED** + **46 STALE** = 75 series flagged.

#### Sub-track 1 — Triage the 29 EXPIRED series

For each EXPIRED row, classify into one of four resolutions:

| Resolution | When to apply | Action |
|---|---|---|
| **Reroute** | A working alternative source exists (e.g. `EA_HICP` from FRED OECD-mirror is dead, but `EA19CPALTT01GYM` is the live monthly version) | Update `data/macro_library_*.csv` to swap source IDs; update any `_get_col(...)` reference in `compute_macro_market.py`; remove the dead row. |
| **Remove** | The publisher genuinely retired the series and no replacement is meaningful | Delete the row from the relevant `data/macro_library_*.csv`; if a Phase E indicator depended on it, accept the n/a and document in §1 Known Data Gaps. |
| **Widen override** | The publisher genuinely lags but data is still arriving on a longer cadence | Set `freshness_override_days` on that row to a value that covers the actual cadence + a small margin. |
| **Defer** | The series is in §1 Known Data Gaps and replacement work is in progress (e.g. China 10Y via DB.nomics) | No CSV edit; the audit continues to surface it as a forcing function. |

The 29 EXPIRED series sorted by age (oldest first):

| Age | Column | Source | Series ID | Last obs | Likely resolution |
|---|---|---|---|---|---|
| 6353d (~17y) | `JPN_POLICY_RATE` | FRED | `IRSTCB01JPM156N` | 2008-12 | Remove or reroute (BoJ direct via §3.2 surveys sub-project) |
| 3826d (~10y) | `CHN_POLICY_RATE` | FRED | `IRSTCB01CNM156N` | 2015-11 | Remove or reroute (PBoC LPR series) |
| 3553d (~9y) | `GBR_BANK_RATE` | FRED | `BOERUKM` | 2016-08 | Reroute to BoE BOESD `IUDBEDR` (via §3.4 New Source Modules) |
| 2461d (~6y) | `CHN_M2` | FRED | `MYAGM2CNM189N` | 2019-08 | Reroute via DB.nomics PBoC mirror or remove |
| 1208d (~3y) | `EA_HICP` | FRED | `EA19CPALTT01GYM` | 2023-01 | Reroute to live `EA19CPALTT01GYM` row (already in library; this row is the OECD-mirror duplicate) |
| 907d (~2.5y) | `CHN_IND_PROD` | FRED | `CHNPRINTO01IXPYM` | 2023-11 | Reroute via NBS or remove |
| 844d (~2y) | `CSCICP03USM665S` | FRED | `CSCICP03USM665S` | 2024-01 | Reroute to Conference Board direct or remove (already covered by `UMCSENT`) |
| 844d | `BSCICP03USM665S` | FRED | `BSCICP03USM665S` | 2024-01 | Reroute via §3.4 New Source Modules (CB Business Confidence) |
| 844d | `CONSUMER_CONF` | FRED | `CSCICP03EZM665S` | 2024-01 | Reroute or remove |
| 788d (~2y) | `DEU_IND_PROD` | FRED | `DEUPROINDMISMEI` | 2024-03 | Reroute to Bundesbank SDMX (§3.4) |
| 788d | `JPN_IND_PROD` | FRED | `JPNPROINDMISMEI` | 2024-03 | Reroute to e-Stat (§3.4) |
| 319d | `EA_DEPOSIT_RATE` | FRED | `ECBDFR` | 2025-06 | Investigate — ECB may have published more recently (override or reroute to ECB Data Portal direct) |
| 235d | `ISM_SVC_PMI` | DB.nomics | `ISM/nm-pmi/pm` | 2025-09 | DB.nomics mirror lag; widen override to 60d |
| 144d × 6 | `CHN_IMPORTS`, `CHN_EXPORTS`, `GBR_UNEMPLOYMENT`, `EZ_IND_PROD`, `EZ_RETAIL_VOL`, `Eurostat employment` | various | various | 2025-12 | Publisher lag; widen override to ~150d |
| 116d × 7 | `PERMIT`, `FEDFUNDS`, `CMRMTSPL`, `FRA_UNEMPLOYMENT`, `DEU_UNEMPLOYMENT`, `EU_ESI`, `EU_IND_CONF`, `EU_SVC_CONF`, `ISM_MFG_PMI`, `ISM_MFG_NEWORD` | various | various | 2026-01 | Probably publisher lag at end-of-period; verify and widen override or reroute |
| 11d | `BAMLC0A0CM` | FRED | daily | 2026-04-17 | 11d on a 5d daily threshold = recent publisher pause; verify next run |

Triage to be done in batches; each `data/macro_library_*.csv` edit + any `_get_col(...)` rewire ships as a separate small commit.

#### Sub-track 2 — STALE override pass

The 46 STALE series (1×–2× tolerance) are mostly publishers genuinely lagging by one publication cycle. For each, decide: is this lag *normal* for this publisher? If yes, set `freshness_override_days` to absorb. The audit's STALE bucket then only contains genuinely-late publishers, not normal cadence.

Bulk pass — should be a single CSV-edit commit covering most rows. Likely overrides:
- Quarterly series (`ULCNFB`, `CP`, `EZ_EMPLOYMENT`): override 180d (publisher lag is typically 1 full quarter).
- Monthly series at 53-81d age: override 75d (publisher 1.5-cycle lag is normal for many BLS / OECD / FRED-mirror series).

#### Sub-track 3 — `validation_status` write-back for `index_library.csv`

Currently `data_audit.py` *reports* the 22 dead yfinance tickers but doesn't write back to the registry. Extend the audit (or a paired tool `library_writeback.py`) so dead tickers automatically get `validation_status = "UNAVAILABLE"` in `index_library.csv` after N consecutive days of failure. This was the residual item from the (now-removed) standalone library-manager utility plan, which was superseded by Phase H's daily audit.

Design:
- Track a per-ticker "consecutive-fail" counter in a small CSV `data/yfinance_failure_streaks.csv` (TBD design — could just be `(ticker, last_seen_date, consecutive_fail_days)`).
- After N=14 consecutive days of being on the dead-ticker list, set `validation_status = "UNAVAILABLE"` in `index_library.csv` and post a one-line note in the audit comment.
- Manual override always wins (operator can re-set `CONFIRMED` after a real fix).

#### Sub-track 4 — Replace dead yfinance tickers where alternatives exist

**Status:** Done 2026-04-28 — all 22 dead tickers triaged. The next pipeline run will regenerate `pipeline.log` without these tickers and Section A of the daily audit will clean up automatically.

The 22 dead tickers (first-run snapshot):

```
ISFA.L · SENSEXBEES.NS · ^CNXSC · ^RMCCG · ^RMCCV · ^SP500-253020 · ^SP500-351030
^SP500-601010 · ^SP500G · ^SP500V · ^SX3P · ^SX4P · ^SX6P · ^SX7E · ^SX8P · ^SXDP
^SXEP · ^SXKP · ^SXNP · ^TOPX · ^TSXV · ^TX60
```

**Disposition (per `data/removed_tickers.csv`):**

- **17 PR-blanks (tr_retained)** — TR ETF proxy on the same row remained working in the audit, so the PR field was blanked and `data_source` flipped to `yfinance TR`. Covers all 9 STOXX 600 sectors (TR proxies `EXH1/3/4/9.DE`, `EXI5.DE`, `EXV1/2/3/4.DE`); ^SP500G→IVW, ^SP500V→IVE, ^RMCCG→IWP, ^RMCCV→IWS; ^TOPX→1306.T, ^TX60→XIU.TO, ^TSXV→XCS.TO; ^CNXSC→SMALLCAP.NS.
- **2 TR-blanks (pr_retained)** — `ISFA.L` (TR for FTSE All-Share, PR `^FTAS` retained); `SENSEXBEES.NS` (TR for S&P BSE Sensex, PR `^BSESN` retained).
- **3 row removals (none)** — `^SP500-253020`, `^SP500-351030`, `^SP500-601010`. No TR proxy was configured, and grep confirmed no Phase E indicator references them by name. No calculator hashing-out required.

**Removal ledger.** Every ticker removed (or PR/TR field cleared) under this sub-track is logged to `data/removed_tickers.csv`. The ledger is the single source of truth for *all* library changes (removals, reroutes, additions) — not just sub-track 4. Schema: `date_removed, action (removed|rerouted|added), ticker, ticker_field, library_name, source_csv, reason, audit_run_date, replacement_status (none|tr_retained|pr_retained|deferred|n/a), target_identifier, notes`. Removal rules (agreed 2026-04-28):

- PR dead, TR working & correctly mapped → blank the PR field, keep the row, log `replacement_status=tr_retained`.
- TR dead, PR working & correctly mapped → blank the TR field, keep the row, log `replacement_status=pr_retained`.
- Both PR and TR dead → remove the entire row, log `replacement_status=none`. Any `_calc_*` indicator referencing the removed `name` is hashed out with a one-line `# DISABLED <date>: source ticker removed, see removed_tickers.csv` comment until a replacement is approved (proxies are NEVER auto-wired without explicit user approval).

Hist-file column drops are handled by `library_sync.py` — the source-of-truth library CSV is the only file edited by hand; the sync utility prunes orphan columns from `data/market_data_comp_hist.csv` and archives them under `data/_archived_columns/`. `data_audit.py`'s static-checks section reports any `_hist.csv` columns that aren't present in their source-of-truth library CSV (registry drift). Drift after the 2026-04-28 triage: 0.

**Outstanding gaps (deferred — proxies require explicit approval per §3.5).** All 17 PR-blanked rows now rely solely on the TR ETF proxy; the underlying index PR series is gone from yfinance for the foreseeable future. Where a replacement PR ticker becomes available (e.g. via §3.5 Community Datasets Review) the row's `ticker_yfinance_pr` can be re-populated.

#### Acceptance

- After one full triage pass on the EXPIRED list: every row classified and the audit's EXPIRED bucket reflects only series in active-fix or accepted-gap state.
- After the STALE override pass: the audit's STALE bucket is small (<10 series) and contains only genuine publisher misbehaviour.
- `index_library.csv` `validation_status` reflects the audit's dead-ticker view (write-back live).
- Daily audit comment routinely reads `**ALL CLEAN**` or contains only single-digit issue counts.

### 3.2 Comprehensive Business + Consumer Survey Data — sub-project

**Priority:** High — surveys are some of the most powerful leading-indicator data we can carry, but coverage today is patchy and several of the highest-signal series are proprietary or unreliable. Promote to a dedicated multi-stage sub-project rather than a series of one-off fetcher additions; absorbs the previously-pending BoJ Tankan work.
**Status:** Not started as a unified sub-project. Multiple isolated attempts to date — see "Prior attempts" below.

**Goal:** for each of the 12 countries / regions in `data/macro_library_countries.csv`, build a comprehensive set of business-confidence and consumer-confidence survey series (manufacturing PMI, services PMI, EC/OECD-equivalent business + consumer confidence balances, country-specific sentiment indices like ifo / Tankan / ZEW / GfK / Westpac / NBS). Where free, reliable, monthly+ frequency sources exist — wire them in. Where they don't — design a robust scraper or accept the gap with a documented proxy.

#### Why this is its own sub-project (not just N more `sources/*.py` modules)

- Surveys are inherently a "find-the-best-available-source-per-region" problem rather than a single-API integration. Each country has different free data infrastructure (FRED OECD-mirror for one, Eurostat for another, scraping for a third).
- We've already attempted partial coverage via FRED, DB.nomics, ifo Excel, and an Investing.com scraper PoC (rejected). Those attempts are recorded under "Prior attempts" — the lessons are durable; we don't want to re-relearn them.
- The signal value is high enough that scraper infrastructure is justified if no API exists. Any scraper here lives in `sources/` and follows the existing fetcher pattern; Phase H's daily audit gives us the safety net to detect when a scraped source breaks.
- Target enumeration needs domain expertise — which surveys are worth carrying for each region. That conversation is best held offline (user + chat/cowork co-research), with the output of that work feeding the implementation queue here.

#### Target survey list — TBD via a separate user-led research job

The starting reference is **`manuals/Macro Market Indicators Reference.docx`**, which catalogues 206 macro/market indicators including most major regional surveys. The first concrete output of this sub-project is a per-country target list distilled from that doc + ad-hoc research, recorded as a CSV at `data/survey_targets.csv` (or appended as a `survey_target=TRUE` column on the existing `data/reference_indicators.csv`).

Worked example (US):
- ISM Manufacturing PMI ✓ (`ISM_MFG_PMI`, DB.nomics) — already wired
- ISM Services PMI ✓ (`ISM_SVC_PMI`, DB.nomics) — already wired
- ISM Manufacturing New Orders ✓ (`ISM_MFG_NEWORD`, DB.nomics) — already wired
- UMich Consumer Sentiment headline ✓ (`UMCSENT`, FRED) — already wired
- UMich Consumer Sentiment sub-indices (Expectations / Current Conditions) — **proprietary**, no free path identified; investigate paid feeds vs scrape vs accept gap
- Conference Board Consumer Confidence ✓ (`CSCICP03USM665S`, FRED OECD-mirror) — **CURRENTLY STALE** (frozen Jan 2024 per the Phase H daily audit)
- Conference Board CEO Confidence — proprietary
- NFIB Small Business Optimism — TBD source check
- Empire State + Philly Fed + Dallas Fed regional surveys ✓ (FRED) — already wired

Same exercise needed for GBR, DEU, FRA, ITA, JPN, CHN, AUS, CAN, CHE, EA19, IND.

#### Plan (post-target-list)

Once the per-country target list exists:

1. **Source classification.** For each target, classify as `LIVE` / `FREE_API_AVAILABLE` / `SCRAPER_REQUIRED` / `PROPRIETARY`. Drives prioritised work order.
2. **`FREE_API_AVAILABLE` work.** Add rows to existing `data/macro_library_*.csv` files where the source already has a fetcher (`fred`, `dbnomics`, `oecd`, etc.). Highest ROI per hour.
3. **New source modules.** For sources with no existing fetcher (e.g. ONS, BoE, e-Stat, BoJ — see also the merged §3.4 below), build a `sources/<name>.py` module + matching `data/macro_library_<name>.csv` registry following the existing pattern (per §0 of this doc).
4. **Scraper infrastructure (if needed).** If a high-value target is only available via website scraping, build a single shared scraping framework in `sources/scraper_base.py` (rate limiting, retry, magic-byte / HTML-shape validation, Cloudflare-detection heuristics) before writing any per-site scraper. The Investing.com PoC's lessons (Cloudflare fragility, JS challenges, ToS concerns — recorded below) inform what to avoid.
5. **BoJ Tankan as concrete first new-source target.** The largest single confirmed gap is `JP_PMI1` (au Jibun Bank Mfg PMI, S&P Global proprietary). BoJ Tankan Large Manufacturers DI is the canonical free Japan business-survey signal — quarterly, range −100…+100, published via `stat-search.boj.or.jp`. DB.nomics mirror was verified empty during Phase D PoC. Implementation pattern: build `sources/boj.py` + `data/macro_library_boj.csv` along the same lines as `sources/ifo.py` (workbook / flat-file fetch with magic-byte validation); update `_calc_JP_PMI1` to use Tankan DI z-scored and resampled to the weekly Friday spine when the proprietary monthly PMI is unavailable.
6. **Acceptance per country.** Defined per the target list. Minimum bar: the country's "PMI-equivalent" (manufacturing OR composite business confidence) and "consumer-confidence" series are both LIVE and feeding at least one Phase E composite indicator.

#### Prior attempts (durable record, not to be re-relearned)

- **FMP economic calendar (Phase D Tier 3, 2026-04 PoC).** Rejected 2026-04-23 — endpoints paywalled (`/v3/economic_calendar` returns HTTP 403, `/stable/economic-calendar` returns HTTP 402) on the free tier. FMP module deleted. See §3.4 source verdicts.
- **Investing.com scraper (Phase D, 2026-04 PoC).** Rejected — fragile anti-bot protections (Cloudflare, JS challenges), frequent HTML changes, rate limiting unsuitable for nightly CI. Lessons inform any future scraper: prefer official APIs; if scraping is unavoidable, target sites without aggressive bot mitigation.
- **OECD / FRED OECD-mirror coverage.** Successfully wired ~9 country business-confidence series, but vintages frozen unpredictably — see Phase H's daily audit; `BSCICP03USM665S` and `CSCICP03USM665S` are confirmed examples where the OECD-mirror-via-FRED route silently went stale in Jan 2024.
- **Eurostat via DB.nomics.** ~3 EZ surveys live (`EU_ESI`, `EU_IND_CONF`, `EU_SVC_CONF`); reliable, monthly, well-maintained. Pattern to replicate where possible.
- **ifo Institute Excel-workbook scrape.** Successful pattern for German business-survey data — 26 series live via `sources/ifo.py`. Reproducible for other workbook-only publishers.
- **ZEW Mannheim sentiment (DE_ZEW1).** No free historical API — ZEW licences the archive. Confirmed proprietary 2026-04-23. Marked as a permanent gap unless a paid-feed decision is taken.
- **Caixin China Manufacturing PMI (CN_PMI2).** S&P Global proprietary. No free monthly source identified. Chinese manufacturing covered by `CN_PMI1` (OECD BCI for China) as proxy.

#### Phase D retrospective (historical context)

Phase D — the original "PMI / Survey Data" coordinator — was retired into Phase ME on 2026-04-23 (see §1 Phase ME). The Phase D pipeline scaffold is gone; what remains is a body of survey series wired through `sources/{fred,oecd,worldbank,imf,dbnomics,ifo}.py` as part of the unified `macro_economic_hist`. 10 of the original 13 Phase D indicators are LIVE; 3 proprietary holdouts (`DE_ZEW1`, `JP_PMI1`, `CN_PMI2`) return `Insufficient Data` and are documented in §1 Known Data Gaps.

**Source-per-indicator detail:** see §3.4.1 below for the FMP-rebuild resolution table and the partial-coverage / proxy / upgrade-path catalogue.

### 3.3 Instrument Expansion

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

### 3.4 Indicator Coverage & Source Expansion

This section catalogues forward-looking work on indicator coverage: source verdicts, the gap between current coverage and the `Macro Market Indicators Reference.docx` baseline, the prioritised FRED additions, the new source modules needed, and the per-indicator source mapping. Replaces and merges the old §3.3 (Calculated Fields Expansion), §3.7 (Source Evaluation Retrospective), and §3.8 (Cycle Timing & Coverage Expansion). The largest single source-expansion track — comprehensive business + consumer surveys — has its own dedicated sub-project at §3.2; this section holds everything else.

#### Outstanding calculated fields

Several calculated fields proposed historically are not yet implemented. Some may already be covered by the 92 macro-market indicators — audit before building duplicates.

| Field | Formula | Status |
|---|---|---|
| HY/IG ratio | BAMLH0A0HYM2 / BAMLC0A0CM | Covered by US_Cr3 (HY-IG spread) |
| EMFX basket | Equal-weight CNY, INR, KRW, TWD vs USD (inverted so rising = EM FX strengthening) | Implemented 2026-04-21 as `FX_EM1` |
| EEM/IWDA ratio | EEM / URTH (MSCI World ETF in USD — functional equivalent of IWDA.L after FX adjustment) | Covered by `GL_G1` |
| MOVE proxy | 30-day realised vol on ^TNX | Not needed — `^MOVE` ticker itself is in the comp pipeline (used in `US_V2`) |
| Global PMI proxy | Equal-weight ISM + Eurozone PMI + Japan PMI | Implemented 2026-04-23 as `GL_PMI1` (4-region z-score composite) |
| Global yield curve | Average of US/DE/UK/JP 10Y-2Y spreads | Not yet implemented (US/DE/UK 10Y available; needs 2Y for DE/UK + full JP curve via §3.4 New Source Modules) |
| % stocks above 200-day MA | Per-index breadth: fraction of constituents with close > 200-day SMA. Not exposed by yfinance as a field and no free FRED/OECD feed exists; StockCharts symbols (`$SPXA200R`, `$NYA200R`, `$NDXA200R`) are proprietary. Compute in-house from constituent daily closes. Candidate indices: S&P 500 (highest signal-to-cost), Nasdaq 100, Russell 1000, FTSE 100. Naming: `US_EQ_B1` / `US_EQ_B2` etc. ("Equity - Breadth"). Adds ~500-1000 extra daily yfinance pulls per index. | Not yet implemented |

New indicators follow the CSV-driven pattern: write a `_calc_*` function, add to `REGIME_RULES` and the relevant `_*_CALCULATORS` dict, add a row to `macro_indicator_library.csv` (with `concept` + `subcategory` per the canonical 17-concept taxonomy + cycle-timing per below).

#### Cycle-timing classification (L/C/G)

The `Macro Market Indicators Reference.docx` source doc catalogues 206 macro/market indicators across 6 regions (US / UK / Eurozone / Japan / China / Global), each classified by cycle timing: **Leading** (L, blue shading `#DCE7F2` — turns 3-12 months ahead of the cycle), **Coincident** (C, beige `#E8E4D9` — confirms current state), **Lagging** (G, pink `#EDE0E0` — confirms trends already in place; turns after the cycle). Colour codes were extracted programmatically from the Word document via `python-docx` and the full 206-row list lives at `data/reference_indicators.csv`.

The `cycle_timing` column was added to `data/macro_indicator_library.csv` for all 92 Phase E indicators in Stage 2 (2026-04-23). Result: **90 Leading, 2 Coincident, 0 Lagging** — the library is overwhelmingly forward-looking by design; the two coincident components are `US_JOBS3` (labour composite blending L+C+G) and `US_G6` (IP + Retail Sales). The L/C/G badges + filter are surfaced in the explorer (per §1 Phase E).

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
| **Bank of Japan** (`stat-search.boj.or.jp`) | Future — see §3.2 | DB.nomics mirror is empty for Tankan; absorbed into the comprehensive surveys sub-project. |
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

**Status (2026-04-29):** Cross-checked the original 20-row priority list against `macro_library_fred.csv`. **17 of 20 are already present** — the table below was largely stale documentation. Two genuinely net-new rows added 2026-04-29 (`RSFSXMV` for US Retail Sales Control Group; `CHNPPIALLMINMEI` for China PPI). The remaining 1 entry (`BOEBRBS` for UK BoE Bank Rate) is *entangled with §3.1 sub-track 1* — the existing `BOERUKM` row is on the EXPIRED list and needs a reroute decision (replace with `BOEBRBS`, or move to BoE BOESD per §3.4 New Source Modules); deferred to that backlog. The 5 EXPIRED reroutes that double as additions (`JPN_POLICY_RATE`/`IRSTCB01JPM156N`, `EA_HICP`/`EA19CPALTT01GYM`, `DEU_IND_PROD`/`DEUPROINDMISMEI`, `JPN_IND_PROD`/`JPNPROINDMISMEI`, `EA_DEPOSIT_RATE`/`ECBDFR`) are listed below as already-in-library and are tracked under §3.1 sub-track 1, not here.

These 20 indicators were originally enumerated as zero-code additions. Status column reflects the 2026-04-29 audit:

| Region | Indicator | FRED Series ID | Status |
|---|---|---|---|
| US | Average Weekly Hours, Manufacturing | AWHMAN | already in library |
| US | Non-Defence Capital Goods Orders ex-Air | NEWORDER (verify) | already in library |
| US | Capacity Utilization | TCU | already in library |
| US | Real Personal Income less Transfers | W875RX1 | already in library |
| US | Real Personal Consumption Expenditures | PCEC96 | already in library |
| US | Manufacturing & Trade Sales | CMRMTSPL | already in library |
| US | Chicago Fed National Activity Index | CFNAI | already in library |
| US | Unit Labour Costs | ULCNFB | already in library |
| US | Average Duration of Unemployment | UEMPMEAN | already in library |
| US | Commercial & Industrial Loans Outstanding | TOTCI | already in library |
| US | Corporate Profits (NIPA) | CP or A053RC1Q027SBEA | already in library |
| US | Retail Sales Control Group | RSFSXMV | **added 2026-04-29** |
| UK | Bank Rate (BoE) | BOEBRBS | deferred — entangled with §3.1 sub-track 1 (BOERUKM EXPIRED reroute) |
| Eurozone | Germany Industrial Production | DEUPROINDMISMEI | already in library (EXPIRED — see §3.1) |
| Eurozone | ECB Deposit Facility Rate | ECBDFR | already in library (EXPIRED — see §3.1) |
| Eurozone | HICP Inflation | EA19CPALTT01GYM | already in library (EXPIRED — see §3.1) |
| Japan | JPY REER (BIS) | RBJPBIS | already in library |
| Japan | Industrial Production | JPNPROINDMISMEI | already in library (EXPIRED — see §3.1) |
| Japan | BoJ Policy Rate | IRSTCB01JPM156N | already in library (EXPIRED — see §3.1) |
| China | PPI Inflation | CHNPPIALLMINMEI | **added 2026-04-29** |

#### New source modules needed (ranked by indicator count)

Some of these overlap with the §3.2 surveys sub-project (BoJ Statistics specifically — covered there). The rest are non-survey targets.

| Source | Indicators | Key Series | Effort |
|---|---|---|---|
| **e-Stat (Japan)** | 16 | Machinery orders, housing starts, economy watchers, retail sales, tertiary industry, coincident/leading indices, labour, household spending | Medium — free API with registration; `estat-api-client` package available |
| **ONS API (UK)** | 14 | Monthly GDP, IP, retail sales, employment, wages, CPI, claimant count, productivity, BICS | Medium — beta REST API; dataset IDs known (mgdp, iop, rsi) |
| **BoJ Statistics (Japan)** | 6 | Tankan (all variants), JGB curve, M2/M3 — see §3.2 | Low-medium — REST API; `bojpy` package wraps it |
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
7. BoJ Statistics (6 Japan series — overlaps with §3.2 surveys; build there)
8. BIS + Bundesbank + Atlanta Fed (4 series — lower priority)

#### Proprietary indicators (user review)

51 indicators in `data/reference_indicators.csv` are flagged PROPRIETARY. The user should review these to determine if any can be sourced via institutional access. Key categories:

- **S&P Global Flash PMIs** (3) — subscriber-only; we do **not** capture them (FMP route rejected). Coverage falls back to OECD BCI mirrors on FRED where available.
- **Conference Board composites** (4) — LEI/CLI; we use OECD CLI as substitute.
- **China NBS sub-data** (12) — property, FAI, retail sales, electricity; no free foreign API. Wind/CEIC/Bloomberg only.
- **Baltic Dry Index** (2) — Baltic Exchange; no reliable free API or yfinance ticker.
- **Sell-side cycle models** (1) — GS/BCA/TS Lombard; subscription research.
- **CBI, Lloyds, Sentix, Reuters Tankan** (5) — UK/EU business surveys with no free API. Some may be revisitable via the §3.2 surveys sub-project's scraper-infrastructure track.
- **Other** (24) — various proprietary feeds across regions.

#### 3.4.1 Per-Indicator Source Mapping

Inverse of the source-verdicts table above: for each Phase E composite that depends on a survey or proxy series, this section records the raw source it currently consumes and any upgrade path. Use it when:

- **Adding a new source** (e.g. BoJ Tankan or ONS UK series — see §3.2) — find which indicators currently depend on alternatives that the new source would replace.
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
| `JP_PMI1` | au Jibun Bank Japan Mfg PMI | **Proprietary** — S&P Global, no monthly free source | n/a — BoJ Tankan quarterly is the future option (§3.2) |
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
| Japan | Mfg PMI (`JP_PMI1`) | None (proprietary; n/a) | BoJ Tankan quarterly DI (§3.2) |
| China | Sovereign Curve (10Y-2Y) | 10Y only via FRED (currently NaN — China 10Y itself unsourced) | 2Y is proprietary (ChinaBond/Wind) — accept the gap |
| China | China 10Y govt bond yield | None — FRED carries only short-term `IR3TTS01CNM156N` | Future: DB.nomics PBoC mirror (see §1 Known Data Gaps) |
| China | Real GDP | IMF annual | Direct PBoC scrape — accept gap (Wind/CEIC otherwise) |
| China | CPI Inflation | FRED `CHNCPIALLMINMEI` (monthly) | **Done** — Stage 2, 2026-04-23 (was World Bank annual) |
| China | Industrial Production | FRED `CHNPRINTO01IXPYM` (monthly) | **Done** — Stage 2, 2026-04-23 |
| China | Urban Surveyed Unemployment | OECD monthly | Functional match — no upgrade |
| Global | Global Mfg PMI | `GL_PMI1` 4-region composite (above) | True JPM Global PMI is proprietary — keep proxy |
| Global | Bloomberg Commodity Index | `DBC` ETF proxy | BCOM itself proprietary — keep DBC |
| Global | Goldman Sachs FCI | `NFCI` (Chicago Fed) substitute | GS FCI proprietary — keep NFCI |

### 3.5 Community Datasets Review — Yahoo-compatible ticker catalogues

**Priority:** Medium — low-effort discovery exercise that could feed §3.1 Sub-track 4 (dead-ticker replacements), §3.3 (Instrument Expansion), and §1 Known Data Gaps in one pass.
**Status:** Not started.

**Context.** Two community-maintained catalogues of yfinance-compatible tickers exist that might cover instruments / regions / proxies the current `data/index_library.csv` misses:

- **Kaggle — "Yahoo Finance Tickers"** (search Kaggle for the dataset of that title; the popular version contains 100,000+ symbols across global exchanges). CSV / database format.
- **GitHub — `stockdatalab/YAHOO-FINANCE-SCREENER-SYMBOLS`** — categorised lists for 40+ countries.

**Recency caveat.** Tickers in either source can be delisted, renamed, or moved between exchanges. Any candidate ticker pulled from these catalogues must be probed via yfinance before being added to `index_library.csv` (the existing validation pattern at §3.3 Step 1 applies).

**Plan:**

1. **Pull both datasets** into a working directory (not committed). Note Kaggle dataset version / GitHub commit hash for reproducibility.
2. **Cross-check against current dead-ticker list** (§3.1 Sub-track 4 — 22 dead tickers as of 2026-04-28). For each dead ticker, search both catalogues for a same-instrument / same-index successor (e.g. is there a live `^TX60` replacement? a viable `^TOPX` substitute? alternative listings for the SX*P STOXX 600 sector family?).
3. **Cross-check against §1 Known Data Gaps.** Specific targets where a free yfinance instrument might serve as a proxy:
    - Euro IG corporate effective yield (`EU_Cr1`) — does either catalogue list a Euro IG corp-bond ETF with usable distribution-yield history?
    - China 10Y govt yield (`AS_CN_R1`) — any free yfinance proxy via a CN govt-bond ETF or futures contract?
    - JP Tankan-equivalent instrument — unlikely yfinance has it, but worth a check before §3.2's BoJ source-build.
4. **Cross-check against §3.3 Instrument Expansion buckets.** Europe sector ETFs (`.DE`, EUR-denominated), EM regional ETFs, UK style ETFs, Asia/Japan additional coverage — does either catalogue surface candidates that haven't already been considered?
5. **Produce a short report** at `manuals/community_datasets_review.md` (one-shot, not a recurring artefact): per-target finding (resolved / partial / no replacement / proxy candidate), with the exact ticker symbol + currency + last-data check date.
6. **Action the wins.** For each candidate that probes clean, add a row to `index_library.csv` with `validation_status = "CONFIRMED"` and the appropriate `base_currency`. Update `§3.1 Sub-track 4` outcomes accordingly. Where no replacement exists, the gap stays in §1 Known Data Gaps (or is accepted as `UNAVAILABLE`).

**Acceptance:**

- The review report identifies, for each of the 22 dead yfinance tickers, whether the community catalogues offer a replacement.
- At least one §1 Known Data Gap is either filled (corp-yield / CN 10Y / similar) or formally confirmed unavailable in the public-data universe.
- Any added tickers ship as a single small commit to `index_library.csv` plus `validation_status` updates.

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
6. **Update `manuals/technical_manual.md`** — drop the "Simple Pipeline" sub-section in §1 / §4 and the related tab descriptions.

**Acceptance:**

- `fetch_data.py` no longer carries a separate simple-pipeline code path.
- `market_data` either deleted or thin-facade-driven from `market_data_comp` (per Step 2 outcome).
- `sentiment_data` retired (in `SHEETS_LEGACY_TABS_TO_DELETE`).
- Daily run wall-clock time decreases by the simple-pipeline budget (~30-60 seconds of yfinance / FRED calls eliminated).
- `trigger.py` continues to function (if still in use) or is acknowledged as retired.

### 3.9 Regime-Based Indicator Labelling & ML-Driven Regime Identification

**Priority:** High strategic — unlocks the §3.10 back-test + portfolio work; once shipped, every macro_market indicator carries a regime label in addition to its cycle-timing label, giving us a per-indicator "what does this say about the current regime?" signal.
**Status:** Not started. Multi-phase research project; depends on §3.3 (full coverage) and Phase H's daily audit (so the regime model isn't trained on stale inputs).

**Goal:** define a small set of well-grounded macroeconomic regimes; tag each Phase E composite indicator with a "regime-identification reliability" score; assemble an ensemble of the most reliable indicators into a current-regime classifier; use the classifier output as the regime status that drives §3.10's portfolio tilts.

#### Framework choice — hybrid 4-quadrant Growth × Inflation, supported by L/C/G

**Primary axis: 4-quadrant Growth × Inflation.** Four regime states defined by direction of macro growth (rising / falling) crossed with direction of inflation (rising / falling):

| | Inflation rising | Inflation falling |
|---|---|---|
| **Growth rising** | Reflation / Overheating | Goldilocks |
| **Growth falling** | Stagflation | Disinflation / Recession |

This framework is well-established in academic + sell-side regime research (Bridgewater All Weather, Goldman Sachs cycle, BCA "Monetary Cycle" frame, Fidelity "business cycle approach"). It maps cleanly onto our existing concept taxonomy (Growth indicators feed the x-axis; Inflation indicators feed the y-axis), and the 4 states are tractable for portfolio rules in §3.10.

**Supporting axis: L/C/G cycle-timing.** The cycle-timing labels (Leading / Coincident / Lagging) already attached to every Phase E indicator give us a confidence dimension on top of the quadrant. A regime call confirmed by Leading + Coincident + Lagging indicators all pointing the same way is high-conviction; a call where Leading indicators have flipped but Coincident + Lagging haven't is the early-turn / regime-transition signal that's most actionable for portfolio tilts.

Combined output per timestamp: `(quadrant, leading_alignment, coincident_alignment, lagging_alignment)` — e.g. `(Goldilocks, +0.7, +0.4, -0.1)` reads as "Goldilocks regime with high-conviction Leading confirmation, moderate Coincident confirmation, Lagging indicators still partly in the prior regime — a transition into Goldilocks is in progress."

#### History-sufficiency problem & proxy-series strategy

The Phase E indicator library has a coverage / history mismatch that the regime work has to work around: the 156-week z-score window plus library start dates (some indicators only go back to 2000 or later) is too short for reliable regime training and validation. We need at least 4-5 full business cycles of labelled data to fit a regime classifier with any confidence — that's ~30+ years.

**Proxy-series strategy.** Train regime identification on a small set of long-history market series that are well-known proxies for our broader concepts, then "graduate" Phase E indicators into the live ensemble based on how well they correlate with the labelled regimes from the proxy training. Candidate proxy panel (all back to ≥1990, mostly to ≥1970):

| Proxy | Concept | Source | History |
|---|---|---|---|
| S&P 500 (price + 12m return) | Equity / Growth | yfinance / FRED `SP500` | 1928+ |
| US 10-Year Treasury yield | Rates | FRED `DGS10` | 1962+ |
| US 3-Month Treasury yield | Rates / Policy | FRED `DGS3MO` | 1981+ (use `TB3MS` for monthly back to 1934) |
| 10Y-3M slope | Yield Curve | derived | 1981+ |
| Gold | Inflation hedge / Risk-off | yfinance `GC=F` (modern); LBMA / FRED for older | 1968+ |
| Copper | Growth | yfinance `HG=F` | 1989+ |
| US Dollar Index (DXY) | FX | yfinance `DX-Y.NYB` (2008+); use FRED `DTWEXBGS` for older | 1973+ |
| MOVE (or constructed bond-vol proxy) | Volatility | yfinance `^MOVE` (1988+); reconstruct from rates if older needed | 1988+ |
| VIX (or constructed equity-vol proxy) | Volatility | yfinance `^VIX` (1990+); use realised SPX vol pre-1990 | 1990+ |
| US CPI (headline, YoY) | Inflation | FRED `CPIAUCSL` | 1947+ |
| US INDPRO (YoY) | Growth | FRED `INDPRO` | 1919+ |
| US UNRATE | Labour | FRED `UNRATE` | 1948+ |
| NBER recession indicator | Cycle-state ground truth | FRED `USREC` | 1854+ |

Steps:
1. **Label history with regime quadrants** using the long-history proxies. NBER recession dates anchor "growth falling"; CPI YoY direction anchors "inflation rising/falling"; INDPRO trend anchors "growth rising/falling" outside recessions. Output: `data/regime_history.csv` — monthly regime labels back to 1947.
2. **Test each Phase E indicator's regime-identification reliability** by computing its predictive power against the labelled regime over its available history. Output: `data/regime_indicator_scores.csv` — per-indicator AUC / hit-rate / lead-time / regime-state-conditional means.
3. **Graduate top-N indicators into the live ensemble** based on a reliability threshold (TBD at implementation — likely AUC > some cutoff plus minimum cycles-of-history).
4. **For ungraduated indicators with too-short history**, look up similar-concept proxy indicators in the long-history panel and use the proxy's regime-conditional behaviour to define provisional thresholds (with help from ML — see below). Where no good proxy exists, lean on academic-paper findings (e.g. Carhart factor regime work for equity styles, Naik–Yadav for bond regimes, Cochrane–Piazzesi for term-structure regimes).

#### ML approach (open — locked in at implementation)

User has flagged this as their first genuine ML project; methods will be chosen at implementation. The framing below is a starting point.

**Indicator selection + threshold tuning** — supervised classification with regime label as `y` and indicator value (level + z-score) as `X`. Methods to consider:
- Logistic regression — interpretable; per-indicator weights map naturally to "this indicator is a 0.32-strength bullish-Goldilocks signal at z>+1".
- Random forest / gradient boosting — capture non-linear thresholds (e.g. "yield-curve inversion is binary, not gradual"). Feature-importance ranks indicators.
- Time-series-aware cross-validation (purged k-fold, walk-forward) — standard random k-fold leaks look-ahead; macro time-series demands a stricter split.

**Regime labelling itself** (when NBER + CPI direction isn't enough) — unsupervised:
- Hidden Markov Models (HMM) on the proxy panel — canonical in regime-detection literature.
- K-means / Gaussian mixture clustering on z-scored proxies — simpler, often works.
- Both produce a discrete state per timestamp; label states post-hoc against the 4-quadrant frame.

**Threshold definition for graduated Phase E indicators** — once an indicator is in the ensemble, its z-score thresholds (currently mostly hand-coded at ±1) get re-fitted to the regime data. ML helps pick thresholds that maximise per-regime classification accuracy rather than the heuristic ±1 rule.

#### Work-stage breakdown

1. **Stage 1 — Long-history label set.** Build `data/regime_history.csv` with monthly 4-quadrant labels back to 1947 using the proxy panel + NBER recession dates. Standalone deliverable; output reusable for any future regime work.
2. **Stage 2 — Per-indicator reliability scoring.** Run each Phase E indicator (where history overlaps the label set) through supervised classification; output `data/regime_indicator_scores.csv` with AUC, hit-rate, lead-time, regime-state-conditional means + std-devs.
3. **Stage 3 — Graduation + ensemble assembly.** Define reliability threshold; pick top-N indicators per concept; assemble the live current-regime classifier (probably ensemble-vote + HMM smoother).
4. **Stage 4 — Per-indicator regime label.** New `regime_label` column on `macro_market.csv` snapshot output: each indicator's current contribution to the regime call (e.g. `goldilocks-confirming`, `reflation-warning`, `neutral`, `data-insufficient`).
5. **Stage 5 — Live regime status output.** New tab `regime_status` (or column on `macro_market_hist`) carrying the timestamped regime call + per-axis confidence. This is what §3.10 consumes.

Each stage ends in a CSV / output that can be inspected and signed off before the next starts.

#### Acceptance

- `data/regime_history.csv` exists, monthly back to 1947, 4-quadrant labels validated against NBER + IMF + Bridgewater public regime dates.
- `data/regime_indicator_scores.csv` exists, one row per Phase E indicator + each long-history proxy.
- `regime_status` output produces a current regime call on every daily run with the four-element tuple `(quadrant, leading_alignment, coincident_alignment, lagging_alignment)`.
- Per-indicator `regime_label` column appears in `macro_market.csv`; explorer surfaces it (small UI follow-up).
- §3.10 back-test consumes `regime_status` directly without further data plumbing.

### 3.10 Regime-Driven Back-Test & Portfolio Optimisation

**Priority:** High strategic — this is the project's end-state artefact: a historical performance record of a regime-tilted multi-asset portfolio vs benchmark, demonstrating whether the indicator library + regime framework actually generates positive excess return.
**Status:** Not started. Hard prerequisite: §3.9 (regime status output). Soft prerequisite: Phase H daily audit + the broader §3 coverage work so the portfolio rules are tilted on clean data.

**Goal:** define a multi-asset portfolio managed against a strategic benchmark; consume `regime_status` from §3.9 plus a small set of explicit tilt rules (which asset classes to over/underweight in each regime, by what amount); back-test the resulting time series of allocations against the benchmark over the longest sample where the data supports; produce a historical performance record that flags whether the system delivers positive excess return.

#### Benchmarks (final composition decided at implementation)

Two benchmarks are planned, run side-by-side:

1. **Classic 60/40** — 60% MSCI ACWI / 40% Bloomberg Global Aggregate (in USD). Industry standard; gives an intuitive "are we beating the obvious passive comparator?" read.
2. **Regime-probability-weighted total-return benchmark** — for each regime, a static long-only composition that represents the regime's "natural" passive blend (e.g. Goldilocks ≈ heavy equity + duration; Stagflation ≈ heavy commodity + short-duration); the live benchmark is the time-weighted average of these compositions weighted by the regime probability output from §3.9. Acts as the "regime-aware buy-and-hold" comparator — the strategy must add value beyond just having the right static blend per regime.

Exact composition of both benchmarks is locked in at implementation, after the §3 coverage work resolves which asset classes we have reliable long-history data for.

#### Asset-class universe & tilt rules

The asset universe will be defined at implementation, **using the existing asset-class nomenclature in `data/index_library.csv`** (Equity / Fixed Income / Rates / Spread / FX / Commodity / Crypto / Volatility, plus the established sub-classes within each). Concrete buckets selected from those classes once §3 coverage tells us what we have reliable data for.

For each (asset class × regime) cell, an explicit **tilt rule** specifies an over/underweight versus the strategic benchmark, e.g.:

| Asset class | Goldilocks | Reflation / Overheating | Stagflation | Disinflation / Recession |
|---|---|---|---|---|
| Developed equity | + | + | − | − |
| EM equity | + | + + | − − | − |
| Long-duration govt | − | − − | − | + + |
| IG credit | + | 0 | − | − |
| HY credit | + | + | − − | − − |
| Commodities | 0 | + + | + | − |
| Gold | − | + | + + | + |
| Cash / short-duration | − | 0 | + | + |

Magnitudes (percentage-point tilts vs benchmark weight) are TBD at implementation. The `leading_alignment` confidence dimension from §3.9 modulates the tilt magnitude — high-conviction regime calls get full tilts; low-conviction or transition states get scaled-down tilts.

#### Mechanics

- **Rebalancing cadence.** Probably **monthly** (matches macro-data cadence) for v1; alternatives (weekly / quarterly / regime-change-triggered) tested at implementation to see which delivers the cleanest excess-return profile without overtrading.
- **Transaction costs.** Ignored for v1. Re-introduce at v2 once the unconstrained back-test confirms the system has signal worth paying costs for.
- **Look-ahead controls.** Regime status used at any back-test timestamp `t` is computed exclusively from data publishable on or before `t` — i.e. respects the data-release-lag of each underlying series (FRED OECD-mirror series have a 1-2 month publication lag; surveys ≈ 1 month; PMIs ≈ same week). Walk-forward construction of the regime classifier (per §3.9) is the upstream guarantee here.
- **Position-size constraints.** Each tilt rule capped at ±X% (TBD) from the benchmark weight; portfolio-level long-only constraint; total weights sum to 100%.

#### Output

A new top-level `backtest/` directory holds:

- `backtest/run_backtest.py` — runs the full back-test from `data/regime_status.csv` + asset return data + the tilt-rules CSV; emits the time series of allocations, returns, and benchmark-relative performance metrics.
- `data/backtest_history.csv` — daily/monthly time series of the regime-tilted portfolio's returns, the benchmark returns, and the tracking error / excess return.
- `data/backtest_summary.txt` — annualised return / vol / Sharpe / max drawdown / hit-rate per regime, vs each benchmark.
- A new explorer tab or section showing the back-test track record alongside live regime status.

#### Work-stage breakdown

1. **Stage 1 — Asset return time series.** Pull the asset universe's return histories (over the longest sample where data is reliable). Reuse `index_library.csv` and `market_data_comp_hist.csv` plus FRED bond-index series. Standalone deliverable: `data/asset_return_panel.csv`.
2. **Stage 2 — Tilt-rules CSV.** Hand-author `data/regime_tilt_rules.csv` from the (asset class × regime) grid. CSV-driven per §0.
3. **Stage 3 — Back-test engine.** Build `backtest/run_backtest.py` that consumes asset returns + regime status + tilt rules and produces the allocation time series + return time series.
4. **Stage 4 — Performance reporting.** Generate `backtest_summary.txt` and visualise track record vs both benchmarks.
5. **Stage 5 — Sensitivity analysis.** Test alternative rebalancing frequencies, alternative tilt magnitudes, and partial-conviction modulation; document which choices materially affect excess return.
6. **Stage 6 — Live integration.** Daily run extends to update `backtest_history.csv` + the explorer view as a paper-traded ongoing record.

#### Acceptance

- `backtest/run_backtest.py` runs end-to-end from CSV inputs and produces clean output.
- `data/backtest_history.csv` has at least 10 years of monthly data covering multiple regime transitions, with positive excess return vs the classic 60/40 benchmark over the full sample.
- Stage 5 sensitivity analysis identifies which mechanic choices (rebalance frequency, tilt magnitude, conviction modulation) drive the most excess return — these become the tuning knobs locked in for live operation.
- Daily run paper-trades the strategy from Stage 6 onward, accumulating a real-time track record alongside the historical back-test.

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
