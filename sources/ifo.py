"""
sources/ifo.py
==============
ifo Business Climate (Germany) source module.

The ifo Institute publishes a monthly Excel workbook at ifo.de.  The file
name encodes the release year-month as `gsk-<e|d>-YYYYMM.xlsx` (`e` =
English, `d` = German).

Discovery strategy, in order:
  1. Direct `requests.get()` against the canonical `secure/timeseries/`
     URLs for the current month and the prior 3 months (gsk-e- then
     gsk-d-).  This is the fast path — if ifo's anti-bot layer ever
     lets us through, we don't pay for a third-party unlock.
  2. If every direct candidate returns the 3038-byte HTML challenge
     page (verified observed behaviour, May-June 2026), fall back to
     **Bright Data Web Unlocker** via its REST API:
         POST https://api.brightdata.com/request
         {"zone": "<zone>", "url": "<ifo url>", "format": "raw"}
     `format: "raw"` returns the upstream body bytes unmodified, so the
     xlsx workbook arrives intact (verified via Bright Data docs:
     `data_format: "screenshot"` + `format: "raw"` is documented as
     binary PNG output via `--output`).

Bright Data is invoked from production Python via its HTTPS API, NOT
the MCP tool — the MCP wrapper only exists inside the Claude harness;
GitHub Actions runs vanilla `requests.post()` straight against the REST
endpoint.

Required secrets (set in repo → Settings → Secrets and variables →
Actions, then surfaced to the runner via the workflow `env:` block):

    BRIGHTDATA_API_KEY   account-level API key from Bright Data
                         (Account settings → API key).  No prefix; pass
                         it raw as the Bearer token.
    BRIGHTDATA_ZONE      (optional) the unlocker zone name.  Defaults
                         to "web_unlocker1" if unset.  Override only if
                         the user named their zone differently in the
                         Bright Data dashboard.

If BRIGHTDATA_API_KEY is unset the module SKIPS cleanly (logs a one-
line notice, raises RuntimeError that callers in
fetch_macro_economic.py already catch as "fetch failed → blank row").
This keeps the local sandbox / forked CI working without a Bright Data
account, while production runs simply route through the unlocker.

Budget guard
------------
A module-level counter caps Bright Data invocations at
`_MAX_BRIGHTDATA_CALLS_PER_RUN = 30` per process to protect the user's
5,000-call/month free tier from a misbehaving retry loop.  Once at the
cap, further calls raise `_BudgetExhausted` (a clean exception the
dispatch handler treats as a SKIP) and a loud `[ifo BUDGET EXHAUSTED]`
line lands in the log.  Current worst case is 6 URLs × 1 unlock call =
6, so 30 is generous headroom.

The English workbook stopped being regularly published at some point;
this module now accepts either language and treats German as the
default.  `parse_workbook` reads by positional column so the German
workbook's column order must still match EXCEL_COL_NAMES.

Indicator definitions live in data/macro_library_ifo.csv (series_id is
the Excel column name, `col` is our canonical output column).
"""

from __future__ import annotations

import io
import os
import pathlib
import re
import time
from datetime import date

import pandas as pd
import requests

_LIBRARY_CSV = pathlib.Path(__file__).parent.parent / "data" / "macro_library_ifo.csv"

IFO_BASE    = "https://www.ifo.de"
IFO_LANDING = f"{IFO_BASE}/en/ifo-time-series"

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# Browser-like headers for the landing-page scrape.  The ifo anti-bot
# layer serves stripped-down HTML (or challenge pages) to bare UAs.
_HTTP_HEADERS = {
    "User-Agent":      USER_AGENT,
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT":             "1",
    "Upgrade-Insecure-Requests": "1",
}

# Separate headers for the workbook download — declare we want the xlsx
# MIME type and set a Referer so the request looks like it came from the
# landing page.  Some anti-bot layers check Referer.
_XLSX_HEADERS = {
    "User-Agent":      USER_AGENT,
    "Accept":          (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,"
        "application/vnd.ms-excel,application/octet-stream,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer":         IFO_LANDING,
}

# First bytes of a valid .xlsx (ZIP archive) file.
_XLSX_MAGIC = b"PK\x03\x04"

# ---------------------------------------------------------------------------
# BRIGHT DATA WEB UNLOCKER CONFIG
# ---------------------------------------------------------------------------
# REST endpoint (verified from docs.brightdata.com/scraping-automation/
# web-unlocker/send-your-first-request).  Always POSTed with a JSON body;
# the upstream URL goes in the `url` field, the upstream method defaults to
# GET, and `format: "raw"` streams the upstream body back unmodified — which
# is what we need for binary xlsx.
_BRIGHTDATA_ENDPOINT = "https://api.brightdata.com/request"
_BRIGHTDATA_DEFAULT_ZONE = "web_unlocker1"
# Per-run safety cap.  At the limit, _call_brightdata raises
# _BudgetExhausted and the caller treats it as a clean SKIP.  Bumping this
# is fine; it exists to stop a misbehaving retry loop from draining the
# user's 5,000/month free-tier quota in a single workflow run.
_MAX_BRIGHTDATA_CALLS_PER_RUN = 30
_BRIGHTDATA_CALLS = 0


class _BudgetExhausted(RuntimeError):
    """Raised when the per-run Bright Data call cap is reached."""


def _brightdata_credentials() -> tuple[str, str] | None:
    """Return (api_key, zone) if BRIGHTDATA_API_KEY is set, else None."""
    api_key = os.environ.get("BRIGHTDATA_API_KEY", "").strip()
    if not api_key:
        return None
    zone = os.environ.get("BRIGHTDATA_ZONE", "").strip() or _BRIGHTDATA_DEFAULT_ZONE
    return api_key, zone


def _call_brightdata(url: str, timeout: int = 60) -> bytes | None:
    """
    Fetch `url` through Bright Data Web Unlocker, returning the raw
    upstream body bytes on a 2xx response.  Returns None on any failure
    (non-2xx, network error, or non-xlsx body).  Raises _BudgetExhausted
    if the per-run call cap is hit before the call is made.

    Network-defensive: every exception is swallowed and logged; the
    caller's outer loop falls through to "no data → blank row" without
    crashing the pipeline.
    """
    global _BRIGHTDATA_CALLS
    creds = _brightdata_credentials()
    if creds is None:
        # No credentials — caller will already have logged the SKIP.
        return None
    api_key, zone = creds

    if _BRIGHTDATA_CALLS >= _MAX_BRIGHTDATA_CALLS_PER_RUN:
        print(
            f"  [ifo BUDGET EXHAUSTED] Bright Data per-run cap of "
            f"{_MAX_BRIGHTDATA_CALLS_PER_RUN} reached; refusing further calls "
            f"this process.  No data fetched.",
            flush=True,
        )
        raise _BudgetExhausted(
            f"Bright Data per-run cap of {_MAX_BRIGHTDATA_CALLS_PER_RUN} reached"
        )
    _BRIGHTDATA_CALLS += 1

    payload = {"zone": zone, "url": url, "format": "raw"}
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    print(
        f"  [ifo] Bright Data unlock #{_BRIGHTDATA_CALLS}/"
        f"{_MAX_BRIGHTDATA_CALLS_PER_RUN}: zone={zone!r} url={url}",
        flush=True,
    )
    try:
        r = requests.post(_BRIGHTDATA_ENDPOINT, headers=headers, json=payload, timeout=timeout)
    except requests.exceptions.RequestException as e:
        print(f"  [ifo] Bright Data POST raised {type(e).__name__}: {e}", flush=True)
        return None

    if r.status_code != 200:
        # 401 = bad API key, 403 = target forbids, 502 = upstream fail,
        # 503 = CAPTCHA/check failed.  Log + give up; the outer loop
        # will try the next URL candidate.
        snippet = r.content[:160].replace(b"\n", b" ")
        print(
            f"  [ifo] Bright Data HTTP {r.status_code} for {url}; "
            f"first 160 bytes: {snippet!r}",
            flush=True,
        )
        return None

    if not r.content.startswith(_XLSX_MAGIC):
        # 200 but body isn't xlsx — Bright Data forwarded a non-xlsx
        # response (rare; sometimes a 200 challenge page).  Treat as
        # miss without retrying through Bright Data again on the same
        # URL — the budget is too precious for that.
        ct = r.headers.get("Content-Type", "")
        snippet = r.content[:120].replace(b"\n", b" ")
        print(
            f"  [ifo] Bright Data returned {len(r.content)} bytes "
            f"(ct={ct!r}) not xlsx for {url}; first 120: {snippet!r}",
            flush=True,
        )
        return None

    print(
        f"  [ifo] Bright Data unlock succeeded for {url} "
        f"({len(r.content):,} bytes)",
        flush=True,
    )
    return r.content

# Match gsk-<e|d>-YYYYMM.xlsx (6 digits).
_HREF_RE = re.compile(
    r'href=[\'"]([^\'"]*gsk-[ed]-\d{6}\.xlsx)[\'"]',
    re.IGNORECASE,
)

# The English workbook's row 9 is the data header; rows 1-8 are titles and
# metadata.  Column A is a "MM/YYYY" label; B-I are the numeric series.
EXCEL_COL_NAMES = [
    "yearmonth",
    "climate_index",
    "situation_index",
    "expectation_index",
    "climate_balance",
    "situation_balance",
    "expectation_balance",
    "uncertainty",
    "economic_expansion",
]


# ---------------------------------------------------------------------------
# LIBRARY LOADER
# ---------------------------------------------------------------------------

def load_library() -> list[dict]:
    """Load ifo indicator definitions from macro_library_ifo.csv."""
    df = pd.read_csv(_LIBRARY_CSV, dtype=str, keep_default_na=False)
    df["sort_key"] = pd.to_numeric(df["sort_key"], errors="coerce").fillna(0)
    df = df.sort_values("sort_key")
    result = []
    for _, row in df.iterrows():
        result.append({
            "source":       "ifo",
            "source_id":    row["series_id"].strip(),
            "col":          row["col"].strip(),
            "name":         row["name"].strip(),
            "country":      row["country"].strip(),
            "category":     row["category"].strip(),
            "subcategory":  row["subcategory"].strip(),
            "concept":      row.get("concept", "").strip(),
            "cycle_timing": row.get("cycle_timing", "").strip(),
            "units":        row["units"].strip(),
            "frequency":    row["frequency"].strip(),
            "notes":        row["notes"].strip(),
            "sort_key":     float(row["sort_key"]),
            # Workbook layout: sheet_index is 0-indexed (so 0 = first
            # sheet regardless of language), excel_col is 1-indexed.
            "sheet_index":  int(row["sheet_index"]),
            "excel_col":    int(row["excel_col"]),
            # Legacy alias for any lingering caller:
            "series_id":    row["series_id"].strip(),
        })
    return result


# ---------------------------------------------------------------------------
# WORKBOOK DISCOVERY + DOWNLOAD
# ---------------------------------------------------------------------------

def _iter_recent_yyyymm(months_back: int = 3):
    """Yield (YYYY, MM, 'YYYYMM') tuples for the current month and the
    `months_back` preceding months."""
    today = date.today()
    y, m = today.year, today.month
    for _ in range(months_back + 1):
        yield y, m, f"{y:04d}{m:02d}"
        m -= 1
        if m < 1:
            m = 12
            y -= 1


def _candidate_urls():
    """Generate direct workbook URLs for the current + prior 4 months.

    Verified live via scripts/ifo_probe.py (2026-05-27): the workbooks are
    English files under the `secure/timeseries/` path —
    `gsk-e-202605.xlsx` there returned the real 101 KB workbook, while the
    old `YYYY-MM/` dated-folder path and the German `gsk-d-` variant
    returned a 3038-byte HTML page. We therefore prefer English
    (`gsk-e-`) across all recent months first — the parser's
    EXCEL_COL_NAMES / sheet+column map is calibrated to the English
    workbook — and only fall back to German (`gsk-d-`) if no English month
    resolves. ifo intermittently throttles with the same 3038-byte HTML, so
    _try_download_xlsx retries each URL with backoff."""
    months = list(_iter_recent_yyyymm(months_back=3))
    for _, _, yyyymm in months:
        yield f"{IFO_BASE}/sites/default/files/secure/timeseries/gsk-e-{yyyymm}.xlsx"
    # German fallback only for the most recent 2 months — keeps the
    # worst-case (all-hang) candidate count bounded: 4 gsk-e + 2 gsk-d = 6
    # URLs x 2 attempts x 15s ≈ 3 min ceiling, vs. ~30 min before.
    for _, _, yyyymm in months[:2]:
        yield f"{IFO_BASE}/sites/default/files/secure/timeseries/gsk-d-{yyyymm}.xlsx"


def _try_download_xlsx(session: requests.Session, url: str, retries: int = 2) -> bytes | None:
    """
    GET `url` through `session` and return the body only if it looks like
    a real xlsx (starts with PK\\x03\\x04).  Returns None otherwise.

    ifo intermittently serves a 3038-byte HTML page in place of a workbook
    that does exist (verified via scripts/ifo_probe.py: the same URL returns
    a real xlsx on one request and HTML on another). So a non-xlsx body is
    treated as a *retryable* throttle, not a hard miss — we retry with a
    short backoff before giving up on this URL.

    Timeout is deliberately tight (15s): ifo is a non-critical source (only
    DE_IFO feeds a calculator) and can hang connections when throttling, so
    the whole resolve must fail fast rather than block the daily pipeline.
    """
    for attempt in range(retries):
        try:
            r = session.get(url, headers=_XLSX_HEADERS, timeout=15)
        except requests.exceptions.RequestException as e:
            print(f"  [ifo] GET {url} raised {type(e).__name__}: {e}", flush=True)
        else:
            if r.status_code == 200 and r.content.startswith(_XLSX_MAGIC):
                return r.content
            if r.status_code != 200:
                print(f"  [ifo] GET {url} HTTP {r.status_code} (attempt {attempt + 1}/{retries})", flush=True)
            else:
                ct = r.headers.get("Content-Type", "")
                head = r.content[:80].replace(b"\n", b" ")
                print(
                    f"  [ifo] GET {url} returned {len(r.content)} bytes "
                    f"(ct={ct!r}) not xlsx (attempt {attempt + 1}/{retries}); "
                    f"first 80: {head!r}", flush=True
                )
        if attempt + 1 < retries:
            time.sleep(1)
    return None


# Process-level cache so resolve_workbook() does its network work once even
# though both the snapshot batch and the history builder call it. Caches the
# failure too (as the raised RuntimeError) so a hung/throttled ifo isn't
# re-attempted a second time within the same run.
_RESOLVE_CACHE: tuple[str, bytes] | None = None
_RESOLVE_ERROR: Exception | None = None


def resolve_workbook() -> tuple[str, bytes]:
    """Cached wrapper around _resolve_workbook_impl — runs once per process."""
    global _RESOLVE_CACHE, _RESOLVE_ERROR
    if _RESOLVE_CACHE is not None:
        return _RESOLVE_CACHE
    if _RESOLVE_ERROR is not None:
        raise _RESOLVE_ERROR
    try:
        _RESOLVE_CACHE = _resolve_workbook_impl()
        return _RESOLVE_CACHE
    except Exception as e:
        _RESOLVE_ERROR = e
        raise


def _resolve_workbook_impl() -> tuple[str, bytes]:
    """
    Find AND download the ifo workbook.  Returns (url, xlsx_bytes) on
    success.

    Discovery order:
      1. Landing-page scrape (sets cookies) + direct GET on each link.
      2. Direct GET on the canonical secure/timeseries/ URLs for the
         current + prior 3 months.
      3. **Bright Data Web Unlocker** on each candidate URL — only
         reached if every direct attempt returned the 3038-byte
         anti-bot HTML challenge page (or 4xx/5xx).  Skipped silently
         when BRIGHTDATA_API_KEY is not set in the environment.

    Raises RuntimeError if nothing succeeds.
    """
    session = requests.Session()
    session.headers.update(_HTTP_HEADERS)
    tried: list[str] = []
    # Distinct list for the unlock fallback so we don't waste budget on
    # landing-page-only URLs (those were one-shot links scraped from
    # cookied HTML; without that cookie the unlock has nothing to grab).
    direct_url_candidates: list[str] = []

    # Strategy 1: hit landing page (sets cookies) and scrape link(s).
    try:
        resp = session.get(IFO_LANDING, timeout=15)
        if resp.status_code == 200:
            matches = _HREF_RE.findall(resp.text)
            # Prefer English when it's present, else keep the encounter order.
            ordered = sorted(set(matches), key=lambda m: "gsk-e-" not in m.lower())
            for href in ordered:
                url = href if href.startswith("http") else IFO_BASE + href
                tried.append(url)
                content = _try_download_xlsx(session, url)
                if content is not None:
                    print(f"  [ifo] Landing-page scrape resolved + validated: {url}")
                    return url, content
            if not matches:
                print(
                    "  [ifo] Landing page returned HTML but no gsk-*.xlsx link; "
                    "trying direct URL fallback."
                )
        else:
            print(
                f"  [ifo] Landing page HTTP {resp.status_code}; "
                "trying direct URL fallback."
            )
    except requests.exceptions.RequestException as e:
        print(f"  [ifo] Landing-page scrape raised {type(e).__name__}: {e}")

    # Strategy 2: direct URL construction, validated per candidate.
    for candidate in _candidate_urls():
        tried.append(candidate)
        direct_url_candidates.append(candidate)
        content = _try_download_xlsx(session, candidate)
        if content is not None:
            print(f"  [ifo] Direct-URL resolve + validated: {candidate}")
            return candidate, content

    # Strategy 3: Bright Data Web Unlocker.  Only invoked if every direct
    # attempt above failed.  This is the documented anti-bot bypass; the
    # ifo challenge layer started blocking the direct path consistently in
    # May 2026.  Each call costs 1 against the user's 5,000/month
    # free-tier quota — the _MAX_BRIGHTDATA_CALLS_PER_RUN guard above
    # caps per-run spend at 30 to absorb a misbehaving retry loop.
    if _brightdata_credentials() is None:
        print(
            "  [ifo] BRIGHTDATA_API_KEY not set — skipping Web Unlocker "
            "fallback.  Set the secret in GitHub Actions to enable.",
            flush=True,
        )
    else:
        print(
            f"  [ifo] Direct fetch exhausted ({len(direct_url_candidates)} "
            f"candidates); trying Bright Data Web Unlocker.",
            flush=True,
        )
        for candidate in direct_url_candidates:
            try:
                content = _call_brightdata(candidate)
            except _BudgetExhausted:
                # Don't keep iterating — the cap is final for this run.
                break
            if content is not None:
                print(f"  [ifo] Bright Data resolve + validated: {candidate}")
                return candidate, content

    raise RuntimeError(
        f"Could not resolve a valid ifo workbook.  Tried {len(tried)} URL(s); "
        f"landing-page scrape, direct fetch, and Bright Data Web Unlocker "
        f"(if credentialed) all failed.  Last tried: "
        f"{tried[-1] if tried else '(none)'}"
    )


def resolve_workbook_url() -> str:
    """Backward-compatible shim — callers that don't need the bytes."""
    url, _ = resolve_workbook()
    return url


def download_workbook(url: str) -> bytes:
    """
    Download the workbook from `url` and verify it's a real xlsx.
    Kept for callers that already have a URL in hand; new code should
    prefer `resolve_workbook()` which combines both steps.
    """
    session = requests.Session()
    session.headers.update(_HTTP_HEADERS)
    content = _try_download_xlsx(session, url)
    if content is None:
        raise RuntimeError(f"Download of {url} did not return a valid xlsx")
    return content


# ---------------------------------------------------------------------------
# WORKBOOK PARSER
# ---------------------------------------------------------------------------

def parse_workbook(xlsx_bytes: bytes, indicators: list[dict]) -> pd.DataFrame:
    """
    Parse the ifo workbook.  Each indicator dict specifies a 0-indexed
    `sheet_index` and a 1-indexed `excel_col`; the parser reads strictly
    by position so it works on both English and German workbooks (whose
    sheet names differ but whose sheet order and column layout match).

    Workbook layout assumptions (verified against gsk-e-202604.xlsx
    English and gsk-d-* German variants):
      - Sheet 0 ("ifo Business Climate" / "ifo Geschäftsklima") holds
        the headline composite plus Uncertainty + Cycle Tracer.
      - Sheet 1 ("Sectors" / "Branchen") holds Industry+Trade and the
        per-sector Climate / Situation / Expectations balances.
      - Both sheets: rows 1-8 are titles + merged headers, row 9 is a
        blank spacer, rows 10+ are data, column A is " MM/YYYY" (note
        the leading space — we strip it before parsing).

    Each sheet is read once, even if multiple indicators pull columns
    from it.  Series across different sheets are outer-joined on the
    month-end date index.
    """
    from collections import defaultdict

    xf = pd.ExcelFile(io.BytesIO(xlsx_bytes), engine="openpyxl")
    by_sheet: dict[int, list[dict]] = defaultdict(list)
    for indic in indicators:
        by_sheet[indic["sheet_index"]].append(indic)

    frames: list[pd.DataFrame] = []
    for sheet_idx, sheet_indicators in by_sheet.items():
        if sheet_idx >= len(xf.sheet_names):
            print(
                f"  [ifo] WARNING: sheet_index {sheet_idx} out of range "
                f"(workbook has {len(xf.sheet_names)} sheets); skipping"
            )
            continue
        sheet_name = xf.sheet_names[sheet_idx]
        print(f"  [ifo] Reading sheet {sheet_idx}: {sheet_name!r}")

        # skiprows=9 drops the 8 title/header rows plus the blank spacer
        # on row 9.  Row 10 (01/1991 for sheet 1, 01/2005 for sheet 0)
        # becomes the first row of the DataFrame.
        df = pd.read_excel(xf, sheet_name=sheet_name, skiprows=9, header=None, engine="openpyxl")

        if df.empty or df.shape[1] < 2:
            print(f"  [ifo] WARNING: sheet {sheet_idx}/{sheet_name!r} returned no usable data")
            continue

        # Column A (1-indexed) → 0-indexed first column.  Strings have a
        # leading space (" 01/2005") so .str.strip() before parsing.
        date_raw = df.iloc[:, 0].astype(str).str.strip()
        dates = pd.to_datetime(date_raw, format="%m/%Y", errors="coerce")
        valid = dates.notna()
        df = df.loc[valid].copy()
        df.index = dates.loc[valid] + pd.offsets.MonthEnd(0)

        sheet_out = pd.DataFrame(index=df.index)
        for indic in sheet_indicators:
            col_idx = indic["excel_col"] - 1  # 1-indexed → 0-indexed
            if col_idx >= df.shape[1]:
                print(
                    f"  [ifo] WARNING: column {indic['excel_col']} out of range "
                    f"({df.shape[1]} cols) on sheet {sheet_name!r} for {indic['col']}"
                )
                sheet_out[indic["col"]] = pd.NA
                continue
            sheet_out[indic["col"]] = pd.to_numeric(df.iloc[:, col_idx], errors="coerce")
        frames.append(sheet_out)

    if not frames:
        return pd.DataFrame()

    merged = pd.concat(frames, axis=1).sort_index()
    # A month might appear in more than one sheet (same Industry+Trade
    # headline lives in both sheets); collapse to the first non-null.
    merged = merged.groupby(level=0).first()
    return merged.dropna(how="all")
