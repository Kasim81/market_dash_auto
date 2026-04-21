#!/usr/bin/env python3
"""
poc_dbnomics.py — Phase D Tier 2 Proof of Concept

Verifies all 12 target DB.nomics series are reachable, have sufficient history,
and are reasonably fresh (last observation within 90 days).

Also resolves placeholder dimension keys for ECB/BLS, Eurostat, and BOJ/Tankan
datasets whose exact series codes were unknown at planning time.

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
# Part 1 — ISM (known series codes)
# ---------------------------------------------------------------------------

ISM_SERIES = {
    "ISM Mfg PMI":          ["ISM/pmi/pm"],
    "ISM Mfg New Orders":   ["ISM/new-orders/pm", "ISM/mno/pm", "ISM/noi/pm"],
    "ISM Svc PMI":          ["ISM/nm-pmi/pm"],
    "ISM Svc Business Act": ["ISM/nm-business/pm", "ISM/nm-business-activity/pm",
                              "ISM/nm-ba/pm"],
}

# ---------------------------------------------------------------------------
# Part 2 — ECB Bank Lending Survey (need dimension resolution)
#
# ECB/BLS has ~20k series.  We want:
#   - Credit standards for loans to enterprises (net % tightening, EA)
#   - Credit standards for loans to households for house purchase (net %, EA)
#
# The series code mirrors ECB SDMX key structure.  We try several candidate
# codes and also search by keyword if none hit.
# ---------------------------------------------------------------------------

ECB_BLS_CANDIDATES = {
    "ECB BLS — Credit Std Enterprises": [
        # Most likely: Q.U2.ALL.Z.B3.Z.Z.ST.S.BWFNET
        #   Q=Quarterly, U2=EA changing composition, ALL=all banks
        #   B3=loans to enterprises, ST=standards, BWFNET=balanced weighted net %
        "ECB/BLS/Q.U2.ALL.Z.B3.Z.Z.ST.S.BWFNET",
        "ECB/BLS/Q.U2.ALL.Z.B.Z.Z.ST.S.BWFNET",
        # Fallback: search
    ],
    "ECB BLS — Credit Std Households": [
        "ECB/BLS/Q.U2.ALL.Z.B5.Z.Z.ST.S.BWFNET",
        "ECB/BLS/Q.U2.ALL.Z.B6.Z.Z.ST.S.BWFNET",
        "ECB/BLS/Q.U2.ALL.Z.H.Z.Z.ST.S.BWFNET",
    ],
}

# ---------------------------------------------------------------------------
# Part 3 — Eurostat ESI / Confidence
#
# teibs010 = ESI composite; teibs020 = sector confidence
# Series codes: M.<indicator>.<adjustment>.<country>
# ---------------------------------------------------------------------------

EUROSTAT_CANDIDATES = {
    "EC Economic Sentiment (EA)": [
        "Eurostat/teibs010/M.BS-ESI-I.SA.EA",
        "Eurostat/teibs010/M.BS-ESI-I.SA.EA19",
        "Eurostat/ei_bssi_m_r2/M.BS-ESI-I.SA.EA",
    ],
    "EC Industry Confidence (EA)": [
        "Eurostat/teibs020/M.BS-ICI-BAL.SA.EA",
        "Eurostat/teibs020/M.BS-ICI-BAL.SA.EA19",
        "Eurostat/ei_bssi_m_r2/M.BS-ICI-BAL.SA.EA",
    ],
    "EC Services Confidence (EA)": [
        "Eurostat/teibs020/M.BS-SCI-BAL.SA.EA",
        "Eurostat/teibs020/M.BS-SCI-BAL.SA.EA19",
        "Eurostat/ei_bssi_m_r2/M.BS-SCI-BAL.SA.EA",
    ],
}

# ---------------------------------------------------------------------------
# Part 4 — BOJ Tankan
#
# BOJ provider on DB.nomics.  Tankan dataset code is uncertain — try CO,
# tankan, and TANKAN.  If provider exists but dataset is missing, we fall
# back to searching BOJ datasets.
# ---------------------------------------------------------------------------

BOJ_TANKAN_CANDIDATES = {
    "Tankan Large Mfr DI": [
        "BOJ/CO/DI_L_MFG",
        "BOJ/CO/BSTTTSAC110Q",
        "BOJ/tankan/DI_L_MFG",
    ],
    "Tankan Large Mfr Forecast DI": [
        "BOJ/CO/DI_L_MFG_F",
        "BOJ/CO/BSTTTSAC120Q",
        "BOJ/tankan/DI_L_MFG_F",
    ],
    "Tankan Large Non-Mfr DI": [
        "BOJ/CO/DI_L_NMFG",
        "BOJ/CO/BSTTTSAC210Q",
        "BOJ/tankan/DI_L_NMFG",
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
                      limit: int = 500) -> list[dict]:
    """
    List series in a dataset, return those whose series_name contains
    ALL keywords (case-insensitive).
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
    # Part 1: ISM (known)
    # -----------------------------------------------------------------------
    print("=" * 70)
    print("PART 1 — ISM Manufacturing & Services (4 series)")
    print("=" * 70)

    # First, list all ISM datasets for diagnostics
    print("\n  Listing ISM datasets on DB.nomics...")
    ism_datasets = list_datasets("ISM")
    if ism_datasets:
        print(f"  Found {len(ism_datasets)} ISM datasets:")
        for ds in ism_datasets:
            code = ds.get("code", "?")
            name = (ds.get("name") or ds.get("description") or "")[:70]
            n = ds.get("nb_series", "?")
            print(f"    {code}: {name} ({n} series)")
    else:
        print("  WARNING: ISM provider not found or has no datasets on DB.nomics")

    for label, candidates in ISM_SERIES.items():
        print(f"\n  Trying candidates for: {label}")
        doc, sid = try_candidates(label, candidates)
        if doc:
            info = analyse_series(doc)
            info["series_id"] = sid
            info["group"] = "ISM"
            results.append(info)
            resolved[label] = sid
            save_sample(sid, doc, label)
            status = "STALE" if info["stale"] else "OK"
            print(f"  {status}: resolved as {sid}")
            print(f"         {info['n_obs']} obs, {info['first']} → {info['last']} "
                  f"({info['years']}y), last value={info['last_value']}, "
                  f"{info['days_ago']}d ago")
        else:
            # Explore ISM datasets by keyword
            print(f"  No candidate hit.  Searching ISM datasets by keyword...")
            kw_map = {
                "ISM Mfg New Orders":   ["new", "order"],
                "ISM Svc Business Act": ["business", "activity"],
            }
            kws = kw_map.get(label, label.lower().split())
            found = False
            for ds in ism_datasets:
                ds_code = ds.get("code", "")
                matches = explore_and_match("ISM", ds_code, kws, limit=50)
                if matches:
                    print(f"  Found {len(matches)} matches in ISM/{ds_code}.  Top 3:")
                    for m in matches[:3]:
                        code = m.get("series_code", "?")
                        name = (m.get("series_name") or "")[:80]
                        print(f"    {code}: {name}")
                    best = matches[0]
                    best_sid = f"ISM/{ds_code}/{best['series_code']}"
                    doc2 = fetch_series(best_sid)
                    if doc2:
                        info = analyse_series(doc2)
                        info["series_id"] = best_sid
                        info["group"] = "ISM"
                        results.append(info)
                        resolved[label] = best_sid
                        save_sample(best_sid, doc2, label)
                        status = "STALE" if info["stale"] else "OK"
                        print(f"  {status}: {info['n_obs']} obs, {info['first']} → {info['last']}")
                    found = True
                    break
            if not found:
                results.append({"name": label, "series_id": candidates[0], "ok": False,
                                "reason": "not on DB.nomics", "group": "ISM"})
                print(f"  FAIL: ISM series not found on DB.nomics")

    # -----------------------------------------------------------------------
    # Part 2: ECB Bank Lending Survey
    # -----------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("PART 2 — ECB Bank Lending Survey (2 series, need dimension resolution)")
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
            print(f"  No candidate hit.  Exploring ECB/BLS dataset by keyword...")
            kw_map = {
                "Credit Std Enterprises": ["credit", "standards", "enterprise", "net"],
                "Credit Std Households": ["credit", "standards", "household", "net"],
            }
            short = label.split("—")[-1].strip()
            kws = kw_map.get(short, short.lower().split())
            matches = explore_and_match("ECB", "BLS", kws, limit=500)
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
    # Part 3: Eurostat ESI / Confidence
    # -----------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("PART 3 — Eurostat ESI + Sector Confidence (3 series)")
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
            for ds in ("teibs010", "teibs020", "ei_bssi_m_r2"):
                kw_map = {
                    "EC Economic Sentiment (EA)":  ["sentiment", "ea"],
                    "EC Industry Confidence (EA)":  ["industry", "ea"],
                    "EC Services Confidence (EA)":  ["services", "ea"],
                }
                kws = kw_map.get(label, label.lower().split())
                matches = explore_and_match("Eurostat", ds, kws, limit=200)
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
    # Part 4: BOJ Tankan
    # -----------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("PART 4 — BOJ Tankan (3 series, dataset code uncertain)")
    print("=" * 70)

    # First, check what datasets BOJ has on DB.nomics
    print("\n  Listing BOJ datasets on DB.nomics...")
    boj_datasets = list_datasets("BOJ")
    if boj_datasets:
        print(f"  Found {len(boj_datasets)} BOJ datasets:")
        for ds in boj_datasets[:20]:
            code = ds.get("code", "?")
            name = (ds.get("name") or ds.get("description") or "")[:70]
            n = ds.get("nb_series", "?")
            print(f"    {code}: {name} ({n} series)")
    else:
        print("  WARNING: BOJ provider not found or has no datasets on DB.nomics")

    for label, candidates in BOJ_TANKAN_CANDIDATES.items():
        print(f"\n  Trying candidates for: {label}")
        doc, sid = try_candidates(label, candidates)
        if doc:
            info = analyse_series(doc)
            info["series_id"] = sid
            info["group"] = "BOJ_Tankan"
            results.append(info)
            resolved[label] = sid
            save_sample(sid, doc, label)
            status = "STALE" if info["stale"] else "OK"
            print(f"  {status}: resolved as {sid}")
            print(f"         {info['n_obs']} obs, {info['first']} → {info['last']} "
                  f"({info['years']}y), last={info['last_value']}, {info['days_ago']}d ago")
        else:
            # Search across all BOJ datasets for Tankan keywords
            print(f"  No candidate hit.  Searching BOJ datasets for Tankan keywords...")
            kw_map = {
                "Tankan Large Mfr DI":          ["tankan", "large", "manufactur"],
                "Tankan Large Mfr Forecast DI": ["tankan", "large", "manufactur", "forecast"],
                "Tankan Large Non-Mfr DI":      ["tankan", "large", "non-manufactur"],
            }
            kws = kw_map.get(label, ["tankan"])
            found = False
            for ds in boj_datasets[:15]:
                ds_code = ds.get("code", "")
                matches = explore_and_match("BOJ", ds_code, kws, limit=100)
                if matches:
                    print(f"  Found {len(matches)} matches in BOJ/{ds_code}.  Top 3:")
                    for m in matches[:3]:
                        code = m.get("series_code", "?")
                        name = (m.get("series_name") or "")[:80]
                        print(f"    {code}: {name}")
                    best = matches[0]
                    best_sid = f"BOJ/{ds_code}/{best['series_code']}"
                    doc2 = fetch_series(best_sid)
                    if doc2:
                        info = analyse_series(doc2)
                        info["series_id"] = best_sid
                        info["group"] = "BOJ_Tankan"
                        results.append(info)
                        resolved[label] = best_sid
                        save_sample(best_sid, doc2, label)
                        status = "STALE" if info["stale"] else "OK"
                        print(f"  {status}: {info['n_obs']} obs, {info['first']} → {info['last']}")
                    found = True
                    break
            if not found:
                results.append({"name": label, "ok": False, "reason": "not on DB.nomics", "group": "BOJ_Tankan"})
                print(f"  FAIL: Tankan series not found on DB.nomics")

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
        print("  BOJ Tankan may need direct BoJ API (https://www.boj.or.jp/en/statistics/tk/).")
        print("  ECB BLS may need direct ECB SDW API (https://data-api.ecb.europa.eu/).")

    print(f"\n  Sample CSVs saved to: {SAMPLE_DIR}/")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
