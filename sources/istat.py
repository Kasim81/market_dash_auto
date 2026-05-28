"""
sources/istat.py
================
ISTAT (Istituto Nazionale di Statistica) source module — Italy
(esploradati.istat.it/SDMXWS).

SDMX 2.1 over REST. Serves SDMX-CSV (and SDMX-ML); we use CSV — same shape
as ECB/ABS (TIME_PERIOD + OBS_VALUE columns).

    https://esploradati.istat.it/SDMXWS/rest/data/<flow>/<key>
        ?lastNObservations=<n>

Per G20 catalogue: no registration, no API key. Note: the ISTAT gateway is
flaky and frequently returns transient HTTP 503 ("upstream connect error")
— we retry generously.

EDITION (vintage) handling
--------------------------
Many ISTAT dataflows (national accounts, labour force) carry an EDITION
dimension as the LAST dimension before TIME_PERIOD: each release is a
separate vintage series (e.g. ``2026M4_1``, ``2026M3``). A pinned edition
would freeze the moment a newer vintage is published, so the registry
leaves the EDITION slot empty (trailing dot) and this module resolves the
*latest* edition at fetch time (the vintage whose series carries the most
recent observation), then pins it. Dataflows without an EDITION dimension
(e.g. industrial production 115_333) are fetched verbatim.

Series ID convention: ``<flow>/<key>``. For vintaged dataflows leave the
final (EDITION) slot empty, e.g. ``151_874/M.IT.UNEM_R.N.1.Y15-74.``
(trailing dot). For non-vintaged dataflows give the full key,
e.g. ``115_333/M.IT.IND_PROD_21.Y.0020``.
"""

from __future__ import annotations

import io
import pathlib
import time
from datetime import date, datetime

import pandas as pd
import requests


_LIBRARY_CSV = pathlib.Path(__file__).parent.parent / "data" / "macro_library_istat.csv"
ISTAT_BASE = "https://esploradati.istat.it/SDMXWS/rest/data"
DEFAULT_HIST_START = "1990-01-01"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; market_dash_auto/1.0)",
    "Accept": "text/csv",
}


# ---------------------------------------------------------------------------
# LIBRARY LOADER
# ---------------------------------------------------------------------------

def load_library() -> list[dict]:
    """Load ISTAT indicator definitions from macro_library_istat.csv."""
    if not _LIBRARY_CSV.exists():
        return []
    df = pd.read_csv(_LIBRARY_CSV, dtype=str, keep_default_na=False)
    df["sort_key"] = pd.to_numeric(df["sort_key"], errors="coerce").fillna(0)
    df = df.sort_values("sort_key")
    result = []
    for _, row in df.iterrows():
        result.append({
            "source":       "ISTAT",
            "source_id":    row["series_id"].strip(),
            "col":          row["col"].strip(),
            "name":         row["name"].strip(),
            "country":      row.get("country", "").strip() or "ITA",
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
# RAW FETCH
# ---------------------------------------------------------------------------

def _fetch_csv(
    flow: str,
    key: str,
    last_n: int | None = None,
    timeout: int = 90,
    retries: int = 6,
) -> str | None:
    """GET one ISTAT data CSV; generous retries for the flaky 503 gateway."""
    url = f"{ISTAT_BASE}/{flow}/{key}"
    params = {}
    if last_n is not None and last_n > 0:
        params["lastNObservations"] = last_n

    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, headers=_HEADERS, timeout=timeout)
            if resp.status_code == 200 and resp.text.strip():
                return resp.text
            if resp.status_code == 404:
                # NoRecordsFound — a real "no data" answer, not worth retrying.
                print(f"    [ISTAT 404] {flow}/{key} — no records")
                return None
            if resp.status_code in (429, 503) or resp.status_code >= 500:
                wait = min(2 ** attempt, 16)
                print(f"    [ISTAT HTTP {resp.status_code}] {flow}/{key} — backing off {wait}s")
                time.sleep(wait)
                continue
            print(f"    [ISTAT HTTP {resp.status_code}] {flow}/{key} — skipping")
            return None
        except requests.Timeout:
            wait = min(2 ** attempt, 16)
            print(f"    [ISTAT timeout] {flow}/{key} — backing off {wait}s")
            time.sleep(wait)
        except requests.RequestException as e:
            print(f"    [ISTAT request error] {flow}/{key}: {e} — backing off")
            time.sleep(2)

    print(f"    [ISTAT FAIL] {flow}/{key} — {retries} attempts exhausted")
    return None


# ---------------------------------------------------------------------------
# CSV PARSING
# ---------------------------------------------------------------------------

def _parse_rows(text: str) -> tuple[pd.DataFrame | None, bool]:
    """Read CSV → (DataFrame, has_edition). None if unparseable/empty."""
    if not text or not text.strip():
        return None, False
    try:
        df = pd.read_csv(io.StringIO(text))
    except Exception as e:
        print(f"    [ISTAT] CSV parse failed: {e}")
        return None, False
    if "TIME_PERIOD" not in df.columns or "OBS_VALUE" not in df.columns:
        print(f"    [ISTAT] unexpected CSV schema: {list(df.columns)[:8]}")
        return None, False
    return df, ("EDITION" in df.columns)


def _latest_edition(df: pd.DataFrame) -> str | None:
    """Return the EDITION whose rows include the most recent TIME_PERIOD."""
    if "EDITION" not in df.columns:
        return None
    best_ed, best_d = None, None
    for ed, sub in df.groupby("EDITION"):
        d = max((_parse_period(str(p)) for p in sub["TIME_PERIOD"]), default=None)
        if d is None:
            continue
        if best_d is None or d > best_d:
            best_d, best_ed = d, str(ed)
    return best_ed


def _rows_to_obs(df: pd.DataFrame) -> list[tuple[date, float]]:
    """DataFrame (single edition / single series) → list of (date, value)."""
    obs: list[tuple[date, float]] = []
    for _, row in df.iterrows():
        d_str = str(row["TIME_PERIOD"]).strip()
        v_raw = row["OBS_VALUE"]
        if pd.isna(v_raw) or not d_str or d_str.lower() in ("nan", ""):
            continue
        d = _parse_period(d_str)
        if d is None:
            continue
        try:
            v = float(v_raw)
        except (ValueError, TypeError):
            continue
        obs.append((d, v))
    # Defensive: dedupe on period (first wins) and sort.
    merged: dict[date, float] = {}
    for d, v in obs:
        merged.setdefault(d, v)
    return sorted(merged.items())


def _parse_period(p: str) -> date | None:
    """Parse ISTAT period strings to a calendar date.

    Cadences: monthly YYYY-MM, quarterly YYYY-Qn, annual YYYY, daily YYYY-MM-DD.
    """
    p = (p or "").strip()
    if not p:
        return None
    try:
        return datetime.strptime(p, "%Y-%m-%d").date()
    except ValueError:
        pass
    if "-Q" in p:
        try:
            yr, q = p.split("-Q")
            return date(int(yr), int(q) * 3, 1)
        except (ValueError, IndexError):
            pass
    try:
        return datetime.strptime(p + "-01", "%Y-%m-%d").date()
    except ValueError:
        pass
    if len(p) == 4 and p.isdigit():
        return date(int(p), 12, 31)
    return None


def _pin_edition(key: str, edition: str) -> str:
    """Replace the final (EDITION) slot of a dotted key with a concrete value."""
    parts = key.split(".")
    parts[-1] = edition
    return ".".join(parts)


# ---------------------------------------------------------------------------
# PUBLIC FETCH
# ---------------------------------------------------------------------------

def fetch_series_as_pandas(
    series_id: str,
    col_name: str | None = None,
    last_n: int | None = None,
) -> pd.Series | None:
    """Fetch one series and return a date-indexed pd.Series, or None on failure.

    last_n: pass a small value (e.g. 3) for snapshot calls. Omit for full
            history. For vintaged dataflows the latest EDITION is resolved
            automatically.
    """
    if "/" not in series_id:
        print(f"    [ISTAT] invalid series_id {series_id!r} (expected '<FLOW>/<KEY>')")
        return None
    flow, key = series_id.split("/", 1)

    # Snapshot path: a single small query is enough; resolve latest edition
    # from whatever comes back.
    if last_n is not None and last_n > 0:
        df, has_ed = _parse_rows(_fetch_csv(flow, key, last_n=last_n) or "")
        if df is None:
            return None
        if has_ed and df["EDITION"].nunique() > 1:
            ed = _latest_edition(df)
            df = df[df["EDITION"].astype(str) == str(ed)]
        obs = _rows_to_obs(df)
    else:
        # History path: for vintaged dataflows, discover the latest edition
        # cheaply (lastN=1 across editions), then pull only that edition's
        # full series — avoids downloading every vintage.
        probe, has_ed = _parse_rows(_fetch_csv(flow, key, last_n=1) or "")
        if probe is None:
            return None
        if has_ed and probe["EDITION"].nunique() >= 1 and probe["EDITION"].notna().any():
            ed = _latest_edition(probe)
            full_key = _pin_edition(key, ed) if ed is not None else key
            df, _ = _parse_rows(_fetch_csv(flow, full_key) or "")
            if df is None:
                return None
            if "EDITION" in df.columns and df["EDITION"].nunique() > 1:
                df = df[df["EDITION"].astype(str) == str(ed)]
        else:
            df, _ = _parse_rows(_fetch_csv(flow, key) or "")
            if df is None:
                return None
        obs = _rows_to_obs(df)

    if not obs:
        return None
    s = pd.Series(
        {pd.Timestamp(d): v for d, v in obs},
        name=col_name or series_id,
    )
    s = s.sort_index()
    return s
