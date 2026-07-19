"""
Clarify Gate Plugin — two-layer enforcement of mandatory clarify().

Layer 1 (pre_llm_call): Sees the user's original message. If ambiguous,
    injects a hard instruction forcing clarify() as the first action.

Layer 2 (pre_tool_call): Blocks action tools (web_search, terminal, etc.)
    if clarify() wasn't called yet for this session's turn.

Both layers reset after clarify() is called, allowing normal execution.
"""

from typing import Any

# ═══════════════════════════════════════════════════════════════
# Ambiguity detection
# ═══════════════════════════════════════════════════════════════

AMBIGUOUS_TERMS: dict[str, list[str]] = {
    "mattermost": ["server", "desktop client"],
    "установи": ["docker", "binary/pkg", "snap/flatpak", "source build"],
    "установить": ["docker", "binary/pkg", "snap/flatpak", "source build"],
    "почини": ["code bug", "config", "data", "process/infra"],
    "починить": ["code bug", "config", "data", "process/infra"],
    "настрой": ["linux host", "docker", "android", "vps"],
    "настроить": ["linux host", "docker", "android", "vps"],
    "скачай": ["binary", "docker image", "appimage", "snap"],
    "скачать": ["binary", "docker image", "appimage", "snap"],
    "запусти": ["native binary", "docker container", "systemd service"],
    "запустить": ["native binary", "docker container", "systemd service"],
    "deploy": ["docker", "kubernetes", "bare metal", "serverless"],
    "собери": ["docker build", "native compile", "pip/package"],
    "подключи": ["usb", "network", "bluetooth", "adb"],
    "добавь": ["code", "config", "database", "memory/skill"],
}

AMBIGUOUS_PRODUCTS: dict[str, str] = {
    "mattermost": "Mattermost SERVER (self-hosted) or DESKTOP client?",
    # "hermes" removed — too broad for daily Hermes development work
    "postgres": "PostgreSQL SERVER or just psql CLIENT?",
    "postgresql": "PostgreSQL SERVER or just psql CLIENT?",
    "redis": "Redis SERVER or just redis-cli?",
    "nginx": "nginx as reverse proxy or static file server?",
    "opencode": "OpenCode+ (local) or OpenCode CLI?",
}


def _detect(user_message: str) -> str | None:
    text = user_message.lower()
    for product, question in AMBIGUOUS_PRODUCTS.items():
        if product in text:
            return question
    for verb, interpretations in AMBIGUOUS_TERMS.items():
        if verb in text and len(interpretations) >= 2:
            variants = ", ".join(interpretations[:4])
            return f"'{verb}' means: {variants}. Which one?"
    return None


# ═══════════════════════════════════════════════════════════════
# Session state
# ═══════════════════════════════════════════════════════════════

READ_ONLY = frozenset({
    "read_file", "search_files", "glob", "list", "skill_view",
    "skills_list", "memory", "session_search", "clarify",
})

ACTION_TOOLS = frozenset({
    "web_search", "web_extract", "browser_navigate", "browser_click",
    "terminal", "execute_code", "write_file", "patch", "delegate_task",
    "image_generate", "cronjob",
})


class _State:
    def __init__(self):
        self.needs_clarify: str | None = None
        self.clarified: bool = False


_sessions: dict[str, _State] = {}


def _get(session_id: str) -> _State:
    s = _sessions.get(session_id)
    if s is None:
        s = _State()
        _sessions[session_id] = s
    return s


# ═══════════════════════════════════════════════════════════════
# Layer 1: pre_llm_call
# ═══════════════════════════════════════════════════════════════

def _pre_llm(**kwargs: Any) -> str | dict | None:
    user_message = str(kwargs.get("user_message", ""))
    session_id = str(kwargs.get("session_id", ""))
    is_first_turn = bool(kwargs.get("is_first_turn", False))

    if not user_message or not session_id:
        return None

    state = _get(session_id)

    if is_first_turn:
        state.clarified = False
        state.needs_clarify = None
    elif state.clarified:
        return None

    if state.needs_clarify:
        return None

    question = _detect(user_message)
    if not question:
        return None

    state.needs_clarify = question
    return {
        "context": (
            "## ⛔ MANDATORY — CLARIFY FIRST\n\n"
            f"The user's request is ambiguous: **{question}**\n\n"
            "Your FIRST and ONLY action this turn MUST be to call "
            "`clarify()` with structured choices for each interpretation. "
            "Do NOT call any other tools until the user answers.\n\n"
            "After receiving the answer, load `graph-of-thoughts` skill "
            "and build a GoT before executing."
        )
    }


# ═══════════════════════════════════════════════════════════════
# Layer 2: pre_tool_call
# ═══════════════════════════════════════════════════════════════

def _pre_tool(**kwargs: Any) -> dict | None:
    tool_name = str(kwargs.get("tool_name", ""))
    session_id = str(kwargs.get("session_id", ""))

    if not session_id:
        return None

    state = _get(session_id)

    if tool_name == "clarify":
        state.clarified = True
        state.needs_clarify = None
        return None

    if state.clarified:
        return None

    if not state.needs_clarify:
        return None

    if tool_name in READ_ONLY:
        return None

    if tool_name not in ACTION_TOOLS:
        return None

    return {
        "action": "block",
        "message": (
            f"⛔ AMBIGUITY NOT RESOLVED\n\n"
            f"{state.needs_clarify}\n\n"
            f"Call `clarify()` with structured choices FIRST."
        ),
    }


# ═══════════════════════════════════════════════════════════════
# Entry point — called by plugin loader
# ═══════════════════════════════════════════════════════════════

def register(ctx: Any) -> None:
    ctx.register_hook("pre_llm_call", _pre_llm)
    ctx.register_hook("pre_tool_call", _pre_tool)
