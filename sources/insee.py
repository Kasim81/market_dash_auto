"""
sources/insee.py
================
INSEE BDM (Banque de Données Macroéconomiques) time-series source module.

INSEE is the ultimate (primary) statistical source for French macro series that
aggregators (Eurostat, OECD, IMF, DB.nomics) merely republish — so it ranks as
a PRIMARY source and wins ties over them.

SDMX 2.1 over REST, served as SDMX-ML.

    https://api.insee.fr/series/BDM/V1/data/<dataset>/<key>

Auth: register an application on the INSEE API portal
(https://portail-api.insee.fr/) subscribed to the "BDM" API, then set the
issued key in the ``INSEE_API_KEY`` env var. It is sent as a Bearer token.
(The legacy api.insee.fr OAuth2 consumer-key/secret token flow is superseded by
the portal-issued key.) Without a key the module no-ops gracefully so the rest
of the pipeline proceeds; the gap surfaces in the daily audit.

Series ID convention: ``<dataset>/<key>`` where key is the SDMX dimension
tuple, e.g. ``CLIMAT-AFFAIRES/000857180``. A bare BDM idbank can be requested
as ``SERIES_BDM/<idbank>``.

Both SDMX-ML shapes are parsed: generic-data (``<Obs><ObsDimension/><ObsValue/>``)
and structure-specific (``<Obs TIME_PERIOD=.. OBS_VALUE=../>``); matching is by
element local-name so it is namespace-version agnostic.
"""

from __future__ import annotations

import os
import pathlib
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime

import pandas as pd
import requests


_LIBRARY_CSV = pathlib.Path(__file__).parent.parent / "data" / "macro_library_insee.csv"
INSEE_BASE = "https://api.insee.fr/series/BDM/V1/data"
DEFAULT_HIST_START = "1970-01-01"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; market_dash_auto/1.0)",
    "Accept": "application/xml",
}


# ---------------------------------------------------------------------------
# LIBRARY LOADER
# ---------------------------------------------------------------------------

def load_library() -> list[dict]:
    """Load INSEE indicator definitions from macro_library_insee.csv.

    Returns [] when the library is empty/absent (scaffold state), so wiring the
    source costs nothing until series are curated.
    """
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
            "source":       "INSEE",
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

def fetch_series(
    series_id: str,
    timeout: int = 60,
    retries: int = 3,
) -> str | None:
    """Fetch a single INSEE BDM series as raw SDMX-ML text, or None.

    series_id: '<dataset>/<key>' (e.g. 'SERIES_BDM/001763852' for an idbank,
    or '<dataflow>/<key>'). The BDM web service is open and keyless; if an
    INSEE_API_KEY is present it is sent as a Bearer token (harmless, and lets a
    metered portal subscription be used), but it is not required.
    """
    if "/" not in series_id:
        print(f"    [INSEE] invalid series_id {series_id!r} (expected '<DATASET>/<KEY>')")
        return None

    url = f"{INSEE_BASE}/{series_id}"
    headers = dict(_HEADERS)
    key = os.environ.get("INSEE_API_KEY", "").strip()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            if resp.status_code == 200 and resp.text.strip():
                return resp.text
            if resp.status_code in (401, 403):
                print(f"    [INSEE HTTP {resp.status_code}] {series_id} — check INSEE_API_KEY")
                return None
            if 500 <= resp.status_code < 600:
                wait = 2 ** attempt
                print(f"    [INSEE HTTP {resp.status_code}] {series_id} — backing off {wait}s")
                time.sleep(wait)
                continue
            print(f"    [INSEE HTTP {resp.status_code}] {series_id} — skipping")
            return None
        except requests.Timeout:
            wait = 2 ** attempt
            print(f"    [INSEE timeout] {series_id} — backing off {wait}s")
            time.sleep(wait)
        except requests.RequestException as e:
            print(f"    [INSEE request error] {series_id}: {e} — skipping")
            return None

    print(f"    [INSEE FAIL] {series_id} — {retries} attempts exhausted")
    return None


# ---------------------------------------------------------------------------
# XML PARSING
# ---------------------------------------------------------------------------

def _local(tag: str) -> str:
    """Strip the namespace from an ElementTree tag → local-name."""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def parse_xml(text: str, series_id: str) -> list[tuple[date, float]]:
    """Parse INSEE SDMX-ML → list of (date, value) tuples.

    Handles both generic-data and structure-specific Obs shapes by matching on
    element local-name (namespace-agnostic)."""
    obs: list[tuple[date, float]] = []
    if not text or not text.strip():
        return obs
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        print(f"    [INSEE] XML parse failed for {series_id}: {e}")
        return obs

    merged: dict[date, float] = {}
    for el in root.iter():
        if _local(el.tag) != "Obs":
            continue
        period_str = el.get("TIME_PERIOD")
        value_str = el.get("OBS_VALUE")
        if period_str is None or value_str is None:
            # generic-data shape: values live in child ObsDimension/ObsValue
            for child in el:
                lname = _local(child.tag)
                if lname == "ObsDimension":
                    period_str = child.get("value", period_str)
                elif lname == "ObsValue":
                    value_str = child.get("value", value_str)
        d = _parse_period(period_str or "")
        if d is None:
            continue
        try:
            merged[d] = float(value_str)
        except (ValueError, TypeError):
            continue
    return sorted(merged.items())


def _parse_period(p: str) -> date | None:
    """Parse an SDMX TIME_PERIOD string to a calendar date.

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
) -> pd.Series | None:
    """Fetch one series and return a date-indexed pd.Series, or None on failure."""
    text = fetch_series(series_id)
    if text is None:
        return None
    obs = parse_xml(text, series_id)
    if not obs:
        return None
    s = pd.Series(
        {pd.Timestamp(d): v for d, v in obs},
        name=col_name or series_id,
    )
    return s.sort_index()
