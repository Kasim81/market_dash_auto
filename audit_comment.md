## Daily audit — 2026-06-02 — **43 ISSUES** (2 fetch errors, 41 stale series)

_Run: 2026-06-02 05:28 UTC_

Full report attached as `data_audit.txt` in today's commit.

<details><summary>Fetch errors</summary>


**yfinance_dead** (1):
- `^SP500-151050`

**other_warnings** (1):
- `[ECB] EU_I1 spread unavailable — EU_Cr1 will return n/a (corp-yield source unwired; see forward_plan.md §1 Known Data Gaps)`

</details>

<details><summary>Stale series</summary>


**EXPIRED** (19):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `CHN_M2` | FRED | Monthly | 2019-08-02 | 2496d | 45d |
| `CHN_PPI` | FRED | Monthly | 2022-12-02 | 1278d | 45d |
| `CHN_IND_PROD` | FRED | Monthly | 2023-11-03 | 942d | 45d |
| `JPN_IND_PROD` | FRED | Monthly | 2024-03-01 | 823d | 45d |
| `GBR_CPI` | FRED | Monthly | 2025-03-07 | 452d | 45d |
| `CHN_CPI` | FRED | Monthly | 2025-04-04 | 424d | 45d |
| `CHN_POLICY_RATE` | DB.nomics | Monthly | 2025-06-06 | 361d | 45d |
| `EA_DEPOSIT_RATE` | ECB | Daily | 2025-06-13 | 354d | 30d\* |
| `ISM_SVC_PMI` | DB.nomics | Monthly | 2025-09-05 | 270d | 60d\* |
| `CAN_POLICY_RATE` | BoC | Daily | 2025-10-31 | 214d | 5d |
| `DEU_IND_PROD` | DB.nomics | Monthly | 2025-12-05 | 179d | 45d |
| `EA_HICP` | DB.nomics | Monthly | 2026-01-02 | 151d | 45d |
| `EU_ESI` | DB.nomics | Monthly | 2026-01-02 | 151d | 45d |
| `EU_IND_CONF` | DB.nomics | Monthly | 2026-01-02 | 151d | 45d |
| `EU_SVC_CONF` | DB.nomics | Monthly | 2026-01-02 | 151d | 45d |
| `ISM_MFG_PMI` | DB.nomics | Monthly | 2026-01-02 | 151d | 45d |
| `ISM_MFG_NEWORD` | DB.nomics | Monthly | 2026-01-02 | 151d | 45d |
| `GBR_EMP_RATE` | ONS | Monthly | 2026-01-02 | 151d | 45d |
| `GBR_UNEMPLOYMENT` | ONS | Monthly | 2026-02-06 | 116d | 45d |

**STALE** (22):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `EZ_EMPLOYMENT` | DB.nomics | Quarterly | 2025-10-03 | 242d | 180d\* |
| `EZ_IND_PROD` | DB.nomics | Monthly | 2025-12-05 | 179d | 150d\* |
| `EZ_RETAIL_VOL` | DB.nomics | Monthly | 2025-12-05 | 179d | 150d\* |
| `AUS_GDP_REAL` | ABS | Quarterly | 2025-12-05 | 179d | 120d |
| `EA19_RATE_3M` | OECD | Monthly | 2026-02-06 | 116d | 90d\* |
| `PIORECRUSDM` | FRED | Monthly | 2026-03-06 | 88d | 75d\* |
| `CMRMTSPL` | FRED | Monthly | 2026-03-06 | 88d | 45d |
| `FRA_UNEMPLOYMENT` | OECD | Monthly | 2026-03-06 | 88d | 75d\* |
| `CAN_GDP_MONTHLY` | StatCan | Monthly | 2026-03-06 | 88d | 45d |
| `GBR_AWE_REGPAY_YOY` | ONS | Monthly | 2026-03-06 | 88d | 45d |
| `ITA_IND_PROD` | ISTAT | Monthly | 2026-03-06 | 88d | 45d |
| `PERMIT` | FRED | Monthly | 2026-04-03 | 60d | 45d |
| `USA_CPI_INDEX` | BLS | Monthly | 2026-04-03 | 60d | 45d |
| `USA_CORE_CPI_INDEX` | BLS | Monthly | 2026-04-03 | 60d | 45d |
| `AUS_UNEMPLOYMENT` | ABS | Monthly | 2026-04-03 | 60d | 45d |
| `CAN_CPI` | StatCan | Monthly | 2026-04-03 | 60d | 45d |
| `CAN_CPI_MEDIAN` | BoC | Monthly | 2026-04-03 | 60d | 45d |
| `CAN_EMPLOYMENT` | StatCan | Monthly | 2026-04-03 | 60d | 45d |
| `GBR_CPI_YOY` | ONS | Monthly | 2026-04-03 | 60d | 45d |
| `GBR_CPIH_YOY` | ONS | Monthly | 2026-04-03 | 60d | 45d |
| `AUS_PART_RATE` | ABS | Monthly | 2026-04-03 | 60d | 45d |
| `USA_AVG_HOURLY_EARN` | BLS | Monthly | 2026-04-03 | 60d | 45d |

</details>

<details><summary>History preservation</summary>


| File | Live rows | Sister rows | Union | Live range | Sister range |
|---|---|---|---|---|---|
| `market_data_comp_hist.csv` | 3,987 | 3,987 | 3,987 | 1950-01-06 → 2026-05-29 | 1950-01-06 → 2026-05-29 |
| `macro_economic_hist.csv` | 4,145 | 4,145 | 4,145 | 1946-12-27 → 2026-05-29 | 1946-12-27 → 2026-05-29 |
| `macro_market_hist.csv` | 1,379 | 1,379 | 1,379 | 2000-01-07 → 2026-06-05 | 2000-01-07 → 2026-06-05 |

</details>


_audit_writeback: 1 ticker(s) on active dead-list streak (threshold 14d); none flipped this run._
