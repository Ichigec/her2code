# AGENTS.md — Hermes Agent Improvement Project

> Автоматически загружается оркестратором при `/agent plan` и сабагентами.
> Единственный источник проектных конвенций. Меняется Auditor'ом по результатам цикла.

## Build & Test Commands

```bash
# Python
python3 -m pytest tests/ -x -q
python3 -m pytest plugins/audit/tests/ -v
python3 -m mypy <file> --ignore-missing-imports

# Android (Hermes GUI)
cd ~/dev/Opencode
./gradlew assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
# Чистая сборка если изменения не подхватились:
rm -rf app/build && ./gradlew assembleDebug --no-build-cache
```

## Code Conventions

| Rule | Detail |
|------|--------|
| **TDD** | RED → GREEN → REFACTOR всегда. Тест → код → рефакторинг. |
| **1 файл = 1 фикс** | Не писать 10 файлов за раз. Файл → проверка → следующий. |
| **Принципы** | KISS, DRY, YAGNI, SOLID (SRP/OCP/LSP/ISP/DIP), APO |
| **Deviation log** | Нарушения → `docs/deviation-log.md` (Время/Файл/Запрет/Причина/Риск) |
| **Lockfiles** | Обновлять при добавлении зависимостей |

## Project Structure

```
~/.hermes/agents/        — ролевые файлы агентов
~/.hermes/plans/         — планы (YYYY-MM-DD_HHMMSS-<slug>.md)
~/.hermes/state.db       — основная БД сессий
~/.hermes/audit.db       — аудит-БД (Agent Improvement Pipeline)
~/.hermes/reports/       — отчёты /audit, /retro
docs/
  requirements/          — фаза 1 (<slug>.md)
  system-analysis/       — фаза 2
  research/              — фаза 3
  architecture/          — фаза 4
  security/              — фаза 7
  deployment/            — фаза 8
  tests/                 — фаза 8.5
```

## Documentation Conventions

Артефакты фаз — markdown на диске, не в чате.

- **Requirements:** Actors, Core User Journey, Acceptance Criteria (SMART), Constraints, NFRs, Out of Scope
- **System Analysis:** SMART-цель, 5 Whys, дерево целей, альтернативы (≥2), WSM/AHP-выбор, точная задача разработчику
- **Research:** RQs, hypotheses, источники с quality scoring (0–2), structured citation mapping
- **Architecture:** Топология, границы модулей, протоколы, потоки данных, развёртывание, безопасность, отказоустойчивость
- **Plan:** Bite-sized TDD задачи с точными путями, командами верификации, acceptance criteria
- **Security:** SAST results (таблица), findings, test suite results, verdict
- **Deployment:** Deploy steps, health check, smoke test, monitoring, issues
- **Test report:** Traceability matrix (тест → требование), failures (expected vs actual), evidence (реальный вывод)

## Development Lifecycle

| # | Phase | Agent | Artifact |
|---|-------|-------|----------|
| 1 | Requirements | #1 Requirements Analyst | `docs/requirements/<slug>.md` |
| 2 | System Analysis | #2 System Analyst | `docs/system-analysis/<slug>.md` |
| 3 | Research | #3 Researcher | `docs/research/<slug>.md` |
| 4 | Architecture | #4 Architect | `docs/architecture/<slug>.md` |
| 5 | Plan | #5 Tech Lead | `.hermes/plans/<ts>-<slug>.md` |
| 6 | Implement | #6 Developer ×N | code + tests |
| 6.5 | Verification | #2 System Analyst | 4 gate checks |
| 7 | Quality | #7 Security Agent | SAST report |
| 8 | Deployment | #9 Deployment Agent | deployment report |
| 8.5 | Acceptance | #8 Tester | test report |
| 9 | Post-Deploy | #3 Researcher | evidence report |
| 10 | Iterate + Audit | Orchestrator + Auditor | audit report |

**Depth modes:** speed (1 dev), balanced (3 dev), quality (7 dev + full suite).

**Agent escalation chain:**
```
developer → techlead → researcher → architect → system-analyst → requirements-agent → пользователь
```

## Testing Conventions

- **TDD always.** RED → GREEN → REFACTOR.
- **Categories:** Smoke, Acceptance, Regression, Integration, Edge case, NFR.
- **Traceability:** каждый тест → конкретный requirement ID.
- **Autonomous testing:** тестировщик НЕ просит пользователя «проверь сам».
- **Reproducible:** каждый ❌ FAIL включает точную команду.
- **Evidence-based:** реальный вывод терминала, не пересказ.
- **NFR measurable:** «достаточно быстро» → `time curl`.

## Security Gate (обязательный)

```bash
bandit -r . --severity-level high
pip-audit
gitleaks detect --no-git -v
semgrep --config=auto --error
npm audit --audit-level=high  # если есть package.json
```

**Severity:** Critical/High → блокирует деплой. Medium → техлид решает. **NEW findings only.**

## Architecture Conventions

- **Plugin-архитектура** предпочтительна: fail-open, не ломает существующее.
- **SQLite:** WAL mode, `PRAGMA foreign_keys=ON`, 0600 права.
- **HMAC-SHA256** для tamper-evidence.
- **Post-hoc пайплайн** — аудит после завершения, не блокирует.
- **Developer isolation:** 1 file = 1 dev, worktrees, Tech Lead мержит.

## Knowledge Sources

| Source | How |
|--------|-----|
| Education Graph (Neo4j) | `mcp_education_graph_education_search` |
| Claw Graph (Neo4j) | `mcp_claw_graph_search_tools`, `graph_traverse` |
| Memory | `memory` tool |
| Session history | `session_search` |
| Web | `web_search`, `browser` |

## Environment

- **Host:** Linux (Jetson ARM64, NVIDIA GB10, CUDA 13.0)
- **Kernel:** 6.17.0-1014-nvidia
- **Python:** 3.12.3, PEP 668
- **Hermes venv:** `~/.hermes/hermes-agent/venv/bin/python3`
- **Neo4j:** `:7474`/`:7687`, pass=`changeme`
- **ADB:** `~/Android/Sdk/platform-tools/adb` (QEMU wrapper)
- **Phone:** Honor, Android 16 (API 36), USB-attached
- **Voice proxy:** port 8647, `~/dev/Opencode/voice_proxy.py`
- **OpenCode+:** port 4000, `~/cursor/opencode+/`

## Known Pitfalls

| Pitfall | Fix |
|---------|-----|
| ADB reverse слетает при USB reconnect | Перезапустить `adb reverse tcp:8643 tcp:8642` |
| Gradle кеш stale | `rm -rf app/build && ./gradlew assembleDebug --no-build-cache` |
| Phone на другой подсети (10.4.x.x) | ADB reverse обязателен |
| Honor hilogd подавляет Log.d() | Использовать `Log.i()` |
| ctranslate2 без CUDA на aarch64 | Только CPU инференс |
| VPN меняет внешний IP | Порт-форвардинг на роутере не работает |
| serveo.net → 502 на первый запрос | Retry |
| **Фоновые процессы умирают** | `hermes gateway run` или systemd unit |
| **pkill убивает терминал** | `kill <PID>` конкретно, не pkill -f |
| **Stale sshd-session на VPS** | `fuser -k 8643/tcp` на VPS перед новым туннелем |
| **AGENTS.md не читается перед задачей** | Оркестратор: `read_file(AGENTS.md)` до делегации |
| **Skills не загружаются по триггерам** | Включить `HERMES_SKILL_ROUTER=1` |
| **Порт 8643 — конфликт** | Hermes Gateway API на 8643, unified proxy убран |
| **OpenCode+ step_start в ответе** | Фильтр в SseClient, серверный костыль |

## File Placement Rules (ENFORCED)

**write_file и patch разрешены ТОЛЬКО в этих корнях:**

| Root | Purpose |
|------|---------|
| `~/dev/codemes/` | Workspace — все проекты |
| `~/.hermes/` | Config, skills, agents, hooks, scripts, cron |
| `/tmp/` | Временные файлы |
| `~/dev/Opencode/` | Android исходники (legacy) |
| `~/cursor/` | OpenCode+ проект |

**Нарушение = хук `enforce-workspace.py` блокирует запись.**

Правило для агента: перед `write_file` проверить что путь начинается с одного из разрешённых корней. Если нет → создать поддиректорию в `~/dev/codemes/<project>/`.

## `/agent plan2` — Оркестратор полного цикла

Активация: `/agent plan2` — запускает 10-фазный цикл разработки с 29 агентами.

**Фазы:** Requirements → System Analysis → Research Orchestra → Architecture Trio → Plan (BDUF) → Pre-Flight Gate → Progressive Dev Pipeline → Security → Deployment → Acceptance Testing → Post-Deploy → Iterate.

**Модель оркестратора:** deepseek-v4-pro (deepseek). Каждый сабагент получает свою модель согласно routing table в `~/.hermes/agents/plan2.md`.

**Глубина:** speed (1 dev, 0 research) / balanced (3 dev, 6 iter) / quality (4 dev, 12 iter).

**Остановка:** «стоп», «stop», «отмена» — отменяет текущую делегацию. Коррекция: «не так, делай X» — переделегирует с исправлением.

**Артефакты:** `docs/requirements/<slug>.md` → `docs/system-analysis/<slug>.md` → `docs/research/<slug>.md` → `docs/architecture/<slug>.md` → `.hermes/plans/<ts>-<slug>.md`.

**Code RAG:** Все dev-агенты ОБЯЗАНЫ перед изменением файла запросить Neo4j codebase graph (`codebase_read_with_deps`) или curl к neo4j:changeme@localhost:7474.

## Progressive Dev Pipeline (Агенты-разработчики)

4 стадии эскалации креативности. Каждая стадия получает свой файл из плана (1 файл = 1 dev, изоляция через worktree).

| # | Агент | Файл | Модель | Принцип |
|---|-------|------|--------|---------|
| 1 | **Skeptic** 🥇 | `dev-skeptic.md` | kimi-k2.7-code | KISS extreme. Минимальные изменения. Если можно конфигом — не пишет код. |
| 2 | **Pragmatic** 🥈 | `dev-pragmatic.md` | deepseek-v4-pro | Стандартные паттерны. Стандартная креативность. |
| 3 | **Creative** 🥉 | `dev-creative.md` | deepseek-v4-pro | Нестандартные архитектуры. Альтернативные подходы. |
| 4 | **Maverick** 💎 | `dev-maverick.md` | deepseek-v4-pro | Ломает правила. Документирует КАЖДОЕ отклонение. |

Эскалация: Skeptic → (tests FAIL) → Pragmatic → (tests FAIL) → Creative → (tests FAIL) → Maverick.
На любом PASS: 5 reviewers (Style/Bugs/Security/Perf/Convention) → возврат к Skeptic для верификации.

**Ручной вызов:** `/agent dev-skeptic`, `/agent dev-pragmatic`, `/agent dev-creative`, `/agent dev-maverick`.

## Docker Hermes GUI

```bash
# Запуск Docker dashboard (один раз):
#   docker run -d --name hermes-dashboard --network host --volumes-from hermes-test \
#     -e HERMES_UID=1000 -e HERMES_GID=1000 \
#     -e HERMES_DASHBOARD_SESSION_TOKEN=*** \
#     -e PYTHONPATH=/opt/data \
#     hermes-agent dashboard --host 127.0.0.1 --port 9119 --insecure --tui --no-open --skip-build

# Запуск GUI (изолированно):
bash ~/.hermes/scripts/launch-docker-gui.sh
```

См. `skill hermes-docker-build` для полного рецепта.
