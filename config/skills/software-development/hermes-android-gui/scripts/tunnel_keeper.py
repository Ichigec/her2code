#!/usr/bin/env python3
"""SSH tunnel keeper — uses ssh -R with auto-restart."""
import subprocess, time

CMD = [
    "ssh", "-o", "StrictHostKeyChecking=no",
    "-o", "ServerAliveInterval=5", "-o", "ServerAliveCountMax=3",
    "-o", "TCPKeepAlive=yes", "-o", "ExitOnForwardFailure=yes",
    "-R", "0.0.0.0:8643:localhost:8643",
    "root@<YOUR_VPS_IP>",
    "while true; do sleep 30; done"
]

def test():
    try:
        r = subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5",
             "root@<YOUR_VPS_IP>", "curl -s --max-time 3 http://127.0.0.1:8643/health"],
            capture_output=True, text=True, timeout=10
        )
        return r.returncode == 0 and '"status":"ok"' in r.stdout
    except:
        return False

def main():
    proc = None
    while True:
        if proc is None or proc.poll() is not None:
            if proc:
                print(f"{time.strftime('%H:%M:%S')} Tunnel died (rc={proc.returncode})", flush=True)
            print(f"{time.strftime('%H:%M:%S')} Starting tunnel...", flush=True)
            # Clean old VPS sessions first
            subprocess.run(["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5",
                "root@<YOUR_VPS_IP>",
                "ss -tlnp | grep 8643 | grep -oP 'pid=\\K\\d+' | xargs -r kill 2>/dev/null; echo done"],
                capture_output=True, timeout=10)
            time.sleep(1)
            proc = subprocess.Popen(CMD, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(4)
            if test():
                print(f"{time.strftime('%H:%M:%S')} Tunnel OK", flush=True)
        time.sleep(10)

if __name__ == "__main__":
    main()
