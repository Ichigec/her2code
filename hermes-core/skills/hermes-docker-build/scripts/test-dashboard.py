#!/usr/bin/env python3
"""Test all Docker Dashboard endpoints the GUI needs. Run BEFORE asking user to launch GUI."""
import urllib.request, json, socket, base64, os, sys

BASE = os.environ.get('DASHBOARD_URL', 'http://127.0.0.1:9119')
TOKEN = os.environ.get('DASHBOARD_TOKEN', 'sk-local')

def test_rest(path):
    """Test REST endpoint with auth token."""
    r = urllib.request.Request(f"{BASE}{path}")
    r.add_header("Authorization", f"Bearer {TOKEN}")
    try:
        resp = urllib.request.urlopen(r, timeout=5)
        body = resp.read().decode()[:200]
        return True, resp.status, body
    except Exception as e:
        return False, getattr(e, 'code', 0), str(e)[:100]

def test_websocket():
    """Test WebSocket upgrade."""
    try:
        key = base64.b64encode(os.urandom(16)).decode()
        s = socket.socket()
        s.settimeout(10)
        host = BASE.split('://')[1].split(':')[0]
        port = int(BASE.split(':')[-1])
        s.connect((host, port))
        req = (f"GET /api/ws?token={TOKEN} HTTP/1.1\r\n"
               f"Host: {host}:{port}\r\n"
               f"Upgrade: websocket\r\n"
               f"Connection: Upgrade\r\n"
               f"Sec-WebSocket-Key: {key}\r\n"
               f"Sec-WebSocket-Version: 13\r\n\r\n")
        s.send(req.encode())
        resp = b''
        while True:
            try:
                chunk = s.recv(4096)
                if not chunk: break
                resp += chunk
                if b'\r\n\r\n' in resp: break
            except: break
        status = resp.decode().split('\r\n')[0]
        s.close()
        return '101' in status, status
    except Exception as e:
        return False, str(e)[:100]

if __name__ == '__main__':
    print(f"Testing endpoints at {BASE} with token={TOKEN[:5]}...")
    print()
    
    all_pass = True
    tests = [
        ('/api/status', 'rest', 'GUI 24%'),
        ('/api/sessions', 'rest', 'GUI 95%'),
        ('/api/logs?file=gui&lines=5', 'rest', 'GUI 95%'),
        ('/api/config', 'rest', 'GUI 95%'),
    ]
    
    for path, method, stage in tests:
        ok, status, body = test_rest(path)
        icon = 'PASS' if ok else 'FAIL'
        if not ok: all_pass = False
        print(f"  [{icon}] {stage}: {path} -> {status} {body[:80]}")
    
    print()
    ok, detail = test_websocket()
    icon = 'PASS' if ok else 'FAIL'
    if not ok: all_pass = False
    print(f"  [{icon}] GUI 95% (chat): /api/ws -> {detail}")
    
    print()
    if all_pass:
        print("ALL PASS. Safe to launch GUI.")
        sys.exit(0)
    else:
        print("SOME FAIL. Fix before launching GUI.")
        sys.exit(1)
