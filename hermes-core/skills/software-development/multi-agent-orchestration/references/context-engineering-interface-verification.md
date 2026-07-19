# Context Engineering Stack + Interface Compatibility Verification

P1 deep dive from Tech Lead v4 research (2026-07-03). Two improvements prioritized
as P1 (High impact, Low-Medium effort, Low risk). Both are reinforcing: better context
→ less drift → tighter contracts → fewer interface bugs.

## Part 1: Context Engineering Stack

### Problem

Current system delivers ~60KB context to each developer agent, of which ~42% is noise
(irrelevant artifacts from other phases). Anthropic 2026: each 1KB irrelevant context
→ ~2% drop in code task accuracy. 25KB noise → ~50% accuracy degradation.

### Architecture (5 components)

```
PRODUCER → REGISTRY → CONSUMER
    │          │          │
    ▼          ▼          ▼
COMPACTOR   ROUTER     BUDGET
    │          │          │
    └──────────┼──────────┘
               ▼
           AUDITOR
```

### 1. Registry (artifact registration with relevance mapping)

Every artifact registered with metadata + `relevance_to` mapping:

```json
{
  "artifacts": [
    {
      "id": "arch-doc",
      "type": "static",
      "sections": [
        {"id": "overview", "tokens": 300},
        {"id": "parser-module", "tokens": 500}
      ],
      "relevance_to": {
        "SW#3": ["overview", "parser-module"],
        "SW#2": ["overview", "test-infra"]
      }
    },
    {
      "id": "sw2-test-results",
      "type": "dynamic",
      "relevance_to": {"SW#3": false, "SW#4": true}
    }
  ]
}
```

### 2. Router (deliver only relevant context per agent role)

```python
def build_context(sw_id, role, registry, dag):
    deps = dag.get_dependencies(sw_id)  # only dependency handoffs

    if role == "jidoka":
        # Jidoka: NO handoffs, NO kaizen, NO navigator
        # ONLY: acceptance criteria + code files + interface contracts
        return {"acceptance": ..., "code": ..., "interfaces": ...}

    if role == "reviewer":
        # Reviewer: NO navigator, NO handoffs
        # ONLY: StandardWork + code + acceptance criteria
        return {"sw": ..., "code": ..., "acceptance": ...}

    # Developer: full but filtered by section + dependencies
    return {
        "static": filter_sections(arch_doc, arch_doc.relevance_to[sw_id]),
        "dynamic": [get_handoff(d) for d in deps],
        "episodic": compact(navigator_bundle, target=1500),
        "semantic": query_neo4j_interfaces(sw_id),
        "task": dag.get(sw_id)
    }
```

| Agent | Before (v2) | After (v4) | Reduction |
|-------|:-----------:|:----------:|:---------:|
| Developer | ~60KB, 42% noise | ~35KB, <5% noise | -42% tokens |
| Jidoka | ~45KB, 60% noise | ~12KB, <5% noise | -73% tokens |
| Reviewer | ~40KB, 50% noise | ~15KB, <5% noise | -63% tokens |

### 3. Compactor (3 strategies, applied in order)

1. **Section filtering** (free): extract only relevant sections from large docs
2. **Summarization** (LLM, once): compress Navigator bundles — keep paths +
   signatures, drop full code snippets. Target: 3800→1500 tokens.
3. **Eviction** (after phase): remove intermediate code versions (keep final +
   diff), replace raw test output with summary, replace Navigator bundle with
   key insights only.

### 4. Budget Enforcer

| Agent | Total budget | Static | Dynamic | Episodic | Semantic |
|-------|:-----------:|:------:|:-------:|:--------:|:--------:|
| Developer | 50K | 5K | 15K | 25K | 5K |
| Jidoka | 30K | 3K | 10K | 15K | 2K |
| Reviewer | 20K | 2K | 8K | 8K | 2K |
| Tech Lead | 100K | 10K | 40K | 30K | 20K |

If over budget: compact largest episodic → drop semantic → compact dynamic.

### 5. Auditor (post-task context quality check)

After each StandardWork, audit:
- Noise estimate > 10%? → recommend tighter routing
- FAIL + context < 10K? → context may be too sparse
- FAIL + context > 80K? → attention diluted, compact more

### Implementation in techlead-agent.md

Add after StandardWork creation (Step 4.5):
- Register artifacts with `relevance_to` mapping in context.json
- Build per-role context bundles (developer/jidoka/reviewer get different slices)
- Enforce budget per role
- Post-task audit → update registry (evict intermediate, keep summary)

## Part 2: Interface Compatibility Verification

### Problem

Current Jidoka checks imports via `grep`. This catches syntax but misses semantics:

| grep finds | grep MISSES |
|------------|-------------|
| `from parser import Parser` ✅ | `Parser.parse(str)` vs `Parser.parse(bytes)` ❌ |
| `import parser` ✅ | `Parser` missing `validate()` method ❌ |
| `parser.Parser` mentioned ✅ | `parse()` returns `dict` not `ParsedDocument` ❌ |
| | Import succeeds but Protocol conformance fails ❌ |
| | Circular import at runtime ❌ |

### 3-Level Verification

```
Level 1: IMPORT EXISTENCE (grep — current)
    "Does the import statement exist?"
         │
         ▼
Level 2: SIGNATURE COMPATIBILITY (AST analysis — NEW)
    "Does the imported symbol have the right shape?"
         │
         ▼
Level 3: RUNTIME CONFORMANCE (actual import + Protocol check — NEW)
    "Does it actually work when loaded?"
```

### Level 2: AST-based Signature Compatibility

```python
import ast
from pathlib import Path

PROTOCOL_REGISTRY = {
    "IParser": {
        "methods": {
            "parse": {
                "params": [{"name": "input", "type": "str"}],
                "returns": "ParsedDocument",
                "raises": ["ParseError"]
            },
            "validate": {
                "params": [{"name": "input", "type": "str"}],
                "returns": "bool",
                "raises": []
            }
        }
    }
}

def check_signature(file_path, class_name, protocol_name):
    """Verify class implements Protocol via AST analysis."""
    violations = []
    tree = ast.parse(Path(file_path).read_text())

    target_class = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            target_class = node
            break

    if not target_class:
        return [{"level": "FATAL", "message": f"Class '{class_name}' not found"}]

    implemented = {n.name: n for n in target_class.body
                   if isinstance(n, ast.FunctionDef)}

    for method_name, spec in PROTOCOL_REGISTRY[protocol_name]["methods"].items():
        if method_name not in implemented:
            violations.append({
                "level": "ERROR",
                "type": "method_missing",
                "message": f"{class_name}.{method_name}() — required by {protocol_name}"
            })
            continue

        method = implemented[method_name]
        # Check return type
        if method.returns:
            ret = ast.unparse(method.returns)
            if spec["returns"] not in ret:
                violations.append({
                    "level": "ERROR",
                    "type": "return_type_mismatch",
                    "message": f"{class_name}.{method_name}() returns '{ret}', "
                             f"expected '{spec['returns']}'"
                })
        # Check param count
        actual_args = [a for a in method.args.args if a.arg != "self"]
        if len(actual_args) != len(spec["params"]):
            violations.append({
                "level": "ERROR",
                "type": "param_count_mismatch",
                "message": f"{class_name}.{method_name}() takes {len(actual_args)} args, "
                         f"expected {len(spec['params'])}"
            })

    return violations
```

### Level 3: Runtime Conformance

```python
import importlib, inspect, traceback

def check_runtime_import(module_path, symbol_name):
    """Actually import the module and verify symbol exists."""
    try:
        module = importlib.import_module(module_path)
    except Exception as e:
        return {"passed": False, "errors": [f"Import failed: {type(e).__name__}: {e}"]}
    if not hasattr(module, symbol_name):
        return {"passed": False, "errors": [f"'{module_path}' has no '{symbol_name}'"]}
    return {"passed": True}

def check_runtime_call(module_path, class_name, method_name,
                        args=None, expected_return_type=None):
    """Actually call the method and verify it doesn't crash."""
    try:
        mod = importlib.import_module(module_path)
        instance = getattr(mod, class_name)()
        result = getattr(instance, method_name)(*args)
        if expected_return_type and not isinstance(result, expected_return_type):
            return {"passed": False, "errors": [
                f"Returned {type(result).__name__}, expected {expected_return_type.__name__}"
            ]}
        return {"passed": True}
    except Exception as e:
        return {"passed": False, "errors": [
            f"{class_name}.{method_name}() raised: {type(e).__name__}: {e}",
            traceback.format_exc()
        ]}
```

### StandardWork Contract Addition

Tech Lead adds `interface_checks` section to each StandardWork:

```json
{
  "interface_checks": {
    "level2_ast": [
      {
        "type": "signature",
        "file": "plugins/foo/parser.py",
        "class": "Parser",
        "protocol": "IParser"
      },
      {
        "type": "imports",
        "file": "plugins/foo/parser.py",
        "expected_imports": [
          "from plugins.foo.contracts import IParser",
          "from plugins.foo.types import ParsedDocument, ParseError"
        ]
      }
    ],
    "level3_runtime": [
      {
        "type": "import",
        "module": "plugins.foo.parser",
        "symbol": "Parser"
      },
      {
        "type": "call",
        "module": "plugins.foo.parser",
        "class": "Parser",
        "method": "parse",
        "args": ["test input string"],
        "expected_return_type": "ParsedDocument"
      }
    ]
  }
}
```

### Jidoka Integration

```markdown
### Step 1: Run AST checks (Level 2)
If AST FAIL → Jidoka verdict = FAIL, don't run runtime checks.

### Step 2: Run Runtime checks (Level 3, only if AST PASS)
If Runtime FAIL → Jidoka verdict = FAIL.

### Step 3: Verdict
- AST PASS + Runtime PASS → continue to acceptance criteria
- AST FAIL → FAIL (structural defect)
- Runtime FAIL → FAIL (behavioral defect)

### Severity mapping:
- FATAL (class missing) → FAIL, no retry
- ERROR (signature mismatch) → FAIL, retry allowed
- WARNING (annotation missing) → PASS with warning, logged for Tech Lead
```

### Comparison: Before vs After

| Failure Mode | grep (v2) | AST + Runtime (v4) |
|--------------|:---------:|:------------------:|
| Import missing | ✅ | ✅ |
| Class missing | ❌ | ✅ |
| Method missing | ❌ | ✅ |
| Return type wrong | ❌ | ✅ |
| Param count wrong | ❌ | ✅ |
| Param type wrong | ❌ | ✅ |
| Protocol not declared | ❌ | ✅ (warn) |
| Import crashes at runtime | ❌ | ✅ |
| Return type wrong at runtime | ❌ | ✅ |

### Reinforcing Effect (P1-A + P1-B together)

```
P1-A: Developer gets ONLY relevant context (interfaces, contracts)
    → less specification drift
    → Developer writes code matching contracts
    ↓
P1-B: Jidoka checks at 3 levels (AST + Protocol + Runtime)
    → catches interface bugs at Jidoka gate, not Review Swarm
    ↓
Fewer bugs reach Review Swarm
    → Reviewers get focused context → faster, more accurate reviews
    ↓
Feedback loop: fewer failures → Tech Lead updates templates faster
    ↓
Cycle N+1: even better context routing + tighter contracts
```

### Expected Impact

| Metric | v2 | v4 (P1-A + P1-B) |
|--------|:--:|:----------------:|
| Interface bugs reaching Review | ~35% | <5% |
| Developer context noise | ~42% | <5% |
| Tokens per SW (all agents) | ~145K | ~67K |
| First-attempt pass rate | ~45% | ~70% |
| False positive reviews | ~20% | <5% |

### Implementation Plan

```
Week 1: P1-B (Interface Compatibility) — standalone scripts, immediate impact
├── Create interface_checker.py + runtime_checker.py
├── Add interface_checks section to StandardWork template
├── Update jidoka-evaluator.md with Level 2+3 checks
└── Test on existing build-migration cycle (dry run)

Week 2: P1-A (Context Engineering) — needs orchestration changes
├── Create context registry schema + context.json format
├── Implement router (filter_sections, compact, evict)
├── Update techlead-agent.md with Step 4.5
├── Add budget enforcement to delegate_task calls
└── Integration test — full cycle with P1-A + P1-B
```

P1-B first because: standalone scripts, doesn't change orchestration flow, immediate
impact per SW. P1-A needs P1-B outputs (interface contracts feed context routing).
