# Inverse-direction proposal — corrections to the regime-AA v2 pipeline handoff

> **Direction:** pipeline (`market_dash_auto`) → consumer (`regime-aa`).
> **Re:** `docs/proposals/data_pipeline_requests/open/2026-06-10-regime-aa-v2-pipeline-handoff.md`.
> **Filed:** 2026-06-10, during the pipeline-side triage of that memo.
> **Action for regime-aa:** fold these corrections into the source memo (and the master-plan references it cites) so the cross-repo contract reflects the pipeline's actual state. None of these block applying the memo on the pipeline side — the asks were landed (reconciled + annotated) in `manuals/forward_plan.md` §3.12–§3.17.

The memo was applied, but the pipeline-side audit found four points where it describes a state that doesn't match the live pipeline. Each could cause regime-AA to schedule the wrong work or mis-state an acceptance criterion.

## 1. §3.12 (monthly z-scores) — the "current state" is wrong

**Memo says:** *"The pipeline currently publishes indicator z-scores computed over a daily 252-day rolling window."* and asks for a new *"monthly 156-week (3-year) z-score."*

**Actual:** `compute_macro_market.py` already standardises on a **156-week (3-year) rolling z-score on the weekly Friday spine** — `ZSCORE_WINDOW = 156`, `ZSCORE_MIN_PERIODS = 52`. There is **no daily 252-day z-score**. The standardisation window regime-AA wants is already the production convention (the master-plan quote in the memo, *"following the data pipeline's existing convention … 156 weeks (three years) on weekly-frequency series,"* is the correct description).

**Consequence:** the real ask is **not** a new z-score definition. It is **month-end *sampling*** of the existing standardisation into a **flat per-(indicator, region) monthly table**. Please restate §3.12 accordingly.

**Open question for regime-AA to resolve:** do you want
- (a) the existing **weekly 156-week** z-score **sampled at month-end**, or
- (b) a **native monthly** z-score over a **36-month** window (156 weeks ≈ 36 months) computed on month-end-resampled inputs?

These differ when a series is weekly/daily vs monthly natively. The pipeline can produce either; (a) is cheaper and guarantees consistency with the Indicator Explorer. Confirm which, and §3.14 in the pipeline forward plan will be implemented to match.

## 2. Section-number collision — the asks were renumbered

**Memo says:** insert as §3.10–§3.15.

**Actual:** `forward_plan.md` had already drifted — **§3.10 (ifo backfill) and §3.11 (Indicator Explorer audit) already exist.** The six asks were therefore landed as **§3.12–§3.17**:

| Memo § | Landed as | Ask |
|---|---|---|
| 3.10 | **3.12** | OECD MEI feed verify + ingest |
| 3.11 | **3.13** | Long-run historical layer |
| 3.12 | **3.14** | Monthly z-score sampling |
| 3.13 | **3.15** | Monthly per-asset EWMA features |
| 3.14 | **3.16** | Monthly seam-test extension |
| 3.15 | **3.17** | ALFRED vintage data |

Any regime-AA references to the pipeline section numbers should use the **3.12–3.17** mapping.

## 3. §3.13 (monthly EWMA features) — blocked on a regime-AA input

The pipeline cannot fully specify or build the per-asset feature CSVs until regime-AA fixes:
- the **Phase-4 regional asset universe** (the ~40–75 `asset_id`s, with `region`), and
- the **per-region 3-month risk-free series** to use for the excess-return `r_f,t`.

Until those land, §3.15 (pipeline numbering) stays specified-but-deferred. Please send the universe + risk-free mapping when the Phase-4 entry decision is made.

## 4. Minor — stale protocol cross-reference

The memo's commit message cites the *"§3.7-style protocol."* In `forward_plan.md`, **§3.7 is a MOVED stub** (regime-driven back-test, relocated to the master plan). The cross-repo-memo convention you mean is real, but the §-pointer is stale — suggest citing `docs/proposals/data_pipeline_requests/README.md` directly.

## Already-handled / overlap notes (FYI, not corrections)

- **§3.12 OECD MEI** is **partially done**: `IRLTLT01{ISO}M156N` 10Y yields exist for GB/DE/IT (+ India); the gap is FR/JP/CA/AU/NL/CH yields and the `SPASTT01` equity indices (none wired). It's the cheap FRED-CSV-row pattern.
- **§3.13 long-run layer** overlaps pre-existing pipeline plans: IMF Primary Commodity Prices is partly wired via FRED `P*USDM` rows; Shiller CAPE is already a planned item (forward_plan §3.3); the full long-run source set was already catalogued in forward_plan §3.1. The new modules are still needed, but the pipeline plan now cross-links rather than duplicates.
