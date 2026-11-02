#!/usr/bin/env python3
"""Run AI's Cart locally: python3 server.py, then open http://localhost:8000

Environment: MODEL_API_KEY (live) or MOCK=1 (sample answers), optional SERVICE_TOKEN, PORT (default 8000).
"""
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from aiscart.web import handle

ROOT = Path(__file__).resolve().parent
STATIC = {"/": ROOT / "index.html"}
STATIC.update({f"/eval/samples/{p.name}": p for p in (ROOT / "eval" / "samples").glob("*.png")})
TYPES = {".html": "text/html; charset=utf-8", ".png": "image/png"}


class Handler(BaseHTTPRequestHandler):
    def _send(self, status, headers, body):
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _run(self, method):
        path = self.path.split("?", 1)[0]
        if method == "GET" and path in STATIC:
            f = STATIC[path]
            return self._send(200, {"Content-Type": TYPES.get(f.suffix, "application/octet-stream")}, f.read_bytes())
        n = int(self.headers.get("Content-Length") or 0)
        self._send(*handle(method, path, dict(self.headers), self.rfile.read(n) if n else b""))

    def do_GET(self):
        self._run("GET")

    def do_POST(self):
        self._run("POST")

    def do_OPTIONS(self):
        self._run("OPTIONS")

    def log_message(self, fmt, *args):
        if os.environ.get("QUIET") != "1":
            super().log_message(fmt, *args)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    print(f"AI's Cart on http://localhost:{port}")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
