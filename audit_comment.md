## Daily audit — 2026-07-10 — **51 ISSUES** (1 fetch error, 49 stale series, 1 static-check failure)

_Run: 2026-07-10 04:55 UTC_

Full report attached as `data_audit.txt` in today's commit.

<details><summary>Fetch errors</summary>


**other_warnings** (1):
- `[ECB] EU_I1 spread unavailable — EU_Cr1 will return n/a (corp-yield source unwired; see forward_plan.md §1 Known Data Gaps)`

</details>

<details><summary>Stale series</summary>


**EXPIRED** (9):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `CHN_PPI` | FRED | Monthly | 2022-12-01 | 1317d | 45d |
| `CHN_IND_PROD` | FRED | Monthly | 2023-11-01 | 982d | 45d |
| `CHN_POLICY_RATE` | DB.nomics | Monthly | 2025-06-30 | 375d | 120d\* |
| `EU_ESI` | DB.nomics | Monthly | 2025-12-31 | 191d | 45d |
| `EU_IND_CONF` | DB.nomics | Monthly | 2025-12-31 | 191d | 45d |
| `EU_SVC_CONF` | DB.nomics | Monthly | 2025-12-31 | 191d | 45d |
| `JPN_IND_PROD` | e-Stat | Monthly | 2026-03-01 | 131d | 60d\* |
| `CMRMTSPL` | FRED | Monthly | 2026-04-01 | 100d | 45d |
| `ITA_UNEMPLOYMENT` | ISTAT | Monthly | 2026-04-01 | 100d | 45d\* |

**STALE** (40):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `USA_CPI_YOY` | World Bank | Annual | 2024-12-31 | 556d | 540d |
| `EZ_EMPLOYMENT` | DB.nomics | Quarterly | 2025-09-30 | 283d | 180d\* |
| `ULCNFB` | FRED | Quarterly | 2026-01-01 | 190d | 180d\* |
| `CP` | FRED | Quarterly | 2026-01-01 | 190d | 180d\* |
| `JP_TANKAN_LNFG` | BoJ | Quarterly | 2026-02-01 | 159d | 100d\* |
| `JP_TANKAN_SMFG` | BoJ | Quarterly | 2026-02-01 | 159d | 100d\* |
| `JP_TANKAN_SNFG` | BoJ | Quarterly | 2026-02-01 | 159d | 100d\* |
| `GBR_RATE_3M` | OECD | Monthly | 2026-02-28 | 132d | 90d\* |
| `CHN_M2` | DB.nomics | Monthly | 2026-02-28 | 132d | 120d\* |
| `JP_TANKAN_LMFG_FCST` | BoJ | Quarterly | 2026-03-01 | 131d | 100d\* |
| `JP_TANKAN_LNFG_FCST` | BoJ | Quarterly | 2026-03-01 | 131d | 100d\* |
| `GBR_GDP_REAL` | ONS | Quarterly | 2026-03-01 | 131d | 90d\* |
| `AUS_CPI_INDEX` | ABS | Quarterly | 2026-03-01 | 131d | 120d\* |
| `AUS_GDP_REAL` | ABS | Quarterly | 2026-03-01 | 131d | 120d\* |
| `FRA_GDP_INDEX` | INSEE | Quarterly | 2026-03-01 | 131d | 120d |
| `USA_SP500_DIV_SHILLER` | Shiller | Monthly | 2026-03-31 | 101d | 90d\* |
| `USA_SP500_EPS_SHILLER` | Shiller | Monthly | 2026-03-31 | 101d | 90d\* |
| `ITA_BTP_10Y` | FRED | Monthly | 2026-04-01 | 100d | 90d\* |
| `CHN_CON_CONF` | FRED | Monthly | 2026-04-01 | 100d | 90d\* |
| `NLD_DSL_10Y` | FRED | Monthly | 2026-04-01 | 100d | 75d\* |
| `JPN_MACH_ORDERS` | e-Stat | Monthly | 2026-04-01 | 100d | 60d\* |
| `CAN_GDP_MONTHLY` | StatCan | Monthly | 2026-04-01 | 100d | 60d\* |
| `GBR_GDP_MONTHLY` | ONS | Monthly | 2026-04-01 | 100d | 75d\* |
| `ITA_IND_PROD` | ISTAT | Monthly | 2026-04-01 | 100d | 60d\* |
| `PERMIT` | FRED | Monthly | 2026-05-01 | 70d | 45d |
| `USA_CPI_INDEX` | BLS | Monthly | 2026-05-01 | 70d | 45d\* |
| `USA_CORE_CPI_INDEX` | BLS | Monthly | 2026-05-01 | 70d | 45d\* |
| `MEDCPIM158SFRBCLE` | FRED | Monthly | 2026-05-01 | 70d | 45d |
| `TRMMEANCPIM158SFRBCLE` | FRED | Monthly | 2026-05-01 | 70d | 45d |
| `PCETRIM12M159SFRBDAL` | FRED | Monthly | 2026-05-01 | 70d | 45d |
| _… 10 more in `data_audit.txt`_ |  |  |  |  |  |

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
- _get_col(...,'GOLD_USD_PM') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv

</details>

<details><summary>History preservation</summary>


| File | Live rows | Sister rows | Union | Live range | Sister range |
|---|---|---|---|---|---|
| `market_data_comp_hist.csv` | 3,993 | 3,993 | 3,993 | 1950-01-06 → 2026-07-10 | 1950-01-06 → 2026-07-10 |
| `macro_economic_hist.csv` | 4,151 | 4,151 | 4,151 | 1946-12-27 → 2026-07-10 | 1946-12-27 → 2026-07-10 |
| `macro_market_hist.csv` | 1,384 | 1,384 | 1,384 | 2000-01-07 → 2026-07-10 | 2000-01-07 → 2026-07-10 |

</details>

