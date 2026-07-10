"""
sources/bdf.py
==============
Banque de France (Webstat) time-series source module.

Banque de France is the ultimate (primary) source for French monetary,
financial and balance-of-payments series that aggregators (ECB SDW, OECD, IMF,
DB.nomics) republish — so it ranks as a PRIMARY source and wins ties.

REST returning Opendatasoft records JSON.

    https://webstat.banque-france.fr/api/explore/v2.1/catalog/datasets/<dataset_id>/records
        ?where=<ODSQL where-clause>
        &order_by=<time-field>
        &limit=<page-size>
        &offset=<page-offset>

The Webstat portal migrated in 2025/2026 from the legacy IBM API Connect stack
(``api.webstat.banque-france.fr/webstat-fr/v1``, Client Id + Client Secret,
SDMX-JSON) to an Opendatasoft Explore v2.1 instance. This module targets the
new stack only — there is no IBM-stack fallback.

Auth: register on the new developer portal at
``https://webstat.banque-france.fr/`` (Login → API), generate an API key, and
set it in the ``BDF_API_KEY`` env var. The key is sent as
``Authorization: Apikey <key>``. Without a key the module no-ops gracefully;
the gap surfaces in the daily audit.

Series ID convention: ``<dataset_id>|<odsql_where>``, where:

- ``<dataset_id>``  — the Opendatasoft dataset id;
- ``<odsql_where>`` — the ODSQL ``where=`` filter pinning a single series.

Data model (verified 2026-07-09, forward_plan §2.A A6): this Webstat instance
does **not** serve observations through per-series datasets — the individual
``mir-*`` (and every other) catalogue entry is an *empty stub*
(``has_records: false``, ``fields: []``). **Every observation across all
dataflows lives in ONE flat store dataset, ``observations``**, keyed by a
``series_key`` text column of the form ``<DATAFLOW>.<dot-key>`` (e.g.
``MIR1.M.FR.B.A22.A.R.A.2250U6.EUR.N``). So a series is pinned with
``observations|series_key='<KEY>'`` — the dataset_id is always ``observations``
and the where-clause filters ``series_key``. ODSQL string literals use single
quotes, so no CSV double-quote escaping is needed. The ``observations`` record
shape exposes ``time_period`` / ``obs_value`` fields, which the heuristic
parser below auto-detects.

The pipe separator keeps the library CSV schema stable (one ``series_id``
column) and survives URL/HTTP encoding because ``|`` does not appear in
Opendatasoft dataset ids or SDMX series keys.

A ``series_id`` whose dataset_id is ``PROVISIONAL`` (case-insensitive) means
the row has not yet been validated against a live credentialed fetch — the
fetcher logs a clear PROVISIONAL warning and skips the row. The notes column
in the library CSV explains what still needs to be confirmed.

Records JSON shape (per Opendatasoft Explore v2.1):

    {"total_count": N, "results": [{<field>: <value>, ...}, ...]}

The time and value field names vary per dataset; this module discovers them
heuristically (any ``time_period`` / ``date`` / ``period`` field for time;
``obs_value`` / ``value`` for the observation), so the same parser works
across BdF's heterogeneous Opendatasoft schemas.
"""

from __future__ import annotations

import os
import pathlib
import time
from datetime import date, datetime

import pandas as pd
import requests


_LIBRARY_CSV = pathlib.Path(__file__).parent.parent / "data" / "macro_library_bdf.csv"
BDF_BASE = "https://webstat.banque-france.fr/api/explore/v2.1"
DEFAULT_HIST_START = "1970-01-01"
_PAGE_LIMIT = 100  # Opendatasoft Explore v2.1 max per page

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; market_dash_auto/1.0)",
    "Accept": "application/json",
}

# Field-name heuristics for the Opendatasoft records parser. BdF datasets
# vary; these cover the common SDMX-derived column names. Order matters —
# earlier names win.
_TIME_FIELD_CANDIDATES = (
    "time_period", "time_period_string", "time_period_id",
    "date", "period", "period_start", "obs_time",
)
_VALUE_FIELD_CANDIDATES = (
    "obs_value", "value", "observation_value", "obsvalue",
)


# ---------------------------------------------------------------------------
# LIBRARY LOADER
# ---------------------------------------------------------------------------

def load_library() -> list[dict]:
    """Load Banque de France indicator definitions from macro_library_bdf.csv.

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
            "source":       "Banque de France",
            "source_id":    row["series_id"].strip(),
            "col":          row["col"].strip(),
            "name":         row["name"].strip(),
            "country":      row.get("country", "").strip() or "FRA",
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

def _split_series_id(series_id: str) -> tuple[str, str] | None:
    """Split '<dataset_id>|<odsql_where>' into its two parts.

    Returns None if the form is invalid."""
    if "|" not in series_id:
        return None
    dataset_id, _, where_clause = series_id.partition("|")
    dataset_id = dataset_id.strip()
    where_clause = where_clause.strip()
    if not dataset_id or not where_clause:
        return None
    return dataset_id, where_clause


def fetch_series(
    series_id: str,
    timeout: int = 60,
    retries: int = 3,
) -> list[dict] | None:
    """Fetch all observations for a Webstat series as a list of record dicts.

    series_id: '<dataset_id>|<odsql_where>'. Reads BDF_API_KEY from env; without
    it the call is skipped gracefully (returns None).

    Returns the concatenated ``results`` arrays across paginated pages, or None
    on failure / no-key / provisional row.
    """
    key = os.environ.get("BDF_API_KEY", "").strip()
    if not key:
        print(f"    [BdF] no BDF_API_KEY env var — skipping {series_id}")
        return None

    parts = _split_series_id(series_id)
    if parts is None:
        print(
            f"    [BdF] invalid series_id {series_id!r} "
            f"(expected '<dataset_id>|<odsql_where>')"
        )
        return None
    dataset_id, where_clause = parts

    if dataset_id.upper() == "PROVISIONAL":
        print(
            f"    [BdF PROVISIONAL] {series_id} — dataset_id not yet identified; "
            f"see macro_library_bdf.csv notes column"
        )
        return None

    url = f"{BDF_BASE}/catalog/datasets/{dataset_id}/records"
    headers = {**_HEADERS, "Authorization": f"Apikey {key}"}

    # Page through results. Opendatasoft caps page size at 100 and total
    # offset+limit at 10000; that's enough for any monthly/quarterly BdF
    # series within the windows we care about.
    all_results: list[dict] = []
    offset = 0
    while True:
        params = {
            "where": where_clause,
            "limit": _PAGE_LIMIT,
            "offset": offset,
        }
        page = _fetch_page(url, headers, params, series_id, timeout, retries)
        if page is None:
            return None
        results = page.get("results", []) or []
        all_results.extend(results)
        total = page.get("total_count", 0) or 0
        if not results or len(all_results) >= total or offset + _PAGE_LIMIT >= 10000:
            break
        offset += _PAGE_LIMIT
    return all_results


def _fetch_page(
    url: str,
    headers: dict,
    params: dict,
    series_id: str,
    timeout: int,
    retries: int,
) -> dict | None:
    """GET a single page of records, with retry / backoff."""
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=timeout)
            if resp.status_code == 200 and resp.text.strip():
                try:
                    return resp.json()
                except ValueError as e:
                    print(f"    [BdF] JSON decode failed for {series_id}: {e}")
                    return None
            if resp.status_code in (401, 403):
                # Capture the upstream message so the post-mortem can
                # distinguish "invalid Apikey" from "dataset not visible to
                # this app" from "rate-limit exceeded" — Opendatasoft returns
                # each as a distinct JSON body even though the status is the
                # same.
                body = (resp.text or "").strip().replace("\n", " ")[:300]
                print(
                    f"    [BdF HTTP {resp.status_code}] {series_id} "
                    f"url={resp.url!r} body={body!r}"
                )
                return None
            if resp.status_code == 404:
                body = (resp.text or "").strip().replace("\n", " ")[:300]
                print(
                    f"    [BdF HTTP 404] {series_id} url={resp.url!r} "
                    f"body={body!r} — dataset_id likely wrong"
                )
                return None
            if 500 <= resp.status_code < 600:
                wait = 2 ** attempt
                print(f"    [BdF HTTP {resp.status_code}] {series_id} — backing off {wait}s")
                time.sleep(wait)
                continue
            print(f"    [BdF HTTP {resp.status_code}] {series_id} — skipping")
            return None
        except requests.Timeout:
            wait = 2 ** attempt
            print(f"    [BdF timeout] {series_id} — backing off {wait}s")
            time.sleep(wait)
        except requests.RequestException as e:
            print(f"    [BdF request error] {series_id}: {e} — skipping")
            return None

    print(f"    [BdF FAIL] {series_id} — {retries} attempts exhausted")
    return None


# ---------------------------------------------------------------------------
# RECORDS PARSING
# ---------------------------------------------------------------------------

def parse_records(records: list[dict], series_id: str) -> list[tuple[date, float]]:
    """Parse an Opendatasoft records list → sorted (date, value) tuples.

    Field names vary across BdF datasets (some expose ``time_period``, others
    ``date`` or ``period``; values can be ``obs_value`` or just ``value``), so
    the parser discovers them heuristically from the first record. Records
    that fail to parse (missing time / value, bad number) are dropped silently
    — matches `sources/insee.py` behaviour."""
    obs: dict[date, float] = {}
    if not records:
        return []
    time_field = _detect_field(records[0], _TIME_FIELD_CANDIDATES)
    value_field = _detect_field(records[0], _VALUE_FIELD_CANDIDATES)
    if not time_field or not value_field:
        print(
            f"    [BdF] unexpected records shape for {series_id} — "
            f"fields={list(records[0].keys())[:10]}"
        )
        return []
    for rec in records:
        d = _parse_period(rec.get(time_field) or "")
        if d is None:
            continue
        raw = rec.get(value_field)
        if raw is None or raw == "":
            continue
        try:
            obs[d] = float(raw)
        except (ValueError, TypeError):
            continue
    return sorted(obs.items())


def _detect_field(record: dict, candidates: tuple[str, ...]) -> str | None:
    """Pick the first candidate field present in the record, case-insensitive."""
    lookup = {k.lower(): k for k in record.keys()}
    for c in candidates:
        if c in lookup:
            return lookup[c]
    return None


def _parse_period(p: str) -> date | None:
    """Parse an SDMX TIME_PERIOD string to a calendar date.

    Cadences: daily YYYY-MM-DD (incl. ISO-8601 with time), monthly YYYY-MM,
    quarterly YYYY-Qn, annual YYYY.
    """
    p = (p or "").strip()
    if not p:
        return None
    # ISO datetime / date.
    try:
        return datetime.fromisoformat(p.replace("Z", "+00:00")).date()
    except ValueError:
        pass
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
    if len(p) == 4 and p.isdigit():
        return date(int(p), 12, 31)
    return None


def fetch_series_as_pandas(
    series_id: str,
    col_name: str | None = None,
) -> pd.Series | None:
    """Fetch one series and return a date-indexed pd.Series, or None on failure."""
    records = fetch_series(series_id)
    if records is None:
        return None
    obs = parse_records(records, series_id)
    if not obs:
        return None
    s = pd.Series(
        {pd.Timestamp(d): v for d, v in obs},
        name=col_name or series_id,
    )
    return s.sort_index()
