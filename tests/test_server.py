"""Done checks 3 and 4: the down message within 5 seconds, and starting the server by itself.

Each test points the tool at an unused local port and replaces the Docker start command
(WEBSEARCH_START_CMD) with a stand-in, so no Docker or network is needed.
"""
import os
import shlex
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path

from helpers import FAKE, TempState, free_port, kill_pidfile, load_websearch, wait_for_file


class DownMessage(unittest.TestCase):
    """Check 3: one line within 5 seconds, naming the built-in search as the fallback."""

    def setUp(self):
        self.t = TempState()
        self.url = f"http://127.0.0.1:{free_port()}"

    def test_cannot_start_gives_one_line_naming_fallback(self):
        cmd = "sh -c 'echo Cannot connect to the Docker daemon >&2; exit 1'"
        p = self.t.run("some query", SEARXNG_URL=self.url, WEBSEARCH_START_CMD=cmd)
        self.assertNotEqual(p.returncode, 0)
        self.assertLess(p.elapsed, 5)
        self.assertEqual(p.stdout, "")
        lines = p.stderr.strip().splitlines()
        self.assertEqual(len(lines), 1, p.stderr)
        self.assertIn("built-in", lines[0])
        self.assertIn("Docker daemon", lines[0])

    def test_still_starting_after_five_seconds_leaves_start_running(self):
        pidfile = self.t.path("starter.pid")
        cmd = f"sh -c 'echo $$ > {pidfile}; exec sleep 30'"
        try:
            p = self.t.run("some query", SEARXNG_URL=self.url, WEBSEARCH_START_CMD=cmd)
            self.assertNotEqual(p.returncode, 0)
            self.assertLess(p.elapsed, 5)
            lines = p.stderr.strip().splitlines()
            self.assertEqual(len(lines), 1, p.stderr)
            self.assertIn("starting", lines[0])
            self.assertIn("built-in", lines[0])
            pid = int(wait_for_file(pidfile))
            os.kill(pid, 0)  # raises if the start command was killed when the tool exited
        finally:
            kill_pidfile(pidfile)

    def test_remote_server_is_never_started(self):
        count = self.t.path("starts")
        cmd = f"sh -c 'echo x >> {count}'"
        p = self.t.run("some query", SEARXNG_URL="http://nothing-here.invalid:8888", WEBSEARCH_START_CMD=cmd)
        self.assertNotEqual(p.returncode, 0)
        self.assertLess(p.elapsed, 5)
        self.assertEqual(len(p.stderr.strip().splitlines()), 1, p.stderr)
        self.assertIn("built-in", p.stderr)
        self.assertFalse(count.exists())


class StartsByItself(unittest.TestCase):
    """Check 4: a search with the server stopped starts it and returns results."""

    def setUp(self):
        self.t = TempState()
        self.port = free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        self.pidfile = self.t.path("server.pid")
        self.count = self.t.path("starts")
        self.cmd = (f"sh -c 'echo x >> {self.count}; exec {shlex.quote(sys.executable)} {FAKE} {self.port} "
                    f"--pidfile {self.pidfile}'")

    def tearDown(self):
        kill_pidfile(self.pidfile)

    def test_search_starts_server_and_returns_results(self):
        p = self.t.run("some query", SEARXNG_URL=self.url, WEBSEARCH_START_CMD=self.cmd)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("Result 1", p.stdout)
        self.assertEqual(self.count.read_text().count("x"), 1)

    def test_two_searches_together_start_one_server(self):
        out = []
        threads = [threading.Thread(target=lambda: out.append(
            self.t.run("q", SEARXNG_URL=self.url, WEBSEARCH_START_CMD=self.cmd))) for _ in range(2)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        for p in out:
            self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(self.count.read_text().count("x"), 1)

    def test_running_server_is_not_started_again(self):
        server = subprocess.Popen([sys.executable, str(FAKE), str(self.port)])
        try:
            time.sleep(0.5)
            p = self.t.run("q", SEARXNG_URL=self.url, WEBSEARCH_START_CMD=self.cmd)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertFalse(self.count.exists())
        finally:
            server.terminate()
            server.wait()


class DefaultAddress(unittest.TestCase):
    def test_default_server_is_this_machine(self):
        saved = os.environ.pop("SEARXNG_URL", None)
        try:
            self.assertEqual(load_websearch().DEFAULT_URL, "http://127.0.0.1:8888")
        finally:
            if saved is not None:
                os.environ["SEARXNG_URL"] = saved


if __name__ == "__main__":
    unittest.main()
