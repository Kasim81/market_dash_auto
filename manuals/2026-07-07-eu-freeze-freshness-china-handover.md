# Handover — EU_INFL1 freeze (P0) + freshness-honesty pass (P1) + China cluster (P2)

> Created 2026-07-07 (UTC) after the CPI-definition split (PR #249) and the
> label-vs-data audit closure (PR #250) landed and the daily workflow re-ran
> (`ba51d46`, 2026-07-07 14:27 UTC). This is a work order for the **next
> credentialed session**. Run it in the Codespace — it needs live network +
> `FRED_API_KEY` / `ESTAT_APP_ID` / `BLS_API_KEY` / `BDF_API_KEY` /
> `BRIGHTDATA_API_KEY` (all present here) and, for a real end-to-end validation,
> `GOOGLE_CREDENTIALS` is optional (skip Sheets push; CSVs are written either way).

## Read first — architecture rules that bind this work
- **Every fetched identifier lives in a `data/macro_library_*.csv`, never in a
  `.py` literal** (`forward_plan.md` §0). All of the changes below are CSV edits
  plus, at most, a one-line calculator repoint.
- The runtime merge is **tier-aware, cadence-first, staleness-fallback**
  (`fetch_macro_economic._dedupe_snapshot_rows` / `_select_winner`, unit-tested in
  `test_tier_merge.py`). Do **not** touch that logic. A column with two sources of
  the same measure-kind lets the finer cadence / fresher obs win automatically.
- Freshness is judged by `data_audit.py` Section C against
  `data/freshness_thresholds.csv` (Daily 5 / Weekly 10 / Monthly 45 / Quarterly
  120 / Annual 540 days) unless a row sets its own `freshness_override_days`.
- **Validation gate for every composite touched: it must MOVE month-to-month
  after the change.** The whole point of P0 is that a frozen-flat raw = a broken
  live indicator (that is how `JP_INFL1` hid at a flat 8.49 for months).

Environment check before starting:

    python3 -c "import os;print({k:bool(os.environ.get(k)) for k in ['FRED_API_KEY','ESTAT_APP_ID','BLS_API_KEY','BDF_API_KEY','BRIGHTDATA_API_KEY']})"
    curl -s --max-time 20 "https://api.db.nomics.world/v22/series/Eurostat/prc_hicp_manr/M.RCH_A.CP00.EA20?observations=1" | head -c 200

---

## P0 — `EU_INFL1` is silently frozen (the real repair; same class as the JP_INFL1 bug)

### Evidence
`EU_INFL1_raw` (from `data/macro_market_hist.csv`, month-end) has been **flat at
2.1% for 6 months** while the healthy composites move:

    JP_INFL1:  2.10 → … → 1.56 → 1.27          ✅ (fixed by PR #249)
    US_INFL1:  2.53 → 2.87 → 3.11 → 3.27 → 2.92 ✅
    EU_INFL1:  2.10 → 2.10 → 2.10 → 2.10 → 2.10 ❌ frozen since 2026-01

`_calc_EU_INFL1` = `mean(EA_HICP, EA_HICP_CORE_YOY)`. Both inputs stall at
`last_obs = 2026-01-02` (age ~186d) in the 2026-07-07 audit. The three EU
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

### What I already ruled out (do NOT repeat)
- **"Just switch to the direct Eurostat API" — does not work.** I probed the
  official Eurostat dissemination API directly:
  `.../statistics/1.0/data/prc_hicp_manr?coicop=CP00&unit=RCH_A&geo=EA20&sinceTimePeriod=2025-10`
  → it also returns **only through 2025-12** (2.1, 2.1, 2.0). So the stall is
  upstream of DB.nomics for this exact `RCH_A / EA20 / CP00` slice.

### Recommended approach (verify live before repointing — guardrail below)
1. **Find why the slice stalls.** Likely a rebase / geo-composition change at
   2026-01 (EA20 vs EA / EA19), or the `RCH_A` (annual-rate) product was
   superseded. Probe: the `prc_hicp_midx` **index** dataset (compute YoY yourself
   from the 12-month ratio), and try `geo=EA` and `geo=EU27_2020`, and newer
   `sinceTimePeriod` values, on both DB.nomics and the direct Eurostat API.
2. **Strong lead — the ECB Data Portal (already wired, `sources/ecb.py`).** ECB
   publishes euro-area HICP (the `ICP` dataset, e.g. an `ICP.M.U2.N.000000.4.ANR`
   annual-rate key and the ex-energy-food core equivalent). We already use ECB for
   CISS, CES, the AAA yield curve, and `EZ_M3`, so a HICP repoint is low-friction
   and ECB is the authoritative euro-area publisher. **Verify the exact key
   returns fresh monthly data (should have May/Jun 2026) before wiring.**
3. Repoint `EA_HICP` / `EA_HICP_CORE_YOY` to the fresher source (add/adjust the
   library row; the cadence-first merge will prefer the fresher obs). If ECB is
   used, add rows to `data/macro_library_ecb.csv`; if a corrected Eurostat slice,
   edit the `data/macro_library_dbnomics.csv` rows in place.
4. Do the same freshness check for the 3 EU sentiment series (Eurostat Business &
   Consumer Survey). If no fresher path exists, they become a documented Known
   Data Gap — but HICP is the priority because it drives `EU_INFL1`.

### Notes
- `EU_NOWCAST1` still **moves** (0.77 → 0.90) despite `EZ_IND_PROD` / `EZ_RETAIL_VOL`
  being ~214d stale, so it is a lower concern than `EU_INFL1` — but the same
  Eurostat `teiis080` / `teiis260` family is stale; fold it into the same probe.
- Effort: M–L (discovery is the work; the CSV repoint is trivial).

---

## P1 — Freshness-honesty pass (restore the audit's signal-to-noise)

The 2026-07-07 run shows **79 issues (78 stale)** — but most are *honest
publication lag under too-tight tolerances*, which is exactly why the genuine
`EU_INFL1` freeze (P0) was invisible in the pile. Widen `freshness_override_days`
**only where the source's real cadence justifies it** — this is honesty tuning,
not hiding P0. Read each row's current value from the library before editing
(don't trust `awk -F,` — the notes columns contain commas; use `csv`/pandas).

### 1. Normal-lag monthly series (add/raise `freshness_override_days`)
- **OECD COICOP2018 CPI-YoY family** (my 7 new rows in
  `data/macro_library_dbnomics.csv`): `JPN_CPI_YOY`, `CAN_CPI_YOY`, `CHE_CPI_YOY`,
  `FRA_CPI_YOY`, `ITA_CPI_YOY`, `NLD_CPI_YOY`, `DEU_CPI_YOY`. OECD publishes
  COICOP CPI ~6–8 weeks in arrears and the DB.nomics mirror adds a little more —
  observed age ~67d vs a 45d default. Set **~90d**. (Cross-check `JPN_CORE_CPI_YOY`,
  which pre-dates this and shows the same cadence.)
- **e-Stat** `JPN_HH_EXP`, `JPN_EWS_DI` (`data/macro_library_estat.csv`): FIES /
  Economy-Watchers publish ~5–6 weeks late; observed ~67d vs a 60d override → set
  **~75–80d**. (`JPN_IND_PROD` at 123d/60d is borderline — the DB table carries
  finals ~T-3 months; leave or nudge, note in PR.)
- **ONS** `GBR_CPI_YOY` (`data/macro_library_ons.csv`): 95d vs 75d → **~90d**.

### 2. Event-driven policy rates (§2.A A7 — flagged stale only because the bank hasn't moved)
Daily-cadence rate series trip the tight tolerance whenever the central bank
holds. Set `freshness_override_days` to the decision cadence (~90–120d):
- `JPN_POLICY_RATE` (`data/macro_library_boj.csv`, 18d vs 5d)
- `CAN_POLICY_RATE` (`data/macro_library_boc.csv`, 249d vs 7d)
- `CHN_POLICY_RATE` (`data/macro_library_dbnomics.csv`, IMF/IFS — also genuinely
  mirror-stale; a wide override is honest either way)
- Also scan `EA_DEPOSIT_RATE`, `GBR_BANK_RATE` for the same pattern.

### 3. Dead, unused frozen mirror — drop or wide-override
- **`JPN_CPI_INDEX`** (`data/macro_library_fred.csv`, FRED `JPNCPIALLMINMEI`,
  frozen 2021-06, age 1859d). The CPI split renamed it from `JPN_CPI`; **nothing
  consumes it now** (grep confirms `JP_INFL1` uses `JPN_CPI_YOY`; no `_calc`
  reads `JPN_CPI_INDEX`). It is pure EXPIRED noise. Either **drop the FRED row**
  (no live JP CPI-index source is wired, so the column would simply disappear) or
  set a very wide override. Recommended: drop it — a discontinued index level with
  no consumer and no live source is not worth carrying. (`CHN_CPI_INDEX` is the
  analogous case but it IS consumed by `CN_INFL1` — handle under P2, not here.)

**Guardrail:** never widen a tolerance to silence a *live composite* that has gone
flat. If a series is genuinely dead and feeds an indicator, that is a P0/P2
source-replacement problem, not a P1 override.

Effort: S (CSV edits only). Validate with a keyed regen + re-run `data_audit.py`;
the STALE/EXPIRED count should drop toward the genuinely-dead residue.

---

## P2 — China inflation cluster (`CN_INFL1` degraded; §2.A A1)

### Evidence
`_calc_CN_INFL1` = `mean(_yoy(CHN_CPI_INDEX), CHN_PPI)` — **both inputs frozen**:
- `CHN_CPI_INDEX` — `data/macro_library_fred.csv`, FRED `CHNCPIALLMINMEI`, frozen
  **2025-04** (age 459d).
- `CHN_PPI` — `data/macro_library_fred.csv`, FRED `CHNPIEATI01GYM`, frozen
  **2022-12** (age 1313d).

So `CN_INFL1` is running on ~1–3-year-old data. (`CHN_CPI_YOY`, the new split
column, exists only on the World Bank annual fallback, itself frozen at 2023 — so
it is *not* a fix.)

### What I already ruled out during PR #249 (do NOT repeat)
- **OECD COICOP2018 has no CHN coverage** (`REF_AREA=CHN` → 0 docs).
- **IMF IFS on DB.nomics is ~1 year stale** (`M.CN.PCPI_PC_CP_A_PT` last obs
  2025-07 when probed 2026-07).
- **NBS on DB.nomics** publishes CPI only as "same-month-last-year = 100" indices
  (`NBS/M_A010101…`) with recent values NA — messy units (YoY% = value − 100) and
  a fetch-time transform the current adapter doesn't do.

### Leads to try
1. **IMF IFS *direct* API** (not the DB.nomics mirror) — the mirror lags, but the
   IMF SDMX/JSON endpoint may be current for `M.CN.PCPI_PC_CP_A_PT` (headline CPI
   YoY) and the PPI equivalent. If fresh, decide whether to add a direct-IMF path
   or accept the mirror lag.
2. **NBS direct** with a value−100 transform in a small helper — only if IFS
   fails; heavier lift.
3. **If nothing fresh exists**, formalize `CN_INFL1` as a *documented degraded
   indicator* in `forward_plan.md` Known Data Gaps (like the existing China
   entries), rather than leaving it silently frozen — and consider a plausibility
   band so the audit flags it if it drifts implausibly.

Effort: M (discovery). Lower urgency than P0 (China is one region; `EU_INFL1`
freeze affects the core euro-area inflation read).

---

## Deliverables
- **P0** and **P2** are source-repair PRs (verify the fresher series returns data
  live *before* repointing — a broken repoint is worse than a frozen one). In each
  PR body, paste the before/after composite tail proving it now MOVES, plus the
  chosen source (`source / series_id / last obs`).
- **P1** is one small CSV-only PR; list each `freshness_override_days` change with
  the source's real publication cadence as the justification, and note the
  `JPN_CPI_INDEX` drop.
- Validation gates for any PR touching the merge/composites: `python3 -m pytest
  test_tier_merge.py -q` green; a full keyed macro regen (`python3
  fetch_macro_economic.py` then `python3 compute_macro_market.py`); confirm the
  target composite moves month-to-month; re-run `python3 data_audit.py` (or read
  the next daily `data_audit.txt`) and confirm the EXPIRED/STALE count falls.
- **Do not commit the regenerated data CSVs** in a source PR — the daily
  `update_data` workflow owns them and will regenerate authoritatively on merge
  (same convention PRs #249/#250 followed). The regen is for validation; put the
  evidence in the PR body.

## Suggested sequence
P0 + P1 as **one focused PR** (fix the one genuinely-broken live indicator *and*
restore the audit's signal-to-noise so the next silent freeze is visible), then P2
separately. P0 is the highest-value item; P1 is what makes future freezes catchable
(and motivates §2.A **A9**, a systematic "is this composite actually moving?"
credibility check — the durable fix for this whole class of bug).
