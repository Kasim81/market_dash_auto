# Manual-Integration Plan — folding the FactIQ handover into the manuals

**Prepared:** 2026-07-14 · **Target manuals:** `manuals/technical_manual.md`, `manuals/forward_plan.md`
**Source material:** everything under `handover/` (FactIQ handover, `FACTIQ_AUDIT_PLAN.md`, `audit/AUDIT_REPORT.md` + artefacts).

## Framing — what actually needs doing

The FactIQ workstream is in an unusual state: **the code and data changes already merged to `main`** (4 fixes via PR #265; the `handover/` folder via PR #266), but **the two hand-written manuals were never updated to match.** So this is mostly a *reconciliation* job (describe what already shipped) plus a *forward-capture* job (record what remains as planned tasks) — not a "document a proposal" job.

Two distinct kinds of content to integrate, and they go to different manuals:

- **Technical manual** = *current state of the code/data as it exists on `main` today.* → the 4 landed fixes + the new Treasury source + the fact that FactIQ is an interactive-only audit tool.
- **Forward plan** = *what is still outstanding + roadmap.* → the §11 direct-wire roadmap, the §12 dead-ticker cleanup backlog, the audit-revalidation task, the latent encoding bug, the architecture-teardown recommendations, and chronology.

The one trap to avoid (called out in the handover §1): **do not describe FactIQ as a pipeline data source.** It is OAuth-MCP, interactive-agent-only, and can *never* be imported by the headless CI pipeline. In both manuals it is an audit/analysis reference + a golden-snapshot hedge, in the same conceptual slot as a reviewer, **not** alongside `sources/*.py`.

---

## Part A — Technical manual edits (describe what already shipped)

Ordered by section number. Each item is a landed change that the manual currently misdescribes or omits.

### A1. New Treasury source — `sources/treasury.py` (fix #4)
`sources/treasury.py`, `data/macro_library_treasury.csv`, the `SourceSpec("Treasury", …)` in `sources/__init__.py`, and the `treasury_src` wiring + `TREASURY_DELAY = 0.6` in `fetch_macro_economic.py` all exist on `main` but appear in **no** manual section. Edits:

- **§5 Data Sources & APIs** — add a "**US Treasury — daily par-yield curve**" entry (keyless `home.treasury.gov` CSV feed, per-year pagination + backoff, 13 tenors). Note explicitly: this is the daily par curve, **not** FiscalData (`api.fiscaldata.treasury.gov` 404s on the daily curve — monthly averages only). Cross-reference §11 of `forward_plan` as milestone 1 of the direct-wire roadmap.
- **§9.5 header count** — "34 modules" → "35 modules"; add `treasury` to *both* printed coordinator read-order lists (the one at ~line 908 and the one at ~line 970 in `load_all_indicators()`), matching the actual order in `fetch_macro_economic.py:128`.
- **§9.5.x** — add a numbered subsection for `sources/treasury.py` (function table: `load_library`, snapshot fetcher, history fetcher; note it's the reference template for the forward direct-wire sources).
- **§2 Directory Structure** and **§7 CSV File Inventory** — add `sources/treasury.py` and `data/macro_library_treasury.csv` (13-tenor par-yield library) to the inventories.

### A2. Pence-gate currency fix — `fetch_data.py` (fix #3)
The manual describes the **old** heuristic (`.endswith(".L")` + median > 50) in three places; the code now gates on `base_currency ∈ {GBP, GBX}` via `_is_pence_quoted()` / `_should_convert_pence()`. Update all three:

- **§5** (~line 272 table row "Pence correction", and the ~line 294 bullet) — replace "Dynamic `.endswith(".L")` + median > 50 check" with the gated version.
- **§10 → "LSE Pence Correction"** (~line 1586) — rewrite: the ÷100 now fires only when `_is_pence_quoted(ticker, base_currency)` is true (`.L` **and** currency GBP/GBX) **and** median > 50. Name the two helpers and note the bug it fixed: EUR-quoted London lines (`IEAC.L` ~€120) were being wrongly shrunk to ~1.2. Note returns were unaffected — display-only.
- Cross-reference the regression test `fixes/test_pence_gate.py`.

### A3. EMB proxy + foreign-currency-label fixes — `data/index_library.csv` (fixes #1, #2)
These change **displayed numbers** and touch the library that §8 treats as the source of truth. The manual's §13 "Metadata / Label Issues — currently clean (last audit 2026-04-21)" is now stale — a newer audit (2026-07-14, FactIQ) found and fixed four issues. Edits:

- **§13 Metadata / Label Issues** — bump the "last full audit" line to note the 2026-07-14 FactIQ audit, and add the resolved items:
  - **EMB** — was proxying 9 library rows and carried an `ARS` label on a USD fund (1Y USD return flipped +11.69% → −13.35%); the 8 country-proxy rows were removed, EMB kept as a standalone USD ETF. (script `audit/fix_emb.py`)
  - **FEZ / ASHR** — split into a native-currency index row (`^STOXX50E` EUR / `000300.SS` CNY) + a USD ETF row. **HYXU → USD**. (scripts `fixes/fix_currency_labels.py`, `fixes/split_dual_ticker_rows.py`)
- **§8 index_library.csv** — under "Library Maintenance", note the dual-ticker split pattern (native index row + USD ETF row) as an accepted representation for US-listed foreign-exposure ETFs.

### A4. FactIQ as an audit reference (not a source) — new short subsection
Add a **brief** subsection — best home is end of **§5** ("Reference / audit-only data — not pipeline sources") or **§14 Operational Notes**. Content: FactIQ is an authenticated MCP plugin used *interactively* to cross-check the pipeline against an independent warehouse; it is **read-only, 50-row/call, ~1 req/s, no CI import path**. Point to `handover/` for the full workstream and to `handover/audit/golden/` for the golden snapshot captured while FactIQ is free. State the rule plainly: **replicate the upstream source, never re-scrape FactIQ's warehouse; FactIQ never becomes a `sources/*.py`.**

### A5. Latent encoding bug — `_load_tier_map()` (pre-existing, surfaced by the audit)
`_load_tier_map()` in `fetch_macro_economic.py` reads library CSVs without `encoding="utf-8"` → `UnicodeDecodeError` on Windows cp1252 (harmless on CI's UTF-8). This is a **known issue**, so record it in **§13 Known Issues & Status** with the one-line fix noted, and mirror it as a task in the forward plan (B-series backlog, see B3 below). *(Verify the bug still exists before writing — grep `_load_tier_map` for an `encoding=` arg.)*

---

## Part B — Forward plan edits (capture what remains + roadmap)

### B1. Direct-wire source roadmap (`FACTIQ_AUDIT_PLAN.md` §11) → a §3.1 subsection
Add **§3.1.x "Direct-wire replicable upstream sources (FactIQ source-inventory strategy)."** Content:

- The three-bucket model: (1) *already covered* via FRED/IMF/WorldBank — add series ids only; (2) *replicate directly* — BLS, BEA, Census, EIA, US Treasury par-yield (**done, milestone 1**), SingStat, Japan e-Stat; (3) *rely on FactIQ-as-aggregator residue* — China NBS/customs, India RBI/DGCI&S, Korea/Taiwan customs, CBO (no clean keyless API).
- **Reconcile against what already exists**: `sources/bls.py` and `sources/estat.py` are *already wired* — so for BLS/Japan the task is "extend series coverage," not "build new." Frame the genuinely-new modules as **BEA, Census, EIA, SingStat**, each built on `sources/treasury.py` as the template. *(Do a quick `ls sources/` reconciliation pass before finalising the list so the roadmap doesn't ask to build what exists.)*
- The hard constraint (repeat from A4): a `sources/factiq.py` is **not viable** — headless CI has no FactIQ auth path.

### B2. Dead-ticker & coverage-gap cleanup (`FACTIQ_AUDIT_PLAN.md` §12) → §2 backlog or §3.8
This is a remediation backlog that fits either **§2.A "Broken-source & freshness backlog"** or the existing **§3.8 "Weekly Retirement Review Workflow"** (it uses the same `removed_tickers.csv` + `yfinance_failure_streaks.csv` machinery §3.8 already describes — likely the cleanest home). Capture the three classes:

- **Class 1 — genuinely dead (retire):** `^CM100`, `^SP500-151050`, `^SP500-551020` (frozen ≥10y, serving stale values).
- **Class 2 — no-output gaps (~29 rows):** ~26 `^SP500-xxxxxx` GICS industry sub-indices (yfinance discontinued), `000905.SS`/`000852.SS`, `^VXEEM`.
- **Class 3 — empty output rows (47):** foreign-listed UCITS proxies (`.L`/`.DE`/`.PA`/`.JO`) — triage into fixable / dead / needs-fallback.
- **Guardrails to preserve verbatim:** do **not** hard-delete (use the `removed_tickers.csv` ledger); the 52 `UNAVAILABLE` rows are curated-by-design, **not** dead — exclude them. **Re-check against LIVE `index_library.csv` first** (it moved ~28 lines since the audit).

### B3. Audit-revalidation + encoding-fix tasks → §2 priority tasks
- **Re-validate the audit against live data** — the value-level findings used the stale 2026-05-13 snapshot; re-run the Tier-A value + Tier-B promotion sweeps against current `market_data_comp.csv` if value-level confidence is needed. Note the structural findings were already re-confirmed and fixed.
- **CSI 500 (`000905.SS`) re-source** — FactIQ prices it (~8138 CNY) though the library marks it UNAVAILABLE; candidate re-wire. (CSI 1000 `000852.SS` genuinely unpriceable — leave it.)
- **`_load_tier_map()` encoding one-liner** (mirror of A5) — small, well-scoped B-backlog item.

### B4. Architecture-teardown recommendations (`FACTIQ_AUDIT_PLAN.md` §8.3) → "Candidate next tracks"
Add to the existing **"Candidate next tracks (broader)"** list (~line 533) the FactIQ-derived design ideas, each as a one-liner with the §8.3 cross-reference — these are *optional strategic* items, not committed work:

- Port the per-source `macro_library_*.csv` + `*_hist.csv` into a single **3-table DuckDB store** (`series` / `data_points` / `dimensions`) — the audit's internal checks collapse to 5-line queries.
- **Cache-first discipline** for `fetch_data.py`/`fetch_macro_economic.py` pulls (raw response to disk before transform → every future audit is diffable).
- A **ChartSpec-style spec layer** between pipeline and outputs before adding any new viz surface.
- Write the audit up as a repeatable **`report-patterns/data-audit.md`** playbook so it re-runs with no rediscovery.

### B5. Golden-snapshot hedge + FactIQ free→paid risk → a forward note
Record (short, in §2 or the risk area of §3.1): FactIQ is free "all data, no limits" *today* but may go paid; the golden snapshot under `handover/audit/golden/` is the hedge — **keep it**, and future re-audits regress against it if live access disappears.

### B6. Chronology
Add to **§4 Project Chronology**: 2026-07-12 FactIQ audit (676 findings, 4 real bugs), 2026-07-14 remediation merged (PR #265), handover folder added (PR #266).

---

## Part C — Execution notes for whoever writes the edits

1. **Verify-before-write on every item.** The manuals are line-referenced above from today's `main`; confirm each anchor still matches before editing (the daily pipeline commits move line numbers). For each landed fix, re-grep the code to confirm the described behaviour (e.g. `_should_convert_pence`, `SourceSpec("Treasury"`, `_load_tier_map` encoding) rather than trusting this plan or the handover text.
2. **The `refresh-manuals` skill is the right vehicle.** This whole job is exactly what `manuals/`'s `refresh-manuals` routine does (reconcile manuals against code, open a PR). Prefer running it over hand-editing, so the house style/section conventions are preserved. This plan is its work-list.
3. **Keep FactIQ framing consistent** across both manuals (audit reference, never a pipeline source) — the single most important correctness point.
4. **Don't duplicate.** BLS and Japan e-Stat already have `sources/*.py` + backlog entries in `forward_plan` §2/§3.1 — extend, don't re-add.
5. **Split the PR sensibly** if desired: technical-manual reconciliation (Part A, describes shipped code) is lower-risk and can land first; forward-plan additions (Part B) are additive roadmap.

## Suggested sequencing
1. Part A (technical manual) — reconcile to shipped state. Lowest risk, highest "the manual is now correct" value.
2. Part B1–B3 (forward plan) — the concrete outstanding tasks. Medium value.
3. Part B4–B6 — strategic/optional + chronology. Do last.
