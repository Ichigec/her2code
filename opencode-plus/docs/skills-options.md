# OpenCode+ — варианты подключения `.ai/skills`

В репозитории skills лежат в **`.ai/`** (git-tracked, общие для clawcode / openhands / opencode). OpenCode умеет нативный discovery в `.opencode/skills/` и через tool `skill`.

## Сравнение вариантов

| Вариант | Как | Плюсы | Минусы |
| ------- | --- | ----- | ------ |
| **A. RO mount (default)** | `OPENCODE_SKILLS_DIR=../.ai` → `/workspace/project/.ai:ro` в [`compose.opencode.yml`](../../compose.opencode.yml) | Один каталог для всех агентов; версионируется в git | Агент не пишет в skills |
| **B. Native `.opencode/skills/`** | Копия или симлинк `SKILL.md` в workspace | Штатный discovery OpenCode + `permission.edit` на SKILL.md | Дублирование с `.ai/` |
| **C. Adapter-only inject** | `opencode-adapter` кладёт matched skills в ACP `session/new` | Нет дубля с native `AGENTS.md` (см. [`docs/skills.md`](../../docs/skills.md)) | Только headless / adapter путь |
| **D. skills-manager CRUD** | HTTP `skills-manager :8795` → пишет в `.ai/skills/` | UI/API для команды | Нужен `compose.agents-mesh.yml` |

## Рекомендация для OpenCode+

**A + `AGENTS.md` в корне workspace** — минимальная настройка для standalone разработки.

Для agent-mesh после `agent-mesh-demo-ru.sh` добавьте **C** (adapter inject) и не дублируйте те же skills в B без необходимости.

## Вариант A — RO mount (текущий default)

```env
# ../.env.opencode
OPENCODE_SKILLS_DIR=./.ai
```

В контейнере: `/workspace/project/.ai/skills/<name>/SKILL.md`.

OpenCode читает skills через tool `skill` и политики в `opencode.json` (`permission.edit` на `**/SKILL.md`).

## Вариант B — Native `.opencode/skills/`

```bash
mkdir -p "$HOME/agent_dev/.opencode/skills/my-skill"
cp .ai/skills/delegate-explore/SKILL.md "$HOME/agent_dev/.opencode/skills/my-skill/"
```

Плюс: совпадает с upstream-документацией OpenCode. Минус: два источника правды.

## Вариант C — Adapter inject

Используется в mesh: [`opencode-adapter`](../../compose.agents-mesh.yml) подбирает skills по запросу и передаёт в ACP без изменения файлов на диске.

Подходит для CI и cross-agent delegation; не заменяет A для локальной разработки в TUI.

## Вариант D — skills-manager

После `bash stack-start.sh` и поднятия agents-mesh:

```bash
curl -s http://127.0.0.1:8795/health
```

CRUD в `.ai/skills/` через HTTP; opencode видит обновления после remount или restart (RO mount — только чтение из контейнера; запись идёт на хост в `.ai/`).

## Сравнение с Claw Code

| | Claw | OpenCode+ |
| - | ---- | --------- |
| Каталог skills | `.ai/skills` (mesh) | Тот же `.ai` (вариант A) |
| Политика | `AGENTS.md` + hooks | `AGENTS.md` + `permission.*` в `opencode.json` |
| Subagent skills | delegate-* skills | Task tool + subagents (C2), skills в C4 |

См. также [`arch/comparison/configs/skills/`](../../arch/comparison/configs/skills/) для delegate-build / delegate-explore примеров.
