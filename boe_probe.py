#!/usr/bin/env python3
"""BoE IADB probe — discover canonical series codes for:
  (a) UK gilt yield curve points (2Y, 5Y, 10Y, 30Y) — fills UK yield-curve gaps
  (b) UK corporate IG / HY bond yield indices — candidate proxies for a UK
      credit spread indicator (mirror of EU_Cr1 work)

Mechanism: hit BoE IADB getMetadata-style URL (the same _iadb-fromshowcolumns.asp
endpoint our sources/boe.py wires) for each candidate; if it returns a non-HTML
CSV with a TIME/DATE row, the series is live and we capture the latest value
+ name. If it returns 404 / HTML / empty, we skip and report.

Sandbox blocks BoE; this runs in CI via .github/workflows/boe_probe.yml.
"""

from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO_ROOT)

from sources import boe as boe_src

# Candidate BoE IADB series codes by goal.
# Codes are educated guesses based on documented IADB naming conventions —
# IUDxxx / IUMxxx prefixes for various rate series. The probe tells us which
# actually resolve on the live API.
CANDIDATES = {
    # Goal: UK gilt par yield curve points (closes UK yield-curve gaps)
    # IUDxxx series are "par" yields; IUMxxx tend to be redemption yields.
    # Pattern: <prefix><tenor in years><PY=par yield / RY=redemption / SY=spot>
    "Gilt_2Y": [
        "IUDMNPY",   # Nominal par yield 2Y
        "IUDSNPY",   # Spot 2Y nominal
        "IUDLNPY",   # Long nominal — may be different tenor
        "IUDAJNB",   # 2Y spot zero-coupon
    ],
    "Gilt_5Y": [
        "IUDSF5Y",   # Spot 5Y
        "IUDMF5Y",   # Maturity 5Y nominal
        "IUDS5NN",   # 5Y zero
        "IUDAMNB",   # Spot 5Y
    ],
    "Gilt_10Y": [
        "IUDMNZC",   # 10Y nominal zero coupon
        "IUDLLAEN",  # 10Y "long" yield
        "IUDS10NN",  # 10Y spot nominal
        "IUDMRFLY",  # 10Y maturity reference
    ],
    "Gilt_30Y": [
        "IUDS30NN",  # 30Y spot nominal
        "IUDMRFL30", # 30Y reference
        "IUDLNZC",   # Long zero-coupon
        "IUDM30NB",  # 30Y nominal bond
    ],
    # Goal: UK corporate IG bond yield (credit spread proxy mirror of EU_Cr1)
    # BoE publishes "Sterling-denominated investment grade corporate bond
    # yield indices" via Bank Of England Composite indices. Candidate codes
    # follow IUDxxx pattern.
    "UK_corp_IG": [
        "IUDLBSCY",  # Sterling investment grade composite yield
        "IUDLBSCM",  # Sterling IG monthly avg
        "IUDLNICY",  # Non-financial corporate yield
        "IUMABCRY",  # Corporate redemption yield
        "IUDLCORY",  # Composite corporate yield
        "IUMAJND",   # Aaa-A composite
    ],
    # Goal: UK corporate HY (high-yield / sub-IG)
    "UK_corp_HY": [
        "IUDLBHCY",  # Sterling HY composite yield
        "IUDLBHCM",  # Sterling HY monthly
        "IUDLNHCY",  # Non-financial HY yield
        "IUMABHRY",  # HY redemption yield
    ],
    # Goal: SONIA & OIS (overnight / short-end fixings, useful for regime work)
    "SONIA_OIS": [
        "IUDSOIA",   # SONIA 1-day rate
        "IUDSAJNB",  # SONIA-OIS 1Y
        "IUDSAJND",  # SONIA-OIS 5Y
        "IUDS01M",   # 1M OIS
    ],
}


def probe_one(code):
    """Returns (status, latest_date, latest_value, raw_first_chars)."""
    try:
        text = boe_src.fetch_series(code, start="2020-01-01", retries=1)
        if text is None:
            return ("no response", None, None, "")
        head = text.lstrip()[:120]
        # Check for HTML form-page response (common BoE failure mode)
        if head.lower().startswith("<!doctype html") or head.lower().startswith("<html"):
            return ("HTML form", None, None, head[:60])
        obs = boe_src.parse_csv(text, code)
        if not obs:
            return ("no data", None, None, head[:60])
        last = obs[-1]
        return ("live", str(last[0]), last[1], head[:60])
    except Exception as e:
        return (f"ERR:{type(e).__name__}", None, None, str(e)[:60])


def main():
    n = sum(len(v) for v in CANDIDATES.values())
    print(f"BoE IADB probe — {n} candidate codes\n")
    print(f"{'goal':<12s}  {'code':<10s}  {'status':<11s}  {'latest':<12s}  value")
    print("-" * 80)

    rows = []
    for goal, codes in CANDIDATES.items():
        for code in codes:
            status, last_date, last_val, head_preview = probe_one(code)
            print(f"{goal:<12s}  {code:<10s}  {status:<11s}  {str(last_date or '—'):<12s}  {last_val or '—'}")
            rows.append({
                "goal": goal,
                "code": code,
                "status": status,
                "last_date": last_date,
                "last_value": last_val,
            })

    print()
    print("=== SUMMARY ===")
    live = [r for r in rows if r["status"] == "live"]
    by_goal = {}
    for r in rows:
        by_goal.setdefault(r["goal"], []).append(r["status"])
    for g, sts in by_goal.items():
        live_count = sum(1 for s in sts if s == "live")
        print(f"  {g:<12s}  {live_count}/{len(sts)} live")
    print(f"  total live: {len(live)}/{len(rows)}")


if __name__ == "__main__":
    main()
