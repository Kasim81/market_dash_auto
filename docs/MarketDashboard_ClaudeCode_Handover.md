# Market Dashboard Expansion — Claude Code Handover
**Version 1.0 | March 2026 | Prepared for handover from claude.ai to Claude Code**

| Property | Value |
|---|---|
| Repository | github.com/Kasim81/market_dash_auto |
| Google Sheet ID | 12nKIUGHz5euDbNQPDTVECsJBNwrceRF1ymsQrIe4_ac |
| Primary contact | kasimzafar@gmail.com |
| Existing secrets | FRED_API_KEY, GOOGLE_CREDENTIALS |
| New secrets needed | BLS_API_KEY, FMP_API_KEY |
| Python version | 3.11 (set in update_data.yml) |
| Run schedule | Daily 06:00 UTC via GitHub Actions |

---

## 1. What Currently Exists (Do Not Break)

### 1.1 Repository Files

| File | Purpose | Status |
|---|---|---|
| fetch_data.py | Main daily collection: 66 instruments, FX, FRED yields/sentiment, Google Sheets push | PRODUCTION — do not modify logic |
| fetch_macro_us_fred.py | 25 US FRED macro indicators → macro_us tab (snapshot, now being replaced by history) | PRODUCTION |
| fetch_hist.py | NEW — historical weekly time series for market_data_hist and macro_us_hist tabs | JUST DEPLOYED — verify first run |
| requirements.txt | yfinance, pandas, numpy, requests, google-auth, google-api-python-client | Add new packages here |
| .github/workflows/update_data.yml | GitHub Actions: daily 06:00 UTC, injects secrets, commits CSVs | Do not change schedule without instruction |

### 1.2 Google Sheet Tabs

| Tab Name | GID | Written By | Contents |
|---|---|---|---|
| market_data | 68683176 | fetch_data.py | 75 rows: 66 instruments + 5 ratios + headers. Daily snapshot of prices and returns (1W/1M/3M/6M/YTD/1Y, local + USD). **NEVER TOUCH.** |
| sentiment_data | 14812133 | fetch_data.py | 5 FRED sentiment series: UMich, Conference Board, ISM, etc. **NEVER TOUCH.** |
| macro_us | (new) | fetch_macro_us_fred.py → being replaced | Was snapshot of 25 US macro indicators. Being replaced by macro_us_hist (full history). |
| market_data_hist | (new) | fetch_hist.py | Weekly Friday prices from 2000-01-07. 1,366 rows × 144 cols. All Local prices then all USD prices. |
| macro_us_hist | (new) | fetch_hist.py | Weekly Friday series from 1947-01-01. 4,132 rows × 26 cols. 25 FRED series, forward-filled to weekly. |
| Market Data | duplicate | Manual / formula | REDUNDANT — duplicate of market_data. Can be deleted after confirming it contains no unique formulas. |

### 1.3 CSV Export URLs (used by trigger.py)

```
market_data:    https://docs.google.com/spreadsheets/d/12nKIUGHz5euDbNQPDTVECsJBNwrceRF1ymsQrIe4_ac/export?format=csv&gid=68683176
sentiment_data: https://docs.google.com/spreadsheets/d/12nKIUGHz5euDbNQPDTVECsJBNwrceRF1ymsQrIe4_ac/export?format=csv&gid=14812133
```

`trigger.py` lives at `C:\Users\kasim\ClaudeWorkflow\` and runs at 06:15 London time. History tabs are for manual analysis only — trigger.py does not read them.

---

## 2. Schema Decisions (Locked)

Do not revisit these without explicit instruction.

| Decision | Choice Made | Rationale |
|---|---|---|
| Data orientation | Long format: dates as rows, indicators as columns | 10M row limit vs 18,278 col limit — long format scales better |
| market_data_hist date range | 2000-01-07 to present (Fridays) | Most instruments have reliable data from 2000 |
| macro_us_hist date range | 1947-01-01 to present (Fridays) | Earliest FRED data; series fill in as they become available |
| Frequency | Weekly, Friday close (W-FRI resample) | Consistent spine; daily would be 5× the rows with marginal benefit |
| Monthly macro in weekly sheet | Forward-fill into intervening weekly slots | Clean spine; blanks rejected because they make charting harder |
| Local vs USD grouping | All Local rows first, then all USD rows | Grouped separately, not interleaved |
| macro_us snapshot tab | Replace with history — drop snapshot | Snapshot was intermediate artefact; history supersedes it |
| trigger.py and history tabs | History tabs are for manual analysis only | trigger.py reads market_data and sentiment_data only |

---

## 3. Source Architecture

| Layer | Coverage | API Key? | Status |
|---|---|---|---|
| yfinance (existing) | All market prices, FX, ETFs, yields (66 instruments) | None | Production |
| FRED API (existing) | US macro: breakevens, yield curve, M2, SLOOS, payrolls, CPI, PCE (25 series) | FRED_API_KEY | Production |
| OpenBB → OECD (new) | Multi-country: CLI, CPI, unemployment, GDP, interest rates | None needed | Phase C |
| OpenBB → IMF (new) | Multi-country: GDP, CPI, current account, EM coverage | None needed | Phase C |
| OpenBB → ECB (new) | Eurozone: ECB policy rate, M3, bank lending | None needed | Phase C |
| OpenBB → BLS (new) | US: nonfarm payrolls detail | BLS_API_KEY (free) | Phase B |
| FMP (new, narrow) | ISM Manufacturing, ISM Services, Philly Fed, Empire State only | FMP_API_KEY (free) | Phase D |

**New pip installs required:**
```
openbb openbb-oecd openbb-imf openbb-ecb openbb-federal-reserve openbb-bls openbb-fmp openbb-fred
```
Add all to requirements.txt. Test locally before committing.

---

## 4. Remaining Implementation Phases

Phases are ordered by priority. Each phase is independent — a failure in one should not block others.

### Phase B — OpenBB Survey Endpoints
- **Module:** fetch_macro_surveys.py
- **Output tab:** macro_surveys (new)
- **Indicators:**
  - SLOOS detail — net tightening by loan category (via OpenBB Federal Reserve)
  - Regional Fed surveys — Philly Fed Mfg, Empire State Mfg (via FMP as fallback)
  - UMich consumer sentiment sub-indices — current conditions vs expectations (FRED: UMCSENT already in macro_us; need sub-indices)
- Rate limiting: match FRED pattern (0.6s delay, exponential backoff on 429).

### Phase C — International Macro (OpenBB OECD / IMF / ECB)
- **Module:** fetch_macro_international.py
- **Output tab:** macro_international (new)

**Countries and regions:**

| Region | Countries | ISO Codes |
|---|---|---|
| North America | United States, Canada | US, CA |
| UK | United Kingdom | GB |
| Europe | Germany, France, Eurozone aggregate | DE, FR, EZ |
| Japan | Japan | JP |
| Asia ex-Japan | China, India, South Korea, Australia | CN, IN, KR, AU |

**Indicators per country (where available):**
- OECD CLI (Composite Leading Indicator) — via OpenBB OECD
- CPI YoY — via OpenBB OECD or IMF
- Unemployment rate — via OpenBB OECD
- GDP YoY — via OpenBB IMF
- Policy interest rate — via OpenBB ECB (Eurozone) or OECD (others)

**Schema:** long format. Columns: `Date | {indicator}_{ISO}` (e.g. CLI_US, CLI_DE, CPI_JP). Forward-fill monthly to weekly.

### Phase D — FMP for PMI / Survey Data
- **Module:** fetch_pmi.py (or integrate into fetch_macro_surveys.py)
- **Output:** append columns to macro_us_hist or new macro_pmi tab
- FMP free tier covers: ISM Manufacturing PMI, ISM Services PMI, Philadelphia Fed Survey, Empire State Survey
- Free API key: financialmodelingprep.com. Store as FMP_API_KEY secret.

### Phase E — New ETFs (Instrument Basket Expansion)
- Additions to fetch_data.py instrument lists. No new modules needed.
- Categories: Europe sector ETFs (.DE, EUR), EM regional ETFs, UK style ETFs, Asia/Japan additional coverage
- For each new .L ETF: verify pence correction applies. For each new non-USD instrument: verify currency is in FX_TICKERS dict.
- **Confirm full instrument list with Kasim before implementing — instrument selection is owner decision.**

### Phase F — Calculated Fields
Append synthetic columns to market_data_hist and macro_us_hist after all instrument fetches.

| Field | Formula | Signal |
|---|---|---|
| HY/IG ratio | BAMLH0A0HYM2 / BAMLC0A0CM (from FRED) | Credit risk appetite; compression = risk-on |
| EMFX basket | Equal-weight CNY, INR, KRW, TWD vs USD | EM risk appetite proxy |
| EEM/IWDA ratio | EEM close / IWDA.L close (FX-adjusted) | EM vs DM relative momentum |
| MOVE proxy | 30-day realised vol on ^TNX (10Y yield) | Bond volatility proxy; substitute for MOVE index |
| Global PMI proxy | Equal-weight ISM + Eurozone PMI + Japan PMI | Global growth signal |
| Global yield curve | Average of US/DE/UK/JP 10Y-2Y spreads | Synchronised monetary tightening signal |

### Phase G — Google Sheets Export Updates
Ensure all new tabs are pushed by the relevant fetch modules. Verify:
- Tab names match exactly (lowercase underscores)
- Protected tabs guard is in place: never write to market_data or sentiment_data
- Batch write logic (10,000 rows per call) is used for large tabs
- GIDs are recorded once tabs are created

---

## 5. Indicator Reference — US Macro (25 FRED Series)

Already implemented in fetch_macro_us_fred.py and fetch_hist.py.

| FRED Series | Name | Category | Frequency |
|---|---|---|---|
| T10Y2Y | US Yield Curve 10Y-2Y Spread | Growth / Monetary | Daily |
| T10Y3M | US Yield Curve 10Y-3M Spread | Growth / Monetary | Daily |
| M2SL | US M2 Money Supply | Monetary | Monthly |
| USSLIND | US Conference Board LEI | Growth | Monthly |
| PERMIT | US Building Permits (SAAR) | Growth | Monthly |
| IC4WSA | Initial Jobless Claims 4-Week Avg | Growth | Weekly |
| PAYEMS | US Nonfarm Payrolls | Growth | Monthly |
| UNRATE | US Unemployment Rate | Growth | Monthly |
| INDPRO | US Industrial Production | Growth | Monthly |
| RSXFS | US Retail Sales ex-Autos | Growth | Monthly |
| DRTSCILM | SLOOS Net Tightening (C&I Large) | Financial Conditions | Quarterly |
| NFCI | Chicago Fed NFCI | Financial Conditions | Weekly |
| CPIAUCSL | US CPI Headline | Inflation | Monthly |
| CPILFESL | US Core CPI | Inflation | Monthly |
| PCEPILFE | US Core PCE Deflator | Inflation | Monthly |
| PPIACO | US PPI All Commodities | Inflation | Monthly |
| T5YIE | US TIPS 5Y Breakeven | Inflation | Daily |
| T10YIE | US TIPS 10Y Breakeven | Inflation | Daily |
| T5YIFR | US 5Y5Y Forward Inflation | Inflation | Daily |
| MICH | UMich Consumer Inflation Expectations | Inflation | Monthly |
| FEDFUNDS | US Federal Funds Rate | Monetary | Monthly |
| DFII10 | US 10Y Real Rate (TIPS) | Monetary | Daily |
| DFII5 | US 5Y Real Rate (TIPS) | Monetary | Daily |
| BAMLH0A0HYM2 | US HY Credit Spread OAS | Financial Conditions | Daily |
| BAMLC0A0CM | US IG Credit Spread OAS | Financial Conditions | Daily |

---

## 6. Indicators Excluded (With Rationale)

Do not attempt to implement these without explicit instruction.

| Indicator | Why Excluded | Proxy Used Instead |
|---|---|---|
| Atlanta Fed GDPNow | Web scrape only — no clean API endpoint | None |
| Fed Funds Futures implied path | CME data — paid subscription required | None (omitted from Phase 1 scope) |
| Taylor Rule Gap | Requires custom calculation from multiple inputs | Deferred to Phase 2 content workflow |
| Global Monetary Policy Tracker | BIS/JP Morgan data — no free API | None |
| NAHB Housing Market Index | Low priority vs Building Permits (already covered) | PERMIT (FRED) |
| Goldman Sachs FCI | Proprietary — not publicly available | Chicago Fed NFCI (FRED: NFCI) |
| Bloomberg FCI | Bloomberg terminal required | Chicago Fed NFCI |
| MOVE Index | Bloomberg terminal required | 30-day realised vol on ^TNX (Phase F) |
| JP Morgan Global PMI | S&P Global licence required | Equal-weight ISM + EZ PMI + Japan PMI (Phase F) |
| EM Currencies Index (EMFX) | JP Morgan index — proprietary | Basket of CNY/INR/KRW/TWD vs USD (Phase F) |
| China 10Y yield (FRED) | Series CHNGDPNQD — data quality issues | CNYB.L ETF used as proxy |
| UK 2Y yield (FRED) | Series IUDSGT02 — retired/invalid | ^IRX used as proxy if needed |

---

## 7. Coding Conventions to Preserve

### 7.1 Rate Limiting
- yfinance: 0.3s delay between per-ticker calls (`YFINANCE_DELAY = 0.3`)
- FRED: 0.6s delay between calls (`FRED_DELAY = 0.6`)
- FRED exponential backoff on 429/5xx: 2s → 4s → 8s → 16s → 32s (max 5 retries)
- yfinance: prefer bulk download (`yf.download([list])`) over per-ticker loops

### 7.2 Error Handling
- Per-series try/except — one failure must never kill the run
- Broad try/except wrapper in fetch_data.py integration block — Phase failures cannot affect existing pipeline
- If FRED_API_KEY absent: skip FRED fetches silently, log warning, continue
- If GOOGLE_CREDENTIALS absent: skip Sheets push, log warning, continue

### 7.3 LSE Pence Correction
```python
if ticker.endswith('.L') and median_price > 50:
    price /= 100
```
Applied to all .L tickers. Median check prevents double-correction on re-runs.

### 7.4 USD Return Calculation
```python
usd_return = (1 + local_return) * (1 + fx_return) - 1  # compounded, not additive
```
FX direction convention:
- `GBPUSD=X`, `EURUSD=X`: **multiply** (USD is quote currency)
- `USDJPY=X`, `USDCNY=X`, `USDINR=X`, `USDKRW=X`, `USDTWD=X`: **divide** (USD is base currency)

### 7.5 Google Sheets Push
- Protected tab guard: hard-refuse writes to `market_data` and `sentiment_data`
- Batch write: 10,000 rows per API call to stay within payload limits
- NaN → empty string before push (never push `"nan"` strings)
- Tab creation: check existing tabs before creating; use `batchUpdate addSheet` request
- Clear before write: `sheets.values().clear()` on the full range before updating

### 7.6 CSV Commit Logic
fetch_data.py uses a diff-check before committing CSVs — only commits if content changed. Preserve this in new modules to avoid noisy daily commits on weekends when data hasn't changed.

---

## 8. First Steps for Claude Code

When starting a new session on this project, follow this sequence:

**Step 1 — Verify the current state**
```bash
head -3 data/market_data_hist.csv      # confirm hist fetch ran
head -3 data/macro_us_hist.csv         # confirm macro hist ran
python fetch_hist.py                    # test run if needed
```

**Step 2 — Check which GitHub secrets are present**

Go to Settings → Secrets → Actions in the repo. Confirm present: `FRED_API_KEY`, `GOOGLE_CREDENTIALS`. Note missing: `BLS_API_KEY`, `FMP_API_KEY` (needed for Phases B and D).

**Step 3 — Install and test OpenBB**
```bash
pip install openbb openbb-oecd openbb-imf openbb-ecb openbb-federal-reserve openbb-bls openbb-fred
python -c "from openbb import obb; data = obb.economy.indicators(countries=['US'], indicators=['CLI']); print(data)"
```
If OpenBB install fails or OECD endpoints return empty, fall back to direct OECD API (`data.oecd.org/api/v2`) — no key required.

**Step 4 — Recommended phase order**

B → C → D → E → F → G. Phase B (survey endpoints) is simpler and self-contained. Phase C (international macro) has more complexity due to multi-country alignment.

**Step 5 — Test any new module standalone before integrating**
```bash
python fetch_macro_surveys.py    # run standalone first
```
Only add the integration call to fetch_data.py after standalone test passes.

---

## 9. Known Issues and Watch Points

| Issue | Status | Action |
|---|---|---|
| 'Market Data' tab (space) is duplicate of market_data (underscore) | Identified — not yet deleted | Delete after confirming no unique formulas |
| macro_us snapshot tab | Being replaced by macro_us_hist | Delete once macro_us_hist is confirmed working |
| fetch_hist.py first run takes 8–12 mins | Expected — fetching decades of history | Subsequent daily runs will be fast |
| China 10Y FRED series removed | CHNGDPNQD had data quality issues | CNYB.L ETF used as proxy |
| UK 2Y FRED series removed | IUDSGT02 series ID retired | ^IRX used as proxy if needed |
| NAPMPI vs NAPM | NAPM retired; NAPMPI is current ISM series | Already fixed in production — do not revert |
| GitHub Actions inactivity pause | Actions pauses after 60 days of no pushes | Push trivial commit or re-enable from Actions tab |
| Google Sheets CDN caching | GitHub raw CSV URL caches aggressively | Always use Sheets export URL (gid= parameter), not GitHub raw URL |

---

## 10. Quick Reference

**Key URLs**
```
Repo:           https://github.com/Kasim81/market_dash_auto
Sheet:          https://docs.google.com/spreadsheets/d/12nKIUGHz5euDbNQPDTVECsJBNwrceRF1ymsQrIe4_ac
market_data:    ...export?format=csv&gid=68683176
sentiment_data: ...export?format=csv&gid=14812133
FRED API:       https://api.stlouisfed.org/fred/series/observations
FRED register:  https://fred.stlouisfed.org → My Account → API Keys
FMP register:   https://financialmodelingprep.com/developer
BLS register:   https://www.bls.gov/developers/api_signature_v2.htm
```

**GitHub Secrets**

| Secret Name | Used For | Status |
|---|---|---|
| FRED_API_KEY | All FRED API calls | Exists |
| GOOGLE_CREDENTIALS | Google Sheets push (full service account JSON) | Exists |
| BLS_API_KEY | BLS nonfarm payrolls detail (Phase B) | MISSING — register at bls.gov |
| FMP_API_KEY | ISM/PMI data via Financial Modeling Prep (Phase D) | MISSING — register at financialmodelingprep.com |
