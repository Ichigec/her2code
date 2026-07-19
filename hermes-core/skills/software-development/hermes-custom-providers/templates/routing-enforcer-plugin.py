"""routing-enforcer — pre-delegation hook for model routing enforcement.

Intercepts every delegate_task call via the pre_tool_call hook.
Validates that each delegation uses the correct model/provider per role.
Blocks invalid delegations BEFORE the subagent spawns, returning
a structured error the orchestrator can understand and correct.

Deploy:
  1. mkdir -p ~/.hermes/plugins/<name>
  2. Copy this file as __init__.py and routing-enforcer-plugin.yaml as plugin.yaml
  3. Edit ROUTING table below for your models
  4. hermes plugins enable <name>
  5. Verify: hermes plugins list | grep <name> → "enabled"

Env vars:
  <NAME>_ROUTING_DISABLE=1   — emergency disable
  <NAME>_ROUTING_WARN_ONLY=1 — warn but don't block (gradual rollout)
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Routing Table (EDIT FOR YOUR MODELS) ────────────────────────────────────

ROUTING: Dict[str, Dict[str, Any]] = {
    "reasoning": {
        "model": "agents-a1-abliterated",
        "provider": "custom:local",
        "port": 8102,
        "aliases": {"agents-a1-abliterated", "agents-a1", "qwen3.6-35b"},
    },
    "coding": {
        "model": "nex-n2-mini",
        "provider": "custom:local",
        "port": 8101,
        "aliases": {"nex-n2-mini", "nex"},
    },
    "simulation": {
        "model": "agentworld",
        "provider": "custom:local",
        "port": 8103,
        "aliases": {"agentworld", "superqwen"},
    },
}

CLOUD_INDICATORS = {
    "deepseek", "kimi", "openai", "zai", "anthropic", "openrouter",
    "google", "xai", "groq", "mistral", "minimax", "dashscope",
}

FORBIDDEN_MODEL_SUBSTRINGS = {"gpt-4.1", "gpt-4", "gpt-3.5", "claude"}

# ── Configuration ──────────────────────────────────────────────────────────


def _plugin_disabled() -> bool:
    return os.environ.get("ROUTING_DISABLE", "").lower() in {"1", "true", "yes", "on"}


def _warn_only_mode() -> bool:
    return os.environ.get("ROUTING_WARN_ONLY", "").lower() in {"1", "true", "yes", "on"}


# ── Role Classification ────────────────────────────────────────────────────

ROLE_KEYWORDS: Dict[str, List[str]] = {
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
    "coding": [
        "code", "код", "implement", "реализ", "develop", "разработ",
        "build", "сборк", "deploy", "деплой", "развёрт", "test",
        "тест", "debug", "отлад", "fix", "исправ", "patch", "патч",
        "terminal", "терминал", "shell", "bash", "script", "скрипт",
        "commit", "коммит", "merge", "слиян", "compile", "компил",
        "devops", "ci/cd", "integrat", "интеграц", "security",
        "безопасност", "sast", "bandit", "semgrep", "install",
        "установ", "package", "пакет", "docker", "container",
    ],
    "simulation": [
        "simulat", "симул", "agentworld", "rl", "reinforcement",
        "environment", "сред", "adversar", "противник",
        "scenario", "сценар", "world model", "world-model",
    ],
}


def classify_role(goal: str) -> Tuple[str, float]:
    goal_lower = goal.lower()
    scores = {role: 0 for role in ROUTING}
    for role, keywords in ROLE_KEYWORDS.items():
        for kw in keywords:
            if kw in goal_lower:
                scores[role] += 1
    total = sum(scores.values())
    if total == 0:
        return ("reasoning", 0.0)
    best = max(scores, key=scores.get)
    return (best, scores[best] / total)


# ── Validation ─────────────────────────────────────────────────────────────


def _normalize_provider(provider: str) -> str:
    return provider.replace("custom:", "").replace("provider:", "")


def _is_cloud(provider: str) -> bool:
    provider_lower = _normalize_provider(provider).lower()
    return any(c in provider_lower for c in CLOUD_INDICATORS)


def _is_forbidden(model: str) -> bool:
    return any(f in model.lower() for f in FORBIDDEN_MODEL_SUBSTRINGS)


def _model_matches(model: str, expected: Dict[str, Any]) -> bool:
    if model == expected["model"]:
        return True
    return model in expected.get("aliases", set())


def validate_delegation(
    model: str,
    provider: str,
    goal: Optional[str] = None,
    role: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    if role is None and goal:
        role, _ = classify_role(goal)
    elif role is None:
        role = "reasoning"

    if role not in ROUTING:
        return (False, f"Unknown role '{role}'. Valid: {list(ROUTING.keys())}")

    expected = ROUTING[role]
    errors: List[str] = []

    if _is_cloud(provider):
        errors.append(f"🚫 CLOUD PROVIDER '{provider}' — requires LOCAL only.")
    if _is_forbidden(model):
        errors.append(f"🚫 FORBIDDEN MODEL '{model}'.")
    if not _model_matches(model, expected):
        errors.append(
            f"🔀 WRONG MODEL: '{model}' for {role}. "
            f"Expected: '{expected['model']}'"
        )
    if not _is_cloud(provider) and \
       _normalize_provider(provider) != _normalize_provider(expected["provider"]):
        errors.append(f"🔀 WRONG PROVIDER: '{provider}'. Expected: '{expected['provider']}'")

    if not errors:
        return (True, None)

    block_msg = f"ROUTING ENFORCER — DELEGATION BLOCKED\n" + "\n".join(errors)
    block_msg += f"\nFIX: model='{expected['model']}', provider='{expected['provider']}'"
    return (False, block_msg)


# ── Hook Implementation ────────────────────────────────────────────────────


def _on_pre_tool_call(
    tool_name: str,
    args: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> Optional[Dict[str, str]]:
    if _plugin_disabled() or tool_name != "delegate_task" or not isinstance(args, dict):
        return None

    warn_only = _warn_only_mode()

    # Single-task mode
    goal = args.get("goal", "")
    model = args.get("model", "")
    provider = args.get("provider", "")
    if goal and (model or provider):
        valid, block_msg = validate_delegation(model, provider, goal=goal)
        if not valid:
            if warn_only:
                logger.warning("ROUTING (WARN): %s", block_msg)
                return None
            return {"action": "block", "message": block_msg}

    # Batch mode
    tasks = args.get("tasks", [])
    if isinstance(tasks, list):
        for i, task in enumerate(tasks):
            if not isinstance(task, dict):
                continue
            t_goal = task.get("goal", "")
            t_model = task.get("model", "")
            t_provider = task.get("provider", "")
            if t_goal and (t_model or t_provider):
                valid, block_msg = validate_delegation(t_model, t_provider, goal=t_goal)
                if not valid:
                    if warn_only:
                        logger.warning("ROUTING (WARN): [%d] %s", i, block_msg)
                        continue
                    return {"action": "block", "message": f"[Task #{i}] {block_msg}"}

    return None


# ── Plugin Registration ────────────────────────────────────────────────────


def register(ctx) -> None:
    if _plugin_disabled():
        logger.info("routing-enforcer: disabled")
        return
    ctx.register_hook("pre_tool_call", _on_pre_tool_call)
    logger.info("routing-enforcer: registered (mode: %s)",
                "warn-only" if _warn_only_mode() else "block")
