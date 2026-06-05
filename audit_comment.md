## Daily audit — 2026-06-05 — **44 ISSUES** (2 fetch errors, 42 stale series)

_Run: 2026-06-05 06:36 UTC_

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
| `CHN_M2` | FRED | Monthly | 2019-08-02 | 2499d | 45d |
| `CHN_PPI` | FRED | Monthly | 2022-12-02 | 1281d | 45d |
| `CHN_IND_PROD` | FRED | Monthly | 2023-11-03 | 945d | 45d |
| `JPN_IND_PROD` | FRED | Monthly | 2024-03-01 | 826d | 45d |
| `GBR_CPI` | FRED | Monthly | 2025-03-07 | 455d | 45d |
| `CHN_CPI` | FRED | Monthly | 2025-04-04 | 427d | 45d |
| `CHN_POLICY_RATE` | DB.nomics | Monthly | 2025-06-06 | 364d | 45d |
| `EA_DEPOSIT_RATE` | ECB | Daily | 2025-06-13 | 357d | 30d\* |
| `ISM_SVC_PMI` | DB.nomics | Monthly | 2025-09-05 | 273d | 60d\* |
| `CAN_POLICY_RATE` | BoC | Daily | 2025-10-31 | 217d | 5d |
| `DEU_IND_PROD` | DB.nomics | Monthly | 2025-12-05 | 182d | 45d |
| `EA_HICP` | DB.nomics | Monthly | 2026-01-02 | 154d | 45d |
| `EU_ESI` | DB.nomics | Monthly | 2026-01-02 | 154d | 45d |
| `EU_IND_CONF` | DB.nomics | Monthly | 2026-01-02 | 154d | 45d |
| `EU_SVC_CONF` | DB.nomics | Monthly | 2026-01-02 | 154d | 45d |
| `ISM_MFG_PMI` | DB.nomics | Monthly | 2026-01-02 | 154d | 45d |
| `ISM_MFG_NEWORD` | DB.nomics | Monthly | 2026-01-02 | 154d | 45d |
| `GBR_EMP_RATE` | ONS | Monthly | 2026-01-02 | 154d | 45d |
| `GBR_UNEMPLOYMENT` | ONS | Monthly | 2026-02-06 | 119d | 45d |
| `CMRMTSPL` | FRED | Monthly | 2026-03-06 | 91d | 45d |
| `GBR_AWE_REGPAY_YOY` | ONS | Monthly | 2026-03-06 | 91d | 45d |

**STALE** (21):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `EZ_EMPLOYMENT` | DB.nomics | Quarterly | 2025-10-03 | 245d | 180d\* |
| `EZ_IND_PROD` | DB.nomics | Monthly | 2025-12-05 | 182d | 150d\* |
| `EZ_RETAIL_VOL` | DB.nomics | Monthly | 2025-12-05 | 182d | 150d\* |
| `EA19_RATE_3M` | OECD | Monthly | 2026-02-06 | 119d | 90d\* |
| `PIORECRUSDM` | FRED | Monthly | 2026-03-06 | 91d | 75d\* |
| `ITA_BTP_10Y` | FRED | Monthly | 2026-03-06 | 91d | 90d\* |
| `IND_GOVT_10Y` | FRED | Monthly | 2026-03-06 | 91d | 90d\* |
| `CHN_CON_CONF` | FRED | Monthly | 2026-03-06 | 91d | 90d\* |
| `FRA_UNEMPLOYMENT` | OECD | Monthly | 2026-03-06 | 91d | 75d\* |
| `GBR_RATE_3M` | OECD | Monthly | 2026-03-06 | 91d | 90d\* |
| `PERMIT` | FRED | Monthly | 2026-04-03 | 63d | 45d |
| `USA_CPI_INDEX` | BLS | Monthly | 2026-04-03 | 63d | 45d |
| `USA_CORE_CPI_INDEX` | BLS | Monthly | 2026-04-03 | 63d | 45d |
| `CAN_CPI_MEDIAN` | BoC | Monthly | 2026-04-03 | 63d | 45d |
| `GBR_CPI_YOY` | ONS | Monthly | 2026-04-03 | 63d | 45d |
| `GBR_CPIH_YOY` | ONS | Monthly | 2026-04-03 | 63d | 45d |
| `AUS_PART_RATE` | ABS | Monthly | 2026-04-03 | 63d | 45d |
| `USA_AVG_HOURLY_EARN` | BLS | Monthly | 2026-04-03 | 63d | 45d |
| `T5YIFR` | FRED | Daily | 2026-05-29 | 7d | 5d |
| `DEU_BUND_10Y` | Bundesbank | Daily | 2026-05-29 | 7d | 5d |
| `JPN_POLICY_RATE` | BoJ | Daily | 2026-05-29 | 7d | 5d |

</details>

<details><summary>History preservation</summary>


| File | Live rows | Sister rows | Union | Live range | Sister range |
|---|---|---|---|---|---|
| `market_data_comp_hist.csv` | 3,988 | 3,988 | 3,988 | 1950-01-06 → 2026-06-05 | 1950-01-06 → 2026-06-05 |
| `macro_economic_hist.csv` | 4,146 | 4,146 | 4,146 | 1946-12-27 → 2026-06-05 | 1946-12-27 → 2026-06-05 |
| `macro_market_hist.csv` | 1,379 | 1,379 | 1,379 | 2000-01-07 → 2026-06-05 | 2000-01-07 → 2026-06-05 |

</details>


_audit_writeback: 1 ticker(s) on active dead-list streak (threshold 14d); none flipped this run._
