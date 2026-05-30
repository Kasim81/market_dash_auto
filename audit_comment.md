## Daily audit — 2026-05-30 — **48 ISSUES** (2 fetch errors, 43 stale series, 3 static-check failures)

_Run: 2026-05-30 04:52 UTC_

Full report attached as `data_audit.txt` in today's commit.

<details><summary>Fetch errors</summary>


**yfinance_dead** (1):
- `^SP500-151050`

**other_warnings** (1):
- `[ECB] EU_I1 spread unavailable — EU_Cr1 will return n/a (corp-yield source unwired; see forward_plan.md §1 Known Data Gaps)`

</details>

<details><summary>Stale series</summary>


**EXPIRED** (18):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `CHN_M2` | FRED | Monthly | 2019-08-02 | 2493d | 45d |
| `CHN_PPI` | FRED | Monthly | 2022-12-02 | 1275d | 45d |
| `CHN_IND_PROD` | FRED | Monthly | 2023-11-03 | 939d | 45d |
| `JPN_IND_PROD` | FRED | Monthly | 2024-03-01 | 820d | 45d |
| `GBR_CPI` | FRED | Monthly | 2025-03-07 | 449d | 45d |
| `CHN_CPI` | FRED | Monthly | 2025-04-04 | 421d | 45d |
| `CHN_POLICY_RATE` | DB.nomics | Monthly | 2025-06-06 | 358d | 45d |
| `EA_DEPOSIT_RATE` | ECB | Daily | 2025-06-13 | 351d | 30d\* |
| `ISM_SVC_PMI` | DB.nomics | Monthly | 2025-09-05 | 267d | 60d\* |
| `CAN_POLICY_RATE` | BoC | Daily | 2025-10-31 | 211d | 5d |
| `DEU_IND_PROD` | DB.nomics | Monthly | 2025-12-05 | 176d | 45d |
| `FEDFUNDS` | FRED | Monthly | 2026-01-02 | 148d | 45d |
| `EA_HICP` | DB.nomics | Monthly | 2026-01-02 | 148d | 45d |
| `EU_ESI` | DB.nomics | Monthly | 2026-01-02 | 148d | 45d |
| `EU_IND_CONF` | DB.nomics | Monthly | 2026-01-02 | 148d | 45d |
| `ISM_MFG_NEWORD` | DB.nomics | Monthly | 2026-01-02 | 148d | 45d |
| `GBR_EMP_RATE` | ONS | Monthly | 2026-01-02 | 148d | 45d |
| `GBR_UNEMPLOYMENT` | ONS | Monthly | 2026-02-06 | 113d | 45d |

**STALE** (25):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `EZ_EMPLOYMENT` | DB.nomics | Quarterly | 2025-10-03 | 239d | 180d\* |
| `EZ_IND_PROD` | DB.nomics | Monthly | 2025-12-05 | 176d | 150d\* |
| `EZ_RETAIL_VOL` | DB.nomics | Monthly | 2025-12-05 | 176d | 150d\* |
| `AUS_GDP_REAL` | ABS | Quarterly | 2025-12-05 | 176d | 120d |
| `DEU_UNEMPLOYMENT` | OECD | Monthly | 2026-01-02 | 148d | 75d\* |
| `EA19_RATE_3M` | OECD | Monthly | 2026-02-06 | 113d | 90d\* |
| `PIORECRUSDM` | FRED | Monthly | 2026-03-06 | 85d | 75d\* |
| `CMRMTSPL` | FRED | Monthly | 2026-03-06 | 85d | 45d |
| `FRA_UNEMPLOYMENT` | OECD | Monthly | 2026-03-06 | 85d | 75d\* |
| `CAN_GDP_MONTHLY` | StatCan | Monthly | 2026-03-06 | 85d | 45d |
| `GBR_AWE_REGPAY_YOY` | ONS | Monthly | 2026-03-06 | 85d | 45d |
| `ITA_IND_PROD` | ISTAT | Monthly | 2026-03-06 | 85d | 45d |
| `PERMIT` | FRED | Monthly | 2026-04-03 | 57d | 45d |
| `USA_CPI_INDEX` | BLS | Monthly | 2026-04-03 | 57d | 45d |
| `USA_CORE_CPI_INDEX` | BLS | Monthly | 2026-04-03 | 57d | 45d |
| `AUS_UNEMPLOYMENT` | ABS | Monthly | 2026-04-03 | 57d | 45d |
| `ITA_UNEMPLOYMENT` | ISTAT | Monthly | 2026-04-03 | 57d | 45d |
| `CAN_CPI` | StatCan | Monthly | 2026-04-03 | 57d | 45d |
| `CAN_CPI_MEDIAN` | BoC | Monthly | 2026-04-03 | 57d | 45d |
| `CAN_EMPLOYMENT` | StatCan | Monthly | 2026-04-03 | 57d | 45d |
| `GBR_CPI_YOY` | ONS | Monthly | 2026-04-03 | 57d | 45d |
| `GBR_CPIH_YOY` | ONS | Monthly | 2026-04-03 | 57d | 45d |
| `AUS_PART_RATE` | ABS | Monthly | 2026-04-03 | 57d | 45d |
| `USA_AVG_HOURLY_EARN` | BLS | Monthly | 2026-04-03 | 57d | 45d |
| `T5YIE` | FRED | Daily | 2026-05-22 | 8d | 5d |

</details>

<details><summary>Static-check failures</summary>


**missing_columns** (3):
- _get_col(...,'DE_IFO') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv
- _get_col(...,'EU_SVC_CONF') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv
- _get_col(...,'ISM_MFG_PMI') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv

</details>

<details><summary>History preservation</summary>


| File | Live rows | Sister rows | Union | Live range | Sister range |
|---|---|---|---|---|---|
| `market_data_comp_hist.csv` | 3,987 | 3,987 | 3,987 | 1950-01-06 → 2026-05-29 | 1950-01-06 → 2026-05-29 |
| `macro_economic_hist.csv` | 4,145 | 4,145 | 4,145 | 1946-12-27 → 2026-05-29 | 1946-12-27 → 2026-05-29 |
| `macro_market_hist.csv` | 1,378 | 1,378 | 1,378 | 2000-01-07 → 2026-05-29 | 2000-01-07 → 2026-05-29 |

</details>


_audit_writeback: 1 ticker(s) on active dead-list streak (threshold 14d); none flipped this run._
