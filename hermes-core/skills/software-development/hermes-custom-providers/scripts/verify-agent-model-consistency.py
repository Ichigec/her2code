#!/usr/bin/env python3
"""
Verify model/provider consistency for a Hermes agent preset.

Checks 5 layers:
  1. config.yaml — model in providers.local.models (menu visibility)
  2. LiteLLM :4000 — model served by proxy (runtime availability)
  3. Agent .md frontmatter — model + provider fields (session model)
  4. registry.json — model + provider for delegation routing
  5. Agent .md body — broken refs + cloud-model-in-local-plan mismatch

Usage:
  python3 verify-agent-model-consistency.py --agent plan3
  python3 verify-agent-model-consistency.py --agent plan3 --expect-local
  python3 verify-agent-model-consistency.py --agent plan3 --expect-local --cloud-ok deepseek,kimi
"""
import argparse
import json
import re
import subprocess
import sys
import urllib.request
import yaml
from pathlib import Path

HERMES_HOME = Path.home() / ".hermes"
AGENTS_DIR = HERMES_HOME / "agents"
CONFIG_PATH = HERMES_HOME / "config.yaml"
REGISTRY_PATH = AGENTS_DIR / "registry.json"


def get_frontmatter(md_path: Path) -> dict:
    text = md_path.read_text()
    if not text.startswith("---"):
        return {}
    end = text.index("---", 3)
    return yaml.safe_load(text[3:end])


def get_litellm_models(port: int = 4000, api_key: str = "sk-local") -> list[str]:
    try:
        req = urllib.request.Request(
            f"http://localhost:{port}/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        return [m["id"] for m in data.get("data", [])]
    except Exception as e:
        print(f"  ⚠️  Cannot reach LiteLLM :{port}: {e}")
        return []


def main():
    parser = argparse.ArgumentParser(description="Verify agent model consistency")
    parser.add_argument("--agent", required=True, help="Agent name (e.g. plan3)")
    parser.add_argument("--expect-local", action="store_true",
                        help="Flag cloud model refs in delegate_task blocks")
    parser.add_argument("--cloud-ok", default="",
                        help="Comma-sep cloud provider names to allow even with --expect-local")
    args = parser.parse_args()

    md_path = AGENTS_DIR / f"{args.agent}.md"
    body = md_path.read_text()
    errors = []

    # --- Layer 1: config.yaml ---
    print("═" * 60)
    print(f"Agent: {args.agent}")
    print("═" * 60)

    cfg = yaml.safe_load(CONFIG_PATH.read_text())
    local_models = cfg.get("providers", {}).get("local", {}).get("models", [])

    # --- Layer 3: frontmatter ---
    fm = get_frontmatter(md_path)
    fm_model = fm.get("model", "")
    fm_provider = fm.get("provider", "")
    print(f"\n[Frontmatter]     model={fm_model}  provider={fm_provider}")

    if fm_model and fm_model not in local_models:
        errors.append(f"Frontmatter model '{fm_model}' NOT in config.yaml providers.local.models")

    # --- Layer 4: registry.json ---
    reg = json.loads(REGISTRY_PATH.read_text())
    reg_entry = reg.get("agents", {}).get(args.agent, {})
    reg_model = reg_entry.get("model", "")
    reg_provider = reg_entry.get("provider", "")
    print(f"[registry.json]   model={reg_model}  provider={reg_provider}")

    if fm_model != reg_model:
        errors.append(f"Frontmatter model ({fm_model}) != registry.json model ({reg_model})")
    if fm_provider != reg_provider:
        errors.append(f"Frontmatter provider ({fm_provider}) != registry.json provider ({reg_provider})")

    # --- Layer 1: config.yaml ---
    print(f"[config.yaml]     {fm_model} in providers.local.models: {fm_model in local_models}")

    # --- Layer 2: LiteLLM ---
    litellm_models = get_litellm_models()
    if fm_model and litellm_models:
        print(f"[LiteLLM :4000]   {fm_model} served: {fm_model in litellm_models}")
        if fm_model not in litellm_models:
            errors.append(f"Frontmatter model '{fm_model}' NOT in LiteLLM model list")

    # --- Layer 5: body references ---
    broken_patterns = [
        "agentworld-abliterated", "agents-a1-fp8",
        "custom:local:fp8", "custom:local:nex",
        "custom:local:agents", "custom:local:world",
    ]
    found_broken = [p for p in broken_patterns if p in body]
    if found_broken:
        errors.append(f"Broken model/sub-provider refs in body: {found_broken}")

    # Check delegate_task blocks for cloud models when --expect-local
    if args.expect_local:
        allowed = set(args.cloud_ok.split(",")) if args.cloud_ok else set()
        cloud_patterns = {
            "deepseek": r'model[=:]\s*"?(?:deepseek-\S+)"?\s*,\s*provider[=:]\s*"?deepseek"?',
            "kimi": r'model[=:]\s*"?(?:kimi-\S+)"?\s*,\s*provider[=:]\s*"?custom:kimi"?',
            "openai": r'model[=:]\s*"?(?:gpt-\S+)"?\s*,\s*provider[=:]\s*"?openai"?',
        }
        for cloud_name, pattern in cloud_patterns.items():
            if cloud_name in allowed:
                continue
            matches = re.findall(pattern, body)
            if matches:
                errors.append(
                    f"{len(matches)} delegate_task blocks use {cloud_name} "
                    f"(expected local-only). Use replace_all patch to fix."
                )

        # Check for dual routing tables (CLOUD + LOCAL) in agent body
        if re.search(r'Routing Rules\s*\(CLOUD', body, re.IGNORECASE):
            errors.append(
                "Agent body contains 'Routing Rules (CLOUD)' table — "
                "delete it, keep only LOCAL routing table. "
                "See references/agent-model-routing-enforcement.md variant A."
            )

    # --- Summary ---
    print("\n" + "═" * 60)
    if errors:
        print(f"❌ {len(errors)} ISSUES FOUND:")
        for e in errors:
            print(f"   • {e}")
        sys.exit(1)
    else:
        print("✅ ALL CONSISTENCY CHECKS PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
