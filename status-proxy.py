#!/usr/bin/env python3
"""Прокси: добавляет /api/status → /health для Desktop GUI"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request
import os

GATEWAY = os.environ.get('GATEWAY_URL', 'http://localhost:8648')

class Proxy(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/status':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status":"ok","auth_required":false}')
        else:
            try:
                req = urllib.request.Request(f'{GATEWAY}{self.path}')
                for h, v in self.headers.items():
                    if h.lower() != 'host':
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
                self.wfile.write(str(e).encode())

HTTPServer(('0.0.0.0', 18648), Proxy).serve_forever()
