# Adopting OpenBB as a unified data layer: evaluation

**Status:** recommendation for approval. No feeds were changed, removed or rewired for this document.
**Written:** 2026-09-08.
**Question asked:** should adopting the OpenBB Platform as a unified data layer take priority over the piecemeal integrations still in the forward plan (survey endpoints, international macro via OECD/IMF/ECB, and a paid route to ISM/PMI)?

## Recommendation in one paragraph

Do not adopt OpenBB as a unified data layer, and do not let it displace anything in the forward plan. Adopt it in one narrow place only: as an optional convenience wrapper over OECD SDMX, behind the existing `sources/` boundary, and only if the direct `sources/oecd.py` module starts costing maintenance time. The reason is specific rather than philosophical. Almost everything OpenBB would supply to this repo, it supplies by calling FRED with our own `FRED_API_KEY`, or OECD SDMX, or yfinance, and this pipeline already calls all three directly. On the one gap that actually motivated the question, ISM/PMI, OpenBB has no endpoint at all. It would add roughly a hundred packages and an AGPL obligation in exchange for coverage we already have, while removing the euro-area aggregate we currently get from our own OECD fan-out.

The corollary matters as much as the recommendation. The ISM/PMI problem is not solvable by picking a better aggregator, because ISM licenses its indexes and the free mirrors are unreliable. That is what CP-05 turned out to be, and the fix landed in this repo on 2026-09-08 as a persisted store of official ISM release points rather than a new provider.

## What I actually ran

Everything below is measured in this container on 2026-09-08 against `openbb` 4.7.2 (published 2026-05-26), Python 3.11, in a clean virtualenv. Where a claim comes from the web rather than from a call I made, it is marked.

| Check | Result |
|---|---|
| `pip install openbb` | 41 s, 100 packages, 353 MB on disk |
| `from openbb import obb` | 10.5 s cold import, no interactive prompt, no config file required |
| Resolved `pandas` / `numpy` | 3.0.5 / 2.4.6, identical to this repo's current environment. No conflict observed |
| Provider models registered | 180 |
| Providers available without extras | benzinga, bls, cftc, congress_gov, econdb, eia, federal_reserve, fmp, fred, government_us, imf, intrinio, oecd, sec, tiingo, tradingeconomics, yfinance |
| `economy` router endpoints | 41 |
| `fixedincome` router commands | 24 |
| Endpoints matching ISM or PMI | none |
| Providers needing no credential | 6 of 17: `federal_reserve`, `government_us`, `imf`, `oecd`, `sec`, `yfinance` |
| Licence | AGPL-3.0-only (PyPI metadata; the repo `LICENSE` reads "Copyright (c) 2021-2025 OpenBB Inc. All files in this repository are licensed under the GNU Affero General Public License v3.0") |

Calls made with no credentials configured:

| Call | Outcome |
|---|---|
| `economy.composite_leading_indicator(country=<10 countries>)` | 6,873 rows, all 10 countries, every one fresh to 2026-08-01 |
| `economy.cpi(country="united_states", provider="oecd")` | 846 rows |
| `economy.unemployment(country="united_states")` | 859 rows |
| `economy.gdp.real(country="united_states", provider="oecd")` | 318 rows |
| `economy.interest_rates(country="united_states")` | 746 rows |
| `economy.survey.university_of_michigan()` | fails: `Missing credential 'fred_api_key'` |
| `economy.survey.sloos()` | fails: same |
| `economy.survey.manufacturing_outlook_ny()` | fails: same |
| `fixedincome.bond_indices(index_type="yield")` | fails: same |
| `fixedincome.government.yield_curve(provider="econdb")` | fails: "The temporary EconDB token could not be retrieved... Your IP address may have been flagged by Cloudflare" |
| `economy.available_indicators(provider="econdb")` | fails inside the library: `AttributeError: 'DataFrame' object has no attribute 'iso'` |
| `currency.price.historical("EURUSD", provider="yfinance")` | fails on this runner's egress policy, not an OpenBB fault |

Two of those results carry most of the weight. The OECD family is genuinely keyless, fast and current. Everything else that this repo would want is either behind our own FRED key, behind an EconDB token this environment cannot obtain, or absent.

## Coverage against what this repo needs

### ISM and PMI

OpenBB has no ISM endpoint and no PMI endpoint. I enumerated all 41 `economy` commands and all 180 provider models; nothing matches. The reason is structural rather than an oversight: OpenBB's US macro comes from FRED, and FRED does not carry ISM. I confirmed that directly against FRED's keyless CSV endpoint, where `NAPM`, `NAPMPI` and `NAPMNOI` all return HTTP 404 while a control series (`MANEMP`) returns 200. ISM restricts redistribution of its indexes, which is why the free aggregators either lag or break.

This is the single most important finding in the evaluation, because ISM/PMI was the strongest argument for adopting OpenBB. It does not survive contact with the API.

The nearest thing OpenBB offers is `economy.survey.manufacturing_outlook_ny` and `economy.survey.manufacturing_outlook_texas`, which are regional Fed surveys, not ISM. This repo already carries the Empire State and Philadelphia Fed equivalents as `GACDISA066MSFRBNY` and `GACDFSA066MSFRBPHI` in `macro_library_fred.csv`.

### Fed and University of Michigan surveys

OpenBB's survey layer is a set of curated FRED bundles. `economy.survey.university_of_michigan` reads exactly two series, `UMCSENT` and `MICH`, then renames them to `consumer_sentiment` and `inflation_expectation`. Both are already columns in `macro_economic_hist.csv`. The same holds across the group: `sloos` maps to the SLOOS family we already reach through `DRTSCILM`, `nonfarm_payrolls` to `PAYEMS`, and the inflation-expectations endpoint to breakevens we already carry as `T5YIE`, `T10YIE` and `T5YIFR`.

Two are genuinely new to us: the Dallas Fed Texas manufacturing outlook and the Chicago Fed survey of economic conditions. Both are FRED series, and both need the FRED key we already hold. Adding them costs one row each in `data/macro_library_fred.csv` and no new dependency.

There is also a trap worth naming. OpenBB's Michigan model divides `MICH` by 100 before returning it, and divides `UMCSENT` too when a transform is requested. That is a reasonable normalisation for OpenBB's own consumers and a silent scale change for ours. A survey series arriving at 0.033 instead of 3.3 would move straight into a z-score. That is the same class of fault as CP-05, where a diffusion index scored 5.9 sigma because its history had a hole. Any adoption has to pin and test units per series, which erodes the "unified layer removes work" argument.

### International macro

This is where OpenBB is real. One keyless call returned the OECD composite leading indicator for the United States, Canada, the United Kingdom, Germany, France, Japan, China, India, South Korea and Australia, all current to August 2026. `cpi`, `unemployment`, `gdp.real`, `gdp.nominal`, `interest_rates`, `house_price_index` and `share_price_index` follow the same pattern.

The catch is the euro area. OpenBB's OECD provider accepts only this country list for the CLI: `g20`, `g7`, `asia5`, `north_america`, `europe4`, `australia`, `brazil`, `canada`, `china`, `france`, `germany`, `india`, `indonesia`, `italy`, `japan`, `mexico`, `spain`, `south_africa`, `south_korea`, `turkey`, `united_states`, `united_kingdom`, `all`. There is no euro-area aggregate. Our own `data/macro_library_oecd.csv` CLI row fans out to `AUS+CAN+CHE+CHN+DEU+EA19+FRA+GBR+ITA+JPN+USA`, which includes `EA19` and also Switzerland. Switching the CLI to OpenBB would lose two members of that set. For a dashboard whose euro-area column is one of the six regions, that is a downgrade, not a consolidation.

The multi-country workhorse in OpenBB is EconDB, reached through `economy.indicators` and `economy.available_indicators`. It needs a token. The built-in temporary-token path failed here with a Cloudflare message, and the catalogue call raised an internal `AttributeError` in 4.7.2. Neither is a good foundation for a job that has to run unattended every morning.

### FX, rates and credit

`currency.price.historical` runs on yfinance, fmp or tiingo. This repo already pulls roughly 401 yfinance instruments through `data/index_library.csv`, so routing them through OpenBB adds a layer without adding a source.

`fixedincome` is broader than I first assumed: 24 commands across `bond_indices`, `mortgage_indices`, `corporate.*` (commercial paper, HQM, spot rates), `government.*` (Treasury rates and prices, auctions, yield curve, Svensson curve, TIPS yields), `rate.*` (EFFR and its forecast, SOFR, SONIA, ESTR, ECB, IORB, AMERIBOR, discount window, overnight bank funding) and `spreads.*` (TCM, TCM-EFFR, Treasury-EFFR). That is a genuinely useful rates surface.

It is also, almost entirely, FRED and federalreserve.gov. Checking the registry's credential map, only six providers are keyless: `federal_reserve`, `government_us`, `imf`, `oecd`, `sec` and `yfinance`. Everything else needs a key, including `fred`, `fmp`, `bls`, `eia`, `tiingo`, `tradingeconomics` and `econdb`. So the keyless part of the rates surface is the Federal Reserve H.15/H.6 scrape, and this repo already reaches the same numbers through `sources/treasury.py` for the par-yield curve and through FRED for the rest. I could not test the `federal_reserve` provider end to end because this container's egress policy blocks `www.federalreserve.gov`; that is an environment limit, not an OpenBB fault, and it would need re-testing on a GitHub Actions runner before anyone relied on it.

There is no credit-spread coverage beyond what FRED already gives us, and the repo already carries the ICE BofA OAS families.

### Mapping to the forward-plan phases

| Forward-plan work | Would OpenBB consolidate or retire it? |
|---|---|
| Survey endpoints (the §2.B / Stage E survey track) | Partly, and only for US series we already have. It adds two new FRED series, both addable as CSV rows. It does not touch Stage E's actual targets, which are BoK BSI via ECOS, IMEF via Banxico SIE, INEGI EMOE, TCMB EVDS, INDEC and Bank Indonesia. OpenBB has no provider for any of those. |
| International macro via OECD / IMF / ECB | Partly. OECD, yes, and cleanly, except it drops `EA19` and `CHE` from our CLI fan-out. IMF is present but its `economy.indicators` symbol format is its own (`dataflow::identifier`) and is not obviously better than our existing `sources/imf_sdmx.py`. There is no ECB provider in the default install; `openbb-ecb` is an optional extra. Our `sources/ecb.py` already reaches the ECB Data Portal, including the Bank Lending Survey. |
| FMP for ISM/PMI (the deleted Phase D calendar track) | No. OpenBB has no ISM or PMI endpoint. It bundles `openbb-fmp`, which is the same paywalled provider that was rejected on 2026-04-23, and the FMP economic-calendar endpoint is the one that returned 403/402 on the free tier. Adopting OpenBB does not change that. |
| §3.13 OECD MEI verification | Slightly helpful as a cross-check. The MEI series in question are already registered through FRED (`IRLTLT01{ISO}M156N`, `SPASTT01{ISO}M661N`), and OpenBB would give an independent read on the same OECD data for continuity verification. That is a testing convenience, not a pipeline change. |

Net: OpenBB would consolidate part of one track, leave two untouched, and retire nothing.

## Integration fit

**Headless in GitHub Actions.** Yes. `from openbb import obb` completes with no TTY, no prompt and no config file. It prints an extension-build line on first import and caches the built router. Cold import measured 10.5 s here, which is real but tolerable against a job that already takes minutes. The install is 41 s and 100 packages against this repo's current 10 direct requirements. `openbb-charting`, `openbb-econometrics` and the other heavy extras are opt-in, so the default install is the lean one.

**Auth and rate limits.** Six of the seventeen default providers need no credential (`federal_reserve`, `government_us`, `imf`, `oecd`, `sec`, `yfinance`); the other eleven do, including `fred`, `fmp`, `bls`, `econdb`, `eia`, `tiingo` and `tradingeconomics`. OpenBB does not proxy anything. Every provider call goes out under our own credential, so rate limits are unchanged from calling the API directly, and so is the failure mode when a key is missing: a clear `Missing credential 'fred_api_key'` error rather than a silent empty frame. That is decent behaviour. It also means the "unified" layer is unified only in call signature, not in access. We would still hold FRED, FMP, Alpha Vantage, BLS and the rest ourselves, plus a new EconDB token if we wanted the multi-country path.

**Provenance and version stability.** This is the weakest part. Three specific concerns, each observed rather than assumed:

1. Silent unit transforms. The Michigan model divides by 100. Nothing in the endpoint name says so.
2. Curated bundles hide the underlying series. `university_of_michigan` returning `consumer_sentiment` is friendlier than `UMCSENT`, and it is also one abstraction further from the thing our audit and freshness logic checks. Our `data_audit.py` and `source_fallbacks.csv` reason about identifiers. If the identifier moves inside OpenBB, our provenance chain gets shorter by exactly one link, in the wrong direction.
3. Version churn. Releases in the last year: 4.4.3 (2025-04-02), 4.4.4 (2025-05-01), 4.4.5 (2025-07-16), 4.5.0 (2025-10-08), 4.6.0 (2026-01-02), 4.7.0 (2026-03-05), 4.7.1 (2026-03-09), 4.7.2 (2026-05-26). That is an active project, which is good, and it is also a moving surface between us and the data. The `available_indicators` crash in 4.7.2 shows the surface does break.

**Architecture fit.** Forward plan §0.1 is non-negotiable: every fetched identifier lives in a CSV under `data/`, never in Python. OpenBB inverts that. Its endpoints are curated Python functions, and the series they read are literals inside the installed package. A naive adoption would move identifier selection out of our registry and into a third-party dependency, which is precisely the drift §0.1 exists to prevent. The rule is satisfiable, but only by wrapping OpenBB the same way every other source is wrapped: a `sources/openbb_oecd.py` module plus a `data/macro_library_openbb.csv` whose rows carry the endpoint, provider and field, for example `economy.cpi|oecd|value`. Any adoption must take that shape.

**Licence.** AGPL-3.0-only. This repo has no LICENSE file today and publishes a static dashboard rather than distributing the pipeline, so importing OpenBB as a library into a private repo is fine as it stands. Worth noting anyway, because AGPL's network clause matters if the pipeline is ever hosted as a service or the repo is ever opened. It is a decision for Kas, not a blocker.

**Coexistence with direct FRED.** Clean, because OpenBB uses the same key against the same API. The risk is not technical conflict but duplicate provenance: two paths to `UMCSENT` reaching the same column, with the tier-aware `_select_winner` merge picking between them on freshness. If OpenBB is ever wired, its rows should get a distinct tier and, where they duplicate a direct row, a distinct column name, exactly as `USA_CPI_SHILLER` sits alongside `USA_CPI_INDEX`.

## Effort and risk against the current plan

Adopting OpenBB as a unified layer, properly done, is not a small job. It means a source module, a registry CSV, a smoke test, unit pinning per series, and a re-audit of every column whose provenance changes. Call it a week, and most of that week buys coverage we already have.

The phase-by-phase plan costs less per unit of new data because each item is scoped to a series we do not yet have. B2 and B3 were roughly six hours for three indicators. The ISM work that closed CP-05 was a day. Stage E's remaining targets are national statistics APIs that OpenBB cannot reach at any price, so that work is unavoidable either way.

The risk asymmetry runs the same direction. The current architecture's failure mode is a single dead feed, which the plausibility guard and the tier merge already contain. A unified layer's failure mode is a version bump that changes units or drops a country across many columns at once. CP-05 is the recent evidence that this pipeline's real hazard is a source going quietly wrong rather than loudly missing, and that hazard scales with how many columns share a provider.

## Recommended sequencing

1. **Now, no OpenBB.** Keep the ISM release-point store as the ISM/PMI answer. It is already the most reliable free path, because it reads the official release rather than a mirror of it.
2. **Now, cheap and unrelated to OpenBB.** Add Dallas Fed Texas manufacturing outlook and the Chicago Fed survey of economic conditions as two rows in `data/macro_library_fred.csv`. These are the only genuinely new series this survey turned up, and they cost nothing beyond the FRED key already in the daily job.
3. **Next, unchanged.** Proceed with Stage C and Stage E as planned. OpenBB does not help with either.
4. **Optional, low priority.** Build `sources/openbb_oecd.py` plus `data/macro_library_openbb.csv` as a tier-2 fallback behind the direct `sources/oecd.py`, covering the ten OECD countries OpenBB does expose. This is worth doing only if the direct OECD SDMX module starts breaking. It must not own the CLI column, because it cannot serve `EA19`.
5. **Do not** pursue EconDB through OpenBB until the token path works from a GitHub Actions runner. Verify that before spending time on it.
6. **Do not** revive FMP for ISM/PMI. It was rejected in April 2026 for being paywalled, and OpenBB bundling `openbb-fmp` does not unpaywall it.

## Migration path that never breaks the live daily job

If Kas approves step 4, this is the shape it takes. Every step is reversible and none of them touches a working feed until the last one.

1. **Add the dependency behind an extra, not the base install.** `openbb` goes into a separate `requirements-openbb.txt`, installed only by the step that needs it. The daily job's core install stays at 10 packages. If OpenBB fails to install, nothing else changes.
2. **Wrap it like any other source.** New `sources/openbb_oecd.py` exposing `fetch_series_as_pandas(series_id)` so it slots into the existing `_make_source_handlers` factory. New `data/macro_library_openbb.csv` carrying endpoint, provider, country and field per row. No identifier in Python. Import OpenBB lazily inside the fetch function so a missing dependency degrades to "no rows" rather than an import error at module load.
3. **Register every row at tier 2 with a distinct column name.** `USA_CLI_OPENBB` alongside `USA_CLI`, not instead of it. The tier-aware `_select_winner` then treats OpenBB as a demoted candidate that only serves periods the owner does not cover, which is the same posture that already governs every fallback in `data/source_fallbacks.csv`.
4. **Run in shadow for two weeks.** The columns land in `macro_economic_hist.csv` and are visible to `data_audit.py`, but no Phase E calculator reads them. Compare `USA_CLI_OPENBB` against `USA_CLI` over the overlap, series by series, with an explicit unit check. The seam-agreement logic in `_assemble_column` already does this kind of comparison and should be the arbiter, not eyeballing.
5. **Only then consider promotion,** and only for a series where the direct module has actually been failing. Promotion is a tier change in the CSV, which is one line and one revert.
6. **Keep the kill switch trivial.** Because everything lives in `data/macro_library_openbb.csv`, disabling OpenBB entirely is deleting rows from a CSV. No Python change, no redeploy, no risk to the other 357 columns.

At no point in that sequence does a live column change owner without a two-week overlap and an explicit unit comparison. If OpenBB is going to surprise us, it surprises a shadow column.

## What would change this recommendation

Three things, in order of likelihood.

- OpenBB ships a working ISM or PMI endpoint from a licensed provider. That would be a genuine reason to revisit, and it is the one gap that matters most.
- The EconDB token path becomes reliable from CI and its multi-country catalogue proves fresher than our direct national sources. That would make the international macro case much stronger than the OECD-only case is today.
- Our own `sources/` modules start costing meaningful maintenance. Right now they do not; the recent failures have been upstream data faults, and a wrapper would not have prevented any of them. CP-05 is the case in point. OpenBB would have inherited the same broken mirror.

## Sources

Measured directly in this container on 2026-09-08 unless noted. Package metadata from [openbb on PyPI](https://pypi.org/project/openbb/). Licence text from [OpenBB-finance/OpenBB LICENSE](https://raw.githubusercontent.com/OpenBB-finance/OpenBB/develop/LICENSE). Licence-change background from [License Change: OpenBB Platform Goes AGPL](https://openbb.co/blog/license-change-openbb-platform-goes-agpl/) and [OpenBB releases Open Data Platform](https://openbb.co/blog/openbb-releases-open-data-platform/). FRED ISM series availability checked against `https://fred.stlouisfed.org/graph/fredgraph.csv`. Repo-side coverage read from `data/macro_economic_hist.csv`, `data/macro_library_fred.csv`, `data/macro_library_oecd.csv` and `manuals/forward_plan.md` at commit `4457428`.
