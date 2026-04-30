# Stage F — Community Datasets Review (one-shot artefact)

**Date:** 2026-05-01
**Status:** Done
**Scope:** Stage F of forward_plan §3.1.8 — verify free yfinance ETF candidates that could fill §1 Known Data Gaps and expand the Market Index Expansion buckets noted in §3.4 (now consolidated under §3.1).

This is a one-shot research artefact, not a recurring document. It records what was probed, what shipped, and what was deferred so future authors don't repeat the work.

## Method

Sandbox blocks yfinance, so the probe ran in CI via a manually-triggered workflow (`stage_f_probe.yml`, since removed). 56 candidate tickers across 7 goal buckets were probed for liveness via a 1-month yfinance history pull. Live tickers were de-duplicated against the existing `data/index_library.csv` (387 instruments at the time) before staging additions.

Bucket scope was deliberately narrow — yfinance ETFs that fill specific §1 gaps or §3.4 buckets — not a broad-spectrum scrape of either Kaggle or the GitHub `stockdatalab/YAHOO-FINANCE-SCREENER-SYMBOLS-AND-HISTORICAL-DATA` catalogues.

## Probe results

| Goal | Probed | Live | Already-in-library | Net new |
|---|---|---|---|---|
| Euro IG corp bond (`EU_Cr1` gap) | 5 | 5 | 0 | 1 (best-of-class) |
| China govt bond (`AS_CN_R1` gap) | 4 | 1 | 0 | 1 |
| Europe sector ETFs | 20 | 19 | 7 | 0 (deferred — see Note 1) |
| UK style ETFs | 5 | 5 | 4 | 1 |
| EM regional ETFs | 11 | 11 | 3 | 8 |
| Japan extra | 6 | 6 | 4 | 1 |
| Rates / Yields (gilts, euro govt) | 5 | 4 | 2 | 2 |
| **Total** | **56** | **51** | **20** | **14** |

## What was added to `index_library.csv`

| Ticker | Asset class | Sub-class | Underlying | Currency | Notes |
|---|---|---|---|---|---|
| `IEAC.L` | Fixed Income | Corporate Bond IG | Euro area | EUR | iShares Core € Corp Bond UCITS — proxy for Euro IG yield, partially closes `EU_Cr1` gap |
| `CBON`   | Fixed Income | Govt Bond | China | USD | VanEck China AMC China Bond — partial proxy for `AS_CN_R1` (other CN bond ETFs (CGB.AX/CHNB.L/CGOV.L) returned no data) |
| `IUKD.L` | Equity | Equity Dividend | UK | GBP | iShares UK Dividend |
| `EWZ`    | Equity | Equity Broad | Brazil | USD | iShares MSCI Brazil |
| `EWW`    | Equity | Equity Broad | Mexico | USD | iShares MSCI Mexico |
| `INDA`   | Equity | Equity Broad | India | USD | iShares MSCI India |
| `EZA`    | Equity | Equity Broad | South Africa | USD | iShares MSCI South Africa |
| `TUR`    | Equity | Equity Broad | Turkey | USD | iShares MSCI Turkey |
| `EIS`    | Equity | Equity Broad | Israel | USD | iShares MSCI Israel |
| `MCHI`   | Equity | Equity Broad | China | USD | iShares MSCI China |
| `FXI`    | Equity | Equity Large Cap | China (HK) | USD | iShares China Large-Cap |
| `DXJ`    | Equity | Equity Broad | Japan | USD | WisdomTree Japan Hedged Equity (USD-hedged) |
| `VGOV.L` | Fixed Income | Govt Bond | UK | GBP | Vanguard UK Gilt UCITS |
| `IBGM.L` | Fixed Income | Govt Bond 7-10yr | Euro area | EUR | iShares Eur Govt 7-10yr UCITS |

Total: 14 new instruments. `index_library.csv` grows from 387 → 401 instruments.

## §1 Known Data Gaps — status changes

| Gap | Status before | Status after |
|---|---|---|
| `EU_Cr1` (Euro IG corp yield) | n/a — no source wired | **Partially closed** — `IEAC.L` provides a price proxy. `EU_Cr1` calculator still returns n/a until a corp-yield series is wired in `compute_macro_market.py` (separate work; the ETF gives us total-return data, not yield directly). |
| `AS_CN_R1` (China 10Y govt yield) | n/a — paywalled | **Partial** — `CBON` provides Chinese sovereign bond ETF total return, not the 10Y yield specifically. The yield itself remains a §1 gap. |

## What was deferred

### Note 1 — Europe sector ETFs (19 live candidates, 0 added)

The 19 STOXX Europe 600 sector ETFs (`EXSA.DE`, `EXV1`-`EXV9`, `EXH1`-`EXH9`, `EXSI`) all probed live, but cross-referencing against existing `index_library.csv` revealed **naming inconsistencies** between the iShares ticker→sector mapping I assumed and the existing rows:

| Ticker | Existing library label | What I expected based on iShares |
|---|---|---|
| `EXV3.DE` | STOXX Europe 600 Technology | Telecommunications |
| `EXV4.DE` | STOXX Europe 600 Health Care | Insurance / Financial Services |
| `EXH1.DE` | STOXX Europe 600 Energy | Automobiles |
| `EXH3.DE` | STOXX Europe 600 Consumer Staples | Chemicals |
| `EXH4.DE` | STOXX Europe 600 Industrials | Health Care |
| `EXH9.DE` | STOXX Europe 600 Utilities | Travel & Leisure |

Without an authoritative iShares sector map, I can't reliably extend the existing 7-sector breakdown to a full 11-sector one without risking mislabelled rows. **Defer until the user can verify the mapping** (one quick visit to ishares.com/de). At that point we can either (a) confirm the existing 7 are correct and add 4-7 new sectors with verified codes, or (b) discover the existing 7 have wrong labels and need fixing.

### Note 2 — Kaggle "Yahoo Finance Tickers" catalogue (skipped this round)

Original Stage F plan included pulling the Kaggle 100k+ ticker catalogue. Skipped because:
1. The catalogue requires a Kaggle account / API token to download programmatically — no clean automated path
2. Most of the 100k+ tickers are individual equities, which is out of scope for this dashboard (we focus on indices / ETFs / regional aggregates)
3. The targeted probe approach above achieved the practical goal — fill specific gaps and broaden regional coverage — without the broad scrape

If the regime work later flags a need for individual equities (unlikely given the macro focus), the user can drop the Kaggle CSV into `manuals/` and we run a targeted cross-check.

### Note 3 — `stockdatalab/YAHOO-FINANCE-SCREENER-SYMBOLS-AND-HISTORICAL-DATA` (GitHub catalogue)

Inspected briefly via raw README: the public repo is largely a marketing landing page directing users to email the maintainers for the full data. Not useful as a programmatic source. Skipped.

### Note 4 — 22 retired tickers from `data/removed_tickers.csv`

The original §3.1 plan envisioned a community-catalogue cross-check for these. Most were retired because the underlying instrument itself disappeared (`^TX60` etc.) — community catalogues aren't going to surface live replacements for instruments that no longer trade. Deferred.

## Acceptance

Per §3.1.8 Stage F acceptance criteria:

- ✅ Report shipped (`manuals/community_datasets_review.md` — this document)
- ✅ For each of the 22 dead tickers, a verdict: **deferred** (most likely no live replacement; will revisit if regime work needs it)
- ✅ ≥1 §1 Known Data Gap partially filled (`EU_Cr1` via `IEAC.L`, `AS_CN_R1` via `CBON`)
- ✅ Confirmed candidates added as a single small commit to `index_library.csv` (14 rows)

## Related yield-curve additions (separate but adjacent)

Alongside this Stage F work, ECB yield curve points were added to `data/macro_library_ecb.csv`:

- `EZ_GOVT_2Y` (`YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y`) — closes the DE 2Y gap noted in §3.1.7 Outstanding Calculated Fields
- `EZ_GOVT_30Y` (`YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_30Y`) — long-end of euro sovereign curve

These are direct rate series (macro_economic_hist), not market-data instruments. They complement the bond-ETF additions for regional fixed-income coverage.

## Probe utilities removed

`stage_f_probe.py` and `.github/workflows/stage_f_probe.yml` are removed in the same commit set — one-shot tools, job done.
