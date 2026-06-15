# Codespace Secrets Checklist — mirror Actions → Codespaces

Date: 2026-06-15. Purpose: the exact list of GitHub **Repository Codespaces
secrets** to mirror from the Actions secret store before running the
label-vs-data audit. Actions and Codespaces have separate stores; GitHub does
not auto-sync them. This is a discovery report — no code was modified.

Sources reconciled: `.github/workflows/update_data.yml` (every `${{ secrets.X }}`)
and all `os.environ.get/[...]` reads under `sources/*.py`, `fetch_*.py`,
`test_*_smoke.py`. Ticker counts are data rows in `data/macro_library_*.csv`.

### Codespace state snapshot

Sorted MISSING-but-needed first. Presence checked via `os.environ.get(name)` —
values never read.

| Secret | SET in Codespace? | In update_data.yml? | Class |
|--------|-------------------|---------------------|-------|
| `FRED_API_KEY`              | **MISSING** | yes | REQUIRED |
| `BLS_API_KEY`               | **MISSING** | yes | REQUIRED |
| `BDF_API_KEY`               | **MISSING** | yes | REQUIRED |
| `ESTAT_APP_ID`              | SET (already mirrored) | yes | REQUIRED |
| `ALPHAVANTAGE_API_KEY`      | MISSING | yes | OPTIONAL |
| `NASDAQ_DATA_LINK_API_KEY`  | MISSING | yes | OPTIONAL |
| `BRIGHTDATA_API_KEY`        | MISSING | yes | OPTIONAL |
| `BRIGHTDATA_ZONE`           | MISSING | yes | OPTIONAL (has default) |
| `INSEE_API_KEY`             | MISSING | **no** | SKIP (keyless) — asymmetry |
| `FMP_API_KEY`               | MISSING | yes | SKIP (orphan) — asymmetry |
| `GOOGLE_CREDENTIALS`        | MISSING | yes | SKIP (complex credential) |
| `SEC_EDGAR_CONTACT`         | MISSING | no  | SKIP (keyless, has default) |

### REQUIRED for the label-vs-data audit

These gate metadata endpoints the audit must hit. **You must mirror the three
MISSING ones below before kicking off the audit** (`ESTAT_APP_ID` is already
present).

- **`FRED_API_KEY`** — unlocks `/fred/series` metadata for FRED. Backs the
  largest source: **122 tickers** (`data/macro_library_fred.csv`), read in
  `fetch_data.py:28`, `fetch_hist.py:60`, `fetch_macro_economic.py:68`.
  **Status: MISSING.** Actions value: Settings → Secrets and variables →
  Actions → `FRED_API_KEY`.
- **`ESTAT_APP_ID`** — Japan e-Stat `getMetaInfo`/`getStatsData`, **5 tickers**
  (`data/macro_library_estat.csv`), read in `sources/estat.py:121`.
  **Status: already SET in this Codespace** — no action needed.
- **`BLS_API_KEY`** — BLS metadata, **4 tickers** (`data/macro_library_bls.csv`),
  read in `sources/bls.py:172`. v1 is keyless but heavily rate-limited; the key
  (v2) is needed for a reliable audit pass. Gates `test_bls_smoke.py`.
  **Status: MISSING.** Actions value: Actions → `BLS_API_KEY`.
- **`BDF_API_KEY`** — Banque de France / Webstat, key-gated, **2 tickers**
  (`data/macro_library_bdf.csv`), read in `sources/bdf.py:155`. Gates
  `test_bdf_smoke.py` (confirmed: skips with "BDF_API_KEY not set").
  **Status: MISSING.** Actions value: Actions → `BDF_API_KEY`.

### OPTIONAL but recommended

Audit doesn't strictly need these, but mirror them if you want local fetcher
testing or if the audit's scope is widened to these sources.

- **`ALPHAVANTAGE_API_KEY`** — `sources/alpha_vantage.py:108`. Primary-source
  tie-break + gates `test_alpha_vantage_smoke.py` (confirmed skip while
  MISSING). Library currently **0 tickers**, so no audit dependency today.
  Actions → `ALPHAVANTAGE_API_KEY`.
- **`NASDAQ_DATA_LINK_API_KEY`** — `sources/nasdaq_data_link.py:50`. Only
  affects rate-limiting; **0 tickers** in `macro_library_nasdaqdl.csv`. Without
  it calls are rate-limited, not blocked. Actions → `NASDAQ_DATA_LINK_API_KEY`.
- **`BRIGHTDATA_API_KEY`** — `sources/ifo.py:140`. Scraping proxy that gates the
  **ifo source (26 tickers**, `data/macro_library_ifo.csv`). It's a fetch proxy,
  not a clean metadata API, so it's not in the audit's core set — but if the
  audit is extended to ifo labels you'll need it. Actions → `BRIGHTDATA_API_KEY`.
- **`BRIGHTDATA_ZONE`** — `sources/ifo.py:143`. Optional; defaults to
  `web_unlocker1`. Mirror only if your Bright Data account uses a non-default
  zone. Actions → `BRIGHTDATA_ZONE`.

### Skip — not needed

- **`GOOGLE_CREDENTIALS`** — service-account JSON for Google Sheets writeback
  (`fetch_data.py:667`, `fetch_hist.py:61`, `fetch_macro_economic.py:67`). Not a
  simple API key and irrelevant to a metadata audit — **complex credential,
  separate handling** if you ever need local writeback.
- **`SEC_EDGAR_CONTACT`** — `sources/sec_edgar.py:79`. Not a secret; a UA contact
  string with a default email baked in. SEC EDGAR is keyless (68 tickers fetch
  fine without it).
- **`INSEE_API_KEY`** — read in `sources/insee.py:112` but INSEE works keyless
  (per workflow comment). See asymmetries.

### Asymmetries detected

| Secret | Type | Detail |
|--------|------|--------|
| `FMP_API_KEY` | Orphan | Wired in `update_data.yml:32` but **no `os.environ` read** in any `sources/`, `fetch_*`, or test file (only a stale comment in `compute_macro_market.py:1878`). Safe to ignore for the audit. |
| `INSEE_API_KEY` | Missing wiring | Read in `sources/insee.py:112` but **not** in `update_data.yml`. Harmless — INSEE v3 is used keyless (3 tickers, `macro_library_insee.csv`); the read is an optional override. |

### Mirror procedure (copy-paste)

For each REQUIRED secret currently MISSING — **`FRED_API_KEY`, `BLS_API_KEY`,
`BDF_API_KEY`**:

1. Open the Actions value: GitHub repo → **Settings → Secrets and variables →
   Actions** → click the secret name → copy its value (you set it; GitHub won't
   re-display it, so retrieve from your own store if needed).
2. Add it to Codespaces: **Settings → Secrets and variables → Codespaces →
   New repository secret** → **Name** = the exact secret name above → **Value**
   = the value from step 1 → select this repository under "Repository access".
3. Repeat for all three.
4. **Rebuild the Codespace** (Command Palette → "Codespaces: Rebuild Container")
   or open a fresh Codespace so the new env vars are injected. They do **not**
   appear in an already-running Codespace until rebuild.
5. Verify (presence only, never prints values):
   `python3 -c "import os; [print(n, 'SET' if os.environ.get(n) else 'MISSING') for n in ['FRED_API_KEY','BLS_API_KEY','BDF_API_KEY','ESTAT_APP_ID']]"`

`ESTAT_APP_ID` is already SET — leave it. Mirror the OPTIONAL set only if you
want local fetcher/smoke testing.
