# Docker-контейнеризация AI coding agents — сравнительный анализ

## Open Interpreter — Docker как песочница

- **Подход:** CLI-first, `pip install open-interpreter`. Docker — опциональный sandbox для изоляции кода.
- **Архитектура:** агент на хосте, каждый запуск кода в отдельном `docker run python:3`.
- **Плюсы:** минимальная конфигурация, не требует Docker для работы.
- **Минусы:** нет healthcheck, нет multi-instance из коробки.
- **Урок:** разделяй «агент» и «среду исполнения» на разные контейнеры.

## OpenHands — Docker sandbox best practices

- **Подход:** каждый task — отдельный Docker-контейнер. `docker-compose.yml` с 3+ сервисами.
- **Ключевые решения:**
  - `network_mode: host` для агента
  - `depends_on: service_healthy` с healthcheck в compose
  - Отдельный `workspace` volume на каждый инстанс
  - GitHub Actions CI/CD для публикации образа
- **Урок:** `depends_on` + healthcheck + CI/CD — три вещи, которых не хватало Hermes.

## Ollama — multi-instance из коробки

- **Подход:** `OLLAMA_HOST=0.0.0.0:11434` — один бинарник, много портов.
- **Изоляция:** `OLLAMA_HOME=/opt/ollama1 ollama serve &` и `OLLAMA_HOME=/opt/ollama2 OLLAMA_HOST=0.0.0.0:11435 ollama serve &`.
- **Урок:** `HERMES_HOME` — правильный паттерн изоляции. Никаких дополнительных файлов.

## vLLM — healthcheck + multi-arch

- **Подход:** `HEALTHCHECK --interval=30s CMD curl -f http://localhost:8000/health || exit 1` в Dockerfile.
- **Multi-arch:** `docker buildx build --platform linux/amd64,linux/arm64 -t vllm/vllm-openai .`
- **Урок:** `HEALTHCHECK` в Dockerfile решает проблему `sleep 180`. `buildx` решает multi-arch.

## Aider — намеренно без Docker

- **Подход:** `pip install aider-chat`. Никакого Docker.
- **Причина:** Aider редактирует локальный код (git, редактор). Docker изолирует его от файлов, которые он должен менять.
- **Урок:** Docker не всегда нужен. Для GitHub-публикации — нужен. Для локальной разработки — `pip install` проще.

## Continue.dev — VS Code extension (Electron-like)

- **Подход:** Расширение VS Code с отдельным backend-сервером. Backend стартует как subprocess.
- **Урок:** Desktop GUI как Continue — бутстрапит свой backend локально, не подключается к удалённому Docker.

## Cursor — удалённый backend + Electron

- **Подход:** Electron-приложение с удалённым backend. Использует `/api/status` для healthcheck.
- **Урок:** `/api/status` — стандартный паттерн для GUI↔Backend. Hermes gateway должен его иметь.

## Выводы

| Практика | Откуда | Статус в Hermes |
|----------|--------|:---:|
| `HERMES_HOME` изоляция | Ollama | ✅ |
| `network_mode: host` | OpenHands | ✅ |
| `HEALTHCHECK` в Dockerfile | vLLM | ❌ (sleep) |
| `depends_on: service_healthy` | OpenHands | ❌ (polling) |
| CI/CD GitHub Actions | OpenHands/Ollama | ❌ |
| Multi-arch `buildx` | vLLM | ❌ |
| `/api/status` эндпоинт | Cursor | ❌ (патч) |
