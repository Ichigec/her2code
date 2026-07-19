#!/usr/bin/env python3
"""Прокси :18649→Docker :18648 со стабами для Desktop GUI.
Решает зависания GUI на 24% (/api/status) и 95% (/api/sessions, /api/logs и др.).
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request, os

GATEWAY = os.environ.get('GATEWAY_URL', 'http://localhost:18648')

STUBS = {
    '/api/status': (200, b'{"status":"ok","auth_required":false}'),
    '/api/sessions': (200, b'[]'),
    '/api/agents': (200, b'[]'),
    '/api/skills': (200, b'[]'),
    '/api/cron': (200, b'[]'),
    '/api/config': (200, b'{}'),
    '/api/memory': (200, b'[]'),
    '/api/models': (200, b'[]'),
    '/api/personalities': (200, b'[]'),
    '/api/profiles': (200, b'{"profiles":[],"active":"default"}'),
    '/api/profiles/active': (200, b'{"profile":"default"}'),
    '/api/hooks': (200, b'[]'),
    '/api/logs': (200, b''),
}

class Proxy(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split('?')[0]
        if path in STUBS:
            status, data = STUBS[path]
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(data)
            return
        self._forward('GET')

    def do_POST(self):
        self._forward('POST')

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.end_headers()

    def _forward(self, method):
        try:
            body = b''
            if method == 'POST':
                body_len = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(body_len) if body_len else b''
            url = f'{GATEWAY}{self.path}'
            req = urllib.request.Request(url, data=body, method=method)
            for h, v in self.headers.items():
                if h.lower() not in ('host', 'connection'):
                    req.add_header(h, v)
            resp = urllib.request.urlopen(req, timeout=60)
            self.send_response(resp.status)
            self.send_header('Access-Control-Allow-Origin', '*')
            for h, v in resp.getheaders():
                if h.lower() != 'transfer-encoding':
                    self.send_header(h, v)
            self.end_headers()
            self.wfile.write(resp.read(65536))
        except Exception:
            # Return 200 with empty JSON instead of 502
            # GUI crashes on 502 ("something broke in the interface")
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(b'{}')

    def log_message(self, format, *args):
        pass  # Quiet

PROXY_PORT = int(os.environ.get('PROXY_PORT', '18649'))
HTTPServer(('0.0.0.0', PROXY_PORT), Proxy).serve_forever()
