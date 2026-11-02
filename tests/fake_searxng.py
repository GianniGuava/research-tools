"""A stand-in SearXNG server for the automated tests.

    python3 tests/fake_searxng.py PORT [--reply FILE] [--pidfile FILE]

Answers /healthz with OK and /search with the JSON in FILE (default: 12 results from two engines).
"""
import argparse
import http.server
import json
import os

DEFAULT_REPLY = {
    "query": "test",
    "results": [
        {"title": f"Result {i}", "url": f"https://example{i % 4}.org/page/{i}",
         "engines": ["brave", "duckduckgo"] if i % 2 else ["brave"], "content": f"snippet {i}"}
        for i in range(1, 13)
    ],
    "unresponsive_engines": [],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("port", type=int)
    ap.add_argument("--reply")
    ap.add_argument("--pidfile")
    a = ap.parse_args()
    reply = json.load(open(a.reply)) if a.reply else DEFAULT_REPLY
    body = json.dumps(reply).encode()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.startswith("/healthz"):
                data, kind = b"OK", "text/plain"
            elif self.path.startswith("/search"):
                data, kind = body, "application/json"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", a.port), Handler)
    if a.pidfile:
        with open(a.pidfile, "w") as f:
            f.write(str(os.getpid()))
    server.serve_forever()


if __name__ == "__main__":
    main()
