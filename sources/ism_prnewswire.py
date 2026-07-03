"""
sources/ism_prnewswire.py
=========================
Fallback source for the ISM PMI headline + sub-indexes, read from the
**official ISM press releases** distributed on PR Newswire.

Why this exists
---------------
The primary ISM source is the DB.nomics mirror (``sources/dbnomics.py`` +
``data/macro_library_dbnomics.csv``). That mirror is free but (a) lags the real
release by ~4-8 months and (b) has shipped physically impossible values when
its upstream scrape broke — the ISM Manufacturing PMI mirror returned ~10 for a
0-100 diffusion index across late 2025 where the real prints were ~48-53. When
DB.nomics is stale or its value is dropped by the plausibility guard, this
module fetches the current month straight from ISM's own release.

ISM's site and PR Newswire both block datacenter IPs (HTTP 403 to vanilla
``requests``), so retrieval routes through the shared Bright Data Web Unlocker
(``sources/brightdata.py``). **Without BRIGHTDATA_API_KEY set, every entry point
here returns None** and the caller simply keeps the last-known DB.nomics value —
no crash, no network.

Licensing note
--------------
ISM restricts recreating/redistributing an *index* of its content. This module
reads the current headline values into the same internal series the pipeline
already maintains; it does not republish ISM's report. Keep that boundary in
mind before widening what is scraped or surfaced.

Discovery
---------
The release URL carries an unpredictable numeric id, so it can't be
constructed — it is discovered from ISM's PR Newswire newsroom listing, which
lists releases newest-first:
    https://www.prnewswire.com/news/institute-for-supply-management/
"""

from __future__ import annotations

import html as _htmllib
import re
from datetime import datetime, timedelta

from . import brightdata

_TAG = "ISM/prnewswire"
_PRN_BASE = "https://www.prnewswire.com"
_NEWSROOM_URL = f"{_PRN_BASE}/news/institute-for-supply-management/"

# Manufacturing-report table labels -> our unified macro_economic column ids.
# Exact-label matching (see _parse_index_value) keeps "Inventories" from
# colliding with "Customers' Inventories", a distinct index in the same table.
MANUFACTURING_COL_MAP: dict[str, str] = {
    "Manufacturing PMI": "ISM_MFG_PMI",
    "New Orders":        "ISM_MFG_NEWORD",
    "Inventories":       "ISM_MFG_INVENTORIES",
    "Prices":            "ISM_MFG_PRICES",
}
SERVICES_COL_MAP: dict[str, str] = {
    "Services PMI": "ISM_SVC_PMI",
}

# Release-slug patterns, newest first in the listing. Group 1 is captured only
# to keep the regex readable; the full match is what we use.
_MFG_LINK_RE = re.compile(
    r"/news-releases/(manufacturing-pmi-[a-z0-9-]*?-"
    r"ism-manufacturing-pmi-report-\d+\.html)",
    re.IGNORECASE,
)
_SVC_LINK_RE = re.compile(
    r"/news-releases/(services-pmi-[a-z0-9-]*?-"
    r"ism-services-pmi-report-\d+\.html)",
    re.IGNORECASE,
)

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}
# `...-<month>-<year>-ism-...` inside the slug gives the report period.
_PERIOD_RE = re.compile(
    r"-(january|february|march|april|may|june|july|august|september|"
    r"october|november|december)-(\d{4})-ism-",
    re.IGNORECASE,
)
# The headline value is baked into the slug too: "manufacturing-pmi-at-53-3-..."
# → 53.3, "manufacturing-pmi-at-54-may-..." → 54.0. This is a robust secondary
# source for the headline PMI even if the release body parse fails.
_SLUG_HEADLINE_RE = re.compile(
    r"(?:manufacturing|services)-pmi-at-(\d+)(?:-(\d+))?-(?:january|february|"
    r"march|april|may|june|july|august|september|october|november|december)-",
    re.IGNORECASE,
)
# Which column each report kind's headline slug value belongs to.
_HEADLINE_COL = {"manufacturing": "ISM_MFG_PMI", "services": "ISM_SVC_PMI"}

# Diffusion indexes live in [0, 100]; the value line we accept for a label must
# fall in this range, which skips stray "Months"/trend integers and dashes.
_VAL_LO, _VAL_HI = 0.0, 100.0

# Per-process caches so N ISM columns in the snapshot + history passes share a
# single newsroom fetch and a single release fetch per report kind.
_LISTING_CACHE: str | None = None
_LISTING_FETCHED = False
_REPORT_CACHE: dict[str, dict | None] = {}


def _normalize_document(text: str) -> list[str]:
    """Flatten an ISM release into a list of one-token-per-line "cells",
    regardless of whether Bright Data returned raw HTML, a Markdown pipe table,
    or line-per-cell Markdown.

    The label→value parser below assumes each index label and each numeric
    reading sit on their own line. Bright Data's Web Unlocker may return any of
    three shapes depending on the ``data_format`` and the page, so we normalise
    all of them to that shape:
      * HTML: entity-unescape, drop <script>/<style>, turn block/cell/row close
        tags and <br> into newlines, strip remaining tags.
      * Markdown pipe tables ("| Manufacturing PMI | 53.3 | ..."): split on '|'.
      * Line-per-cell Markdown: already in the target shape.
    Over-splitting is harmless — the parser scans forward for the first numeric
    after an exact label match.
    """
    t = _htmllib.unescape(text)
    if "<" in t and ">" in t:
        t = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", t)
        t = re.sub(r"(?i)<(br|/td|/th|/tr|/p|/div|/li|/h[1-6])\s*/?>", "\n", t)
        t = re.sub(r"<[^>]+>", " ", t)
    t = t.replace("|", "\n")
    return t.splitlines()


def _normalize_label(line: str) -> str:
    """Strip markdown / trademark noise so a table label line compares cleanly.
    'Manufacturing PMI\\*\\*®\\*\\*' -> 'manufacturing pmi'."""
    s = line.replace("\\", "")
    s = re.sub(r"[*®™#]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip().lower()


def _to_float(line: str) -> float | None:
    m = re.match(r"^[+-]?\d+(?:\.\d+)?$", line.strip())
    if not m:
        return None
    try:
        return float(line.strip())
    except ValueError:
        return None


def _parse_index_value(lines: list[str], label: str) -> float | None:
    """Return the current-month value for an ISM index `label`.

    Finds the first line that, normalized, equals the label exactly (so prose
    like 'The New Orders Index expanded ...' is ignored), then the first
    following line that parses as a number in the diffusion-index range. The
    release's summary table lists each index as a bare label line immediately
    above its current reading, and that table precedes the per-index prose, so
    the first exact-label hit is the table row.
    """
    target = label.lower()
    for i, ln in enumerate(lines):
        if _normalize_label(ln) != target:
            continue
        for j in range(i + 1, min(i + 6, len(lines))):
            v = _to_float(lines[j])
            if v is not None and _VAL_LO <= v <= _VAL_HI:
                return v
    return None


def parse_report(text: str, col_map: dict[str, str]) -> dict[str, float]:
    """Parse an ISM release into {col_id: value} using `col_map`.

    Accepts raw HTML, Markdown pipe tables, or line-per-cell Markdown — the
    input is normalised first. Returns only the columns found; an empty dict
    means the parse failed (a layout change) and the caller should keep
    last-known data.
    """
    lines = _normalize_document(text)
    out: dict[str, float] = {}
    for label, col in col_map.items():
        v = _parse_index_value(lines, label)
        if v is not None:
            out[col] = v
    return out


def _period_end_from_slug(slug: str) -> str | None:
    """'...-june-2026-ism-...' -> '2026-06-30' (end-of-month, matching the
    DB.nomics monthly convention). None if the slug lacks a month/year."""
    m = _PERIOD_RE.search(slug)
    if not m:
        return None
    month = _MONTHS[m.group(1).lower()]
    year = int(m.group(2))
    if month == 12:
        end = datetime(year, 12, 31)
    else:
        end = datetime(year, month + 1, 1) - timedelta(days=1)
    return end.strftime("%Y-%m-%d")


def _headline_from_slug(slug: str) -> float | None:
    """'manufacturing-pmi-at-53-3-june-...' -> 53.3; '...-at-54-may-...' ->
    54.0. Robust headline recovery that doesn't depend on the release body."""
    m = _SLUG_HEADLINE_RE.search(slug)
    if not m:
        return None
    whole, frac = m.group(1), m.group(2)
    try:
        return float(f"{whole}.{frac}") if frac else float(whole)
    except ValueError:
        return None


def _get_listing() -> str | None:
    global _LISTING_CACHE, _LISTING_FETCHED
    if not _LISTING_FETCHED:
        _LISTING_FETCHED = True
        _LISTING_CACHE = brightdata.unlock_text(
            _NEWSROOM_URL, tag=_TAG, data_format="markdown"
        )
    return _LISTING_CACHE


def discover_latest_url(kind: str) -> str | None:
    """Absolute URL of the newest manufacturing/services release, or None."""
    listing = _get_listing()
    if not listing:
        return None
    rx = _MFG_LINK_RE if kind == "manufacturing" else _SVC_LINK_RE
    m = rx.search(listing)
    if not m:
        print(f"  [{_TAG}] no {kind} release link found in newsroom listing", flush=True)
        return None
    return _PRN_BASE + "/news-releases/" + m.group(1)


def fetch_latest(kind: str = "manufacturing") -> dict | None:
    """Fetch + parse the latest ISM release of `kind`.

    Returns {"kind", "url", "period", "values": {col_id: float}} or None when
    credentials are absent, the release can't be retrieved, or the parse yields
    nothing. Cached per process so repeated calls in one run are free.
    """
    if kind in _REPORT_CACHE:
        return _REPORT_CACHE[kind]

    result: dict | None = None
    if brightdata.available():
        url = discover_latest_url(kind)
        if url:
            text = brightdata.unlock_text(url, tag=_TAG, data_format="markdown")
            period = _period_end_from_slug(url)
            col_map = (
                MANUFACTURING_COL_MAP if kind == "manufacturing"
                else SERVICES_COL_MAP
            )
            values = parse_report(text, col_map) if text else {}
            # Guaranteed headline recovery from the slug, even if the body
            # parse comes back empty (e.g. an unexpected release layout).
            headline_col = _HEADLINE_COL.get(kind)
            if headline_col and headline_col not in values:
                hv = _headline_from_slug(url)
                if hv is not None:
                    values[headline_col] = hv
                    print(
                        f"  [{_TAG}] {kind} headline recovered from slug: "
                        f"{headline_col}={hv}",
                        flush=True,
                    )
            if values and period:
                result = {
                    "kind":   kind,
                    "url":    url,
                    "period": period,
                    "values": values,
                }
                print(
                    f"  [{_TAG}] parsed {kind} release {period}: {values}",
                    flush=True,
                )
            else:
                print(
                    f"  [{_TAG}] {kind} release parse yielded no usable "
                    f"data (period={period}, values={values}, "
                    f"text_len={len(text) if text else 0})",
                    flush=True,
                )
    _REPORT_CACHE[kind] = result
    return result


# Which report kind each ISM column comes from.
_COL_KIND: dict[str, str] = {
    **{c: "manufacturing" for c in MANUFACTURING_COL_MAP.values()},
    **{c: "services" for c in SERVICES_COL_MAP.values()},
}


def latest_value_for_col(col: str) -> tuple[str, float] | None:
    """(period_end_date, value) for one ISM column from the latest release,
    or None. Convenience wrapper the fetch layer uses to splice a fresh point
    onto a stale/guarded DB.nomics series."""
    kind = _COL_KIND.get(col)
    if kind is None:
        return None
    report = fetch_latest(kind)
    if not report:
        return None
    val = report["values"].get(col)
    if val is None:
        return None
    return report["period"], val
