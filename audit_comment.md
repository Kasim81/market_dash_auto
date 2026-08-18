## Daily audit — 2026-08-18 — **98 ISSUES** (1 fetch error, 97 stale series)

_Run: 2026-08-18 02:28 UTC_

Full report attached as `data_audit.txt` in today's commit.

<details><summary>Fetch errors</summary>


**other_warnings** (1):
- `[ECB] EU_I1 spread unavailable — EU_Cr1 will return n/a (corp-yield source unwired; see forward_plan.md §1 Known Data Gaps)`

</details>

<details><summary>Stale series</summary>


**EXPIRED** (5):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `CHN_PPI` | FRED | Monthly | 2022-12-01 | 1356d | 45d |
| `CHN_IND_PROD` | FRED | Monthly | 2023-11-01 | 1021d | 45d |
| `CHN_POLICY_RATE` | DB.nomics | Monthly | 2025-06-30 | 414d | 120d\* |
| `JPN_IND_PROD` | e-Stat | Monthly | 2026-03-01 | 170d | 60d\* |
| `CMRMTSPL` | FRED | Monthly | 2026-05-01 | 109d | 45d |

**STALE** (92):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `USA_CPI_YOY_ANNUAL` | World Bank | Annual | 2024-12-31 | 595d | 540d |
| `CP` | FRED | Quarterly | 2026-01-01 | 229d | 180d\* |
| `CHE_IND_PROD` | IMF SDMX | Quarterly | 2026-01-01 | 229d | 210d\* |
| `DEU_GDP_INDEX` | IMF SDMX | Quarterly | 2026-01-01 | 229d | 210d\* |
| `JPN_GDP_INDEX` | IMF SDMX | Quarterly | 2026-01-01 | 229d | 210d\* |
| `ITA_GDP_INDEX` | IMF SDMX | Quarterly | 2026-01-01 | 229d | 210d\* |
| `CHE_GDP_INDEX` | IMF SDMX | Quarterly | 2026-01-01 | 229d | 210d\* |
| `NLD_GDP_INDEX` | IMF SDMX | Quarterly | 2026-01-01 | 229d | 210d\* |
| `CAN_GDP_INDEX` | IMF SDMX | Quarterly | 2026-01-01 | 229d | 210d\* |
| `JP_TANKAN1` | BoJ | Quarterly | 2026-02-01 | 198d | 180d\* |
| `GBR_RATE_3M` | OECD | Monthly | 2026-02-28 | 171d | 90d\* |
| `CHN_M2` | DB.nomics | Monthly | 2026-02-28 | 171d | 120d\* |
| `DEU_IND_PROD` | IMF SDMX | Monthly | 2026-03-01 | 170d | 150d\* |
| `AUS_GDP_GROWTH` | ABS | Quarterly | 2026-03-01 | 170d | 120d\* |
| `ITA_GDP_GROWTH` | ISTAT | Quarterly | 2026-03-01 | 170d | 90d\* |
| `NLD_IND_PROD` | IMF SDMX | Monthly | 2026-03-01 | 170d | 150d\* |
| `USA_SP500_DIV_SHILLER` | Shiller | Monthly | 2026-03-31 | 140d | 90d\* |
| `USA_SP500_EPS_SHILLER` | Shiller | Monthly | 2026-03-31 | 140d | 90d\* |
| `USA_SP500_PE` | Shiller | Monthly | 2026-03-31 | 140d | 90d\* |
| `EZ_BUILD_PERMITS` | Eurostat | Monthly | 2026-04-01 | 139d | 120d\* |
| `JPN_CORE_CPI_YOY` | DB.nomics | Monthly | 2026-04-30 | 110d | 90d\* |
| `JPN_CPI_YOY` | DB.nomics | Monthly | 2026-04-30 | 110d | 90d\* |
| `CAN_CPI_YOY` | DB.nomics | Monthly | 2026-04-30 | 110d | 90d\* |
| `ITA_CPI_YOY` | DB.nomics | Monthly | 2026-04-30 | 110d | 90d\* |
| `CHN_CON_CONF` | FRED | Monthly | 2026-05-01 | 109d | 90d\* |
| `CHN_BUS_CONF` | FRED | Monthly | 2026-05-01 | 109d | 75d\* |
| `JPN_MACH_ORDERS` | e-Stat | Monthly | 2026-05-01 | 109d | 60d\* |
| `M2SL` | FRED | Monthly | 2026-06-01 | 78d | 75d\* |
| `PERMIT` | FRED | Monthly | 2026-06-01 | 78d | 45d |
| `INDPRO` | FRED | Monthly | 2026-06-01 | 78d | 75d\* |
| _… 62 more in `data_audit.txt`_ |  |  |  |  |  |

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
| `market_data_comp_hist.csv` | 3,998 | 3,998 | 3,998 | 1950-01-06 → 2026-08-14 | 1950-01-06 → 2026-08-14 |
| `macro_economic_hist.csv` | 4,156 | 4,156 | 4,156 | 1946-12-27 → 2026-08-14 | 1946-12-27 → 2026-08-14 |
| `macro_market_hist.csv` | 1,390 | 1,390 | 1,390 | 2000-01-07 → 2026-08-21 | 2000-01-07 → 2026-08-21 |

</details>

