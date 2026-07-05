## Daily audit — 2026-07-05 — **72 ISSUES** (1 fetch error, 70 stale series, 1 static-check failure)

_Run: 2026-07-05 05:02 UTC_

Full report attached as `data_audit.txt` in today's commit.

<details><summary>Fetch errors</summary>


**other_warnings** (1):
- `[ECB] EU_I1 spread unavailable — EU_Cr1 will return n/a (corp-yield source unwired; see forward_plan.md §1 Known Data Gaps)`

</details>

<details><summary>Stale series</summary>


**EXPIRED** (16):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `CHN_PPI` | FRED | Monthly | 2022-12-02 | 1311d | 45d |
| `CHN_IND_PROD` | FRED | Monthly | 2023-11-03 | 975d | 45d |
| `CHN_POLICY_RATE` | DB.nomics | Monthly | 2025-06-06 | 394d | 45d |
| `CAN_POLICY_RATE` | BoC | Daily | 2025-10-31 | 247d | 7d\* |
| `DEU_IND_PROD` | DB.nomics | Monthly | 2025-12-05 | 212d | 45d |
| `EA_HICP` | DB.nomics | Monthly | 2026-01-02 | 184d | 45d |
| `EU_ESI` | DB.nomics | Monthly | 2026-01-02 | 184d | 45d |
| `EU_IND_CONF` | DB.nomics | Monthly | 2026-01-02 | 184d | 45d |
| `EU_SVC_CONF` | DB.nomics | Monthly | 2026-01-02 | 184d | 45d |
| `EA_HICP_CORE_YOY` | DB.nomics | Monthly | 2026-01-02 | 184d | 45d |
| `JPN_IND_PROD` | e-Stat | Monthly | 2026-03-06 | 121d | 60d\* |
| `CMRMTSPL` | FRED | Monthly | 2026-04-03 | 93d | 45d |
| `ITA_UNEMPLOYMENT` | ISTAT | Monthly | 2026-04-03 | 93d | 45d\* |
| `JPN_SPPI` | BoJ | Monthly | 2026-04-03 | 93d | 45d\* |
| `CAN_CPI_MEDIAN` | BoC | Monthly | 2026-04-03 | 93d | 45d\* |
| `JPN_POLICY_RATE` | BoJ | Daily | 2026-06-19 | 16d | 5d |

**STALE** (54):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `USA_CPI` | World Bank | Annual | 2025-01-03 | 548d | 540d |
| `CHN_GDP_GROWTH` | IMF | Annual | 2025-01-03 | 548d | 540d |
| `EZ_EMPLOYMENT` | DB.nomics | Quarterly | 2025-10-03 | 275d | 180d\* |
| `EZ_IND_PROD` | DB.nomics | Monthly | 2025-12-05 | 212d | 150d\* |
| `EZ_RETAIL_VOL` | DB.nomics | Monthly | 2025-12-05 | 212d | 150d\* |
| `ULCNFB` | FRED | Quarterly | 2026-01-02 | 184d | 180d\* |
| `CP` | FRED | Quarterly | 2026-01-02 | 184d | 180d\* |
| `GBR_EMP_RATE` | ONS | Monthly | 2026-01-02 | 184d | 150d\* |
| `JP_TANKAN_LNFG` | BoJ | Quarterly | 2026-02-06 | 149d | 100d\* |
| `JP_TANKAN_SMFG` | BoJ | Quarterly | 2026-02-06 | 149d | 100d\* |
| `JP_TANKAN_SNFG` | BoJ | Quarterly | 2026-02-06 | 149d | 100d\* |
| `DEU_UNEMPLOYMENT` | OECD | Monthly | 2026-03-06 | 121d | 75d\* |
| `GBR_RATE_3M` | OECD | Monthly | 2026-03-06 | 121d | 90d\* |
| `AUS_CPI` | ABS | Quarterly | 2026-03-06 | 121d | 120d\* |
| `CHN_M2` | DB.nomics | Monthly | 2026-03-06 | 121d | 120d\* |
| `JP_TANKAN_LMFG_FCST` | BoJ | Quarterly | 2026-03-06 | 121d | 100d\* |
| `JP_TANKAN_LNFG_FCST` | BoJ | Quarterly | 2026-03-06 | 121d | 100d\* |
| `GBR_GDP_REAL` | ONS | Quarterly | 2026-03-06 | 121d | 90d\* |
| `GBR_IND_PROD` | ONS | Monthly | 2026-03-06 | 121d | 105d\* |
| `AUS_GDP_REAL` | ABS | Quarterly | 2026-03-06 | 121d | 120d\* |
| `FRA_GDP_INDEX` | INSEE | Quarterly | 2026-03-06 | 121d | 120d |
| `AWHMAN` | FRED | Monthly | 2026-04-03 | 93d | 75d\* |
| `ITA_BTP_10Y` | FRED | Monthly | 2026-04-03 | 93d | 90d\* |
| `ITA_BUS_CONF` | FRED | Monthly | 2026-04-03 | 93d | 75d\* |
| `CHN_CON_CONF` | FRED | Monthly | 2026-04-03 | 93d | 90d\* |
| `NLD_DSL_10Y` | FRED | Monthly | 2026-04-03 | 93d | 75d\* |
| `JPN_MACH_ORDERS` | e-Stat | Monthly | 2026-04-03 | 93d | 60d\* |
| `CAN_GDP_MONTHLY` | StatCan | Monthly | 2026-04-03 | 93d | 60d\* |
| `GBR_CPI_YOY` | ONS | Monthly | 2026-04-03 | 93d | 75d\* |
| `GBR_CPIH_YOY` | ONS | Monthly | 2026-04-03 | 93d | 75d\* |
| _… 24 more in `data_audit.txt`_ |  |  |  |  |  |

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
| `market_data_comp_hist.csv` | 3,992 | 3,992 | 3,992 | 1950-01-06 → 2026-07-03 | 1950-01-06 → 2026-07-03 |
| `macro_economic_hist.csv` | 4,150 | 4,150 | 4,150 | 1946-12-27 → 2026-07-03 | 1946-12-27 → 2026-07-03 |
| `macro_market_hist.csv` | 1,383 | 1,383 | 1,383 | 2000-01-07 → 2026-07-03 | 2000-01-07 → 2026-07-03 |

</details>

