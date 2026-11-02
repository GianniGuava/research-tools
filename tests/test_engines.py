"""Done check 2: when an engine blocks the server, the output names it."""
import json
import subprocess
import sys
import time
import unittest

from helpers import FAKE, TempState, free_port

BLOCKED = {
    "query": "q",
    "results": [{"title": "Only one", "url": "https://example.org/", "engines": ["brave"]}],
    "unresponsive_engines": [["google", "CAPTCHA"], ["qwant", "access denied"]],
}
CLEAN = dict(BLOCKED, unresponsive_engines=[])


class FailedEngines(unittest.TestCase):
    def serve(self, reply):
        self.t = TempState()
        port = free_port()
        f = self.t.path("reply.json")
        f.write_text(json.dumps(reply))
        self.server = subprocess.Popen([sys.executable, str(FAKE), str(port), "--reply", str(f)])
        self.addCleanup(self.server.wait)
        self.addCleanup(self.server.terminate)
        self.url = f"http://127.0.0.1:{port}"
        time.sleep(0.4)

    def search(self, *args):
        return self.t.run(*args, "q", SEARXNG_URL=self.url, WEBSEARCH_START_CMD="false")

    def test_list_output_names_each_failed_engine_and_reason(self):
        self.serve(BLOCKED)
        p = self.search()
        self.assertEqual(p.returncode, 0, p.stderr)
        line = next(l for l in p.stdout.splitlines() if "failed engines" in l)
        self.assertIn("google (CAPTCHA)", line)
        self.assertIn("qwant (access denied)", line)

    def test_json_output_names_failed_engines_on_stderr(self):
        self.serve(BLOCKED)
        p = self.search("--json")
        self.assertEqual(p.returncode, 0, p.stderr)
        json.loads(p.stdout)  # stdout stays clean JSON
        self.assertIn("google (CAPTCHA)", p.stderr)
        self.assertIn("qwant (access denied)", p.stderr)

    def test_no_failures_no_line(self):
        self.serve(CLEAN)
        for args in ((), ("--json",)):
            p = self.search(*args)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertNotIn("failed engines", p.stdout + p.stderr)


if __name__ == "__main__":
    unittest.main()
