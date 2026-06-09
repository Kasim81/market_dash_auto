---
name: refresh-manuals
description: >-
  Update the two hand-written contributor manuals (manuals/technical_manual.md
  and manuals/forward_plan.md) so they accurately describe the current state of
  the codebase, then open a pull request for review. Use this when asked to
  refresh, update, or reconcile the manuals/docs against the code — and it is
  the task run by the scheduled "Refresh Manuals" routine.
---

# Refresh the contributor manuals

You are updating this repo's two hand-written contributor manuals so they keep
tracking the live codebase, then opening **one pull request** for human review.
When run as a scheduled routine you are autonomous — be thorough and decisive,
but stay strictly within the scope below.

## Files you may modify — and only these
- `manuals/technical_manual.md` — authoritative record of current code state.
- `manuals/forward_plan.md` — phase summary, priority queue (§2), roadmap (§3),
  chronology (§4).

Do **not** edit any code, data, CSV, or workflow file. Do not touch anything
outside those two manuals. If you spot a code bug or a doc that can't be fixed
without code changes, note it in the PR body rather than fixing it here.

## Step 1 — review what changed (code + GitHub history)
Reconstruct what has actually changed since the manuals were last updated. Use
both the working tree and GitHub history:
- `git log --since="60 days ago" --pretty='%h %ad %s' --date=short`
- `git diff --stat HEAD~25..HEAD` (widen the range as useful)
- Read the top "> Last updated: YYYY-MM-DD" stamp in each manual to anchor how
  far back to look.
- Review recent **merged pull requests** and notable issues via the GitHub
  tools (e.g. the perpetual "Daily Audit Log" issue) for context the commit
  messages don't capture.

## Step 2 — reconcile each drift-prone area against reality
For each item below, compare what the manual *claims* to what the code *does*,
and edit only where they diverge:
- **Data sources & APIs:** cross-check the prose source list against the actual
  modules in `sources/*.py` and the curated libraries `data/macro_library_*.csv`.
  Add new sources, remove deleted ones, fix descriptions.
- **Coverage gaps:** state countries/series with **no dedicated source** —
  e.g. a country covered only by World Bank / IMF aggregators with no national
  statistics-office source wired. Absence is information; record it.
- **GitHub Secrets table (technical manual §12):** reconcile every row against
  the `env:` block of `.github/workflows/update_data.yml` and the modules that
  read each key. Add/clarify/remove rows so the table matches what the workflow
  passes and what code consumes.
- **Module reference (§9.x):** module list, counts, and approximate line counts.
  Recompute from the tree (`ls sources/*.py`, `wc -l <files>`) and update the
  figures instead of leaving stale numbers.
- **Schedule & operational notes:** confirm the cron(s) and workflow env
  settings described match the actual workflow files.
- **Known issues / status, forward-plan priority queue (§2) and chronology
  (§4):** retire completed items, add newly completed or newly discovered work,
  keep dates accurate.
- **Provisional / unverified wiring:** sources awaiting their first successful
  credentialed fetch — describe status truthfully.

## Step 3 — editorial rules
- Match the existing voice, structure, heading style, and the dated-entry
  convention already used in each manual. Do not restructure or reflow sections
  you are not changing.
- Be factual and specific; never invent behaviour. If unsure whether something
  changed, verify it in the code before writing it.
- Bump the "> Last updated: YYYY-MM-DD" stamp (UTC) on any manual you change.
- Keep the diff tight — change only what is genuinely stale.

## Step 4 — output
- **If nothing is materially stale:** make no changes, open no PR, and report a
  one-line note that the manuals are already current.
- **Otherwise:** create a `claude/`-prefixed branch (e.g.
  `claude/manual-refresh-<YYYY-MM-DD>`), commit **only** the two manual files
  with a clear message, push, and open a pull request titled
  `Docs: refresh technical manual & forward plan (<YYYY-MM-DD>)`. The PR body
  must list the concrete changes grouped by manual and section, each with a
  one-line reason tied to a code fact (file/commit). Do not merge the PR and do
  not push to the default branch.
