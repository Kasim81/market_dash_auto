"""
scripts/ifo_probe.py
====================
One-shot diagnostic for the ifo Geschäftsklimaindex (gsk-*.xlsx) fetch
failure. Runs in GitHub Actions (full network) and writes findings to
ifo_probe_result.txt so they can be committed and reviewed — the daily
pipeline.log shows gsk URLs returning 3038-byte HTML instead of the
workbook, and we need to know whether that's a stale URL or an anti-bot
block before fixing sources/ifo.py.

Three tests:
  1. Known-good control — a WES-Euro workbook that downloads fine in a
     browser. If the runner gets a real xlsx here, automated download
     works and the gsk failure is a URL problem. If it gets HTML, the
     runner itself is being blocked (anti-bot / WAF).
  2. Link discovery — fetch ifo's time-series / data landing pages and
     extract every href containing 'xlsx' or 'gsk', revealing the CURRENT
     Geschäftsklima download link.
  3. Regression — re-test the gsk URL patterns sources/ifo.py currently
     guesses, to confirm they are dead.

No repo imports; only requests (already in requirements.txt).
"""
from __future__ import annotations

import re
from datetime import date, datetime

import requests

OUT = "ifo_probe_result.txt"

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
}
XLSX_MAGIC = b"PK\x03\x04"

# Control: a known-good ifo xlsx (WES-Euro, supplied by operator).
CONTROL_URL = "https://www.ifo.de/sites/default/files/2019-10/wes-euro-e-2019q4.xlsx"

# Pages that have historically listed the gsk download link.
LANDING_PAGES = [
    "https://www.ifo.de/en/ifo-time-series",
    "https://www.ifo.de/en/survey/ifo-business-survey",
    "https://www.ifo.de/en/ifo-business-climate-index",
    "https://www.ifo.de/ifo-zeitreihen",
]


def _now_yyyymm_candidates(n: int = 4):
    today = date.today()
    out = []
    y, m = today.year, today.month
    for _ in range(n):
        out.append(f"{y:04d}{m:02d}")
        out.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return out


def _gsk_candidates():
    urls = []
    for ym in _now_yyyymm_candidates():
        ym_compact = ym.replace("-", "")
        for stem in (f"gsk-e-{ym_compact}", f"gsk-d-{ym_compact}"):
            urls.append(f"https://www.ifo.de/sites/default/files/{ym}/{stem}.xlsx"
                        if "-" in ym else
                        f"https://www.ifo.de/sites/default/files/{ym[:4]}-{ym[4:]}/{stem}.xlsx")
            urls.append(f"https://www.ifo.de/sites/default/files/secure/timeseries/{stem}.xlsx")
    # de-dup, keep order
    seen, out = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u); out.append(u)
    return out


def _classify(resp: bytes, ctype: str) -> str:
    if resp[:4] == XLSX_MAGIC:
        return "XLSX (real workbook)"
    head = resp.lstrip()[:64].lower()
    if head.startswith(b"<!doctype html") or head.startswith(b"<html"):
        return "HTML"
    return f"OTHER (ctype={ctype})"


def _get(url: str, lines: list):
    try:
        r = requests.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
        body = r.content or b""
        kind = _classify(body, r.headers.get("Content-Type", ""))
        final = r.url if r.url != url else ""
        lines.append(f"    HTTP {r.status_code}  {len(body):>8} bytes  {kind}"
                     + (f"  -> {final}" if final else ""))
        return r, body
    except requests.RequestException as e:
        lines.append(f"    REQUEST ERROR: {type(e).__name__}: {str(e)[:160]}")
        return None, b""


def main():
    lines = [f"=== ifo probe @ {datetime.utcnow().isoformat()}Z ===", ""]

    lines.append("[1] CONTROL — known-good WES-Euro workbook")
    lines.append(f"  {CONTROL_URL}")
    _get(CONTROL_URL, lines)
    lines.append("")

    lines.append("[2] LINK DISCOVERY — scrape landing pages for xlsx/gsk hrefs")
    href_re = re.compile(r'href=[\'"]([^\'"]+)[\'"]', re.IGNORECASE)
    found = set()
    for page in LANDING_PAGES:
        lines.append(f"  {page}")
        r, body = _get(page, lines)
        if r is not None and body:
            try:
                html = body.decode("utf-8", "ignore")
            except Exception:
                html = ""
            for href in href_re.findall(html):
                low = href.lower()
                if "xlsx" in low or "gsk" in low or "geschaeftsklima" in low or "klima" in low:
                    found.add(href)
    lines.append("")
    lines.append("  Candidate download links found:")
    if found:
        for h in sorted(found):
            lines.append(f"    {h}")
    else:
        lines.append("    (none — page likely JS-rendered or restructured)")
    lines.append("")

    lines.append("[3] REGRESSION — gsk URL patterns sources/ifo.py currently guesses")
    for url in _gsk_candidates():
        lines.append(f"  {url}")
        _get(url, lines)
    lines.append("")
    lines.append("=== interpretation ===")
    lines.append("  [1] XLSX  => runner CAN download ifo files -> gsk failure is a URL problem (use [2]).")
    lines.append("  [1] HTML  => runner is blocked (anti-bot/WAF) -> need cookies/headless or substitute.")

    text = "\n".join(lines) + "\n"
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(text)
    print(text)


if __name__ == "__main__":
    main()
