## Daily audit — 2026-05-03 — **32 ISSUES** (1 fetch error, 27 stale series, 2 static-check failures, 2 history-preservation issues)

_Run: 2026-05-03 04:41 UTC_

Full report attached as `data_audit.txt` in today's commit.

<details><summary>Fetch errors</summary>


**other_warnings** (1):
- `[ECB] EU_I1 spread unavailable — EU_Cr1 will return n/a (corp-yield source unwired; see forward_plan.md §1 Known Data Gaps)`

</details>

<details><summary>Stale series</summary>


**EXPIRED** (15):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `CHN_M2` | FRED | Monthly | 2019-08-02 | 2466d | 45d |
| `CHN_PPI` | FRED | Monthly | 2022-12-02 | 1248d | 45d |
| `CHN_IND_PROD` | FRED | Monthly | 2023-11-03 | 912d | 45d |
| `JPN_IND_PROD` | e-Stat | Monthly | 2024-03-01 | 793d | 45d |
| `CHN_POLICY_RATE` | DB.nomics | Monthly | 2025-06-06 | 331d | 45d |
| `EA_DEPOSIT_RATE` | ECB | Daily | 2025-06-13 | 324d | 30d\* |
| `ISM_SVC_PMI` | DB.nomics | Monthly | 2025-09-05 | 240d | 60d\* |
| `DEU_IND_PROD` | DB.nomics | Monthly | 2025-12-05 | 149d | 45d |
| `FEDFUNDS` | FRED | Monthly | 2026-01-02 | 121d | 45d |
| `EA_HICP` | DB.nomics | Monthly | 2026-01-02 | 121d | 45d |
| `EU_ESI` | DB.nomics | Monthly | 2026-01-02 | 121d | 45d |
| `EU_IND_CONF` | DB.nomics | Monthly | 2026-01-02 | 121d | 45d |
| `EU_SVC_CONF` | DB.nomics | Monthly | 2026-01-02 | 121d | 45d |
| `ISM_MFG_PMI` | DB.nomics | Monthly | 2026-01-02 | 121d | 45d |
| `ISM_MFG_NEWORD` | DB.nomics | Monthly | 2026-01-02 | 121d | 45d |

**STALE** (12):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `ULCNFB` | FRED | Quarterly | 2025-10-03 | 212d | 180d\* |
| `CP` | FRED | Quarterly | 2025-10-03 | 212d | 180d\* |
| `EZ_EMPLOYMENT` | DB.nomics | Quarterly | 2025-10-03 | 212d | 180d\* |
| `GBR_UNEMPLOYMENT` | OECD | Monthly | 2025-12-05 | 149d | 75d\* |
| `DRTSCILM` | FRED | Quarterly | 2026-01-02 | 121d | 120d |
| `DRTSCIS` | FRED | Quarterly | 2026-01-02 | 121d | 120d |
| `DRTSCLCC` | FRED | Quarterly | 2026-01-02 | 121d | 120d |
| `STDSOTHCONS` | FRED | Quarterly | 2026-01-02 | 121d | 120d |
| `SUBLPDRCSN` | FRED | Quarterly | 2026-01-02 | 121d | 120d |
| `DEU_UNEMPLOYMENT` | OECD | Monthly | 2026-01-02 | 121d | 75d\* |
| `CMRMTSPL` | FRED | Monthly | 2026-02-06 | 86d | 45d |
| `PERMIT` | FRED | Monthly | 2026-03-06 | 58d | 45d |

</details>

<details><summary>Static-check failures</summary>


**missing_columns** (2):
- _get_col(...,'CHN_GOVT_10Y') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv
- _get_col(...,'DE_IFO') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv

</details>

<details><summary>History preservation</summary>


| File | Live rows | Sister rows | Union | Live range | Sister range |
|---|---|---|---|---|---|
| `market_data_comp_hist.csv` | 3,983 | 3,982 | 3,983 | 1950-01-06 → 2026-05-01 | 1950-01-06 → 2026-04-24 |
| `macro_economic_hist.csv` | 4,141 | 4,140 | 4,141 | 1946-12-27 → 2026-05-01 | 1946-12-27 → 2026-04-24 |
| `macro_market_hist.csv` | 1,374 | 1,374 | 1,374 | 2000-01-07 → 2026-05-01 | 2000-01-07 → 2026-05-01 |

**ALERTS** (2):
- market_data_comp_hist.csv: sister rows are a strict subset of live (3982 ⊂ 3983) — sister may have been rewritten incorrectly
- macro_economic_hist.csv: sister rows are a strict subset of live (4140 ⊂ 4141) — sister may have been rewritten incorrectly

</details>

