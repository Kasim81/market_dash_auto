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

> **Why this section lives in forward_plan and not technical_manual:** §1 Project Phase Summary and §1 Data-Layer Registry below are intentionally kept here as ongoing reminders for both the user and Claude — they anchor the architectural shape of what's been built so future feature work in §3 starts from the right baseline. Even though most rows are marked `Done` / `Production`, do **not** migrate this content to `technical_manual.md`; the technical manual is the canonical implementation reference, this is the planning anchor. (If you're a future Claude wondering "should I move this?" — no. The user and previous Claude already considered it.)

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

Phase D's "Tier 3 FMP calendar" track was paywalled and rejected on 2026-04-23 — the FMP module is also deleted. See §3.1.10 for the Phase D retrospective context (folded into prior-attempts record).

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

92 composite indicators computed from the unified `macro_economic_hist` (per §1 Phase ME) plus the comp-pipeline market data. Each indicator produces: raw value, 156-week (3-year) rolling z-score, regime classification, forward regime signal (`improving`/`stable`/`deteriorating`, with optional `[leading]` suffix), and z-score trend diagnostics (`intensifying` / `fading` / `reversing` / `stable`) against 1w, 4w, 13w lookbacks. A `cycle_timing` column (L/C/G) classifies each indicator's position in the business cycle (90 Leading, 2 Coincident, 0 Lagging — see §3.1.6). Metadata is a single source of truth in `data/macro_indicator_library.csv` — no hardcoded `INDICATOR_META` dict in Python. The library carries `concept` + `subcategory` columns populated against a canonical 17-concept taxonomy (Equity, Rates / Yields, Credit / Spreads, Inflation, Sentiment / Survey, Leading Indicators, Growth, Labour, Cross-Asset, Volatility, Momentum, FX, Money / Liquidity, Housing, Manufacturing, External / Trade, Consumer); these surface in `macro_market.csv` and the explorer payload. Outputs `macro_market` (snapshot) and `macro_market_hist` (weekly history). As of the 2026-04-26 supplemental refactor Phase E contains zero direct API contact — every series the calculators read is provisioned through the unified hist; PR3 (2026-04-26) cleared the build-phase `DataFrame is highly fragmented` warnings, and the 2026-04-27 fix-forward cleared the output-phase ones plus the EU_Cr1 / `BAMLEC0A0RMEY` regression. EU_Cr1 (Euro IG spread) returns n/a until a free Euro IG corporate yield source is wired (see §1 Known Data Gaps); EU_Cr2 (Euro HY spread, reads `BAMLHE00EHYIOAS`) covers the Euro-HY regime as a separate indicator.

`docs/indicator_explorer.html` (built by `docs/build_html.py`) renders the library through a three-section sidebar — **Macro Market Indicators** (Phase E composites, By Region ↔ By Concept toggle), **Economic Data** (every raw-macro source merged, By Country ↔ By Concept toggle), **Market Data** (yfinance comp pipeline, Local ↔ USD variant). Filter pipeline supports text search, market-data variant, L/C/G cycle-timing chips, and country dropdown. Country list is read from `data/macro_library_countries.csv` (no hardcoded JS literal — per §0).

#### Phase F — Calculated Fields — Partial

Several synthetic fields originally scoped under Phase F have been absorbed into Phase E indicators (HY/IG ratio → `US_Cr3`; value/growth → `US_EQ_F2`; US 5-regime credit spread → `US_Cr2`; EM vs DM equity ratio → `GL_G1` as EEM/URTH; EMFX basket → `FX_EM1` as of 2026-04-21; MOVE index → already ingested as `^MOVE` and used in `US_V2`). Outstanding items:

- Global PMI proxy — equal-weight ISM + Eurozone PMI + Japan PMI (blocked on Phase D)
- Global yield curve — average of US / DE / UK / JP 10Y-2Y spreads (needs DE/UK 2Y yields + JP 2Y/10Y added to `macro_library_fred.csv`)
- Per-index breadth-above-200DMA — requires in-house computation from constituent closes; no free feed exists for `$SPXA200R`-style symbols

See §3.1.5 for the audit. New indicators follow the CSV-driven pattern: write a `_calc_*` function, add to `REGIME_RULES` and the relevant `_*_CALCULATORS` dict, add a row to `macro_indicator_library.csv`.

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

These 10 CSVs in `data/` are the single source of truth for everything the pipeline fetches or computes. Adding / removing / renaming a series = edit the relevant CSV. Never a Python literal (per §0.1).

| File | Rows | Owner | Used by |
|---|---|---|---|
| `index_library.csv` | ~387 | Comp pipeline | `fetch_data.py`, `fetch_hist.py` |
| `macro_library_countries.csv` | 12 | Phase ME | `sources/countries.py` (canonical / WB / IMF code mappings) |
| `macro_library_fred.csv` | ~82 | Phase ME | `sources/fred.py` |
| `macro_library_oecd.csv` | 3 | Phase ME | `sources/oecd.py` |
| `macro_library_worldbank.csv` | 1 | Phase ME | `sources/worldbank.py` |
| `macro_library_imf.csv` | 1 | Phase ME | `sources/imf.py` |
| `macro_library_dbnomics.csv` | 9 | Phase ME | `sources/dbnomics.py` |
| `macro_library_ifo.csv` | 26 | Phase ME | `sources/ifo.py` |
| `macro_indicator_library.csv` | 92 | Phase E | `compute_macro_market.py` (composite indicator registry) |
| `reference_indicators.csv` | 206 | Reference (gap audit) | §3.1.5 cross-reference; not consumed by the runtime pipeline |

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
| **`JP_PMI1`** (au Jibun Bank Japan Manufacturing PMI) | Returns Insufficient Data. S&P Global proprietary, no monthly free source. | Future partial fix: BoJ Tankan quarterly DI via direct fetcher — covered as Stage D in §3.1.8 (sequenced build plan: `sources/boj.py`). |
| **`CN_PMI2`** (Caixin China Manufacturing PMI) | Returns Insufficient Data. S&P Global proprietary. | Substitute: Chinese manufacturing is covered by `CN_PMI1` (OECD BCI for China). |
| **OECD CLI for EA19 / CHE** | Not published by OECD. | `compute_macro_market.py` uses DEU+FRA equal-weight as the Eurozone CLI proxy. |
| **`NAPMOI`** (FRED ISM new orders) | Retired by FRED in April 2026 (HTTP 400 from late April onwards). | `US_ISM1` reads `ISM_MFG_NEWORD` from DB.nomics via the unified hist (PR2, 2026-04-26). |
| **9 stale FRED rows kept as forcing functions (2026-04-29)** | FRED OECD-mirror data has frozen for `JPN_POLICY_RATE` (2008-12), `CHN_POLICY_RATE` (2015-11), `GBR_BANK_RATE` (BOERUKM, 2016-08), `CHN_M2` (2019-08), `EA_HICP` (`EA19CPALTT01GYM`, 2023-01), `CHN_IND_PROD` (CHNPRINTO01IXPYM, 2023-11), `DEU_IND_PROD` (DEUPROINDMISMEI, 2024-03), `JPN_IND_PROD` (JPNPROINDMISMEI, 2024-03), `EA_DEPOSIT_RATE` (ECBDFR, 2025-06). Rows are kept in `macro_library_fred.csv` so the daily audit keeps them surfaced. None feed any Phase E indicator. | Each has a documented fallback chain in §3.1.8 Stage B (T1 aggregator) and Stage D (T2 direct module) — BoJ Tankan for `JPN_POLICY_RATE`; DB.nomics PBoC mirror for `CHN_POLICY_RATE` / `CHN_M2`; FRED `BOEBRBS` reroute or BoE IADB for `GBR_BANK_RATE`; DB.nomics Eurostat / ECB Data Portal for `EA_HICP` / `EA_DEPOSIT_RATE`; DB.nomics NBS for `CHN_IND_PROD`; Bundesbank SDMX for `DEU_IND_PROD`; e-Stat for `JPN_IND_PROD`. |
| **10 stale series in the 117d cluster (2026-04-29)** | `PERMIT`, `FEDFUNDS`, `CMRMTSPL`, `FRA_UNEMPLOYMENT`, `DEU_UNEMPLOYMENT`, `EU_ESI`, `EU_IND_CONF`, `EU_SVC_CONF`, `ISM_MFG_PMI`, `ISM_MFG_NEWORD` — all 117d old (last_obs 2026-01-02) at the 2026-04-28 audit. 117d for monthly publishers is too long for normal lag; suggests a real fetch or publisher issue, not benign cadence. | Deliberately **not** widened in the 2026-04-29 override pass — left at base 45d tolerance so the audit keeps surfacing them. Re-investigate when they show up on the next audit; if a specific publisher genuinely went silent, document here as a permanent gap. |
| **Investing.com / Trading Economics / S&P Global direct / FMP economic calendar** | Evaluated and rejected: scraping fragility (Cloudflare), paid-only APIs, FMP endpoints paywalled August 2025. | Do not revisit. |


---

## 2. Resume Here — Priority Tasks

**Active priority is open.** The audit-remediation backlog (sub-tracks 1–4) closed 2026-04-29; durable outcomes live in `manuals/technical_manual.md` (§7, §9.8 cluster reference, §9.9 library_sync, §9.10 audit_writeback, §13 ticker dispositions, §14 daily flow) and ongoing forcing-function gaps live in §1 Known Data Gaps.

Candidate next tracks:
- **§3.1 Macro & Market Coverage Expansion** — unified track. **Stage A is critical-path** (history-preservation safeguard for FRED ICE BofA truncation, blocks next nightly run); Stages B–G follow with fallback-chain remediation, regional roll-up coverage, on-demand direct-source modules, surveys deep-dive, community ticker review.
- **§3.2 Retire the Simple Pipeline** — deprecation track.
- **§3.3 PE Ratio Integration** — small contained feature add.
- **§3.4 Market Index Expansion** — broadens market coverage; CSV-only additions to `index_library.csv`.
- **§3.5 / §3.7 Regime work** — multi-stage research projects.
- **§3.6 Incremental Fetch Mode** — performance work for `fetch_hist.py`.

---

## 3. New Feature Development

### 3.1 Macro & Market Coverage Expansion

**Priority:** High — subsumes the highest-priority items from the prior §3.1 (community datasets), §3.2 (indicator coverage) and §3.3 (surveys sub-project), now consolidated into a single coherent track with two binding architectural rules: history preservation under source truncation (§3.1.1) and the fallback chain per series (§3.1.2).

**Status:** Not started as a unified track. Several constituent threads have prior attempts on record (see §3.1.10).

**Goal.** Close the gap between the indicators we want to carry and the indicators we currently capture, while making the source architecture resilient to staleness, provider churn, and retroactive history truncation.

Three reference files anchor the work:

- `manuals/Macro Market Indicators Reference.docx` — **demand side**: 206 indicators across 6 regions (US / UK / Eurozone / Japan / China / Global) with cycle-timing classification (L/C/G) and a build-priority hierarchy (composites → high-signal singles → region-specific → lagging).
- `manuals/G20_Free_API_Catalogue_v2.docx` — **supply side**: 9 aggregators + 39 direct sources across all G20 jurisdictions with verdicts and freshness lag.
- `data/reference_indicators.csv` — **bridge**: per-indicator match status, flag (PROPRIETARY / NEW_SOURCE / FRED_ADD / DBNOMICS_ADD / DERIVED) and resolution path.

The active workstream (§3.1.8) is sequenced from cheapest / highest-signal first per the demand doc's build-priority guidance (§3.1.3) and resolves indicators through the fallback chain defined in §3.1.2. Existing wired primaries are never rewired through aggregators; new work targets gaps and stale-primary remediation only.

#### 3.1.1 Architecture — history preservation under source truncation

**Trigger (April 2026, critical).** ICE Data demanded that FRED truncate redistributed ICE BofA series to a rolling 3-year window. Affected on this pipeline include `BAMLH0A0HYM2` (US HY OAS), `BAMLC0A0CM` (US IG OAS), `BAMLHE00EHYIOAS` (Euro HY OAS), and any other `BAML*` series we carry. Without intervention, the next nightly fetch will overwrite local history with the 3-year cropped window and 20+ years of pre-2023 spread data will be lost. Other providers can change retention policy at any time; this safeguard is general-purpose, not ICE-specific.

**Rule.** A fetcher must never overwrite local history with a shorter source-side window. When a new fetch would shrink the local series (earliest source-side date is later than earliest local-stored date), the rows that would otherwise disappear are moved to a sister CSV with the `_hist_x.csv` suffix ("x" = "extended"); the live `*_hist.csv` is then refreshed normally with the truncated current window.

**File pairing (per source CSV).** For every `data/<file>_hist.csv` the fetcher writes, there is a sister `data/<file>_hist_x.csv` holding any rows that pre-date the current source-side window. Examples:

| Live | Extended-history sister |
|---|---|
| `data/macro_economic_hist.csv` | `data/macro_economic_hist_x.csv` |
| `data/market_data_comp_hist.csv` | `data/market_data_comp_hist_x.csv` |
| (per-source) `data/<source>_hist.csv` | `data/<source>_hist_x.csv` |

The sister file is created on first truncation event and appended to (not rewritten) on each subsequent event. Once a row is in the sister, it stays there — the sister is append-only.

**Detection logic (per series within a file).** On each fetch:

1. For each series column in the new download, compute `new_earliest = first non-null date`.
2. Look up `local_earliest = first non-null date` for the same column in the live CSV.
3. If `new_earliest > local_earliest`: the rows in `[local_earliest, new_earliest)` are about to be lost. Append them to the sister CSV (deduplicated against any rows already there), then write the live CSV with the new (shorter) window.
4. If `new_earliest <= local_earliest`: write the live CSV normally; sister untouched.

**Read-back semantics (most important).** Downstream consumers — Phase E indicator calculators, the dashboard, the back-test work in §3.7 — must see the full historical series, not the truncated live window. A shared loader (`library_utils.load_hist_with_archive()` or similar) transparently unions `*_hist.csv` ∪ `*_hist_x.csv` ordered by date and deduplicates. All call sites that currently `pd.read_csv("…_hist.csv")` migrate to the loader; the loader is a one-line replacement at each site.

**Implementation locus.** Two changes:

1. **Writer** — every `_hist.csv` writer (today: `fetch_data.py`, `fetch_hist.py`, `fetch_macro_economic.py`, the Phase E hist writer in `compute_macro_market.py`) gets the diff-and-archive step ahead of `to_csv`. Encapsulate in a helper `library_utils.write_hist_with_archive(df, path)` so the rule is enforced in one place.
2. **Reader** — every consumer of `_hist.csv` files goes through `load_hist_with_archive()`. Phase H's daily audit reads through the same loader so freshness checks see the unioned series, not the cropped one.

**Acceptance for the safeguard itself** — see Stage A in §3.1.9. In short: by the next nightly run, no `_hist.csv` writer can shorten local history; all `_hist.csv` readers transparently see archived rows; an audit row in `data/data_audit.txt` reports the union counts (live rows + archived rows) per series per night.

**Out of scope here.** This rule is about *not losing* history we already have. It does not address back-filling history that we never captured (a separate research task — would require a paid bulk download from ICE or an alternative free archive, addressed via the fallback chain in §3.1.2 if such a source emerges).

#### 3.1.2 Architecture — fallback chain per series

Every indicator has an ordered fallback chain rather than a single hard-coded source. The chain has four tiers:

| Tier | Role | Examples |
|---|---|---|
| **T0** | Existing wired primary — *never rewire if working* | `sources/fred.py`, `sources/dbnomics.py`, `sources/oecd.py`, `sources/worldbank.py`, `sources/imf.py`, `sources/ifo.py`, `sources/ecb.py` |
| **T1** | Aggregator fallback (free, low-effort CSV row) | DBnomics, OECD Data Explorer, IMF Data Portal, Eurostat, FRED (for non-US passthrough), BIS Data Portal |
| **T2** | Direct source (national statistical office or central bank) — built only when T1 fails or the series is absent from every aggregator | BoE IADB, BoJ Time-Series, ONS, e-Stat, Bundesbank, ECB Data Portal extension, Banxico SIE, BCB SGS, BoK ECOS, etc. (per G20 catalogue §2) |
| **T3** | Scraper, community ticker catalogue, or accepted gap | ifo Excel-workbook pattern, Kaggle / GitHub ticker lists, "Insufficient Data" |

**Trigger.** The existing Phase H daily freshness check classifies every series as LIVE / STALE / EXPIRED. When a row is STALE or EXPIRED, the fetcher walks the chain to the next tier until a fresh value is found or the chain is exhausted. Exhaustion logs to §1 Known Data Gaps.

**Implementation (β: central registry).** A new file `data/source_fallbacks.csv` carries one row per indicator with columns:

`indicator_id, t0_source, t0_id, t1_source, t1_id, t2_source, t2_id, t3_source, t3_id, last_resolved_tier, last_resolved_at`

`last_resolved_tier` and `last_resolved_at` are written by the fetcher on each successful pull, giving the daily audit a clear view of which tier each series resolved against. `data/macro_library_<source>.csv` files continue to drive primary ingestion; the fallback registry overlays them.

**Two architectural rules**:

1. **Never rewire a working T0.** If a series is fresh through its existing primary, leave it alone — even if a "more canonical" source is now catalogued. The fallback chain documents alternatives but does not displace working wires.
2. **Build T2 modules only on demand.** A direct-source module enters the build queue only when an indicator routes through it (Stage D in §3.1.8). The G20 catalogue is a reference for *what's available*, not a backlog of *what to build*.

**Interaction with §3.1.1.** Tier-walking and history-preservation are independent rules that compose: when a fallback fires (e.g. T0 EXPIRED → T1 takes over), the new tier's history-preservation safeguard still applies — if the T1 source provides a shorter window than what we already hold from T0, the pre-T1 rows route to `*_hist_x.csv` per §3.1.1 rather than being lost.

**Worked example** — `JPN_POLICY_RATE`:

| Tier | Source | ID | Status today |
|---|---|---|---|
| T0 | FRED | `IRSTCB01JPM156N` | EXPIRED 2008-12 (forcing-function row) |
| T1 | DBnomics | `OECD/MEI/JPN.IR3TIB.M` (verify) | candidate — needs probe |
| T2 | BoJ Time-Series | `IR0[…]` (BoJ policy rate series) | candidate — `sources/boj.py` would be built in Stage D |
| T3 | — | — | n/a — chain resolves at T1 or T2 |

The Phase H audit pings T0; when EXPIRED, the next pull attempts T1; if T1 returns an empty / stale value, T2; chain success writes `last_resolved_tier = T1` (or T2) and the daily audit reports the route in use.

#### 3.1.3 Suggested build priority (from `Macro Market Indicators Reference.docx`)

The demand doc carries its own build-priority guidance, reproduced here as soft guidance for Stage C ordering (regional roll-up takes precedence — see §3.1.8):

1. **Composite frameworks** — Conference Board LEI, OECD CLI, CFNAI (US), ESI (EZ), Tankan (JP). These do the aggregation work pre-baked; one row each gets you a regional read.
2. **Highest-signal singles** — yield curves (10Y-2Y, 10Y-3M), HY credit spreads, PMI new-orders sub-indices, initial claims / non-farm payrolls, sentiment indices (UMich, ZEW, ifo).
3. **Region-specific idiosyncratics** — China credit impulse, Japan machinery orders, UK RICS housing balance, German ifo Geschäftsklima, US SLOOS bank lending standards.
4. **Lagging indicators** — CPI, unemployment rate, wages — track for policy-risk calibration only; do not over-weight in cycle calls.

Cycle-timing labels (L/C/G — see §3.1.6) reinforce this hierarchy: the library is intentionally Leading-heavy (90 of 92 Phase E indicators are Leading).

#### 3.1.4 Source verdicts (consolidated)

Outcome of the 2026-04 source-evaluation cycle, expanded to the full G20 catalogue. Verdicts are durable — do not re-investigate without new evidence. Status taxonomy:

- **PRIMARY-LIVE** — currently wired as T0; ingestion path proven.
- **PRIMARY-LIVE-LIMITED** — partial T0 wire; module exists but not yet generalised.
- **TIER1-PLANNED** — aggregator candidate for T1 fallback; not yet wired.
- **TIER2-PLANNED** — direct source on the on-demand build queue (Stage D in §3.1.8).
- **TIER2-DEFER** — direct source catalogued but covered by aggregator passthrough; low gap-impact.
- **TIER3-DEFER** — bulk-only / scrape-only; very low priority.
- **SKIP-PAID** — commercial only; not actionable on free-tier.
- **SKIP-TOS / SKIP-SANCTIONS / SKIP-PROPRIETARY** — series-specific blockers.

##### Aggregators (T0 / T1)

| Source | Tier role | Status | Auth | Verdict / coverage |
|---|---|---|---|---|
| **FRED** (St. Louis Fed) | T0 (US + OECD/IMF/ECB/BIS passthrough) | PRIMARY-LIVE | Free key | Already wired (`sources/fred.py`). ALFRED gives unique vintage history for back-test (§3.7). ICE BofA series now 3-yr-rolling (§3.1.1). |
| **DBnomics** | T0 + T1 | PRIMARY-LIVE | None | Already wired (`sources/dbnomics.py`). Recommended T1 for EU / IMF / WB / Eurostat passthrough. ~100 providers; clients in Python/R. |
| **OECD Data Explorer** | T0 + T1 | PRIMARY-LIVE | None (60 q/h) | Already wired (`sources/oecd.py`). Best for harmonised cross-country (CLI / MEI / QNA). Mind the 60/h rate limit — paginate and cache. |
| **IMF Data Portal** (SDMX 3.0) | T0 + T1 | PRIMARY-LIVE | None | Already wired (`sources/imf.py`). Best for EM external accounts, FX reserves, fiscal cross-country. |
| **World Bank WDI** | T0 + T1 | PRIMARY-LIVE | None | Already wired (`sources/worldbank.py`). Long-run structural; 6-12 month lag. Not for high-frequency. |
| **Eurostat** (via DB.nomics) | T0 (passthrough) | PRIMARY-LIVE | None | Wired through DB.nomics today. Eurostat-direct (SDMX 2.1) is faster (twice-daily refresh) — TIER1-PLANNED upgrade if EU-headline lag matters. |
| **ifo Institute Excel** | T0 | PRIMARY-LIVE | None | Already wired (`sources/ifo.py`). 26 series, 1991+. Reproducible workbook-scrape pattern. |
| **ECB Data Portal** (`data-api.ecb.europa.eu`) | T0 (limited) | PRIMARY-LIVE-LIMITED | None | Inline use today (`sources/ecb.py`, Euro IG yield-curve point only). Generalise to full Tier 2 module — TIER2-PLANNED. SDMX 2.1; same-day press-release. |
| **BIS Data Portal** | T1 / T2 | TIER1-PLANNED | None | Unique for cross-country credit cycles, BIS REER, harmonised central bank balance sheets. Russia data dropped Feb 2022. New module: ~2-3 series initially. |
| **UN Comtrade** | T1 | DEFER | Free key | Bilateral merchandise trade — out of scope for current macro-monitoring panel. Free tier: 500 calls/day. |
| **ILOSTAT** | T1 | DEFER | None | Labour-market indicators — covered today by FRED/OECD passthrough; revisit only if a labour-deep-dive triggers it. |

##### Direct sources by jurisdiction (T2 / T3)

| Jurisdiction | Source | Tier role | Status | Verdict |
|---|---|---|---|---|
| United States | BLS (`api.bls.gov`) | T2 | TIER2-DEFER | Covered by FRED passthrough; v2 limits 50 series/req, 500 q/day. |
| United States | US Treasury Fiscal Data | T2 | TIER2-DEFER | Covered by FRED for headline; consider only if Daily Treasury Statement granularity needed. |
| United Kingdom | Bank of England — IADB | T2 | TIER2-PLANNED | Same-day gilts, SONIA, Bank Rate, sterling FX — fixes `BOERUKM` forcing-function row. CSV/Excel only; up to 300 series/req. |
| United Kingdom | ONS API (`api.beta.ons.gov.uk`) | T2 | TIER2-PLANNED | UK CPI/GDP/labour/retail sales — beta REST. ~14 indicators today flagged NEW_SOURCE. |
| Euro Area | ECB Data Portal (general module) | T2 | TIER2-PLANNED | €STR, AAA curve, MFI balance sheets, monetary aggregates. Generalise the existing inline call. |
| Germany | Deutsche Bundesbank (SDMX) | T2 | TIER2-PLANNED | German bunds incl. zero-coupon, BoP, FDI — fixes `DEU_IND_PROD` forcing-function row via mirror. |
| Germany | Destatis GENESIS | T2 | TIER2-DEFER | Free creds; CPI / PPI / IPI — covered today by Eurostat passthrough. |
| France | Banque de France — Webstat | T2 | TIER2-DEFER | OAT yields — covered via OECD; consider if ECB SDW gap. |
| France | INSEE — BDM | T2 | TIER2-DEFER | French CPI/HICP/GDP — covered via Eurostat passthrough. OAuth required. |
| Italy | Banca d'Italia — Infostat | T2 | TIER2-DEFER | BTP yields, public finances — covered via OECD/Eurostat. |
| Italy | ISTAT (SDMX) | T2 | TIER2-DEFER | IT CPI/GDP/IPI — covered via Eurostat passthrough. 5 q/min limit. |
| Japan | BoJ Time-Series API | T2 | TIER2-PLANNED | NEW Feb 2026 API. ~200k series. Fixes `JP_PMI1` (Tankan), `JPN_POLICY_RATE`, JGB curve — multiple §1 forcing-function rows resolve here. Highest single-jurisdiction value. |
| Japan | e-Stat | T2 | TIER2-PLANNED | JP CPI / national accounts / labour / household. ~16 indicators today flagged NEW_SOURCE. Fixes `JPN_IND_PROD`. Free key. |
| Canada | Bank of Canada — Valet | T2 | TIER2-DEFER | CAD/USD, GoC yields, CORRA. JSON. Consider if FRED passthrough lag matters for daily FX. |
| Canada | Statistics Canada — WDS | T2 | TIER2-DEFER | CA CPI/GDP/Labour Force — covered via OECD. |
| South Korea | Bank of Korea — ECOS | T2 | TIER2-DEFER | KR rates, KRW FX, BoP, household debt, BSI. Free key, JSON. |
| South Korea | KOSIS | T2 | TIER2-DEFER | KR CPI / employment / IPI — covered via OECD passthrough. |
| Australia | RBA — Statistical Tables | T2 | TIER2-DEFER | AU cash rate, AGS yields. Bulk CSV per table; no SDMX. |
| Australia | ABS Data API | T2 | TIER2-DEFER | AU CPI/WPI/GDP — covered via OECD passthrough. SDMX 2.1 beta. |
| Brazil | Banco Central do Brasil — SGS | T2 | TIER2-PLANNED | Selic, IPCA, BRL PTAX, Focus survey — Brazil unique data not on aggregators. ~18k series. |
| Brazil | IBGE — SIDRA | T2 | TIER2-DEFER | BR national accounts — covered via IMF/WB. |
| India | RBI — DBIE | T3 | TIER3-DEFER | No public REST API; bulk Excel/PDF only. RBI rates, INR FX, banking. Accept gap unless EM-priority shifts. |
| India | data.gov.in / MoSPI | T2 | TIER2-DEFER | MoSPI CPI / IIP / GDP — covered via OECD/WB. Free key, JSON. |
| China | NBS | T3 | TIER3-DEFER | Undocumented endpoint; IP-restricted; CAPTCHA. Per `reference_indicators.csv`, 12 indicators flagged PROPRIETARY here — accept the gap. |
| China | PBoC | T3 | TIER3-DEFER | Bulk Excel/PDF; LPR, MLF, RRR, RMB CFETS. Try DB.nomics PBoC mirror first. |
| Indonesia | Bank Indonesia — SEKI | T3 | TIER3-DEFER | Excel/PDF only; no REST. ID rates, JIBOR, IDR. Accept gap. |
| Indonesia | BPS — WebAPI | T2 | TIER2-DEFER | ID CPI/GDP — covered via OECD/WB. |
| Mexico | Banxico — SIE | T2 | TIER2-DEFER | MX rates, TIIE, MXN. Free token, TLS 1.3 mandatory. |
| Mexico | INEGI — BIE | T2 | TIER2-DEFER | MX CPI/GDP — covered via OECD passthrough. |
| Türkiye | CBRT — EVDS | T2 | TIER2-DEFER | TR rates, TRY, BoP, REER. Free key; 150-obs cap per call. Not on most aggregators — promote to PLANNED if Turkey panel widens. |
| Türkiye | TÜİK | T3 | TIER3-DEFER | No REST; CBRT EVDS mirrors headline. |
| Saudi Arabia | SAMA Open Data | T3 | TIER3-DEFER | Bulk CSV/Excel; no REST. SAR FX peg, SAIBOR. |
| Saudi Arabia | GASTAT / DataSaudi | T3 | TIER3-DEFER | Bulk CSV; KSA CPI/GDP. |
| South Africa | SARB Web API | T2 | TIER2-DEFER | SARB repo, SABOR, ZAR. XML responses. |
| South Africa | Stats SA | T3 | TIER3-DEFER | Bulk Excel only. ZA CPI/GDP. |
| Argentina | BCRA | T3 | TIER3-DEFER | BCRA reference rate, ARS official + financial FX. JSON. |
| Argentina | INDEC / Datos Argentina | T2 | TIER2-DEFER | IPC, EMAE — covered via IMF/WB. |
| Russia | Bank of Russia (CBR) | — | SKIP-SANCTIONS | BIS dropped Russia Feb 2022. CBR site IP-restricted in places. Accept gap. |
| Russia | Rosstat | — | SKIP-SANCTIONS | IP-restricted. Accept gap. |

##### Skipped / paid / proprietary

| Source | Status | Rationale |
|---|---|---|
| **Bloomberg / LSEG (Refinitiv)** | SKIP-PAID | Recommended in `Macro Market Indicators Reference.docx` appendix as primary commercial; out of scope on free tier. |
| **Conference Board Data Central** | SKIP-PAID | Authoritative LEI/CEI/LAG composites for 12+ economies; subscription. We use OECD CLI as substitute. |
| **Sell-side strategists** (GS / JPM / Morgan Stanley / UBS / DB / BCA / TS Lombard) | SKIP-PAID | Subscription research dashboards. |
| **Trading Economics** | SKIP-PAID | Same data via DB.nomics + FRED. |
| **FMP economic calendar** | SKIP-PAID | Paywalled Aug 2025; module deleted 2026-04-23. |
| **S&P Global / ISM direct** | SKIP-PAID | No programmatic API; subscriber-only sub-indices. ISM headlines redistributed by DB.nomics. |
| **S&P Global Flash PMIs** | SKIP-PAID | Subscriber-only; OECD BCI mirrors used as proxy where available. |
| **Caixin China Mfg PMI** | SKIP-PAID | S&P Global / Caixin proprietary; `CN_PMI1` (OECD BCI for China) is the proxy. |
| **ZEW Mannheim** | SKIP-PAID | Archive licensed. `DE_IFO1` + `DEU_BUS_CONF` cover. |
| **Investing.com** | SKIP-TOS | `investpy` broken since 2023 (Cloudflare); scraping violates ToS. |
| **UMich consumer sentiment portal** | DEFER | No official API; headline `UMCSENT` already on FRED; sub-indices proprietary. |
#### 3.1.5 Coverage today vs the 206-row reference baseline

Cross-reference of every reference indicator from `manuals/Macro Market Indicators Reference.docx` against our pipeline (last refreshed 2026-04). Full list at `data/reference_indicators.csv` (206 rows × 10 cols).

| Match Status | Count | Description |
|---|---|---|
| Full | 44 | Fully captured in our pipeline |
| Partial | 22 | Close proxy or related series captured |
| None | 140 | Not yet captured |

| Flag | Count | Meaning |
|---|---|---|
| PROPRIETARY | 51 | No free API available — see §3.1.4 SKIP rows |
| NEW_SOURCE | 54 | Requires new direct-source module — built only on demand per §3.1.2 (Stage D in §3.1.8) |
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
- **UK** and **Japan** have the largest actionable gaps (25 and 29 respectively) — these need direct-source modules (ONS, BoE, e-Stat, BoJ — see §3.1.4 TIER2-PLANNED rows).
- **China** has the most proprietary gaps (19) — NBS data has no free foreign API. Practical coverage limited to FRED OECD mirrors (`CHN_BUS_CONF`, `CHN_CON_CONF`).
- **Eurozone** is well-served by existing Eurostat / DB.nomics, with ECB Data Portal generalisation as the main upgrade.

#### 3.1.6 Cycle-timing classification (L/C/G)

`Macro Market Indicators Reference.docx` classifies each of its 206 indicators by cycle timing: **Leading** (L, blue shading `#DCE7F2` — turns 3-12 months ahead of the cycle), **Coincident** (C, beige `#E8E4D9` — confirms current state), **Lagging** (G, pink `#EDE0E0` — confirms trends already in place; turns after the cycle). Colour codes were extracted programmatically via `python-docx`; the full 206-row list with classifications lives at `data/reference_indicators.csv`.

The `cycle_timing` column was added to `data/macro_indicator_library.csv` for all 92 Phase E indicators in Stage 2 (2026-04-23). Result: **90 Leading, 2 Coincident, 0 Lagging** — the library is overwhelmingly forward-looking by design; the two coincident components are `US_JOBS3` (labour composite blending L+C+G) and `US_G6` (IP + Retail Sales). The L/C/G badges + filter are surfaced in the explorer (per §1 Phase E).

#### 3.1.7 Outstanding calculated fields

Several calculated fields proposed historically are not yet implemented. Some may already be covered by the 92 macro-market indicators — audit before building duplicates.

| Field | Formula | Status |
|---|---|---|
| HY/IG ratio | BAMLH0A0HYM2 / BAMLC0A0CM | Covered by US_Cr3 (HY-IG spread) |
| EMFX basket | Equal-weight CNY, INR, KRW, TWD vs USD (inverted so rising = EM FX strengthening) | Implemented 2026-04-21 as `FX_EM1` |
| EEM/IWDA ratio | EEM / URTH (MSCI World ETF in USD — functional equivalent of IWDA.L after FX adjustment) | Covered by `GL_G1` |
| MOVE proxy | 30-day realised vol on ^TNX | Not needed — `^MOVE` ticker itself is in the comp pipeline (used in `US_V2`) |
| Global PMI proxy | Equal-weight ISM + Eurozone PMI + Japan PMI | Implemented 2026-04-23 as `GL_PMI1` (4-region z-score composite) |
| Global yield curve | Average of US/DE/UK/JP 10Y-2Y spreads | Not yet implemented (US/DE/UK 10Y available; needs 2Y for DE/UK + full JP curve via §3.1.4 TIER2-PLANNED Bundesbank / BoJ rows) |
| % stocks above 200-day MA | Per-index breadth: fraction of constituents with close > 200-day SMA. Not exposed by yfinance as a field and no free FRED/OECD feed exists; StockCharts symbols (`$SPXA200R`, `$NYA200R`, `$NDXA200R`) are proprietary. Compute in-house from constituent daily closes. Candidate indices: S&P 500 (highest signal-to-cost), Nasdaq 100, Russell 1000, FTSE 100. Naming: `US_EQ_B1` / `US_EQ_B2` etc. ("Equity - Breadth"). Adds ~500-1000 extra daily yfinance pulls per index. | Not yet implemented |

New indicators follow the CSV-driven pattern: write a `_calc_*` function, add to `REGIME_RULES` and the relevant `_*_CALCULATORS` dict, add a row to `macro_indicator_library.csv` (with `concept` + `subcategory` per the canonical 17-concept taxonomy + cycle-timing per §3.1.6).
#### 3.1.8 Sequenced build plan

Seven stages, ordered by urgency and dependency. Stage A is critical-path (must ship before the next nightly run that would otherwise truncate ICE BofA history). Stages B–E are the substantive coverage work; Stage F runs last as a parallel mop-up; Stage G is the closeout.

##### Stage A — History-preservation safeguard (§3.1.1) — *URGENT, blocks next nightly run*

**Scope.** Land the writer / reader helpers and migrate all `_hist.csv` call sites before the next FRED pull truncates ICE BofA history.

Work items:

1. **One-time snapshot.** Before any code change ships, copy the current `data/macro_economic_hist.csv` to `data/macro_economic_hist_x.csv` so the pre-2023 ICE BofA rows are preserved even if Stage A's first run hits an edge case. Archive the snapshot date in `data/data_audit.txt`.
2. **Helpers.** Add `write_hist_with_archive(df, path)` and `load_hist_with_archive(path)` to `library_utils.py`. Writer detects per-column shrinkage and routes the would-be-lost rows to `<path>_x.csv`. Loader unions live + archive transparently.
3. **Writer migration.** Replace direct `df.to_csv(path)` calls in `fetch_data.py`, `fetch_hist.py`, `fetch_macro_economic.py`, `compute_macro_market.py` with the helper.
4. **Reader migration.** Replace direct `pd.read_csv(path)` calls in Phase E calculators (`compute_macro_market.py`), the dashboard payload builder (`docs/build_html.py`), the daily audit (`data_audit.py`), and writeback (`audit_writeback.py`) with the helper.
5. **Audit row.** `data_audit.py` reports per-series union counts (live + archived) so the daily audit catches any unexpected drop in archived row count.

**Exit criteria.** A full nightly run completes with no `_hist.csv` shorter than its previous local copy; `*_hist_x.csv` files exist and are non-empty for at least the ICE BofA series; downstream Phase E indicators that depend on long history (`US_Cr3` HY-IG spread, regime-relevant series) reproduce their pre-Stage-A z-scores within a numerical tolerance.

##### Stage B — Stale-primary remediation via fallback chains

**Scope.** Resolve the 9 forcing-function rows from §1 Known Data Gaps via the §3.1.2 chain. CSV-only changes where T1 covers; new T2 module only when T1 fails.

| Indicator | T0 status | Proposed T1 | Proposed T2 |
|---|---|---|---|
| `JPN_POLICY_RATE` (FRED `IRSTCB01JPM156N`) | EXPIRED 2008-12 | DB.nomics OECD MEI mirror | BoJ Time-Series (Stage D) |
| `CHN_POLICY_RATE` | EXPIRED 2015-11 | DB.nomics PBoC mirror | PBoC bulk (T3) |
| `GBR_BANK_RATE` (FRED `BOERUKM`) | EXPIRED 2016-08 | FRED `BOEBRBS` reroute | BoE IADB (Stage D) |
| `CHN_M2` | EXPIRED 2019-08 | DB.nomics PBoC mirror | accept gap |
| `EA_HICP` (FRED `EA19CPALTT01GYM`) | EXPIRED 2023-01 | DB.nomics Eurostat | ECB Data Portal (Stage D) |
| `CHN_IND_PROD` (FRED `CHNPRINTO01IXPYM`) | EXPIRED 2023-11 | DB.nomics NBS | accept gap |
| `DEU_IND_PROD` (FRED `DEUPROINDMISMEI`) | EXPIRED 2024-03 | DB.nomics Eurostat | Bundesbank SDMX (Stage D) |
| `JPN_IND_PROD` (FRED `JPNPROINDMISMEI`) | EXPIRED 2024-03 | DB.nomics OECD | e-Stat (Stage D) |
| `EA_DEPOSIT_RATE` (FRED `ECBDFR`) | EXPIRED 2025-06 | DB.nomics ECB | ECB Data Portal (Stage D) |

Each row gets an entry in the new `data/source_fallbacks.csv`. T0 is preserved (per §3.1.2 rule 1) so the audit alarm continues to surface the underlying provider's stop-feed event; T1 carries the fresh data.

**Exit criteria.** Phase H daily audit reports zero EXPIRED rows that don't have a working T1 or T2 fallback firing. `last_resolved_tier` columns populated for all 9 rows.

##### Stage C — Reference-baseline coverage close-out (regional roll-up)

**Scope.** Close the 99 actionable gaps in `reference_indicators.csv` via aggregator-first additions. Regional order: **US → UK → Japan → Eurozone → China → Global** (US first because cheapest — most US gaps are FRED_ADD; UK / Japan next because largest absolute gaps; Eurozone / China / Global thereafter).

Per-region work pattern:

1. Filter `reference_indicators.csv` to `match_status = None` and `flag ∈ {FRED_ADD, DBNOMICS_ADD, DERIVED}` for the region.
2. For each row, attempt aggregator resolution in order: FRED → DB.nomics → OECD → IMF → BIS → Eurostat (where applicable).
3. Add a row to the appropriate `data/macro_library_<source>.csv` for the wins; mark `match_status = Full` in `reference_indicators.csv`.
4. Rows that don't resolve at the aggregator tier route into Stage D (direct-source module candidates).
5. Rows flagged `PROPRIETARY` are not in scope here — they stay in the `data/reference_indicators.csv` ledger as accepted gaps unless §3.1.4 SKIP-PAID status changes.

Build-priority guidance from §3.1.3 applies as a **soft filter within each region**: composites first, then high-signal singles, then idiosyncratics, then lagging.

**Exit criteria.** Per-region scorecard (§3.1.5) updated; aggregator-resolvable gaps closed; remaining unresolved rows logged with target T2 module.

##### Stage D — Direct-source modules (built only on demand)

**Scope.** Build a `sources/<name>.py` + `data/macro_library_<name>.csv` for each direct source that Stage B or C identifies as required. Module enters the build queue only when ≥1 indicator routes through it.

Likely build order (highest gap-resolution count first; subject to Stage B/C outcomes):

1. **`sources/boj.py`** — BoJ Time-Series API (Feb 2026). Resolves `JPN_POLICY_RATE`, JGB curve, `JP_PMI1` (Tankan), monetary base. Largest single-jurisdiction gap-resolution.
2. **`sources/ons.py`** — UK CPI/GDP/labour/retail sales (~14 NEW_SOURCE rows).
3. **`sources/estat.py`** — Japan e-Stat (CPI / national accounts / labour / household; ~16 NEW_SOURCE rows + `JPN_IND_PROD`).
4. **`sources/boe.py`** — BoE IADB (gilts / SONIA / Bank Rate / sterling FX; resolves `GBR_BANK_RATE` if FRED reroute insufficient).
5. **`sources/bundesbank.py`** — Bundesbank SDMX (bunds + zero-coupon term structure; resolves `DEU_IND_PROD` mirror).
6. **`sources/ecb.py` generalisation** — extend the existing inline ECB Data Portal use into a full module (€STR, AAA curve, MFI, monetary aggregates; resolves `EA_DEPOSIT_RATE`, `EA_HICP`).
7. **`sources/bis.py`** — BIS Data Portal (REER, credit-to-GDP gap, central bank balance sheets; small but unique).

Each new module follows the existing pattern (per §0): fetcher in `sources/`, registry CSV in `data/`, magic-byte / response-shape validation, no hardcoded series IDs. Each ships in a small dedicated PR.

**Exit criteria.** Each module passes daily audit with zero stale rows in its registry; the indicators it was built to resolve are marked LIVE in `data/source_fallbacks.csv`.

##### Stage E — Survey deep-dive (per-region target lists)

**Scope.** Distil per-country survey-target lists from `manuals/Macro Market Indicators Reference.docx` (US worked example carried forward from old §3.3); fill via the T0–T2 chain built in Stages B–D; build scraper infrastructure (`sources/scraper_base.py`) only as last resort.

Per-country targets follow the pattern:

| Country | Mfg PMI / Business confidence | Services PMI | Consumer confidence | Idiosyncratic | Status |
|---|---|---|---|---|---|
| US | ISM Mfg ✓ | ISM Svc ✓ | UMich ✓ + Conf Board (stale) | NFIB / Empire / Philly / Dallas Fed ✓ | LIVE except Conf Board |
| UK | UK PMI (proxy via OECD BCI) | UK Svc PMI | GfK | CBI Industrial Trends, BoE Agents | partial — Stage D ONS |
| Eurozone | EU IND_CONF / ESI ✓ | EU SVC_CONF ✓ | EC Cons Conf ✓ | ifo (DE) ✓ / INSEE (FR) / ISTAT (IT) | LIVE EU + DE; FR/IT pending |
| Japan | Tankan (proprietary today) | Tankan | Cons Conf (proxy) | Economy Watchers, Reuters Tankan | Stage D BoJ resolves Tankan |
| China | NBS Mfg PMI (proprietary) | NBS Non-Mfg PMI | NBS Cons Conf (proxy) | Caixin (proprietary) | proxy via OECD BCI |
| Global | Global PMI (proxy GL_PMI1 ✓) | — | — | JPM Global PMI (proprietary) | LIVE proxy |
| GBR / DEU / FRA / ITA / JPN / CHN / AUS / CAN / CHE / EA19 / IND | per-country list | — | — | — | TBD per the demand-doc tour |

The starting reference is the demand doc + ad-hoc research; the output is `data/survey_targets.csv` (or a `survey_target=TRUE` column on `data/reference_indicators.csv`). Then for each target: classify as LIVE / FREE_API_AVAILABLE / SCRAPER_REQUIRED / PROPRIETARY; route via the chain.

**Acceptance per country.** The country's "PMI-equivalent" (manufacturing OR composite business confidence) and "consumer-confidence" series are both LIVE and feeding ≥1 Phase E composite indicator.

##### Stage F — Community ticker catalogues for market data (runs last; parallelisable)

**Scope.** Cross-check two community-maintained yfinance ticker lists against our retired tickers, market-data gaps, and Market Index Expansion buckets. Independent of Stages A–E.

Sources:
- **Kaggle "Yahoo Finance Tickers"** — 100k+ symbols across global exchanges. CSV.
- **GitHub `stockdatalab/YAHOO-FINANCE-SCREENER-SYMBOLS`** — categorised lists for 40+ countries.

Cross-check questions:

1. **22 retired tickers** (`data/removed_tickers.csv` + `manuals/technical_manual.md` §13) — same-instrument / same-index successor for `^TX60`, `^TOPX`, the SX*P STOXX 600 sector family, etc.
2. **§1 Known Data Gaps with yfinance-proxy potential** — Euro IG corp-bond ETF for `EU_Cr1`; CN govt-bond ETF for `AS_CN_R1`; JP Tankan-equivalent (unlikely but worth a check).
3. **§3.4 Market Index Expansion buckets** (after cascade renumber: was §3.6 in current numbering) — Europe sector ETFs (`.DE`, EUR-denominated), EM regional ETFs, UK style ETFs, Asia/Japan additional coverage.

Output: `manuals/community_datasets_review.md` — per-target finding (resolved / partial / no-replacement / proxy-candidate), with ticker symbol + currency + last-data check date. Action wins to `data/index_library.csv` (`validation_status = "CONFIRMED"`) and `data/removed_tickers.csv` (action=added).

**Exit criteria.** Report shipped; for each of the 22 dead tickers, a verdict (replaced / unavailable); ≥1 §1 Known Data Gap either filled or formally confirmed unavailable.

##### Stage G — Closeout

1. Refresh §1 Known Data Gaps with the closed/remaining status of every row touched in Stages B–E.
2. Refresh §3.1.9 (per-indicator source mapping) to reflect new chains.
3. Record any new gaps surfaced during the build.
4. Single closeout commit; archive the working notes.
#### 3.1.9 Per-indicator source mapping & fallback chains

Inverse of the source-verdicts table at §3.1.4: for each Phase E composite that depends on a survey or proxy series, this section records the raw source it currently consumes and its planned fallback chain. Use it when:

- **Adding a new source** (e.g. BoJ Tankan or ONS UK series — see Stage D in §3.1.8) — find which indicators currently depend on alternatives that the new source would replace.
- **Diagnosing why an indicator returns n/a** — trace the calculator back to the missing input.
- **Deciding whether a series can be retired** — find every indicator that reads it.
- **Authoring `data/source_fallbacks.csv`** — the tables below are the seed for the registry.

##### Survey / PMI indicators wired during the Phase D / FMP rebuild (2026-04-21 → 2026-04-23)

12 Phase E indicators were originally scoped against the FMP economic calendar. After FMP's free tier paywalled in Aug 2025 (verified 2026-04-22), the table below records the resolution and the fallback chain for each. 9 are LIVE through free proxies; 3 remain proprietary (no free monthly source exists today).

| Phase E ID | Description | T0 (current primary) | T1 (aggregator fallback) | T2 (direct source) | Status |
|---|---|---|---|---|---|
| `US_PMI1` | ISM Manufacturing PMI | DB.nomics `ISM/pmi/pm` (`ISM_MFG_PMI`) | OECD BCI `BSCICP02USM460S` | n/a — ISM proprietary | LIVE |
| `US_PMI2` / `US_ISM1` | ISM Manufacturing New Orders | DB.nomics `ISM/neword/in` (`ISM_MFG_NEWORD`) | — | n/a — ISM proprietary | LIVE (rerouted from FRED `NAPMOI` after FRED retired the series in April 2026) |
| `US_SVC1` | ISM Services PMI | DB.nomics `ISM/nm-pmi/pm` (`ISM_SVC_PMI`) | — | n/a — ISM proprietary | LIVE |
| `DE_IFO1` | ifo Business Climate | ifo Excel workbook (`sources/ifo.py`) | OECD BCI for DE | Bundesbank (Stage D) | LIVE |
| `EU_PMI1` | EZ Manufacturing PMI | EC Industry Confidence `EU_IND_CONF` (DB.nomics Eurostat) | — | ECB Data Portal (Stage D) | LIVE (proxy) |
| `EU_PMI2` | EZ Services PMI | EC Services Confidence `EU_SVC_CONF` (DB.nomics Eurostat) | — | ECB Data Portal (Stage D) | LIVE (proxy) |
| `UK_PMI1` | UK Manufacturing PMI | OECD BCI for UK (FRED `BSCICP02GBM460S`, `GBR_BUS_CONF`) | DB.nomics OECD passthrough | ONS (Stage D) | LIVE (proxy, monthly) |
| `CN_PMI1` | China NBS Manufacturing PMI | OECD BCI for China (FRED `CHNBSCICP02STSAM`, `CHN_BUS_CONF`) | DB.nomics OECD passthrough | NBS (T3, accept gap) | LIVE (proxy) |
| `GL_PMI1` | Global PMI | Z-score-normalised 4-region composite (`ISM_MFG_PMI` + `EU_IND_CONF` + `GBR_BUS_CONF` + `CHN_BUS_CONF`) | — | — | LIVE (auto-rebuilds from components) |
| `DE_ZEW1` | ZEW Economic Sentiment | n/a — covered by `DE_IFO1` + `DEU_BUS_CONF` | — | — | SKIP-PAID (ZEW Mannheim licences archive) |
| `JP_PMI1` | au Jibun Bank Japan Mfg PMI | n/a (proprietary) | — | BoJ Tankan via Stage D `sources/boj.py` | n/a today — Stage D resolves to Tankan quarterly DI |
| `CN_PMI2` | Caixin China Mfg PMI | n/a — Chinese mfg covered by `CN_PMI1` | — | — | SKIP-PAID (S&P Global / Caixin) |

##### Partial-coverage indicators (proxy in use, upgrade paths noted)

These reference indicators have partial coverage today via adjacent / standardised proxies. Rows marked **Done** landed in Stage 2 (2026-04-23); rows without a date are still actionable upgrades, with the chain target identified. Items flagged "no upgrade" are functional matches (proxy is fine) or genuinely blocked.

| Region | Indicator | Current source (T0) | Chain target (T1 or T2) |
|---|---|---|---|
| US | UMich Consumer Sentiment — Expectations sub-index | `UMCSENT` headline only | No free path — sub-index is UMich portal only (SKIP — DEFER) |
| US | Retail Sales (Control Group) | `RSXFS` (ex-Autos) | T1: FRED `RSFSXMV` (zero-code row, **added 2026-04-29**) |
| UK | UK Gilt Curve (10Y-2Y) | 10Y only via FRED | T2: BoE IADB (Stage D) for UK 2Y |
| UK | UK CPI Inflation | FRED `GBRCPIALLMINMEI` (monthly) | **Done** — Stage 2, 2026-04-23 (was World Bank annual) |
| Eurozone | EC Consumer Confidence | FRED OECD proxy | Functional match — no upgrade |
| Eurozone | INSEE Business Climate | FRED OECD proxy | Functional match — no upgrade |
| Eurozone | ISTAT Business Confidence | FRED OECD proxy | Functional match — no upgrade |
| Eurozone | Bund Curve (10Y-2Y) | 10Y only via FRED | T2: ECB Data Portal / Bundesbank (Stage D) for DE 2Y |
| Eurozone | Eurozone GDP | IMF annual | T1: Eurostat quarterly via DB.nomics |
| Eurozone | Euro Area Unemployment | OECD monthly | Functional match — no upgrade |
| Eurozone | HICP Inflation | FRED `EA19CPALTT01GYM` (monthly) | **Done** — Stage 2, 2026-04-23. T1 fallback: DB.nomics Eurostat (Stage B). |
| Eurozone | Industrial Production | DB.nomics Eurostat (`EZ_IND_PROD`) | **Done** — Stage 2, 2026-04-23 |
| Eurozone | Retail Sales | DB.nomics Eurostat (`EZ_RETAIL_VOL`) | **Done** — Stage 2, 2026-04-23 |
| Eurozone | Employment | DB.nomics Eurostat (`EZ_EMPLOYMENT`, quarterly) | **Done** — Stage 2, 2026-04-23 |
| Eurozone | Euro IG corporate bond yield (component of `EU_Cr1` IG spread) | None — FRED `BAMLEC0A0RMEY` invalid; row removed 2026-04-27 | T1: DB.nomics ECB MIR; T2: Bundesbank SDMX or ECB Data Portal; T3: iShares EUR IG ETF proxy via §3.1.8 Stage F. EU_Cr1 returns n/a until wired. |
| Japan | Consumer Confidence Index | FRED OECD proxy | Functional match — no upgrade |
| Japan | Real GDP | IMF annual | T2: e-Stat quarterly (Stage D) |
| Japan | Unemployment Rate | OECD monthly | Functional match — no upgrade |
| Japan | Core CPI | FRED `JPNCPIALLMINMEI` (monthly) | **Done** — Stage 2, 2026-04-23 |
| Japan | Mfg PMI (`JP_PMI1`) | None (proprietary; n/a) | T2: BoJ Tankan quarterly DI (Stage D `sources/boj.py`) |
| China | Sovereign Curve (10Y-2Y) | 10Y only via FRED (currently NaN — China 10Y itself unsourced) | 2Y proprietary (ChinaBond/Wind) — accept the gap |
| China | China 10Y govt bond yield | None — FRED carries only short-term `IR3TTS01CNM156N` | T1: DB.nomics PBoC mirror; T3: accept if not present |
| China | Real GDP | IMF annual | T1: DB.nomics OECD QNA; T3: PBoC scrape (accept gap otherwise) |
| China | CPI Inflation | FRED `CHNCPIALLMINMEI` (monthly) | **Done** — Stage 2, 2026-04-23 |
| China | Industrial Production | FRED `CHNPRINTO01IXPYM` (monthly) | **Done** — Stage 2, 2026-04-23. EXPIRED 2023-11; Stage B fallback to DB.nomics NBS. |
| China | Urban Surveyed Unemployment | OECD monthly | Functional match — no upgrade |
| Global | Global Mfg PMI | `GL_PMI1` 4-region composite | True JPM Global PMI is proprietary — keep proxy |
| Global | Bloomberg Commodity Index | `DBC` ETF proxy | BCOM itself proprietary — keep DBC |
| Global | Goldman Sachs FCI | `NFCI` (Chicago Fed) substitute | GS FCI proprietary — keep NFCI |
#### 3.1.10 Prior attempts (durable record, do not re-relearn)

- **ICE BofA series truncation on FRED (April 2026).** ICE Data demanded FRED restrict redistributed ICE BofA series to a rolling 3-year window. Affected: `BAMLH0A0HYM2`, `BAMLC0A0CM`, `BAMLHE00EHYIOAS`, plus other `BAML*` rows. Triggered the §3.1.1 history-preservation architecture. Lesson: provider retention policies can flip retroactively at any time; the writer/reader split must be defensive by default.
- **FMP economic calendar (Phase D Tier 3, 2026-04 PoC).** Rejected 2026-04-23 — endpoints paywalled (`/v3/economic_calendar` returns HTTP 403, `/stable/economic-calendar` returns HTTP 402) on the free tier. FMP module deleted. See §3.1.4 SKIP-PAID row.
- **Investing.com scraper (Phase D, 2026-04 PoC).** Rejected — fragile anti-bot protections (Cloudflare, JS challenges), frequent HTML changes, rate limiting unsuitable for nightly CI. Lessons inform any future scraper: prefer official APIs; if scraping is unavoidable, target sites without aggressive bot mitigation.
- **OECD / FRED OECD-mirror coverage.** Successfully wired ~9 country business-confidence series, but vintages frozen unpredictably — see Phase H's daily audit; `BSCICP03USM665S` and `CSCICP03USM665S` are confirmed examples where the OECD-mirror-via-FRED route silently went stale in Jan 2024. Lesson: an OECD-mirror-on-FRED row is one provider, not two — needs an explicit T1 fallback to DB.nomics OECD-direct.
- **Eurostat via DB.nomics.** ~3 EZ surveys live (`EU_ESI`, `EU_IND_CONF`, `EU_SVC_CONF`); reliable, monthly, well-maintained. Pattern to replicate where possible.
- **ifo Institute Excel-workbook scrape.** Successful pattern for German business-survey data — 26 series live via `sources/ifo.py`. Reproducible for other workbook-only publishers; informs the `sources/scraper_base.py` work queued in Stage E.
- **ZEW Mannheim sentiment (`DE_ZEW1`).** No free historical API — ZEW licences the archive. Confirmed proprietary 2026-04-23. Marked as a permanent gap unless a paid-feed decision is taken.
- **Caixin China Manufacturing PMI (`CN_PMI2`).** S&P Global proprietary. No free monthly source identified. Chinese manufacturing covered by `CN_PMI1` (OECD BCI for China) as proxy.

#### 3.1.11 Acceptance

Section-wide acceptance is the union of the per-stage exit criteria in §3.1.8, plus:

- **Architecture rules live.** `data/source_fallbacks.csv` exists and is the single source of truth for tier ordering per indicator; `library_utils.write_hist_with_archive()` and `load_hist_with_archive()` are the only paths through which `_hist.csv` files are written / read by production code.
- **No silent history loss.** Phase H daily audit reports per-series union counts (live + archived rows); any unexpected drop in archived row count flags as ALERT.
- **Coverage scorecard movement.** The §3.1.5 region scorecard moves materially: target ≥ 60% Full+Partial in every region except China (which remains gated on paid sources).
- **Forcing-function rows resolved.** All 9 §1 Known Data Gaps forcing-function rows have a working T1 or T2 fallback firing; `last_resolved_tier` populated for each.
- **Stage F report shipped.** `manuals/community_datasets_review.md` exists; for each of the 22 retired tickers a verdict is recorded; ≥1 Known Data Gap is filled or formally confirmed unavailable via the community-catalogue route.
- **Closeout commit.** §1 Known Data Gaps and §3.1.9 source mapping are refreshed to reflect the ending state; archive working notes; subsection enters `Status: Done` posture.

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

### 3.5 Regime-Based Indicator Labelling & ML-Driven Regime Identification

**Priority:** High strategic — unlocks the §3.7 back-test + portfolio work; once shipped, every macro_market indicator carries a regime label in addition to its cycle-timing label, giving us a per-indicator "what does this say about the current regime?" signal.
**Status:** Not started. Multi-phase research project; depends on §3.2 (full coverage) and Phase H's daily audit (so the regime model isn't trained on stale inputs).

**Goal:** define a small set of well-grounded macroeconomic regimes; tag each Phase E composite indicator with a "regime-identification reliability" score; assemble an ensemble of the most reliable indicators into a current-regime classifier; use the classifier output as the regime status that drives §3.7's portfolio tilts.

#### Framework choice — hybrid 4-quadrant Growth × Inflation, supported by L/C/G

**Primary axis: 4-quadrant Growth × Inflation.** Four regime states defined by direction of macro growth (rising / falling) crossed with direction of inflation (rising / falling):

| | Inflation rising | Inflation falling |
|---|---|---|
| **Growth rising** | Reflation / Overheating | Goldilocks |
| **Growth falling** | Stagflation | Disinflation / Recession |

This framework is well-established in academic + sell-side regime research (Bridgewater All Weather, Goldman Sachs cycle, BCA "Monetary Cycle" frame, Fidelity "business cycle approach"). It maps cleanly onto our existing concept taxonomy (Growth indicators feed the x-axis; Inflation indicators feed the y-axis), and the 4 states are tractable for portfolio rules in §3.7.

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
5. **Stage 5 — Live regime status output.** New tab `regime_status` (or column on `macro_market_hist`) carrying the timestamped regime call + per-axis confidence. This is what §3.7 consumes.

Each stage ends in a CSV / output that can be inspected and signed off before the next starts.

#### Acceptance

- `data/regime_history.csv` exists, monthly back to 1947, 4-quadrant labels validated against NBER + IMF + Bridgewater public regime dates.
- `data/regime_indicator_scores.csv` exists, one row per Phase E indicator + each long-history proxy.
- `regime_status` output produces a current regime call on every daily run with the four-element tuple `(quadrant, leading_alignment, coincident_alignment, lagging_alignment)`.
- Per-indicator `regime_label` column appears in `macro_market.csv`; explorer surfaces it (small UI follow-up).
- §3.7 back-test consumes `regime_status` directly without further data plumbing.

### 3.6 Incremental Fetch Mode (fetch_hist.py)

**Priority:** Medium — performance improvement.

Currently `fetch_hist.py` rebuilds the entire dataset from scratch on every run (~8-12 min for `run_comp_hist()`). An incremental append mode would:

1. Check the last date in the existing CSV
2. Only fetch new weekly rows since the last update
3. Append to existing data rather than full rebuild

This would reduce daily historical data runtime from ~10 minutes to seconds.

### 3.7 Regime-Driven Back-Test & Portfolio Optimisation

**Priority:** High strategic — this is the project's end-state artefact: a historical performance record of a regime-tilted multi-asset portfolio vs benchmark, demonstrating whether the indicator library + regime framework actually generates positive excess return.
**Status:** Not started. Hard prerequisite: §3.5 (regime status output). Soft prerequisite: Phase H daily audit + the broader §3 coverage work so the portfolio rules are tilted on clean data.

**Goal:** define a multi-asset portfolio managed against a strategic benchmark; consume `regime_status` from §3.5 plus a small set of explicit tilt rules (which asset classes to over/underweight in each regime, by what amount); back-test the resulting time series of allocations against the benchmark over the longest sample where the data supports; produce a historical performance record that flags whether the system delivers positive excess return.

#### Benchmarks (final composition decided at implementation)

Two benchmarks are planned, run side-by-side:

1. **Classic 60/40** — 60% MSCI ACWI / 40% Bloomberg Global Aggregate (in USD). Industry standard; gives an intuitive "are we beating the obvious passive comparator?" read.
2. **Regime-probability-weighted total-return benchmark** — for each regime, a static long-only composition that represents the regime's "natural" passive blend (e.g. Goldilocks ≈ heavy equity + duration; Stagflation ≈ heavy commodity + short-duration); the live benchmark is the time-weighted average of these compositions weighted by the regime probability output from §3.5. Acts as the "regime-aware buy-and-hold" comparator — the strategy must add value beyond just having the right static blend per regime.

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

Magnitudes (percentage-point tilts vs benchmark weight) are TBD at implementation. The `leading_alignment` confidence dimension from §3.5 modulates the tilt magnitude — high-conviction regime calls get full tilts; low-conviction or transition states get scaled-down tilts.

#### Mechanics

- **Rebalancing cadence.** Probably **monthly** (matches macro-data cadence) for v1; alternatives (weekly / quarterly / regime-change-triggered) tested at implementation to see which delivers the cleanest excess-return profile without overtrading.
- **Transaction costs.** Ignored for v1. Re-introduce at v2 once the unconstrained back-test confirms the system has signal worth paying costs for.
- **Look-ahead controls.** Regime status used at any back-test timestamp `t` is computed exclusively from data publishable on or before `t` — i.e. respects the data-release-lag of each underlying series (FRED OECD-mirror series have a 1-2 month publication lag; surveys ≈ 1 month; PMIs ≈ same week). Walk-forward construction of the regime classifier (per §3.5) is the upstream guarantee here.
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
