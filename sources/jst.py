"""
sources/jst.py
==============
Jordà-Schularick-Taylor Macrohistory database (§3.13 long-run layer).

The JST Macrohistory database is the canonical long-run cross-country macro
dataset: 18 advanced economies × ~25 series × ~150 years (1870+), annual
frequency. See https://www.macrohistory.net/database/ for the codebook and
release notes (current release as of 2026-06: R6, JSTdatasetR6.dta).

Access is a single Stata-format download. The whole file is small enough
(~5 MB compressed, ~50 MB in memory) that we cache it in-process and slice
per indicator from the cached DataFrame — same pattern as
`sources/ifo.py::_resolve_workbook_impl()`.

Series-ID convention
--------------------
Each library row's `series_id` is a composite of `<country_iso>|<column>`,
e.g. `USA|cpi` for US CPI or `GBR|gdp` for UK real GDP. The fetcher splits
on `|` to know which (country, column) pair to slice from the cached
DataFrame.  JST's wide-format schema has columns: `year`, `iso` (3-letter
country code), `country` (full name), plus one column per series — `cpi`,
`gdp`, `pop`, `eq_tr` (equity total return), `eq_dp` (equity dividend
yield), `bond_rate`, `stir` (short-term rate), `ltrate` (long-term rate),
`housing_capgain`, `debtgdp`, etc. See JST_documentationR6.pdf for the full
column inventory and unit definitions.

Role in regime AA
-----------------
Per the 2026-06-10 regime-AA v2 handoff memo §3.11: JST is a "confirmatory
pre-1950 cross-validation anchor, not as primary regime-engine input." It
gives us 1870+ depth on CPI / real GDP / equity TR / long-rate for the
priority-5 regions (USA/GBR/DEU/FRA/JPN) so downstream regime-label work
can be validated against pre-WWII history without depending on FRED or
OECD post-1957 coverage.

Sandbox access note
-------------------
www.macrohistory.net is on the pipeline allow-list, but some CI hosts and
local dev environments still receive `host_not_allowed` 403s at the network
edge. The fetcher logs the failure and returns None; the smoke test SKIPs
when the host is unreachable.  The daily CI run on the production host
should succeed.
"""

from __future__ import annotations

import io
import pathlib

import pandas as pd
import requests


_LIBRARY_CSV = pathlib.Path(__file__).parent.parent / "data" / "macro_library_jst.csv"

# Canonical release URL. The JST team bumps the version (R5 → R6 → R7…)
# every couple of years; when a new release lands, update _PRIMARY and add
# the old version to _FALLBACKS so we degrade rather than break mid-release.
# Verified 2026-06-10: R6 is the current release.
JST_BASE = "https://www.macrohistory.net"
_PRIMARY = f"{JST_BASE}/app/download/9834512469/JSTdatasetR6.dta"
_FALLBACKS: list[str] = []

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/octet-stream,application/x-stata-dta,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": f"{JST_BASE}/database/",
}


# ---------------------------------------------------------------------------
# LIBRARY LOADER
# ---------------------------------------------------------------------------

def load_library() -> list[dict]:
    """Load JST indicator definitions from macro_library_jst.csv.

    Returns the unified-schema rows other source modules emit so the
    dispatch layer in fetch_macro_economic.py can register them uniformly
    after the parent session wires JST into the dispatch.
    """
    if not _LIBRARY_CSV.exists():
        return []
    df = pd.read_csv(_LIBRARY_CSV, dtype=str, keep_default_na=False)
    df["sort_key"] = pd.to_numeric(df["sort_key"], errors="coerce").fillna(0)
    df = df.sort_values("sort_key")
    result: list[dict] = []
    for _, row in df.iterrows():
        result.append({
            "source":       "JST",
            "source_id":    row["series_id"].strip(),
            "col":          row["col"].strip(),
            "name":         row["name"].strip(),
            "country":      (row.get("country", "") or "").strip() or "GLOBAL",
            "category":     row["category"].strip(),
            "subcategory":  row["subcategory"].strip(),
            "concept":      (row.get("concept", "") or "").strip(),
            "cycle_timing": (row.get("cycle_timing", "") or "").strip(),
            "units":        row["units"].strip(),
            "frequency":    row["frequency"].strip(),
            "notes":        (row.get("notes", "") or "").strip(),
            "sort_key":     float(row["sort_key"]),
            "series_id":    row["series_id"].strip(),
            "freshness_override_days": (
                row.get("freshness_override_days", "") or ""
            ).strip(),
        })
    return result


# ---------------------------------------------------------------------------
# CACHED WORKBOOK RESOLVER (mirrors sources/ifo.py::_resolve_workbook_impl)
# ---------------------------------------------------------------------------

# Process-level cache for the parsed .dta DataFrame. JST is ~50 MB resident
# but only ~5 MB on the wire; caching avoids re-downloading once per
# (country, column) the dispatch layer fans out to.
_DTA_CACHE: pd.DataFrame | None = None
_DTA_ERROR: Exception | None = None
_DTA_SOURCE_URL: str | None = None


def _candidate_urls() -> list[str]:
    return [_PRIMARY, *_FALLBACKS]


def _try_download(url: str, timeout: int = 60) -> bytes | None:
    """GET `url`; return body if it looks like a Stata .dta file."""
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=timeout)
    except requests.exceptions.RequestException as e:
        print(f"  [JST] GET {url} raised {type(e).__name__}: {e}", flush=True)
        return None
    if resp.status_code != 200:
        print(f"  [JST] GET {url} HTTP {resp.status_code}", flush=True)
        return None
    body = resp.content
    if not body:
        print(f"  [JST] GET {url} returned empty body", flush=True)
        return None
    # Stata .dta files begin with either a `<stata_dta>` XML-ish wrapper
    # (Stata 13+ / format 117+) or a single binary magic byte. We only
    # need to rule out the obvious "got an HTML error page" case.
    head = body[:16]
    if head.startswith(b"<!DOCTYPE") or head.startswith(b"<html"):
        print(
            f"  [JST] GET {url} returned HTML ({len(body)} bytes) — "
            f"likely an error/landing page, not the .dta", flush=True
        )
        return None
    return body


def _resolve_dataframe_impl() -> tuple[str, pd.DataFrame]:
    """Download + parse the JST .dta file. Returns (url, dataframe).

    Tries each candidate URL in order; first one that returns a parseable
    Stata file wins. Raises RuntimeError if none succeed — callers
    (`fetch_series_as_pandas`) catch and downgrade to a None return so
    the daily pipeline never hard-fails on a JST outage.
    """
    last_err: Exception | None = None
    for url in _candidate_urls():
        body = _try_download(url)
        if body is None:
            continue
        try:
            df = pd.read_stata(io.BytesIO(body), convert_categoricals=False)
        except (ValueError, KeyError, Exception) as e:  # noqa: BLE001
            print(f"  [JST] pandas.read_stata({url}) raised "
                  f"{type(e).__name__}: {e}", flush=True)
            last_err = e
            continue
        print(f"  [JST] Resolved .dta from {url} "
              f"({len(df)} rows × {len(df.columns)} cols)")
        return url, df

    raise RuntimeError(
        f"Could not resolve JST .dta from any of {len(_candidate_urls())} "
        f"candidate URL(s). Last error: {last_err!r}"
    )


def resolve_dataframe() -> pd.DataFrame:
    """Cached wrapper — runs the network resolve at most once per process.

    On repeated failure within the same process we re-raise the cached
    exception instead of re-hitting the network (matches the ifo cache).
    """
    global _DTA_CACHE, _DTA_ERROR, _DTA_SOURCE_URL
    if _DTA_CACHE is not None:
        return _DTA_CACHE
    if _DTA_ERROR is not None:
        raise _DTA_ERROR
    try:
        url, df = _resolve_dataframe_impl()
        _DTA_CACHE = df
        _DTA_SOURCE_URL = url
        return df
    except Exception as e:
        _DTA_ERROR = e
        raise


def _reset_cache() -> None:
    """Test helper — clear the process-level cache."""
    global _DTA_CACHE, _DTA_ERROR, _DTA_SOURCE_URL
    _DTA_CACHE = None
    _DTA_ERROR = None
    _DTA_SOURCE_URL = None


# ---------------------------------------------------------------------------
# SERIES FETCH
# ---------------------------------------------------------------------------

def _parse_series_id(series_id: str) -> tuple[str, str] | None:
    """Split `<ISO>|<col>` into (iso, col); return None on malformed input."""
    if not series_id or "|" not in series_id:
        print(f"  [JST] malformed series_id {series_id!r} — "
              f"expected '<country_iso>|<column>'")
        return None
    iso, col = series_id.split("|", 1)
    iso = iso.strip().upper()
    col = col.strip()
    if not iso or not col:
        print(f"  [JST] malformed series_id {series_id!r}")
        return None
    return iso, col


def fetch_series_as_pandas(
    series_id: str,
    col_name: str | None = None,
) -> pd.Series | None:
    """Fetch one JST series as an annual date-indexed pd.Series.

    `series_id` is `<country_iso>|<column>`, e.g. `USA|cpi`. The fetcher
    pulls (and caches) the full .dta, filters by `iso == country_iso`,
    then returns the requested column with the `year` column reified as
    a year-end DatetimeIndex.

    Returns None on download failure, unknown column, or empty filter
    result. All failure modes are logged for the daily pipeline.log.
    """
    parsed = _parse_series_id(series_id)
    if parsed is None:
        return None
    iso, col = parsed

    try:
        df = resolve_dataframe()
    except Exception as e:  # noqa: BLE001
        print(f"  [JST FAIL] {series_id}: resolve failed — {e}")
        return None

    if "iso" not in df.columns or "year" not in df.columns:
        print(f"  [JST] cached .dta missing 'iso'/'year' columns "
              f"(have {list(df.columns)[:8]}…)")
        return None
    if col not in df.columns:
        print(f"  [JST] {series_id}: column {col!r} not in .dta "
              f"(first few: {list(df.columns)[:12]})")
        return None

    sub = df.loc[df["iso"].astype(str).str.upper() == iso, ["year", col]]
    if sub.empty:
        print(f"  [JST] {series_id}: no rows for iso={iso!r} "
              f"(known: {sorted(df['iso'].astype(str).str.upper().unique())[:10]}…)")
        return None

    # Annual: convert `year` to a year-end DatetimeIndex so downstream
    # weekly resamplers can place the observation cleanly.
    year = pd.to_numeric(sub["year"], errors="coerce")
    valid = year.notna()
    sub = sub.loc[valid].copy()
    sub["__dt"] = pd.to_datetime(
        year.loc[valid].astype(int).astype(str) + "-12-31",
        errors="coerce",
    )
    sub = sub.dropna(subset=["__dt"])
    if sub.empty:
        print(f"  [JST] {series_id}: no parseable years after filtering")
        return None

    series = pd.Series(
        pd.to_numeric(sub[col], errors="coerce").values,
        index=pd.DatetimeIndex(sub["__dt"].values),
        name=col_name or series_id,
    )
    series = series.dropna().sort_index()
    if series.empty:
        print(f"  [JST] {series_id}: column {col!r} all-NaN for iso={iso!r}")
        return None
    series = series[~series.index.duplicated(keep="last")]
    return series
