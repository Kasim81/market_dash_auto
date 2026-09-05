## Daily audit — 2026-09-05 — **81 ISSUES** (3 fetch errors, 75 stale series, 3 static-check failures)

_Run: 2026-09-05 05:28 UTC_

Full report attached as `data_audit.txt` in today's commit.

<details><summary>Fetch errors</summary>


**fallback_demotions** (2):
- `[FALLBACK] (snapshot) ITA_UNEMPLOYMENT: declared primary ISTAT/151_874/M.IT.UNEM_R.N.1.Y15-74. (tier 0) demoted — stale 127d (last obs 2026-05-01, group freshest 2026-07-28, gate 2x31d); serving OECD/UNEMPLOYMENT (tier 1, Monthly, last 2026-07-28)`
- `[FALLBACK] ITA_UNEMPLOYMENT: declared primary ISTAT/151_874/M.IT.UNEM_R.N.1.Y15-74. (tier 0) demoted — stale 127d (last obs 2026-05-01, group freshest 2026-07-31, gate 2x31d); serving OECD/UNEMPLOYMENT (tier 1, Monthly, last 2026-07-31)`

**other_warnings** (1):
- `[ECB] EU_I1 spread unavailable — EU_Cr1 will return n/a (corp-yield source unwired; see forward_plan.md §1 Known Data Gaps)`

</details>

<details><summary>Stale series</summary>


**EXPIRED** (9):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `CHN_PPI` | FRED | Monthly | 2022-12-01 | 1374d | 45d |
| `CHN_IND_PROD` | FRED | Monthly | 2023-11-01 | 1039d | 45d |
| `CHN_POLICY_RATE` | DB.nomics | Monthly | 2025-06-30 | 432d | 120d\* |
| `GBR_RATE_3M` | OECD | Monthly | 2026-02-28 | 189d | 90d\* |
| `JPN_IND_PROD` | e-Stat | Monthly | 2026-03-01 | 188d | 60d\* |
| `ITA_GDP_GROWTH` | ISTAT | Quarterly | 2026-03-01 | 188d | 90d\* |
| `CMRMTSPL` | FRED | Monthly | 2026-06-01 | 96d | 45d |
| `FRA_LOAN_RATE_HOUSE` | Banque de France | Monthly | 2026-06-01 | 96d | 45d |
| `FRA_LOAN_RATE_NFC` | Banque de France | Monthly | 2026-06-01 | 96d | 45d |

**STALE** (66):

| Series | Source | Frequency | Last obs | Age | Tolerance |
|---|---|---|---|---|---|
| `USA_CPI_YOY_ANNUAL` | World Bank | Annual | 2024-12-31 | 613d | 540d |
| `CHE_IND_PROD` | IMF SDMX | Quarterly | 2026-01-01 | 247d | 210d\* |
| `DEU_GDP_INDEX` | IMF SDMX | Quarterly | 2026-01-01 | 247d | 210d\* |
| `ITA_GDP_INDEX` | IMF SDMX | Quarterly | 2026-01-01 | 247d | 210d\* |
| `CHE_GDP_INDEX` | IMF SDMX | Quarterly | 2026-01-01 | 247d | 210d\* |
| `NLD_GDP_INDEX` | IMF SDMX | Quarterly | 2026-01-01 | 247d | 210d\* |
| `JP_TANKAN1` | BoJ | Quarterly | 2026-02-01 | 216d | 180d\* |
| `CHN_M2` | DB.nomics | Monthly | 2026-02-28 | 189d | 120d\* |
| `DEU_IND_PROD` | IMF SDMX | Monthly | 2026-03-01 | 188d | 150d\* |
| `EZ_EMPLOYMENT` | ECB | Quarterly | 2026-03-01 | 188d | 180d\* |
| `NLD_IND_PROD` | IMF SDMX | Monthly | 2026-03-01 | 188d | 150d\* |
| `USA_SP500_DIV_SHILLER` | Shiller | Monthly | 2026-03-31 | 158d | 90d\* |
| `USA_SP500_EPS_SHILLER` | Shiller | Monthly | 2026-03-31 | 158d | 90d\* |
| `USA_SP500_PE` | Shiller | Monthly | 2026-03-31 | 158d | 90d\* |
| `JPN_CORE_CPI_YOY` | DB.nomics | Monthly | 2026-04-30 | 128d | 90d\* |
| `JPN_CPI_YOY` | DB.nomics | Monthly | 2026-04-30 | 128d | 90d\* |
| `ITA_CPI_YOY` | DB.nomics | Monthly | 2026-04-30 | 128d | 90d\* |
| `CAN_CPI_YOY` | DB.nomics | Monthly | 2026-04-30 | 128d | 90d\* |
| `CHN_CON_CONF` | FRED | Monthly | 2026-05-01 | 127d | 90d\* |
| `CHN_BUS_CONF` | FRED | Monthly | 2026-05-01 | 127d | 75d\* |
| `EZ_BUILD_PERMITS` | Eurostat | Monthly | 2026-05-01 | 127d | 120d\* |
| `GBR_INFL_EXP_5Y` | BoE Survey | Quarterly | 2026-05-01 | 127d | 120d\* |
| `CHE_CPI_YOY` | DB.nomics | Monthly | 2026-05-31 | 97d | 90d\* |
| `NLD_CPI_YOY` | DB.nomics | Monthly | 2026-05-31 | 97d | 90d\* |
| `DEU_CPI_YOY` | DB.nomics | Monthly | 2026-05-31 | 97d | 90d\* |
| `USA_TREAS_10Y` | FRED | Monthly | 2026-06-01 | 96d | 75d\* |
| `USA_EQUITY_MEI` | FRED | Monthly | 2026-06-01 | 96d | 75d\* |
| `GBR_GILT_10Y` | FRED | Monthly | 2026-06-01 | 96d | 75d\* |
| `DEU_BUS_CONF` | FRED | Monthly | 2026-06-01 | 96d | 75d\* |
| `GBR_BUS_CONF` | FRED | Monthly | 2026-06-01 | 96d | 75d\* |
| _… 36 more in `data_audit.txt`_ |  |  |  |  |  |

</details>

<details><summary>Active historical anchors (informational)</summary>

| Series | Source | Last obs | Next expected release |
|---|---|---|---|
| `USA_CPI_JST` | JST | 2020-12-31 | 2026-12-31 |
| `USA_GDP_JST` | JST | 2020-12-31 | 2026-12-31 |
| `USA_EQUITY_TR_JST` | JST | 2020-12-31 | 2026-12-31 |
| `USA_LTRATE_JST` | JST | 2020-12-31 | 2026-12-31 |
| `GBR_CPI_JST` | JST | 2020-12-31 | 2026-12-31 |
| `GBR_GDP_JST` | JST | 2020-12-31 | 2026-12-31 |
| `GBR_EQUITY_TR_JST` | JST | 2020-12-31 | 2026-12-31 |
| `GBR_LTRATE_JST` | JST | 2020-12-31 | 2026-12-31 |
| `DEU_CPI_JST` | JST | 2020-12-31 | 2026-12-31 |
| `DEU_GDP_JST` | JST | 2020-12-31 | 2026-12-31 |
| `DEU_EQUITY_TR_JST` | JST | 2020-12-31 | 2026-12-31 |
| `DEU_LTRATE_JST` | JST | 2020-12-31 | 2026-12-31 |
| `FRA_CPI_JST` | JST | 2020-12-31 | 2026-12-31 |
| `FRA_GDP_JST` | JST | 2020-12-31 | 2026-12-31 |
| `FRA_EQUITY_TR_JST` | JST | 2020-12-31 | 2026-12-31 |
| `FRA_LTRATE_JST` | JST | 2020-12-31 | 2026-12-31 |
| `JPN_CPI_JST` | JST | 2020-12-31 | 2026-12-31 |
| `JPN_GDP_JST` | JST | 2020-12-31 | 2026-12-31 |
| `JPN_EQUITY_TR_JST` | JST | 2020-12-31 | 2026-12-31 |
| `JPN_LTRATE_JST` | JST | 2020-12-31 | 2026-12-31 |
| `ITA_CPI_JST` | JST | 2020-12-31 | 2026-12-31 |
| `ITA_GDP_JST` | JST | 2020-12-31 | 2026-12-31 |
| `ITA_EQUITY_TR_JST` | JST | 2020-12-31 | 2026-12-31 |
| `ITA_LTRATE_JST` | JST | 2020-12-31 | 2026-12-31 |
| `CAN_CPI_JST` | JST | 2020-12-31 | 2026-12-31 |
| `CAN_GDP_JST` | JST | 2020-12-31 | 2026-12-31 |
| `CAN_LTRATE_JST` | JST | 2020-12-31 | 2026-12-31 |
| `AUS_CPI_JST` | JST | 2020-12-31 | 2026-12-31 |
| `AUS_GDP_JST` | JST | 2020-12-31 | 2026-12-31 |
| `AUS_EQUITY_TR_JST` | JST | 2020-12-31 | 2026-12-31 |
| _… 9 more in `data_audit.txt`_ |  |  |  |

</details>

<details><summary>Static-check failures</summary>


**missing_columns** (1):
- _get_col(...,'GOLD_USD_PM') referenced in the calculator layer but column absent from macro_economic_hist.csv

**unadjusted_splits** (2):
- BTC-USD: 62975.6 → 78335.2 (1.244x) at 2026-08-21, matches clean split ratio + new level held within ±15% over the next 2 weeks — possible unadjusted split; add a data/manual_splits.csv row and run scripts/backadjust_hist_splits.py
- ETH-USD: 1880.65 → 2515.28 (1.337x) at 2026-08-21, matches clean split ratio + new level held within ±15% over the next 2 weeks — possible unadjusted split; add a data/manual_splits.csv row and run scripts/backadjust_hist_splits.py

</details>

<details><summary>History preservation</summary>


| File | Live rows | Sister rows | Union | Live range | Sister range |
|---|---|---|---|---|---|
| `market_data_comp_hist.csv` | 4,001 | 4,001 | 4,001 | 1950-01-06 → 2026-09-04 | 1950-01-06 → 2026-09-04 |
| `macro_economic_hist.csv` | 4,159 | 4,159 | 4,159 | 1946-12-27 → 2026-09-04 | 1946-12-27 → 2026-09-04 |
| `macro_market_hist.csv` | 1,392 | 1,392 | 1,392 | 2000-01-07 → 2026-09-04 | 2000-01-07 → 2026-09-04 |

</details>

