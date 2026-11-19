"""Vercel pilot API, separate from the existing service-token API."""
import sys
from pathlib import Path
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs,urlparse
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from aiscart.pilot import handle
class handler(BaseHTTPRequestHandler):
    def _run(self,method):
        n=int(self.headers.get('Content-Length') or 0)
        if n>4400000:
            self.send_response(413);self.end_headers();return
        action=parse_qs(urlparse(self.path).query).get('action',['status'])[0]
        status,headers,body=handle(method,action,dict(self.headers),self.rfile.read(n) if n else b'')
        self.send_response(status)
        for key,value in headers.items():self.send_header(key,value)
        self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def do_GET(self):self._run('GET')
    def do_POST(self):self._run('POST')
    def do_PUT(self):self._run('PUT')
    def do_DELETE(self):self._run('DELETE')
