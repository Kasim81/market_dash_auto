# Alpha Vantage — value-add evaluation against existing pipelines

> **Filed 2026-06-10** as the durable record of the AV evaluation requested after `ALPHAVANTAGE_API_KEY` landed in GitHub Secrets. Companion to `manuals/community_datasets_review.md` (which evaluated yfinance community ticker catalogues for §3.1 Stage F). **This is an evaluation, not an integration plan.** Wiring decisions belong in `forward_plan.md` (see §3.3 PE Ratio Integration, where the scaffolded `sources/alpha_vantage.py` already lives).

## Scope notes

- **Daily workflow** (news scan → brief + 8 LinkedIn posts): the news-scan / brief / post-generation code lives at `C:\Users\kasim\ClaudeWorkflow\` (per `technical_manual.md` §14 and `forward_plan.md` §3.10) — a separate Windows-local repo not accessible from the evaluator's sandbox. What `trigger.py` consumes from this pipeline is fully visible (the `market_data` Google Sheet tab, GID `68683176`); what the news-scan and post-generation steps consume beyond that CSV is **flagged as an assumption** below.
- **Regime / CMA pipeline (`regime-aa`):** not in MCP scope or local FS. Source of truth for what it consumes: `manuals/2026-06-10-regime-aa-v2-pipeline-handoff.md` §7.2 and `forward_plan.md §3.10–§3.17` (renumbered to §3.12–§3.17 on this side per the corrections memo).
- **Alpha Vantage docs:** sandbox 403s `www.alphavantage.co` even after allowlist update. Analysis uses the user-provided catalogue + AV's well-known free-tier API surface (function names: `REAL_GDP`, `CPI`, `FEDERAL_FUNDS_RATE`, `TREASURY_YIELD`, `UNEMPLOYMENT`, `NONFARM_PAYROLL`, `RETAIL_SALES`, `CONSUMER_SENTIMENT`, `DURABLES`, `INFLATION`, `WTI`, `BRENT`, `NATURAL_GAS`, `COPPER`, `ALUMINUM`, `WHEAT`, `CORN`, `COTTON`, `SUGAR`, `COFFEE`, `ALL_COMMODITIES`, `FX_DAILY/WEEKLY/MONTHLY`, `CURRENCY_EXCHANGE_RATE`, `OVERVIEW`).

---

## 1. Current inputs per pipeline

### 1a. Daily market workflow

**Entry point (visible):** `trigger.py` runs 06:15 London on a Windows box, pulls the `market_data` tab of the Google Sheet via CSV export. That tab is the **simple pipeline's output** — 70 instruments from `data/market_data.csv` (`fetch_data.py`). Each row carries `Symbol, Name, Ticker Type, Broad Asset Class, Region, Sub-Category, Currency, Last Price, Last Date`, plus performance columns (Local/USD 1W/1M/3M/6M/YTD/1Y, and bps versions for rates).

Instrument categories on the tab (full inventory from the CSV):

| Bucket | Tickers consumed |
|---|---|
| US equity indices / sectors / factors | SPY, QQQ, IWM, IWF, XLP/V/U/I/E/C/K/Y/B/F/RE (11 sector ETFs) |
| Intl equity indices | IWDA.L, IWFV.L, ISF.L, VMID.L, EXS1.DE (DAX), FEZ, EWJ, 1321.T (Nikkei), VFEM.L, NDIA.L, AAXJ, EWY, EWT, 000001.SS, 399001.SZ, NIFTYBEES.NS, ^BSESN, ILF |
| Bonds | AGGG.L, IGOV, IGLS.L, IGLT.L, VDET.L, SLXX.L, IHYU.L, EXX6.DE, CNYB.L |
| Sovereign yields | ^TNX, ^IRX, ^TYX, ^FVX, DGS2 (FRED), IRLTLT01GBM156N / IRLTLT01DEM156N / IRLTLT01JPM156N (FRED, monthly OECD MEI) |
| FX | DX-Y.NYB, EURUSD=X, GBPUSD=X, USDJPY=X, CNY=X, INR=X, KRW=X, TWD=X |
| Commodities | BZ=F (Brent), CL=F (WTI), GC=F (Gold), SI=F (Silver), ALI=F (Aluminium), HG=F (Copper), KC=F (Coffee), CT=F (Cotton), CMOD.L (broad index ETF) |
| Crypto | BTC-USD, ETH-USD |
| Vol | ^VIX |

**Data sources backing the tab:** yfinance for almost all of it; FRED for the 4 OECD-MEI yields and DGS2 — i.e. the simple pipeline already has FRED + yfinance wired and the CSV is the union.

**News scan / brief / posts (NOT visible):** the task description says it's a two-stage news-scan → brief + 8 LinkedIn posts workflow. **Working assumption** (flag): (a) the news scan is HTML/RSS scraping or an LLM web-pull agent, (b) the brief/post generator reads `market_data.csv` for the numeric overlay and the news scan for the narrative. What other inputs (FRED macro snapshots, economic-calendar feeds, transcripts) the brief/post generator consumes is not verifiable from this evaluation.

### 1b. Regime / CMA pipeline (regime-aa)

Per the handoff memo §7.2, regime-aa consumes the **following from this pipeline today**:

- `macro_economic_hist.csv` — weekly Friday-spine raw macro across 12 economies (USA, GBR, DEU, FRA, ITA, JPN, CHN, AUS, CAN, CHE, EA19, IND), sourced from FRED, OECD, World Bank, IMF, DB.nomics, ifo, BoE, ECB, BoJ, e-Stat, LBMA, BoC, StatCan, ONS, Bundesbank, ABS, ISTAT, BLS, INSEE, BdF (provisional).
- `macro_market_hist.csv` — 99 Phase E composite indicators with weekly 156-week rolling z-score / regime / forward-regime / cycle tag.
- `data/macro_market_monthly_hist.csv` (shipped 2026-06-10, §3.14) — month-end-sampled view of the above for the regime engine's monthly Layer-1 frame.
- `index_library.csv` — investable instrument registry.
- The Indicator Explorer payload.

**Outstanding asks (forward_plan §3.12–§3.17, not yet fully shipped):** OECD MEI monthly rows for the priority-10 regions (§3.12, shipped 2026-06-10), long-run sources (Shiller / Ken French / IMF PCPS / JST / BoE Millennium — §3.13, Shiller scaffold shipped), monthly EWMA features (§3.15, blocked on universe), ALFRED vintage data (§3.17, capability shipped, writer deferred). **No row in any of these asks references Alpha Vantage.**

---

## 2. Coverage map — AV category vs current sources

### 2a. AV US economic indicators (`REAL_GDP`, `REAL_GDP_PER_CAPITA`, `TREASURY_YIELD`, `FEDERAL_FUNDS_RATE`, `CPI`, `INFLATION`, `UNEMPLOYMENT`, `NONFARM_PAYROLL`, `RETAIL_SALES`, `DURABLES`, `CONSUMER_SENTIMENT`)

| AV series | Current source in this pipeline | Verdict |
|---|---|---|
| `REAL_GDP` (annual / quarterly) | Not in pipeline as a direct column (FRED GDP not in `macro_library_fred.csv`). | **Duplicates** what FRED already publishes (`GDPC1` etc.) — adding it is a one-line FRED CSV row, not an AV reason. |
| `REAL_GDP_PER_CAPITA` | Not in pipeline. | Same — FRED `A939RX0Q048SBEA` etc. |
| `TREASURY_YIELD` (3m / 2y / 5y / 7y / 10y / 30y; d/w/m) | Daily FRED: `DGS2`, `DGS10` wired + `^IRX/^FVX/^TNX/^TYX` via yfinance in simple pipeline. | **Full duplicate** — FRED daily covers everything AV exposes, with longer history. |
| `FEDERAL_FUNDS_RATE` | FRED `FEDFUNDS` — wired (sort_key 230 in `macro_library_fred.csv`). | **Full duplicate.** |
| `CPI` | FRED `CPIAUCSL` (headline) + `CPILFESL` (core) — wired. BLS `CUSR0000SA0` / `CUSR0000SA0L1E` — wired as primary, FRED as fallback (`sources/bls.py`). | **Full duplicate** — BLS is the ultimate source already wired ahead of FRED. |
| `INFLATION` (annual %) | Derivable from `CPIAUCSL` YoY; already feeds `US_INFL1`. | **Computed downstream** — AV's value is a single number, not new info. |
| `UNEMPLOYMENT` | BLS `LNS14000000` — wired as primary; FRED `UNRATE` as fallback. | **Full duplicate** (primary already in). |
| `NONFARM_PAYROLL` | FRED `PAYEMS` — wired. | **Full duplicate.** |
| `RETAIL_SALES` | FRED `RSXFS` and `RSFSXMV` (control group) — wired. | **Full duplicate.** |
| `DURABLES` | FRED `NEWORDER` — wired. | **Full duplicate.** |
| `CONSUMER_SENTIMENT` | FRED `UMCSENT` — wired. AV is the same University of Michigan series. | **Full duplicate.** |

**Net:** AV's US macro endpoints are 100% duplicates of series we already pull from FRED (often via BLS as primary). AV adds **no series** and importantly **no non-US coverage** — UK, EZ, JP, CN regime inputs that drive every regime-AA regional ask (§3.12 OECD MEI, BoE, ECB, BoJ, ONS, Eurostat, etc.) have **no AV counterpart**.

### 2b. AV Commodities (`WTI`, `BRENT`, `NATURAL_GAS`, `COPPER`, `ALUMINUM`, `WHEAT`, `CORN`, `COTTON`, `SUGAR`, `COFFEE`, `ALL_COMMODITIES`)

| AV series | Daily workflow today | Regime pipeline today (post 2026-06-10 §3.9.1) | Verdict |
|---|---|---|---|
| `WTI` (monthly) | `CL=F` futures (daily) on `market_data` | `WTI_USD` (FRED `WTISPLC`, monthly, §3.9.1) | **Full duplicate** — same series, FRED is the canonical IMF PCPS mirror. |
| `BRENT` (monthly) | `BZ=F` futures (daily) | `BRENT_USD` (`POILBREUSDM`) | Full duplicate. |
| `NATURAL_GAS` | not on `market_data` tab | `NATGAS_HH_USD` (`PNGASUSUSDM`) | Full duplicate (post-2026-06-10). |
| `COPPER` | `HG=F` futures | `COPPER_USD` (`PCOPPUSDM`) | Full duplicate. |
| `ALUMINUM` | `ALI=F` futures | `ALUM_USD` (`PALUMUSDM`) | Full duplicate. |
| `WHEAT` / `CORN` / `COTTON` / `SUGAR` / `COFFEE` | Cotton `CT=F` and Coffee `KC=F` on `market_data`; wheat / corn / sugar not on the tab today | All 5 wired via FRED IMF PCPS (§3.9.1) | AV duplicates the FRED rows; daily-workflow gap of wheat/corn/sugar is already addressed by §3.9.1. |
| `ALL_COMMODITIES` (index) | `CMOD.L` (tradable ETF — proxy, not index) | `IMF_PCPS_ALL` (`PALLFNFINDEXM`) | Full duplicate of the FRED IMF PCPS aggregate. |

**Net:** AV's commodity catalogue is the same IMF PCPS data we already mirror via FRED, plus the same precious-metals data we mirror from LBMA. Adds no series. Yfinance futures on the simple pipeline give the daily granularity AV's monthly endpoints don't.

### 2c. AV FX (`FX_DAILY/WEEKLY/MONTHLY`, `CURRENCY_EXCHANGE_RATE` spot)

| AV capability | Current source | Verdict |
|---|---|---|
| Daily FX history | yfinance `=X` tickers — `EURUSD=X`, `GBPUSD=X`, `USDJPY=X`, `CNY=X`, `INR=X`, `KRW=X`, `TWD=X` already on `market_data`; comp pipeline carries 18 currencies via `COMP_FX_TICKERS`. | **Duplicate.** |
| Spot exchange rate | yfinance `=X` + ECB / BoC / IMF rates already pulled. | Duplicate. |

### 2d. AV Equities / ETFs (`TIME_SERIES_DAILY_ADJUSTED`, `OVERVIEW`, technical indicators)

| AV capability | Current source | Verdict |
|---|---|---|
| `TIME_SERIES_DAILY_ADJUSTED` | yfinance comp pipeline (~400 instruments daily) + `market_data_comp_hist` (weekly Friday from 1990). | **Duplicate.** AV's free tier (25/day) cannot replace yfinance's batch coverage. |
| `OVERVIEW` — trailing PE, forward PE, PEG, dividend yield, EPS, book value (snapshot) | **Not in pipeline.** yfinance carries snapshot PE per ticker in `Ticker.info` but it's not pulled or stored today. | **Gap-fill** — this is genuinely new data. Already scaffolded in `sources/alpha_vantage.py` (§3.3, 2026-06-10). |
| Technical indicators (SMA / EMA / RSI / MACD / Bollinger / ATR / ADX / OBV …) | Not computed in pipeline. | Could be a gap-fill *for the brief/posts narrative* if the workflow wants pre-computed TA — but TA is trivially computable from `market_data_comp_hist` (one pandas line per indicator). AV's free-tier quota makes a per-indicator pull infeasible for any list larger than ~5 tickers/day. |

---

## 3. Value-add per pipeline

### 3a. Daily workflow

**Working assumption:** the brief/post generator reads `market_data.csv` for numeric overlay + the news scan for narrative.

| Use case | AV value-add? | Why |
|---|---|---|
| **Numeric overlay on `market_data` tab** (levels, 1W/1M/YTD performance) | **None.** | The CSV already has everything AV's commodity / FX / equity endpoints would supply, at higher quality (yfinance daily + ULP performance windows) than AV's monthly cadence. |
| **US macro context for the brief** (CPI, NFP, FFR, retail sales) | **None directly,** but the CSV doesn't currently *include* these as cells. If the brief wants the latest CPI / NFP / FFR / retail-sales number cited, the pipeline already has them in `macro_economic.csv` snapshot tab and could be surfaced into a "market overlay" view. AV would duplicate what FRED + BLS already provide. | The right fix is to expose existing FRED snapshot columns to whatever the brief reads, not to add AV. |
| **Commodity prices for the daily brief** | **None.** | `market_data` carries `BZ=F`, `CL=F`, `GC=F`, `SI=F`, `HG=F`, `ALI=F`, `KC=F`, `CT=F` daily; AV monthly is a regression. |
| **Forward-looking commentary (PE valuations on indices)** | **Yes, modest.** | The `OVERVIEW` endpoint gives current trailing/forward PE for SPY/QQQ/IWM/EFA/EEM (5 tickers = 5 of 25 daily quota → fits). If the brief wants to say "S&P trades at X× forward earnings vs Y last year" this is new data not in the pipeline today. Scaffolded via §3.3 commit 2026-06-10. |
| **Headline news / sentiment** | **AV not the right tool.** | AV doesn't have a news-classification API at the depth of commercial feeds. The news scan should remain whatever it is today. |

**Bottom line for daily workflow:** AV adds **one useful capability** — snapshot PE / forward-PE / PEG for major index ETFs via `OVERVIEW` — and that's it. Everything else AV offers is either already in `market_data.csv` (commodities/FX/equities daily) or in `macro_economic.csv` (US macro, via FRED).

### 3b. Regime / CMA pipeline

| Use case | AV value-add? | Why |
|---|---|---|
| Per-region growth / inflation / rates inputs (the regime classifier's core) | **None.** | The regime engine is explicitly multi-region — US, UK, EZ, JP, CN, plus the §3.12 priority-10. AV's macro endpoints are **US-only**. UK, EZ, JP, CN all stay on FRED / OECD / BoE / ECB / BoJ / ONS / Eurostat — AV cannot replace any. |
| US growth axis specifically (GDP, IP, employment) | **None as primary.** FRED + BLS already deliver the same series with longer history, no rate cap, and ALFRED vintage. | A paid AV tier would still be worse than FRED for the US-only subset because FRED carries the methodological metadata (real-time vs revised, source, revision history) that vintage-aware backtests need. |
| US Treasury yields (3m–30y) | **None.** | `DGS2` / `DGS10` / `^IRX` / `^FVX` / `^TNX` / `^TYX` already daily via FRED + yfinance. AV's monthly `TREASURY_YIELD` is a regression. |
| Commodity returns pillar (regime-AA `commodity_return`) | **None.** | §3.9.1 (2026-06-10) already wires the full IMF PCPS set via FRED + LBMA gold daily. AV is the same data. |
| Long-run depth (§3.13 Shiller / French / JST / IMF PCPS aggregate) | **None.** | AV has nothing pre-1980 (it depends on FRED / IMF for its macro). For Shiller (1871+), Ken French (1926+), JST (1870+) AV simply doesn't compete. |
| ALFRED vintage (§3.17) | **None.** | AV serves revised data only. Backtest-vintage work must use ALFRED. |

**Bottom line for regime / CMA:** AV has **zero role** as a primary, secondary, or tertiary source. The US-only constraint alone disqualifies it before the rate-cap question matters. None of the §3.10–§3.17 asks reference it.

---

## 4. Overlaps and risks

| Issue | Detail |
|---|---|
| **US-only ceiling** | The regime classifier is built around per-region desynchronisation (Goldilocks / Overheating / Downturn / Stagflation per region). AV covers only US. Even at the paid premium tier, the structural gap is the same. |
| **Free-tier rate cap (25/day, 5/min)** | 25/day fits ~5 tickers via `OVERVIEW` + 1 smoke test, well under the limit. **It does not** fit pulling per-region macro daily for the regime pipeline (which would need at minimum GDP / CPI / IP / rates × 5 regions = 25+ calls just for one cadence, before history backfills). |
| **Reconcile-before-publish** | AV is documented unofficial-grade. For LinkedIn posts going out under your name, anything cited as a hard number (CPI = X, NFP = Y, PE = Z) must be reconciled against the licensed / primary source first. FRED + BLS + ONS + Eurostat already serve that role for macro; AV would re-introduce a reconciliation step that doesn't exist today. |
| **Duplication overhead** | Wiring AV for series we already have means a per-series merge / dedup choice (which source wins?). The pipeline's existing primary-source-wins pattern (BLS over FRED, Bundesbank over FRED monthly) is well-tested. Inserting AV into that hierarchy gains nothing and adds noise. |
| **Single-vendor concentration** | Adding AV as a *fallback* would be useful only if a primary source dies. We already have layered fallbacks per source (T0 / T1 / T2 / T3 in `source_fallbacks.csv`). AV would land at T3 at best, and only for US series we already have at T0. Negligible incremental resilience. |
| **PE-snapshot freshness** | AV `OVERVIEW` updates daily, but the underlying fundamentals (last reported EPS, book value) update only on earnings dates. For *trailing* PE the value is fine; *forward* PE depends on whose consensus AV is using and isn't disclosed precisely. For LinkedIn-published commentary, cite trailing PE as snapshot and treat forward PE as directional. |

---

## 5. Recommendation per use case

| Use case | Recommendation | Why |
|---|---|---|
| **Daily workflow — AV macro endpoints** (REAL_GDP, CPI, FFR, UNRATE, NFP, etc.) | **Skip.** | Pure duplicates of FRED + BLS already in `macro_economic.csv`. If the brief wants them cited, surface the existing FRED snapshot columns to whatever reads `market_data` — don't add AV. |
| **Daily workflow — AV commodities + FX** | **Skip.** | `market_data` already carries the relevant futures (`BZ=F`, `CL=F`, `GC=F`, `HG=F`, `ALI=F`, `KC=F`, `CT=F`) and FX pairs (EUR/GBP/USD/JPY/CNY/INR/KRW/TWD) at daily granularity. AV's monthly cadence is a regression. |
| **Daily workflow — AV `OVERVIEW` (PE / forward PE / PEG)** | **Use, as the one genuine value-add.** Already scaffolded 2026-06-10 via §3.3 (`sources/alpha_vantage.py` + smoke test). Wire 5 major index ETFs (SPY / QQQ / IWM / EFA / EEM) into a daily PE snapshot CSV, gate on `ALPHAVANTAGE_API_KEY`, treat trailing PE as snapshot and forward PE as directional. Storage: a new `data/equity_pe_snapshot.csv`, not mixed into the time-series hist (see §3.3 follow-up note). | Real new capability not duplicated anywhere; quota fits. |
| **Daily workflow — AV technical indicators** | **Use as prototyping only.** | Trivially computable in-pipeline from `market_data_comp_hist` (one pandas line per indicator); AV's 25/day quota cannot scale to a real per-ticker indicator pull. Use AV at most to validate against a small set of tickers, then compute locally. |
| **Regime / CMA pipeline — anything** | **Skip.** | US-only ceiling disqualifies AV before the rate cap matters. Every regime input the pipeline owes regime-AA (§3.10–§3.17) already has a better-fit source: FRED (free, vintage-capable via ALFRED for §3.17), OECD (monthly MEI for §3.12), BLS / BoE / ECB / BoJ / ONS / Eurostat for primary national, Shiller / Ken French / IMF PCPS / JST for long-run (§3.13). |

### Premium tier?

A premium AV tier (~$50/month for 75/min, ~$150 for 1200/min) would lift the rate cap but **doesn't change any of the above recommendations** — the US-only gap is structural, not a quota issue. Don't pay for AV premium for either pipeline.

---

## 6. Net summary

- **Daily workflow:** **use AV for one thing — index-ETF PE snapshots via `OVERVIEW`** — and skip the rest.
- **Regime / CMA pipeline:** **skip AV entirely.** FRED + OECD + the long-run sources (Shiller / French / JST / IMF PCPS) are strictly dominant.
- **Assumption flagged:** the news-scan / brief / post-generation code wasn't visible to the evaluator (lives in `C:\Users\kasim\ClaudeWorkflow\`). If the brief currently consumes a source that isn't in `market_data.csv` and isn't FRED-derivable, the calculus could shift. Worth a 5-minute scan of that directory to confirm.

---

*See `forward_plan.md §3.3` for the implementation track that absorbs this recommendation; `sources/alpha_vantage.py` and `test_alpha_vantage_smoke.py` were scaffolded 2026-06-10 ahead of this evaluation and are gated on `ALPHAVANTAGE_API_KEY`.*
