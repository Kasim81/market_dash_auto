## Daily audit — 2026-05-26 — **33 ISSUES** (1 fetch error, 31 stale series, 1 static-check failure)

_Run: 2026-05-26 04:58 UTC_

Full report attached as `data_audit.txt` in today's commit.

<details><summary>Fetch errors</summary>


**other_warnings** (1):
- `[ECB] EU_I1 spread unavailable — EU_Cr1 will return n/a (corp-yield source unwired; see forward_plan.md §1 Known Data Gaps)`

</details>

<details><summary>Stale series</summary>


**EXPIRED** (17):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `CHN_M2` | FRED | Monthly | 2019-08-02 | 2489d | 45d |
| `CHN_PPI` | FRED | Monthly | 2022-12-02 | 1271d | 45d |
| `CHN_IND_PROD` | FRED | Monthly | 2023-11-03 | 935d | 45d |
| `JPN_IND_PROD` | e-Stat | Monthly | 2024-03-01 | 816d | 45d |
| `CHN_POLICY_RATE` | DB.nomics | Monthly | 2025-06-06 | 354d | 45d |
| `EA_DEPOSIT_RATE` | ECB | Daily | 2025-06-13 | 347d | 30d\* |
| `ISM_SVC_PMI` | DB.nomics | Monthly | 2025-09-05 | 263d | 60d\* |
| `DEU_IND_PROD` | DB.nomics | Monthly | 2025-12-05 | 172d | 45d |
| `FEDFUNDS` | FRED | Monthly | 2026-01-02 | 144d | 45d |
| `EA_HICP` | DB.nomics | Monthly | 2026-01-02 | 144d | 45d |
| `EU_ESI` | DB.nomics | Monthly | 2026-01-02 | 144d | 45d |
| `EU_IND_CONF` | DB.nomics | Monthly | 2026-01-02 | 144d | 45d |
| `EU_SVC_CONF` | DB.nomics | Monthly | 2026-01-02 | 144d | 45d |
| `ISM_MFG_PMI` | DB.nomics | Monthly | 2026-01-02 | 144d | 45d |
| `ISM_MFG_NEWORD` | DB.nomics | Monthly | 2026-01-02 | 144d | 45d |
| `CMRMTSPL` | FRED | Monthly | 2026-02-06 | 109d | 45d |
| `BAMLC0A0CM` | FRED | Daily | 2026-05-15 | 11d | 5d |

**STALE** (14):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `CP` | FRED | Quarterly | 2025-10-03 | 235d | 180d\* |
| `EZ_EMPLOYMENT` | DB.nomics | Quarterly | 2025-10-03 | 235d | 180d\* |
| `EZ_IND_PROD` | DB.nomics | Monthly | 2025-12-05 | 172d | 150d\* |
| `EZ_RETAIL_VOL` | DB.nomics | Monthly | 2025-12-05 | 172d | 150d\* |
| `DEU_UNEMPLOYMENT` | OECD | Monthly | 2026-01-02 | 144d | 75d\* |
| `GBR_UNEMPLOYMENT` | OECD | Monthly | 2026-02-06 | 109d | 75d\* |
| `EA19_RATE_3M` | OECD | Monthly | 2026-02-06 | 109d | 90d\* |
| `M2SL` | FRED | Monthly | 2026-03-06 | 81d | 75d\* |
| `UNRATE` | FRED | Monthly | 2026-03-06 | 81d | 75d\* |
| `PIORECRUSDM` | FRED | Monthly | 2026-03-06 | 81d | 75d\* |
| `CFNAI` | FRED | Monthly | 2026-03-06 | 81d | 75d\* |
| `FRA_UNEMPLOYMENT` | OECD | Monthly | 2026-03-06 | 81d | 75d\* |
| `PERMIT` | FRED | Monthly | 2026-04-03 | 53d | 45d |
| `BACTUAMFRBDAL` | FRED | Monthly | 2026-04-03 | 53d | 45d |

</details>

<details><summary>Static-check failures</summary>


**missing_columns** (1):
- _get_col(...,'CHN_GOVT_10Y') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv

</details>

<details><summary>History preservation</summary>


| File | Live rows | Sister rows | Union | Live range | Sister range |
|---|---|---|---|---|---|
| `market_data_comp_hist.csv` | 3,986 | 3,986 | 3,986 | 1950-01-06 → 2026-05-22 | 1950-01-06 → 2026-05-22 |
| `macro_economic_hist.csv` | 4,144 | 4,144 | 4,144 | 1946-12-27 → 2026-05-22 | 1946-12-27 → 2026-05-22 |
| `macro_market_hist.csv` | 1,377 | 1,377 | 1,377 | 2000-01-07 → 2026-05-22 | 2000-01-07 → 2026-05-22 |

</details>

