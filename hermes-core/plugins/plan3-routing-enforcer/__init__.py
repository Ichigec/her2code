"""plan3-routing-enforcer — pre-delegation hook for plan3 model routing.

Intercepts every delegate_task call via the pre_tool_call hook.
Validates that each delegation uses the correct model/provider per role:
  - Reasoning  → agents-a1-abliterated (custom:local, :8102)
  - Coding     → nex-n2-mini           (custom:local, :8101)
  - Simulation → agentworld            (custom:local, :8103)

Blocks invalid delegations BEFORE the subagent spawns, returning
a structured error the orchestrator can understand and correct.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Routing Table ──────────────────────────────────────────────────────────

ROUTING: Dict[str, Dict[str, Any]] = {
    "reasoning": {
        "model": "agents-a1-abliterated",
        "provider": "custom:local",
        "port": 8102,
        "benchmarks": "GAIA 96, IFEval 94.8, IFBench 80.6",
        "aliases": {"agents-a1-abliterated", "agents-a1", "qwen3.6-35b"},
    },
    "coding": {
        "model": "nex-n2-mini",
        "provider": "custom:local",
        "port": 8101,
        "benchmarks": "SWE-Bench 74.4, Terminal-Bench 60.7",
        "aliases": {"nex-n2-mini", "nex"},
    },
    "simulation": {
        "model": "agentworld",
        "provider": "custom:local",
        "port": 8103,
        "benchmarks": "AgentWorldBench 56.39",
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
    """Allow disabling via env var for emergencies."""
    return os.environ.get("PLAN3_ROUTING_DISABLE", "").lower() in {"1", "true", "yes", "on"}


def _warn_only_mode() -> bool:
    """Warn but don't block — for gradual rollout."""
    return os.environ.get("PLAN3_ROUTING_WARN_ONLY", "").lower() in {"1", "true", "yes", "on"}


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
        "refactor", "рефактор", "strategy", "стратег", "mcts",
        "orchestrat", "оркестр", "coordinat", "координац",
        "phase", "фаза", "requirements", "constraint", "ограничен",
        "findings", "find", "найт", "search", "поиск",
    ],
    "coding": [
        "code", "код", "implement", "реализ", "develop", "разработ",
        "build", "сборк", "deploy", "деплой", "развёрт", "test",
        "тест", "debug", "отлад", "fix", "исправ", "patch", "патч",
        "terminal", "терминал", "shell", "bash", "script", "скрипт",
        "commit", "коммит", "merge", "слиян", "pull request", "PR",
        "compile", "компил", "devops", "ci/cd", "integrat", "интеграц",
        "security", "безопасност", "sast", "bandit", "semgrep",
        "install", "установ", "package", "пакет", "dependency", "зависим",
        "docker", "container", "контейнер", "write", "напиши", "создай",
        "create", "add", "добав", "remove", "удал",
    ],
    "simulation": [
        "simulat", "симул", "agentworld", "rl", "reinforcement",
        "environment", "сред", "adversar", "противник",
        "scenario", "сценар", "world model", "world-model",
        "agent behavior", "поведен", "принятие решений",
    ],
}


def classify_role(goal: str) -> Tuple[str, float]:
    """Determine whether a delegation goal is reasoning, coding, or simulation."""
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
    confidence = scores[best] / total if total > 0 else 0.0
    return (best, confidence)


# ── Validation ─────────────────────────────────────────────────────────────


def _normalize_provider(provider: str) -> str:
    """Strip custom: prefix for comparison."""
    return provider.replace("custom:", "").replace("provider:", "")


def _is_cloud(provider: str) -> bool:
    provider_lower = _normalize_provider(provider).lower()
    return any(c in provider_lower for c in CLOUD_INDICATORS)


def _is_forbidden(model: str) -> bool:
    return any(f in model.lower() for f in FORBIDDEN_MODEL_SUBSTRINGS)


def _model_matches(model: str, expected: Dict[str, Any]) -> bool:
    """Check if model matches expected, including aliases."""
    if model == expected["model"]:
        return True
    return model in expected.get("aliases", set())


def validate_delegation(
    model: str,
    provider: str,
    goal: Optional[str] = None,
    role: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    """Validate model/provider against plan3 routing.

    Returns (is_valid, block_message_or_None).
    """
    # Auto-classify
    if role is None and goal:
        role, confidence = classify_role(goal)
        if confidence < 0.3:
            # Very low confidence — treat as reasoning but with warning
            pass
    elif role is None:
        role = "reasoning"

    if role not in ROUTING:
        return (
            False,
            f"❌ PLAN3 ROUTING: Unknown role '{role}'. "
            f"Valid roles: {', '.join(ROUTING.keys())}. "
            f"Available models: agents-a1-abliterated (reasoning :8102), "
            f"nex-n2-mini (coding :8101), agentworld (simulation :8103).",
        )

    expected = ROUTING[role]
    errors: List[str] = []

    # Cloud check
    if _is_cloud(provider):
        errors.append(
            f"🚫 CLOUD PROVIDER '{provider}' — plan3 requires LOCAL models only."
        )

    # Forbidden check
    if _is_forbidden(model):
        errors.append(
            f"🚫 FORBIDDEN MODEL '{model}' — excluded from ALL plan3 roles."
        )

    # Model check
    if not _model_matches(model, expected):
        errors.append(
            f"🔀 WRONG MODEL: '{model}' for {role} role. "
            f"Expected: '{expected['model']}' "
            f"(port :{expected['port']}, {expected['benchmarks']})"
        )

    # Provider check (skip if already flagged as cloud)
    if not _is_cloud(provider) and _normalize_provider(provider) != _normalize_provider(expected["provider"]):
        errors.append(
            f"🔀 WRONG PROVIDER: '{provider}' for {role} role. "
            f"Expected: '{expected['provider']}'"
        )

    if not errors:
        return (True, None)

    # Build block message
    block_msg = (
        f"╔══════════════════════════════════════════════════════════════╗\n"
        f"║  PLAN3 ROUTING ENFORCER — DELEGATION BLOCKED               ║\n"
        f"╠══════════════════════════════════════════════════════════════╣\n"
    )
    for err in errors:
        block_msg += f"║  {err}\n"
    block_msg += (
        f"╠══════════════════════════════════════════════════════════════╣\n"
        f"║  FIX: delegate_task(model='{expected['model']}',            ║\n"
        f"║       provider='{expected['provider']}', role='...')       ║\n"
        f"╠══════════════════════════════════════════════════════════════╣\n"
        f"║  Model routing (plan3):                                     ║\n"
        f"║    Reasoning  → agents-a1-abliterated :8102                ║\n"
        f"║    Coding     → nex-n2-mini           :8101                ║\n"
        f"║    Simulation → agentworld            :8103                ║\n"
        f"╚══════════════════════════════════════════════════════════════╝"
    )

    return (False, block_msg)


# ── Hook Implementation ────────────────────────────────────────────────────


def _on_pre_tool_call(
    tool_name: str,
    args: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> Optional[Dict[str, str]]:
    """pre_tool_call hook — intercept delegate_task and validate routing.

    Returns {"action": "block", "message": "..."} to block the call,
    or None to allow it.
    """
    if _plugin_disabled():
        return None

    # Only intercept delegate_task (single and batch modes)
    if tool_name != "delegate_task":
        return None

    if not isinstance(args, dict):
        return None

    warn_only = _warn_only_mode()

    # ── Check single-task mode ──
    goal = args.get("goal", "")
    model = args.get("model", "")
    provider = args.get("provider", "")

    if goal and (model or provider):
        # Only validate if model/provider explicitly set
        valid, block_msg = validate_delegation(
            model=model,
            provider=provider,
            goal=goal,
        )
        if not valid:
            if warn_only:
                logger.warning("PLAN3 ROUTING (WARN): %s", block_msg.replace("\n", " "))
                return None
            return {"action": "block", "message": block_msg}

    # ── Check batch mode ──
    tasks = args.get("tasks", [])
    if isinstance(tasks, list):
        for i, task in enumerate(tasks):
            if not isinstance(task, dict):
                continue
            t_goal = task.get("goal", "")
            t_model = task.get("model", "")
            t_provider = task.get("provider", "")

            if t_goal and (t_model or t_provider):
                valid, block_msg = validate_delegation(
                    model=t_model,
                    provider=t_provider,
                    goal=t_goal,
                )
                if not valid:
                    indexed_msg = f"[Batch task #{i}] {block_msg}"
                    if warn_only:
                        logger.warning("PLAN3 ROUTING (WARN): %s", indexed_msg.replace("\n", " "))
                        continue
                    return {"action": "block", "message": indexed_msg}

    return None


# ── Plugin Registration ────────────────────────────────────────────────────


def register(ctx) -> None:
    """Register the pre_tool_call hook with Hermes plugin system."""
    if _plugin_disabled():
        logger.info("plan3-routing-enforcer: disabled via PLAN3_ROUTING_DISABLE")
        return

    ctx.register_hook("pre_tool_call", _on_pre_tool_call)
    logger.info(
        "plan3-routing-enforcer: registered pre_tool_call hook "
        "(mode: %s)",
        "warn-only" if _warn_only_mode() else "block",
    )
