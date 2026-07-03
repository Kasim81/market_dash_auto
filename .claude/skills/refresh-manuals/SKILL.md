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
tracking the live codebase, then maintaining **a single rolling pull request**
for human review — and only when the manuals are actually stale. When run as a
scheduled routine you are autonomous — be thorough and decisive, but stay
strictly within the scope below. There must never be more than one open
manual-refresh PR; reuse the rolling branch and PR rather than opening a new one
each run.

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

## Step 4 — output: one rolling PR, only when stale
Never open more than one manual-refresh PR, and never open one that isn't
warranted. Reuse a single rolling branch and PR rather than minting a new one
each run.

- **If nothing is materially stale** — the reconciliation produces no diff
  against the default branch — make no changes and open no PR. Report a one-line
  note that the manuals are already current. A bump of the `> Last updated:`
  stamp is **not** by itself a material change: if the stamp is the only thing
  that would change, leave it and treat the manuals as current. If a rolling PR
  happens to be open but its diff against the default branch is now empty (e.g.
  the drift was fixed elsewhere), close it so nothing stale lingers.
- **If there are material changes:**
  1. Use the single fixed rolling branch **`refresh-manuals/rolling`** — never a
     dated branch. Reset it onto the latest default branch so it never
     accumulates stale history or conflicts:
     `git fetch origin <default> && git checkout -B refresh-manuals/rolling origin/<default>`,
     apply the edits, then commit **only** the two manual files with a clear
     message.
  2. Force-push it: `git push -f -u origin refresh-manuals/rolling`.
  3. If an open PR from `refresh-manuals/rolling` into the default branch already
     exists, the force-push updates it in place — do **not** open another. Only
     if none is open, open **one** PR titled `Docs: rolling manual refresh`
     (check first with `gh pr list --head refresh-manuals/rolling --state open`,
     or the GitHub MCP tools if `gh` is unavailable). Either way the body lists
     the concrete changes grouped by manual and section, each with a one-line
     reason tied to a code fact (file/commit).
- Never merge the PR yourself and never push to the default branch.
