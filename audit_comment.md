## Daily audit — 2026-07-30 — **49 ISSUES** (48 stale series, 1 static-check failure)

_Run: 2026-07-30 09:38 UTC_

Full report attached as `data_audit.txt` in today's commit.

<details><summary>Stale series</summary>


**EXPIRED** (5):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `CHN_PPI` | FRED | Monthly | 2022-12-01 | 1337d | 45d |
| `CHN_IND_PROD` | FRED | Monthly | 2023-11-01 | 1002d | 45d |
| `CHN_POLICY_RATE` | DB.nomics | Monthly | 2025-06-30 | 395d | 120d\* |
| `JPN_IND_PROD` | e-Stat | Monthly | 2026-03-01 | 151d | 60d\* |
| `CMRMTSPL` | FRED | Monthly | 2026-04-01 | 120d | 45d |

**STALE** (43):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `USA_CPI_YOY_ANNUAL` | World Bank | Annual | 2024-12-31 | 576d | 540d |
| `ULCNFB` | FRED | Quarterly | 2026-01-01 | 210d | 180d\* |
| `CP` | FRED | Quarterly | 2026-01-01 | 210d | 180d\* |
| `GBR_RATE_3M` | OECD | Monthly | 2026-02-28 | 152d | 90d\* |
| `CHN_M2` | DB.nomics | Monthly | 2026-02-28 | 152d | 120d\* |
| `DEU_IND_PROD` | IMF SDMX | Monthly | 2026-03-01 | 151d | 150d\* |
| `FRA_UNEMPLOYMENT` | INSEE | Quarterly | 2026-03-01 | 151d | 120d |
| `AUS_GDP_GROWTH` | ABS | Quarterly | 2026-03-01 | 151d | 120d\* |
| `ITA_GDP_GROWTH` | ISTAT | Quarterly | 2026-03-01 | 151d | 90d\* |
| `FRA_GDP_INDEX` | INSEE | Quarterly | 2026-03-01 | 151d | 120d |
| `EZ_BUILD_PERMITS` | Eurostat | Monthly | 2026-03-01 | 151d | 120d\* |
| `NLD_IND_PROD` | IMF SDMX | Monthly | 2026-03-01 | 151d | 150d\* |
| `USA_SP500_DIV_SHILLER` | Shiller | Monthly | 2026-03-31 | 121d | 90d\* |
| `USA_SP500_EPS_SHILLER` | Shiller | Monthly | 2026-03-31 | 121d | 90d\* |
| `USA_SP500_PE` | Shiller | Monthly | 2026-03-31 | 121d | 90d\* |
| `CAN_CPI_YOY` | DB.nomics | Monthly | 2026-04-30 | 91d | 90d\* |
| `ITA_CPI_YOY` | DB.nomics | Monthly | 2026-04-30 | 91d | 90d\* |
| `JPN_CPI_YOY` | DB.nomics | Monthly | 2026-04-30 | 91d | 90d\* |
| `PCETRIM12M159SFRBDAL` | FRED | Monthly | 2026-05-01 | 90d | 45d |
| `MICH` | FRED | Monthly | 2026-05-01 | 90d | 75d\* |
| `UMCSENT` | FRED | Monthly | 2026-05-01 | 90d | 75d\* |
| `CHN_BUS_CONF` | FRED | Monthly | 2026-05-01 | 90d | 75d\* |
| `JPN_MACH_ORDERS` | e-Stat | Monthly | 2026-05-01 | 90d | 60d\* |
| `JPN_HH_EXP` | e-Stat | Monthly | 2026-05-01 | 90d | 80d\* |
| `FRA_LOAN_RATE_HOUSE` | Banque de France | Monthly | 2026-05-01 | 90d | 45d |
| `FRA_LOAN_RATE_NFC` | Banque de France | Monthly | 2026-05-01 | 90d | 45d |
| `EZ_PPI` | Eurostat | Monthly | 2026-05-01 | 90d | 75d\* |
| `PERMIT` | FRED | Monthly | 2026-06-01 | 59d | 45d |
| `USA_UNEMPLOYMENT` | BLS | Monthly | 2026-06-01 | 59d | 45d\* |
| `USA_CPI_INDEX` | BLS | Monthly | 2026-06-01 | 59d | 45d\* |
| _… 13 more in `data_audit.txt`_ |  |  |  |  |  |

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

<details><summary>Static-check failures</summary>


**missing_columns** (1):
- _get_col(...,'JPN_CORE_CPI_YOY') referenced in the calculator layer but column absent from macro_economic_hist.csv

</details>

<details><summary>History preservation</summary>


| File | Live rows | Sister rows | Union | Live range | Sister range |
|---|---|---|---|---|---|
| `market_data_comp_hist.csv` | 3,995 | 3,995 | 3,995 | 1950-01-06 → 2026-07-24 | 1950-01-06 → 2026-07-24 |
| `macro_economic_hist.csv` | 4,153 | 4,153 | 4,153 | 1946-12-27 → 2026-07-24 | 1946-12-27 → 2026-07-24 |
| `macro_market_hist.csv` | 1,387 | 1,387 | 1,387 | 2000-01-07 → 2026-07-31 | 2000-01-07 → 2026-07-31 |

</details>

