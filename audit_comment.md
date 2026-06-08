## Daily audit — 2026-06-08 — **41 ISSUES** (2 fetch errors, 38 stale series, 1 static-check failure)

_Run: 2026-06-08 06:53 UTC_

Full report attached as `data_audit.txt` in today's commit.

<details><summary>Fetch errors</summary>


**yfinance_dead** (1):
- `^SP500-151050`

**other_warnings** (1):
- `[ECB] EU_I1 spread unavailable — EU_Cr1 will return n/a (corp-yield source unwired; see forward_plan.md §1 Known Data Gaps)`

</details>

<details><summary>Stale series</summary>


**EXPIRED** (21):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `CHN_M2` | FRED | Monthly | 2019-08-02 | 2502d | 45d |
| `CHN_PPI` | FRED | Monthly | 2022-12-02 | 1284d | 45d |
| `CHN_IND_PROD` | FRED | Monthly | 2023-11-03 | 948d | 45d |
| `JPN_IND_PROD` | FRED | Monthly | 2024-03-01 | 829d | 45d |
| `GBR_CPI` | FRED | Monthly | 2025-03-07 | 458d | 45d |
| `CHN_CPI` | FRED | Monthly | 2025-04-04 | 430d | 45d |
| `CHN_POLICY_RATE` | DB.nomics | Monthly | 2025-06-06 | 367d | 45d |
| `EA_DEPOSIT_RATE` | ECB | Daily | 2025-06-13 | 360d | 30d\* |
| `ISM_SVC_PMI` | DB.nomics | Monthly | 2025-09-05 | 276d | 60d\* |
| `CAN_POLICY_RATE` | BoC | Daily | 2025-10-31 | 220d | 5d |
| `DEU_IND_PROD` | DB.nomics | Monthly | 2025-12-05 | 185d | 45d |
| `EA_HICP` | DB.nomics | Monthly | 2026-01-02 | 157d | 45d |
| `EU_ESI` | DB.nomics | Monthly | 2026-01-02 | 157d | 45d |
| `EU_IND_CONF` | DB.nomics | Monthly | 2026-01-02 | 157d | 45d |
| `EU_SVC_CONF` | DB.nomics | Monthly | 2026-01-02 | 157d | 45d |
| `ISM_MFG_PMI` | DB.nomics | Monthly | 2026-01-02 | 157d | 45d |
| `ISM_MFG_NEWORD` | DB.nomics | Monthly | 2026-01-02 | 157d | 45d |
| `GBR_EMP_RATE` | ONS | Monthly | 2026-01-02 | 157d | 45d |
| `GBR_UNEMPLOYMENT` | ONS | Monthly | 2026-02-06 | 122d | 45d |
| `CMRMTSPL` | FRED | Monthly | 2026-03-06 | 94d | 45d |
| `GBR_AWE_REGPAY_YOY` | ONS | Monthly | 2026-03-06 | 94d | 45d |

**STALE** (17):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `EZ_EMPLOYMENT` | DB.nomics | Quarterly | 2025-10-03 | 248d | 180d\* |
| `EZ_IND_PROD` | DB.nomics | Monthly | 2025-12-05 | 185d | 150d\* |
| `EZ_RETAIL_VOL` | DB.nomics | Monthly | 2025-12-05 | 185d | 150d\* |
| `EA19_RATE_3M` | OECD | Monthly | 2026-02-06 | 122d | 90d\* |
| `ITA_BTP_10Y` | FRED | Monthly | 2026-03-06 | 94d | 90d\* |
| `IND_GOVT_10Y` | FRED | Monthly | 2026-03-06 | 94d | 90d\* |
| `CHN_CON_CONF` | FRED | Monthly | 2026-03-06 | 94d | 90d\* |
| `FRA_UNEMPLOYMENT` | OECD | Monthly | 2026-03-06 | 94d | 75d\* |
| `GBR_RATE_3M` | OECD | Monthly | 2026-03-06 | 94d | 90d\* |
| `PERMIT` | FRED | Monthly | 2026-04-03 | 66d | 45d |
| `USA_CPI_INDEX` | BLS | Monthly | 2026-04-03 | 66d | 45d |
| `USA_CORE_CPI_INDEX` | BLS | Monthly | 2026-04-03 | 66d | 45d |
| `CAN_CPI_MEDIAN` | BoC | Monthly | 2026-04-03 | 66d | 45d |
| `GBR_CPI_YOY` | ONS | Monthly | 2026-04-03 | 66d | 45d |
| `GBR_CPIH_YOY` | ONS | Monthly | 2026-04-03 | 66d | 45d |
| `AUS_PART_RATE` | ABS | Monthly | 2026-04-03 | 66d | 45d |
| `T5YIFR` | FRED | Daily | 2026-05-29 | 10d | 5d |

</details>

<details><summary>Static-check failures</summary>


**missing_columns** (1):
- _get_col(...,'DE_IFO') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv

</details>

<details><summary>History preservation</summary>


| File | Live rows | Sister rows | Union | Live range | Sister range |
|---|---|---|---|---|---|
| `market_data_comp_hist.csv` | 3,988 | 3,988 | 3,988 | 1950-01-06 → 2026-06-05 | 1950-01-06 → 2026-06-05 |
| `macro_economic_hist.csv` | 4,146 | 4,146 | 4,146 | 1946-12-27 → 2026-06-05 | 1946-12-27 → 2026-06-05 |
| `macro_market_hist.csv` | 1,379 | 1,379 | 1,379 | 2000-01-07 → 2026-06-05 | 2000-01-07 → 2026-06-05 |

</details>


_audit_writeback: flipped 1 row(s) to validation_status=UNAVAILABLE after 14-day dead-list streak: ^SP500-151050._
