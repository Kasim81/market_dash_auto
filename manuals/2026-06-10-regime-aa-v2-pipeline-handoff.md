# Memo — Comprehensive handoff: data pipeline asks for regime-AA v2

> **Format note.** This memo is structurally larger than the single-insertion memos in `applied/`. It is a **comprehensive briefing** for the next data-pipeline build session — the consumer-side specification of every CSV, series, and processing step that the upstream pipeline needs to produce for regime-AA v2 to progress through Phases 0–7. It can be handed to a fresh Claude session for the `kasim81/market_dash_auto` repo with no other context; everything required is captured below.
>
> The memo follows the same target-repo / branch / commit / acceptance convention as the single-insertion memos so the cross-repo audit trail stays consistent. Where a specific insertion into `manuals/forward_plan.md` is required, the §-numbered insertion block is given verbatim in §3. Where the work spans multiple files in the pipeline repo, the file-by-file scope is in §3 sub-blocks.
>
> Filed 2026-06-10 from regime-aa, branch `claude/rebuild-master-plan-v2-jnOKI` post-merge to `main`. Driven by the v2 recalibration of the master plan (commit `e456d35` merged via PR #17) plus the existing Phase 0 verification state (Sources 1–2 implemented, Sources 3–6 outstanding, full availability run not yet executed).

## 1. Target

- **Repo:** `kasim81/market_dash_auto`
- **Files touched (all in target repo):**
  - `manuals/forward_plan.md` — multi-section addition documenting the regime-AA v2 asks (single PR; sections §3.10–§3.15)
  - Subsequent implementation across `sources/`, `data/`, `compute_macro_market.py` as the §3.10–§3.15 entries are worked through their normal lifecycle.

## 2. Insertion point (for the forward_plan.md additions)

Insert **immediately before** the line that reads:

```
---

## 4. Project Chronology
```

i.e. the new content lands as new §3.10–§3.15 sub-sections between the previous §3.x tail (whichever was most recently added per the §3.9 precedent in `applied/2026-05-08-ndl-gold-source.md`) and §4 Project Chronology, preserving the existing horizontal rule (`---`) and the §4 heading.

If the file has drifted: place the new content as the last sub-sections under §3 (before whatever horizontal rule precedes §4). The §3.10–§3.15 sub-section headings and ordering are the load-bearing requirement, not the exact line numbers.

## 3. Content to paste (verbatim)

Copy the contents of this fenced block. The leading blank line separates the new sub-sections from the previous §3.x tail.

```md

### 3.10 OECD MEI feed end-to-end verification and ingestion (regime-AA-driven)

**Priority:** CRITICAL — every per-region regime architecture in regime-AA v2 depends on the OECD MEI mirrored series being retrievable and continuous for the priority five regions back to January 1957. Surfaced by regime AA Phase 0 (test plan `docs/phase_0_data_availability_test_plan.md` §2, Source 1).

**Status:** Verifier written in regime-aa (`src/data_ingestion/verify_fred_oecd.py`), not yet run end-to-end against FRED. Pipeline-side ingestion not yet wired.

**Driver:** regime AA Phase 0 (`docs/phase_0_data_availability_test_plan.md`) needs the per-region availability matrix; regime AA Phase 1 then consumes these series as the principal monthly per-region equity and yield inputs for regime label production; regime AA Phase 3 consumes them for the Layer-1 pillar score.

**Scope:**

- Verify retrievability of monthly equity share-price indices `SPASTT01{ISO}M661N` for US, GB, DE, FR, JP, IT, CA, AU, NL, CH (the priority five plus the wider OECD set the regime-aa verifier already targets).
- Verify retrievability of monthly 10-year sovereign yields `IRLTLT01{ISO}M156N` for the same set.
- Confirm continuity from January 1957 to current month for each (series, region) pair, with explicit documentation of any breaks or methodology changes.
- Ingest the verified series into the pipeline registry. Register in `data/macro_library_fred.csv` (or the relevant per-source library) with appropriate `series_id`, `region`, `pillar`, and `frequency` columns.
- Configure the daily orchestration to refresh these series in the standard cadence.
- Sister-file safeguard applied per Stage A (`*_hist_x.csv`).
- Output: rows in `macro_market_hist.csv` and `macro_economic_hist.csv` (per the existing pipeline schema) covering all (series, region) combinations.

**Acceptance:**

- `verify_fred_oecd.py` in regime-aa returns a clean matrix with `retrievable = True` for all priority-five (series, region) pairs.
- For at least US, UK, DE, FR, JP, the equity series has ≥ 800 monthly observations starting 1957-01.
- Pipeline produces these series in `macro_market_hist.csv` / `macro_economic_hist.csv` from the daily orchestration.
- regime-aa repo's `data/phase_0/availability/<date>/` matrix records `fred_oecd` rows sourced from pipeline.

**Related:** Cross-references regime-aa repo files `src/data_ingestion/verify_fred_oecd.py`, `scripts/run_phase_0_availability.py`, `.github/workflows/phase_0_availability.yml`.

### 3.11 Long-run historical data layer ingestion (regime-AA-driven)

**Priority:** HIGH — regime-AA v2 Phase 0 catalogues five long-run sources that must be ingested into the pipeline registry to support Phase 1 regime label production with multi-decade depth. Currently only FRED-native series (already in pipeline) and the OECD MEI feed (§3.10) are wired; the remaining four sources are outstanding.

**Status:** Verifier scripts not yet written in regime-aa for Sources 3–6 (Shiller, Ken French, IMF PCPS, JST). Ingestion-side modules not yet written in pipeline. The regime-aa Phase 0 test plan (`docs/phase_0_data_availability_test_plan.md` §3) specifies one Python verifier per source; the pipeline-side ingestion modules follow once each verifier confirms retrievability.

**Driver:** regime AA Phase 0 (long-run data layer); regime AA Phase 1 (historical regime label production uses the long-run layer as cross-validation anchors and pre-1957 historical depth where available).

**Scope (one new source module per item):**

- **`sources/shiller.py`** — Robert Shiller monthly US series 1871+: S&P 500 price + dividends + earnings, US CPI, long-term rate, CAPE. Two access paths: (a) Yale Excel download `ie_data.xls`; (b) community JSON API mirror `posix4e.github.io/shiller_wrapper_data`. Pipeline canonical = community mirror for automated daily access; Yale Excel as periodic cross-check.
- **`sources/french.py`** — Kenneth French factor library: US 5-factor returns (Mkt-RF, SMB, HML, RMW, CMA) + risk-free rate back to 1926 (monthly); international developed factors back to 1990; EM factors back to 2000. Access via `pandas-datareader` (`web.DataReader('F-F_Research_Data_5_Factors_2x3', 'famafrench')`) with direct ZIP download fallback.
- **`sources/imf_pcps.py`** — IMF Primary Commodity Prices: aggregate indices via FRED-mirror (`PALLFNFINDEXM` etc., already partially covered by FRED-native ingestion) plus per-commodity series via IMF SDMX API. Pipeline-side scope: confirm FRED-mirror coverage of aggregate indices; add SDMX-direct fetch for individual commodities not on FRED.
- **`sources/jst.py`** — Jordà-Schularick-Taylor Macrohistory database: 18 advanced economies × ~10 series × ~150 years (1870+) annual. Access via direct Stata file download from `macrohistory.net/database/`. Annual frequency; used as confirmatory pre-1950 cross-validation anchor, not as primary regime-engine input.
- **`sources/boe_millennium.py`** *(optional, lower priority)* — Bank of England Millennium dataset: UK rates (Bank Rate, long rate, real rate), UK CPI, UK GDP back to early 1700s. Annual + some monthly via FRED mirrors. Used as pre-1957 UK regime anchor where available.

For each new source module: new library CSV per §0.1 architecture rule (every fetched identifier in CSV not Python); sister-file safeguard `*_hist_x.csv`; registry rows in `data/source_fallbacks.csv` as appropriate.

**Acceptance:**

- Each new source module fetches its target series end-to-end via the daily / scheduled run.
- New library CSVs (`data/macro_library_shiller.csv`, `_french.csv`, `_imf_pcps.csv`, `_jst.csv`, optionally `_boe_millennium.csv`) live in the registry; rows pass the daily integrated audit.
- regime-aa Phase 0 verifier scripts for these sources (`verify_shiller.py`, `verify_french.py`, `verify_imf_pcps.py`, `verify_jst.py`) can read the pipeline-produced CSVs and confirm depth against the per-region availability matrix schema.

### 3.12 Monthly z-score normalisation alongside daily (regime-AA-driven, v2)

**Priority:** CRITICAL — regime-AA v2 recalibrated the regime engine from a daily/weekly cadence to a monthly cadence to match the institutional regime horizon (target 9–18 month asset-specific regime episodes; multi-quarter macro four-quadrant calls). The pipeline currently publishes indicator z-scores computed over a daily 252-day rolling window; regime-AA v2's per-region Layer-1 pillar score (master plan §3.5.2) requires the **monthly 156-week (3-year) z-score**.

**Status:** Pipeline currently publishes daily 252-day z-scores for every composite. v2 monthly z-score column does not yet exist.

**Driver:** regime AA Phase 2 (indicator validation) and Phase 3 (regime engine build) both consume the monthly 156-week z-score as the per-indicator standardisation. master plan v2 §3.5.2: *"The standard window in the master plan, following the data pipeline's existing convention, is 156 weeks (three years) on weekly-frequency series."*

**Scope:**

- Augment `compute_macro_market.py` to compute, per composite, **two z-score columns**: the existing daily 252-day rolling z-score (retained for the Indicator Explorer's daily-cadence monitoring), and a new monthly 156-week (52-week minimum) rolling z-score sampled at month-end.
- Output a new monthly-snapshot CSV `macro_market_monthly_hist.csv` (or extend the existing schema with monthly-aligned rows / a `z_score_monthly` column — the precise schema choice is a pipeline-side architectural call). Either way: the regime-AA engine must be able to read per-(indicator, region) monthly z-scores as a flat table.
- Document the schema in `manuals/technical_manual.md` so downstream consumers (regime-AA) can stable-import the column.

**Acceptance:**

- The pipeline produces monthly z-scores for every composite at every month-end going back as far as the underlying series supports.
- regime-AA Phase 3's Layer-1 pillar score reads the monthly z-score directly without further transformation.
- The daily z-score continues to be produced unchanged for the Indicator Explorer.

### 3.13 Monthly EWMA features per asset (regime-AA-driven, v2 Layer 2)

**Priority:** HIGH (only required if the regime-AA asset-specific Layer 2 is built in Phase 3; defer if Phase 3 settles on macro-only Layer 1).

**Status:** Not in pipeline. Currently the regime-AA engine would have to compute these in-phase from raw monthly returns. Pipeline-side production is more efficient and lets the dashboard show them.

**Driver:** regime AA Phase 3 Layer 2 — Statistical Jump Model + GBDT forecaster (master plan v2 §3.1.1 and §3.2.2). v2 specifies the feature set on monthly excess returns, with EWMA halflives in months.

**Scope:**

- For each asset in the regime-AA regional asset universe (selected at Phase 4 entry; ~8–15 assets per region × 5 regions ≈ 40–75 assets total):
  - Compute monthly excess return $r_t = R_t - r_{f,t}/12$ where $R_t$ is the asset's monthly total return and $r_{f,t}$ is the regional 3-month risk-free rate.
  - Compute EWMA features at halflives $h \in \{3, 6, 12\}$ months:
    - $\mathrm{DD}_{h,t} = \sqrt{\mathrm{EWM}(\min(r_t,0)^2, h)}$ (downside deviation)
    - $\mathrm{AR}_{h,t} = \mathrm{EWM}(r_t, h)$ (EWMA average return)
    - $\mathrm{SR}_{h,t} = \mathrm{AR}_{h,t} / \mathrm{DD}_{h^*,t}$ (Sortino-style ratio) with $h^* = 12$ for $h \in \{3,6\}$, $h^* = h$ for $h = 12$.
  - Compose the 8-feature vector: $\log(\mathrm{DD}_{h,t} + 10^{-8})$ at $h \in \{3, 12\}$; $\mathrm{AR}_{h,t}$ at $h \in \{3, 6, 12\}$; $\mathrm{SR}_{h,t}$ at $h \in \{3, 6, 12\}$.
  - Standardise each feature against rolling 60-month (5-year) mean and standard deviation.
- Output: `asset_jm_features_monthly.csv` with columns `(asset_id, region, date, log_dd_3m, log_dd_12m, ar_3m, ar_6m, ar_12m, sr_3m, sr_6m, sr_12m)`, monthly cadence.
- Also: monthly cross-asset macro features per region (master plan v2 §3.2.2 table): 2y yield change (EWM halflife 6 months), yield-curve slope (EWM halflife 3 months), slope change (EWM halflife 6 months), VIX log-change (EWM halflife 6 months), 36-month equity-bond correlation. Output: `macro_features_monthly.csv` per region.

**Acceptance:**

- For every asset in the agreed regime-AA asset universe (list provided once Phase 4 entry decision is made), the 8-feature monthly vector is available from the asset's earliest available month-end return.
- The cross-asset macro features are available per region back to 1957 (where source data supports).
- regime-AA Phase 3 Layer 2 reads these CSVs directly to fit the JM and train the GBDT.

### 3.14 Seam-test extension to monthly-aligned regime AA inputs (regime-AA-driven, v2)

**Priority:** MEDIUM — the regime-AA `src/data_ingestion/seam_test.py` confirms the daily seam between pipeline and consumer. v2's monthly cadence means the seam should also be tested at month-end alignment.

**Status:** Existing daily seam test (`seam_test.py`) passed 2026-05-07 with 92 indicators. Monthly seam not tested.

**Scope:** Once §3.12 (monthly z-scores) and §3.13 (monthly EWMA features) are in production:

- Extend regime-AA `src/data_ingestion/seam_test.py` to also check the monthly-aligned outputs (count of (indicator, region) pairs with monthly z-scores; count of (asset, region) pairs with monthly feature vectors).
- Pipeline side: confirm the monthly CSVs publish on a schedule the regime-AA daily seam test can pick up.

**Acceptance:**

- `seam_test.py` reports counts for both daily and monthly seams in `data/outputs/seam_test/summary.csv`.

### 3.15 ALFRED vintage-data exposure (regime-AA-driven, lower priority)

**Priority:** LOW — useful for Phase 6 backtest fidelity but not blocking earlier phases.

**Status:** Not in pipeline. Currently all backtests would use revised (post-revision) FRED data, which is known to overstate out-of-sample performance (master plan v2 §9.1 "Vintage data neglect").

**Driver:** regime AA Phase 6 backtest — the master plan specifies that *"Where the regime classifier's input series are available in ALFRED, the backtest in Phase 6 uses the vintage data"* (master plan §9.1).

**Scope:**

- Add an optional vintage-data fetch mode to the FRED source module, calling the ALFRED archive (`series/observations?file_type=json&realtime_start=YYYY-MM-DD&realtime_end=YYYY-MM-DD`) for series flagged as critical to backtest fidelity (NBER recession indicator, GDP advance vs revised, CPI revisions, etc.).
- Output: parallel vintage-data CSV (`macro_vintage_hist.csv`) with columns `(series_id, observation_date, vintage_date, value)`.
- Document ALFRED's coverage limits (US-centric; sparse for non-US series).

**Acceptance:**

- Vintage data retrievable for at least the NBER recession indicator and US CPI back to the start of the ALFRED record.
- regime-AA Phase 6 backtest can opt into vintage data per series; documented limitations explicit.
```

## 4. Suggested branch + commit message

- **Branch:** `feature/forward-plan-regime-aa-v2-asks`
- **Commit message:**

```
forward plan §3.10–§3.15: regime-AA v2 data pipeline asks

Comprehensive consumer-side specification of the data the regime-AA
v2 master plan needs from this pipeline at every phase. Filed under
the §3.7-style protocol (regime AA work surfaces a need; the request
comes back here as a §3 entry).

Six new asks:
- §3.10 OECD MEI feed verification and ingestion (CRITICAL)
- §3.11 Long-run historical data layer ingestion (HIGH)
- §3.12 Monthly z-score normalisation alongside daily (CRITICAL)
- §3.13 Monthly EWMA features per asset for Layer 2 (HIGH if Layer 2)
- §3.14 Seam-test extension to monthly outputs (MEDIUM)
- §3.15 ALFRED vintage-data exposure (LOW, Phase 6 fidelity)

Cross-references regime-aa repo:
docs/proposals/data_pipeline_requests/open/
2026-06-10-regime-aa-v2-pipeline-handoff.md.
```

## 5. Acceptance

Once applied, append the following stanza at the bottom of this memo (after moving it to `applied/`):

```
## Applied

- Target commit: <sha-from-market_dash_auto>
- Target PR:     <github-pr-url>
- Date applied:  <YYYY-MM-DD>
- regime-aa marking commit: <sha-from-regime-aa-marking-commit>
```

## 6. How to apply this memo — explicit step-by-step (for Cowork / pickup session)

This section is self-contained: a fresh session can execute every step below using only the contents of this memo. No other context required.

### Step 0 — Prerequisites

- Local clones of both repos available (`regime-aa` and `market_dash_auto` as siblings).
- Cowork can run shell commands and edit files in both clones.

### Step 1 — Pull the latest `market_dash_auto/main`

In the `market_dash_auto` clone:

```bash
git checkout main
git pull origin main
git status   # confirm clean working tree
```

### Step 2 — Create the feature branch

```bash
git checkout -b feature/forward-plan-regime-aa-v2-asks
```

### Step 3 — Apply the edit to `manuals/forward_plan.md`

Open `manuals/forward_plan.md`. Locate the `---` horizontal rule that precedes `## 4. Project Chronology` (this is the same anchor used by the §3.9 NDL memo in `applied/2026-05-08-ndl-gold-source.md`). The previous §3.x tail should be visible immediately above the `---`.

Insert the entire block from §3 of this memo (the fenced ```md … ``` block, ~140 lines) **immediately before** the `---` horizontal rule. The result should read:

```
… (previous §3.x tail) …

### 3.10 OECD MEI feed end-to-end verification and ingestion …
… (full content of §3.10–§3.15 as in §3 of this memo) …

---

## 4. Project Chronology
```

### Step 4 — Verify the diff before committing

```bash
git diff manuals/forward_plan.md
```

Expected: ~140-line addition at the right position; no other changes; no whitespace damage to surrounding sections.

### Step 5 — Commit and push

```bash
git add manuals/forward_plan.md
git commit -m "$(cat <<'EOF'
forward plan §3.10–§3.15: regime-AA v2 data pipeline asks

Comprehensive consumer-side specification of the data the regime-AA
v2 master plan needs from this pipeline at every phase. Filed under
the §3.7-style protocol (regime AA work surfaces a need; the request
comes back here as a §3 entry).

Six new asks:
- §3.10 OECD MEI feed verification and ingestion (CRITICAL)
- §3.11 Long-run historical data layer ingestion (HIGH)
- §3.12 Monthly z-score normalisation alongside daily (CRITICAL)
- §3.13 Monthly EWMA features per asset for Layer 2 (HIGH if Layer 2)
- §3.14 Seam-test extension to monthly outputs (MEDIUM)
- §3.15 ALFRED vintage-data exposure (LOW, Phase 6 fidelity)

Cross-references regime-aa repo:
docs/proposals/data_pipeline_requests/open/
2026-06-10-regime-aa-v2-pipeline-handoff.md.
EOF
)"
git push -u origin feature/forward-plan-regime-aa-v2-asks
```

### Step 6 — Open and merge the PR

```bash
gh pr create \
  --repo Kasim81/market_dash_auto \
  --base main \
  --head feature/forward-plan-regime-aa-v2-asks \
  --title "forward plan §3.10–§3.15: regime-AA v2 data pipeline asks" \
  --body "Cross-repo memo: regime-aa/docs/proposals/data_pipeline_requests/open/2026-06-10-regime-aa-v2-pipeline-handoff.md (will move to applied/ once this PR is merged).

This memo records six new pipeline-side asks driven by the regime-AA v2 master plan recalibration. Sub-sections §3.10–§3.15 are sequenced from CRITICAL (must complete before Phase 1 of regime AA can start) through LOW (Phase 6 backtest fidelity nice-to-have)."
```

Then merge via the GitHub UI (or `gh pr merge --squash`).

### Step 7 — Sanity check the result

```bash
git checkout main
git pull origin main
grep -n "^### 3\.1[0-5] " manuals/forward_plan.md   # should print all six §3.10–§3.15 headings
grep -n "^## 4\. " manuals/forward_plan.md          # should print §4, after §3.15
```

### Step 8 — Mark the memo applied in regime-aa

In the `regime-aa` clone:

```bash
git pull origin main
git checkout -b chore/apply-regime-aa-v2-pipeline-handoff
git mv docs/proposals/data_pipeline_requests/open/2026-06-10-regime-aa-v2-pipeline-handoff.md \
       docs/proposals/data_pipeline_requests/applied/
```

Append the `## Applied` stanza (from §5 of this memo) with the merged-PR commit SHA and PR URL.

```bash
git add docs/proposals/data_pipeline_requests/applied/2026-06-10-regime-aa-v2-pipeline-handoff.md
git commit -m "chore: mark regime-aa-v2-pipeline-handoff applied (<target-commit-sha>)"
git push -u origin chore/apply-regime-aa-v2-pipeline-handoff
```

Merge the PR. The memo now lives in `applied/` with its outcome recorded.

## 7. Background context (for the pickup session)

The pickup session can read just the above sections (1–6) to apply the memo. The context below is provided for situations where the pickup session needs to make judgment calls about how to schedule or implement the new §3.10–§3.15 work within the pipeline's existing roadmap.

### 7.1 What the regime-AA v2 master plan does

The `regime-aa` repository builds a regime-based asset allocation programme on top of this data pipeline. It identifies four macroeconomic regimes per region (Goldilocks, Overheating, Downturn, Stagflation) and produces three parallel client-implementation frameworks (TAA around a multi-asset policy; TAA around the rg-ERC dynamic benchmark; absolute return CPI+4–5%).

Version 2 of the master plan (merged 2026-06-XX) recalibrated the regime engine from a daily/weekly cadence to a **monthly cadence**, targeting **9–18 month regime episodes** consistent with the multi-billion-dollar, quarterly-investment-committee context the framework serves. The pipeline-side consequences of that recalibration are §3.12 (monthly z-scores) and §3.13 (monthly EWMA features). Everything else in §3.10–§3.15 is either foundation work (OECD MEI feed for per-region modelling; long-run sources for historical depth) or backtest fidelity (ALFRED vintage data).

### 7.2 What regime-AA already consumes from this pipeline (no change)

- `macro_economic_hist.csv` — daily raw macro series across 12 economies.
- `macro_market_hist.csv` — daily market instruments and composite indicators.
- 92 composite indicators with daily 252-day rolling z-scores, regime classification, forward-regime signal, and z-score trajectory diagnostic.
- `index_library.csv` — investable instrument registry.
- The Indicator Explorer HTML dashboard.

These continue to be produced unchanged. §3.12 (monthly z-scores) and §3.13 (monthly EWMA features) are **additive**: the existing daily outputs are retained.

### 7.3 Priority ordering for the pipeline session

The six asks form a partial order driven by regime-AA's phase dependencies:

| Order | Ask | Blocks regime-AA phase |
|---|---|---|
| 1 | §3.10 OECD MEI verification and ingestion | Phase 0 completion → Phase 1 entry |
| 2 | §3.11 Shiller + French (within long-run layer) | Phase 0 completion → Phase 1 entry |
| 3 | §3.12 Monthly z-scores | Phase 2 validation → Phase 3 engine build |
| 4 | §3.13 Monthly EWMA features | Phase 3 Layer 2 (only if built) |
| 5 | §3.14 Monthly seam test extension | After §3.12, §3.13 |
| 6 | §3.15 ALFRED vintage data | Phase 6 backtest fidelity (not blocking) |

§3.10 is the single most important: regime-AA Phase 0 cannot conclude without it, and every subsequent phase is gated on Phase 0.

### 7.4 Source-of-truth references in regime-aa

- Master plan v2 PDF: `docs/master_plan/built/master_plan.docx` (rendered from markdown in `docs/master_plan/source/`).
- Phase 0 test plan: `docs/phase_0_data_availability_test_plan.md`.
- Phase 0 verifier scripts: `src/data_ingestion/verify_fred_oecd.py`, `verify_fred_us_native.py`, `seam_test.py`.
- Phase 0 runner + CI workflow: `scripts/run_phase_0_availability.py`, `.github/workflows/phase_0_availability.yml`.
- Responsibilities boundary: `docs/responsibilities_boundary.md`.
- Cross-repo memo convention: `docs/proposals/data_pipeline_requests/README.md`.

Section numbers in the master plan referenced by the §3.10–§3.15 asks:

| Ask | Master plan reference |
|---|---|
| §3.10 OECD MEI | §17.2 Phase 0; §5.1.5 (long-run data layer); test plan §2 Source 1 |
| §3.11 Long-run layer | §17.2 Phase 0; §5.1.5; test plan §2 Sources 3–6 |
| §3.12 Monthly z-scores | §3.0 (v2 horizon principle); §3.5.2 (indicator normalisation) |
| §3.13 Monthly EWMA features | §3.1.1 (JM features); §3.2.2 (GBDT macro features); §3.0 (v2 horizon principle) |
| §3.14 Monthly seam test | §17.2 Phase 0 acceptance criteria |
| §3.15 ALFRED vintage data | §9.1 (Vintage data neglect); §17.8 Phase 6 backtest |

### 7.5 What is NOT requested from the pipeline

These items are owned by regime-AA, not the pipeline:

- **Phase 1 regime label production.** regime-AA computes the per-region monthly regime label series in-phase. The pipeline supplies the inputs (CPI, equity, yields, IP, rates) — already covered by existing pipeline + §3.10–§3.11.
- **Phase 2 indicator validation.** regime-AA runs the validation framework against the existing 92 composites and the structured library. No pipeline-side scoring or filtering is requested.
- **Phase 4 regime-conditional moments.** regime-AA computes regime-conditional means/covariances in-phase from monthly returns + regime labels. The pipeline supplies monthly asset returns (already covered).
- **Phases 5–8 frameworks, backtest, dashboard, agents.** All regime-AA-side.

If the pipeline session sees an opportunity for pipeline-side pre-computation that would simplify regime-AA's work (e.g., pre-computed per-regime sample moments cached in pipeline output), file an inverse-direction proposal back to regime-AA per the standing protocol; do not pre-emptively add work to the pipeline scope.
