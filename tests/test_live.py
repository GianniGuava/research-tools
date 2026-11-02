"""Live checks against the real SearXNG server and APIs.

Skipped unless RT_LIVE=1, because they need the network and the running container:

    RT_LIVE=1 python3 -m unittest tests.test_live -v
"""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WEBSEARCH = REPO / "bin" / "websearch"
LOCAL_URL = "http://127.0.0.1:8888"

live = unittest.skipUnless(os.environ.get("RT_LIVE") == "1", "live check; set RT_LIVE=1")


def run(*args, timeout=120):
    return subprocess.run([sys.executable, str(WEBSEARCH), *args], capture_output=True, text=True, timeout=timeout)


@live
class Check1Results(unittest.TestCase):
    """Done check 1: at least 10 results from at least 2 different engines."""

    def test_general_query_returns_ten_results_from_two_engines(self):
        p = run("--json", "--url", LOCAL_URL, "python asyncio tutorial")
        self.assertEqual(p.returncode, 0, p.stderr)
        results = json.loads(p.stdout)["results"]
        engines = {e for r in results for e in (r.get("engines") or [])}
        print(f"\n  check 1: {len(results)} results, engines {sorted(engines)}", file=sys.stderr)
        self.assertGreaterEqual(len(results), 10)
        self.assertGreaterEqual(len(engines), 2)


if __name__ == "__main__":
    unittest.main()
