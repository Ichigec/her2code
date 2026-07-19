# Ambiguity Examples

Concrete cases from real sessions where the agent assumed one interpretation and wasted time.

## Example 1: Mattermost (server vs desktop)

**User said:** «скачай и установи mattermost пожалуйста»

**Agent assumed:** Server — downloaded 430MB server binary, configured PostgreSQL, wrote config JSON, set up Docker container.

**Actual intent:** Desktop client application.

**Correct response:** 
```
«Mattermost» — это и сервер, и десктоп-клиент. Что ставим?
1. Сервер (self-hosted, с PostgreSQL, порт 8065)
2. Десктоп-приложение (AppImage, ~120MB)
```

**Waste:** ~80% of session (Docker pulls, DB setup, binary download, config writing, background process management).

**Rule:** Product names with multiple products under the same brand → clarify immediately.

## Example 2: Docker vs native install

**User said:** «зачем в докере, ставь на систему»

**Context:** Agent installed PostgreSQL in Docker because `sudo apt install` failed. User wanted everything native.

**Correct response:** 
```
PostgreSQL в Docker потому что нет sudo. Установить нативно не могу.
Варианты:
1. Оставить PostgreSQL в Docker (работает), Mattermost нативно
2. Ты даёшь sudo-доступ — ставлю всё нативно
```

## Example 3: «Проверь» = inspect or fix?

**User said:** «проверь конфиг»

**Ambiguity:** Just read and report? Or find and fix issues?

**Correct response:**
```
Проверить — просто показать что в конфиге, или найти и исправить проблемы?
```

**Rule:** «Проверь» в русском = read-only по умолчанию. Не начинать правки без подтверждения.
