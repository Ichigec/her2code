#!/usr/bin/env python3
"""Unified proxy + built-in SSH tunnel keeper. ONE process to rule them all.
For the hermes-android-app skill.
"""
import http.server, urllib.request, json, sys, threading, time

VPS = '<YOUR_VPS_IP>'
VPS_USER = 'root'
REMOTE_PORT = 8643
LITELLM = 'http://127.0.0.1:4000/v1/chat/completions'
OPENCODE = 'http://127.0.0.1:8646/v1/chat/completions'
LITELLM_KEY = 'sk-local'

AGENT_MODELS = {'hermes-agent', 'general', 'build', 'plan', 'review', 'safe',
                'explore', 'scout', 'deep-explore', 'claw', 'composter'}


def tunnel_thread():
    """Keep SSH reverse tunnel alive using subprocess ssh -R (NOT paramiko)."""
    import subprocess
    while True:
        try:
            r = subprocess.run([
                'ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'ConnectTimeout=5',
                f'{VPS_USER}@{VPS}',
                f'curl -s --max-time 3 http://127.0.0.1:{REMOTE_PORT}/health'
            ], capture_output=True, text=True, timeout=10)
            if r.returncode == 0 and '"status":"ok"' in r.stdout:
                time.sleep(15)
                continue
        except:
            pass
        
        print(f"Tunnel dead, restarting...", flush=True)
        subprocess.run(['pkill', '-f', f'ssh.*-R.*0.0.0.0:{REMOTE_PORT}'], capture_output=True)
        subprocess.run(['ssh', '-o', 'StrictHostKeyChecking=no', f'{VPS_USER}@{VPS}',
            f'ss -tlnp | grep {REMOTE_PORT} | grep -oP "pid=\\\\K\\d+" | xargs -r kill'
        ], capture_output=True, timeout=10)
        time.sleep(1)
        subprocess.Popen([
            'ssh', '-o', 'StrictHostKeyChecking=no',
            '-o', 'ServerAliveInterval=5', '-o', 'ServerAliveCountMax=3',
            '-o', 'TCPKeepAlive=yes', '-o', 'ExitOnForwardFailure=yes',
            '-fN', '-R', f'0.0.0.0:{REMOTE_PORT}:localhost:{REMOTE_PORT}',
            f'{VPS_USER}@{VPS}'
        ])
        time.sleep(5)


class Proxy(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            body_len = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(body_len)
            data = json.loads(body)
            model = data.get('model', '')
            
            if model in AGENT_MODELS:
                target = OPENCODE
                auth = self.headers.get('Authorization', '')
            else:
                target = LITELLM
                auth = f'Bearer {LITELLM_KEY}'
            
            req = urllib.request.Request(target, data=body,
                headers={'Authorization': auth, 'Content-Type': 'application/json'})
            resp = urllib.request.urlopen(req, timeout=120)
            
            self.send_response(resp.status)
            self.send_header('Content-Type', resp.headers.get('Content-Type', 'application/json'))
            self.end_headers()
            while True:
                chunk = resp.read(8192)
                if not chunk: break
                self.wfile.write(chunk)
                self.wfile.flush()
        except Exception as e:
            self.send_response(502)
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())

    def do_GET(self):
        if '/health' in self.path:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8647
    t = threading.Thread(target=tunnel_thread, daemon=True)
    t.start()
    print(f"Proxy on port {port}, tunnel thread started", flush=True)
    http.server.HTTPServer(('', port), Proxy).serve_forever()
