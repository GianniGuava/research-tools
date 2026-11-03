"""Done check 6: comparing two result lists (which links both found, which only one found)."""
import json
import subprocess
import sys
import time
import unittest

from helpers import FAKE, TempState, free_port, load_websearch

ws = load_websearch()


class Tidy(unittest.TestCase):
    """Links that differ only trivially count as the same; different pages do not."""

    def same(self, a, b):
        self.assertEqual(ws.norm_url(a), ws.norm_url(b), f"{a} vs {b}")

    def test_trivial_differences_ignored(self):
        self.same("http://example.org/a", "https://example.org/a")
        self.same("https://www.example.org/a", "https://example.org/a")
        self.same("https://example.org/a/", "https://example.org/a")
        self.same("https://example.org/", "https://example.org")
        self.same("https://example.org/a#section-2", "https://example.org/a")
        self.same("https://example.org/a?utm_source=x&utm_medium=y", "https://example.org/a")
        self.same("https://example.org/a?srsltid=abc&gclid=1&fbclid=2", "https://example.org/a")
        self.same("https://EXAMPLE.org/a", "https://example.org/a")
        self.same("https://example.org:443/a", "https://example.org/a")
        self.same("https://example.org/a?b=2&a=1", "https://example.org/a?a=1&b=2")
        self.same("https://example.org/caf%C3%A9", "https://example.org/café")

    def test_different_pages_on_one_site_differ(self):
        n = ws.norm_url
        self.assertNotEqual(n("https://example.org/a"), n("https://example.org/b"))
        self.assertNotEqual(n("https://example.org/a?id=1"), n("https://example.org/a?id=2"))
        self.assertNotEqual(n("https://example.org/A"), n("https://example.org/a"))
        self.assertNotEqual(n("https://docs.example.org/a"), n("https://example.org/a"))


class Compare(unittest.TestCase):
    A = ["https://a.org/1", "https://b.org/2", "http://www.c.org/3/", "https://d.org/4"]
    B = ["https://c.org/3", "https://e.org/5", "https://a.org/1#top", "https://f.org/6", "https://a.org/1"]

    def test_shared_and_unique_links(self):
        c = ws.compare_lists(self.A, self.B)
        self.assertEqual(c["both"], ["https://a.org/1", "http://www.c.org/3/"])
        self.assertEqual(c["only_a"], ["https://b.org/2", "https://d.org/4"])
        self.assertEqual(c["only_b"], ["https://e.org/5", "https://f.org/6"])
        self.assertEqual((c["n_a"], c["n_b"]), (4, 4))  # B's repeat of a.org/1 counted once
        self.assertAlmostEqual(c["overlap"], 2 / 6)
        self.assertEqual(c["top10_shared"], 2)

    def test_identical_and_disjoint(self):
        self.assertAlmostEqual(ws.compare_lists(self.A, list(self.A))["rbo"], 1.0)
        self.assertAlmostEqual(ws.compare_lists(self.A, list(self.A))["overlap"], 1.0)
        c = ws.compare_lists(["https://x.org/"], ["https://y.org/"])
        self.assertEqual((c["overlap"], c["rbo"]), (0.0, 0.0))

    def test_rbo_hand_worked_values(self):
        # Even lists, Webber et al. eq. 23: [a,b] vs [b,a], p=0.9 -> 0.81 + (0.1/0.9) * 0.81 = 0.9
        self.assertAlmostEqual(ws.rbo_ext(["a", "b"], ["b", "a"]), 0.9)
        # Uneven lists, eq. 32: a list that is the start of the other extrapolates to identical
        self.assertAlmostEqual(ws.rbo_ext(["a"], ["a", "b"]), 1.0)
        self.assertAlmostEqual(ws.rbo_ext(["a", "b"], ["a"]), 1.0)
        self.assertAlmostEqual(ws.rbo_ext(["x"], ["a", "b"]), 0.0)

    def test_top_ranks_weigh_more(self):
        base = [f"u{i}" for i in range(20)]
        swap_top = [base[1], base[0]] + base[2:]
        swap_bottom = base[:18] + [base[19], base[18]]
        self.assertLess(ws.rbo_ext(base, swap_top), ws.rbo_ext(base, swap_bottom))

    def test_empty_lists(self):
        self.assertIsNone(ws.compare_lists([], [])["rbo"])
        self.assertEqual(ws.compare_lists(self.A, [])["rbo"], 0.0)


class CompareCommand(unittest.TestCase):
    def setUp(self):
        self.t = TempState()
        self.a = self.t.path("builtin.txt")
        self.a.write_text("https://example1.org/page/1\n\nhttps://only-here.org/x\n")
        self.b = self.t.path("searx.json")
        self.b.write_text(json.dumps({"results": [{"url": "http://www.example1.org/page/1/"},
                                                  {"url": "https://example2.org/page/2"}]}))

    def test_text_output_lists_each_group(self):
        p = self.t.run("compare", str(self.a), str(self.b), "--labels", "built-in,searxng")
        self.assertEqual(p.returncode, 0, p.stderr)
        out = p.stdout
        self.assertIn("in both: 1", out)
        self.assertIn("only built-in: 1", out)
        self.assertIn("only searxng: 1", out)
        both = out.split("## in both")[1].split("##")[0]
        self.assertIn("example1.org/page/1", both)
        self.assertIn("only-here.org/x", out.split("## only in built-in")[1].split("##")[0])
        self.assertIn("example2.org/page/2", out.split("## only in searxng")[1])

    def test_json_output_and_list_of_objects(self):
        self.a.write_text(json.dumps([{"title": "t", "url": "https://example1.org/page/1"}]))
        p = self.t.run("compare", str(self.a), str(self.b), "--json")
        self.assertEqual(p.returncode, 0, p.stderr)
        c = json.loads(p.stdout)
        self.assertEqual(len(c["both"]), 1)
        self.assertEqual(c["only_b"], ["https://example2.org/page/2"])

    def test_against_a_fresh_searxng_search(self):
        port = free_port()
        server = subprocess.Popen([sys.executable, str(FAKE), str(port)])
        self.addCleanup(server.wait)
        self.addCleanup(server.terminate)
        time.sleep(0.4)
        p = self.t.run("compare", str(self.a), "--query", "test", SEARXNG_URL=f"http://127.0.0.1:{port}",
                       WEBSEARCH_START_CMD="false")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("in both: 1", p.stdout)  # fake server's Result 1 is example1.org/page/1
        self.assertIn("only searxng: 11", p.stdout)

    def test_unreadable_input_one_line(self):
        p = self.t.run("compare", str(self.t.path("missing.txt")), str(self.b))
        self.assertNotEqual(p.returncode, 0)
        self.assertEqual(len(p.stderr.strip().splitlines()), 1, p.stderr)


if __name__ == "__main__":
    unittest.main()
