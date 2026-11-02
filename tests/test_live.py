"""Live checks against the real SearXNG server and APIs.

Skipped unless RT_LIVE=1, because they need the network and the running container:

    RT_LIVE=1 python3 -m unittest tests.test_live -v
"""
import json
import os
import subprocess
import sys
import time
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


def docker(*args):
    sys.path.insert(0, str(REPO / "tests"))
    from helpers import load_websearch
    return subprocess.run(load_websearch().docker_cmd(list(args)), capture_output=True, text=True, timeout=120)


def search_until_results(limit=60):
    """Search until results come back. Returns (seconds taken, outputs seen on the way)."""
    start, seen = time.monotonic(), []
    while time.monotonic() - start < limit:
        p = run("--url", LOCAL_URL, "-n", "3", "debian release notes")
        seen.append((p.returncode, (p.stdout + p.stderr).strip().splitlines()[:1]))
        if p.returncode == 0:
            return time.monotonic() - start, seen
        time.sleep(1)
    raise AssertionError(f"no results within {limit}s: {seen}")


@live
class Check4StartsByItself(unittest.TestCase):
    """Done check 4: with the container stopped, searching brings it back with nothing else done.

    The fourth part (after Docker itself restarts, the container is running again) needs sudo,
    so it is run by hand in stage 5: `sudo systemctl restart docker`, then `websearch server status`.
    """

    def test_stopped_container_comes_back_on_search(self):
        self.assertEqual(docker("stop", "searxng").returncode, 0)
        took, seen = search_until_results()
        print(f"\n  check 4: results {took:.1f}s after the stop; outputs on the way: {seen}", file=sys.stderr)
        for rc, first in seen[:-1]:
            self.assertEqual(len(first), 1)
            self.assertIn("starting", first[0])

    def test_two_searches_together_give_one_container(self):
        self.assertEqual(docker("stop", "searxng").returncode, 0)
        procs = [subprocess.Popen([sys.executable, str(WEBSEARCH), "--url", LOCAL_URL, "q"],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) for _ in range(2)]
        for pr in procs:
            pr.wait(timeout=60)
        search_until_results()
        names = docker("ps", "-a", "--filter", "name=searxng", "--format", "{{.Names}}").stdout.split()
        self.assertEqual(names, ["searxng"])


@live
class Check5Scholar(unittest.TestCase):
    """Done check 5 with the real key: 10 searches in a row, no rate-limit refusals, spaced 1.1 s or more.

    Uses 12 of the day's 200 requests. The key is compared inside the test and never printed.
    """

    def test_ten_searches_in_a_row(self):
        key = (Path.home() / ".config" / "research-tools" / "s2_api_key").read_text().strip()
        queries = ["rank biased overlap", "metasearch engine evaluation", "search result overlap",
                   "web search engine comparison", "query log analysis", "information retrieval evaluation",
                   "learning to rank", "search engine bias", "federated search", "result merging"]
        outputs = [run("scholar", "-n", "3", q) for q in queries]
        for q, p in zip(queries, outputs):
            self.assertEqual(p.returncode, 0, f"{q}: {p.stderr.replace(key, '[key]')}")
            self.assertNotIn("429", p.stderr)
            self.assertNotIn("without a key", p.stderr)
            self.assertFalse(key in p.stdout or key in p.stderr, "the key appeared in the output")
        state = json.loads((Path.home() / ".local" / "state" / "research-tools" / "s2_requests.json").read_text())
        times = state["recent"][-10:]
        gaps = [b - a for a, b in zip(times, times[1:])]
        print(f"\n  check 5: 10 searches ok; smallest gap {min(gaps):.2f}s; {state['count']} requests today",
              file=sys.stderr)
        self.assertTrue(all(g >= 1.1 for g in gaps), gaps)

    def test_cited_by_and_references_still_work(self):
        doi = "DOI:10.1145/1852102.1852106"  # Webber, Moffat and Zobel, rank-biased overlap
        for flag in ("--cited-by", "--references"):
            p = run("scholar", flag, doi, "-n", "3")
            self.assertEqual(p.returncode, 0, p.stderr[:300])
            self.assertIn(" 1. ", p.stdout)


if __name__ == "__main__":
    unittest.main()
