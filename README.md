# her2code — агентный пайплайн на базе Hermes

**Сильно доработанный AI-агентный пайплайн** — 33 агента, 132 навыка, 14 quality gates, dual-arch (ARM64 + x64).

Построен на [Hermes Agent](https://github.com/NousResearch/hermes-agent) v0.16.0 (Nous Research, MIT License).

## Quick Start

```bash
# 1. Clone
git clone git@github.com:Ichigec/her2code.git && cd her2code

# 2. Download Docker image + GUI binaries (see Releases)
#    Or build from source (requires Docker)

# 3. Start backend
./start-backend.sh

# 4. Configure LLM key
cp .env.example .env && nano .env  # uncomment one LLM provider key

# 5. Launch GUI
./launch.sh
```

## What's in this repo

| Component | Description |
|-----------|-------------|
| `hermes-core/` | 33 agents, 132 skills, 9 hooks, 4 plugins, quality gates |
| `pip-packages/` | 60 Python wheels for offline Hermes CLI install |
| `*.sh` | Launch scripts (start-backend, launch GUI, chat, stop, status) |
| `.env.example` | Environment template (LLM keys, ports) |
| `ARCHITECTURE.svg` | System architecture diagram |
| `DESCRIPTION.md` | Full project description (architecture, agents, quality gates) |

## What's NOT in this repo (download separately)

| File | Size | Purpose |
|------|------|---------|
| `hermes-agent-arm64.tar.gz` | 1.6 GB | Docker image for ARM64 |
| `hermes-agent-x64.tar.gz` | 810 MB | Docker image for x86_64 |
| `gui-arm64/Hermes` | 344 MB | Electron GUI for ARM64 |
| `gui-x64/Hermes` | 339 MB | Electron GUI for x86_64 |

> These files exceed GitHub's 100 MB limit. Download from [Releases](https://github.com/Ichigec/her2code/releases) or build from source.

## Build from source (Docker image)

```bash
# Requires: Docker, ~5 GB disk space
cd her2code
docker build -t hermes-agent:latest -f docker/Dockerfile .
# Or use the official image:
docker pull nousresearch/hermes-agent:latest
```

## Architecture

```
User → GUI (Electron) → Dashboard (:9123) → Gateway (:18649) → LLM Provider
  │                                                              (OpenRouter/
  └── CLI (curl) ──────────────────────────────────────────────►  DeepSeek/...)
```

## Оркестраторы

Выбор оркестратора через `/agent` в GUI или CLI:

| Оркестратор | Модели | Статус |
|-------------|--------|:------:|
| **plan2** | DeepSeek V4 (аналитика) + GLM (исполнители) | ✅ **Рекомендуемый** |
| plan3 | Qwen3.6 + Nex + AgentWorld (3 модели) | 🧪 Экспериментальный |
| plan4 | DiffusionGemma (1 модель) | 🧪 Экспериментальный |
| plan1 | GLM (оркестратор) + DeepSeek | ⚠️ Устаревший |

> **plan2 — наиболее работоспособный.** Полный цикл: требования → анализ → research →
> архитектура → план → pre-flight gate → progressive dev (4 стадии эскалации) →
> security SAST → деплой → приёмка. 5 стилей разработки, 4 наблюдателя.

## Sanitization

This distribution contains **zero** API keys, personal data, or session state:
- All paths: `/home/user/` (no real usernames)
- All API keys: `<YOUR_..._KEY>` placeholders
- No databases, no memory files, no observer state

See [DESCRIPTION.md](DESCRIPTION.md) §4 for full sanitization details.

## Requirements

- Linux (ARM64/AArch64 or x86_64/AMD64)
- Docker 20.10+
- curl, openssl, python3
- 5 GB free disk space (plus Docker image)
- Internet connection (for LLM API calls)
