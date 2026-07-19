# Sequence Diagrams — Current (hermes-agent) vs Original

## 1. Текущая реализация (hermes-agent, tools/delegate_tool.py)

### 1a. Основной цикл агента (без делегирования)

```
User       TUI/Gateway      AIAgent               LLM Provider
 │             │              │                      │
 │  message   │              │                      │
 │────────────►│              │                      │
 │             │  run_conversation()                  │
 │             │─────────────►│                      │
 │             │              │  ┌─────────────────┐ │
 │             │              │  │ while budget>0:  │ │
 │             │              │  │                 │ │
 │             │              │  │ 1. check        │ │
 │             │              │  │    interrupt    │ │
 │             │              │  │                 │ │
 │             │              │  │ 2. touch        │ │
 │             │              │  │    activity     │ │
 │             │              │  │                 │ │
 │             │              │  │ 3. LLM call     │ │
 │             │              │  │    ─────────────►│
 │             │              │  │    (messages +    │
 │             │              │  │     tool schemas) │
 │             │              │  │◄─────────────────│
 │             │              │  │    response       │
 │             │              │  │                 │ │
 │             │              │  │ 4a. tool_calls?  │ │
 │             │              │  │    YES:          │ │
 │             │              │  │    _dispatch_    │ │
 │             │              │  │    _tool()       │ │
 │             │              │  │    append result │ │
 │             │              │  │    continue      │ │
 │             │              │  │                 │ │
 │             │              │  │ 4b. NO:          │ │
 │             │              │  │    return text   │ │
 │             │              │  └─────────────────┘ │
 │             │              │◄─────────────────────│
 │             │  {final_response,                      │
 │             │   messages, completed,                 │
 │             │   api_calls, duration}                │
 │             │──────────────────────────────────────│
 │             │              │                      │
 │             │  display response                    │
 │             │              │                      │
```

### 1b. Делегирование — одиночная задача (role='leaf')

```
User       AIAgent (parent, depth=0)    ThreadPoolExecutor
 │             │                           │
 │  delegate   │                           │
 │  _task()    │                           │
 │────────────►│                           │
 │             │ 1. Check pause + depth    │
 │             │ 2. Normalise role='leaf'  │
 │             │ 3. _build_child_agent():  │
 │             │    a. Intersect toolsets   │
 │             │    b. Strip blocked tools  │
 │             │    c. Build prompt        │
 │             │    d. AIAgent(quiet=True, │
 │             │       ephemeral_prompt)   │
 │             │ 4. _register_subagent()   │
 │             │                           │
 │             │ 5. executor.submit()      │──►│ Worker Thread
 │             │                           │   │
 │             │                           │   │ 6. _run_single_child():
 │             │                           │   │    a. _heartbeat_loop()
 │             │                           │   │       (daemon thread)
 │             │                           │   │    b. child.run_conversation()
 │             │                           │   │       ┌─────────────────┐
 │             │                           │   │       │ while budget:   │
 │             │                           │   │       │   LLM call      │
 │             │                           │   │       │   tool dispatch │
 │             │                           │   │       │   no delegate_  │
 │             │                           │   │       │   task blocked  │
 │             │                           │   │       └─────────────────┘
 │             │                           │   │    c. extract summary
 │             │                           │   │    d. _unregister()
 │             │                           │   │    e. child.close()
 │             │                           │◄──┘
 │             │                           │
 │             │ 7. Wait for completion    │
 │             │    (poll + interrupt chk) │
 │             │                           │
 │             │ 8. Aggregate results      │
 │             │ 9. Fold child cost into   │
 │             │    parent session         │
 │             │10. Fire subagent_stop hook│
 │             │                           │
 │             │  return JSON:             │
 │             │  {results, total_duration}│
 │             │◄──────────────────────────│
 │             │                           │
 │             │  display tree view +      │
 │             │  summary                  │
```

### 1c. Делегирование — батч (parallel tasks)

```
User       AIAgent (parent)     ThreadPoolExecutor(max_workers=3)
 │             │                         │
 │  delegate_  │                         │
 │  task(tasks)│                         │
 │────────────►│                         │
 │             │ 1. Validate len(tasks)  │
 │             │    <= max_workers       │
 │             │ 2. Build ALL children   │
 │             │    (loop, no threads)   │
 │             │                         │
 │             │ 3. executor.submit() ×3 │──►│ Worker 0
 │             │    (all at once)        │   │   ┌─────────────────┐
 │             │                         │   │   │ run_single_     │
 │             │                         │   │   │ child(0)        │
 │             │                         │   │   │                 │
 │             │                         │◄──┤   │ run_conversation│
 │             │                         │   │   │                 │
 │             │                         │   │   │ ◄── LLM call ──│
 │             │                         │   │   │                 │
 │             │                         │   │   │ ◄── tool call ──│
 │             │                         │   │   │                 │
 │             │                         │   │   │ ◄── LLM call ──│
 │             │                         │   │   │                 │
 │             │                         │   │   │ ◄── tool call ──│
 │             │                         │   │   │                 │
 │             │                         │   │   │ ◄── LLM (no     │
 │             │                         │   │   │    tool_calls)   │
 │             │                         │   │   │                 │
 │             │                         │   │   │ ◄── summary     │
 │             │                         │   │   └─────────────────┘
 │             │                         │   │
 │             │                         │   │   ┌─────────────────┐
 │             │                         │◄──┤   │ run_single_     │
 │             │                         │   │   │ child(1)        │
 │             │                         │   │   │                 │
 │             │                         │   │   │ ◄── LLM ────────│
 │             │                         │   │   │ ◄── tool ───────│
 │             │                         │   │   │ ◄── LLM ────────│
 │             │                         │   │   │ ◄── text resp   │
 │             │                         │   │   └─────────────────┘
 │             │                         │   │
 │             │                         │   │   ┌─────────────────┐
 │             │                         │◄──┤   │ run_single_     │
 │             │                         │   │   │ child(2)        │
 │             │                         │   │   │                 │
 │             │                         │   │   │ ◄── LLM ────────│
 │             │                         │   │   │ ◄── tool ───────│
 │             │                         │   │   │ ◄── tool ───────│
 │             │                         │   │   │ ◄── LLM ────────│
 │             │                         │   │   │ ◄── text resp   │
 │             │                         │   │   └─────────────────┘
 │             │                         │   │
 │             │ 4. Poll futures:        │   │
 │             │    wait(FIRST_COMPLETED)│   │
 │             │    print completion     │   │
 │             │    line for each done   │   │
 │             │                         │   │
 │             │ 5. Sort + aggregate     │   │
 │             │ 6. Unregister all       │   │
 │             │ 7. Fire hooks           │   │
 │             │ 8. Return JSON          │   │
 │             │                           │
```

### 1d. Вложенное делегирование (orchestrator → workers)

```
User       AIAgent (depth=0)     Child Orch (depth=1)     Workers (depth=2)
 │             │                        │                         │
 │  delegate   │                        │                         │
 │  _task(     │                        │                         │
 │   role=     │                        │                         │
 │   'orch')   │                        │                         │
 │────────────►│                        │                         │
 │             │ 1. depth(0) < max     │                         │
 │             │    spawn_depth(3)? YES│                         │
 │             │ 2. _build_child_      │                         │
 │             │    agent(role='orch') │                         │
 │             │    → retains          │                         │
 │             │      'delegation'     │                         │
 │             │ 3. child.run_conv()   │──►│                       │
 │             │    (child is orchestr)│   │                       │
 │             │                        │  ┌──────────────────┐  │
 │             │                        │  │ Inside orchestr:  │  │
 │             │                        │  │                   │  │
 │             │                        │  │ LLM: "I'll spawn  │  │
 │             │                        │  │  2 workers"       │  │
 │             │                        │  │                   │  │
 │             │                        │  │ delegate_task(    │  │
 │             │                        │  │   tasks=[...],    │  │
 │             │                        │  │   role='leaf'     │  │
 │             │                        │  │ )                 │  │
 │             │                        │  │                   │  │
 │             │                        │  │ executor.submit() ×2 ─►│
 │             │                        │  │  Worker 0 (dep=2)  │
 │             │                        │  │  Worker 1 (dep=2)  │
 │             │                        │  │                   │  │
 │             │                        │  │ Wait + aggregate   │  │
 │             │                        │  │                   │  │
 │             │                        │  │ Return orchestr   │  │
 │             │                        │  │ summary           │  │
 │             │                        │  └──────────────────┘  │
 │             │                        │◄──────────────────────│
 │             │ 4. Get orchestr summary│                         │
 │             │ 5. Return to parent    │                         │
 │             │◄───────────────────────│                         │
 │             │                        │                         │
```

### 1e. Interrupt propagation

```
User       TUI       AIAgent (parent)     Children (running)
 │         │              │                      │
 │  Stop   │              │                      │
 │────────►│              │                      │
 │         │  interrupt   │                      │
 │         │  _requested  │                      │
 │         │◄─────────────│                      │
 │         │              │  _interrupt_         │
 │         │              │  _requested = True   │
 │         │              │                      │
 │         │              │  for child in        │
 │         │              │    _active_children:  │
 │         │              │    child.interrupt() │──►│ _interrupt_
 │         │              │                      │  _requested = True
 │         │              │                      │
 │         │              │                      │  (next loop
 │         │              │                      │   iteration: break)
 │         │              │◄─────────────────────│
 │         │              │                      │
 │         │              │  next while-iter:    │
 │         │              │  check interrupt →   │
 │         │              │  break               │
 │         │              │                      │
 │         │  response:   │                      │
 │         │  interrupted │                      │
 │         │  = true      │                      │
 │         │◄─────────────│                      │
```

### 1f. Credential rotation + heartbeat

```
Child AIAgent         Credential Pool        Parent AIAgent
     │                       │                        │
     │  acquire_lease()     │                        │
     │──────────────────────►│                        │
     │  lease=key1           │                        │
     │◄──────────────────────│                        │
     │                       │                        │
     │  run_conversation()   │                        │
     │                       │                        │
     │  LLM → rate limit    │                        │
     │  ◄─────────────────  │                        │
     │                       │                        │
     │  swap credential     │                        │
     │  → key2              │                        │
     │──────────────────────►│                        │
     │  retry               │                        │
     │                       │                        │
     │  LLM OK              │                        │
     │  ◄─────────────────  │                        │
     │                       │                        │
     │  release_lease()     │                        │
     │──────────────────────►│                        │
     │                       │                        │
     │  heartbeat:          │                        │
     │  touch("subagent 0    │                        │
     │   running terminal") │────────────────────────►│
     │                       │                        │ _last_activity
     │                       │                        │  = now
```

---

## 2. Оригинальная реализация (упрощённый вариант до делегирования)

Это то, как агент работал до добавления `delegate_task`:

```
User       CLI/Gateway      AIAgent               LLM Provider
 │             │              │                      │
 │  message   │              │                      │
 │────────────►│              │                      │
 │             │  chat()      │                      │
 │             │─────────────►│                      │
 │             │              │  ┌─────────────────┐ │
 │             │              │  │ init messages   │ │
 │             │              │  │ [system, user]  │ │
 │             │              │  │                 │ │
 │             │              │  │ while iter<90:  │ │
 │             │              │  │   response =    │ │
 │             │              │  │   LLM(messages) │ │───►│
 │             │              │  │                 │◄───│
 │             │              │  │   if tool_calls:│ │
 │             │              │  │     for each:   │ │
 │             │              │  │       exec tool │ │
 │             │              │  │       append res│ │
 │             │              │  │   else:         │ │
 │             │              │  │     return text │ │
 │             │              │  └─────────────────┘ │
 │             │              │◄─────────────────────│
 │             │  final text  │                      │
 │             │◄────────────────────────────────────│
 │             │              │                      │
 │             │  display     │                      │
```

### Ключевые отличия оригинала от текущей версии:

```
┌─────────────────────────────────────────────────────────────────┐
│                    ДО vs ПОСЛЕ делегирования                     │
├──────────────────────┬──────────────────────────────────────────┤
│     Аспект           │ Сравнение                                │
├──────────────────────┼──────────────────────────────────────────┤
│ Архитектура          │ До: плоский while-цикл                   │
│                      │ После: while-цикл + ThreadPoolExecutor   │
│                      │           + nested child AIAgents        │
├──────────────────────┼──────────────────────────────────────────┤
│ Контекст             │ До: единый messages[] для всего          │
│                      │ После: parent видит только summary       │
│                      │         children имеют свой messages[]   │
├──────────────────────┼──────────────────────────────────────────┤
│ Инструменты          │ До: все инструменты доступны             │
│                      │ После: child-агенты получают restricted │
│                      │         набор (blocked tools)            │
├──────────────────────┼──────────────────────────────────────────┤
│ Итерации             │ До: shared budget (max=90)              │
│                      │ После: каждый child имеет свой budget   │
│                      │         (max_iterations=50)             │
├──────────────────────┼──────────────────────────────────────────┤
│ Прерывание           │ До: один флаг _interrupt_requested      │
│                      │ После: cascade to children via          │
│                      │         _active_children                 │
├──────────────────────┼──────────────────────────────────────────┤
│ Дисплей              │ До: один спиннер                         │
│                      │ После: дерево с emoji + per-task lines  │
├──────────────────────┼──────────────────────────────────────────┤
│ Timeout              │ До: общий для всей сессии               │
│                      │ После: per-child timeout (600s default) │
├──────────────────────┼──────────────────────────────────────────┤
│ Credentials          │ До: один ключ на агента                 │
│                      │ После: credential pool + rotation       │
├──────────────────────┼──────────────────────────────────────────┤
│ Глубина              │ До: нет                                 │
│                      │ После: max_spawn_depth (default=1)      │
├──────────────────────┼──────────────────────────────────────────┤
│ Роль                 │ До: нет                                │
│                      │ После: leaf vs orchestrator             │
├──────────────────────┼──────────────────────────────────────────┤
│ Heartbeat            │ До: нет                                 │
│                      │ После: daemon thread → parent._touch()  │
│                      │         stale detection (idle/in-tool)  │
├──────────────────────┼──────────────────────────────────────────┤
│ Hook система         │ До: нет                                 │
│                      │ После: subagent_start / subagent_stop   │
├──────────────────────┼──────────────────────────────────────────┤
│ Стоимость            │ До: только parent API calls             │
│                      │ После: rollup parent + all children     │
└──────────────────────┴──────────────────────────────────────────┘
```

### 2a. Последовательность оригинального агента (до делегирования)

```
Step  Action                              Description
──────────────────────────────────────────────────────────────────
 1    User types "What's 2+2?"            User sends message
 2    AIAgent.__init__()                   Create agent instance
 3    run_conversation("What's 2+2?")      Start conversation
 4    messages = [system, "What's 2+2?"]   Initialise messages
 5    LLM(messages, tools=[...])           First API call
 6    → tool_calls=[{name:"terminal",     LLM wants to run terminal
        args:{command:"echo 2+2"}}]
 7    _dispatch_tool("terminal", {...})    Execute terminal tool
 8    → "4"                                Tool returns result
 9    messages.append(tool_result("4"))    Append to history
10    LLM(messages)                        Second API call
11    → content="2+2=4"                    Final response (no tools)
12    return "2+2=4"                       Done!
```

### 2b. Последовательность текущего агента (с делегированием)

```
Step  Action                              Description
──────────────────────────────────────────────────────────────────
 1    User types "Research X and Y"       User sends message
 2    run_conversation("Research...")      Start conversation
 3    LLM(messages, tools=[...])           First API call
 4    → tool_calls=[{name:"delegate_      LLM decides to delegate
        task", args:{tasks:[
        {goal:"Research X"},
        {goal:"Research Y"}]}}]
 5    _dispatch_tool("delegate_task", ...) Dispatch tool
 6    delegate_task():                     Main delegation function
 7      a. Check depth + pause             Guard rails
 8      b. _build_child_agent(0)           Build child 0
 9      c. _build_child_agent(1)           Build child 1
10      d. ThreadPoolExecutor.submit() ×2  Launch both in parallel
11      e. Poll futures + interrupt check  Wait for completion
12      f. Aggregate results               Merge summaries
13      g. Fire subagent_stop hooks        Notify plugins
14      h. Fold child costs               Update parent spend
15      i. Return JSON results            Back to agent
16    messages.append(tool_result(json))  Append delegation result
17    LLM(messages)                        Second API call
18    → content="X says... Y says..."     Final response
19    return "X says... Y says..."         Done!
```

### 2c. Сравнение потоков выполнения

```
ОРИГИНАЛ (до делегирования):
───────────────────────────────────────────────────────────
Main Thread:
  AIAgent ──────────────────────────────────────────────────►
    ┌────────┐   ┌────────┐   ┌────────┐   ┌────────┐
    │ LLM #1 │──►│terminal│──►│ LLM #2 │──►│  DONE  │
    └────────┘   └────────┘   └────────┘   └────────┘
    (serial, single thread)

ПОСЛЕ (с делегированием):
───────────────────────────────────────────────────────────
Main Thread:
  AIAgent ──────────────────────────────────────────────────►
    ┌────────┐   ┌─────────────────┐   ┌────────┐   ┌────────┐
    │ LLM #1 │──►│ delegate_task() │──►│ LLM #2 │──►│  DONE  │
    └────────┘   └────────┬────────┘   └────────┘   └────────┘
                          │
Worker Thread 0:         │
  Child 0 ────────────────┘
    ┌────────┐   ┌────────┐   ┌────────┐
    │ LLM #1 │──►│ file   │──►│ LLM #2 │
    └────────┘   └────────┘   └────────┘

Worker Thread 1:
  Child 1 ──────────────────────────────────────────────────────►
    ┌────────┐   ┌────────┐   ┌────────┐   ┌────────┐
    │ LLM #1 │──►│ web    │──►│ web    │──►│ LLM #2 │
    └────────┘   └────────┘   └────────┘   └────────┘

Daemon Thread:
  Heartbeat ────────────────────────────────────────────────────►
    (every 30s: parent._touch_activity())
```
