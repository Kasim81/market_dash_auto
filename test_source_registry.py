"""Offline regression tests for the single source registry (§2.C C2).

sources.SOURCE_REGISTRY is the one table tying together each source's
display label, library-CSV filename stem, and module name. The coordinator's
_SOURCE_HANDLERS dispatch and the sibling tools' mappings all derive from it
— these tests hold the pieces consistent so a new source registered in one
place is wired (or loudly rejected) everywhere.

No network, no API keys — runs in the ci.yml offline gate.
"""
import glob
import importlib
import os
import sys
import unittest

os.environ.setdefault("FRED_API_KEY", "x")
os.environ.setdefault("SHEET_ID", "x")
os.environ.setdefault("GOOGLE_CREDENTIALS_JSON", "{}")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sources  # noqa: E402
import fetch_macro_economic as fme  # noqa: E402

# Library CSVs that are deliberately not in the registry (not macro sources
# or a different schema — see sources/__init__.py docstring).
NON_SOURCE_STEMS = {"countries", "sec_edgar"}


class SourceRegistryTest(unittest.TestCase):
    def test_every_library_csv_has_a_registry_entry(self):
        stems = {
            os.path.basename(p)[len("macro_library_"):-len(".csv")]
            for p in glob.glob("data/macro_library_*.csv")
        } - NON_SOURCE_STEMS
        missing = stems - set(sources.LABEL_BY_STEM)
        self.assertFalse(
            missing,
            f"library CSV(s) with no SOURCE_REGISTRY entry: {sorted(missing)}",
        )

    def test_every_registry_module_imports(self):
        for spec in sources.SOURCE_REGISTRY:
            mod = importlib.import_module(f"sources.{spec.module}")
            if spec.module == "fred":
                # FRED keeps its historical dual loaders (US fast path +
                # intl library) instead of a single load_library().
                self.assertTrue(hasattr(mod, "load_us_library_as_list"))
                self.assertTrue(hasattr(mod, "load_intl_library"))
            else:
                self.assertTrue(hasattr(mod, "load_library"),
                                f"sources.{spec.module} lacks load_library()")

    def test_labels_and_stems_are_unique(self):
        labels = [s.label for s in sources.SOURCE_REGISTRY]
        stems = [s.stem for s in sources.SOURCE_REGISTRY]
        self.assertEqual(len(labels), len(set(labels)))
        self.assertEqual(len(stems), len(set(stems)))


class DispatchCoverageTest(unittest.TestCase):
    def test_every_loaded_indicator_has_a_handler(self):
        inds = fme.load_all_indicators()
        self.assertGreater(len(inds), 250)
        fme._validate_dispatch(inds)  # raises on any gap

    def test_every_handler_label_is_registered(self):
        # Dispatch entries must use registry labels — a handler keyed by a
        # typo'd label would silently never fire.
        registry_labels = set(sources.STEM_BY_LABEL) | {"ifo"}
        unknown = set(fme._SOURCE_HANDLERS) - registry_labels
        self.assertFalse(
            unknown,
            f"_SOURCE_HANDLERS key(s) not in SOURCE_REGISTRY: {sorted(unknown)}",
        )

    def test_unknown_label_raises(self):
        with self.assertRaises(RuntimeError):
            fme._validate_dispatch([{"source": "Typo Source", "col": "X"}])

    def test_handlers_are_snapshot_history_pairs(self):
        for label, pair in fme._SOURCE_HANDLERS.items():
            self.assertEqual(len(pair), 2, label)
            self.assertTrue(callable(pair[0]) and callable(pair[1]), label)


if __name__ == "__main__":
    unittest.main()
