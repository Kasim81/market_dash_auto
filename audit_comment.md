## Daily audit — 2026-05-28 — **44 ISSUES** (2 fetch errors, 42 stale series)

_Run: 2026-05-28 05:04 UTC_

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
| `CHN_M2` | FRED | Monthly | 2019-08-02 | 2491d | 45d |
| `CHN_PPI` | FRED | Monthly | 2022-12-02 | 1273d | 45d |
| `CHN_IND_PROD` | FRED | Monthly | 2023-11-03 | 937d | 45d |
| `JPN_IND_PROD` | e-Stat | Monthly | 2024-03-01 | 818d | 45d |
| `CHN_POLICY_RATE` | DB.nomics | Monthly | 2025-06-06 | 356d | 45d |
| `EA_DEPOSIT_RATE` | ECB | Daily | 2025-06-13 | 349d | 30d\* |
| `ISM_SVC_PMI` | DB.nomics | Monthly | 2025-09-05 | 265d | 60d\* |
| `DEU_IND_PROD` | DB.nomics | Monthly | 2025-12-05 | 174d | 45d |
| `FEDFUNDS` | FRED | Monthly | 2026-01-02 | 146d | 45d |
| `EA_HICP` | DB.nomics | Monthly | 2026-01-02 | 146d | 45d |
| `EU_ESI` | DB.nomics | Monthly | 2026-01-02 | 146d | 45d |
| `EU_IND_CONF` | DB.nomics | Monthly | 2026-01-02 | 146d | 45d |
| `EU_SVC_CONF` | DB.nomics | Monthly | 2026-01-02 | 146d | 45d |
| `ISM_MFG_PMI` | DB.nomics | Monthly | 2026-01-02 | 146d | 45d |
| `ISM_MFG_NEWORD` | DB.nomics | Monthly | 2026-01-02 | 146d | 45d |
| `CMRMTSPL` | FRED | Monthly | 2026-02-06 | 111d | 45d |

**STALE** (26):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `CP` | FRED | Quarterly | 2025-10-03 | 237d | 180d\* |
| `EZ_EMPLOYMENT` | DB.nomics | Quarterly | 2025-10-03 | 237d | 180d\* |
| `EZ_IND_PROD` | DB.nomics | Monthly | 2025-12-05 | 174d | 150d\* |
| `EZ_RETAIL_VOL` | DB.nomics | Monthly | 2025-12-05 | 174d | 150d\* |
| `DEU_UNEMPLOYMENT` | OECD | Monthly | 2026-01-02 | 146d | 75d\* |
| `GBR_UNEMPLOYMENT` | OECD | Monthly | 2026-02-06 | 111d | 75d\* |
| `EA19_RATE_3M` | OECD | Monthly | 2026-02-06 | 111d | 90d\* |
| `UNRATE` | FRED | Monthly | 2026-03-06 | 83d | 75d\* |
| `PIORECRUSDM` | FRED | Monthly | 2026-03-06 | 83d | 75d\* |
| `FRA_UNEMPLOYMENT` | OECD | Monthly | 2026-03-06 | 83d | 75d\* |
| `PERMIT` | FRED | Monthly | 2026-04-03 | 55d | 45d |
| `T10Y2Y` | FRED | Daily | 2026-05-22 | 6d | 5d |
| `T10Y3M` | FRED | Daily | 2026-05-22 | 6d | 5d |
| `T5YIE` | FRED | Daily | 2026-05-22 | 6d | 5d |
| `T10YIE` | FRED | Daily | 2026-05-22 | 6d | 5d |
| `T5YIFR` | FRED | Daily | 2026-05-22 | 6d | 5d |
| `DGS2` | FRED | Daily | 2026-05-22 | 6d | 5d |
| `DGS10` | FRED | Daily | 2026-05-22 | 6d | 5d |
| `DFII10` | FRED | Daily | 2026-05-22 | 6d | 5d |
| `DFII5` | FRED | Daily | 2026-05-22 | 6d | 5d |
| `BAMLH0A0HYM2` | FRED | Daily | 2026-05-22 | 6d | 5d |
| `BAMLC0A0CM` | FRED | Daily | 2026-05-22 | 6d | 5d |
| `BAMLC0A0CMEY` | FRED | Daily | 2026-05-22 | 6d | 5d |
| `BAMLCC0A0CMTRIV` | FRED | Daily | 2026-05-22 | 6d | 5d |
| `BAMLHE00EHYIOAS` | FRED | Daily | 2026-05-22 | 6d | 5d |
| `JPN_POLICY_RATE` | BoJ | Daily | 2026-05-22 | 6d | 5d |

</details>

<details><summary>History preservation</summary>


| File | Live rows | Sister rows | Union | Live range | Sister range |
|---|---|---|---|---|---|
| `market_data_comp_hist.csv` | 3,986 | 3,986 | 3,986 | 1950-01-06 → 2026-05-22 | 1950-01-06 → 2026-05-22 |
| `macro_economic_hist.csv` | 4,144 | 4,144 | 4,144 | 1946-12-27 → 2026-05-22 | 1946-12-27 → 2026-05-22 |
| `macro_market_hist.csv` | 1,378 | 1,378 | 1,378 | 2000-01-07 → 2026-05-29 | 2000-01-07 → 2026-05-29 |

</details>


_audit_writeback: 1 ticker(s) on active dead-list streak (threshold 14d); none flipped this run._
