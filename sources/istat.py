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

The historical resolve-on-every-call strategy used an empty-EDITION
wildcard probe which the server services by enumerating every vintage
— that probe routinely times out at 30s+ (see 2026-06-12 ops post-
mortem). The current strategy is a per-series ``data/istat_edition_cache.csv``
cache: pin the cached EDITION on every call (fast path); on a 404 (cached
edition has been superseded by a new release) do ONE wildcard probe to
discover the freshest EDITION, cache it, then re-fetch pinned. The
wildcard is fast on a healthy gateway (~2-3s) but only runs on edition
turnover, so daily runs are dominated by the fast pinned path. EDITION
labels include an unpredictable per-release suffix (e.g. ``2026M5G29``
where ``G29`` is the publication day of the release), so brute-forcing
the next label is infeasible — only the wildcard probe + ``_latest_edition``
can name the actual vintage. Cache file is committed to the repo so
daily runs start hot.

Series ID convention: ``<flow>/<key>``. For vintaged dataflows leave the
final (EDITION) slot empty, e.g. ``151_874/M.IT.UNEM_R.N.1.Y15-74.``
(trailing dot). For non-vintaged dataflows give the full key,
e.g. ``115_333/M.IT.IND_PROD_21.Y.0020``.
"""

from __future__ import annotations

import io
import pathlib
import time
from datetime import date, datetime, timezone

import pandas as pd
import requests


_LIBRARY_CSV = pathlib.Path(__file__).parent.parent / "data" / "macro_library_istat.csv"
_CACHE_CSV = pathlib.Path(__file__).parent.parent / "data" / "istat_edition_cache.csv"
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
    timeout: int = 30,
    retries: int = 3,
) -> str | None:
    """GET one ISTAT data CSV; bounded retries for the flaky 503 gateway.

    Budget tuned 2026-06-12 from (timeout=90, retries=6) to (30, 3) after a
    full-outage day burned ~60min of pipeline time on 3 stuck series. Worst-
    case dead-wait per series drops from ~570s to ~97s while still allowing
    a transient 503 cycle to clear. No process-wide circuit breaker on top:
    if the gateway flips on between calls, we want to capture whichever
    series do come back."""
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


def _has_wildcard_edition(key: str) -> bool:
    """True if the key's last dimension slot is empty (trailing dot) — i.e.
    a vintaged dataflow where we resolve EDITION at fetch time."""
    return key.endswith(".")


def _infer_freq(key: str) -> str:
    """SDMX frequency lives in the first dimension: M / Q / A / D."""
    return key.split(".", 1)[0] if "." in key else ""


# ---------------------------------------------------------------------------
# EDITION CACHE
# ---------------------------------------------------------------------------

def _load_cache() -> dict[str, str]:
    """Read `data/istat_edition_cache.csv` → {series_id: last_known_edition}."""
    if not _CACHE_CSV.exists():
        return {}
    try:
        df = pd.read_csv(_CACHE_CSV, dtype=str, keep_default_na=False)
        return {
            row["series_id"]: row["last_known_edition"]
            for _, row in df.iterrows()
            if row.get("series_id") and row.get("last_known_edition")
        }
    except Exception as e:
        print(f"    [ISTAT cache] read failed ({e}); treating as empty")
        return {}


def _save_cache(cache: dict[str, str]) -> None:
    """Persist cache sorted by series_id (stable git diffs). Best-effort —
    a write failure logs but doesn't bubble."""
    try:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        rows = [
            {"series_id": k, "last_known_edition": v, "last_resolved_at": today}
            for k, v in sorted(cache.items())
        ]
        pd.DataFrame(rows, columns=["series_id", "last_known_edition", "last_resolved_at"]).to_csv(
            _CACHE_CSV, index=False
        )
    except Exception as e:
        print(f"    [ISTAT cache] write failed ({e}); continuing")


def _wildcard_resolve_edition(flow: str, key: str) -> str | None:
    """One small wildcard probe (lastN=1 across all editions) to discover
    the freshest EDITION label, then return it. The probe is fast on a
    healthy gateway (~2-3s observed) and serves as the cache-miss path —
    pinning is otherwise impossible because EDITION labels include an
    unpredictable per-release suffix (e.g. `2026M5G29` where `G29` is the
    publication day of the release). Returns None on timeout / empty."""
    text = _fetch_csv(flow, key, last_n=1)
    if not text:
        return None
    df, has_ed = _parse_rows(text)
    if df is None or not has_ed:
        return None
    return _latest_edition(df)


# Module-level cache: loaded once per process; mutated as we resolve.
_EDITION_CACHE: dict[str, str] = _load_cache()


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
            history. For vintaged dataflows the EDITION is resolved via the
            persistent cache → probe-forward fallback (no expensive wildcard
            probe). See module docstring."""
    if "/" not in series_id:
        print(f"    [ISTAT] invalid series_id {series_id!r} (expected '<FLOW>/<KEY>')")
        return None
    flow, key = series_id.split("/", 1)

    if not _has_wildcard_edition(key):
        # Non-vintaged dataflow — direct fetch.
        df, _ = _parse_rows(_fetch_csv(flow, key, last_n=last_n) or "")
        if df is None:
            return None
        obs = _rows_to_obs(df)
    else:
        # Vintaged — try cached EDITION first, fall back to probe-forward.
        text, edition_used = _resolve_vintaged_csv(flow, key, series_id, last_n)
        if text is None:
            return None
        df, has_ed = _parse_rows(text)
        if df is None:
            return None
        if has_ed and df["EDITION"].nunique() > 1:
            df = df[df["EDITION"].astype(str) == str(edition_used)]
        obs = _rows_to_obs(df)

    if not obs:
        return None
    s = pd.Series(
        {pd.Timestamp(d): v for d, v in obs},
        name=col_name or series_id,
    )
    s = s.sort_index()
    return s


def _resolve_vintaged_csv(
    flow: str,
    key: str,
    series_id: str,
    last_n: int | None,
) -> tuple[str | None, str | None]:
    """Cache-first EDITION resolution. Fast path: pin the cached EDITION
    and fetch in one call. Slow path: on cache miss or pinned-fetch 404,
    do a single wildcard probe to discover the freshest EDITION, cache it,
    then re-fetch pinned. Returns (csv_text, edition_used)."""
    cached_ed = _EDITION_CACHE.get(series_id)

    # 1. Fast path — pin cached and fetch.
    if cached_ed:
        pinned = _pin_edition(key, cached_ed)
        text = _fetch_csv(flow, pinned, last_n=last_n)
        if text:
            return text, cached_ed
        # else: cached edition has been superseded → fall through to discovery.

    # 2. Slow path — one wildcard probe to discover the freshest EDITION.
    fresh_ed = _wildcard_resolve_edition(flow, key)
    if fresh_ed is None:
        print(f"    [ISTAT] could not resolve EDITION for {series_id} "
              f"(cache '{cached_ed or 'cold'}'; wildcard probe failed)")
        return None, None

    # 3. Cache the discovered edition + re-fetch pinned (full dataset path).
    if fresh_ed != cached_ed:
        _EDITION_CACHE[series_id] = fresh_ed
        _save_cache(_EDITION_CACHE)
        print(f"    [ISTAT cache] {series_id}: {cached_ed or '(cold)'} → {fresh_ed}")

    pinned = _pin_edition(key, fresh_ed)
    text = _fetch_csv(flow, pinned, last_n=last_n)
    return text, fresh_ed
