# Macro-Market Indicator Manual

> **Purpose:** Educational reference for all 70 composite indicators computed by `compute_macro_market.py`. Each entry covers the formula, data sources, economic rationale drawn from academic and practitioner research, and regime interpretation calibrated for a **6–9 month investment horizon**.
>
> **Output columns per indicator:** `raw` (the computed series), `zscore` (260-week rolling z-score), `regime` (current state label), `fwd_regime` (1–2 month trajectory based on 8-week z-score slope).
>
> Last updated: 2026-04-01

---

## Table of Contents

1. [US Growth & Style Indicators](#1-us-growth--style-indicators)
2. [US Rates, Credit, Volatility & Momentum](#2-us-rates-credit-volatility--momentum)
3. [US Macro Fundamentals & Europe/UK](#3-us-macro-fundamentals--europeuk)
4. [Asia-Pacific, Japan & Global/Regional](#4-asia-pacific-japan--globalregional)

---

## 1. US Growth & Style Indicators

*These indicators use relative equity price ratios to infer the market's real-time assessment of the economic cycle — effectively crowdsourcing the business cycle signal from millions of portfolio decisions. They require no publication lag and update continuously.*

---

### US_G1 — Cyclicals vs Defensives (Discretionary/Staples)

| | |
|---|---|
| **Formula** | `log(XLY / XLP)` |
| **Data** | SPDR S&P 500 Consumer Discretionary ETF (XLY) / SPDR S&P 500 Consumer Staples ETF (XLP) — yfinance TR |
| **Lookback** | 260-week rolling z-score |

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

### US_G2 — Broader Cyclicals vs Defensives (Industrials+Financials / Utilities+Staples)

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

### US_G2b — Financials vs Utilities

| | |
|---|---|
| **Formula** | `log(XLF / XLU)` |
| **Data** | XLF (Financials), XLU (Utilities) — yfinance TR |

**Economic Rationale**

A focused two-ticker version of US_G2 that isolates the *credit and rates* dimension of the cycle. Financials earn more when the yield curve is steep (NIM expands as they borrow short and lend long), when loan demand is strong, and when credit losses are low — all conditions associated with early and mid-cycle expansion. Utilities are explicitly rate-sensitive: their dividend yields compete with bonds, so they outperform in falling-rate or growth-scare environments.

The XLF/XLU ratio is therefore a combined proxy for (1) yield curve steepness, (2) credit demand, and (3) risk appetite — making it a compact recession indicator. Borio & Lowe (2002, BIS) document that banking sector underperformance relative to defensive sectors reliably precedes credit-cycle downturns.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `risk-on` | OW financials, steepener trades |
| < −1 | `defensive` | OW utilities, long duration |

---

### US_G3 — Size Cycle (Russell 2000 / Russell 1000)

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

### US_G3b — Size Cycle S&P Proxy (Russell 2000 / S&P 500)

| | |
|---|---|
| **Formula** | `log(IWM / SPY)` |
| **Data** | IWM (Russell 2000), SPY (S&P 500) — yfinance TR |

**Economic Rationale**

Functionally identical in economic meaning to US_G3 but benchmarks the Russell 2000 against the most widely followed large-cap index rather than the Russell 1000. The S&P 500 includes a large weight in mega-cap technology and platform companies — which have near-zero correlation with the domestic credit cycle — making this ratio slightly more sensitive to the cyclical vs secular-growth distinction than the Russell 2000/1000 pair. Both indicators are retained as they can diverge at tech cycle peaks.

---

### US_G4 — Style: Value vs Growth (Russell 1000)

| | |
|---|---|
| **Formula** | `log(IWD / IWF)` |
| **Data** | iShares Russell 1000 Value ETF (IWD) / iShares Russell 1000 Growth ETF (IWF) — yfinance TR |

**Economic Rationale**

The *value premium* — the historical tendency of cheap stocks (high book/price, high earnings yield) to outperform expensive stocks — is one of the most studied phenomena in empirical finance (Fama & French 1992, 1993). In a macro context, however, value vs growth rotation is more reliably driven by the *real rate cycle* than by static valuation alone.

Growth stocks (technology, biotech, platform companies) have long-duration cash flows heavily weighted to the distant future. Like long-duration bonds, their present value is highly sensitive to the discount rate. When real rates rise, the PV of those distant cash flows falls more than the PV of near-term value cash flows — causing growth to underperform value. When real rates fall or remain low, the opposite holds.

This relationship was quantified by Lettau & Wachter (2007, JF) and has been consistently confirmed in practitioner research by AQR, GMO, and Research Affiliates. For a 6–9 month investor, the key variable is the *direction* of real rates (US_RR1), which US_G4 tends to anticipate in price.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `value-regime` | OW value, cyclicals, banks; UW long-duration growth |
| −1 to +1 | `mixed` | Factor-neutral |
| < −1 | `growth-regime` | OW quality growth, mega-cap tech; add duration |

---

### US_G4b — Style: Growth vs Value (S&P 500)

| | |
|---|---|
| **Formula** | `log(IVW / IVE)` |
| **Data** | iShares S&P 500 Growth ETF (IVW) / iShares S&P 500 Value ETF (IVE) — yfinance TR |

**Economic Rationale**

The inverse of US_G4 using the S&P 500 decomposition rather than the Russell 1000. The S&P 500 growth/value split weights mega-cap technology more heavily (Apple, Microsoft, NVIDIA etc. dominate IVW) than the Russell 1000 equivalent. This means US_G4b is particularly sensitive to AI/technology cycle dynamics that may not show up as strongly in the broader Russell series. Both indicators are retained: US_G4 gives the broad style signal, US_G4b isolates the mega-cap-tech dimension.

Note that because this is *growth/value* (inverted relative to US_G4), z > +1 here means the *growth regime*, not the value regime.

---

### US_G5 — Technology Leadership (NASDAQ-100 vs S&P 500)

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

### US_G6 — Market Breadth (Equal-Weight vs Cap-Weight S&P 500)

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

*End of Section 1 — US Growth & Style Indicators (9 indicators: US_G1, US_G2, US_G2b, US_G3, US_G3b, US_G4, US_G4b, US_G5, US_G6)*

---

## 2. US Rates, Credit, Volatility & Momentum

### Section 2a — US Rates & Credit (US_I1–I11, US_R1–R2, US_RR1)

*Fixed-income and credit indicators are the backbone of macro regime identification. They reflect the cost and availability of capital — the single most important driver of business investment, housing, and consumer spending over a 6–9 month horizon. Unlike equity ratios, which can remain elevated for years on sentiment, credit spreads and yield curves have hard economic anchors in default rates and monetary policy.*

---

### US_I1 — Yield-Curve Slope 10Y–3M

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

### US_I6 — Yield-Curve Slope 2s10s (FRED)

| | |
|---|---|
| **Formula** | `T10Y2Y` — FRED direct (US 10-Year CMT minus US 2-Year CMT) |
| **Data** | Federal Reserve H.15 via FRED |

**Economic Rationale**

The 2s10s curve is the market's benchmark measure of monetary policy stance vs. long-run growth expectations. The 2-year yield is highly sensitive to Fed policy expectations 1–2 years out; the 10-year reflects the longer-run nominal growth and inflation outlook.

While the 10Y–3M spread (US_I1) is the better *recession predictor*, the 2s10s spread is more widely used by traders and market participants because it is more liquid and more reactive to near-term Fed policy shifts. Reinhart & Rogoff (2009) and Campbell Harvey's original dissertation (1986) document both curves' predictive power. The 2s10s is complementary to US_I1: divergence between the two signals can identify whether the inversion is driven by Fed overtightening (3M elevated) or by collapsing long-run growth expectations (10Y falling).

### US_I6b — Yield-Curve Slope 2s10s (Market)

| | |
|---|---|
| **Formula** | `^TNX (yfinance) − DGS2 (FRED)` |
| **Data** | yfinance 10Y yield level + FRED 2Y CMT |

Functionally identical to US_I1 in interpretation. Retained as a cross-check: the yfinance-sourced 10Y yield updates intraday, while FRED T10Y2Y has a 1-day publication lag. Any persistent divergence between US_I6 and US_I6b would indicate a data feed issue.

---

### US_I2 — US High-Yield Credit Spread (OAS)

| | |
|---|---|
| **Formula** | `BAMLH0A0HYM2` — ICE BofA US High Yield Master II Option-Adjusted Spread |
| **Data** | FRED (Federal Reserve Economic Data), St. Louis Fed |
| **Regime trigger** | Level-based: OAS > 700 bps or z > +1.5 triggers `stress` |

**Economic Rationale**

The HY OAS measures the yield premium that sub-investment-grade (rated BB and below) corporate borrowers must pay over equivalent-maturity US Treasuries. It is one of the most sensitive real-time measures of *credit conditions* and *default risk expectations*.

Altman (1968, JF) established the theoretical link between credit spreads and default probability via Z-score models. Subsequent work by Duffie & Singleton (1999) and the Merton (1974) structural credit model formalised the spread as compensation for expected loss (probability of default × loss given default) plus a *liquidity premium* and a *risk premium*.

From a cycle perspective, HY spreads are *coincident-to-leading*: they tend to widen before official recession declarations because the corporate bond market prices deteriorating fundamentals faster than equity analysts revise earnings. The 400-bps level has historically divided benign from stressed environments; 700 bps marks systemic distress (2001 TMT bust, 2008 GFC, 2020 COVID shock).

For a 6–9 month investor, *the direction of spreads matters more than the level*: a spread at 450 bps and widening is more dangerous than 600 bps and tightening.

**Regime Classification**

| Condition | Label | Positioning |
|---|---|---|
| OAS > 700 or z > +1.5 | `stress` | De-risk HY; OW IG and Treasuries |
| 400–700 bps, \|z\| ≤ 1 | `normal` | Carry regime; hold HY at benchmark |
| OAS < 400, z < −1 | `frothy` | Consider UW HY; credit cycle late |

---

### US_I4 — US Investment-Grade Credit Spread (OAS)

| | |
|---|---|
| **Formula** | `BAMLC0A0CM` — ICE BofA US Corporate Master Option-Adjusted Spread |
| **Data** | FRED |

**Economic Rationale**

The IG OAS measures the spread demanded for investment-grade (BBB and above) corporate credit. IG spreads are structurally lower than HY and less volatile, reflecting the lower default probability of investment-grade issuers. However, they are highly sensitive to *liquidity conditions* and *risk appetite* in the institutional investor base (insurance companies, pension funds, foreign reserve managers all hold significant IG).

The IG spread and HY spread together paint a complete picture of the credit cycle. When HY spreads widen significantly but IG remains contained, stress is isolated to lower-quality borrowers — a typical mid-cycle signal. When both widen simultaneously (tracked by US_I5), financial conditions are tightening broadly.

---

### US_I5 — HY–IG Spread Differential

| | |
|---|---|
| **Formula** | `BAMLH0A0HYM2 − BAMLC0A0CM` — arithmetic difference |
| **Data** | FRED |

**Economic Rationale**

This differential captures the *quality spread* — the additional compensation demanded specifically for default risk, net of liquidity and macro premia embedded in both HY and IG. When the HY–IG differential widens, it signals rising *discrimination* against lower-quality issuers, which precedes rising defaults by 6–12 months (Altman, NYU Stern annual default reports). When it narrows (compressed differential), it suggests complacency about credit quality — a signal associated with late-cycle over-extension.

---

### US_I3 — Commodities vs Bonds

| | |
|---|---|
| **Formula** | `log(DBC / GOVT)` — Invesco DB Commodity Index Fund vs ICE BofA US Treasury Index ETF |
| **Data** | yfinance TR |

**Economic Rationale**

The commodity/Treasury ratio is a *nominal growth vs. safety* barometer. Strong commodities relative to Treasuries occurs in *reflationary* environments where: real demand is growing, inflation is above target, and the risk-free rate is insufficient compensation for holding cash. Strong Treasuries relative to commodities occurs in *deflationary* or *growth-scare* environments.

This relationship was formalised in asset allocation research by Bridgewater Associates in their *All Weather* framework (Dalio, 2004) and independently in the *inter-market analysis* tradition of John Murphy (1991). The DBC commodity basket diversifies across energy, metals, and agriculture, making it responsive to the global growth cycle rather than idiosyncratic commodity shocks.

---

### US_I7 — 10-Year Breakeven Inflation

| | |
|---|---|
| **Formula** | `T10YIE` — FRED direct (10-Year Treasury Inflation-Indexed Security, Break-Even Inflation Rate) |
| **Data** | FRED (Fed H.15 release) |

**Economic Rationale**

The 10-year breakeven inflation rate is derived from the difference between nominal 10-year Treasury yields and TIPS 10-year real yields. It represents the market's expectation of average CPI inflation over the next decade, and the price at which an investor is indifferent between holding nominal Treasuries and inflation-protected TIPS.

Breakeven inflation is distinct from *realised* inflation: it reflects forward expectations and can diverge significantly in periods of uncertainty. During QE cycles, breakevens were suppressed by Fed asset purchases; during supply shocks (2021–2022), they surged ahead of realised CPI. For the 6–9 month investor, the *direction* of breakevens is more important than the absolute level: rising breakevens signal inflation-pricing-in, which supports inflation-linked assets (TIPS, real estate, commodities, gold) and pressures long nominal duration.

---

### US_I8 — Risk-On vs Risk-Off (Equities vs Treasuries)

| | |
|---|---|
| **Formula** | `log(SPY / GOVT)` |
| **Data** | SPY (SPDR S&P 500 ETF TR), GOVT (ICE BofA US Treasury Index ETF TR) |

**Economic Rationale**

The equity/Treasury ratio is the most fundamental *risk-on/risk-off* barometer in markets. In a classical *Capital Asset Pricing Model* framework, the equity risk premium (ERP) is the excess return of equities over the risk-free rate. The SPY/GOVT ratio in log-price terms tracks the *cumulative* realised ERP — rising when equities outperform (investors are willing to hold risk), falling when Treasuries outperform (flight to safety).

Ibbotson & Sinquefield (1976) documented the long-run superiority of equities over bonds, while Shiller's (1981) excess-volatility puzzle showed equity prices move far more than dividends justify — implying that most of the variation in this ratio reflects *time-varying risk premia* rather than fundamental news. For a 6–9 month investor, z-score extremes are useful: deep z < −1 readings have historically marked moments of maximum pessimism from which equity returns are above average.

---

### US_I9 — HY vs IG Credit (ETF Ratio)

| | |
|---|---|
| **Formula** | `log(IHYU.L / SLXX.L)` |
| **Data** | iShares USD HY Corp Bond UCITS ETF (IHYU.L) / iShares Core GBP Corporate Bond UCITS ETF (SLXX.L) — yfinance TR |

**Economic Rationale**

This ratio uses European-listed ETFs to measure the *relative total return* of USD high-yield credit vs. investment-grade GBP corporate credit. Rising ratio = investors preferring speculative-grade over investment-grade = credit risk appetite. The use of ETF price ratios (rather than OAS levels as in US_I2 and US_I4) captures both spread changes *and* the duration and carry component, giving a more complete total-return perspective.

---

### US_I10 — HY vs Treasuries (Credit Risk)

| | |
|---|---|
| **Formula** | `log(IHYU.L / GOVT)` |
| **Data** | IHYU.L (iShares USD HY UCITS ETF) / GOVT (ICE BofA US Treasury Index ETF) |

**Economic Rationale**

The broadest total-return credit signal: HY vs. pure government bonds. This encompasses the full *credit risk premium* — compensation for default, liquidity, and economic uncertainty. Unlike the OAS measures (US_I2, US_I4) which use yield differentials, this log price ratio captures realised investor experience. During credit crises, IHYU.L falls sharply while GOVT rises — the ratio collapses, generating a strong `flight-to-quality` regime signal.

---

### US_I11 — Mortgage Credit Spread (Affordability Stress)

| | |
|---|---|
| **Formula** | `MORTGAGE30US − DGS10` — arithmetic difference (bps) |
| **Data** | FRED: 30-Year Fixed Mortgage Rate (MORTGAGE30US), 10-Year Treasury (DGS10) |

**Economic Rationale**

The spread between the 30-year mortgage rate and the 10-year Treasury yield reflects lender risk aversion and housing credit availability. In normal conditions, the spread runs 150–200 bps, compensating mortgage originators for prepayment risk, credit risk, and servicing costs. When the spread widens above 250 bps (as it did in 2022–2023), it signals that lenders are charging an elevated premium above risk-free rates — effectively tightening housing credit even if the Fed has stopped hiking.

The MBA Mortgage Bankers Association and the National Association of Realtors track this spread as a primary affordability indicator. Academic work by Campbell & Cocco (2015, JF) documents the direct transmission from mortgage rates to housing turnover and consumer spending via the *home equity* channel. For a 6–9 month investor, this indicator leads building permits (US_HOUS1) by 3–6 months.

---

### US_R1 — VIX Term Structure (Equity Vol)

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

### US_R2 — Rates vs Equity Vol (MOVE/VIX Ratio)

| | |
|---|---|
| **Formula** | `log(MOVE / VIX)` |
| **Data** | yfinance: `^MOVE` (ICE BofA MOVE Index), `^VIX` |

**Economic Rationale**

The MOVE Index (Merrill Lynch Option Volatility Estimate) measures 1-month implied volatility in the US Treasury market, constructed similarly to the VIX but for rates rather than equities. The MOVE/VIX ratio therefore captures whether macro/policy uncertainty (rates volatility) is elevated relative to equity-market fear.

A high MOVE/VIX ratio — common during Fed tightening cycles and fiscal crises — indicates that rates are the dominant driver of uncertainty, not equity fundamentals. This is important for a multi-asset investor because in these environments, the traditional equity-bond diversification benefit breaks down: both assets can sell off simultaneously (as in 2022). Research by Goldman Sachs Global Investment Research and by Ilmanen (2011, *Expected Returns*) documents that equity-bond correlation flips positive during inflation regimes, precisely when MOVE/VIX is elevated.

---

### US_RR1 — Real Rates (TIPS 10-Year Yield)

| | |
|---|---|
| **Formula** | `DFII10` — FRED direct (Market Yield on US Treasury Securities at 10-Year, Inflation-Indexed) |
| **Data** | FRED (Federal Reserve H.15 release, daily) |

**Economic Rationale**

The 10-year real interest rate is arguably the single most important macro variable for valuing long-duration assets. It is the *risk-free real discount rate* that anchors equity multiples, real estate cap rates, and gold prices — all of which can be modelled as the present value of future real cash flows.

Fisher (1930) established the decomposition of nominal rates into real rates and expected inflation. In modern macro-finance, the real rate is determined by: (1) the stance of monetary policy relative to the neutral rate (r*), (2) the term premium for holding duration, and (3) global safe-asset demand (the *global saving glut* identified by Bernanke 2005).

For equity investors, the relationship between real rates and P/E multiples is direct: the Gordon Growth Model implies P/E = 1 / (r_real + ERP − g), so rising real rates compress multiples, particularly for long-duration growth stocks (US_G5, US_G4 rotate together with US_RR1). For a 6–9 month investor, the *direction* of real rates is the key variable: TIPS yields rising from negative to positive (-0.5% to +2% as in 2022) caused the most severe equity de-rating in decades.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `high-real-rates` | UW long-duration growth; OW value, short-duration; hold gold only as hedge |
| −1 to +1 | `normal` | Standard allocation |
| < −1 | `low-real-rates` | OW quality growth, duration, gold, EM carry |

---

*End of Section 2a — US Rates & Credit (14 indicators: US_I1, US_I2, US_I3, US_I4, US_I5, US_I6, US_I6b, US_I7, US_I8, US_I9, US_I10, US_I11, US_R1, US_R2, US_RR1)*

---

## 2b. US FX & Momentum Indicators

*This group captures two distinct signals: (1) the **dollar cycle** and its effect on cross-asset pricing (US_FX1, US_FX2), and (2) **systematic trend/momentum** filters that determine whether the current price environment is conducive to risk-taking across equities, credit and multi-asset portfolios (M1–M5). These indicators sit at the boundary between fundamental macro and quantitative strategy.*

---

### US_FX1 — Dollar vs Emerging Markets

| | |
|---|---|
| **Formula** | `log(EEM / DX-Y.NYB)` |
| **Data** | iShares MSCI Emerging Markets ETF (EEM) / ICE US Dollar Index (DX-Y.NYB) — yfinance |
| **Lookback** | 260-week rolling z-score |

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

### US_FX2 — Copper/Gold Ratio (Global Growth Barometer)

| | |
|---|---|
| **Formula** | `log(HG=F / GC=F)` |
| **Data** | Copper Futures (HG=F) / Gold Futures (GC=F) — yfinance |
| **Lookback** | 260-week rolling z-score |

**Economic Rationale**

The copper/gold ratio is one of the most closely watched cross-commodity signals in macro finance. Copper is the industrial bellwether: approximately 60% of global copper demand comes from construction, electrical grids and industrial machinery, making it highly sensitive to global capex cycles and Chinese infrastructure spending. Gold, by contrast, is the quintessential safe-haven asset — its price responds to risk aversion, real-rate declines and monetary system uncertainty.

The ratio therefore distils a binary question: is the world's marginal capital seeking productive investment (high copper demand relative to safe haven) or protecting itself (high gold demand relative to copper)? Jeffrey Gundlach of DoubleLine popularised the copper/gold ratio as a predictor of 10-year Treasury yields — empirically, the ratio leads the 10-year yield by 6–12 months, because both respond to forward growth expectations. Erb & Harvey (2006, *FAJ*) documented that commodity returns are driven by roll yield, spot return and inflation — and copper's spot return is uniquely tied to the global manufacturing PMI.

For a multi-asset investor at a 6–9 month horizon, the ratio serves as a cross-check on the yield curve and equity cyclicals signals: a rising copper/gold ratio alongside a steepening yield curve (US_I1 improving) and rising cyclicals/defensives (US_G1/G2 improving) is a high-conviction pro-growth signal.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `pro-growth` | OW cyclicals, industrials, EM commodities; UW gold, long-duration |
| −1 to +1 | `neutral` | Balanced |
| < −1 | `growth-scare` | OW gold, defensive duration; UW cyclicals, EM, copper-sensitive assets |

---

### M1 — US Equity Trend (S&P 500 vs 40-Week SMA)

| | |
|---|---|
| **Formula** | `log(SPY / SMA_40w(SPY))` |
| **Data** | SPDR S&P 500 ETF (SPY) — yfinance |
| **Lookback** | 260-week rolling z-score of distance from SMA |

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

### M2 — Multi-Asset Trend Breadth (5-Asset Faber TAA)

| | |
|---|---|
| **Formula** | Fraction of {SPY, URTH, GOVT, VNQ, DBC} above their 40-week SMA |
| **Data** | SPY, iShares MSCI World (URTH), iShares US Treasury Bond (GOVT), Vanguard Real Estate (VNQ), Invesco DB Commodity (DBC) — yfinance |
| **Lookback** | 260-week rolling z-score of breadth fraction |

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

### M3 — Dual Momentum (Antonacci Equity/Bond Regime)

| | |
|---|---|
| **Formula** | `max(12m_return(SPY), 12m_return(URTH)) − 12m_return(SHY)` |
| **Data** | SPY (US equity), URTH (global equity), SHY (1–3yr Treasuries as cash proxy) — yfinance |
| **Lookback** | 260-week rolling z-score of excess return signal |

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

### M4 — High Yield Trend with Spread Override

| | |
|---|---|
| **Formula** | `log(BAMLHYH0A0HYM2TRIV / SMA_40w(BAMLHYH0A0HYM2TRIV))`; forced to −1 if HY OAS (BAMLH0A0HYM2) > 600 bps |
| **Data** | FRED: ICE BofA US HY Total Return Index, ICE BofA US HY Option-Adjusted Spread |
| **Lookback** | 260-week rolling z-score |

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

### M5 — VIX Regime Filter (13-Week vs 52-Week MA)

| | |
|---|---|
| **Formula** | `log(VIX_13w_MA / VIX_52w_MA)` |
| **Data** | CBOE VIX Index (^VIX) — yfinance, resampled to weekly |
| **Lookback** | 260-week rolling z-score |

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

*End of Section 2b — US FX & Momentum (7 indicators: US_FX1, US_FX2, M1, M2, M3, M4, M5)*

---

## 3a. US Macro Fundamentals

*These indicators draw on official economic data releases rather than market prices. They measure the underlying real economy — labour markets, production, credit, housing and liquidity — and provide the fundamental backdrop that ultimately drives asset price regimes over 6–9 months. Publication lags range from 1 week (jobless claims) to 6 weeks (ISM, JOLTS), so these signals are best combined with the market-based indicators in Sections 1–2.*

---

### US_LEI1 — Conference Board Leading Economic Index

| | |
|---|---|
| **Formula** | `USSLIND` (Conference Board LEI) — 6-month annualised % change |
| **Data** | FRED: USSLIND (monthly, released ~3 weeks after month-end) |
| **Lookback** | 260-week rolling z-score of 6m annualised change |

**Economic Rationale**

The Conference Board Leading Economic Index (LEI) is a composite of ten sub-indicators designed to lead business cycle turning points by 6–9 months. Its components span financial conditions (S&P 500, yield curve), credit (ISM new orders, building permits), and labour markets (initial claims, average workweek). The breadth of coverage is its primary strength: no single data series dominates, making it more robust than any individual indicator.

The academic foundation is Burns & Mitchell (1946, NBER), whose pioneering work on business cycle measurement established that leading indicators consistently precede cycle peaks and troughs. Diebold & Rudebusch (1989, *American Economic Review*) and Stock & Watson (1989, *JASA*) formalised the statistical evidence for composite leading indicators, showing that equal-weighted combinations of leading series outperform individual series for 3–6 month ahead GDP forecasts.

The **6-month annualised change** is the Conference Board's own preferred signal transformation: it smooths monthly noise while remaining responsive to genuine trend reversals. Their research (Conference Board 2001) shows that a 6-month decline of roughly 4.3% or more, accompanied by broad diffusion, has preceded all post-war US recessions with only two false positives (1966, 1995). This threshold is incorporated directly into the regime rules.

For a 6–9 month investor, LEI is the highest-level cycle signal available: a sustained negative trend (consecutive monthly declines, 6m change < −4%) is a strong signal to reduce gross risk, rotate toward quality and duration, and reduce EM/commodity exposure.

**Regime Classification**

| Condition | Label | Positioning |
|---|---|---|
| 6m change < −4.3% AND z < −1.5 | `recession-risk` | Cap equity risk; OW high-quality bonds and defensives |
| 6m change 0 to −4.3% | `late-cycle` | Selective; reduce cyclicals, monitor credit spreads |
| 6m change > 0 | `expansion` | Normal equity risk budget |

---

### US_JOBS1 — Initial Jobless Claims (YoY Change)

| | |
|---|---|
| **Formula** | YoY % change of `IC4WSA` (4-week moving average of initial claims) |
| **Data** | FRED: IC4WSA (weekly, released Thursday for prior week) |
| **Lookback** | 260-week rolling z-score |

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

### US_LAB1 — Labour Market Composite

| | |
|---|---|
| **Formula** | Equal-weighted average of z-scores of: inverted `UNRATE`, `PAYEMS` YoY%, inverted `IC4WSA` |
| **Data** | FRED: UNRATE (monthly), PAYEMS (monthly), IC4WSA (weekly) |
| **Lookback** | 260-week rolling z-score of composite |

**Economic Rationale**

No single labour market series captures the full picture: unemployment is a lagging indicator, payrolls are coincident, and claims are leading. US_LAB1 synthesises all three into a single composite score that spans the lead-coincident-lag spectrum of labour market data — mimicking how the Federal Reserve's own staff models assess labour market conditions.

The Federal Reserve's *Labour Market Conditions Index* (LMCI), developed by Hakkio & Willis (2014, *Kansas City Fed*) and extended by the Board of Governors, uses a factor model to extract a common latent state from 19 labour market indicators. US_LAB1 implements a simplified version of the same concept using three key series, with the inversions applied so that the composite is positive when labour markets are strong and negative when weak.

Bernanke & Carey (1996, *Quarterly Journal of Economics*) demonstrated that labour market tightness is the primary transmission channel from monetary policy to inflation and growth — central banks tighten specifically to cool labour markets, and recessions begin when the cooling overshoots. For a 6–9 month investor, US_LAB1 captures the real-time state of this channel: high composite z-score implies continued consumer spending support; low composite z-score implies deteriorating income dynamics and rising recession probability.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `labour-strong` | Supports earnings/cyclicals; watch for rate-hike risk if inflation elevated |
| −1 to +1 | `labour-balanced` | Mid-cycle allocation |
| < −1 | `labour-weak` | Defensive tilt; OW duration and quality; UW cyclicals |

---

### US_LAB2 — JOLTS Labour Market Tightness *(Naturally Leading)*

| | |
|---|---|
| **Formula** | `JTSJOL / UNEMPLOY` — ratio of job openings to unemployed persons |
| **Data** | FRED: JTSJOL (monthly JOLTS), UNEMPLOY (monthly) |
| **Lookback** | 260-week rolling z-score |
| **Lead** | ~2 months ahead of reported unemployment; ~3–4 months ahead of wage inflation |

**Economic Rationale**

The job openings–to–unemployed ratio is the canonical measure of **labour market tightness** developed from search-and-matching theory. When openings exceed unemployed persons (ratio > 1), every unemployed worker notionally has more than one available job, implying strong wage bargaining power and accelerating wage growth.

The theoretical framework is the Diamond-Mortensen-Pissarides (DMP) search model (Pissarides 1985, *Review of Economic Studies*; Mortensen & Pissarides 1994, *Review of Economic Studies*; both authors received the Nobel Prize in 2010). The DMP model predicts that the vacancy-unemployment ratio is a sufficient statistic for the tightness of the matching market: as it rises, workers find jobs faster, wages rise, and the employment rate increases. Shimer (2005, *American Economic Review*) further showed that vacancies are 10× more volatile than unemployment across the cycle — making the ratio a more sensitive early signal of cycle turns than unemployment alone.

Practically, the JOLTS ratio leads reported unemployment by approximately 2 months and leads the Employment Cost Index (ECI, the broadest wage measure) by 3–4 months, making it *naturally leading*: the current reading already embeds the signal about labour market conditions 1–2 months ahead. This is why US_LAB2 is included in the `NATURALLY_LEADING` set, and its `fwd_regime` is tagged `[leading]`.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `labour-tight` | Wage pressure; consumer resilient; watch for inflation overshoot |
| −1 to +1 | `balanced` | Equilibrium labour market; mid-cycle |
| < −1 | `labour-slack` | Unemployment rising; consumer vulnerable; easing bias |

---

### US_GROWTH1 — Real Activity Composite (IP + Retail Sales)

| | |
|---|---|
| **Formula** | Equal-weighted z-score composite of: `INDPRO` 12m % change + `RSXFS` 12m % change |
| **Data** | FRED: INDPRO (Industrial Production, monthly), RSXFS (Retail Sales ex-Autos, monthly) |
| **Lookback** | 260-week rolling z-score of composite |

**Economic Rationale**

US_GROWTH1 combines the two broadest real-activity measures spanning the supply and demand sides of the US economy: industrial production (supply/manufacturing) and retail sales ex-autos (consumer demand). Together they provide a coincident composite analogous to the NBER Business Cycle Dating Committee's own primary indicators.

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

### US_HOUS1 — Housing / Building Permits *(Naturally Leading)*

| | |
|---|---|
| **Formula** | `PERMIT` — 12-month % change |
| **Data** | FRED: PERMIT (Building Permits, monthly, released ~3 weeks after month-end) |
| **Lookback** | 260-week rolling z-score |
| **Lead** | Typically leads housing starts by 1–2 months; leads GDP by 2–4 quarters |

**Economic Rationale**

Building permits are one of the most reliable leading indicators in the NBER framework — they are included in the Conference Board LEI (US_LEI1) and are published earlier than housing starts, making them the first-available signal of construction cycle direction.

The transmission mechanism is multilayered. First, housing construction has extremely high labour and material intensity — a single-family home creates approximately 3 person-years of employment across construction, materials and professional services. Second, new housing generates significant downstream spending: buyers purchase appliances, furniture and home improvement goods (the IKEA/Home Depot multiplier). Third, rising construction activity raises land and existing home prices, increasing household net worth and supporting the *wealth effect* on consumption (Case, Quigley & Shiller 2005, *Brookings Papers*).

The interest-rate sensitivity of permits is also why US_HOUS1 is *naturally leading* for monetary policy transmission: permit applications collapse within months of rate rises (the 2022 experience saw permits fall 25% within 6 months of the first Fed hike) and recover months before the broader economy when rate cuts arrive. The current reading therefore already captures conditions 2–4 months ahead of when the impact will appear in GDP.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `housing-expanding` | OW REITs, homebuilders, building materials |
| −1 to +1 | `neutral` | Standard allocation |
| < −1 | `housing-contracting` | UW REITs vs broad equity; OW defensives and duration |

---

### US_M2L1 — M2 Money Supply Growth (Liquidity Indicator)

| | |
|---|---|
| **Formula** | `M2SL` — YoY % change |
| **Data** | FRED: M2SL (monthly, revised quarterly) |
| **Lookback** | 260-week rolling z-score |

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

### US_ISM1 — ISM Manufacturing New Orders *(Naturally Leading)*

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

*End of Section 3a — US Macro Fundamentals (8 indicators: US_LEI1, US_JOBS1, US_LAB1, US_LAB2, US_GROWTH1, US_HOUS1, US_M2L1, US_ISM1)*

---

## 3b. Europe & UK Indicators

*This group covers equity, rates, credit, FX and sovereign-stress signals for the Eurozone and United Kingdom. The European macro cycle has historically diverged from the US cycle due to structural differences: greater export dependency (Germany, Netherlands), energy import vulnerability, ECB mandate constraints, and fiscal fragmentation across sovereign states. These indicators capture both intra-European dynamics (periphery vs core, UK vs Eurozone) and European performance relative to the global cycle.*

---

### EU_G1 — European Cyclicals vs Defensives

| | |
|---|---|
| **Formula** | `log((EXV1.DE + EXH1.DE + EXV3.DE) / (EXV2.DE + EXH3.DE))` |
| **Data** | STOXX Europe 600 sector ETFs: Industrials, Banks, Technology vs Utilities, Consumer Staples — yfinance |
| **Lookback** | 260-week rolling z-score |

**Economic Rationale**

EU_G1 is the European analogue of US_G1/G2: relative performance of cyclical sectors (industrials, banks, technology) versus defensive sectors (utilities, consumer staples) as a real-time market-based assessment of the European growth outlook.

The choice of European Banks as a cyclical component is particularly important and differs from the US construction. European banks are more directly tied to the sovereign credit cycle than US banks: their balance sheets carry significant sovereign bond holdings, and their lending spreads respond directly to ECB policy and peripheral sovereign stress (EU_I4). When banks outperform defensives in Europe, it signals improving credit conditions, a steepening yield curve and diminishing tail risk — all supportive of the broader European growth narrative.

Fama & French (1989) showed that cyclical-to-defensive spread returns predict future economic conditions across markets, not just the US. Dimson, Marsh & Staunton (2002, *Triumph of the Optimists*) extended this analysis to European markets, confirming that sector rotation signals are robust across the UK, Germany and France. The European cycle is also highly sensitive to global trade volumes — particularly Chinese demand for German capital goods — making EU_G1 a dual signal for both European domestic conditions and global goods cycle strength.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `pro-growth-europe` | OW European cyclicals, financials, industrials |
| −1 to +1 | `neutral` | Balanced European allocation |
| < −1 | `defensive-europe` | OW European utilities, staples; reduce European bank exposure |

---

### EU_G2 — UK Domestic vs Global (FTSE 250 / FTSE 100)

| | |
|---|---|
| **Formula** | `log(MCX.L / ISF.L)` — FTSE 250 ETF / FTSE 100 ETF |
| **Data** | iShares FTSE 250 ETF (MCX.L) / iShares Core FTSE 100 ETF (ISF.L) — yfinance |
| **Lookback** | 260-week rolling z-score |

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

### EU_G3 — Eurozone vs US Equity Leadership

| | |
|---|---|
| **Formula** | `log(FEZ / SPY)` — Euro Stoxx 50 ETF / S&P 500 ETF (both in USD) |
| **Data** | SPDR Euro Stoxx 50 ETF (FEZ) / SPDR S&P 500 ETF (SPY) — yfinance |
| **Lookback** | 260-week rolling z-score |

**Economic Rationale**

EU_G3 measures relative equity leadership between the Eurozone and the United States — one of the most important regional allocation decisions in a global multi-asset portfolio.

The drivers of Eurozone-vs-US relative performance are well-documented in the academic literature on international equity premium differentials. Solnik (1974, *Journal of Finance*) established that international diversification reduces portfolio risk precisely because national equity cycles diverge — the Eurozone and US cycles correlate at approximately 0.75 over rolling 3-year periods but can diverge sharply at cycle inflection points. Asness, Moskowitz & Pedersen (2013) showed that cross-country equity momentum is one of the most persistent and risk-adjusted-efficient factors in international investing.

Key structural drivers of Eurozone outperformance phases include: (1) EUR appreciation relative to USD (foreign earnings accrete in USD terms); (2) China stimulus (Eurozone, particularly Germany, has high export exposure to China capital goods demand); (3) ECB accommodation combined with Eurozone fiscal expansion (rare but powerful, as in 2021 and post-2023 fiscal plans); (4) relative earnings valuation — the Eurozone has historically traded at a 20–30% P/E discount to the US, creating mean-reversion opportunities. US dominance phases tend to coincide with strong-dollar regimes, US tech cycle leadership and European political stress.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `eurozone-outperform` | OW Eurozone vs US; hedge USD/EUR to capture local-currency return |
| −1 to +1 | `neutral` | Balanced regional allocation |
| < −1 | `us-dominance` | OW US large-cap; reduce Eurozone equity weight |

---

### EU_G4 — Eurozone vs Global Equities

| | |
|---|---|
| **Formula** | `log(EZU / URTH)` — iShares MSCI Eurozone ETF / iShares MSCI World ETF (both USD) |
| **Data** | EZU, URTH — yfinance |
| **Lookback** | 260-week rolling z-score |

**Economic Rationale**

EU_G4 broadens the Eurozone comparison from US-only (EU_G3) to the full global developed-market universe. This distinction matters: Eurozone outperformance relative to the US (EU_G3 positive) can coexist with Eurozone underperformance relative to MSCI World if Japan, UK or other developed markets are simultaneously strong. EU_G4 therefore answers the regional allocation question from the perspective of a globally diversified investor.

The MSCI World benchmark (proxied by URTH) covers 23 developed markets with approximately 70% US weight, meaning EU_G4 is a less US-centric comparison than EU_G3. When EU_G4 is positive, Eurozone equities are genuinely outperforming the blended global developed market — capturing not just EUR/USD dynamics but also European fundamentals versus the broader international cycle.

For a 6–9 month investor constructing a MSCI World-based equity allocation, EU_G4 provides the primary signal for whether to overweight or underweight European equities relative to the benchmark. A sustained positive z-score of EU_G4 combined with a positive EU_G1 (European cyclicals leading) and a compressed EU_I4 (BTP-Bund spread) constitutes a high-conviction Eurozone overweight signal.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `eurozone-outperform` | OW European equities vs global benchmark; supportive of EUR |
| −1 to +1 | `neutral` | Benchmark-weight Europe |
| < −1 | `eurozone-underperform` | UW Europe vs global; favour US/Japan/EM alternatives |

---

### EU_I1 — Euro Corporate vs Government Spread

| | |
|---|---|
| **Formula** | `yield(ICE BofA Euro Corporate Index) − yield(ICE BofA Euro Government Index)` |
| **Data** | FRED: BAMLHE00EHY0EY (Euro HY OAS) and BAMLHE4XEHYSIS (Euro IG OAS) — arithmetic difference |
| **Lookback** | 260-week rolling z-score |

**Economic Rationale**

EU_I1 is the European equivalent of US_I2 (HY OAS): the spread between corporate bond yields and risk-free government yields captures the aggregate risk premium demanded for Euro corporate credit. This spread is one of the broadest and most liquid financial conditions indicators for the Eurozone economy.

The credit channel of monetary policy in Europe is particularly important because European companies are far more bank-dependent than US companies: approximately 70–80% of Eurozone corporate financing comes from bank loans versus approximately 40% in the US. Bank lending rates closely track the corporate bond market's risk premium signal — when EU_I1 widens, it signals tighter bank lending conditions, which feed through to investment, hiring and production with a 2–4 quarter lag (ECB Lending Survey research, Altunbas et al. 2010, *Journal of Banking & Finance*).

Gilchrist & Zakrajšek (2012, *American Economic Review*) developed the excess bond premium (EBP) framework, showing that corporate spread widening beyond what can be explained by expected defaults is the most powerful predictor of future real activity — more powerful than the yield curve alone. EU_I1 captures a similar signal for the Eurozone: widening that exceeds the credit cycle's default-justified level indicates financial conditions tightening beyond fundamentals, a regime shift requiring defensive positioning.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `euro-credit-stress` | UW Euro corporate bonds; OW core government bonds (Bunds) |
| −1 to +1 | `normal` | Standard allocation |
| < −1 | `compressed-spreads` | Watch for late-cycle reach-for-yield; be cautious adding credit risk |

---

### EU_I2 — UK Inflation Expectations Proxy (Linker/Gilt Ratio)

| | |
|---|---|
| **Formula** | `log(INXG.L / IGLT.L)` — iShares UK Inflation-Linked Gilt ETF / iShares UK Gilt ETF |
| **Data** | INXG.L, IGLT.L — yfinance |
| **Lookback** | 260-week rolling z-score |

**Economic Rationale**

The ratio of inflation-linked gilt (linker) prices to nominal gilt prices is a market-based proxy for UK inflation expectations and real rate dynamics. When linkers outperform nominal gilts, the market is pricing rising inflation breakevens or falling real rates — both signals that the inflation-adjusted return on nominal bonds is declining, a headwind for long-duration fixed income.

The theoretical basis comes from the Fisher (1930) decomposition: nominal yield = real yield + expected inflation + term premium. The linker/gilt price ratio implicitly captures the inflation component: linkers pay a real coupon plus CPI uplift, so they outperform nominal gilts when inflation expectations rise or when real rates fall. This mirrors the TIPS-based US_RR1 and US_I7 indicators but uses the ETF price ratio rather than FRED yield data, since UK real yield data availability on FRED is limited.

Post-Brexit, UK inflation dynamics have been structurally different from the Eurozone: UK CPI peaked at 11.1% in October 2022, driven by energy dependency and sterling weakness — the highest level among major developed economies. The Bank of England's (BoE) dual mandate complication — inflation control versus financial stability — makes the linker/gilt ratio a particularly important signal for UK rate risk and gilt market positioning.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `uk-inflation-elevated` | UW long gilts; OW UK real assets, inflation-linked bonds, commodities |
| −1 to +1 | `neutral` | Standard UK fixed income |
| < −1 | `uk-disinflation` | OW long gilts and duration; UW inflation-linked |

---

### EU_I3 — UK–Germany 10-Year Spread (Gilt–Bund)

| | |
|---|---|
| **Formula** | `UK 10Y Gilt Yield − Germany 10Y Bund Yield` |
| **Data** | FRED: IRLTLT01GBM156N (UK 10Y) − IRLTLT01DEM156N (Germany 10Y) |
| **Lookback** | 260-week rolling z-score |

**Economic Rationale**

The UK–Germany 10-year yield spread distils three distinct macro signals into a single number: (1) relative inflation expectations (UK has historically run higher inflation than Germany); (2) relative fiscal risk (UK deficit dynamics vs German Schuldenbremse fiscal rule); and (3) monetary policy divergence between the Bank of England and ECB.

During normal periods, the spread reflects the structural inflation and growth premium of the UK over Germany — typically 50–150 bps. When the spread widens sharply above historical norms, it signals that UK-specific risk is being priced: fiscal credibility concerns (as in the 2022 Truss mini-budget, when the gilt–bund spread spiked 100 bps in days, forcing BoE intervention), inflation overshoot, or BoE policy lag risk. Conversely, a compressed spread can signal relative UK macro weakness or Eurozone stress.

Blanchard & Summers (1984) showed that long-term yield differentials between developed countries embed both current and expected future short-rate differentials — meaning the gilt–bund spread also captures expectations about the future BoE/ECB policy divergence path over 2–5 years. For a multi-asset investor, sharp moves in EU_I3 are often early warnings of GBP volatility and UK equity risk repricing.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `uk-risk-premium` | Caution on long gilts vs Bunds; expect GBP weakness vs EUR |
| −1 to +1 | `normal` | Standard UK/Germany allocation |
| < −1 | `uk-relative-strength` | Gilts attractive vs Bunds; potential GBP strength |

---

### EU_I4 — BTP–Bund Spread (Peripheral Sovereign Stress)

| | |
|---|---|
| **Formula** | `Italy 10Y Yield − Germany 10Y Bund Yield` |
| **Data** | FRED: IRLTLT01ITM156N − IRLTLT01DEM156N |
| **Lookback** | 260-week rolling z-score; raw level override at 2.5% |

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

### EU_R1 — UK Credit Conditions (Corporates vs Gilts)

| | |
|---|---|
| **Formula** | `log(SLXX.L / IGLT.L)` — iShares Core GBP Corporate Bond ETF / iShares UK Gilt ETF |
| **Data** | SLXX.L, IGLT.L — yfinance |
| **Lookback** | 260-week rolling z-score |

**Economic Rationale**

EU_R1 measures the relative performance of GBP investment-grade corporate bonds versus UK government gilts — the UK equivalent of the US investment-grade credit spread signal. When corporates outperform gilts, it signals that investors are willing to accept lower incremental yield for UK credit risk; the financial conditions environment is supportive. When gilts outperform, it signals a flight to safety within the UK fixed income market.

The UK corporate bond market is smaller and less liquid than the US market, which means EU_R1 tends to move more sharply at inflection points and can lead equity market stress. Longstaff & Schwartz (1995, *Journal of Finance*) showed that corporate–government spread dynamics are driven by both default risk and liquidity premiums, with the liquidity component dominating during stress — a feature particularly pronounced in the GBP corporate market.

Post-Brexit, UK corporate spreads have also incorporated a structural UK-specific risk premium absent from EUR or USD corporate markets: sterling liquidity risk, UK political risk, and the reduced depth of the GBP investor base. EU_R1 therefore serves as both a domestic credit conditions indicator and a barometer of UK-specific macro risk relative to the global credit cycle.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `uk-credit-appetite` | GBP corporates outperforming; supportive of UK equities and risk |
| −1 to +1 | `neutral` | Standard UK credit allocation |
| < −1 | `uk-flight-to-quality` | Reduce GBP corporates; OW gilts; caution on UK risk assets |

---

### EU_FX1 — EUR Macro Composite (EUR/USD + European Cyclicals)

| | |
|---|---|
| **Formula** | Average z-score of `log(EURUSD=X)` and `log(EXV1.DE / EXV2.DE)` (European industrials/utilities) |
| **Data** | EUR/USD spot (EURUSD=X) + STOXX Europe 600 Industrials/Utilities ratio — yfinance |
| **Lookback** | 260-week rolling z-score of composite |

**Economic Rationale**

EU_FX1 combines two complementary signals — the EUR exchange rate and European sector rotation — into a composite that distinguishes genuine Eurozone macro strength from currency-only moves. This design choice is deliberate: EUR appreciation alone can occur for reasons unrelated to European growth (e.g. USD weakness, safe-haven flows during non-European crises), but EUR appreciation *combined with European cyclicals outperforming defensives* is a stronger signal that Eurozone fundamentals are genuinely improving.

The EUR is the second most important reserve currency globally and reflects the aggregate macro credibility of the Eurozone — fiscal discipline, ECB policy, and trade competitiveness. Frankel & Rose (1995, *Journal of International Economics*) documented that currency strength in export-oriented economies correlates with export-driven growth cycles; Obstfeld & Rogoff (1996, *Foundations of International Macroeconomics*) formalised the link between terms-of-trade improvement and currency appreciation for industrial exporters like Germany.

The industrial/utilities sector component captures domestic capex and credit cycle conditions within Europe, filtering out external demand effects. When both legs of EU_FX1 are positive simultaneously — EUR strengthening AND European cyclicals leading defensives — the composite provides a high-conviction signal that European equity risk is well-compensated for the 6–9 month horizon.

**Regime Classification**

| z-score | Label | Positioning |
|---|---|---|
| > +1 | `eurozone-macro-strong` | OW European equities and EUR; supportive of export-linked cyclicals |
| −1 to +1 | `neutral` | Balanced European macro view |
| < −1 | `eurozone-under-strain` | UW European cyclicals; hedge EUR exposure; favour core govts |

---

*End of Section 3b — Europe & UK (10 indicators: EU_G1, EU_G2, EU_G3, EU_G4, EU_I1, EU_I2, EU_I3, EU_I4, EU_R1, EU_FX1)*
