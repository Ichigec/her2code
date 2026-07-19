# Full /agent slash command handler for Hermes CLI
# Insert this method into the HermesCLI class in cli.py
# + add dispatch line in process_command: elif canonical == "agent": self._handle_agent_command(cmd_original)

def _handle_agent_command(self, cmd: str):
    """Handle /agent — switch agent preset (build|plan|review|safe).

    Changes enabled toolsets and reasoning effort atomically.
    Usage: /agent [build|plan|review|safe]
    """
    from hermes_cli.colors import Colors as _Colors
    _DIM = _Colors.DIM
    _BOLD = _Colors.BOLD
    _RST = _Colors.RST
    _GREEN = _Colors.GREEN

    presets = {
        "build": {
            "label": "Build",
            "toolsets": ["terminal", "file", "web", "browser", "delegation"],
            "reasoning": "high",
        },
        "plan": {
            "label": "Plan",
            "toolsets": ["web", "file", "search", "browser"],
            "reasoning": "medium",
        },
        "review": {
            "label": "Review",
            "toolsets": ["file", "terminal", "web"],
            "reasoning": "minimal",
        },
        "safe": {
            "label": "Safe",
            "toolsets": ["web", "file", "search"],
            "reasoning": "minimal",
        },
    }

    parts = cmd.strip().split(maxsplit=1)
    name = parts[1].strip().lower() if len(parts) > 1 else ""

    if not name:
        names = ", ".join(presets.keys())
        print(f"  {_DIM}Usage: /agent [{names}] — switch agent preset{_RST}")
        print(f"  {_DIM}Current toolsets: {', '.join(self.enabled_toolsets) if self.enabled_toolsets else 'all'}{_RST}")
        return

    preset = presets.get(name)
    if not preset:
        names = ", ".join(presets.keys())
        print(f"  {_DIM}✗ Unknown agent '{name}'. Available: {names}{_RST}")
        return

    # Switch toolsets
    self.enabled_toolsets = preset["toolsets"]
    if hasattr(self, "agent") and self.agent:
        self.agent.enabled_toolsets = preset["toolsets"]
        from tools.registry import get_tool_definitions
        self.agent.tools = get_tool_definitions(
            enabled_toolsets=preset["toolsets"],
            quiet_mode=getattr(self.agent, "quiet_mode", False),
        )

    # Switch reasoning
    self.reasoning_effort = preset["reasoning"]
    if hasattr(self, "agent") and self.agent:
        self.agent.reasoning_effort = preset["reasoning"]
        from hermes_constants import parse_reasoning_effort
        self.agent.reasoning_config = parse_reasoning_effort(preset["reasoning"])

    tools_str = ", ".join(preset["toolsets"])
    print(f"  {_GREEN}{_BOLD}✓ {preset['label']}{_RST}  {_DIM}tools: {tools_str}  ·  reasoning: {preset['reasoning']}{_RST}")
