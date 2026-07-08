"""
sources/bundesbank.py
=====================
Deutsche Bundesbank time-series source module
(api.statistiken.bundesbank.de).

SDMX 2.1 over REST, served as SDMX-ML (the API does NOT support the
SDMX-JSON or CSV flavours — verified live 2026-05-28; JSON/CSV Accept
headers return HTTP 406, ``application/xml`` returns generic-data XML).

    https://api.statistiken.bundesbank.de/rest/data/<flow>/<key>
        ?lastNObservations=<n>   # latest n observations (snapshot fast path)

Per G20 catalogue: no registration, no API key.

Series ID convention: ``<flow>/<key>`` where the key is the full,
dot-separated SDMX dimension tuple, e.g.
``BBSIS/D.I.UMR.RD.EUR.A.B.A.R0910.R.A.A._Z._Z.A`` (daily yield of
domestic bearer debt securities, residual maturity 9-10y). Note: keys must
specify EVERY dimension — e.g. the BBSIS/BBK_SEIS structure has 15
dimensions, so the key has 15 dot-separated values. Getting the count
wrong returns HTTP 404 (verified — the original probe key had 13 values).

Generic-data XML shape:
    <generic:Series>
      <generic:SeriesKey>...</generic:SeriesKey>
      <generic:Obs>
        <generic:ObsDimension value="2026-05-27"/>
        <generic:ObsValue value="3.12"/>
      </generic:Obs>
    </generic:Series>
"""

from __future__ import annotations

import pathlib
import xml.etree.ElementTree as ET
from datetime import date, datetime

import pandas as pd

from sources.base import fetch_with_backoff


_LIBRARY_CSV = pathlib.Path(__file__).parent.parent / "data" / "macro_library_bundesbank.csv"
BBK_BASE = "https://api.statistiken.bundesbank.de/rest/data"
DEFAULT_HIST_START = "1970-01-01"

# Bundesbank only serves SDMX-ML; request generic-data XML explicitly.
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; market_dash_auto/1.0)",
    "Accept": "application/xml",
}

# SDMX 2.1 generic-data namespace.
_GEN = "{http://www.sdmx.org/resources/sdmxml/schemas/v2_1/data/generic}"


# ---------------------------------------------------------------------------
# LIBRARY LOADER
# ---------------------------------------------------------------------------

def load_library() -> list[dict]:
    """Load Bundesbank indicator definitions from macro_library_bundesbank.csv."""
    if not _LIBRARY_CSV.exists():
        return []
    df = pd.read_csv(_LIBRARY_CSV, dtype=str, keep_default_na=False)
    df["sort_key"] = pd.to_numeric(df["sort_key"], errors="coerce").fillna(0)
    df = df.sort_values("sort_key")
    result = []
    for _, row in df.iterrows():
        result.append({
            "source":       "Bundesbank",
            "source_id":    row["series_id"].strip(),
            "col":          row["col"].strip(),
            "name":         row["name"].strip(),
            "country":      row.get("country", "").strip() or "DEU",
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
    series_id: str,
    last_n: int | None = None,
    timeout: int = 60,
    retries: int = 3,
) -> str | None:
    """Fetch a single Bundesbank series as raw SDMX-ML text, or None.

    series_id: '<flow>/<key>' format.
    last_n:    if set, append ?lastNObservations=<n> (snapshot fast path).
    """
    if "/" not in series_id:
        print(f"    [Bundesbank] invalid series_id {series_id!r} (expected '<FLOW>/<KEY>')")
        return None
    url = f"{BBK_BASE}/{series_id}"
    params = {}
    if last_n is not None and last_n > 0:
        params["lastNObservations"] = last_n

    text = fetch_with_backoff(
        url, params=params, label=f"Bundesbank {series_id}", accept_csv=True,
        retries=retries, timeout=timeout, headers=_HEADERS,
    )
    return text if isinstance(text, str) and text.strip() else None


# ---------------------------------------------------------------------------
# XML PARSING
# ---------------------------------------------------------------------------

def parse_xml(text: str, series_id: str) -> list[tuple[date, float]]:
    """Parse Bundesbank generic-data XML → list of (date, value) tuples.

    A single-key request returns one Series; we read every Series' Obs to be
    safe and merge them (period → value, last wins on dupes)."""
    obs: list[tuple[date, float]] = []
    if not text or not text.strip():
        return obs
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        print(f"    [Bundesbank] XML parse failed for {series_id}: {e}")
        return obs

    merged: dict[date, float] = {}
    for series in root.iter(_GEN + "Series"):
        for o in series.findall(_GEN + "Obs"):
            dim = o.find(_GEN + "ObsDimension")
            val = o.find(_GEN + "ObsValue")
            if dim is None or val is None:
                continue
            d = _parse_period(dim.get("value", ""))
            if d is None:
                continue
            try:
                v = float(val.get("value"))
            except (ValueError, TypeError):
                continue
            merged[d] = v
    return sorted(merged.items())


def _parse_period(p: str) -> date | None:
    """Parse Bundesbank TIME_PERIOD strings to a calendar date.

    Cadences: daily YYYY-MM-DD, monthly YYYY-MM, quarterly YYYY-Qn, annual YYYY.
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
    if len(p) == 4 and p.isdigit():
        return date(int(p), 12, 31)
    return None


def fetch_series_as_pandas(
    series_id: str,
    col_name: str | None = None,
    last_n: int | None = None,
) -> pd.Series | None:
    """Fetch one series and return a date-indexed pd.Series, or None on failure."""
    text = fetch_series(series_id, last_n=last_n)
    if text is None:
        return None
    obs = parse_xml(text, series_id)
    if not obs:
        return None
    s = pd.Series(
        {pd.Timestamp(d): v for d, v in obs},
        name=col_name or series_id,
    )
    s = s.sort_index()
    return s
