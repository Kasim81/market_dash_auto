## Daily audit — 2026-04-30 — **41 ISSUES** (1 fetch error, 39 stale series, 1 static-check failure)

_Run: 2026-04-30 09:14 UTC_

Full report attached as `data_audit.txt` in today's commit.

<details><summary>Fetch errors</summary>


**other_warnings** (1):
- `[ECB] EU_I1 spread unavailable — EU_Cr1 will return n/a (corp-yield source unwired; see forward_plan.md §1 Known Data Gaps)`

</details>

<details><summary>Stale series</summary>


**EXPIRED** (19):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `JPN_POLICY_RATE` | FRED | Monthly | 2008-12-05 | 6355d | 45d |
| `CHN_POLICY_RATE` | FRED | Monthly | 2015-11-06 | 3828d | 45d |
| `GBR_BANK_RATE` | FRED | Monthly | 2016-08-05 | 3555d | 45d |
| `CHN_M2` | FRED | Monthly | 2019-08-02 | 2463d | 45d |
| `CHN_PPI` | FRED | Monthly | 2022-12-02 | 1245d | 45d |
| `EA_HICP` | FRED | Monthly | 2023-01-06 | 1210d | 45d |
| `CHN_IND_PROD` | FRED | Monthly | 2023-11-03 | 909d | 45d |
| `DEU_IND_PROD` | FRED | Monthly | 2024-03-01 | 790d | 45d |
| `JPN_IND_PROD` | FRED | Monthly | 2024-03-01 | 790d | 45d |
| `EA_DEPOSIT_RATE` | FRED | Daily | 2025-06-13 | 321d | 5d |
| `ISM_SVC_PMI` | DB.nomics | Monthly | 2025-09-05 | 237d | 60d\* |
| `FEDFUNDS` | FRED | Monthly | 2026-01-02 | 118d | 45d |
| `CMRMTSPL` | FRED | Monthly | 2026-01-02 | 118d | 45d |
| `EU_ESI` | DB.nomics | Monthly | 2026-01-02 | 118d | 45d |
| `EU_IND_CONF` | DB.nomics | Monthly | 2026-01-02 | 118d | 45d |
| `EU_SVC_CONF` | DB.nomics | Monthly | 2026-01-02 | 118d | 45d |
| `ISM_MFG_PMI` | DB.nomics | Monthly | 2026-01-02 | 118d | 45d |
| `ISM_MFG_NEWORD` | DB.nomics | Monthly | 2026-01-02 | 118d | 45d |
| `BAMLC0A0CM` | FRED | Daily | 2026-04-17 | 13d | 5d |

**STALE** (20):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `ULCNFB` | FRED | Quarterly | 2025-10-03 | 209d | 180d\* |
| `CP` | FRED | Quarterly | 2025-10-03 | 209d | 180d\* |
| `EZ_EMPLOYMENT` | DB.nomics | Quarterly | 2025-10-03 | 209d | 180d\* |
| `GBR_UNEMPLOYMENT` | OECD | Monthly | 2025-12-05 | 146d | 75d\* |
| `DEU_UNEMPLOYMENT` | OECD | Monthly | 2026-01-02 | 118d | 75d\* |
| `FRA_UNEMPLOYMENT` | OECD | Monthly | 2026-01-02 | 118d | 75d\* |
| `PERMIT` | FRED | Monthly | 2026-03-06 | 55d | 45d |
| `T10Y2Y` | FRED | Daily | 2026-04-24 | 6d | 5d |
| `T10Y3M` | FRED | Daily | 2026-04-24 | 6d | 5d |
| `T5YIE` | FRED | Daily | 2026-04-24 | 6d | 5d |
| `T10YIE` | FRED | Daily | 2026-04-24 | 6d | 5d |
| `T5YIFR` | FRED | Daily | 2026-04-24 | 6d | 5d |
| `DGS2` | FRED | Daily | 2026-04-24 | 6d | 5d |
| `DGS10` | FRED | Daily | 2026-04-24 | 6d | 5d |
| `DFII10` | FRED | Daily | 2026-04-24 | 6d | 5d |
| `DFII5` | FRED | Daily | 2026-04-24 | 6d | 5d |
| `BAMLH0A0HYM2` | FRED | Daily | 2026-04-24 | 6d | 5d |
| `BAMLC0A0CMEY` | FRED | Daily | 2026-04-24 | 6d | 5d |
| `BAMLCC0A0CMTRIV` | FRED | Daily | 2026-04-24 | 6d | 5d |
| `BAMLHE00EHYIOAS` | FRED | Daily | 2026-04-24 | 6d | 5d |

</details>

<details><summary>Static-check failures</summary>


**missing_columns** (1):
- _get_col(...,'CHN_GOVT_10Y') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv

</details>

