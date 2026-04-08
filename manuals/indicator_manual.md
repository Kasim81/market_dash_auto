# Macro-Market Indicator Manual


> **Purpose:** Educational reference for all 68 composite indicators computed by `compute_macro_market.py`. Each entry covers the formula, data sources, economic rationale drawn from academic and practitioner research, and regime interpretation calibrated for a **6–9 month investment horizon**.
>
> **Output columns per indicator:** `raw` (the computed series), `zscore` (156-week rolling z-score), `regime` (current state label), `fwd_regime` (1–2 month trajectory based on 8-week z-score slope).
>
> Last updated: 2026-04-08

---

## Table of Contents

1. [US](#1-us)
2. [UK](#2-uk)
3. [Europe](#3-europe)
4. [Japan](#4-japan)
5. [Asia](#5-asia)
6. [Global](#6-global)
7. [FX & Commodities](#7-fx--commodities)

---

## 1. US

*US indicators span equity rotation signals, rates and credit conditions, volatility regimes, macro fundamentals, and momentum — together forming the deepest and most granular regional coverage in the library.*

---

### Equity - Growth

#### US_G1 — Cyclicals vs Defensives (Discretionary/Staples)

| | |
|---|---|
| **Formula** | `log(XLY / XLP)` |
| **Data** | SPDR S&P 500 Consumer Discretionary ETF (XLY) / SPDR S&P 500 Consumer Staples ETF (XLP) — yfinance TR |
| **Lookback** | 156-week rolling z-score |

**Economic Rationale**

Consumer Discretionary encompasses goods and services that households purchase when they feel financially secure: autos, leisure, apparel, restaurants. Consumer Staples covers non-cyclical necessities: food, beverages, household products, tobacco. The ratio therefore distils the aggregate confidence of millions of households and portfolio managers about the near-term economic outlook.

The theoretical basis is the *permanent income hypothesis* (Friedman 1957): consumption of durables and discretionaries is highly sensitive to perceived permanent income, while spending on staples is near-inelastic. When the ratio rises, it signals that consumers and investors expect rising real income and stable credit conditions over the coming quarters.

Empirically, the XLY/XLP ratio has historically been one of the highest-correlating equity ratios with the Conference Board LEI (Fama & French 1989 showed that cyclicals lead staples in returns around cycle turns). The ratio tends to peak 3–6 months ahead of the economic cycle itself, making it a useful coincident-to-slightly-leading indicator for a 6–9 month horizon.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `pro-growth` | OW discretionary, HY credit, cyclical EM |
| −1 to +1 | `neutral` | Balanced allocation |
| < −1 | `defensive` | OW staples, defensive sectors, investment grade |

---

#### US_G2 — Broader Cyclicals vs Defensives (Industrials+Financials / Utilities+Staples)

| | |
|---|---|
| **Formula** | `log((XLI + XLF) / (XLU + XLP))` — sum of prices, then ratio |
| **Data** | XLI (Industrials), XLF (Financials), XLU (Utilities), XLP (Staples) — yfinance TR |

**Economic Rationale**

This indicator broadens the US_G1 signal by adding Industrials and Financials on the cyclical side and Utilities on the defensive side. Financials are particularly important: they are leveraged directly to credit creation, NIM expansion, and loan demand — all of which reflect the *credit cycle*, a concept formalised by Minsky (1986) and more recently by Bernanke et al. in the *financial accelerator* framework.

Industrials represent capital expenditure expectations — businesses invest in equipment and infrastructure when they expect demand to persist. Utilities are regulated, bond-proxy equities: they outperform when rates fall or growth expectations deteriorate.

The combination of four sectors creates a more robust signal than US_G1 alone, less susceptible to idiosyncratic shocks in any single sector. Research by Fidelity's Sector Investing team and MSCI's factor work (2018) confirms that cyclical sector breadth is a strong predictor of subsequent 6–12 month equity returns.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `risk-on` | OW cyclicals, banks, industrials; HY credit |
| −1 to +1 | `neutral` | Balanced |
| < −1 | `late-cycle` | OW defensives, utilities, duration |

---

#### US_G3 — Banks vs Utilities

| | |
|---|---|
| **Formula** | `log(^SP500-4010 / XLU)` |
| **Data** | S&P 500 Banks Industry Group (^SP500-4010) / SPDR S&P 500 Utilities ETF (XLU) — yfinance TR |

**Economic Rationale**

A focused two-ticker version of US_G2 that isolates the *credit and rates* dimension of the cycle using the S&P 500 Banks industry group rather than broad financials (XLF). Banks are more directly leveraged to the yield curve, loan demand, and credit losses than the broader financials sector (which includes insurance, fintech, and asset management). Banks earn more when the yield curve is steep (NIM expands as they borrow short and lend long), when loan demand is strong, and when credit losses are low — all conditions associated with early and mid-cycle expansion. Utilities are explicitly rate-sensitive: their dividend yields compete with bonds, so they outperform in falling-rate or growth-scare environments.

The banks/utilities ratio is therefore a combined proxy for (1) yield curve steepness, (2) credit demand, and (3) risk appetite — making it a compact recession indicator. Borio & Lowe (2002, BIS) document that banking sector underperformance relative to defensive sectors reliably precedes credit-cycle downturns.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `risk-on` | OW financials, steepener trades |
| < −1 | `defensive` | OW utilities, long duration |

---

#### US_G5 — Technology Leadership (NASDAQ-100 vs S&P 500)

| | |
|---|---|
| **Formula** | `log(QQQ / SPY)` |
| **Data** | Invesco QQQ Trust (QQQ) / SPDR S&P 500 ETF (SPY) — yfinance TR |

**Economic Rationale**

The NASDAQ-100 is heavily concentrated in large-cap technology, semiconductors, and platform businesses — together constituting approximately 60% of the index. The QQQ/SPY ratio therefore measures the *premium* that the market is placing on technology-sector earnings growth relative to the broader economy.

A rising ratio signals that investors expect technology earnings to compound faster than the rest of the S&P 500, which historically occurs during: (1) monetary accommodation (low real rates expanding multiples), (2) strong business investment cycles (cloud, AI capex), and (3) low-volatility regimes where high-multiple stocks hold their premium.

The danger signal is a ratio that has been persistently elevated: at the extremes (z > +2), the ratio has historically coincided with late-cycle concentration, where market returns depend on a handful of names. Ned Davis Research (2021) and Goldman Sachs Portfolio Strategy have documented that extreme NASDAQ/SPY premiums are associated with elevated 12-month drawdown risk.

For a 6–9 month investor, the signal is most actionable *at the inflection* — when the ratio's z-slope turns negative (captured by `fwd_regime = deteriorating`), it often signals the beginning of a broader sector rotation that persists for 6–12 months.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `tech-led` | OW tech, growth, momentum; accept higher multiple risk |
| −1 to +1 | `neutral` | Balanced sector exposure |
| < −1 | `defensive-rotation` | Favour value, staples, small caps; reduce tech |

---

#### US_G4 — Market Breadth (Equal-Weight vs Cap-Weight S&P 500)

| | |
|---|---|
| **Formula** | `log(RSP / SPY)` |
| **Data** | Invesco S&P 500 Equal Weight ETF (RSP) / SPDR S&P 500 ETF (SPY) — yfinance TR |

**Economic Rationale**

The difference between an equal-weight and a cap-weight index of the same 500 stocks is purely attributable to the *distribution of returns* across the index. When RSP outperforms SPY, the average stock is beating the average dollar invested — indicating a broad, healthy rally with participation across size and sector. When SPY outperforms RSP, returns are driven by a small number of very large companies, indicating a *narrow rally*.

Market breadth has been a cornerstone of technical and fundamental analysis since Robert Farrell's market rules (Merrill Lynch, 1970s) and is formally related to the *Herfindahl-Hirschman Index* of market concentration. Narrow markets are fragile: when the leaders stumble, there are few other winners to offset the losses.

Ned Davis Research has documented that periods of SPY > RSP (narrow markets) have historically preceded corrections more reliably than valuation metrics alone. More recently, academic work by Maio & Santa-Clara (2021) confirms that equal-weight minus value-weight returns negatively predict future index returns, particularly over 6–12 month horizons.

For a 6–9 month investor, this indicator is particularly useful as a *risk management signal*: it does not tell you what to buy, but it tells you how much confidence to have in the continuation of a trend.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `broad-rally` | Confident in trend; buy dips broadly |
| −1 to +1 | `neutral` | Selective; focus on confirmed sectors |
| < −1 | `narrow-concentrated` | Late-cycle warning; reduce index beta, tighten stops |

---

---

### Equity - Factor (Style)

#### US_EQ_F1 — Style: Value vs Growth (Russell 1000)

| | |
|---|---|
| **Formula** | `log(IWD / IWF)` |
| **Data** | iShares Russell 1000 Value ETF (IWD) / iShares Russell 1000 Growth ETF (IWF) — yfinance TR |

**Economic Rationale**

The *value premium* — the historical tendency of cheap stocks (high book/price, high earnings yield) to outperform expensive stocks — is one of the most studied phenomena in empirical finance (Fama & French 1992, 1993). In a macro context, however, value vs growth rotation is more reliably driven by the *real rate cycle* than by static valuation alone.

Growth stocks (technology, biotech, platform companies) have long-duration cash flows heavily weighted to the distant future. Like long-duration bonds, their present value is highly sensitive to the discount rate. When real rates rise, the PV of those distant cash flows falls more than the PV of near-term value cash flows — causing growth to underperform value. When real rates fall or remain low, the opposite holds.

This relationship was quantified by Lettau & Wachter (2007, JF) and has been consistently confirmed in practitioner research by AQR, GMO, and Research Affiliates. For a 6–9 month investor, the key variable is the *direction* of real rates (US_R5), which US_EQ_F1 tends to anticipate in price.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `value-regime` | OW value, cyclicals, banks; UW long-duration growth |
| −1 to +1 | `mixed` | Factor-neutral |
| < −1 | `growth-regime` | OW quality growth, mega-cap tech; add duration |

---

#### US_EQ_F2 — Style: Value vs Growth (S&P 500)

| | |
|---|---|
| **Formula** | `log(IVE / IVW)` |
| **Data** | iShares S&P 500 Value ETF (IVE) / iShares S&P 500 Growth ETF (IVW) — yfinance TR |

**Economic Rationale**

The S&P 500 counterpart to US_EQ_F1, using the same value/growth convention (positive z = value regime). The S&P 500 growth/value split weights mega-cap technology more heavily (Apple, Microsoft, NVIDIA etc. dominate IVW) than the Russell 1000 equivalent. This means US_EQ_F2 is particularly sensitive to AI/technology cycle dynamics that may not show up as strongly in the broader Russell series. Both indicators are retained: US_EQ_F1 gives the broad style signal, US_EQ_F2 isolates the mega-cap-tech dimension.

---

### Equity - Factor (Size)

#### US_EQ_F3 — Size Cycle (Russell 2000 / Russell 1000)

| | |
|---|---|
| **Formula** | `log(IWM / IWB)` |
| **Data** | iShares Russell 2000 ETF (IWM) / iShares Russell 1000 ETF (IWB) — yfinance TR |

**Economic Rationale**

Small-cap companies are more sensitive to the *domestic* credit cycle than large-caps for several structural reasons: (1) they have less access to bond markets and rely more on bank loans; (2) they have less diversified revenue and higher operating leverage; (3) they tend to have higher variable-rate debt exposure.

The Fama-French *size factor* (SMB — small minus big) captures this risk premium, but in a regime-cycle context the ratio is more useful as a leading indicator: small caps lead large caps at cycle turns because they are more exposed to the first-derivative of credit availability. When the Fed starts cutting and credit loosens, small caps tend to re-rate sharply ahead of the broader market.

Research by Ibbotson et al. (2013) and more recently AQR (2018) confirms that small-cap leadership is concentrated in early-cycle and stimulus-driven phases. At the 6–9 month horizon, a persistent z > +1 reading often precedes a broad cyclical bull market.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `small-cap-lead` | OW small/mid cap, domestic cyclicals |
| < −1 | `large-cap-safety` | OW large-cap quality, mega-cap defensives |

---

#### US_EQ_F4 — Size Cycle S&P Proxy (Russell 2000 / S&P 500)

| | |
|---|---|
| **Formula** | `log(IWM / SPY)` |
| **Data** | IWM (Russell 2000), SPY (S&P 500) — yfinance TR |

**Economic Rationale**

Functionally identical in economic meaning to US_EQ_F3 but benchmarks the Russell 2000 against the most widely followed large-cap index rather than the Russell 1000. The S&P 500 includes a large weight in mega-cap technology and platform companies — which have near-zero correlation with the domestic credit cycle — making this ratio slightly more sensitive to the cyclical vs secular-growth distinction than the Russell 2000/1000 pair. Both indicators are retained as they can diverge at tech cycle peaks.

---

### CrossAsset - Growth

#### US_CA_G1 — Risk-On vs Risk-Off (Equities vs Treasuries)

| | |
|---|---|
| **Formula** | `log(SPY / GOVT)` |
| **Data** | SPY (SPDR S&P 500 ETF TR), GOVT (ICE BofA US Treasury Index ETF TR) |

**Economic Rationale**

The equity/Treasury ratio is the most fundamental *risk-on/risk-off* barometer in markets. In a classical *Capital Asset Pricing Model* framework, the equity risk premium (ERP) is the excess return of equities over the risk-free rate. The SPY/GOVT ratio in log-price terms tracks the *cumulative* realised ERP — rising when equities outperform (investors are willing to hold risk), falling when Treasuries outperform (flight to safety).

Ibbotson & Sinquefield (1976) documented the long-run superiority of equities over bonds, while Shiller's (1981) excess-volatility puzzle showed equity prices move far more than dividends justify — implying that most of the variation in this ratio reflects *time-varying risk premia* rather than fundamental news. For a 6–9 month investor, z-score extremes are useful: deep z < −1 readings have historically marked moments of maximum pessimism from which equity returns are above average.

---

### Credit

#### US_Cr2 — US High-Yield Credit Spread (5-Regime Framework)

| | |
|---|---|
| **Formula** | `yield(ICE BofA US High Yield Index) − US 10-Year Treasury Yield` |
| **Data** | FRED: BAMLH0A0HYM2 (HY OAS) and DGS10 (10Y Treasury) |
| **Regime trigger** | 5-regime framework based on raw spread level + z-score (see below) |

**Economic Rationale**

The HY spread measures the yield premium that sub-investment-grade (rated BB and below) corporate borrowers must pay over US Treasuries. It is one of the most sensitive real-time measures of *credit conditions* and *default risk expectations*.

Altman (1968, JF) established the theoretical link between credit spreads and default probability via Z-score models. Subsequent work by Duffie & Singleton (1999) and the Merton (1974) structural credit model formalised the spread as compensation for expected loss (probability of default × loss given default) plus a *liquidity premium* and a *risk premium*.

The regime framework uses two key structural pivots from practitioner research: **500 bps** is the pivot between normal and stressed conditions (PitchBook/LCD research shows this threshold separates default-cycle regimes); **800 bps** is a historically compelling contrarian buy level (T. Rowe Price research shows median 23.6% one-year forward return from this level, per CFA Institute analysis of post-crisis recoveries).

**Regime Classification**

| Condition | Label | Positioning |
|---|---|---|
| Spread > 800 bps or z > +2 | `opportunity` | Contrarian buy — historically strong forward returns |
| Spread > 500 bps and z > +1 | `stress` | De-risk HY; OW IG and Treasuries |
| 400–600 bps, \|z\| < 1 | `normal` | Carry regime; hold HY at benchmark |
| Spread < 400 bps, z < −0.5 | `complacent` | Below-average compensation; tighten risk |
| Spread < 300 bps, z < −1 | `frothy` | Asymmetric downside; consider UW HY |

---

#### US_Cr1 — US Investment-Grade Credit Spread (OAS)

| | |
|---|---|
| **Formula** | `BAMLC0A0CM` — ICE BofA US Corporate Master Option-Adjusted Spread |
| **Data** | FRED |

**Economic Rationale**

The IG OAS measures the spread demanded for investment-grade (BBB and above) corporate credit. IG spreads are structurally lower than HY and less volatile, reflecting the lower default probability of investment-grade issuers. However, they are highly sensitive to *liquidity conditions* and *risk appetite* in the institutional investor base (insurance companies, pension funds, foreign reserve managers all hold significant IG).

The IG spread and HY spread together paint a complete picture of the credit cycle. When HY spreads widen significantly but IG remains contained, stress is isolated to lower-quality borrowers — a typical mid-cycle signal. When both widen simultaneously (tracked by US_Cr3), financial conditions are tightening broadly.

---

#### US_Cr3 — HY–IG Spread Differential

| | |
|---|---|
| **Formula** | `BAMLH0A0HYM2 − BAMLC0A0CM` — arithmetic difference |
| **Data** | FRED |

**Economic Rationale**

This differential captures the *quality spread* — the additional compensation demanded specifically for default risk, net of liquidity and macro premia embedded in both HY and IG. When the HY–IG differential widens, it signals rising *discrimination* against lower-quality issuers, which precedes rising defaults by 6–12 months (Altman, NYU Stern annual default reports). When it narrows (compressed differential), it suggests complacency about credit quality — a signal associated with late-cycle over-extension.

---

#### US_Cr4 — HY vs Treasuries (Credit Risk)

| | |
|---|---|
| **Formula** | `log(IHYU.L / GOVT)` |
| **Data** | IHYU.L (iShares USD HY UCITS ETF) / GOVT (ICE BofA US Treasury Index ETF) |

**Economic Rationale**

The broadest total-return credit signal: HY vs. pure government bonds. This encompasses the full *credit risk premium* — compensation for default, liquidity, and economic uncertainty. Unlike the OAS measures (US_Cr2, US_Cr1) which use yield differentials, this log price ratio captures realised investor experience. During credit crises, IHYU.L falls sharply while GOVT rises — the ratio collapses, generating a strong `flight-to-quality` regime signal.

---

### Rates - Growth

#### US_R1 — Yield-Curve Slope 10Y–3M

| | |
|---|---|
| **Formula** | `T10Y3M` — FRED direct (US 10-Year CMT minus US 3-Month CMT, in percentage points) |
| **Data** | Federal Reserve H.15 release via FRED |
| **Regime trigger** | Level-based: spread < 0 overrides z-score |

**Economic Rationale**

The 10Y–3M Treasury spread is the most empirically validated recession predictor in macroeconomics. The 3-month yield is almost entirely determined by the current Federal Funds Rate, while the 10-year yield blends expectations for future short rates (the *expectations hypothesis*) with a *term premium* compensating for duration risk.

When the curve inverts (3M > 10Y), it signals that markets expect the Fed will need to *cut* rates materially in the future — which only happens in recessions. Estrella & Mishkin (1996, NBER) demonstrated that an inverted 10Y–3M curve outperforms all other single indicators in predicting US recessions 4–6 quarters ahead. The NY Fed publishes a recession probability model based solely on this spread, which has called every post-war recession.

For a 6–9 month investor, the key insight is *where you are in the inversion cycle*: (1) initial inversion → caution; (2) sustained deep inversion → de-risk; (3) re-steepening after inversion → often the buy signal for equities (the *bull steepener* precedes the early-cycle recovery). The `fwd_regime` z-slope captures the re-steepening transition.

**Regime Classification**

| Condition | Label | Positioning |
|---|---|---|
| Spread < 0 | `recession-watch` | Reduce equity beta; OW short-duration, quality |
| Spread > 0, z > +1 | `early-cycle` | OW cyclicals, extend credit, add EM |
| Spread > 0, −1 to +1 | `mid-cycle` | Balanced |
| Spread > 0, z < −1 | `late-cycle` | Reduce duration; watch for inversion |

---

#### US_R2 — Yield-Curve Slope 2s10s (FRED)

| | |
|---|---|
| **Formula** | `T10Y2Y` — FRED direct (US 10-Year CMT minus US 2-Year CMT) |
| **Data** | Federal Reserve H.15 via FRED |

**Economic Rationale**

The 2s10s curve is the market's benchmark measure of monetary policy stance vs. long-run growth expectations. The 2-year yield is highly sensitive to Fed policy expectations 1–2 years out; the 10-year reflects the longer-run nominal growth and inflation outlook.

While the 10Y–3M spread (US_R1) is the better *recession predictor*, the 2s10s spread is more widely used by traders and market participants because it is more liquid and more reactive to near-term Fed policy shifts. Reinhart & Rogoff (2009) and Campbell Harvey's original dissertation (1986) document both curves' predictive power. The 2s10s is complementary to US_R1: divergence between the two signals can identify whether the inversion is driven by Fed overtightening (3M elevated) or by collapsing long-run growth expectations (10Y falling).

---

#### US_R3 — Yield-Curve Slope 2s10s (Market)

| | |
|---|---|
| **Formula** | `^TNX (yfinance) − DGS2 (FRED)` |
| **Data** | yfinance 10Y yield level + FRED 2Y CMT |

Functionally identical to US_R1 in interpretation. Retained as a cross-check: the yfinance-sourced 10Y yield updates intraday, while FRED T10Y2Y has a 1-day publication lag. Any persistent divergence between US_R2 and US_R3 would indicate a data feed issue.

---

### Rates - Inflation

#### US_R4 — 10-Year Breakeven Inflation

| | |
|---|---|
| **Formula** | `T10YIE` — FRED direct (10-Year Treasury Inflation-Indexed Security, Break-Even Inflation Rate) |
| **Data** | FRED (Fed H.15 release) |

**Economic Rationale**

The 10-year breakeven inflation rate is derived from the difference between nominal 10-year Treasury yields and TIPS 10-year real yields. It represents the market's expectation of average CPI inflation over the next decade, and the price at which an investor is indifferent between holding nominal Treasuries and inflation-protected TIPS.

Breakeven inflation is distinct from *realised* inflation: it reflects forward expectations and can diverge significantly in periods of uncertainty. During QE cycles, breakevens were suppressed by Fed asset purchases; during supply shocks (2021–2022), they surged ahead of realised CPI. For the 6–9 month investor, the *direction* of breakevens is more important than the absolute level: rising breakevens signal inflation-pricing-in, which supports inflation-linked assets (TIPS, real estate, commodities, gold) and pressures long nominal duration.

---

### Rates

#### US_R5 — Real Rates (TIPS 10-Year Yield)

| | |
|---|---|
| **Formula** | `DFII10` — FRED direct (Market Yield on US Treasury Securities at 10-Year, Inflation-Indexed) |
| **Data** | FRED (Federal Reserve H.15 release, daily) |

**Economic Rationale**

The 10-year real interest rate is arguably the single most important macro variable for valuing long-duration assets. It is the *risk-free real discount rate* that anchors equity multiples, real estate cap rates, and gold prices — all of which can be modelled as the present value of future real cash flows.

Fisher (1930) established the decomposition of nominal rates into real rates and expected inflation. In modern macro-finance, the real rate is determined by: (1) the stance of monetary policy relative to the neutral rate (r*), (2) the term premium for holding duration, and (3) global safe-asset demand (the *global saving glut* identified by Bernanke 2005).

For equity investors, the relationship between real rates and P/E multiples is direct: the Gordon Growth Model implies P/E = 1 / (r_real + ERP − g), so rising real rates compress multiples, particularly for long-duration growth stocks (US_G5, US_EQ_F1 rotate together with US_R5). For a 6–9 month investor, the *direction* of real rates is the key variable: TIPS yields rising from negative to positive (-0.5% to +2% as in 2022) caused the most severe equity de-rating in decades.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `high-real-rates` | UW long-duration growth; OW value, short-duration; hold gold only as hedge |
| −1 to +1 | `normal` | Standard allocation |
| < −1 | `low-real-rates` | OW quality growth, duration, gold, EM carry |

---

---

#### US_R6 — Mortgage Credit Spread (Affordability Stress)

| | |
|---|---|
| **Formula** | `MORTGAGE30US − DGS10` — arithmetic difference (bps) |
| **Data** | FRED: 30-Year Fixed Mortgage Rate (MORTGAGE30US), 10-Year Treasury (DGS10) |

**Economic Rationale**

The spread between the 30-year mortgage rate and the 10-year Treasury yield reflects lender risk aversion and housing credit availability. In normal conditions, the spread runs 150–200 bps, compensating mortgage originators for prepayment risk, credit risk, and servicing costs. When the spread widens above 250 bps (as it did in 2022–2023), it signals that lenders are charging an elevated premium above risk-free rates — effectively tightening housing credit even if the Fed has stopped hiking.

The MBA Mortgage Bankers Association and the National Association of Realtors track this spread as a primary affordability indicator. Academic work by Campbell & Cocco (2015, JF) documents the direct transmission from mortgage rates to housing turnover and consumer spending via the *home equity* channel. For a 6–9 month investor, this indicator leads building permits (US_HOUS1) by 3–6 months.

---

### Volatility

#### US_V1 — VIX Term Structure (Equity Vol)

| | |
|---|---|
| **Formula** | `VIX3M − VIX` — arithmetic spread (CBOE 3-Month VIX minus CBOE VIX) |
| **Data** | yfinance: `^VIX3M`, `^VIX` |
| **Regime trigger** | Level-based: spread < 0 (inversion) triggers `stress` |

**Economic Rationale**

The VIX measures the market's 30-day implied volatility expectation for the S&P 500, derived from option prices. The VIX3M (also called the VXMT) measures the same expectation over a 3-month horizon. In normal markets, the term structure is in *contango* — 3-month vol exceeds 1-month vol because there is more uncertainty over longer horizons. The spread VIX3M − VIX is therefore normally positive.

When this spread *inverts* (VIX > VIX3M), it signals that near-term uncertainty exceeds longer-term expectations — a hallmark of *acute stress* events where investors are paying premium prices for immediate hedges. This inversion has preceded and coincided with most major market dislocations (2008 GFC, 2011 Euro crisis, 2015 China shock, 2020 COVID, 2022 rate shock).

Whaley (2009, JFM) and subsequent CBOE research documents the term structure of implied volatility as a real-time fear gauge. Carr & Wu (2006) formalise the variance risk premium embedded in VIX, showing that the premium is highest precisely during inversions.

**Regime Classification**

| Condition | Label | Positioning |
|---|---|---|
| VIX3M − VIX < 0 | `stress` | Tighten risk immediately; defensive positioning |
| Spread > 0, z < −1 | `complacency` | Normal calm; watch for sudden spike |
| Spread > 0, \|z\| ≤ 1 | `normal` | Standard risk budget |

---

#### US_V2 — Rates vs Equity Vol (MOVE/VIX Ratio)

| | |
|---|---|
| **Formula** | `log(MOVE / VIX)` |
| **Data** | yfinance: `^MOVE` (ICE BofA MOVE Index), `^VIX` |

**Economic Rationale**

The MOVE Index (Merrill Lynch Option Volatility Estimate) measures 1-month implied volatility in the US Treasury market, constructed similarly to the VIX but for rates rather than equities. The MOVE/VIX ratio therefore captures whether macro/policy uncertainty (rates volatility) is elevated relative to equity-market fear.

A high MOVE/VIX ratio — common during Fed tightening cycles and fiscal crises — indicates that rates are the dominant driver of uncertainty, not equity fundamentals. This is important for a multi-asset investor because in these environments, the traditional equity-bond diversification benefit breaks down: both assets can sell off simultaneously (as in 2022). Research by Goldman Sachs Global Investment Research and by Ilmanen (2011, *Expected Returns*) documents that equity-bond correlation flips positive during inflation regimes, precisely when MOVE/VIX is elevated.

---

### Macro

#### US_JOBS1 — Initial Jobless Claims (YoY Change)

| | |
|---|---|
| **Formula** | YoY % change of `IC4WSA` (4-week moving average of initial claims) |
| **Data** | FRED: IC4WSA (weekly, released Thursday for prior week) |
| **Lookback** | 156-week rolling z-score |

**Economic Rationale**

Initial jobless claims are the most timely labour market indicator available, published weekly with a one-week lag. The 4-week moving average (IC4WSA) smooths the well-known seasonal noise in the weekly series. As a leading indicator, claims tend to rise 2–4 weeks before nonfarm payrolls turn negative and 4–8 weeks before the unemployment rate inflects upward, giving investors advance notice of labour market deterioration.

The theoretical transmission is straightforward: a layoff wave reduces household incomes within weeks, triggering contraction in consumer spending (which accounts for approximately 70% of US GDP). Blanchard & Diamond (1990, *Quarterly Journal of Economics*) showed that the job-finding rate — closely related to claims — is the most cyclically sensitive component of unemployment dynamics. Gordon (2003) documented that the claims-to-employment ratio is among the best single-variable predictors of recession timing at 1–3 month horizons.

The YoY transformation is preferred for two reasons: (1) it eliminates seasonal distortions without requiring seasonal adjustment factors that can be revised; (2) it captures the *direction* of the labour cycle, which matters more than the absolute level. A YoY rise of 20–30% in claims has been associated with every post-war recession.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `labour-deteriorating` | Tighten risk: UW US HY and small caps; OW defensives and duration |
| −1 to +1 | `stable` | Standard allocation |
| < −1 | `labour-tight` | Labour market overheating; watch for Fed tightening response |

---

#### US_JOBS3 — Labour Market Composite

| | |
|---|---|
| **Formula** | Equal-weighted average of z-scores of: inverted `UNRATE`, `PAYEMS` YoY%, inverted `IC4WSA` |
| **Data** | FRED: UNRATE (monthly), PAYEMS (monthly), IC4WSA (weekly) |
| **Lookback** | 156-week rolling z-score of composite |

**Economic Rationale**

No single labour market series captures the full picture: unemployment is a lagging indicator, payrolls are coincident, and claims are leading. US_JOBS3 synthesises all three into a single composite score that spans the lead-coincident-lag spectrum of labour market data — mimicking how the Federal Reserve's own staff models assess labour market conditions.

The Federal Reserve's *Labour Market Conditions Index* (LMCI), developed by Hakkio & Willis (2014, *Kansas City Fed*) and extended by the Board of Governors, uses a factor model to extract a common latent state from 19 labour market indicators. US_JOBS3 implements a simplified version of the same concept using three key series, with the inversions applied so that the composite is positive when labour markets are strong and negative when weak.

Bernanke & Carey (1996, *Quarterly Journal of Economics*) demonstrated that labour market tightness is the primary transmission channel from monetary policy to inflation and growth — central banks tighten specifically to cool labour markets, and recessions begin when the cooling overshoots. For a 6–9 month investor, US_JOBS3 captures the real-time state of this channel: high composite z-score implies continued consumer spending support; low composite z-score implies deteriorating income dynamics and rising recession probability.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `labour-strong` | Supports earnings/cyclicals; watch for rate-hike risk if inflation elevated |
| −1 to +1 | `labour-balanced` | Mid-cycle allocation |
| < −1 | `labour-weak` | Defensive tilt; OW duration and quality; UW cyclicals |

---

#### US_G6 — Real Activity Composite (IP + Retail Sales)

| | |
|---|---|
| **Formula** | Equal-weighted z-score composite of: `INDPRO` 12m % change + `RSXFS` 12m % change |
| **Data** | FRED: INDPRO (Industrial Production, monthly), RSXFS (Retail Sales ex-Autos, monthly) |
| **Lookback** | 156-week rolling z-score of composite |

**Economic Rationale**

US_G6 combines the two broadest real-activity measures spanning the supply and demand sides of the US economy: industrial production (supply/manufacturing) and retail sales ex-autos (consumer demand). Together they provide a coincident composite analogous to the NBER Business Cycle Dating Committee's own primary indicators.

Industrial production (INDPRO), published by the Federal Reserve Board, covers manufacturing, mining and utilities — approximately 20% of GDP but highly cyclical and leading for corporate earnings. Bernanke (1983, *American Economic Review*) showed that industrial production is one of the first GDP components to inflect at cycle turning points. Its YoY change correlates closely with corporate earnings growth and is a core input into manufacturing PMI surveys.

Retail sales ex-autos captures the broadest consumer spending signal available on a monthly basis (Autos are excluded because they introduce high serial correlation and measurement noise). Consumer spending accounts for approximately 70% of US GDP, and its YoY trend is one of the most reliable coincident indicators of recession and expansion (Hall et al. 2010, NBER recession-dating methodology).

The composite z-score removes the need to interpret two series simultaneously, providing a single read on whether the real economy is running above or below its historical trend.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `strong-growth` | OW cyclicals and value; UW long nominal duration |
| −1 to +1 | `normal` | Standard allocation |
| < −1 | `weak-growth` | OW defensives, quality and duration |

---

#### US_HOUS1 — Housing / Building Permits *(Naturally Leading)*

| | |
|---|---|
| **Formula** | `PERMIT` — 12-month % change |
| **Data** | FRED: PERMIT (Building Permits, monthly, released ~3 weeks after month-end) |
| **Lookback** | 156-week rolling z-score |
| **Lead** | Typically leads housing starts by 1–2 months; leads GDP by 2–4 quarters |

**Economic Rationale**

Building permits are one of the most reliable leading indicators in the NBER framework — they were included in the Conference Board LEI and are published earlier than housing starts, making them the first-available signal of construction cycle direction.

The transmission mechanism is multilayered. First, housing construction has extremely high labour and material intensity — a single-family home creates approximately 3 person-years of employment across construction, materials and professional services. Second, new housing generates significant downstream spending: buyers purchase appliances, furniture and home improvement goods (the IKEA/Home Depot multiplier). Third, rising construction activity raises land and existing home prices, increasing household net worth and supporting the *wealth effect* on consumption (Case, Quigley & Shiller 2005, *Brookings Papers*).

The interest-rate sensitivity of permits is also why US_HOUS1 is *naturally leading* for monetary policy transmission: permit applications collapse within months of rate rises (the 2022 experience saw permits fall 25% within 6 months of the first Fed hike) and recover months before the broader economy when rate cuts arrive. The current reading therefore already captures conditions 2–4 months ahead of when the impact will appear in GDP.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `housing-expanding` | OW REITs, homebuilders, building materials |
| −1 to +1 | `neutral` | Standard allocation |
| < −1 | `housing-contracting` | UW REITs vs broad equity; OW defensives and duration |

---

#### US_M2 — M2 Money Supply Growth (Liquidity Indicator)

| | |
|---|---|
| **Formula** | `M2SL` — YoY % change |
| **Data** | FRED: M2SL (monthly, revised quarterly) |
| **Lookback** | 156-week rolling z-score |

**Economic Rationale**

M2 money supply growth is the broadest practical measure of monetary liquidity available in real time. M2 includes currency, demand deposits, savings accounts, money market funds and small time deposits — the pool of readily deployable financial capital in the economy. Its YoY growth rate captures whether the banking system and Fed are expanding or contracting the available funding for investment, consumption and asset purchases.

The *quantity theory of money* (Fisher 1911; Friedman & Schwartz 1963, *A Monetary History of the United States*) established that sustained changes in the money supply lead to changes in nominal spending 12–24 months later. While the simple quantity theory has been challenged by modern monetary economics, the empirical relationship between M2 growth and subsequent asset returns remains significant: Asness (1997) and DeSantis & Gérard (1997) documented that broad money growth is a statistically significant predictor of equity and bond returns over 6–18 month horizons.

More directly relevant for markets, M2 contraction has historically been associated with financial stress: the 2022–23 M2 contraction (−4% YoY — the first since the 1930s) preceded a significant tightening of financial conditions, P/E multiple compression and EM outflows. Conversely, the post-2020 M2 expansion (+27% YoY peak) directly fuelled asset price inflation before the 2022 correction. For a 6–9 month investor, accelerating M2 growth is a permissive environment for risk assets; decelerating or negative M2 growth is a structural headwind.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `abundant-liquidity` | Tolerant of equity/credit/EM risk; OW gold if inflation rising |
| −1 to +1 | `neutral` | Standard allocation |
| < −1 | `tight-liquidity` | OW quality, short duration; UW EM/HY; reduce leverage |

---

#### US_JOBS2 — JOLTS Labour Market Tightness *(Naturally Leading)*

| | |
|---|---|
| **Formula** | `JTSJOL / UNEMPLOY` — ratio of job openings to unemployed persons |
| **Data** | FRED: JTSJOL (monthly JOLTS), UNEMPLOY (monthly) |
| **Lookback** | 156-week rolling z-score |
| **Lead** | ~2 months ahead of reported unemployment; ~3–4 months ahead of wage inflation |

**Economic Rationale**

The job openings–to–unemployed ratio is the canonical measure of **labour market tightness** developed from search-and-matching theory. When openings exceed unemployed persons (ratio > 1), every unemployed worker notionally has more than one available job, implying strong wage bargaining power and accelerating wage growth.

The theoretical framework is the Diamond-Mortensen-Pissarides (DMP) search model (Pissarides 1985, *Review of Economic Studies*; Mortensen & Pissarides 1994, *Review of Economic Studies*; both authors received the Nobel Prize in 2010). The DMP model predicts that the vacancy-unemployment ratio is a sufficient statistic for the tightness of the matching market: as it rises, workers find jobs faster, wages rise, and the employment rate increases. Shimer (2005, *American Economic Review*) further showed that vacancies are 10× more volatile than unemployment across the cycle — making the ratio a more sensitive early signal of cycle turns than unemployment alone.

Practically, the JOLTS ratio leads reported unemployment by approximately 2 months and leads the Employment Cost Index (ECI, the broadest wage measure) by 3–4 months, making it *naturally leading*: the current reading already embeds the signal about labour market conditions 1–2 months ahead. This is why US_JOBS2 is included in the `NATURALLY_LEADING` set, and its `fwd_regime` is tagged `[leading]`.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `labour-tight` | Wage pressure; consumer resilient; watch for inflation overshoot |
| −1 to +1 | `balanced` | Equilibrium labour market; mid-cycle |
| < −1 | `labour-slack` | Unemployment rising; consumer vulnerable; easing bias |

---

### Macro - Survey

#### US_ISM1 — ISM Manufacturing New Orders *(Naturally Leading)*

| | |
|---|---|
| **Formula** | `NAPMOI` — ISM New Orders Index level (published monthly by ISM) |
| **Data** | FRED: NAPMOI (monthly, released first business day after month-end) |
| **Lookback** | Regime based on level thresholds (50 = neutral, 52/48 boundaries); z-score supplemental |
| **Lead** | Leads industrial production by approximately 6 weeks |

**Economic Rationale**

The ISM Manufacturing New Orders Index is the single most closely watched sub-component of the ISM Manufacturing PMI. It is a diffusion index — the percentage of companies reporting rising new orders minus those reporting falling orders, plus 50 — and is constructed from a monthly survey of approximately 300 purchasing managers across 18 industries.

New orders are inherently *forward-looking*: a purchasing manager reports that new orders are rising before the actual production to fulfil those orders has begun, let alone before output data is measured and published. This makes the series *naturally leading*: the current reading already projects conditions 1–2 months ahead. Marquette (1992, *Business Economics*) showed that ISM New Orders leads the production component by approximately 6 weeks and leads industrial production (INDPRO) by 1–3 months.

Gordon (1990, *Business Cycles, Indicators and Forecasting*, NBER) and more recently Dueker (2005, *Federal Reserve Bank of St. Louis*) demonstrated that ISM New Orders crossing the 50 boundary is one of the most reliable coincident-to-leading markers of cycle transitions. The 52 threshold (slightly above neutral) is preferred to 50 for `expansion` labelling because the ISM survey exhibits slight upward drift — historically, the manufacturing sector grows when new orders are at or above 52 rather than exactly 50. The 48 threshold (below neutral but not sharply contractionary) marks the transition to `contraction`.

**Regime Classification**

| Level | Label | Positioning |
|---|---|---|
| > 52 | `ism-expansion` | Supports industrials, materials and HY carry |
| 48–52 | `ism-neutral` | Transition zone; directional z-score trend guides positioning |
| < 48 | `ism-contraction` | OW defensives, IG, Treasuries; reduce industrial/commodity exposure |

---

---

### Mmtm - Equity

#### M1 — US Equity Trend (S&P 500 vs 40-Week SMA)

| | |
|---|---|
| **Formula** | `log(SPY / SMA_40w(SPY))` |
| **Data** | SPDR S&P 500 ETF (SPY) — yfinance |
| **Lookback** | 156-week rolling z-score of distance from SMA |

**Economic Rationale**

M1 is the foundational trend-following rule for US equities: hold when price is above its long-term moving average, exit when below. The empirical case for this rule is one of the most extensively documented in quantitative finance.

Faber (2007, *JIAM*) showed that a 10-month SMA rule (equivalent to the 40-week SMA used here) applied to the S&P 500 from 1901–2006 produced a Sharpe ratio of approximately 0.77 versus 0.31 for buy-and-hold, while reducing maximum drawdown from −83% to −25%. The key mechanism is *persistence of momentum*: bear markets and bull markets last 12–36 months on average, far longer than can be explained by rational Bayesian updating — implying systematic under-reaction to macro fundamentals.

The theoretical underpinning comes from the *Grossman-Stiglitz paradox* (1980): if markets were perfectly efficient, no one would pay for information. The existence of persistent trends suggests that the marginal investor processes macro information with a lag. Trend-following exploits this lag. Daniel, Hirshleifer & Subrahmanyam (1998) formalise this as investor overconfidence bias — self-attribution causes investors to anchor too long on prior narratives, generating autocorrelated returns.

The 40-week window is the practitioner consensus for *slow trend* — long enough to filter noise and short-term corrections, short enough to exit bear markets before maximum damage. For a 6–9 month investment horizon, M1 acts as the primary binary filter: below-trend SPY (M1 regime = `trend-down`) is a signal to systematically reduce gross risk.

**Regime Classification**

| z-score / raw | Label | Positioning |
|---|---|---|
| log ratio > 0 (price above SMA) | `trend-up` | Risk-on for US equities; standard equity allocation |
| log ratio < 0 (price below SMA) | `trend-down` | Risk-off; underweight US equities, reduce gross risk |

---

### Mmtm - CrossAsset

#### M2 — Multi-Asset Trend Breadth (5-Asset Faber TAA)

| | |
|---|---|
| **Formula** | Fraction of {SPY, URTH, GOVT, VNQ, DBC} above their 40-week SMA |
| **Data** | SPY, iShares MSCI World (URTH), iShares US Treasury Bond (GOVT), Vanguard Real Estate (VNQ), Invesco DB Commodity (DBC) — yfinance |
| **Lookback** | 156-week rolling z-score of breadth fraction |

**Economic Rationale**

M2 extends the single-asset trend rule of M1 into a **diversified trend breadth** framework across five major asset classes: US equities, global equities, bonds, real estate and commodities. The indicator answers: across the investable universe, how many asset classes are in uptrends simultaneously?

The theoretical basis is Mebane Faber's *Quantitative Approach to Tactical Asset Allocation* (2007), which showed that applying a 10-month SMA rule to five asset classes and holding only those in uptrend reduced annual standard deviation from 10% to 7% while maintaining the same expected return. The key insight is that asset class trends are *partially independent*: commodities can be in uptrend while bonds are in downtrend, meaning breadth captures diversified macro regime information that no single-asset rule can.

From a macro perspective, high trend breadth (4–5 assets above SMA) tends to occur in reflation phases or mid-cycle expansions where fiscal stimulus, accommodative monetary policy and earnings growth all contribute simultaneously. Low trend breadth (0–2 assets above SMA) is characteristic of late-cycle tightenings, recessions or financial crises. The reading of 3/5 often occurs at cycle inflection points — directional signal from other indicators becomes important.

For a multi-asset portfolio manager, M2 is a *portfolio heat* indicator: when all five asset classes trend up, the macro environment rewards broad risk-taking; when most trend down, capital preservation dominates.

**Regime Classification**

| Breadth fraction | Label | Positioning |
|---|---|---|
| ≥ 0.6 (3+ assets above SMA) | `risk-on` | Full broad-asset risk allocation |
| 0.4–0.6 (2–3 assets) | `mixed` | Selective; favour highest-trend-strength assets |
| ≤ 0.4 (0–2 assets above SMA) | `risk-off` | Capital preservation; move to cash or short-duration |

---

#### M3 — Dual Momentum (Antonacci Equity/Bond Regime)

| | |
|---|---|
| **Formula** | `max(12m_return(SPY), 12m_return(URTH)) − 12m_return(SHY)` |
| **Data** | SPY (US equity), URTH (global equity), SHY (1–3yr Treasuries as cash proxy) — yfinance |
| **Lookback** | 156-week rolling z-score of excess return signal |

**Economic Rationale**

M3 implements Gary Antonacci's *Dual Momentum* framework (2014, *McGraw-Hill*), which combines two momentum signals:

1. **Absolute momentum (time-series)**: Is the best-performing equity index beating cash? If not, shift to bonds — this is the primary risk-off trigger.
2. **Relative momentum (cross-sectional)**: Between US equities (SPY) and global equities (URTH), which has higher 12-month return? This determines the equity allocation when the absolute signal is positive.

The theoretical foundations span two literatures. *Absolute momentum* exploits the time-series autocorrelation documented by Moskowitz, Ooi & Pedersen (2012) in their *time-series momentum* paper — across 58 futures markets, past 12-month return strongly predicts next-month return with a t-stat > 5. *Relative momentum* exploits the cross-sectional momentum effect documented by Jegadeesh & Titman (1993, *Journal of Finance*) — the single most replicated finding in empirical asset pricing.

For a 6–9 month investor, M3 provides a principled answer to two allocation questions simultaneously: whether to hold equities at all, and whether to tilt toward US or global equities. Because the 12-month lookback spans a full business cycle quarter, it captures sustained directional shifts rather than short-term noise. Antonacci documented that dual momentum strategies outperformed buy-and-hold by 3–5% annually from 1974–2013 with lower drawdowns, primarily by avoiding the worst of bear markets.

**Regime Classification**

| Signal | Label | Positioning |
|---|---|---|
| Both equity returns < SHY return | `bond-regime` | Exit equities; shift to intermediate Treasuries |
| max(SPY, URTH) > SHY, SPY > URTH | `US-equity-regime` | OW US equities vs global |
| max(SPY, URTH) > SHY, URTH > SPY | `global-equity-regime` | OW global/non-US equities vs US |

---

### Mmtm - Credit

#### M4 — High Yield Trend with Spread Override

| | |
|---|---|
| **Formula** | `log(BAMLHYH0A0HYM2TRIV / SMA_40w(BAMLHYH0A0HYM2TRIV))`; forced to −1 if HY OAS (BAMLH0A0HYM2) > 600 bps |
| **Data** | FRED: ICE BofA US HY Total Return Index, ICE BofA US HY Option-Adjusted Spread |
| **Lookback** | 156-week rolling z-score |

**Economic Rationale**

M4 applies the same trend-following logic as M1 to the **high yield credit market** rather than equities. The distinction is important: HY total return combines price appreciation, coupon income and spread compression — meaning a trend-following signal on HY total return captures the credit cycle more directly than an equity signal.

The academic basis comes from Ilmanen (2011, *Expected Returns*, Chapter 15): HY credit has historically offered a substantial risk premium — approximately 2–3% above investment grade — but with significant left-tail risk during credit events. Tactical allocation based on price trend (above/below 200-day or 40-week SMA) has been shown to dramatically reduce drawdowns: Asness, Moskowitz & Pedersen (2013) document that trend momentum in credit markets has a Sharpe ratio of ~0.6 independently from equity momentum.

The **600 bps spread override** is a fundamental safety valve. Empirically, OAS spreads above 600 bps have historically corresponded to high default-cycle periods (e.g. 2002, 2009, 2020). When spreads exceed this threshold, the recovery from price trend signals is unreliable because forced selling, liquidity spirals and default clustering distort the price signal. Altman's (2002) research on default cycles shows that above-600-bps environments are associated with speculative-grade default rates exceeding 8%, making trend-following unreliable as a timing tool. The override provides a hard risk-management floor that cannot be over-ridden by a false positive trend reading.

**Regime Classification**

| Condition | Label | Positioning |
|---|---|---|
| Log ratio > 0 AND OAS ≤ 600 bps | `carry-regime` | Hold HY; collect carry |
| Log ratio < 0 OR OAS > 600 bps | `stress-regime` | Exit HY; move to short-duration Treasuries |

---

### Mmtm - Volatility

#### M5 — VIX Regime Filter (13-Week vs 52-Week MA)

| | |
|---|---|
| **Formula** | `log(VIX_13w_MA / VIX_52w_MA)` |
| **Data** | CBOE VIX Index (^VIX) — yfinance, resampled to weekly |
| **Lookback** | 156-week rolling z-score |

**Economic Rationale**

M5 uses the *relative level* of short-term versus long-term implied volatility to determine whether the equity market's volatility regime is expanding or contracting. Unlike M1–M4 which use price trend, M5 uses the *second moment* of equity returns — implied volatility — as the regime signal.

The theoretical foundation draws on Whaley (1993), who introduced VIX as the market's *fear gauge*, and Carr & Wu (2006), who documented that implied volatility contains information about future realised volatility beyond what can be extracted from historical returns alone. The critical insight for M5 is mean reversion of volatility (Bollerslev 1986, GARCH): volatility is not independently distributed but *clusters*, with prolonged low-vol and high-vol regimes. The ratio of short-term to long-term MA therefore captures whether the current vol cluster is in an expanding or contracting phase.

The specific window choice — 13 weeks (~3 months) versus 52 weeks (1 year) — is calibrated for the 6–9 month investment horizon. The 52-week denominator anchors to the full recent business cycle and provides a stable mean, preventing short-term spikes from triggering false alarms. The 13-week numerator is responsive enough to capture genuine regime shifts (post-crisis vol compression, pre-crisis vol expansion) without over-reacting to single-event spikes. When log(13w/52w) < 0, short-term vol is running below its annual mean: conditions are conducive to equity risk-taking. When > 0, vol is trending above its annual mean: markets are pricing in persistent uncertainty, and risk reduction is warranted.

Ang, Hodrick, Xing & Zhang (2006, *Journal of Finance*) showed that high-idiosyncratic-vol stocks underperform low-idiosyncratic-vol stocks in the following month — the "low-vol anomaly." M5 operationalises this as a systematic overlay: when the vol regime is unfavourable, even strong trend and fundamental signals should be discounted.

**Regime Classification**

| log ratio | Label | Positioning |
|---|---|---|
| < 0 (13w MA < 52w MA) | `vol-compressing` | Equity-friendly; add equity risk, reduce hedges |
| > 0 (13w MA > 52w MA) | `vol-expanding` | Defensive; reduce equity exposure, add hedges, raise cash |

---

---

*End of Section 1 — US (34 indicators: US_G1, US_G2, US_G3, US_G5, US_G4, US_EQ_F1, US_EQ_F2, US_EQ_F3, US_EQ_F4, US_CA_G1, US_Cr2, US_Cr1, US_Cr3, US_Cr4, US_R1, US_R2, US_R3, US_R4, US_R5, US_R6, US_V1, US_V2, US_JOBS1, US_JOBS3, US_G6, US_HOUS1, US_M2, US_JOBS2, US_ISM1, M1, M2, M3, M4, M5)*

---

## 2. UK

*UK indicators capture the domestic vs global equity rotation, credit conditions, rate dynamics relative to Europe, and inflation expectations — reflecting the UK's unique post-Brexit macro environment.*

---

### Equity - Growth

#### UK_G1 — UK Domestic vs Global (FTSE 250 / FTSE 100)

| | |
|---|---|
| **Formula** | `log(MCX.L / ISF.L)` — FTSE 250 ETF / FTSE 100 ETF |
| **Data** | iShares FTSE 250 ETF (MCX.L) / iShares Core FTSE 100 ETF (ISF.L) — yfinance |
| **Lookback** | 156-week rolling z-score |

**Economic Rationale**

The FTSE 250/FTSE 100 ratio is one of the cleanest available signals for UK domestic economic conditions versus global macro. The FTSE 100 is dominated by globally-oriented mega-caps — energy majors (Shell, BP), mining companies (Rio Tinto, Anglo American), banks with large international operations (HSBC, Standard Chartered), and consumer staples (Unilever, Diageo) — approximately 75% of FTSE 100 revenues are generated outside the UK. In contrast, the FTSE 250 is predominantly composed of UK-domestic businesses: real estate, regional banks, retailers, media and professional services.

This structural composition difference makes the ratio a powerful lens on relative confidence in UK domestic demand versus global earnings. When sterling weakens (as post-Brexit), the FTSE 100 typically outperforms because its foreign revenues are worth more in GBP terms. When sterling strengthens and the UK domestic economy grows, the FTSE 250 tends to lead. The ratio therefore also carries an implicit GBP signal.

Dimson, Marsh & Staunton (2002) noted the UK equity market's historically high international exposure relative to other developed markets, which is why a domestic-vs-global decomposition provides more information in the UK than in most other countries. For post-Brexit UK, the ratio has taken on additional significance as a gauge of trade policy confidence and Bank of England credibility.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `uk-domestic-strength` | OW UK mid/small caps, domestic consumer, housebuilders |
| −1 to +1 | `neutral` | Balanced UK allocation |
| < −1 | `uk-global-preference` | OW FTSE 100 mega-caps; reduce UK-domestic exposure |

---

### Credit

#### UK_Cr1 — UK Credit Conditions (Corporates vs Gilts)

| | |
|---|---|
| **Formula** | `log(SLXX.L / IGLT.L)` — iShares Core GBP Corporate Bond ETF / iShares UK Gilt ETF |
| **Data** | SLXX.L, IGLT.L — yfinance |
| **Lookback** | 156-week rolling z-score |

**Economic Rationale**

UK_Cr1 measures the relative performance of GBP investment-grade corporate bonds versus UK government gilts — the UK equivalent of the US investment-grade credit spread signal. When corporates outperform gilts, it signals that investors are willing to accept lower incremental yield for UK credit risk; the financial conditions environment is supportive. When gilts outperform, it signals a flight to safety within the UK fixed income market.

The UK corporate bond market is smaller and less liquid than the US market, which means UK_Cr1 tends to move more sharply at inflection points and can lead equity market stress. Longstaff & Schwartz (1995, *Journal of Finance*) showed that corporate–government spread dynamics are driven by both default risk and liquidity premiums, with the liquidity component dominating during stress — a feature particularly pronounced in the GBP corporate market.

Post-Brexit, UK corporate spreads have also incorporated a structural UK-specific risk premium absent from EUR or USD corporate markets: sterling liquidity risk, UK political risk, and the reduced depth of the GBP investor base. UK_Cr1 therefore serves as both a domestic credit conditions indicator and a barometer of UK-specific macro risk relative to the global credit cycle.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `uk-credit-appetite` | GBP corporates outperforming; supportive of UK equities and risk |
| −1 to +1 | `neutral` | Standard UK credit allocation |
| < −1 | `uk-flight-to-quality` | Reduce GBP corporates; OW gilts; caution on UK risk assets |

---

### Rates - Growth

#### UK_R1 — UK–Germany 10-Year Spread (Gilt–Bund)

| | |
|---|---|
| **Formula** | `UK 10Y Gilt Yield − Germany 10Y Bund Yield` |
| **Data** | FRED: IRLTLT01GBM156N (UK 10Y) − IRLTLT01DEM156N (Germany 10Y) |
| **Lookback** | 156-week rolling z-score |

**Economic Rationale**

The UK–Germany 10-year yield spread distils three distinct macro signals into a single number: (1) relative inflation expectations (UK has historically run higher inflation than Germany); (2) relative fiscal risk (UK deficit dynamics vs German Schuldenbremse fiscal rule); and (3) monetary policy divergence between the Bank of England and ECB.

During normal periods, the spread reflects the structural inflation and growth premium of the UK over Germany — typically 50–150 bps. When the spread widens sharply above historical norms, it signals that UK-specific risk is being priced: fiscal credibility concerns (as in the 2022 Truss mini-budget, when the gilt–bund spread spiked 100 bps in days, forcing BoE intervention), inflation overshoot, or BoE policy lag risk. Conversely, a compressed spread can signal relative UK macro weakness or Eurozone stress.

Blanchard & Summers (1984) showed that long-term yield differentials between developed countries embed both current and expected future short-rate differentials — meaning the gilt–bund spread also captures expectations about the future BoE/ECB policy divergence path over 2–5 years. For a multi-asset investor, sharp moves in UK_R1 are often early warnings of GBP volatility and UK equity risk repricing.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `uk-risk-premium` | Caution on long gilts vs Bunds; expect GBP weakness vs EUR |
| −1 to +1 | `normal` | Standard UK/Germany allocation |
| < −1 | `uk-relative-strength` | Gilts attractive vs Bunds; potential GBP strength |

---

### Rates - Inflation

#### UK_R2 — UK Inflation Expectations Proxy (Linker/Gilt Ratio)

| | |
|---|---|
| **Formula** | `log(INXG.L / IGLT.L)` — iShares UK Inflation-Linked Gilt ETF / iShares UK Gilt ETF |
| **Data** | INXG.L, IGLT.L — yfinance |
| **Lookback** | 156-week rolling z-score |

**Economic Rationale**

The ratio of inflation-linked gilt (linker) prices to nominal gilt prices is a market-based proxy for UK inflation expectations and real rate dynamics. When linkers outperform nominal gilts, the market is pricing rising inflation breakevens or falling real rates — both signals that the inflation-adjusted return on nominal bonds is declining, a headwind for long-duration fixed income.

The theoretical basis comes from the Fisher (1930) decomposition: nominal yield = real yield + expected inflation + term premium. The linker/gilt price ratio implicitly captures the inflation component: linkers pay a real coupon plus CPI uplift, so they outperform nominal gilts when inflation expectations rise or when real rates fall. This mirrors the TIPS-based US_R5 and US_R4 indicators but uses the ETF price ratio rather than FRED yield data, since UK real yield data availability on FRED is limited.

Post-Brexit, UK inflation dynamics have been structurally different from the Eurozone: UK CPI peaked at 11.1% in October 2022, driven by energy dependency and sterling weakness — the highest level among major developed economies. The Bank of England's (BoE) dual mandate complication — inflation control versus financial stability — makes the linker/gilt ratio a particularly important signal for UK rate risk and gilt market positioning.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `uk-inflation-elevated` | UW long gilts; OW UK real assets, inflation-linked bonds, commodities |
| −1 to +1 | `neutral` | Standard UK fixed income |
| < −1 | `uk-disinflation` | OW long gilts and duration; UW inflation-linked |

---

*End of Section 2 — UK (4 indicators: UK_G1, UK_Cr1, UK_R1, UK_R2)*

---

## 3. Europe

*European indicators cover equity leadership signals, credit conditions, peripheral sovereign risk, and OECD-based leading indicators — capturing the Eurozone's distinct policy cycle and structural dynamics.*

---

### Equity - Growth

#### EU_G3 — European Cyclicals vs Defensives

| | |
|---|---|
| **Formula** | `log((EXV1.DE + EXH1.DE + EXV3.DE) / (EXV2.DE + EXH3.DE))` |
| **Data** | STOXX Europe 600 sector ETFs: Industrials, Banks, Technology vs Utilities, Consumer Staples — yfinance |
| **Lookback** | 156-week rolling z-score |

**Economic Rationale**

EU_G3 is the European analogue of US_G1/G2: relative performance of cyclical sectors (industrials, banks, technology) versus defensive sectors (utilities, consumer staples) as a real-time market-based assessment of the European growth outlook.

The choice of European Banks as a cyclical component is particularly important and differs from the US construction. European banks are more directly tied to the sovereign credit cycle than US banks: their balance sheets carry significant sovereign bond holdings, and their lending spreads respond directly to ECB policy and peripheral sovereign stress (EU_R1). When banks outperform defensives in Europe, it signals improving credit conditions, a steepening yield curve and diminishing tail risk — all supportive of the broader European growth narrative.

Fama & French (1989) showed that cyclical-to-defensive spread returns predict future economic conditions across markets, not just the US. Dimson, Marsh & Staunton (2002, *Triumph of the Optimists*) extended this analysis to European markets, confirming that sector rotation signals are robust across the UK, Germany and France. The European cycle is also highly sensitive to global trade volumes — particularly Chinese demand for German capital goods — making EU_G1 a dual signal for both European domestic conditions and global goods cycle strength.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `pro-growth-europe` | OW European cyclicals, financials, industrials |
| −1 to +1 | `neutral` | Balanced European allocation |
| < −1 | `defensive-europe` | OW European utilities, staples; reduce European bank exposure |

---

#### EU_G2 — Eurozone vs US Equity Leadership

| | |
|---|---|
| **Formula** | `log(FEZ / SPY)` — Euro Stoxx 50 ETF / S&P 500 ETF (both in USD) |
| **Data** | SPDR Euro Stoxx 50 ETF (FEZ) / SPDR S&P 500 ETF (SPY) — yfinance |
| **Lookback** | 156-week rolling z-score |

**Economic Rationale**

EU_G2 measures relative equity leadership between the Eurozone and the United States — one of the most important regional allocation decisions in a global multi-asset portfolio.

The drivers of Eurozone-vs-US relative performance are well-documented in the academic literature on international equity premium differentials. Solnik (1974, *Journal of Finance*) established that international diversification reduces portfolio risk precisely because national equity cycles diverge — the Eurozone and US cycles correlate at approximately 0.75 over rolling 3-year periods but can diverge sharply at cycle inflection points. Asness, Moskowitz & Pedersen (2013) showed that cross-country equity momentum is one of the most persistent and risk-adjusted-efficient factors in international investing.

Key structural drivers of Eurozone outperformance phases include: (1) EUR appreciation relative to USD (foreign earnings accrete in USD terms); (2) China stimulus (Eurozone, particularly Germany, has high export exposure to China capital goods demand); (3) ECB accommodation combined with Eurozone fiscal expansion (rare but powerful, as in 2021 and post-2023 fiscal plans); (4) relative earnings valuation — the Eurozone has historically traded at a 20–30% P/E discount to the US, creating mean-reversion opportunities. US dominance phases tend to coincide with strong-dollar regimes, US tech cycle leadership and European political stress.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `eurozone-outperform` | OW Eurozone vs US; hedge USD/EUR to capture local-currency return |
| −1 to +1 | `neutral` | Balanced regional allocation |
| < −1 | `us-dominance` | OW US large-cap; reduce Eurozone equity weight |

---

#### EU_G4 — EUR Macro Composite (EUR/USD + European Cyclicals)

| | |
|---|---|
| **Formula** | Average z-score of `log(EURUSD=X)` and `log(EXV1.DE / EXV2.DE)` (European industrials/utilities) |
| **Data** | EUR/USD spot (EURUSD=X) + STOXX Europe 600 Industrials/Utilities ratio — yfinance |
| **Lookback** | 156-week rolling z-score of composite |

**Economic Rationale**

EU_G4 combines two complementary signals — the EUR exchange rate and European sector rotation — into a composite that distinguishes genuine Eurozone macro strength from currency-only moves. This design choice is deliberate: EUR appreciation alone can occur for reasons unrelated to European growth (e.g. USD weakness, safe-haven flows during non-European crises), but EUR appreciation *combined with European cyclicals outperforming defensives* is a stronger signal that Eurozone fundamentals are genuinely improving.

The EUR is the second most important reserve currency globally and reflects the aggregate macro credibility of the Eurozone — fiscal discipline, ECB policy, and trade competitiveness. Frankel & Rose (1995, *Journal of International Economics*) documented that currency strength in export-oriented economies correlates with export-driven growth cycles; Obstfeld & Rogoff (1996, *Foundations of International Macroeconomics*) formalised the link between terms-of-trade improvement and currency appreciation for industrial exporters like Germany.

The industrial/utilities sector component captures domestic capex and credit cycle conditions within Europe, filtering out external demand effects. When both legs of EU_G4 are positive simultaneously — EUR strengthening AND European cyclicals leading defensives — the composite provides a high-conviction signal that European equity risk is well-compensated for the 6–9 month horizon.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `eurozone-macro-strong` | OW European equities and EUR; supportive of export-linked cyclicals |
| −1 to +1 | `neutral` | Balanced European macro view |
| < −1 | `eurozone-under-strain` | UW European cyclicals; hedge EUR exposure; favour core govts |

---

---

#### EU_G1 — Eurozone vs Global Equities

| | |
|---|---|
| **Formula** | `log(EZU / URTH)` — iShares MSCI Eurozone ETF / iShares MSCI World ETF (both USD) |
| **Data** | EZU, URTH — yfinance |
| **Lookback** | 156-week rolling z-score |

**Economic Rationale**

EU_G1 broadens the Eurozone comparison from US-only (EU_G2) to the full global developed-market universe. This distinction matters: Eurozone outperformance relative to the US (EU_G2 positive) can coexist with Eurozone underperformance relative to MSCI World if Japan, UK or other developed markets are simultaneously strong. EU_G1 therefore answers the regional allocation question from the perspective of a globally diversified investor.

The MSCI World benchmark (proxied by URTH) covers 23 developed markets with approximately 70% US weight, meaning EU_G1 is a less US-centric comparison than EU_G2. When EU_G1 is positive, Eurozone equities are genuinely outperforming the blended global developed market — capturing not just EUR/USD dynamics but also European fundamentals versus the broader international cycle.

For a 6–9 month investor constructing a MSCI World-based equity allocation, EU_G1 provides the primary signal for whether to overweight or underweight European equities relative to the benchmark. A sustained positive z-score of EU_G1 combined with a positive EU_G3 (European cyclicals leading) and a compressed EU_R1 (BTP-Bund spread) constitutes a high-conviction Eurozone overweight signal.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `eurozone-outperform` | OW European equities vs global benchmark; supportive of EUR |
| −1 to +1 | `neutral` | Benchmark-weight Europe |
| < −1 | `eurozone-underperform` | UW Europe vs global; favour US/Japan/EM alternatives |

---

### Credit

#### EU_Cr1 — Euro Corporate vs Government Spread

| | |
|---|---|
| **Formula** | `yield(ICE BofA Euro Corporate Index) − yield(ICE BofA Euro Government Index)` |
| **Data** | FRED: BAMLHE00EHY0EY (Euro HY OAS) and BAMLHE4XEHYSIS (Euro IG OAS) — arithmetic difference |
| **Lookback** | 156-week rolling z-score |

**Economic Rationale**

EU_Cr1 is the European equivalent of US_Cr2 (HY spread): the spread between corporate bond yields and risk-free government yields captures the aggregate risk premium demanded for Euro corporate credit. This spread is one of the broadest and most liquid financial conditions indicators for the Eurozone economy.

The credit channel of monetary policy in Europe is particularly important because European companies are far more bank-dependent than US companies: approximately 70–80% of Eurozone corporate financing comes from bank loans versus approximately 40% in the US. Bank lending rates closely track the corporate bond market's risk premium signal — when EU_Cr1 widens, it signals tighter bank lending conditions, which feed through to investment, hiring and production with a 2–4 quarter lag (ECB Lending Survey research, Altunbas et al. 2010, *Journal of Banking & Finance*).

Gilchrist & Zakrajšek (2012, *American Economic Review*) developed the excess bond premium (EBP) framework, showing that corporate spread widening beyond what can be explained by expected defaults is the most powerful predictor of future real activity — more powerful than the yield curve alone. EU_Cr1 captures a similar signal for the Eurozone: widening that exceeds the credit cycle's default-justified level indicates financial conditions tightening beyond fundamentals, a regime shift requiring defensive positioning.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `euro-credit-stress` | UW Euro corporate bonds; OW core government bonds (Bunds) |
| −1 to +1 | `normal` | Standard allocation |
| < −1 | `compressed-spreads` | Watch for late-cycle reach-for-yield; be cautious adding credit risk |

---

### Rates - Growth

#### EU_R1 — BTP–Bund Spread (Peripheral Sovereign Stress)

| | |
|---|---|
| **Formula** | `Italy 10Y Yield − Germany 10Y Bund Yield` |
| **Data** | FRED: IRLTLT01ITM156N − IRLTLT01DEM156N |
| **Lookback** | 156-week rolling z-score; raw level override at 2.5% |

**Economic Rationale**

The BTP–Bund spread is the defining gauge of Eurozone fiscal fragmentation risk and ECB credibility. Italy is the critical peripheral sovereign because it is the third-largest Eurozone economy and has the highest debt-to-GDP ratio (~140%) among major Eurozone members, making it the tail-risk node in the Eurozone system.

The academic framework is the *sovereign debt crisis* literature: De Grauwe (2011, *CEPS*) argued that Eurozone sovereigns face a structural vulnerability absent in countries with their own central bank — they cannot unilaterally guarantee liquidity for their own debt, making self-fulfilling crisis equilibria possible. Arghyrou & Kontonikas (2012, *Journal of International Money and Finance*) showed that BTP–Bund spreads above ~200–250 bps have historically been associated with self-reinforcing dynamics requiring external intervention.

In practice, the ECB has intervened twice with explicit backstops at critical BTP–Bund thresholds: Draghi's "whatever it takes" speech in 2012 (spread ~550 bps) and the PEPP pandemic programme in 2020 (spread ~280 bps). The 250 bps raw level threshold used in the regime rules therefore reflects the empirical ECB intervention zone — above this level, market stress escalates and European risk assets reprice. For EU equities and EUR, the BTP–Bund spread is a first-order risk variable.

**Regime Classification**

| Condition | Label | Positioning |
|---|---|---|
| Raw > 2.5% OR z > +1.5 | `peripheral-stress` | Reduce EU periphery equities; reduce EUR; watch for ECB response |
| −1 ≤ z ≤ +1.5 | `normal` | Standard Eurozone allocation |
| z < −1 | `compressed` | Eurozone unity premium; favourable for EZU, EUR |

---

### CLI

#### EU_CLI1 — Europe Block CLI State (DEU + FRA + GBR Average)

| | |
|---|---|
| **Formula** | `avg(DEU_CLI, FRA_CLI, GBR_CLI)` — equal-weighted average |
| **Data** | OECD CLIs: Germany, France, United Kingdom (monthly) |
| **Lookback** | 156-week rolling z-score; regime also references CLI level vs 100 |

**Economic Rationale**

EU_CLI1 provides a composite read on European economic momentum by averaging the three largest European economies — Germany, France and the UK. While EU_G3 captures the market's real-time assessment of Europe, EU_CLI1 provides the underlying fundamental confirmation from official leading indicator data, with a 6–9 month forward-looking horizon.

Germany, France and the UK together represent approximately 55% of European GDP. Germany's CLI is heavily influenced by industrial orders, exports and ifo business surveys — making it the most sensitive to global trade and China linkages. France's CLI is more domestically oriented, reflecting services and consumer confidence. The UK CLI incorporates post-Brexit specific dynamics. The equal-weighted average smooths idiosyncratic national noise and captures the European macro consensus.

The significance of the 100-level threshold is directly from OECD methodology: CLIs are normalised so that 100 represents the long-run trend rate of growth. Above 100 means the European block is growing above trend and accelerating; below 100 means below-trend and decelerating. The combination of CLI level > 100 *and* positive z-score provides the strongest European expansion signal; CLI < 100 *and* negative z-score is the most reliable contraction signal.

**Regime Classification**

| Condition | Label | Positioning |
|---|---|---|
| CLI > 100 AND z > +1 | `EU-above-trend` | OW European cyclicals and EUR assets |
| CLI ≈ 100, |z| ≤ 1 | `EU-near-trend` | Neutral; await confirmation |
| CLI < 100 AND z < −1 | `EU-below-trend` | UW Europe; reduce EUR risk; favour core govts |

---

*End of Section 3 — Europe (7 indicators: EU_G3, EU_G2, EU_G4, EU_G1, EU_Cr1, EU_R1, EU_CLI1)*

---

## 4. Japan

*Japan's equity indicator captures the interaction of BOJ policy, yen dynamics, and China trade links — making it one of the most globally systemic signals in the library.*

---

### Equity - Growth

#### JP_G1 — Japan vs Global Equities (EWJ / URTH)

| | |
|---|---|
| **Formula** | `log(EWJ / URTH)` — iShares MSCI Japan ETF / iShares MSCI World ETF (both USD) |
| **Data** | EWJ, URTH — yfinance |
| **Lookback** | 156-week rolling z-score |

**Economic Rationale**

Japan equity relative to global equities in USD terms is driven by three distinct forces that make it unlike any other developed market: (1) the yen exchange rate; (2) BOJ monetary policy; and (3) China demand for Japanese capital goods.

**Yen dynamics** are the most immediate driver. Japan's equity market is dominated by global exporters (Toyota, Sony, Keyence, Fanuc) whose yen-denominated earnings rise mechanically when JPY weakens against USD. Approximately 60% of Nikkei earnings are derived from overseas — meaning a 10% JPY depreciation mechanically adds approximately 4–5% to Nikkei earnings in JPY terms. In USD terms, EWJ partially offsets this (USD-denominated ETF), but the *local-currency outperformance* of Japan versus global benchmarks persists during yen-weakness phases. This creates a tight link between JP_G1 and FX_2 (JPY momentum).

**BOJ policy** is the second driver. Japan has been the primary practitioner of unconventional monetary policy since the 1990s — yield curve control (YCC), quantitative and qualitative easing, and negative rates. When the BOJ maintains accommodation while other central banks tighten, the interest rate differential supports both yen weakness and Japanese equity multiples. Conversely, BOJ hawkish surprises (as in July/August 2024, when the BOJ raised rates and triggered the largest single-day Nikkei decline since 1987) cause sharp JPY appreciation and equity underperformance simultaneously.

**China trade links** are the third driver: Japan is a major exporter of machine tools, semiconductor equipment and auto parts to China. China recovery phases (positive AS_CN_G2) tend to lift Japanese capital-goods exporters.

For a 6–9 month investor, JP_G1 is best interpreted alongside FX_2: if both are positive (Japan equities outperforming AND JPY weakening), the carry trade is ON and Japanese export earnings are supportive. If JP_G1 is positive but FX_2 is negative (JPY strengthening), it signals a higher-quality, domestically-driven Japanese expansion — rarer but more durable.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `japan-outperform` | OW Japan equities; hedge JPY if driven by yen weakness; monitor BOJ |
| −1 to +1 | `neutral` | Benchmark-weight Japan |
| < −1 | `japan-underperform` | Reduce Japan; watch for yen-driven risk-off contagion to global equities |

---

*End of Section 4 — Japan (1 indicators: JP_G1)*

---

## 5. Asia

*Asia indicators cover China and India equity rotation, carry trade dynamics, and OECD composite leading indicators — capturing the region's policy-driven cycles and structural growth stories.*

---

### CLI

#### AS_CLI1 — Asia-Pacific Block CLI State (CHN + JPN + AUS Average)

| | |
|---|---|
| **Formula** | `avg(CHN_CLI, JPN_CLI, AUS_CLI)` — equal-weighted average |
| **Data** | OECD CLIs: China, Japan, Australia (monthly) |
| **Lookback** | 156-week rolling z-score; regime also references CLI level vs 100 |

**Economic Rationale**

AS_CLI1 constructs an Asia-Pacific composite CLI from the three OECD-tracked economies that best represent the region's growth cycle: China (demand engine), Japan (supply chain and capital goods), and Australia (commodity supply barometer).

The three components are complementary rather than redundant. China's CLI captures domestic demand and policy stimulus. Japan's CLI is heavily export-oriented, meaning it leads on global trade cycle and reflects Chinese demand for Japanese capital goods. Australia's CLI is dominated by commodity export dynamics — iron ore, coal, LNG — making it an amplifier of Chinese infrastructure demand. Together they form a triangulated Asia-Pacific signal that is more robust than any single national CLI.

Importantly, Australia's inclusion provides a *commodity-sector early warning*: Australian business confidence and dwelling investment tend to respond quickly to changes in Chinese steel demand, making the AUS CLI a forward-looking signal for commodity-cycle turns. RBA research (Berkelmans 2005, *RBA Working Paper*) showed that Chinese demand shocks transmit to Australian activity within 1–2 quarters — faster than most commodity exporters.

For a global investor, a high AS_CLI1 reading is one of the most bullish signals available for EM equities, commodity-linked currencies and materials/energy sectors simultaneously.

**Regime Classification**

| Condition | Label | Positioning |
|---|---|---|
| CLI > 100 AND z > +1 | `Asia-above-trend` | OW Asia equities and China-sensitive global cyclicals |
| |z| ≤ 1 | `Asia-near-trend` | Neutral; await confirmation |
| CLI < 100 AND z < −1 | `Asia-below-trend` | UW Asia risk; favour DM equities; reduce commodity exposure |

---

### China - Equity (Growth)

#### AS_CN_G2 — China vs Global Developed Markets

| | |
|---|---|
| **Formula** | `log(000001.SS / URTH)` — Shanghai Composite / iShares MSCI World ETF (USD-adjusted) |
| **Data** | Shanghai Composite (000001.SS), iShares MSCI World ETF (URTH) — yfinance |
| **Lookback** | 156-week rolling z-score |

**Economic Rationale**

AS_CN_G2 compares Chinese equity performance to the global developed-market benchmark in USD terms, capturing the net effect of all China-specific macro forces — growth, policy, geopolitics, valuation and FX — relative to the global cycle. It is the primary signal for whether to overweight or underweight China versus a global DM baseline.

The theoretical rationale draws on the *emerging market premium* literature. Bekaert & Harvey (1995, *Journal of Finance*) showed that EM equities carry a risk premium over DM equities that varies with openness, policy risk and integration with global capital markets. China's equity market is partially segmented from global markets (capital controls, A-share accessibility) meaning the A-share market often diverges significantly from global trends — creating genuine alpha opportunities when Chinese policy cycles diverge from the global cycle.

Key drivers of China outperformance phases: (1) PBOC easing and credit expansion (RRR cuts, LPR reductions); (2) fiscal stimulus targeted at infrastructure and housing; (3) regulatory easing after crackdowns; (4) CNY stability or strengthening (FX_CN1 positive). Underperformance phases are typically associated with: regulatory tightening (2021 tech crackdown), property sector stress (Evergrande, 2021–23), US-China geopolitical escalation, or CNY depreciation pressure.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `china-outperform` | OW China/EM equities; positive for commodity-linked assets |
| −1 to +1 | `neutral` | Benchmark-weight China |
| < −1 | `china-underperform` | UW China; rotate to other EM or DM; reduce commodity-sensitive exposure |

---

#### AS_CN_G1 — China vs Broad EM (FXI / EEM)

| | |
|---|---|
| **Formula** | `log(FXI / EEM)` — iShares China Large-Cap ETF / iShares MSCI EM ETF (both USD) |
| **Data** | FXI, EEM — yfinance |
| **Lookback** | 156-week rolling z-score |

**Economic Rationale**

AS_CN_G1 measures whether China is driving or lagging the broader EM complex — an intra-EM rotation signal. Because China constitutes approximately 25–30% of the MSCI EM Index (and historically up to 40% prior to index reconstitutions), FXI/EEM measures China *relative* to the full EM basket including India (~18%), Taiwan (~16%), Korea (~12%), Brazil and South Africa.

When FXI outperforms EEM, China is the marginal driver of EM returns — typically during domestic Chinese stimulus phases where commodity demand is rising and the PBOC is accommodating. This is directly positive for commodity-currency pairs (AUD/USD, BRL/USD, CLP/USD) since Chinese infrastructure demand is the primary marginal buyer of iron ore, copper and soybeans. When EEM outperforms FXI, other EM economies — particularly India, Korea (technology cycle) or Brazil (commodity producers) — are leading, indicating a more diversified EM expansion less dependent on Chinese credit.

Rajan & Subramanian (2011, *Journal of Development Economics*) and Prasad (2014, *The Dollar Trap*) documented the transmission channels from Chinese growth to EM commodity exporters, confirming that China-driven EM cycles have distinct sectoral signatures versus India or Korea-driven cycles. For an EM portfolio manager, AS_CN_G1 determines whether to tilt toward China and commodity-linked EM (FXI outperformance) or diversified/non-China EM (EEM outperformance).

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `china-driving-EM` | OW China, commodity-linked EM (Brazil, Chile, Australia); positive for copper/iron ore |
| −1 to +1 | `neutral` | Balanced EM allocation |
| < −1 | `non-china-EM-leading` | Rotate to India, Korea, Taiwan-led EM; reduce commodity-sensitive exposure |

---

### China - Equity - Factor (Size)

#### AS_CN_G3 — China Size Cycle (CSI 500 / CSI 300)

| | |
|---|---|
| **Formula** | `log(000905.SS / 000300.SS)` — CSI 500 / CSI 300 |
| **Data** | CSI 500 Index (000905.SS) / CSI 300 Index (000300.SS) — yfinance |
| **Lookback** | 156-week rolling z-score |

**Economic Rationale**

The CSI 300 covers the 300 largest A-share companies listed on the Shanghai and Shenzhen exchanges — dominated by state-owned enterprises (SOEs) in banking, energy and telecoms. The CSI 500 covers the next 500 by market cap — a more diverse mix of private-sector mid-cap companies in manufacturing, technology, consumer and healthcare. Their ratio therefore captures the *domestic breadth* of Chinese growth: SOE-led recovery versus private-sector dynamism.

This decomposition is structurally important in China because the SOE and private-sector economies respond to different policy levers. SOE outperformance (CSI 300 leading) tends to occur during credit-driven infrastructure stimulus phases — the PBOC and policy banks direct lending to SOEs, which expand capacity. Private-sector outperformance (CSI 500 leading) tends to occur when consumption, technology and services are driving growth — a higher quality, more self-sustaining cycle. Lardy (2014, *Markets Over Mao*, Peterson Institute) documented this structural duality and its implications for sustainable Chinese growth.

For a 6–9 month international investor, AS_CN_G3 signals whether Chinese stimulus is creating genuine domestic demand (CSI 500 leadership, positive for global consumer goods exporters) or infrastructure-only reflation (CSI 300 leadership, more directly positive for industrial metals). The ratio also serves as a proxy for Chinese risk appetite breadth: mid-cap leadership implies broader investor participation and confidence.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `china-domestic-breadth` | Favour China consumer/tech; domestic demand supports broader EM |
| −1 to +1 | `neutral` | Balanced China allocation |
| < −1 | `china-large-cap-safety` | Narrow leadership; caution on China risk assets; watch credit conditions |

---

### China - Rates

#### AS_CN_R1 — China–US Yield Spread (Carry Signal)

| | |
|---|---|
| **Formula** | `IRLTLT01CNM156N − DGS10` — China 10Y Government Bond Yield minus US 10Y Treasury Yield |
| **Data** | FRED: IRLTLT01CNM156N (China 10Y), DGS10 (US 10Y) — monthly, interpolated to weekly |
| **Lookback** | 156-week rolling z-score |

**Economic Rationale**

The China–US 10-year yield spread is the primary carry signal for CNY-denominated fixed income and a structural anchor for CNY exchange rate dynamics. When the spread is wide (China yields > US yields), foreign investors are incentivised to hold Chinese government bonds (CGBs) rather than US Treasuries — creating capital inflow pressure that supports the CNY and Chinese risk assets broadly. When the spread compresses or inverts (as in 2022–23, when the PBOC cut rates while the Fed hiked aggressively), carry incentives reverse, creating CNY depreciation pressure and EM capital outflows.

The uncovered interest parity (UIP) framework (Fama 1984, *Journal of Monetary Economics*) predicts that yield differentials should be offset by expected exchange rate changes. In practice, however, carry trades persist because of risk premiums and capital account frictions — particularly in China, where capital controls partially segment the onshore from offshore CNY markets. Brunnermeier, Nagel & Pedersen (2009, *Quarterly Journal of Economics*) documented carry trade crash risk: when carry differentials collapse rapidly, the reversal is sharp and highly correlated across EM currencies.

For a 6–9 month investor, the China–US spread therefore serves a dual purpose: (1) a direct signal for CGBs' attractiveness as a carry asset; (2) an indirect signal for CNY pressure and the risk of disorderly capital outflows that could destabilise Chinese equity markets and EM sentiment.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `china-carry-attractive` | Wide spread supports CNY inflows; constructive China risk appetite |
| −1 to +1 | `neutral` | Carry neutral; standard China allocation |
| < −1 | `china-carry-unattractive` | Spread compressed; CNY outflow risk; caution on China risk assets |

---

### India - Equity - Factor (Size)

#### AS_IN_G1 — India Domestic Growth Breadth (Nifty Mid/Smallcap vs Nifty 50)

| | |
|---|---|
| **Formula** | `log(NIFTY_MIDCAP150 / ^NSEI)` and `log(NIFTY_SMALLCAP250 / ^NSEI)` — z-score of each |
| **Data** | Nifty Midcap 150, Nifty Smallcap 250, Nifty 50 (^NSEI) — yfinance |
| **Lookback** | 156-week rolling z-score |

**Economic Rationale**

India's equity market structure mirrors the UK dynamic (UK_G1) in one key respect: the Nifty 50 is dominated by globally competitive large-caps (Reliance Industries, TCS, Infosys, HDFC Bank) with significant international revenue exposure and institutional ownership, while the Nifty Midcap 150 and Smallcap 250 are primarily domestic businesses — regional banks, domestic consumer brands, real estate developers, infrastructure contractors.

The mid/small-cap-to-large-cap ratio in India therefore captures domestic animal spirits and the *democratisation of the growth cycle*: when mid and small caps outperform, credit is flowing broadly through the domestic economy, consumption is strong, and smaller businesses are accessing capital and winning market share. This is characteristic of India's mid-cycle expansions. When large caps dominate, it signals selective institutional positioning in quality names — often coinciding with RBI tightening, INR depreciation or global risk-off reducing appetite for illiquid smaller stocks.

India's structural growth story — demographics, formalisation of the economy via GST and Aadhaar, manufacturing relocation from China — creates a long-run tailwind for the ratio, but the cyclical overlay remains important for 6–9 month positioning. Patnaik & Shah (2012, *NIPFP*) and Gopinath (2015, *IMF*) documented India's growing but still-fragile integration with global capital flows, which makes domestic indicators like AS_IN_G1 more informative than pure top-down EM signals.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `india-domestic-expansion` | OW Indian mid/small caps; domestic consumer and financials |
| −1 to +1 | `neutral` | Balanced India allocation |
| < −1 | `india-large-cap-safety` | OW Nifty 50 quality; reduce domestic-cyclical India exposure |

---

### India - Rates

#### AS_IN_R1 — India–US Yield Spread (INR Carry Signal)

| | |
|---|---|
| **Formula** | `IRLTLT01INM156N − DGS10` — India 10Y Government Bond Yield minus US 10Y Treasury Yield |
| **Data** | FRED: IRLTLT01INM156N (India 10Y), DGS10 (US 10Y) — monthly, interpolated to weekly |
| **Lookback** | 156-week rolling z-score |

**Economic Rationale**

India's sovereign 10-year yield incorporates a structural premium over US Treasuries reflecting: (1) India's higher trend inflation (CPI has averaged 5–6% versus ~2% in the US); (2) India's chronic current account deficit (typically −1.5% to −3% of GDP), requiring sustained foreign capital inflows; (3) India's fiscal deficit (~5–6% of GDP), meaning higher issuance supply. The spread over US Treasuries is therefore not purely cyclical — it has a structural floor — but the z-score of the spread captures cyclical deviations from this norm.

When the spread widens above its historical average (positive z-score), Indian bonds are offering unusually attractive carry relative to their historical risk premium — typically coinciding with: RBI rate hikes in advance of the Fed, INR stability, or compression of India's fiscal risk premium. This supports foreign portfolio investment (FPI) inflows into Indian government securities, which strengthens the INR and underpins Indian equity performance by improving financial conditions.

The risk scenario is spread compression driven by US rate rises (as in 2022) without offsetting RBI hikes — the spread falls to historical lows, FPI outflows from Indian bonds accelerate, INR depreciates (worsening the current account) and domestic financial conditions tighten involuntarily. Patnaik & Felman (2014, *IMF Working Paper*) documented this *imported tightening* channel for India specifically.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `india-carry-attractive` | Wide spread; supportive of INR bonds and India risk assets |
| −1 to +1 | `neutral` | Standard India fixed income allocation |
| < −1 | `india-carry-unattractive` | Compressed spread; INR depreciation risk; reduce India overweight |

---

*End of Section 5 — Asia (7 indicators: AS_CLI1, AS_CN_G2, AS_CN_G1, AS_CN_G3, AS_CN_R1, AS_IN_G1, AS_IN_R1)*

---

## 6. Global

*Global indicators operate at the highest level of abstraction: cross-regional growth differentials, risk appetite, EM vs DM cycles, and commodities vs bonds — the final confirmation layer before broad asset allocation decisions.*

---

### CrossAsset - Growth

#### GL_G2 — Global Multi-Asset Risk Appetite (ACWI / GOVT)

| | |
|---|---|
| **Formula** | `log(ACWI / GOVT)` — iShares MSCI ACWI ETF / iShares US Treasury Bond ETF |
| **Data** | ACWI (iShares MSCI ACWI — 47-country global equity), GOVT (iShares US Treasury) — yfinance |
| **Lookback** | 156-week rolling z-score |

**Economic Rationale**

GL_G2 is the broadest single risk-on/risk-off signal in the library. ACWI covers approximately 3,000 stocks across 47 developed and emerging market countries — the most comprehensive equity benchmark available. GOVT provides the risk-free anchor. Their ratio captures the aggregate preference of global capital between the riskiest (global equities) and safest (US Treasuries) assets.

This is the global-scope extension of US_CA_G1 (SPY/GOVT), which only covers US equities. The distinction matters because global and US risk appetite can diverge: in 2022, US equities underperformed while EM equities were more resilient; in 2021, EM sold off while US equities continued higher. GL_G2 captures the net global verdict.

The theoretical foundation is the *flight-to-quality* literature. Vayanos (2004, *Journal of Finance*) and Brunnermeier & Pedersen (2009, *Review of Financial Studies*) documented that episodes of global risk aversion trigger simultaneous equity outflows and Treasury inflows — compressing the equity/Treasury ratio sharply and persistently. These episodes are not simply correlated with higher volatility; they represent genuine regime shifts in the risk tolerance of the global investor base.

For a 6–9 month investor, GL_G2 is the top-level confirmation signal: when it is in the `global-risk-on` regime, virtually all risk assets are supported and the cost of hedges is high; when it is in `global-risk-off`, the burden of proof shifts to individual risk positions.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `global-risk-on` | Raise equity beta; reduce duration; favour EM and HY |
| −1 to +1 | `neutral` | Standard allocation |
| < −1 | `global-risk-off` | Reduce equities; add duration; raise quality; reduce EM/HY |

---

#### GL_G1 — Emerging Markets vs Developed Markets (EEM / URTH)

| | |
|---|---|
| **Formula** | `log(EEM / URTH)` — iShares MSCI EM ETF / iShares MSCI World ETF (both USD) |
| **Data** | EEM, URTH — yfinance |
| **Lookback** | 156-week rolling z-score |

**Economic Rationale**

GL_G1 measures the relative performance of emerging markets versus developed markets in USD terms — the primary signal for the EM vs DM allocation decision in a global equity portfolio. It complements FX_CMD2 (which captures the dollar/EM channel) by focusing on the equity relative return directly.

EM outperformance requires three conditions to align simultaneously: (1) **weak USD** — a strong dollar raises EM debt burdens and tightens financial conditions (FX_CMD2 must be positive); (2) **positive EM growth differential vs DM** — EM earnings must be growing faster than DM (GL_CLI1–2, EU_CLI1, AS_CLI1 and GL_CLI5 must support EM); (3) **commodity strength** — most EM economies are net commodity exporters, so rising commodity prices (FX_CMD6 positive) directly improve terms of trade. When all three conditions are simultaneously met, EM outperformance can be very powerful — the 2002–2007 EM bull market saw EEM outperform URTH by approximately 20% per year.

Harvey (1995, *Journal of Finance*) showed that EM expected returns are driven by different risk factors than DM — including political risk, currency risk and liquidity risk — meaning EM equity cycles are genuinely partially independent from DM cycles. Bekaert, Harvey & Lundblad (2005, *Journal of Financial Economics*) documented that EM equity liberalisation and greater global integration have increased correlations over time, but genuine alpha windows remain around EM-specific growth and policy cycles.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `EM-outperform` | OW EM equities and EM local bonds; favour commodity currencies |
| −1 to +1 | `neutral` | Benchmark-weight EM/DM split |
| < −1 | `DM-outperform` | OW DM equities (especially US); reduce EM; favour USD and quality |

---

### CrossAsset - Inflation

#### GL_CA_I1 — Commodities vs Bonds

| | |
|---|---|
| **Formula** | `log(DBC / GOVT)` — Invesco DB Commodity Index Fund vs ICE BofA US Treasury Index ETF |
| **Data** | yfinance TR |

**Economic Rationale**

The commodity/Treasury ratio is a *nominal growth vs. safety* barometer. Strong commodities relative to Treasuries occurs in *reflationary* environments where: real demand is growing, inflation is above target, and the risk-free rate is insufficient compensation for holding cash. Strong Treasuries relative to commodities occurs in *deflationary* or *growth-scare* environments.

This relationship was formalised in asset allocation research by Bridgewater Associates in their *All Weather* framework (Dalio, 2004) and independently in the *inter-market analysis* tradition of John Murphy (1991). The DBC commodity basket diversifies across energy, metals, and agriculture, making it responsive to the global growth cycle rather than idiosyncratic commodity shocks.

---

### CLI

#### GL_CLI1 — US vs Eurozone Growth Differential (OECD CLI)

| | |
|---|---|
| **Formula** | `USA_CLI − avg(DEU_CLI, FRA_CLI)` |
| **Data** | OECD Composite Leading Indicators: USA, DEU, FRA (monthly, ~6-week publication lag) |
| **Lookback** | 156-week rolling z-score |

**Economic Rationale**

GL_CLI1 computes the US–Eurozone growth momentum differential using OECD Composite Leading Indicators (CLIs). CLIs are designed to anticipate turning points in economic activity relative to trend by approximately 6–9 months, making this a *leading* differential signal rather than a coincident one.

The OECD CLI methodology (OECD 2012, *Composite Leading Indicators: A Tool for Short-Term Analysis*) constructs each country's CLI from 6–10 component series selected for cyclical leading properties — typically including business surveys, financial variables, housing and order data. The CLIs are normalised to a long-run mean of 100, so the arithmetic difference captures whether the US or the Eurozone is running above or below its own historical trend by a larger margin.

For a 6–9 month investor, GL_CLI1 is the primary signal for the US vs Eurozone regional equity allocation. Bekaert & Hodrick (2009, *International Financial Management*) showed that short-term growth differentials between major economies are among the most reliable predictors of equity outperformance at 6–12 month horizons — particularly for large economies like the US and Eurozone where relative macro momentum is a dominant driver of relative equity returns. The signal also carries FX implications: a widening US growth lead versus the Eurozone is supportive of USD relative to EUR.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `US-leads-EU` | OW US equities vs Eurozone; supportive of USD vs EUR |
| −1 to +1 | `neutral` | Balanced US/Eurozone allocation |
| < −1 | `EU-leads-US` | OW Eurozone equities; supportive of EUR vs USD |

---

#### GL_CLI2 — US vs China Growth Differential (OECD CLI)

| | |
|---|---|
| **Formula** | `USA_CLI − CHN_CLI` |
| **Data** | OECD Composite Leading Indicators: USA, CHN (monthly) |
| **Lookback** | 156-week rolling z-score |

**Economic Rationale**

GL_CLI2 measures the growth momentum differential between the US and China — the two largest economies and the principal poles of the global growth cycle. A positive differential means the US cycle is running ahead of China's on an OECD-normalised basis; a negative differential means China's momentum is superior.

The US–China growth differential is one of the most consequential macro variables for multi-asset portfolios because of its broad transmission. When China leads (negative GL_CLI2): commodity demand accelerates (iron ore, copper, soybeans), commodity-exporting EM economies outperform, the AUD and BRL typically strengthen, and China equity outperformance (AS_CN_G2) tends to follow. When the US leads (positive GL_CLI2): the dollar tends to be supported, US equity earnings growth dominates, and commodity-sensitive EM assets are under relative pressure.

The OECD China CLI is constructed from industrial production, business surveys, money supply and equity market signals — a broader set than the NBS official PMI and less subject to Chinese statistical smoothing. Fernald & Babson (2016, *Federal Reserve Bank of San Francisco*) showed that OECD CLI-based signals for China lead the official GDP figures by 1–2 quarters, providing genuine advance information about the Chinese cycle direction.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `US-leads-China` | OW US vs China/Asia equities; cautious on China-sensitive cyclicals |
| −1 to +1 | `neutral` | Balanced US/China cycle |
| < −1 | `China-leads-US` | OW China/Asia equities; favour China-sensitive commodities and EM |

---

#### GL_CLI5 — Global Growth Breadth Diffusion Index *(Naturally Leading)*

| | |
|---|---|
| **Formula** | Fraction of {USA, DEU, FRA, GBR, ITA, JPN, CHN, AUS, CAN} where `CLI > 100 AND CLI > CLI_26w_ago` |
| **Data** | OECD CLIs: all 9 countries (monthly) |
| **Output range** | 0.0 (no country above trend and improving) to 1.0 (all 9 countries above trend and improving) |
| **Lookback** | 156-week rolling z-score; regime also references raw fraction |

**Economic Rationale**

GL_CLI5 is the broadest and most powerful macro signal in the library: a global growth diffusion index measuring how many of the world's nine largest OECD-tracked economies are *simultaneously* above trend and accelerating. It answers the most fundamental question a multi-asset investor can ask: is the global economy broadly expanding or contracting?

The diffusion index methodology has deep roots in business cycle analysis. Burns & Mitchell (1946, NBER) showed that the simultaneity of expansion across sectors and countries is one of the most reliable characteristics distinguishing genuine expansions from sector-specific or regional recoveries. Harding & Pagan (2002, *Journal of Applied Econometrics*) formalised the concordance statistic — measuring the fraction of time two cycles are in the same phase — and showed that high global concordance (many countries expanding together) is associated with the most durable and broad-based expansions.

The dual condition — CLI > 100 *and* CLI > its 26-week lagged value — requires both level and momentum to confirm inclusion: a country that is above trend but decelerating does not count as a positive contributor. This prevents the index from overstating expansion breadth in late-cycle phases when several countries remain above trend but are clearly losing momentum. The 26-week lag captures 6-month direction change — consistent with the medium-term investment horizon throughout this library.

The thresholds reflect historical calibration: a fraction of 0.7 or above (6–7 of 9 economies above trend and improving) has historically coincided with the most robust global bull markets. A fraction below 0.4 (fewer than 4 economies qualifying) has historically been associated with global recessions or near-recessions.

Because CLIs are themselves designed to lead economic activity, GL_CLI5 is *naturally leading*: the current reading already embeds a 6–9 month forward signal for global growth conditions.

**Regime Classification**

| Fraction | Label | Positioning |
|---|---|---|
| ≥ 0.7 | `broad-expansion` | Raise global equity beta; OW EM, cyclicals, HY |
| 0.4–0.7 | `mixed` | Selective; focus on regions confirmed by GL_CLI1–2, EU_CLI1, AS_CLI1 |
| < 0.4 | `contracting` | De-risk beta; favour quality, IG, core govts |

---

*End of Section 6 — Global (6 indicators: GL_G2, GL_G1, GL_CA_I1, GL_CLI1, GL_CLI2, GL_CLI5)*

---

## 7. FX & Commodities

*FX and commodity indicators capture currency momentum, dollar dynamics, commodity cycle signals, and the China infrastructure cycle — cross-cutting signals that inform positioning across all regional equity and fixed income allocations.*

---

### CrossAsset - Growth

#### FX_CMD2 — Dollar vs Emerging Markets

| | |
|---|---|
| **Formula** | `log(EEM / DX-Y.NYB)` |
| **Data** | iShares MSCI Emerging Markets ETF (EEM) / ICE US Dollar Index (DX-Y.NYB) — yfinance |
| **Lookback** | 156-week rolling z-score |

**Economic Rationale**

The US dollar is the world's primary reserve currency and the invoicing currency for the majority of global trade and commodity contracts. When the dollar strengthens, it creates three simultaneous headwinds for EM economies: (1) external debt denominated in USD becomes more expensive to service in local currency terms; (2) commodity prices (priced in USD) fall in absolute terms, hurting commodity-exporting EM nations; (3) the risk premium on EM assets rises as capital flows back toward the US.

The theoretical foundation comes from *original sin* literature (Eichengreen & Hausmann 1999), which formalised why EM sovereigns and corporates are structurally exposed to dollar fluctuations. Bruno & Shin (2015, BIS) documented the *dollar credit channel*: a strong dollar tightens global financial conditions through the balance sheets of international banks even in countries with no direct dollar exposure.

For a 6–9 month investor, the dollar cycle is one of the highest-impact multi-asset allocation signals available. The Hershey-Berge dollar cycle model suggests EM equities and commodities outperform by 5–8% per year on average in dollar downtrend phases versus dollar uptrend phases. The EEM/DXY ratio usefully combines the EM equity demand signal and the dollar strength signal into a single ratio: when positive, it confirms that both EM earnings and dollar tailwinds are aligned.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `weak-USD` | OW EM equities, commodities, gold; UW USD-denominated assets |
| −1 to +1 | `neutral` | Neutral dollar allocation |
| < −1 | `strong-USD` | UW EM; OW US large-cap, USD cash; reduce commodity exposure |

---

#### FX_CMD1 — Copper/Gold Ratio (Global Growth Barometer)

| | |
|---|---|
| **Formula** | `log(HG=F / GC=F)` |
| **Data** | Copper Futures (HG=F) / Gold Futures (GC=F) — yfinance |
| **Lookback** | 156-week rolling z-score |

**Economic Rationale**

The copper/gold ratio is one of the most closely watched cross-commodity signals in macro finance. Copper is the industrial bellwether: approximately 60% of global copper demand comes from construction, electrical grids and industrial machinery, making it highly sensitive to global capex cycles and Chinese infrastructure spending. Gold, by contrast, is the quintessential safe-haven asset — its price responds to risk aversion, real-rate declines and monetary system uncertainty.

The ratio therefore distils a binary question: is the world's marginal capital seeking productive investment (high copper demand relative to safe haven) or protecting itself (high gold demand relative to copper)? Jeffrey Gundlach of DoubleLine popularised the copper/gold ratio as a predictor of 10-year Treasury yields — empirically, the ratio leads the 10-year yield by 6–12 months, because both respond to forward growth expectations. Erb & Harvey (2006, *FAJ*) documented that commodity returns are driven by roll yield, spot return and inflation — and copper's spot return is uniquely tied to the global manufacturing PMI.

For a multi-asset investor at a 6–9 month horizon, the ratio serves as a cross-check on the yield curve and equity cyclicals signals: a rising copper/gold ratio alongside a steepening yield curve (US_R1 improving) and rising cyclicals/defensives (US_G1/G2 improving) is a high-conviction pro-growth signal.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `pro-growth` | OW cyclicals, industrials, EM commodities; UW gold, long-duration |
| −1 to +1 | `neutral` | Balanced |
| < −1 | `growth-scare` | OW gold, defensive duration; UW cyclicals, EM, copper-sensitive assets |

---

### China - FX Mmtm

#### FX_CN1 — CNY Directional Momentum

| | |
|---|---|
| **Formula** | `log(CNY=X / SMA_26w(CNY=X))` — CNY/USD spot vs its 26-week moving average |
| **Data** | CNY=X (USD per CNY, so higher = stronger CNY) — yfinance |
| **Lookback** | 156-week rolling z-score |

**Economic Rationale**

FX_CN1 measures the 6-month directional momentum of the Chinese yuan — whether the CNY is strengthening or weakening relative to its recent trend. This momentum framing is deliberate: the CNY is a managed currency (the PBOC sets a daily fixing within a ±2% band), meaning absolute FX levels are policy-controlled and less informative than the *direction* of the trend, which reflects the net of PBOC management intentions and market pressure.

CNY strengthening momentum signals: (1) PBOC comfort with or active support of a stronger currency, typically associated with confidence in the domestic economy; (2) capital inflows driven by China's current account surplus or foreign portfolio investment; (3) reduced US-China trade tension (tariff escalation typically triggers CNY depreciation as a partial offset). CNY weakening momentum signals the reverse: PBOC allowing depreciation to cushion export competitiveness, capital flight, or external pressure.

The 26-week SMA was chosen as the trend anchor because it represents approximately half a year — the typical horizon over which PBOC policy signals are visible and the period over which carry positions in CNY assets build or unwind. Cheung, Chinn & Fujii (2007, *Journal of International Money and Finance*) showed that CNY momentum is a stronger short-to-medium-term FX predictor than purchasing power parity models in the managed-float regime.

For a global investor, CNY momentum is a direct signal for China equity positioning and an indirect signal for commodity-linked currencies (AUD, BRL) and EM sentiment broadly.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `CNY-strengthening` | OW China equities and EM assets; positive commodity signals |
| −1 to +1 | `neutral` | Standard CNY exposure |
| < −1 | `CNY-weakening` | Caution on China risk; watch for EM contagion; reduce AUD/BRL exposure |

---

### India - FX Mmtm

#### FX_1 — INR Directional Momentum

| | |
|---|---|
| **Formula** | `log(INR=X / SMA_26w(INR=X))` — INR/USD spot vs its 26-week moving average |
| **Data** | INR=X (USD per INR, higher = stronger INR) — yfinance |
| **Lookback** | 156-week rolling z-score |

**Economic Rationale**

FX_1 mirrors FX_CN1 for India: 6-month INR directional momentum. The INR is also a managed float (the RBI intervenes via FX reserves to smooth volatility) but with less direct daily management than the CNY, making momentum signals somewhat more market-driven.

INR strengthening momentum reflects: (1) strong FPI inflows — both equity (India's structural growth premium attracting global allocation) and debt (carry attractiveness from AS_IN_R1); (2) RBI reserve accumulation and hawkish policy stance; (3) lower oil prices (India imports approximately 85% of its oil, so lower crude is a direct terms-of-trade benefit that reduces the current account deficit and supports INR). INR weakening momentum reflects: (1) elevated oil prices widening the current account deficit; (2) FPI outflows triggered by US rate rises or global risk-off; (3) domestic inflation overshooting RBI's 4% target, eroding real yield differentials.

The 26-week SMA anchor captures the medium-term policy and flow dynamics for INR. Kohli (2015, *RBI Working Paper*) documented that INR momentum tracks the BoP capital account closely at 3–6 month horizons — making FX_1 an early indicator of whether foreign capital is building or reducing India exposure.

For equity investors, INR strength is positively correlated with Indian equity returns in USD terms — it both signals risk appetite and improves the USD return on local equity positions.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `INR-strengthening` | OW India equities and bonds in USD terms; carry inflows supporting |
| −1 to +1 | `neutral` | Standard INR exposure |
| < −1 | `INR-weakening` | Hedge FX exposure or reduce India overweight; watch oil/BoP dynamics |

---

---

### Japan - FX Mmtm

#### FX_2 — JPY Carry Trade Signal (USD/JPY 26-Week Momentum) *(Naturally Leading)*

| | |
|---|---|
| **Formula** | `log(USDJPY=X / SMA_26w(USDJPY=X))` — USD/JPY spot vs its 26-week moving average |
| **Data** | USDJPY=X — yfinance (higher = JPY weaker / USD stronger) |
| **Lookback** | 156-week rolling z-score |
| **Lead** | JPY moves precede equity/EM impact by days to 2–4 weeks |

**Economic Rationale**

The Japanese yen carry trade is the most systematically important cross-asset transmission mechanism in global finance. The JPY carry trade works as follows: investors borrow cheaply in Japanese yen (historically near-zero or negative rates) and invest in higher-yielding assets globally — US equities, EM bonds, high-yield credit, commodity currencies. When carry is profitable (JPY weakening, stable high-yield assets), the trade generates positive carry plus FX gains, attracting ever-more leverage. When the trade reverses, it unwinds explosively.

The academic documentation is extensive. Burnside et al. (2011, *Journal of Finance*) showed that carry trades earn a substantial risk premium that is compensation for rare but severe crash risk — periods of sudden JPY appreciation when risk appetite collapses globally. Brunnermeier, Nagel & Pedersen (2009, *Quarterly Journal of Economics*) formalised the *carry crash* mechanism: when global volatility spikes (VIX rises sharply), leveraged carry traders face margin calls and simultaneously unwind positions across all asset classes, generating correlations between apparently unrelated assets (EM currencies, US high yield, commodity markets) that are entirely carry-trade-driven.

The **26-week SMA momentum** captures the *sustained direction* of the carry trade cycle rather than day-to-day JPY moves. When USD/JPY is running above its 26-week average (positive momentum = JPY weakening trend), carry trade positions are being added and global risk appetite is supported. When USD/JPY breaks below its 26-week average (negative momentum = JPY strengthening trend), the carry trade is being unwound — and the signal is *naturally leading* because the FX move precedes the equity and credit market impact by days to 2–4 weeks as positions are forced closed.

The August 2024 carry unwind — triggered by a surprise BOJ rate hike — is the canonical recent example: USD/JPY fell from ~160 to ~142 within weeks, the Nikkei dropped 13% in a single day, EM currencies fell in tandem, and VIX spiked to 65. FX_2 would have been flashing a `carry-unwind` regime in the days before the equity damage arrived.

For a global multi-asset investor, FX_2 is the single most important *systemic risk indicator* in the library for detecting forced deleveraging events.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +0.5 | `carry-on` | Global risk appetite supported; favour EM and HY |
| −1 to +0.5 | `neutral` | Monitor for carry build; standard allocation |
| < −1 | `carry-unwind` | **Systemic risk-off signal**: expect equity/EM drawdown within 2–4 weeks; reduce gross risk, add JPY exposure, reduce HY/EM |

---

---

### Growth (China infra)

#### FX_CMD5 — Iron Ore / Copper (China Infrastructure vs Broad Industrial)

| | |
|---|---|
| **Formula** | `log(Iron Ore price / HG=F)` — Iron Ore spot / Copper Futures |
| **Data** | Iron Ore (World Bank commodity price series or spot proxy) / Copper Futures (HG=F) — yfinance |
| **Lookback** | 156-week rolling z-score |

**Economic Rationale**

Iron ore and copper are both industrial metals, but they serve distinct economic functions that create a highly informative ratio. Copper is a broad industrial bellwether used in electrical wiring, motors, plumbing and electronics across virtually every industry globally (hence its nickname "Dr Copper" for its diagnostic power). Iron ore is almost exclusively used in steel production, and China accounts for approximately 70% of global seaborne iron ore demand — making it uniquely sensitive to Chinese infrastructure investment and property construction.

The iron ore / copper ratio therefore answers a specific question: is China's demand for steel (infrastructure, property) running ahead of or behind the global industrial cycle (capex, electronics, manufacturing)? When iron ore outperforms copper (ratio rising), it signals that China's heavy-industry and construction cycle is the dominant driver of commodity demand — typically coinciding with government-directed fiscal stimulus (fixed asset investment) or a property market recovery. When copper outperforms iron ore, global manufacturing and electronics are driving demand more broadly — a higher-quality global expansion rather than a China-specific credit-driven cycle.

Kilian (2009, *American Economic Review*) showed that commodity price decompositions into supply vs demand components are essential for interpreting commodity signals correctly. Heap (2005, *Citigroup Metals Research*) first formalised the China commodity intensity thesis: that China's steel intensity per unit of GDP is structurally higher during urbanisation phases, creating a duration of iron ore demand that is decoupled from the global industrial cycle. For a 6–9 month investor, FX_CMD5 distinguishes between commodity exposure types: iron-ore-sensitive (Australian miners, bulk shippers, Brazil iron ore exporters) versus copper-sensitive (diversified industrials, electrical infrastructure).

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `china-infra-led` | OW iron ore miners, bulk shippers, China-construction-linked equities |
| −1 to +1 | `neutral` | Balanced commodity allocation |
| < −1 | `global-industrial-led` | OW copper, diversified industrials; iron ore/China construction risk elevated |

---

### Growth (China broad)

#### FX_CMD4 — Iron Ore / Broad Commodities (China vs Global Commodity Cycle)

| | |
|---|---|
| **Formula** | `log(Iron Ore / DBC)` — Iron Ore spot / Invesco DB Commodity Index ETF |
| **Data** | Iron Ore spot / DBC (DBC covers energy ~55%, metals ~25%, agriculture ~20%) — yfinance |
| **Lookback** | 156-week rolling z-score |

**Economic Rationale**

FX_CMD4 compares the China-specific iron ore cycle against the full diversified commodity complex, which is dominated by energy (crude oil, natural gas, heating oil), industrial metals and agriculture. Where FX_CMD5 identifies the *composition* of industrial demand (China-heavy vs global manufacturing), FX_CMD4 identifies whether China's cycle is *leading or lagging* the broader commodity market.

The DBC commodity index captures the global commodity cycle in its full breadth: energy prices driven by OPEC supply decisions and US shale output; agricultural prices driven by weather, fertiliser costs and food demand; and metals driven by both China and global industrial activity. When iron ore outperforms DBC, it means Chinese heavy-industry demand is running above the average commodity cycle — typically during fiscal stimulus phases where Chinese steel output and fixed asset investment are prioritised. When DBC outperforms iron ore, the global energy and agricultural cycle (driven by geopolitical supply shocks, US inflation, or weather events) is dominating, and China's contribution to global commodity demand is relatively subdued.

The distinction is crucial for portfolio construction: an iron ore overweight versus DBC underweight is a China-specific, policy-driven bet. An iron ore underweight versus DBC overweight is an energy/inflation/global-supply-shock hedge. Frankel (2008, *Brookings*) showed that commodity price co-movements are driven by a combination of common factors (global growth, USD) and idiosyncratic supply factors — the iron ore/DBC ratio isolates the China-idiosyncratic demand component from the common commodity factor.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `china-commodity-leading` | China policy/construction driving cycle; OW China, bulk commodities, AUD |
| −1 to +1 | `neutral` | China in line with global commodity cycle |
| < −1 | `global-commodity-leading` | Energy/ag driving commodities; China heavy-industry subdued; OW energy/ag vs iron ore |

---

### Growth Mmtm

#### FX_CMD6 — Global Commodity Cycle Momentum (DBC 52-Week Return)

| | |
|---|---|
| **Formula** | `log(DBC / DBC_52w_ago)` — Invesco DB Commodity Index 52-week log return |
| **Data** | DBC (Invesco DB Commodity Index Tracking Fund) — yfinance |
| **Lookback** | 156-week rolling z-score |

**Economic Rationale**

FX_CMD6 measures the 12-month momentum of the broad commodity complex — the clearest signal of whether the global commodity supercycle is in an uptrend or downtrend. The DBC index covers energy (~55%), metals (~25%) and agriculture (~20%), making it a comprehensive proxy for global physical demand conditions.

The theoretical rationale for using 12-month momentum on commodities is well-established. Gorton & Rouwenhorst (2006, *FAJ*) showed that commodity futures have historically delivered equity-like returns over full cycles, with their returns driven by roll yield, spot price changes and rebalancing. Momentum is particularly strong in commodities because supply adjustment lags demand — it takes 3–7 years to bring new oil fields, mines or agricultural capacity online, meaning commodity price uptrends driven by demand can persist far longer than equity uptrends where the supply response (new issuance, capex, competition) is faster.

For a multi-asset investor, FX_CMD6 serves as the primary signal for whether to hold commodity-linked equity sectors (energy, materials, mining) and whether to overweight commodity-exporting equity markets (ASX 200, Bovespa, JSE, TSX). Erb & Harvey (2006, *FAJ*) documented that commodity momentum is strongest at 12-month horizons, justifying the 52-week lookback. Additionally, rising commodity momentum leads EM equity outperformance by 8–12 weeks on positive cycle turns — making FX_CMD6 a leading signal for GL_G1.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `commodity-bull` | OW energy, materials, commodity exporters; add inflation-linked bonds |
| −1 to +1 | `neutral` | Standard commodity allocation |
| < −1 | `commodity-bear` | UW commodities; favour consumer-driven EM and quality DM equities |

---

### Inflation

#### FX_CMD3 — Oil vs Gold (Growth-Inflation Regime Signal)

| | |
|---|---|
| **Formula** | `log(CL=F / GC=F)` — WTI Crude Oil Futures / Gold Futures |
| **Data** | CL=F (WTI Crude), GC=F (Gold) — yfinance |
| **Lookback** | 156-week rolling z-score |

**Economic Rationale**

FX_CMD3 is the energy-extended version of the copper/gold ratio (FX_CMD1), using crude oil versus gold to distinguish between growth-driven inflation regimes and fear-driven safe-haven regimes. Oil and gold both rise during inflationary episodes, but they respond differently to the *type* of inflation: oil is primarily sensitive to demand-driven (growth-positive) inflation, while gold is primarily sensitive to fear-driven or monetary debasement inflation.

When oil outperforms gold (ratio rising): the world is pricing *reflationary growth* — energy demand is rising because economic activity is expanding, corporate capital expenditure is healthy, and consumers are spending on transport and energy-intensive goods. This is positive for cyclicals, energy, materials and commodity currencies. When gold outperforms oil (ratio falling): the world is pricing *deflation risk, geopolitical shock or growth deceleration* — gold is rising as a safe haven while oil demand is falling on recession fears, or oil supply is contracting but this is a supply shock rather than a demand signal.

Erb & Harvey (2013, *FAJ*) documented that oil and gold respond to different components of the inflation process: oil tracks demand-pull inflation, gold tracks monetary inflation and tail risk. Hamilton (1983, *Journal of Political Economy*) showed that oil price shocks that are demand-driven (rising oil due to growth) have very different macro consequences than supply shocks — a distinction that the oil/gold ratio helps to identify.

The oil/gold ratio complements FX_CMD1 (copper/gold) by adding the energy dimension: when both copper/gold (FX_CMD1) and oil/gold (FX_CMD3) are positive, the global growth-inflation signal is high-conviction. When they diverge (e.g. oil rising on geopolitical supply shock but copper flat), the signal is more ambiguous and cross-referencing with GL_CLI5 and GL_G2 is warranted.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `growth-inflation` | OW cyclicals, energy, materials; favour equities over bonds |
| −1 to +1 | `balanced` | Standard allocation |
| < −1 | `deflation-risk` | OW gold, defensives, long duration; reduce energy and cyclicals |

---

---

*End of Section 7 — FX & Commodities (9 indicators: FX_CMD2, FX_CMD1, FX_CN1, FX_1, FX_2, FX_CMD5, FX_CMD4, FX_CMD6, FX_CMD3)*

---

*End of Manual — 68 indicators total across Sections 1–7 (US, UK, Europe, Japan, Asia, Global, FX & Commodities)*
