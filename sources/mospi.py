"""
sources/mospi.py
================
MoSPI (Ministry of Statistics & Programme Implementation, India) source module,
served through the Open Government Data platform data.gov.in.

MoSPI is the ultimate (primary) source for Indian macro series (CPI, IIP, etc.)
that aggregators (World Bank, IMF, OECD, DB.nomics) republish — so it ranks as a
PRIMARY source and wins ties.

REST returning JSON records.

    https://api.data.gov.in/resource/<resource_id>?api-key=<key>&format=json

Auth: register at https://data.gov.in/, request an API key (My Account → APIs),
and set it in the ``MOSPI_API_KEY`` env var. It is sent as the ``api-key`` query
parameter. Without a key the module no-ops gracefully; the gap surfaces in the
daily audit.

Series ID convention: ``<resource_id>?period=<field>&value=<field>[&<filter>=..]``
where ``period`` / ``value`` name the date and value columns of that resource
(record schemas differ per resource, so they are declared per series). Any extra
``k=v`` pairs become record-level filters passed through to the API.
Example: ``8f...c3?period=month&value=index&base_year=2012``.
"""

from __future__ import annotations

import os
import pathlib
import time
from datetime import date, datetime
from urllib.parse import parse_qsl

import pandas as pd
import requests


_LIBRARY_CSV = pathlib.Path(__file__).parent.parent / "data" / "macro_library_mospi.csv"
MOSPI_BASE = "https://api.data.gov.in/resource"
DEFAULT_LIMIT = 10000

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; market_dash_auto/1.0)",
    "Accept": "application/json",
}


# ---------------------------------------------------------------------------
# LIBRARY LOADER
# ---------------------------------------------------------------------------

def load_library() -> list[dict]:
    """Load MoSPI indicator definitions from macro_library_mospi.csv.

    Returns [] when the library is empty/absent (scaffold state)."""
    if not _LIBRARY_CSV.exists():
        return []
    df = pd.read_csv(_LIBRARY_CSV, dtype=str, keep_default_na=False)
    if df.empty:
        return []
    df["sort_key"] = pd.to_numeric(df["sort_key"], errors="coerce").fillna(0)
    df = df.sort_values("sort_key")
    result = []
    for _, row in df.iterrows():
        result.append({
            "source":       "MoSPI",
            "source_id":    row["series_id"].strip(),
            "col":          row["col"].strip(),
            "name":         row["name"].strip(),
            "country":      row.get("country", "").strip() or "IND",
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

def _split_series_id(series_id: str) -> tuple[str, dict]:
    """Split '<resource_id>?k=v&...' → (resource_id, {k: v})."""
    if "?" not in series_id:
        return series_id.strip(), {}
    rid, query = series_id.split("?", 1)
    return rid.strip(), dict(parse_qsl(query, keep_blank_values=False))


def fetch_records(
    series_id: str,
    timeout: int = 60,
    retries: int = 3,
) -> tuple[list[dict], dict] | None:
    """Fetch a MoSPI/data.gov.in resource; returns (records, opts) or None.

    opts carries the per-series period/value field names (and filters) parsed
    from the series_id query string. Reads MOSPI_API_KEY from env; without it
    the call is skipped gracefully.
    """
    key = os.environ.get("MOSPI_API_KEY", "").strip()
    if not key:
        print(f"    [MoSPI] no MOSPI_API_KEY env var — skipping {series_id}")
        return None

    resource_id, opts = _split_series_id(series_id)
    if not resource_id:
        print(f"    [MoSPI] invalid series_id {series_id!r}")
        return None

    period_field = opts.pop("period", "")
    value_field = opts.pop("value", "")
    params = {"api-key": key, "format": "json", "limit": DEFAULT_LIMIT}
    # Remaining opts become record-level filters: filters[<field>]=<value>.
    for fk, fv in opts.items():
        params[f"filters[{fk}]"] = fv

    url = f"{MOSPI_BASE}/{resource_id}"
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=_HEADERS, params=params, timeout=timeout)
            if resp.status_code == 200 and resp.text.strip():
                try:
                    doc = resp.json()
                except ValueError as e:
                    print(f"    [MoSPI] JSON decode failed for {resource_id}: {e}")
                    return None
                records = doc.get("records", [])
                return records, {"period": period_field, "value": value_field}
            if resp.status_code in (401, 403):
                print(f"    [MoSPI HTTP {resp.status_code}] {resource_id} — check MOSPI_API_KEY")
                return None
            if 500 <= resp.status_code < 600:
                wait = 2 ** attempt
                print(f"    [MoSPI HTTP {resp.status_code}] {resource_id} — backing off {wait}s")
                time.sleep(wait)
                continue
            print(f"    [MoSPI HTTP {resp.status_code}] {resource_id} — skipping")
            return None
        except requests.Timeout:
            wait = 2 ** attempt
            print(f"    [MoSPI timeout] {resource_id} — backing off {wait}s")
            time.sleep(wait)
        except requests.RequestException as e:
            print(f"    [MoSPI request error] {resource_id}: {e} — skipping")
            return None

    print(f"    [MoSPI FAIL] {resource_id} — {retries} attempts exhausted")
    return None


# ---------------------------------------------------------------------------
# RECORD PARSING
# ---------------------------------------------------------------------------

def parse_records(
    records: list[dict],
    period_field: str,
    value_field: str,
    series_id: str,
) -> list[tuple[date, float]]:
    """Parse data.gov.in records → list of (date, value) tuples."""
    obs: list[tuple[date, float]] = []
    if not records or not period_field or not value_field:
        if records and (not period_field or not value_field):
            print(f"    [MoSPI] {series_id}: period/value field not declared in series_id")
        return obs
    merged: dict[date, float] = {}
    for rec in records:
        d = _parse_period(str(rec.get(period_field, "")), rec)
        if d is None:
            continue
        try:
            merged[d] = float(rec.get(value_field))
        except (ValueError, TypeError):
            continue
    return sorted(merged.items())


_MONTHS = {
    m.lower(): i for i, m in enumerate(
        ["January", "February", "March", "April", "May", "June", "July",
         "August", "September", "October", "November", "December"], start=1)
}
_MONTHS.update({m[:3].lower(): i for m, i in list(_MONTHS.items())})


def _parse_period(p: str, rec: dict | None = None) -> date | None:
    """Parse a MoSPI period token to a calendar date.

    Handles YYYY-MM-DD, YYYY-MM, 'Month YYYY', 'Month' (+ a 'year' field on the
    record), quarterly 'YYYY-Qn', and bare YYYY.
    """
    p = (p or "").strip()
    if not p:
        return None
    try:
        return datetime.strptime(p, "%Y-%m-%d").date()
    except ValueError:
        pass
    try:
        return datetime.strptime(p + "-01", "%Y-%m-%d").date()
    except ValueError:
        pass
    if "-Q" in p:
        try:
            yr, q = p.split("-Q")
            return date(int(yr), int(q) * 3, 1)
        except (ValueError, IndexError):
            pass
    # 'Month YYYY' or a bare month name paired with a 'year' record field.
    parts = p.replace(",", " ").split()
    month = next((_MONTHS[w.lower()] for w in parts if w.lower() in _MONTHS), None)
    if month is not None:
        yr = next((int(w) for w in parts if w.isdigit() and len(w) == 4), None)
        if yr is None and rec is not None:
            try:
                yr = int(str(rec.get("year", "")).strip()[:4])
            except (ValueError, TypeError):
                yr = None
        if yr is not None:
            return date(yr, month, 1)
    if len(p) == 4 and p.isdigit():
        return date(int(p), 12, 31)
    return None


def fetch_series_as_pandas(
    series_id: str,
    col_name: str | None = None,
) -> pd.Series | None:
    """Fetch one series and return a date-indexed pd.Series, or None on failure."""
    got = fetch_records(series_id)
    if got is None:
        return None
    records, opts = got
    obs = parse_records(records, opts["period"], opts["value"], series_id)
    if not obs:
        return None
    s = pd.Series(
        {pd.Timestamp(d): v for d, v in obs},
        name=col_name or series_id,
    )
    return s.sort_index()
