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
BOE_BASE = "https://www.bankofengland.co.uk/boeapps/database/fromshowcolumns.asp"
DEFAULT_HIST_START = "1975-01-01"


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
        try:
            resp = requests.get(BOE_BASE, params=params, timeout=timeout)
            if resp.status_code == 200 and resp.text:
                return resp.text
            if 500 <= resp.status_code < 600:
                wait = 2 ** attempt
                print(f"    [BoE HTTP {resp.status_code}] {series_code} — backing off {wait}s")
                time.sleep(wait)
                continue
            print(f"    [BoE HTTP {resp.status_code}] {series_code} — skipping")
            return None
        except requests.Timeout:
            wait = 2 ** attempt
            print(f"    [BoE timeout] {series_code} — backing off {wait}s")
            time.sleep(wait)
        except requests.RequestException as e:
            print(f"    [BoE request error] {series_code}: {e} — skipping")
            return None

    print(f"    [BoE FAIL] {series_code} — {retries} attempts exhausted")
    return None


# ---------------------------------------------------------------------------
# CSV PARSING
# ---------------------------------------------------------------------------
# IADB CSV shape (CSVF=TT):
#     DATE,IUDBEDR
#     01 Jan 1975,9.50
#     02 Jan 1975,9.50
#     ...
# The header line uses the series code as the column name (matches the code
# we requested via SeriesCodes). Some downloads include a leading title row;
# pandas.read_csv handles that gracefully when we pin the column lookup.

def parse_csv(text: str, series_code: str) -> list[tuple[date, float]]:
    """Parse IADB CSV response → list of (date, value) tuples (None values dropped)."""
    obs: list[tuple[date, float]] = []
    if not text or not text.strip():
        return obs

    try:
        df = pd.read_csv(io.StringIO(text))
    except Exception as e:
        print(f"    [BoE] CSV parse failed for {series_code}: {e}")
        return obs

    # Normalise columns case-insensitively to find DATE + the series code col.
    cols_lower = {c.lower(): c for c in df.columns}
    date_col = cols_lower.get("date")
    val_col = cols_lower.get(series_code.lower())
    if date_col is None or val_col is None:
        print(f"    [BoE] unexpected CSV schema for {series_code}: {list(df.columns)}")
        return obs

    for _, row in df.iterrows():
        d_str = str(row[date_col]).strip()
        v_raw = row[val_col]
        if pd.isna(v_raw):
            continue
        v_str = str(v_raw).strip()
        if not d_str or not v_str or v_str.lower() in ("nan", "n/a", ""):
            continue
        # IADB date format: "01 Jan 1975" or sometimes "01/01/1975"
        d = None
        for fmt in ("%d %b %Y", "%d/%m/%Y", "%Y-%m-%d"):
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
