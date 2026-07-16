"""
fetch_pe.py — daily equity-valuation snapshot writer (§3.3).

Resolves trailing/forward P/E for the major-index ETF set through the
yfinance → Alpha Vantage source chain (see sources/equity_pe.py) and upserts the
result into data/equity_pe_snapshot.csv under today's UTC date, growing the file
into a daily P/E history. Prints a one-line-per-ticker summary.

Non-fatal by design: run under `continue-on-error` in update_data.yml. A total
fetch miss (network/quota) leaves the existing history untouched and exits 0, so
a transient outage never turns the daily run red.
"""

import datetime as _dt

from sources import equity_pe


def main() -> int:
    asof = _dt.datetime.now(_dt.timezone.utc).date().isoformat()
    print(f"[fetch_pe] building equity P/E snapshot for {asof} "
          f"({len(equity_pe.MAJOR_INDEX_ETFS)} tickers)")
    rows = equity_pe.build_snapshot(asof)
    for r in rows:
        ttm = f"{r['pe_ttm']:.2f}" if r["pe_ttm"] is not None else "—"
        fwd = f"{r['pe_forward']:.2f}" if r["pe_forward"] is not None else "—"
        print(f"    {r['ticker']:5s} PE(ttm)={ttm:>7s}  PE(fwd)={fwd:>7s}  "
              f"[{r['source']}]  {r['name']}")
    if not rows:
        print("[fetch_pe] no P/E data resolved this run — history left unchanged")
        return 0
    out = equity_pe.upsert_snapshot(rows)
    print(f"[fetch_pe] wrote {len(rows)} row(s) for {asof}; "
          f"history now {len(out)} row(s) across "
          f"{out['asof_date'].nunique()} date(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
