#!/usr/bin/env python3
"""
poc_fmp_calendar.py — Phase D Tier 3 Proof of Concept

Queries the FMP economic calendar for the last 5 years and verifies that
the 8 target PMI/survey events appear with sufficient history (≥3 years)
and reasonable freshness (last observation within 90 days).

Also discovers the exact event names FMP uses (S&P Global rebranded from
"Markit" to "HCOB"/"Jibun Bank" etc., so names may have changed).

Usage:
    export FMP_API_KEY=your_key_here
    python poc_fmp_calendar.py

Output:
    - Summary table of matched events with observation counts and date ranges
    - Sample CSVs saved to data/poc_fmp/
    - Resolved event-name mapping saved to data/poc_fmp/_resolved_events.json

Requires: requests, pandas
API:      https://financialmodelingprep.com/api/v3/economic_calendar
          250 calls/day on free tier
"""

import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta

import pandas as pd
import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

FMP_API_KEY = os.environ.get("FMP_API_KEY", "")
FMP_BASE = "https://financialmodelingprep.com/api/v3/economic_calendar"

SAMPLE_DIR = os.path.join("data", "poc_fmp")
STALE_DAYS = 90
MIN_YEARS = 3
LOOKBACK_YEARS = 5

# How many months per API call (FMP may limit date range per request)
CHUNK_MONTHS = 6

# ---------------------------------------------------------------------------
# Target events — candidate name patterns (case-insensitive substring match)
#
# FMP event names have changed over time (Markit → HCOB, etc.), so we search
# by multiple patterns and report which ones hit.
# ---------------------------------------------------------------------------

TARGET_EVENTS = {
    "EZ_MFG_PMI": {
        "description": "S&P Global Eurozone Manufacturing PMI",
        "country_filter": None,  # match on event name alone
        "patterns": [
            "eurozone manufacturing pmi",
            "hcob eurozone manufacturing pmi",
            "s&p global eurozone manufacturing pmi",
            "eurozone markit manufacturing pmi",
        ],
    },
    "EZ_SVC_PMI": {
        "description": "S&P Global Eurozone Services PMI",
        "country_filter": None,
        "patterns": [
            "eurozone services pmi",
            "hcob eurozone services pmi",
            "s&p global eurozone services pmi",
            "eurozone markit services pmi",
        ],
    },
    "DE_ZEW": {
        "description": "ZEW Economic Sentiment (Germany)",
        "country_filter": None,
        "patterns": [
            "zew economic sentiment",
            "germany zew economic sentiment",
            "german zew economic sentiment",
        ],
    },
    "DE_IFO": {
        "description": "IFO Business Climate (Germany)",
        "country_filter": None,
        "patterns": [
            "ifo business climate",
            "germany ifo business climate",
            "german ifo business climate",
        ],
    },
    "UK_PMI": {
        "description": "S&P Global UK Manufacturing PMI",
        "country_filter": None,
        "patterns": [
            "uk manufacturing pmi",
            "s&p global uk manufacturing pmi",
            "uk markit manufacturing pmi",
            "s&p global / cips uk manufacturing pmi",
        ],
    },
    "JP_PMI": {
        "description": "Jibun Bank Japan Manufacturing PMI",
        "country_filter": None,
        "patterns": [
            "japan manufacturing pmi",
            "jibun bank japan manufacturing pmi",
            "au jibun bank japan manufacturing pmi",
            "japan markit manufacturing pmi",
            "japan nikkei manufacturing pmi",
        ],
    },
    "CN_NBS_PMI": {
        "description": "NBS China Manufacturing PMI",
        "country_filter": None,
        "patterns": [
            "chinese manufacturing pmi",
            "china manufacturing pmi",
            "nbs manufacturing pmi",
            "china nbs manufacturing pmi",
            "chinese nbs manufacturing pmi",
        ],
    },
    "CN_CAIXIN_PMI": {
        "description": "Caixin China Manufacturing PMI",
        "country_filter": None,
        "patterns": [
            "caixin manufacturing pmi",
            "china caixin manufacturing pmi",
            "caixin china general manufacturing pmi",
            "caixin china manufacturing pmi",
        ],
    },
}


# ---------------------------------------------------------------------------
# FMP API helpers
# ---------------------------------------------------------------------------

def fetch_calendar_chunk(start_date: str, end_date: str) -> list[dict]:
    """
    Fetch one chunk of the FMP economic calendar.
    Returns list of event dicts or empty list on failure.
    """
    if not FMP_API_KEY:
        print("  ERROR: FMP_API_KEY not set")
        return []

    params = {
        "from": start_date,
        "to": end_date,
        "apikey": FMP_API_KEY,
    }

    for attempt in range(3):
        try:
            resp = requests.get(FMP_BASE, params=params, timeout=30)

            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    return data
                if isinstance(data, dict) and "Error Message" in data:
                    print(f"  API error: {data['Error Message']}")
                    return []
                return []

            elif resp.status_code == 429:
                wait = 2 ** (attempt + 1)
                print(f"  Rate limited — waiting {wait}s...")
                time.sleep(wait)

            elif resp.status_code >= 500:
                wait = 2 ** (attempt + 1)
                print(f"  Server error {resp.status_code} — waiting {wait}s...")
                time.sleep(wait)

            else:
                print(f"  HTTP {resp.status_code} for {start_date}→{end_date}")
                return []

        except requests.exceptions.RequestException as e:
            print(f"  Request error: {e}")
            wait = 2 ** (attempt + 1)
            time.sleep(wait)

    return []


def fetch_full_calendar(years: int = LOOKBACK_YEARS) -> list[dict]:
    """
    Fetch the full economic calendar in chunks over the lookback period.
    Returns all events as a flat list.
    """
    all_events = []
    end = datetime.now()
    start = end - timedelta(days=years * 365)

    # Chunk into CHUNK_MONTHS-month windows
    cursor = start
    chunk_num = 0
    while cursor < end:
        chunk_end = min(cursor + timedelta(days=CHUNK_MONTHS * 30), end)
        s = cursor.strftime("%Y-%m-%d")
        e = chunk_end.strftime("%Y-%m-%d")
        chunk_num += 1
        print(f"  Chunk {chunk_num}: {s} → {e} ...", end=" ", flush=True)

        events = fetch_calendar_chunk(s, e)
        print(f"{len(events)} events")
        all_events.extend(events)

        cursor = chunk_end + timedelta(days=1)
        time.sleep(0.5)  # courtesy delay

    print(f"\n  Total events fetched: {len(all_events)}")
    return all_events


# ---------------------------------------------------------------------------
# Event matching
# ---------------------------------------------------------------------------

def match_events(all_events: list[dict]) -> dict[str, list[dict]]:
    """
    Match fetched calendar events against target patterns.
    Returns {target_key: [matched_event_dicts]} sorted by date ascending.
    """
    matched = defaultdict(list)

    for event in all_events:
        name = (event.get("event") or "").lower().strip()
        country = (event.get("country") or "").lower().strip()
        actual = event.get("actual")

        for key, spec in TARGET_EVENTS.items():
            # Check if any pattern matches
            for pattern in spec["patterns"]:
                if pattern.lower() in name:
                    # Optional country filter
                    cf = spec.get("country_filter")
                    if cf and cf.lower() not in country:
                        continue
                    matched[key].append(event)
                    break  # don't double-match same event to same target

    # Sort each target's matches by date ascending
    for key in matched:
        matched[key].sort(key=lambda e: e.get("date", ""))

    return dict(matched)


def analyse_matched(key: str, events: list[dict]) -> dict:
    """Analyse a set of matched events for one target."""
    spec = TARGET_EVENTS[key]

    # Filter to events with actual values
    with_actual = [
        e for e in events
        if e.get("actual") is not None and str(e["actual"]).strip() not in ("", "None")
    ]

    if not with_actual:
        return {
            "key": key,
            "description": spec["description"],
            "ok": False,
            "reason": f"{len(events)} events matched but none have 'actual' values",
            "total_matches": len(events),
        }

    first_date = with_actual[0].get("date", "?")
    last_date = with_actual[-1].get("date", "?")
    last_actual = with_actual[-1].get("actual")
    event_names = set(e.get("event", "?") for e in with_actual)

    # Freshness
    days_ago = None
    try:
        last_dt = datetime.strptime(str(last_date)[:10], "%Y-%m-%d")
        days_ago = (datetime.now() - last_dt).days
    except ValueError:
        pass

    # History depth
    years = None
    try:
        first_dt = datetime.strptime(str(first_date)[:10], "%Y-%m-%d")
        last_dt = datetime.strptime(str(last_date)[:10], "%Y-%m-%d")
        years = round((last_dt - first_dt).days / 365.25, 1)
    except ValueError:
        pass

    return {
        "key": key,
        "description": spec["description"],
        "ok": True,
        "n_actual": len(with_actual),
        "total_matches": len(events),
        "first_date": str(first_date)[:10],
        "last_date": str(last_date)[:10],
        "last_actual": last_actual,
        "days_ago": days_ago,
        "stale": days_ago is not None and days_ago > STALE_DAYS,
        "years": years,
        "shallow": years is not None and years < MIN_YEARS,
        "event_names": sorted(event_names),
    }


# ---------------------------------------------------------------------------
# Discovery — find all unique event names by country
# ---------------------------------------------------------------------------

def discover_event_names(all_events: list[dict], countries: list[str] = None) -> dict:
    """
    Group all unique event names by country.
    If countries is provided, only include those countries.
    Returns {country: {event_name: count}}.
    """
    by_country = defaultdict(lambda: defaultdict(int))
    for event in all_events:
        country = (event.get("country") or "unknown").strip()
        name = (event.get("event") or "").strip()
        if countries and country.lower() not in [c.lower() for c in countries]:
            continue
        by_country[country][name] += 1
    return dict(by_country)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if not FMP_API_KEY:
        print("ERROR: Set FMP_API_KEY environment variable before running.")
        print("  export FMP_API_KEY=your_key_here")
        return 1

    os.makedirs(SAMPLE_DIR, exist_ok=True)
    resolved = {}

    # -----------------------------------------------------------------------
    # Step 1: Fetch calendar
    # -----------------------------------------------------------------------
    print("=" * 70)
    print(f"STEP 1 — Fetch FMP Economic Calendar ({LOOKBACK_YEARS} years)")
    print("=" * 70)
    all_events = fetch_full_calendar(LOOKBACK_YEARS)
    if not all_events:
        print("\nFATAL: No events returned.  Check API key and network.")
        return 1

    # -----------------------------------------------------------------------
    # Step 2: Discovery — what PMI/survey events exist?
    # -----------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("STEP 2 — Discover PMI/Survey Event Names")
    print("=" * 70)

    pmi_keywords = ["pmi", "ifo", "zew", "tankan", "sentiment", "confidence",
                     "manufacturing", "services"]
    pmi_events = [
        e for e in all_events
        if any(kw in (e.get("event") or "").lower() for kw in pmi_keywords)
    ]
    print(f"\n  Found {len(pmi_events)} events matching PMI/survey keywords")

    # Show unique names grouped by rough country
    name_counts = defaultdict(int)
    for e in pmi_events:
        name = (e.get("event") or "?").strip()
        name_counts[name] += 1

    print(f"\n  Unique event names ({len(name_counts)}):")
    for name, count in sorted(name_counts.items(), key=lambda x: -x[1])[:50]:
        print(f"    [{count:>3}x] {name}")

    # -----------------------------------------------------------------------
    # Step 3: Match against targets
    # -----------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("STEP 3 — Match Target Events")
    print("=" * 70)

    matched = match_events(all_events)
    results = []

    for key in TARGET_EVENTS:
        events = matched.get(key, [])
        if not events:
            info = {
                "key": key,
                "description": TARGET_EVENTS[key]["description"],
                "ok": False,
                "reason": "no matching events found",
                "total_matches": 0,
            }
            results.append(info)
            print(f"\n  {key}: NO MATCH")
            print(f"    Patterns tried: {TARGET_EVENTS[key]['patterns']}")
        else:
            info = analyse_matched(key, events)
            results.append(info)
            resolved[key] = {
                "event_names": info.get("event_names", []),
                "first_date": info.get("first_date"),
                "last_date": info.get("last_date"),
                "n_actual": info.get("n_actual", 0),
            }

            status = "OK"
            if not info["ok"]:
                status = "NO_ACTUAL"
            elif info.get("stale"):
                status = "STALE"
            elif info.get("shallow"):
                status = "SHALLOW"

            print(f"\n  {key}: {status}")
            print(f"    Description:  {info['description']}")
            print(f"    Event names:  {info.get('event_names', [])}")
            print(f"    With actual:  {info.get('n_actual', 0)} / {info['total_matches']} total")
            if info["ok"]:
                print(f"    Range:        {info['first_date']} → {info['last_date']} "
                      f"({info['years']}y)")
                print(f"    Last actual:  {info['last_actual']} ({info['days_ago']}d ago)")

            # Save sample CSV
            if events:
                sample_df = pd.DataFrame(events)
                cols = [c for c in ["date", "event", "country", "actual", "previous",
                                     "estimate", "impact"] if c in sample_df.columns]
                sample_df = sample_df[cols].sort_values("date")
                sample_path = os.path.join(SAMPLE_DIR, f"{key}.csv")
                sample_df.to_csv(sample_path, index=False)

    # -----------------------------------------------------------------------
    # Step 4: Summary
    # -----------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    ok_count = sum(1 for r in results if r.get("ok"))
    fail_count = sum(1 for r in results if not r.get("ok"))
    stale_count = sum(1 for r in results if r.get("stale"))
    shallow_count = sum(1 for r in results if r.get("shallow"))

    print(f"\n  Targets:    {len(results)}")
    print(f"  OK:         {ok_count}")
    print(f"  FAILED:     {fail_count}")
    print(f"  STALE:      {stale_count}")
    print(f"  SHALLOW:    {shallow_count}")

    print(f"\n  {'Key':<16} {'Description':<45} {'Status':<9} {'N':>4} "
          f"{'Range':<25} {'Days':>5}")
    print("  " + "-" * 110)

    for r in results:
        key = r["key"]
        desc = r["description"][:44]
        if not r.get("ok"):
            status = "FAIL"
            print(f"  {key:<16} {desc:<45} {status:<9} {'':>4} "
                  f"{r.get('reason', ''):<25}")
        else:
            status = "STALE" if r.get("stale") else ("SHALLOW" if r.get("shallow") else "OK")
            rng = f"{r['first_date']} → {r['last_date']}"
            print(f"  {key:<16} {desc:<45} {status:<9} {r['n_actual']:>4} "
                  f"{rng:<25} {r.get('days_ago', ''):>5}")

    # Save resolved mapping
    resolved_path = os.path.join(SAMPLE_DIR, "_resolved_events.json")
    with open(resolved_path, "w") as f:
        json.dump(resolved, f, indent=2)
    print(f"\n  Resolved event mapping saved to: {resolved_path}")
    print(f"  Sample CSVs saved to: {SAMPLE_DIR}/")

    if fail_count:
        print(f"\n  WARNING: {fail_count} targets failed to match.")
        print("  Check STEP 2 output above for actual event names in the FMP calendar.")
        print("  You may need to update the 'patterns' list in this script.")

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
