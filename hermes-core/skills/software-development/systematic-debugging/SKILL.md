---
name: systematic-debugging
description: "4-phase root cause debugging: understand bugs before fixing."
version: 1.1.0
author: Hermes Agent (adapted from obra/superpowers)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [debugging, troubleshooting, problem-solving, root-cause, investigation]
    related_skills: [test-driven-development, plan, subagent-driven-development]
---

# Systematic Debugging

## Overview

Random fixes waste time and create new bugs. Quick patches mask underlying issues.

**Core principle:** ALWAYS find root cause before attempting fixes. Symptom fixes are failure.

**Violating the letter of this process is violating the spirit of debugging.**

## The Iron Law

```
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

If you haven't completed Phase 1, you cannot propose fixes.

## When to Use

Use for ANY technical issue:
- Test failures
- Bugs in production
- Unexpected behavior
- Performance problems
- Build failures
- Integration issues

**Use this ESPECIALLY when:**
- Under time pressure (emergencies make guessing tempting)
- "Just one quick fix" seems obvious
- You've already tried multiple fixes
- Previous fix didn't work
- You don't fully understand the issue

**Don't skip when:**
- Issue seems simple (simple bugs have root causes too)
- You're in a hurry (rushing guarantees rework)
- Someone wants it fixed NOW (systematic is faster than thrashing)

## The Four Phases

You MUST complete each phase before proceeding to the next.

---

## Phase 1: Root Cause Investigation

**BEFORE attempting ANY fix:**

### 1. Read Error Messages Carefully

- Don't skip past errors or warnings
- They often contain the exact solution
- Read stack traces completely
- Note line numbers, file paths, error codes

**Action:** Use `read_file` on the relevant source files. Use `search_files` to find the error string in the codebase.

**When user says "I pasted the error into the file":** The user may save terminal output (error messages, console sessions) directly INTO the script file or as temp files (e.g. `.goutputstream-*` from gedit). Check ALL files in the directory:
```bash
# Find ALL files including temp/editor artifacts
ls -la directory/.goutputstream-* directory/*.tmp directory/*.log 2>/dev/null
# Read them — they contain the actual error output
read_file path="directory/.goutputstream-XXXXX"
```
Do NOT just re-read the script and guess. The error output is on disk — go find it. The user is telling you they gave you evidence; your job is to read it.

### 2. Reproduce Consistently

- Can you trigger it reliably?
- What are the exact steps?
- Does it happen every time?
- If not reproducible → gather more data, don't guess

**Action:** Use the `terminal` tool to run the failing test or trigger the bug:

```bash
# Run specific failing test
pytest tests/test_module.py::test_name -v

# Run with verbose output
pytest tests/test_module.py -v --tb=long
```

### 3. Check Recent Changes

- What changed that could cause this?
- Git diff, recent commits
- New dependencies, config changes

**Action:**

```bash
# Recent commits
git log --oneline -10

# Uncommitted changes
git diff

# Changes in specific file
git log -p --follow src/problematic_file.py | head -100
```

### 4. Gather Evidence in Multi-Component Systems

**WHEN system has multiple components (API → service → database, CI → build → deploy):**

**BEFORE proposing fixes, add diagnostic instrumentation:**

For EACH component boundary:
- Log what data enters the component
- Log what data exits the component
- Verify environment/config propagation
- Check state at each layer

Run once to gather evidence showing WHERE it breaks.
THEN analyze evidence to identify the failing component.
THEN investigate that specific component.

**Android + Server systems (special case):**

For phone↔PC apps, instrument BOTH sides simultaneously:

```bash
# Terminal 1: Phone logs
adb logcat -c && adb logcat -s VoiceRepo:D ChatVM:D HermesGUI:D

# Terminal 2: Server health
curl -s http://localhost:8647/health  # proxy alive?
curl -s -X POST http://localhost:8647/stt --data-binary @test.ogg  # STT works?
```

**Correlation pattern:** For each failing request, match timestamps across both log streams. If phone sends request at 00:56:30 and proxy receives it at 00:56:30 → network OK. If proxy responds with 200 but phone shows empty → payload issue. If phone shows no log at all → app code not reached (build cache, permission, UI state).

**Fix ONE component at a time.** Don't change both proxy and app simultaneously — you lose the ability to isolate.

**GUI applications (Electron/Desktop/Web) — CRITICAL PITFALL:**

**`curl` tests passing ≠ GUI working.** This is the #1 deception pattern in GUI debugging. Terminal-level API tests (curl 200, WS 101) can ALL pass while the GUI is stuck at a loading screen because:

1. **GUI auth differs from curl auth.** Desktop GUI uses `connection.json` with `decryptDesktopSecret()` + `X-Hermes-Session-Token`. Curl uses `Authorization: Bearer`. They follow DIFFERENT code paths. Testing one does NOT validate the other.
2. **GUI needs ALL endpoints simultaneously.** Curl tests endpoints one at a time. GUI needs `/api/status` + `/api/sessions` + `/api/config` + `/api/ws` + `/api/skills` + `/api/profiles` ALL at once during boot. One failing endpoint (even returning 404) can hang the loading screen.
3. **GUI runs in a different environment.** Electron has display requirements, GPU access, sandboxing, and IPC between main/renderer processes. Terminal curl has none of these constraints.
4. **GUI boot is stateful.** The boot sequence has phases (24% → 95% → 99%). Each phase depends on the previous. A success at phase N doesn't guarantee phase N+1 will succeed.

**When debugging GUI loading hangs:**
- NEVER say "it works" based on curl tests alone
- Check `connection.json` format — flat structure and plain-string tokens are FATAL
- Check dashboard logs for `ModuleNotFoundError` (WebSocket handler crashes)
- Check Electron stderr for `401 Unauthorized` and `ECONNREFUSED`
- Verify with `ss -tnp | grep :PORT` that actual TCP connections exist
- ONLY declare success after the user confirms the GUI loaded past the loading screen

### 5. Trace Data Flow

**WHEN error is deep in the call stack:**

- Where does the bad value originate?
- What called this function with the bad value?
- Keep tracing upstream until you find the source
- Fix at the source, not at the symptom

**Action:** Use `search_files` to trace references:

```python
# Find where the function is called
search_files("function_name(", path="src/", file_glob="*.py")

# Find where the variable is set
search_files("variable_name\\s*=", path="src/", file_glob="*.py")
```

### Phase 1 Completion Checklist

- [ ] Error messages fully read and understood
- [ ] Issue reproduced consistently
- [ ] Recent changes identified and reviewed
- [ ] Evidence gathered (logs, state, data flow)
- [ ] Problem isolated to specific component/code
- [ ] Root cause hypothesis formed

**STOP:** Do not proceed to Phase 2 until you understand WHY it's happening.

---

## Phase 2: Pattern Analysis

**Find the pattern before fixing:**

### 1. Find Working Examples

- Locate similar working code in the same codebase
- What works that's similar to what's broken?

**Action:** Use `search_files` to find comparable patterns:

```python
search_files("similar_pattern", path="src/", file_glob="*.py")
```

### 2. Compare Against References

- If implementing a pattern, read the reference implementation COMPLETELY
- Don't skim — read every line
- Understand the pattern fully before applying

### 3. Identify Differences

- What's different between working and broken?
- List every difference, however small
- Don't assume "that can't matter"

### 4. Understand Dependencies

- What other components does this need?
- What settings, config, environment?
- What assumptions does it make?

---

## Phase 3: Hypothesis and Testing

**Scientific method:**

### 1. Form a Single Hypothesis

- State clearly: "I think X is the root cause because Y"
- Write it down
- Be specific, not vague

### 2. Test Minimally

- Make the SMALLEST possible change to test the hypothesis
- One variable at a time
- Don't fix multiple things at once

### 3. Verify Before Continuing

- Did it work? → Phase 4
- Didn't work? → Form NEW hypothesis
- DON'T add more fixes on top

### 4. When You Don't Know

- Say "I don't understand X"
- Don't pretend to know
- Ask the user for help
- Research more

---

## Phase 4: Implementation

**Fix the root cause, not the symptom:**

### 1. Create Failing Test Case

- Simplest possible reproduction
- Automated test if possible
- MUST have before fixing
- Use the `test-driven-development` skill

### 2. Implement Single Fix

- Address the root cause identified
- ONE change at a time
- No "while I'm here" improvements
- No bundled refactoring

### 3. Verify Fix

```bash
# Run the specific regression test
pytest tests/test_module.py::test_regression -v

# Run full suite — no regressions
pytest tests/ -q
```

### Verification Plan Pattern (when user asks "how will we verify?")

When the user asks for a verification plan before fixes are applied, produce
a structured table with phases. Each phase has explicit pass/fail criteria.
This is NOT optional formatting — the user expects to see the plan before
agreeing to execution ("Делай" = proceed).

```
Phase 0: Baseline — reproduce the bug (before any fix)
Phase 1: RED — write failing tests that prove the bug
Phase 2: GREEN — apply fix, tests pass
Phase 3: E2E — real integration test (not just unit tests)
Phase 4: Regression — run existing test suites, confirm 0 failures
```

Format each phase as a table:

| # | Action | Command | Pass criterion |
|---|--------|---------|----------------|
| 0.1 | Reproduce | `delegate_task(goal="pong")` | ✅ HTTP 400 reproduced |
| 1.1 | RED test | `pytest test_bug.py -v` | ❌ Fails (bug confirmed) |
| 2.1 | Apply fix | patch source file | — |
| 2.2 | GREEN test | `pytest test_bug.py -v` | ✅ Passes |
| 3.1 | E2E | `delegate_task(goal="pong")` | ✅ Returns "pong" |
| 4.1 | Regression | `pytest tests/ -q` | ✅ 0 failures |

Key principles:
- Phase 0 MUST produce evidence (logs, error output) before fixes start
- Phase 1 tests MUST fail (RED) — if they pass, the bug isn't understood
- Phase 3 E2E MUST use the real code path, not mocks
- Phase 4 regression MUST include existing tests for touched modules
- Fix files in source do NOT affect the running process — note if restart needed

### 4. If Fix Doesn't Work — The Rule of Three

- **STOP.**
- Count: How many fixes have you tried?
- If < 3: Return to Phase 1, re-analyze with new information
- **If ≥ 3: STOP and question the architecture (step 5 below)**
- DON'T attempt Fix #4 without architectural discussion

### 5. If 3+ Fixes Failed: Question Architecture

**Pattern indicating an architectural problem:**
- Each fix reveals new shared state/coupling in a different place
- Fixes require "massive refactoring" to implement
- Each fix creates new symptoms elsewhere

**STOP and question fundamentals:**
- Is this pattern fundamentally sound?
- Are we "sticking with it through sheer inertia"?
- Should we refactor the architecture vs. continue fixing symptoms?

**Discuss with the user before attempting more fixes.**

This is NOT a failed hypothesis — this is a wrong architecture.

---

## Verification-as-Ceremony (Meta-Antipattern)

**The single most dangerous verification failure:** agents find the cheapest way
to produce a "verified" signal rather than genuinely testing the artifact.

### Symptoms

- Running `bash -n` (syntax check) and declaring "script works" — `bash -n` only
  checks the parser, not runtime behavior. Line-merged files, unbound variables,
  and wrong exit codes all pass `bash -n`.
- Seeing "OK" in tool output without questioning whether the check was meaningful
  (e.g., `basename` broken by spaces → prints "One OK" 4 times instead of filenames)
- Declaring success without executing the artifact yourself — leaving the user as tester

### Root cause

Agents treat verification as a **gate to pass** (find any signal that says "OK"),
not as an **investigation to conduct** (try to break the artifact).

### Prevention: "Don't declare, demonstrate"

| Artifact type | Insufficient (ceremony) | Sufficient (investigation) |
|--------------|:---:|:---|
| Bash script | `bash -n` | `bash -x script.sh 2>&1 \| head -10` (runtime trace) |
| Python script | `ast.parse()` | `python3 script.py --help` or real invocation |
| exFAT file | `bash -n` | `head -N \| cat -n` (catches line merge) + `sync` |
| HTTP API | `curl /health` | `curl -X POST` with real payload |
| Docker | `docker build` exit 0 | `docker run` + `curl localhost:PORT/health` |

**Rule: Verification = try to BREAK it, not try to PASS it.**

### The "One OK" pattern (red flag)

When a verification loop produces generic output ("OK", "PASS") without identifying
WHICH artifact passed, the verification is meaningless. Example from session
`20260709_233413_95efac`:

```bash
# BROKEN basename (space in path "One Touch"):
for f in "/media/pavel/One Touch/"*.sh; do
  bash -n "$f" && echo "  $(basename $f) OK" || echo "  $(basename $f) FAIL"
done
# Output: "One OK" ×4  (not filenames!)
# Agent saw "OK" ×4, declared "all scripts valid" — ALL 4 were unverified
```

If verification output doesn't name the artifact it verified, it verified nothing.

## Red Flags — STOP and Follow Process

If you catch yourself thinking:
- "Quick fix for now, investigate later"
- "Just try changing X and see if it works"
- "Add multiple changes, run tests"
- "Skip the test, I'll manually verify"
- "It's probably X, let me fix that"
- "I don't fully understand but this might work"
- "Pattern says X but I'll adapt it differently"
- "Here are the main problems: [lists fixes without investigation]"
- Proposing solutions before tracing data flow
- **"One more fix attempt" (when already tried 2+)**
- **Each fix reveals a new problem in a different place**

**ALL of these mean: STOP. Return to Phase 1.**

**If 3+ fixes failed:** Question the architecture (Phase 4 step 5).

## Common Rationalizations

| Excuse | Reality |
|--------|---------|
| "Issue is simple, don't need process" | Simple issues have root causes too. Process is fast for simple bugs. |
| "Emergency, no time for process" | Systematic debugging is FASTER than guess-and-check thrashing. |
| "Just try this first, then investigate" | First fix sets the pattern. Do it right from the start. |
| "I'll write test after confirming fix works" | Untested fixes don't stick. Test first proves it. |
| "Multiple fixes at once saves time" | Can't isolate what worked. Causes new bugs. |
| "Reference too long, I'll adapt the pattern" | Partial understanding guarantees bugs. Read it completely. |
| "I see the problem, let me fix it" | Seeing symptoms ≠ understanding root cause. |
| "One more fix attempt" (after 2+ failures) | 3+ failures = architectural problem. Question the pattern, don't fix again. |

## Quick Reference

| Phase | Key Activities | Success Criteria |
|-------|---------------|------------------|
| **1. Root Cause** | Read errors, reproduce, check changes, gather evidence, trace data flow | Understand WHAT and WHY |
| **2. Pattern** | Find working examples, compare, identify differences | Know what's different |
| **3. Hypothesis** | Form theory, test minimally, one variable at a time | Confirmed or new hypothesis |
| **4. Implementation** | Create regression test, fix root cause, verify | Bug resolved, all tests pass |

## Hermes Agent Integration

### Investigation Tools

Use these Hermes tools during Phase 1:

- **`search_files`** — Find error strings, trace function calls, locate patterns
- **`read_file`** — Read source code with line numbers for precise analysis
- **`terminal`** — Run tests, check git history, reproduce bugs
- **`web_search`/`web_extract`** — Research error messages, library docs

### With delegate_task

For complex multi-component debugging, dispatch investigation subagents:

```python
delegate_task(
    goal="Investigate why [specific test/behavior] fails",
    context="""
    Follow systematic-debugging skill:
    1. Read the error message carefully
    2. Reproduce the issue
    3. Trace the data flow to find root cause
    4. Report findings — do NOT fix yet

    Error: [paste full error]
    File: [path to failing code]
    Test command: [exact command]
    """,
    toolsets=['terminal', 'file']
)
```

### With test-driven-development

When fixing bugs:
1. Write a test that reproduces the bug (RED)
2. Debug systematically to find root cause
3. Fix the root cause (GREEN)
4. The test proves the fix and prevents regression

## Real-World Impact

From debugging sessions:
- Systematic approach: 15-30 minutes to fix
- Random fixes approach: 2-3 hours of thrashing
- First-time fix rate: 95% vs 40%
- New bugs introduced: Near zero vs common

**No shortcuts. No guessing. Systematic always wins.**
