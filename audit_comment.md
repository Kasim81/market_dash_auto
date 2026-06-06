## Daily audit — 2026-06-06 — **39 ISSUES** (2 fetch errors, 31 stale series, 6 static-check failures)

_Run: 2026-06-06 06:15 UTC_

Full report attached as `data_audit.txt` in today's commit.

<details><summary>Fetch errors</summary>


**yfinance_dead** (1):
- `^SP500-151050`

**other_warnings** (1):
- `[ECB] EU_I1 spread unavailable — EU_Cr1 will return n/a (corp-yield source unwired; see forward_plan.md §1 Known Data Gaps)`

</details>

<details><summary>Stale series</summary>


**EXPIRED** (16):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `CHN_POLICY_RATE` | FRED | Monthly | 2015-11-06 | 3865d | 45d |
| `CHN_M2` | FRED | Monthly | 2019-08-02 | 2500d | 45d |
| `CHN_PPI` | FRED | Monthly | 2022-12-02 | 1282d | 45d |
| `EA_HICP` | FRED | Monthly | 2023-01-06 | 1247d | 45d |
| `CHN_IND_PROD` | FRED | Monthly | 2023-11-03 | 946d | 45d |
| `DEU_IND_PROD` | FRED | Monthly | 2024-03-01 | 827d | 45d |
| `JPN_IND_PROD` | FRED | Monthly | 2024-03-01 | 827d | 45d |
| `GBR_CPI` | FRED | Monthly | 2025-03-07 | 456d | 45d |
| `CHN_CPI` | FRED | Monthly | 2025-04-04 | 428d | 45d |
| `EA_DEPOSIT_RATE` | ECB | Daily | 2025-06-13 | 358d | 30d\* |
| `CAN_POLICY_RATE` | BoC | Daily | 2025-10-31 | 218d | 5d |
| `GBR_EMP_RATE` | ONS | Monthly | 2026-01-02 | 155d | 45d |
| `GBR_UNEMPLOYMENT` | ONS | Monthly | 2026-02-06 | 120d | 45d |
| `USA_UNEMPLOYMENT` | BLS | Monthly | 2026-03-06 | 92d | 45d |
| `CMRMTSPL` | FRED | Monthly | 2026-03-06 | 92d | 45d |
| `GBR_AWE_REGPAY_YOY` | ONS | Monthly | 2026-03-06 | 92d | 45d |

**STALE** (15):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `EA19_RATE_3M` | OECD | Monthly | 2026-02-06 | 120d | 90d\* |
| `ITA_BTP_10Y` | FRED | Monthly | 2026-03-06 | 92d | 90d\* |
| `IND_GOVT_10Y` | FRED | Monthly | 2026-03-06 | 92d | 90d\* |
| `CHN_CON_CONF` | FRED | Monthly | 2026-03-06 | 92d | 90d\* |
| `FRA_UNEMPLOYMENT` | OECD | Monthly | 2026-03-06 | 92d | 75d\* |
| `GBR_RATE_3M` | OECD | Monthly | 2026-03-06 | 92d | 90d\* |
| `PERMIT` | FRED | Monthly | 2026-04-03 | 64d | 45d |
| `USA_CPI_INDEX` | BLS | Monthly | 2026-04-03 | 64d | 45d |
| `USA_CORE_CPI_INDEX` | BLS | Monthly | 2026-04-03 | 64d | 45d |
| `CAN_CPI_MEDIAN` | BoC | Monthly | 2026-04-03 | 64d | 45d |
| `GBR_CPI_YOY` | ONS | Monthly | 2026-04-03 | 64d | 45d |
| `GBR_CPIH_YOY` | ONS | Monthly | 2026-04-03 | 64d | 45d |
| `AUS_PART_RATE` | ABS | Monthly | 2026-04-03 | 64d | 45d |
| `T5YIFR` | FRED | Daily | 2026-05-29 | 8d | 5d |
| `JPN_POLICY_RATE` | BoJ | Daily | 2026-05-29 | 8d | 5d |

</details>

<details><summary>Static-check failures</summary>


**missing_columns** (6):
- _get_col(...,'EU_ESI') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv
- _get_col(...,'EU_IND_CONF') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv
- _get_col(...,'EU_SVC_CONF') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv
- _get_col(...,'ISM_MFG_NEWORD') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv
- _get_col(...,'ISM_MFG_PMI') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv
- _get_col(...,'ISM_SVC_PMI') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv

</details>

<details><summary>History preservation</summary>


| File | Live rows | Sister rows | Union | Live range | Sister range |
|---|---|---|---|---|---|
| `market_data_comp_hist.csv` | 3,988 | 3,988 | 3,988 | 1950-01-06 → 2026-06-05 | 1950-01-06 → 2026-06-05 |
| `macro_economic_hist.csv` | 4,146 | 4,146 | 4,146 | 1946-12-27 → 2026-06-05 | 1946-12-27 → 2026-06-05 |
| `macro_market_hist.csv` | 1,379 | 1,379 | 1,379 | 2000-01-07 → 2026-06-05 | 2000-01-07 → 2026-06-05 |

</details>


_audit_writeback: 1 ticker(s) on active dead-list streak (threshold 14d); none flipped this run._
