"""
sources/fred.py
===============
FRED (Federal Reserve Economic Data) source module.  Single home for:
  - loading indicator metadata from data/macro_library_fred.csv
  - fetching observations from the FRED API
  - parsing FRED JSON responses

Coordinators that consume this module:
  - fetch_macro_us_fred.py     — US snapshot (macro_us tab)
  - fetch_macro_international.py — FRED-intl rows merged into macro_intl
  - fetch_hist.py              — US history (macro_us_hist tab)

The module is side-effect-free: no CSV writing, no Sheets pushing.
"""

from __future__ import annotations

import pathlib
import time

import pandas as pd
import requests

_LIBRARY_CSV = pathlib.Path(__file__).parent.parent / "data" / "macro_library_fred.csv"

# FRED REST endpoints
OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"
SERIES_META_URL  = "https://api.stlouisfed.org/fred/series"

# Default request-delay + backoff tuning.  Callers can override.
DEFAULT_DELAY        = 0.6   # seconds between sequential FRED calls (~100 req/min)
DEFAULT_BACKOFF_BASE = 2
DEFAULT_MAX_RETRIES  = 5


# ---------------------------------------------------------------------------
# LIBRARY LOADERS
# ---------------------------------------------------------------------------

def _load_raw() -> pd.DataFrame:
    """Read macro_library_fred.csv as strings; numeric sort_key."""
    try:
        df = pd.read_csv(_LIBRARY_CSV, dtype=str, keep_default_na=False)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"macro_library_fred.csv not found at {_LIBRARY_CSV}. "
            "Restore the file before running."
        )
    df["sort_key"] = pd.to_numeric(df["sort_key"], errors="coerce").fillna(0)
    return df


def load_us_library() -> tuple[dict, dict]:
    """
    US FRED library: rows where `country` column is blank.

    Returns:
        (FRED_MACRO_US, FRED_MACRO_US_FREQ)

        FRED_MACRO_US      : {series_id: (name, category, subcategory, units, notes)}
        FRED_MACRO_US_FREQ : {series_id: frequency_string}

    Row order in the CSV controls display order in the macro_us output.
    """
    df = _load_raw()
    us = df[df["country"].str.strip() == ""].sort_values("sort_key")
    macro_us = {
        row["series_id"]: (
            row["name"],
            row["category"],
            row["subcategory"],
            row["units"],
            row["notes"],
        )
        for _, row in us.iterrows()
    }
    freq_map = {row["series_id"]: row["frequency"] for _, row in us.iterrows()}
    return macro_us, freq_map


def load_us_library_as_list() -> list[dict]:
    """
    US FRED library as a list of dicts (not the legacy tuple shape).
    Used by the unified fetch_macro_economic coordinator.  Every dict has
    the unified indicator schema: source_id, col, name, country, category,
    subcategory, concept, cycle_timing, units, frequency, notes, sort_key.
    For US series `country` is forced to "USA" and `col` = series_id.
    """
    df = _load_raw()
    us = df[df["country"].str.strip() == ""].sort_values("sort_key")
    return [
        {
            "source":       "FRED",
            "source_id":    row["series_id"].strip(),
            "col":          row["series_id"].strip(),
            "name":         row["name"].strip(),
            "country":      "USA",
            "category":     row["category"].strip(),
            "subcategory":  row["subcategory"].strip(),
            "concept":      row.get("concept", "").strip(),
            "cycle_timing": row.get("cycle_timing", "").strip(),
            "units":        row["units"].strip(),
            "frequency":    row["frequency"].strip(),
            "notes":        row["notes"].strip(),
            "sort_key":     float(row["sort_key"]),
        }
        for _, row in us.iterrows()
    ]


def load_intl_library() -> list[dict]:
    """
    International FRED library: rows where `country` column is non-blank.
    Each row becomes a dict with the keys expected by
    fetch_macro_international.py: col, name, category, units, frequency,
    notes, source, country, fred_id, plus concept + cycle_timing (added
    in Stage 2).
    """
    df = _load_raw()
    intl = df[df["country"].str.strip() != ""].sort_values("sort_key")
    result = []
    for _, row in intl.iterrows():
        col = row["col"].strip() if row["col"].strip() else row["series_id"]
        result.append({
            "source":       "FRED",
            "source_id":    row["series_id"].strip(),
            "col":          col,
            "name":         row["name"].strip(),
            "country":      row["country"].strip(),
            "category":     row["category"].strip(),
            "subcategory": row.get("subcategory", "").strip(),
            "concept":      row.get("concept", "").strip(),
            "cycle_timing": row.get("cycle_timing", "").strip(),
            "units":         row["units"].strip(),
            "frequency":     row["frequency"].strip(),
            "notes":         row["notes"].strip(),
            "sort_key":      float(row["sort_key"]),
            # Legacy aliases retained for existing callers in
            # fetch_macro_international.py (fred_id, source).
            "fred_id":       row["series_id"].strip(),
        })
    return result


# ---------------------------------------------------------------------------
# LIBRARY VALIDATION
# ---------------------------------------------------------------------------

def validate_series(
    indicators: list[dict],
    api_key: str,
    label_prefix: str = "FRED",
    delay: float = 0.3,
) -> list[str]:
    """
    Call /series?series_id=... for each indicator to confirm it exists.
    `indicators` is a list of dicts with at least {series_id, name}.
    Returns a list of warning strings; empty list = all valid.
    Skipped silently if api_key is empty.
    """
    if not api_key:
        print(f"  [{label_prefix}] FRED_API_KEY not set — skipping validation")
        return []

    warnings = []
    total = len(indicators)
    print(f"\nValidating {total} series against FRED API...")

    for i, indic in enumerate(indicators, 1):
        sid = indic["series_id"]
        try:
            resp = requests.get(
                SERIES_META_URL,
                params={"series_id": sid, "api_key": api_key, "file_type": "json"},
                timeout=10,
            )
            time.sleep(delay)

            if resp.status_code == 200:
                seriess = resp.json().get("seriess", [])
                if seriess:
                    official = seriess[0]["title"]
                    print(f"  [{i}/{total}] {sid}")
                    print(f"    csv : {indic.get('name', '')}")
                    print(f"    fred: {official}")
                else:
                    warnings.append(
                        f"FRED '{sid}' returned no results — verify series_id"
                    )
            else:
                warnings.append(f"FRED '{sid}' HTTP {resp.status_code}")
        except Exception as e:
            print(f"  [SKIP] {sid}: validation error — {e}")

    return warnings


# ---------------------------------------------------------------------------
# OBSERVATION FETCH
# ---------------------------------------------------------------------------

def fetch_observations(
    series_id: str,
    api_key: str,
    start: str | None = None,
    end: str | None = None,
    limit: int | None = None,
    sort_order: str = "asc",
    timeout: int = 20,
    retries: int = DEFAULT_MAX_RETRIES,
    backoff_base: int = DEFAULT_BACKOFF_BASE,
    label: str | None = None,
) -> dict | None:
    """
    Fetch observations for a FRED series with exponential backoff.

    Returns the parsed JSON dict (not yet decoded into tuples) so callers
    can inspect the raw payload if they need extra metadata.  Use
    parse_observations() to convert to (date, value) tuples.

    Returns None on unrecoverable failure.
    """
    if not api_key:
        return None

    params: dict[str, object] = {
        "series_id": series_id,
        "api_key":   api_key,
        "file_type": "json",
        "sort_order": sort_order,
    }
    if start is not None:
        params["observation_start"] = start
    if end is not None:
        params["observation_end"] = end
    if limit is not None:
        params["limit"] = limit

    log_label = label or series_id

    for attempt in range(retries):
        try:
            resp = requests.get(OBSERVATIONS_URL, params=params, timeout=timeout)

            if resp.status_code == 200:
                return resp.json()

            if resp.status_code == 429 or resp.status_code >= 500:
                wait = backoff_base ** (attempt + 1)
                print(
                    f"  [FRED] HTTP {resp.status_code} on {log_label} — "
                    f"backoff {wait}s (attempt {attempt+1}/{retries})"
                )
                time.sleep(wait)
                continue

            print(f"  [FRED] HTTP {resp.status_code} on {log_label} — skipping")
            return None

        except requests.exceptions.Timeout:
            wait = backoff_base ** (attempt + 1)
            print(f"  [FRED] Timeout on {log_label} — backoff {wait}s")
            time.sleep(wait)

        except requests.exceptions.RequestException as e:
            print(f"  [FRED] Request error on {log_label}: {e} — skipping")
            return None

    print(f"  [FRED] All {retries} attempts failed for {log_label} — skipping")
    return None


def parse_observations(data: dict | None) -> list[tuple[str, float]]:
    """
    Extract valid (date_string, float_value) tuples from a FRED response.
    Order is whatever the caller requested via sort_order in fetch_observations.
    Non-numeric ("."), empty, or missing values are dropped.
    """
    if not data or "observations" not in data:
        return []
    out: list[tuple[str, float]] = []
    for o in data["observations"]:
        val = o.get("value")
        if val in (".", "", None):
            continue
        try:
            out.append((o["date"], float(val)))
        except (TypeError, ValueError, KeyError):
            continue
    return out


def fetch_latest_prior(
    series_id: str,
    api_key: str,
    lookback_start: str | None = None,
    limit: int = 24,
) -> tuple[float | None, float | None, str | None]:
    """
    Convenience helper for snapshot output: fetch the most recent `limit`
    observations (descending), return (latest_value, prior_value, latest_date).

    lookback_start bounds how far back the server searches.  Default None
    (FRED uses its full history).
    """
    data = fetch_observations(
        series_id,
        api_key,
        start=lookback_start,
        limit=limit,
        sort_order="desc",
        timeout=15,
    )
    if not data or "observations" not in data:
        return None, None, None
    obs = [o for o in data["observations"] if o.get("value") not in (".", "", None)]
    if not obs:
        return None, None, None

    latest = obs[0]
    prior = obs[1] if len(obs) > 1 else None
    try:
        latest_val = float(latest["value"])
    except (ValueError, TypeError):
        return None, None, None
    try:
        prior_val = float(prior["value"]) if prior else None
    except (ValueError, TypeError):
        prior_val = None

    return latest_val, prior_val, latest.get("date", "")


def fetch_series_as_pandas(
    series_id: str,
    api_key: str,
    start: str,
) -> pd.Series | None:
    """
    Fetch a full series since `start` and return it as a pd.Series indexed
    by DatetimeIndex (sorted ascending).  Returns None if no data.
    """
    data = fetch_observations(
        series_id, api_key, start=start, limit=100_000, sort_order="asc"
    )
    obs = parse_observations(data)
    if not obs:
        return None
    s = pd.Series({d: v for d, v in obs}, name=series_id)
    s.index = pd.to_datetime(s.index)
    return s


# ---------------------------------------------------------------------------
# INTL MONTHLY HELPER
# ---------------------------------------------------------------------------

def parse_monthly_by_country(
    data: dict | None, country_code: str
) -> dict[str, list[tuple[str, float]]]:
    """
    Parse a FRED response into {country_code: [(YYYY-MM, val), ...]} with
    dates truncated to year-month — matches the OECD monthly shape used in
    fetch_macro_international.py.  Returns {} on failure.
    """
    obs = parse_observations(data)
    if not obs:
        return {}
    pairs = [(date_str[:7], val) for date_str, val in obs]
    return {country_code: pairs}
