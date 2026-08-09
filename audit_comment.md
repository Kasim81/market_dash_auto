## Daily audit — 2026-08-09 — **44 ISSUES** (4 fetch errors, 40 stale series)

_Run: 2026-08-09 03:08 UTC_

Full report attached as `data_audit.txt` in today's commit.

<details><summary>Fetch errors</summary>


**fallback_demotions** (3):
- `[FALLBACK] (snapshot) USA_UNEMPLOYMENT: declared primary BLS/LNS14000000 (tier 0) demoted — primary returned no data this run; serving FRED/UNRATE (tier 1, Monthly, last 2026-07-01)`
- `[FALLBACK] (snapshot) USA_CPI_INDEX: declared primary BLS/CUSR0000SA0 (tier 0) demoted — primary returned no data this run; serving FRED/CPIAUCSL (tier 1, Monthly, last 2026-06-01)`
- `[FALLBACK] (snapshot) USA_CORE_CPI_INDEX: declared primary BLS/CUSR0000SA0L1E (tier 0) demoted — primary returned no data this run; serving FRED/CPILFESL (tier 1, Monthly, last 2026-06-01)`

**other_warnings** (1):
- `[ECB] EU_I1 spread unavailable — EU_Cr1 will return n/a (corp-yield source unwired; see forward_plan.md §1 Known Data Gaps)`

</details>

<details><summary>Stale series</summary>


**EXPIRED** (6):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `CHN_PPI` | FRED | Monthly | 2022-12-01 | 1347d | 45d |
| `CHN_IND_PROD` | FRED | Monthly | 2023-11-01 | 1012d | 45d |
| `CHN_POLICY_RATE` | DB.nomics | Monthly | 2025-06-30 | 405d | 120d\* |
| `JPN_IND_PROD` | e-Stat | Monthly | 2026-03-01 | 161d | 60d\* |
| `CMRMTSPL` | FRED | Monthly | 2026-05-01 | 100d | 45d |
| `FRA_LOAN_RATE_NFC` | Banque de France | Monthly | 2026-05-01 | 100d | 45d |

**STALE** (34):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `USA_CPI_YOY_ANNUAL` | World Bank | Annual | 2024-12-31 | 586d | 540d |
| `CP` | FRED | Quarterly | 2026-01-01 | 220d | 180d\* |
| `CHE_IND_PROD` | IMF SDMX | Quarterly | 2026-01-01 | 220d | 210d\* |
| `DEU_GDP_INDEX` | IMF SDMX | Quarterly | 2026-01-01 | 220d | 210d\* |
| `JPN_GDP_INDEX` | IMF SDMX | Quarterly | 2026-01-01 | 220d | 210d\* |
| `ITA_GDP_INDEX` | IMF SDMX | Quarterly | 2026-01-01 | 220d | 210d\* |
| `CHE_GDP_INDEX` | IMF SDMX | Quarterly | 2026-01-01 | 220d | 210d\* |
| `NLD_GDP_INDEX` | IMF SDMX | Quarterly | 2026-01-01 | 220d | 210d\* |
| `CAN_GDP_INDEX` | IMF SDMX | Quarterly | 2026-01-01 | 220d | 210d\* |
| `JP_TANKAN1` | BoJ | Quarterly | 2026-02-01 | 189d | 180d\* |
| `GBR_RATE_3M` | OECD | Monthly | 2026-02-28 | 162d | 90d\* |
| `CHN_M2` | DB.nomics | Monthly | 2026-02-28 | 162d | 120d\* |
| `DEU_IND_PROD` | IMF SDMX | Monthly | 2026-03-01 | 161d | 150d\* |
| `AUS_GDP_GROWTH` | ABS | Quarterly | 2026-03-01 | 161d | 120d\* |
| `ITA_GDP_GROWTH` | ISTAT | Quarterly | 2026-03-01 | 161d | 90d\* |
| `NLD_IND_PROD` | IMF SDMX | Monthly | 2026-03-01 | 161d | 150d\* |
| `USA_SP500_DIV_SHILLER` | Shiller | Monthly | 2026-03-31 | 131d | 90d\* |
| `USA_SP500_EPS_SHILLER` | Shiller | Monthly | 2026-03-31 | 131d | 90d\* |
| `USA_SP500_PE` | Shiller | Monthly | 2026-03-31 | 131d | 90d\* |
| `EZ_BUILD_PERMITS` | Eurostat | Monthly | 2026-04-01 | 130d | 120d\* |
| `JPN_CORE_CPI_YOY` | DB.nomics | Monthly | 2026-04-30 | 101d | 90d\* |
| `JPN_CPI_YOY` | DB.nomics | Monthly | 2026-04-30 | 101d | 90d\* |
| `CAN_CPI_YOY` | DB.nomics | Monthly | 2026-04-30 | 101d | 90d\* |
| `ITA_CPI_YOY` | DB.nomics | Monthly | 2026-04-30 | 101d | 90d\* |
| `CHN_CON_CONF` | FRED | Monthly | 2026-05-01 | 100d | 90d\* |
| `CHN_BUS_CONF` | FRED | Monthly | 2026-05-01 | 100d | 75d\* |
| `JPN_MACH_ORDERS` | e-Stat | Monthly | 2026-05-01 | 100d | 60d\* |
| `PERMIT` | FRED | Monthly | 2026-06-01 | 69d | 45d |
| `MEDCPIM158SFRBCLE` | FRED | Monthly | 2026-06-01 | 69d | 45d |
| `TRMMEANCPIM158SFRBCLE` | FRED | Monthly | 2026-06-01 | 69d | 45d |
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
| `market_data_comp_hist.csv` | 3,997 | 3,997 | 3,997 | 1950-01-06 → 2026-08-07 | 1950-01-06 → 2026-08-07 |
| `macro_economic_hist.csv` | 4,155 | 4,155 | 4,155 | 1946-12-27 → 2026-08-07 | 1946-12-27 → 2026-08-07 |
| `macro_market_hist.csv` | 1,388 | 1,388 | 1,388 | 2000-01-07 → 2026-08-07 | 2000-01-07 → 2026-08-07 |

</details>

