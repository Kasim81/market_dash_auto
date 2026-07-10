"""
sources/french.py
=================
Kenneth French Data Library — long-run US/international/EM factor returns.

Wired §3.11 (2026-06-10) as one of the regime-AA-driven long-run sources.
Provides US factor monthly returns plus the 1-month T-bill risk-free
rate.  The factors come from two sibling ZIP files published at:

    https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/
        F-F_Research_Data_Factors_CSV.zip            (3-Factor, 1926-07+)
        F-F_Research_Data_5_Factors_2x3_CSV.zip      (5-Factor, 1963-07+)

The 5-Factor file is the canonical Mkt/SMB/HML/RMW/CMA/RF bundle but
its monthly history only goes back to **1963-07** — RMW and CMA depend
on Compustat operating-profitability data that is unavailable before
then (verified against Ken French's f-f_5_factors_2x3.html details
page).  The 3-Factor file is the long-history source for Mkt-RF, SMB,
HML, and RF and covers **July 1926 to present**.

The library mixes both: Mkt-RF / SMB / HML / RF point at the 3-Factor
ZIP (full 1926-07 history) and RMW / CMA point at the 5-Factor ZIP
(1963-07 history).  Previously every row pointed at the 5-Factor ZIP,
which silently truncated the four long-history factors to 1963-07 —
fixed 2026-06-11 by switching the four series and updating notes.

Each ZIP unpacks to a single CSV containing both a monthly block and an
annual block.  We extract the monthly block only.  Indicator definitions
live in ``data/macro_library_french.csv`` and the ``series_id`` column
encodes ``<zip_stem>|<column_name>`` (e.g. ``F-F_Research_Data_Factors|Mkt-RF``)
so one library row picks exactly one column out of one ZIP.  The
per-process ZIP cache means a single run downloads each of the two ZIPs
at most once even though six library rows reference them.

Access strategy — ZIP-direct only:
  - ``pandas-datareader``'s ``famafrench`` reader hits the same ZIP under
    the hood, so taking a direct dependency on it would just wrap our own
    requests call in another layer.  We skip the dependency and pull the
    ZIP ourselves with browser-like headers (mirrors the ifo pattern that
    already works for other anti-bot-sensitive sources).
  - The ZIP file is cached per-process: ``_resolve_zip()`` runs the HTTP
    fetch + ``zipfile.ZipFile`` open once and reuses the result for every
    column the registry asks for.

The Dartmouth host occasionally 403s bare-UA requests (and the sandbox
egress block of this repo's CI auto-allow-list returns "Host not allowed"
until ``mba.tuck.dartmouth.edu`` is added).  Per the §3.11 handoff the
allow-list now includes that host; CI IPs reach it cleanly, sandbox dev
boxes may not.  On any failure the loader logs to stdout (so
``pipeline.log`` captures it) and returns ``None`` — the dispatch layer
treats a missing column as "no rows this run", same shape as every other
source module.
"""

from __future__ import annotations

import io
import pathlib
import zipfile

import pandas as pd

from sources.base import fetch_with_backoff


_LIBRARY_CSV = pathlib.Path(__file__).parent.parent / "data" / "macro_library_french.csv"

FRENCH_BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french"
FRENCH_FTP = f"{FRENCH_BASE}/ftp"
FRENCH_LANDING = f"{FRENCH_BASE}/data_library.html"

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

_HEADERS = {
    "User-Agent":      USER_AGENT,
    "Accept":          "application/zip,application/octet-stream,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer":         FRENCH_LANDING,
}

# First 4 bytes of a real ZIP archive.
_ZIP_MAGIC = b"PK\x03\x04"


# ---------------------------------------------------------------------------
# LIBRARY LOADER
# ---------------------------------------------------------------------------

def load_library() -> list[dict]:
    """Load Ken French indicator definitions from macro_library_french.csv.

    The ``series_id`` column is a composite ``<zip_stem>|<column_name>``
    token; the fetch path splits on ``|`` so one CSV row picks one column
    out of one ZIP.
    """
    if not _LIBRARY_CSV.exists():
        return []
    df = pd.read_csv(_LIBRARY_CSV, dtype=str, keep_default_na=False)
    df["sort_key"] = pd.to_numeric(df["sort_key"], errors="coerce").fillna(0)
    df = df.sort_values("sort_key")
    result = []
    for _, row in df.iterrows():
        result.append({
            "source":       "KenFrench",
            "source_id":    row["series_id"].strip(),
            "col":          row["col"].strip(),
            "name":         row["name"].strip(),
            "country":      row.get("country", "").strip() or "USA",
            "category":     row["category"].strip(),
            "subcategory":  row["subcategory"].strip(),
            "concept":      row.get("concept", "").strip(),
            "cycle_timing": row.get("cycle_timing", "").strip(),
            "units":        row["units"].strip(),
            "frequency":    row["frequency"].strip(),
            "notes":        row.get("notes", "").strip(),
            "sort_key":     float(row["sort_key"]),
            "series_id":    row["series_id"].strip(),
        })
    return result


# ---------------------------------------------------------------------------
# ZIP RESOLUTION + PER-PROCESS CACHE
# ---------------------------------------------------------------------------

# Cache keyed by zip_stem so we never download the same archive twice in
# one process.  Failures are cached as exception instances so a hung /
# blocked host isn't re-attempted within the same run (same pattern as
# sources/ifo.py::_RESOLVE_CACHE / _RESOLVE_ERROR).
_ZIP_CACHE: dict[str, bytes] = {}
_ZIP_ERROR: dict[str, Exception] = {}


def _zip_url(zip_stem: str) -> str:
    """Construct the canonical ZIP URL on the Dartmouth FTP path."""
    return f"{FRENCH_FTP}/{zip_stem}_CSV.zip"


def _resolve_zip(zip_stem: str, retries: int = 3, timeout: int = 30) -> bytes | None:
    """Download (and cache) one Ken French ZIP by its stem.

    Returns the raw ZIP bytes on success or ``None`` if every attempt
    fails.  Failure is logged to stdout for pipeline.log capture.
    """
    if zip_stem in _ZIP_CACHE:
        return _ZIP_CACHE[zip_stem]
    if zip_stem in _ZIP_ERROR:
        # Already tried and failed this process — don't hammer the host.
        return None

    url = _zip_url(zip_stem)

    # §2.C C3 (2026-07-09): shared retry engine — retry_errors=True keeps the
    # old retry-on-connection-error posture toward the Dartmouth host; the
    # validate hook keeps the ZIP magic-byte sniff. The per-process
    # _ZIP_CACHE / _ZIP_ERROR memo (don't re-hammer a dead host within one
    # run) stays here — it's a caching concern, not a retry concern.
    def _reject(body: bytes) -> str | None:
        if not body.startswith(_ZIP_MAGIC):
            head = body[:80].replace(b"\n", b" ")
            return f"non-ZIP body len={len(body)} first 80={head!r}"
        return None

    body = fetch_with_backoff(
        url, label="KenFrench", accept="bytes",
        retries=retries, timeout=timeout, headers=_HEADERS,
        context=zip_stem, validate=_reject, retry_errors=True,
    )
    if body is not None:
        _ZIP_CACHE[zip_stem] = body
        print(f"    [KenFrench] resolved {url} ({len(body)} bytes)", flush=True)
        return body
    _ZIP_ERROR[zip_stem] = RuntimeError("fetch failed (see log above)")
    return None


# ---------------------------------------------------------------------------
# CSV PARSER (the monthly block inside the ZIP)
# ---------------------------------------------------------------------------

def _read_zip_member(zip_bytes: bytes, zip_stem: str) -> str | None:
    """Open the ZIP and read the single CSV member inside.

    Ken French ZIPs contain exactly one CSV named ``<zip_stem>.csv`` (or
    a near-match — capitalisation is consistent but we tolerate it).
    Returns the CSV body as text, or None on a parse miss.
    """
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile as e:
        print(f"    [KenFrench] {zip_stem}: bad ZIP — {e}", flush=True)
        return None
    names = zf.namelist()
    if not names:
        print(f"    [KenFrench] {zip_stem}: ZIP empty", flush=True)
        return None
    # Prefer exact stem match; otherwise take the first .csv member.
    member = None
    target = zip_stem.lower()
    for n in names:
        if n.lower().rstrip(".csv") == target:
            member = n
            break
    if member is None:
        for n in names:
            if n.lower().endswith(".csv"):
                member = n
                break
    if member is None:
        print(f"    [KenFrench] {zip_stem}: no CSV member found in {names}", flush=True)
        return None
    try:
        return zf.read(member).decode("latin-1")
    except (KeyError, UnicodeDecodeError) as e:
        print(f"    [KenFrench] {zip_stem}: read({member!r}) failed — {e}", flush=True)
        return None


def _parse_monthly_block(csv_text: str, zip_stem: str) -> pd.DataFrame | None:
    """Extract the monthly section from a Ken French data-library CSV.

    Every Ken French file follows the same multi-section shape:
      - A multi-line prose preamble (research disclaimer, dataset name,
        copyright) — variable number of lines, no comma structure.
      - One or more **data sections**, each separated from the next by one
        or more blank lines.  Each section starts with a header row that
        has an empty first field followed by the factor column names
        (e.g. ``,Mkt-RF,SMB,HML,RMW,CMA,RF``).  Data rows follow with a
        date key in the first field.
      - The first data section uses ``YYYYMM`` (6 digits) keys = monthly.
      - Subsequent sections use ``YYYY`` (4 digits) keys = annual (with
        sub-flavours for Jan-Dec vs Jul-Jun calendars).

    We split the file on blank lines into sections, then pick the first
    section whose first data row's first field is exactly 6 digits — that
    is the monthly block by construction.

    Returns a DataFrame indexed by month-end ``Timestamp`` with float
    columns, or ``None`` if no monthly section is found.
    """
    lines = csv_text.splitlines()

    # Group consecutive non-blank lines into sections.  A "blank line"
    # here means a line whose stripped form is empty OR whose every comma-
    # separated field is empty (sometimes Ken French emits ", , , ," gap
    # lines instead of a pure newline).
    sections: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if not line.strip() or all(not p.strip() for p in line.split(",")):
            if current:
                sections.append(current)
                current = []
            continue
        current.append(line)
    if current:
        sections.append(current)

    # Find the first section whose first data row (the line after the
    # header) carries a 6-digit YYYYMM key.  That is the monthly block.
    monthly_section: list[str] | None = None
    for section in sections:
        if len(section) < 2:
            continue
        # The header is the first line of the section whose first field is
        # empty (i.e. ",Col1,Col2,...") — but we tolerate the rare case
        # where the date column carries a label like "Date".  We locate
        # the first data row by scanning forward for a line whose first
        # comma-separated field is all digits.
        first_data_field: str | None = None
        for line in section[1:]:
            head = line.split(",", 1)[0].strip()
            if head and head.isdigit():
                first_data_field = head
                break
        if first_data_field is None:
            continue
        if len(first_data_field) == 6:
            monthly_section = section
            break

    if monthly_section is None:
        print(f"    [KenFrench] {zip_stem}: no monthly section located "
              f"(scanned {len(sections)} sections)", flush=True)
        return None

    header_parts = [p.strip() for p in monthly_section[0].split(",")]
    # First column is the YYYYMM date column (usually empty header); the
    # remaining are factor columns.  Drop the leading date-column slot.
    col_names = [c for c in header_parts[1:] if c]
    if not col_names:
        print(f"    [KenFrench] {zip_stem}: monthly header has no factor "
              f"columns: {header_parts!r}", flush=True)
        return None

    rows: list[tuple[pd.Timestamp, list[float]]] = []
    for line in monthly_section[1:]:
        parts = [p.strip() for p in line.split(",")]
        if not parts or not parts[0]:
            continue
        head = parts[0]
        if not (len(head) == 6 and head.isdigit()):
            # Stray non-monthly row inside the monthly section — skip.
            # (Defensive; in practice the section is homogeneous.)
            continue
        try:
            year = int(head[:4])
            month = int(head[4:])
            if not (1 <= month <= 12):
                continue
            ts = pd.Timestamp(year=year, month=month, day=1) + pd.offsets.MonthEnd(0)
        except (ValueError, TypeError):
            continue
        vals: list[float] = []
        for p in parts[1:1 + len(col_names)]:
            try:
                vals.append(float(p))
            except (ValueError, TypeError):
                vals.append(float("nan"))
        # Pad if the row is short (rare but defensive).
        while len(vals) < len(col_names):
            vals.append(float("nan"))
        rows.append((ts, vals))

    if not rows:
        print(f"    [KenFrench] {zip_stem}: monthly section parsed 0 rows", flush=True)
        return None

    idx = [r[0] for r in rows]
    data = [r[1] for r in rows]
    df = pd.DataFrame(data, index=pd.DatetimeIndex(idx), columns=col_names)
    # Ken French uses -99.99 / -999 as missing sentinels on some files.
    df = df.replace([-99.99, -999.0], float("nan"))
    return df


# Cached per-(zip_stem) parsed DataFrame so multiple columns from the
# same ZIP share one parse.
_FRAME_CACHE: dict[str, pd.DataFrame] = {}


def _resolve_frame(zip_stem: str) -> pd.DataFrame | None:
    """Download + parse the ZIP for ``zip_stem`` and cache the DataFrame."""
    if zip_stem in _FRAME_CACHE:
        return _FRAME_CACHE[zip_stem]
    zip_bytes = _resolve_zip(zip_stem)
    if zip_bytes is None:
        return None
    csv_text = _read_zip_member(zip_bytes, zip_stem)
    if csv_text is None:
        return None
    df = _parse_monthly_block(csv_text, zip_stem)
    if df is None:
        return None
    _FRAME_CACHE[zip_stem] = df
    return df


# ---------------------------------------------------------------------------
# SERIES FETCH
# ---------------------------------------------------------------------------

def fetch_series_as_pandas(
    series_id: str,
    col_name: str | None = None,
) -> pd.Series | None:
    """Fetch one Ken French monthly series.

    ``series_id`` is the composite ``<zip_stem>|<column_name>`` token, e.g.
    ``F-F_Research_Data_5_Factors_2x3|Mkt-RF``.  The function splits on
    ``|``, downloads (+ caches) the named ZIP, parses its monthly block,
    and returns the named column as a month-end-indexed ``pd.Series``.

    Returns ``None`` on any failure — graceful no-op so a Dartmouth blip
    can't sink the pipeline run.
    """
    if not series_id or "|" not in series_id:
        print(f"    [KenFrench] bad series_id {series_id!r} — expected "
              f"'<zip_stem>|<column>'", flush=True)
        return None
    zip_stem, _, column = series_id.partition("|")
    zip_stem = zip_stem.strip()
    column = column.strip()
    if not zip_stem or not column:
        print(f"    [KenFrench] empty stem or column in {series_id!r}", flush=True)
        return None

    df = _resolve_frame(zip_stem)
    if df is None:
        return None

    if column not in df.columns:
        # Whitespace / case tolerance — Ken French headers usually have
        # padding spaces in the raw CSV but we already strip() during parse.
        # Try case-insensitive match as a last resort.
        lower = {c.lower(): c for c in df.columns}
        actual = lower.get(column.lower())
        if actual is None:
            print(f"    [KenFrench] {zip_stem}: column {column!r} not in "
                  f"{list(df.columns)}", flush=True)
            return None
        column = actual

    s = df[column].dropna()
    if s.empty:
        print(f"    [KenFrench] {zip_stem}|{column}: 0 non-NaN observations", flush=True)
        return None
    s.name = col_name or series_id
    return s.sort_index()
