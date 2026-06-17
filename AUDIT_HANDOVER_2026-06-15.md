# HANDOVER — Label-vs-Data Audit (2026-06-15, updated 2026-06-17)

Status file so the audit can be resumed if this Codespace closes.

## TL;DR — where we are

**Updated 2026-06-17: the audit is now COMPLETE except BLS (3 macro).** The required
secrets were mirrored; the 2026-06-17 pass audited **FRED (104 macro + 27 market)**
and **ifo (26 macro)**, probed **BDF (2, PROVISIONAL)**, reconfirmed the 3 e-Stat
CRITICALs (unchanged), and classified the **41 market other/none** rows (all
UNAVAILABLE). The full report is at:

> **`manuals/2026-06-15-label-vs-data-audit.md`** (updated in place 2026-06-17).

Branches: original `claude/label-vs-data-audit-2026-06-15`; the 2026-06-17 doc
updates are on `claude/label-vs-data-audit-refresh-2026-06-17`.

The ONLY work left is **BLS (3 macro)** — `BLS_API_KEY` is still MISSING from this
Codespace. Mirror it (see `manuals/2026-06-15-codespace-secrets-checklist.md`) and
finish via the report's RESUME-FROM marker.

## Credential state (updated 2026-06-17)
- **SET:** `ESTAT_APP_ID`, `FRED_API_KEY`, `BDF_API_KEY`, `BRIGHTDATA_API_KEY`.
- **MISSING:** `BLS_API_KEY`, `BRIGHTDATA_ZONE`, `NASDAQ_DATA_LINK_API_KEY`,
  `ALPHAVANTAGE_API_KEY`.
- Note: `BRIGHTDATA_ZONE` is unset and the source default `web_unlocker1` does not
  exist on this account; ifo was fetched via the live zone `mcp_unlocker` (found via
  `/zone/get_active_zones`). `BDF_API_KEY` authenticates but the BdF Opendatasoft
  catalogue still exposes only `tableaux_rapports_preetablis` → BDF rows PROVISIONAL.
- *(At the 2026-06-15 audit start only `ESTAT_APP_ID` was present.)*

## Headline findings (37 CRITICAL: 22 macro, 15 market — was 31 at 2026-06-15)
New 2026-06-17 macro CRITICALs: `GBR_CPI` (frozen OECD-MEI mirror forward-filling a
15-month-stale value; ONS live alt exists), `CHN_IND_PROD` (WRONG-UNITS: YoY index
mislabelled 2015=100 SA), and 4 FRED rows with non-existent `series_id`
(`IRLTLT01CNM156N`, `NAHBSHF`, `MICH5YR`, `BAMLER00ICOAS` — pre-hist, "VERIFY"
notes). `US_GDPNOW` is now root-cause-fixed by commit `ce1225e` (stale values remain
in hist pending macro regen). ifo (26) and FRED market (31 ids) came back clean.
3 highest-priority (next "Japan e-Stat wrong-table" equivalents):
1. **JPN_RETAIL_SALES** (e-Stat 0003138782) — frozen **2013 annual archive**
   (CYCLE=年次, SURVEY_DATE 201301-201312), mislabelled Monthly Trillion JPY.
2. **US_GDPNOW** (AtlantaFed) — parser contamination serving **~32%** vs the
   correct ~3.3% nowcast (wrong data live in hist right now).
3. **11× `<ISO>_GDP_JST`** — JST **nominal** GDP mislabelled "Real GDP"
   (confirmed: USA grew 64× 1950→2015; real grows ~6×). Feeds Phase E composites.
Also: **8× EMB collision** (8 country bond indices all point at one USD fund),
DEU_HICP_INDEX (2015=100 vs rebased 2025=100), JPN_HH_EXP & JPN_EWS_DI
(WRONG-SLICE, no cdCat filters), 3× pence factor-100 ETFs, ^SP500-6020,
SMALLCAP.NS, NDIA.L, CMOD.L. Full detail + remediation in the report.

## What was done (all committed in the report)
- e-Stat (5 regs) — audited directly with the live key.
- Keyless macro — OECD(26), DB.nomics(16), ONS(13), IMF(12), WorldBank(8),
  BoJ(9), BoE(7), BoC(5), ECB(5), Bundesbank(4), ISTAT(3), INSEE(3), JST(39),
  Shiller(6), KenFrench/French(6), ABS(5), LBMA(1), AtlantaFed(1), NYFed(1).
- Market — all 333 yfinance tickers (name + currency + liveness).
- Intermediate manifests are in `/tmp/audit/` (NOT committed; regenerate if the
  Codespace was wiped — see below).

## If you must restart from scratch
1. `git checkout claude/label-vs-data-audit-2026-06-15` (or `git pull` — it's on
   origin). The report is already there; you may not need to redo anything.
2. To regenerate the `/tmp/audit/` manifests (per-source ticker lists + empirical
   cadence), re-run the manifest-builder: it joins `data/macro_economic_hist.csv`
   (row0=Column ID, row1=Series ID, row2=Source) to `data/macro_library_*.csv`,
   and computes median days between value-changes per column. (~30 lines of pandas/
   csv; the report Methodology section documents every endpoint used.)
3. Mirror `BLS_API_KEY` (the only remaining gap), then work the report's
   **RESUME FROM** list (BLS — 3 macro). FRED, ifo, BDF, e-Stat reconfirm, and the
   41 other/none market rows were completed 2026-06-17.

## Git
- Branch `claude/label-vs-data-audit-2026-06-15`, identity Claude
  <noreply@anthropic.com>. Report committed + pushed. Do NOT open a PR (user
  reviews and queues remediation separately). This handover file is committed too.

---

## ORIGINAL PROMPT (verbatim, for full context on restart)

You are working on the kasim81/market_dash_auto data pipeline IN A GITHUB CODESPACE.
Your task: audit every ticker in the pipeline (macro AND market) to verify that the
underlying data series actually matches the metadata label attached to it. This is
the "wrong-table" / "wrong-slice" / "frozen-mirror" audit that the freshness and
source-tier audits don't catch on their own.

### Why this matters
PR #208 (2026-06-15) discovered that two e-Stat registrations were tied to the
WRONG TABLES entirely:
- statsDataId 0003446463 was labelled "JPN_IND_PROD — Industrial Production (METI)"
  but actually points to stat 00100406 (Cabinet Office Composite Index of Business
  Conditions). Different agency, methodology, release calendar.
- statsDataId 0003355224 was labelled "JPN_MACH_ORDERS — Monthly machinery orders"
  but actually points to the ANNUAL fiscal-year Original-Series machinery table.
Today's source-tier audit also found seven series structurally annual/frozen-mirror
despite Monthly labels. PRs #205 (UK_INFL1) and #208 fixed three; four remain
(CHN_CPI, CHN_PPI, CHN_M2, CHN_IND_PROD — last two accepted gaps). The standard
freshness audit can't catch these because the weekly Friday spine forward-fills.

### Credentials (Codespaces)
Actions secrets are write-only; not auto-synced to Codespaces. User mirrors them as
Repository Codespaces secrets. Required: FRED_API_KEY (122/263 macro on FRED),
ESTAT_APP_ID. Useful: BLS, BDF, BRIGHTDATA(+ZONE), NASDAQ_DATA_LINK, ALPHAVANTAGE.
Keyless: OECD, ECB, ONS, DB.nomics, Bundesbank, BoE, ABS, ISTAT, BoC, StatCan,
INSEE, IMF, World Bank, JST, Shiller, KenFrench, LBMA, AtlantaFed, NYFed, BoJ.
For sources whose key is missing, mark per-ticker results SKIPPED-CREDS and move on —
DO NOT stop the audit because one source's key is absent.

### Scope
- MACRO: all 263 columns in data/macro_economic_hist.csv (row-0 Column ID =
  canonical name; row-2 Source = registered source; macro_library_*.csv = full
  label+description).
- MARKET: all ~400 rows in data/index_library.csv (name, asset_class, region,
  country_market, units, yfinance/FRED ticker fields).
- Phase E composites in data/macro_indicator_library.csv NOT in scope.

### What to verify per ticker (4 claims)
1. Identity — source metadata endpoint's official TITLE matches the library label
   (title mismatch = WRONG-TABLE).
2. Cadence — library frequency matches source metadata + empirical value-change
   cadence in hist (mismatch = WRONG-CADENCE).
3. Units & range — library units match observed value distribution (mismatch =
   WRONG-UNITS).
4. Within-source slice — multi-dim tables (e-Stat cdCat, OECD/ABS/Bundesbank
   multi-dim) must pin a SINGLE series; unfilled dims = WRONG-SLICE.

### How to verify per source
FRED /fred/series; e-Stat getMetaInfo (TABLE_INF/STAT_NAME + TITLE_SPEC + cdCat
dims; PR #208 also fixed _parse_estat_time — test against corrected main); OECD
SDMX dataflow XML; DB.nomics /v22/series; Bundesbank/ECB SDMX; ABS Data API; BoE
IADB; BoJ catalogue (list_series); BLS /v2 catalog=true; ONS /data; INSEE BDM;
BdF Opendatasoft (PROVISIONAL ok); ISTAT SDMX; StatCan/BoC/WorldBank/IMF/LBMA/
Shiller/KenFrench/JST/AtlantaFed/NYFed source-specific; yfinance Ticker.info+history
for market (name vs library name, currency vs base_currency); FRED market tickers
via FRED metadata.

### Budgets/constraints
Use existing sources/*.py metadata helpers. FRED 120 req/min — pace. e-Stat per-day
cap — sleep. Bright Data only for sources that block vanilla requests (ifo). 263+400
tickers; a single run gets 4-6h; leave a RESUME FROM marker if unfinished.

### Output
Single markdown report at manuals/2026-06-15-label-vs-data-audit.md with sections:
Codespace credential snapshot; Executive summary (totals, probed vs SKIPPED, counts
by flag, counts by severity CRITICAL/WARNING/OK); CRITICAL findings per ticker
(ticker, source+series_id, registered label, official upstream title, mismatch
nature, remediation, evidence; sort Phase-E-feeding macro first, then macro, then
market); WARNING findings (same + "why uncertain"); Source coverage matrix
(source → audited/SKIPPED-CREDS/probe-failed); Methodology (endpoint+fields per
source, reproducible); Accepted-gap reaffirmations; RESUME FROM marker (omit if
complete).

### Important
RESEARCH report — do NOT edit source files/CSVs/modules. Don't flag JST historical
anchors as WRONG-CADENCE (intentionally annual). No model identifier anywhere.

### Git discipline
Branch claude/label-vs-data-audit-2026-06-15. Identity Claude
<noreply@anthropic.com>. One commit, the new manuals/*.md file. Push with
git push -u origin <branch>. Do NOT open a PR.

### Report back
Branch+commit SHA; total tickers audited / CRITICAL / WARNING / SKIPPED-CREDS;
credentials present vs absent; 3 highest-priority CRITICAL; whether complete or
RESUME FROM left.
