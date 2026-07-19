"""
GatePassport — HMAC-SHA256 cryptographic certificate.

Proves that ALL quality gates passed. Used by:
- commit-msg git hook (requires passport in commit message)
- VPS pre-deploy-gate.sh (requires valid passport for deployment)

Tamper-evident: HMAC-signed with secret key, freshness-checked (30 min expiry),
bound to git commit + workdir hash.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from pathlib import Path
from typing import Optional


SECRET_PATH = Path.home() / ".hermes" / "gates" / ".gate-secret"


def _load_secret() -> bytes:
    """Load or create the HMAC secret key."""
    secret_path = SECRET_PATH

    if secret_path.exists():
        return secret_path.read_bytes()

    # Generate new secret
    secret = os.urandom(32)
    secret_path.parent.mkdir(parents=True, exist_ok=True)
    secret_path.write_bytes(secret)
    secret_path.chmod(0o600)
    return secret


def _get_git_commit(workdir: str) -> str:
    """Get HEAD git commit hash."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, cwd=workdir, timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def _hash_workdir_tree(workdir: str) -> str:
    """Compute a hash of all tracked files in the workdir."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z"],
            capture_output=True, text=False, cwd=workdir, timeout=10,
        )
        if result.returncode != 0:
            return "hash:unknown"
        files = result.stdout.decode("utf-8", errors="replace").split("\0")
        files = [f for f in files if f]

        hasher = hashlib.sha256()
        for f in sorted(files):
            fpath = Path(workdir) / f
            if fpath.is_file():
                hasher.update(f.encode())
                hasher.update(fpath.read_bytes())
        return f"sha256:{hasher.hexdigest()}"
    except Exception:
        return "hash:unknown"


def generate_passport(verdict_dict: dict, workdir: str) -> Optional[dict]:
    """
    Generate an HMAC-SHA256 signed GatePassport from a GateVerdict.

    Args:
        verdict_dict: GateVerdict.to_dict() output
        workdir: project root path

    Returns:
        Passport dict with hmac_signature, or None if verdict is not ALL_PASSED
    """
    if verdict_dict.get("verdict") != "ALL_PASSED":
        return None

    secret = _load_secret()

    # Build payload
    payload = {
        "cycle_id": verdict_dict.get("cycle_id", "unknown"),
        "timestamp": time.time(),
        "verdict": "ALL_PASSED",
        "total_gates": verdict_dict.get("total_gates", 0),
        "passed_gates": verdict_dict.get("passed_gates", 0),
        "git_commit": _get_git_commit(workdir),
        "workdir_hash": _hash_workdir_tree(workdir),
        "runner_version": "1.0.0",
    }

    # HMAC-SHA256 sign
    payload_bytes = json.dumps(payload, sort_keys=True).encode()
    signature = hmac.new(secret, payload_bytes, hashlib.sha256).hexdigest()

    passport = {**payload, "hmac_signature": signature}
    return passport


def verify_passport(passport: dict) -> tuple[bool, str]:
    """
    Verify a GatePassport's authenticity and freshness.

    Returns:
        (is_valid, reason)
    """
    # Check required fields
    required = ["cycle_id", "timestamp", "verdict", "hmac_signature"]
    for field in required:
        if field not in passport:
            return False, f"Missing required field: {field}"

    # Check verdict
    if passport.get("verdict") != "ALL_PASSED":
        return False, "Verdict is not ALL_PASSED"

    # Check freshness (30 minutes)
    age = time.time() - passport.get("timestamp", 0)
    if age > 1800:
        return False, f"Passport expired ({age:.0f}s old, max 1800s)"

    # Recompute HMAC
    secret = _load_secret()
    verify_payload = {
        k: v for k, v in passport.items()
        if k not in ("hmac_signature",)
    }
    payload_bytes = json.dumps(verify_payload, sort_keys=True).encode()
    expected_sig = hmac.new(secret, payload_bytes, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected_sig, passport.get("hmac_signature", "")):
        return False, "HMAC signature mismatch — passport may be FORGED"

    return True, "Valid"


def format_passport_string(passport: dict) -> str:
    """Format passport as a string for git commit messages."""
    sig = passport.get("hmac_signature", "")[:16]
    cycle_id = passport.get("cycle_id", "unknown")
    return f"GatePassport:{cycle_id}:{sig}"
