"""
sources/eurostat.py
===================
Eurostat dissemination API (ec.europa.eu) direct source module.

Keyless JSON-stat 2.0 over REST. No registration, no API key.

    https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/<dataset>
        ?<dim>=<code>&<dim>=<code>&...&format=JSON

Wired §2.A A12 (2026-07-09) to re-source the DG ECFIN Business & Consumer
Survey sentiment trio (``EU_ESI`` / ``EU_IND_CONF`` / ``EU_SVC_CONF``) after
the DB.nomics Eurostat provider mirror froze (last converted 2026-01-22) AND
the underlying euro-area slice migrated: **Bulgaria adopted the euro on
2026-01-01**, so the aggregate geo code changed from ``EA20`` (frozen at
2025-12, now labelled "Euro area – 20 countries (2023-2025)") to ``EA21``
("Euro area – 21 countries (from 2026)", back-recomputed to 1980-01 and fresh
to the current month). The dataset ``ei_bssi_m_r2`` itself never moved — only
the geo dimension code did. Future euro-area enlargements will bump the code
again (``EA22`` …); when a euro-area Eurostat row goes stale, check the geo
label's "(from YYYY)" suffix first.

Indicator definitions live in ``data/macro_library_eurostat.csv``.

Series ID convention: ``<dataset_code>?<query>`` where ``<query>`` is the
url-encoded dimension filter that pins one observation series, e.g.
``ei_bssi_m_r2?indic=BS-ESI-I&s_adj=SA&geo=EA21&freq=M``. The string after
``?`` is interpreted verbatim as additional query parameters appended to the
API call (same shape convention as ``sources/estat.py``).

JSON-stat 2.0 response shape (relevant fields only)::

    {
      "value": {"0": 95.7, "1": 96.9, ...},        # flat position -> value
      "id": ["freq", "indic", "s_adj", "geo", "time"],
      "size": [1, 1, 1, 1, 558],
      "dimension": {"time": {"category": {"index": {"1980-01": 0, ...}}}, ...}
    }

Because the series_id pins every dimension except ``time`` to a single code
(size 1) and ``time`` is the last (fastest-varying) dimension in ``id``, the
flat ``value`` position equals the ``time`` category index — so the parser
maps positions straight through the inverted time index.
"""

from __future__ import annotations

import pathlib
from datetime import date, datetime
from urllib.parse import parse_qsl

import pandas as pd

from sources.base import fetch_with_backoff


_LIBRARY_CSV = pathlib.Path(__file__).parent.parent / "data" / "macro_library_eurostat.csv"
EUROSTAT_BASE = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
)
DEFAULT_HIST_START = "1970-01-01"


# ---------------------------------------------------------------------------
# LIBRARY LOADER
# ---------------------------------------------------------------------------

def load_library() -> list[dict]:
    """Load Eurostat indicator definitions from macro_library_eurostat.csv.

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
            "source":       "Eurostat",
            "source_id":    row["series_id"].strip(),
            "col":          row["col"].strip(),
            "name":         row["name"].strip(),
            "country":      row.get("country", "").strip() or "EA19",
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
    """Split '<dataset>?indic=..&s_adj=..' → (dataset, {indic:..,s_adj:..})."""
    if "?" not in series_id:
        return series_id.strip(), {}
    dataset, qs = series_id.split("?", 1)
    return dataset.strip(), dict(parse_qsl(qs))


def fetch_series(
    series_id: str,
    start: str = DEFAULT_HIST_START,
    timeout: int = 60,
    retries: int = 3,
    last_n: int | None = None,
) -> dict | None:
    """Fetch a single Eurostat series as parsed JSON-stat, or None on failure.

    series_id: '<dataset>?<dim=code&...>' — the query pins one series.
    last_n:    if set, request only the latest n observations
               (``lastTimePeriod``); much smaller payload for snapshot calls.
               Otherwise the full series from ``start`` (``sinceTimePeriod``).
    """
    dataset, extras = _split_series_id(series_id)
    if not dataset:
        print(f"    [Eurostat] invalid series_id {series_id!r} (expected '<dataset>?<query>')")
        return None

    params = {"format": "JSON"}
    params.update(extras)
    if last_n is not None and last_n > 0:
        params["lastTimePeriod"] = str(last_n)
    elif start:
        # Eurostat accepts YYYY or YYYY-MM for sinceTimePeriod.
        params["sinceTimePeriod"] = start[:7] if len(start) >= 7 and start[4] == "-" else start

    doc = fetch_with_backoff(
        EUROSTAT_BASE + "/" + dataset,
        params=params,
        label=f"Eurostat {series_id}",
        retries=retries,
        timeout=timeout,
    )
    if not isinstance(doc, dict) or "value" not in doc:
        return None
    return doc


# ---------------------------------------------------------------------------
# JSON-STAT PARSING
# ---------------------------------------------------------------------------

def parse_jsonstat(doc: dict, series_id: str) -> list[tuple[date, float]]:
    """Parse a Eurostat JSON-stat response → sorted (date, value) tuples.

    Assumes every dimension except ``time`` is pinned to size 1 (the series_id
    query does this); the flat ``value`` position then equals the ``time``
    category index. Defensive: if a non-time dimension has size > 1 the parse
    is ambiguous and we bail with a warning rather than emit wrong data (the
    PR #208 wrong-slice guard)."""
    obs: list[tuple[date, float]] = []
    if not doc:
        return obs

    dims = doc.get("id", [])
    sizes = doc.get("size", [])
    dimension = doc.get("dimension", {})
    if "time" not in dims:
        print(f"    [Eurostat] no time dimension for {series_id}")
        return obs

    # Guard: every non-time dimension must be pinned to a single code, else the
    # flat position no longer maps 1:1 to the time index.
    for name, sz in zip(dims, sizes):
        if name != "time" and sz != 1:
            print(f"    [Eurostat] dimension {name!r} not pinned (size={sz}) for {series_id} — refusing ambiguous slice")
            return obs

    time_index = dimension.get("time", {}).get("category", {}).get("index", {})
    if not time_index:
        print(f"    [Eurostat] empty time index for {series_id}")
        return obs
    pos_to_label = {int(pos): label for label, pos in time_index.items()}

    value = doc.get("value", {})
    # JSON-stat 'value' may be a dict {pos: val} (sparse) or a list [val, ...].
    if isinstance(value, list):
        items = enumerate(value)
    else:
        items = ((int(k), v) for k, v in value.items())

    for pos, val in items:
        if val is None:
            continue
        label = pos_to_label.get(pos)
        if label is None:
            continue
        d = _parse_period(label)
        if d is None:
            continue
        try:
            obs.append((d, float(val)))
        except (ValueError, TypeError):
            continue

    return sorted(obs)


def _parse_period(p: str) -> date | None:
    """Parse a Eurostat time label → calendar date (period-end conventions
    match OECD/ECB: monthly → 1st, quarterly → last month of quarter, annual →
    year-end)."""
    p = (p or "").strip()
    if not p:
        return None
    # Monthly YYYY-MM
    try:
        return datetime.strptime(p + "-01", "%Y-%m-%d").date()
    except ValueError:
        pass
    # Daily YYYY-MM-DD
    try:
        return datetime.strptime(p, "%Y-%m-%d").date()
    except ValueError:
        pass
    # Quarterly YYYY-Qn
    if "-Q" in p:
        try:
            yr, q = p.split("-Q")
            return date(int(yr), int(q) * 3, 1)
        except (ValueError, IndexError):
            pass
    # Annual YYYY
    if len(p) == 4 and p.isdigit():
        return date(int(p), 12, 31)
    return None


def fetch_series_as_pandas(
    series_id: str,
    start: str = DEFAULT_HIST_START,
    col_name: str | None = None,
    last_n: int | None = None,
) -> pd.Series | None:
    """Fetch one series and return a date-indexed pd.Series, or None on failure."""
    doc = fetch_series(series_id, start=start, last_n=last_n)
    if doc is None:
        return None
    obs = parse_jsonstat(doc, series_id)
    if not obs:
        return None
    s = pd.Series(
        {pd.Timestamp(d): v for d, v in obs},
        name=col_name or series_id,
    )
    return s.sort_index()
