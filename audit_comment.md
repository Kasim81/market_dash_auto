## Daily audit — 2026-04-28 — **100 ISSUES** (24 fetch errors, 75 stale series, 1 static-check failure)

_Run: 2026-04-28 13:39 UTC_

Full report attached as `data_audit.txt` in today's commit.

<details><summary>Fetch errors</summary>


**yfinance_dead** (22):
- `ISFA.L`
- `SENSEXBEES.NS`
- `^CNXSC`
- `^RMCCG`
- `^RMCCV`
- `^SP500-253020`
- `^SP500-351030`
- `^SP500-601010`
- `^SP500G`
- `^SP500V`
- `^SX3P`
- `^SX4P`
- `^SX6P`
- `^SX7E`
- `^SX8P`
- `^SXDP`
- `^SXEP`
- `^SXKP`
- `^SXNP`
- `^TOPX`
- `^TSXV`
- `^TX60`

**other_warnings** (2):
- `[ECB] EU_I1 spread unavailable — EU_Cr1 will return n/a (corp-yield source unwired; see forward_plan.md §1 Known Data Gaps)`
- `[ECB] AAA euro govt yield: 5530 obs`

</details>

<details><summary>Stale series</summary>


**EXPIRED** (29):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `JPN_POLICY_RATE` | FRED | Monthly | 2008-12-05 | 6353d | 45d |
| `CHN_POLICY_RATE` | FRED | Monthly | 2015-11-06 | 3826d | 45d |
| `GBR_BANK_RATE` | FRED | Monthly | 2016-08-05 | 3553d | 45d |
| `CHN_M2` | FRED | Monthly | 2019-08-02 | 2461d | 45d |
| `EA_HICP` | FRED | Monthly | 2023-01-06 | 1208d | 45d |
| `CHN_IND_PROD` | FRED | Monthly | 2023-11-03 | 907d | 45d |
| `CSCICP03USM665S` | FRED | Monthly | 2024-01-05 | 844d | 45d |
| `BSCICP03USM665S` | FRED | Monthly | 2024-01-05 | 844d | 45d |
| `CONSUMER_CONF` | FRED | Monthly | 2024-01-05 | 844d | 45d |
| `DEU_IND_PROD` | FRED | Monthly | 2024-03-01 | 788d | 45d |
| `JPN_IND_PROD` | FRED | Monthly | 2024-03-01 | 788d | 45d |
| `EA_DEPOSIT_RATE` | FRED | Daily | 2025-06-13 | 319d | 5d |
| `ISM_SVC_PMI` | DB.nomics | Monthly | 2025-09-05 | 235d | 45d |
| `CHN_IMPORTS` | FRED | Monthly | 2025-12-05 | 144d | 45d |
| `CHN_EXPORTS` | FRED | Monthly | 2025-12-05 | 144d | 45d |
| `GBR_UNEMPLOYMENT` | OECD | Monthly | 2025-12-05 | 144d | 45d |
| `EZ_IND_PROD` | DB.nomics | Monthly | 2025-12-05 | 144d | 45d |
| `EZ_RETAIL_VOL` | DB.nomics | Monthly | 2025-12-05 | 144d | 45d |
| `PERMIT` | FRED | Monthly | 2026-01-02 | 116d | 45d |
| `FEDFUNDS` | FRED | Monthly | 2026-01-02 | 116d | 45d |
| `CMRMTSPL` | FRED | Monthly | 2026-01-02 | 116d | 45d |
| `FRA_UNEMPLOYMENT` | OECD | Monthly | 2026-01-02 | 116d | 45d |
| `DEU_UNEMPLOYMENT` | OECD | Monthly | 2026-01-02 | 116d | 45d |
| `EU_ESI` | DB.nomics | Monthly | 2026-01-02 | 116d | 45d |
| `EU_IND_CONF` | DB.nomics | Monthly | 2026-01-02 | 116d | 45d |
| `EU_SVC_CONF` | DB.nomics | Monthly | 2026-01-02 | 116d | 45d |
| `ISM_MFG_PMI` | DB.nomics | Monthly | 2026-01-02 | 116d | 45d |
| `ISM_MFG_NEWORD` | DB.nomics | Monthly | 2026-01-02 | 116d | 45d |
| `BAMLC0A0CM` | FRED | Daily | 2026-04-17 | 11d | 5d |

**STALE** (46):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `ULCNFB` | FRED | Quarterly | 2025-10-03 | 207d | 120d |
| `CP` | FRED | Quarterly | 2025-10-03 | 207d | 120d |
| `EZ_EMPLOYMENT` | DB.nomics | Quarterly | 2025-10-03 | 207d | 120d |
| `M2SL` | FRED | Monthly | 2026-02-06 | 81d | 45d |
| `JTSJOL` | FRED | Monthly | 2026-02-06 | 81d | 45d |
| `PCEPILFE` | FRED | Monthly | 2026-02-06 | 81d | 45d |
| `NEWORDER` | FRED | Monthly | 2026-02-06 | 81d | 45d |
| `W875RX1` | FRED | Monthly | 2026-02-06 | 81d | 45d |
| `PCEC96` | FRED | Monthly | 2026-02-06 | 81d | 45d |
| `ITA_BTP_10Y` | FRED | Monthly | 2026-02-06 | 81d | 45d |
| `IND_GOVT_10Y` | FRED | Monthly | 2026-02-06 | 81d | 45d |
| `JPN_CON_CONF` | FRED | Monthly | 2026-02-06 | 81d | 45d |
| `CHN_CON_CONF` | FRED | Monthly | 2026-02-06 | 81d | 45d |
| `EA19_RATE_3M` | OECD | Monthly | 2026-02-06 | 81d | 45d |
| `PAYEMS` | FRED | Monthly | 2026-03-06 | 53d | 45d |
| `UNRATE` | FRED | Monthly | 2026-03-06 | 53d | 45d |
| `UNEMPLOY` | FRED | Monthly | 2026-03-06 | 53d | 45d |
| `INDPRO` | FRED | Monthly | 2026-03-06 | 53d | 45d |
| `RSXFS` | FRED | Monthly | 2026-03-06 | 53d | 45d |
| `CPIAUCSL` | FRED | Monthly | 2026-03-06 | 53d | 45d |
| `CPILFESL` | FRED | Monthly | 2026-03-06 | 53d | 45d |
| `PPIACO` | FRED | Monthly | 2026-03-06 | 53d | 45d |
| `MICH` | FRED | Monthly | 2026-03-06 | 53d | 45d |
| `UMCSENT` | FRED | Monthly | 2026-03-06 | 53d | 45d |
| `PIORECRUSDM` | FRED | Monthly | 2026-03-06 | 53d | 45d |
| `AWHMAN` | FRED | Monthly | 2026-03-06 | 53d | 45d |
| `TCU` | FRED | Monthly | 2026-03-06 | 53d | 45d |
| `CFNAI` | FRED | Monthly | 2026-03-06 | 53d | 45d |
| `UEMPMEAN` | FRED | Monthly | 2026-03-06 | 53d | 45d |
| `GBR_GILT_10Y` | FRED | Monthly | 2026-03-06 | 53d | 45d |
| _… 16 more in `data_audit.txt`_ |  |  |  |  |  |

</details>

<details><summary>Static-check failures</summary>


**missing_columns** (1):
- _get_col(...,'CHN_GOVT_10Y') referenced in compute_macro_market.py but column absent from macro_economic_hist.csv

</details>

