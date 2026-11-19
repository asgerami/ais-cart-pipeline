#!/usr/bin/env python3
"""Run AI's Cart locally: python3 server.py, then open http://localhost:8000

Environment: MODEL_API_KEY (live) or MOCK=1 (sample answers), optional SERVICE_TOKEN, PORT (default 8000).
"""
import os
import json
import subprocess
from urllib.parse import parse_qs,urlparse
from aiscart.pilot import handle as pilot_handle
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from aiscart.web import handle

ROOT = Path(__file__).resolve().parent
STATIC = {"/": ROOT / "index.html", **{"/"+p: ROOT/p for p in ("pilot.html","pilot.js","pilot.css")}}
STATIC.update({f"/eval/samples/{p.name}": p for p in (ROOT / "eval" / "samples").glob("*.png")})
TYPES = {".html": "text/html; charset=utf-8", ".png": "image/png", ".js":"text/javascript; charset=utf-8", ".css":"text/css; charset=utf-8"}


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
        if n > 4400000:
            return self._send(413, {"Content-Type": "application/json"}, b'{"error":{"message":"Request too large"}}')
        body = self.rfile.read(n) if n else b""
        if path == "/api/pilot":
            action=parse_qs(urlparse(self.path).query).get("action",["status"])[0]
            return self._send(*pilot_handle(method,action,dict(self.headers),body))
        if path == "/api/recommend":
            try:
                payload = {"method": method, "body": body.decode("utf-8")}
                result = subprocess.run(["node", str(ROOT / "scripts/recommend-local.js")],
                                        input=json.dumps(payload), text=True, capture_output=True, timeout=15, check=True)
                answer = json.loads(result.stdout)
                return self._send(answer["status"], {"Content-Type": "application/json", **answer["headers"]},
                                  json.dumps(answer["body"]).encode())
            except (OSError, subprocess.SubprocessError, ValueError):
                return self._send(502, {"Content-Type": "application/json"},
                                  b'{"error":{"message":"Local recommendations need Node.js 18 or later."}}')
        self._send(*handle(method, path, dict(self.headers), body))

    def do_GET(self):
        self._run("GET")

    def do_POST(self):
        self._run("POST")

    def do_PUT(self):
        self._run("PUT")

    def do_DELETE(self):
        self._run("DELETE")

    def do_OPTIONS(self):
        self._run("OPTIONS")

    def log_message(self, fmt, *args):
        if os.environ.get("QUIET") != "1":
            super().log_message(fmt, *args)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    print(f"AI's Cart on http://localhost:{port}")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
