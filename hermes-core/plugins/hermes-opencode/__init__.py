"""hermes-opencode plugin — opencode-style agents, permissions, and tools.

This plugin is the wiring layer described in the Hermes opencode-port plan:

* It ensures the opencode-parity tools (``glob``, ``list``, ``lsp``) are
  imported and registered (they self-register on import).
* It primes the declarative permission engine so plugin-declared rights
  (``plugin.yaml -> permission:``), the global ``config.yaml -> permission:``
  block, and ``model_policies:`` are all reloaded.
* It registers a ``pre_tool_call`` hook that enforces ``deny`` decisions from
  the active permission policy. This is the *update-safe* enforcement point:
  even on a Hermes install where the core ``tool_executor`` / ``approval``
  patches were lost on update, denied tools are still blocked. ``ask``
  decisions remain the responsibility of the core integration (which can run
  the interactive approval flow); the hook never silently allows.

The agent registry (``agent/agents.py``) already ships the opencode read-only
subagents ``explore`` and ``scout`` plus ``plan``/``review``/``safe`` with
read-only permission blocks, so no extra registration is needed here — the
plugin simply makes sure the engine reflects the latest config + plugin rights.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _ensure_tools_imported() -> None:
    """Import the opencode-parity tool modules so they self-register."""
    for mod in ("tools.glob_tool", "tools.list_tool", "tools.lsp_tool"):
        try:
            __import__(mod)
        except Exception as exc:  # noqa: BLE001
            logger.debug("hermes-opencode: could not import %s: %s", mod, exc)


def _prime_permissions() -> None:
    """Reload the global/model permission policy (picks up plugin rights)."""
    try:
        from agent import permissions as perms

        perms.reset_caches()
        perms.load_global_policy(force=True)
    except Exception as exc:  # noqa: BLE001
        logger.debug("hermes-opencode: permission prime failed: %s", exc)


def _on_pre_tool_call(
    tool_name: str = "",
    args: Optional[Dict[str, Any]] = None,
    **_: Any,
) -> Optional[Dict[str, str]]:
    """Enforce ``deny`` from the active permission policy (update-safe).

    Uses the active per-turn policy when the core integration published one;
    otherwise falls back to the global+model policy so plugin/config/model
    ``deny`` rules still apply. Only ``deny`` is enforced here — ``ask`` is left
    to the core approval flow so we never produce a non-interactive block for a
    rule the user wanted to be promptable.
    """
    try:
        from agent import permissions as perms

        policy = perms.get_active_policy()
        model = perms.get_active_model()
        if policy is None:
            policy = perms.get_global_policy()
            model = None
        if policy is None or policy.is_empty():
            return None
        decision = policy.evaluate(tool_name, args or {}, model=model)
        if decision == perms.DENY:
            return {
                "action": "block",
                "message": (
                    f"Tool '{tool_name}' is denied by the active permission "
                    f"policy (hermes-opencode)."
                ),
            }
    except Exception as exc:  # noqa: BLE001
        logger.debug("hermes-opencode: pre_tool_call enforcement error: %s", exc)
    return None


def register(ctx) -> None:
    _ensure_tools_imported()
    _prime_permissions()
    ctx.register_hook("pre_tool_call", _on_pre_tool_call)
    logger.debug("hermes-opencode plugin registered")
