# Dead References → Constraint Relaxation

When a system prompt ported from one ecosystem to another contains references
to tools/skills/paths that don't exist in the target, those constraints become
**cosmetic** — the agent sees them, tries to execute them, fails silently, and
proceeds without enforcement.

## Evidence: OpenCode+ general agent (2026-06-12)

The `general` agent in opencode+ uses a frozen Hermes v1 prompt with 20+ dead refs:

| Reference | Hermes | OpenCode reality |
|-----------|--------|-----------------|
| `skill_view("build-engineering-standards")` | Loads real skill → KISS/DRY/YAGNI enforced | No `skill_view` tool → silently fails |
| `skill_view("secure-coding")` | Loads real skill → OWASP checklist | No such tool → fails |
| `skill_view("sast-audit")` | Security gate enforced | No such tool → fails |
| `/build`, `/security` slash commands | Active commands | Not supported in OpenCode |

## Consequence: cosmetic strictness → pragmatic freedom

An agent with ALL constraints working (like Hermes general agent) will refuse
"hacky" approaches like:
- Replacing AAPT2 binary in Gradle cache
- Using socat for port forwarding
- Reading SharedPreferences through adb shell

An agent with DEAD constraints (like OpenCode+ general agent) cannot enforce
these rules because the enforcement tools don't exist. The lifecycle text is
present but the mechanics are absent.

## Lesson for prompt engineering

When comparing agent behavior across ecosystems, check whether the constraints
in the prompt are **real** (backed by existing tools) or **cosmetic** (dead
references). Two agents with identical-looking prompts can behave radically
differently depending on which tools their ecosystem provides.

When porting prompts: every tool reference that doesn't resolve in the target
ecosystem silently weakens the prompt's enforcement. Count dead references
before predicting behavior.
