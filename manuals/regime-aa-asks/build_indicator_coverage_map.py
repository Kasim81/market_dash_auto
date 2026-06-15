#!/usr/bin/env python3
"""
Build the regime-aa indicator coverage map.

Reads the indicator demand specified in `regime-aa-indicator-req.md` (§5 of the
regime-aa master plan) and cross-references each requested indicator, broken out
per region, against the data pipeline's actual coverage:

  - data/macro_economic.csv          (296 base economic series)
  - data/macro_indicator_library.csv (107 derived regime composites)
  - data/macro_market.csv            (computed snapshot of the same 107 composites)
  - data/index_library.csv           (401 market-data instruments: equities, bonds,
                                       credit OAS, rates, FX, volatility indices)

Emits one row per (indicator x region) with the metadata needed to decide
whether the indicator is already covered, missing-but-sourceable, or
missing-and-hard-to-source. Outputs:

  - regime-aa-indicator-coverage.csv
  - regime-aa-indicator-coverage.md

Status vocabulary:
  Covered            pipeline carries the series (or a direct derivation of
                     series it carries) for that region
  Partial            pipeline carries a proxy / related series, not the exact
                     instrument, or only part of the regional breadth
  Missing-Sourceable not in pipeline, but a free/public source exists
  Missing-Hard       not in pipeline, only proprietary or no reliable free source
  Accepted-Gap       explicitly accepted in the spec (no free source for region)

The free-source judgements for the harder gaps were cross-checked with web
research; see the `notes` column for the specific source named.
"""
import csv
import os

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# Column order for both outputs.
COLUMNS = [
    "indicator",
    "pillar",
    "sub_group",
    "cycle_timing_prior",
    "region",
    "regional_analogue",
    "requested_source_freq",
    "lag",
    "status",
    "pipeline_match",
    "pipeline_source",
    "candidate_free_source",
    "notes",
]

# Status codes (kept stable for downstream tooling / phase_0 coverage check).
COVERED = "Covered"
PARTIAL = "Partial"
SOURCEABLE = "Missing-Sourceable"
HARD = "Missing-Hard"
ACCEPTED = "Accepted-Gap"

# Each entry: indicator-level metadata + a list of per-region dicts.
# Per-region dict keys: region, analogue, status, match, src, cand, notes
DATA = [
    # ============================ 5.1 GROWTH ============================
    # ---- 5.1.1 Forward-Looking / Anticipatory (Tier 1-2) ----
    {
        "indicator": "Yield Curve (10y minus 2y)",
        "pillar": "Growth", "sub_group": "Forward-Looking (Tier 1-2)",
        "cycle": "Leading", "src": "FRED / daily", "lag": "Real-time",
        "regions": [
            {"region": "US", "analogue": "UST 10y-2y", "status": COVERED,
             "match": "T10Y2Y; US_R2; US_R3", "psrc": "FRED",
             "cand": "", "notes": "Direct series plus 2s10s composites."},
            {"region": "UK", "analogue": "Gilts 10y-2y", "status": PARTIAL,
             "match": "IRLTLT01GBM156N (10y gilt); IUDSNPY/IUDMNPY (BoE par yields)", "psrc": "FRED / BoE",
             "cand": "BoE gilt yield curve (free)", "notes": "10y present; no clean 2y benchmark, slope derivable from BoE par-yield curve."},
            {"region": "Eurozone", "analogue": "Bunds 10y-2y", "status": COVERED,
             "match": "Germany 10y Bund + 1-2y Bund yield (Bundesbank); ECB AAA 2Y", "psrc": "Bundesbank / ECB",
             "cand": "", "notes": "10y and short-tenor Bund both present; slope derivable."},
            {"region": "Japan", "analogue": "JGBs 10y-2y", "status": PARTIAL,
             "match": "IRLTLT01JPM156N (10y JGB); RATE_3M (3m)", "psrc": "FRED / OECD",
             "cand": "MoF Japan JGB yields (free)", "notes": "10y present, no 2y benchmark; only 10y-3m computable today."},
            {"region": "China", "analogue": "CGBs 10y-2y", "status": PARTIAL,
             "match": "IRLTLT01CNM156N (10y, OECD MEI monthly)", "psrc": "FRED",
             "cand": "2y CGB leg + daily frequency remain hard", "notes": "10y leg now catalogued (IRLTLT01CNM156N, monthly). Slope still partial: no clean free 2y CGB benchmark and only monthly frequency. Resolves the spec's CN-10y 'accepted gap' for the 10y leg."},
        ],
    },
    {
        "indicator": "Yield Curve (10y minus 3m)",
        "pillar": "Growth", "sub_group": "Forward-Looking (Tier 1-2)",
        "cycle": "Leading", "src": "FRED / daily", "lag": "Real-time",
        "regions": [
            {"region": "US", "analogue": "UST 10y-3m", "status": COVERED,
             "match": "T10Y3M; US_R1", "psrc": "FRED", "cand": "", "notes": "Direct series plus composite."},
            {"region": "UK", "analogue": "Gilt 10y-3m", "status": COVERED,
             "match": "IRLTLT01GBM156N + RATE_3M", "psrc": "FRED / OECD", "cand": "", "notes": "10y gilt and 3m short rate both present; slope derivable."},
            {"region": "Eurozone", "analogue": "Bund 10y-3m", "status": COVERED,
             "match": "Germany 10y Bund + RATE_3M", "psrc": "Bundesbank / OECD", "cand": "", "notes": "Derivable."},
            {"region": "Japan", "analogue": "JGB 10y-3m", "status": COVERED,
             "match": "IRLTLT01JPM156N + RATE_3M", "psrc": "FRED / OECD", "cand": "", "notes": "Derivable."},
        ],
    },
    {
        "indicator": "OECD Composite Leading Indicator (CLI)",
        "pillar": "Growth", "sub_group": "Forward-Looking (Tier 1-2)",
        "cycle": "Leading", "src": "OECD / monthly", "lag": "5-6 weeks",
        "regions": [
            {"region": "US", "analogue": "OECD CLI US", "status": COVERED,
             "match": "OECD CLI; US_CLI1", "psrc": "OECD", "cand": "", "notes": ""},
            {"region": "UK", "analogue": "OECD CLI UK", "status": COVERED,
             "match": "OECD CLI; UK_CLI1", "psrc": "OECD", "cand": "", "notes": ""},
            {"region": "Eurozone", "analogue": "OECD CLI EA/DE/FR/IT", "status": COVERED,
             "match": "OECD CLI; EU_CLI1; DE_CLI1; FR_CLI1; IT_CLI1", "psrc": "OECD", "cand": "", "notes": ""},
            {"region": "Japan", "analogue": "OECD CLI JP", "status": COVERED,
             "match": "OECD CLI; JP_CLI1", "psrc": "OECD", "cand": "", "notes": ""},
            {"region": "China", "analogue": "OECD CLI CN", "status": COVERED,
             "match": "OECD CLI; CN_CLI1", "psrc": "OECD", "cand": "", "notes": ""},
            {"region": "EM aggregate", "analogue": "OECD CLI EM block", "status": PARTIAL,
             "match": "AS_CLI1; GL_CLI5", "psrc": "OECD", "cand": "", "notes": "Asia/global diffusion composites approximate the EM aggregate; no dedicated EM CLI."},
        ],
    },
    {
        "indicator": "Conference Board LEI",
        "pillar": "Growth", "sub_group": "Forward-Looking (Tier 1-2)",
        "cycle": "Leading", "src": "Conference Board / monthly", "lag": "3-4 weeks",
        "regions": [
            {"region": "US", "analogue": "Conference Board LEI (US)", "status": PARTIAL,
             "match": "CFNAI (proxy); US_CLI1", "psrc": "FRED / OECD",
             "cand": "Conference Board LEI is proprietary", "notes": "CB LEI itself is paywalled. Pipeline carries CFNAI and OECD CLI as free leading-composite proxies."},
            {"region": "UK", "analogue": "UK national LEI", "status": PARTIAL,
             "match": "UK_CLI1 (OECD CLI proxy)", "psrc": "OECD",
             "cand": "Conference Board UK LEI is proprietary", "notes": "OECD CLI substitutes for the proprietary national LEI."},
            {"region": "Eurozone", "analogue": "DE national LEI", "status": PARTIAL,
             "match": "DE_CLI1; DE_IFO1; DE_ZEW1", "psrc": "OECD / ifo",
             "cand": "National LEIs proprietary", "notes": "ifo and ZEW composites plus OECD CLI cover the German leading signal. Spec: none for Asia."},
        ],
    },
    {
        "indicator": "M2 Money Supply (YoY%)",
        "pillar": "Growth", "sub_group": "Forward-Looking (Tier 1-2)",
        "cycle": "Leading", "src": "Federal Reserve / monthly", "lag": "4-6 weeks",
        "regions": [
            {"region": "US", "analogue": "US M2 YoY", "status": COVERED,
             "match": "M2SL; US_M2", "psrc": "FRED", "cand": "", "notes": ""},
            {"region": "UK", "analogue": "UK M4", "status": SOURCEABLE,
             "match": "", "psrc": "", "cand": "BoE M4 (IADB LPMVWYH) - free", "notes": "Not in pipeline; BoE publishes M4 free via IADB."},
            {"region": "Eurozone", "analogue": "EZ M3", "status": COVERED,
             "match": "MABMM301EZM189S", "psrc": "FRED", "cand": "", "notes": "Catalogued (Bucket A). VERIFY id on first fetch."},
            {"region": "Japan", "analogue": "JP M2", "status": COVERED,
             "match": "MYAGM2JPM189S", "psrc": "FRED", "cand": "", "notes": "Catalogued (Bucket A). VERIFY N/S suffix on first fetch."},
            {"region": "China", "analogue": "CN M2", "status": COVERED,
             "match": "MYAGM2CNM189N", "psrc": "FRED", "cand": "", "notes": "China M2 YoY already in pipeline."},
        ],
    },
    {
        "indicator": "NAHB Housing Market Index",
        "pillar": "Growth", "sub_group": "Forward-Looking (Tier 1-2)",
        "cycle": "Leading", "src": "NAHB / monthly", "lag": "Mid-month",
        "regions": [
            {"region": "US", "analogue": "NAHB HMI", "status": COVERED,
             "match": "NAHBSHF; PERMIT; US_HOUS1; US_R6", "psrc": "FRED",
             "cand": "", "notes": "NAHB HMI catalogued (Bucket A, NAHBSHF). VERIFY id on first fetch. Permits/mortgage-spread already present."},
            {"region": "UK", "analogue": "RICS Housing Survey", "status": HARD,
             "match": "", "psrc": "", "cand": "RICS survey is paywalled", "notes": "RICS is proprietary. Free proxy: ONS/Land Registry house-price index (not in pipeline)."},
            {"region": "Eurozone", "analogue": "ifo Construction", "status": COVERED,
             "match": "ifo Construction Climate/Expectations/Situation", "psrc": "ifo", "cand": "", "notes": "Full ifo construction survey already in pipeline."},
        ],
    },
    {
        "indicator": "Building Permits (SAAR)",
        "pillar": "Growth", "sub_group": "Forward-Looking (Tier 1-2)",
        "cycle": "Leading", "src": "Census Bureau / monthly", "lag": "4 weeks",
        "regions": [
            {"region": "US", "analogue": "US Building Permits", "status": COVERED,
             "match": "PERMIT; US_HOUS1", "psrc": "FRED", "cand": "", "notes": ""},
            {"region": "UK", "analogue": "ONS housing permits / starts", "status": SOURCEABLE,
             "match": "", "psrc": "", "cand": "MHCLG dwelling starts (not on ONS timeseries API)", "notes": "UK new-build starts are published by MHCLG, not via the ONS timeseries (Zebedee) API the fetcher uses. Needs a separate MHCLG source or CMD path. Deferred."},
            {"region": "Eurozone", "analogue": "DE Bauantraege (Destatis)", "status": SOURCEABLE,
             "match": "", "psrc": "", "cand": "Destatis building permits / Eurostat sts_cobp_m - free", "notes": "Not in pipeline; Eurostat construction-permits series free."},
        ],
    },
    {
        "indicator": "Senior Loan Officer Survey (SLOOS)",
        "pillar": "Growth", "sub_group": "Forward-Looking (Tier 1-2)",
        "cycle": "Leading", "src": "Federal Reserve / quarterly", "lag": "Quarterly",
        "regions": [
            {"region": "US", "analogue": "Fed SLOOS net tightening", "status": COVERED,
             "match": "DRTSCILM; DRTSCIS; DRTSCLCC; STDSOTHCONS", "psrc": "FRED", "cand": "", "notes": "Full SLOOS tightening suite in pipeline."},
            {"region": "UK", "analogue": "BoE Credit Conditions Survey", "status": SOURCEABLE,
             "match": "", "psrc": "", "cand": "BoE Credit Conditions Survey - free (published data)", "notes": "Not in pipeline; BoE publishes free, though programmatic access is via spreadsheet, not API."},
            {"region": "Eurozone", "analogue": "ECB Bank Lending Survey", "status": SOURCEABLE,
             "match": "", "psrc": "", "cand": "ECB BLS dataset (free); exact net-% key pending", "notes": "Free via ECB Data Portal, dataflow BLS (10 dims). Net-% series use BLS_ITEM=APP + agg WFNET (e.g. BLS/Q.U2.ALL.APP.E.O.B6.ST.S.WFNET backward / .F6. forward); BLS_ITEM=LEV gives only count aggregations. Canonical 'net % tightening, enterprises, 3m' not yet pinned — deferred to avoid a wrong series."},
            {"region": "Japan", "analogue": "BoJ Tankan lending attitude", "status": PARTIAL,
             "match": "BoJ Tankan DIs", "psrc": "BoJ", "cand": "BoJ Tankan lending-attitude DI - free", "notes": "Tankan business-conditions DIs in pipeline; the dedicated lending-attitude DI is free but not yet fetched."},
        ],
    },
    # ---- 5.1.2 Business-Cycle Confirmers (Tier 3) ----
    {
        "indicator": "ISM Manufacturing PMI",
        "pillar": "Growth", "sub_group": "Business-Cycle Confirmer (Tier 3)",
        "cycle": "Coincident", "src": "ISM / monthly", "lag": "1st business day",
        "regions": [
            {"region": "US", "analogue": "ISM Manufacturing PMI", "status": COVERED,
             "match": "ISM/pmi/pm; US_PMI1", "psrc": "DB.nomics", "cand": "", "notes": ""},
            {"region": "UK", "analogue": "S&P Global / CIPS UK Mfg PMI", "status": PARTIAL,
             "match": "UK_PMI1 (OECD BCI proxy)", "psrc": "OECD", "cand": "S&P Global UK PMI is proprietary", "notes": "Actual PMI paywalled; OECD BCI used as free proxy."},
            {"region": "Eurozone", "analogue": "HCOB Eurozone Mfg PMI", "status": PARTIAL,
             "match": "EU_PMI1 (EC Industry Confidence proxy)", "psrc": "DB.nomics", "cand": "S&P Global EZ PMI is proprietary", "notes": "EC Industry Confidence used as free proxy."},
            {"region": "Japan", "analogue": "Japan Tankan / au Jibun Mfg PMI", "status": COVERED,
             "match": "BoJ Tankan; JP_PMI1", "psrc": "BoJ", "cand": "", "notes": "Tankan large-mfg DI is the free Japan PMI substitute."},
            {"region": "China", "analogue": "Caixin / NBS Mfg PMI", "status": PARTIAL,
             "match": "CN_PMI1; CN_PMI2 (OECD BCI proxies)", "psrc": "OECD", "cand": "NBS PMI free; Caixin proprietary", "notes": "OECD-standardised NBS proxy in pipeline; raw NBS PMI is free but not directly fetched."},
        ],
    },
    {
        "indicator": "ISM New Orders minus Inventories",
        "pillar": "Growth", "sub_group": "Business-Cycle Confirmer (Tier 3)",
        "cycle": "Leading", "src": "ISM (calculated)", "lag": "1st business day",
        "regions": [
            {"region": "US", "analogue": "ISM New Orders - Inventories", "status": COVERED,
             "match": "ISM/neword/in; ISM/inventories/in; US_ISM1", "psrc": "DB.nomics",
             "cand": "", "notes": "Both legs now catalogued (Inventories added, ISM/inventories/in, verified live). Spread = New Orders minus Inventories computable; add the calculator (Bucket D follow-on)."},
            {"region": "UK", "analogue": "UK PMI sub-indices", "status": HARD,
             "match": "", "psrc": "", "cand": "S&P Global PMI sub-indices proprietary", "notes": "Sub-indices paywalled."},
            {"region": "Eurozone", "analogue": "EZ PMI sub-indices", "status": HARD,
             "match": "", "psrc": "", "cand": "S&P Global PMI sub-indices proprietary", "notes": "Sub-indices paywalled."},
        ],
    },
    {
        "indicator": "JP Morgan Global Manufacturing PMI",
        "pillar": "Growth", "sub_group": "Business-Cycle Confirmer (Tier 3)",
        "cycle": "Coincident", "src": "JP Morgan / S&P / monthly", "lag": "1st business day",
        "regions": [
            {"region": "Global", "analogue": "JPM Global Mfg PMI", "status": COVERED,
             "match": "GL_PMI1", "psrc": "pipeline composite", "cand": "JPM/S&P global PMI proprietary", "notes": "Proprietary index; GL_PMI1 is the 4-region equal-weight free substitute (spec calls it out explicitly)."},
        ],
    },
    {
        "indicator": "ISM Services PMI (NMI)",
        "pillar": "Growth", "sub_group": "Business-Cycle Confirmer (Tier 3)",
        "cycle": "Coincident", "src": "ISM / monthly", "lag": "3rd business day",
        "regions": [
            {"region": "US", "analogue": "ISM Services PMI", "status": COVERED,
             "match": "ISM/nm-pmi/pm; US_SVC1", "psrc": "DB.nomics", "cand": "", "notes": ""},
            {"region": "UK", "analogue": "S&P Global UK Services PMI", "status": HARD,
             "match": "", "psrc": "", "cand": "S&P Global UK Services PMI proprietary", "notes": "No clean free UK services-PMI proxy; UK_PMI1 is manufacturing only."},
            {"region": "Eurozone", "analogue": "HCOB EZ Services PMI", "status": PARTIAL,
             "match": "EU_PMI2 (EC Services Confidence proxy)", "psrc": "DB.nomics", "cand": "S&P Global EZ Services PMI proprietary", "notes": "EC Services Confidence used as free proxy."},
        ],
    },
    {
        "indicator": "Philadelphia Fed Manufacturing Survey",
        "pillar": "Growth", "sub_group": "Business-Cycle Confirmer (Tier 3)",
        "cycle": "Coincident", "src": "Philadelphia Fed / monthly", "lag": "3rd Thursday",
        "regions": [
            {"region": "US", "analogue": "Philly Fed Mfg", "status": COVERED,
             "match": "GACDFSA066MSFRBPHI", "psrc": "FRED", "cand": "", "notes": "No regional analogue (spec: none)."},
        ],
    },
    {
        "indicator": "Empire State Manufacturing Survey",
        "pillar": "Growth", "sub_group": "Business-Cycle Confirmer (Tier 3)",
        "cycle": "Coincident", "src": "NY Fed / monthly", "lag": "2nd Monday",
        "regions": [
            {"region": "US", "analogue": "Empire State Mfg", "status": COVERED,
             "match": "GACDISA066MSFRBNY", "psrc": "FRED", "cand": "", "notes": "No regional analogue (spec: none)."},
        ],
    },
    {
        "indicator": "Consumer Confidence (Conference Board)",
        "pillar": "Growth", "sub_group": "Business-Cycle Confirmer (Tier 3)",
        "cycle": "Coincident", "src": "Conference Board / monthly", "lag": "Last Tuesday",
        "regions": [
            {"region": "US", "analogue": "Conference Board Consumer Confidence", "status": PARTIAL,
             "match": "UMCSENT (UMich proxy)", "psrc": "FRED", "cand": "Conference Board CC is proprietary", "notes": "CB Consumer Confidence paywalled; UMich Consumer Sentiment is the free US substitute."},
            {"region": "UK", "analogue": "GfK Consumer Confidence", "status": COVERED,
             "match": "CSCICP02GBM460S", "psrc": "FRED/OECD", "cand": "", "notes": "OECD-based UK consumer confidence in pipeline (GfK itself proprietary)."},
            {"region": "Eurozone", "analogue": "EC Consumer Confidence", "status": COVERED,
             "match": "EU_ESI1; EC sentiment indicators", "psrc": "DB.nomics", "cand": "", "notes": "EC consumer/ESI confidence in pipeline."},
            {"region": "Japan", "analogue": "JP Cabinet Office Consumer Confidence", "status": COVERED,
             "match": "CSCICP02JPM460S; Economy Watchers Survey", "psrc": "FRED / e-Stat", "cand": "", "notes": ""},
        ],
    },
    {
        "indicator": "Initial Jobless Claims",
        "pillar": "Growth", "sub_group": "Business-Cycle Confirmer (Tier 3)",
        "cycle": "Coincident", "src": "Department of Labor / weekly", "lag": "Thursday",
        "regions": [
            {"region": "US", "analogue": "US Initial Claims (4wk MA)", "status": COVERED,
             "match": "IC4WSA; US_JOBS1", "psrc": "FRED", "cand": "", "notes": ""},
            {"region": "UK", "analogue": "ONS Claimant Count", "status": COVERED,
             "match": "employmentandlabourmarket/peoplenotinwork/outofworkbenefits/timeseries/bcjd/unem", "psrc": "ONS", "cand": "", "notes": "Catalogued (Bucket C): ONS Total Claimant Count UK SA (BCJD, dataset 'unem'; 'lms' edition frozen 2017). Verified live. Monthly, not weekly."},
            {"region": "Eurozone", "analogue": "DE/FR/IT unemployment claims", "status": PARTIAL,
             "match": "OECD UNEMPLOYMENT; national unemployment rates", "psrc": "OECD",
             "cand": "BA (DE) registered unemployment - free", "notes": "Unemployment-rate levels in pipeline; high-frequency claims not (varying national frequency)."},
        ],
    },
    # ---- 5.1.3 Coincident Real-Time Gauges (Tier 3-4) ----
    {
        "indicator": "Nonfarm Payrolls (MoM change)",
        "pillar": "Growth", "sub_group": "Coincident Real-Time (Tier 3-4)",
        "cycle": "Lagging", "src": "BLS / monthly", "lag": "1st Friday",
        "regions": [
            {"region": "US", "analogue": "US Nonfarm Payrolls", "status": COVERED,
             "match": "PAYEMS", "psrc": "FRED", "cand": "", "notes": ""},
            {"region": "UK", "analogue": "ONS payrolled employees", "status": SOURCEABLE,
             "match": "UK Employment Rate (related)", "psrc": "ONS", "cand": "ONS PAYE RTI (CMD datasets API, not classic timeseries)", "notes": "PAYE RTI payrolls are not in the classic ONS timeseries (Zebedee) API the fetcher uses — they live in the newer CMD datasets API. Needs a CMD-fetch path, or use LFS employment level as a proxy. Deferred."},
            {"region": "Eurozone", "analogue": "DE/FR employment", "status": PARTIAL,
             "match": "Eurozone Employment (DBnomics); OECD", "psrc": "DB.nomics", "cand": "Eurostat lfsi_emp_m - free", "notes": "Quarterly employment in pipeline; monthly employment-change limited."},
            {"region": "Japan", "analogue": "JP employment", "status": PARTIAL,
             "match": "OECD UNEMPLOYMENT (JP)", "psrc": "OECD", "cand": "e-Stat Labour Force Survey - free", "notes": "Unemployment in pipeline; employment-change not."},
        ],
    },
    {
        "indicator": "Industrial Production (YoY%)",
        "pillar": "Growth", "sub_group": "Coincident Real-Time (Tier 3-4)",
        "cycle": "Coincident", "src": "Federal Reserve / monthly", "lag": "~2 weeks",
        "regions": [
            {"region": "US", "analogue": "US IP", "status": COVERED, "match": "INDPRO", "psrc": "FRED", "cand": "", "notes": ""},
            {"region": "UK", "analogue": "ONS Index of Production", "status": COVERED, "match": "UK Index of Production (B-E)", "psrc": "ONS", "cand": "", "notes": ""},
            {"region": "Eurozone", "analogue": "Eurostat IPI", "status": COVERED, "match": "Eurozone IP; Germany IP", "psrc": "DB.nomics", "cand": "", "notes": ""},
            {"region": "Japan", "analogue": "METI IIP", "status": COVERED, "match": "JPNPROINDMISMEI", "psrc": "FRED", "cand": "", "notes": ""},
            {"region": "China", "analogue": "NBS IP", "status": COVERED, "match": "CHNPRINTO01IXPYM", "psrc": "FRED", "cand": "", "notes": ""},
        ],
    },
    {
        "indicator": "Retail Sales (MoM%, ex autos)",
        "pillar": "Growth", "sub_group": "Coincident Real-Time (Tier 3-4)",
        "cycle": "Coincident", "src": "Census Bureau / monthly", "lag": "~2 weeks",
        "regions": [
            {"region": "US", "analogue": "US Retail Sales ex-autos", "status": COVERED, "match": "RSXFS; RSFSXMV (control)", "psrc": "FRED", "cand": "", "notes": ""},
            {"region": "UK", "analogue": "ONS Retail Sales", "status": COVERED, "match": "UK Retail Sales Index (Volume)", "psrc": "ONS", "cand": "", "notes": ""},
            {"region": "Eurozone", "analogue": "Eurostat retail trade", "status": COVERED, "match": "Eurozone Retail Sales Volume", "psrc": "DB.nomics", "cand": "", "notes": ""},
            {"region": "Japan", "analogue": "METI retail", "status": COVERED, "match": "Japan Retail Sales (METI)", "psrc": "e-Stat", "cand": "", "notes": ""},
        ],
    },
    {
        "indicator": "Real GDP (advance estimate)",
        "pillar": "Growth", "sub_group": "Coincident Real-Time (Tier 3-4)",
        "cycle": "Lagging", "src": "BEA / quarterly", "lag": "~4 weeks",
        "regions": [
            {"region": "US", "analogue": "US Real GDP", "status": COVERED, "match": "IMF NGDP_RPCH; JST USA|gdp; nowcasts", "psrc": "IMF / JST", "cand": "BEA GDP (FRED GDPC1) - free", "notes": "Annual/long-run GDP in pipeline; quarterly advance via FRED GDPC1 free (nowcasts US_GDPNOW1/US_NOWCAST1 cover real-time)."},
            {"region": "UK", "analogue": "ONS GDP", "status": COVERED, "match": "UK Monthly Real GDP; UK_NOWCAST1", "psrc": "ONS", "cand": "", "notes": ""},
            {"region": "Eurozone", "analogue": "Eurostat GDP", "status": COVERED, "match": "IMF NGDP; EU_NOWCAST1", "psrc": "IMF / DB.nomics", "cand": "Eurostat namq_10_gdp - free", "notes": ""},
            {"region": "Japan", "analogue": "Cabinet Office GDP", "status": COVERED, "match": "IMF NGDP; JST; JP_NOWCAST1", "psrc": "IMF / JST", "cand": "", "notes": ""},
            {"region": "China", "analogue": "NBS GDP", "status": PARTIAL, "match": "IMF NGDP_RPCH (annual)", "psrc": "IMF", "cand": "NBS quarterly GDP - free", "notes": "Only annual IMF GDP in pipeline; quarterly NBS free but not fetched."},
        ],
    },
    {
        "indicator": "Atlanta Fed GDPNow",
        "pillar": "Growth", "sub_group": "Coincident Real-Time (Tier 3-4)",
        "cycle": "Coincident", "src": "Atlanta Fed / continuous", "lag": "Real-time",
        "regions": [
            {"region": "US", "analogue": "Atlanta Fed GDPNow", "status": COVERED, "match": "gdpnow_us_qoq_saar; US_GDPNOW1; US_NOWCAST1 (NY Fed)", "psrc": "AtlantaFed / NYFed", "cand": "", "notes": ""},
            {"region": "UK", "analogue": "ONS monthly GDP", "status": COVERED, "match": "UK_NOWCAST1", "psrc": "ONS", "cand": "", "notes": "ONS monthly GDP is the UK real-time growth signal."},
            {"region": "Eurozone", "analogue": "CEPR Eurocoin", "status": COVERED, "match": "EU_NOWCAST1", "psrc": "pipeline composite", "cand": "Eurocoin (CEPR) - free", "notes": "EU nowcast composite in pipeline as Eurocoin substitute."},
        ],
    },
    {
        "indicator": "Chicago Fed NFCI",
        "pillar": "Growth", "sub_group": "Coincident Real-Time (Tier 3-4)",
        "cycle": "Leading", "src": "Chicago Fed / weekly", "lag": "Friday",
        "regions": [
            {"region": "US", "analogue": "Chicago Fed NFCI", "status": COVERED, "match": "NFCI", "psrc": "FRED", "cand": "", "notes": ""},
            {"region": "UK", "analogue": "BoE FCI", "status": HARD, "match": "", "psrc": "", "cand": "BoE FCI not freely programmatic", "notes": "BoE FCI published only occasionally; no clean free feed."},
            {"region": "Eurozone", "analogue": "ECB CISS", "status": COVERED, "match": "CISS/D.U2.Z0Z.4F.EC.SS_CIN.IDX", "psrc": "ECB", "cand": "", "notes": "Catalogued (Bucket C), ECB CISS, verified live. Shared by the GS-FCI and Bloomberg-FCI EZ rows."},
            {"region": "Japan", "analogue": "(none clean)", "status": HARD, "match": "", "psrc": "", "cand": "No clean free JP FCI", "notes": "Spec: no clean JP analogue."},
            {"region": "China", "analogue": "(none clean)", "status": HARD, "match": "", "psrc": "", "cand": "No clean free CN FCI", "notes": "Spec: no clean CN analogue."},
        ],
    },
    # ============================ 5.2 INFLATION ============================
    {
        "indicator": "CPI Headline (YoY%)",
        "pillar": "Inflation", "sub_group": "Official Inflation",
        "cycle": "Lagging", "src": "BLS / monthly", "lag": "~2 weeks",
        "regions": [
            {"region": "US", "analogue": "US CPI", "status": COVERED, "match": "CUSR0000SA0; US_INFL1", "psrc": "BLS", "cand": "", "notes": ""},
            {"region": "UK", "analogue": "ONS CPI", "status": COVERED, "match": "UK CPI (ONS/FRED); UK_INFL1", "psrc": "ONS / FRED", "cand": "", "notes": ""},
            {"region": "Eurozone", "analogue": "Eurostat HICP", "status": COVERED, "match": "Eurozone HICP; EU_INFL1", "psrc": "DB.nomics", "cand": "", "notes": ""},
            {"region": "Japan", "analogue": "MIC CPI", "status": COVERED, "match": "JP CPI; JP_INFL1", "psrc": "World Bank / JST", "cand": "", "notes": ""},
            {"region": "China", "analogue": "NBS CPI", "status": COVERED, "match": "CHNCPIALLMINMEI; CN_INFL1", "psrc": "FRED", "cand": "", "notes": ""},
        ],
    },
    {
        "indicator": "Core CPI (ex food & energy)",
        "pillar": "Inflation", "sub_group": "Official Inflation",
        "cycle": "Lagging", "src": "BLS / monthly", "lag": "~2 weeks",
        "regions": [
            {"region": "US", "analogue": "US Core CPI", "status": COVERED, "match": "CUSR0000SA0L1E", "psrc": "BLS", "cand": "", "notes": ""},
            {"region": "UK", "analogue": "ONS Core CPI", "status": COVERED, "match": "UK Core CPI Annual Rate", "psrc": "ONS", "cand": "", "notes": ""},
            {"region": "Eurozone", "analogue": "Core HICP", "status": COVERED, "match": "Eurozone Core HICP", "psrc": "DB.nomics", "cand": "", "notes": ""},
            {"region": "Japan", "analogue": "JP Core CPI", "status": COVERED, "match": "Japan Core CPI YoY", "psrc": "DB.nomics", "cand": "", "notes": ""},
            {"region": "China", "analogue": "NBS Core CPI", "status": PARTIAL, "match": "CN_INFL1 (CPI+PPI blend)", "psrc": "FRED", "cand": "NBS core CPI - free (limited history)", "notes": "China core CPI thin; CN_INFL1 blends headline CPI and PPI instead."},
        ],
    },
    {
        "indicator": "PCE Deflator (Core)",
        "pillar": "Inflation", "sub_group": "Official Inflation",
        "cycle": "Lagging", "src": "BEA / monthly", "lag": "~5 weeks",
        "regions": [
            {"region": "US", "analogue": "US Core PCE", "status": COVERED, "match": "PCEPILFE", "psrc": "FRED", "cand": "", "notes": "US-specific Fed measure; no regional analogue (spec: none)."},
        ],
    },
    {
        "indicator": "Trimmed Mean / Median CPI",
        "pillar": "Inflation", "sub_group": "Official Inflation",
        "cycle": "Lagging", "src": "Cleveland / Dallas Fed", "lag": "~2 weeks",
        "regions": [
            {"region": "US", "analogue": "Cleveland Median / Trimmed-Mean CPI", "status": COVERED,
             "match": "MEDCPIM158SFRBCLE; TRMMEANCPIM158SFRBCLE; PCETRIM12M159SFRBDAL", "psrc": "FRED", "cand": "", "notes": "Catalogued (Bucket A): Cleveland median + 16% trimmed-mean CPI and Dallas trimmed PCE. VERIFY ids on first fetch. No regional analogue (spec: none)."},
        ],
    },
    {
        "indicator": "PPI Final Demand (YoY%)",
        "pillar": "Inflation", "sub_group": "Official Inflation",
        "cycle": "Leading", "src": "BLS / monthly", "lag": "~2 weeks",
        "regions": [
            {"region": "US", "analogue": "US PPI", "status": COVERED, "match": "PPIACO (All Commodities)", "psrc": "FRED", "cand": "FRED PPIFIS (Final Demand) - free", "notes": "All-Commodities PPI in pipeline; Final-Demand variant free on FRED if exact definition needed."},
            {"region": "UK", "analogue": "ONS PPI", "status": COVERED, "match": "economy/inflationandpriceindices/timeseries/gd6y/ppi", "psrc": "ONS", "cand": "", "notes": "Catalogued (Bucket C): ONS PPI output, all manufactured products (GD6Y, dataset 'ppi'; mm22 edition frozen 2020). Index; YoY downstream. Verified live."},
            {"region": "Eurozone", "analogue": "Eurostat PPI", "status": SOURCEABLE, "match": "", "psrc": "", "cand": "Eurostat sts_inpp_m - free", "notes": "Not in pipeline; Eurostat PPI free."},
            {"region": "Japan", "analogue": "BoJ PPI", "status": COVERED, "match": "Japan PPI (All Commodities); Japan Services PPI", "psrc": "BoJ", "cand": "", "notes": ""},
            {"region": "China", "analogue": "NBS PPI", "status": COVERED, "match": "CHNPIEATI01GYM", "psrc": "FRED", "cand": "", "notes": ""},
        ],
    },
    {
        "indicator": "TIPS 5-year Breakeven Rate",
        "pillar": "Inflation", "sub_group": "Market-Implied Expectations",
        "cycle": "Leading", "src": "FRED / daily", "lag": "Real-time",
        "regions": [
            {"region": "US", "analogue": "US 5y breakeven", "status": COVERED, "match": "T5YIE", "psrc": "FRED", "cand": "", "notes": ""},
            {"region": "UK", "analogue": "UK linker breakeven", "status": COVERED, "match": "UK_R2 (gilt-linker breakeven)", "psrc": "pipeline composite", "cand": "", "notes": "5y/10y not split, but UK breakeven covered."},
            {"region": "Eurozone", "analogue": "OATei / Bundei breakeven", "status": SOURCEABLE, "match": "", "psrc": "", "cand": "ECB / Eurostat HICP-linked yields - free (limited)", "notes": "Not in pipeline; EZ linker breakevens partially free via ECB."},
        ],
    },
    {
        "indicator": "TIPS 10-year Breakeven Rate",
        "pillar": "Inflation", "sub_group": "Market-Implied Expectations",
        "cycle": "Leading", "src": "FRED / daily", "lag": "Real-time",
        "regions": [
            {"region": "US", "analogue": "US 10y breakeven", "status": COVERED, "match": "T10YIE; US_R4", "psrc": "FRED", "cand": "", "notes": ""},
            {"region": "UK", "analogue": "UK 10y breakeven", "status": COVERED, "match": "UK_R2", "psrc": "pipeline composite", "cand": "", "notes": ""},
            {"region": "Eurozone", "analogue": "EZ 10y inflation swap", "status": HARD, "match": "", "psrc": "", "cand": "Inflation swaps proprietary; ECB linker breakeven partial", "notes": "Swap proprietary; ECB linker-implied breakeven a partial free substitute."},
            {"region": "Japan", "analogue": "JP 10y breakeven", "status": HARD, "match": "", "psrc": "", "cand": "JP breakevens thin / proprietary", "notes": "JGBi market thin; limited free data."},
        ],
    },
    {
        "indicator": "5y5y Forward Inflation Swap",
        "pillar": "Inflation", "sub_group": "Market-Implied Expectations",
        "cycle": "Leading", "src": "Bloomberg / daily", "lag": "Real-time",
        "regions": [
            {"region": "US", "analogue": "US 5y5y forward inflation", "status": COVERED, "match": "T5YIFR; US_INFEXP1", "psrc": "FRED", "cand": "", "notes": "FRED publishes US 5y5y forward (T5YIFR); proprietary swap not needed."},
            {"region": "UK", "analogue": "UK 5y5y", "status": HARD, "match": "", "psrc": "", "cand": "Bloomberg inflation swap proprietary", "notes": "No free UK 5y5y; derivable approximation from linker curve only."},
            {"region": "Eurozone", "analogue": "EZ 5y5y", "status": HARD, "match": "", "psrc": "", "cand": "No clean free ECB 5y5y ILS", "notes": "CORRECTION (live ECB API check): the ECB FM dataflow carries only nominal yields, money-market rates and equity indices - no inflation-linked-swap series. EZ 5y5y is proprietary (Bloomberg), like UK/JP. Earlier 'sourceable via ECB' was incorrect."},
            {"region": "Japan", "analogue": "JP 5y5y", "status": HARD, "match": "", "psrc": "", "cand": "Proprietary", "notes": ""},
        ],
    },
    {
        "indicator": "University of Michigan Inflation Expectations (5-10y)",
        "pillar": "Inflation", "sub_group": "Survey Expectations",
        "cycle": "Lagging", "src": "Univ. Michigan / monthly", "lag": "Mid-month prelim",
        "regions": [
            {"region": "US", "analogue": "UMich 5-10y inflation expectations", "status": COVERED,
             "match": "MICH5YR; MICH (1y)", "psrc": "FRED", "cand": "", "notes": "5-10y catalogued (Bucket A, MICH5YR); 1y MICH already present. VERIFY id on first fetch."},
            {"region": "UK", "analogue": "BoE Inflation Attitudes Survey", "status": SOURCEABLE,
             "match": "", "psrc": "", "cand": "BoE/Ipsos Inflation Attitudes Survey - free (quarterly)", "notes": "Not in pipeline; BoE publishes free."},
            {"region": "Eurozone", "analogue": "ECB Survey of Consumer Expectations", "status": COVERED,
             "match": "CES/M.Z18.ALL.T.C1120.NUM_VAR.WM", "psrc": "ECB", "cand": "", "notes": "Catalogued (Bucket C): ECB CES euro-area 12m-ahead inflation expectations (weighted median), verified live. 3y-ahead horizon also in CES if a longer anchor is wanted."},
        ],
    },
    {
        "indicator": "ISM / PMI Prices Paid",
        "pillar": "Inflation", "sub_group": "Inflation-Adjacent / Commodity",
        "cycle": "Leading", "src": "ISM / monthly", "lag": "1st business day",
        "regions": [
            {"region": "US", "analogue": "ISM Manufacturing Prices Paid", "status": COVERED,
             "match": "ISM/prices/in", "psrc": "DB.nomics", "cand": "", "notes": "Catalogued (Bucket C), ISM/prices/in, verified live."},
            {"region": "UK", "analogue": "UK PMI Prices Paid", "status": HARD, "match": "", "psrc": "", "cand": "S&P Global PMI sub-index proprietary", "notes": ""},
            {"region": "Eurozone", "analogue": "EZ PMI Prices Paid", "status": HARD, "match": "", "psrc": "", "cand": "S&P Global PMI sub-index proprietary", "notes": ""},
        ],
    },
    {
        "indicator": "CRB Raw Industrials Index",
        "pillar": "Inflation", "sub_group": "Inflation-Adjacent / Commodity",
        "cycle": "Leading", "src": "Bloomberg / daily", "lag": "Real-time",
        "regions": [
            {"region": "Global", "analogue": "CRB Raw Industrials", "status": PARTIAL,
             "match": "PALLFNFINDEXM (IMF non-fuel commodity index); copper/aluminium/iron ore", "psrc": "FRED",
             "cand": "CRB index proprietary; IMF/World Bank industrial-metal indices - free", "notes": "CRB proprietary; pipeline carries IMF non-fuel commodity index and individual industrial metals as a free ex-energy proxy."},
        ],
    },
    {
        "indicator": "Brent Crude Oil Price",
        "pillar": "Inflation", "sub_group": "Inflation-Adjacent / Commodity",
        "cycle": "Coincident", "src": "Bloomberg / daily", "lag": "Real-time",
        "regions": [
            {"region": "Global", "analogue": "Brent crude", "status": COVERED,
             "match": "POILBREUSDM (Brent); WTISPLC (WTI)", "psrc": "FRED", "cand": "", "notes": ""},
        ],
    },
    # ====================== 5.3 FINANCIAL CONDITIONS ======================
    {
        "indicator": "HY Credit Spreads (ICE BofA OAS)",
        "pillar": "Financial Conditions", "sub_group": "Credit",
        "cycle": "Leading", "src": "FRED / daily", "lag": "Real-time",
        "regions": [
            {"region": "US", "analogue": "US HY OAS", "status": COVERED, "match": "BAMLH0A0HYM2; US_Cr2", "psrc": "FRED", "cand": "", "notes": "5-regime classifier US_Cr2."},
            {"region": "Eurozone", "analogue": "Euro HY OAS", "status": COVERED, "match": "BAMLHE00EHYIOAS; EU_Cr2", "psrc": "FRED", "cand": "", "notes": ""},
            {"region": "UK", "analogue": "GBP HY", "status": PARTIAL, "match": "UK_Cr1 (GBP corp vs gilt)", "psrc": "pipeline composite", "cand": "No standalone free GBP HY OAS", "notes": "GBP corporate-vs-gilt proxy in pipeline; no clean free GBP HY OAS series."},
            {"region": "Asia", "analogue": "Asia HY", "status": COVERED, "match": "BAMLEMRACRPIASIAOAS (EM Asia Corp OAS); BAMLEMCBPIOAS (EM Corp); BAMLEM2BRRBBBCRPIOAS (EM BBB)", "psrc": "FRED (index_library)", "cand": "", "notes": "ICE BofA EM Asia Corporate OAS already in the market-data index library."},
        ],
    },
    {
        "indicator": "IG Credit Spreads (OAS)",
        "pillar": "Financial Conditions", "sub_group": "Credit",
        "cycle": "Leading", "src": "FRED / daily", "lag": "Real-time",
        "regions": [
            {"region": "US", "analogue": "US IG OAS", "status": COVERED, "match": "BAMLC0A0CM; US_Cr1", "psrc": "FRED", "cand": "", "notes": ""},
            {"region": "Eurozone", "analogue": "Euro IG OAS", "status": COVERED, "match": "BAMLER00ICOAS; EU_Cr1 (proxy)", "psrc": "FRED", "cand": "", "notes": "Euro Corp OAS catalogued (Bucket A, BAMLER00ICOAS). VERIFY id on first fetch."},
            {"region": "UK", "analogue": "GBP IG OAS", "status": HARD, "match": "UK_Cr1 (proxy)", "psrc": "pipeline composite", "cand": "No clean free GBP IG OAS", "notes": ""},
            {"region": "Japan", "analogue": "JPY IG OAS", "status": HARD, "match": "", "psrc": "", "cand": "Proprietary", "notes": "EM Asia Corp OAS (in library) is broad-EM, not JP-specific."},
            {"region": "China", "analogue": "CNY IG OAS", "status": PARTIAL, "match": "BAMLEMRACRPIASIAOAS (EM Asia Corp OAS); BAMLEMCBPIOAS (EM Corp)", "psrc": "FRED (index_library)", "cand": "", "notes": "Broad EM-Asia corporate OAS in library proxies CN credit; no clean standalone CNY IG OAS."},
        ],
    },
    {
        "indicator": "VIX (CBOE Volatility Index)",
        "pillar": "Financial Conditions", "sub_group": "Volatility",
        "cycle": "Coincident", "src": "CBOE / daily", "lag": "Real-time",
        "regions": [
            {"region": "US", "analogue": "VIX", "status": COVERED, "match": "^VIX, ^VIX3M, ^VIX9D, ^VVIX, ^SKEW (index_library); US_V1", "psrc": "yfinance (index_library)", "cand": "", "notes": "Full VIX term-structure suite in the market-data library; US_V1 term-structure composite."},
            {"region": "Eurozone", "analogue": "VSTOXX (V2X) / VXEFA", "status": COVERED, "match": "^VXEFA (CBOE EAFE Volatility)", "psrc": "yfinance (index_library)", "cand": "STOXX VSTOXX/V2X also free", "notes": "CBOE EAFE vol (^VXEFA) in library is the developed-Europe/Japan equity-vol gauge; dedicated VSTOXX free from STOXX if EZ-specific needed."},
            {"region": "UK", "analogue": "VFTSE / VXEFA", "status": PARTIAL, "match": "^VXEFA (EAFE incl. UK)", "psrc": "yfinance (index_library)", "cand": "VFTSE discontinued", "notes": "UK is inside the EAFE vol index (^VXEFA) already in library; no clean UK-specific equity-vol index (VFTSE discontinued)."},
            {"region": "Asia", "analogue": "VXEEM / Nikkei VI / India VIX", "status": COVERED, "match": "^VXEEM (CBOE EM Volatility); ^VXEFA (developed Asia/Japan)", "psrc": "yfinance (index_library)", "cand": "India VIX, Nikkei VI, VHSI also free", "notes": "CBOE EM vol (^VXEEM) covers EM/China; EAFE vol (^VXEFA) covers developed Asia/Japan - both in library."},
        ],
    },
    {
        "indicator": "MOVE Index (US Treasury Volatility)",
        "pillar": "Financial Conditions", "sub_group": "Volatility",
        "cycle": "Coincident", "src": "Bloomberg / daily", "lag": "Real-time",
        "regions": [
            {"region": "US", "analogue": "MOVE", "status": COVERED, "match": "^MOVE (index_library); US_V2 (MOVE / VIX)", "psrc": "yfinance (index_library)", "cand": "", "notes": "MOVE index directly in the market-data library (^MOVE) and consumed via US_V2."},
            {"region": "Global", "analogue": "Regional bond-vol", "status": HARD, "match": "", "psrc": "", "cand": "No free regional bond-vol analogue", "notes": "Spec: less-developed regional analogues; none freely available."},
        ],
    },
    {
        "indicator": "US Dollar Index (DXY)",
        "pillar": "Financial Conditions", "sub_group": "FX",
        "cycle": "Coincident", "src": "Bloomberg / daily", "lag": "Real-time",
        "regions": [
            {"region": "Global", "analogue": "DXY", "status": COVERED, "match": "DX-Y.NYB (index_library); FX_CMD2 (dollar)", "psrc": "yfinance (index_library)", "cand": "", "notes": "DXY index directly in the market-data library (DX-Y.NYB); FRED DTWEXAFEGS is a free fallback."},
        ],
    },
    {
        "indicator": "Goldman Sachs FCI (US)",
        "pillar": "Financial Conditions", "sub_group": "Composite FCI",
        "cycle": "Leading", "src": "Goldman Sachs / daily", "lag": "Real-time",
        "regions": [
            {"region": "US", "analogue": "GS US FCI", "status": HARD, "match": "NFCI (free proxy)", "psrc": "FRED", "cand": "GS FCI proprietary; free proxy = Chicago Fed NFCI / OFR FCI", "notes": "GS FCI paywalled; Chicago Fed NFCI (in pipeline) and OFR FCI are the free substitutes."},
            {"region": "UK", "analogue": "GS UK FCI", "status": HARD, "match": "", "psrc": "", "cand": "Proprietary; no clean free UK FCI", "notes": ""},
            {"region": "Eurozone", "analogue": "GS EZ FCI", "status": COVERED, "match": "CISS/D.U2.Z0Z.4F.EC.SS_CIN.IDX (ECB CISS)", "psrc": "ECB", "cand": "", "notes": "ECB CISS catalogued (Bucket C) as the free EZ financial-conditions substitute."},
            {"region": "Japan", "analogue": "GS JP FCI", "status": HARD, "match": "", "psrc": "", "cand": "Proprietary", "notes": ""},
        ],
    },
    {
        "indicator": "Bloomberg US FCI",
        "pillar": "Financial Conditions", "sub_group": "Composite FCI",
        "cycle": "Leading", "src": "Bloomberg / daily", "lag": "Real-time",
        "regions": [
            {"region": "US", "analogue": "Bloomberg US FCI", "status": HARD, "match": "NFCI (free proxy)", "psrc": "FRED", "cand": "Bloomberg FCI proprietary; free proxy = NFCI / OFR FCI", "notes": "Proprietary; NFCI in pipeline is the free substitute."},
            {"region": "UK", "analogue": "Bloomberg UK FCI", "status": HARD, "match": "", "psrc": "", "cand": "Proprietary", "notes": ""},
            {"region": "Eurozone", "analogue": "Bloomberg EZ FCI", "status": COVERED, "match": "CISS/D.U2.Z0Z.4F.EC.SS_CIN.IDX (ECB CISS)", "psrc": "ECB", "cand": "", "notes": "ECB CISS catalogued (Bucket C) as the free EZ financial-conditions substitute."},
        ],
    },
    {
        "indicator": "EM Currencies (EMFX Index)",
        "pillar": "Financial Conditions", "sub_group": "FX",
        "cycle": "Coincident", "src": "Bloomberg / daily", "lag": "Real-time",
        "regions": [
            {"region": "Global", "analogue": "EMFX index", "status": COVERED, "match": "FX_EM1 (EM basket); USD/CNY, USD/INR, USD/KRW, USD/TWD (index_library); FX_1; FX_2; FX_CN1", "psrc": "yfinance (index_library) / composite", "cand": "JPM EMFX proprietary", "notes": "Proprietary index; pipeline builds a free EM-currency basket (FX_EM1) from the FX pairs in the market-data library."},
        ],
    },
    # ====================== 5.4 MONETARY POLICY ======================
    {
        "indicator": "Federal Funds Rate (effective)",
        "pillar": "Monetary Policy", "sub_group": "Policy Rate",
        "cycle": "Leading", "src": "Fed / 8 meetings per year", "lag": "Same day",
        "regions": [
            {"region": "US", "analogue": "Fed Funds Rate", "status": COVERED, "match": "FEDFUNDS", "psrc": "FRED", "cand": "", "notes": ""},
            {"region": "UK", "analogue": "BoE Bank Rate", "status": COVERED, "match": "IUDBEDR", "psrc": "BoE", "cand": "", "notes": ""},
            {"region": "Eurozone", "analogue": "ECB Deposit Rate", "status": COVERED, "match": "ECB Deposit Facility Rate", "psrc": "ECB", "cand": "", "notes": ""},
            {"region": "Japan", "analogue": "BoJ Policy Rate", "status": COVERED, "match": "BoJ Policy Rate (overnight call)", "psrc": "BoJ", "cand": "", "notes": ""},
            {"region": "China", "analogue": "PBoC LPR", "status": PARTIAL, "match": "PBoC Policy Rate (IMF IFS)", "psrc": "DB.nomics", "cand": "PBoC 1y LPR - free", "notes": "PBoC policy rate in pipeline; the specific 1y LPR is free but not the exact series fetched."},
        ],
    },
    {
        "indicator": "Real Federal Funds Rate",
        "pillar": "Monetary Policy", "sub_group": "Policy Rate (derived)",
        "cycle": "Leading", "src": "Calculated / monthly", "lag": "Monthly",
        "regions": [
            {"region": "US", "analogue": "Real FFR (FFR - Core PCE)", "status": COVERED, "match": "FEDFUNDS - PCEPILFE; US_R5 (real yield)", "psrc": "FRED", "cand": "", "notes": "Derivable from series in pipeline."},
            {"region": "UK", "analogue": "Real Bank Rate", "status": COVERED, "match": "IUDBEDR - UK Core CPI", "psrc": "BoE / ONS", "cand": "", "notes": "Derivable."},
            {"region": "Eurozone", "analogue": "Real ECB rate", "status": COVERED, "match": "ECB Deposit Rate - Core HICP", "psrc": "ECB / DB.nomics", "cand": "", "notes": "Derivable."},
            {"region": "Japan", "analogue": "Real BoJ rate", "status": COVERED, "match": "BoJ Policy Rate - JP Core CPI", "psrc": "BoJ / DB.nomics", "cand": "", "notes": "Derivable."},
            {"region": "China", "analogue": "Real PBoC rate", "status": PARTIAL, "match": "PBoC Policy Rate - CN CPI", "psrc": "DB.nomics / FRED", "cand": "", "notes": "Derivable from policy rate + CPI; core-CPI deflator weaker."},
        ],
    },
    {
        "indicator": "Fed Funds Futures (implied path)",
        "pillar": "Monetary Policy", "sub_group": "Market-Implied Policy",
        "cycle": "Leading", "src": "CME / daily", "lag": "Real-time",
        "regions": [
            {"region": "US", "analogue": "Fed Funds Futures / FedWatch", "status": HARD, "match": "", "psrc": "", "cand": "CME futures proprietary; FedWatch not programmatic free", "notes": "No clean free implied-path feed; CME data licensed."},
            {"region": "UK", "analogue": "SONIA futures path", "status": HARD, "match": "", "psrc": "", "cand": "ICE SONIA futures proprietary", "notes": ""},
            {"region": "Eurozone", "analogue": "ESTR futures path", "status": HARD, "match": "", "psrc": "", "cand": "ESTR/Euribor futures proprietary", "notes": ""},
        ],
    },
    {
        "indicator": "Taylor Rule Gap",
        "pillar": "Monetary Policy", "sub_group": "Policy Stance (derived)",
        "cycle": "Leading", "src": "Calculated / quarterly", "lag": "Quarterly",
        "regions": [
            {"region": "US", "analogue": "US Taylor Rule gap", "status": SOURCEABLE, "match": "Inputs present (FFR, CPI, output gap)", "psrc": "FRED", "cand": "Derivable; Atlanta Fed Taylor Rule utility - free", "notes": "Not currently computed; all inputs in pipeline, so derivable."},
            {"region": "UK", "analogue": "UK Taylor Rule gap", "status": SOURCEABLE, "match": "Inputs partially present", "psrc": "BoE / ONS", "cand": "Derivable", "notes": "Derivable from Bank Rate, CPI, output gap."},
            {"region": "Eurozone", "analogue": "EZ Taylor Rule gap", "status": SOURCEABLE, "match": "Inputs partially present", "psrc": "ECB / Eurostat", "cand": "Derivable", "notes": "Derivable."},
            {"region": "Japan", "analogue": "JP Taylor Rule gap", "status": SOURCEABLE, "match": "Inputs partially present", "psrc": "BoJ", "cand": "Derivable", "notes": "Derivable."},
            {"region": "China", "analogue": "CN Taylor Rule gap", "status": SOURCEABLE, "match": "Inputs partially present", "psrc": "PBoC / NBS", "cand": "Derivable (output gap weak)", "notes": "Derivable but China output-gap estimate is weak."},
        ],
    },
    {
        "indicator": "Global Monetary Policy Tracker",
        "pillar": "Monetary Policy", "sub_group": "Global Stance",
        "cycle": "Coincident", "src": "JP Morgan / BIS / monthly", "lag": "Monthly",
        "regions": [
            {"region": "Global", "analogue": "Net % central banks hiking vs cutting", "status": SOURCEABLE,
             "match": "Policy rates for US/UK/EZ/JP/CN/CA partly present", "psrc": "BIS / national CBs",
             "cand": "Constructable from BIS central-bank policy rates - free", "notes": "JPM/BIS tracker proprietary, but constructable from the free BIS policy-rate panel already partially in pipeline."},
        ],
    },
    # ==================== 5.5 RISK-APPETITE / SENTIMENT ====================
    {
        "indicator": "HY-IG Spread Ratio",
        "pillar": "Risk-Appetite / Sentiment", "sub_group": "GS Risk-Appetite Proxy",
        "cycle": "Leading", "src": "Derived (pipeline) / daily", "lag": "Real-time",
        "regions": [
            {"region": "US", "analogue": "HY-IG ratio (z-scored)", "status": COVERED, "match": "US_Cr3 (HY-IG); US_Cr1; US_Cr2", "psrc": "FRED", "cand": "", "notes": "Derivable from HY and IG OAS already in pipeline."},
        ],
    },
    {
        "indicator": "Equity Risk Premium (earnings yield minus 10y real yield)",
        "pillar": "Risk-Appetite / Sentiment", "sub_group": "GS Risk-Appetite Proxy",
        "cycle": "Coincident", "src": "Derived (pipeline) / daily", "lag": "Real-time",
        "regions": [
            {"region": "US", "analogue": "US ERP (CAPE inverse vs real yield)", "status": COVERED, "match": "Shiller CAPE / Earnings + DFII10 (10y real yield)", "psrc": "Shiller / FRED", "cand": "", "notes": "Derivable; Shiller earnings yield and TIPS real yield both in pipeline."},
        ],
    },
    {
        "indicator": "VIX Term-Structure Slope",
        "pillar": "Risk-Appetite / Sentiment", "sub_group": "GS Risk-Appetite Proxy",
        "cycle": "Coincident", "src": "Derived (pipeline) / daily", "lag": "Real-time",
        "regions": [
            {"region": "US", "analogue": "VIX9D/VIX3M/spot term structure", "status": COVERED, "match": "US_V1 (VIX3M - VIX)", "psrc": "market data", "cand": "", "notes": "Term-structure composite in pipeline; VIX9D extension free from CBOE."},
        ],
    },
]


def flatten(data):
    rows = []
    for ind in data:
        for r in ind["regions"]:
            rows.append({
                "indicator": ind["indicator"],
                "pillar": ind["pillar"],
                "sub_group": ind["sub_group"],
                "cycle_timing_prior": ind["cycle"],
                "region": r["region"],
                "regional_analogue": r["analogue"],
                "requested_source_freq": ind["src"],
                "lag": ind["lag"],
                "status": r["status"],
                "pipeline_match": r.get("match", ""),
                "pipeline_source": r.get("psrc", ""),
                "candidate_free_source": r.get("cand", ""),
                "notes": r.get("notes", ""),
            })
    return rows


def write_csv(rows, path):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def md_escape(s):
    return (s or "").replace("|", "\\|").replace("\n", " ")


def write_md(rows, path):
    # Summary counts
    from collections import Counter
    status_counts = Counter(r["status"] for r in rows)
    pillar_status = {}
    for r in rows:
        pillar_status.setdefault(r["pillar"], Counter())[r["status"]] += 1

    lines = []
    lines.append("# Regime-AA Indicator Coverage Map")
    lines.append("")
    lines.append("Generated by `build_indicator_coverage_map.py`. Cross-references every "
                 "indicator requested in `regime-aa-indicator-req.md` (§5), broken out "
                 "per region, against the data pipeline's actual coverage "
                 "(`data/macro_economic.csv`, 296 base series; "
                 "`data/macro_indicator_library.csv` / `data/macro_market.csv`, 107 "
                 "composites; `data/index_library.csv`, 401 market-data instruments "
                 "covering equities, bonds, credit OAS, rates, FX and volatility).")
    lines.append("")
    lines.append("**One row per (indicator × region).** Status tells you whether the "
                 "indicator is already in the pipeline, missing but free-sourceable, or "
                 "missing and hard to source.")
    lines.append("")
    lines.append("### Status vocabulary")
    lines.append("")
    lines.append("| Status | Meaning |")
    lines.append("|---|---|")
    lines.append("| **Covered** | Pipeline carries the series (or a direct derivation of series it carries) for that region |")
    lines.append("| **Partial** | Pipeline carries a proxy / related series, not the exact instrument, or only part of the regional breadth |")
    lines.append("| **Missing-Sourceable** | Not in pipeline, but a free / public source exists |")
    lines.append("| **Missing-Hard** | Not in pipeline; only proprietary, or no reliable free source |")
    lines.append("| **Accepted-Gap** | Explicitly accepted in the spec (no free source for that region) |")
    lines.append("")
    lines.append("### Coverage summary")
    lines.append("")
    lines.append("| Status | Count |")
    lines.append("|---|---|")
    for s in [COVERED, PARTIAL, SOURCEABLE, HARD, ACCEPTED]:
        lines.append(f"| {s} | {status_counts.get(s, 0)} |")
    lines.append(f"| **Total** | **{len(rows)}** |")
    lines.append("")
    lines.append("### By pillar")
    lines.append("")
    lines.append("| Pillar | Covered | Partial | Sourceable | Hard | Accepted-Gap |")
    lines.append("|---|---|---|---|---|---|")
    for pillar in ["Growth", "Inflation", "Financial Conditions", "Monetary Policy", "Risk-Appetite / Sentiment"]:
        c = pillar_status.get(pillar, Counter())
        lines.append(f"| {pillar} | {c.get(COVERED,0)} | {c.get(PARTIAL,0)} | "
                     f"{c.get(SOURCEABLE,0)} | {c.get(HARD,0)} | {c.get(ACCEPTED,0)} |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Full table grouped by pillar
    hdr = ("| Indicator | Pillar | Sub-group | Cycle (prior) | Region | "
           "Regional analogue | Requested source/freq | Lag | Status | "
           "Pipeline match | Pipeline source | Candidate free source | Notes |")
    sep = "|" + "---|" * 13
    current_pillar = None
    for r in rows:
        if r["pillar"] != current_pillar:
            current_pillar = r["pillar"]
            lines.append(f"## {current_pillar}")
            lines.append("")
            lines.append(hdr)
            lines.append(sep)
        lines.append("| " + " | ".join(md_escape(r[c]) for c in COLUMNS) + " |")
        # close table block when pillar changes is handled by next header
    lines.append("")

    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def main():
    rows = flatten(DATA)
    write_csv(rows, os.path.join(OUT_DIR, "regime-aa-indicator-coverage.csv"))
    write_md(rows, os.path.join(OUT_DIR, "regime-aa-indicator-coverage.md"))
    print(f"Wrote {len(rows)} rows.")
    from collections import Counter
    for s, n in Counter(r["status"] for r in rows).most_common():
        print(f"  {s:20} {n}")


if __name__ == "__main__":
    main()
