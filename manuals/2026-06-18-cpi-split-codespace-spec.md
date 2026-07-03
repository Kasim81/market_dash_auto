# Codespace work order — CPI definition split (fixes the *_INFL1 composites)

**Run this in the Codespace** (needs DB.nomics network + API keys + a full macro
regen — none of which exist in the Claude-Code web sandbox). It is the
workstream that actually fixes `JP_INFL1` (and `US_/UK_/CN_INFL1`).

Base your branch on **`claude/p1-source-precedence-2026-06-18`** (the P1 tier work),
not `main` — you rely on the `tier` column and the kind-guarded merge it adds.
First confirm the environment:

    python3 -c "import os;print('DBNOMICS reachable test below');print('keys:',{k:bool(os.environ.get(k)) for k in ['FRED_API_KEY','ESTAT_APP_ID']})"
    curl -s --max-time 30 "https://api.db.nomics.world/v22/series/OECD/DSD_PRICES_COICOP2018@DF_PRICES_C2018_N_TXCP01_NRG/JPN.M.N.CPI.PA._TXCP01_NRG.N.GY?observations=1" | head -c 300

If DB.nomics is unreachable, stop and report — the sourcing step can't proceed.

---

## 1. Problem

The country `<C>_CPI` columns conflate two different measures under one column,
and the inflation composites blend whatever wins:

| `_CPI` column | serves today | kind | consumed by |
|---|---|---|---|
| USA_CPI, JPN_CPI, CHE/DEU/EA19/FRA/ITA/NLD_CPI | World Bank `FP.CPI.TOTL.ZG` | **annual YoY** | US_INFL1 (USA), JP_INFL1 (JPN) |
| GBR_CPI | ONS `…/d7bt/mm23` | **monthly INDEX** | UK_INFL1 |
| CHN_CPI | FRED `CHNCPIALLMINMEI` | **monthly INDEX** | CN_INFL1 |
| AUS_CPI | ABS `CPI/1.10001.10.50.Q` | **quarterly INDEX** | — |
| CAN_CPI | StatCan `41690973` | **monthly INDEX** | — |

`US_INFL1 / JP_INFL1` blend an **annual** YoY into a monthly composite (so it
moves annually); `UK_INFL1 / CN_INFL1` blend an **index level** (~110–130) with a
core YoY (~2–4%) — badly wrong. All four expect **headline CPI YoY %**.

## 2. Target data model

Split every country CPI into two single-definition columns (this matches the
existing convention — `USA_CPI_INDEX`, `USA_CORE_CPI_INDEX`, `GBR_CPI_YOY`,
`JPN_CORE_CPI_YOY` already exist):

- **`<C>_CPI_INDEX`** — monthly (or native-cadence) CPI **index level**.
  Repoint the existing national INDEX registrations here:
  `GBR_CPI` (ONS d7bt) → `GBR_CPI_INDEX`; `CHN_CPI` (FRED CHNCPIALLMINMEI) →
  `CHN_CPI_INDEX`; `AUS_CPI` (ABS) → `AUS_CPI_INDEX`; `CAN_CPI` (StatCan) →
  `CAN_CPI_INDEX`.
- **`<C>_CPI_YOY`** — monthly headline CPI **YoY %** (NEW; see §3).
- **Retire `<C>_CPI`**: repoint the World Bank `CPI` fan-out
  (`macro_library_worldbank.csv`, col `CPI`) to feed **`<C>_CPI_YOY` as an
  annual tier-1 fallback** (change its `col` from `CPI` to `CPI_YOY`; it stays
  annual, so the monthly source wins by cadence and WB only fills gaps). No
  column should be left named `<C>_CPI`.
- **Repoint the composites** in `macro_indicator_library.csv`
  (`formula_using_library_names`): `US_INFL1 USA_CPI→USA_CPI_YOY`,
  `JP_INFL1 JPN_CPI→JPN_CPI_YOY`, `UK_INFL1 GBR_CPI→GBR_CPI_YOY`,
  `CN_INFL1 CHN_CPI→CHN_CPI_YOY`. Update each composite's prose to say YoY.

## 3. Sourcing `<C>_CPI_YOY` (monthly headline YoY) — mirror the core series

The working core series to mirror (in `macro_library_dbnomics.csv`):

    JPN_CORE_CPI_YOY = OECD/DSD_PRICES_COICOP2018@DF_PRICES_C2018_N_TXCP01_NRG/JPN.M.N.CPI.PA._TXCP01_NRG.N.GY
    (COICOP `_TXCP01_NRG` = ex-food-and-energy; `.GY` = growth-over-1-year = YoY; `.M` = monthly)

For **headline all-items**, the COICOP coverage code changes from `_TXCP01_NRG`
(core) to all-items (**`_T`** in COICOP2018, sometimes exposed under a different
DB.nomics dataset). **Explore DB.nomics to find the exact all-items series per
country** — do NOT assume the key; verify it returns monthly data:

    # discover the dataset + all-items dimension
    curl -s "https://api.db.nomics.world/v22/datasets/OECD?limit=50" | grep -i coicop
    curl -s "https://api.db.nomics.world/v22/series/OECD/<dataset>?dimensions={\"MEASURE\":[\"GY\"],\"REF_AREA\":[\"USA\"]}&limit=20"
    # confirm a candidate returns recent monthly obs:
    curl -s "https://api.db.nomics.world/v22/series/OECD/<dataset>/<ISO>.M.N.CPI.PA._T.N.GY?observations=1"

Source **per country** in this preference order; pick the first that returns a
**monthly YoY** series with recent obs, and record the exact series_id + last obs:
1. **OECD COICOP2018 all-items YoY** (`_T`) — preferred; same family as the core.
2. **Eurostat HICP all-items YoY** for EU-area (`Eurostat/prc_hicp_manr/M.RCH_A.CP00.<GEO>`,
   already used by `EA_HICP`) — note it's HICP not national CPI; label it so.
3. **World Bank annual** stays as the tier-1 fallback (from §2), so every country
   has *something* even if no monthly source exists.

Countries needing `_CPI_YOY` (at minimum the composites' four: USA, JPN, GBR, CHN;
ideally all 12: AUS CAN CHE DEU EA19 FRA GBR ITA JPN NLD USA CHN). If a country has
no monthly YoY source, create the column with only the WB annual fallback and
flag it (do not fabricate).

Set tiers per P1: the monthly DB.nomics/OECD source can be tier 1 (aggregator) —
cadence-first still makes it beat the annual WB tier-1 fallback. National direct
sources (ONS/Eurostat-direct) = tier 0.

## 4. Library edits (concrete)

- `macro_library_dbnomics.csv`: add `<C>_CPI_YOY` rows (verified series_ids),
  units `Percent Change YoY`, frequency `Monthly`, concept `Inflation`.
- `macro_library_ons.csv` / `_fred.csv` / `_abs.csv` / `_statcan.csv`: change the
  `col` of the four national CPI-index rows from `<C>_CPI` to `<C>_CPI_INDEX`.
- `macro_library_worldbank.csv`: change row `FP.CPI.TOTL.ZG` col `CPI` → `CPI_YOY`
  (now an annual fallback for `<C>_CPI_YOY`).
- `macro_indicator_library.csv`: repoint the four `*_INFL1` formulas.

## 5. Validate (must all pass before PR)

1. `python3 -m pytest test_tier_merge.py -q` still green.
2. Full macro regen (the daily fetch path) with keys. Then check
   `data/macro_economic_hist.csv`:
   - `JPN_CPI_YOY`, `USA_CPI_YOY`, `GBR_CPI_YOY`, `CHN_CPI_YOY` exist, are
     **Monthly**, with a **recent** last obs and plausible values (~0–5%).
   - `JP_INFL1` now changes month-to-month (not a flat annual step) and equals
     `mean(JPN_CPI_YOY, JPN_CORE_CPI_YOY)`; same shape for US/UK/CN_INFL1.
   - no column named `<C>_CPI` remains; `<C>_CPI_INDEX` carries the index levels.
3. `python3 build_source_inventory.py` → the CPI columns no longer carry
   `FLAG_definition_collision` (should drop from 5 toward 0).
4. Spot-check the explorer/dashboard renders the four `*_INFL1` as monthly.

## 6. Guardrails

- **Never repoint a composite to a `_CPI_YOY` column you haven't confirmed
  returns data** — a broken repoint is worse than the current state. Verify the
  series live first.
- Keep the WB annual as a **tier-1 fallback** on `_CPI_YOY`, don't delete it —
  it's the safety net for countries without a monthly source.
- Don't touch the kind-guard / `_select_winner` logic; it's unit-tested. After
  the split each CPI column is single-kind, so cadence-first applies cleanly.
- Update `manuals/2026-06-18-source-wiring-audit-proposal.md` and the audit doc's
  resolution table when done.

## 7. Deliverable

One PR on a branch off `claude/p1-source-precedence-2026-06-18`. In the PR body,
list each `<C>_CPI_YOY` source you chose (source/series_id + last obs) and paste
the before/after `JP_INFL1` series tail showing it now moves monthly.
