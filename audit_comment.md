## Daily audit — 2026-05-10 — **33 ISSUES** (1 fetch error, 23 stale series, 9 static-check failures)

_Run: 2026-05-10 05:41 UTC_

Full report attached as `data_audit.txt` in today's commit.

<details><summary>Fetch errors</summary>


**other_warnings** (1):
- `[ECB] EU_I1 spread unavailable — EU_Cr1 will return n/a (corp-yield source unwired; see forward_plan.md §1 Known Data Gaps)`

</details>

<details><summary>Stale series</summary>


**EXPIRED** (11):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `CHN_M2` | FRED | Monthly | 2019-08-02 | 2473d | 45d |
| `CHN_PPI` | FRED | Monthly | 2022-12-02 | 1255d | 45d |
| `CHN_IND_PROD` | FRED | Monthly | 2023-11-03 | 919d | 45d |
| `JPN_IND_PROD` | e-Stat | Monthly | 2024-03-01 | 800d | 45d |
| `CHN_POLICY_RATE` | DB.nomics | Monthly | 2025-06-06 | 338d | 45d |
| `EA_DEPOSIT_RATE` | ECB | Daily | 2025-06-13 | 331d | 30d\* |
| `DEU_IND_PROD` | DB.nomics | Monthly | 2025-12-05 | 156d | 45d |
| `GBR_UNEMPLOYMENT` | OECD | Monthly | 2025-12-05 | 156d | 75d\* |
| `FEDFUNDS` | FRED | Monthly | 2026-01-02 | 128d | 45d |
| `EA_HICP` | DB.nomics | Monthly | 2026-01-02 | 128d | 45d |
| `CMRMTSPL` | FRED | Monthly | 2026-02-06 | 93d | 45d |

**STALE** (12):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `CP` | FRED | Quarterly | 2025-10-03 | 219d | 180d\* |
| `EZ_EMPLOYMENT` | DB.nomics | Quarterly | 2025-10-03 | 219d | 180d\* |
| `CHN_IMPORTS` | FRED | Monthly | 2025-12-05 | 156d | 150d\* |
| `CHN_EXPORTS` | FRED | Monthly | 2025-12-05 | 156d | 150d\* |
| `DEU_UNEMPLOYMENT` | OECD | Monthly | 2026-01-02 | 128d | 75d\* |
| `ITA_BTP_10Y` | FRED | Monthly | 2026-02-06 | 93d | 90d\* |
| `IND_GOVT_10Y` | FRED | Monthly | 2026-02-06 | 93d | 90d\* |
| `JPN_CON_CONF` | FRED | Monthly | 2026-02-06 | 93d | 90d\* |
| `CHN_CON_CONF` | FRED | Monthly | 2026-02-06 | 93d | 90d\* |
| `EA19_RATE_3M` | OECD | Monthly | 2026-02-06 | 93d | 90d\* |
| `PERMIT` | FRED | Monthly | 2026-03-06 | 65d | 45d |
| `JPN_POLICY_RATE` | BoJ | Daily | 2026-05-01 | 9d | 5d |

</details>

<details><summary>Static-check failures</summary>


**missing_columns** (9):
- _get_col(...,'CHN_GOVT_10Y') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv
- _get_col(...,'DE_IFO') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv
- _get_col(...,'EU_ESI') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv
- _get_col(...,'EU_IND_CONF') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv
- _get_col(...,'EU_SVC_CONF') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv
- _get_col(...,'GOLD_USD_PM') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv
- _get_col(...,'ISM_MFG_NEWORD') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv
- _get_col(...,'ISM_MFG_PMI') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv
- _get_col(...,'ISM_SVC_PMI') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv

</details>

<details><summary>History preservation</summary>


| File | Live rows | Sister rows | Union | Live range | Sister range |
|---|---|---|---|---|---|
| `market_data_comp_hist.csv` | 3,984 | 3,984 | 3,984 | 1950-01-06 → 2026-05-08 | 1950-01-06 → 2026-05-08 |
| `macro_economic_hist.csv` | 4,142 | 4,142 | 4,142 | 1946-12-27 → 2026-05-08 | 1946-12-27 → 2026-05-08 |
| `macro_market_hist.csv` | 1,375 | 1,375 | 1,375 | 2000-01-07 → 2026-05-08 | 2000-01-07 → 2026-05-08 |

</details>

