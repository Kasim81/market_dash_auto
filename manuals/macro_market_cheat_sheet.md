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

## 1. US Equity — Growth & Style (9 indicators)

| ID | Short Name | Regime Thresholds | Positive Label | Neutral | Negative Label |
|---|---|---|---|---|---|
| US_G1 | Cyclicals vs Defensives | z +/-1 | `pro-growth` | `neutral` | `defensive` |
| US_G2 | Broader Cyclicals vs Defensives | z +/-1 | `risk-on` | `neutral` | `late-cycle` |
| US_G3 | Banks vs Utilities | z +/-1 | `risk-on` | `neutral` | `defensive` |
| US_G4 | Market Breadth (RSP/SPY) | z +/-1 | `broad-rally` | `neutral` | `narrow-concentrated` |
| US_G5 | Technology Leadership | z +/-1 | `tech-led` | `neutral` | `defensive-rotation` |
| US_EQ_F1 | Value vs Growth (Russell) | z +/-1 | `value-regime` | `mixed` | `growth-regime` |
| US_EQ_F2 | Value vs Growth (S&P) | *mirrors US_EQ_F1* | | | |
| US_EQ_F3 | Size Cycle (Russell) | z +/-1 | `small-cap-lead` | `neutral` | `large-cap-safety` |
| US_EQ_F4 | Size Cycle (S&P) | *mirrors US_EQ_F3* | | | |

**Narrative themes:**
- *Growth rotation*: US_G1 + US_G2 both `pro-growth` / `risk-on` = broad cyclical recovery; strongest signal when combined with steepening yield curve (US_R1)
- *Narrow market*: US_G4 `narrow-concentrated` + US_G5 `tech-led` = mega-cap tech carrying the market; fragile if rates rise
- *Value revival*: US_EQ_F1 `value-regime` + US_G3 `risk-on` (banks leading) = interest-rate-sensitive value rotation; typical in early/mid cycle
- *Defensive tilt*: US_G1 `defensive` + US_G5 `defensive-rotation` = late-cycle or recession-positioning; check credit (US_Cr2) for confirmation

---

## 2a. US Rates, Credit & Volatility (14 indicators)

### Rates

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| US_R1 **+** | Yield Curve 10Y-3M | Spread < 0: `recession-watch`; > 0 & z > +1: `early-cycle`; > 0 & |z| <= 1: `mid-cycle`; > 0 & z < -1: `late-cycle` | Level override at inversion |
| US_R2 | Yield Curve 2s10s (FRED) | *mirrors US_R1 interpretation* | |
| US_R3 | Yield Curve 2s10s (Market) | *mirrors US_R1 interpretation* | |
| US_R4 | 10Y Breakeven Inflation | z +/-1 | `inflation-elevated` / `neutral` / `disinflation` |
| US_R5 | Real Rates (TIPS 10Y) | z +/-1 | `high-real-rates` / `normal` / `low-real-rates` |
| US_R6 | Mortgage Credit Spread | z +/-1 | `mortgage-stress` / `normal` / `mortgage-easing` |

### Credit

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| US_Cr2 **+** | HY Credit Spread | >800bps or z>+2: `opportunity`; >500bps & z>+1: `stress`; 400-600 & |z|<1: `normal`; <400 & z<-0.5: `complacent`; <300 & z<-1: `frothy` | 5-regime framework |
| US_Cr1 | IG Credit Spread | z +/-1 | `ig-stress` / `normal` / `ig-compressed` |
| US_Cr3 | HY-IG Differential | z +/-1 | `credit-stress` / `normal` / `credit-compressed` |
| US_Cr4 | HY vs Treasuries | z +/-1 | `hy-risk-on` / `neutral` / `hy-risk-off` |
| GL_CA_I1 | Commodities vs Bonds | z +/-1 | `reflation` / `balanced` / `deflation-scare` |
| US_CA_G1 | Risk-On vs Risk-Off (SPY/GOVT) | z +/-1 | `risk-on` / `neutral` / `risk-off` |

### Volatility

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| US_V1 **+** | VIX Term Structure | VIX3M - VIX < 0: `stress`; > 0 & z < -1: `complacency`; > 0 & |z| <= 1: `normal` | Level override at inversion |
| US_V2 | MOVE/VIX Ratio | z +/-1 | `rates-vol-elevated` / `normal` / `equity-vol-elevated` |

**Narrative themes:**
- *Yield curve inversion alert*: US_R1 `recession-watch` = the single most historically reliable recession predictor; strongest when sustained > 3 months
- *Credit stress cascade*: US_Cr2 `stress` + US_V1 `stress` (inverted vol curve) = active deleveraging; watch FX_2 (carry unwind) for global transmission
- *5-regime HY framework*: US_Cr2 at `opportunity` (>800bps) is historically the highest-conviction entry point for credit; `frothy` (<300bps) is the highest-risk exit signal
- *Reflation trade*: GL_CA_I1 `reflation` + US_R4 `inflation-elevated` + US_R5 `low-real-rates` = commodity/inflation-linked positioning; negative for long-duration bonds
- *Vol divergence*: US_V2 extreme = rates and equity vol decoupled; if MOVE elevated but VIX compressed, bond market is pricing risk that equity market is ignoring

---

## 2b. US Dollar, Commodities & Momentum (7 indicators)

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| FX_CMD2 | Dollar vs EM & Commodities | z +/-1 | `weak-USD` / `neutral` / `strong-USD` |
| FX_CMD1 | Copper / Gold | z +/-1 | `pro-growth` / `neutral` / `growth-scare` |
| M1 | US Equity Trend | log ratio > 0 / < 0 | `trend-up` / `trend-down` |
| M2 | Multi-Asset Trend Breadth | >= 0.6 / 0.4-0.6 / <= 0.4 | `risk-on` / `mixed` / `risk-off` |
| M3 | Dual Momentum | Rule-based | `US-equity-regime` / `global-equity-regime` / `bond-regime` |
| M4 **+** | HY Trend + Spread Override | log > 0 AND OAS <= 600: `carry-regime`; else: `stress-regime` | Level override at 600bps |
| M5 | VIX Regime Filter | log ratio < 0 / > 0 | `vol-compressing` / `vol-expanding` |

**Narrative themes:**
- *King Dollar*: FX_CMD2 `strong-USD` = headwind for EM, commodities, and multinational earnings; typically aligns with Fed hawkishness
- *Global growth conviction*: FX_CMD1 `pro-growth` + M2 `risk-on` + M1 `trend-up` = high-conviction risk-on; all asset classes aligned
- *Momentum regime shift*: M1 flips `trend-down` while M2 still `risk-on` = early warning of US equity divergence from other assets
- *Carry with confidence*: M4 `carry-regime` + US_Cr2 `normal` or better = high-yield carry trade supported by both trend and fundamentals

---

## 3a. US Macro Fundamentals (7 indicators)

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| US_JOBS1 | Initial Jobless Claims | z +/-1 | `labour-deteriorating` / `stable` / `labour-tight` |
| US_JOBS2 | JOLTS Tightness | z +/-1 | `labour-tight` / `balanced` / `labour-slack` |
| US_JOBS3 | Labour Market Composite | z +/-1 | `labour-strong` / `labour-balanced` / `labour-weak` |
| US_G6 | Real Activity Composite | z +/-1 | `strong-growth` / `normal` / `weak-growth` |
| US_HOUS1 | Housing / Building Permits | z +/-1 | `housing-expanding` / `neutral` / `housing-contracting` |
| US_M2 | M2 Money Supply Growth | z +/-1 | `abundant-liquidity` / `neutral` / `tight-liquidity` |
| US_ISM1 **+** | ISM Mfg New Orders | Level > 52: `ism-expansion`; 48-52: `ism-neutral`; < 48: `ism-contraction` | Absolute level thresholds |

**Narrative themes:**
- *Hard landing signals*: US_JOBS1 `labour-deteriorating` + US_G6 `weak-growth` + US_ISM1 `ism-contraction` = recession probability elevated; strongest when yield curve already inverted (US_R1)
- *Goldilocks*: US_JOBS2 `balanced` + US_G6 `normal` + US_M2 `neutral` = neither too hot nor too cold; supports equity multiples
- *Housing cycle turn*: US_HOUS1 shift from `housing-contracting` to `expanding` is one of the most reliable early-cycle signals; leads employment by 6-9 months
- *Liquidity impulse*: US_M2 `abundant-liquidity` = monetary conditions easing; historically leads equity and credit markets by 3-6 months

---

## 3b. Europe & UK (10 indicators)

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| EU_G1 | Eurozone vs Global | z +/-1 | `eurozone-outperform` / `neutral` / `eurozone-underperform` |
| EU_G2 | Eurozone vs US | z +/-1 | `eurozone-outperform` / `neutral` / `us-dominance` |
| EU_G3 | European Cyclicals vs Defensives | z +/-1 | `pro-growth-europe` / `neutral` / `defensive-europe` |
| EU_G4 | EUR Macro Composite | z +/-1 | `eurozone-macro-strong` / `neutral` / `eurozone-under-strain` |
| EU_Cr1 | Euro IG Spread | z +/-1 | `euro-credit-stress` / `normal` / `compressed-spreads` |
| EU_R1 **+** | BTP-Bund Spread | Raw > 2.5% or z > +1.5: `peripheral-stress`; |z| <= 1: `normal`; z < -1: `compressed` | Level override + asymmetric z |
| UK_G1 | UK Domestic vs Global | z +/-1 | `uk-domestic-strength` / `neutral` / `uk-global-preference` |
| UK_R1 | UK-Germany 10Y Spread | z +/-1 | `uk-risk-premium` / `normal` / `uk-relative-strength` |
| UK_R2 | UK Inflation Expectations | z +/-1 | `uk-inflation-elevated` / `neutral` / `uk-disinflation` |
| UK_Cr1 | UK Credit Conditions | z +/-1 | `uk-credit-appetite` / `neutral` / `uk-flight-to-quality` |

**Narrative themes:**
- *Europe awakening*: EU_G1 `eurozone-outperform` + EU_G3 `pro-growth-europe` + EU_G4 `eurozone-macro-strong` = rare but powerful European bull signal; strongest when EU_R1 `compressed` (no peripheral stress)
- *Peripheral risk*: EU_R1 `peripheral-stress` = Italian sovereign risk repricing; contagion risk to European banks (EU_G3 typically goes `defensive-europe` simultaneously)
- *Brexit Britain*: UK_G1 `uk-domestic-strength` + UK_Cr1 `uk-credit-appetite` = UK-specific recovery; often driven by housing and consumer credit
- *EUR credibility*: EU_G2 `eurozone-outperform` vs US is rare and newsworthy; when combined with EU_G4 `eurozone-macro-strong`, indicates genuine European fundamental improvement not just USD weakness

---

## 4a. Asia — China & India (8 indicators)

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| AS_CN_G1 | China vs Broad EM | z +/-1 | `china-driving-EM` / `neutral` / `non-china-EM-leading` |
| AS_CN_G2 | China vs Global DM | z +/-1 | `china-outperform` / `neutral` / `china-underperform` |
| AS_CN_G3 | China Size Cycle | z +/-1 | `china-domestic-breadth` / `neutral` / `china-large-cap-safety` |
| AS_IN_G1 | India Domestic Growth Breadth | z +/-1 | `india-domestic-expansion` / `neutral` / `india-large-cap-safety` |
| AS_CN_R1 | China-US Yield Spread | z +/-1 | `china-carry-attractive` / `neutral` / `china-carry-unattractive` |
| AS_IN_R1 | India-US Yield Spread | z +/-1 | `india-carry-attractive` / `neutral` / `india-carry-unattractive` |
| FX_CN1 | CNY Momentum | z +/-1 | `CNY-strengthening` / `neutral` / `CNY-weakening` |
| FX_1 | INR Momentum | z +/-1 | `INR-strengthening` / `neutral` / `INR-weakening` |

**Narrative themes:**
- *China stimulus trade*: AS_CN_G2 `china-outperform` + AS_CN_G3 `china-domestic-breadth` + FX_CN1 `CNY-strengthening` = trifecta of Chinese recovery; positive for commodities (FX_CMD5, FX_CMD4) and AUD
- *China vs rest of EM*: AS_CN_G1 `china-driving-EM` = China policy stimulus lifting all boats; `non-china-EM-leading` = India/Korea/Taiwan tech cycle driving EM instead
- *India structural story*: AS_IN_G1 `india-domestic-expansion` + FX_1 `INR-strengthening` = India's domestic-led growth cycle is alive; positive for domestic banks, consumer discretionary
- *Asia carry divergence*: AS_CN_R1 and AS_IN_R1 moving in opposite directions = differentiated Asia positioning; India carry trades behave differently from China carry trades

---

## 4b. Asia Commodities & Japan (4 indicators)

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| FX_CMD5 | Iron Ore / Copper | z +/-1 | `china-infra-led` / `neutral` / `global-industrial-led` |
| FX_CMD4 | Iron Ore / Broad Commodities | z +/-1 | `china-commodity-leading` / `neutral` / `global-commodity-leading` |
| JP_G1 | Japan vs Global Equities | z +/-1 | `japan-outperform` / `neutral` / `japan-underperform` |
| FX_2 **+** | JPY Carry Trade Signal | z > +0.5: `carry-on`; -1 to +0.5: `neutral`; z < -1: `carry-unwind` | Asymmetric thresholds |

**Narrative themes:**
- *China infrastructure cycle*: FX_CMD5 `china-infra-led` + FX_CMD4 `china-commodity-leading` = China-specific heavy-industry stimulus is dominant global commodity driver; OW iron ore miners, bulk shippers, AUD
- *Carry unwind alert*: FX_2 `carry-unwind` = **systemic risk-off signal**; JPY strengthening precedes equity/EM damage by 2-4 weeks; historically the single most important forced-deleveraging signal in the library
- *Japan + carry alignment*: JP_G1 `japan-outperform` + FX_2 `carry-on` = carry trade is ON and Japanese export earnings supportive; if JP_G1 positive but FX_2 negative = higher-quality domestically-driven Japanese expansion

---

## 4c. Global & Regional (9 indicators)

| ID | Short Name | Regime Thresholds | Labels |
|---|---|---|---|
| GL_CLI1 | US vs Eurozone Growth | z +/-1 | `US-leads-EU` / `neutral` / `EU-leads-US` |
| GL_CLI2 | US vs China Growth | z +/-1 | `US-leads-China` / `neutral` / `China-leads-US` |
| EU_CLI1 **+** | Europe Block CLI | CLI > 100 & z > +1: `EU-above-trend`; CLI ~ 100 & |z| <= 1: `EU-near-trend`; CLI < 100 & z < -1: `EU-below-trend` | Level + z-score |
| AS_CLI1 **+** | Asia-Pacific Block CLI | CLI > 100 & z > +1: `Asia-above-trend`; |z| <= 1: `Asia-near-trend`; CLI < 100 & z < -1: `Asia-below-trend` | Level + z-score |
| GL_CLI5 **+** | Global Growth Breadth | Fraction >= 0.7: `broad-expansion`; 0.4-0.7: `mixed`; < 0.4: `contracting` | Fraction-based (naturally leading) |
| GL_G2 | Global Risk Appetite (ACWI/GOVT) | z +/-1 | `global-risk-on` / `neutral` / `global-risk-off` |
| GL_G1 | EM vs DM (EEM/URTH) | z +/-1 | `EM-outperform` / `neutral` / `DM-outperform` |
| FX_CMD6 | Commodity Cycle Momentum | z +/-1 | `commodity-bull` / `neutral` / `commodity-bear` |
| FX_CMD3 | Oil vs Gold | z +/-1 | `growth-inflation` / `balanced` / `deflation-risk` |

**Narrative themes:**
- *Synchronised global expansion*: GL_CLI5 `broad-expansion` (>= 7/9 countries above trend) + GL_G2 `global-risk-on` = the most bullish macro backdrop possible; raise equity beta across regions, favour EM and HY
- *Global contraction*: GL_CLI5 `contracting` (< 4/9) + GL_G2 `global-risk-off` = de-risk; favour quality, IG, core government bonds, reduce EM/HY
- *EM rotation window*: GL_G1 `EM-outperform` + FX_CMD2 `weak-USD` + FX_CMD6 `commodity-bull` = all three EM conditions met simultaneously; historically the highest-conviction EM overweight signal
- *Reflation vs deflation*: FX_CMD3 `growth-inflation` + FX_CMD1 `pro-growth` = high-conviction growth-driven reflation; FX_CMD3 `deflation-risk` + FX_CMD1 `growth-scare` = deflation/recession positioning
- *Regional leadership*: GL_CLI1 and GL_CLI2 determine the primary equity regional tilt; when both point `US-leads`, dollar-denominated US assets are the gravitational centre

---

## Non-Standard Threshold Summary

Nine indicators use non-standard regime logic:

| ID | Type | Key Rule |
|---|---|---|
| US_R1 | Level override | Spread < 0 (inversion) → `recession-watch` regardless of z |
| US_Cr2 | Absolute levels | 5-regime framework using HY spread bps (300/400/500/800) |
| US_V1 | Level override | VIX3M - VIX < 0 (inversion) → `stress` regardless of z |
| US_ISM1 | Absolute levels | ISM New Orders: 48/52 thresholds |
| EU_R1 | Level + asymmetric z | BTP-Bund raw > 2.5% overrides z; uses +1.5/-1 asymmetric |
| FX_2 | Asymmetric z | +0.5 / -1 (lower bar for carry-on, higher bar for carry-unwind) |
| EU_CLI1 | Level + z | CLI > 100 AND z > +1 required for `above-trend` |
| AS_CLI1 | Level + z | CLI > 100 AND z > +1 required for `above-trend` |
| GL_CLI5 | Fraction-based | 0.4/0.7 fraction of 9 countries meeting dual condition |

---

## Cross-Indicator Confirmation Patterns

These are the highest-conviction multi-indicator signals for blog narrative generation:

### Bull Confirmation Stack
1. **US growth**: US_G1 `pro-growth` + US_G2 `risk-on` + US_G4 `broad-rally`
2. **Credit healthy**: US_Cr2 `normal` or `complacent` + US_V1 `normal`
3. **Rates supportive**: US_R1 `early-cycle` or `mid-cycle` (no inversion)
4. **Global breadth**: GL_CLI5 `broad-expansion` + GL_G2 `global-risk-on`
5. **Momentum aligned**: M1 `trend-up` + M2 `risk-on`

### Bear / Recession Stack
1. **Yield curve**: US_R1 `recession-watch` (inverted) for > 3 months
2. **Credit deteriorating**: US_Cr2 `stress` or `opportunity` + US_Cr3 widening
3. **Labour cracking**: US_JOBS1 `labour-deteriorating` + US_JOBS2 `labour-slack`
4. **Vol stress**: US_V1 `stress` (inverted term structure)
5. **Global contraction**: GL_CLI5 `contracting` + GL_G2 `global-risk-off`
6. **Carry unwind**: FX_2 `carry-unwind` (systemic deleveraging)

### EM Outperformance Stack
1. **Dollar weak**: FX_CMD2 `weak-USD`
2. **EM leading**: GL_G1 `EM-outperform`
3. **Commodities rising**: FX_CMD6 `commodity-bull`
4. **China recovery**: AS_CN_G2 `china-outperform` + FX_CN1 `CNY-strengthening`
5. **Growth breadth**: GL_CLI5 `broad-expansion` + GL_CLI2 `China-leads-US`

### Europe Revival Stack
1. **Outperformance**: EU_G1 `eurozone-outperform` + EU_G2 `eurozone-outperform`
2. **Cyclicals leading**: EU_G3 `pro-growth-europe`
3. **No peripheral stress**: EU_R1 `compressed` or `normal`
4. **Fundamentals**: EU_CLI1 `EU-above-trend` + EU_G4 `eurozone-macro-strong`

### Inflation / Reflation Stack
1. **Breakevens rising**: US_R4 `inflation-elevated`
2. **Real rates low**: US_R5 `low-real-rates`
3. **Commodities vs bonds**: GL_CA_I1 `reflation`
4. **Oil outperforming gold**: FX_CMD3 `growth-inflation`
5. **Copper outperforming gold**: FX_CMD1 `pro-growth`

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

*End of Cheat Sheet — companion to the Indicator Manual (68 indicators)*
