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
