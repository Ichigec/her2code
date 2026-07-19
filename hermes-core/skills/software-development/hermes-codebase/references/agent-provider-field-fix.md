# AgentDef provider field fix — verification (2026-07-10)

## Bug

`AgentDef` had no `provider` field. `/agent plan3` with `provider: custom:local`
in frontmatter silently failed to switch providers — TypeError swallowed.

## Fix applied (4 patches to `agent/agents.py`)

| # | Line(s) | Change |
|---|---------|--------|
| 1 | 44 | Added `provider: Optional[str] = None` to `AgentDef` dataclass |
| 2 | 330 | Added `"provider"` to `_FRONTMATTER_FIELDS` set |
| 3 | 356 | `_coerce_agent_def` reads `data.get("provider")` |
| 4 | 704-715 | `apply_agent` passes `new_provider=agent_def.provider or agent_obj.provider` |

## Verification (run from `~/.hermes/hermes-agent/`)

```python
python3 -c "
from agent.agents import AgentDef, _coerce_agent_def, _FRONTMATTER_FIELDS, apply_agent
from unittest.mock import MagicMock

# 1. Provider field exists
a = AgentDef(id='test', model='m1', provider='p1')
assert a.provider == 'p1', f'Expected p1, got {a.provider}'

# 2. Frontmatter whitelist includes provider
assert 'provider' in _FRONTMATTER_FIELDS

# 3. _coerce_agent_def parses provider
import yaml
fm = yaml.safe_load('model: agents-a1-abliterated\nprovider: custom:local')
d = _coerce_agent_def('test', fm)
assert d.provider == 'custom:local'

# 4. apply_agent calls switch_model with both args
class MockAgent:
    model = 'deepseek-v4-pro'
    provider = 'deepseek'
    switch_model = MagicMock()
    ephemeral_system_prompt = ''
    toolsets = []
    reasoning_config = {}

agent_obj = MockAgent()
summary = apply_agent(agent_obj, d)
kwargs = agent_obj.switch_model.call_args.kwargs
assert kwargs['new_model'] == 'agents-a1-abliterated'
assert kwargs['new_provider'] == 'custom:local'
assert summary.get('provider') == 'custom:local'
print('ALL CHECKS PASSED')
"
```

## Key insight

`switch_model(self, new_model, new_provider, api_key='', base_url='', api_mode='')`
— `new_provider` is a REQUIRED positional arg (no default). Calling without it
raises `TypeError`, not `AttributeError` as previously documented.
