# Hermes Portable v4 — Elevator Pitch

## Одной строкой

**Hermes Portable v4** — это самодостаточный AI-агентный дистрибутив:
33 агента, 132 навыка, 14 quality gates, dual-arch (ARM64 + x86_64),
нулевое содержание PII. Один USB-накопитель = рабочий AI-агент на любой Linux-машине.

## Ключевые цифры

| Метрика | Значение |
|---------|----------|
| Агентов | 33 (8 оркестраторов, 7 разработчиков, 9 аналитиков, 4 наблюдателя, 5 специалистов) |
| Навыков | 132 SKILL.md — процедурная память |
| Quality Gates | 14 гейтов на 10 фаз (deny-by-default, OPA-модель) |
| Плагинов | 4 (Neo4j MCP, OpenCode, routing, gating) |
| Хуков | 9 (pre/post tool, preflight, observer, curator) |
| Размер | 3.2 GB (включая Docker-образы + GUI-бинари для ARM64 и x86_64) |
| PII | 0 — полная санитизация |

## Что решает

1. **Фрагментация AI-агентов** → единая среда с общей памятью и оркестрацией
2. **Повторение ошибок** → навыки (skills) накапливают успешные паттерны
3. **Ручная передача контекста** → автоматическая оркестрация через plan1-4
4. **Качество без контроля** → 14 гейтов + 4 наблюдателя
5. **Сложность развёртывания** → один скрипт `./start-backend.sh`

## Отличия от аналогов

| | Hermes Portable | Claude Code | Codex | OpenCode |
|---|:---:|:---:|:---:|:---:|
| Multi-agent | ✅ 33 | ❌ | ❌ | ❌ |
| Skills (память агента) | ✅ 132 | ❌ | ❌ | ❌ |
| Quality Gates | ✅ 14 | ❌ | ❌ | ❌ |
| Offline-установка | ✅ USB | ❌ | ❌ | ❌ |
| Dual-arch | ✅ ARM64+x64 | ❌ | ❌ | ❌ |
| Open-source | ✅ MIT | ❌ | ❌ | ❌ |

## Где взять

- **GitHub:** https://github.com/Ichigec/her2code
- **Release (бинарные файлы):** https://github.com/Ichigec/her2code/releases/tag/v4.0.0
- **Презентация:** PRESENTATION.html (открыть в браузере)
- **Архитектура:** ARCHITECTURE.svg
- **Полное описание:** DESCRIPTION.md (284 строки)
