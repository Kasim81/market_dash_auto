# Source-overlap survey

Contested columns: **36**; pairs classified: **34**; fetch errors: **0**; candidates returning no data: **0**

| verdict | n |
|---|---|
| SAME_SERIES | 12 |
| DIFFERENT | 11 |
| CADENCE_DIFF | 9 |
| SAME_REBASED | 2 |

## Detail

| column | verdict | A (priority) | A span | B | B span | ovl | B adds | detail |
|---|---|---|---|---|---|---|---|---|
| `AUS_GDP_GROWTH` | CADENCE_DIFF | IMF t1 Annual | 1980→2031 | ABS t0 Quarterly | 1959Q4→2026Q1 | 47 | head | end-of-period: DIFFERENT (max|diff|=5.8000 mean=2.4723) | mean: DIFFERENT (max|diff|=5.0250 mean=2.4223) |
| `CHN_CPI_YOY` | CADENCE_DIFF | IMF SDMX t1 Monthly | 1994-01→2026-06 | World Bank t1 Annual | 1987→2025 | 32 | head | end-of-period: DIFFERENT (max|diff|=6.6912 mean=1.2040) | mean: DIFFERENT (max|diff|=0.2754 mean=0.0166) |
| `DEU_BUND_10Y` | CADENCE_DIFF | FRED t1 Monthly | 1956-05→2026-06 | Bundesbank t0 Daily | 1997-07-01→2026-07-28 | 348 | tail | end-of-period: DIFFERENT (max|diff|=1.1457 mean=0.1969) | mean: DIFFERENT (max|diff|=0.6086 mean=0.1998) |
| `DEU_CPI_YOY` | CADENCE_DIFF | DB.nomics t1 Monthly | 1996-12→2026-05 | World Bank t1 Annual | 1960→2025 | 30 | head | end-of-period: DIFFERENT (max|diff|=2.7274 mean=0.7118) | mean: DIFFERENT (max|diff|=1.7608 mean=0.2252) |
| `GBR_CPI_YOY` | CADENCE_DIFF | World Bank t1 Annual | 1960→2025 | ONS t0 Monthly | 1989-01→2026-06 | 37 | tail | end-of-period: DIFFERENT (max|diff|=2.8816 mean=0.6485) | mean: DIFFERENT (max|diff|=1.1280 mean=0.3107) |
| `ITA_CPI_YOY` | CADENCE_DIFF | DB.nomics t1 Monthly | 1956-01→2026-04 | World Bank t1 Annual | 1960→2025 | 66 | none | end-of-period: DIFFERENT (max|diff|=5.7152 mean=0.9784) | mean: DIFFERENT (max|diff|=0.2853 mean=0.0165) |
| `ITA_GDP_GROWTH` | CADENCE_DIFF | IMF t1 Annual | 1980→2031 | ISTAT t0 Quarterly | 1996Q2→2026Q1 | 31 | none | end-of-period: DIFFERENT (max|diff|=9.1740 mean=1.7645) | mean: DIFFERENT (max|diff|=7.9665 mean=1.6100) |
| `JPN_CPI_YOY` | CADENCE_DIFF | DB.nomics t1 Monthly | 1971-01→2026-04 | World Bank t1 Annual | 1960→2025 | 55 | head | end-of-period: DIFFERENT (max|diff|=6.6914 mean=0.8358) | mean: DIFFERENT (max|diff|=0.1771 mean=0.0196) |
| `NLD_CPI_YOY` | CADENCE_DIFF | DB.nomics t1 Monthly | 1960-04→2026-05 | World Bank t1 Annual | 1960→2025 | 66 | head | end-of-period: DIFFERENT (max|diff|=4.3501 mean=0.6131) | mean: DIFFERENT (max|diff|=3.4879 mean=0.0723) |
| `CHN_POLICY_RATE` | DIFFERENT | FRED t1 Monthly | 1990-03→2023-11 | DB.nomics t1 Monthly | 2016-02→2025-06 | 94 | tail | max|diff|=1.1000 mean=0.6255 |
| `DEU_IND_PROD` | DIFFERENT | FRED t1 Monthly | 1958-01→2024-03 | IMF SDMX t1 Monthly | 1958-01→2026-03 | 795 | tail | ratio drift=0.0665, median r=1.1185 |
| `EA_HICP` | DIFFERENT | FRED t1 Monthly | 1991-01→2023-01 | ECB t0 Monthly | 1997-01→2026-06 | 313 | tail | max|diff|=0.1799 mean=0.0340 |
| `FRA_BUS_CONF` | DIFFERENT | FRED t1 Monthly | 1975-12→2026-06 | INSEE t0 Monthly | 1977-01→2026-07 | 594 | tail | max|rel|=1.92560 |
| `FRA_IND_PROD` | DIFFERENT | IMF SDMX t1 Monthly | 1956-01→2026-03 | INSEE t0 Monthly | 1990-01→2026-05 | 435 | tail | ratio drift=0.0271, median r=1.0227 |
| `GBR_CPI_INDEX` | DIFFERENT | FRED t1 Monthly | 1955-01→2025-03 | ONS t0 Monthly | 1988-01→2026-06 | 447 | tail | ratio drift=0.0554, median r=1.0000 |
| `GBR_UNEMPLOYMENT` | DIFFERENT | OECD t1 Monthly | 1983-01→2026-04 | ONS t0 Monthly | 1971-02→2026-04 | 520 | head | max|diff|=1.2000 mean=0.0612 |
| `ITA_UNEMPLOYMENT` | DIFFERENT | OECD t1 Monthly | 1983-01→2026-05 | ISTAT t0 Monthly | 2004-01→2026-05 | 269 | none | max|diff|=2.6609 mean=0.9290 |
| `JPN_CPI_INDEX` | DIFFERENT | DB.nomics t1 Monthly | 1955-01→2026-04 | e-Stat t0 Monthly | 1970-01→2026-06 | 676 | tail | ratio drift=0.0368, median r=0.9822 |
| `JPN_IND_PROD` | DIFFERENT | FRED t1 Monthly | 1955-01→2024-03 | e-Stat t0 Monthly | 2018-01→2026-03 | 75 | tail | ratio drift=0.0306, median r=1.1005 |
| `JPN_POLICY_RATE` | DIFFERENT | FRED t1 Monthly | 1960-01→2023-12 | DB.nomics t1 Monthly | 2006-03→2025-07 | 174 | tail | max|diff|=0.4000 mean=0.3115 |
| `USA_CORE_CPI_INDEX` | SAME_REBASED | FRED t1 Monthly | 1957-01→2026-06 | BLS t0 Monthly | 1957-01→2026-06 | 833 | none | ratio drift=0.0000, median r=1.0000 |
| `USA_CPI_INDEX` | SAME_REBASED | FRED t1 Monthly | 1947-01→2026-06 | BLS t0 Monthly | 1947-01→2026-06 | 953 | none | ratio drift=0.0000, median r=1.0000 |
| `AUS_UNEMPLOYMENT` | SAME_SERIES | OECD t1 Monthly | 1978-02→2026-06 | ABS t0 Monthly | 1978-02→2026-06 | 581 | none | max|diff|=0.0000 mean=0.0000 |
| `CAN_CPI_YOY` | SAME_SERIES | DB.nomics t1 Monthly | 1915-01→2026-04 | World Bank t1 Annual | 1960→2025 | 66 | none | end-of-period: DIFFERENT (max|diff|=2.3510 mean=0.6716) | mean: SAME_SERIES (max|diff|=0.0437 mean=0.0053) |
| `CAN_GOV_10Y` | SAME_SERIES | FRED t1 Monthly | 1955-01→2026-06 | BoC t0 Daily | 2001-01-02→2026-07-28 | 306 | tail | end-of-period: DIFFERENT (max|diff|=0.4332 mean=0.0857) | mean: SAME_SERIES (max|diff|=0.0350 mean=0.0002) |
| `CAN_UNEMPLOYMENT` | SAME_SERIES | OECD t1 Monthly | 1955-01→2026-06 | StatCan t0 Monthly | 1976-01→2026-06 | 606 | none | max|diff|=0.0000 mean=0.0000 |
| `CHE_CPI_YOY` | SAME_SERIES | DB.nomics t1 Monthly | 1956-01→2026-05 | World Bank t1 Annual | 1960→2025 | 66 | none | end-of-period: DIFFERENT (max|diff|=3.2488 mean=0.6041) | mean: SAME_SERIES (max|diff|=0.0468 mean=0.0036) |
| `EA_DEPOSIT_RATE` | SAME_SERIES | FRED t1 Daily | 1999-01-01→2026-07-29 | ECB t0 Daily | 1999-01-01→2026-07-29 | 10072 | none | max|diff|=0.0000 mean=0.0000 |
| `FRA_CPI_YOY` | SAME_SERIES | DB.nomics t1 Monthly | 1956-01→2026-04 | World Bank t1 Annual | 1960→2025 | 66 | none | end-of-period: DIFFERENT (max|diff|=2.2876 mean=0.5508) | mean: SAME_SERIES (max|diff|=0.0727 mean=0.0064) |
| `GBR_BANK_RATE` | SAME_SERIES | FRED t1 Monthly | 1947-01→2017-01 | BoE t0 Monthly | 1975-01→2026-07 | 505 | tail | max|diff|=0.0050 mean=0.0016 |
| `IND_GOVT_10Y` | SAME_SERIES | FRED t1 Monthly | 2011-12→2026-05 | OECD t1 Monthly | 2011-12→2026-06 | 174 | tail | max|diff|=0.0000 mean=0.0000 |
| `ITA_BTP_10Y` | SAME_SERIES | FRED t1 Monthly | 1991-03→2026-06 | ECB t0 Monthly | 1991-03→2026-06 | 424 | none | max|diff|=0.0000 mean=0.0000 |
| `NLD_DSL_10Y` | SAME_SERIES | FRED t1 Monthly | 1959-01→2026-06 | ECB t0 Monthly | 1986-04→2026-06 | 483 | none | max|diff|=0.0000 mean=0.0000 |
| `USA_UNEMPLOYMENT` | SAME_SERIES | FRED t1 Monthly | 1948-01→2026-06 | OECD t1 Monthly | 1955-01→2026-06 | 857 | none | max|diff|=0.0000 mean=0.0000 |
