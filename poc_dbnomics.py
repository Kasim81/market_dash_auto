#!/usr/bin/env python3
"""
poc_dbnomics.py — Phase D Tier 2 Proof of Concept

Verifies the 5 target DB.nomics series (ECB BLS x2 + Eurostat x3) are
reachable, have sufficient history, and are reasonably fresh.

Also resolves placeholder dimension keys for ECB/BLS and Eurostat datasets
whose exact series codes were unknown at planning time.

Scope change (post-round-1 findings):
  - ISM moved to Tier 3 FMP (DB.nomics mirror was 4-8 months stale)
  - BOJ Tankan dropped entirely (not available on DB.nomics)
  - Japan sentiment comes from JP_MFG_PMI via poc_fmp_calendar.py

Usage:  python poc_dbnomics.py
Output: prints a summary table; writes sample CSVs to data/poc_dbnomics/

Requires: requests, pandas
API:      https://api.db.nomics.world/v22/  — no API key needed
"""

import json
import os
import sys
from datetime import datetime, timedelta

import pandas as pd
import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE = "https://api.db.nomics.world/v22"
STALE_DAYS = 120  # flag if last observation older than this many days
SAMPLE_DIR = os.path.join("data", "poc_dbnomics")
MIN_YEARS = 3  # minimum acceptable history depth

# ---------------------------------------------------------------------------
# NOTE on scope (post-round-1 findings):
#   - ISM was moved to Tier 3 (FMP calendar) — DB.nomics ISM mirror is 4-8
#     months stale. See poc_fmp_calendar.py for ISM verification.
#   - BOJ Tankan is not available on DB.nomics (BOJ provider only has 3
#     datasets: BP, CGPI, SPPI). Japan sentiment comes from JP_MFG_PMI
#     via FMP calendar.
#   - This PoC now verifies only ECB BLS + Eurostat (5 series, all EA).
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Part 1 — ECB Bank Lending Survey (need dimension resolution)
#
# ECB/BLS has ~20k series.  We want:
#   - Credit standards for loans to enterprises (net % tightening, EA)
#   - Credit standards for loans to households for house purchase (net %, EA)
#
# The series code mirrors ECB SDMX key structure.  We try several candidate
# codes and also search by keyword if none hit.
# ---------------------------------------------------------------------------

ECB_BLS_CANDIDATES = {
    # Candidates derived from confirmed Austria pattern Q.AT.ALL.{factor}.E.{size}.B3.ST.S.FNET
    # substituting AT → U2 (Euro Area, changing composition).
    # Dimension 4 (factor): Z=aggregate/all factors, BC=bank competition,
    #   CP=capital position, BSC=balance-sheet constraints, CS=credit standards summary
    "ECB BLS — Credit Std Enterprises": [
        "ECB/BLS/Q.U2.ALL.Z.E.LE.B3.ST.S.FNET",      # aggregate factor, large enterprise
        "ECB/BLS/Q.U2.ALL.Z.E.Z.B3.ST.S.FNET",       # aggregate factor, all sizes
        "ECB/BLS/Q.U2.ALL.Z.E.SME.B3.ST.S.FNET",     # aggregate factor, SME
        "ECB/BLS/Q.U2.ALL.BC.E.LE.B3.ST.S.FNET",     # bank competition factor
        "ECB/BLS/Q.U2.ALL.BC.E.Z.B3.ST.S.FNET",
    ],
    "ECB BLS — Credit Std Households": [
        "ECB/BLS/Q.U2.ALL.Z.H.H.B3.ST.S.FNET",       # aggregate factor, housing loans
        "ECB/BLS/Q.U2.ALL.Z.H.C.B3.ST.S.FNET",       # aggregate factor, consumer credit
        "ECB/BLS/Q.U2.ALL.BC.H.H.B3.ST.S.FNET",      # bank competition factor, housing
        "ECB/BLS/Q.U2.ALL.BC.H.C.B3.ST.S.FNET",      # bank competition factor, consumer
    ],
}

# ---------------------------------------------------------------------------
# Part 2 — Eurostat ESI / Confidence
#
# teibs010 = ESI composite; teibs020 = sector confidence
# Series codes: M.<indicator>.<adjustment>.<country>
# ---------------------------------------------------------------------------

EUROSTAT_CANDIDATES = {
    # NB: teibs010/teibs020 are summary tables with only ~12 obs of history.
    # Prefer ei_bssi_m_r2 (Business and Consumer Surveys, full history).
    "EC Economic Sentiment (EA)": [
        "Eurostat/ei_bssi_m_r2/M.SA.BS-ESI-I.EA20",
        "Eurostat/ei_bssi_m_r2/M.SA.BS-ESI-I.EA19",
        "Eurostat/ei_bssi_m_r2/M.BS-ESI-I.SA.EA20",
        "Eurostat/ei_bssi_m_r2/M.BS-ESI-I.SA.EA19",
    ],
    "EC Industry Confidence (EA)": [
        "Eurostat/ei_bssi_m_r2/M.SA.BS-ICI-BAL.EA20",
        "Eurostat/ei_bssi_m_r2/M.SA.BS-ICI-BAL.EA19",
        "Eurostat/ei_bssi_m_r2/M.BS-ICI-BAL.SA.EA20",
        "Eurostat/ei_bssi_m_r2/M.BS-ICI-BAL.SA.EA19",
    ],
    "EC Services Confidence (EA)": [
        "Eurostat/ei_bssi_m_r2/M.SA.BS-SCI-BAL.EA20",
        "Eurostat/ei_bssi_m_r2/M.SA.BS-SCI-BAL.EA19",
        "Eurostat/ei_bssi_m_r2/M.BS-SCI-BAL.SA.EA20",
        "Eurostat/ei_bssi_m_r2/M.BS-SCI-BAL.SA.EA19",
    ],
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fetch_series(series_id: str) -> dict | None:
    """
    Fetch a single series from DB.nomics.
    series_id: "PROVIDER/DATASET/SERIES_CODE"
    Returns parsed JSON or None on failure.
    """
    url = f"{BASE}/series?observations=1&series_ids={series_id}&limit=1"
    try:
        r = requests.get(url, timeout=30)
        if r.status_code != 200:
            return None
        data = r.json()
        docs = data.get("series", {}).get("docs", [])
        if not docs:
            return None
        return docs[0]
    except Exception as e:
        print(f"  [ERROR] {series_id}: {e}")
        return None


def search_dataset(provider: str, dataset: str, limit: int = 200) -> list:
    """List series within a dataset (for exploration)."""
    url = f"{BASE}/series/{provider}/{dataset}?limit={limit}&offset=0"
    try:
        r = requests.get(url, timeout=30)
        if r.status_code != 200:
            return []
        data = r.json()
        return data.get("series", {}).get("docs", [])
    except Exception:
        return []


def fetch_dataset_metadata(provider: str, dataset: str) -> dict:
    """Fetch dataset metadata showing available dimensions and codes."""
    url = f"{BASE}/dataset/{provider}/{dataset}"
    try:
        r = requests.get(url, timeout=30)
        print(f"    [metadata] GET {url} → HTTP {r.status_code}")
        if r.status_code != 200:
            return {}
        return r.json().get("dataset", {})
    except Exception as e:
        print(f"    [metadata] exception: {e}")
        return {}


def fetch_series_by_dimensions(provider: str, dataset: str,
                               dimensions: dict, limit: int = 100) -> list:
    """
    Fetch series filtered by dimension values (server-side filter).
    dimensions: {dim_name: [value1, value2]} — uses DB.nomics dimensions param.
    """
    dim_json = json.dumps(dimensions)
    url = f"{BASE}/series/{provider}/{dataset}?dimensions={dim_json}&limit={limit}"
    try:
        r = requests.get(url, timeout=30)
        print(f"    [dimquery] HTTP {r.status_code}, {len(r.text)} bytes")
        if r.status_code != 200:
            return []
        return r.json().get("series", {}).get("docs", [])
    except Exception as e:
        print(f"    [dimquery] exception: {e}")
        return []


def list_datasets(provider: str) -> list:
    """List datasets for a provider."""
    url = f"{BASE}/datasets/{provider}?limit=100"
    try:
        r = requests.get(url, timeout=30)
        if r.status_code != 200:
            return []
        data = r.json()
        return data.get("datasets", {}).get("docs", [])
    except Exception:
        return []


def analyse_series(doc: dict) -> dict:
    """Extract key metrics from a series document."""
    periods = doc.get("period", [])
    values = doc.get("value", [])
    name = doc.get("series_name", doc.get("series_code", "?"))
    series_code = doc.get("series_code", "?")

    valid_pairs = [
        (p, v) for p, v in zip(periods, values)
        if v is not None and str(v).lower() not in ("na", "nan", "")
    ]
    if not valid_pairs:
        return {"name": name, "code": series_code, "ok": False, "reason": "no valid observations"}

    first_period = valid_pairs[0][0]
    last_period = valid_pairs[-1][0]
    last_value = valid_pairs[-1][1]
    n_obs = len(valid_pairs)

    try:
        for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
            try:
                last_dt = datetime.strptime(str(last_period), fmt)
                first_dt = datetime.strptime(str(first_period), fmt)
                break
            except ValueError:
                continue
        else:
            last_dt = first_dt = None
    except Exception:
        last_dt = first_dt = None

    stale = False
    days_ago = None
    years_span = None
    if last_dt:
        days_ago = (datetime.now() - last_dt).days
        stale = days_ago > STALE_DAYS
    if first_dt and last_dt:
        years_span = round((last_dt - first_dt).days / 365.25, 1)

    return {
        "name": name,
        "code": series_code,
        "ok": True,
        "n_obs": n_obs,
        "first": str(first_period),
        "last": str(last_period),
        "last_value": last_value,
        "days_ago": days_ago,
        "stale": stale,
        "years": years_span,
        "shallow": years_span is not None and years_span < MIN_YEARS,
    }


def save_sample(series_id: str, doc: dict, label: str):
    """Save a sample CSV for a fetched series."""
    periods = doc.get("period", [])
    values = doc.get("value", [])
    df = pd.DataFrame({"period": periods, "value": values})
    fname = label.replace(" ", "_").replace("/", "_").replace("—", "-") + ".csv"
    path = os.path.join(SAMPLE_DIR, fname)
    df.to_csv(path, index=False)
    return path


def try_candidates(label: str, candidates: list[str]) -> tuple[dict | None, str | None]:
    """Try a list of candidate series IDs, return first that works."""
    for sid in candidates:
        doc = fetch_series(sid)
        if doc:
            return doc, sid
    return None, None


# ---------------------------------------------------------------------------
# Exploration fallback — keyword search within a dataset
# ---------------------------------------------------------------------------

def explore_and_match(provider: str, dataset: str, keywords: list[str],
                      limit: int = 500, required_substrings: list[str] = None) -> list[dict]:
    """
    List series in a dataset, return those whose series_name+code contains
    ALL keywords (case-insensitive).

    required_substrings: optional list of strings that MUST appear in the
    series_code (e.g., ['U2'] to require Euro Area).  Applied after keyword
    filtering.
    """
    url = f"{BASE}/series/{provider}/{dataset}?limit={limit}&offset=0"
    try:
        r = requests.get(url, timeout=60)
        if r.status_code != 200:
            print(f"  [WARN] Could not list {provider}/{dataset}: HTTP {r.status_code}")
            return []
        data = r.json()
        docs = data.get("series", {}).get("docs", [])
        matches = []
        kw_lower = [k.lower() for k in keywords]
        for d in docs:
            name = (d.get("series_name") or "").lower()
            code = (d.get("series_code") or "").lower()
            combined = name + " " + code
            if all(k in combined for k in kw_lower):
                if required_substrings:
                    code_upper = (d.get("series_code") or "").upper()
                    if not all(req.upper() in code_upper for req in required_substrings):
                        continue
                matches.append(d)
        return matches
    except Exception as e:
        print(f"  [ERROR] explore {provider}/{dataset}: {e}")
        return []


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs(SAMPLE_DIR, exist_ok=True)
    results = []
    resolved = {}  # label → series_id (for building the library CSV later)
    now = datetime.now()

    # -----------------------------------------------------------------------
    # Part 1: ECB Bank Lending Survey
    # -----------------------------------------------------------------------
    print("=" * 70)
    print("PART 1 — ECB Bank Lending Survey (2 series, need dimension resolution)")
    print("=" * 70)
    for label, candidates in ECB_BLS_CANDIDATES.items():
        print(f"\n  Trying candidates for: {label}")
        doc, sid = try_candidates(label, candidates)
        if doc:
            info = analyse_series(doc)
            info["series_id"] = sid
            info["group"] = "ECB_BLS"
            results.append(info)
            resolved[label] = sid
            save_sample(sid, doc, label)
            status = "STALE" if info["stale"] else "OK"
            print(f"  {status}: resolved as {sid}")
            print(f"         {info['n_obs']} obs, {info['first']} → {info['last']} "
                  f"({info['years']}y), last={info['last_value']}, {info['days_ago']}d ago")
        else:
            print(f"  No candidate hit.  Fetching ECB/BLS dimension metadata...")
            meta = fetch_dataset_metadata("ECB", "BLS")
            print(f"  Metadata keys: {list(meta.keys())[:20] if meta else '(empty)'}")
            dims_order = meta.get("dimensions_codes_order", []) if meta else []
            dims_labels = meta.get("dimensions_values_labels", {}) if meta else {}
            if dims_order:
                print(f"  Dataset has {len(dims_order)} dimensions: {dims_order}")
                for dim_name in dims_order:
                    vals = dims_labels.get(dim_name, {})
                    if isinstance(vals, dict):
                        sample = list(vals.items())[:6]
                    elif isinstance(vals, list):
                        sample = vals[:6]
                    else:
                        sample = []
                    print(f"    {dim_name}: {sample}")
            else:
                print("  WARNING: no dimension metadata returned")

            # Try server-side dimensions filter (requires knowing dim names)
            matches = []
            if dims_order:
                ref_area_dim = next((d for d in dims_order
                                     if d.upper() in ("REF_AREA", "AREA", "COUNTRY", "BLS_COUNTRY")),
                                    None)
                if ref_area_dim:
                    print(f"  Trying server-side filter: {ref_area_dim}=U2 ...")
                    docs = fetch_series_by_dimensions("ECB", "BLS",
                                                     {ref_area_dim: ["U2"]}, limit=200)
                    print(f"  Returned {len(docs)} series with {ref_area_dim}=U2")
                    # Filter client-side for "ST" (standards) in series_code
                    short = label.split("—")[-1].strip()
                    kws_filter = ["enterprise"] if "Enterprises" in short else ["household"]
                    for d in docs:
                        code = (d.get("series_code") or "").upper()
                        name = (d.get("series_name") or "").lower()
                        if ".ST." not in code:
                            continue
                        if not any(k in name for k in kws_filter):
                            continue
                        matches.append(d)
                    print(f"  After filtering for .ST. + keyword: {len(matches)} matches")

            if not matches:
                print(f"\n  Falling back to keyword listing (limit=500)...")
                kw_map = {
                    "Credit Std Enterprises": ["standards", "enterprise"],
                    "Credit Std Households":  ["standards", "household"],
                }
                short = label.split("—")[-1].strip()
                kws = kw_map.get(short, short.lower().split())
                matches = explore_and_match("ECB", "BLS", kws, limit=500,
                                            required_substrings=["Q.U2.", ".ST."])
            if matches:
                print(f"  Found {len(matches)} keyword matches.  Top 5:")
                for m in matches[:5]:
                    code = m.get("series_code", "?")
                    name = (m.get("series_name") or "")[:80]
                    print(f"    {code}: {name}")
                # Pick first match and fetch with observations
                best = matches[0]
                best_sid = f"ECB/BLS/{best['series_code']}"
                print(f"  Fetching best match: {best_sid}")
                doc2 = fetch_series(best_sid)
                if doc2:
                    info = analyse_series(doc2)
                    info["series_id"] = best_sid
                    info["group"] = "ECB_BLS"
                    results.append(info)
                    resolved[label] = best_sid
                    save_sample(best_sid, doc2, label)
                    status = "STALE" if info["stale"] else "OK"
                    print(f"  {status}: {info['n_obs']} obs, {info['first']} → {info['last']}")
                else:
                    results.append({"name": label, "ok": False, "reason": "keyword match but no obs", "group": "ECB_BLS"})
                    print(f"  FAIL: keyword match found but could not fetch observations")
            else:
                results.append({"name": label, "ok": False, "reason": "no match", "group": "ECB_BLS"})
                print(f"  FAIL: no matching series found in ECB/BLS")

    # -----------------------------------------------------------------------
    # Part 2: Eurostat ESI / Confidence
    # -----------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("PART 2 — Eurostat ESI + Sector Confidence (3 series)")
    print("=" * 70)
    for label, candidates in EUROSTAT_CANDIDATES.items():
        print(f"\n  Trying candidates for: {label}")
        doc, sid = try_candidates(label, candidates)
        if doc:
            info = analyse_series(doc)
            info["series_id"] = sid
            info["group"] = "Eurostat"
            results.append(info)
            resolved[label] = sid
            save_sample(sid, doc, label)
            status = "STALE" if info["stale"] else "OK"
            print(f"  {status}: resolved as {sid}")
            print(f"         {info['n_obs']} obs, {info['first']} → {info['last']} "
                  f"({info['years']}y), last={info['last_value']}, {info['days_ago']}d ago")
        else:
            # Explore: try listing teibs010 and teibs020
            print(f"  No candidate hit.  Exploring Eurostat datasets...")
            # Prefer ei_bssi_m_r2 (full history) over teibs010/020 (summary, 12 obs only)
            for ds in ("ei_bssi_m_r2", "teibs010", "teibs020"):
                kw_map = {
                    "EC Economic Sentiment (EA)":  ["sentiment"],
                    "EC Industry Confidence (EA)":  ["industrial", "confidence"],
                    "EC Services Confidence (EA)":  ["services", "confidence"],
                }
                kws = kw_map.get(label, label.lower().split())
                # Euro Area country code in Eurostat: EA19 (pre-2023) or EA20 (current)
                matches = (explore_and_match("Eurostat", ds, kws, limit=500,
                                             required_substrings=[".EA20"])
                           or explore_and_match("Eurostat", ds, kws, limit=500,
                                                required_substrings=[".EA19"])
                           or explore_and_match("Eurostat", ds, kws, limit=500,
                                                required_substrings=[".EA."]))
                if matches:
                    print(f"  Found {len(matches)} matches in Eurostat/{ds}.  Top 3:")
                    for m in matches[:3]:
                        code = m.get("series_code", "?")
                        name = (m.get("series_name") or "")[:80]
                        print(f"    {code}: {name}")
                    best = matches[0]
                    best_sid = f"Eurostat/{ds}/{best['series_code']}"
                    doc2 = fetch_series(best_sid)
                    if doc2:
                        info = analyse_series(doc2)
                        info["series_id"] = best_sid
                        info["group"] = "Eurostat"
                        results.append(info)
                        resolved[label] = best_sid
                        save_sample(best_sid, doc2, label)
                        status = "STALE" if info["stale"] else "OK"
                        print(f"  {status}: {info['n_obs']} obs, {info['first']} → {info['last']}")
                    break
            else:
                results.append({"name": label, "ok": False, "reason": "no match", "group": "Eurostat"})
                print(f"  FAIL: no matching series found")

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    ok_count = sum(1 for r in results if r.get("ok"))
    fail_count = sum(1 for r in results if not r.get("ok"))
    stale_count = sum(1 for r in results if r.get("stale"))
    shallow_count = sum(1 for r in results if r.get("shallow"))

    print(f"\n  Total series tested: {len(results)}")
    print(f"  OK:                  {ok_count}")
    print(f"  FAILED:              {fail_count}")
    print(f"  STALE (>{STALE_DAYS}d):      {stale_count}")
    print(f"  SHALLOW (<{MIN_YEARS}y):     {shallow_count}")

    print(f"\n  {'Label':<35} {'Series ID':<45} {'Status':<8} {'Obs':>5} {'Range':<25} {'Days':>5}")
    print("  " + "-" * 128)
    for r in results:
        label = r.get("name", "?")[:34]
        sid = r.get("series_id", "?")[:44]
        if not r.get("ok"):
            status = "FAIL"
            print(f"  {label:<35} {sid:<45} {status:<8} {'':>5} {r.get('reason',''):<25} {'':>5}")
        else:
            status = "STALE" if r["stale"] else ("SHALLOW" if r.get("shallow") else "OK")
            rng = f"{r['first']} → {r['last']}"
            days = r.get('days_ago')
            days_str = str(days) if days is not None else ""
            print(f"  {label:<35} {sid:<45} {status:<8} {r['n_obs']:>5} {rng:<25} {days_str:>5}")

    # Resolved series mapping (for building macro_library_dbnomics.csv)
    print(f"\n  Resolved series IDs ({len(resolved)}):")
    for label, sid in resolved.items():
        print(f"    {label:<35} → {sid}")

    # Save resolved mapping
    resolved_path = os.path.join(SAMPLE_DIR, "_resolved_series.json")
    with open(resolved_path, "w") as f:
        json.dump(resolved, f, indent=2)
    print(f"\n  Resolved mapping saved to: {resolved_path}")

    if fail_count:
        print(f"\n  WARNING: {fail_count} series failed.  Check output above for fallback options.")
        print("  ECB BLS fallback: direct ECB SDW API (https://data-api.ecb.europa.eu/).")
        print("  Eurostat fallback: direct Eurostat REST API.")

    print(f"\n  Sample CSVs saved to: {SAMPLE_DIR}/")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
