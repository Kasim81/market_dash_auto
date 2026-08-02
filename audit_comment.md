## Daily audit — 2026-08-02 — **63 ISSUES** (4 fetch errors, 58 stale series, 1 static-check failure)

_Run: 2026-08-02 04:39 UTC_

Full report attached as `data_audit.txt` in today's commit.

<details><summary>Fetch errors</summary>


**fallback_demotions** (3):
- `[FALLBACK] (snapshot) FRA_BUS_CONF: declared primary INSEE/SERIES_BDM/001565530 (tier 0) demoted — primary returned no data this run; serving FRED/BSCICP02FRM460S (tier 1, Monthly, last 2026-06-01)`
- `[FALLBACK] (snapshot) FRA_CPI_YOY: declared primary INSEE/SERIES_BDM/011814632 (tier 0) demoted — primary returned no data this run; serving DB.nomics/OECD/DSD_PRICES_COICOP2018@DF_PRICES_C2018_ALL/FRA.M.N.CPI.PA._T.N.GY (tier 1, Monthly, last 2026-04-28)`
- `[FALLBACK] (snapshot) FRA_IND_PROD: declared primary INSEE/SERIES_BDM/010768261 (tier 0) demoted — primary returned no data this run; serving IMF SDMX/IMF.STA,PI/FRA.IND.SA_IX.M (tier 1, Monthly, last 2026-03-01)`

**other_warnings** (1):
- `[ECB] EU_I1 spread unavailable — EU_Cr1 will return n/a (corp-yield source unwired; see forward_plan.md §1 Known Data Gaps)`

</details>

<details><summary>Stale series</summary>


**EXPIRED** (7):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `CHN_PPI` | FRED | Monthly | 2022-12-01 | 1340d | 45d |
| `CHN_IND_PROD` | FRED | Monthly | 2023-11-01 | 1005d | 45d |
| `CHN_POLICY_RATE` | DB.nomics | Monthly | 2025-06-30 | 398d | 120d\* |
| `JPN_IND_PROD` | e-Stat | Monthly | 2026-03-01 | 154d | 60d\* |
| `CMRMTSPL` | FRED | Monthly | 2026-05-01 | 93d | 45d |
| `FRA_LOAN_RATE_HOUSE` | Banque de France | Monthly | 2026-05-01 | 93d | 45d |
| `FRA_LOAN_RATE_NFC` | Banque de France | Monthly | 2026-05-01 | 93d | 45d |

**STALE** (51):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `USA_CPI_YOY_ANNUAL` | World Bank | Annual | 2024-12-31 | 579d | 540d |
| `ULCNFB` | FRED | Quarterly | 2026-01-01 | 213d | 180d\* |
| `CP` | FRED | Quarterly | 2026-01-01 | 213d | 180d\* |
| `CHE_IND_PROD` | IMF SDMX | Quarterly | 2026-01-01 | 213d | 210d\* |
| `DEU_GDP_INDEX` | IMF SDMX | Quarterly | 2026-01-01 | 213d | 210d\* |
| `JPN_GDP_INDEX` | IMF SDMX | Quarterly | 2026-01-01 | 213d | 210d\* |
| `ITA_GDP_INDEX` | IMF SDMX | Quarterly | 2026-01-01 | 213d | 210d\* |
| `CHE_GDP_INDEX` | IMF SDMX | Quarterly | 2026-01-01 | 213d | 210d\* |
| `NLD_GDP_INDEX` | IMF SDMX | Quarterly | 2026-01-01 | 213d | 210d\* |
| `CAN_GDP_INDEX` | IMF SDMX | Quarterly | 2026-01-01 | 213d | 210d\* |
| `JP_TANKAN1` | BoJ | Quarterly | 2026-02-01 | 182d | 180d\* |
| `GBR_RATE_3M` | OECD | Monthly | 2026-02-28 | 155d | 90d\* |
| `CHN_M2` | DB.nomics | Monthly | 2026-02-28 | 155d | 120d\* |
| `DEU_IND_PROD` | IMF SDMX | Monthly | 2026-03-01 | 154d | 150d\* |
| `AUS_GDP_GROWTH` | ABS | Quarterly | 2026-03-01 | 154d | 120d\* |
| `ITA_GDP_GROWTH` | ISTAT | Quarterly | 2026-03-01 | 154d | 90d\* |
| `FRA_IND_PROD` | IMF SDMX | Monthly | 2026-03-01 | 154d | 150d\* |
| `EZ_BUILD_PERMITS` | Eurostat | Monthly | 2026-03-01 | 154d | 120d\* |
| `NLD_IND_PROD` | IMF SDMX | Monthly | 2026-03-01 | 154d | 150d\* |
| `USA_SP500_DIV_SHILLER` | Shiller | Monthly | 2026-03-31 | 124d | 90d\* |
| `USA_SP500_EPS_SHILLER` | Shiller | Monthly | 2026-03-31 | 124d | 90d\* |
| `USA_SP500_PE` | Shiller | Monthly | 2026-03-31 | 124d | 90d\* |
| `DRTSCILM` | FRED | Quarterly | 2026-04-01 | 123d | 120d |
| `DRTSCIS` | FRED | Quarterly | 2026-04-01 | 123d | 120d |
| `DRTSCLCC` | FRED | Quarterly | 2026-04-01 | 123d | 120d |
| `STDSOTHCONS` | FRED | Quarterly | 2026-04-01 | 123d | 120d |
| `SUBLPDRCSN` | FRED | Quarterly | 2026-04-01 | 123d | 120d |
| `FRA_CPI_YOY` | DB.nomics | Monthly | 2026-04-30 | 94d | 90d\* |
| `JPN_CORE_CPI_YOY` | DB.nomics | Monthly | 2026-04-30 | 94d | 90d\* |
| `JPN_CPI_YOY` | DB.nomics | Monthly | 2026-04-30 | 94d | 90d\* |
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

<details><summary>Static-check failures</summary>


**missing_columns** (1):
- _get_col(...,'GOLD_USD_PM') referenced in the calculator layer but column absent from macro_economic_hist.csv

</details>

<details><summary>History preservation</summary>


| File | Live rows | Sister rows | Union | Live range | Sister range |
|---|---|---|---|---|---|
| `market_data_comp_hist.csv` | 3,996 | 3,996 | 3,996 | 1950-01-06 → 2026-07-31 | 1950-01-06 → 2026-07-31 |
| `macro_economic_hist.csv` | 4,154 | 4,154 | 4,154 | 1946-12-27 → 2026-07-31 | 1946-12-27 → 2026-07-31 |
| `macro_market_hist.csv` | 1,387 | 1,387 | 1,387 | 2000-01-07 → 2026-07-31 | 2000-01-07 → 2026-07-31 |

</details>

