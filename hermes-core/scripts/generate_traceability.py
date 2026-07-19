#!/usr/bin/env python3
"""
Generate traceability.yaml from requirements document.

Parses docs/requirements/<slug>.md and extracts:
- REQ-IDs from ## REQ-XXX headers
- Descriptions
- Acceptance criteria from bullet lists under ## Acceptance Criteria

Output: traceability.yaml in workdir root.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path


def parse_requirements(md_path: str) -> list[dict]:
    """Parse a requirements markdown document into structured requirements."""
    content = Path(md_path).read_text()

    requirements = []
    current_req = None
    current_section = None
    in_acceptance_criteria = False
    acceptance_criteria = []

    for line in content.split("\n"):
        stripped = line.strip()

        # REQ header: ## REQ-001
        req_match = re.match(r"^##\s+(REQ-\d+)", stripped)
        if req_match:
            if current_req:
                if acceptance_criteria:
                    current_req["acceptance_criteria"] = acceptance_criteria
                requirements.append(current_req)

            current_req = {
                "id": req_match.group(1),
                "description": "",
                "code_paths": [],
                "test_ids": [],
                "security_checks": [],
                "acceptance_criteria": [],
                "acceptance_test_ids": [],
            }
            current_section = "req_header"
            acceptance_criteria = []
            in_acceptance_criteria = False
            continue

        if current_req is None:
            continue

        # Description: text after ## REQ-XXX until next ## or criteria
        if current_section == "req_header" and stripped and not stripped.startswith("#"):
            if not stripped.startswith("**") and not stripped.startswith("-"):
                current_req["description"] = stripped
                current_section = "body"
            continue

        # Acceptance Criteria section
        if re.match(r"^###?\s*Acceptance\s+Criteria", stripped, re.IGNORECASE):
            in_acceptance_criteria = True
            continue

        # Next section ends acceptance criteria
        if in_acceptance_criteria and re.match(r"^##\s+", stripped):
            in_acceptance_criteria = False
            current_req["acceptance_criteria"] = acceptance_criteria
            acceptance_criteria = []
            continue

        # Bullet point in acceptance criteria
        if in_acceptance_criteria and stripped.startswith("-"):
            ac = stripped.lstrip("- ").strip()
            if ac:
                acceptance_criteria.append(ac)

        # NFR section
        if re.match(r"^###?\s*Non[-\s]Functional\s+Requirements", stripped, re.IGNORECASE):
            current_section = "nfr"
            continue

    # Don't forget the last requirement
    if current_req:
        if acceptance_criteria:
            current_req["acceptance_criteria"] = acceptance_criteria
        requirements.append(current_req)

    return requirements


def generate_traceability_yaml(
    requirements: list[dict],
    cycle_id: str,
    requirements_doc: str,
) -> str:
    """Generate traceability.yaml content from parsed requirements."""
    lines = [
        f"# Traceability Matrix",
        f"# Generated: {_now()}",
        f"# Source: {requirements_doc}",
        "",
        f"meta:",
        f"  cycle_id: \"{cycle_id}\"",
        f"  requirements_doc: \"{requirements_doc}\"",
        f"  generated_by: \"traceability-generator/1.0.0\"",
        f"  last_updated: \"{_now()}\"",
        "",
        f"requirements:",
    ]

    for req in requirements:
        lines.append(f"  - id: {req['id']}")
        if req["description"]:
            lines.append(f"    description: \"{req['description']}\"")
        lines.append(f"    code_paths: []")
        lines.append(f"    test_ids: []")
        lines.append(f"    security_checks: []")
        if req.get("acceptance_criteria"):
            lines.append(f"    acceptance_criteria:")
            for ac in req["acceptance_criteria"]:
                lines.append(f"      - \"{ac}\"")
            lines.append(f"    acceptance_test_ids: []")
        lines.append(f"    status: uncovered")
        lines.append("")  # blank line between requirements

    return "\n".join(lines)


def _now() -> str:
    import time
    return time.strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    import time

    if len(sys.argv) < 2:
        print("Usage: generate_traceability.py <requirements_doc.md> [output_path]")
        print("Example: generate_traceability.py docs/requirements/login.md")
        sys.exit(1)

    requirements_doc = sys.argv[1]
    workdir = os.getcwd()

    # Determine output path
    if len(sys.argv) >= 3:
        output_path = sys.argv[2]
    else:
        output_path = os.path.join(workdir, "traceability.yaml")

    if not os.path.exists(requirements_doc):
        print(f"❌ Requirements doc not found: {requirements_doc}")
        sys.exit(1)

    print(f"📄 Parsing: {requirements_doc}")
    requirements = parse_requirements(requirements_doc)

    if not requirements:
        print("⚠ No requirements found. Check document format:")
        print("   Expected: ## REQ-001")
        print("             Description text...")
        print("             ### Acceptance Criteria")
        print("             - criterion 1")
        print("             - criterion 2")
        sys.exit(1)

    print(f"   Found {len(requirements)} requirements:")
    for req in requirements:
        ac_count = len(req.get("acceptance_criteria", []))
        print(f"     {req['id']}: {req['description'][:60]}{'...' if len(req['description'])>60 else ''} ({ac_count} acceptance criteria)")

    cycle_id = f"{Path(workdir).name}_{time.strftime('%Y%m%d_%H%M%S')}"

    yaml_content = generate_traceability_yaml(requirements, cycle_id, requirements_doc)

    Path(output_path).write_text(yaml_content)
    print(f"\n✅ Traceability matrix written: {output_path}")
    print(f"   {len(requirements)} requirements, all status=uncovered")
    print(f"   Run quality_gate_runner.py to check coverage.")


if __name__ == "__main__":
    main()
