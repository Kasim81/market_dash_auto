"""Offline unit tests for sources/base.fetch_with_backoff (§2.C C3).

The helper is the single retry/backoff engine for every converted source
module, so its semantics are pinned here with mocked HTTP: the original
single-URL contract (429/5xx backoff, hard-4xx abort, JSON/text modes) and
the 2026-07-09 C3-remainder extensions (mirror-URL rotation, bytes mode,
POST via json_body, the `context` log shape data_audit Section A scrapes,
and per-mirror content validation).

No network, no API keys — runs in the ci.yml offline gate.
"""
import contextlib
import io
import os
import sys
import unittest
from unittest import mock

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sources import base  # noqa: E402


def _resp(status=200, json_data=None, text="", content=b""):
    r = mock.Mock()
    r.status_code = status
    r.text = text
    r.content = content
    if json_data is not None:
        r.json.return_value = json_data
    else:
        r.json.side_effect = ValueError("no JSON")
    return r


class FetchBackoffTest(unittest.TestCase):
    def setUp(self):
        self.get = mock.patch.object(base.requests, "get").start()
        self.post = mock.patch.object(base.requests, "post").start()
        self.sleep = mock.patch.object(base.time, "sleep").start()
        self.addCleanup(mock.patch.stopall)

    def _call(self, *args, **kw):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            out = base.fetch_with_backoff(*args, **kw)
        return out, buf.getvalue()

    # ---- original single-URL contract ----
    def test_json_success(self):
        self.get.return_value = _resp(json_data={"ok": 1})
        out, _ = self._call("http://x", label="T")
        self.assertEqual(out, {"ok": 1})

    def test_text_mode_via_accept_csv(self):
        self.get.return_value = _resp(text="a,b\n1,2")
        out, _ = self._call("http://x", label="T", accept_csv=True)
        self.assertEqual(out, "a,b\n1,2")

    def test_5xx_backs_off_then_succeeds(self):
        self.get.side_effect = [_resp(500), _resp(json_data={"ok": 1})]
        out, log = self._call("http://x", label="T", retries=3)
        self.assertEqual(out, {"ok": 1})
        self.assertEqual(self.sleep.call_count, 1)
        self.assertIn("Backing off", log)

    def test_hard_4xx_aborts_without_retry(self):
        self.get.return_value = _resp(404)
        out, log = self._call("http://x", label="T", retries=5)
        self.assertIsNone(out)
        self.assertEqual(self.get.call_count, 1)
        self.assertIn("HTTP 404 — skipping", log)

    def test_exhausted_retries_return_none(self):
        self.get.return_value = _resp(503)
        out, log = self._call("http://x", label="T", retries=2)
        self.assertIsNone(out)
        self.assertEqual(self.get.call_count, 2)
        self.assertIn("All 2 attempts failed", log)

    def test_request_exception_aborts(self):
        self.get.side_effect = requests.exceptions.ConnectionError("boom")
        out, log = self._call("http://x", label="T")
        self.assertIsNone(out)
        self.assertIn("Request error", log)

    def test_timeout_retries(self):
        self.get.side_effect = [requests.exceptions.Timeout(),
                                _resp(json_data={"ok": 1})]
        out, _ = self._call("http://x", label="T", retries=3)
        self.assertEqual(out, {"ok": 1})

    def test_non_json_200_aborts_single_url(self):
        self.get.return_value = _resp(text="<html>")
        out, log = self._call("http://x", label="T", retries=5)
        self.assertIsNone(out)
        self.assertEqual(self.get.call_count, 1)   # a bad 200 body won't improve
        self.assertIn("non-JSON body", log)

    # ---- C3-remainder extensions ----
    def test_context_appears_in_skip_line_for_audit_scrape(self):
        # data_audit Section A regex: [FRED] HTTP <code> on <series> — skipping
        self.get.return_value = _resp(400)
        _, log = self._call("http://x", label="FRED", context="FRED/CPIAUCSL")
        self.assertIn("[FRED] HTTP 400 on FRED/CPIAUCSL — skipping", log)

    def test_bytes_mode(self):
        self.get.return_value = _resp(content=b"\x50\x4b binary")
        out, _ = self._call("http://x", label="T", accept="bytes")
        self.assertEqual(out, b"\x50\x4b binary")

    def test_post_mode_via_json_body(self):
        self.post.return_value = _resp(json_data=[{"status": "SUCCESS"}])
        out, _ = self._call("http://x", label="T", json_body=[{"vectorId": 1}])
        self.assertEqual(out, [{"status": "SUCCESS"}])
        self.post.assert_called_once()
        self.get.assert_not_called()
        self.assertEqual(self.post.call_args.kwargs["json"], [{"vectorId": 1}])

    def test_mirror_rotation_falls_through_to_second_host(self):
        self.get.side_effect = [_resp(404), _resp(json_data={"ok": 1})]
        out, log = self._call(["http://a/one", "http://b/two"], label="T")
        self.assertEqual(out, {"ok": 1})
        self.assertEqual(self.get.call_count, 2)
        self.assertIn("via one", log)              # per-mirror failure logged
        self.assertEqual(self.sleep.call_count, 0)  # no backoff needed

    def test_mirror_full_pass_failure_backs_off_then_recovers(self):
        self.get.side_effect = [_resp(500), requests.exceptions.Timeout(),
                                _resp(json_data={"ok": 1})]
        out, log = self._call(["http://a/one", "http://b/two"],
                              label="T", retries=3)
        self.assertEqual(out, {"ok": 1})
        self.assertEqual(self.sleep.call_count, 1)
        self.assertIn("mirror(s) failed", log)

    def test_mirror_exhaustion_returns_none_without_trailing_sleep(self):
        self.get.return_value = _resp(500)
        out, _ = self._call(["http://a/one", "http://b/two"],
                            label="T", retries=2)
        self.assertIsNone(out)
        self.assertEqual(self.get.call_count, 4)   # 2 mirrors × 2 attempts
        self.assertEqual(self.sleep.call_count, 1)  # between attempts only

    def test_validate_rejection_tries_next_mirror(self):
        html = _resp(text="<html>form</html>")
        csv_ok = _resp(text="Date,Value\n2026-01-01,1")
        self.get.side_effect = [html, csv_ok]
        sniff = (lambda t: "HTML form" if t.lstrip().lower().startswith("<html") else None)
        out, log = self._call(["http://a/one", "http://b/two"], label="T",
                              accept="text", validate=sniff)
        self.assertEqual(out, "Date,Value\n2026-01-01,1")
        self.assertIn("rejected", log)

    def test_validate_rejection_aborts_on_single_url(self):
        self.get.return_value = _resp(text="<html>form</html>")
        sniff = (lambda t: "HTML form" if t.lstrip().lower().startswith("<html") else None)
        out, _ = self._call("http://x", label="T", accept="text",
                            validate=sniff, retries=5)
        self.assertIsNone(out)
        self.assertEqual(self.get.call_count, 1)


if __name__ == "__main__":
    unittest.main()
