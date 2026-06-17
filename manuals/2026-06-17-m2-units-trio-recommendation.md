# M2/M3 money-supply units trio — recommendation memo (2026-06-17)

**READ-ONLY recommendation.** No CSVs or modules were modified by this memo.
It resolves the deferred judgment call in the handoff backlog
("M2 / JPN_M2 / EZ_M3 units trio: relabel-to-level vs source a real YoY
series") and follows up the WARNING rows added to
`manuals/2026-06-15-label-vs-data-audit.md` on 2026-06-17.

## The defect

Three FRED OECD-MEI mirror rows declare units **"Percent Change YoY"** but the
underlying FRED series serve **levels**, not growth rates. Confirmed both from
the 2026-06-17 credentialed FRED probe (audit) and from the values now sitting
in `data/macro_economic.csv`:

| col / series_id | library units (claimed) | FRED actual units | served value (level) | FRED `observation_end` | in named hist column? |
|---|---|---|---|---|---|
| `CHN_M2` — `MYAGM2CNM189N` | Percent Change YoY | National Currency | 1.935e14 (≈ ¥193.5 tn) | **2019-08** (frozen ~7y) | **yes — active** (`col=CHN_M2`) |
| (none) `MYAGM2JPM189S` ("Japan M2 … YoY") | Percent Change YoY | National Currency | 9.632e14 (≈ ¥963 tn) | **2017-02** (frozen ~9y) | no (`col` empty; "VERIFY … on first fetch") |
| (none) `MABMM301EZM189S` ("Eurozone M3 … YoY") | Percent Change YoY | Euro | 1.603e13 (≈ €16.0 tn) | **2023-11** (frozen ~2.5y) | no (`col` empty; "VERIFY … on first fetch") |

Note `M2SL` (US M2, `Billions USD (SA)`) is **not** part of this trio — it is a
level honestly labelled as a level, and is correct.

Two things are wrong with each of the three, not one:

1. **Label lie** — units say YoY %, the data is a stock level (off by ~13
   orders of magnitude from any % reading).
2. **Wrong transform for the column's purpose** — every one of these rows is
   named "… Money Supply YoY", sits in category `Growth / Money Supply`, and the
   notes describe growth-based analytics ("M1-M2 spread … liquidity gauge",
   "YoY growth leads nominal GDP"). The analytical intent is unambiguously a
   **YoY growth rate**, so relabelling the row to "level" would keep a series
   that is the wrong transform for how the dashboard uses it.

On top of that, **all three FRED series are frozen/discontinued** (CHN 2019-08,
JPN 2017-02, EZ 2023-11). So "just relabel to level" preserves a row that is
*both* the wrong transform *and* dead.

## Recommendation — per series (not a single uniform answer)

### EZ_M3 → **source the live YoY series (ECB).** High confidence.

ECB publishes the euro-area M3 **annual growth rate** directly, keyless, on the
ECB Data Portal SDMX — and ECB is already a wired tier-1 source in this repo
(`data/macro_library_ecb.csv`, `sources/ecb.py`). Verified live 2026-06-17:

- Series key: `BSI/M.U2.Y.V.M30.X.I.U2.2300.Z01.A`
  (Monthly / Euro area / **annual growth rate** of M3).
- Latest obs: **2.74% @ 2026-04** (prior 3.23% @ 2026-03) — a real YoY %,
  fresh, exactly the transform the column wants.

Action (a later editing batch, not this memo): add an ECB library row for the
`EZ_M3` column pointing at that key, units "Percent Change YoY"; the ECB row
will win the freshness merge over the frozen FRED mirror (same pattern as
`EA_DEPOSIT_RATE`/`GBR_CPI`). Keep the FRED row as a backfill or drop it.
**Do not relabel-to-level** — the live YoY exists and is trivially sourced.

### JPN_M2 → **source the live YoY series (BoJ).** Medium confidence; small discovery step.

BoJ publishes Money Stock M2 (average amounts outstanding + YoY) on the BoJ
Time-Series Data Search, which the existing generic `sources/boj.py` fetcher
already serves by series code (it carries the policy rate, PPI/SPPI, and the
seven Tankan rows). The exact Money-Stock series code should be **pinned via
`getMetadata`** before wiring — the same disciplined step already used for the
Tankan rows ("Pinned from CO-db getMetadata on 2026-06-11"). I did not invent a
code here. The frozen FRED level (2017-02) is not a viable fallback.

Action (later batch): discover the BoJ M2 YoY code via getMetadata, add a BoJ
library row for a `JPN_M2` column, units "Percent Change YoY". Effort: S–M
(discovery only; no module change).

### CHN_M2 → **the hard one; relabel honestly now, source later if a free live YoY surfaces.** 

This is the genuinely-blocked member and, critically, **the only one of the
three that is live in the dashboard** (`col=CHN_M2`), so it is actively serving a
frozen-2019 *level* under a "Percent Change YoY" label today. China money/credit
has no clean free programmatic live source — consistent with the existing
documented accepted gaps for `CHN_IND_PROD`, `CHN_CPI`, `CHN_PPI`
(forward_plan §1 Known Data Gaps; NBS/PBoC have no free API).

Two-part recommendation:
- **Immediate, low-risk:** stop the label lie. Either relabel `CHN_M2` units to
  the level it actually serves (e.g. "RMB (level), NSA") **or** mark the row
  dead/accepted-gap — whichever the maintainer prefers — but it should not keep
  claiming "Percent Change YoY" while serving a frozen level. This is the most
  harmful of the three precisely because it is the one users see.
- **Investigate (S):** probe DB.nomics for a live China M2 YoY mirror (IMF/IFS
  or BIS provider paths the repo already uses elsewhere) before accepting the
  gap as permanent. If a fresh free YoY exists, prefer sourcing it over the
  relabel.

## Summary

| series | verdict | why |
|---|---|---|
| **EZ_M3** | **Source live YoY (ECB BSI, verified 2.74% @ 2026-04)** | live keyless tier-1 source already wired; YoY is the intended transform |
| **JPN_M2** | **Source live YoY (BoJ Money Stock, code TBD via getMetadata)** | existing BoJ fetcher; small discovery step; FRED level dead since 2017 |
| **CHN_M2** | **Relabel honestly now + investigate DB.nomics; accept-gap if none** | no free live China M2 YoY; it is the only one active in the dashboard |

The overarching judgment: **do not blanket-relabel the trio to "level."** For
EZ_M3 and JPN_M2 the correct YoY series exist on sources the repo already trusts;
relabelling them would entrench the wrong transform. Relabel-to-(honest-units) is
the right move **only** for CHN_M2, and only as the interim stop-the-lie step
until the sourcing question is settled.

All three remediations are library-CSV edits (no module changes) and should be
verified by a regen run; none was made here.
