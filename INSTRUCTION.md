# Hermes Portable v4 — Инструкция по запуску

## Системные требования

- Linux (ARM64/AArch64 или x86_64/AMD64)
- Docker 20.10 или новее
- Рекомендуется: curl, openssl, python3

## Установка

### Шаг 1: Скопируйте на компьютер

Скопируйте всю папку `hermes_portable_v4` с USB-накопителя на ваш компьютер
(рекомендуется в домашнюю директорию).

```bash
cp -r /media/usb/hermes_portable_v4 ~/
cd ~/hermes_portable_v4
```

### Шаг 2: Установите Docker (если ещё нет)

```bash
curl -fsSL https://get.docker.com | bash
sudo usermod -aG docker $USER
# Перезайдите в систему
```

### Шаг 3: Запустите backend

```bash
./start-backend.sh
```

Скрипт автоматически:
- Определит архитектуру (ARM64 или x64)
- Загрузит Docker-образ
- Скопирует hermes-core в ~/.hermes-portable/
- Сгенерирует API_SERVER_KEY
- Запустит gateway и dashboard

### Шаг 4: Настройте LLM-провайдера

Отредактируйте файл `.env` (создан автоматически из `.env.example`):

```bash
nano .env
```

Раскомментируйте и заполните ОДИН из провайдеров:
- `OPENROUTER_API_KEY=...` — OpenRouter (https://openrouter.ai/keys)
- `DEEPSEEK_API_KEY=...` — DeepSeek (https://platform.deepseek.com/)
- `ANTHROPIC_API_KEY=...` — Anthropic (https://console.anthropic.com/)
- `OPENAI_API_KEY=...` — OpenAI (https://platform.openai.com/)

Перезапустите контейнеры после изменения .env:
```bash
./stop.sh && ./start-backend.sh
```

### Шаг 5: Запустите GUI

```bash
./launch.sh
```

Или используйте CLI-чат:
```bash
./chat.sh
```

## Структура дистрибутива

```
hermes_portable_v4/
|-- start-backend.sh    # Запуск Docker-контейнеров (gateway + dashboard)
|-- launch.sh           # Запуск Desktop GUI
|-- chat.sh             # CLI-чат через Gateway API
|-- status.sh           # Проверка статуса
|-- stop.sh             # Остановка контейнеров
|-- VERSION             # Версия Hermes Agent
|-- .env.example        # Шаблон переменных окружения
|-- README.md           # Английская документация
|-- INSTRUCTION.md      # Эта инструкция (русский)
|-- docker/             # Docker-образы (tar.gz)
|   |-- hermes-agent-arm64.tar.gz
|   |-- hermes-agent-x64.tar.gz
|   |-- docker-entrypoint.sh
|-- gui-arm64/          # GUI для ARM64 (Jetson, Raspberry Pi 5)
|-- gui-x64/            # GUI для x86_64 (обычные ПК)
|-- gui-x64/Hermes      # Исполняемый файл Electron
|-- hermes-core/        # Ядро Hermes (санитизированное)
|   |-- agents/         # 32 агента
|   |-- skills/         # 130+ навыков
|   |-- hooks/          # 10 хуков
|   |-- scripts/        # 32 скрипта
|   |-- plugins/        # Плагины
|   |-- gates/          # Система quality gates
|   |-- cron/           # Cron-задачи
|   |-- config.yaml.template  # Шаблон конфигурации
|   |-- persona.md      # Шаблон persona
|   |-- AGENTS.md       # Конвенции разработки
|-- pip-packages/       # Офлайн-установка Hermes CLI (60 wheels)
```

## Архитектура

```
+------------------+     +-------------------+     +------------------+
| Electron GUI     |---->| Dashboard (:9123) |---->| Gateway (:18649) |
| (launch.sh)      |     | WebSocket + REST  |     | LLM API + Tools  |
+------------------+     +-------------------+     +------------------+
                                  |                          |
                                  |     +------------------+ |
                                  +---->| LLM Provider     |-+
                                        | (OpenRouter/etc) |
                                        +------------------+
```

## Частые проблемы

| Проблема | Решение |
|----------|---------|
| GUI не запускается (чёрный экран) | `./status.sh` — проверьте что dashboard жив |
| 401 Unauthorized | Проверьте `.env`: раскомментирован и заполнен API-ключ |
| Контейнеры падают | `docker logs hermes-gateway` или `hermes-dashboard` |
| Порт занят | `PORT_GW=18650 PORT_DASH=9124 ./start-backend.sh` |
| GUI крашится на ARM64 (Jetson) | Флаг `--disable-gpu` уже есть в launch.sh |

## Безопасность

Дистрибутив НЕ содержит:
- API-ключей (все заменены на placeholders)
- Персональных данных (IP, пути, имена пользователей)
- Баз данных сессий (state.db)
- Файлов памяти (memories/)

Все ключи генерируются заново при первом запуске (`start-backend.sh`).
