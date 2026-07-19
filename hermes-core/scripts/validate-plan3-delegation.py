#!/usr/bin/env python3
"""
validate-plan3-delegation.py — Pre-delegation routing enforcer for plan3.

Validates that every delegate_task call respects the plan3 model routing table:
  - Reasoning → agents-a1-abliterated :8102
  - Coding    → nex-n2-mini           :8101
  - Simulation→ agentworld            :8103

Usage:
    python3 validate-plan3-delegation.py --model <m> --provider <p> --role <r> [--goal <g>]
    python3 validate-plan3-delegation.py --model <m> --provider <p> --goal <g>  # auto-classify
    python3 validate-plan3-delegation.py --json  # output routing table as JSON

Exit codes: 0=valid, 1=invalid routing, 2=cloud provider detected
"""

import argparse
import json
import os
import re
import sys
from typing import Optional, Tuple

# ── Routing Table ──────────────────────────────────────────────────────────
# Design intent: plan3 "Fully Local" model routing.

ROUTING = {
    "reasoning": {
        "model": "agents-a1-abliterated",
        "provider": "custom:local",
        "port": 8102,
        "benchmarks": "GAIA 96, IFEval 94.8, IFBench 80.6",
    },
    "coding": {
        "model": "nex-n2-mini",
        "provider": "custom:local",
        "port": 8101,
        "benchmarks": "SWE-Bench 74.4, Terminal-Bench 60.7",
    },
    "simulation": {
        "model": "agentworld",
        "provider": "custom:local",
        "port": 8103,
        "benchmarks": "AgentWorldBench 56.39",
    },
}

CLOUD_PROVIDERS = {"deepseek", "kimi", "openai", "zai", "anthropic", "openrouter", "google", "xai", "groq", "mistral", "minimax", "dashscope"}

FORBIDDEN_MODELS = {"gpt-4.1", "gpt-4.1-mini", "gpt-4", "gpt-3.5", "claude"}

# ── Role Classification ────────────────────────────────────────────────────

# Keyword → (role, confidence)
ROLE_KEYWORDS = {
    # Reasoning keywords
    "reasoning": [
        "анализ", "analysis", "research", "исследова", "plan", "план",
        "architect", "архитект", "design", "проектирован", "evaluat",
        "audit", "аудит", "critic", "критик", "curat", "куратор",
        "observ", "наблюд", "require", "требован", "system analyst",
        "системный анализ", "idea", "иде", "synthes", "синтез",
        "review", "обзор", "реценз", "citation", "цитат", "verify",
        "проверк", "валидац", "validate", "spec", "специфик",
        "refactor", "рефактор", "strategy", "стратег",
    ],
    # Coding keywords
    "coding": [
        "code", "код", "implement", "реализ", "develop", "разработ",
        "build", "сборк", "deploy", "деплой", "развёрт", "test",
        "тест", "debug", "отлад", "fix", "исправ", "patch", "патч",
        "terminal", "терминал", "shell", "bash", "script", "скрипт",
        "commit", "коммит", "merge", "слиян", "pull request", "PR",
        "compile", "компил", "devops", "ci/cd", "integrat", "интеграц",
        "security", "безопасност", "sast", "bandit", "semgrep",
        "install", "установ", "package", "пакет", "dependency", "зависим",
        "docker", "container", "контейнер",
    ],
    # Simulation keywords
    "simulation": [
        "simulat", "симул", "agentworld", "rl", "reinforcement",
        "environment", "сред", "adversar", "противник",
        "scenario", "сценар", "world model", "world-model",
    ],
}


def classify_role(goal: str) -> Tuple[str, float]:
    """Classify a delegation goal into reasoning/coding/simulation.

    Returns (role, confidence) where role ∈ {reasoning, coding, simulation}.
    """
    goal_lower = goal.lower()
    scores = {role: 0 for role in ROUTING}

    for role, keywords in ROLE_KEYWORDS.items():
        for kw in keywords:
            if kw in goal_lower:
                scores[role] += 1

    total = sum(scores.values())
    if total == 0:
        return ("reasoning", 0.0)  # default to reasoning

    best = max(scores, key=scores.get)
    confidence = scores[best] / total
    return (best, confidence)


# ── Validation ─────────────────────────────────────────────────────────────


def is_cloud(provider: str) -> bool:
    """Check if provider is a cloud/remote API (not local)."""
    provider_lower = provider.lower().replace("custom:", "")
    return any(c in provider_lower for c in CLOUD_PROVIDERS)


def is_forbidden(model: str) -> bool:
    """Check if model is on the forbidden list."""
    return any(f in model.lower() for f in FORBIDDEN_MODELS)


def validate(
    model: str,
    provider: str,
    role: Optional[str] = None,
    goal: Optional[str] = None,
) -> dict:
    """Validate model/provider against plan3 routing table.

    Returns dict with: valid, role, expected, errors[], warnings[].
    """
    errors = []
    warnings = []

    # Auto-classify if no explicit role
    if role is None and goal:
        role, confidence = classify_role(goal)
        if confidence < 0.5:
            warnings.append(
                f"Low classification confidence ({confidence:.1%}) for goal. "
                f"Classified as '{role}'. Verify manually."
            )
    elif role is None:
        role = "reasoning"
        warnings.append("No role or goal provided — defaulting to 'reasoning'.")

    # Validate role
    if role not in ROUTING:
        return {
            "valid": False,
            "role": role,
            "errors": [f"Unknown role '{role}'. Valid: {list(ROUTING.keys())}"],
            "warnings": warnings,
        }

    expected = ROUTING[role]

    # Check for cloud providers (BLOCKER)
    if is_cloud(provider):
        errors.append(
            f"CLOUD PROVIDER DETECTED: '{provider}'. "
            f"Plan3 requires LOCAL models only. Expected: custom:local"
        )

    # Check for forbidden models
    if is_forbidden(model):
        errors.append(
            f"FORBIDDEN MODEL: '{model}'. This model is excluded from ALL plan3 roles."
        )

    # Check model match
    if model != expected["model"]:
        errors.append(
            f"WRONG MODEL: '{model}' for role '{role}'. "
            f"Expected: '{expected['model']}' "
            f"(port :{expected['port']}, {expected['benchmarks']})"
        )

    # Check provider match
    if provider != expected["provider"]:
        errors.append(
            f"WRONG PROVIDER: '{provider}' for role '{role}'. "
            f"Expected: '{expected['provider']}'"
        )

    return {
        "valid": len(errors) == 0,
        "role": role,
        "expected": expected,
        "errors": errors,
        "warnings": warnings,
        "model": model,
        "provider": provider,
    }


# ── CLI ────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Validate plan3 delegation model routing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --model agents-a1-abliterated --provider custom:local --role reasoning
  %(prog)s --model nex-n2-mini --provider custom:local --goal "Write Python tests"
  %(prog)s --model deepseek-v4-pro --provider deepseek --role coding
        """,
    )
    parser.add_argument("--model", help="Model name from delegate_task")
    parser.add_argument("--provider", help="Provider from delegate_task")
    parser.add_argument("--role", choices=["reasoning", "coding", "simulation"],
                        help="Explicit role (skips auto-classification)")
    parser.add_argument("--goal", help="Goal text for auto-classification")
    parser.add_argument("--json", action="store_true", help="Output routing table as JSON")
    parser.add_argument("--strict", action="store_true",
                        help="Exit 1 on warnings too (not just errors)")

    args = parser.parse_args()

    # --json mode: dump routing table
    if args.json:
        print(json.dumps(ROUTING, indent=2))
        return

    # Validation mode
    if not args.model or not args.provider:
        parser.error("--model and --provider required for validation mode")

    result = validate(
        model=args.model,
        provider=args.provider,
        role=args.role,
        goal=args.goal,
    )

    # Print result
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # Exit code
    if args.strict and result.get("warnings"):
        sys.exit(1)
    sys.exit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
