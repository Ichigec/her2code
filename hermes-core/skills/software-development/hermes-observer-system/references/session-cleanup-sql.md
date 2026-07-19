# Session Cleanup — SQL Recipes

Comprehensive recipes for identifying and deleting observer/auto-generated sessions from `~/.hermes/state.db`. Use these when the desktop sidebar is cluttered with garbage sessions.

## Step 0: Always Survey First

Never delete blindly. Show the user what you're about to delete:

```sql
-- Count garbage by category
SELECT 'CLI observer (Session analysis for)' AS category,
       COUNT(DISTINCT s.id) AS cnt
FROM sessions s
JOIN messages m ON m.session_id = s.id AND m.role = 'user'
WHERE s.archived = 0 AND s.source = 'cli'
  AND m.content LIKE 'Session analysis for% observer%'
UNION ALL
SELECT 'All CLI sessions',
       COUNT(*)
FROM sessions WHERE archived = 0 AND source = 'cli'
UNION ALL
SELECT 'Empty TUI (0 msgs, NULL title)',
       COUNT(*)
FROM sessions WHERE archived = 0 AND source = 'tui'
  AND title IS NULL AND message_count = 0
UNION ALL
SELECT 'Observer TUI (≤3 msgs, observer first msg)',
       COUNT(DISTINCT s.id)
FROM sessions s
JOIN messages m ON m.session_id = s.id AND m.role = 'user'
WHERE s.archived = 0 AND s.source = 'tui' AND s.title IS NULL
  AND s.message_count <= 3
  AND (m.content LIKE 'Session analysis for%'
    OR m.content LIKE '%observer%'
    OR m.content LIKE 'Auditor%'
    OR m.content LIKE 'Critic%'
    OR m.content LIKE 'Idea Generator%'
    OR m.content LIKE 'Knowledge Curator%'
    OR m.content LIKE 'Генератор идей%'
    OR m.content LIKE 'Критик%'
    OR m.content LIKE 'Аудитор%'
    OR m.content LIKE 'Наблюдай за%');
```

## Phase 1: CLI Sessions (Observer Subagent Spawns)

All CLI sessions are observer subagent spawns — the CLI source is only used for `hermes -z` batch invocations from `observer_worker.py`.

```sql
-- Delete messages first (no CASCADE in Hermes state.db)
DELETE FROM messages WHERE session_id IN (
    SELECT id FROM sessions WHERE archived = 0 AND source = 'cli'
);
-- Delete sessions
DELETE FROM sessions WHERE archived = 0 AND source = 'cli';
```

The first user message in these sessions is the tell: `"Session analysis for <critic|auditor|idea-generator|knowledge-curator> observer."`

## Phase 2: Empty Shells

Sessions with 0 messages and NULL title are empty shells — created by hooks or tool invocations that never produced content.

```sql
DELETE FROM messages WHERE session_id IN (
    SELECT id FROM sessions
    WHERE archived = 0 AND message_count = 0
      AND title IS NULL
      AND source IN ('tui', 'unknown')
);
DELETE FROM sessions
WHERE archived = 0 AND message_count = 0
  AND title IS NULL
  AND source IN ('tui', 'unknown');
```

## Phase 3: Short Observer TUI Sessions

Some observer tasks run through the TUI (desktop app) rather than CLI. These have:
- NULL title
- ≤3 messages
- First user message clearly identifies an observer role

```sql
DELETE FROM messages WHERE session_id IN (
    SELECT DISTINCT s.id
    FROM sessions s
    JOIN messages m ON m.session_id = s.id AND m.role = 'user'
    WHERE s.archived = 0 AND s.source = 'tui' AND s.title IS NULL
      AND s.message_count <= 3
      AND (m.content LIKE 'Session analysis for%'
        OR m.content LIKE 'Auditor%checkpoint%'
        OR m.content LIKE 'Auditor PII%'
        OR m.content LIKE 'Critic%checkpoint%'
        OR m.content LIKE 'Critic: Наблюдай%'
        OR m.content LIKE 'Idea Generator checkpoint%'
        OR m.content LIKE 'Idea Generator:%'
        OR m.content LIKE 'Knowledge Curator%checkpoint%'
        OR m.content LIKE 'Enterprise Architect%checkpoint%'
        OR m.content LIKE 'Auditor + Critic:%'
        OR m.content LIKE 'Retry healthcheck for observer%'
        OR m.content LIKE 'Наблюдай за ВСЕМ циклом%'
        OR m.content LIKE 'Ты — оркестратор Hermes Agent%'
        OR m.content LIKE 'Ты — Генератор идей%'
        OR m.content LIKE 'Ты — Критик%'
        OR m.content LIKE 'Ты — Enterprise Architect%')
);

DELETE FROM sessions WHERE id IN (
    SELECT DISTINCT s.id
    FROM sessions s
    JOIN messages m ON m.session_id = s.id AND m.role = 'user'
    WHERE s.archived = 0 AND s.source = 'tui' AND s.title IS NULL
      AND s.message_count <= 3
      AND (m.content LIKE 'Session analysis for%'
        OR m.content LIKE 'Auditor%checkpoint%'
        OR m.content LIKE 'Auditor PII%'
        OR m.content LIKE 'Critic%checkpoint%'
        OR m.content LIKE 'Critic: Наблюдай%'
        OR m.content LIKE 'Idea Generator checkpoint%'
        OR m.content LIKE 'Idea Generator:%'
        OR m.content LIKE 'Knowledge Curator%checkpoint%'
        OR m.content LIKE 'Enterprise Architect%checkpoint%'
        OR m.content LIKE 'Auditor + Critic:%'
        OR m.content LIKE 'Retry healthcheck for observer%'
        OR m.content LIKE 'Наблюдай за ВСЕМ циклом%'
        OR m.content LIKE 'Ты — оркестратор Hermes Agent%'
        OR m.content LIKE 'Ты — Генератор идей%'
        OR m.content LIKE 'Ты — Критик%'
        OR m.content LIKE 'Ты — Enterprise Architect%')
);
```

## Phase 4: Observer TUI with 4-10 Messages

Some observer sessions have slightly more messages (4-10). The first message patterns are the same. Be more careful here — some 4-10 message sessions are real user tasks. Only delete if the first message is clearly an observer role assignment.

```sql
DELETE FROM messages WHERE session_id IN (
    SELECT DISTINCT s.id
    FROM sessions s
    JOIN messages m ON m.session_id = s.id AND m.role = 'user'
       AND m.id = (SELECT MIN(id) FROM messages WHERE session_id = s.id AND role = 'user')
    WHERE s.archived = 0 AND s.source = 'tui' AND s.title IS NULL
      AND s.message_count BETWEEN 4 AND 10
      AND (m.content LIKE 'Phase % - %Analyst:%'
        OR m.content LIKE 'Research angle:%'
        OR m.content LIKE 'Idea Generator%'
        OR m.content LIKE 'Auditor%checkpoint%'
        OR m.content LIKE 'Critic%checkpoint%'
        OR m.content LIKE 'Knowledge Curator%'
        OR m.content LIKE 'Enterprise Architect%'
        OR m.content LIKE 'Ты — Генератор идей%'
        OR m.content LIKE 'Ты — Критик%'
        OR m.content LIKE 'Ты — Enterprise Architect%'
        OR m.content LIKE 'Наблюдай за%'
        OR m.content LIKE 'Retry healthcheck%')
);

DELETE FROM sessions WHERE id IN ( ... same subquery ... );
```

## What NOT to Delete

**Sessions with >10 messages AND NULL title** — these are real user conversations that just never got auto-titled. Examples from Pavel's DB:
- "как создать яндекс метрику что бы рекламировать группу в телеграмм?" (412 msgs)
- "Проведи глубокое исследование (DEEP mode, 8+ итераций) на тему MEMORY SCAFFOLDING" (156 msgs)
- "/home/user/dev/codemes/... проведи глубокий анализ" (986 msgs)

**Cron sessions** — all have titles and are legitimate scheduled jobs.

**Sessions with explicit titles set by the user** — regardless of source.

## Verification

After cleanup:
```sql
SELECT 'Remaining: ' || COUNT(*) FROM sessions WHERE archived = 0;
SELECT source, COUNT(*) FROM sessions WHERE archived = 0 GROUP BY source;
SELECT 'Untitled TUI: ' || COUNT(*)
FROM sessions WHERE archived = 0 AND source = 'tui' AND title IS NULL;
```

The remaining untitled TUI sessions should all have >10 messages — these are real conversations.

## Pitfall: Live DB Growth During Cleanup

`state.db` is the live database. New sessions are created while you work. If you run the count queries at the start, then do deletions, the final count may not equal `initial - deleted`. This is normal — new sessions were created in the meantime. Don't try to reconcile to exact numbers.
