## Daily audit — 2026-08-08 — **43 ISSUES** (1 fetch error, 42 stale series)

_Run: 2026-08-08 02:57 UTC_

Full report attached as `data_audit.txt` in today's commit.

<details><summary>Fetch errors</summary>


**other_warnings** (1):
- `[ECB] EU_I1 spread unavailable — EU_Cr1 will return n/a (corp-yield source unwired; see forward_plan.md §1 Known Data Gaps)`

</details>

<details><summary>Stale series</summary>


**EXPIRED** (6):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `CHN_PPI` | FRED | Monthly | 2022-12-01 | 1346d | 45d |
| `CHN_IND_PROD` | FRED | Monthly | 2023-11-01 | 1011d | 45d |
| `CHN_POLICY_RATE` | DB.nomics | Monthly | 2025-06-30 | 404d | 120d\* |
| `JPN_IND_PROD` | e-Stat | Monthly | 2026-03-01 | 160d | 60d\* |
| `CMRMTSPL` | FRED | Monthly | 2026-05-01 | 99d | 45d |
| `FRA_LOAN_RATE_NFC` | Banque de France | Monthly | 2026-05-01 | 99d | 45d |

**STALE** (36):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `USA_CPI_YOY_ANNUAL` | World Bank | Annual | 2024-12-31 | 585d | 540d |
| `CP` | FRED | Quarterly | 2026-01-01 | 219d | 180d\* |
| `CHE_IND_PROD` | IMF SDMX | Quarterly | 2026-01-01 | 219d | 210d\* |
| `DEU_GDP_INDEX` | IMF SDMX | Quarterly | 2026-01-01 | 219d | 210d\* |
| `JPN_GDP_INDEX` | IMF SDMX | Quarterly | 2026-01-01 | 219d | 210d\* |
| `ITA_GDP_INDEX` | IMF SDMX | Quarterly | 2026-01-01 | 219d | 210d\* |
| `CHE_GDP_INDEX` | IMF SDMX | Quarterly | 2026-01-01 | 219d | 210d\* |
| `NLD_GDP_INDEX` | IMF SDMX | Quarterly | 2026-01-01 | 219d | 210d\* |
| `CAN_GDP_INDEX` | IMF SDMX | Quarterly | 2026-01-01 | 219d | 210d\* |
| `JP_TANKAN1` | BoJ | Quarterly | 2026-02-01 | 188d | 180d\* |
| `GBR_RATE_3M` | OECD | Monthly | 2026-02-28 | 161d | 90d\* |
| `CHN_M2` | DB.nomics | Monthly | 2026-02-28 | 161d | 120d\* |
| `DEU_IND_PROD` | IMF SDMX | Monthly | 2026-03-01 | 160d | 150d\* |
| `AUS_GDP_GROWTH` | ABS | Quarterly | 2026-03-01 | 160d | 120d\* |
| `ITA_GDP_GROWTH` | ISTAT | Quarterly | 2026-03-01 | 160d | 90d\* |
| `NLD_IND_PROD` | IMF SDMX | Monthly | 2026-03-01 | 160d | 150d\* |
| `USA_SP500_DIV_SHILLER` | Shiller | Monthly | 2026-03-31 | 130d | 90d\* |
| `USA_SP500_EPS_SHILLER` | Shiller | Monthly | 2026-03-31 | 130d | 90d\* |
| `USA_SP500_PE` | Shiller | Monthly | 2026-03-31 | 130d | 90d\* |
| `EZ_BUILD_PERMITS` | Eurostat | Monthly | 2026-04-01 | 129d | 120d\* |
| `JPN_CORE_CPI_YOY` | DB.nomics | Monthly | 2026-04-30 | 100d | 90d\* |
| `JPN_CPI_YOY` | DB.nomics | Monthly | 2026-04-30 | 100d | 90d\* |
| `CAN_CPI_YOY` | DB.nomics | Monthly | 2026-04-30 | 100d | 90d\* |
| `ITA_CPI_YOY` | DB.nomics | Monthly | 2026-04-30 | 100d | 90d\* |
| `CHN_CON_CONF` | FRED | Monthly | 2026-05-01 | 99d | 90d\* |
| `CHN_BUS_CONF` | FRED | Monthly | 2026-05-01 | 99d | 75d\* |
| `JPN_MACH_ORDERS` | e-Stat | Monthly | 2026-05-01 | 99d | 60d\* |
| `PERMIT` | FRED | Monthly | 2026-06-01 | 68d | 45d |
| `USA_CPI_INDEX` | BLS | Monthly | 2026-06-01 | 68d | 45d\* |
| `USA_CORE_CPI_INDEX` | BLS | Monthly | 2026-06-01 | 68d | 45d\* |
| _… 6 more in `data_audit.txt`_ |  |  |  |  |  |

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
| `market_data_comp_hist.csv` | 3,997 | 3,997 | 3,997 | 1950-01-06 → 2026-08-07 | 1950-01-06 → 2026-08-07 |
| `macro_economic_hist.csv` | 4,155 | 4,155 | 4,155 | 1946-12-27 → 2026-08-07 | 1946-12-27 → 2026-08-07 |
| `macro_market_hist.csv` | 1,388 | 1,388 | 1,388 | 2000-01-07 → 2026-08-07 | 2000-01-07 → 2026-08-07 |

</details>

