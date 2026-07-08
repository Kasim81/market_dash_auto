# Fable Recommendations — MERGED into forward_plan (2026-07-08)

**This document is superseded.** Its full contents were merged into
`manuals/forward_plan.md` on 2026-07-08 so the project has **one unified track
of work**:

- **Live data repairs** (was Part 0: EU_INFL1 freeze / freshness-honesty pass /
  China cluster) → already tracked as forward_plan **§2.A A10 / A11 / A1**
  (operational detail also in
  `manuals/2026-07-07-eu-freeze-freshness-china-handover.md`).
- **Structural / architecture track** (was Parts 1–2: precedence enforcement,
  source registry, backoff consolidation, `__main__` guard, CI test gate,
  library_sync dedup, calculators split, audit hard-fail class, Pages
  deployment, log artifacts, hist-churn reduction, simple-pipeline canary,
  staged CI) → forward_plan **§2.C, items C1–C13**.
- **Endorsed-as-is decisions** (was Parts 3–4) → the "Reviewed and endorsed
  as-is" block at the end of §2.C.
- **Unified sequencing** → the "§2.C sequencing" note (A10+A11 → A1 → C4 → C5 →
  C3 → C2 → C1 → C9/C10 → multifreq §5).

The original review text (2026-07-07, evidence line numbers at commit
`08e7026`) is preserved in git history at this path — see
`git log -- "fable recommendations.md"`.

**Do not add new work items here.** Add them to `manuals/forward_plan.md` §2.
