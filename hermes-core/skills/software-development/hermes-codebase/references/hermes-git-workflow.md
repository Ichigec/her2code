# Hermes Git Workflow

## Repos

Копии Hermes Agent на хосте:

| Repo | Branch | Remote | Назначение |
|------|--------|--------|------------|
| `~/.hermes/hermes-agent/` | `dev` | `github.com/NousResearch/hermes-agent.git` | **Установленная/рабочая версия.** Активная разработка на dev-ветке (observer, ACP, gateway fixes). |
| `~/.hermes-docker/hermes-agent/` | `main` | `github.com/NousResearch/hermes-agent.git` | Docker-форк. Отстаёт от dev. |
| `~/dev/hermes/` | `master` | Gitea | Legacy, не используется. |
| `~/dev/codemes/<SESSION_ID>/her2code/` | `master` | GitHub | Санитизированный дистрибутив. Содержит `hermes-agent` как git submodule. |

## Workflow: «сделай гит коммит»

Когда Pavel говорит «сделай гит коммит» — это **полный цикл**: stage → commit → push.

1. Определить контекст: какой репо? Если не указано — `~/.hermes/hermes-agent/` (рабочая версия).
2. Просмотреть diff для осмысленного сообщения.
3. `git add -A && git commit -m "..."` — Conventional Commits message.
4. **`git push`** — запушить на GitHub.

Если Pavel говорит «в локальный гит» — push не делать.

## Git config

Git global config может отсутствовать. Установить при первом коммите:

```bash
git config --global user.name "Pavel"
git config --global user.email "ichigec@gmail.com"
```
