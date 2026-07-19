#!/usr/bin/env python3
"""Persistent TCP proxy: 0.0.0.0:8643 → 127.0.0.1:8642. Never dies."""
import socket, threading, sys

LISTEN = ("0.0.0.0", 8643)
TARGET = ("127.0.0.1", 8642)

def proxy(client, addr):
    try:
        backend = socket.create_connection(TARGET, timeout=30)
        def forward(src, dst):
            while True:
                data = src.recv(8192)
                if not data: break
                dst.sendall(data)
        t1 = threading.Thread(target=forward, args=(client, backend), daemon=True)
        t2 = threading.Thread(target=forward, args=(backend, client), daemon=True)
        t1.start(); t2.start()
        t1.join(); t2.join()
    except Exception as e:
        print(f"[proxy] {addr} error: {e}", flush=True)
    finally:
        try: client.close()
        except: pass
        try: backend.close()
        except: pass

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(LISTEN)
server.listen(50)
print(f"[proxy] Listening on {LISTEN[0]}:{LISTEN[1]} → {TARGET[0]}:{TARGET[1]}", flush=True)

while True:
    try:
        client, addr = server.accept()
        threading.Thread(target=proxy, args=(client, addr), daemon=True).start()
    except KeyboardInterrupt:
        break
    except Exception as e:
        print(f"[proxy] accept error: {e}", flush=True)
