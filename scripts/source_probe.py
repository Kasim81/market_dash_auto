#!/usr/bin/env python3
"""
scripts/source_probe.py — general runner-side source probe (diagnostic)
======================================================================

Several strands of §2.C C16.1 are blocked not on design but on *where the
code runs*: the dev sandbox has no API keys (``ESTAT_APP_ID``, ``BLS_API_KEY``,
``BDF_API_KEY``) and its network policy 403s several statistical-agency hosts
(``bfs.admin.ch``, ``cbs.nl``, ``ec.europa.eu``). The GitHub runner has both.

Before this script each blocked strand got its own throwaway workflow
(``ifo_probe.yml``, ``source_survey.yml``) with its own "delete me later"
note. This is the general instrument that replaces that pattern: one script,
one ``workflow_dispatch``, three modes, results in the job log.

Modes
-----
``fetch``    Fetch a series through the coordinator's OWN history handler and
             report obs count / span / last value / decimal places. Two forms:

               {"mode":"fetch","col":"JPN_CPI_YOY"}
                   every registered row serving that column, across all
                   libraries — the shape wanted for freshness recalibration.

               {"mode":"fetch","source":"e-Stat","series_id":"0003427113?..."}
                   an unregistered candidate series id, fetched exactly as
                   production would fetch it.

``compare``  Fetch two series and report the seam statistics *plus* the
             verdict from the pipeline's own ``_seam_agreement``, so a probe
             result and a production splice decision cannot disagree:

               {"mode":"compare",
                "a":{"source":"ISTAT","series_id":"..."},
                "b":{"col":"ITA_CPI_YOY"},
                "units":"Percent"}

``http``     Raw GET against an allowlisted host, for exploring an API that
             has no adapter yet (the Swiss FSO / CBS Netherlands case).
             Host-allowlisted deliberately — see ``_ALLOWED_HOSTS``.

Spec comes from ``$PROBE_SPEC`` as JSON: one object, or a list of objects run
in order. Results go to stdout and to ``source_probe_result.txt``.

Read-only: no CSV writes, no Sheets, no library mutation.
"""

from __future__ import annotations

import json
import os
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

# The coordinator hard-fails at import without these; a probe never uses them.
os.environ.setdefault("FRED_API_KEY", "x")
os.environ.setdefault("SHEET_ID", "x")
os.environ.setdefault("GOOGLE_CREDENTIALS_JSON", "{}")

import pandas as pd  # noqa: E402

import sources  # noqa: E402
import fetch_macro_economic as fme  # noqa: E402


# Hosts the `http` mode may reach. Kept explicit rather than open: this
# workflow runs with every repository secret in its environment, so an
# arbitrary-URL fetch would be a poor trade for a diagnostic's convenience.
_ALLOWED_HOSTS = {
    # candidate sources with no adapter yet (C16.1 national CPI track)
    "www.pxweb.bfs.admin.ch", "dam-api.bfs.admin.ch", "www.bfs.admin.ch",
    "opendata.cbs.nl", "odata4.cbs.nl", "dataderden.cbs.nl",
    # registered-but-locally-blocked
    "ec.europa.eu",
}

_OUT = pathlib.Path("source_probe_result.txt")
_lines: list[str] = []


def out(msg: str = "") -> None:
    print(msg, flush=True)
    _lines.append(msg)


# ---------------------------------------------------------------------------
# LIBRARY LOOKUP
# ---------------------------------------------------------------------------

def _all_library_rows() -> list[dict]:
    """Every registered indicator dict, from every source's own loader."""
    rows: list[dict] = []
    for spec in sources.SOURCE_REGISTRY:
        try:
            mod = __import__(f"sources.{spec.module}", fromlist=["x"])
        except Exception as e:
            out(f"  [warn] sources.{spec.module} import failed: {e}")
            continue
        try:
            if spec.module == "fred":
                got = list(mod.load_us_library_as_list()) + list(mod.load_intl_library())
            else:
                got = list(mod.load_library())
        except Exception as e:
            out(f"  [warn] {spec.label} load_library failed: {e}")
            continue
        rows.extend(got)
    return rows


def _rows_for_col(col: str) -> list[dict]:
    """Registered rows serving `col`, including fan-out siblings (ISO_COL)."""
    hits = []
    for r in _all_library_rows():
        base = r.get("col", "")
        if base == col:
            hits.append(r)
            continue
        # fan-out: a row with col=UNEMPLOYMENT serves CAN_UNEMPLOYMENT etc.
        if col.endswith("_" + base) and len(col) > len(base) + 1:
            hits.append(r)
    return hits


# Fields that belong to the *template row* rather than to the source, and so
# must be dropped when cloning. Learned the hard way: the first probe run
# cloned a DB.nomics ISM row and inherited its plausible_min/max of [15, 99],
# which silently dropped 761 of 844 CPI observations and reported the
# survivors as if they were the series. A probe that quietly discards 90% of
# its data is worse than one that fails.
_TEMPLATE_DROP = (
    "plausible_min", "plausible_max",     # per-row validity bands
    "name", "notes", "category", "subcategory", "concept", "cycle_timing",
    "sort_key", "tier", "freshness_override_days",
)


def _template_indic(source_label: str) -> dict:
    """A real library row for `source_label`, to clone for an unregistered id.

    Cloning beats hand-building: every field the source's history handler
    reads is present with a shape that handler already accepts, including the
    fan-out and edition-pinning fields that differ per source. Row-specific
    fields are cleared — see _TEMPLATE_DROP.
    """
    for r in _all_library_rows():
        if r.get("source") == source_label:
            indic = dict(r)
            for k in _TEMPLATE_DROP:
                if k in indic:
                    indic[k] = None if k.startswith("plausible") else ""
            return indic
    raise SystemExit(f"no registered rows for source {source_label!r} to clone")


def _resolve(spec: dict) -> list[tuple[str, dict]]:
    """A fetch/compare leg spec -> [(label, indic), ...]."""
    if spec.get("col") and not spec.get("series_id"):
        hits = _rows_for_col(spec["col"])
        if not hits:
            raise SystemExit(f"no registered row serves col {spec['col']!r}")
        if spec.get("source"):
            hits = [h for h in hits if h.get("source") == spec["source"]]
            if not hits:
                raise SystemExit(f"no {spec['source']!r} row serves {spec['col']!r}")
        return [(f"{h['source']} {h['source_id']}", h) for h in hits]

    if not (spec.get("source") and spec.get("series_id")):
        raise SystemExit(f"leg needs either 'col', or 'source'+'series_id': {spec}")

    indic = _template_indic(spec["source"])
    indic["source_id"] = spec["series_id"]
    indic["col"] = spec.get("as_col", "PROBE")
    for k in ("units", "frequency", "country"):
        if spec.get(k):
            indic[k] = spec[k]
    return [(f"{spec['source']} {spec['series_id']}", indic)]


# ---------------------------------------------------------------------------
# FETCH
# ---------------------------------------------------------------------------

def _fetch(indic: dict) -> pd.Series | None:
    """Fetch through the coordinator's own history handler for this source."""
    label = indic.get("source", "")
    handlers = fme._SOURCE_HANDLERS.get(label)
    if not handlers:
        out(f"  [error] no _SOURCE_HANDLERS entry for source {label!r}")
        return None
    got = handlers[1](indic)
    if not got:
        return None
    # Handlers return {column_name: Series}; a fan-out row yields many. Prefer
    # the probe column, else the longest series.
    if indic.get("col") in got:
        return got[indic["col"]]
    for name, s in got.items():
        if name.endswith("_" + indic.get("col", "")):
            return s
    return max(got.values(), key=lambda s: len(s.dropna()))


def _decimals(s: pd.Series, sample: int = 200) -> int:
    """Max decimal places seen in the tail — catches 1-dp publication."""
    best = 0
    for v in s.dropna().tail(sample):
        txt = f"{float(v):.10f}".rstrip("0")
        best = max(best, len(txt.split(".")[1]) if "." in txt else 0)
    return best


def _describe(name: str, s: pd.Series | None) -> None:
    if s is None or s.dropna().empty:
        out(f"  {name}: NO DATA")
        return
    d = s.dropna()
    out(f"  {name}: {len(d)} obs  {d.index.min().date()} -> {d.index.max().date()}  "
        f"last={d.iloc[-1]}  decimals<={_decimals(d)}")


# ---------------------------------------------------------------------------
# MODES
# ---------------------------------------------------------------------------

def mode_fetch(spec: dict) -> None:
    for label, indic in _resolve(spec):
        out(f"[fetch] {label}   (col={indic.get('col')}, units={indic.get('units')!r}, "
            f"freq={indic.get('frequency')!r}, tier={indic.get('tier')})")
        try:
            _describe("result", _fetch(indic))
        except Exception as e:
            out(f"  ERROR {type(e).__name__}: {e}")


def mode_compare(spec: dict) -> None:
    legs = {}
    for side in ("a", "b"):
        if side not in spec:
            raise SystemExit(f"compare needs legs 'a' and 'b': {spec}")
        label, indic = _resolve(spec[side])[0]
        out(f"[compare:{side}] {label}")
        try:
            s = _fetch(indic)
        except Exception as e:
            out(f"  ERROR {type(e).__name__}: {e}")
            s = None
        _describe("result", s)
        legs[side] = (s, indic)

    (sa, ia), (sb, ib) = legs["a"], legs["b"]
    if sa is None or sb is None or sa.dropna().empty or sb.dropna().empty:
        out("  -> cannot compare: a leg has no data")
        return

    units = spec.get("units") or ia.get("units") or ib.get("units") or ""
    kind = fme._measure_kind(units)
    fa = ia.get("frequency", "Monthly")
    fb = ib.get("frequency", "Monthly")

    A, B = sa.dropna(), sb.dropna()
    PA, PB = A.copy(), B.copy()
    PA.index = pd.PeriodIndex(PA.index, freq="M")
    PB.index = pd.PeriodIndex(PB.index, freq="M")
    PA, PB = PA[~PA.index.duplicated()], PB[~PB.index.duplicated()]
    j = pd.concat([PA.rename("a"), PB.rename("b")], axis=1).dropna()
    if j.empty:
        out("  -> NO OVERLAP")
    else:
        diff = (j.a - j.b).abs()
        out(f"  overlap n={len(j)}  {j.index.min()}..{j.index.max()}  "
            f"max|diff|={diff.max():.4f}  mean|diff|={diff.mean():.4f}")
        worst = diff.sort_values(ascending=False).index[:5]
        for p in worst:
            out(f"    {p}  a={j.a[p]!s:<12} b={j.b[p]!s:<12} diff={j.a[p] - j.b[p]:+.4f}")

    ok, reason, scale = fme._seam_agreement(A, fa, B, fb, kind)
    out(f"  seam verdict (pipeline _seam_agreement, kind={kind!r}): "
        f"{'PASS' if ok else 'REFUSE'} — {reason}" + (f" (scale={scale})" if scale else ""))


def mode_http(spec: dict) -> None:
    import urllib.parse
    import requests

    url = spec.get("url", "")
    host = urllib.parse.urlparse(url).hostname or ""
    out(f"[http] {url}")
    if host not in _ALLOWED_HOSTS:
        out(f"  REFUSED: host {host!r} not in the allowlist. This workflow runs with "
            f"repository secrets in its environment; add the host to _ALLOWED_HOSTS "
            f"in scripts/source_probe.py if the probe genuinely needs it.")
        return
    headers = {"User-Agent": "Mozilla/5.0 (compatible; market_dash_auto/1.0)"}
    headers.update(spec.get("headers") or {})
    try:
        r = requests.get(url, headers=headers, timeout=spec.get("timeout", 90))
    except Exception as e:
        out(f"  ERROR {type(e).__name__}: {e}")
        return
    out(f"  HTTP {r.status_code}  len={len(r.content)}  "
        f"content-type={r.headers.get('Content-Type', '')}")
    body = r.text[: int(spec.get("max_chars", 4000))]
    for line in body.splitlines():
        out(f"    {line}")
    if len(r.text) > len(body):
        out(f"    ... truncated, {len(r.text) - len(body)} chars omitted")


_MODES = {"fetch": mode_fetch, "compare": mode_compare, "http": mode_http}


def main() -> int:
    raw = os.environ.get("PROBE_SPEC", "").strip()
    if not raw:
        out("PROBE_SPEC is empty — nothing to probe.")
        out(__doc__ or "")
        _OUT.write_text("\n".join(_lines) + "\n")
        return 1

    try:
        spec = json.loads(raw)
    except json.JSONDecodeError as e:
        out(f"PROBE_SPEC is not valid JSON: {e}")
        _OUT.write_text("\n".join(_lines) + "\n")
        return 1

    specs = spec if isinstance(spec, list) else [spec]
    failed = 0
    for i, s in enumerate(specs, 1):
        mode = (s or {}).get("mode", "")
        out(f"{'=' * 72}")
        out(f"probe {i}/{len(specs)}  mode={mode!r}")
        fn = _MODES.get(mode)
        if not fn:
            out(f"  unknown mode {mode!r}; expected one of {sorted(_MODES)}")
            failed += 1
            continue
        try:
            fn(s)
        except SystemExit as e:
            out(f"  ABORT: {e}")
            failed += 1
        except Exception as e:
            out(f"  ERROR {type(e).__name__}: {e}")
            failed += 1
        out("")

    _OUT.write_text("\n".join(_lines) + "\n")
    print(f"\nwrote {_OUT} ({len(_lines)} lines); {failed} of {len(specs)} probes failed")
    # A failed probe is a finding, not a broken workflow — the job stays green
    # so the log and artifact are always easy to reach.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
