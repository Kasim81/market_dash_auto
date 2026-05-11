## Daily audit — 2026-05-11 — **35 ISSUES** (1 fetch error, 31 stale series, 3 static-check failures)

_Run: 2026-05-11 05:00 UTC_

Full report attached as `data_audit.txt` in today's commit.

<details><summary>Fetch errors</summary>


**other_warnings** (1):
- `[ECB] EU_I1 spread unavailable — EU_Cr1 will return n/a (corp-yield source unwired; see forward_plan.md §1 Known Data Gaps)`

</details>

<details><summary>Stale series</summary>


**EXPIRED** (17):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `CHN_M2` | FRED | Monthly | 2019-08-02 | 2474d | 45d |
| `CHN_PPI` | FRED | Monthly | 2022-12-02 | 1256d | 45d |
| `CHN_IND_PROD` | FRED | Monthly | 2023-11-03 | 920d | 45d |
| `JPN_IND_PROD` | e-Stat | Monthly | 2024-03-01 | 801d | 45d |
| `CHN_POLICY_RATE` | DB.nomics | Monthly | 2025-06-06 | 339d | 45d |
| `EA_DEPOSIT_RATE` | ECB | Daily | 2025-06-13 | 332d | 30d\* |
| `ISM_SVC_PMI` | DB.nomics | Monthly | 2025-09-05 | 248d | 60d\* |
| `DEU_IND_PROD` | DB.nomics | Monthly | 2025-12-05 | 157d | 45d |
| `GBR_UNEMPLOYMENT` | OECD | Monthly | 2025-12-05 | 157d | 75d\* |
| `FEDFUNDS` | FRED | Monthly | 2026-01-02 | 129d | 45d |
| `EA_HICP` | DB.nomics | Monthly | 2026-01-02 | 129d | 45d |
| `EU_ESI` | DB.nomics | Monthly | 2026-01-02 | 129d | 45d |
| `EU_IND_CONF` | DB.nomics | Monthly | 2026-01-02 | 129d | 45d |
| `EU_SVC_CONF` | DB.nomics | Monthly | 2026-01-02 | 129d | 45d |
| `ISM_MFG_PMI` | DB.nomics | Monthly | 2026-01-02 | 129d | 45d |
| `ISM_MFG_NEWORD` | DB.nomics | Monthly | 2026-01-02 | 129d | 45d |
| `CMRMTSPL` | FRED | Monthly | 2026-02-06 | 94d | 45d |

**STALE** (14):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `CP` | FRED | Quarterly | 2025-10-03 | 220d | 180d\* |
| `EZ_EMPLOYMENT` | DB.nomics | Quarterly | 2025-10-03 | 220d | 180d\* |
| `CHN_IMPORTS` | FRED | Monthly | 2025-12-05 | 157d | 150d\* |
| `CHN_EXPORTS` | FRED | Monthly | 2025-12-05 | 157d | 150d\* |
| `EZ_IND_PROD` | DB.nomics | Monthly | 2025-12-05 | 157d | 150d\* |
| `EZ_RETAIL_VOL` | DB.nomics | Monthly | 2025-12-05 | 157d | 150d\* |
| `DEU_UNEMPLOYMENT` | OECD | Monthly | 2026-01-02 | 129d | 75d\* |
| `ITA_BTP_10Y` | FRED | Monthly | 2026-02-06 | 94d | 90d\* |
| `IND_GOVT_10Y` | FRED | Monthly | 2026-02-06 | 94d | 90d\* |
| `JPN_CON_CONF` | FRED | Monthly | 2026-02-06 | 94d | 90d\* |
| `CHN_CON_CONF` | FRED | Monthly | 2026-02-06 | 94d | 90d\* |
| `EA19_RATE_3M` | OECD | Monthly | 2026-02-06 | 94d | 90d\* |
| `PERMIT` | FRED | Monthly | 2026-03-06 | 66d | 45d |
| `JPN_POLICY_RATE` | BoJ | Daily | 2026-05-01 | 10d | 5d |

</details>

<details><summary>Static-check failures</summary>


**missing_columns** (3):
- _get_col(...,'CHN_GOVT_10Y') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv
- _get_col(...,'DE_IFO') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv
- _get_col(...,'GOLD_USD_PM') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv

</details>

<details><summary>History preservation</summary>


| File | Live rows | Sister rows | Union | Live range | Sister range |
|---|---|---|---|---|---|
| `market_data_comp_hist.csv` | 3,984 | 3,984 | 3,984 | 1950-01-06 → 2026-05-08 | 1950-01-06 → 2026-05-08 |
| `macro_economic_hist.csv` | 4,142 | 4,142 | 4,142 | 1946-12-27 → 2026-05-08 | 1946-12-27 → 2026-05-08 |
| `macro_market_hist.csv` | 1,375 | 1,375 | 1,375 | 2000-01-07 → 2026-05-08 | 2000-01-07 → 2026-05-08 |

</details>

