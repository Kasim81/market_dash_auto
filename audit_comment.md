## Daily audit — 2026-06-13 — **46 ISSUES** (1 fetch error, 43 stale series, 2 static-check failures)

_Run: 2026-06-13 06:00 UTC_

Full report attached as `data_audit.txt` in today's commit.

<details><summary>Fetch errors</summary>


**other_warnings** (1):
- `[ECB] EU_I1 spread unavailable — EU_Cr1 will return n/a (corp-yield source unwired; see forward_plan.md §1 Known Data Gaps)`

</details>

<details><summary>Stale series</summary>


**EXPIRED** (21):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `CHN_M2` | FRED | Monthly | 2019-08-02 | 2507d | 45d |
| `CHN_PPI` | FRED | Monthly | 2022-12-02 | 1289d | 45d |
| `CHN_IND_PROD` | FRED | Monthly | 2023-11-03 | 953d | 45d |
| `JPN_IND_PROD` | FRED | Monthly | 2024-03-01 | 834d | 45d |
| `GBR_CPI` | FRED | Monthly | 2025-03-07 | 463d | 45d |
| `CHN_CPI` | FRED | Monthly | 2025-04-04 | 435d | 45d |
| `CHN_POLICY_RATE` | DB.nomics | Monthly | 2025-06-06 | 372d | 45d |
| `EA_DEPOSIT_RATE` | ECB | Daily | 2025-06-13 | 365d | 30d\* |
| `ISM_SVC_PMI` | DB.nomics | Monthly | 2025-09-05 | 281d | 60d\* |
| `JPN_MACH_ORDERS` | e-Stat | Monthly | 2025-10-03 | 253d | 60d\* |
| `CAN_POLICY_RATE` | BoC | Daily | 2025-10-31 | 225d | 7d\* |
| `DEU_IND_PROD` | DB.nomics | Monthly | 2025-12-05 | 190d | 45d |
| `EA_HICP` | DB.nomics | Monthly | 2026-01-02 | 162d | 45d |
| `EU_ESI` | DB.nomics | Monthly | 2026-01-02 | 162d | 45d |
| `EU_IND_CONF` | DB.nomics | Monthly | 2026-01-02 | 162d | 45d |
| `EU_SVC_CONF` | DB.nomics | Monthly | 2026-01-02 | 162d | 45d |
| `ISM_MFG_PMI` | DB.nomics | Monthly | 2026-01-02 | 162d | 45d |
| `ISM_MFG_NEWORD` | DB.nomics | Monthly | 2026-01-02 | 162d | 45d |
| `EA_HICP_CORE_YOY` | DB.nomics | Monthly | 2026-01-02 | 162d | 45d |
| `CMRMTSPL` | FRED | Monthly | 2026-03-06 | 99d | 45d |
| `JPN_POLICY_RATE` | BoJ | Daily | 2026-05-29 | 15d | 5d |

**STALE** (22):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `EZ_EMPLOYMENT` | DB.nomics | Quarterly | 2025-10-03 | 253d | 180d\* |
| `EZ_IND_PROD` | DB.nomics | Monthly | 2025-12-05 | 190d | 150d\* |
| `EZ_RETAIL_VOL` | DB.nomics | Monthly | 2025-12-05 | 190d | 150d\* |
| `JP_TANKAN_LNFG` | BoJ | Quarterly | 2026-01-02 | 162d | 100d\* |
| `JP_TANKAN_SMFG` | BoJ | Quarterly | 2026-01-02 | 162d | 100d\* |
| `JP_TANKAN_SNFG` | BoJ | Quarterly | 2026-01-02 | 162d | 100d\* |
| `GBR_EMP_RATE` | ONS | Monthly | 2026-01-02 | 162d | 150d\* |
| `EA19_RATE_3M` | OECD | Monthly | 2026-02-06 | 127d | 90d\* |
| `JP_TANKAN_LMFG_FCST` | BoJ | Quarterly | 2026-02-06 | 127d | 100d\* |
| `JP_TANKAN_LNFG_FCST` | BoJ | Quarterly | 2026-02-06 | 127d | 100d\* |
| `ITA_BTP_10Y` | FRED | Monthly | 2026-03-06 | 99d | 90d\* |
| `IND_GOVT_10Y` | FRED | Monthly | 2026-03-06 | 99d | 90d\* |
| `CHN_CON_CONF` | FRED | Monthly | 2026-03-06 | 99d | 90d\* |
| `NLD_DSL_10Y` | FRED | Monthly | 2026-03-06 | 99d | 75d\* |
| `FRA_UNEMPLOYMENT` | OECD | Monthly | 2026-03-06 | 99d | 75d\* |
| `GBR_RATE_3M` | OECD | Monthly | 2026-03-06 | 99d | 90d\* |
| `GBR_GDP_REAL` | ONS | Quarterly | 2026-03-06 | 99d | 90d\* |
| `PERMIT` | FRED | Monthly | 2026-04-03 | 71d | 45d |
| `JPN_SPPI` | BoJ | Monthly | 2026-04-03 | 71d | 45d\* |
| `CAN_CPI_MEDIAN` | BoC | Monthly | 2026-04-03 | 71d | 45d\* |
| `AUS_PART_RATE` | ABS | Monthly | 2026-04-03 | 71d | 45d\* |
| `NFCI` | FRED | Weekly | 2026-05-22 | 22d | 14d\* |

</details>

<details><summary>Active historical anchors (informational)</summary>

| Series | Source | Last obs | Next expected release |
|---|---|---|---|
| `USA_CPI_JST` | JST | 2021-01-01 | 2026-12-31 |
| `USA_GDP_JST` | JST | 2021-01-01 | 2026-12-31 |
| `USA_EQUITY_TR_JST` | JST | 2021-01-01 | 2026-12-31 |
| `USA_LTRATE_JST` | JST | 2021-01-01 | 2026-12-31 |
| `GBR_CPI_JST` | JST | 2021-01-01 | 2026-12-31 |
| `GBR_GDP_JST` | JST | 2021-01-01 | 2026-12-31 |
| `GBR_EQUITY_TR_JST` | JST | 2021-01-01 | 2026-12-31 |
| `GBR_LTRATE_JST` | JST | 2021-01-01 | 2026-12-31 |
| `DEU_CPI_JST` | JST | 2021-01-01 | 2026-12-31 |
| `DEU_GDP_JST` | JST | 2021-01-01 | 2026-12-31 |
| `DEU_EQUITY_TR_JST` | JST | 2021-01-01 | 2026-12-31 |
| `DEU_LTRATE_JST` | JST | 2021-01-01 | 2026-12-31 |
| `FRA_CPI_JST` | JST | 2021-01-01 | 2026-12-31 |
| `FRA_GDP_JST` | JST | 2021-01-01 | 2026-12-31 |
| `FRA_EQUITY_TR_JST` | JST | 2021-01-01 | 2026-12-31 |
| `FRA_LTRATE_JST` | JST | 2021-01-01 | 2026-12-31 |
| `JPN_CPI_JST` | JST | 2021-01-01 | 2026-12-31 |
| `JPN_GDP_JST` | JST | 2021-01-01 | 2026-12-31 |
| `JPN_EQUITY_TR_JST` | JST | 2021-01-01 | 2026-12-31 |
| `JPN_LTRATE_JST` | JST | 2021-01-01 | 2026-12-31 |
| `ITA_CPI_JST` | JST | 2021-01-01 | 2026-12-31 |
| `ITA_GDP_JST` | JST | 2021-01-01 | 2026-12-31 |
| `ITA_EQUITY_TR_JST` | JST | 2021-01-01 | 2026-12-31 |
| `ITA_LTRATE_JST` | JST | 2021-01-01 | 2026-12-31 |
| `CAN_CPI_JST` | JST | 2021-01-01 | 2026-12-31 |
| `CAN_GDP_JST` | JST | 2021-01-01 | 2026-12-31 |
| `CAN_LTRATE_JST` | JST | 2021-01-01 | 2026-12-31 |
| `AUS_CPI_JST` | JST | 2021-01-01 | 2026-12-31 |
| `AUS_GDP_JST` | JST | 2021-01-01 | 2026-12-31 |
| `AUS_EQUITY_TR_JST` | JST | 2021-01-01 | 2026-12-31 |
| _… 9 more in `data_audit.txt`_ |  |  |  |

</details>

<details><summary>Static-check failures</summary>


**missing_columns** (2):
- _get_col(...,'JPN_RETAIL_SALES') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv
- _get_col(...,'US_GDPNOW') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv

</details>

<details><summary>History preservation</summary>


| File | Live rows | Sister rows | Union | Live range | Sister range |
|---|---|---|---|---|---|
| `market_data_comp_hist.csv` | 3,989 | 3,989 | 3,989 | 1950-01-06 → 2026-06-12 | 1950-01-06 → 2026-06-12 |
| `macro_economic_hist.csv` | 4,147 | 4,147 | 4,147 | 1946-12-27 → 2026-06-12 | 1946-12-27 → 2026-06-12 |
| `macro_market_hist.csv` | 1,380 | 1,380 | 1,380 | 2000-01-07 → 2026-06-12 | 2000-01-07 → 2026-06-12 |

</details>

