# Subagent Delegation Architecture

Two patterns for splitting agent work across specialised subagents. Use pattern 1 for
simple delegation (General stays primary). Use pattern 2 when the orchestrator should be
a dedicated agent that doesn't do analysis or code itself.

## Pattern 1 — General as orchestrator (3 agents)

```
GENERAL (аналитик)             EXECUTOR (исполнитель)        REVIEWER (проверяльщик)
──────────────────             ─────────────────────        ───────────────────────
Phase 1: Requirements  ──┐
Phase 2: System Analysis ─┤
Phase 3: Deep Analysis  ──┤     Phase 6: Implement           Phase 7: Quality
Phase 4: Architecture   ──┤     ─ получает план             ─ чужими глазами
Phase 5: Plan (BDUF)    ──┘     ─ работает > красиво        ─ SAST gate
                                ─ 1 баг → 1 фикс → 1 тест   ─ test suite
Phase 6.5: Verification Gate    ─ не сдаётся                ─ security audit
Phase 8: Deployment             ─ проверяет на устройстве   ─ отчёт
Phase 9: Post-Deploy
Phase 10: Iterate
```

General делает фазы 1–5 и 8–10. Executor — фазу 6. Reviewer — фазу 7.

## Pattern 2 — Plan as dedicated orchestrator (11 agents)

```
Plan (оркестратор) — НЕ анализирует, НЕ пишет код. Только координирует через delegate_task.
───────────────

 Phase 1          Phase 2          Phase 3          Phase 4          Phase 5
 Requirements → System Analyst → Deep Researcher → Architect → Tech Lead
 (subagent)     (subagent,        (subagent,       (subagent)      (subagent,
                 весь цикл)        весь цикл)                       управляет 7 devs)
                                                                        │
                                                                        ▼
                                                                   Phase 6
                                                                   Developers ×7
                                                                   (subagents)
                                                                        │
                                                                        ▼
 Phase 9          Phase 8          Phase 7
 Iterate    ←    Deployment   ←   Security
 (Plan сам)      (subagent)       (subagent)
```

**Агенты 2, 3, 4 — «старшие»** — живут весь цикл, могут создавать sub-агентов, помогают всем.

### Состав команды

| # | Агент | Файл персоны | Роль | Весь цикл? |
|---|-------|-------------|------|-----------|
| — | **Plan** | `plan.md` | Оркестратор — координирует, не делает работу сам | — |
| 1 | Requirements | `requirements-agent.md` | Задаёт уточняющие вопросы, перезапускает цикл | Нет |
| 2 | System Analyst | `system-analyst.md` | SMART→5Whys→GoalTree, возвращает к целям, фаза 6.5 | **Да** |
| 3 | Researcher | `researcher.md` | Итеративный поиск, создаёт sub-агентов, structured citations | **Да** |
| 4 | Architect | `architect-agent.md` | Проектирует, лазит в education/claw/memory, user sign-off | **Да** |
| 5 | Tech Lead | `techlead-agent.md` | План, управляет 7 devs, код-ревью, принципы | Нет |
| 6 | Developers ×7 | `developer-agent.md` | RED→GREEN→REFACTOR, упёртые, могут нарушать запреты | Нет |
| 7 | Security | `security-agent.md` | SAST, пароли, утечки, угрозы КОМАНДЕ | Нет |
| 8 | Deployment | `deployment-agent.md` | Health check, smoke test, мониторинг | Нет |

### Ключевые принципы

**Developer (фаза 6):**
- RED → GREEN → REFACTOR всегда. Тест до кода.
- Работает > красиво. socat, qemu wrapper, подмена бинарников — разрешены
- Может нарушать запреты промпта если нужно для работающего кода
- 1 баг = 1 фикс = 1 проверка. Не писать 10 файлов за раз
- НЕ лазит во вне (web_search/browser запрещены) — спрашивает окружающих агентов
- Не сдаётся. «Невозможно» = «пока не нашёл способ»

**Security (фаза 7):**
- Защищает КОМАНДУ, не пользователей кода
- SAST gate: semgrep, bandit, gitleaks, pip-audit, npm audit
- Если код опасен для других — ничего страшного. Главное — команда в безопасности
- Critical/High findings блокируют деплой

**System Analyst, Researcher, Architect (фазы 2, 3, 4):**
- Живут весь цикл — от требований до деплоя
- Могут создавать собственных sub-агентов
- Если любой агент застрял — помогают решить

### Конфигурация

```yaml
# ~/.hermes/config.yaml
delegation:
  max_spawn_depth: 5  # Plan → любой subagent → sub-subagent → ...
```

### Агенты в UI

Для группировки в селекторе используется префикс `label: Plan · Name` в фронтматтере.
Все sub-агенты: `mode: primary`.

### Pitfalls

- Plan НЕ должен сам писать код или анализировать — его промпт явно запрещает
- Developer без ограничения «не лазить во вне» будет делать web_search вместо того чтобы спрашивать команду
- Без `max_spawn_depth ≥ 3` «старшие» агенты не смогут создавать своих sub-агентов
- Если Developer не обязан возвращаться на ревью к Tech Lead — код уйдёт непроверенным
- Security agent без правила «защищаем только команду» будет тратить время на этические вопросы
