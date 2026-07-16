"""
sources package
===============
Per-source data providers for the macro-data pipeline.  Each submodule exposes
a small, consistent interface (library loader + snapshot fetcher + history
fetcher) with no CSV or Sheets side effects — those live in the root-level
coordinator scripts (fetch_macro_*.py).

The `base` submodule provides shared plumbing used by both source modules and
coordinators.

SOURCE_REGISTRY (§2.C C2, 2026-07-09) is the single table tying together a
source's three identities:

  * label  — the display string each ``load_library()`` emits as
             ``indic["source"]`` and the hist metadata carries in its Source
             row (e.g. ``"DB.nomics"``, ``"Banque de France"``);
  * stem   — the ``data/macro_library_<stem>.csv`` filename stem;
  * module — the importable submodule name under ``sources/``.

Before C2 these mappings were duplicated (and drifting) across
``fetch_macro_economic._FILE_SOURCE``, ``data_audit.SOURCE_BY_LIBRARY``,
``build_source_inventory.FILE_SOURCE`` and ``library_sync.MACRO_LIBS`` — all
four now derive from this table.  Registering a new source =  one
``SourceSpec`` here + a handler entry in
``fetch_macro_economic._SOURCE_HANDLERS`` (the coordinator hard-fails at
startup on any library row whose label has no handler — no more silent
"[WARN] Unknown source" skips).

``sec_edgar`` (equity fundamentals, different schema, isolated phase) and
``countries`` (code registry, not a source) are deliberately absent.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceSpec:
    label: str    # display label emitted by load_library() → indic["source"]
    stem: str     # data/macro_library_<stem>.csv
    module: str   # submodule name under sources/


SOURCE_REGISTRY: tuple[SourceSpec, ...] = (
    SourceSpec("FRED",             "fred",           "fred"),
    SourceSpec("OECD",             "oecd",           "oecd"),
    SourceSpec("World Bank",       "worldbank",      "worldbank"),
    SourceSpec("IMF",              "imf",            "imf"),
    SourceSpec("DB.nomics",        "dbnomics",       "dbnomics"),
    SourceSpec("ifo",              "ifo",            "ifo"),
    SourceSpec("BoE",              "boe",            "boe"),
    SourceSpec("Treasury",         "treasury",       "treasury"),
    SourceSpec("ECB",              "ecb",            "ecb"),
    SourceSpec("BoJ",              "boj",            "boj"),
    SourceSpec("e-Stat",           "estat",          "estat"),
    SourceSpec("Nasdaq Data Link", "nasdaqdl",       "nasdaq_data_link"),
    SourceSpec("LBMA",             "lbma",           "lbma"),
    SourceSpec("BoC",              "boc",            "boc"),
    SourceSpec("StatCan",          "statcan",        "statcan"),
    SourceSpec("ONS",              "ons",            "ons"),
    SourceSpec("Bundesbank",       "bundesbank",     "bundesbank"),
    SourceSpec("ABS",              "abs",            "abs"),
    SourceSpec("ISTAT",            "istat",          "istat"),
    SourceSpec("BLS",              "bls",            "bls"),
    SourceSpec("INSEE",            "insee",          "insee"),
    SourceSpec("Banque de France", "bdf",            "bdf"),
    SourceSpec("Eurostat",         "eurostat",       "eurostat"),
    SourceSpec("Alpha Vantage",    "alpha_vantage",  "alpha_vantage"),
    SourceSpec("Shiller",          "shiller",        "shiller"),
    SourceSpec("KenFrench",        "french",         "french"),
    SourceSpec("JST",              "jst",            "jst"),
    SourceSpec("AtlantaFed",       "atlanta_fed",    "atlanta_fed"),
    SourceSpec("NYFed",            "ny_fed",         "ny_fed"),
    SourceSpec("IMF SDMX",         "imf_sdmx",       "imf_sdmx"),
    SourceSpec("BoE Survey",       "boe_survey",     "boe_survey"),
    SourceSpec("ONS RTI",          "ons_rti",        "ons_rti"),
    SourceSpec("ONS Housing",      "ons_housing",    "ons_housing"),
)

LABEL_BY_STEM: dict[str, str] = {s.stem: s.label for s in SOURCE_REGISTRY}
STEM_BY_LABEL: dict[str, str] = {s.label: s.stem for s in SOURCE_REGISTRY}

# The three aggregators whose single library row fans out into one column per
# country (col = f"{country}_{col}") — everything else is single-column.
FANOUT_LABELS: frozenset = frozenset({"OECD", "World Bank", "IMF"})
