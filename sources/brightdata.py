"""
sources/brightdata.py
=====================
Thin, shared Bright Data **Web Unlocker** client.

Some sources publish only behind bot-protection that a vanilla
``requests.get()`` cannot pass (HTTP 403 / CAPTCHA challenge) — e.g. the
official ISM PMI press releases on PR Newswire, or the ifo workbook when the
canonical host blocks datacenter IPs. Bright Data's Web Unlocker proxies the
request through a residential-grade unlocker and streams the upstream body
back unmodified.

Contract (verified from docs.brightdata.com/scraping-automation/web-unlocker):

    POST https://api.brightdata.com/request
    Authorization: Bearer <BRIGHTDATA_API_KEY>
    {"zone": "<zone>", "url": "<target url>", "format": "raw"}

Environment:

    BRIGHTDATA_API_KEY   account-level API key. **If unset, this module is a
                         clean no-op** — ``unlock()`` returns None and the
                         caller degrades to last-known data. Local dev and
                         forks therefore never touch the network; only a
                         credentialed production run routes through the
                         unlocker.
    BRIGHTDATA_ZONE      (optional) unlocker zone name; defaults to
                         "web_unlocker1".

A process-wide call cap (``_MAX_CALLS_PER_RUN``) protects the user's monthly
quota from a runaway retry loop. The counter is shared across every caller in
the process, so the ISM fallback and any other Bright Data consumer draw from
one budget.

Historical note: ``sources/ifo.py`` predates this module and carries its own
equivalent client; it can adopt this one later. New code should use this.
"""

from __future__ import annotations

import os

import requests

_ENDPOINT = "https://api.brightdata.com/request"
_DEFAULT_ZONE = "web_unlocker1"

# Per-process safety cap. At the limit unlock() logs and returns None; the
# caller treats it as a clean miss. Bumping this is fine — it exists only to
# stop a misbehaving loop from draining the free-tier quota in one run.
_MAX_CALLS_PER_RUN = 30
_CALLS = 0


def credentials() -> tuple[str, str] | None:
    """Return (api_key, zone) if BRIGHTDATA_API_KEY is set, else None."""
    api_key = os.environ.get("BRIGHTDATA_API_KEY", "").strip()
    if not api_key:
        return None
    zone = os.environ.get("BRIGHTDATA_ZONE", "").strip() or _DEFAULT_ZONE
    return api_key, zone


def available() -> bool:
    """True when credentials are configured (a fetch would actually run)."""
    return credentials() is not None


def calls_made() -> int:
    """Number of unlocker calls issued so far this process (for tests/logs)."""
    return _CALLS


def unlock(url: str, tag: str = "brightdata", timeout: int = 60) -> bytes | None:
    """Fetch ``url`` through Bright Data Web Unlocker, returning the raw
    upstream body bytes on HTTP 200, or None on any failure / no-credentials /
    budget exhausted.

    Network-defensive: every exception is swallowed and logged so a caller in
    the daily pipeline can fall through to "no data → last-known" without
    crashing. ``tag`` is a short caller label used only in log lines.
    """
    global _CALLS
    creds = credentials()
    if creds is None:
        return None
    api_key, zone = creds

    if _CALLS >= _MAX_CALLS_PER_RUN:
        print(
            f"  [{tag} BUDGET EXHAUSTED] Bright Data per-run cap of "
            f"{_MAX_CALLS_PER_RUN} reached; refusing further calls this "
            f"process.",
            flush=True,
        )
        return None
    _CALLS += 1

    payload = {"zone": zone, "url": url, "format": "raw"}
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    print(
        f"  [{tag}] Bright Data unlock #{_CALLS}/{_MAX_CALLS_PER_RUN}: "
        f"zone={zone!r} url={url}",
        flush=True,
    )
    try:
        r = requests.post(_ENDPOINT, headers=headers, json=payload, timeout=timeout)
    except requests.exceptions.RequestException as e:
        print(f"  [{tag}] Bright Data POST raised {type(e).__name__}: {e}", flush=True)
        return None

    if r.status_code != 200:
        snippet = r.content[:160].replace(b"\n", b" ")
        print(
            f"  [{tag}] Bright Data HTTP {r.status_code} for {url}; "
            f"first 160 bytes: {snippet!r}",
            flush=True,
        )
        return None

    return r.content


def unlock_text(url: str, tag: str = "brightdata", timeout: int = 60) -> str | None:
    """unlock() decoded as UTF-8 text (errors replaced). None on failure."""
    body = unlock(url, tag=tag, timeout=timeout)
    if body is None:
        return None
    return body.decode("utf-8", errors="replace")
