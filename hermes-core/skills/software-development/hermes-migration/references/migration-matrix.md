# Migration Matrix — что копировать

Полная инвентаризация `~/.hermes/` с решениями: копировать / не копировать / пересобрать.

```
Источник: /home/user/.hermes/ (11 GB всего, 2026-07-06)
```

## 🔴 IDENTITY — копировать обязательно

| Путь | Размер | Почему критично |
|------|--------|-----------------|
| `.env` | 25K | Все API ключи (DeepSeek, Kimi, Telegram...) |
| `config.yaml` | 12K | Провайдеры, модель, порты, делегирование |
| `persona.md` | 2.6K | Характер, стиль, язык общения |
| `profiles/` | 19M | Профили с настройками и skills |

## 🟡 KNOWLEDGE — копировать (потеря = потеря памяти)

| Путь | Размер | Почему важно |
|------|--------|-------------|
| `state.db` | 335M | ВСЕ сессии, `session_search` |
| `memories/` | 12K | MEMORY.md + USER.md |
| `auditor_memory.md` | 1.3K | Кросс-цикловые паттерны |
| `sessions/` | 3M | JSON-дампы сессий |

## 🟢 TOOLS — копировать (потеря = потеря наработок)

| Путь | Размер | Содержимое |
|------|--------|-----------|
| `agents/` | 1.2M | 38 agent-файлов |
| `skills/` | 17M | 133 скилла (24 категории) |
| `hooks/` | 100K | 8 хуков |
| `scripts/` | 452K | 30 скриптов |
| `gates/` | 536K | Quality gates система |
| `plugins/` | 45M | MCP плагины (claw-neo4j и др.) |
| `cron/` | 196K | Cron-задачи + output |
| `AGENTS.md` | 15K | Проектные конвенции |
| `SOUL.md` | 0.5K | Персона Hermes |
| `skill-bundles/` | 12K | build.yaml, security.yaml |
| `schemas/` | 16K | research-output-v1.json |
| `opencode_claw/` | 972K | Claw agent config |

## 🟤 OPTIONAL — копировать по желанию

| Путь | Размер | Примечание |
|------|--------|-----------|
| `observations/` | 160K | Observer findings |
| `reports/` | 84K | Отчёты аудитора |
| `plans/` | 832K | Планы оркестратора |
| `pairing/` | 12K | Pairing данные |
| `state-snapshots/` | 56K | Снапшоты конфигов |

## ⬜ REBUILDABLE — НЕ копировать

| Путь | Размер | Как восстановить |
|------|--------|-----------------|
| `hermes-agent/` | 8.1G | `pip install hermes-agent` |
| `lsp/` | 105M | `hermes lsp install` |
| `bin/` | 95M | `hermes lsp install` |

## ⬜ JUNK — НЕ копировать

| Путь | Размер | Почему мусор |
|------|--------|-------------|
| `state.db.bak.*` | 821M | Старые бэкапы БД |
| `logs/` | 39M | Логи |
| `cache/` | 1.9M | Кэш моделей |
| `image_cache/` | ? | Медиа-кэш |
| `audio_cache/` | 708K | Аудио-кэш |
| `backups/` | 48K | Бэкапы конфигов |
| `sandboxes/` | 8K | Временные песочницы |
| `home/` | 1G | Циклическая копия ~/.hermes |
| `agents.backup-*/` | 188K | Stale backup |
| `workspace/` | 4K | Пустая |
| `platforms/` | 8K | Может содержать токены |

## Итого

```
Копировать:    ~450 MB  (identity + knowledge + tools + optional)
НЕ копировать: ~10.5 GB (rebuildable + junk)
─────────────────────────────────────────────────────
ВСЕГО:         ~11 GB
```
