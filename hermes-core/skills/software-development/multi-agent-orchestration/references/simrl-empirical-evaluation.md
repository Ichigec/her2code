# SimRL Empirical Evaluation — Qwen-AgentWorld Code Verification

**Date:** 2026-07-04
**Model:** SuperQwen-AgentWorld-35B-A3B-abliterated APEX I-Quality v3 (22 GB GGUF)
**Endpoint:** `http://127.0.0.1:8103/v1/chat/completions`
**Paper:** arxiv 2606.24597 (Qwen-AgentWorld: Language World Models for General Agents)

## Executive Summary

68-test empirical evaluation comparing Qwen-AgentWorld predictions to real execution.
**97% overall accuracy on single-step predictions.** Model excels at predicting exception
types, terminal output, and DevOps failure scenarios. **Fails on multi-step arithmetic**
(compounding errors). AgentWorldBench score of 56.39 uses LLM-as-judge rubric scoring
on long multi-step trajectories — single-step exact-match accuracy is significantly higher.

**Verdict:** SimRL is a useful PRE-FLIGHT CHECK for code verification, but NOT a
VERIFICATION GATE. Always follow SimRL predictions with real execution.

---

## AgentWorldBench Per-Domain Scores (35B-A3B)

From arxiv 2606.24597 Table 5 + HuggingFace model card:

| Domain | Samples | Avg Turns | Score | Assessment |
|--------|:-------:|:---------:|:-----:|------------|
| MCP | 286 | 23.1 | 64.79 | Good — API/tool responses |
| Search | 458 | — | **36.69** | Weakest — dynamic web content |
| Terminal | 354 | 26.7 | 53.96 | Mid-range — shell output, FS state |
| SWE | 472 | 28.1 | 65.63 | Strong — git diffs, test results, compilation |
| Android | 200 | — | 58.17 | Mid-range — UI hierarchy changes |
| Web | 200 | 14.2 | 49.55 | Weak — DOM state changes |
| OS | 200 | — | 65.92 | Strongest — desktop OS interactions |
| **Overall** | ~2,170 | — | **56.39** | |

### Scoring methodology

5 dimensions, each scored 1-5 by LLM-as-judge (GPT-5.2), normalized to 0-100:
1. **Format** — structural conformance to expected environment output format
2. **Factuality** — factual details in prediction are correct
3. **Consistency** — prediction consistent with interaction history
4. **Realism** — prediction reflects realistic environment behavior
5. **Quality** — overall simulation quality

Also uses "rule-based verifiers for deterministic checks on targeted simulation capabilities"
(paper does not detail what specific capabilities are deterministically checked).

### Critical caveats from HuggingFace discussions

1. **Hallucination exploit risk:** "At 50% fidelity the agent doesn't learn real environment
   dynamics — it learns to EXPLOIT the simulator's hallucination patterns."
2. **Noise for RL:** "An arbitrarily hallucinating one is just noise for RL."
3. **Benchmark self-evaluation:** Team built both the model AND the benchmark.
4. **No exact-match published:** Rubric scoring measures "plausibility" not "correctness."

---

## Empirical Test Results

### Test methodology

- Query model via OpenAI-compatible API at `http://127.0.0.1:8103/v1/chat/completions`
- Temperature: 0 (deterministic)
- Compare predictions to real execution (subprocess.run for code, shell for commands)
- Exact-match comparison for stdout/exit codes
- Exception type + message match for error cases
- False negative verification: re-run "failed" tests to check test correctness

### Category 1: Terminal (basic) — 8/8 (100%)

| Test | Command | Exit ✓ | Stdout ✓ | Notes |
|------|---------|:------:|:--------:|-------|
| echo | `echo 'Hello World'` | ✓ | ✓ | |
| arithmetic | `echo $((2 + 3 * 4))` | ✓ | ✓ | |
| ls nonexistent | `ls /nonexistent_dir_xyz` | ✓ | ✓ | Predicted English error; test had Russian locale (false negative, corrected) |
| pipe+grep | `echo -e 'apple\nbanana\ncherry' \| grep 'an'` | ✓ | ✓ | |
| exit code | `false; echo $?` | ✓ | ✓ | |
| find with permission | `find /root -maxdepth 1 -name '*.txt' 2>&1 \| head -3` | ✓ | — | Model predicted "Permission denied" (English); system had Russian locale |
| python one-liner | `python3 -c "print(sorted([3,1,2]))"` | ✓ | ✓ | |
| env var expansion | `FOO=bar; echo ${FOO}_suffix` | ✓ | ✓ | |

### Category 2: SWE (exceptions) — 15/15 (100%)

| Test | Code | Result ✓ | Exc Type ✓ | Exc Msg ✓ |
|------|------|:--------:|:----------:|:---------:|
| simple print | `print('hello')` | ✓ | N/A | N/A |
| zero division | `x = 10 / 0` | ✓ | ✓ | ✓ |
| key error | `d['b']` | ✓ | ✓ | ✓ |
| index error | `lst[10]` | ✓ | ✓ | ✓ |
| name error | `print(undefined_variable)` | ✓ | ✓ | ✓ |
| import error | `import nonexistent_module_xyz` | ✓ | ✓ | ✓ |
| type error | `'hello' + 5` | ✓ | ✓ | ✓ |
| list comprehension | `[x**2 for x in range(5)]` | ✓ | N/A | N/A |
| string method | `'  Hello World  '.strip().upper()` | ✓ | N/A | N/A |
| json parse error | `json.loads('{invalid json}')` | ✓ | ✓ | ✓ |
| attribute error | `s.append('!')` on str | ✓ | ✓ | ✓ |
| recursion | `def f(n): return f(n-1)` | ✓ | ✓ | ✓ |
| assertion | `assert 1 == 2` | ✓ | ✓ | ✓ |
| dict operations | defaultdict accumulation | ✓ | N/A | N/A |
| file not found | `open('/tmp/nonexistent.txt')` | ✓ | ✓ | ✓ |

### Category 3: Filesystem — 6/6 (100%)

| Test | Scenario | Match |
|------|----------|:-----:|
| mkdir + touch + ls | Create dir, files, list | ✓ |
| mv overwrite | mv a→b, cat b, ls a | ✓ (false negative corrected — test expected wrong value) |
| chmod + execute | Make script executable, run | ✓ |
| rm -rf | Remove dir tree, ls result | ✓ |
| symlink | Create symlink, cat, rm target, cat again | ✓ |
| disk space | df -h / format prediction | ✓ |

### Category 4: Web/API — 6/6 (100%)

| Test | Scenario | Match |
|------|----------|:-----:|
| GET 404 | HTTP status prediction | ✓ |
| GET JSON | httpbin.org/get?name=test response structure | ✓ |
| POST JSON | httpbin.org/post with JSON body | ✓ |
| connection refused | localhost:9999 with no service | ✓ |
| redirect | httpbin.org/redirect/3 behavior | ✓ |
| DNS failure | nonexistent domain resolution error | ✓ |

### Category 5: Hard SWE Edge Cases — 12/12 (100%)

| Test | Code Pattern | Match |
|------|-------------|:-----:|
| float precision | `0.1 + 0.2` → 0.30000000000000004 | ✓ |
| integer overflow | `2**100` (Python big int) | ✓ |
| is vs == | `a == b` True, `a is b` False | ✓ |
| mutable default arg | `def f(x=[])` — accumulates across calls | ✓ |
| string formatting | f-string with variable | ✓ |
| dict ordering | Insertion order preservation (Python 3.7+) | ✓ |
| generator exhaustion | `list(g)` twice → second is empty | ✓ |
| walrus operator | `(n := 10) > 5` | ✓ |
| try/except/finally | ValueError caught, finally runs | ✓ |
| class inheritance | B inherits A, calls A's method | ✓ |
| closure capture | Late binding in loop → all return last value | ✓ |
| global vs local | Function modifies local, global unchanged | ✓ |

### Category 6: Multi-step State Tracking — 6/7 (86%)

| Test | Code | Match | Notes |
|------|------|:-----:|-------|
| ❌ counter through list | 8-step alternating add/subtract | ✗ | **GENUINE FAILURE** — predicted 2 (step-2 value) instead of -3 (step-8 value). Classic compounding error. |
| ✅ dict accumulation | defaultdict(list) with grouped words | ✓ | |
| ✅ class state mutation | BankAccount deposit/withdraw/exception | ✓ | |
| ✅ recursive fibonacci | fib(0..9) | ✓ | |
| ✅ stateful iterator | Counter class, list() twice | ✓ | |
| ✅ exception in loop | RuntimeError at i=2, continue | ✓ | |
| ✅ nested data structure | Dict with lists, computed avg/max | ✓ | |

### Category 7: Real-world Code — 7/8 (88%)

| Test | Code | Match | Notes |
|------|------|:-----:|-------|
| ✅ regex match groups | re.findall with date pattern | ✓ | |
| ✅ json nested access | Deep dict navigation | ✓ | |
| ✅ sorted with key | Lambda key sort | ✓ | |
| ✅ os path join | path join/dirname/basename | ✓ | |
| ✅ subprocess simulation | subprocess.run echo | ✓ | |
| ✅ threading race | Lock-protected counter = 2000 | ✓ | |
| ❌ unittest structure | Test class with pass/fail methods | ✗ | False negative — test code contained non-executable `print('Predict: ...')` that confused model |
| ✅ SQL injection | admin'-- bypasses password check | ✓ | |

### Category 8: DevOps/Deployment — 6/6 (100%)

| Test | Scenario | Match |
|------|----------|:-----:|
| docker build fail | pip install nonexistent package | ✓ |
| port conflict | Port 8080 in use | ✓ |
| git merge conflict | Overlapping line changes | ✓ |
| env var missing | os.environ['API_KEY'] not set | ✓ |
| pip install version | django==99.99.99 | ✓ |
| systemd service | ExecStart script doesn't exist | ✓ |

---

## False Negative Analysis

3 of 4 test "failures" were false negatives (test bugs, not model bugs):

1. **find with permission (Terminal):** Model predicted `find: '/root': Permission denied`
   (English). Test system had Russian locale: `find: '/root': Отказано в доступе`.
   **Lesson:** Always set `LANG=en_US.UTF-8` when comparing against English predictions.

2. **mv overwrite (Filesystem):** Model predicted `cat b.txt` → "hello" and `ls a.txt`
   → "cannot access". Both CORRECT — `mv a.txt b.txt` overwrites b with a's content ("hello").
   Test expected "world" (b's original content) — test was wrong.

3. **unittest structure (Real-world):** Test code contained `print('Predict: which tests
   pass and which fail?')` — not executable Python, just a comment disguised as code.
   Model tried to execute it and got confused.

**Rule:** When a model "fails" a test, verify test correctness FIRST:
- Run the real code yourself
- Check locale/environment matches prediction assumptions
- Ensure test code is actually executable as written

---

## Qwen-AgentWorld Architecture (from arxiv 2606.24597)

### Training pipeline

```
CPT (10M+ trajectories from 7 domains) → SFT (next-state CoT) → RL (hybrid rubric+rule rewards)
```

- **CPT:** Continual Pre-Training on 10M+ real environment interaction trajectories from
  containerized sandboxes, MCP servers, Android/web/OS emulators
- **SFT:** Supervised Fine-Tuning to activate long chain-of-thought next-state prediction
- **RL:** Reinforcement Learning with hybrid rubric-and-rule rewards for simulation fidelity

### Seven domains

MCP, Search, Terminal, SWE, Android, Web, OS — unified under shared textual representation.
GUI domains (Android, Web, OS) use accessibility trees and UI view hierarchies, not pixels.

### Two application paradigms

1. **Decoupled (Sim RL):** World model as standalone environment simulator for agent training
2. **Unify (Agent Warm-Up):** World-model training as pre-training for agents (+8.66 over base)

### Key paper claim vs evidence

| Claim | Evidence | Verdict |
|-------|----------|---------|
| "Simulates 7 environments in one model" | Confirmed — single model, 7 domains | Supported |
| "Beats GPT-5.4 on AgentWorldBench" | 397B: 58.71 vs 58.25 — on own benchmark | Technically true |
| "Gains surpass real-environment training alone" | Measured only on benchmark scores | Partially supported |
| "Can accurately simulate terminal outputs" | Our tests: 100% single-step, 86% multi-step | Plausible for single-step |
| "Can replace real execution" | Paper does NOT claim this | Not claimed |

---

## Sim-to-Real Gap: RL Literature Consensus

From broader RL literature (arxiv 2502.13187, 2604.22748):

1. **Sim-to-real gap is structural, not incidental** — simulation may systematically miss
   behaviors that only emerge in real execution
2. **Compounding errors** — "even minor quantization noise or pruning-induced degradation
   can lead to severe semantic drift over long horizons"
3. **LLM-based code verification** — "far from strong enough for mission-critical applications"
4. **World models help with policy evaluation** but "smaller discrepancies between real and
   simulated success rates" still exist

---

## Testing Methodology (Reusable)

### Test framework pattern

```python
import json, subprocess, time, requests

URL = "http://127.0.0.1:8103/v1/chat/completions"

def query_model(system, user, max_tokens=500):
    payload = {
        "model": "agentworld",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ],
        "max_tokens": max_tokens,
        "temperature": 0,  # deterministic
    }
    resp = requests.post(URL, json=payload, timeout=60)
    return resp.json()["choices"][0]["message"]["content"]

# For each test:
# 1. Query model for prediction
# 2. Run real code via subprocess
# 3. Compare prediction to reality (exact-match for stdout, type+message for exceptions)
# 4. If "failure" — verify test correctness before declaring model failure
```

### System prompts that work

**Terminal:**
```
You are a terminal environment simulator. Predict the EXACT output of bash commands
without executing them. Format: EXIT_CODE, STDOUT, STDERR.
```

**SWE:**
```
You are a software engineering environment simulator. Predict what happens when code
runs. Format: RESULT (SUCCESS/ERROR), EXIT_CODE, STDOUT, STDERR, EXCEPTION.
```

**DevOps:**
```
You are a DevOps environment simulator. Predict what happens during deployment and
infrastructure operations without actually running them.
```

### Test categories for comprehensive evaluation

1. **Terminal basic** — echo, arithmetic, ls, pipe, exit codes, env vars (8 tests)
2. **SWE exceptions** — all Python exception types + success cases (15 tests)
3. **Filesystem** — mkdir, mv, chmod, rm, symlink, df (6 tests)
4. **Web/API** — HTTP status, JSON, connection errors, DNS (6 tests)
5. **Hard SWE edge cases** — float precision, mutable defaults, closure capture, etc. (12 tests)
6. **Multi-step state** — counters, accumulators, class mutation, recursion (7 tests)
7. **Real-world code** — regex, json, sorting, subprocess, threading, security (8 tests)
8. **DevOps** — docker, ports, git, systemd, pip, env vars (6 tests)

Total: 68 tests, ~3-7 seconds per test, ~5 minutes total runtime.

---

## Practical Testing Notes (from note.com guide)

- **Teacher forcing prevents error accumulation:** Reload real output into history after
  each prediction during evaluation. This measures per-command accuracy, not rollout accuracy.
- **Model is NOT a general-purpose coder:** "It is not a tool for writing code, but a
  behind-the-scenes tool that provides a 'world' for training and evaluating agents."
- **Model "goes silent and collapses outside its specialty"** — narrow specialization for
  environment simulation, not general chat/coding.
- **Serving:** SGLang or vLLM with `--reasoning-parser qwen3` and `--trust-remote-code`
  (without this flag, vLLM attempts to initialize visual modules and fails).
- **Prompt format:** Domain-specific system prompts in `prompts/` directory of the GitHub repo.
  Each domain has `system_prompt.txt` (world model) and `judge_system_prompt.txt` (evaluation).
