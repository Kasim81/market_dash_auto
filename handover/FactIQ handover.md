# FactIQ Handover — `market_dash_auto`

**Repo:** github.com/Kasim81/market_dash_auto · **Prepared:** 2026-07-14 ·
**Audience:** a fresh Claude Code session (or engineer) picking up this work.

This is the **single entry point** for the FactIQ data-audit workstream. It
indexes the source planning/audit documents in this folder, records what has
shipped (with PR/branch references), and lists what remains outstanding.

---

## 0. What this workstream was
The dashboard's market/macro data (from yfinance + FRED + ~30 other sources) was
audited **ticker-by-ticker against FactIQ** (an authenticated data-warehouse
plugin) as an independent reference, to catch value and metadata errors. The
audit found four real bugs; all four are now fixed and merged. A second goal —
learning from / partially replicating FactIQ's own sources — produced the
source-wiring strategy in the plan (§11) and the first direct-wire source
(US Treasury), also merged.

---

## 1. ⚠️ Environment gotchas — READ BEFORE DOING ANYTHING

1. **This local clone drifts FAR behind `origin/main`.** It was found **348
   commits (~9 weeks) behind**. The daily CI pipeline commits to *remote* `main`;
   this OneDrive clone is **not** auto-pulled. **Always `git fetch origin` and
   diff against `origin/main` before trusting local files or `git log`.** (A prior
   session wrongly concluded the pipeline had "stopped on May 13" — it was just
   the stale clone. The pipeline is healthy and commits daily.)
2. **TLS-intercepting proxy on this machine.** Strict HTTPS fails cert validation
   locally and `google.oauth2` (a CI-only dep) is **not installed** — so you
   **cannot** run the live pipeline or live network fetches here. Validate code
   with `python -m py_compile` + unit tests that **stub** the heavy modules
   (google/googleapiclient/gspread, and the source modules). Real end-to-end runs
   happen in **GitHub Actions (CI)** on Linux/UTF-8.
3. **`gh` is installed + authenticated** (account `Kasim81`, keyring). It is
   **not on the bash PATH** — call it as `"/c/Program Files/GitHub CLI/gh.exe"`.
   Use it for PRs and, crucially, `gh run list --workflow=update_data.yml` to
   inspect the *actual* pipeline status instead of guessing from the local clone.
4. **Pipeline is HEALTHY.** `.github/workflows/update_data.yml` (cron `34 0 * * *`)
   runs daily/green and auto-commits "Update market data + explorer" to `main`.
5. **FactIQ = an authenticated MCP plugin.** Tools are deferred — load via
   `ToolSearch("select:mcp__plugin_factiq_factiq__get_market_data,...")`. Read-only
   warehouse; 50-row cap per call (aggregate in SQL); ~1 req/sec; no monthly
   quota. It runs **only inside an interactive agent session** and can NEVER be
   imported by the headless CI pipeline. **Free today, may become paid** — hence
   the golden snapshot (see §4).

---

## 2. Source documents in this folder

| File | What it is |
|---|---|
| `FactIQ handover.md` | **This file** — the master index. |
| `FACTIQ_AUDIT_PLAN.md` | The full plan. Key sections: **§8** FactIQ architecture teardown (what's cloneable), **§11** source inventory & direct-wire strategy (three buckets), **§12** dead-ticker & coverage-gap cleanup backlog. |
| `audit/AUDIT_REPORT.md` | The audit report — headline findings, counts, per-finding triage, methodology. |
| `audit/findings.csv` | 636 findings (ticker, check, repo value vs FactIQ, severity, verdict). |
| `audit/working_list.csv` | All ~401 instruments with their audit tier (A/B/C) + flags. |
| `audit/golden/*.json` | **Golden snapshot** — FactIQ reference values captured while free (insurance vs a future paywall). |
| `audit/cache/*.json` | Raw FactIQ pulls (catalog snapshot, quotes) backing the findings. |
| `audit/*.py` | The audit's own build/fix scripts (reproducibility). |

> **Important caveat on the audit:** it was run against a **stale local snapshot
> (data as-of 2026-05-13)**. The **structural** findings (metadata/code bugs)
> were re-confirmed against live `main` and fixed. The **data-value** numbers
> (prices/returns) are stale — a value-level re-check needs a fresh run against
> current data (see §5, item 1).

---

## 3. What has been COMPLETED

**All four fixes merged to `main` via PR #265** — _"Re-apply FactIQ-audit
data/pipeline fixes on current main"_ (merge commit `0d50a02`, merged
2026-07-14, from branch `fix/factiq-remediation-live`).

| # | Fix | Where it landed (on `main`) | Verified |
|---|---|---|---|
| 1 | **EMB proxy/currency bug** — one USD ETF proxied 9 rows; dedup leaked an `ARS` label onto a USD instrument (1Y USD return flipped +11.69% → −13.35%). Removed the 8 country-proxy rows; kept EMB as a standalone USD ETF. | `data/index_library.csv` (script `audit/fix_emb.py`) | row count + currency checked |
| 2 | **FEZ / ASHR / HYXU currency** — US-listed USD ETFs mislabeled foreign. `HYXU→USD`; **`FEZ`/`ASHR` split** into a native-currency index row (`^STOXX50E` EUR / `000300.SS` CNY) + a USD ETF row. | `data/index_library.csv` (scripts `fixes/fix_currency_labels.py`, `fixes/split_dual_ticker_rows.py`) | before/after rows checked |
| 3 | **`.L` pence ÷100 misfire** — every `.L` ticker was divided by 100; EUR-quoted London ETFs (`IEAC.L` ~€120→1.2) were wrongly shrunk. Gated on `base_currency ∈ {GBP,GBX}`. (Returns were unaffected — only `Last Price` display.) | `fetch_data.py` (`_is_pence_quoted` / `_should_convert_pence`); test `fixes/test_pence_gate.py` | regression test **passes** |
| 4 | **US Treasury par-yield curve** — new keyless source (13 tenors, daily `home.treasury.gov` CSV feed; NOT FiscalData). Wired into the source registry. | `sources/treasury.py`, `data/macro_library_treasury.csv`, `fetch_macro_economic.py`, `sources/__init__.py` | registers; handler callable; compiles |

Verification was **local** (`py_compile` + stubbed unit tests + registry checks).
The **real end-to-end proof runs in CI** on the next pipeline execution — worth
confirming with `gh run list --workflow=update_data.yml` after the next daily run.

---

## 4. Key artifacts & the golden snapshot
- The **golden snapshot** (`audit/golden/`, `audit/cache/`) captures FactIQ
  reference values + the data catalog **while FactIQ is free**. If FactIQ moves
  to paid, this is the fallback reference set for re-auditing. Keep it.
- FactIQ's warehouse normalizes ~22 official sources into a 3-table model
  (`series` / `data_points` / `dimensions`) — see `FACTIQ_AUDIT_PLAN.md` §8 for
  what's learnable vs proprietary.

---

## 5. What remains OUTSTANDING

Ordered by suggested priority. Cross-references are to `FACTIQ_AUDIT_PLAN.md`.

1. **Re-validate the audit against LIVE data.** The value-level findings used the
   stale 2026-05-13 snapshot. Re-run the Tier-A value + Tier-B promotion sweeps
   against the current `market_data_comp.csv` on `main` if value-level confidence
   is required. Method + tiering are in `AUDIT_REPORT.md` / `working_list.csv`.
2. **§12 Dead-ticker & coverage cleanup** — `^CM100`, discontinued `^SP500-xxxxxx`
   GICS sub-indices, `^VXEEM`, ~47 empty foreign UCITS proxies. **Re-check against
   LIVE `index_library.csv` first** (it moved ~28 lines upstream since the audit),
   then retire via the existing `data/removed_tickers.csv` ledger +
   `data/yfinance_failure_streaks.csv`.
3. **CSI 500 (`000905.SS`) re-source** — library marks it UNAVAILABLE, but FactIQ
   prices it (~8138 CNY). Candidate to wire a working source. (Its sibling CSI
   1000 `000852.SS` is genuinely unpriceable — leave it.)
4. **§11 direct-wire roadmap (continue)** — Treasury was milestone 1 (done). Next
   keyless/low-friction public-API sources, each as its own `sources/*.py` using
   Treasury as the template: **BLS, BEA, Census, EIA, SingStat, Japan e-Stat**.
   Reminder: FactIQ itself is NOT wireable into CI (OAuth MCP, interactive-only);
   it stays an audit/analysis tool + the golden snapshot.
5. **Latent pre-existing bug (not from this work):** `_load_tier_map()` in
   `fetch_macro_economic.py` reads library CSVs without `encoding="utf-8"` →
   `UnicodeDecodeError` on Windows cp1252 (harmless on CI's UTF-8). One-line fix.
6. **Housekeeping:** the superseded local branch `fix/factiq-audit-remediation`
   (see §6) can be deleted once you've confirmed everything valuable from it now
   lives in this `handover/` folder (it does).

---

## 6. Branch / PR ledger

| Branch | Commit | State | Contents |
|---|---|---|---|
| `main` | — | live | Includes all 4 fixes (via PR #265) and this `handover/` folder (via PR for `docs/factiq-handover`). |
| `fix/factiq-remediation-live` | `b51d85e` | **merged → PR #265** | The 4 fixes, re-derived on current `main`. |
| `docs/factiq-handover` | — | this delivery | Adds the `handover/` folder (this document + all planning/audit docs). |
| `fix/factiq-audit-remediation` | `b9191d8` | **superseded, local-only (never pushed)** | The FIRST fix attempt, built on a 9-week-STALE base — do NOT merge. Its audit deliverables have been copied into this `handover/` folder, so it is now safe to delete. |

---

## 7. Working conventions & lessons (worth repeating)
- Prefer surgical `Edit`s + one reviewable script per data change (with a backup)
  over hand-editing CSVs. See `fixes/` and `audit/fix_emb.py` on `main`.
- Verify code with `py_compile` + **stubbed** unit tests; a local run never
  reflects CI here (TLS proxy). CI is the source of truth.
- **Always reconcile the local clone with `origin/main` first** — the single
  biggest trap in this repo (see §1.1).
- Background subagents can be **very slow to start** (one took ~44h wall-clock).
  Don't declare an agent "dead" from a stale transcript alone, and don't launch
  duplicates — check for real output/liveness first.
