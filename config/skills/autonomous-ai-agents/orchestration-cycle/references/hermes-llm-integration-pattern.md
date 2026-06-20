# Hermes LLM Integration Pattern

> When a P0 feature needs LLM access from a component that doesn't have a direct AIAgent reference.

## Pattern

1. **Import the auxiliary client** in the component that needs LLM access:
```python
from agent.auxiliary_client import call_llm as _aux_call_llm
```

2. **Add a fail-open LLM method** with `hasattr` discovery:
```python
def _call_consolidation_llm(self, prompt: str) -> Optional[str]:
    try:
        response = _aux_call_llm(
            task="compression",          # reuse task config from Hermes config
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,              # budget for output tokens
            timeout=30.0,
        )
        return response.choices[0].message.content
    except Exception:
        return None                      # fail-open → caller gets placeholder
```

3. **Caller discovers via `hasattr`** (no hard dependency):
```python
if hasattr(self._mm, "_call_consolidation_llm"):
    return self._mm._call_consolidation_llm(prompt)
return self._build_placeholder_summary(prompt)  # graceful degradation
```

## Why this works

- `task="compression"` reads `provider`/`model` from `~/.hermes/config.yaml` — zero new config
- `timeout=30.0` prevents hanging the consolidation daemon thread
- `max_tokens=800` ≈ 2000 characters output — fits structured summaries
- Fail-open: error → `None` → structured placeholder with actual message stats

## Tested

DeepSeek V4 Pro, 9.4s call time for a 3-message session summary. 24 integration tests pass.

## Pitfall

`conversation_compression.py` (785 lines) already has a full LLM summarization pipeline with `AuxiliaryClient`, retry, and model fallback. If you're building something that overlaps with compression, extend that instead of building a parallel LLM path — otherwise the same session gets summarized twice.
