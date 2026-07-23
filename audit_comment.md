## Daily audit — 2026-07-23 — **81 ISSUES** (7 fetch errors, 74 stale series)

_Run: 2026-07-23 04:29 UTC_

Full report attached as `data_audit.txt` in today's commit.

<details><summary>Fetch errors</summary>


**fallback_demotions** (6):
- `[FALLBACK] (snapshot) FRA_UNEMPLOYMENT: declared primary INSEE/SERIES_BDM/001688527 (tier 0) demoted — finer-cadence fallback outranks coarser primary (cadence-first); serving OECD/UNEMPLOYMENT (tier 1, Monthly, last 2026-05-28)`
- `[FALLBACK] (snapshot) AUS_GDP_GROWTH: declared primary ABS/ANA_AGG/M2.GPM.20.AUS.Q (tier 0) demoted — stale 144d (last obs 2026-03-01, group freshest 2031-12-31, gate 2x93d); serving IMF/NGDP_RPCH (tier 1, Annual, last 2031-12-31)`
- `[FALLBACK] (snapshot) ITA_GDP_GROWTH: declared primary ISTAT/163_156/Q.IT.B1GQ_B_W2_S1.G1.Y. (tier 0) demoted — stale 144d (last obs 2026-03-01, group freshest 2031-12-31, gate 2x93d); serving IMF/NGDP_RPCH (tier 1, Annual, last 2031-12-31)`
- `[FALLBACK] FRA_UNEMPLOYMENT: declared primary INSEE/SERIES_BDM/001688527 (tier 0) demoted — finer-cadence fallback outranks coarser primary (cadence-first); serving OECD/UNEMPLOYMENT (tier 1, Monthly, last 2026-05-31)`
- `[FALLBACK] AUS_GDP_GROWTH: declared primary ABS/ANA_AGG/M2.GPM.20.AUS.Q (tier 0) demoted — stale 144d (last obs 2026-03-01, group freshest 2031-12-31, gate 2x93d); serving IMF/NGDP_RPCH (tier 1, Annual, last 2031-12-31)`
- `[FALLBACK] ITA_GDP_GROWTH: declared primary ISTAT/163_156/Q.IT.B1GQ_B_W2_S1.G1.Y. (tier 0) demoted — stale 144d (last obs 2026-03-01, group freshest 2031-12-31, gate 2x93d); serving IMF/NGDP_RPCH (tier 1, Annual, last 2031-12-31)`

**other_warnings** (1):
- `[ECB] EU_I1 spread unavailable — EU_Cr1 will return n/a (corp-yield source unwired; see forward_plan.md §1 Known Data Gaps)`

</details>

<details><summary>Stale series</summary>


**EXPIRED** (6):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `CHN_PPI` | FRED | Monthly | 2022-12-01 | 1330d | 45d |
| `CHN_IND_PROD` | FRED | Monthly | 2023-11-01 | 995d | 45d |
| `CHN_POLICY_RATE` | DB.nomics | Monthly | 2025-06-30 | 388d | 120d\* |
| `JPN_IND_PROD` | e-Stat | Monthly | 2026-03-01 | 144d | 60d\* |
| `CMRMTSPL` | FRED | Monthly | 2026-04-01 | 113d | 45d |
| `EZ_INFL_EXP_12M` | ECB | Monthly | 2026-05-01 | 83d | 40d\* |

**STALE** (68):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `USA_CPI_YOY` | World Bank | Annual | 2024-12-31 | 569d | 540d |
| `ULCNFB` | FRED | Quarterly | 2026-01-01 | 203d | 180d\* |
| `CP` | FRED | Quarterly | 2026-01-01 | 203d | 180d\* |
| `JP_TANKAN_LNFG` | BoJ | Quarterly | 2026-02-01 | 172d | 100d\* |
| `JP_TANKAN_SMFG` | BoJ | Quarterly | 2026-02-01 | 172d | 100d\* |
| `JP_TANKAN_SNFG` | BoJ | Quarterly | 2026-02-01 | 172d | 100d\* |
| `GBR_RATE_3M` | OECD | Monthly | 2026-02-28 | 145d | 90d\* |
| `CHN_M2` | DB.nomics | Monthly | 2026-02-28 | 145d | 120d\* |
| `JP_TANKAN_LMFG_FCST` | BoJ | Quarterly | 2026-03-01 | 144d | 100d\* |
| `JP_TANKAN_LNFG_FCST` | BoJ | Quarterly | 2026-03-01 | 144d | 100d\* |
| `GBR_GDP_REAL` | ONS | Quarterly | 2026-03-01 | 144d | 90d\* |
| `AUS_CPI_INDEX` | ABS | Quarterly | 2026-03-01 | 144d | 120d\* |
| `AUS_GDP_REAL` | ABS | Quarterly | 2026-03-01 | 144d | 120d\* |
| `FRA_GDP_INDEX` | INSEE | Quarterly | 2026-03-01 | 144d | 120d |
| `EZ_BUILD_PERMITS` | Eurostat | Monthly | 2026-03-01 | 144d | 120d\* |
| `USA_SP500_DIV_SHILLER` | Shiller | Monthly | 2026-03-31 | 114d | 90d\* |
| `USA_SP500_EPS_SHILLER` | Shiller | Monthly | 2026-03-31 | 114d | 90d\* |
| `USA_SP500_PE` | Shiller | Monthly | 2026-03-31 | 114d | 90d\* |
| `CAN_GDP_MONTHLY` | StatCan | Monthly | 2026-04-01 | 113d | 60d\* |
| `M2SL` | FRED | Monthly | 2026-05-01 | 83d | 75d\* |
| `PCETRIM12M159SFRBDAL` | FRED | Monthly | 2026-05-01 | 83d | 45d |
| `MICH` | FRED | Monthly | 2026-05-01 | 83d | 75d\* |
| `UMCSENT` | FRED | Monthly | 2026-05-01 | 83d | 75d\* |
| `CFNAI` | FRED | Monthly | 2026-05-01 | 83d | 75d\* |
| `CHN_BUS_CONF` | FRED | Monthly | 2026-05-01 | 83d | 75d\* |
| `JPN_REER` | FRED | Monthly | 2026-05-01 | 83d | 75d\* |
| `ITA_UNEMPLOYMENT` | ISTAT | Monthly | 2026-05-01 | 83d | 45d\* |
| `EZ_M3` | ECB | Monthly | 2026-05-01 | 83d | 45d\* |
| `JPN_SPPI` | BoJ | Monthly | 2026-05-01 | 83d | 45d\* |
| `JPN_MACH_ORDERS` | e-Stat | Monthly | 2026-05-01 | 83d | 60d\* |
| _… 38 more in `data_audit.txt`_ |  |  |  |  |  |

</details>

<details><summary>Active historical anchors (informational)</summary>

| Series | Source | Last obs | Next expected release |
|---|---|---|---|
| `USA_CPI_JST` | JST | 2020-12-31 | 2026-12-31 |
| `USA_GDP_JST` | JST | 2020-12-31 | 2026-12-31 |
| `USA_EQUITY_TR_JST` | JST | 2020-12-31 | 2026-12-31 |
| `USA_LTRATE_JST` | JST | 2020-12-31 | 2026-12-31 |
| `GBR_CPI_JST` | JST | 2020-12-31 | 2026-12-31 |
| `GBR_GDP_JST` | JST | 2020-12-31 | 2026-12-31 |
| `GBR_EQUITY_TR_JST` | JST | 2020-12-31 | 2026-12-31 |
| `GBR_LTRATE_JST` | JST | 2020-12-31 | 2026-12-31 |
| `DEU_CPI_JST` | JST | 2020-12-31 | 2026-12-31 |
| `DEU_GDP_JST` | JST | 2020-12-31 | 2026-12-31 |
| `DEU_EQUITY_TR_JST` | JST | 2020-12-31 | 2026-12-31 |
| `DEU_LTRATE_JST` | JST | 2020-12-31 | 2026-12-31 |
| `FRA_CPI_JST` | JST | 2020-12-31 | 2026-12-31 |
| `FRA_GDP_JST` | JST | 2020-12-31 | 2026-12-31 |
| `FRA_EQUITY_TR_JST` | JST | 2020-12-31 | 2026-12-31 |
| `FRA_LTRATE_JST` | JST | 2020-12-31 | 2026-12-31 |
| `JPN_CPI_JST` | JST | 2020-12-31 | 2026-12-31 |
| `JPN_GDP_JST` | JST | 2020-12-31 | 2026-12-31 |
| `JPN_EQUITY_TR_JST` | JST | 2020-12-31 | 2026-12-31 |
| `JPN_LTRATE_JST` | JST | 2020-12-31 | 2026-12-31 |
| `ITA_CPI_JST` | JST | 2020-12-31 | 2026-12-31 |
| `ITA_GDP_JST` | JST | 2020-12-31 | 2026-12-31 |
| `ITA_EQUITY_TR_JST` | JST | 2020-12-31 | 2026-12-31 |
| `ITA_LTRATE_JST` | JST | 2020-12-31 | 2026-12-31 |
| `CAN_CPI_JST` | JST | 2020-12-31 | 2026-12-31 |
| `CAN_GDP_JST` | JST | 2020-12-31 | 2026-12-31 |
| `CAN_LTRATE_JST` | JST | 2020-12-31 | 2026-12-31 |
| `AUS_CPI_JST` | JST | 2020-12-31 | 2026-12-31 |
| `AUS_GDP_JST` | JST | 2020-12-31 | 2026-12-31 |
| `AUS_EQUITY_TR_JST` | JST | 2020-12-31 | 2026-12-31 |
| _… 9 more in `data_audit.txt`_ |  |  |  |

</details>

<details><summary>History preservation</summary>


| File | Live rows | Sister rows | Union | Live range | Sister range |
|---|---|---|---|---|---|
| `market_data_comp_hist.csv` | 3,994 | 3,994 | 3,994 | 1950-01-06 → 2026-07-17 | 1950-01-06 → 2026-07-17 |
| `macro_economic_hist.csv` | 4,152 | 4,152 | 4,152 | 1946-12-27 → 2026-07-17 | 1946-12-27 → 2026-07-17 |
| `macro_market_hist.csv` | 1,386 | 1,386 | 1,386 | 2000-01-07 → 2026-07-24 | 2000-01-07 → 2026-07-24 |

</details>

