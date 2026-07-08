# Fable Recommendations — Architecture Review

**Date:** 2026-07-07
**Scope:** Full review of the codebase, `manuals/technical_manual.md`, `manuals/forward_plan.md`, the dated handover/audit memos, CI workflows, tests, and the `data/` layout.
**Guiding rule (per your brief):** recommend a change only where the current structure demonstrably causes recurring cost — bugs, drift, repo bloat, or untestability — with concrete evidence from this repo. Section 3 lists things reviewed and deliberately left alone.

**Constraints taken as fixed:** free public APIs only; GitHub Actions as the runtime; Google Sheets output stays; the codebase is maintained by a mix of you and Claude sessions, so readability beats abstraction and the dependency footprint stays minimal. The simple pipeline's future is treated as an open question (§2.4), not a constraint.

---

## Summary table

| # | Recommendation | Fixes | Effort | Priority |
|---|---|---|---|---|
| 1.1 | Enforce source precedence at runtime (kill last-writer-wins) | The frozen-mirror bug class (JP_INFL1, EU_INFL1, CN_INFL1) | M | **Highest** |
| 1.2 | One source registry instead of string-ladder dispatch | Registry drift; 54-branch ladders; 54 boilerplate wrappers | M | High |
| 1.3 | Route all sources through `base.fetch_with_backoff` | 25 hand-rolled retry loops | S | High |
| 1.4 | Move the module-level pipeline chain behind `__main__` | Import side effects; untestability | S | High |
| 1.5 | Run the offline test suite in CI on PRs | Zero test gate on merges to main | S | High |
| 1.6 | Deduplicate `library_sync.py`'s three copy-pasted trios | 3× maintenance of identical logic | S | Medium |
| 1.7 | Split `compute_macro_market.py` into a small package | 2,550-line file; merge-conflict surface | M | Low (opportunistic) |
| 1.8 | One narrow hard-fail class in the audit | Nothing gates the daily commit except a crash | S | Medium |
| 2.1 | Stop committing the 30 MB explorer artefacts; deploy to Pages | ~30 MB/day of binary-ish churn in git history | M | **Highest of Part 2** |
| 2.2 | Move `pipeline.log` / `data_audit.txt` out of git history | Whole-file diffs of mutable logs every run | S | Medium |
| 2.3 | Reduce hist-CSV churn (row-append discipline, then format options) | 8k-line daily rewrites of hist files; 103 MiB pack | M–L | Medium |
| 2.4 | Simple-pipeline decision path (canary test for `trigger.py`) | Unfalsifiable "is it still used?" blocker on §3.2 | S | Medium |
| 2.5 | Staged CI workflow with a single commit step | Partial-state commits, failure attribution | M | Low |

---

## Part 1 — Incremental recommendations

These keep the current shape — CSV registry, single daily Actions run, git-committed outputs — and could each land as an ordinary PR.

### 1.1 Enforce source precedence at runtime — retire implicit last-writer-wins

**Problem.** In `fetch_macro_economic.py`, the history merge's fallback mechanism is implicit: sources are fetched in a fixed read order and the last writer to a column wins. The tier system exists (`_attach_tiers`, `_select_winner` at lines 310/365 — used for **snapshot** dedup), and `data/source_fallbacks.csv` documents T0→T3 chains per indicator, but nothing walks those chains when the history is written. The technical manual itself calls the fallback "implicit."

This is the single most expensive structural gap in the repo, because it is the root cause of your dominant recurring bug class:

- **JP_INFL1** frozen at 8.49 (fixed via CPI split, PR #249)
- **EU_INFL1** silently frozen at 2.1% for six months — the live P0 in `manuals/2026-07-07-eu-freeze-freshness-china-handover.md`
- **CN_INFL1** on 1–3-year-stale FRED mirrors (P2 in the same memo)
- The 2026-06-18 source-wiring audit found **25 column collisions, 11 cadence mismatches, 14 columns where the runtime winner ≠ the declared primary, 18 ambiguous-precedence cases**.

Each incident so far has been fixed point-wise (repoint a series, split a definition). The class keeps reproducing because the architecture doesn't encode which source *should* win a column, so a frozen or coarser source can win silently.

**Recommendation.** Make column ownership explicit and enforced:

1. Add a `declared_primary` notion per served column (the wiring audit already computed this; it can live as a column in the `macro_library_*.csv` rows or as a generated `data/column_owners.csv`).
2. In the history merge, replace "last writer wins" with a winner function per column that prefers the declared primary but **demotes it when it fails a freshness/cadence guard** (you already have `freshness_thresholds.csv` and the cadence-rank logic inside `_select_winner` — this extends the tested snapshot tie-break to history writes).
3. Log every demotion loudly (`[FALLBACK] col=EA_HICP primary=estat stale 190d → fell back to ecb`) so `data_audit.py` Section A can surface it — a frozen primary then becomes a *reported event on day one*, not a silent six-month freeze.

**Why structurally better.** It converts the fallback chains from documentation (`source_fallbacks.csv`) into behaviour, and turns the frozen-mirror failure mode from "silent wrong data" into "audible fallback." It is also the substantive core of forward-plan item **A9** ("comprehensive data-credibility check") — value-plausibility bands are a good second layer, but precedence + freshness enforcement is the layer that would have caught all three INFL1 incidents.

**Does not change:** the library-CSV registry rule, source modules, or output schemas. Effort: **M**. Do this first; 1.2 makes it easier but is not a prerequisite.

### 1.2 One source registry instead of string-ladder dispatch

**Problem.** `fetch_macro_economic.py` (1,680 lines) dispatches to source modules via two ~27-branch `if src == "..."` / `elif` ladders (snapshot and history), backed by **54** near-identical `_fetch_<src>_snapshot` / `_fetch_<src>_history` wrappers that differ only in the module called. The source-label and cadence-rank mappings are additionally duplicated in `build_source_inventory.py` (`FILE_SOURCE`, `FANOUT`) and `library_sync.py`. Matching is on exact display strings (`"Banque de France"`, `"e-Stat"`); a typo falls into a silent `[WARN] Unknown source` skip path. The tell is that `data_audit.py::_check_registry_drift` exists specifically to police this wiring — an audit written to compensate for a structure.

**Recommendation.** A single registry in `sources/__init__.py`, mirroring the `_ALL_CALCULATORS` pattern that already works well in `compute_macro_market.py`:

```python
SOURCES = {
    "FRED":            SourceSpec(module=fred,  has_history=True,  tier_default=4),
    "Banque de France": SourceSpec(module=bdf,  has_history=True,  tier_default=1),
    ...
}
```

The two ladders collapse to one lookup each; the 54 wrappers collapse to two generic functions (any real per-source kwargs move into the spec); `build_source_inventory.py` and `library_sync.py` import the same table. An unknown label becomes a startup error listing valid labels instead of a silent skip.

**Why structurally better.** Adding a source today means touching ~5 places across 3 files that must stay string-identical; afterwards it means one registry entry plus the module. It deletes roughly 400–500 lines of boilerplate and removes the drift class outright (the `_check_registry_drift` audit can then verify library CSVs against one table instead of three). This is a proven in-repo pattern, not a new abstraction. Effort: **M** (mechanical, easy to verify: byte-identical output CSVs on a re-run).

### 1.3 Consolidate retry/backoff into `sources/base.fetch_with_backoff`

**Problem.** The shared helper exists in `sources/base.py`, but only 4 of 28 source modules use it (`imf`, `oecd`, `worldbank`, `sec_edgar`). There are **25 hand-rolled `for attempt in range(...)` retry loops** across `sources/*.py`; `sources/fred.py:257–286` is essentially a line-for-line reimplementation of the base function. `fetch_data.py` and `fetch_hist.py` carry their own copies too.

**Recommendation.** Route every plain-HTTP source through `fetch_with_backoff` (parameterise the few real differences: which status codes retry, per-source budgets/circuit-breakers from Pattern 10). Sources with genuinely unusual transport (Bright Data escalation for ifo/ISM) keep their own path but still share the backoff arithmetic.

**Why structurally better.** Retry policy is exactly the kind of thing that should change in one place (e.g. when you next hit a rate-limit change or want jitter). Today a policy fix means ~25 edits by whoever (you or a Claude session) remembers all the copies. Effort: **S–M**, fully mechanical, one module per commit if you want it low-risk.

### 1.4 Kill the import-side-effect pipeline in `fetch_data.py`

**Problem.** `main()` is guarded at line 834, but lines 855–998 run the rest of the pipeline — `run_comp_hist()`, `run_phase_macro_economic()`, `run_phase_e()`, the SEC EDGAR block — at **module level**. The header comment ("PASTE THIS BLOCK at the bottom of fetch_data.py") records the append-driven history. Consequence: `import fetch_data` executes a multi-hour, multi-API pipeline. Nothing can unit-test, lint-import, or selectively reuse anything in `fetch_data.py` without triggering it, and any future tooling (a test collector, a doc generator, an incremental-fetch mode) has to know not to import it.

**Recommendation.**

```python
def run_all():
    main()
    _run_isolated("CompHist", lambda: fetch_hist.run_comp_hist())
    _run_isolated("macro_economic", ...)
    _run_isolated("Phase E", ...)
    _run_isolated("EquityFundamentals", ...)

if __name__ == "__main__":
    run_all()
```

The per-phase broad `try/except` isolation (Pattern 1) is preserved verbatim inside `_run_isolated`; the workflow's `python fetch_data.py` invocation is unchanged.

**Why structurally better.** Phase isolation is a good pattern; it just belongs in a function. This is a prerequisite for 1.5 (tests that import pipeline modules), for the incremental-fetch roadmap item (§3.6), and for the staged workflow option (§2.5). Effort: **S** — pure indentation/move; verify with a dry run.

### 1.5 Gate merges with the offline tests

**Problem.** The repo has a real offline suite — `test_tier_merge`, `test_atlanta_fed_parse`, `test_estat_parse`, `test_ism_prnewswire_parse`, `test_library_utils_hist`, `test_macro_hist_merge`, `test_dbnomics_plausibility` — that is **never run by CI**. The only CI test execution is the 10 network smoke modules inside the daily data run (`update_data.yml` line 82), with `continue-on-error: true`. There is no PR/push workflow at all, so a PR that breaks the tier tie-break or the hist archiver merges green and is discovered by the next day's data.

**Recommendation.** Add a ~20-line `ci.yml` on `pull_request` + `push` to main: checkout, install `requirements.txt`, `SKIP_NETWORK_TESTS=1 python -m unittest <offline modules> -v`. Make it a required check. Keep the smoke tests exactly where they are — non-blocking in the daily run is the right design for network-dependent checks.

**Why structurally better.** Your merge-eve safety currently rests on whoever authored the PR having run the tests locally — with Claude sessions authoring many PRs, an enforced gate is the difference between "convention" and "guarantee." The suite already exists and is deterministic; this is pure wiring. Effort: **S**. (Keeping the module list fresh can be one `Glob`-driven line: run every `test_*` that skips cleanly offline, or adopt a `test_offline_*` naming convention.)

### 1.6 Deduplicate `library_sync.py`

**Problem.** Three copy-pasted trios — `_comp_*` (lines 76–108), `_macro_econ_*` (175–249), `_macro_mkt_*` (277–311) — implement the same expected/present/orphan-index/archive shape per hist↔library pair, differing only in file paths, key column, and metadata-prefix depth.

**Recommendation.** One `SyncSpec` (hist path, library loader, key column, prefix rows) and one generic `sync(spec, confirm)` loop over the three specs. Adding a fourth hist pair (e.g. when the multifreq plan lands) becomes a spec entry, not a fourth copy.

**Why structurally better.** This tool mutates committed history files; identical logic in three copies is exactly where a fix applied to two of three creates a subtle data bug. Effort: **S**. (Same disease, smaller dose, exists in the archived-column handling — fold it in.)

### 1.7 Split `compute_macro_market.py` — opportunistic, not urgent

**Problem.** 2,550 lines, 107 `_calc_*` functions. The *dispatch* is the best pattern in the repo (`_ALL_CALCULATORS`); the file size is the only issue: it's the most-edited file (every new indicator), so it has the largest merge-conflict surface between concurrent Claude sessions, and finding one calculator among 107 costs scroll time.

**Recommendation.** A mechanical move into `calculators/` (per-region modules: `us.py`, `eu.py`, `asia.py`, `inflation.py`, `nowcast.py`) that each export their dict, merged in `calculators/__init__.py`. Shared helpers (`_log_ratio`, `_yoy`, `_rolling_zscore`, `make_result`, `REGIME_RULES`) move to `calculators/common.py`. No behaviour or abstraction change.

**Why only "Low/opportunistic":** unlike 1.1–1.3, nothing is *breaking* because of this file; it's ergonomics. Do it when the file next causes a real conflict or when the multifreq rewrite touches it anyway. Effort: **M** (mechanical but wide; verify byte-identical `macro_market.csv` on re-run).

### 1.8 One narrow hard-fail class in the audit

**Problem.** By design, `data_audit.py` always exits 0 and the smoke tests are non-blocking — a philosophy the technical manual defends and which is *mostly right* (a warning channel shouldn't block a data pipeline). But the net effect is that **nothing gates the daily commit except a hard crash**: the Atlanta-Fed-24%-nowcast class of wrong data ships, and so would a catastrophic regression (e.g. a protected column going all-NaN, or `macro_economic_hist.csv` shrinking by half).

**Recommendation.** Keep the audit a warning channel, but define one tiny CRITICAL class that returns a nonzero exit and skips the commit step for the *data* files (still upload `pipeline.log` for diagnosis): (a) any `SHEETS_PROTECTED_TABS` output empty/all-NaN, (b) any hist CSV losing more than N% of its rows or columns versus the committed version. Two checks, deliberately hard to trigger falsely.

**Why structurally better.** Right now the git history is your rollback mechanism, but a bad commit still propagates to Sheets and `trigger.py` the same morning. A minimal circuit breaker preserves the "never block on quality warnings" philosophy while making the two genuinely unrecoverable-downstream cases impossible to ship. Effort: **S**.

---

## Part 2 — Larger structural options

Bigger moves, each with tradeoffs. 2.1 and 2.2 are near-pure wins; 2.3 has real design choices; 2.5 is optional polish.

### 2.1 Stop committing the explorer artefacts; deploy to GitHub Pages instead

**Problem.** `docs/indicator_explorer.html` (13.5 MB) and `docs/indicator_explorer_mkt.js` (16.4 MB) are regenerated and re-committed daily. They are build artefacts — fully reproducible from the committed CSVs by `docs/build_html.py` — yet they dominate repo weight (the pack is at 103 MiB and grows with every daily blob).

**Recommendation.** Serve them via GitHub Pages **artifact deployment** (`actions/deploy-pages`): the daily workflow builds the explorer and uploads it as a Pages artifact instead of committing it. No gh-pages branch, no history at all for artefacts. `.gitignore` the two files; do a one-time history rewrite (`git filter-repo`) to purge old blobs if you want the ~100 MiB back, or just let history stop growing.

**Tradeoffs.** You lose "old explorer versions in git" — but every input CSV *is* versioned, so any past explorer can be rebuilt from a checkout. URL changes from `raw.githubusercontent`/local file to `kasim81.github.io/market_dash_auto/…` (bookmark update). This is the highest-value, lowest-regret item in Part 2: it removes ~30 MB/day of churn without touching the data model at all. Effort: **M** (workflow edit + one-time cleanup).

### 2.2 Move `pipeline.log` and `data_audit.txt` out of git history

**Problem.** A 98 KB mutable log and a 20 KB report are committed every run, producing whole-file diffs daily forever. Their value is post-mortem diagnosis and the daily Issue comment — neither needs git history.

**Recommendation.** Upload both as workflow **artifacts** (`actions/upload-artifact`, retention 30–90 days) and keep posting `audit_comment.md` content to the daily-audit Issue (which is already your rolling 10-comment window). Stop committing all three files. The manuals' references to "committed even on crash for post-mortem" are satisfied by artifacts, which survive crashes the same way (upload with `if: always()`).

**Tradeoff:** logs expire after the retention window; if you value >90-day forensics, keep committing `data_audit.txt` only (small, and its diffs are meaningful) and artifact the log. Effort: **S**.

### 2.3 Reduce hist-CSV churn — first fix the writes, then consider format

**Problem.** Yesterday's data commit (`ba51d46`) shows the real issue: `macro_economic_hist.csv` alone diffed **8,330 lines**, and the run totalled ~8,261 insertions / 8,239 deletions — the hist files are effectively *rewritten*, not appended to, every day. That both bloats history and destroys the main benefit of git-as-database (meaningful diffs: "what changed today?" is currently unanswerable from the diff).

**Recommendation — in order:**

1. **(Keep git, fix the writer — do this regardless.)** Make hist writes append-stable: canonical float formatting (fixed `float_format`), stable column order, and never re-emitting unchanged historical rows with re-derived values. If a re-fetch revises history (sources do revise), that's a legitimate diff; today's noise is formatting/re-fill churn drowning those legitimate revisions. This makes daily diffs small, human-auditable, and cheap to store — and it directly serves your freshness/credibility auditing, because "which historical values changed today" becomes visible.
2. **(Optional, if weight still matters after 1 and 2.1/2.2.)** Move only the `_hist_x` **sister archives** (append-only by design, never human-diffed) to compressed Parquet. Keeps every human-facing CSV diffable; pandas reads/writes Parquet natively via `pyarrow` (one dependency). The `_hist` heads stay CSV.
3. **(Alternative, if you want zero format change.)** A separate `data` branch for machine commits, squashed monthly to a single snapshot commit. Preserves CSVs and diffs while keeping `main`'s history human-scale. Cost: cross-branch workflow complexity — I'd only pick this if Parquet is unacceptable.

Given your "diffs are valuable" constraint, step 1 is the structural fix and steps 2–3 are optional weight reduction. Effort: step 1 **M**, step 2 **S**, step 3 **M**.

### 2.4 Simple-pipeline decision path

Forward-plan §3.2 (retire the simple pipeline) has been blocked indefinitely on "confirm whether `trigger.py` still reads the market_data tab." That's currently unfalsifiable from inside this repo, so make it falsifiable:

1. Check the Google Cloud console for the service account's Sheets API usage, or simpler: `trigger.py` runs at 06:15 London on your Windows machine — check whether the scheduled task still exists/fires.
2. If you can't check the client side, run a **canary**: add a timestamp cell to a non-protected corner of the tab and have `trigger.py` (one-line change, if it's alive) echo it somewhere observable; or temporarily rename the tab for one day and see if anything breaks.
3. Then either delete the simple pipeline (removing `load_simple_library`, `collect_simple_fred_assets`, and the ~70-instrument duplicate fetch — the comp pipeline already covers the data), or record in the forward plan that it's confirmed-live with a named consumer and re-check date.

The structural point: an output with an *unknown* consumer is the worst of both worlds — it can't be changed safely and can't be deleted. Effort of deciding: **S**.

### 2.5 Staged CI workflow (optional)

Split the single 120-minute job into `fetch` → `build-explorer` → `audit` jobs passing the `data/` directory as an artifact, with one final commit/deploy step. Benefits: failure attribution per stage, re-run only the failed stage, and no partial-state commits. Tradeoff: meaningful workflow complexity (artifact plumbing, ~3× job boilerplate) for a pipeline that currently fails rarely and is protected by phase isolation anyway. **Only worth doing if you adopt 2.1** (the deploy step then has a natural home) or when the multifreq migration forces workflow surgery regardless. Not recommended on its own today.

### Sequencing note — the multifreq plan (forward_plan §5)

Nothing above is thrown away by the planned Friday-spine → native-frequency migration. Two items are effectively *prerequisites* that de-risk it: 1.2 (the migration must touch every source path once — far safer through one registry than two 27-branch ladders) and 1.1 (precedence enforcement defines the correctness contract that a multi-frequency merge has to preserve). 1.5's test gate is what lets a migration of that size proceed in reviewable steps. I'd sequence: 1.4 → 1.5 → 1.3 → 1.2 → 1.1 → (2.1/2.2 anytime) → multifreq.

---

## Part 3 — Reviewed and deliberately not recommended for change

Per your brief, these were examined and are endorsed as-is:

- **The data-layer registry rule** (every identifier in a `macro_library_*.csv`, never in Python; forward_plan §0). This is the repo's best architectural decision — it's what makes the codebase safe for mixed human/Claude maintenance. Everything in Part 1 strengthens it; nothing weakens it.
- **The `_ALL_CALCULATORS` registry** in `compute_macro_market.py` — the model that 1.2 copies.
- **Phase isolation** (Pattern 1) — broad per-phase `try/except` is unusual style but correct for a daily data pipeline; 1.4 relocates it without changing it.
- **The `_hist` / `_hist_x` sister-archive concept** (Pattern 9) — the right defence against rolling-window source truncation. The known `keep="first"` self-heal question is real but already tracked with candidate designs in forward_plan §3.6a; no new recommendation beyond: resolve it before 2.3-step-2 changes the archive format.
- **stdlib `unittest` over pytest** — keeping the CI dependency surface minimal is coherent; 1.5 works fine with unittest.
- **`print` + `tee pipeline.log` logging** — adequate for a single-process daily batch; a logging framework would add ceremony without new capability. Worth only a convention (consistent `[WARN]`/`[ERROR]`/`[FALLBACK]` prefixes) so audits can grep severity — which 1.1's demotion logging would formalise anyway.
- **Sheets protected-tab safety** (`SHEETS_PROTECTED_TABS`, legacy-tab sweeping) and the **audit-as-warning-channel philosophy** — kept, with only the two-check circuit breaker of 1.8 as an exception.
- **Small CSVs as committed config/state** (`freshness_thresholds.csv`, `manual_splits.csv`, `yfinance_failure_streaks.csv`, `istat_edition_cache.csv`, per-source libraries) — git-versioned, diffable config is a feature here, not debt. 2.3 targets only the multi-MB rewritten hist files.
- **The audit/writeback loop** (Phase H, 14-day dead-ticker flips) — sound; the weekly human-in-the-loop retirement review is already planned (§3.8) and needs no re-design here.
- **The manuals system** — the count drift I found (indicator_manual's "68" vs 108; 66-vs-70 simple instruments; 1950-vs-1990 comp start; the stale multifreq copy in `multifreq_plan.md` vs forward_plan §5) is refresh-routine territory, not architecture; flagging it here so the next `refresh-manuals` run picks it up.

---

*Prepared from a full-repo review session on 2026-07-07. Evidence line numbers refer to the tree at commit `08e7026`.*
