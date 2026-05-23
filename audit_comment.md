## Daily audit — 2026-05-23 — **59 ISSUES** (1 fetch error, 57 stale series, 1 static-check failure)

_Run: 2026-05-23 04:39 UTC_

Full report attached as `data_audit.txt` in today's commit.

<details><summary>Fetch errors</summary>


**other_warnings** (1):
- `[ECB] EU_I1 spread unavailable — EU_Cr1 will return n/a (corp-yield source unwired; see forward_plan.md §1 Known Data Gaps)`

</details>

<details><summary>Stale series</summary>


**EXPIRED** (16):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `CHN_M2` | FRED | Monthly | 2019-08-02 | 2486d | 45d |
| `CHN_PPI` | FRED | Monthly | 2022-12-02 | 1268d | 45d |
| `CHN_IND_PROD` | FRED | Monthly | 2023-11-03 | 932d | 45d |
| `JPN_IND_PROD` | e-Stat | Monthly | 2024-03-01 | 813d | 45d |
| `CHN_POLICY_RATE` | DB.nomics | Monthly | 2025-06-06 | 351d | 45d |
| `EA_DEPOSIT_RATE` | ECB | Daily | 2025-06-13 | 344d | 30d\* |
| `ISM_SVC_PMI` | DB.nomics | Monthly | 2025-09-05 | 260d | 60d\* |
| `DEU_IND_PROD` | DB.nomics | Monthly | 2025-12-05 | 169d | 45d |
| `FEDFUNDS` | FRED | Monthly | 2026-01-02 | 141d | 45d |
| `EA_HICP` | DB.nomics | Monthly | 2026-01-02 | 141d | 45d |
| `EU_ESI` | DB.nomics | Monthly | 2026-01-02 | 141d | 45d |
| `EU_IND_CONF` | DB.nomics | Monthly | 2026-01-02 | 141d | 45d |
| `EU_SVC_CONF` | DB.nomics | Monthly | 2026-01-02 | 141d | 45d |
| `ISM_MFG_PMI` | DB.nomics | Monthly | 2026-01-02 | 141d | 45d |
| `ISM_MFG_NEWORD` | DB.nomics | Monthly | 2026-01-02 | 141d | 45d |
| `CMRMTSPL` | FRED | Monthly | 2026-02-06 | 106d | 45d |

**STALE** (41):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `CP` | FRED | Quarterly | 2025-10-03 | 232d | 180d\* |
| `EZ_EMPLOYMENT` | DB.nomics | Quarterly | 2025-10-03 | 232d | 180d\* |
| `EZ_IND_PROD` | DB.nomics | Monthly | 2025-12-05 | 169d | 150d\* |
| `EZ_RETAIL_VOL` | DB.nomics | Monthly | 2025-12-05 | 169d | 150d\* |
| `DEU_UNEMPLOYMENT` | OECD | Monthly | 2026-01-02 | 141d | 75d\* |
| `GBR_UNEMPLOYMENT` | OECD | Monthly | 2026-02-06 | 106d | 75d\* |
| `EA19_RATE_3M` | OECD | Monthly | 2026-02-06 | 106d | 90d\* |
| `M2SL` | FRED | Monthly | 2026-03-06 | 78d | 75d\* |
| `UNRATE` | FRED | Monthly | 2026-03-06 | 78d | 75d\* |
| `PIORECRUSDM` | FRED | Monthly | 2026-03-06 | 78d | 75d\* |
| `CFNAI` | FRED | Monthly | 2026-03-06 | 78d | 75d\* |
| `FRA_UNEMPLOYMENT` | OECD | Monthly | 2026-03-06 | 78d | 75d\* |
| `DE_IFO` | ifo | Monthly | 2026-03-06 | 78d | 45d |
| `DE_IFO_SIT` | ifo | Monthly | 2026-03-06 | 78d | 45d |
| `DE_IFO_EXP` | ifo | Monthly | 2026-03-06 | 78d | 45d |
| `DE_IFO_BAL` | ifo | Monthly | 2026-03-06 | 78d | 45d |
| `DE_IFO_SIT_BAL` | ifo | Monthly | 2026-03-06 | 78d | 45d |
| `DE_IFO_EXP_BAL` | ifo | Monthly | 2026-03-06 | 78d | 45d |
| `DE_IFO_MFG` | ifo | Monthly | 2026-03-06 | 78d | 45d |
| `DE_IFO_MFG_SIT` | ifo | Monthly | 2026-03-06 | 78d | 45d |
| `DE_IFO_MFG_EXP` | ifo | Monthly | 2026-03-06 | 78d | 45d |
| `DE_IFO_SVC` | ifo | Monthly | 2026-03-06 | 78d | 45d |
| `DE_IFO_SVC_SIT` | ifo | Monthly | 2026-03-06 | 78d | 45d |
| `DE_IFO_SVC_EXP` | ifo | Monthly | 2026-03-06 | 78d | 45d |
| `DE_IFO_TRD` | ifo | Monthly | 2026-03-06 | 78d | 45d |
| `DE_IFO_TRD_SIT` | ifo | Monthly | 2026-03-06 | 78d | 45d |
| `DE_IFO_TRD_EXP` | ifo | Monthly | 2026-03-06 | 78d | 45d |
| `DE_IFO_WHS` | ifo | Monthly | 2026-03-06 | 78d | 45d |
| `DE_IFO_WHS_SIT` | ifo | Monthly | 2026-03-06 | 78d | 45d |
| `DE_IFO_WHS_EXP` | ifo | Monthly | 2026-03-06 | 78d | 45d |
| _… 11 more in `data_audit.txt`_ |  |  |  |  |  |

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

