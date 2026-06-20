# Где лежит OpenCode (файлы и настройки)

## Бинарник

| Путь | Назначение |
|------|------------|
| `~/.opencode/bin/opencode` | Установка через `opencode+/install-opencode.sh` |
| `~/.local/bin/opencode` | Альтернатива после `curl opencode.ai/install` |

Проверка: `which opencode` или `~/.opencode/bin/opencode --version`

## Конфиг (редактировать вручную)

| Путь | Назначение |
|------|------------|
| **`~/.config/opencode/opencode.json`** | Главный конфиг UI/TUI (провайдеры, модели, default model) |
| `opencode+/configs/opencode.litellm-dual.json` | Шаблон в репо: LiteLLM + tvall + llama alias |
| `opencode+/configs/profiles/*.env` | Сохранённые профили запуска |

Скрипт `start-opencode.sh` / `start-opencode-litellm.sh` **перезаписывает** `~/.config/opencode/opencode.json` при старте.

## Состояние сессий (не трогать без нужды)

| Путь | Назначение |
|------|------------|
| **`~/.opencode-host/`** | `OPENCODE_HOME` для native-режима (сессии, кэш, внутренние данные) |
| `~/.opencode/` | Старое/дефолтное состояние; Docker-режим использовал uid 10102 |
| `opencode+/.run/opencode-web.log` | Лог Web UI |
| `opencode+/.run/opencode-web.pid` | PID `opencode web` |

## Workspace (проект агента)

| Путь | Назначение |
|------|------------|
| **`~/cursor/first`** | `OPENCODE_WORKSPACE_DIR` — корень репо, откуда агент видит файлы |
| `~/cursor/first/.ai/` | Skills (symlink при старте, если нет `.ai` в workspace) |

## LiteLLM / LM Studio / llama

| Путь | Назначение |
|------|------------|
| `docker/litellm/config.yaml` | Алиасы моделей в gateway |
| `.env.llamacpp` | `LMSTUDIO_API_BASE`, `LLAMA_CPP_API_BASE` для Docker |
| `opencode+/.run/llama.log` | Лог host llama-server |

## Web UI

http://127.0.0.1:3400 — порт `OPENCODE_WEB_HOST_PORT`

## Полезные команды

```bash
# Где конфиг
ls -la ~/.config/opencode/

# Состояние
ls -la ~/.opencode-host/

# Лог web
tail -f ~/cursor/first/opencode+/.run/opencode-web.log
```

Документация продукта: https://opencode.ai/docs
