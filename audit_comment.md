## Daily audit — 2026-05-14 — **49 ISSUES** (1 fetch error, 45 stale series, 3 static-check failures)

_Run: 2026-05-14 04:44 UTC_

Full report attached as `data_audit.txt` in today's commit.

<details><summary>Fetch errors</summary>


**other_warnings** (1):
- `[ECB] EU_I1 spread unavailable — EU_Cr1 will return n/a (corp-yield source unwired; see forward_plan.md §1 Known Data Gaps)`

</details>

<details><summary>Stale series</summary>


**EXPIRED** (18):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `CHN_M2` | FRED | Monthly | 2019-08-02 | 2477d | 45d |
| `CHN_PPI` | FRED | Monthly | 2022-12-02 | 1259d | 45d |
| `CHN_IND_PROD` | FRED | Monthly | 2023-11-03 | 923d | 45d |
| `JPN_IND_PROD` | e-Stat | Monthly | 2024-03-01 | 804d | 45d |
| `CHN_POLICY_RATE` | DB.nomics | Monthly | 2025-06-06 | 342d | 45d |
| `EA_DEPOSIT_RATE` | ECB | Daily | 2025-06-13 | 335d | 30d\* |
| `ISM_SVC_PMI` | DB.nomics | Monthly | 2025-09-05 | 251d | 60d\* |
| `DEU_IND_PROD` | DB.nomics | Monthly | 2025-12-05 | 160d | 45d |
| `GBR_UNEMPLOYMENT` | OECD | Monthly | 2025-12-05 | 160d | 75d\* |
| `FEDFUNDS` | FRED | Monthly | 2026-01-02 | 132d | 45d |
| `EA_HICP` | DB.nomics | Monthly | 2026-01-02 | 132d | 45d |
| `EU_ESI` | DB.nomics | Monthly | 2026-01-02 | 132d | 45d |
| `EU_IND_CONF` | DB.nomics | Monthly | 2026-01-02 | 132d | 45d |
| `EU_SVC_CONF` | DB.nomics | Monthly | 2026-01-02 | 132d | 45d |
| `ISM_MFG_PMI` | DB.nomics | Monthly | 2026-01-02 | 132d | 45d |
| `ISM_MFG_NEWORD` | DB.nomics | Monthly | 2026-01-02 | 132d | 45d |
| `CMRMTSPL` | FRED | Monthly | 2026-02-06 | 97d | 45d |
| `JPN_POLICY_RATE` | BoJ | Daily | 2026-05-01 | 13d | 5d |

**STALE** (27):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `CP` | FRED | Quarterly | 2025-10-03 | 223d | 180d\* |
| `EZ_EMPLOYMENT` | DB.nomics | Quarterly | 2025-10-03 | 223d | 180d\* |
| `CHN_IMPORTS` | FRED | Monthly | 2025-12-05 | 160d | 150d\* |
| `CHN_EXPORTS` | FRED | Monthly | 2025-12-05 | 160d | 150d\* |
| `EZ_IND_PROD` | DB.nomics | Monthly | 2025-12-05 | 160d | 150d\* |
| `EZ_RETAIL_VOL` | DB.nomics | Monthly | 2025-12-05 | 160d | 150d\* |
| `DEU_UNEMPLOYMENT` | OECD | Monthly | 2026-01-02 | 132d | 75d\* |
| `ITA_BTP_10Y` | FRED | Monthly | 2026-02-06 | 97d | 90d\* |
| `IND_GOVT_10Y` | FRED | Monthly | 2026-02-06 | 97d | 90d\* |
| `JPN_CON_CONF` | FRED | Monthly | 2026-02-06 | 97d | 90d\* |
| `CHN_CON_CONF` | FRED | Monthly | 2026-02-06 | 97d | 90d\* |
| `EA19_RATE_3M` | OECD | Monthly | 2026-02-06 | 97d | 90d\* |
| `PERMIT` | FRED | Monthly | 2026-03-06 | 69d | 45d |
| `T10Y2Y` | FRED | Daily | 2026-05-08 | 6d | 5d |
| `T10Y3M` | FRED | Daily | 2026-05-08 | 6d | 5d |
| `T5YIE` | FRED | Daily | 2026-05-08 | 6d | 5d |
| `T10YIE` | FRED | Daily | 2026-05-08 | 6d | 5d |
| `T5YIFR` | FRED | Daily | 2026-05-08 | 6d | 5d |
| `DGS2` | FRED | Daily | 2026-05-08 | 6d | 5d |
| `DGS10` | FRED | Daily | 2026-05-08 | 6d | 5d |
| `DFII10` | FRED | Daily | 2026-05-08 | 6d | 5d |
| `DFII5` | FRED | Daily | 2026-05-08 | 6d | 5d |
| `BAMLH0A0HYM2` | FRED | Daily | 2026-05-08 | 6d | 5d |
| `BAMLC0A0CM` | FRED | Daily | 2026-05-08 | 6d | 5d |
| `BAMLC0A0CMEY` | FRED | Daily | 2026-05-08 | 6d | 5d |
| `BAMLCC0A0CMTRIV` | FRED | Daily | 2026-05-08 | 6d | 5d |
| `BAMLHE00EHYIOAS` | FRED | Daily | 2026-05-08 | 6d | 5d |

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
| `macro_market_hist.csv` | 1,376 | 1,376 | 1,376 | 2000-01-07 → 2026-05-15 | 2000-01-07 → 2026-05-15 |

</details>

