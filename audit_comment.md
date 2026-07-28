## Daily audit — 2026-07-28 — **40 ISSUES** (1 fetch error, 39 stale series)

_Run: 2026-07-28 04:15 UTC_

Full report attached as `data_audit.txt` in today's commit.

<details><summary>Fetch errors</summary>


**other_warnings** (1):
- `[ECB] EU_I1 spread unavailable — EU_Cr1 will return n/a (corp-yield source unwired; see forward_plan.md §1 Known Data Gaps)`

</details>

<details><summary>Stale series</summary>


**EXPIRED** (5):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `CHN_PPI` | FRED | Monthly | 2022-12-01 | 1335d | 45d |
| `CHN_IND_PROD` | FRED | Monthly | 2023-11-01 | 1000d | 45d |
| `CHN_POLICY_RATE` | DB.nomics | Monthly | 2025-06-30 | 393d | 120d\* |
| `JPN_IND_PROD` | e-Stat | Monthly | 2026-03-01 | 149d | 60d\* |
| `CMRMTSPL` | FRED | Monthly | 2026-04-01 | 118d | 45d |

**STALE** (34):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `USA_CPI_YOY` | World Bank | Annual | 2024-12-31 | 574d | 540d |
| `ULCNFB` | FRED | Quarterly | 2026-01-01 | 208d | 180d\* |
| `CP` | FRED | Quarterly | 2026-01-01 | 208d | 180d\* |
| `GBR_RATE_3M` | OECD | Monthly | 2026-02-28 | 150d | 90d\* |
| `CHN_M2` | DB.nomics | Monthly | 2026-02-28 | 150d | 120d\* |
| `FRA_UNEMPLOYMENT` | INSEE | Quarterly | 2026-03-01 | 149d | 120d |
| `AUS_GDP_GROWTH` | ABS | Quarterly | 2026-03-01 | 149d | 120d\* |
| `ITA_GDP_GROWTH` | ISTAT | Quarterly | 2026-03-01 | 149d | 90d\* |
| `FRA_GDP_INDEX` | INSEE | Quarterly | 2026-03-01 | 149d | 120d |
| `EZ_BUILD_PERMITS` | Eurostat | Monthly | 2026-03-01 | 149d | 120d\* |
| `USA_SP500_DIV_SHILLER` | Shiller | Monthly | 2026-03-31 | 119d | 90d\* |
| `USA_SP500_EPS_SHILLER` | Shiller | Monthly | 2026-03-31 | 119d | 90d\* |
| `USA_SP500_PE` | Shiller | Monthly | 2026-03-31 | 119d | 90d\* |
| `M2SL` | FRED | Monthly | 2026-05-01 | 88d | 75d\* |
| `PCETRIM12M159SFRBDAL` | FRED | Monthly | 2026-05-01 | 88d | 45d |
| `MICH` | FRED | Monthly | 2026-05-01 | 88d | 75d\* |
| `UMCSENT` | FRED | Monthly | 2026-05-01 | 88d | 75d\* |
| `CHN_BUS_CONF` | FRED | Monthly | 2026-05-01 | 88d | 75d\* |
| `JPN_MACH_ORDERS` | e-Stat | Monthly | 2026-05-01 | 88d | 60d\* |
| `JPN_HH_EXP` | e-Stat | Monthly | 2026-05-01 | 88d | 80d\* |
| `FRA_LOAN_RATE_HOUSE` | Banque de France | Monthly | 2026-05-01 | 88d | 45d |
| `FRA_LOAN_RATE_NFC` | Banque de France | Monthly | 2026-05-01 | 88d | 45d |
| `EZ_PPI` | Eurostat | Monthly | 2026-05-01 | 88d | 75d\* |
| `PERMIT` | FRED | Monthly | 2026-06-01 | 57d | 45d |
| `USA_UNEMPLOYMENT` | BLS | Monthly | 2026-06-01 | 57d | 45d\* |
| `USA_CPI_INDEX` | BLS | Monthly | 2026-06-01 | 57d | 45d\* |
| `USA_CORE_CPI_INDEX` | BLS | Monthly | 2026-06-01 | 57d | 45d\* |
| `MEDCPIM158SFRBCLE` | FRED | Monthly | 2026-06-01 | 57d | 45d |
| `TRMMEANCPIM158SFRBCLE` | FRED | Monthly | 2026-06-01 | 57d | 45d |
| `FEDFUNDS` | FRED | Monthly | 2026-06-01 | 57d | 45d |
| _… 4 more in `data_audit.txt`_ |  |  |  |  |  |

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
| `market_data_comp_hist.csv` | 3,995 | 3,995 | 3,995 | 1950-01-06 → 2026-07-24 | 1950-01-06 → 2026-07-24 |
| `macro_economic_hist.csv` | 4,153 | 4,153 | 4,153 | 1946-12-27 → 2026-07-24 | 1946-12-27 → 2026-07-24 |
| `macro_market_hist.csv` | 1,387 | 1,387 | 1,387 | 2000-01-07 → 2026-07-31 | 2000-01-07 → 2026-07-31 |

</details>

