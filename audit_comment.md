## Daily audit — 2026-08-31 — **98 ISSUES** (4 fetch errors, 94 stale series)

_Run: 2026-08-31 06:34 UTC_

Full report attached as `data_audit.txt` in today's commit.

<details><summary>Fetch errors</summary>


**yfinance_dead** (3):
- `HYXU`
- `IFRB.L`
- `^KS200`

**other_warnings** (1):
- `[ECB] EU_I1 spread unavailable — EU_Cr1 will return n/a (corp-yield source unwired; see forward_plan.md §1 Known Data Gaps)`

</details>

<details><summary>Stale series</summary>


**EXPIRED** (9):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `CHN_PPI` | FRED | Monthly | 2022-12-01 | 1369d | 45d |
| `CHN_IND_PROD` | FRED | Monthly | 2023-11-01 | 1034d | 45d |
| `CHN_POLICY_RATE` | DB.nomics | Monthly | 2025-06-30 | 427d | 120d\* |
| `GBR_RATE_3M` | OECD | Monthly | 2026-02-28 | 184d | 90d\* |
| `JPN_IND_PROD` | e-Stat | Monthly | 2026-03-01 | 183d | 60d\* |
| `ITA_GDP_GROWTH` | ISTAT | Quarterly | 2026-03-01 | 183d | 90d\* |
| `CMRMTSPL` | FRED | Monthly | 2026-06-01 | 91d | 45d |
| `FRA_LOAN_RATE_HOUSE` | Banque de France | Monthly | 2026-06-01 | 91d | 45d |
| `FRA_LOAN_RATE_NFC` | Banque de France | Monthly | 2026-06-01 | 91d | 45d |

**STALE** (85):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `USA_CPI_YOY_ANNUAL` | World Bank | Annual | 2024-12-31 | 608d | 540d |
| `CHE_IND_PROD` | IMF SDMX | Quarterly | 2026-01-01 | 242d | 210d\* |
| `DEU_GDP_INDEX` | IMF SDMX | Quarterly | 2026-01-01 | 242d | 210d\* |
| `JPN_GDP_INDEX` | IMF SDMX | Quarterly | 2026-01-01 | 242d | 210d\* |
| `ITA_GDP_INDEX` | IMF SDMX | Quarterly | 2026-01-01 | 242d | 210d\* |
| `CHE_GDP_INDEX` | IMF SDMX | Quarterly | 2026-01-01 | 242d | 210d\* |
| `NLD_GDP_INDEX` | IMF SDMX | Quarterly | 2026-01-01 | 242d | 210d\* |
| `CAN_GDP_INDEX` | IMF SDMX | Quarterly | 2026-01-01 | 242d | 210d\* |
| `JP_TANKAN1` | BoJ | Quarterly | 2026-02-01 | 211d | 180d\* |
| `CHN_M2` | DB.nomics | Monthly | 2026-02-28 | 184d | 120d\* |
| `DEU_IND_PROD` | IMF SDMX | Monthly | 2026-03-01 | 183d | 150d\* |
| `AUS_GDP_GROWTH` | ABS | Quarterly | 2026-03-01 | 183d | 120d\* |
| `EZ_EMPLOYMENT` | ECB | Quarterly | 2026-03-01 | 183d | 180d\* |
| `NLD_IND_PROD` | IMF SDMX | Monthly | 2026-03-01 | 183d | 150d\* |
| `USA_SP500_DIV_SHILLER` | Shiller | Monthly | 2026-03-31 | 153d | 90d\* |
| `USA_SP500_EPS_SHILLER` | Shiller | Monthly | 2026-03-31 | 153d | 90d\* |
| `USA_SP500_PE` | Shiller | Monthly | 2026-03-31 | 153d | 90d\* |
| `EZ_BUILD_PERMITS` | Eurostat | Monthly | 2026-04-01 | 152d | 120d\* |
| `JPN_CORE_CPI_YOY` | DB.nomics | Monthly | 2026-04-30 | 123d | 90d\* |
| `JPN_CPI_YOY` | DB.nomics | Monthly | 2026-04-30 | 123d | 90d\* |
| `ITA_CPI_YOY` | DB.nomics | Monthly | 2026-04-30 | 123d | 90d\* |
| `CAN_CPI_YOY` | DB.nomics | Monthly | 2026-04-30 | 123d | 90d\* |
| `CHN_CON_CONF` | FRED | Monthly | 2026-05-01 | 122d | 90d\* |
| `CHN_BUS_CONF` | FRED | Monthly | 2026-05-01 | 122d | 75d\* |
| `ITA_UNEMPLOYMENT` | ISTAT | Monthly | 2026-05-01 | 122d | 120d\* |
| `GBR_INFL_EXP_5Y` | BoE Survey | Quarterly | 2026-05-01 | 122d | 120d\* |
| `JPN_RATE_3M` | OECD | Monthly | 2026-05-31 | 92d | 90d\* |
| `CHE_CPI_YOY` | DB.nomics | Monthly | 2026-05-31 | 92d | 90d\* |
| `NLD_CPI_YOY` | DB.nomics | Monthly | 2026-05-31 | 92d | 90d\* |
| `DEU_CPI_YOY` | DB.nomics | Monthly | 2026-05-31 | 92d | 90d\* |
| _… 55 more in `data_audit.txt`_ |  |  |  |  |  |

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
| `market_data_comp_hist.csv` | 4,000 | 4,000 | 4,000 | 1950-01-06 → 2026-08-28 | 1950-01-06 → 2026-08-28 |
| `macro_economic_hist.csv` | 4,158 | 4,158 | 4,158 | 1946-12-27 → 2026-08-28 | 1946-12-27 → 2026-08-28 |
| `macro_market_hist.csv` | 1,391 | 1,391 | 1,391 | 2000-01-07 → 2026-08-28 | 2000-01-07 → 2026-08-28 |

</details>


_audit_writeback: 3 ticker(s) on active dead-list streak (threshold 14d); none flipped this run._
