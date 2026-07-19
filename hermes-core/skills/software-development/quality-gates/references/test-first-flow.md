# Test-First Gate Lifecycle

> Reference for quality-gates skill. Pavel's requirement: tests designed FROM requirements, BEFORE code.

## Pipeline with Test-First Gate

```
Phase 1: Requirements Analyst
   │  REQ-001, REQ-002, REQ-003 with acceptance criteria
   ▼
Phase 1.5: TEST DESIGN GATE (NEW)
   │  For each acceptance criterion → draft acceptance test
   │  CLARIFY → user: approve or reject each test
   │
   ├─ User approves → test locked, approved_by: user
   └─ User rejects → test rewritten → user re-approves
   │
   ▼  ALL acceptance criteria have approved tests
Phase 2-5: System Analysis → Research → Architecture → Plan
   ▼
Phase 6: Implementation
   │  Developer writes code AGAINST approved tests
   │  Gate Runner: approved tests must PASS
   │
   ├─ Test passes → continue
   └─ Test fails → rewrite CODE (never test)
   ▼
Phase 8.5: Acceptance
   │  User reviews results
   │
   ├─ "Тест не нравится" → rewrite TEST → user re-approves → re-run
   └─ Approved test fails → rewrite CODE
```

## Authority Hierarchy

```
USER (approves/rejects tests)
  ├─ APPROVED TEST (immutable without user re-approval)
  │    └─ CODE (must conform to test)
  │
  └─ REJECTED TEST
       └─ TEST rewritten (code unchanged)
```

## Test Approval States

| approved_by | Who created | Can rewrite without user? |
|-------------|-----------|--------------------------|
| `user` | User explicitly said "протестируй это" | ❌ No — user must re-approve |
| `analyst` | Business Analyst or System Analyst | ❌ No — user must re-approve |
| `architect` | Architect | ✅ Tech Lead can |
| `techlead` | Tech Lead | ✅ Developer can (with notification) |

## Two Distinct Cycles

| Cycle | Trigger | Change | Unchanged |
|-------|---------|--------|-----------|
| **Test Rejection** | User: "test is wrong" | Test rewritten | Code |
| **Code Fix** | Gate: approved test FAILs | Code rewritten | Test (approved) |
| **Cascade** | New approved test → old code fails | Test first, then code | — |
