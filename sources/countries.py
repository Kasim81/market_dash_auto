"""
sources/countries.py
====================
Country metadata loader.  Loads data/macro_library_countries.csv and
exposes helpers for the three mappings that previously lived in Python:
  - code -> (name, region)            [was COUNTRY_META]
  - wb_code -> code                   [was WB_CODE_MAP]
  - imf_code -> code                  [was IMF_CODE_MAP]

Cached at import time; re-run load_countries() after editing the CSV
in a long-lived process.
"""

from __future__ import annotations

import csv
import pathlib
from functools import lru_cache

_LIBRARY_CSV = pathlib.Path(__file__).parent.parent / "data" / "macro_library_countries.csv"


@lru_cache(maxsize=1)
def load_countries() -> tuple[dict, ...]:
    """
    Return the rows of macro_library_countries.csv as a tuple of dicts.
    Cached at first call; cleared by calling load_countries.cache_clear().
    """
    with _LIBRARY_CSV.open(newline="") as f:
        return tuple(csv.DictReader(f))


@lru_cache(maxsize=1)
def country_meta() -> dict[str, tuple[str, str]]:
    """{canonical_code: (display_name, region)}."""
    return {row["code"]: (row["name"], row["region"]) for row in load_countries()}


@lru_cache(maxsize=1)
def wb_code_map() -> dict[str, str]:
    """{WB source code: canonical_code}."""
    return {row["wb_code"]: row["code"] for row in load_countries() if row["wb_code"]}


@lru_cache(maxsize=1)
def wb_countries_query_string() -> str:
    """Semicolon-joined WB codes for the /country/{codes}/indicator endpoint."""
    return ";".join(row["wb_code"] for row in load_countries() if row["wb_code"])


@lru_cache(maxsize=1)
def imf_code_map() -> dict[str, str]:
    """{IMF source code: canonical_code}."""
    return {row["imf_code"]: row["code"] for row in load_countries() if row["imf_code"]}
