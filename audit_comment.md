## Daily audit — 2026-06-27 — **72 ISSUES** (1 fetch error, 57 stale series, 14 static-check failures)

_Run: 2026-06-27 04:57 UTC_

Full report attached as `data_audit.txt` in today's commit.

<details><summary>Fetch errors</summary>


**other_warnings** (1):
- `[ECB] EU_I1 spread unavailable — EU_Cr1 will return n/a (corp-yield source unwired; see forward_plan.md §1 Known Data Gaps)`

</details>

<details><summary>Stale series</summary>


**EXPIRED** (7):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `CHN_POLICY_RATE` | FRED | Monthly | 2015-11-06 | 3886d | 45d |
| `CHN_PPI` | FRED | Monthly | 2022-12-02 | 1303d | 45d |
| `EA_HICP` | FRED | Monthly | 2023-01-06 | 1268d | 45d |
| `CHN_IND_PROD` | FRED | Monthly | 2023-11-03 | 967d | 45d |
| `DEU_IND_PROD` | FRED | Monthly | 2024-03-01 | 848d | 45d |
| `CHN_CPI` | FRED | Monthly | 2025-04-04 | 449d | 45d |
| `CAN_POLICY_RATE` | BoC | Daily | 2025-10-31 | 239d | 7d\* |

**STALE** (50):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `JP_TANKAN_LNFG` | BoJ | Quarterly | 2026-01-02 | 176d | 100d\* |
| `JP_TANKAN_SMFG` | BoJ | Quarterly | 2026-01-02 | 176d | 100d\* |
| `JP_TANKAN_SNFG` | BoJ | Quarterly | 2026-01-02 | 176d | 100d\* |
| `GBR_EMP_RATE` | ONS | Monthly | 2026-01-02 | 176d | 150d\* |
| `EA19_RATE_3M` | OECD | Monthly | 2026-02-06 | 141d | 90d\* |
| `JP_TANKAN_LMFG_FCST` | BoJ | Quarterly | 2026-02-06 | 141d | 100d\* |
| `JP_TANKAN_LNFG_FCST` | BoJ | Quarterly | 2026-02-06 | 141d | 100d\* |
| `JPN_IND_PROD` | e-Stat | Monthly | 2026-03-06 | 113d | 60d\* |
| `FRA_UNEMPLOYMENT` | OECD | Monthly | 2026-03-06 | 113d | 75d\* |
| `GBR_RATE_3M` | OECD | Monthly | 2026-03-06 | 113d | 90d\* |
| `CAN_GDP_MONTHLY` | StatCan | Monthly | 2026-03-06 | 113d | 60d\* |
| `GBR_GDP_REAL` | ONS | Quarterly | 2026-03-06 | 113d | 90d\* |
| `GBR_IND_PROD` | ONS | Monthly | 2026-03-06 | 113d | 105d\* |
| `USA_UNEMPLOYMENT` | OECD | Monthly | 2026-04-03 | 85d | 75d\* |
| `AWHMAN` | FRED | Monthly | 2026-04-03 | 85d | 75d\* |
| `CMRMTSPL` | FRED | Monthly | 2026-04-03 | 85d | 45d |
| `ITA_BUS_CONF` | FRED | Monthly | 2026-04-03 | 85d | 75d\* |
| `NLD_DSL_10Y` | FRED | Monthly | 2026-04-03 | 85d | 75d\* |
| `DEU_UNEMPLOYMENT` | OECD | Monthly | 2026-04-03 | 85d | 75d\* |
| `EZ_M3` | ECB | Monthly | 2026-04-03 | 85d | 45d\* |
| `JPN_SPPI` | BoJ | Monthly | 2026-04-03 | 85d | 45d\* |
| `JPN_MACH_ORDERS` | e-Stat | Monthly | 2026-04-03 | 85d | 60d\* |
| `CAN_CPI_MEDIAN` | BoC | Monthly | 2026-04-03 | 85d | 45d\* |
| `GBR_CPI_YOY` | ONS | Monthly | 2026-04-03 | 85d | 75d\* |
| `GBR_CPIH_YOY` | ONS | Monthly | 2026-04-03 | 85d | 75d\* |
| `GBR_GDP_MONTHLY` | ONS | Monthly | 2026-04-03 | 85d | 75d\* |
| `ITA_IND_PROD` | ISTAT | Monthly | 2026-04-03 | 85d | 60d\* |
| `PERMIT` | FRED | Monthly | 2026-05-01 | 57d | 45d |
| `USA_CPI_INDEX` | BLS | Monthly | 2026-05-01 | 57d | 45d\* |
| `USA_CORE_CPI_INDEX` | BLS | Monthly | 2026-05-01 | 57d | 45d\* |
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


**missing_columns** (13):
- _get_col(...,'EA_HICP_CORE_YOY') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv
- _get_col(...,'EU_ESI') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv
- _get_col(...,'EU_IND_CONF') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv
- _get_col(...,'EU_SVC_CONF') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv
- _get_col(...,'EZ_IND_PROD') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv
- _get_col(...,'EZ_RETAIL_VOL') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv
- _get_col(...,'GOLD_USD_PM') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv
- _get_col(...,'ISM_MFG_INVENTORIES') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv
- _get_col(...,'ISM_MFG_NEWORD') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv
- _get_col(...,'ISM_MFG_PMI') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv
- _get_col(...,'ISM_SVC_PMI') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv
- _get_col(...,'JPN_CORE_CPI_YOY') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv
- _get_col(...,'JPN_RETAIL_SALES') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv

**missing_explorer_indicators** (1):
- indicator 'US_ISM2' present in library but no `US_ISM2_raw` column in macro_market_hist.csv (trigger update_data run, or check calculator returned non-empty Series)

</details>

<details><summary>History preservation</summary>


| File | Live rows | Sister rows | Union | Live range | Sister range |
|---|---|---|---|---|---|
| `market_data_comp_hist.csv` | 3,991 | 3,991 | 3,991 | 1950-01-06 → 2026-06-26 | 1950-01-06 → 2026-06-26 |
| `macro_economic_hist.csv` | 4,149 | 4,149 | 4,149 | 1946-12-27 → 2026-06-26 | 1946-12-27 → 2026-06-26 |
| `macro_market_hist.csv` | 1,382 | 1,382 | 1,382 | 2000-01-07 → 2026-06-26 | 2000-01-07 → 2026-06-26 |

</details>

