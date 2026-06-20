---
name: codemes-distribution
description: "Упаковка Hermes в дистрибутив codemes_1 — структура, ключевые решения, pitfalls."
version: 1.0.0
author: Hermes Agent + User
license: MIT
metadata:
  hermes:
    tags: [distribution, packaging, codemes, hermes-agent]
---

# codemes_1 — Hermes Distribution

## Структура

```
/home/user/dev/codemes/codemes_1/
├── pack.sh              ← сборщик (exit 0, 7/7 валидаций)
├── install.sh           ← установщик с merge/upgrade
├── manifest.yaml        ← декларативная спецификация
├── lib/                 ← 12 bash-библиотек
├── templates/           ← ИНСТРУКЦИЯ.md, НАСТРОЙКА.md, .env.template
├── llm_bootstrap/       ← first-run LLM onboarding
├── dist/                ← собранный дистрибутив (647 файлов, 9.1 MB)
├── README.md            ← стиль lego-claw
└── CHANGELOG.md, LICENSE (MIT), VERSION (2026.06.14)
```

## Ключевые решения (Q1-Q10, утверждены User)

| Q | Решение |
|---|---------|
| Q1 | Путь задаёт пользователь, env-переменные удалены |
| Q2 | Любой Linux |
| Q3 | install.sh дополняет, не перезаписывает (механизм обновления) |
| Q4 | Бинарники исключены |
| Q5 | Два варианта: codemes_1 (без памяти) + codemes_1_pers (с памятью) |
| Q6 | Оригиналы в одном месте, без дублирования |
| Q7 | Включить всё необходимое; LLM при первом запуске объяснит что добавить |
| Q8 | Структура и содержание не хуже lego-claw |
| Q9 | MIT |
| Q10 | По дате (2026.06.14) |

## Архитектурный долг (найден Критиком #11)

- **manifest.yaml ≠ source of truth**: pack.sh дублирует include-правила хардкодом вместо парсинга manifest.yaml
- **yaml_parser.sh, secret_sanitizer.sh, file_copier.sh**: написаны и протестированы, но НЕ используются pack.sh
- **structure.md**: неисполненный шаблон, мёртвый файл
- **llm-bootstrap/** (дефис): дубликат llm_bootstrap/ (подчёркивание)

## Результат

- 14/14 acceptance criteria PASS
- ~174 тестов pass
- gitleaks clean, bandit clean
- Размер: 9.1 MB (лимит 200 MB)
