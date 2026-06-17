# Label-vs-Data Audit — 2026-06-15 (updated 2026-06-17)

> **Updated 2026-06-17:** credential-blocked population completed — FRED (104 macro +
> 27 market) and ifo (26 macro) audited, BDF (2) probed (PROVISIONAL), the 3 e-Stat
> CRITICALs reconfirmed unchanged, and the 41 market other/none rows classified. Only
> BLS (3 macro) remains SKIPPED-CREDS. New findings are tagged *added 2026-06-17*.

Wrong-table / wrong-slice / wrong-units / frozen-mirror audit across the full
macro + market pipeline. Triggered by PR #208 (two e-Stat registrations pointed
at the wrong tables). This audit verifies, per ticker, that the underlying data
series actually matches the four claims its library metadata makes: **Identity**
(official upstream title), **Cadence** (publish frequency), **Units & range**,
and **Within-source slice** (multi-dim tables pin a single series).

READ-ONLY research report. No source files, CSVs, or modules were modified.

---

## Codespace credential snapshot

**Updated 2026-06-17 (audit-completion pass).** The required secrets were mirrored
into the Codespace after the 2026-06-15 pass; this table reflects the current state.
Presence checked via `os.environ.get` — values never read. The 2026-06-15 snapshot
had only `ESTAT_APP_ID` present.

| Secret | State (2026-06-17) | Effect on audit |
|--------|--------------------|-----------------|
| `ESTAT_APP_ID` | **SET** | e-Stat fully audited (5 regs) ✓ |
| `FRED_API_KEY` | **SET** (newly mirrored) | **FRED 104 macro + 27 market now audited** ✓ |
| `BDF_API_KEY` | **SET** (newly mirrored) | BdF catalogue reachable; 2 PROVISIONAL rows still blocked upstream (catalogue exposes only `tableaux_rapports_preetablis`) |
| `BRIGHTDATA_API_KEY` | **SET** (newly mirrored) | **ifo 26 macro now audited** ✓ — fetched via the account's live zone `mcp_unlocker` |
| `BRIGHTDATA_ZONE` | MISSING | the source's default `web_unlocker1` does **not** exist on this account; the live unlocker zone `mcp_unlocker` was discovered via `/zone/get_active_zones` and used for the ifo workbook fetch |
| `BLS_API_KEY` | **MISSING** | **BLS 3 macro remain SKIPPED-CREDS** |
| `NASDAQ_DATA_LINK_API_KEY` | MISSING | (0 NDL tickers in hist) |
| `ALPHAVANTAGE_API_KEY` | MISSING | (0 AV tickers in hist) |

All keyless macro sources (OECD, ECB, ONS, DB.nomics, Bundesbank, BoE, ABS, ISTAT,
BoC, StatCan, INSEE, IMF, World Bank, JST, Shiller, KenFrench/French, LBMA,
AtlantaFed, NYFed, BoJ) and all 333 yfinance market tickers were audited in the
2026-06-15 pass. **As of 2026-06-17 the credential-blocked population is cleared
except BLS (3 macro):** FRED (104 macro + 27 market) and ifo (26 macro) are now
audited; BDF (2) is reachable but its MFI rate series remain unpublished on the BdF
Opendatasoft catalogue, so those 2 rows stay PROVISIONAL (not a credential gap). The
only key still to mirror for full coverage is `BLS_API_KEY`. See
`manuals/2026-06-15-codespace-secrets-checklist.md`.

---

## Executive summary

**Updated 2026-06-17.** The 2026-06-17 pass added FRED (104 macro + 27 market), ifo
(26 macro), BDF (2, PROVISIONAL) and reconfirmed the 3 e-Stat CRITICALs + classified
the 41 market other/none rows. Counts below are the cumulative totals.

| | Audited | SKIPPED-CREDS | CRITICAL | WARNING | OK |
|--|--|--|--|--|--|
| **Macro** (299 hist cols + 3 not-yet-fetched e-Stat regs) | ~296 + 3 regs | 3 (BLS) | **22** | 9 | ~265 |
| **Market** (401 rows) | 360 (333 yfinance + 27 FRED) | 0 | **15** | ~26 | ~319 |
| **TOTAL** | **~656** | **3** | **37** | **~35** | **~584** |

The 41 market "other/none" rows are all `data_source=UNAVAILABLE` and absent from
hist (no resolvable ticker → no data served) — classified, 0 findings; they are
declared-unavailable placeholders, not credential-blocked.

Flag breakdown (CRITICAL+WARNING): WRONG-TABLE/INSTRUMENT 14 · WRONG-CADENCE 1 ·
WRONG-UNITS 16 (incl. 11 JST + base-year/pence + 3 FRED OECD-MEI level-vs-YoY +
CHN_IND_PROD) · WRONG-SLICE 2 · WRONG-DATA/frozen-serving 2 (US_GDPNOW parser +
GBR_CPI frozen mirror) · broken-registration 4 (FRED non-existent series_id) ·
currency/pence factor-100 ~12 · dead/stale ~4.

**The audit is now COMPLETE for every source except BLS (3 macro, key still
MISSING).** FRED, ifo, and the e-Stat reconfirmation closed the 2026-06-15
credential-blocked backlog. See "Source coverage matrix" and the shrunk
"RESUME FROM marker".

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

**6. `US_GDPNOW` (AtlantaFed) — PARSER CONTAMINATION. ROOT-CAUSE-FIXED 2026-06-17.**
The endpoint and label are right, but `sources/atlanta_fed.py` parsed ~23 sheets
of the GDPNow workbook (including subcomponent/contribution tabs) and a
rightmost-non-null heuristic grabbed a non-headline column. Confirmed in hist:
recent `US_GDPNOW` = **32.3, 29.5, 28.3** (2026-05-29→06-12) vs the correct
GDPNow 2026-Q2 nowcast of ~3.3% (the 2026-05-08 value 3.29 was right, then it
breaks). Cadence (weekly, gap 7) is fine; the *values are not the nowcast*.
**Status (updated 2026-06-17):** root cause fixed at the code level by commit
`ce1225e` — `sources/atlanta_fed.py` now uses a headline-tab allowlist
(`_is_headline_sheet`: TrackingArchives/TrackingDeepArchives + a per-quarter
live-tab pattern) instead of a narrow skip-set, and `data_audit.py` gained a
Section E value-plausibility band (`US_GDPNOW = [-15, 20]`) as a backstop. **The
contaminated ~28/29/24 values still sit in the committed `macro_economic_hist.csv`
and will not clear until the next clean macro regeneration** (code fixed, data not
yet). (NYFed twin was OK only because its workbook lacks those tabs.)

### Macro — added 2026-06-17 (FRED, now credentialed)

**M13. `GBR_CPI` (FRED `GBRCPIALLMINMEI`) — FROZEN OECD-MEI MIRROR SERVING STALE.**
Identity and units are correct (UK CPI, Index 2015=100, Monthly), but the FRED
OECD-MEI series **stopped updating at 2025-03** (`observation_end=2025-03-01`,
value 136.1) and `GBR_CPI` is the **active source** for this column — the weekly
spine has forward-filled the frozen 136.1 unchanged since March 2025 (~15 months;
last distinct value `2025-03-07 = 136.1`). Unlike the CHN OECD-MEI mirrors this is
**not an accepted gap**: ONS publishes UK CPI live and the pipeline already uses
ONS for other UK series. **Remediation:** repoint `GBR_CPI` to the live ONS CPIH/CPI
series (or the OECD live SDMX flow) so a fresh source wins the merge.

**M14. `CHN_IND_PROD` (FRED `CHNPRINTO01IXPYM`) — WRONG-UNITS.** Library claims
`Index 2015=100 (SA)`, but FRED units are **"Index, same period previous year =
100"** — i.e. a YoY growth index, *not* a fixed-2015-base level and *not* seasonally
adjusted. Charting it as a 2015=100 SA level is wrong (the hist value ~106.6 is a
~6.6% YoY reading, not a level vs 2015). Series is also frozen (`obs_end 2023-11`,
already a documented China accepted-gap), but the units mislabel is a distinct,
active defect. **Remediation:** relabel units to "Index, same period prev year=100
(YoY)"; drop "(SA)".

**M15. 4× FRED rows with NON-EXISTENT `series_id` — BROKEN REGISTRATION (pre-hist).**
All four `/fred/series` calls return HTTP 400 *"The series does not exist."* and all
four carry a library note flagging "VERIFY id on first fetch"; none is in hist (no
`col` assigned), so they serve no data — but they would silently never populate:
`IRLTLT01CNM156N` (China 10Y govt yield — OECD MEI has no China long-term-rate
series), `NAHBSHF` (NAHB Housing Market Index), `MICH5YR` (UMich 5-10y inflation
expectations), `BAMLER00ICOAS` (ICE BofA Euro Corporate IG OAS). **Remediation:**
find the correct FRED id for each or drop the row; none of these four indices is
published on FRED under the registered id.

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
| `CHN_M2` | FRED `MYAGM2CNM189N` | WRONG-UNITS | *(added 2026-06-17)* Library "Percent Change YoY" but FRED units = "National Currency" — a level, not a YoY %. Active in hist (last value ~1.9e9 = a level). Also frozen 2019-08 (China accepted-gap). |
| `JPN_M2` `EZ_M3` | FRED `MYAGM2JPM189S` / `MABMM301EZM189S` | WRONG-UNITS, pre-hist | *(added 2026-06-17)* Library "Percent Change YoY" but FRED units are levels ("National Currency" / "Euro"); both frozen (2017-02 / 2023-11) and both have empty `col` + "VERIFY id on first fetch" notes — not yet in hist, so not serving, but would mislabel if activated. |
| 2× "Global Corporate" + "Global High Yield" | FRED `BAMLCC0A0CMTRIV` / `BAMLHYH0A0HYM2TRIV` | proxy labelling | *(added 2026-06-17)* "ICE BofA Global Corporate Bond Index" (×2) and "Global High Yield Bond Index" are served by the **US** Corporate/High-Yield total-return indices. `proxy_flag=True` is set (intentional), but the row names don't say "(proxy)". Consider relabelling. All other 31 FRED market ids resolve, are fresh, and match their labels. |

---

## Source coverage matrix

Updated 2026-06-17 (FRED / ifo / BDF rows revised; market FRED + other/none closed).

| Source | In hist | Audited | SKIPPED-CREDS | CRITICAL | WARNING |
|--------|--------:|--------:|--------------:|---------:|--------:|
| FRED | 98 (104 lib) | 104 | 0 | **6** | 3 |
| ifo | 26 | 26 | 0 | 0 | 0 |
| BDF | 0 (2 lib) | 2 | 0 | 0 | 0 |
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
| **Market: FRED** | 27 | 27 | 0 | 0 | 1 |
| **Market: other/none** | 41 | 41 (classified) | 0 | 0 | 0 |

---

## Methodology (reproducibility)

- **e-Stat:** `GET api.e-stat.go.jp/rest/3.0/app/json/getMetaInfo?appId=$ESTAT_APP_ID
  &statsDataId=<id>`. Parsed `TABLE_INF/{STAT_NAME,TITLE,GOV_ORG,CYCLE,SURVEY_DATE}`
  for identity+cadence; enumerated `CLASS_INF/CLASS_OBJ` to count unfilled `cdCat`
  dims for slice. PR #208 `_parse_estat_time` fix is on main (audited against it).
- **FRED:** `/fred/series?series_id&api_key&file_type=json` → `title,frequency,units,
  observation_end`. *Run 2026-06-17* across all 104 macro + 31 distinct market ids;
  compared title/units/frequency to the library and used `observation_end` to detect
  frozen OECD-MEI mirrors. 4 macro ids returned HTTP 400 "series does not exist".
- **ifo:** *Run 2026-06-17.* The current workbook `gsk-e-202605.xlsx` (Index +
  Sectors sheets) was fetched through Bright Data — default zone `web_unlocker1` is
  absent on this account, so the live zone `mcp_unlocker` (from `/zone/get_active_zones`)
  was used. Verified every `(sheet_index, excel_col)` mapping against the sheet
  headers (Industry+Trade index/balance + Manufacturing/Services/Trade/Wholesaling/
  Retailing/Construction balances; Uncertainty index; Cycle-Tracer probability).
- **BDF:** *Probed 2026-06-17.* `BDF_API_KEY` authenticates against the Opendatasoft
  catalogue (`webstat.banque-france.fr/api/explore/v2.1`), but it still exposes only
  `tableaux_rapports_preetablis` — the MFI interest-rate series are not published, so
  both rows stay PROVISIONAL (upstream gap, not a credential gap).
- **Market other/none:** *Classified 2026-06-17.* All 41 rows are
  `data_source=UNAVAILABLE` / `validation_status=UNAVAILABLE` with no resolvable
  yfinance/FRED ticker and absent from hist — nothing to probe, nothing served.
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

**Updated 2026-06-17 — only BLS remains.** FRED (104 macro + 27 market), ifo (26),
and the e-Stat reconfirmation are done; BDF (2) is probed (PROVISIONAL, upstream
gap); the 41 market other/none rows are classified (all UNAVAILABLE). The single
outstanding item:

1. **BLS — 3 macro** (`macro_library_bls.csv`): mirror `BLS_API_KEY` (still MISSING),
   then `api.bls.gov/publicAPI/v2/...?registrationkey=&catalog=true` for catalogue
   title + units per series.

Everything else in this report is final.
