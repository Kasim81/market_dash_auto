# Indicator Pipeline Review — 2026-04-23

Baseline: `data/reference_indicators.csv` (206 indicators across US / UK / Eurozone / Japan / China / Global).
Purpose: single view of what is integrated, what is broken, and what remains outstanding — with concrete sourcing proposals for every gap.

## Executive Summary

| Status | Count | Share | Notes |
|---|---:|---:|---|
| **Full** (production) | 44 | 21% | All 10 previously-broken FMP indicators now resolved (8 restored with free proxies, 2 proprietary — see §1) |
| **Partial** (proxy / adjacent series) | 26 | 13% | Includes 4 new PMI proxies (EU_PMI1/2, UK_PMI1, CN_PMI1) + GL_PMI1 composite |
| **None** (outstanding) | 136 | 66% | Prioritised by source type in §4 |
| **Effective production** | **44** | 21% | All Full indicators now live (FMP rebuild complete) |

### Health by Region

| Region | Total | Full | Partial | None | Proprietary† | Effective Full |
|---|---:|---:|---:|---:|---:|---:|
| US | 37 | 19 | 2 | 16 | 0 | 19 |
| UK | 36 | 2 | 3 | 31 | 0 | 2 |
| Eurozone | 36 | 9 | 9 | 18 | 1 | 9 |
| Japan | 35 | 2 | 4 | 29 | 1 | 2 |
| China | 36 | 3 | 5 | 28 | 1 | 3 |
| Global | 26 | 9 | 3 | 14 | 0 | 9 |
| **Total** | **206** | **44** | **26** | **136** | **3** | **44** |

† "Proprietary" = no free monthly source exists. DE_ZEW1 (ZEW Mannheim), JP_PMI1 (S&P Global), CN_PMI2 (S&P Global/Caixin). These return `Insufficient Data` but are covered by adjacent free indicators in the same region.

The US and Global cuts are in the strongest shape. FMP rebuild is complete — all restorable indicators now use free proxies. The 3 remaining proprietary indicators have no free monthly equivalent anywhere (exhaustively verified across FRED, DB.nomics, OECD, ECB, Bundesbank, BoJ, NBS, Eurostat).

---

## 1. FMP Calendar Rebuild — RESOLVED

FMP's free tier no longer includes the economic calendar (HTTP 402/403 — verified 2026-04-22). All 12 Phase E indicators that depended on FMP have been resolved: 8 restored with free proxy sources, 3 classified as proprietary (no free monthly source exists anywhere), 1 auto-rebuilds from components.

| Phase E ID | Reference row | Resolution | Status |
|---|---|---|---|
| **US_PMI1** (ISM Mfg) | not in ref | DB.nomics `ISM/pmi/pm` | **LIVE** (commit `1667276`) |
| **US_PMI2** (ISM New Orders) | US #1 | DB.nomics `ISM/neword` | **LIVE** |
| **US_SVC1** (ISM Services) | US #2 | DB.nomics `ISM/nm-pmi/pm` | **LIVE** |
| **DE_IFO1** (IFO Climate) | Eurozone #4 | ifo Institute Excel (`fetch_macro_ifo.py`) | **LIVE** (commit `f35a0aa`) |
| **EU_PMI1** (EZ Mfg PMI) | Eurozone #1 | EC Industry Confidence (`EU_IND_CONF`, DB.nomics Eurostat) — same 3 PMI questions | **LIVE** — proxy, already in `dbn` |
| **EU_PMI2** (EZ Svc PMI) | Eurozone #2 | EC Services Confidence (`EU_SVC_CONF`, DB.nomics Eurostat) | **LIVE** — proxy, already in `dbn` |
| **UK_PMI1** (UK Mfg PMI) | UK #1 | OECD BCI for UK (`GBR_BUS_CONF`, FRED `BSCICP02GBM460S`, monthly) | **LIVE** — proxy, upgraded from quarterly |
| **CN_PMI1** (NBS Mfg) | China #1 | OECD BCI for China (`CHN_BUS_CONF`, FRED `CHNBSCICP02STSAM`, monthly) | **LIVE** — proxy, new FRED row |
| **GL_PMI1** (Global proxy) | Global #2 | Z-score-normalised 4-region composite (ISM + EU_IND_CONF + GBR_BUS_CONF + CHN_BUS_CONF) | **LIVE** — auto-rebuilds |
| **DE_ZEW1** (ZEW Sentiment) | Eurozone #6 | **PROPRIETARY** — ZEW Mannheim licences archive | No free monthly source. Covered by DE_IFO1 + DEU_BUS_CONF. |
| **JP_PMI1** (JP Mfg PMI) | Japan #1 | **PROPRIETARY** — S&P Global / au Jibun Bank | No free monthly source. BoJ Tankan (quarterly) is future option. |
| **CN_PMI2** (Caixin Mfg) | China #3 | **PROPRIETARY** — S&P Global / Caixin | No free monthly source. Chinese manufacturing covered by CN_PMI1. |

**Investing.com scraper rejected** (2026-04-23): Fragile anti-bot protections (Cloudflare, JS challenges), frequent HTML changes, and rate limiting make it unreliable for a nightly CI pipeline. Free proxy alternatives found instead for 4 of the 7 planned indicators; remaining 3 confirmed proprietary after exhaustive search across FRED, DB.nomics, OECD, ECB, Bundesbank, BoJ, NBS, and Eurostat.

---

## 2. Fully Integrated — Production (34 effective)

These flow end-to-end today and populate `macro_market.csv` / regional snapshot CSVs.

### US (17 effective)
Yield curve (T10Y3M, T10Y2Y); HY/IG credit spreads (BAML); SLOOS (5 series); Fed Funds; M2; jobless claims; building permits; S&P 500; Philly Fed + Empire State Mfg; NFP; Industrial Production; Unemployment; Core CPI; Core PCE. Source: **FRED** + yfinance.

### UK (1)
FTSE 100 / FTSE 250 (yfinance). UK is the weakest non-Asian region — only equities integrated.

### Eurozone (5 effective)
EU_ESI1 (EC Economic Sentiment); EU_IND_CONF / EU_SVC_CONF (not yet wired to Phase E indicators); peripheral spreads (BTP-Bund); EuroStoxx 50/600 (yfinance). Source: **DB.nomics Eurostat** + FRED + yfinance.

### Japan (1)
TOPIX / Nikkei 225 (yfinance).

### China (1 effective)
CSI 300 / Hang Seng / MSCI China (yfinance).

### Global (9)
OECD CLIs for 9+ countries (Phase C + GL_CLI composites); copper/gold ratio; oil/gold ratio; BCOM (via DBC); MSCI ACWI / URTH; DXY; US HY OAS (as global DM HY proxy); NFCI (as GS FCI substitute); VIX + MOVE; TIPS real yield.

---

## 3. Partially Integrated — Proxy-Based (22)

These use adjacent series (usually OECD-standardised) as proxies. Some are near-perfect substitutes and don't need upgrading; others are upgrade candidates if history depth / freshness warrants.

| Region | # | Indicator | Current proxy | Upgrade path |
|---|---|---|---|---|
| US | 15 | Michigan Consumer Sentiment — Expectations sub | UMCSENT (headline) | **No free path** — sub-index is UMich portal only |
| US | 25 | Retail Sales (Control Group) | RSXFS (ex-Autos) | Swap to FRED `RSFSXMV` |
| UK | 12 | UK Gilt Curve (10Y-2Y) | 10Y only via FRED | Add UK 2Y via **BoE IADB API** |
| UK | 31 | UK CPI Inflation | World Bank annual | Swap to **FRED `GBRCPIALLMINMEI`** (monthly) |
| Eurozone | 11 | EC Consumer Confidence | FRED OECD proxy | No upgrade needed — functional match |
| Eurozone | 12 | INSEE Business Climate | FRED OECD proxy | No upgrade needed |
| Eurozone | 13 | ISTAT Business Confidence | FRED OECD proxy | No upgrade needed |
| Eurozone | 14 | Bund Curve (10Y-2Y) | 10Y only via FRED | Add DE 2Y via **ECB SDW / Bundesbank** |
| Eurozone | 25 | Eurozone GDP | IMF annual | Swap to **Eurostat quarterly** via DB.nomics |
| Eurozone | 26 | Euro Area Unemployment | OECD monthly | Already close — no upgrade needed |
| Eurozone | 30 | HICP Inflation | World Bank annual | Swap to **FRED `EA19CPALTT01GYM`** (monthly) |
| Japan | 17 | Consumer Confidence Index | FRED OECD proxy | No upgrade needed |
| Japan | 26 | Real GDP | IMF annual | Swap to **e-Stat quarterly** (new source) |
| Japan | 29 | Unemployment Rate | OECD monthly | No upgrade needed |
| Japan | 30 | Core CPI | World Bank annual | Swap to **FRED `JPNCPIALLMINMEI`** (monthly) |
| China | 18 | Sovereign Curve (10Y-2Y) | 10Y only via FRED | 2Y is proprietary (ChinaBond/Wind) — accept the gap |
| China | 25 | Real GDP | IMF annual | **FMP_CHECK** was in original plan — now dead. GDP release data needs scraping |
| China | 31 | CPI Inflation | World Bank annual | Swap to **FRED `CHNCPIALLMINMEI`** (monthly) |
| China | 33 | Urban Surveyed Unemployment | OECD monthly | No upgrade needed |
| Global | 2 | Global Mfg PMI | GL_PMI1 equal-weight proxy | True JPM Global PMI is proprietary — keep proxy |
| Global | 11 | Bloomberg Commodity Index | DBC ETF proxy | BCOM itself proprietary — keep DBC |
| Global | 18 | Goldman Sachs FCI | NFCI (Chicago Fed) substitute | GS FCI proprietary — keep NFCI |

**Upgrade priority**: Swap World Bank / IMF annual macros (CPI, GDP, unemployment) for FRED or Eurostat monthly/quarterly equivalents. This is the biggest ROI upgrade — five indicators get a 4-12× frequency boost with trivial effort (new rows in existing `macro_library_fred.csv`).

---

## 4. Outstanding Indicators — Priority Tiers (140 total)

Grouped by how cheap it is to integrate. Tier 1 = trivial (row addition to an existing library). Tier 4 = genuinely blocked by paywalled or non-free data.

### Tier 1 — Row addition to existing library (zero infra work) — **26 indicators**

These just need rows appended to `macro_library_fred.csv` or `macro_library_dbnomics.csv`. Existing fetchers handle them automatically.

**FRED_ADD (18 indicators):**
- US: Avg Weekly Hours Mfg (`AWHMAN`), NEWORDER, Capacity Utilization (`TCU`), Real Pers Income ex Transfers (`W875RX1`), Real PCE (`PCEC96`), Mfg & Trade Sales (`CMRMTSPL`), CFNAI, Unit Labor Costs (`ULCNFB`), UEMPMEAN, C&I Loans (`TOTCI`), Corporate Profits (`CP`)
- Eurozone: Germany IP (`DEUPROINDMISMEI`), ECB Deposit Facility Rate (`ECBDFR`)
- Japan: JPY REER (`RBJPBIS`), Japan IP (`JPNPROINDMISMEI`), BoJ Policy Rate (`IRSTCB01JPM156N`)
- China: CN M2 (`MYAGM2CNM189N`), CN PPI (`CHNPPIALLMINMEI`)

**DBNOMICS_ADD (3 confirmed available):**
- EZ Industrial Production (`Eurostat/STS_INPR_M`)
- EZ Retail Sales Volume (`Eurostat/STS_TRTU_M`)
- EZ Employment Change (quarterly)

**FRED_CHECK (5 need verification):**
- Commercial & Industrial Loans variants
- CN Industrial Production (`CHNPROINDMISMEI`)
- CN Imports / Exports YoY (`XTIMVA01CNM667S`, `XTEXVA01CNM667S`)
- EMBI Global (`BAMLEMHBHYCRSP`)

### Tier 2 — New free source with known API (modest infra work) — **38 indicators**

Each tier-2 source needs a new fetcher module following the existing pattern. All are free, no API key required (except e-Stat which has free registration).

| Source | API / URL | Indicators | Count |
|---|---|---|---|
| **Japan e-Stat** | `api.e-stat.go.jp` (JSON, free registration) | JP Leading EI (#8), Machinery Orders (#10), Housing Starts (#12), Economy Watchers (#13), Inventory Ratio (#18), BSI DI (#20), Coincident EI (#21), Industrial Production (#22), Tertiary Industry (#23), Retail Sales (#24), Household Spending (#25), Real GDP (#26, upgrade), Jobs/Applicants (#27), Exports (#28), Core-Core CPI (#31), Real Cash Earnings (#32), Capacity Utilization (#35) | 14 |
| **UK ONS** | `api.ons.gov.uk` (JSON, free, no auth) | Index of Services (#17), PAYE Payrolls (#18), BICS (#19), Monthly GDP (#21), IP (#22), Manufacturing Output (#23), Retail Sales Volume (#24), LFS Employment (#25), Workforce Jobs (#28), Claimant Count (#30), CPI (#31 upgrade), Avg Weekly Earnings (#32), Unemployment (#29), Productivity (#36) | 11 |
| **Bank of Japan** | `boj.or.jp` Time-Series Statistics | Tankan (#3-6), JGB Curve 2Y (#15), Money Supply (#19), Policy Rate (#33 alt) | 5 |
| **Bank of England** | IADB API (free, no auth) | Credit Conditions Survey (#9), Mortgage Approvals (#14), UK 2Y Gilt (#12 upgrade), M4 Money Supply (#20), Bank Rate (#33 alt) | 3 |
| **ECB SDW** | `data-api.ecb.europa.eu` (free, no auth) | ECB Bank Lending Survey (#19), M3 Money Supply (#20), Negotiated Wages (#31), DE 2Y yield (#14 upgrade) | 2 |
| **CPB (NL)** | `cpb.nl/en/world-trade-monitor` (CSV download) | World Trade Volume (#23), World IP (#24) | 2 |
| **OFR** | `financialresearch.gov/financial-stress-index` (CSV/JSON, free daily) | OFR Financial Stress Index (#17) | 1 |
| **BIS** | BIS SDMX API (free) | CN Household Debt/GDP (#36), Global credit components (#5 partial) | 1 |
| **Atlanta Fed** | `atlantafed.org/cqer/research/gdpnow` (JSON) | GDPNow (#29) — snapshot only, need cron-append logic | 1 |

Some counts above are cumulative where a source covers several indicators. Deduplicated Tier 2 total: ~38 indicators across 9 new source modules.

### Tier 3 — Web scrape required (new scraping module) — **14 indicators**

Primary scraping target is **Investing.com economic calendar** (event ID system). Also covers the 11 broken FMP indicators in §1. Scraping infra built once then reused.

- FMP-replacement scrapes: 11 (listed in §1)
- Additional reference indicators where FMP_CHECK pivots to scraping:
  - UK Services PMI, UK Construction PMI, CBI Industrial Trends, GfK Consumer Confidence, RICS Housing, Halifax/Nationwide HPI
  - EZ Construction PMI
  - JP Services PMI, Machine Tool Orders
  - CN NBS Non-Mfg PMI, Caixin Services PMI, Caixin Composite PMI
  - China GDP release

Many of these overlap with the ONS/BoE sources — ONS API is preferred over scraping where available. Net Tier 3 after deduplication: ~14 reference indicators.

### Tier 4 — Proprietary / derived / blocked — **62 indicators**

No free source exists. These are deferred permanently unless a paid data feed is added or an acceptable proxy can be built.

**Proprietary data vendors (no free tier):**
- S&P Global PMI flash releases (4 indicators)
- Conference Board LEI / Global LEI / Credit Index / China LEI (4)
- Markit iTraxx CDS indices (2)
- J.P. Morgan EMBI, Global PMI (2)
- Refinitiv IBES / MSCI earnings (2)
- Baltic Exchange BDI, Drewry WCI, SCFI (3)
- Sentix, SIA, GS/BCA cycle models (4)

**China data lock-in (Wind/CEIC/Bloomberg only):**
- PBoC TSF, New RMB Loans, property series, retail sales, FAI, industrial profits, electricity, youth unemployment, 70-city property prices, NBS PMI sub-indices (12 indicators)

**UK / Japan private surveys / admin data:**
- CBI surveys, Lloyds Barometer, BRC sales, SMMT car registrations, Insolvency Service, BoE Agents narrative (6)
- Reuters Tankan (1)

**Derived composites** (require multi-source computation):
- Credit impulse (EZ, CN, global) — 3
- Li Keqiang Index components — 1
- Global Equity Breadth above 200DMA — 1 (noted in forward_plan §3.3)

**Total blocked / proprietary: ~62 indicators**. Realistically achievable maximum free-tier coverage: **~144 of 206 = 70%** (current effective: 34 = 16%).

---

## 5. Recommended Build Sequence

Ordered by ROI (signal restored / effort required). Each stage delivers coverage gains on its own so progress is never blocked on the next stage.

### Stage 1 — Restore broken pipeline (fix what existed) — COMPLETE

1. ~~Add 3 ISM rows to `macro_library_dbnomics.csv`~~ — **done** (commit `1667276`).
2. ~~Add ifo Excel downloader for DE_IFO1~~ — **done** (commit `f35a0aa`, new module `fetch_macro_ifo.py`).
3. ~~Probe ECB RTD for ZEW sentiment~~ — **done** (commit `c3e8c5a`). ZEW confirmed proprietary.
4. ~~Evaluate Investing.com scraper~~ — **rejected** 2026-04-23. Fragile anti-bot protections make it unreliable for nightly CI.
5. ~~Wire EU_PMI1/2 to EC Industry/Services Confidence~~ — **done** 2026-04-23. Data already in `dbn`.
6. ~~Wire UK_PMI1 to OECD BCI (monthly), CN_PMI1 to OECD BCI (NBS-derived)~~ — **done** 2026-04-23.
7. ~~Rebuild GL_PMI1 as z-score-normalised 4-region composite~~ — **done** 2026-04-23.
8. DE_ZEW1, JP_PMI1, CN_PMI2 classified **PROPRIETARY** — no free monthly source exists.

**Result:** 9 of 12 broken Phase E indicators restored (8 live proxies + GL_PMI1 composite). 3 proprietary. Effective Full: 34 → 44.

### Stage 2 — Cheap upgrades of existing Partial / add Tier 1 — 26 indicators
1. Swap 5 World Bank/IMF annual macros to FRED monthly (UK CPI, EZ CPI, JP CPI, CN CPI, EZ GDP).
2. Add 18 `FRED_ADD` rows to `macro_library_fred.csv`.
3. Add 3 Eurostat `DBNOMICS_ADD` rows (EZ IP, EZ Retail Sales, EZ Employment).
4. Verify 5 `FRED_CHECK` candidates.

**Deliverable:** +26 indicators. Effective Full: 46 → 72. ~3-4 days of work.

### Stage 3 — New-source pipelines (highest strategic value) — 38 indicators
Build one source module per region, in priority order:
1. **Japan e-Stat** (14 indicators — biggest single gain; Japan goes from 1 → 15 effective)
2. **UK ONS** (11 indicators — UK goes from 1 → 12 effective)
3. **BoE IADB** (3 indicators + DE 2Y, UK 2Y yield upgrades)
4. **ECB SDW** (2 indicators + DE 2Y yield upgrade)
5. **CPB World Trade Monitor** (2 indicators — global trade signal)
6. **OFR FSI** (1 indicator — trivial CSV download, high-value daily signal)
7. **BoJ, BIS, Atlanta Fed** (remaining 5 indicators — smaller wins)

**Deliverable:** +38 indicators. Effective Full: 72 → 110 (~53% coverage). ~3-4 weeks of work distributed over time.

### Stage 4 — Deferred / accept the gap — 62 indicators
Document in `forward_plan.md` which indicators are permanently blocked and why. Revisit if:
- A paid data feed (Bloomberg, FactSet, CEIC, Wind) is added to the stack.
- A free alternative emerges (e.g., PBoC publishes English API, SEMI restarts book-to-bill).
- A new derived-composite approach works (e.g., global credit impulse from country components).

---

## 6. Summary

- **Stage 1 COMPLETE** — 9 of 12 broken Phase E indicators restored (8 live proxies + GL_PMI1 composite). 3 proprietary (DE_ZEW1, JP_PMI1, CN_PMI2). Effective Full: 34 → 44.
- **After Stage 2**: ~70 effective indicators (~34% of reference baseline) with zero new fetcher modules.
- **After Stage 3**: ~108 indicators (~52%) — the realistic near-term ceiling.
- **~65 indicators are permanently blocked** by proprietary data, mostly concentrated in China (12), sell-side research (6), Conference Board / J.P. Morgan proprietary composites (8), S&P Global flash PMIs (4), S&P Global country PMIs (3), ZEW (1), and China derived composites.

Stages 2-3 together bring the project from 21% to ~52% reference coverage without any paid data subscription.




