"""
sources/boe.py
==============
Bank of England Interactive Statistical Database (IADB) source module.

IADB is the BoE's free, no-key statistical database. It exposes a CSV
download endpoint:

    https://www.bankofengland.co.uk/boeapps/database/fromshowcolumns.asp
        ?csv.x=yes
        &Datefrom=DD/Mon/YYYY
        &Dateto=DD/Mon/YYYY
        &SeriesCodes=<code>[,...,<code>]   (up to 300)
        &CSVF=TT
        &UsingCodes=Y
        &Filter=N
        &VPD=Y

Per G20 catalogue: no registration, no API key, CSV/Excel only, up to
300 series codes per request.

Indicator definitions live in data/macro_library_boe.csv.

Wired §3.1 Stage D (2026-04-30) to resolve GBR_BANK_RATE (currently
EXPIRED via FRED BOERUKM, frozen 2016-08-05). IUDBEDR is the canonical
BoE Bank Rate series.
"""

from __future__ import annotations

import io
import pathlib
import time
from datetime import date, datetime

import pandas as pd
import requests


_LIBRARY_CSV = pathlib.Path(__file__).parent.parent / "data" / "macro_library_boe.csv"

# IADB endpoint URL. The BoE site has gone through several reorgs over the
# years; we try the canonical paths in order:
#   1. _iadb-fromshowcolumns.asp — listed in the G20 catalogue (April 2026).
#   2. fromshowcolumns.asp        — historical path; often still works as a
#                                   redirect target.
# A bare URL hit returned HTML (the form page) rather than CSV from the
# GitHub Actions runner, indicating the second path now serves the form.
# We try the first; on HTML response we fall back to the second.
BOE_URLS = [
    "https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp",
    "https://www.bankofengland.co.uk/boeapps/database/fromshowcolumns.asp",
]
DEFAULT_HIST_START = "1975-01-01"

# IADB returns HTTP 403 to default python-requests User-Agent (verified
# from GitHub Actions runner, 2026-04-30). A browser-like UA + standard
# Accept headers gets through. This is benign content negotiation —
# IADB itself is open public data with no key required.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/csv,text/plain,application/csv,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}


# ---------------------------------------------------------------------------
# LIBRARY LOADER
# ---------------------------------------------------------------------------

def load_library() -> list[dict]:
    """Load BoE IADB indicator definitions from macro_library_boe.csv."""
    if not _LIBRARY_CSV.exists():
        return []
    df = pd.read_csv(_LIBRARY_CSV, dtype=str, keep_default_na=False)
    df["sort_key"] = pd.to_numeric(df["sort_key"], errors="coerce").fillna(0)
    df = df.sort_values("sort_key")
    result = []
    for _, row in df.iterrows():
        result.append({
            "source":       "BoE",
            "source_id":    row["series_id"].strip(),
            "col":          row["col"].strip(),
            "name":         row["name"].strip(),
            "country":      row.get("country", "").strip() or "GBR",
            "category":     row["category"].strip(),
            "subcategory":  row["subcategory"].strip(),
            "concept":      row.get("concept", "").strip(),
            "cycle_timing": row.get("cycle_timing", "").strip(),
            "units":        row["units"].strip(),
            "frequency":    row["frequency"].strip(),
            "notes":        row.get("notes", "").strip(),
            "sort_key":     float(row["sort_key"]),
            "series_id":    row["series_id"].strip(),
        })
    return result


# ---------------------------------------------------------------------------
# SERIES FETCH
# ---------------------------------------------------------------------------

def fetch_series(
    series_code: str,
    start: str = DEFAULT_HIST_START,
    timeout: int = 30,
    retries: int = 3,
) -> str | None:
    """Fetch a single BoE IADB series as raw CSV text.

    series_code: e.g. 'IUDBEDR' for Bank Rate.
    start: ISO date 'YYYY-MM-DD'; converted to BoE's 'DD/Mon/YYYY' format.
    Returns the raw CSV body (UTF-8 string), or None on error.
    """
    try:
        start_dt = datetime.strptime(start, "%Y-%m-%d")
    except ValueError:
        print(f"    [BoE] invalid start date {start!r}; defaulting to {DEFAULT_HIST_START}")
        start_dt = datetime.strptime(DEFAULT_HIST_START, "%Y-%m-%d")

    today = date.today()
    params = {
        "csv.x": "yes",
        "Datefrom": start_dt.strftime("%d/%b/%Y"),
        "Dateto":   today.strftime("%d/%b/%Y"),
        "SeriesCodes": series_code,
        "CSVF": "TT",
        "UsingCodes": "Y",
        "Filter": "N",
        "title": "",
        "VPD": "Y",
    }

    for attempt in range(retries):
        for base in BOE_URLS:
            try:
                resp = requests.get(base, params=params, headers=_HEADERS, timeout=timeout)
                if resp.status_code != 200 or not resp.text:
                    if 500 <= resp.status_code < 600:
                        print(f"    [BoE HTTP {resp.status_code}] {series_code} via {base.rsplit('/', 1)[-1]} — server error")
                    else:
                        print(f"    [BoE HTTP {resp.status_code}] {series_code} via {base.rsplit('/', 1)[-1]}")
                    continue
                # Reject HTML responses (form page) — try the next URL.
                head = resp.text.lstrip()[:200].lower()
                if head.startswith("<!doctype html") or head.startswith("<html"):
                    print(f"    [BoE] {base.rsplit('/', 1)[-1]} returned HTML form (not CSV) — trying alt")
                    continue
                return resp.text
            except requests.Timeout:
                print(f"    [BoE timeout] {series_code} via {base.rsplit('/', 1)[-1]}")
                continue
            except requests.RequestException as e:
                print(f"    [BoE request error] {series_code} via {base.rsplit('/', 1)[-1]}: {e}")
                continue
        # All URLs failed for this attempt; back off before next attempt.
        wait = 2 ** attempt
        print(f"    [BoE] all URLs failed for {series_code} — backing off {wait}s")
        time.sleep(wait)

    print(f"    [BoE FAIL] {series_code} — {retries} attempts × {len(BOE_URLS)} URLs exhausted")
    return None


# ---------------------------------------------------------------------------
# CSV PARSING
# ---------------------------------------------------------------------------
# IADB CSV shape (CSVF=TT):
# The download includes a multi-line title/source preamble before the
# actual data table:
#     "Bank of England"
#     "Bank of England Statistical Interactive Database"
#     ""
#     "Source code","IUDBEDR"
#     "Description","Official Bank Rate"
#     ""
#     DATE,IUDBEDR
#     01 Jan 1975,12.25
#     ...
# We detect the header row dynamically by finding the first line whose
# first comma-separated token (stripped of quotes) equals "DATE", then
# pass that line index to pd.read_csv as `skiprows`.

def parse_csv(text: str, series_code: str) -> list[tuple[date, float]]:
    """Parse IADB CSV response → list of (date, value) tuples (None values dropped)."""
    obs: list[tuple[date, float]] = []
    if not text or not text.strip():
        return obs

    # Locate the data header row (line starting with "DATE,...")
    lines = text.splitlines()
    header_idx = None
    for i, line in enumerate(lines):
        first_token = line.split(",", 1)[0].strip().strip('"').upper()
        if first_token == "DATE":
            header_idx = i
            break
    if header_idx is None:
        print(f"    [BoE] no DATE header row found in {series_code} response "
              f"(first line: {lines[0][:80] if lines else '<empty>'!r})")
        return obs

    try:
        df = pd.read_csv(io.StringIO(text), skiprows=header_idx)
    except Exception as e:
        print(f"    [BoE] CSV parse failed for {series_code}: {e}")
        return obs

    # Normalise columns case-insensitively to find DATE + the series code col.
    cols_lower = {c.strip().lower(): c for c in df.columns}
    date_col = cols_lower.get("date")
    val_col = cols_lower.get(series_code.lower())
    if date_col is None or val_col is None:
        print(f"    [BoE] unexpected CSV schema for {series_code}: {list(df.columns)}")
        return obs

    for _, row in df.iterrows():
        d_str = str(row[date_col]).strip().strip('"')
        v_raw = row[val_col]
        if pd.isna(v_raw):
            continue
        v_str = str(v_raw).strip().strip('"')
        if not d_str or not v_str or v_str.lower() in ("nan", "n/a", ""):
            continue
        # IADB date format: "01 Jan 1975" or sometimes "01/01/1975"
        d = None
        for fmt in ("%d %b %Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%b-%Y"):
            try:
                d = datetime.strptime(d_str, fmt).date()
                break
            except ValueError:
                continue
        if d is None:
            continue
        try:
            v = float(v_str)
        except ValueError:
            continue
        obs.append((d, v))

    return obs


def fetch_series_as_pandas(
    series_code: str,
    start: str = DEFAULT_HIST_START,
    col_name: str | None = None,
) -> pd.Series | None:
    """Fetch one series and return a date-indexed pd.Series, or None on failure."""
    text = fetch_series(series_code, start=start)
    if text is None:
        return None
    obs = parse_csv(text, series_code)
    if not obs:
        return None
    s = pd.Series(
        {pd.Timestamp(d): v for d, v in obs},
        name=col_name or series_code,
    )
    s = s.sort_index()
    return s
