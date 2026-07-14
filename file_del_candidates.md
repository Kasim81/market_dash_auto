# Repo File-Deletion Candidates

> Audit only — **no files are deleted by this document.** Each entry is the
> auditor's reasoning + a confidence rating + any reference cleanup needed; the
> owner decides what (if anything) to remove.
> **Last audited: 2026-07-14** (branch `claude/youthful-gates-iyqv23`). This pass
> re-audited **every `.md` file in the repo** against the current code and the two
> manuals (`manuals/technical_manual.md`, `manuals/forward_plan.md`), and refreshed
> the prior 2026-04-27 non-`.md` candidates. Supersedes the 2026-04-27 audit.

## Method & headline

Each dated handoff / audit / spec `.md` was checked for: (1) is its work **implemented and captured** in the code and/or the two manuals? (2) does it hold **durable content missing from the manuals** that should be migrated before deletion? (3) is it **referenced** by code or the manuals (a referenced file needs its pointers handled first)?

**Headline:** the transient handoff/audit notes are overwhelmingly **fully implemented and their durable outcomes already live in the manuals** (forward_plan §2.A/§2.B/§2.C/§3.12–§3.17 chronology, technical_manual §9/§12/§13 + Appendix A/B). **Nothing of durable value needs to be *added* to either manual** — every "keep" file below already *is* the durable home for its unique content. The one adjacent fix (not a manual edit): `manuals/multifreq_plan.md` carries **stale counts** (50 indicators / 302 tickers / 8.4M cells) that should be refreshed to match forward_plan §5 (91 / 390 / 8.8M) — forward_plan §5 already flags this drift.

## Resolution log — 2026-07-14 cleanup pass (branch `claude/find-prompt-9vtb0t`)

The repo-cleanup work-order — now folded into `forward_plan.md` §2 "Repo file-hygiene —
doc-deletion sweep" plus the §4 chronology, and retired as a standalone file — was
executed collaboratively with the owner. Outcome of each item:

**Actioned — deleted (with inbound references rewired to surviving homes):**
- **#1 `AUDIT_HANDOVER_2026-06-15.md`** — deleted. Its audit is fully closed; it had no inbound references. (The handover §0 wrongly assumed PR #267 had already removed it.)
- **#5 (B5) `manuals/2026-06-17-m2-units-trio-recommendation.md`** — deleted. Provenance note in `macro_library_{ecb,boj,dbnomics}.csv` (and the regenerated `macro_economic.csv` snapshot) repointed to "forward_plan §2.B / chronology (PR #221)".
- **#6 (B6) `manuals/2026-07-07-eu-freeze-freshness-china-handover.md`** — deleted. forward_plan A10 discovery-notes parenthetical dropped.
- **#10 (C10) `manuals/2026-06-15-source-tier-audit.md`** — deleted. The live `compute_macro_market.py` `_calc_UK_INFL1` docstring comment and the 3 forward_plan refs (384/411/541) repointed to the codified tier model (`technical_manual.md` §9.4).
- **#11 (C11) `manuals/2026-06-15-label-vs-data-audit.md`** — deleted (owner elected to retire the audit-of-record). forward_plan 396 + technical_manual §12 closure line reworded to drop the file path. Note: the KEEP file `…source-wiring-audit-proposal.md` does **not** in fact reference it (register #11's `:40` pointer was stale).

**Deferred / kept by owner decision (unchanged this pass):**
- **#4 (B4) + #12 (C12)** `…regime-aa-v2-pipeline-handoff.md` and `…-corrections.md` — **kept**. They are coupled (C12 cross-references B4) and gated on confirming the outbound "file back to regime-aa" inverse-direction proposal was delivered; not yet confirmed. (B4 also carries an extra live pointer at `…alpha-vantage-evaluation.md:8` §7.2 that would need handling on deletion.)
- **Group E — #7/#8/#9 (B7/B8/B9) + #13 (C13)** the generated `regime-aa-asks/` `.md` layer — **kept**. Owner chose to keep committing the generated layer (the generators are not run in CI, so a durable deletion would require `.gitignore`/build-script changes); skipped.
- **Section D non-`.md` (archive `.py`+`.xlsx`, the two `manuals/*.docx`)** — **kept**. Owner elected no deletions in Group D this pass.

---

## Confidence definitions

- **High** — provably superseded/orphaned; deleting has no functional impact and no (or one trivial) reference to fix.
- **Medium** — content fully captured elsewhere, but the file is cross-referenced (manual prose, a sibling doc, or a CSV note field); delete only after rewording those pointers.
- **Low / Defer** — referenced by live code or still doing work; resolve the reference (or keep as an archived record) before any deletion.

---

## A. DELETE — ready (High confidence)

| # | Path | Size | Status / why | Reference cleanup |
|---|---|---|---|---|
| 1 | `AUDIT_HANDOVER_2026-06-15.md` | 9.5 KB | Pure "resume-if-the-Codespace-dies" scaffolding for the label-vs-data audit, which is **100% closed** (PR #250, forward_plan §2.A A8/A17). No durable content. | **None** — unreferenced (only self-matches). |
| 2 | `manuals/2026-06-15-codespace-secrets-checklist.md` | 7.7 KB | One-time Codespace secret-mirroring checklist; every secret is already in **technical_manual §12** with richer notes, and matches the workflow `env:` block. | Only referenced by #1 and the (deferred) label-vs-data audit — both retiring. |
| 3 | `manuals/2026-06-18-cpi-split-codespace-spec.md` | 7.3 KB | One-shot work-order for the CPI-definition split; **executed** (PR #249). Its resolution record lives in the source-wiring-audit-proposal + forward_plan §2.A A1/A13. | Update 1 line in `…source-wiring-audit-proposal.md:174` (a KEEP file) when deleting. |

## B. DELETE — after a small reference cleanup (Medium)

| # | Path | Size | Status / why | Reference cleanup |
|---|---|---|---|---|
| 4 | `manuals/2026-06-10-regime-aa-v2-pipeline-handoff.md` | 26 KB | Cross-repo handoff memo; **fully reconciled** into forward_plan §3.12–§3.17 (each ask carries an audited status line). | Reword forward_plan **line 550** and **line 1183** to cite §3.12–§3.17 instead of the file. |
| 5 | `manuals/2026-06-17-m2-units-trio-recommendation.md` | 6.4 KB | M2/M3-trio relabel recommendation; **shipped** (PR #221 — EZ_M3/JPN_M2/CHN_M2). Outcome in forward_plan §2.B + chronology. | Repoint the provenance note in **3 library CSVs** (`macro_library_{ecb,boj,dbnomics}.csv`) — or accept a dangling citation. |
| 6 | `manuals/2026-07-07-eu-freeze-freshness-china-handover.md` | 13.5 KB | P0/P1/P2 work-order; **all three resolved** (forward_plan §2.A A10/A11/A1, richer than the memo). | Reword the forward_plan **A10 "Original discovery notes"** parenthetical (line 435). |
| 7 | `manuals/regime-aa-asks/regime-aa-fill-report.md` | 14 KB | **Generated** point-in-time fill snapshot (`build_fill_report.py`); headline (98/24/15/25) is verbatim in forward_plan §2.B. No live consumer reads it. | **None** (regenerable; unreferenced). |
| 8 | `manuals/regime-aa-asks/regime-aa-sourcing-backlog.md` | 5.6 KB | **Generated** backlog (`build_sourcing_backlog.py`); forward_plan §2.B is "distilled from" it and is now a **superset** (B1–B15 carry exact series ids, effort, sequencing). | Reword the two "distilled from" pointers (forward_plan **466, 542**) to cite the coverage CSV + build script. |
| 9 | `manuals/regime-aa-asks/requests/*.md` (15 files) | ~10 KB total | **Generated** per-gap cross-repo memos (`scripts/phase_0_coverage_check.py --write-memos`), one per missing-sourceable slot = forward_plan §2.B B1–B15, one-to-one. Tool *output*, not source. | Pointed at by the phase_0 tool (write-target) + sourcing-backlog (#8). Cosmetic delete — see caveat ⚠️1. |

## C. DEFER — referenced by live code / active work (resolve first, or keep as archived record)

| # | Path | Size | Why defer |
|---|---|---|---|
| 10 | `manuals/2026-06-15-source-tier-audit.md` | 17 KB | Findings resolved & the tier model is now in code (`_load_tier_map`/`_select_winner`, technical_manual §9.4) — **but a live code comment `compute_macro_market.py:2078` points to it**, plus forward_plan 384/411/541. Fix the code comment before deleting. |
| 11 | `manuals/2026-06-15-label-vs-data-audit.md` | 29 KB | Fully remediated (PR #225/#250) but still the cross-referenced **audit-of-record** (forward_plan 396; `…m2-trio.md:7`; `…source-wiring-proposal.md:40`). Prune those pointers or keep as archive. |
| 12 | `manuals/2026-06-10-regime-aa-v2-pipeline-handoff-corrections.md` | 4.6 KB | In-repo content fully captured (forward_plan §3.14/§3.15), but it is the source artefact for an **outbound "file back to regime-aa" action** (forward_plan:1183) that can't be verified from this repo. Confirm that was delivered, then delete with #4. |
| 13 | `manuals/regime-aa-asks/regime-aa-indicator-coverage.md` | 45 KB | **Generated** readable twin of the live `data/regime-aa-indicator-coverage.csv`. Delete only as a deliberate decision to stop committing the generated-`.md` layer (see caveat ⚠️1) — and **never delete the `.csv`** (caveat ⚠️2). |

## D. Prior (2026-04-27) non-`.md` candidates — refreshed status

| Path | 2026-07-14 status |
|---|---|
| `manuals/pipeline_review.md` | ✅ **Already deleted** (was prior #2). |
| `archive/generate_review_excel.py` (5.3 KB) | Still present; still a **High**-confidence orphan (pre-2026-04-08 indicator ids absent from the live library). |
| `archive/indicator_groups_review.xlsx` (16 KB) | Still present; **Medium** — its only consumer was the script above. |
| `archive/indicator_groups_review_UPDATED.xlsx` (23 KB) | Still present; **Medium** — historical review output. |
| `manuals/indicator_manual.docx` (89 KB) | Still present; **Medium** — regenerable from the `.md` via `build_docx.py`, not built by CI (owner call: keep only if distributed externally). |
| `manuals/macro_market_cheat_sheet.docx` (46 KB) | Still present; **Medium** — same reasoning via `md_to_docx.py`. |

*(These are outside this pass's `.md` scope but retained here so this file stays the single canonical deletion register.)*

---

## KEEP — scrutinised and rejected as candidates

| Path | Why kept |
|---|---|
| `README.md`, `requirements.txt`, `.gitignore`, `.github/workflows/*` | Repo essentials. |
| `audit_comment.md` | **Generated every run** by `data_audit.py`, committed by CI and posted to the daily audit Issue (workflow lines 147-181). Live artefact, not documentation. |
| `pipeline.log` | Committed by CI each run — diagnostic artefact (technical_manual §14). |
| `manuals/technical_manual.md`, `manuals/forward_plan.md` | The two living manuals. |
| `manuals/indicator_manual.md`, `manuals/macro_market_cheat_sheet.md` | Durable user-facing reference docs (technical_manual §2). |
| `manuals/factiq_audit_*.csv`, `manuals/factiq_golden_*.json` | FactIQ audit data backing technical_manual Appendix A/B (relocated here 2026-07-14, PR #267). |
| `.claude/skills/refresh-manuals/SKILL.md` | Active skill. |
| `manuals/2026-06-10-alpha-vantage-evaluation.md` | **Open work item** — cited by forward_plan §3.3 as the decision-record for the un-shipped PE-snapshot writer (`equity_pe_snapshot.csv` does not exist; AV library empty). |
| `manuals/2026-06-18-source-wiring-audit-proposal.md` | **Companion doc** for the committed `build_source_inventory.py` (technical_manual §9.11 cites it); **sole home** of the workbook `FLAG_*` definitions + the CPI-split resolution record. |
| `manuals/community_datasets_review.md` | Cited **Stage F deliverable** (forward_plan §3.1.8) for 14 shipped tickers + BoE/ECB codes; sole home of durable deferred notes (STOXX-600 sector-label caveat, UK-corp-bond-yield gap, ECB MIR lead). |
| `manuals/multifreq_plan.md` | **Active, unstarted Phase 2** design (forward_plan §5 + technical_manual §2). Needs a counts refresh, not deletion. |
| `manuals/regime-aa-asks/regime-aa-indicator-req.md` | The **external requirements contract** (§5 of the regime-AA master plan) the whole coverage subsystem is built against; forward_plan §2.B distils only a 15-item slice. Holds cycle-timing priors + the per-region matrix found nowhere else. |
| `manuals/Macro Market Indicators Reference.docx` | Original 206-indicator source doc (irreplaceable; drove `data/reference_indicators.csv`). |
| `manuals/build_docx.py`, `manuals/md_to_docx.py` | Regenerate the `.docx` artefacts (become candidates only if both `.docx` are dropped). |
| `sources/*.py`, `data/*.csv`, `compute_macro_market.py`, `fetch_*.py`, `library_*.py`, `docs/build_html.py` + outputs, all `test_*.py`, `build_source_inventory.py`, `audit_writeback.py` | Live runtime / generated pipeline outputs. |

---

## ⚠️ Critical caveats before acting

1. **The `regime-aa-asks/` `.md` files (#7, #8, #9, #13) are a *generated* layer.** They are emitted by committed scripts (`build_indicator_coverage_map.py`, `build_fill_report.py`, `build_sourcing_backlog.py`, `scripts/phase_0_coverage_check.py`) from `data/regime-aa-indicator-coverage.csv`. Deleting a `.md` is **cosmetic** — the next run of the corresponding script recreates it. A durable deletion means also deciding to **stop committing the generated `.md` layer** (e.g. gitignore them / drop the emit step), keeping only the `.csv` + scripts. Treat #7–#9 and #13 as one decision, not four.
2. **Do NOT delete `data/regime-aa-indicator-coverage.csv`.** It is the live machine input to `scripts/phase_0_coverage_check.py` (a documented, exit-code-gating operator utility referenced from both manuals). It is not a `.md` and is not a candidate — flagged only to prevent an accidental sweep of the folder.
3. **Reference graph among candidates.** #2 is referenced only by #1 + #11; #3 by #6's sibling KEEP doc; #9 by #8. Deleting in the order A → B → resolve-C minimises dangling pointers. The only reference into **live code** is #10 → `compute_macro_market.py:2078` — fix that comment first.

## Suggested order of deletion (if you choose to act)

1. **#1, #2** (root handover + secrets checklist) — safe immediately; no code touches them.
2. **#7** (`regime-aa-fill-report.md`) — unreferenced regenerable snapshot; lowest-risk of the generated layer.
3. **#3, #4, #5, #6** — each after the noted one-line reference reword.
4. **#8 + #9 + #13** — as a single "retire the generated regime-aa `.md` layer" decision (caveat ⚠️1), keeping the `.csv` + build scripts.
5. **#10, #11, #12** — defer until the code comment (#10), audit-of-record pointers (#11), and outbound regime-aa action (#12) are settled.
6. **Prior non-`.md` candidates** (Section D) — `archive/generate_review_excel.py` deletes immediately; the `.docx` pair on the external-distribution decision.
