# FactIQ Audit Plan — `market_dash_auto`

**Status:** PLAN ONLY — nothing in this document has been executed.
**Date:** 2026-07-12
**Owner:** Kas
**Reference source:** FactIQ — the **live** service (`https://api.factiq.com/mcp`, catalog at https://factiq.com/catalog). The Claude Code plugin v0.15.0 (`C:\Users\kasim\.claude\plugins\marketplaces\factiq\`) supplies the local scripts/specs for the architecture teardown only.
**Target repo:** `C:\Users\kasim\OneDrive\GitHub\market_dash_auto`
**Executor:** Opus (fresh session) — this document is the complete brief; no prior conversation context is required.

**Standing assumption (per Kas + live catalog, 2026-07-12):** the audit runs against the **full live FactIQ catalog — 25M+ time series, 22 official sources, ~1,000 US companies, "all data, no limits" (no monthly usage quota).** The bundled `references/data/schemas.md` (v0.15.0) is **stale and understates coverage** (e.g. it predates the Federal Reserve, US Treasury, Department of Labor, FHFA, CBO, and Japan/Taiwan customs sources). **The executor must call the live `get_data_catalog` at the start and treat its output — not the bundled schemas.md — as the source of truth for what schemas/series exist.** Use schemas.md only for the §8 teardown (design patterns), never for coverage decisions.

---

## 0. Executor handoff (read first)

This plan is self-contained and written to be executed by an Opus session with no access to the conversation that produced it. Before starting:

- **Confirm FactIQ auth** (Section 2). If the `mcp__plugin_factiq_factiq__*` tools error, stop and ask the user to run `/mcp` → factiq — do not attempt the audit without them.
- **Treat this as report-only.** The audit *reports* discrepancies; it does not edit pipeline code or CSVs (except writing new files under a new `audit/` directory and, optionally, a `snapshots/` golden dataset).
- **Three decisions Kas may pre-answer; otherwise use these defaults and note them in the final report:**
  1. *Coverage* → **there is no monthly quota** ("all data, no limits", 2026-07-12), so default to **FULL coverage of all ~401 tickers** and every check. No sampling fallback (Section 6).
  2. *Pipeline freshness* → **do not re-run the pipeline**; audit the committed `market_data_comp.csv` as-is and treat staleness as a finding.
  3. *Tier-B proxies* → **allowed as directional-only checks** (e.g. `^STOXX50E` vs US-listed `FEZ`), flagged `PROXY` and never counted as CRITICAL.
- **Work Tier A → B → C, and do all zero-cost internal checks (Section 4a) before making any FactIQ calls.** Cache every FactIQ response to `audit/cache/` so a re-run is free and instant — and because data is unlimited-but-free today, the cache doubles as the golden snapshot (§8.3.4).

---

## 1. Objective & scope

Two explicit goals:

1. **Ticker-by-ticker data audit.** For every instrument in `data/index_library.csv` (~401 rows), verify against FactIQ as an *independent* source (independent of yfinance/FRED, which the pipeline itself uses):
   - **Values** — Last Price, the Perf 1W/1M/3M/6M/YTD/1Y returns (local and USD), the bps-change columns, and data freshness.
   - **Metadata** — name, region, asset class / sub-category, currency, units, ticker type, data_source, validation_status, data_start plausibility, and internal consistency of the library row itself.

2. **Architecture teardown of FactIQ.** Analyse how the plugin is built, separate what is cloneable/learnable (local skill files, scripts, schema design, playbooks) from what is proprietary (hosted warehouse, MCP server), and produce concrete recommendations for Kas's own pipeline — *now, while FactIQ is free*.

3. **Source inventory & direct-wire strategy (see §11).** Document every upstream source FactIQ aggregates, decide which the repo can wire *directly*, and keep FactIQ as an additional aggregator layer (the same role `dbnomics` already plays) for the rest — "replicate what we can replicate, then rely on FactIQ as an additional data-source aggregator."

**In scope:** `index_library.csv`, `market_data_comp.csv` (the full-library output), `market_data.csv` (simple subset — audited implicitly as a subset-consistency check), FRED-sourced rows, and a lighter-touch pass on `macro_economic.csv` / `macro_market.csv`. Freshness rules from `freshness_thresholds.csv`.

**Out of scope:** auditing the Google Sheets push (assume CSV = Sheets), re-deriving `compute_macro_market.py` composite methodology (only its input freshness/values), historical backfill quality beyond spot-checks, and any modification of pipeline code (the audit only *reports*; fixes are a follow-up).

---

## 2. Pre-flight

Checklist (Phase 0):

- [ ] **Authenticate FactIQ MCP.** In Claude Code run `/mcp` → select `factiq` → complete OAuth. Tools appear namespaced `mcp__plugin_factiq_factiq__*`.
- [ ] **Smoke test.** Call `get_data_catalog` exactly once (the skill mandates this before other tools; it is also how you confirm the *live* schema list — see standing assumption above) and one cheap `get_market_data(function="GLOBAL_QUOTE", symbol="SPY")` to confirm end-to-end. **Snapshot the catalog output to `audit/cache/data_catalog_2026-07-12.json`** — it is both the coverage source of truth and part of the golden snapshot (§8.3).
- [ ] **Note the only two operational constraints (neither limits coverage):**
  - Every row-returning tool caps at **50 rows per response** → aggregate in SQL, never dump. This is a per-call shape detail, *not* a cap on how much you can audit.
  - A possible **~1 request/second** rate limit → keep calls sequential for politeness/runtime, not for quota. There is **no monthly usage quota** — full coverage is affordable (see §6).
- [ ] **Build the working ticker list.** One local pandas script (no FactIQ calls):
  - Load `data/index_library.csv`; derive `audit_symbol` = the ticker actually used per `data_source` ("yfinance PR" → `ticker_yfinance_pr`, "yfinance TR" → `ticker_yfinance_tr`, "FRED" → the populated `ticker_fred_*` column; "UNAVAILABLE" → no symbol).
  - Left-join `data/market_data_comp.csv` on `Symbol` = `audit_symbol`. Rows in the library with no output row, and output rows with no library row, are the **first findings** (severity: HIGH).
  - Merge in `level_change_tickers.csv` (flag `is_level`), infer `is_yield` (asset_class in Rates/Spread or FRED yield/OAS/spread tickers), flag pence (`.L` suffix) and USX candidates.
  - Save as `audit/working_list.csv` with an assigned **tier** (see §3). This file drives everything downstream.
- [ ] **Create output scaffolding:** `audit/` directory in the repo with `cache/` (raw pulls as JSON), `golden/` (the free-now reference snapshot, §8.3.4), `findings.csv` (append-only), and a run log.

---

## 3. Ticker tiering — how auditable is each instrument against FactIQ?

FactIQ's `get_market_data` covers equity quotes across **global exchanges** (real-time/delayed, 52-week range), daily/weekly/monthly OHLCV for equities & FX, a broad commodity set (**WTI, Brent, natural gas, gold, silver, copper, corn, wheat, soybeans, coffee** with futures), major + cross FX pairs, and cross-market symbol search. On the macro side the live catalog now includes **Federal Reserve** (policy/market rates, money stock, industrial production — 44K series, 1919–present) and **US Treasury** (federal debt, **par yield curve**, TIC — 1990–present), on top of BLS/BEA/Census/EIA/IMF/World Bank etc. This makes coverage materially wider than the old "US large-cap only" assumption. Still, some library symbols are **index-level** tickers with no company/ETF quote behind them (`^SX7E`, `^TOPX`, `^CNXSC`, `^SP500-xxxxxx`, `^VIX*`) and those remain unpriceable on the market-data endpoint. Assign every row a tier in `working_list.csv`:

| Tier | Definition | FactIQ auditability | Decision rule from library columns |
|---|---|---|---|
| **A** | US-listed equities & ETFs, major + cross FX pairs, the **broad commodity set** (WTI/Brent/nat-gas/gold/silver/copper/corn/wheat/soybeans/coffee), the **Rates/yield universe** (via Federal Reserve + US Treasury par-yield-curve schemas), and all FRED-sourced macro series | **Full** — price/history/metadata via `get_market_data`; rates & macro via the live macro schemas | `data_source == "FRED"` → A. Else: plain US ticker (no `^`, no exchange suffix) or US-listed ETF; `commodity_group` in {Energy, Precious, Base, Ags} with a mapped commodity function; G10 + cross FX; asset_class in {Rates, Spread} → A via Fed/Treasury schemas |
| **B** | Developed- and emerging-market ETFs/ADRs and index tickers that resolve on **global-exchange** quotes or SYMBOL_SEARCH (global equity coverage means more of these now resolve directly, e.g. `IWDA.L`, `SENSEXBEES.NS`), or via a liquid US-listed proxy (`^STOXX50E`→FEZ, `^N225`→EWJ — *proxy caveat noted*) | **Partial→often full** — **always attempt SYMBOL_SEARCH / global quote before assuming failure**; only fall back to a proxy, and only demote to C if the symbol genuinely does not resolve | `region` outside US, ticker is an exchange-suffixed ETF (`.L`/`.AS`/`.DE`/`.NS`…) or `^INDEX` with a plausible listed instrument/proxy |
| **C** | **Index-LEVEL tickers that are not company/ETF quotes** — sector sub-indices (`^SP500-xxxxxx`), VIX family (`^VIX*`), and non-US index levels (`^TOPX`, `^SX7E`, `^CNXSC`); plus anything `data_source == "UNAVAILABLE"` | **None via FactIQ pricing** — internal-consistency audit only + flag for manual/secondary review (later yfinance-vs-secondary spot check, outside this plan's FactIQ scope) | `^`-prefixed index levels with no tradable instrument behind them; VIX family from `level_change_tickers.csv`; `data_source == "UNAVAILABLE"` |

Tiering is done **locally, before any FactIQ call**, then refined during Phases 1/4: for every Tier-B symbol, **actually run SYMBOL_SEARCH / a global quote first** — with global-exchange coverage many will resolve directly and be promoted to full-audit; only genuinely unresolvable symbols demote to C (cache the result so it's never retried).

Expected rough split (to validate in Phase 0, and now skewed **upward** vs the pre-live-catalog estimate): A ≈ 150–200 rows (incl. all FRED + rates + broad commodities), B ≈ 80–120 (more resolve directly), **C smaller, ≈ 60–110** (true index-level tickers only). **Every row gets a metadata + internal-consistency audit regardless of tier** — the tier only governs the external value cross-check.

---

## 4. The per-ticker audit procedure

A single repeatable loop, run per batch (§6). For each ticker:

### 4a. Metadata checks (all tiers)

Internal consistency (pure-local, no FactIQ calls):

| # | Check | Rule |
|---|---|---|
| M1 | Ticker columns match data_source | `data_source == "yfinance PR"` ⇒ `ticker_yfinance_pr` populated; `"yfinance TR"` ⇒ `ticker_yfinance_tr`; `"FRED"` ⇒ exactly the relevant `ticker_fred_*`; `"UNAVAILABLE"` ⇒ no output row expected |
| M2 | validation_status | must be `CONFIRMED`; anything else → LOW finding (stale library curation) |
| M3 | Currency vs region/country | e.g. `country_market` UK + `.L` ticker ⇒ `base_currency` GBP (or GBp handled by pence rule); Japan ⇒ JPY; `hedged == True` ⇒ `hedge_currency` populated |
| M4 | Units vs asset class | asset_class in {Rates, Spread} ⇒ units consistent with yield/spread and output uses **bps** columns; VIX family ⇒ level/points |
| M5 | USD == Local when base is USD | for `base_currency == USD` rows, `Local Perf X == USD Perf X` in `market_data_comp.csv` (exact) |
| M6 | bps arithmetic | for yield rows, `Local Perf X (bps)` ≈ raw change ×100, 1dp rounding |
| M7 | data_start plausibility | `data_start` ≤ first non-null date in `market_data_comp_hist.csv` column for that ticker; data_start not in the future; famous indices sanity (e.g. ^GSPC 1927-12-30 ✓) |
| M8 | Cross-file subset | every `simple_dash == True` row appears in `market_data.csv` with identical values to `market_data_comp.csv` |
| M9 | Hist ↔ snapshot tie-out | last value of the ticker's column in `market_data_comp_hist.csv` == `Last Price` (after the same rounding) |

External metadata (Tier A/B only, via FactIQ):

- `get_market_data(function="SYMBOL_SEARCH", keywords="<name or symbol>")` → compare returned **name, region/exchange, currency, asset type** against library `name`, `region`/`country_market`, `base_currency`, and the equity/ETF classification. Fuzzy name match (normalised, ≥ token-overlap threshold); currency must match exactly (after pence→GBP normalisation).
- For US single-name/ETF rows where fundamentals exist: `get_market_data(function="OVERVIEW", symbol=...)` → country, exchange, asset type, sector (cross-check `sector_style`).
- **data_start cross-check (sampled):** earliest date visible in `TIME_SERIES_MONTHLY` for ~10% of Tier A — FactIQ history depth won't match yfinance depth, so only flag when FactIQ has *earlier* data than `data_start` claims exists (impossible-claim direction only).

### 4b. Value checks (Tier A fully; Tier B best-effort; Tier C internal-only)

1. **Last Price.**
   `get_market_data(function="GLOBAL_QUOTE", symbol="SPY")` → compare to `Last Price` **only after aligning as-of dates** (repo `Last Date` vs quote date; if they differ, pull the matching close from `TIME_SERIES_DAILY` instead). Apply repo conventions first: pence `.L` ÷100, USX ÷100, and remember the repo rounds price to 4dp.
2. **Recompute the perf windows** from FactIQ history. All six windows share a single history pull, so recomputing more of them costs **no extra calls** — recompute **1M and YTD at minimum** (one short, one anchored), and extend to all six (1W/1M/3M/6M/YTD/1Y) since coverage is unlimited:
   - `TIME_SERIES_DAILY` (compact; tool returns ≤50 rows — request and let it cap; for 1Y/YTD anchors use `TIME_SERIES_WEEKLY`/`TIME_SERIES_MONTHLY` to reach the lookback date within the row cap).
   - Replicate `fetch_data.py` logic: % change vs value **at/after** the target lookback date; YTD anchored to first obs ≥ Jan-1; `is_yield` → bps = Δ×100; `is_level` → absolute point change.
   - Compare to the matching `Local Perf X` columns (and bps columns for yields).
3. **USD-adjusted returns (all non-USD Tier A/B rows — a single `FX_DAILY` pull per currency is shared across every ticker in that currency, so full coverage is nearly free).** Pull `FX_DAILY(from_symbol=<ccy>, to_symbol="USD")` once per currency and cache it, recombine with the recomputed local return, mind the FCY-per-USD inversion convention, compare to `USD Perf X`.
4. **Freshness.** Local-only: `today − Last Date` vs `freshness_thresholds.csv` by the series' frequency (Daily 5, Weekly 10, Monthly 45, Quarterly 120 days). Stale → finding regardless of tier. Also cross-reference `yfinance_failure_streaks.csv` — a stale row with an active failure streak is *explained* (severity downgrade to LOW, note the cause).

### Tolerances

| Comparison | Tolerance (same as-of date) | Notes |
|---|---|---|
| Last Price — US equity/ETF | \|Δ\| ≤ 0.10% | both should be official close |
| Last Price — FX | \|Δ\| ≤ 0.30% | different snap times (WM/London vs NY) |
| Last Price — commodities | \|Δ\| ≤ 1.0% | contract/settlement conventions differ |
| Recomputed perf (%, equities/FX) | \|Δ\| ≤ 0.25 pp | dominated by anchor-date choice; widen to 0.50 pp if anchor dates provably differ |
| Recomputed perf (bps, yields) | \|Δ\| ≤ 5 bps | |
| VIX-family point change | \|Δ\| ≤ 0.5 pts | Tier C — internal recompute from hist file only |
| PR vs TR mismatch | expected drift ≈ dividend yield × window | if repo says TR and FactIQ quote is PR (or vice versa), compare direction + magnitude only and note it |

### Severity scale & verdicts

- **CRITICAL** — sign flip, order-of-magnitude error (missed ÷100 pence/USX, %-vs-bps confusion), or library/output row mismatch.
- **HIGH** — outside tolerance ×3, wrong currency/asset-class metadata, staleness beyond 2× threshold.
- **MEDIUM** — outside tolerance but < ×3; name/region mismatch that's plausibly a labelling choice.
- **LOW** — validation_status not CONFIRMED, cosmetic metadata drift, explained staleness.
- **Verdicts** per check: `PASS` / `FLAG(sev)` / `UNAUDITABLE` (Tier C external checks) / `RECONCILIATION` (Fed-source vs FRED, §5 caveat a — passes but note it is not a fully independent check).

---

## 5. Macro / FRED series audit (separate track)

FRED-sourced library rows plus `macro_economic.csv` / `macro_market.csv` inputs. The live catalog makes this track **much stronger** than the bundled schemas.md implied: FactIQ now carries a **Federal Reserve** source (44K series, 1919–present: policy/market rates, money stock, bank balance sheets, industrial production), the **US Treasury par yield curve** and debt/TIC series, **Department of Labor** weekly jobless claims by state, **FHFA** house-price indices, and **CBO** projections — alongside BLS/BEA/Census/EIA/IMF/World Bank. So the FRED-sourced rows *and* the Rates/Spread/yield tickers are now strongly cross-checkable.

**Two caveats to record in the report:**

- **(a) Fed-source vs FRED is a reconciliation, not full independence.** FactIQ's Federal Reserve source and FRED both draw on the **same underlying Federal Reserve data**, so cross-checking a FRED rate against FactIQ's Fed series is a *transcription/reconciliation* check (catches ingestion/rounding/vintage errors), **not** an independent second opinion on the number itself. For genuine independence, prefer the **primary issuer** schema where the repo's FRED series actually originates elsewhere — BLS for CPI/employment, BEA for GDP/PCE, EIA for energy, **US Treasury for the yield curve** — rather than routing everything through the Fed source.
- **(b) Mapping is still required but coverage is near-complete.** FactIQ series ids ≠ FRED ids, so the mapping step below still runs — but with 22 sources and 25M+ series, far fewer "unmappable" rows are expected than previously feared. **Yield-curve / constant-maturity Treasury tickers must be checked specifically against the US Treasury par-yield-curve series** (not a generic rates series).

FactIQ series IDs ≠ FRED IDs, so there is a **mapping step**:

1. **Resolve once, cache forever.** For each FRED ticker, map to the right FactIQ schema — for rates/curve prefer **`federal_reserve`** (policy/market rates) and **`treasury`** (par yield curve); otherwise `bls` (CPI/employment/PPI/JOLTS), `bea` (GDP), `census` (trade), `eia` (energy), `imf`/`worldbank` (international) — via `search_datasets` → `search_series`, or directly in SQL against the normalized catalog (**confirm exact schema names from the live `get_data_catalog`, not schemas.md**):

   ```sql
   -- one schema per run_sql call; 50-row cap ⇒ filter hard
   SELECT series_id, series_title, frequency, measurement_units,
          adjusted_for_seasonality, end_time
   FROM series
   WHERE series_title ILIKE '%consumer price index%'
     AND geography ILIKE '%united states%'
     AND frequency = 'Monthly'
   LIMIT 20;
   ```

   Persist the mapping as `audit/fred_to_factiq_map.csv` (fred_id, factiq_schema, factiq_series_id, match_confidence, units_note). This is reusable capital beyond the audit.

2. **Cross-check latest print + 2 history points** per mapped series:

   ```sql
   SELECT time, value FROM data_points
   WHERE series_id = '<factiq_id>'
   ORDER BY time DESC
   LIMIT 13;   -- ~1y of monthly data in one call
   ```

   Compare: latest value vs repo latest (tolerance: exact for rates/levels; ≤0.1 index pts or ≤0.05 pp for transformed series), latest **date** (release-lag aware: FactIQ and FRED may be one release apart — flag only ≥2 periods apart), and two mid-history points 6m/12m back.

3. **Units/SA traps:** match `adjusted_for_seasonality` and `measurement_units` to the FRED variant used (SA vs NSA, index base year, YoY vs level). A "discrepancy" that is really an SA/NSA or base-year mismatch is a **mapping** finding, not a data finding — record it as such.
4. **Composite indicators** (`macro_market.csv`): audit **inputs only** (each underlying series latest value + freshness); the composite math itself is out of scope.

---

## 6. Batching & efficiency strategy

**Plan of record: FULL coverage of all ~401 tickers and every check.** There is **no monthly usage quota** ("all data, no limits", 2026-07-12), so there is no sampling and no call budget to ration. Only two operational constraints remain, and **neither limits coverage**:

- **50 rows per response** — a per-call *shape* detail, handled by aggregating in SQL (`run_sql`) and by choosing WEEKLY/MONTHLY series to reach long anchors within the cap. It never forces you to audit fewer tickers.
- **~1 request/second** rate limit — keep calls sequential and gently batched for politeness and predictable runtime, not to save quota. A full run of ~1,000–1,200 calls is ~20 minutes of wall clock.

Design principles:

- **Local first.** All of §4a internal checks (M1–M9), freshness, and tiering cost **zero** FactIQ calls. Run them for all ~401 rows before any external call — some rows fail internally and need no external check.
- **Cache everything.** Every FactIQ response → `audit/cache/<tool>_<symbol-or-id>_<date>.json` before parsing (the `build_viz.py` `save` step is the pattern to copy). Re-runs read cache, never re-call. Failed SYMBOL_SEARCHes are cached as negative results. Because data is currently free, **caching doubles as the golden snapshot** (§8.3) — capture generously.
- **Prefer `run_sql` aggregation** over row dumps for macro (one 13-row query replaces multiple `get_series` calls).
- **Batch size:** 25 tickers per session-batch, Tier A first, alphabetical within tier; checkpoint `findings.csv` after each batch so an interrupted run resumes cleanly.

**Indicative call volume (for runtime planning only — not a cap):** roughly 4 calls/ticker for Tier-A equities/ETFs, ~1–2 for FX/commodities, ~3 for each FRED/macro series (mapping + data), plus Tier-B resolution probes. Order of ~1,000–1,200 calls total for the full universe. Run it all.

---

## 7. Outputs / deliverables

All under `market_dash_auto/audit/`:

1. **`findings.csv`** — one row per (ticker × check):
   `ticker, name, tier, check_type, check_id, repo_value, factiq_value, as_of_repo, as_of_factiq, delta, tolerance, severity, verdict, notes`
2. **`FACTIQ_AUDIT_REPORT.md`** — executive summary: pass/flag/unauditable counts **by tier and by check type**, top-20 worst discrepancies, systematic patterns found (e.g. "all `.L` pence rows off by 100×" would be one root cause, not 15 findings), freshness league table, and the Tier-C list needing a secondary source.
3. **`working_list.csv`**, **`fred_to_factiq_map.csv`**, **`cache/`**, **`golden/`** — reusable artefacts.
4. **Optional:** a FactIQ-published discrepancy chart via `share_chart` (delta-vs-tolerance scatter by asset class) and/or a `share_report` — nice-to-have, do last.
5. **Golden snapshot** (see §8) — `audit/golden/` reference values captured while FactIQ is free.

---

## 8. Architecture teardown — what can we learn / clone from FactIQ

The second objective. All paths below are local and inspectable under `C:\Users\kasim\.claude\plugins\marketplaces\factiq\`. **The plugin is MIT-licensed (per its LICENSE/README), so the local scripts, specs, and patterns are legitimately reusable** — verify the LICENSE file text once during Phase 5 and record it in the report.

### 8.1 Cloneable / directly learnable (local files, open patterns)

| Asset | Where | What to take |
|---|---|---|
| **3-table normalized schema** | `references\data\schemas.md` | *The* big idea: every one of ~20 sources flattens into identical `series` (catalog + human_friendly_title, frequency, units, SA flag, geography, begin/end_time, data_type) / `data_points` (series_id, time, value) / `dimensions` (series_id, type, code, name) tables, plus `tabular_data` JSONB and `COMPOUND::` series. This is a direct blueprint for unifying market_dash_auto's dozen `macro_library_*.csv` catalogs (fred, oecd, imf, worldbank, ecb, boe, boj, ifo, dbnomics, estat, nasdaqdl, countries) into one queryable store (SQLite/DuckDB) instead of per-source CSV shapes. |
| **Agent-as-analyst orchestration** | `skills\factiq\SKILL.md` | The workflow grammar: catalog once → search → describe → SQL-aggregate (never row-dump) → compute → publish. Also its freshness discipline and quota etiquette. Copy this structure for a `market_dash_auto` skill so Claude can self-serve the dashboard data. |
| **SQL idioms** | `references\data\sql-guide.md` | Patterns for working under a 50-row cap: aggregate-first, window functions for latest-per-series, pivots. Reusable verbatim against a local DuckDB port of the 3-table model. |
| **ChartSpec + report JSON specs** | `references\output\chart-spec.md`, `report-spec.md`, `viz-guide.md` | Declarative chart/report contracts — a clean interface between "analysis" and "rendering". Adopt as the schema for market_dash_auto's own dashboard exports (today it exports raw CSVs to Sheets; a spec layer would decouple viz from pipeline). |
| **`term_chart.py`** | `scripts\term_chart.py` | Stdlib-only terminal chart renderer — zero-dependency visual QC. Drop-in useful for eyeballing any hist CSV series during pipeline debugging. |
| **`build_viz.py` + `viz-shell.html`** | `scripts\`, `assets\` | The fetch → **save (cache JSON)** → assemble → render local-HTML loop. Two takeaways: (a) the cache-before-parse discipline this audit itself adopts in §6; (b) a self-contained local HTML dashboard pattern as an alternative/adjunct to Google Sheets. |
| **Report-pattern playbooks** | `references\report-patterns\*.md` | Domain playbooks (monetary-policy, bilateral-trade, fiscal-policy-revenue, business-formation, interview-step) structured as thesis → antithesis → synthesis. Template for Kas's own macro playbooks — including writing *this audit* up as `report-patterns/data-audit.md` so it becomes a repeatable procedure, not a one-off. |
| **Plugin packaging** | `.mcp.json`, `commands\ask.md`, README | How a skill + references + scripts + command are packaged as a Claude Code plugin — the template if Kas ever ships `market_dash_auto` as a plugin for his own use. |

### 8.2 NOT cloneable (proprietary / server-side)

- The **warehouse contents** — the actual normalized data for ~20 sources.
- The **ingestion pipelines** that flatten each source into the 3-table model (only their *output shape* is visible via schemas.md; the ETL code is server-side).
- The **hosted MCP server + OAuth** at `https://api.factiq.com/mcp`, and the `share_chart` / `share_report` publishing backends and hosting.

### 8.3 Concrete recommendations (deliverable of Phase 5)

1. **Adopt the 3-table model locally.** Port `market_data_comp_hist.csv` + `macro_*_hist.csv` + the `macro_library_*` catalogs into a DuckDB file with `series` / `data_points` / `dimensions`. Immediate wins: one query surface, trivial freshness SQL, and the audit's internal checks become 5-line queries.
2. **Steal the cache-first discipline** (`build_viz.py` save step) for `fetch_data.py`'s yfinance/FRED pulls — raw responses to disk before transformation makes every future audit diffable.
3. **Write market_dash_auto's own audit playbook** in the report-pattern style so this plan re-runs quarterly with no rediscovery cost.
4. **Golden snapshot NOW, while free and unlimited — do this FIRST, opportunistically, even before the audit fully runs.** With the *entire* catalog (25M+ series, 22 sources) currently free with no quota, the single highest-leverage action is to capture reference data now as a hedge against a future free→paid switch. Two layers: (i) the `data_catalog` output + the relevant **series catalogs** (the `series`-table rows for every schema the audit touches — rates, Treasury curve, BLS/BEA/EIA, plus the market symbols), and (ii) every **reference value** pulled during the audit (prices, perf anchors, macro prints) into `audit/golden/` as a versioned dataset. Grab catalog/series breadth generously beyond the strict audit need — it is free today and may not be tomorrow. If FactIQ goes paid, future audits regress against the golden set instead of live calls.
5. **Reuse `term_chart.py`** as a QC step at the end of `fetch_data.py` runs (render 3–4 sentinel series to the log).
6. **Consider a spec layer** (ChartSpec-style JSON) between the pipeline and its outputs before adding any new visualisation surface.
7. **Direct-wire the replicable upstream providers** as `sources/*.py` modules (NOT a `sources/factiq.py` — FactIQ can't run headless in CI; see §11). `sources/treasury.py` (par-yield curve) is the reference implementation. The golden snapshot (rec. 4) is the insurance for the genuinely-blocked "rely-on-FactIQ" residue.

---

## 9. Risks, caveats & assumptions

| Risk / caveat | Mitigation |
|---|---|
| FactIQ coverage gaps — now limited to true **index-level** tickers (sector sub-indices, VIX family, non-US index levels) with no tradable instrument behind them | Tiering (§3, Tier C is now smaller); attempt SYMBOL_SEARCH/global quote before assuming failure; Tier C gets internal-consistency audit + explicit `UNAUDITABLE` verdicts; secondary-source follow-up in report |
| **Fed-source vs FRED non-independence** — FactIQ's Federal Reserve source and FRED share the same underlying Fed data, so that cross-check is reconciliation, not a true second opinion | For genuine independence route to the primary issuer (BLS/BEA/EIA/**Treasury** for the curve), not the Fed source; label Fed-vs-FRED checks as `RECONCILIATION` in findings (§5 caveat a) |
| As-of date / timezone mismatch (repo Last Date vs FactIQ quote date; Asian closes vs US EOD) | Always compare same-dated closes via TIME_SERIES, never quote-vs-quote across dates |
| PR vs TR vs index-vs-ETF differences (e.g. ^GSPC vs SPY) | Record which flavour each side is; widen tolerance by expected dividend drift; never compare PR index vs TR ETF blind |
| Pence `.L` / USX ÷100 conventions | Normalise before comparison; a 100× delta is a convention finding, classify separately |
| FX inversion (FCY-per-USD vs USD-per-FCY) | Standardise to USD-per-FCY before comparing; sign-flip in USD perf is the tell |
| Macro base-year / SA-NSA / release-lag mismatches | §5 step 3 — classify as mapping findings, not data findings; ≥2-period date gaps only |
| 50-row cap truncating history pulls | Use WEEKLY/MONTHLY series for long anchors; SQL aggregation for macro |
| **FactIQ free→paid (primary strategic risk)** — "all data, no limits" is true today (2026-07-12) and may not persist | **Capture the golden snapshot + series catalogs NOW, first, generously** (§8.3.4); the mapping file and cache are durable assets that keep the audit runnable if access changes |
| Rounding noise (price 4dp, perf 2dp, bps 1dp) | Fold rounding into tolerances; never flag sub-rounding deltas |
| Assumption: `market_data_comp.csv` reflects the latest pipeline run | Check file mtimes vs Last Date in pre-flight; re-run `fetch_data.py` first if stale (Kas's call) |

---

## 10. Phased execution roadmap

Full coverage throughout — no sampling. The "FactIQ calls" column is an indicative runtime estimate, not a budget.

| Phase | Work | FactIQ calls (indicative) | Effort |
|---|---|---|---|
| **0. Pre-flight** | Auth, smoke test, **snapshot live `get_data_catalog` + start the golden series-catalog capture (§8.3.4) opportunistically**, working list + tiering, internal checks M1–M9 + freshness for all ~401 rows, scaffolding | ~5 | 0.5 day |
| **1. Tier A — US equities/ETFs** | SYMBOL_SEARCH/OVERVIEW metadata + GLOBAL_QUOTE + 1M/YTD recompute, batches of 25 | ~440 | 1 day |
| **2. Tier A — FX & commodities** | FX_DAILY crosses (one pull/currency, cached), broad commodity set (WTI/Brent/nat-gas/gold/silver/copper/corn/wheat/soybeans/coffee), full USD-adjustment | ~60 | 0.5 day |
| **3. FRED / macro track** | Build `fred_to_factiq_map.csv`, latest-print + history-point checks, macro input freshness | ~240 | 1 day |
| **4. Tier B/C sweep** | Tier-B SYMBOL_SEARCH probes + proxy checks; Tier-C internal recomputes from hist file; demotions recorded | ~115 | 0.5 day |
| **5. Architecture teardown** | Read the 8 local reference docs + 2 scripts, verify MIT license text, write §8 recommendations | 0 | 0.5 day |
| **6. Report & golden snapshot** | `FACTIQ_AUDIT_REPORT.md`, findings triage into root causes, golden dataset commit, optional `share_chart` | ~5 | 0.5 day |

**Total: ~4.5 days effort, ≈1,000–1,200 FactIQ calls at full coverage** (no quota, so run it all; ~20 min of wall-clock at ~1 req/s).

---

## 11. FactIQ source inventory & direct-wire strategy

**Strategic intent (Kas):** *replicate what we can replicate, then rely on FactIQ as an additional data-source aggregator.* FactIQ aggregates 22 upstream official sources. For each, the goal is to decide whether the repo should ingest the provider **directly** (its own `sources/*.py` module, like it already does for FRED/OECD/IMF/dbnomics) or **lean on FactIQ** as an aggregation layer (the same role `dbnomics` already plays in the repo). The two are complementary: the repo already wires sources FactIQ does **not** carry — **OECD, ECB, BoE, BoJ, Eurostat, ifo, Nasdaq Data Link, dbnomics** (via `sources/oecd.py`, `ecb.py`, `boe.py`, `boj.py`, `estat.py`, `ifo.py`, `nasdaqdl`, `dbnomics.py`) plus **yfinance** for prices — so **repo ∪ FactIQ is broader than either alone.** FactIQ is an addition, not a replacement.

> **Verify-before-build:** the "Direct-access route" column lists **known public entry points to confirm at execution time**, not guaranteed-stable endpoints. The executing session must validate each route (endpoint live, auth/key still free, schema as expected) before writing an ingester.

| FactIQ source | Provider | Coverage | Direct-access route | Auth/friction | Repo status | Strategy |
|---|---|---|---|---|---|---|
| BLS | Bureau of Labor Statistics | CPI/PPI, employment, JOLTS, wages/ECI | `api.bls.gov/publicAPI/v2` | Free registration key | Partial via FRED | **Replicate (direct API)** |
| BEA | Bureau of Economic Analysis | GDP, PCE, personal income | `apps.bea.gov/api` | Free key | Partial via FRED | **Replicate** |
| Census | Census Bureau | Trade (HS-level), retail, housing, business formation | `api.census.gov` | Free key | Not in repo | **Replicate (esp. HS trade)** |
| EIA | Energy Information Administration | Petroleum/gas/electricity/renewables, prices | `api.eia.gov/v2` | Free key | Not in repo | **Replicate** |
| US Treasury | US Treasury | Federal debt, **par yield curve**, TIC | FiscalData `api.fiscaldata.treasury.gov` + daily par-yield-curve feed (XML/CSV) | No key | Not in repo | **Replicate — HIGH PRIORITY** (par yield curve directly backs the repo's Rates/yield tickers) |
| SEC EDGAR | SEC | XBRL financials, ~1,000 US large caps | `data.sec.gov` API | No key (User-Agent header required) | Not in repo | **Replicate only if fundamentals wanted — optional** (likely out of scope for a price/returns dashboard) |
| USDA ERS | USDA Economic Research Service | Farm income, food economics | Bulk downloads / limited API | Downloads | Not in repo | **Rely-on-FactIQ** (low value here) |
| BTS | Bureau of Transportation Statistics | Freight, aviation, transit | Data-portal downloads | Downloads | Not in repo | **Rely-on-FactIQ** (low value) |
| Federal Reserve | Federal Reserve | Policy/market rates, money stock, industrial production | Already via **FRED (`fred.py`)** | (as FRED) | **Covered via FRED** | **Already covered — add series ids, no new wiring** |
| Department of Labor | DoL / ETA | Weekly jobless claims | On FRED (`ICSA`/`CCSA`) | (as FRED) | **Covered via FRED** | **Already covered — add series** |
| FHFA | Federal Housing Finance Agency | House Price Index | On FRED | (as FRED) | **Covered via FRED** | **Already covered — add series** |
| CBO | Congressional Budget Office | Budget history + 10-yr projections | Publication/data downloads, no clean API | Downloads | Not in repo | **Rely-on-FactIQ** |
| China NBS | National Bureau of Statistics | Macro | `data.stats.gov.cn` (no clean public API) | High friction | Not in repo | **Rely-on-FactIQ** |
| China GACC | China Customs | HS trade | No clean public API | High friction | Not in repo | **Rely-on-FactIQ** |
| India MOSPI | MOSPI | CPI/WPI/IIP/GDP | Newer `esankhyiki.mospi.gov.in` API | Moderate | Not in repo | **Rely-on-FactIQ** (or attempt eSankhyiki) |
| India RBI | Reserve Bank of India | Banking, rates, forex | DBIE portal (awkward) | High friction | Not in repo | **Rely-on-FactIQ** |
| India DGCI&S | DGCI&S | HS trade | Commerce-dept portal | High friction | Not in repo | **Rely-on-FactIQ** |
| Japan customs | Japan Customs | HS trade | Reachable via e-Stat API | Moderate (key) | Not in repo | **Replicate-possible** / else Rely-on-FactIQ |
| Korea customs | Korea Customs Service | HS trade | KCS / TRASS | High friction | Not in repo | **Rely-on-FactIQ** |
| Taiwan customs | Taiwan Customs | HS trade | Customs portal | High friction | Not in repo | **Rely-on-FactIQ** |
| Singapore SingStat | SingStat | National statistics | `tablebuilder` API (clean) | Low | Not in repo | **Replicate-possible** |
| IMF | IMF | International macro | Already via `imf.py` | (existing) | **Covered** | **Already covered** |
| World Bank | World Bank | International development/macro | Already via `worldbank.py` | (existing) | **Covered** | **Already covered** |
| *(market layer)* | Alpha Vantage-style | Equity/index/FX/commodity quotes, OHLCV, OVERVIEW | Alpha Vantage API (`get_market_data` mirrors its function set: SYMBOL_SEARCH, GLOBAL_QUOTE, TIME_SERIES_*, OVERVIEW, FX, WTI/BRENT/GOLD…) | Free key (~25 req/day free; premium for more) | Repo uses **yfinance** | **Keep yfinance primary; document Alpha Vantage as a fallback/second-source** (repo already has a `source_fallbacks.csv` concept) |

### Three-bucket strategy

1. **Already covered — add series ids only:** Federal Reserve, DoL claims, FHFA (all via existing **FRED** / `fred.py`, which *is* the Federal Reserve distribution — 83 series today), plus **IMF** and **World Bank**. No new wiring; just extend the series catalog.
2. **Replicate directly (clean free public APIs, high value):** **BLS, BEA, Census, EIA, US Treasury par yield curve (priority), Singapore SingStat, Japan e-Stat.** SEC EDGAR optional (fundamentals — likely out of scope for a price/returns dashboard).
3. **Rely on FactIQ as aggregator (no clean API / high friction) — the `dbnomics`-style layer:** **China NBS + GACC customs, India MOSPI / RBI / DGCI&S, Korea & Taiwan customs, CBO, USDA ERS, BTS.** These are exactly the sources where standing up a direct ingester is expensive or infeasible, so FactIQ earns its keep here.

### Wiring mechanism — corrected after implementation (2026-07-12)

> **A `sources/factiq.py` pipeline module is NOT viable — do not build one.** FactIQ's data is reachable **only** through its OAuth-gated MCP inside an interactive Claude/Codex agent session; there is **no API key a headless GitHub Actions run can use.** The repo's pipeline runs headless in CI, so it can never `import` a FactIQ client. This was confirmed while wiring the Treasury source (milestone 1 below). The §11 buckets therefore split by **access mechanism**, not by data value:

1. **Direct-wire in CI (the "replicate" bucket)** — every source with its own keyless/low-friction public API gets a `sources/*.py` calling the **upstream provider directly**, reusing `sources/base.py` plumbing and feeding the Friday-spine / history CSVs exactly like `fred`/`oecd`/`imf` do. **Reference implementation: `sources/treasury.py`** (US Treasury daily par-yield curve, keyless `home.treasury.gov` CSV feed, per-year pagination + backoff — the template for BLS, BEA, Census, EIA, SingStat, Japan e-Stat). Note: the FiscalData API (`api.fiscaldata.treasury.gov`) does **not** carry the daily par curve (404 — monthly averages only); use the `home.treasury.gov` daily feed.
2. **FactIQ = interactive/agent-side only** — audit cross-check, ad-hoc analysis, and the **§8.3 golden snapshot** captured now while free. It is a Claude-session aggregator, **never a pipeline import.**
3. **Genuinely blocked residue** — sources with no free keyless API of their own (license-gated / scrape-hostile: parts of China NBS/customs, India RBI/DGCI&S, Korea/Taiwan customs, CBO). For these the honest options are FRED-as-proxy where it carries the series, or the golden snapshot — **not** live FactIQ calls from CI. Everything cheaply-wireable should be pulled OUT of this bucket and direct-wired, shrinking it to the truly high-friction sources.

**Licensing note:** the plugin's *local scripts/patterns* are MIT and reusable, but FactIQ **data access is via the hosted service and is not licensed for redistribution** — so the rule is **"replicate the upstream source, don't rescrape FactIQ's warehouse."**

---

## 12. Dead-ticker & coverage-gap cleanup (remediation backlog)

Surfaced by the 2026-07-12 audit (`audit/findings.csv`, `audit/working_list.csv`). This is a **forward remediation plan**, separate from the read-only audit: it proposes changes to `index_library.csv`. **Do not hard-delete rows** — the repo already has a retirement workflow (`data/removed_tickers.csv` ledger + `data/yfinance_failure_streaks.csv` streak tracker). Retire tickers *through that machinery* so history and rationale are preserved.

**Scope guard:** the 52 `validation_status = UNAVAILABLE` rows (Treasury/Bund/JGB yields, breakevens, SOFR, Fed funds, curve spreads, ICE BofA USD-hedged gilt/EGB families) are **curated-by-design placeholders, NOT dead** — they are sourced elsewhere (FRED / direct-wire per §11) or intentionally parked. Exclude them from cleanup.

### Class 1 — Genuinely dead (frozen ≥ 10 years, yfinance discontinued) → **retire**
| Ticker | Name | Frozen for | Action |
|---|---|---|---|
| `^CM100` | CAC Mid 60 | ~3,860 d | Retire → `removed_tickers.csv`. Optional replacement: a CAC Mid 60 ETF/index proxy if the exposure is wanted. |
| `^SP500-151050` | S&P 500 Paper & Forest Products | ~3,859 d | Retire (GICS sub-index yfinance no longer serves). |
| `^SP500-551020` | S&P 500 Gas Utilities | ~3,664 d | Retire. |

These serve *frozen stale values* today — worse than a blank, because they look live. Highest cleanup priority.

### Class 2 — No-output yfinance gaps (in library, produce no comp row) → **retire or re-source** (29 rows)
- **~26 S&P 500 GICS industry sub-indices** (`^SP500-151010` Chemicals, `^SP500-401010` Banks, `^SP500-601040` Office REITs, … full list in `audit/working_list.csv` where `has_output=False` & `data_source='yfinance PR'`). yfinance stopped serving GICS *industry-level* `^SP500-xxxxxx` indices. **Decision:** (a) retire the industry granularity and keep only the sector level the dashboard already gets, or (b) wire a secondary source (S&P/GICS index data is licensed — likely not free). Recommend (a) unless industry-level detail is a hard requirement.
- **`000905.SS` (CSI 500), `000852.SS` (CSI 1000)** — Chinese index tickers yfinance returns nothing for. Re-source via a China-listed ETF proxy (e.g. an onshore/HK-listed CSI 500/1000 ETF) or retire.
- **`^VXEEM` (CBOE EM Volatility)** — index discontinued by CBOE; retire.

### Class 3 — Empty output rows (comp row present, `Last Price` blank) → **triage fetch failures** (47 rows)
Almost all are **foreign-listed UCITS ETF proxies**: `.L` (London), `.DE` (Xetra), `.PA` (Paris), `.JO` (Johannesburg) — e.g. `IWDA.L`, `ISF.L`, `VGOV.L`, `AGGG.L`, `EXSA.DE`, `C40.PA`, `STX40.JO`. A blank `Last Price` means the fetch failed or the symbol/line is stale. Triage each into: **(i) fixable** (wrong exchange suffix, multi-share-class/line ambiguity, or the `.L` pence-÷100 bug in §finding below that corrupts EUR-quoted London lines), **(ii) genuinely dead** → retire, or **(iii) needs a fallback source** (`source_fallbacks.csv` already exists for this). Cross-reference `yfinance_failure_streaks.csv`: symbols with long consecutive-fail streaks are retire candidates; intermittent ones are fetch-robustness bugs, not dead tickers.

> **Related fix, not a dead ticker:** the six `.L` EUR bond ETFs (`IEAC.L`, `IEAG.L`, `IBGL.L`, `IFRB.L`, `IITB.L`) get wrongly ÷100'd by the pence heuristic (`ticker.endswith(".L")` in `fetch_data.py`), which assumes London = pence. They are EUR-quoted, so the division produces a spurious ~1.x "price". This is a **scale/labeling bug to fix in code**, not a ticker to retire (returns are unaffected; only `Last Price` display). See the open decision in the handover discussion.

### Recommended cleanup procedure (per retired ticker)
1. Append a row to `data/removed_tickers.csv` (`date_removed`, `action=removed`, `ticker`, `ticker_field`, `library_name`, `source_csv=index_library.csv`, `reason`, `audit_run_date=2026-07-12`, `replacement_status`, `target_identifier`, `notes`).
2. Remove (or, if a proxy exists, repoint) the row in `index_library.csv`.
3. Re-run the pipeline and confirm the row is gone / repointed and no new orphan appears.
4. For Class 2 industry sub-indices, do them as one batch with a shared `notes` tag (mirrors the existing `batch=STOXX600_sector` convention already in `removed_tickers.csv`).

**Effort:** Class 1 ~15 min (3 rows). Class 2 ~1 hr (batch retire + decide China/EM-vol re-sourcing). Class 3 ~half a day (47 rows need individual triage; many resolve to the pence-bug fix or a suffix correction rather than retirement).

---

### Appendix — example calls (for the executing session)

```text
# metadata
mcp__plugin_factiq_factiq__get_market_data { "function": "SYMBOL_SEARCH", "keywords": "SPDR S&P 500 ETF" }
mcp__plugin_factiq_factiq__get_market_data { "function": "OVERVIEW", "symbol": "SPY" }

# values
mcp__plugin_factiq_factiq__get_market_data { "function": "GLOBAL_QUOTE", "symbol": "SPY" }
mcp__plugin_factiq_factiq__get_market_data { "function": "TIME_SERIES_DAILY", "symbol": "SPY", "outputsize": "compact" }
mcp__plugin_factiq_factiq__get_market_data { "function": "FX_DAILY", "from_symbol": "EUR", "to_symbol": "USD" }

# macro mapping + check (one schema per run_sql call)
mcp__plugin_factiq_factiq__run_sql {
  "schema": "bls",
  "sql": "SELECT series_id, series_title, frequency, measurement_units, end_time FROM series WHERE series_title ILIKE '%unemployment rate%' AND adjusted_for_seasonality = true LIMIT 20"
}
mcp__plugin_factiq_factiq__run_sql {
  "schema": "bls",
  "sql": "SELECT time, value FROM data_points WHERE series_id = '<id>' ORDER BY time DESC LIMIT 13"
}

# NEW: rates cross-check against the live Federal Reserve / US Treasury schemas
# (confirm exact schema names from the live get_data_catalog first)
# policy / market rate — Federal Reserve schema
mcp__plugin_factiq_factiq__run_sql {
  "schema": "federal_reserve",
  "sql": "SELECT series_id, series_title, frequency, measurement_units, end_time FROM series WHERE series_title ILIKE '%federal funds%' AND frequency = 'Daily' LIMIT 20"
}
# US Treasury par yield curve — check constant-maturity Treasury tickers against THIS, not a generic rate
mcp__plugin_factiq_factiq__run_sql {
  "schema": "treasury",
  "sql": "SELECT s.series_id, s.series_title, d.time, d.value FROM series s JOIN data_points d ON d.series_id = s.series_id WHERE s.series_title ILIKE '%par yield%' AND s.series_title ILIKE '%10-year%' ORDER BY d.time DESC LIMIT 10"
}
```
