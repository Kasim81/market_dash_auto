# Macro-Market Indicator Cheat Sheet

**68 indicators | 156-week (3-year) rolling z-score | CSV-driven architecture**
**Date: 2026-04-08**

This cheat sheet is a quick-reference companion to the full *Indicator Manual*. It covers every indicator's regime rules, threshold logic, and narrative themes — designed to support blog idea generation, regime commentary, and snapshot interpretation at a glance.

---

## How to Read This Document

- **Standard regime**: z > +1 / -1 to +1 / z < -1 (most indicators)
- **Non-standard**: marked with a dagger (**+**) — uses absolute levels, asymmetric thresholds, or fraction-based logic
- **Forward regime**: `improving` / `stable` / `deteriorating`, with `[leading]` suffix for naturally leading indicators
- **Narrative themes**: short phrases for blog/commentary framing when the indicator is in an extreme regime

---

## 1. US (34 indicators)

### Equity - Growth

| ID | Short Name | Regime Thresholds | Positive Label | Neutral | Negative Label |
|---|---|---|---|---|---|
| US_G1 | Cyclicals vs Defensives | z +/-1 | `pro-growth` | `neutral` | `defensive` |
| US_G2 | Broader Cyclicals vs Defensives | z +/-1 | `risk-on` | `neutral` | `late-cycle` |
| US_G3 | Banks vs Utilities | z +/-1 | `risk-on` | `neutral` | `defensive` |
| US_G5 | Technology Leadership | z +/-1 | `tech-led` | `neutral` | `defensive-rotation` |
| US_G4 | Market Breadth (RSP/SPY) | z +/-1 | `broad-rally` | `neutral` | `narrow-concentrated` |

### Equity - Factor (Style)

| ID | Short Name | Regime Thresholds | Positive Label | Neutral | Negative Label |
|---|---|---|---|---|---|
| US_EQ_F1 | Value vs Growth (Russell) | z +/-1 | `value-regime` | `mixed` | `growth-regime` |
| US_EQ_F2 | Value vs Growth (S&P) | *mirrors US_EQ_F1* | | | |

### Equity - Factor (Size)

| ID | Short Name | Regime Thresholds | Positive Label | Neutral | Negative Label |
|---|---|---|---|---|---|
| US_EQ_F3 | Size Cycle (Russell) | z +/-1 | `small-cap-lead` | `neutral` | `large-cap-safety` |
| US_EQ_F4 | Size Cycle (S&P) | *mirrors US_EQ_F3* | | | |

### CrossAsset - Growth

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| US_CA_G1 | Risk-On vs Risk-Off (SPY/GOVT) | z +/-1 | `risk-on` / `neutral` / `risk-off` |

### Credit

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| US_Cr2 **+** | HY Credit Spread | >800bps or z>+2: `opportunity`; >500bps & z>+1: `stress`; 400-600 & |z|<1: `normal`; <400 & z<-0.5: `complacent`; <300 & z<-1: `frothy` | 5-regime framework |
| US_Cr1 | IG Credit Spread | z +/-1 | `ig-stress` / `normal` / `ig-compressed` |
| US_Cr3 | HY-IG Differential | z +/-1 | `credit-stress` / `normal` / `credit-compressed` |
| US_Cr4 | HY vs Treasuries | z +/-1 | `hy-risk-on` / `neutral` / `hy-risk-off` |

### Rates - Growth

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| US_R1 **+** | Yield Curve 10Y-3M | Spread < 0: `recession-watch`; > 0 & z > +1: `early-cycle`; > 0 & |z| <= 1: `mid-cycle`; > 0 & z < -1: `late-cycle` | Level override at inversion |
| US_R2 | Yield Curve 2s10s (FRED) | *mirrors US_R1 interpretation* | |
| US_R3 | Yield Curve 2s10s (Market) | *mirrors US_R1 interpretation* | |

### Rates - Inflation

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| US_R4 | 10Y Breakeven Inflation | z +/-1 | `inflation-elevated` / `neutral` / `disinflation` |

### Rates

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| US_R5 | Real Rates (TIPS 10Y) | z +/-1 | `high-real-rates` / `normal` / `low-real-rates` |
| US_R6 | Mortgage Credit Spread | z +/-1 | `mortgage-stress` / `normal` / `mortgage-easing` |

### Volatility

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| US_V1 **+** | VIX Term Structure | VIX3M - VIX < 0: `stress`; > 0 & z < -1: `complacency`; > 0 & |z| <= 1: `normal` | Level override at inversion |
| US_V2 | MOVE/VIX Ratio | z +/-1 | `rates-vol-elevated` / `normal` / `equity-vol-elevated` |

### Macro

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| US_JOBS1 | Initial Jobless Claims | z +/-1 | `labour-deteriorating` / `stable` / `labour-tight` |
| US_JOBS3 | Labour Market Composite | z +/-1 | `labour-strong` / `labour-balanced` / `labour-weak` |
| US_G6 | Real Activity Composite | z +/-1 | `strong-growth` / `normal` / `weak-growth` |
| US_HOUS1 | Housing / Building Permits | z +/-1 | `housing-expanding` / `neutral` / `housing-contracting` |
| US_M2 | M2 Money Supply Growth | z +/-1 | `abundant-liquidity` / `neutral` / `tight-liquidity` |
| US_JOBS2 | JOLTS Tightness | z +/-1 | `labour-tight` / `balanced` / `labour-slack` |

### Macro - Survey

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| US_ISM1 **+** | ISM Mfg New Orders | Level > 52: `ism-expansion`; 48-52: `ism-neutral`; < 48: `ism-contraction` | Absolute level thresholds |

### Mmtm - Equity

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| M1 | US Equity Trend | log ratio > 0 / < 0 | `trend-up` / `trend-down` |

### Mmtm - CrossAsset

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| M2 | Multi-Asset Trend Breadth | >= 0.6 / 0.4-0.6 / <= 0.4 | `risk-on` / `mixed` / `risk-off` |
| M3 | Dual Momentum | Rule-based | `US-equity-regime` / `global-equity-regime` / `bond-regime` |

### Mmtm - Credit

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| M4 **+** | HY Trend + Spread Override | log > 0 AND OAS <= 600: `carry-regime`; else: `stress-regime` | Level override at 600bps |

### Mmtm - Volatility

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| M5 | VIX Regime Filter | log ratio < 0 / > 0 | `vol-compressing` / `vol-expanding` |

**Narrative themes:**
- *Growth rotation*: US_G1 + US_G2 both `pro-growth` / `risk-on` = broad cyclical recovery; strongest when combined with steepening yield curve (US_R1)
- *Narrow market*: US_G4 `narrow-concentrated` + US_G5 `tech-led` = mega-cap tech carrying the market; fragile if rates rise
- *Value revival*: US_EQ_F1 `value-regime` + US_G3 `risk-on` (banks leading) = interest-rate-sensitive value rotation; typical in early/mid cycle
- *Credit stress cascade*: US_Cr2 `stress` + US_V1 `stress` (inverted vol curve) = active deleveraging; watch FX_2 (carry unwind) for global transmission
- *Yield curve inversion alert*: US_R1 `recession-watch` = the single most historically reliable recession predictor; strongest when sustained > 3 months
- *Hard landing signals*: US_JOBS1 `labour-deteriorating` + US_G6 `weak-growth` + US_ISM1 `ism-contraction` = recession probability elevated
- *Momentum alignment*: M1 `trend-up` + M2 `risk-on` + M4 `carry-regime` = all trend signals confirming risk-on

---

## 2. UK (4 indicators)

### Equity - Growth

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| UK_G1 | UK Domestic vs Global | z +/-1 | `uk-domestic-strength` / `neutral` / `uk-global-preference` |

### Credit

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| UK_Cr1 | UK Credit Conditions | z +/-1 | `uk-credit-appetite` / `neutral` / `uk-flight-to-quality` |

### Rates - Growth

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| UK_R1 | UK-Germany 10Y Spread | z +/-1 | `uk-risk-premium` / `normal` / `uk-relative-strength` |

### Rates - Inflation

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| UK_R2 | UK Inflation Expectations | z +/-1 | `uk-inflation-elevated` / `neutral` / `uk-disinflation` |

**Narrative themes:**
- *Brexit Britain recovery*: UK_G1 `uk-domestic-strength` + UK_Cr1 `uk-credit-appetite` = UK-specific domestic recovery; often driven by housing and consumer credit
- *UK inflation problem*: UK_R2 `uk-inflation-elevated` + UK_R1 `uk-risk-premium` = BoE credibility under pressure; negative for gilts

---

## 3. Europe (7 indicators)

### Equity - Growth

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| EU_G3 | European Cyclicals vs Defensives | z +/-1 | `pro-growth-europe` / `neutral` / `defensive-europe` |
| EU_G2 | Eurozone vs US | z +/-1 | `eurozone-outperform` / `neutral` / `us-dominance` |
| EU_G4 | EUR Macro Composite | z +/-1 | `eurozone-macro-strong` / `neutral` / `eurozone-under-strain` |
| EU_G1 | Eurozone vs Global | z +/-1 | `eurozone-outperform` / `neutral` / `eurozone-underperform` |

### Credit

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| EU_Cr1 | Euro IG Spread | z +/-1 | `euro-credit-stress` / `normal` / `compressed-spreads` |

### Rates - Growth

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| EU_R1 **+** | BTP-Bund Spread | Raw > 2.5% or z > +1.5: `peripheral-stress`; |z| <= 1: `normal`; z < -1: `compressed` | Level override + asymmetric z |

### CLI

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| EU_CLI1 **+** | Europe Block CLI | CLI > 100 & z > +1: `EU-above-trend`; CLI ~ 100 & |z| <= 1: `EU-near-trend`; CLI < 100 & z < -1: `EU-below-trend` | Level + z-score |

**Narrative themes:**
- *Europe awakening*: EU_G1 `eurozone-outperform` + EU_G3 `pro-growth-europe` + EU_G4 `eurozone-macro-strong` = rare but powerful European bull signal; strongest when EU_R1 `compressed`
- *Peripheral risk*: EU_R1 `peripheral-stress` = Italian sovereign risk repricing; contagion risk to European banks
- *EUR credibility*: EU_G2 `eurozone-outperform` vs US + EU_G4 `eurozone-macro-strong` = genuine European fundamental improvement, not just USD weakness

---

## 4. Japan (1 indicator)

### Equity - Growth

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| JP_G1 | Japan vs Global Equities | z +/-1 | `japan-outperform` / `neutral` / `japan-underperform` |

**Narrative themes:**
- *Japan + carry alignment*: JP_G1 `japan-outperform` + FX_2 `carry-on` = carry trade ON and Japanese export earnings supportive
- *Domestically-driven Japan*: JP_G1 positive + FX_2 negative (JPY strengthening) = rarer but more durable quality expansion

---

## 5. Asia (7 indicators)

### CLI

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| AS_CLI1 **+** | Asia-Pacific Block CLI | CLI > 100 & z > +1: `Asia-above-trend`; |z| <= 1: `Asia-near-trend`; CLI < 100 & z < -1: `Asia-below-trend` | Level + z-score |

### China - Equity (Growth)

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| AS_CN_G2 | China vs Global DM | z +/-1 | `china-outperform` / `neutral` / `china-underperform` |
| AS_CN_G1 | China vs Broad EM | z +/-1 | `china-driving-EM` / `neutral` / `non-china-EM-leading` |

### China - Equity - Factor (Size)

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| AS_CN_G3 | China Size Cycle | z +/-1 | `china-domestic-breadth` / `neutral` / `china-large-cap-safety` |

### China - Rates

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| AS_CN_R1 | China-US Yield Spread | z +/-1 | `china-carry-attractive` / `neutral` / `china-carry-unattractive` |

### India - Equity - Factor (Size)

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| AS_IN_G1 | India Domestic Growth Breadth | z +/-1 | `india-domestic-expansion` / `neutral` / `india-large-cap-safety` |

### India - Rates

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| AS_IN_R1 | India-US Yield Spread | z +/-1 | `india-carry-attractive` / `neutral` / `india-carry-unattractive` |

**Narrative themes:**
- *China stimulus trade*: AS_CN_G2 `china-outperform` + AS_CN_G3 `china-domestic-breadth` + FX_CN1 `CNY-strengthening` = trifecta of Chinese recovery
- *China vs rest of EM*: AS_CN_G1 `china-driving-EM` = China policy stimulus lifting all boats; `non-china-EM-leading` = India/Korea/Taiwan tech cycle driving EM
- *India structural story*: AS_IN_G1 `india-domestic-expansion` + FX_1 `INR-strengthening` = India's domestic-led growth cycle is alive

---

## 6. Global (6 indicators)

### CrossAsset - Growth

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| GL_G2 | Global Risk Appetite (ACWI/GOVT) | z +/-1 | `global-risk-on` / `neutral` / `global-risk-off` |
| GL_G1 | EM vs DM (EEM/URTH) | z +/-1 | `EM-outperform` / `neutral` / `DM-outperform` |

### CrossAsset - Inflation

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| GL_CA_I1 | Commodities vs Bonds | z +/-1 | `reflation` / `balanced` / `deflation-scare` |

### CLI

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| GL_CLI1 | US vs Eurozone Growth | z +/-1 | `US-leads-EU` / `neutral` / `EU-leads-US` |
| GL_CLI2 | US vs China Growth | z +/-1 | `US-leads-China` / `neutral` / `China-leads-US` |
| GL_CLI5 **+** | Global Growth Breadth | Fraction >= 0.7: `broad-expansion`; 0.4-0.7: `mixed`; < 0.4: `contracting` | Fraction-based (naturally leading) |

**Narrative themes:**
- *Synchronised global expansion*: GL_CLI5 `broad-expansion` + GL_G2 `global-risk-on` = most bullish macro backdrop; raise equity beta, favour EM and HY
- *Global contraction*: GL_CLI5 `contracting` + GL_G2 `global-risk-off` = de-risk; favour quality, IG, core government bonds
- *EM rotation window*: GL_G1 `EM-outperform` + FX_CMD2 `weak-USD` + FX_CMD6 `commodity-bull` = highest-conviction EM overweight signal

---

## 7. FX & Commodities (9 indicators)

### CrossAsset - Growth

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| FX_CMD2 | Dollar vs EM & Commodities | z +/-1 | `weak-USD` / `neutral` / `strong-USD` |
| FX_CMD1 | Copper / Gold | z +/-1 | `pro-growth` / `neutral` / `growth-scare` |

### China - FX Mmtm

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| FX_CN1 | CNY Momentum | z +/-1 | `CNY-strengthening` / `neutral` / `CNY-weakening` |

### India - FX Mmtm

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| FX_1 | INR Momentum | z +/-1 | `INR-strengthening` / `neutral` / `INR-weakening` |

### Japan - FX Mmtm

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| FX_2 **+** | JPY Carry Trade Signal | z > +0.5: `carry-on`; -1 to +0.5: `neutral`; z < -1: `carry-unwind` | Asymmetric thresholds |

### Growth (China infra)

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| FX_CMD5 | Iron Ore / Copper | z +/-1 | `china-infra-led` / `neutral` / `global-industrial-led` |

### Growth (China broad)

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| FX_CMD4 | Iron Ore / Broad Commodities | z +/-1 | `china-commodity-leading` / `neutral` / `global-commodity-leading` |

### Growth Mmtm

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| FX_CMD6 | Commodity Cycle Momentum | z +/-1 | `commodity-bull` / `neutral` / `commodity-bear` |

### Inflation

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| FX_CMD3 | Oil vs Gold | z +/-1 | `growth-inflation` / `balanced` / `deflation-risk` |

**Narrative themes:**
- *King Dollar*: FX_CMD2 `strong-USD` = headwind for EM, commodities, multinational earnings; typically aligns with Fed hawkishness
- *Carry unwind alert*: FX_2 `carry-unwind` = **systemic risk-off signal**; JPY strengthening precedes equity/EM damage by 2-4 weeks
- *China infrastructure cycle*: FX_CMD5 `china-infra-led` + FX_CMD4 `china-commodity-leading` = China heavy-industry stimulus is dominant commodity driver
- *Growth-inflation conviction*: FX_CMD1 `pro-growth` + FX_CMD3 `growth-inflation` = high-conviction growth-driven reflation

---

## Non-Standard Threshold Summary

Nine indicators use non-standard regime logic:

| ID | Type | Key Rule |
|---|---|---|
| US_R1 | Level override | Spread < 0 (inversion) → `recession-watch` regardless of z |
| US_Cr2 | Absolute levels | 5-regime framework using HY spread bps (300/400/500/800) |
| US_V1 | Level override | VIX3M - VIX < 0 (inversion) → `stress` regardless of z |
| US_ISM1 | Absolute levels | ISM New Orders: 48/52 thresholds |
| M4 | Level override | OAS > 600bps overrides trend signal → `stress-regime` |
| EU_R1 | Level + asymmetric z | BTP-Bund raw > 2.5% overrides z; uses +1.5/-1 asymmetric |
| FX_2 | Asymmetric z | +0.5 / -1 (lower bar for carry-on, higher bar for carry-unwind) |
| EU_CLI1 | Level + z | CLI > 100 AND z > +1 required for `above-trend` |
| AS_CLI1 | Level + z | CLI > 100 AND z > +1 required for `above-trend` |
| GL_CLI5 | Fraction-based | 0.4/0.7 fraction of 9 countries meeting dual condition |

---

## Cross-Indicator Confirmation Patterns — Macro Quadrants

These are the highest-conviction multi-indicator signals, organised by the four macro regimes defined by the intersection of growth and inflation conditions.

### Quadrant 1: Growth + / Inflation + (Reflation / Boom)

*Economy expanding, prices rising. Favour cyclicals, commodities, value, short duration.*

**Growth signals:**
- US_G1 `pro-growth` + US_G2 `risk-on` + US_G4 `broad-rally`
- US_ISM1 `ism-expansion` + US_G6 `strong-growth`
- GL_CLI5 `broad-expansion` + GL_G2 `global-risk-on`
- M1 `trend-up` + M2 `risk-on`

**Inflation signals:**
- US_R4 `inflation-elevated` + US_R5 `low-real-rates`
- GL_CA_I1 `reflation` (commodities outperforming bonds)
- FX_CMD3 `growth-inflation` (oil outperforming gold)
- FX_CMD1 `pro-growth` (copper outperforming gold)
- FX_CMD6 `commodity-bull`

**Positioning:** OW cyclicals, value, energy, materials, commodity exporters. UW long-duration bonds, defensives. Add inflation-linked bonds (TIPS). OW EM if FX_CMD2 `weak-USD`.

---

### Quadrant 2: Growth + / Inflation - (Goldilocks / Disinflation Boom)

*Economy expanding, prices stable or falling. Favour growth equities, credit, duration-neutral.*

**Growth signals:**
- US_G1 `pro-growth` + US_G4 `broad-rally`
- US_R1 `early-cycle` or `mid-cycle` (no inversion)
- US_JOBS2 `balanced` + US_G6 `normal` or `strong-growth`
- GL_CLI5 `broad-expansion` or `mixed` trending up
- US_Cr2 `normal` or `complacent` (credit healthy)

**Disinflation signals:**
- US_R4 `neutral` or `disinflation`
- GL_CA_I1 `balanced` or `deflation-scare`
- FX_CMD3 `balanced` or `deflation-risk`
- US_R5 `normal` or `high-real-rates` (real rates not being inflated away)
- US_M2 `neutral` (no excess liquidity)

**Positioning:** OW growth equities (US_G5 `tech-led` is supportive here), quality credit (IG and HY if US_Cr2 healthy). Neutral duration. This is the environment that supports equity multiple expansion. OW US if GL_CLI1 `US-leads-EU`.

---

### Quadrant 3: Growth - / Inflation + (Stagflation)

*Economy weakening, prices still rising. The worst quadrant for traditional portfolios. Favour real assets, gold, short duration.*

**Growth deterioration signals:**
- US_R1 `recession-watch` or `late-cycle`
- US_JOBS1 `labour-deteriorating` + US_G6 `weak-growth`
- US_ISM1 `ism-contraction`
- GL_CLI5 `contracting` or `mixed` trending down
- US_V1 `stress` (inverted vol term structure)
- M1 `trend-down` + M2 `risk-off`

**Persistent inflation signals:**
- US_R4 `inflation-elevated`
- GL_CA_I1 `reflation` (commodities still outperforming bonds despite weak growth)
- FX_CMD3 `growth-inflation` BUT FX_CMD1 `growth-scare` (oil up on supply shock, copper weak = supply-driven inflation, not demand)
- UK_R2 `uk-inflation-elevated` (stagflation often hits UK hardest)

**Positioning:** OW gold, commodities as inflation hedge, TIPS. UW equities broadly, especially long-duration growth. UW long-duration nominal bonds. Reduce HY (US_Cr2 likely moving to `stress`). Cash is a valid position. This quadrant is rare but devastating.

---

### Quadrant 4: Growth - / Inflation - (Deflation / Recession)

*Economy contracting, prices falling. Favour duration, quality, safe havens.*

**Growth deterioration signals:**
- US_R1 `recession-watch` (inverted yield curve sustained > 3 months)
- US_Cr2 `stress` or `opportunity` + US_Cr3 widening
- US_JOBS1 `labour-deteriorating` + US_JOBS2 `labour-slack`
- US_V1 `stress` (inverted vol term structure)
- GL_CLI5 `contracting` + GL_G2 `global-risk-off`
- FX_2 `carry-unwind` (systemic deleveraging)
- M1 `trend-down` + M2 `risk-off` + M4 `stress-regime`

**Deflation signals:**
- US_R4 `disinflation` + US_R5 `high-real-rates`
- GL_CA_I1 `deflation-scare` (bonds outperforming commodities)
- FX_CMD3 `deflation-risk` (gold outperforming oil)
- FX_CMD1 `growth-scare` (gold outperforming copper)
- FX_CMD6 `commodity-bear`
- US_M2 `tight-liquidity`

**Positioning:** Max duration (long-dated govts). OW quality/defensives. UW equities, especially cyclicals and EM. Reduce HY and EM debt. Add JPY exposure (carry unwind benefits yen). US_Cr2 at `opportunity` (>800bps) is historically the highest-conviction credit entry point — but only if growth signals begin stabilising.

---

## Naturally Leading Indicators

These indicators are flagged as naturally leading — their current reading already embeds a forward signal:

| ID | Lead Mechanism | Typical Lead Time |
|---|---|---|
| US_R1 | Yield curve leads recession by 12-18 months | 12-18 months |
| US_JOBS1 | Initial claims lead payroll deterioration | 2-4 months |
| US_HOUS1 | Building permits lead construction employment | 6-9 months |
| US_ISM1 | New orders lead industrial production | 3-6 months |
| US_M2 | Money supply leads nominal GDP and asset prices | 3-6 months |
| FX_2 | JPY carry move precedes equity/EM impact | Days to 2-4 weeks |
| GL_CLI5 | CLIs are themselves forward-looking | 6-9 months |
| GL_CLI2 | CLI differential leads relative equity returns | 6-9 months |

---

*End of Cheat Sheet — companion to the Indicator Manual (68 indicators across 7 sections: US, UK, Europe, Japan, Asia, Global, FX & Commodities)*
