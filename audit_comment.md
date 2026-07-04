## Daily audit — 2026-07-04 — **66 ISSUES** (1 fetch error, 62 stale series, 3 static-check failures)

_Run: 2026-07-04 04:49 UTC_

Full report attached as `data_audit.txt` in today's commit.

<details><summary>Fetch errors</summary>


**other_warnings** (1):
- `[ECB] EU_I1 spread unavailable — EU_Cr1 will return n/a (corp-yield source unwired; see forward_plan.md §1 Known Data Gaps)`

</details>

<details><summary>Stale series</summary>


**EXPIRED** (12):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `CHN_PPI` | FRED | Monthly | 2022-12-02 | 1310d | 45d |
| `CHN_IND_PROD` | FRED | Monthly | 2023-11-03 | 974d | 45d |
| `CHN_POLICY_RATE` | DB.nomics | Monthly | 2025-06-06 | 393d | 45d |
| `CAN_POLICY_RATE` | BoC | Daily | 2025-10-31 | 246d | 7d\* |
| `DEU_IND_PROD` | DB.nomics | Monthly | 2025-12-05 | 211d | 45d |
| `EA_HICP` | DB.nomics | Monthly | 2026-01-02 | 183d | 45d |
| `EU_ESI` | DB.nomics | Monthly | 2026-01-02 | 183d | 45d |
| `EA_HICP_CORE_YOY` | DB.nomics | Monthly | 2026-01-02 | 183d | 45d |
| `CMRMTSPL` | FRED | Monthly | 2026-04-03 | 92d | 45d |
| `JPN_SPPI` | BoJ | Monthly | 2026-04-03 | 92d | 45d\* |
| `CAN_CPI_MEDIAN` | BoC | Monthly | 2026-04-03 | 92d | 45d\* |
| `JPN_POLICY_RATE` | BoJ | Daily | 2026-06-19 | 15d | 5d |

**STALE** (50):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `USA_CPI` | World Bank | Annual | 2025-01-03 | 547d | 540d |
| `CHN_GDP_GROWTH` | IMF | Annual | 2025-01-03 | 547d | 540d |
| `EZ_EMPLOYMENT` | DB.nomics | Quarterly | 2025-10-03 | 274d | 180d\* |
| `EZ_IND_PROD` | DB.nomics | Monthly | 2025-12-05 | 211d | 150d\* |
| `EZ_RETAIL_VOL` | DB.nomics | Monthly | 2025-12-05 | 211d | 150d\* |
| `ULCNFB` | FRED | Quarterly | 2026-01-02 | 183d | 180d\* |
| `CP` | FRED | Quarterly | 2026-01-02 | 183d | 180d\* |
| `GBR_EMP_RATE` | ONS | Monthly | 2026-01-02 | 183d | 150d\* |
| `JP_TANKAN_LNFG` | BoJ | Quarterly | 2026-02-06 | 148d | 100d\* |
| `JP_TANKAN_SMFG` | BoJ | Quarterly | 2026-02-06 | 148d | 100d\* |
| `JP_TANKAN_SNFG` | BoJ | Quarterly | 2026-02-06 | 148d | 100d\* |
| `JPN_IND_PROD` | e-Stat | Monthly | 2026-03-06 | 120d | 60d\* |
| `DEU_UNEMPLOYMENT` | OECD | Monthly | 2026-03-06 | 120d | 75d\* |
| `GBR_RATE_3M` | OECD | Monthly | 2026-03-06 | 120d | 90d\* |
| `JP_TANKAN_LMFG_FCST` | BoJ | Quarterly | 2026-03-06 | 120d | 100d\* |
| `JP_TANKAN_LNFG_FCST` | BoJ | Quarterly | 2026-03-06 | 120d | 100d\* |
| `GBR_GDP_REAL` | ONS | Quarterly | 2026-03-06 | 120d | 90d\* |
| `GBR_IND_PROD` | ONS | Monthly | 2026-03-06 | 120d | 105d\* |
| `AWHMAN` | FRED | Monthly | 2026-04-03 | 92d | 75d\* |
| `ITA_BTP_10Y` | FRED | Monthly | 2026-04-03 | 92d | 90d\* |
| `ITA_BUS_CONF` | FRED | Monthly | 2026-04-03 | 92d | 75d\* |
| `CHN_CON_CONF` | FRED | Monthly | 2026-04-03 | 92d | 90d\* |
| `NLD_DSL_10Y` | FRED | Monthly | 2026-04-03 | 92d | 75d\* |
| `JPN_MACH_ORDERS` | e-Stat | Monthly | 2026-04-03 | 92d | 60d\* |
| `CAN_GDP_MONTHLY` | StatCan | Monthly | 2026-04-03 | 92d | 60d\* |
| `GBR_CPI_YOY` | ONS | Monthly | 2026-04-03 | 92d | 75d\* |
| `GBR_CPIH_YOY` | ONS | Monthly | 2026-04-03 | 92d | 75d\* |
| `GBR_GDP_MONTHLY` | ONS | Monthly | 2026-04-03 | 92d | 75d\* |
| `USA_SP500_DIV_SHILLER` | Shiller | Monthly | 2026-04-03 | 92d | 90d\* |
| `USA_SP500_EPS_SHILLER` | Shiller | Monthly | 2026-04-03 | 92d | 90d\* |
| _… 20 more in `data_audit.txt`_ |  |  |  |  |  |

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


**missing_columns** (3):
- _get_col(...,'EU_IND_CONF') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv
- _get_col(...,'EU_SVC_CONF') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv
- _get_col(...,'JPN_RETAIL_SALES') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv

</details>

<details><summary>History preservation</summary>


| File | Live rows | Sister rows | Union | Live range | Sister range |
|---|---|---|---|---|---|
| `market_data_comp_hist.csv` | 3,992 | 3,992 | 3,992 | 1950-01-06 → 2026-07-03 | 1950-01-06 → 2026-07-03 |
| `macro_economic_hist.csv` | 4,150 | 4,150 | 4,150 | 1946-12-27 → 2026-07-03 | 1946-12-27 → 2026-07-03 |
| `macro_market_hist.csv` | 1,383 | 1,383 | 1,383 | 2000-01-07 → 2026-07-03 | 2000-01-07 → 2026-07-03 |

</details>

