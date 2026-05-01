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

Phase D's "Tier 3 FMP calendar" track was paywalled and rejected on 2026-04-23 — the FMP module is also deleted. See `manuals/technical_manual.md` §13 for the durable Phase D retrospective (prior-attempts record).

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
| **`JP_PMI1`** (au Jibun Bank Japan Manufacturing PMI) | Returns Insufficient Data. S&P Global proprietary, no monthly free source. | ✅ Functionally resolved 2026-04-30 — `JP_TANKAN1` (BoJ Tankan Large Mfg Business Conditions DI) wired via `sources/boj.py` substitutes for the proprietary PMI. See `manuals/technical_manual.md` §5 BoJ section. |
| **`CN_PMI2`** (Caixin China Manufacturing PMI) | Returns Insufficient Data. S&P Global proprietary. | Substitute: Chinese manufacturing is covered by `CN_PMI1` (OECD BCI for China). |
| **OECD CLI for EA19 / CHE** | Not published by OECD. | `compute_macro_market.py` uses DEU+FRA equal-weight as the Eurozone CLI proxy. |
| **`NAPMOI`** (FRED ISM new orders) | Retired by FRED in April 2026 (HTTP 400 from late April onwards). | `US_ISM1` reads `ISM_MFG_NEWORD` from DB.nomics via the unified hist (PR2, 2026-04-26). |
| **9 stale FRED rows kept as forcing functions (2026-04-29)** | FRED OECD-mirror data has frozen for `JPN_POLICY_RATE` (2008-12), `CHN_POLICY_RATE` (2015-11), `GBR_BANK_RATE` (BOERUKM, 2016-08), `CHN_M2` (2019-08), `EA_HICP` (`EA19CPALTT01GYM`, 2023-01), `CHN_IND_PROD` (CHNPRINTO01IXPYM, 2023-11), `DEU_IND_PROD` (DEUPROINDMISMEI, 2024-03), `JPN_IND_PROD` (JPNPROINDMISMEI, 2024-03), `EA_DEPOSIT_RATE` (ECBDFR, 2025-06). Rows are kept in `macro_library_fred.csv` so the daily audit keeps them surfaced. None feed any Phase E indicator. | ✅ 7 of 9 resolved via Stage B T1 fallbacks + Stage D T2 modules (DB.nomics IMF/IFS, Eurostat, BoE IADB, ECB Data Portal, BoJ Time-Series, e-Stat). Per-indicator chain in `data/source_fallbacks.csv`; status in `manuals/technical_manual.md` §13. Two remain accepted gaps: `CHN_M2` and `CHN_IND_PROD` (NBS/PBoC have no free programmatic source). |
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

**Priority:** High — provides the macro + market data foundation for the regime work in §3.5 and §3.7. Most architecture is now shipped (Stages A / B / D / F per `manuals/technical_manual.md`); §3.1 below tracks only what's outstanding.

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
| **C — Reference-baseline close-out (regional roll-up)** | **Outstanding** | Close the 118 `Missing` rows in `reference_indicators.csv` where a free path exists. Priority: **UK growth (0/8 — ONS API)**, **Japan growth (3/7 → ~6/7 via e-Stat extension)**, China growth (mostly proprietary; accept). Mechanically: add rows to existing `data/macro_library_<source>.csv` files; new T2 modules only if no aggregator + no Stage-D-module path exists. |
| D — On-demand T2 modules | ✅ Shipped 2026-04-30 | — (4 modules built: BoE / ECB / BoJ / e-Stat) |
| **E — Survey deep-dive** | **Outstanding** | Per-country survey target list distilled from `Macro Market Indicators Reference.docx`; fill via T0/T1/T2 chains using existing modules. Largest open buckets: UK CBI / GfK / RICS (most proprietary — accept), JP Tankan sub-DIs (BoJ module exists; just add rows), CN NBS sub-data (proprietary — accept). Scraper infrastructure (`sources/scraper_base.py`) only as last resort. |
| F — Community ticker catalogues | ✅ Shipped 2026-04-30 | — (14 ETFs added; report at `manuals/community_datasets_review.md`) |
| **G — Closeout** | **Outstanding** | Refresh §1 Known Data Gaps, refresh `data/source_fallbacks.csv` per-indicator mapping, refresh `manuals/macro_market_indicators_coverage.xlsx`, archive working notes. Final commit when Stage C and E close. |

#### 3.1.3 Growth + Inflation focus for regime prep

§3.5 regime work uses a Growth × Inflation 4-quadrant frame (Goldilocks / Reflation / Stagflation / Disinflation). The regime classifier needs per-region clean reads on each axis. Current state has well-known gaps on both:

**Growth axis** — well-covered for US / EZ; thin for UK / JP / CN.

| Region | Action | Specific targets |
|---|---|---|
| US | ✅ no action — 6/6 captured | — |
| **UK** | **wire ONS API** (new T2 module `sources/ons.py`) | Monthly UK GDP, Index of Production (IoP), Retail Sales Index, Index of Services, claimant count, employment level, average weekly earnings, BICS business survey. ~8 rows; closes the entire UK growth column. |
| **JP** | **extend e-Stat library** | `sources/estat.py` already exists; just add rows: machinery orders (Cabinet Office), retail sales, household income/expenditure, economy watchers DI, tertiary industry index. ~4-6 rows; brings JP from 3/7 → 6/7. |
| EZ | ✅ no action — 6/6 captured | — |
| CN | accept gaps | NBS retail / FAI / electricity / industrial profits / property — all flagged PROPRIETARY in `reference_indicators.csv` (no free foreign API). Current 3/9 is the practical ceiling. |
| Global | optional: CPB World Trade Monitor + IP | New T3 fetcher `sources/cpb.py` (free CSV download, monthly); 2 rows. Low priority. |

**Inflation axis** — surface coverage is OK (7 of 9 reference rows captured), but Phase E inflation indicators are too thin for regime work.

Current Phase E library has only **2 indicators with `concept = "Inflation"`** (`US_R4`, `UK_R2`). For regime work we want per-region inflation regime classifiers. **Outstanding additions** to `macro_indicator_library.csv`:

| New indicator | Composition | Cycle | Concept |
|---|---|---|---|
| `US_INFL1` | CPI YoY z-score + Core PCE YoY z-score + 5y5y forward inflation expectation (`T5YIFR`) — output regime: high / above-target / on-target / below-target / disinflationary | L | Inflation |
| `UK_INFL1` | UK CPI YoY (already wired via FRED `GBRCPIALLMINMEI`) + UK breakeven if available | L | Inflation |
| `EU_INFL1` | HICP YoY (`EA_HICP` — Stage B wired) + 5y5y forward inflation expectation (ECB) | L | Inflation |
| `JP_INFL1` | Core CPI YoY (`JPNCPIALLMINMEI`) + JP breakevens if available | L | Inflation |
| `CN_INFL1` | CPI YoY + PPI YoY composite (both wired) | L | Inflation |

These are pure-derived Phase E composites — implementation is a `_calc_*` function in `compute_macro_market.py` + a row in `macro_indicator_library.csv`. No new fetchers needed.

**Two underlying-data fills** required first:
- **JP PPI / Services PPI** — 2 missing inflation rows from the reference doc. Wire via e-Stat (`sources/estat.py` extension; both series exist on e-Stat).
- **Inflation expectations integration** — `T5YIE`, `T10YIE`, `T5YIFR`, `MICH` are already in `macro_economic_hist.csv` but not surfaced as Phase E indicators. Surface as `US_INFEXP1` (composite) so the regime model can use them.

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

**Acceptance for §3.1.4:** all 4 nowcast composites (`US_GDPNOW1`, `US_NOWCAST1`, `UK_NOWCAST1`, `EU_NOWCAST1`, `JP_NOWCAST1`) appear in `macro_market.csv` with a clean weekly time series feeding the §3.5 regime classifier's Growth axis.

#### 3.1.5 Outstanding calculated fields

| Field | Status | Plan |
|---|---|---|
| Global yield curve composite (10Y-2Y average across US / DE / UK / JP) | Partial | US 10Y-2Y ✓ via FRED. DE 2Y wired Stage F (`EZ_GOVT_2Y`). UK has S/M/L par-yield buckets — need specific 2Y/10Y mapping (BoE yield-curve files; deferred — see §3.1.6). JP 2Y missing — needs BoJ row addition (Stage E extension; module exists). |
| % stocks above 200-day MA — per-index breadth | Not implemented | Compute in-house from constituent daily closes. Candidate indices: S&P 500 (`US_EQ_B1`), Nasdaq 100, Russell 1000, FTSE 100. Adds ~500-1000 daily yfinance pulls per index. Defer until regime work has shape — may not be needed. |

(Other previously-listed calculated fields are now closed — HY/IG ratio = `US_Cr3`, EMFX basket = `FX_EM1`, EEM/IWDA = `GL_G1`, MOVE = `^MOVE`, Global PMI proxy = `GL_PMI1`.)

#### 3.1.6 Deferred specific items

Each of these has a clear path forward but isn't a Stage C/E/G blocker. Pulled out to a single list so they don't stay buried inside the stage tables.

| Item | Why deferred | When to revisit |
|---|---|---|
| **ECB MIR — Composite Cost of Borrowing for NFCs** | Closes the Euro corporate borrowing-rate gap (proxy for `EU_Cr1` corp-yield half). ECB MIR series-code pattern needs probing — multi-dimensional dataset; canonical CCBI series ID isn't in either G20 or Market_Data catalogue. | When regime model wants explicit Euro corp credit spread vs the `IEAC.L` ETF total-return proxy that's currently doing the job. |
| **BoE per-tenor gilt yields (2Y / 5Y / 10Y / 30Y)** | Today we have S/M/L par-yield buckets (`GBR_GILT_S/M/L`) and zero-coupon M/L from BoE IADB. Specific tenor breakdowns require fetching the BoE yield-curve spreadsheet files (separate fetcher; spreadsheet parsing). | If §3.5 regime work specifically needs UK 10Y-2Y slope rather than the S/M/L proxy. |
| **`sources/bundesbank.py`** | Germany Bundesbank publishes corporate bond yield indices by rating — closes the Euro IG corp yield gap properly. New T2 module (~80-100 lines, SDMX 2.1). | When ECB MIR proves insufficient and / or regime work needs true bond yields rather than borrowing rates. |
| **iShares STOXX Europe 600 sector ETF naming verification** | 19 sector ETFs (`EXV1`-`EXV9`, `EXH1`-`EXH9`, `EXSI`) all probed live in Stage F but cross-reference revealed the 7 already in `index_library.csv` have inconsistent ticker→sector labels (e.g. `EXH1.DE` labelled "Energy" in our library but listed as "Automobiles" by iShares). Without authoritative mapping I risk mislabelling new rows. | One-off Chrome lookup against ishares.com/de to confirm the 11-sector breakdown, then bulk-add. |
| **Refactor `fetch_ecb_euro_ig_spread()` in `compute_macro_market.py`** | Legacy inline ECB call (precedes `sources/ecb.py`). Functional but architecturally inconsistent — should route through the new module so all ECB calls share one code path. | Low-priority hygiene — schedule for Stage G closeout. |
| **22 retired yfinance tickers** | The original §3.1 plan envisioned a community-catalogue cross-check for these. Most were retired because the underlying instrument disappeared (`^TX60` etc.); community catalogues unlikely to surface live replacements for instruments that no longer trade. | Defer permanently unless §3.5 regime work specifically flags a need for a retired instrument's exposure. |
| **Kaggle "Yahoo Finance Tickers" catalogue (100k+ tickers)** | Mostly individual equities; out of scope for our index/ETF/aggregate focus. Account/API-key required. | If §3.5 regime work flags a need for individual-stock data — unlikely given the macro focus. |

#### 3.1.7 Acceptance

Outstanding-work-only acceptance criteria for §3.1 closure:

- ✅ Stage A — history-preservation safeguard live with audit hook (`section_d_history_preservation` in `data_audit.py`).
- ✅ Stage B — 4 of 9 forcing-function rows resolved at T1; the other 5 either route through Stage D T2 modules or are accepted gaps.
- ✅ Stage D — 4 T2 modules built (BoE / ECB / BoJ / e-Stat) and exercising in CI without regression.
- ✅ Stage F — community-ticker review shipped (`manuals/community_datasets_review.md`); 14 ETF additions in `index_library.csv`.
- ⏳ **Stage C** — UK growth column (0/8 → ≥6/8) via `sources/ons.py`; JP growth column (3/7 → ≥6/7) via `sources/estat.py` extension. Region scorecard in `manuals/macro_market_indicators_coverage.xlsx` updated.
- ⏳ **Growth + Inflation focus (§3.1.3)** — 5 new per-region inflation regime composites (`US_INFL1` / `UK_INFL1` / `EU_INFL1` / `JP_INFL1` / `CN_INFL1`) live in `macro_indicator_library.csv`; JP PPI and Services PPI rows added via e-Stat.
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
