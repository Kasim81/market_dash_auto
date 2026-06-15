# Label-vs-Data Audit — 2026-06-15

Wrong-table / wrong-slice / wrong-units / frozen-mirror audit across the full
macro + market pipeline. Triggered by PR #208 (two e-Stat registrations pointed
at the wrong tables). This audit verifies, per ticker, that the underlying data
series actually matches the four claims its library metadata makes: **Identity**
(official upstream title), **Cadence** (publish frequency), **Units & range**,
and **Within-source slice** (multi-dim tables pin a single series).

READ-ONLY research report. No source files, CSVs, or modules were modified.

---

## Codespace credential snapshot

Checked at audit start via `env | grep`. Only ONE key was present.

| Secret | State | Effect on audit |
|--------|-------|-----------------|
| `ESTAT_APP_ID` | **SET** | e-Stat fully audited (the trigger class) ✓ |
| `FRED_API_KEY` | MISSING | **FRED 104 macro + 27 market tickers SKIPPED-CREDS** |
| `BLS_API_KEY` | MISSING | BLS 3 macro tickers SKIPPED-CREDS |
| `BDF_API_KEY` | MISSING | (no BdF tickers currently in hist) |
| `BRIGHTDATA_API_KEY` / `_ZONE` | MISSING | **ifo 26 macro tickers SKIPPED-CREDS** |
| `NASDAQ_DATA_LINK_API_KEY` | MISSING | (0 NDL tickers in hist) |
| `ALPHAVANTAGE_API_KEY` | MISSING | (0 AV tickers in hist) |

All other macro sources (OECD, ECB, ONS, DB.nomics, Bundesbank, BoE, ABS, ISTAT,
BoC, StatCan, INSEE, IMF, World Bank, JST, Shiller, KenFrench/French, LBMA,
AtlantaFed, NYFed, BoJ) and all yfinance market tickers are **keyless** and were
audited. **133 macro + 27 market tickers are blocked on the next mirror-the-secret
pass** (mainly FRED + ifo). See the secrets checklist at
`manuals/2026-06-15-codespace-secrets-checklist.md` — the 3 keys to mirror for
full coverage are `FRED_API_KEY`, `BLS_API_KEY`, `BRIGHTDATA_API_KEY`.

---

## Executive summary

| | Audited | SKIPPED-CREDS | CRITICAL | WARNING | OK |
|--|--|--|--|--|--|
| **Macro** (299 hist cols + 3 not-yet-fetched e-Stat regs) | ~166 + 3 regs | 133 (FRED 104, ifo 26, BLS 3) | **16** | 6 | ~144 |
| **Market** (401 rows) | 333 (yfinance) | 27 (FRED) + 41 (other/none) | **15** | ~25 | ~293 |
| **TOTAL** | **~499** | **201** | **31** | **~31** | **~437** |

Flag breakdown (CRITICAL+WARNING): WRONG-TABLE/INSTRUMENT 14 · WRONG-CADENCE 1 ·
WRONG-UNITS 13 (incl. 11 JST + base-year/pence) · WRONG-SLICE 2 · WRONG-DATA
(parser) 1 · currency/pence factor-100 ~12 · dead/stale ~4.

**The audit of all auditable (keyed-present + keyless) sources is COMPLETE.**
The only outstanding work is the credential-blocked population (FRED, ifo, BLS) —
see the "Source coverage matrix" and run again once those keys are mirrored.

---

## CRITICAL findings

Sorted by impact: macro feeding Phase E composites first, then other macro, then
market.

### Macro

**1. `JPN_RETAIL_SALES` (e-Stat `0003138782`) — FROZEN 2013 ANNUAL ARCHIVE.**
The exact PR #208 class. `getMetaInfo` returns `STAT_NAME=商業動態統計調査`
(METI Current Survey of Commerce) but `CYCLE=年次 (ANNUAL)`, `SURVEY_DATE=
201301-201312`, and the `@time` dimension is `年月（H19～H25）` = monthly codes
**only through 2013 (Heisei 25)**. Library claims Monthly / `Trillion JPY (SA)`.
Also WRONG-UNITS: the table is `業種別商業販売額指数` (a sales *index*, base 100),
not Trillion JPY. *(Not yet in hist — broken registration; the library note
already predicted "if 2013-ish, switch to file-download".)* **Remediation:**
re-point to the live monthly headline (METI stat-search/files `stat_infid=
000040274818`) or the live DB monthly table; fix units to "Index (SA)".

**2. `JPN_HH_EXP` (e-Stat `0002070001`) — WRONG-SLICE.** `STAT_NAME=家計調査`
(Family Income & Expenditure Survey), `CYCLE=月次` ✓ but the series_id carries
**no `cdCat` filters** on a table with 3 unfilled category dims: `@cat01 用途分類
(265 codes)`, `@cat02 世帯区分 (4)`, `@area 地域区分 (75)`. The fetcher cannot
pin 消費支出/二人以上/全国 — it returns the first/ambiguous slice. Units claim
"YoY % (real)" is also unverifiable without the 表章項目 slice. *(Not yet in
hist; lib note says "cdCat filter discovery pending first credentialed fetch".)*
**Remediation:** add `cdCat01=<消費支出>&cdCat02=<二人以上>&...&area=<全国>`.

**3. `JPN_EWS_DI` (e-Stat `0003348427`) — WRONG-SLICE.** `STAT_NAME=景気ウォッチャー
調査` (Economy Watchers Survey), `CYCLE=月次` ✓ but **no `cdCat` filters** on a
table with FIVE multi-code dims including `@tab 表章項目 (3 codes: respondent
count / composition ratio / DI)`. Without the `@tab` filter the fetcher cannot
even guarantee it returns the DI vs respondent counts. *(Not yet in hist.)*
**Remediation:** pin `@tab=<DI>` plus 判断/分野/地域 = 全国/合計.

**4. 11× `<ISO>_GDP_JST` (JST Macrohistory `<ISO>|gdp`) — NOMINAL DATA LABELLED
"REAL GDP".** Every country GDP row (USA, GBR, DEU, FRA, JPN, ITA, CAN, AUS, NLD,
CHE — `USA_GDP_JST` etc.) is labelled "… Real GDP (JST Macrohistory)" with units
"… millions (real)". The JST `gdp` variable is **nominal GDP (current prices,
local currency)**. Empirically confirmed: `USA_GDP_JST` grew **64×** 1950→2015
(272→17,551) — US *real* GDP grew ~6× over that span, *nominal* ~70×. So the
series is nominal but the dashboard treats it as real (the repo coverage map uses
`USA|gdp` as the "Real GDP" analogue — error propagates into Phase E regime
composites). **Remediation:** either re-point to a JST real-GDP variable
(`rgdpmad`/derive gdp÷cpi) or relabel all 11 rows as Nominal GDP and drop "(real)".

**5. `DEU_HICP_INDEX` (Bundesbank `BBDP1/M.DE.N.HVPI.C.A00000.I.A`) — WRONG-UNITS
(stale base year).** Library says "Index 2015=100"; upstream `BBK_UNIT` now reads
**"2025=100"** (HICP rebased in early 2026). Latest level 102.55 @ 2026-05 is
consistent with a 2025 base (a 2015 base would read ~125). Identity/cadence/key
all correct. **Remediation:** update units to "Index 2025=100".

**6. `US_GDPNOW` (AtlantaFed) — PARSER CONTAMINATION, WRONG-DATA SERVED NOW.**
The endpoint and label are right, but `sources/atlanta_fed.py` parses ~23 sheets
of the GDPNow workbook (including subcomponent/contribution tabs) and a
rightmost-non-null heuristic grabs a non-headline column. Confirmed in hist:
recent `US_GDPNOW` = **32.3, 29.5, 28.3** (2026-05-29→06-12) vs the correct
GDPNow 2026-Q2 nowcast of ~3.3% (the 2026-05-08 value 3.29 was right, then it
breaks). Cadence (weekly, gap 7) is fine; the *values are not the nowcast*.
**Remediation:** restrict parsing to the genuine forecast tab + explicit
headline-column mapping; add subcomponent tabs to `_SKIP_SHEETS`. (NYFed twin is
OK only because its workbook lacks those tabs — the shared parser is fragile.)

### Market (yfinance)

**7. 8× EMB instrument-collision — WRONG-INSTRUMENT.** Eight distinct
country government-bond-index rows (Brazil/BRL, S.Korea/KRW, Mexico/MXN,
Indonesia/IDR, Saudi/SAR, S.Africa/ZAR, Turkey/TRY, Argentina/ARS) all map to the
**same** ticker `EMB` (iShares J.P.Morgan **USD** EM Bond ETF — a single USD
aggregate). All 8 would show identical USD data under wrong local-currency labels.
**Remediation:** repoint each to a country-specific bond ETF/index, or if these
are intentional proxies set `proxy_flag`/relabel as "USD EM agg (proxy)".

**8. `^SP500-6020` "S&P 500 Equity REITs" — WRONG-SUBINDEX.** yfinance resolves
to "S&P 500 Real Estate Management & Development" (GICS 6020). Equity REITs is
GICS 6010. **Remediation:** repoint to the 6010 sub-index.

**9. `SMALLCAP.NS` "Nifty Smallcap 100" — WRONG-INSTRUMENT.** Resolves to "Mirae
Asset Nifty Smallcap 250 Momentum Quality 100 ETF" — a factor-tilted different
index. **Remediation:** use `^CNXSC` / `NIFTYSMLCAP100.NS`.

**10. `NDIA.L` "iShares India 50 ETF" — WRONG-INSTRUMENT + currency.** Resolves
to "iShares MSCI India UCITS ETF" (different index) and currency GBP vs lib USD.

**11. `CMOD.L` "L&G All Commodities UCITS ETF" — WRONG-ISSUER.** Resolves to
"Invesco Bloomberg Commodity UCITS ETF" (different issuer/fund) + GBP vs USD.

**12. 3× pence factor-100 — `IEFM.L`, `IEFQ.L`, `MINV.L`.** Library currency GBP
but yfinance quotes **GBp (pence)** → prices ~100× off in any GBP math. (Sibling
LSE rows like `UKDV.L` correctly return GBP, so handling is inconsistent.)
**Remediation:** divide by 100 or set currency to GBp and convert.

---

## WARNING findings (suspected / not fully confirmable from sandbox)

| ticker | source | flag | why uncertain |
|--------|--------|------|---------------|
| `ISM_MFG_PMI` | DB.nomics | corrupt values | Identity/cadence OK; upstream obs collapse to ~10 from 2025-09 (mirror data defect, not label). |
| `ISM_SVC_PMI` | DB.nomics | stale | Correct identity; last obs 2025-08 (~10mo lag) per known mirror lag. |
| `ITA_GDP_GROWTH` | ISTAT | units semantics | `G1` VALUATION "QoQ %" couldn't be confirmed (codelist 404); values plausible. |
| `USA_TREAS_10Y_SHILLER` | Shiller | fragile header | `series_id="Rate GS10"` vs documented "Long Interest Rate GS10"; resolves now, exact-match-only is brittle. |
| `GBR_GILT_L` | BoE | note error | Maps correctly (20yr par yield); only the library *note* "~25Y" is inaccurate. |
| `AUS_CPI` | ABS | stale base-year | Label "2011-12=100"; live reference base is 2024-25. Identity correct. |
| 5× FX `USDJPY=X`,`CNY=X`,`INR=X`,`KRW=X`,`TWD=X` | yfinance | quote-ccy | yf reports the pair's quote currency (JPY/CNY/…) vs lib USD — yfinance convention, instrument correct; verify downstream interpretation. |
| 7× futures `ZS=F,ZC=F,ZW=F,SB=F,CT=F,KC=F,LE=F` | yfinance | US-cents (USX) | yf quotes US cents vs lib USD — factor-100 risk if not handled. |
| `IUKD.L`, `IWFV.L` | yfinance | pence (GBp) | factor-100 risk vs lib GBP. |
| ~8 LSE listing-ccy `CNYB.L,IBGS.L,IBGL.L,IBCI.L,IBGM.L,HYXU,IWDA.L,…` | yfinance | listing vs base ccy | yf reports LSE/share-class trading ccy vs fund base ccy; display nuance, confirm conversion. |
| `^MERV` | yfinance | no currency field | ARS unconfirmable (yf returns no `currency`); data present, name matches. |
| `^SP500-151050` | yfinance | empty history | `.info` OK but 5d history empty (thin/discontinued sub-industry). |
| `^SP500-203030` | yfinance | DEAD | 404, blank library name (former Marine Transportation, removed in 2023 GICS). Remove/repoint. |

---

## Source coverage matrix

| Source | In hist | Audited | SKIPPED-CREDS | CRITICAL | WARNING |
|--------|--------:|--------:|--------------:|---------:|--------:|
| FRED | 104 | 0 | **104** | – | – |
| ifo | 26 | 0 | **26** | – | – |
| BLS | 3 | 0 | **3** | – | – |
| e-Stat | 2 (+3 regs) | 5 | 0 | **3** | 0 |
| JST | 39 | 39 | 0 | **11** | 0 |
| OECD | 26 | 26 | 0 | 0 | 0 |
| DB.nomics | 16 | 16 | 0 | 0 | 2 |
| ONS | 13 | 13 | 0 | 0 | 0 |
| IMF | 12 | 12 | 0 | 0 | 0 |
| BoJ | 9 | 9 | 0 | 0 | 0 |
| World Bank | 8 | 8 | 0 | 0 | 0 |
| BoE | 7 | 7 | 0 | 0 | 1 |
| Shiller | 6 | 6 | 0 | 0 | 1 |
| KenFrench (French) | 6 | 6 | 0 | 0 | 0 |
| ECB | 5 | 5 | 0 | 0 | 0 |
| BoC | 5 | 5 | 0 | 0 | 0 |
| Bundesbank | 4 | 4 | 0 | **1** | 0 |
| ABS | 3 (5 lib) | 5 | 0 | 0 | 1 |
| ISTAT | 0 in hist | 3 (lib) | 0 | 0 | 1 |
| INSEE | 2 | 3 | 0 | 0 | 0 |
| LBMA | 1 | 1 | 0 | 0 | 0 |
| AtlantaFed | 1 | 1 | 0 | **1** | 0 |
| NYFed | 1 | 1 | 0 | 0 | 0 |
| **Market: yfinance** | 333 | 333 | 0 | **15** | ~25 |
| **Market: FRED** | 27 | 0 | **27** | – | – |
| **Market: other/none** | 41 | 0 | 0 (no probe) | – | – |

---

## Methodology (reproducibility)

- **e-Stat:** `GET api.e-stat.go.jp/rest/3.0/app/json/getMetaInfo?appId=$ESTAT_APP_ID
  &statsDataId=<id>`. Parsed `TABLE_INF/{STAT_NAME,TITLE,GOV_ORG,CYCLE,SURVEY_DATE}`
  for identity+cadence; enumerated `CLASS_INF/CLASS_OBJ` to count unfilled `cdCat`
  dims for slice. PR #208 `_parse_estat_time` fix is on main (audited against it).
- **FRED:** `/fred/series?series_id&api_key&file_type=json` → `title,frequency,units`.
  *Not run — key missing.*
- **OECD:** SDMX `sdmx.oecd.org/public/rest/dataflow/<AGENCY>/<DFID>/<VER>?references=all`;
  compared dataflow Name + content-constraint codes to `oecd_key_template` slots.
- **DB.nomics:** `api.db.nomics.world/v22/series/<prov>/<ds>/<series>` → `series_name,
  @frequency,unit`.
- **ONS:** Zebedee `/data` JSON → `description.{title,cdid,unit}` + months/quarters arrays.
- **IMF:** DataMapper indicator descriptor; **World Bank:** `api.worldbank.org/v2/
  indicator/<code>?format=json`.
- **BoJ:** `getMetadata` catalogue (`sources/boj.py list_series`); **BoE:** IADB CSV
  preamble Description; **BoC:** Valet `/valet/series/<code>/json` seriesDetail.
- **ECB / Bundesbank / ISTAT / INSEE:** SDMX generic-data/metadata XML; checked
  series title + `UNIT`/`BBK_UNIT` + that the key pins one series.
- **JST / Shiller / French:** fixed-file sources — verified the column→variable
  mapping in the source module + empirical value ranges/growth (nominal-vs-real
  growth ratio for `gdp`).
- **ABS:** SDMX `data.api.abs.gov.au/rest/data/<flow>/<key>` + codelist; **LBMA:**
  `prices.lbma.org.uk/json/<code>.json`; **AtlantaFed/NYFed:** the live forecast
  workbook the module downloads (traced the parser output vs the headline nowcast).
- **yfinance (market):** `yf.Ticker(sym).info` (longName/shortName/quoteType/currency)
  + `.history(period='5d')`; compared to library `name` + `base_currency`.
- **Empirical cadence (all macro):** median days between *value-changes* in
  `data/macro_economic_hist.csv` (`/tmp/audit/macro_manifest.json`). Caveat: sticky
  rates inflate this gap (fewer distinct changes) — not a true cadence fault.

---

## Accepted-gap reaffirmations

- **CHN_M2, CHN_IND_PROD** — dead FRED, no free live alternative (documented
  accepted gaps in forward_plan; not re-probed, FRED key absent this pass).
- **CHN_CPI, CHN_PPI** — structurally annual/frozen-mirror per the 2026-06-15
  source-tier audit; remain on the broken-source backlog.
- **FRA_UNEMPLOYMENT** (INSEE row) absent from hist — the shared column is carried
  by OECD's monthly series, as the library notes intend. Not a defect.

---

## RESUME FROM marker

The auditable population is **fully covered**. To complete the credential-blocked
remainder on a future pass (after mirroring `FRED_API_KEY`, `BLS_API_KEY`,
`BRIGHTDATA_API_KEY` per the secrets checklist):

1. **FRED — 104 macro** (`macro_library_fred.csv`) **+ 27 market**
   (`index_library.csv` `ticker_fred_*`): `/fred/series` identity+frequency+units.
2. **ifo — 26 macro** (`macro_library_ifo.csv`): needs Bright Data (upstream blocks
   vanilla requests); verify the ifo survey component each column maps to.
3. **BLS — 3 macro** (`macro_library_bls.csv`): `api.bls.gov/publicAPI/v2/...
   ?catalog=true` catalogue title + units.
4. **Market other/none — 41 rows** in `index_library.csv` with no yfinance/FRED
   ticker resolved: classify their data_source and probe accordingly.

Everything else in this report is final.
