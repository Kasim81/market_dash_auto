# Repo Cleanup Handover — work-order for a dedicated cleanup session

**Prepared:** 2026-07-14 · **Audience:** a fresh Claude Code session dedicated to
repo tidy-up. **Scope:** finish the `.md`-file deletion sweep that began with the
2026-07-14 manuals-integration work.

This is a **self-contained work-order** — everything you need is below; you do not
need the analysis doc to execute it (though the full rationale lives in
`file_del_candidates.md`, rebuilt in **PR #267**).

---

## 0. What has already been done (do NOT redo)

**PR #267** (branch `claude/youthful-gates-iyqv23`) folded the FactIQ audit workstream
into the manuals and retired the `handover/` folder (data relocated to `manuals/factiq_*`),
and rebuilt `file_del_candidates.md` as the full analytical register.

The three Section-A **High-confidence deletes were *not* carried by #267** (they were
a post-merge commit that never landed) and were completed afterwards:
- `AUDIT_HANDOVER_2026-06-15.md` — removed by repo-cleanup **PR #269**.
- `manuals/2026-06-15-codespace-secrets-checklist.md` and
  `manuals/2026-06-18-cpi-split-codespace-spec.md` — removed by the **reconciliation PR**
  that also refreshed `manuals/multifreq_plan.md` counts (50/302/8.4M → 91/390/8.8M) and
  repointed all inbound references (incl. 5 CSV/HTML data-provenance citations of the
  cpi-split spec → `2026-06-18-source-wiring-audit-proposal.md` §Resolution).

**All three Section-A files are now gone from `main`.** This handover covers everything
that remains (Sections B, C, D below).

> ⚠️ **Line numbers drift.** The daily pipeline commits to `main` constantly and
> PR #267 changed line counts, so every reference below is given by **filename +
> section/anchor**, not line number. Always `grep` for the filename to find the
> live reference before editing.

---

## 1. The prompt (paste this to start the dedicated session)

> Execute the repo-cleanup work-order in `REPO_CLEANUP_HANDOVER.md`. Work through
> Group B (delete-after-reword), then decide Group C (deferred / needs a call) and
> the Group E generated-layer question, then Group D (non-`.md`). For every deletion:
> (1) `grep -rn "<filename>"` across `--include=*.md --include=*.py --include=*.yml`
> first; (2) rewire each inbound reference in a *surviving* file per the notes here;
> (3) `git rm`; (4) re-grep to confirm zero dangling references; (5) `python -m
> py_compile` any touched `.py` and run the relevant `test_*.py`. Do NOT delete any
> `data/*.csv`. Respect the guardrails in §3. Commit in logical groups; open one PR.

---

## 2. The remaining work

### Group B — DELETE after a small reference reword (Medium confidence)

Each of these is **fully implemented and captured in the manuals**; only a pointer or
two needs rewording in a surviving file first.

| # | File to delete | Why it's safe | Reference(s) to rewire first |
|---|---|---|---|
| B4 | `manuals/2026-06-10-regime-aa-v2-pipeline-handoff.md` | Cross-repo handoff memo; fully reconciled into **forward_plan §3.12–§3.17** (each ask has an audited status line). | `forward_plan.md` cites it by name in **two** places — the §3.12–§3.17 "Provenance & reconciliation" blockquote and the §2 "Candidate next tracks → Regime-AA v2 asks" bullet. Reword both to cite "§3.12–§3.17" instead of the file. |
| B5 | `manuals/2026-06-17-m2-units-trio-recommendation.md` | M2/M3-trio relabel; **shipped PR #221** (EZ_M3/JPN_M2/CHN_M2). Outcome in forward_plan §2.B + chronology. | Cited as the rationale note in **3 library CSVs**: `data/macro_library_ecb.csv`, `…_boj.csv`, `…_dbnomics.csv`. Repoint those note fields to "forward_plan §2.B / chronology (PR #221)" or drop the citation. (These are note-column edits, not schema changes.) |
| B6 | `manuals/2026-07-07-eu-freeze-freshness-china-handover.md` | P0/P1/P2 work-order; all three resolved — **forward_plan §2.A A10 / A11 / A1** (richer than the memo). | `forward_plan.md` A10 ends with a parenthetical "(Original discovery notes: `…eu-freeze-freshness-china-handover.md` P0 section.)". Drop or reword that clause. |
| B7 | `manuals/regime-aa-asks/regime-aa-fill-report.md` | **Generated** fill snapshot (`build_fill_report.py`); its headline (98/24/15/25) is verbatim in **forward_plan §2.B**. | None — unreferenced. **But see Group E** (it regenerates). |
| B8 | `manuals/regime-aa-asks/regime-aa-sourcing-backlog.md` | **Generated** backlog (`build_sourcing_backlog.py`); **forward_plan §2.B is a superset** (B1–B15 carry exact series ids, effort, sequencing). | `forward_plan.md` §2.B says it is "distilled from" this file in **two** places (the §2.B intro and the §2 "candidate next tracks" bullet). Reword to cite the coverage map (`data/regime-aa-indicator-coverage.csv` + `build_sourcing_backlog.py`). **See Group E.** |
| B9 | `manuals/regime-aa-asks/requests/*.md` (**15 files**) | **Generated** per-gap memos (`scripts/phase_0_coverage_check.py --write-memos`) = forward_plan §2.B **B1–B15**, one-to-one. Tool output, not source. | Written by the phase_0 tool; pointed at by B8. **See Group E — deleting these is cosmetic unless the generator stops.** |

### Group C — DEFER: needs a call or a code fix first

| # | File | What to resolve before deleting |
|---|---|---|
| C10 | `manuals/2026-06-15-source-tier-audit.md` | Findings resolved & the tier model is now in code (`_load_tier_map`/`_select_winner`, technical_manual §9.4). **BUT a live code comment in `compute_macro_market.py` references it** (`grep -n "source-tier-audit" compute_macro_market.py` — was ~line 2078). **Fix that comment first** (repoint to technical_manual §9.4 or drop it), plus the forward_plan §2.A pointers. Then it deletes cleanly. |
| C11 | `manuals/2026-06-15-label-vs-data-audit.md` | Fully remediated (PR #225/#250) but it is the cross-referenced **audit-of-record**. Referenced by forward_plan §2.A (the PR #225 reconciliation bullet) and `…source-wiring-audit-proposal.md` (a KEEP file). **Owner decision:** delete after pruning those pointers, **or keep as the archived audit-of-record.** (Its one reference to the now-deleted secrets checklist was already repointed to technical_manual §12 in PR #267.) |
| C12 | `manuals/2026-06-10-regime-aa-v2-pipeline-handoff-corrections.md` | In-repo content fully captured (forward_plan §3.14/§3.15), but it is the source artefact for an **outbound "file back to regime-aa" action** (noted in the forward_plan §3.12–§3.17 provenance blockquote). **Confirm that inverse-direction proposal was delivered to the regime-aa project**, then delete alongside B4 and update the provenance blockquote. |
| C13 | `manuals/regime-aa-asks/regime-aa-indicator-coverage.md` | **Generated** readable twin of the live `data/regime-aa-indicator-coverage.csv`. Part of the Group E decision. |

### Group D — Prior (2026-04-27) non-`.md` candidates (re-verify, then owner call)

| Path | Note |
|---|---|
| `archive/generate_review_excel.py` (5.3 KB) | High-confidence orphan — pre-2026-04-08 indicator ids absent from the live `data/macro_indicator_library.csv` (`grep` to confirm). Deletes immediately. |
| `archive/indicator_groups_review.xlsx` (16 KB) | Its only consumer was the script above. Delete with it. |
| `archive/indicator_groups_review_UPDATED.xlsx` (23 KB) | Historical review output. Owner call. |
| `manuals/indicator_manual.docx` (89 KB) | Regenerable from the `.md` via `manuals/build_docx.py`; not built by CI. **Owner call: keep only if distributed externally.** If dropped, `build_docx.py` becomes a candidate too. |
| `manuals/macro_market_cheat_sheet.docx` (46 KB) | Same via `manuals/md_to_docx.py`. If both `.docx` go, both helper scripts become candidates. |

### Group E — the generated `regime-aa-asks/` `.md` layer (one decision)

`regime-aa-fill-report.md` (B7), `regime-aa-sourcing-backlog.md` (B8), the
`requests/*.md` (B9) and `regime-aa-indicator-coverage.md` (C13) are **emitted by
committed scripts** — `build_indicator_coverage_map.py`, `build_fill_report.py`,
`build_sourcing_backlog.py`, `scripts/phase_0_coverage_check.py` — from
`data/regime-aa-indicator-coverage.csv`. **Deleting a `.md` is cosmetic: the next run
of its generator recreates it.**

A durable deletion is therefore one *decision*, not four: **do you want to stop
committing the generated `.md` layer?** If yes → delete the four `.md` files **and**
add them to `.gitignore` (or drop the `.md`-emit step in the build scripts), keeping
only the `.csv` + scripts as the source of truth. If no → keep them and skip B7/B8/B9/C13.
Either way, `regime-aa-indicator-req.md` (the hand-written requirements spec) **stays**.

---

## 3. Guardrails (do not skip)

1. **NEVER delete `data/regime-aa-indicator-coverage.csv`.** It is the live machine
   input to `scripts/phase_0_coverage_check.py` (a documented, exit-code-gating
   operator utility referenced from both manuals). It is not a candidate.
2. **NEVER delete any `data/*.csv`, `sources/*.py`, or `test_*.py`** — all live
   runtime / pipeline outputs.
3. **Verify-before-delete, verify-after-delete.** For each file: `grep -rn
   "<basename>" --include=*.md --include=*.py --include=*.yml .` before (to find
   refs) and after (to confirm zero dangling). The only reference into **live code**
   in this whole set is C10 → `compute_macro_market.py`; handle it first.
4. **Keep these — they are NOT candidates** (verified 2026-07-14): `manuals/2026-06-10-alpha-vantage-evaluation.md`
   (open PE-writer work item), `manuals/2026-06-18-source-wiring-audit-proposal.md`
   (companion to `build_source_inventory.py` + sole home of the `FLAG_*` defs),
   `manuals/community_datasets_review.md` (Stage F deliverable + deferred notes),
   `manuals/multifreq_plan.md` (active Phase 2), `manuals/regime-aa-asks/regime-aa-indicator-req.md`
   (external requirements contract), plus `README.md`, `audit_comment.md` (generated
   daily), `indicator_manual.md`, `macro_market_cheat_sheet.md`.

---

## 4. Suggested execution order

1. **C10 first** — fix the `compute_macro_market.py` code comment, then delete the
   source-tier audit (the only code-referencing item).
2. **B4, B5, B6** — reword the forward_plan / CSV-note pointers, then delete.
3. **Group E decision** → if "stop committing", do B7/B8/B9/C13 + `.gitignore`; reword
   the two forward_plan §2.B "distilled from" pointers.
4. **C11, C12** — owner call (archive-of-record?) / confirm the outbound regime-aa action.
5. **Group D** — `archive/generate_review_excel.py` + its `.xlsx`; the `.docx` pair on
   the external-distribution decision.
6. **Finally** — update `file_del_candidates.md` to mark everything actioned, and
   consider whether the register itself (a completed audit artefact) should be retired.

## 5. Done-when

- `grep -rn "2026-06-10-regime-aa-v2-pipeline-handoff\|2026-06-17-m2-units-trio\|eu-freeze-freshness-china-handover\|source-tier-audit\|regime-aa-fill-report\|regime-aa-sourcing-backlog"` returns **no live references** in surviving `.md`/`.py`/`.yml` (only historical mentions inside `file_del_candidates.md` are acceptable).
- `python -m py_compile compute_macro_market.py` passes; `test_tier_merge.py` still passes.
- No `data/*.csv` was touched; `data/regime-aa-indicator-coverage.csv` still present.
- One PR, grouped commits, clear body.
