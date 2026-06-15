# Source-Tier & Freshness-Cadence Audit — 2026-06-15

Full-population audit of every economic indicator column in
`data/macro_economic_hist.csv` against two dimensions: **actual freshness cadence**
(empirical, not the library label) and **primary-source alignment** (tier in the
source hierarchy). Triggered by the discovery that `JP_INFL1` was running on a FRED
OECD-MEI mirror (`JPNCPIALLMINMEI`) that updates annually while presenting as monthly
through weekly-spine forward-fill.

Scope: research only. No source files, CSVs, or modules were edited.

---

## Executive summary

**Total indicators audited:** 263 data columns (all columns below the 14 metadata
prefix rows in `macro_economic_hist.csv`; the `Date` column is excluded).

**Count by current source tier**

| Tier | Definition | Sources in use | Columns |
|------|------------|----------------|--------:|
| Tier 1 | National stat office / central bank direct, or primary academic dataset | BLS, ONS, INSEE, e-Stat, BoE, BoC, BoJ, Bundesbank, StatCan, ABS, NYFed, LBMA, Shiller, KenFrench, **JST (39 historical anchors)** | 101 |
| Tier 2 | Regional aggregator direct | OECD SDMX (26), ECB (3) | 29 |
| Tier 3 | Cross-source mirror w/ curation | DB.nomics (14), IMF (12), World Bank (7) | 33 |
| Tier 4 | FRED (third-party aggregator; many slow OECD-MEI mirrors) | FRED | 100 |

*Of the 101 Tier-1 columns, 39 are JST historical anchors (intentionally annual,
`is_historical_anchor=True`, `freshness_override_days=730`); 62 are live Tier-1 feeds.*

**Flagged counts**

| Class | Count | Notes |
|-------|------:|-------|
| **Fake-cadence (silently annual / frozen mirror presented as monthly)** | **7** | 5 of 7 feed a live Phase-E composite |
| **Tier-downgrade (Tier-3/4 in use while Tier-1/2 is wired & available)** | **2 strong + 4 discovery-needed** | GBR_CPI→ONS and JPN_IND_PROD→e-Stat are the high-confidence pair |
| **Accepted gaps reaffirmed** | **7** | China M2/IndProd/core-CPI/10Y, JP 2Y, UK claimant count, UK LMS lag |

**Biggest single offender source:** **FRED (Tier 4).** All 7 fake-cadence columns
are FRED OECD-MEI mirrors except `JPN_MACH_ORDERS` (an e-Stat slice problem) — i.e.
**6 of 7** trace to FRED. FRED is also the single largest source (100 of 263 columns),
and every frozen-mirror EXPIRED row in the pipeline's own staleness gate that is *not*
an event-driven policy rate is a FRED non-US series.

**Cross-check with the pipeline's own staleness gate** (`pipeline.log` Section C, run
2026-06-15): `FRESH 179 · STALE 24 · EXPIRED 21 · ANCHORS 39` = 263. This independent
gate corroborates the empirical findings below; the 6 FRED frozen mirrors all appear
in its EXPIRED bucket ("age beyond 2× tolerance — series almost certainly dead").

---

## Fake-cadence violations (HIGH priority)

A column is a fake-cadence violation when the library frequency is **Monthly** but the
series has produced **no new value-change in many multiples of the stated cadence** —
the weekly spine forward-fills the last print so the column *looks* like fresh monthly
data. Two detection signals converge here: (a) the empirical median value-change gap
(`JPN_MACH_ORDERS` is structurally annual at 364d), and (b) frozen-mirror staleness —
a series that updated monthly historically then stopped, which the median-gap heuristic
alone misses but the days-since-last-change check catches.

Sorted by impact — Phase-E composite inputs first.

| # | Col | Lib freq | Empirical / effective cadence | Last real value-change | Age | Current source (tier) | Feeds (Phase E) | Recommended swap |
|---|-----|----------|-------------------------------|------------------------|----:|-----------------------|-----------------|------------------|
| 1 | `GBR_CPI` | Monthly | Frozen (no change in 15 mo) | 2025-03-07 | 465d | FRED `GBRCPIALLMINMEI` (T4) | **UK_INFL1** | Re-point UK_INFL1 to **`GBR_CPI_YOY`** — already live from ONS (T1) in the same file |
| 2 | `CHN_CPI` | Monthly | Frozen (no change in 14 mo) | 2025-04-04 | 437d | FRED `CHNCPIALLMINMEI` (T4) | **CN_INFL1** | Probe IMF IFS / DB.nomics CN headline CPI (T3); else reaffirm accepted gap |
| 3 | `CHN_PPI` | Monthly | Frozen (no change in 3.5 yr) | 2022-12-02 | 1291d | FRED `CHNPIEATI01GYM` (T4) | **CN_INFL1** | Probe IMF IFS / DB.nomics CN PPI (T3); else reaffirm accepted gap |
| 4 | `JPN_IND_PROD` | Monthly | Frozen (no change in 27 mo) | 2024-03-01 | 836d | FRED `JPNPROINDMISMEI` (T4) | **JP_NOWCAST1** | Activate the wired e-Stat path (`statsDataId 0003446463`, METI IIP, T1) |
| 5 | `JPN_MACH_ORDERS` | Monthly | **Annual** (median gap 364d) | 2025-10-03 | 255d | e-Stat `0003355224` (T1) | **JP_NOWCAST1** | Within-source fix: add `cdCatNN` filter to pin the monthly SA private-ex-volatile slice (currently resolving an annual table) |
| 6 | `CHN_M2` | Monthly | Frozen (no change in 6.9 yr) | 2019-08-02 | 2509d | FRED `MYAGM2CNM189N` (T4) | — | **No fix** → accepted gap (see below) |
| 7 | `CHN_IND_PROD` | Monthly | Frozen (no change in 2.6 yr) | 2023-11-03 | 955d | FRED `CHNPRINTO01IXPYM` (T4) | — | **No fix** → accepted gap (see below) |

Notes:

- **#1 `GBR_CPI` is the cleanest and highest-value fix.** This is the exact analogue
  of the `JP_INFL1` discovery: a frozen FRED OECD-MEI CPI mirror feeding a live regime
  composite while a fresh Tier-1 ONS replacement (`GBR_CPI_YOY`, last change 2026-04-03)
  already sits in the same CSV. `UK_INFL1` currently averages `GBR_CPI` (frozen) with
  `GBR_CORE_CPI_YOY` (live ONS) — the headline leg is stale while the core leg is fresh.
- **#4 `JPN_IND_PROD`**: the e-Stat module *and* library row are already wired
  (`sources/estat.py`, `macro_library_estat.csv` row `0003446463`), but the live column
  is still the dead FRED mirror. `pipeline.log` shows both `[FRED/JPN_IND_PROD]` and
  `[e-Stat/JPN_IND_PROD]` fetch attempts; the FRED value is winning and e-Stat is not
  populating — consistent with the `ESTAT_APP_ID` credential not being present in the
  runtime (the sibling provisional e-Stat IDs error `STATUS=300 … does not exist`).
- **#5 `JPN_MACH_ORDERS`** is the only column the strict median-gap heuristic flags on
  its own: 20 value-changes at a 364-day median. The library note already anticipates
  this ("Still needs `cdCatNN` filter to pin the private-ex-volatile SA slice"). This is
  a within-source correction, not a tier change.
- **#2 / #3 (China CPI & PPI)** feed `CN_INFL1` and are badly stale (PPI for 3.5 years),
  but China headline inflation has no currently-wired free Tier-1/2 path. IMF IFS carries
  CN monthly CPI series (per `forward_plan` §3.1.3) and is worth a probe for the headline;
  the core slice is a confirmed accepted gap. Treat as best-effort upgrade, not a clean swap.

---

## Tier-downgrade candidates (MEDIUM priority)

Indicators on a Tier-3/4 source where a more authoritative Tier-1/2 source is wired and
available. Restricted to evidence-backed cases (a `sources/<x>.py` module plus a library
row or live column proving the capability). Bulk US-on-FRED series are deliberately *not*
listed — see the note at the end of this section.

| Col | Current source (tier) | Recommended source (tier) | Wired-and-available evidence | Cost estimate |
|-----|-----------------------|---------------------------|------------------------------|---------------|
| `GBR_CPI` | FRED `GBRCPIALLMINMEI` (T4) | **ONS** (T1) | `sources/ons.py` wired; `GBR_CPI_YOY` + `GBR_CORE_CPI_YOY` already live in hist | **CSV/formula row move only** — re-point `UK_INFL1` to `GBR_CPI_YOY` |
| `JPN_IND_PROD` | FRED `JPNPROINDMISMEI` (T4) | **e-Stat** (T1) | `sources/estat.py` wired; `macro_library_estat.csv` row `0003446463` (METI IIP) present | Credential + priority — module wired, blocked on `ESTAT_APP_ID` in runtime |
| `JPN_MACH_ORDERS` | e-Stat (T1, wrong slice) | e-Stat (T1, correct slice) | Same module/row; needs slice filter | Within-source `cdCatNN` discovery (1 fetch) |
| `ITA_BTP_10Y` | FRED `IRLTLT01ITM156N` (T4) | Banca d'Italia / ECB SDW (T1/T2) | OECD-MEI-shaped monthly mirror, STALE 101d | **New source_id discovery** — ECB YC carries the AAA curve only, not BTP-specific |
| `NLD_DSL_10Y` | FRED `IRLTLT01NLM156N` (T4) | ECB SDW (T2) | OECD-MEI-shaped monthly mirror, STALE 101d | **New source_id discovery** (ECB country-specific 10Y) |
| `CHN_CON_CONF` | FRED `CSCICP02CNM460S` (T4) | OECD SDMX direct (T2) | `sources/oecd.py` wired; OECD-MEI consumer-confidence series | **New oecd_key discovery** (lower confidence — OECD MEI may be the only path) |

`ITA_BTP_10Y`, `NLD_DSL_10Y`, and `IND_GOVT_10Y` share the FRED `IRLTLT01*M156N`
monthly-yield family — all three are STALE at ~101d (last change 2026-03-06). They are
the next cluster worth a discovery pass once the two strong swaps above land.

**Why the rest of FRED's 100 columns are not flagged:** 51 are US series (PAYEMS,
INDPRO, UNEMPLOY, PCEPILFE, the Treasury/breakeven/credit-spread family, etc.) and 14
are GLOBAL commodity/spread series. For these, FRED mirrors the Tier-1 source (BLS,
Census, BEA, the Fed's own H.15) **at native cadence with same-day latency** — there is
no freshness loss, so a swap to `sources/bls.py` buys accuracy parity at non-trivial
cost. The primary-source principle bites only where the FRED mirror is *degraded*
(the slow OECD-MEI international mirrors), which is exactly the non-US set captured above.

---

## Confirmed OK (LOW priority — count + summary)

The audit ran on the **full 263-column population**, not a sample. Beyond the flagged
rows, the live Tier-1/Tier-2 estate is behaving as expected:

- **179 columns FRESH** in the pipeline's value-change gate (age within 1× tolerance).
- **62 live Tier-1 columns** (ONS, BoJ, BoE, BoC, Bundesbank, BLS, ABS, StatCan, INSEE,
  NYFed, LBMA, Shiller, KenFrench) plus **29 Tier-2** (OECD SDMX, ECB) — the great
  majority FRESH. The handful in the STALE bucket (e.g. `GBR_GDP_REAL`, `GBR_EMP_RATE`,
  the BoJ Tankan quarterlies, `CAN_GDP_MONTHLY`) are **publication-lag-honest**: their
  `freshness_override_days` are set to the real release cadence (90–180d), so they age
  past the base tolerance without being stale in substance. These are correct, not bugs.
- **39 JST historical anchors** correctly excluded from frequency-based staleness
  (`is_historical_anchor=True`, `next_expected_release` tracked); 0 overdue.
- **Event-driven rates** (`CHN_POLICY_RATE`, `EA_DEPOSIT_RATE`, `CAN_POLICY_RATE`,
  `JPN_POLICY_RATE`, `GBR_BANK_RATE`) show long gaps between value-changes by nature —
  the central bank simply hasn't moved — and are **not** fake-cadence. Several were
  themselves the *successful* swaps off frozen FRED mirrors (e.g. `EA_DEPOSIT_RATE` is
  now ECB-direct, `GBR_BANK_RATE` is now BoE IUDBEDR, `CHN_POLICY_RATE` is now IMF IFS).

Net: the audit confirms 7 of the 9 historical "stale FRED forcing-function rows"
(`forward_plan` §284) have genuinely been resolved onto fresher tiers; only the two
documented China accepted-gaps remain on dead FRED, plus the newly-surfaced `GBR_CPI`
and the e-Stat-credential-blocked `JPN_IND_PROD`.

---

## Accepted gaps reaffirmed

These were confirmed stale/inferior by the audit but have a `forward_plan`-documented
rationale and no better wired source today:

1. **`CHN_M2`** — FRED `MYAGM2CNM189N` frozen since 2019-08. PBoC publishes only bulk
   Excel/PDF; no free programmatic source (`forward_plan` §284, `source_fallbacks.csv`).
2. **`CHN_IND_PROD`** — FRED `CHNPRINTO01IXPYM` frozen since 2023-11. NBS undocumented
   + IP-restricted; no free source (`forward_plan` §284).
3. **China core CPI** (`CN_INFL1` core leg) — no free aggregator-mirrored ex-food-energy
   slice (OECD COICOP2018 returns 0 docs for `REF_AREA=CHN`; NBS tree has no such cut).
   `CN_INFL1` stays a headline-CPI + PPI blend (`forward_plan` §3.1.3, line ~466).
4. **China 10Y government bond** (`CHN_GOVT_10Y`) — no free direct yield series; proxied
   by the `CBON` ETF distribution yield in Stage F. The dangling `_get_col` reference in
   `_calc_AS_CN_R1` is deliberate and allow-listed (`forward_plan` §275, §3.1.6).
5. **JP 2Y JGB yield** — BoJ confirmed not to publish JGB benchmark yields; IMF IFS path
   frozen at 2017-05; only route is MoF Japan direct, deferred (`forward_plan` §3.1.5, §507).
6. **UK claimant count** (`BCJD`/`BCJE`) — canonical CDIDs frozen at 2017-01 after the
   Universal-Credit methodology migration; ONS path not surfacing UK-aggregate series
   (`forward_plan` §425, §3.1 Stage C).
7. **UK LMS labour series** (`GBR_EMP_RATE`, `GBR_UNEMPLOYMENT`, `GBR_AWE_REGPAY_YOY`) —
   surfaced at ~quarterly cadence with ~45-day lag; `freshness_override_days` bumped to
   150d as honest signal. OECD/Eurostat/IMF/ILO alternatives are derivative ONS data,
   as-slow-or-slower (`forward_plan` §326). Not a tier problem — a cadence reality.

---

## Methodology footnote

**Cadence detection (reproducibility).** For each column below the 14 metadata prefix
rows, load the series, drop NaN, and find rows where the value actually *changes*
(`s != s.shift(1)`); take the **median gap in days between consecutive value-changes**
and classify (≤7d Daily/Weekly · 25–35d Monthly · 80–100d Quarterly · 350–380d Annual ·
else irregular). This is intentionally computed from value-changes, not row spacing,
because the weekly-Friday spine forward-fills every series — row gaps are always 7 days
regardless of the true release cadence. **One known blind spot:** the median-gap method
is dominated by history, so a series that printed monthly for years and then *froze*
still reads "Monthly." It is therefore paired with a **days-since-last-value-change**
check (vs the run date 2026-06-15), which catches frozen mirrors; `is_historical_anchor`
and `freshness_override_days ≥ 365` are honored as legitimate-annual exemptions. Findings
were cross-validated against the pipeline's own Section-C value-change staleness gate in
`pipeline.log` (EXPIRED = age beyond 2× tolerance). A future re-run only needs
`macro_economic_hist.csv` plus the per-source `macro_library_*.csv` override/anchor
columns.
