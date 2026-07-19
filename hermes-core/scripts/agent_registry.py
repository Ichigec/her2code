#!/usr/bin/env python3
"""Agent Registry Generator for Hermes.

Scans ~/.hermes/agents/ recursively for *.md files, extracts YAML frontmatter,
and generates ~/.hermes/agents/registry.json.

Usage:
    python3 agent_registry.py           # Generate registry.json
    python3 agent_registry.py --validate # Validate YAML frontmatter only
    python3 agent_registry.py --json    # Output JSON to stdout, skip file write

Requirements: Python 3.12+, standard library only.
"""

import json
import os
import sys
import re
from datetime import datetime, timezone
from pathlib import Path


# ── Defaults for legacy agent files (Format 1: label/description/toolsets) ──
LEGACY_DEFAULTS = {
    "model": "deepseek-v4-pro",
    "provider": "deepseek",
    "permissionMode": "default",
    "allowedSubagents": [],
    "mcpServers": [],
    "isolation": "none",
    "memory": "session",
}

# Required fields for every entry in the registry
REQUIRED_FIELDS = [
    "name", "description", "model", "provider", "tools",
    "permissionMode", "allowedSubagents", "mcpServers",
    "isolation", "memory",
]


def parse_simple_yaml(text: str) -> dict:
    """Parse a flat YAML frontmatter block (key: value + inline lists).

    Handles:
        key: value
        key: "value"
        key: [item1, item2]
        key: []
        key: true / false
    Does NOT handle nested dicts, multiline strings, or anchors.
    """
    result = {}

    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # Line must have a colon for key: value
        if ":" not in stripped:
            continue

        key, _, rest = stripped.partition(":")
        key = key.strip()
        rest = rest.strip()

        if not key:
            continue

        # Inline list: [a, b, c] or []
        if rest.startswith("[") and rest.endswith("]"):
            inner = rest[1:-1].strip()
            if inner:
                items = [
                    item.strip().strip("\"'")
                    for item in _split_list(inner)
                ]
            else:
                items = []
            result[key] = items
            continue

        # Scalar value — strip quotes
        value = rest.strip().strip("\"'")
        if value == "true":
            result[key] = True
        elif value == "false":
            result[key] = False
        elif value == "~" or value == "null":
            result[key] = None
        else:
            result[key] = value

    return result


def _split_list(inner: str) -> list[str]:
    """Split comma-separated list items, respecting quoted strings."""
    items = []
    current = []
    in_quote = False
    quote_char = None

    for ch in inner:
        if ch in ('"', "'") and not in_quote:
            in_quote = True
            quote_char = ch
            continue
        elif ch == quote_char and in_quote:
            in_quote = False
            quote_char = None
            continue
        elif ch == "," and not in_quote:
            items.append("".join(current).strip())
            current = []
            continue
        current.append(ch)

    if current:
        items.append("".join(current).strip())

    return [i for i in items if i]


def extract_frontmatter(content: str) -> dict | None:
    """Extract and parse YAML frontmatter between --- delimiters.

    Returns None if no frontmatter found or if it's malformed.
    """
    lines = content.split("\n")
    if not lines or lines[0].strip() != "---":
        return None

    # Find closing ---
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return None  # No closing delimiter

    frontmatter_text = "\n".join(lines[1:end_idx])
    if not frontmatter_text.strip():
        return None  # Empty frontmatter

    return parse_simple_yaml(frontmatter_text)


def derive_name_from_label(label: str) -> str:
    """Derive a clean agent name from a legacy 'label' field.

    'Plan · Developer'     -> 'Developer'
    'Claw Orchestrator'    -> 'Claw Orchestrator'
    'General'              -> 'General'
    'Knowledge Curator'    -> 'Knowledge Curator'
    """
    # Strip "Plan · " prefix if present
    name = re.sub(r"^Plan\s*·\s*", "", label).strip()
    return name


def normalize_agent(
    fm: dict,
    rel_path: str,
    filename_stem: str,
    is_legacy: bool,
) -> dict:
    """Normalize frontmatter into the standard registry entry format.

    Legacy agents (Format 1) have: label, description, mode, emoji,
    reasoning, toolsets.  New agents (Format 2) have: name, description,
    model, provider, tools, permissionMode, etc.
    """
    entry = {}

    if is_legacy:
        # ── Legacy (Format 1) ──
        entry["name"] = derive_name_from_label(
            fm.get("label", filename_stem)
        )
        entry["description"] = fm.get("description", "")
        entry["model"] = fm.get("model", LEGACY_DEFAULTS["model"])
        entry["provider"] = fm.get("provider", LEGACY_DEFAULTS["provider"])
        entry["tools"] = fm.get("toolsets", [])
        entry["permissionMode"] = fm.get(
            "permissionMode", LEGACY_DEFAULTS["permissionMode"]
        )
        entry["allowedSubagents"] = fm.get(
            "allowedSubagents", LEGACY_DEFAULTS["allowedSubagents"]
        )
        entry["mcpServers"] = fm.get(
            "mcpServers", LEGACY_DEFAULTS["mcpServers"]
        )
        entry["isolation"] = fm.get(
            "isolation", LEGACY_DEFAULTS["isolation"]
        )
        entry["memory"] = fm.get("memory", LEGACY_DEFAULTS["memory"])
    else:
        # ── New (Format 2) ──
        entry["name"] = fm.get("name", filename_stem)
        entry["description"] = fm.get("description", "")
        entry["model"] = fm.get("model", LEGACY_DEFAULTS["model"])
        entry["provider"] = fm.get("provider", LEGACY_DEFAULTS["provider"])
        entry["tools"] = fm.get("tools", [])
        entry["permissionMode"] = fm.get(
            "permissionMode", LEGACY_DEFAULTS["permissionMode"]
        )
        entry["allowedSubagents"] = fm.get(
            "allowedSubagents", LEGACY_DEFAULTS["allowedSubagents"]
        )
        entry["mcpServers"] = fm.get(
            "mcpServers", LEGACY_DEFAULTS["mcpServers"]
        )
        entry["isolation"] = fm.get(
            "isolation", LEGACY_DEFAULTS["isolation"]
        )
        entry["memory"] = fm.get("memory", LEGACY_DEFAULTS["memory"])

    return entry


def is_legacy_format(fm: dict) -> bool:
    """Determine if frontmatter uses the legacy format (has 'label' not 'name')."""
    return "label" in fm and "name" not in fm


def scan_agents(agents_dir: Path) -> list[tuple[Path, str]]:
    """Recursively find all *.md files under agents_dir.

    Returns list of (absolute_path, relative_path_from_agents_dir).
    """
    results = []
    for md_file in sorted(agents_dir.rglob("*.md")):
        rel = md_file.relative_to(agents_dir)
        results.append((md_file, str(rel)))
    return results


def build_registry(agents_dir: Path) -> tuple[dict, list[str]]:
    """Build the complete registry dict and collect warnings.

    Returns (registry_dict, warnings_list).
    """
    registry: dict[str, dict] = {}
    warnings: list[str] = []

    agent_files = scan_agents(agents_dir)

    for abs_path, rel_path in agent_files:
        try:
            content = abs_path.read_text(encoding="utf-8")
        except Exception as e:
            warnings.append(f"ERROR reading {rel_path}: {e}")
            continue

        fm = extract_frontmatter(content)

        # Determine format
        legacy = is_legacy_format(fm) if fm else False

        if fm is None:
            # No valid frontmatter
            warnings.append(
                f"WARNING: {rel_path} — missing or malformed YAML frontmatter "
                f"(skipping)"
            )
            continue

        # Validate required fields for non-legacy
        if not legacy:
            missing = [
                f for f in ["name", "description", "tools"]
                if f not in fm
            ]
            if missing:
                warnings.append(
                    f"WARNING: {rel_path} — missing fields in frontmatter: "
                    f"{', '.join(missing)}"
                )
        else:
            missing = [
                f for f in ["label", "description"]
                if f not in fm
            ]
            if missing:
                warnings.append(
                    f"WARNING: {rel_path} — legacy format missing fields: "
                    f"{', '.join(missing)}"
                )

        # Derive registry key from relative path (strip .md)
        key = str(Path(rel_path).with_suffix(""))

        entry = normalize_agent(
            fm, rel_path, Path(rel_path).stem, legacy
        )
        entry["path"] = rel_path

        registry[key] = entry

    return registry, warnings


def print_warnings(warnings: list[str]):
    """Print warnings to stderr."""
    if warnings:
        print(f"\n⚠  {len(warnings)} warning(s):", file=sys.stderr)
        for w in warnings:
            print(f"   {w}", file=sys.stderr)
        print(file=sys.stderr)


def validate_only(agents_dir: Path) -> int:
    """Validate YAML frontmatter only; return exit code."""
    registry, warnings = build_registry(agents_dir)

    total = len(scan_agents(agents_dir))
    valid = len(registry)

    print(f"Scanned: {total} agent files")
    print(f"Valid frontmatter: {valid}")
    print(f"Issues: {len(warnings)}")

    print_warnings(warnings)

    if warnings:
        return 1
    print("✓ All agent files have valid YAML frontmatter.")
    return 0


def get_hermes_root() -> Path:
    """Derive .hermes root from this script's location.

    The script lives at <hermes_root>/scripts/agent_registry.py.
    Falls back to $HERMES_HOME or ~/.hermes if detection fails.
    """
    script_path = Path(__file__).resolve()
    if script_path.parent.name == "scripts":
        return script_path.parent.parent
    hermes_home = os.environ.get("HERMES_HOME")
    if hermes_home:
        return Path(hermes_home)
    return Path.home() / ".hermes"


def main():
    hermes_root = get_hermes_root()
    agents_dir = hermes_root / "agents"
    registry_path = agents_dir / "registry.json"

    json_only = "--json" in sys.argv
    validate = "--validate" in sys.argv

    if validate:
        sys.exit(validate_only(agents_dir))

    registry, warnings = build_registry(agents_dir)

    output = {
        "agents": registry,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_agents": len(registry),
    }

    json_text = json.dumps(output, ensure_ascii=False, indent=2)

    if json_only:
        print(json_text)
    else:
        registry_path.write_text(json_text + "\n", encoding="utf-8")
        print(f"✓ Registry written: {registry_path}")
        print(f"  Total agents: {len(registry)}")

    print_warnings(warnings)


if __name__ == "__main__":
    main()
