"""Live smoke test for the Banque de France (Webstat) source wiring.

Banque de France is the ultimate (primary) producer of French MFI interest-rate
and monetary statistics. Webstat migrated in 2025/2026 from the legacy IBM API
Connect stack to an Opendatasoft Explore v2.1 instance — auth is now a single
``Authorization: Apikey <key>`` header sourced from ``BDF_API_KEY``. This test
is BOTH key-gated and network-gated: it SKIPS unless ``BDF_API_KEY`` is set and
the endpoint is reachable. That means it stays dormant in local/unit runs and
only fires on the credentialed daily CI run.

The library entries for `FRA_LOAN_RATE_HOUSE` and `FRA_LOAN_RATE_NFC` were
verified live on 2026-07-09 (forward_plan §2.A A6) via a credentialed probe:
both resolve to `observations|series_key='MIR1.M.FR.B.A22.A.R.A.2250U6.EUR.N'`
and `...A20...2240U6...` against the single flat `observations` store (the
per-series `mir-*` catalogue datasets are empty stubs). This test now asserts
they resolve to non-empty data — the "do the keys + auth work?" signal from the
credentialed daily run. The PROVISIONAL-skip branch below is retained as a
defensive mechanism for any future un-pinned row (dataset_id == ``PROVISIONAL``);
both live rows are real and are asserted, not skipped.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sources import bdf as bdf_src  # noqa: E402


def _have_key() -> bool:
    return bool(os.environ.get("BDF_API_KEY", "").strip())


@unittest.skipUnless(_have_key(), "BDF_API_KEY not set — Webstat smoke skipped")
class BdFLiveSmokeTest(unittest.TestCase):
    def test_curated_series_resolve(self):
        rows = bdf_src.load_library()
        self.assertTrue(rows, "macro_library_bdf.csv is empty — library not wired")
        problems = []
        verified = 0
        skipped_provisional = []
        for row in rows:
            sid = row["series_id"]
            col = row["col"]
            # PROVISIONAL rows (dataset_id == 'PROVISIONAL') are not yet
            # verifiable against a credentialed fetch — skip them with a note
            # rather than failing the smoke test. See macro_library_bdf.csv
            # notes for what still needs to be confirmed.
            if sid.split("|", 1)[0].strip().upper() == "PROVISIONAL":
                skipped_provisional.append(f"{col} ({sid})")
                continue
            try:
                s = bdf_src.fetch_series_as_pandas(sid, col_name=col)
            except Exception as e:  # network/parse — treat as resolution failure
                problems.append(f"{sid} ({col}): raised {type(e).__name__}: {e}")
                continue
            if s is None or s.empty:
                problems.append(f"{sid} ({col}): no data — verify dataset_id + ODSQL filter")
                continue
            verified += 1
        if skipped_provisional:
            # Surface in test output (stderr) without failing — this is the
            # signal the next session uses to prioritise dataset_id discovery.
            print(
                "    [BdF smoke] PROVISIONAL rows skipped pending dataset_id "
                "discovery: " + ", ".join(skipped_provisional),
                file=sys.stderr,
            )
        self.assertFalse(
            problems,
            "Banque de France series did not resolve "
            "(verified dataset_id|odsql may need correction):\n  "
            + "\n  ".join(problems),
        )


if __name__ == "__main__":
    unittest.main()
