## Daily audit — 2026-08-03 — **59 ISSUES** (1 fetch error, 58 stale series)

_Run: 2026-08-03 04:41 UTC_

Full report attached as `data_audit.txt` in today's commit.

<details><summary>Fetch errors</summary>


**other_warnings** (1):
- `[ECB] EU_I1 spread unavailable — EU_Cr1 will return n/a (corp-yield source unwired; see forward_plan.md §1 Known Data Gaps)`

</details>

<details><summary>Stale series</summary>


**EXPIRED** (7):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `CHN_PPI` | FRED | Monthly | 2022-12-01 | 1341d | 45d |
| `CHN_IND_PROD` | FRED | Monthly | 2023-11-01 | 1006d | 45d |
| `CHN_POLICY_RATE` | DB.nomics | Monthly | 2025-06-30 | 399d | 120d\* |
| `JPN_IND_PROD` | e-Stat | Monthly | 2026-03-01 | 155d | 60d\* |
| `CMRMTSPL` | FRED | Monthly | 2026-05-01 | 94d | 45d |
| `FRA_LOAN_RATE_HOUSE` | Banque de France | Monthly | 2026-05-01 | 94d | 45d |
| `FRA_LOAN_RATE_NFC` | Banque de France | Monthly | 2026-05-01 | 94d | 45d |

**STALE** (51):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `USA_CPI_YOY_ANNUAL` | World Bank | Annual | 2024-12-31 | 580d | 540d |
| `ULCNFB` | FRED | Quarterly | 2026-01-01 | 214d | 180d\* |
| `CP` | FRED | Quarterly | 2026-01-01 | 214d | 180d\* |
| `CHE_IND_PROD` | IMF SDMX | Quarterly | 2026-01-01 | 214d | 210d\* |
| `DEU_GDP_INDEX` | IMF SDMX | Quarterly | 2026-01-01 | 214d | 210d\* |
| `JPN_GDP_INDEX` | IMF SDMX | Quarterly | 2026-01-01 | 214d | 210d\* |
| `ITA_GDP_INDEX` | IMF SDMX | Quarterly | 2026-01-01 | 214d | 210d\* |
| `CHE_GDP_INDEX` | IMF SDMX | Quarterly | 2026-01-01 | 214d | 210d\* |
| `NLD_GDP_INDEX` | IMF SDMX | Quarterly | 2026-01-01 | 214d | 210d\* |
| `CAN_GDP_INDEX` | IMF SDMX | Quarterly | 2026-01-01 | 214d | 210d\* |
| `JP_TANKAN1` | BoJ | Quarterly | 2026-02-01 | 183d | 180d\* |
| `GBR_RATE_3M` | OECD | Monthly | 2026-02-28 | 156d | 90d\* |
| `CHN_M2` | DB.nomics | Monthly | 2026-02-28 | 156d | 120d\* |
| `DEU_IND_PROD` | IMF SDMX | Monthly | 2026-03-01 | 155d | 150d\* |
| `AUS_GDP_GROWTH` | ABS | Quarterly | 2026-03-01 | 155d | 120d\* |
| `ITA_GDP_GROWTH` | ISTAT | Quarterly | 2026-03-01 | 155d | 90d\* |
| `EZ_BUILD_PERMITS` | Eurostat | Monthly | 2026-03-01 | 155d | 120d\* |
| `NLD_IND_PROD` | IMF SDMX | Monthly | 2026-03-01 | 155d | 150d\* |
| `FRA_UNEMPLOYMENT` | INSEE | Quarterly | 2026-03-01 | 155d | 120d |
| `USA_SP500_DIV_SHILLER` | Shiller | Monthly | 2026-03-31 | 125d | 90d\* |
| `USA_SP500_EPS_SHILLER` | Shiller | Monthly | 2026-03-31 | 125d | 90d\* |
| `USA_SP500_PE` | Shiller | Monthly | 2026-03-31 | 125d | 90d\* |
| `DRTSCILM` | FRED | Quarterly | 2026-04-01 | 124d | 120d |
| `DRTSCIS` | FRED | Quarterly | 2026-04-01 | 124d | 120d |
| `DRTSCLCC` | FRED | Quarterly | 2026-04-01 | 124d | 120d |
| `STDSOTHCONS` | FRED | Quarterly | 2026-04-01 | 124d | 120d |
| `SUBLPDRCSN` | FRED | Quarterly | 2026-04-01 | 124d | 120d |
| `JPN_CORE_CPI_YOY` | DB.nomics | Monthly | 2026-04-30 | 95d | 90d\* |
| `JPN_CPI_YOY` | DB.nomics | Monthly | 2026-04-30 | 95d | 90d\* |
| `CAN_CPI_YOY` | DB.nomics | Monthly | 2026-04-30 | 95d | 90d\* |
| _… 21 more in `data_audit.txt`_ |  |  |  |  |  |

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
| `market_data_comp_hist.csv` | 3,996 | 3,996 | 3,996 | 1950-01-06 → 2026-07-31 | 1950-01-06 → 2026-07-31 |
| `macro_economic_hist.csv` | 4,154 | 4,154 | 4,154 | 1946-12-27 → 2026-07-31 | 1946-12-27 → 2026-07-31 |
| `macro_market_hist.csv` | 1,387 | 1,387 | 1,387 | 2000-01-07 → 2026-07-31 | 2000-01-07 → 2026-07-31 |

</details>

