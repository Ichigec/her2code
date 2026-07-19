#!/usr/bin/env python3
"""
Combined launcher: starts diffusion server as subprocess, runs training, cleans up.

Use this pattern when Hermes kills background processes between turns.
Server and training run as children of ONE background process, so both survive.

Copy and modify MODEL_PATH, BINARY, PORT, SERVER_SCRIPT, TRAINING_SCRIPT.
"""
import subprocess, sys, time, os, signal, urllib.request

# ── CONFIG (modify these) ─────────────────────────────────────────
MODEL_PATH = "/path/to/model.gguf"
BINARY = "/path/to/llama-diffusion-cli"
PORT = 8646
SERVER_SCRIPT = "/path/to/diffusion-server.py"
TRAINING_SCRIPT = "/path/to/self_play_loop.py"
TRAINING_CWD = "/path/to/rldiffusion"
VENV_PYTHON = "/path/to/venv/bin/python3"
# ────────────────────────────────────────────────────────────────────

env = os.environ.copy()
env.update({
    "DG_MODEL_PATH": MODEL_PATH,
    "DG_BINARY": BINARY,
    "DG_NGL": "99",
    "DG_CTX_SIZE": "65536",
    "DG_PORT": str(PORT),
    "DG_MODEL_NAME": "diffusion-gemma-26b",
    "DG_DEFAULT_STEPS": "16",
})

# Start server
print("[launcher] Starting DiffusionGemma server...")
server = subprocess.Popen(
    [VENV_PYTHON, SERVER_SCRIPT],
    env=env,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
print(f"[launcher] Server PID: {server.pid}")

# Wait for health
for i in range(60):
    time.sleep(2)
    try:
        r = urllib.request.urlopen(f"http://localhost:{PORT}/health", timeout=3)
        if r.status == 200:
            print(f"[launcher] Server ready after {(i+1)*2}s")
            break
    except Exception:
        pass
else:
    print("[launcher] Server failed to start")
    server.kill()
    sys.exit(1)

# Run training
print("[launcher] Starting training...")
train_env = os.environ.copy()
train_env["PYTHONUNBUFFERED"] = "1"
result = subprocess.run(
    [VENV_PYTHON, "-u", TRAINING_SCRIPT],
    cwd=TRAINING_CWD,
    env=train_env,
)

# Cleanup
print(f"\n[launcher] Training finished (exit={result.returncode}). Stopping server...")
server.terminate()
try:
    server.wait(timeout=10)
except subprocess.TimeoutExpired:
    server.kill()
print("[launcher] Done.")
