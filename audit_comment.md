## Daily audit — 2026-06-12 — **67 ISSUES** (54 stale series, 11 static-check failures, 2 history-preservation issues)

_Run: 2026-06-12 06:42 UTC_

Full report attached as `data_audit.txt` in today's commit.

<details><summary>Stale series</summary>


**EXPIRED** (22):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `CHN_M2` | FRED | Monthly | 2019-08-02 | 2506d | 45d |
| `CHN_PPI` | FRED | Monthly | 2022-12-02 | 1288d | 45d |
| `CHN_IND_PROD` | FRED | Monthly | 2023-11-03 | 952d | 45d |
| `JPN_IND_PROD` | FRED | Monthly | 2024-03-01 | 833d | 45d |
| `GBR_CPI` | FRED | Monthly | 2025-03-07 | 462d | 45d |
| `CHN_CPI` | FRED | Monthly | 2025-04-04 | 434d | 45d |
| `CHN_POLICY_RATE` | DB.nomics | Monthly | 2025-06-06 | 371d | 45d |
| `EA_DEPOSIT_RATE` | ECB | Daily | 2025-06-13 | 364d | 30d\* |
| `ISM_SVC_PMI` | DB.nomics | Monthly | 2025-09-05 | 280d | 60d\* |
| `JPN_MACH_ORDERS` | e-Stat | Monthly | 2025-10-03 | 252d | 60d\* |
| `CAN_POLICY_RATE` | BoC | Daily | 2025-10-31 | 224d | 7d\* |
| `DEU_IND_PROD` | DB.nomics | Monthly | 2025-12-05 | 189d | 45d |
| `EA_HICP` | DB.nomics | Monthly | 2026-01-02 | 161d | 45d |
| `EU_ESI` | DB.nomics | Monthly | 2026-01-02 | 161d | 45d |
| `EU_IND_CONF` | DB.nomics | Monthly | 2026-01-02 | 161d | 45d |
| `EU_SVC_CONF` | DB.nomics | Monthly | 2026-01-02 | 161d | 45d |
| `ISM_MFG_PMI` | DB.nomics | Monthly | 2026-01-02 | 161d | 45d |
| `ISM_MFG_NEWORD` | DB.nomics | Monthly | 2026-01-02 | 161d | 45d |
| `EA_HICP_CORE_YOY` | DB.nomics | Monthly | 2026-01-02 | 161d | 45d |
| `CMRMTSPL` | FRED | Monthly | 2026-03-06 | 98d | 45d |
| `T5YIFR` | FRED | Daily | 2026-05-29 | 14d | 5d |
| `JPN_POLICY_RATE` | BoJ | Daily | 2026-05-29 | 14d | 5d |

**STALE** (32):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `EZ_EMPLOYMENT` | DB.nomics | Quarterly | 2025-10-03 | 252d | 180d\* |
| `EZ_IND_PROD` | DB.nomics | Monthly | 2025-12-05 | 189d | 150d\* |
| `EZ_RETAIL_VOL` | DB.nomics | Monthly | 2025-12-05 | 189d | 150d\* |
| `GBR_EMP_RATE` | ONS | Monthly | 2026-01-02 | 161d | 150d\* |
| `EA19_RATE_3M` | OECD | Monthly | 2026-02-06 | 126d | 90d\* |
| `ITA_BTP_10Y` | FRED | Monthly | 2026-03-06 | 98d | 90d\* |
| `IND_GOVT_10Y` | FRED | Monthly | 2026-03-06 | 98d | 90d\* |
| `CHN_CON_CONF` | FRED | Monthly | 2026-03-06 | 98d | 90d\* |
| `NLD_DSL_10Y` | FRED | Monthly | 2026-03-06 | 98d | 75d\* |
| `FRA_UNEMPLOYMENT` | OECD | Monthly | 2026-03-06 | 98d | 75d\* |
| `GBR_RATE_3M` | OECD | Monthly | 2026-03-06 | 98d | 90d\* |
| `CAN_GDP_MONTHLY` | StatCan | Monthly | 2026-03-06 | 98d | 60d\* |
| `GBR_GDP_REAL` | ONS | Quarterly | 2026-03-06 | 98d | 90d\* |
| `PERMIT` | FRED | Monthly | 2026-04-03 | 70d | 45d |
| `CAN_CPI` | StatCan | Monthly | 2026-04-03 | 70d | 45d\* |
| `JPN_SPPI` | BoJ | Monthly | 2026-04-03 | 70d | 45d\* |
| `CAN_CPI_MEDIAN` | BoC | Monthly | 2026-04-03 | 70d | 45d\* |
| `ITA_IND_PROD` | ISTAT | Monthly | 2026-04-03 | 70d | 60d\* |
| `NFCI` | FRED | Weekly | 2026-05-22 | 21d | 14d\* |
| `T10Y2Y` | FRED | Daily | 2026-06-05 | 7d | 5d |
| `T10Y3M` | FRED | Daily | 2026-06-05 | 7d | 5d |
| `T5YIE` | FRED | Daily | 2026-06-05 | 7d | 5d |
| `T10YIE` | FRED | Daily | 2026-06-05 | 7d | 5d |
| `DGS2` | FRED | Daily | 2026-06-05 | 7d | 5d |
| `DGS10` | FRED | Daily | 2026-06-05 | 7d | 5d |
| `DFII10` | FRED | Daily | 2026-06-05 | 7d | 5d |
| `DFII5` | FRED | Daily | 2026-06-05 | 7d | 5d |
| `BAMLH0A0HYM2` | FRED | Daily | 2026-06-05 | 7d | 5d |
| `BAMLC0A0CM` | FRED | Daily | 2026-06-05 | 7d | 5d |
| `BAMLC0A0CMEY` | FRED | Daily | 2026-06-05 | 7d | 5d |
| _… 2 more in `data_audit.txt`_ |  |  |  |  |  |

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


**missing_columns** (5):
- _get_col(...,'GBR_GDP_MONTHLY') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv
- _get_col(...,'JP_TANKAN_LMFG_FCST') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv
- _get_col(...,'JP_TANKAN_LNFG') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv
- _get_col(...,'JP_TANKAN_SMFG') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv
- _get_col(...,'US_GDPNOW') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv

**missing_explorer_indicators** (6):
- indicator 'EU_NOWCAST1' present in library but no `EU_NOWCAST1_raw` column in macro_market_hist.csv (trigger update_data run, or check calculator returned non-empty Series)
- indicator 'US_GDPNOW1' present in library but no `US_GDPNOW1_raw` column in macro_market_hist.csv (trigger update_data run, or check calculator returned non-empty Series)
- indicator 'JP_TANKAN_SPREAD1' present in library but no `JP_TANKAN_SPREAD1_raw` column in macro_market_hist.csv (trigger update_data run, or check calculator returned non-empty Series)
- indicator 'JP_TANKAN_SVC1' present in library but no `JP_TANKAN_SVC1_raw` column in macro_market_hist.csv (trigger update_data run, or check calculator returned non-empty Series)
- indicator 'JP_TANKAN_FWD1' present in library but no `JP_TANKAN_FWD1_raw` column in macro_market_hist.csv (trigger update_data run, or check calculator returned non-empty Series)
- indicator 'UK_NOWCAST1' present in library but no `UK_NOWCAST1_raw` column in macro_market_hist.csv (trigger update_data run, or check calculator returned non-empty Series)

</details>

<details><summary>History preservation</summary>


| File | Live rows | Sister rows | Union | Live range | Sister range |
|---|---|---|---|---|---|
| `market_data_comp_hist.csv` | 3,989 | 3,989 | 3,989 | 1950-01-06 → 2026-06-12 | 1950-01-06 → 2026-06-12 |
| `macro_economic_hist.csv` | 4,146 | 4,140 | 4,146 | 1946-12-27 → 2026-06-05 | 1946-12-27 → 2026-04-24 |
| `macro_market_hist.csv` | 1,380 | 1,374 | 1,380 | 2000-01-07 → 2026-06-12 | 2000-01-07 → 2026-05-01 |

**ALERTS** (2):
- macro_economic_hist.csv: sister rows are a strict subset of live (4140 ⊂ 4146) — sister may have been rewritten incorrectly
- macro_market_hist.csv: sister rows are a strict subset of live (1374 ⊂ 1380) — sister may have been rewritten incorrectly

</details>

