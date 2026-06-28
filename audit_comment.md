## Daily audit — 2026-06-28 — **80 ISSUES** (1 fetch error, 78 stale series, 1 static-check failure)

_Run: 2026-06-28 05:21 UTC_

Full report attached as `data_audit.txt` in today's commit.

<details><summary>Fetch errors</summary>


**other_warnings** (1):
- `[ECB] EU_I1 spread unavailable — EU_Cr1 will return n/a (corp-yield source unwired; see forward_plan.md §1 Known Data Gaps)`

</details>

<details><summary>Stale series</summary>


**EXPIRED** (16):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `CHN_PPI` | FRED | Monthly | 2022-12-02 | 1304d | 45d |
| `CHN_IND_PROD` | FRED | Monthly | 2023-11-03 | 968d | 45d |
| `CHN_CPI` | FRED | Monthly | 2025-04-04 | 450d | 45d |
| `CHN_POLICY_RATE` | DB.nomics | Monthly | 2025-06-06 | 387d | 45d |
| `ISM_SVC_PMI` | DB.nomics | Monthly | 2025-09-05 | 296d | 60d\* |
| `CAN_POLICY_RATE` | BoC | Daily | 2025-10-31 | 240d | 7d\* |
| `DEU_IND_PROD` | DB.nomics | Monthly | 2025-12-05 | 205d | 45d |
| `ISM_MFG_PRICES` | DB.nomics | Monthly | 2025-12-05 | 205d | 45d |
| `EA_HICP` | DB.nomics | Monthly | 2026-01-02 | 177d | 45d |
| `EU_ESI` | DB.nomics | Monthly | 2026-01-02 | 177d | 45d |
| `EU_IND_CONF` | DB.nomics | Monthly | 2026-01-02 | 177d | 45d |
| `EU_SVC_CONF` | DB.nomics | Monthly | 2026-01-02 | 177d | 45d |
| `ISM_MFG_PMI` | DB.nomics | Monthly | 2026-01-02 | 177d | 45d |
| `ISM_MFG_NEWORD` | DB.nomics | Monthly | 2026-01-02 | 177d | 45d |
| `ISM_MFG_INVENTORIES` | DB.nomics | Monthly | 2026-01-02 | 177d | 45d |
| `EA_HICP_CORE_YOY` | DB.nomics | Monthly | 2026-01-02 | 177d | 45d |

**STALE** (62):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `JPN_CPI` | World Bank | Annual | 2025-01-03 | 541d | 540d |
| `CHE_CPI` | World Bank | Annual | 2025-01-03 | 541d | 540d |
| `DEU_CPI` | World Bank | Annual | 2025-01-03 | 541d | 540d |
| `FRA_CPI` | World Bank | Annual | 2025-01-03 | 541d | 540d |
| `ITA_CPI` | World Bank | Annual | 2025-01-03 | 541d | 540d |
| `NLD_CPI` | World Bank | Annual | 2025-01-03 | 541d | 540d |
| `USA_CPI` | World Bank | Annual | 2025-01-03 | 541d | 540d |
| `CHN_GDP_GROWTH` | IMF | Annual | 2025-01-03 | 541d | 540d |
| `EZ_EMPLOYMENT` | DB.nomics | Quarterly | 2025-10-03 | 268d | 180d\* |
| `EZ_IND_PROD` | DB.nomics | Monthly | 2025-12-05 | 205d | 150d\* |
| `EZ_RETAIL_VOL` | DB.nomics | Monthly | 2025-12-05 | 205d | 150d\* |
| `JP_TANKAN_LNFG` | BoJ | Quarterly | 2026-01-02 | 177d | 100d\* |
| `JP_TANKAN_SMFG` | BoJ | Quarterly | 2026-01-02 | 177d | 100d\* |
| `JP_TANKAN_SNFG` | BoJ | Quarterly | 2026-01-02 | 177d | 100d\* |
| `GBR_EMP_RATE` | ONS | Monthly | 2026-01-02 | 177d | 150d\* |
| `EA19_RATE_3M` | OECD | Monthly | 2026-02-06 | 142d | 90d\* |
| `JP_TANKAN_LMFG_FCST` | BoJ | Quarterly | 2026-02-06 | 142d | 100d\* |
| `JP_TANKAN_LNFG_FCST` | BoJ | Quarterly | 2026-02-06 | 142d | 100d\* |
| `JPN_IND_PROD` | e-Stat | Monthly | 2026-03-06 | 114d | 60d\* |
| `FRA_UNEMPLOYMENT` | OECD | Monthly | 2026-03-06 | 114d | 75d\* |
| `GBR_RATE_3M` | OECD | Monthly | 2026-03-06 | 114d | 90d\* |
| `CAN_GDP_MONTHLY` | StatCan | Monthly | 2026-03-06 | 114d | 60d\* |
| `GBR_GDP_REAL` | ONS | Quarterly | 2026-03-06 | 114d | 90d\* |
| `GBR_IND_PROD` | ONS | Monthly | 2026-03-06 | 114d | 105d\* |
| `USA_UNEMPLOYMENT` | OECD | Monthly | 2026-04-03 | 86d | 75d\* |
| `AWHMAN` | FRED | Monthly | 2026-04-03 | 86d | 75d\* |
| `CMRMTSPL` | FRED | Monthly | 2026-04-03 | 86d | 45d |
| `ITA_BUS_CONF` | FRED | Monthly | 2026-04-03 | 86d | 75d\* |
| `NLD_DSL_10Y` | FRED | Monthly | 2026-04-03 | 86d | 75d\* |
| `DEU_UNEMPLOYMENT` | OECD | Monthly | 2026-04-03 | 86d | 75d\* |
| _… 32 more in `data_audit.txt`_ |  |  |  |  |  |

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


**missing_columns** (1):
- _get_col(...,'JPN_RETAIL_SALES') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv

</details>

<details><summary>History preservation</summary>


| File | Live rows | Sister rows | Union | Live range | Sister range |
|---|---|---|---|---|---|
| `market_data_comp_hist.csv` | 3,991 | 3,991 | 3,991 | 1950-01-06 → 2026-06-26 | 1950-01-06 → 2026-06-26 |
| `macro_economic_hist.csv` | 4,149 | 4,149 | 4,149 | 1946-12-27 → 2026-06-26 | 1946-12-27 → 2026-06-26 |
| `macro_market_hist.csv` | 1,382 | 1,382 | 1,382 | 2000-01-07 → 2026-06-26 | 2000-01-07 → 2026-06-26 |

</details>

