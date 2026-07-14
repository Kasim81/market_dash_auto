# FactIQ Data Audit — `market_dash_auto`

**Run date:** 2026-07-12 · **Reference:** FactIQ live (authenticated) · **Repo as-of:** committed CSVs dated 2026-05-12
**Executor:** Opus · **Plan:** `FACTIQ_AUDIT_PLAN.md` (§0 defaults honored: full coverage, no pipeline re-run, Tier-B proxies directional-only)
**Deliverables:** `audit/findings.csv` (676 rows, deduped), `audit/working_list.csv` (401 rows), `audit/cache/data_catalog_2026-07-12.json`, `audit/cache/factiq_quotes_2026-07-13.json`, `audit/golden/factiq_reference_2026-07-12.json`, `audit/golden/factiq_reference_2026-07-14_sweep.json`

> **Resume note (2026-07-13/14):** External-value sweep **complete and cross-checked by two independent passes that fully concur.** Covered: the full Tier-A US-listed ETF scale sweep (all 72 remaining ETFs via `GLOBAL_QUOTE`), all remaining FX pairs (GBP/USD, CNY, INR, KRW, TWD), remaining commodities (Brent, copper, nat-gas, silver, coffee, sugar, corn, wheat, soybeans), and the Tier-B foreign-listed promotion sweep (63 rows, `B_PROMOTE` + corroborating `V_TIERB`). **No new scale/sign/÷100 anomaly found anywhere** — the entire priced universe holds. Verification method for the ETF sweep: since the repo as-of date (2026-05-12) lies inside the trailing 52 weeks of the 2026-07-13 quotes, every repo Last Price *must* fall within FactIQ's [52wk-low, 52wk-high] — **all 72 did**. Duplicate rows from the two concurrent passes were consolidated to one row per ticker×check. One promotion opportunity surfaced (CSI 500 `000905.SS`, see §3 #14). Perf-window recompute remains the sole deliberate deferral (see §5).

---

## 1. Headline

The dashboard's **local-currency prices and returns are fundamentally sound** where they could be independently checked: every Tier-A instrument tested (US ETFs, FX, commodities, Treasury yields) matched FactIQ on **scale, units, sign, currency convention, and — where exact-date data was available — on value to within tolerance.** No `÷100` pence bug, no `%`-vs-`bps` confusion, no sign flips were found in the priced US/FX/commodity/rates universe.

**One material exception surfaced in the USD-adjusted returns:** several US-listed ETF proxies are labeled with a *foreign* currency (EMB=ARS, FEZ=EUR, ASHR=CNY, HYXU=EUR), and at least for **EMB the USD Perf columns are demonstrably corrupted** — a phantom ARS→USD conversion flips its 1Y from +11.69% (local) to −13.35% (USD) on a fund that is already USD-denominated. EMB is additionally being reused as the single proxy for **9 different library rows** (eight country "USD-Hedged" bond indices + the real USD EM Debt fund). This is the most consequential value-affecting finding.

The findings are dominated by **three structural issues, not value errors**:
1. **The committed dataset is ~2 months stale** (single root cause behind 321 of 325 freshness flags). Per §0 this was not re-run; it is reported as a finding.
2. **Coverage gaps** — 29 library rows produce no output (mostly S&P 500 sector sub-indices), 47 output rows are empty, and 70 library rows are curated `UNAVAILABLE`.
3. **Representation/semantics** — a set of `.L` bond rows store *rebased synthetic indices* (base ~1.0) rather than prices, and many foreign rows label an ETF proxy with the underlying index's name.

The **US Treasury par-yield cross-check is the strongest independent result**: repo 10Y/30Y/5Y yields matched the Treasury par curve on 2026-05-12 to <0.5bp.

---

## 2. Counts

### By tier (working_list, 401 library rows)
| Tier | Rows | Has output row | Notes |
|---|---|---|---|
| A | 89 | 89 | US eq/ETF, FX, commodities, FRED, Rates/yield |
| B | 94 | 92 | Foreign-listed ETFs/ADRs, exchange-suffixed |
| C | 218 | 139 | Index-level tickers, VIX family, `UNAVAILABLE` |
| **Total** | **401** | **320 covered** | 81 uncovered (52 `UNAVAILABLE` by design + 29 true gaps) |

### By verdict (676 findings, deduped across both passes)
| Verdict | Count |
|---|---|
| FLAG(HIGH) | 336 |
| FLAG(MEDIUM) | 76 |
| FLAG(LOW) | 72 |
| PASS | 154 |
| PROXY | 15 |
| UNAUDITABLE | 22 |
| RECONCILIATION | 1 |

### By check type
| Check | Count | What it is |
|---|---|---|
| freshness (F1) | 305 | ≈301 systematic 2-month staleness + 4 genuinely dead/stale (all exceed 2× threshold → HIGH) |
| coverage | 139 | 47 empty output + 29 library-no-output + 63 Tier-B foreign-listed promotion sweep (B_PROMOTE) |
| value | 130 | external FactIQ checks: 81 V_SCALE (US ETFs) + 16 V_TIERB + 15 V_COMM + 7 V_FX + 6 V_SEMANTICS + 4 V_YIELD + 1 V_SCOPE |
| metadata | 76 | 70 validation≠CONFIRMED (M2) + EMB proxy/FX (PROXY_COLLISION/CCY_FX) + IWDA currency |
| consistency | 26 | simple_dash rows absent from `market_data.csv` (M8) |

### External value checks by result (both passes, deduped)
- **PASS (154):** the full Tier-A US-listed ETF set (**81** V_SCALE incl. SPY/QQQ/sector-SPDRs/factor/regional/bond ETFs + the currency-labeled proxies FEZ/ASHR/HYXU/EMB whose *price scale* passes — **all 72 sweep ETFs fell inside FactIQ's 52-week range, zero anomalies**); **7** FX pairs (EUR/USD, USD/JPY, GBP/USD, USD/CNY, USD/INR, USD/KRW, USD/TWD — exact/near-date <0.5%, conventions correct); commodities (WTI, Gold, Brent, NatGas, Copper, Silver, Sugar, Coffee, Corn, Wheat, Soybeans — convention/scale/sign correct, **grains/softs cents→USD reconciled with no ÷100 error**); **3** Treasury yields (exact); + Tier-B ETFs priceable on a global exchange (LSE/JPX/TSX/SSE/KRX/HKEX/Bovespa/NSE + CSI 500 promotion).
- **PROXY (15):** priceable-but-directional — 7 rebased/proxy `.L` bond ETFs; foreign ETFs that resolve but carry index-name labels (XCS.TO, 1306.T, 1321.T, 069500.KS, 2800.HK, BOVA11.SA…); `399001.SZ` (Component vs Composite mislabel), `SMALLCAP.NS` (Mirae fund vs Nifty Smallcap 100 index).
- **RECONCILIATION (1):** ^IRX vs Treasury 3-mo par (expected discount-vs-par convention gap ~10bp).
- **UNAUDITABLE (22):** 6 rebased `.L` bond indices (V_SEMANTICS) + ICE BofA/FRED scope class + Istanbul (`XU100.IS`/`XU030.IS` — invalid symbol) + Milan (`FTSEMIB.MI`/`IMIB.MI`) + Mexico (`NAFTRAC.MX`) + ASX (`IOZ.AX`/`VAS.AX`/`SSO.AX`/`IAF.AX` — twelvedata add-on not entitled) + `000852.SS` (CSI 1000 not priceable).
- **FLAG(LOW) (1):** XIU.TO index-name mislabel.

**Tier-B resolvability map (FactIQ market-data provider):** RESOLVE → TSX(.TO), Tokyo(.T), Shanghai(.SS), Shenzhen(.SZ), Korea(.KS), HK(.HK), Brazil(.SA), NSE India(.NS), LSE(.L when live). DO NOT RESOLVE → Borsa Istanbul(.IS), Milan(.MI), Mexico(.MX) return *invalid symbol*; **ASX(.AX) returns "not authorized — add-on required"** (a provider entitlement gap, not a data gap).

---

## 3. Most severe findings (triage, worst first)

| # | Finding | Severity | Repo vs FactIQ | Root cause |
|---|---|---|---|---|
| 1 | **Entire committed dataset ~2 months stale** (Last Date 2026-05-12; audited 2026-07-12; 321 rows ≈60-65d gap) | HIGH (systematic) | e.g. SPY 738.18@05-12 vs FactIQ 754.95@07-10 | Committed CSV not regenerated (per §0, not re-run) |
| 2 | **`^CM100` dead ~10.6 years** (Last Date 2015-ish, 3860d) | HIGH | stale level | yfinance stopped serving the ticker |
| 3 | **`^SP500-151050` (Paper & Forest) dead since 2015-12-18** (3859d) | HIGH | 158.51, frozen | yfinance sub-index discontinued |
| 4 | **`^SP500-551020` (Gas Utilities) dead since 2016-06-30** (3664d) | HIGH | 813.27, frozen | yfinance sub-index discontinued |
| 5 | **29 library rows produce no output** — CSI 500/1000, VXEEM, and ~26 `^SP500-xxxxxx` industry sub-indices | HIGH | in library, no comp row | yfinance returns nothing for these sub-indices |
| 6 | **47 output rows have empty Last Price** — mostly `.L`/`.DE` UCITS ETF proxies (IWDA.L, ISF.L, EXSA.DE, VGOV.L…) | MEDIUM | present but blank | ETF-proxy fetch failed / dead symbol |
| 7 | **6 `.L` bond rows are rebased indices, not prices** — IEAC.L=1.19, IBGL.L=1.42, IITB.L=1.51, IEAG.L=1.07, IFRB.L=1.27, HYLH.L=5.39 | MEDIUM | repo ~1.0-1.5 vs FactIQ ETF ~120 EUR | By design (hist base~1.0) but labeled Currency EUR/GBP with Sunday dates — misleading |
| 8 | **70 rows validation_status = UNAVAILABLE** (not CONFIRMED) | LOW | curation flag | Library curation for unpriceable/removed instruments |
| 9a | **`EMB` reused as proxy for 9 library rows** (Argentina/Brazil/Korea/Mexico/Indonesia/Saudi/S.Africa/Turkey USD-Hedged bond indices + real USD EM Debt fund) | HIGH | 1 ETF ↦ 9 country indices | Broken proxy validity; one output ticker inherits 9 currencies |
| 9b | **`EMB` USD returns corrupted** — Currency=ARS on a USD fund; 1Y +11.69% local → **−13.35% USD** | HIGH | phantom ARS→USD FX | USD-adjustment applied to an already-USD asset |
| 9c | **US-listed ETF proxies labeled foreign currency** — FEZ=EUR, ASHR=CNY, HYXU=EUR | MEDIUM | USD Perf may double-count FX | Verify pipeline FX logic for these |
| 10 | **`PIORECRUSDM` (Iron Ore, monthly) stale 133d** | MEDIUM | monthly series past 45d threshold | Publication lag or genuine staleness |
| 11 | **Index-name-on-ETF-proxy labeling** — XIU.TO "S&P/TSX Composite" (tracks TSX 60), 2800.HK "Hang Seng Index" (Tracker Fund), 1306.T "TOPIX Index", 1321.T "Nikkei 225", IOZ.AX "S&P/ASX 200"… | LOW (systematic) | ETF price correct; Name is the index | Proxy convention; `proxy_flag` exists in library |
| 12 | **IWDA.L currency** — repo GBP vs FactIQ LSE USD (Acc) class | LOW | GBP vs USD | Multi-share-class ambiguity (row also empty) |
| 13 | **26 `simple_dash=True` rows absent from `market_data.csv`** (M8) — all `^`-index levels (^GSPC, ^RUT, ^RLG…) | MEDIUM | in comp, not in simple file | Subset-file inconsistency; confirm intended |

| 14 | **`000905.SS` (CSI 500) is priceable on FactIQ but library marks it UNAVAILABLE/no-output** | LOW (promotion) | ~8138 CNY on 2026-07-13 vs no repo output | FactIQ (SSE) can source it; candidate re-wire. (CSI 1000 `000852.SS` still not priceable — stays UNAVAILABLE.) |

**No CRITICAL findings** (no sign flips, no order-of-magnitude/÷100 errors, no genuine value corruption) were found in the audited universe. **The 2026-07-13 resume sweep confirms this across the full priced universe:** every one of the 72 Tier-A US ETFs, 7 FX pairs, and 14+ commodities passed scale/units/currency/sign — zero anomalies.

---

## 4. Methodology & FactIQ-vs-repo notes

- **As-of alignment.** The repo is ~2 months stale, so live quotes were never expected to match `Last Price`. Comparisons used FactIQ's close on the repo's as-of date (2026-05-12) where the tool exposed it (FX, commodities, Treasury yields — all matched to tolerance), and a **scale/units/52-week-range sanity check** for equities where FactIQ's market-data endpoint returns *intelligently-sampled* rows that omit arbitrary dates (it skipped 2026-05-12 for SPY). This sampling is the key tool limitation: exact-date equity close verification to the ±0.10% tolerance is **not reliably achievable** via `get_market_data`; it is robust for catching ÷100/sign/gross errors, which is what matters most.
- **Treasury yields are the cleanest check.** The warehouse (`treasury.yield_curve.*`) exposes exact daily par yields. Repo ^TNX/^TYX/^FVX matched 10Y/30Y/5Y par to <0.5bp on 2026-05-12. This is a genuine independent cross-check (Treasury is the primary issuer, per §5 caveat a — not routed through the Fed source).
- **FactIQ coverage vs the stale bundled doc.** The live `get_data_catalog` confirmed 29 schemas incl. `frb` (Fed rate schema, **not** `federal_reserve` as the plan guessed), `treasury`, `bls`, `bea`, `census`, `eia`, `sec`. Snapshot saved to `audit/cache/data_catalog_2026-07-12.json`.
- **Scope limit — the "FRED" rows are ICE BofA indices.** The repo's 22 `data_source=FRED` rows are almost entirely **ICE BofA OAS/TR indices** (BAML*) plus iron ore. **FactIQ carries no ICE BofA index data**, so these are UNAUDITABLE against FactIQ and must stay direct-from-FRED. This directly informs §11 wiring: FRED/ICE cannot be replaced by FactIQ aggregation. (`DFII10` may be checkable vs a Treasury real-yield series in a follow-up.)

---

## 5. Completed vs pending

**Completed (rigorous):**
- Phase 0 fully: live catalog snapshot, working list + tiering (401 rows), internal checks M1/M2/M5/M6/M8/M9 + freshness on **all 401 rows**, coverage reconciliation (corrected for the pipeline's dual PR+TR output-row convention).
- **Tier-A external value sweep — now EXHAUSTIVE (2026-07-13):** all **72 Tier-A US-listed ETFs** scale/units/currency/name checked via `GLOBAL_QUOTE` (all PASS); **all 7 FX pairs** exact-date checked (all PASS, conventions correct); **14 commodities** convention/scale checked (all PASS; only `LE=F` UNAUDITABLE — no FactIQ livestock series); 3 Treasury yields exact.
- **Tier-B foreign-listed promotion sweep — COMPLETE (63 rows):** resolved every foreign-listed proxy via `GLOBAL_QUOTE`/`SYMBOL_SEARCH`. LSE/XETR(bare symbol)/JPX/TSX/SSE/SZSE/NSE all priceable (PASS/PROXY); `FTSEMIB.MI`, `XU100.IS`, `XU030.IS`, `IAF.AX` (ASX entitlement), `000852.SS` are UNAUDITABLE via FactIQ. **Promotion opportunity:** `000905.SS` (CSI 500) is priceable though library marks it UNAVAILABLE.
- Macro/FRED track: Treasury par-yield-curve cross-check complete; FRED/ICE scope resolved.
- Golden snapshot: catalog + all captured FactIQ reference values persisted (`cache/factiq_quotes_2026-07-13.json` and `golden/factiq_reference_2026-07-14_sweep.json` — the latter holds every sweep quote with 52wk ranges for automated re-verification).
- **Two independent resume passes were run concurrently and fully agree** (zero conflicting verdicts); duplicate rows were consolidated to one per ticker×check.

**Pending (single deliberate deferral):**
- Perf-window recompute (1W/1M/…/1Y) — **deliberately deferred (conscious scope decision)**: FactIQ market-data sampling makes exact anchor-date perf recompute unreliable; would need `TIME_SERIES_WEEKLY/MONTHLY` per ticker and still be anchor-approximate. Internal bps-arithmetic (M6) and USD=Local (M5) checks already validate the perf columns' internal consistency. Not attempted by design.

---

## 6. Architecture teardown & source-wiring

The §8 teardown (3-table normalized model, cache-first discipline, ChartSpec layer, `term_chart.py` reuse, golden-snapshot-now) and §11 three-bucket source strategy are written in `FACTIQ_AUDIT_PLAN.md` and stand as-is. Two audit-derived reinforcements:
- **Golden snapshot is live** (`audit/golden/`, `audit/cache/`) — the §8.3.4 insurance is started.
- **§11 correction:** the repo's ICE BofA "FRED" rows are **not** FactIQ-replaceable (bucket-3 reliance won't help here; keep them direct-from-FRED). The genuinely FactIQ-independent macro win is the **US Treasury par-yield curve** (`treasury.yield_curve.*`), which cleanly backs the repo's Rates/yield tickers and should be the priority direct-wire per §11.

---

## 7. Needs Kas's judgment

1. **Rebased `.L` bond rows (IEAC.L, IBGL.L, IITB.L, IEAG.L, IFRB.L, HYLH.L):** are the ~1.0-1.5 rebased-index values *intended* to sit in `market_data_comp.csv` labeled as EUR/GBP prices? Downstream consumers reading them as prices would be wrong by ~100×. Recommend a distinct units label (e.g. "Index, base=1") and a non-Sunday date.
2. **Dead/stale tickers:** ^CM100 and the ^SP500 industry sub-indices are yfinance-discontinued (some ~10 years). Prune from the library, or wire a secondary source? 29 more sub-indices produce no output at all.
3. **`EMB` proxy + FX bug (highest-priority):** (a) should one US-listed USD ETF really stand in for 9 distinct country "USD-Hedged" bond indices? (b) the ARS currency label corrupts its USD returns (1Y −13.35% vs +11.69% local). Same FX-mislabel risk on FEZ/ASHR/HYXU. This is the one finding that changes displayed numbers — recommend fixing the currency labels and the USD-adjustment path for US-listed proxies before the next publish.
