#!/usr/bin/env python3
"""Прокси: добавляет /api/status и стабы для Desktop GUI к Docker Gateway"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request
import os

GATEWAY = os.environ.get('GATEWAY_URL', 'http://localhost:8648')

# Стабы для эндпоинтов которые GUI ждёт но Docker-gateway не имеет
STUBS = {
    '/api/status': b'{"status":"ok","auth_required":false}',
    '/api/sessions': b'[]',
    '/api/agents': b'[]',
    '/api/skills': b'[]',
    '/api/cron': b'[]',
    '/api/config': b'{}',
}

class Proxy(BaseHTTPRequestHandler):
    def do_GET(self):
        # Стабы
        for stub_path, stub_data in STUBS.items():
            if self.path == stub_path or self.path.startswith(stub_path + '?'):
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(stub_data)
                return

        # Прокси на Docker
        try:
            req = urllib.request.Request(f'{GATEWAY}{self.path}')
            for h, v in self.headers.items():
                if h.lower() not in ('host', 'connection'):
                    req.add_header(h, v)
            resp = urllib.request.urlopen(req, timeout=30)
            self.send_response(resp.status)
            for h, v in resp.getheaders():
                if h.lower() != 'transfer-encoding':
                    self.send_header(h, v)
            self.end_headers()
            self.wfile.write(resp.read())
        except Exception as e:
            self.send_response(502)
            self.end_headers()
            self.wfile.write(b'{"error":"upstream unavailable"}')

    def do_POST(self):
        # Проксируем POST (чат и т.д.)
        try:
            body_len = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(body_len) if body_len else b''
            req = urllib.request.Request(f'{GATEWAY}{self.path}', data=body)
            for h, v in self.headers.items():
                if h.lower() not in ('host', 'connection'):
                    req.add_header(h, v)
            resp = urllib.request.urlopen(req, timeout=120)
            self.send_response(resp.status)
            for h, v in resp.getheaders():
                if h.lower() != 'transfer-encoding':
                    self.send_header(h, v)
            self.end_headers()
            self.wfile.write(resp.read())
        except Exception as e:
            self.send_response(502)
            self.end_headers()
            self.wfile.write(b'{"error":"upstream unavailable"}')

    def log_message(self, format, *args):
        pass  # Тихо

PROXY_PORT = int(os.environ.get('PROXY_PORT', '18649'))
HTTPServer(('0.0.0.0', PROXY_PORT), Proxy).serve_forever()
