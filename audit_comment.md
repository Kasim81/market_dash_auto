## Daily audit — 2026-06-10 — **45 ISSUES** (39 stale series, 4 static-check failures, 2 history-preservation issues)

_Run: 2026-06-10 16:46 UTC_

Full report attached as `data_audit.txt` in today's commit.

<details><summary>Stale series</summary>


**EXPIRED** (23):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `CHN_M2` | FRED | Monthly | 2019-08-02 | 2504d | 45d |
| `CHN_PPI` | FRED | Monthly | 2022-12-02 | 1286d | 45d |
| `CHN_IND_PROD` | FRED | Monthly | 2023-11-03 | 950d | 45d |
| `JPN_IND_PROD` | FRED | Monthly | 2024-03-01 | 831d | 45d |
| `GBR_CPI` | FRED | Monthly | 2025-03-07 | 460d | 45d |
| `CHN_CPI` | FRED | Monthly | 2025-04-04 | 432d | 45d |
| `CHN_POLICY_RATE` | DB.nomics | Monthly | 2025-06-06 | 369d | 45d |
| `EA_DEPOSIT_RATE` | ECB | Daily | 2025-06-13 | 362d | 30d\* |
| `ISM_SVC_PMI` | DB.nomics | Monthly | 2025-09-05 | 278d | 60d\* |
| `CAN_POLICY_RATE` | BoC | Daily | 2025-10-31 | 222d | 5d |
| `DEU_IND_PROD` | DB.nomics | Monthly | 2025-12-05 | 187d | 45d |
| `EA_HICP` | DB.nomics | Monthly | 2026-01-02 | 159d | 45d |
| `EU_ESI` | DB.nomics | Monthly | 2026-01-02 | 159d | 45d |
| `EU_IND_CONF` | DB.nomics | Monthly | 2026-01-02 | 159d | 45d |
| `EU_SVC_CONF` | DB.nomics | Monthly | 2026-01-02 | 159d | 45d |
| `ISM_MFG_PMI` | DB.nomics | Monthly | 2026-01-02 | 159d | 45d |
| `ISM_MFG_NEWORD` | DB.nomics | Monthly | 2026-01-02 | 159d | 45d |
| `GBR_EMP_RATE` | ONS | Monthly | 2026-01-02 | 159d | 45d |
| `GBR_UNEMPLOYMENT` | ONS | Monthly | 2026-02-06 | 124d | 45d |
| `CMRMTSPL` | FRED | Monthly | 2026-03-06 | 96d | 45d |
| `GBR_AWE_REGPAY_YOY` | ONS | Monthly | 2026-03-06 | 96d | 45d |
| `T5YIFR` | FRED | Daily | 2026-05-29 | 12d | 5d |
| `JPN_POLICY_RATE` | BoJ | Daily | 2026-05-29 | 12d | 5d |

**STALE** (16):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `EZ_EMPLOYMENT` | DB.nomics | Quarterly | 2025-10-03 | 250d | 180d\* |
| `EZ_IND_PROD` | DB.nomics | Monthly | 2025-12-05 | 187d | 150d\* |
| `EZ_RETAIL_VOL` | DB.nomics | Monthly | 2025-12-05 | 187d | 150d\* |
| `EA19_RATE_3M` | OECD | Monthly | 2026-02-06 | 124d | 90d\* |
| `ITA_BTP_10Y` | FRED | Monthly | 2026-03-06 | 96d | 90d\* |
| `IND_GOVT_10Y` | FRED | Monthly | 2026-03-06 | 96d | 90d\* |
| `CHN_CON_CONF` | FRED | Monthly | 2026-03-06 | 96d | 90d\* |
| `NLD_DSL_10Y` | FRED | Monthly | 2026-03-06 | 96d | 75d\* |
| `FRA_UNEMPLOYMENT` | OECD | Monthly | 2026-03-06 | 96d | 75d\* |
| `GBR_RATE_3M` | OECD | Monthly | 2026-03-06 | 96d | 90d\* |
| `PERMIT` | FRED | Monthly | 2026-04-03 | 68d | 45d |
| `CAN_CPI_MEDIAN` | BoC | Monthly | 2026-04-03 | 68d | 45d |
| `GBR_CPI_YOY` | ONS | Monthly | 2026-04-03 | 68d | 45d |
| `GBR_CPIH_YOY` | ONS | Monthly | 2026-04-03 | 68d | 45d |
| `AUS_PART_RATE` | ABS | Monthly | 2026-04-03 | 68d | 45d |
| `NFCI` | FRED | Weekly | 2026-05-22 | 19d | 14d\* |

</details>

<details><summary>Static-check failures</summary>


**missing_columns** (3):
- _get_col(...,'EA_HICP_CORE_YOY') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv
- _get_col(...,'GBR_CORE_CPI_YOY') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv
- _get_col(...,'JPN_CORE_CPI_YOY') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv

**registry_drift** (1):
- hist column 'FRA_GDP_INDEX' present in macro_economic_hist.csv but no matching row in source-of-truth library (run: python library_sync.py --confirm)

</details>

<details><summary>History preservation</summary>


| File | Live rows | Sister rows | Union | Live range | Sister range |
|---|---|---|---|---|---|
| `market_data_comp_hist.csv` | 3,988 | 3,988 | 3,988 | 1950-01-06 → 2026-06-05 | 1950-01-06 → 2026-06-05 |
| `macro_economic_hist.csv` | 4,146 | 4,140 | 4,146 | 1946-12-27 → 2026-06-05 | 1946-12-27 → 2026-04-24 |
| `macro_market_hist.csv` | 1,380 | 1,374 | 1,380 | 2000-01-07 → 2026-06-12 | 2000-01-07 → 2026-05-01 |

**ALERTS** (2):
- macro_economic_hist.csv: sister rows are a strict subset of live (4140 ⊂ 4146) — sister may have been rewritten incorrectly
- macro_market_hist.csv: sister rows are a strict subset of live (1374 ⊂ 1380) — sister may have been rewritten incorrectly

</details>

