"""Done check 5: Semantic Scholar key from a private file, never printed, requests spaced and capped.

A fake Semantic Scholar server runs inside the test (S2_API_URL points the tool at it), and the
key is a made-up one. Checks that the key is absent from output compare inside the program and
report only pass or fail, never the text.
"""
import http.server
import json
import subprocess
import sys
import threading
import time
import unittest
from datetime import datetime, timezone

from helpers import WEBSEARCH, TempState

FAKE_KEY = "fake-key-0123456789abcdef0123456789abcdef"


class FakeS2:
    """Records each request's arrival time and x-api-key header; answers with a set status and body."""

    def __init__(self, status=200, body=None, refusals=0):
        """Answers with `status`, except that the first `refusals` requests get a 429."""
        self.hits = []
        fake = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                fake.hits.append((time.time(), self.headers.get("x-api-key")))
                code = 429 if len(fake.hits) <= refusals else status
                reply = {"message": "Too Many Requests"} if code == 429 else body
                data = json.dumps(reply if reply is not None else {"total": 0, "data": []}).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/graph/v1"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class Scholar(unittest.TestCase):
    def setUp(self):
        self.t = TempState()
        self.keydir = self.t.dir / "config" / "research-tools"
        self.keydir.mkdir(parents=True)
        self.statefile = self.t.dir / "state" / "research-tools" / "s2_requests.json"

    def fake(self, **kw):
        f = FakeS2(**kw)
        self.addCleanup(f.close)
        return f

    def write_key(self, text=FAKE_KEY + "\n"):
        (self.keydir / "s2_api_key").write_text(text)

    def scholar(self, url, *args, timeout=60):
        return self.t.run("scholar", *args, "test query", timeout=timeout, S2_API_URL=url, S2_RETRY_BASE="0.1")

    def assertKeyNotShown(self, p):
        self.assertFalse(FAKE_KEY in p.stdout or FAKE_KEY in p.stderr, "the key appeared in the output")

    def test_key_read_from_file_trimmed_and_sent_as_header(self):
        self.write_key("  " + FAKE_KEY + " \n")
        s2 = self.fake()
        p = self.scholar(s2.url)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(len(s2.hits), 1)
        self.assertTrue(s2.hits[0][1] == FAKE_KEY, "x-api-key header differs from the trimmed key")
        self.assertKeyNotShown(p)

    def test_missing_key_file_one_line_and_search_without_key(self):
        s2 = self.fake()
        p = self.scholar(s2.url)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(len(p.stderr.strip().splitlines()), 1, p.stderr)
        self.assertIn("without a key", p.stderr)
        self.assertIsNone(s2.hits[0][1])

    def test_key_with_a_second_line_is_not_used_and_not_shown(self):
        self.write_key(FAKE_KEY + "\nnotes from the phone\n")
        s2 = self.fake()
        p = self.scholar(s2.url)
        self.assertEqual(p.returncode, 0, "search without the key should still run")
        self.assertEqual(len(p.stderr.strip().splitlines()), 1)
        self.assertIn("not used", p.stderr)
        self.assertIsNone(s2.hits[0][1])
        self.assertKeyNotShown(p)

    def test_future_timestamp_does_not_stall(self):
        self.write_key()
        s2 = self.fake()
        self.statefile.parent.mkdir(parents=True)
        self.statefile.write_text(json.dumps({"day": "2000-01-01", "count": 0, "recent": [time.time() + 1000]}))
        start = time.monotonic()
        p = self.scholar(s2.url)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertLess(time.monotonic() - start, 5)

    def test_refused_key_error_does_not_show_key(self):
        self.write_key()
        s2 = self.fake(status=403, body={"message": f"Forbidden for key {FAKE_KEY}"})
        p = self.scholar(s2.url)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("403", p.stderr)
        self.assertKeyNotShown(p)

    def test_network_failure_does_not_show_key(self):
        self.write_key()
        p = self.scholar("http://127.0.0.1:9/graph/v1")
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("cannot reach", p.stderr)
        self.assertKeyNotShown(p)

    def test_two_processes_at_once_are_spaced(self):
        self.write_key()
        s2 = self.fake()
        cmd = [sys.executable, str(WEBSEARCH), "scholar", "test query"]
        env = dict(self.t.env, S2_API_URL=s2.url)
        procs = [subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) for _ in range(3)]
        for pr in procs:
            self.assertEqual(pr.wait(timeout=30), 0)
        times = sorted(t for t, _ in s2.hits)
        self.assertEqual(len(times), 3)
        gaps = [b - a for a, b in zip(times, times[1:])]
        self.assertTrue(all(g >= 1.09 for g in gaps), f"gaps {gaps}")

    def test_daily_cap_refuses_without_sending(self):
        self.write_key()
        s2 = self.fake()
        self.statefile.parent.mkdir(parents=True)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.statefile.write_text(json.dumps({"day": today, "count": 200, "recent": []}))
        p = self.scholar(s2.url)
        self.assertNotEqual(p.returncode, 0)
        self.assertEqual(len(p.stderr.strip().splitlines()), 1, p.stderr)
        self.assertIn("200", p.stderr)
        self.assertEqual(s2.hits, [])

    def test_count_resets_on_a_new_day(self):
        self.write_key()
        s2 = self.fake()
        self.statefile.parent.mkdir(parents=True)
        self.statefile.write_text(json.dumps({"day": "2000-01-01", "count": 200, "recent": []}))
        p = self.scholar(s2.url)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(self.statefile.read_text())["count"], 1)

    def test_rate_limit_gives_up_after_five_retries_in_one_line(self):
        self.write_key()
        s2 = self.fake(refusals=99)
        p = self.scholar(s2.url, timeout=90)
        self.assertNotEqual(p.returncode, 0)
        self.assertEqual(len(s2.hits), 6)
        self.assertEqual(json.loads(self.statefile.read_text())["count"], 6)
        times = [t for t, _ in s2.hits]
        self.assertTrue(all(b - a >= 1.09 for a, b in zip(times, times[1:])))
        self.assertEqual(len(p.stderr.strip().splitlines()), 1, p.stderr)
        self.assertKeyNotShown(p)

    def test_refused_then_answered_succeeds_with_one_summary_line(self):
        self.write_key()
        s2 = self.fake(refusals=2)
        p = self.scholar(s2.url, timeout=90)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(len(s2.hits), 3)
        lines = p.stderr.strip().splitlines()
        self.assertEqual(len(lines), 1, p.stderr)
        self.assertIn("refused 2", lines[0])
        self.assertIn("# Semantic Scholar", p.stdout)


if __name__ == "__main__":
    unittest.main()
