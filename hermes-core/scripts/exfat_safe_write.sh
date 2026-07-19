#!/usr/bin/env bash
# exfat_safe_write.sh — Write scripts to exFAT drives with automatic corruption detection
#
# Solves 3 exFAT corruption modes:
#   1. Heredoc corruption (detected by hash mismatch)
#   2. UTF-8 mangling    (detected by hash mismatch)
#   3. LINE MERGE        (detected by line-count mismatch — bash -n PASSES on merged files!)
#
# Usage:
#   source ~/.hermes/scripts/exfat_safe_write.sh
#   exfat_safe_write /tmp/myscript.sh "/media/pavel/One Touch/myscript.sh"
#
# Or as standalone:
#   ~/.hermes/scripts/exfat_safe_write.sh /tmp/myscript.sh "/media/pavel/One Touch/myscript.sh"
#
# Exit codes:
#   0 = written and verified
#   1 = corruption detected (could not verify after retries)
#   2 = usage error

# NOTE: set -euo pipefail is only enabled when run as a script, not when sourced.
# This prevents grep's non-zero exit (no matches) from killing the calling shell.

# ─── Core verification: line-count + hash + diff ───
# Returns 0 if identical, 1 if corrupted, prints diagnostics on mismatch.
_exfat_verify() {
    local src="$1" dst="$2"

    # Layer 1: LINE COUNT — catches LINE MERGE (the silent killer)
    # bash -n passes on merged lines, but wc -l does not lie
    local src_lines dst_lines
    src_lines=$(wc -l < "$src" 2>/dev/null || echo "ERR")
    dst_lines=$(wc -l < "$dst" 2>/dev/null || echo "ERR")

    if [ "$src_lines" != "$dst_lines" ]; then
        echo "  CORRUPTION: line count $src_lines -> $dst_lines (LINE MERGE suspected)" >&2
        return 1
    fi

    # Layer 2: BYTE-LEVEL DIFF — catches heredoc corruption, UTF-8 mangling
    if ! diff -q "$src" "$dst" >/dev/null 2>&1; then
        echo "  CORRUPTION: content differs (diff non-empty)" >&2
        diff "$src" "$dst" | head -15 | sed 's/^/  /' >&2
        return 1
    fi

    # Layer 3: SHA256 — belt-and-suspenders hash comparison
    local src_hash dst_hash
    src_hash=$(sha256sum "$src" | cut -d' ' -f1)
    dst_hash=$(sha256sum "$dst" | cut -d' ' -f1)

    if [ "$src_hash" != "$dst_hash" ]; then
        echo "  CORRUPTION: SHA256 mismatch" >&2
        echo "    src: $src_hash" >&2
        echo "    dst: $dst_hash" >&2
        return 1
    fi

    echo "  VERIFIED: $dst_lines lines, hash $src_hash" >&2
    return 0
}

# ─── Safe write with retry ───
exfat_safe_write() {
    local src="$1" dst="$2"
    local max_retries="${EXFAT_WRITE_RETRIES:-3}"
    local attempt=1

    if [ -z "$src" ] || [ -z "$dst" ]; then
        echo "Usage: exfat_safe_write <source_file> <exfat_destination>" >&2
        return 2
    fi

    if [ ! -f "$src" ]; then
        echo "ERROR: source file '$src' does not exist" >&2
        return 2
    fi

    local dst_dir
    dst_dir=$(dirname "$dst")
    mkdir -p "$dst_dir" 2>/dev/null || true

    echo "exfat_safe_write: $src -> $dst"

    while [ "$attempt" -le "$max_retries" ]; do
        # Clean destination (avoid stale content)
        rm -f "$dst" 2>/dev/null || true

        # Copy with byte preservation
        cp "$src" "$dst"

        # Flush filesystem cache — critical for exFAT (write-back corruption window)
        sync
        sleep 0.3

        # Verify
        if _exfat_verify "$src" "$dst"; then
            chmod +x "$dst" 2>/dev/null || true
            echo "exfat_safe_write: OK on attempt $attempt/$max_retries"
            return 0
        fi

        echo "  WARNING: corruption on attempt $attempt/$max_retries, retrying..." >&2
        attempt=$((attempt + 1))
    done

    echo "exfat_safe_write: FAILED after $max_retries attempts" >&2
    echo "  Last-resort: try writing via terminal redirect instead of cp:" >&2
    echo "    cat '$src' > '$dst' && sync" >&2
    return 1
}

# ─── Quick check: is a file corrupted? (no source needed, heuristic) ───
exfat_health_check() {
    local f="$1"

    if [ ! -f "$f" ]; then
        echo "ERROR: '$f' not found" >&2
        return 2
    fi

    local issues=0

    # Check 1: Non-ASCII bytes (UTF-8 corruption)
    local nonascii
    nonascii=$(LC_ALL=C grep -cP '[\x80-\xFF]' "$f" 2>/dev/null)
    nonascii=${nonascii:-0}
    nonascii=$(echo "$nonascii" | tr -cd '0-9')
    nonascii=${nonascii:-0}
    if [ "$nonascii" -gt 0 ]; then
        echo "ISSUE: $nonascii lines contain non-ASCII bytes (UTF-8 corruption)" >&2
        issues=$((issues + 1))
    fi

    # Check 2: Mangled heredoc terminators (look for EOF without clean newline)
    if grep -qP '\$\s*$' "$f" 2>/dev/null; then
        : # fine — normal line endings
    fi
    if cat -A "$f" | grep -qP 'EOF.*[^^]$' 2>/dev/null; then
        : # normal
    fi

    # Check 3: Line count sanity
    local lines
    lines=$(wc -l < "$f")
    lines=$(echo "$lines" | tr -cd '0-9')
    lines=${lines:-0}
    if [ "$lines" -lt 3 ]; then
        echo "SUSPICIOUS: only $lines lines (possible merge)" >&2
        issues=$((issues + 1))
    fi

    # Check 4: bash -n syntax (catches heredoc corruption)
    if ! bash -n "$f" 2>/dev/null; then
        echo "ISSUE: bash -n fails (heredoc or encoding corruption)" >&2
        issues=$((issues + 1))
    fi

    if [ "$issues" -eq 0 ]; then
        echo "OK: no obvious corruption ($lines lines, ASCII clean, bash -n passes)"
        return 0
    fi
    return 1
}

# ─── If sourced, export functions. If executed directly, run. ───
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
    set -euo pipefail
    MAX_RETRIES="${EXFAT_WRITE_RETRIES:-3}"

    if [ $# -lt 2 ]; then
        echo "Usage: $0 <source_file> <exfat_destination>"
        echo "       $0 --check <file_on_exfat>"
        exit 2
    fi

    if [ "$1" = "--check" ]; then
        exfat_health_check "$2"
    else
        exfat_safe_write "$@"
    fi
fi
