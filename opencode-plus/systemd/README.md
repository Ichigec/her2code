# OpenCode+ systemd unit

Системный сервис `opencode-plus.service` запускает **только agent (web UI на `:3400`)** от пользователя `pavel`. `llama.cpp` автоматически **не** стартует — её поднимаешь руками, когда нужна:

```bash
bash /home/user/cursor/first/opencode+/start-llama-qwen.sh --daemon
```

Файл юнита: [`opencode-plus.service`](./opencode-plus.service).

---

## Установка (один раз)

```bash
sudo install -m 0644 \
  /home/user/cursor/first/opencode+/systemd/opencode-plus.service \
  /etc/systemd/system/opencode-plus.service

sudo systemctl daemon-reload
```

После любого изменения файла в репо — повторить `install` + `daemon-reload`.

---

## Включить автозапуск при загрузке

```bash
sudo systemctl enable --now opencode-plus.service
```

- `enable` — добавить в автозагрузку (`multi-user.target`).
- `--now` — стартовать прямо сейчас, не дожидаясь перезагрузки.

Web UI: <http://127.0.0.1:3400>.

---

## Выключить

```bash
# Остановить сейчас + убрать из автозагрузки
sudo systemctl disable --now opencode-plus.service

# Только остановить (автозапуск останется)
sudo systemctl stop opencode-plus.service

# Только убрать из автозагрузки (текущий процесс не трогаем)
sudo systemctl disable opencode-plus.service
```

---

## Перезапуск / статус

```bash
sudo systemctl restart opencode-plus.service
systemctl status       opencode-plus.service
systemctl is-enabled   opencode-plus.service
systemctl is-active    opencode-plus.service
```

---

## Логи

```bash
# systemd journal (stdout/stderr ExecStart/ExecStop)
journalctl -u opencode-plus.service -e -n 200
journalctl -u opencode-plus.service -f          # follow

# Файлы (тоже пишутся юнитом)
tail -f /home/user/cursor/first/opencode+/.run/systemd.log
tail -f /home/user/cursor/first/opencode+/.run/opencode-web.log
```

---

## Полное удаление

```bash
sudo systemctl disable --now opencode-plus.service
sudo rm /etc/systemd/system/opencode-plus.service
sudo systemctl daemon-reload
```

---

## Поведение / детали

- `Type=oneshot` + `RemainAfterExit=yes` — `start-opencode.sh` делает `nohup opencode web … &` и завершается; PID web хранится в `opencode+/.run/opencode-web.pid`. Systemd считает сервис «active» после успешного выхода `ExecStart`.
- `ExecStop` зовёт `stop-opencode.sh` — гасит web по PID-файлу и, если запущен Docker-контейнер `opencode`, его тоже.
- `User=user`, `Group=pavel`, `WorkingDirectory=/home/user/cursor/first/opencode+`, `HOME=/home/user`.
- `After=network-online.target docker.service`, без `Requires=docker.service` — opencode поднимется даже если docker недоступен. Docker нужен только когда руками включишь LiteLLM-профиль.
- LLM не проверяется жёстко: если `http://127.0.0.1:8092/v1` не отвечает, в логе будет warning, но web всё равно стартует — UI будет ругаться на пустые ответы, пока не запустишь `llama.cpp`.

---

## Запустить llama.cpp руками (по требованию)

```bash
# В фоне + лог
bash /home/user/cursor/first/opencode+/start-llama-qwen.sh --daemon
tail -f /home/user/cursor/first/opencode+/.run/llama.log

# Остановить
bash /home/user/cursor/first/opencode+/stop-llama.sh
```

---

## Сменить порт / окружение

Правь `Environment=` в [`opencode-plus.service`](./opencode-plus.service) или положи дополнительные переменные в `opencode+/.env` (читаются `start-opencode.sh` через `lib/env.sh`). После правки юнита:

```bash
sudo install -m 0644 \
  /home/user/cursor/first/opencode+/systemd/opencode-plus.service \
  /etc/systemd/system/opencode-plus.service
sudo systemctl daemon-reload
sudo systemctl restart opencode-plus.service
```
