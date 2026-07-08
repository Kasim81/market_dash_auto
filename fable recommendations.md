# Fable Recommendations — Architecture Review + Live Data Repairs

**Date:** 2026-07-07 (merged 2026-07-08 with `manuals/2026-07-07-eu-freeze-freshness-china-handover.md`)
**Scope:** Full review of the codebase, `manuals/technical_manual.md`, `manuals/forward_plan.md`, the dated handover/audit memos, CI workflows, tests, and the `data/` layout — **plus** the live data-repair work order raised after the CPI split (PR #249) and audit closure (PR #250) landed.
**Guiding rule (per your brief):** recommend a change only where the current structure demonstrably causes recurring cost — bugs, drift, repo bloat, or untestability — with concrete evidence from this repo. Section 4 lists things reviewed and deliberately left alone.

**Constraints taken as fixed:** free public APIs only; GitHub Actions as the runtime; Google Sheets output stays; the codebase is maintained by a mix of you and Claude sessions, so readability beats abstraction and the dependency footprint stays minimal. The simple pipeline's future is treated as an open question (§2.4), not a constraint.

**How this document is organised.** Part 0 is the *operational* track — live, broken-today indicators and the freshness tuning that makes the next freeze visible; it needs the credentialed Codespace. Parts 1–2 are the *structural* track — architecture changes that stop the bug class from reproducing. They meet in item 1.1: Part 0 fixes the current instances, 1.1 is the durable fix for the class.

---

## Summary table

| # | Recommendation | Fixes | Effort | Priority |
|---|---|---|---|---|
| 0.1 | Repair the frozen `EU_INFL1` (Eurostat HICP stall → likely ECB repoint) | The one *currently broken* live composite | M–L | **Do first (Codespace)** |
| 0.2 | Freshness-honesty pass (`freshness_override_days` tuning + drop dead `JPN_CPI_INDEX`) | 78 noise-stale flags drowning genuine freezes | S | **Do with 0.1 (same PR)** |
| 0.3 | China inflation cluster (`CN_INFL1` on 1–3-year-frozen mirrors) | Degraded CN inflation regime read | M | High (after 0.1) |
| 1.1 | Enforce source precedence at runtime (kill last-writer-wins) | The frozen-mirror bug class (JP_INFL1, EU_INFL1, CN_INFL1) | M | **Highest structural** |
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

## Part 0 — Live data repairs (Codespace work order)

> Absorbed from `manuals/2026-07-07-eu-freeze-freshness-china-handover.md`
> (created after PR #249 CPI split + PR #250 audit closure and the 2026-07-07
> daily re-run `ba51d46`). **Run in the Codespace** — needs live network +
> `FRED_API_KEY` / `ESTAT_APP_ID` / `BLS_API_KEY` / `BDF_API_KEY` /
> `BRIGHTDATA_API_KEY` (all present there); `GOOGLE_CREDENTIALS` optional
> (skip the Sheets push; CSVs are written either way).

### Architecture rules that bind this work

- **Every fetched identifier lives in a `data/macro_library_*.csv`, never in a
  `.py` literal** (`forward_plan.md` §0). Everything below is CSV edits plus, at
  most, a one-line calculator repoint.
- The runtime merge is **tier-aware, cadence-first, staleness-fallback**
  (`fetch_macro_economic._dedupe_snapshot_rows` / `_select_winner`, unit-tested
  in `test_tier_merge.py`). Do **not** touch that logic. A column with two
  sources of the same measure-kind lets the finer cadence / fresher obs win
  automatically.
- Freshness is judged by `data_audit.py` Section C against
  `data/freshness_thresholds.csv` (Daily 5 / Weekly 10 / Monthly 45 / Quarterly
  120 / Annual 540 days) unless a row sets its own `freshness_override_days`.
- **Validation gate for every composite touched: it must MOVE month-to-month
  after the change.** A frozen-flat raw = a broken live indicator (that is how
  `JP_INFL1` hid at a flat 8.49 for months).

Environment check before starting:

    python3 -c "import os;print({k:bool(os.environ.get(k)) for k in ['FRED_API_KEY','ESTAT_APP_ID','BLS_API_KEY','BDF_API_KEY','BRIGHTDATA_API_KEY']})"
    curl -s --max-time 20 "https://api.db.nomics.world/v22/series/Eurostat/prc_hicp_manr/M.RCH_A.CP00.EA20?observations=1" | head -c 200

### 0.1 (P0) — `EU_INFL1` is silently frozen — the same class as the JP_INFL1 bug

**Evidence.** `EU_INFL1_raw` (from `data/macro_market_hist.csv`, month-end) has
been **flat at 2.1% for 6 months** while the healthy composites move:

    JP_INFL1:  2.10 → … → 1.56 → 1.27           ✅ (fixed by PR #249)
    US_INFL1:  2.53 → 2.87 → 3.11 → 3.27 → 2.92  ✅
    EU_INFL1:  2.10 → 2.10 → 2.10 → 2.10 → 2.10  ❌ frozen since 2026-01

`_calc_EU_INFL1` = `mean(EA_HICP, EA_HICP_CORE_YOY)`. Both inputs stall at
`last_obs = 2026-01-02` (age ~186d) in the 2026-07-07 audit — and the three EU
sentiment series stall at the **same** date:

| Col | DB.nomics series_id | last_obs |
|---|---|---|
| `EA_HICP` | `Eurostat/prc_hicp_manr/M.RCH_A.CP00.EA20` | 2026-01-02 |
| `EA_HICP_CORE_YOY` | `Eurostat/prc_hicp_manr/M.RCH_A.TOT_X_NRG_FOOD.EA20` | 2026-01-02 |
| `EU_ESI` | `Eurostat/ei_bssi_m_r2/M.BS-ESI-I.SA.EA20` | 2026-01-02 |
| `EU_IND_CONF` | `Eurostat/ei_bssi_m_r2/M.BS-ICI-BAL.SA.EA20` | 2026-01-02 |
| `EU_SVC_CONF` | `Eurostat/ei_bssi_m_r2/M.BS-SCI-BAL.SA.EA20` | 2026-01-02 |

All rows live in `data/macro_library_dbnomics.csv`. The coordinated stall at one
date screams a **Eurostat-side dataset/vintage change at year-end 2025**, not a
DB.nomics-only mirror bug.

**Already ruled out (do NOT repeat):** "just switch to the direct Eurostat API"
— probed
`.../statistics/1.0/data/prc_hicp_manr?coicop=CP00&unit=RCH_A&geo=EA20&sinceTimePeriod=2025-10`
→ it also returns **only through 2025-12** (2.1, 2.1, 2.0). The stall is
upstream of DB.nomics for this exact `RCH_A / EA20 / CP00` slice.

**Recommended approach (verify live before repointing):**

1. **Find why the slice stalls.** Likely a rebase / geo-composition change at
   2026-01 (EA20 vs EA / EA19), or the `RCH_A` (annual-rate) product was
   superseded. Probe: the `prc_hicp_midx` **index** dataset (compute YoY from
   the 12-month ratio), and `geo=EA` / `geo=EU27_2020`, with newer
   `sinceTimePeriod` values, on both DB.nomics and the direct Eurostat API.
2. **Strong lead — the ECB Data Portal (already wired, `sources/ecb.py`).** ECB
   publishes euro-area HICP (the `ICP` dataset, e.g. an
   `ICP.M.U2.N.000000.4.ANR` annual-rate key and the ex-energy-food core
   equivalent). We already use ECB for CISS, CES, the AAA yield curve and
   `EZ_M3`, so a HICP repoint is low-friction and ECB is the authoritative
   euro-area publisher. **Verify the exact key returns fresh monthly data
   (should have May/Jun 2026) before wiring.**
3. Repoint `EA_HICP` / `EA_HICP_CORE_YOY` to the fresher source (add/adjust the
   library row; the cadence-first merge prefers the fresher obs). ECB → rows in
   `data/macro_library_ecb.csv`; corrected Eurostat slice → edit the
   `data/macro_library_dbnomics.csv` rows in place.
4. Same freshness check for the 3 EU sentiment series (Eurostat Business &
   Consumer Survey). If no fresher path exists they become a documented Known
   Data Gap — but HICP is the priority because it drives `EU_INFL1`.

**Notes.** `EU_NOWCAST1` still **moves** (0.77 → 0.90) despite `EZ_IND_PROD` /
`EZ_RETAIL_VOL` being ~214d stale, so it is a lower concern — but the same
Eurostat `teiis080` / `teiis260` family is stale; fold it into the same probe.
Effort: **M–L** (discovery is the work; the CSV repoint is trivial).

### 0.2 (P1) — Freshness-honesty pass (restore the audit's signal-to-noise)

The 2026-07-07 run shows **79 issues (78 stale)** — most are *honest publication
lag under too-tight tolerances*, which is exactly why the genuine `EU_INFL1`
freeze was invisible in the pile. Widen `freshness_override_days` **only where
the source's real cadence justifies it** — honesty tuning, not hiding 0.1. Read
each row's current value from the library before editing (don't trust
`awk -F,` — the notes columns contain commas; use `csv`/pandas).

1. **Normal-lag monthly series (add/raise `freshness_override_days`):**
   - **OECD COICOP2018 CPI-YoY family** (7 rows in
     `data/macro_library_dbnomics.csv`: `JPN_CPI_YOY`, `CAN_CPI_YOY`,
     `CHE_CPI_YOY`, `FRA_CPI_YOY`, `ITA_CPI_YOY`, `NLD_CPI_YOY`,
     `DEU_CPI_YOY`). OECD publishes ~6–8 weeks in arrears, the mirror adds
     more — observed age ~67d vs a 45d default. Set **~90d**. (Cross-check
     `JPN_CORE_CPI_YOY`, which pre-dates the split and shows the same cadence.)
   - **e-Stat** `JPN_HH_EXP`, `JPN_EWS_DI` (`data/macro_library_estat.csv`):
     FIES / Economy-Watchers publish ~5–6 weeks late; observed ~67d vs a 60d
     override → set **~75–80d**. (`JPN_IND_PROD` at 123d/60d is borderline —
     the DB table carries finals ~T-3 months; leave or nudge, note in PR.)
   - **ONS** `GBR_CPI_YOY` (`data/macro_library_ons.csv`): 95d vs 75d → **~90d**.
2. **Event-driven policy rates** (§2.A A7 — flagged stale only because the bank
   hasn't moved). Daily-cadence rate series trip the tight tolerance whenever
   the central bank holds. Set `freshness_override_days` to the decision
   cadence (~90–120d): `JPN_POLICY_RATE` (boj, 18d vs 5d), `CAN_POLICY_RATE`
   (boc, 249d vs 7d), `CHN_POLICY_RATE` (dbnomics IMF/IFS — also genuinely
   mirror-stale; a wide override is honest either way). Scan `EA_DEPOSIT_RATE`,
   `GBR_BANK_RATE` for the same pattern.
3. **Dead, unused frozen mirror — drop:** **`JPN_CPI_INDEX`**
   (`data/macro_library_fred.csv`, FRED `JPNCPIALLMINMEI`, frozen 2021-06, age
   1859d). The CPI split renamed it from `JPN_CPI`; **nothing consumes it now**
   (grep confirms `JP_INFL1` uses `JPN_CPI_YOY`; no `_calc` reads
   `JPN_CPI_INDEX`). Pure EXPIRED noise — **drop the FRED row** (no live JP
   CPI-index source is wired, so the column simply disappears). A discontinued
   index level with no consumer and no live source is not worth carrying.
   (`CHN_CPI_INDEX` is the analogous case but **is** consumed by `CN_INFL1` —
   handle under 0.3, not here.)

**Guardrail:** never widen a tolerance to silence a *live composite* that has
gone flat. If a series is genuinely dead and feeds an indicator, that is a
0.1/0.3-class source-replacement problem, not an override.

Effort: **S** (CSV edits only). Validate with a keyed regen + re-run
`data_audit.py`; the STALE/EXPIRED count should drop toward the genuinely-dead
residue.

### 0.3 (P2) — China inflation cluster (`CN_INFL1` degraded; §2.A A1)

**Evidence.** `_calc_CN_INFL1` = `mean(_yoy(CHN_CPI_INDEX), CHN_PPI)` — **both
inputs frozen**:
- `CHN_CPI_INDEX` — `data/macro_library_fred.csv`, FRED `CHNCPIALLMINMEI`,
  frozen **2025-04** (age 459d).
- `CHN_PPI` — `data/macro_library_fred.csv`, FRED `CHNPIEATI01GYM`, frozen
  **2022-12** (age 1313d).

So `CN_INFL1` runs on ~1–3-year-old data. (`CHN_CPI_YOY`, the split column,
exists only on the World Bank annual fallback, itself frozen at 2023 — *not* a
fix.)

**Already ruled out during PR #249 (do NOT repeat):**
- **OECD COICOP2018 has no CHN coverage** (`REF_AREA=CHN` → 0 docs).
- **IMF IFS on DB.nomics is ~1 year stale** (`M.CN.PCPI_PC_CP_A_PT` last obs
  2025-07 when probed 2026-07).
- **NBS on DB.nomics** publishes CPI only as "same-month-last-year = 100"
  indices (`NBS/M_A010101…`) with recent values NA — messy units
  (YoY% = value − 100) and a fetch-time transform the current adapter doesn't do.

**Leads to try, in order:**
1. **IMF IFS *direct* API** (not the DB.nomics mirror) — the IMF SDMX/JSON
   endpoint may be current for `M.CN.PCPI_PC_CP_A_PT` (headline CPI YoY) and
   the PPI equivalent. If fresh, decide direct-IMF path vs accepting mirror lag.
2. **NBS direct** with a value−100 transform in a small helper — only if IFS
   fails; heavier lift.
3. **If nothing fresh exists**, formalize `CN_INFL1` as a *documented degraded
   indicator* in `forward_plan.md` Known Data Gaps (like the existing China
   entries) rather than leaving it silently frozen — and consider a
   plausibility band so the audit flags implausible drift.

Effort: **M** (discovery). Lower urgency than 0.1 (China is one region; the
`EU_INFL1` freeze affects the core euro-area inflation read).

### Part 0 deliverables and sequencing

- **0.1 + 0.2 as one focused PR** (fix the one genuinely-broken live indicator
  *and* restore the audit's signal-to-noise so the next silent freeze is
  visible), then **0.3 separately**.
- 0.1 and 0.3 are source-repair PRs: **verify the fresher series returns data
  live *before* repointing** — a broken repoint is worse than a frozen one. In
  each PR body, paste the before/after composite tail proving it now MOVES,
  plus the chosen source (`source / series_id / last obs`).
- 0.2 is CSV-only; list each `freshness_override_days` change with the source's
  real publication cadence as justification, and note the `JPN_CPI_INDEX` drop.
- Validation gates for any PR touching the merge/composites:
  `python3 -m pytest test_tier_merge.py -q` green; a full keyed macro regen
  (`python3 fetch_macro_economic.py` then `python3 compute_macro_market.py`);
  confirm the target composite moves month-to-month; re-run
  `python3 data_audit.py` (or read the next daily `data_audit.txt`) and confirm
  the EXPIRED/STALE count falls.
- **Do not commit the regenerated data CSVs** in a source PR — the daily
  `update_data` workflow owns them and regenerates authoritatively on merge
  (the convention PRs #249/#250 followed). The regen is for validation; put the
  evidence in the PR body.
- Part 0 motivates forward-plan §2.A **A9** — a systematic "is this composite
  actually moving?" credibility check — whose durable form is item **1.1**
  below.

---

## Part 1 — Incremental structural recommendations

These keep the current shape — CSV registry, single daily Actions run,
git-committed outputs — and could each land as an ordinary PR.

### 1.1 Enforce source precedence at runtime — retire implicit last-writer-wins

**Problem.** In `fetch_macro_economic.py`, the history merge's fallback mechanism is implicit: sources are fetched in a fixed read order and the last writer to a column wins. The tier system exists (`_attach_tiers`, `_select_winner` at lines 310/365 — used for **snapshot** dedup), and `data/source_fallbacks.csv` documents T0→T3 chains per indicator, but nothing walks those chains when the history is written. The technical manual itself calls the fallback "implicit."

This is the single most expensive structural gap in the repo, because it is the root cause of your dominant recurring bug class:

- **JP_INFL1** frozen at 8.49 (fixed via CPI split, PR #249)
- **EU_INFL1** silently frozen at 2.1% for six months — the live P0 in Part 0 (§0.1)
- **CN_INFL1** on 1–3-year-stale FRED mirrors (§0.3)
- The 2026-06-18 source-wiring audit found **25 column collisions, 11 cadence mismatches, 14 columns where the runtime winner ≠ the declared primary, 18 ambiguous-precedence cases**.

Each incident so far has been fixed point-wise (repoint a series, split a definition). The class keeps reproducing because the architecture doesn't encode which source *should* win a column, so a frozen or coarser source can win silently.

**Recommendation.** Make column ownership explicit and enforced:

1. Add a `declared_primary` notion per served column (the wiring audit already computed this; it can live as a column in the `macro_library_*.csv` rows or as a generated `data/column_owners.csv`).
2. In the history merge, replace "last writer wins" with a winner function per column that prefers the declared primary but **demotes it when it fails a freshness/cadence guard** (you already have `freshness_thresholds.csv` and the cadence-rank logic inside `_select_winner` — this extends the tested snapshot tie-break to history writes).
3. Log every demotion loudly (`[FALLBACK] col=EA_HICP primary=estat stale 190d → fell back to ecb`) so `data_audit.py` Section A can surface it — a frozen primary then becomes a *reported event on day one*, not a silent six-month freeze.

**Why structurally better.** It converts the fallback chains from documentation (`source_fallbacks.csv`) into behaviour, and turns the frozen-mirror failure mode from "silent wrong data" into "audible fallback." It is also the substantive core of forward-plan item **A9** ("comprehensive data-credibility check") — value-plausibility bands are a good second layer, but precedence + freshness enforcement is the layer that would have caught all three INFL1 incidents.

**Relationship to Part 0.** 0.1–0.3 repair today's instances by hand; 1.1 is what makes the *next* instance self-report on day one. The freshness overrides tuned in 0.2 feed directly into 1.1's demotion guard — do 0.2 first so the guard starts life with honest thresholds.

**Does not change:** the library-CSV registry rule, source modules, or output schemas. Effort: **M**. Do this first among the structural items; 1.2 makes it easier but is not a prerequisite.

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

**Why structurally better.** Right now the git history is your rollback mechanism, but a bad commit still propagates to Sheets and `trigger.py` the same morning. A minimal circuit breaker preserves the "never block on quality warnings" philosophy while making the two genuinely unrecoverable-downstream cases impossible to ship. Effort: **S**. (A natural third check, once 1.1 lands: a live composite whose raw has not changed for > k months — the `EU_INFL1` signature — though 1.1's fallback logging may make that redundant.)

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

---

## Part 3 — Unified sequencing

**Operational first, then structural** — the operational items are live-broken
today and also generate the evidence (honest freshness thresholds, fallback
events) the structural work builds on:

1. **0.1 + 0.2 in one Codespace PR** — repair `EU_INFL1`, tune freshness
   honesty, drop `JPN_CPI_INDEX`.
2. **0.3** — China cluster (or a documented degraded-indicator entry if no
   fresh source exists).
3. **Structural track:** 1.4 → 1.5 → 1.3 → 1.2 → **1.1** → (2.1/2.2 anytime) →
   multifreq. 1.1 lands last of the core structural items *by dependency
   convenience* (1.2 makes it easier) but is the highest-value structural item;
   pull it earlier if another freeze appears before the registry work is done.

**Multifreq note (forward_plan §5).** Nothing above is thrown away by the
planned Friday-spine → native-frequency migration. Two items are effectively
*prerequisites* that de-risk it: 1.2 (the migration must touch every source
path once — far safer through one registry than two 27-branch ladders) and 1.1
(precedence enforcement defines the correctness contract that a
multi-frequency merge has to preserve). 1.5's test gate is what lets a
migration of that size proceed in reviewable steps.

---

## Part 4 — Reviewed and deliberately not recommended for change

Per your brief, these were examined and are endorsed as-is:

- **The data-layer registry rule** (every identifier in a `macro_library_*.csv`, never in Python; forward_plan §0). This is the repo's best architectural decision — it's what makes the codebase safe for mixed human/Claude maintenance. Everything in Part 1 strengthens it; nothing weakens it. (Part 0 works entirely within it.)
- **The `_ALL_CALCULATORS` registry** in `compute_macro_market.py` — the model that 1.2 copies.
- **Phase isolation** (Pattern 1) — broad per-phase `try/except` is unusual style but correct for a daily data pipeline; 1.4 relocates it without changing it.
- **The tier-aware snapshot merge** (`_select_winner`, `test_tier_merge.py`) — the tested foundation that both Part 0 (its guardrails forbid touching it) and 1.1 (which extends it to history writes) build on.
- **The `_hist` / `_hist_x` sister-archive concept** (Pattern 9) — the right defence against rolling-window source truncation. The known `keep="first"` self-heal question is real but already tracked with candidate designs in forward_plan §3.6a; no new recommendation beyond: resolve it before 2.3-step-2 changes the archive format.
- **stdlib `unittest` over pytest** — keeping the CI dependency surface minimal is coherent; 1.5 works fine with unittest.
- **`print` + `tee pipeline.log` logging** — adequate for a single-process daily batch; a logging framework would add ceremony without new capability. Worth only a convention (consistent `[WARN]`/`[ERROR]`/`[FALLBACK]` prefixes) so audits can grep severity — which 1.1's demotion logging would formalise anyway.
- **Sheets protected-tab safety** (`SHEETS_PROTECTED_TABS`, legacy-tab sweeping) and the **audit-as-warning-channel philosophy** — kept, with only the two-check circuit breaker of 1.8 as an exception.
- **Small CSVs as committed config/state** (`freshness_thresholds.csv`, `manual_splits.csv`, `yfinance_failure_streaks.csv`, `istat_edition_cache.csv`, per-source libraries) — git-versioned, diffable config is a feature here, not debt. 2.3 targets only the multi-MB rewritten hist files. (0.2's `freshness_override_days` edits are exactly this kind of config change.)
- **The audit/writeback loop** (Phase H, 14-day dead-ticker flips) — sound; the weekly human-in-the-loop retirement review is already planned (§3.8) and needs no re-design here.
- **The manuals system** — the count drift I found (indicator_manual's "68" vs 108; 66-vs-70 simple instruments; 1950-vs-1990 comp start; the stale multifreq copy in `multifreq_plan.md` vs forward_plan §5) is refresh-routine territory, not architecture; flagging it here so the next `refresh-manuals` run picks it up.

---

*Prepared from a full-repo review session on 2026-07-07 (evidence line numbers refer to the tree at commit `08e7026`); merged 2026-07-08 with the 2026-07-07 EU-freeze / freshness / China handover, which remains at `manuals/2026-07-07-eu-freeze-freshness-china-handover.md` as the original work order.*
