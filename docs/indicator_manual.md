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
