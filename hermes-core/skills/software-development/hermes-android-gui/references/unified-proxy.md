# Unified Proxy — Smart Model Routing

Один HTTP-прокси (Python, `http.server`) который принимает все chat-запросы на одном порту и маршрутизирует по имени модели.

## Архитектура

```
📱 Android → http://<YOUR_VPS_IP>:8643
                  │ SSH reverse tunnel
                  ▼
           socat :8643 → :8647
                  ▼
         unified_proxy.py :8647
          ├─ chat models (deepseek-chat, qwen, gpt-4o...) → LiteLLM :4000 (ключ sk-local)
          └─ agent models (hermes-agent, general, build...) → OpenCode+ API :8646
```

## Зачем

До unified proxy было две системы:
- Hermes режим → LiteLLM (порт 8644) — два SSH-туннеля
- OC+ режим → OpenCode+ (порт 8643)

Два туннеля = два источника падений. Unified proxy даёт ОДИН туннель, ОДИН порт.

## Модели-агенты (маршрутизируются в OpenCode+)

```python
AGENT_MODELS = {'hermes-agent', 'general', 'build', 'plan', 'review', 'safe',
                'explore', 'scout', 'deep-explore', 'claw', 'composter'}
```

Все остальные модели идут в LiteLLM.

## Запуск

```bash
# Убить старые socat и циклы
pkill -9 -f "socat.*8643" 2>/dev/null
pkill -9 -f "while true.*socat.*8643" 2>/dev/null
sleep 1

# Запустить unified proxy
python3 /home/user/unified_proxy.py 8647 &

# Пробросить порт
socat TCP-LISTEN:8643,reuseaddr,fork TCP:127.0.0.1:8647 &
```

## Питфол: старые socat-циклы

Где-то может быть запущен `while true; do socat TCP-LISTEN:8643 ... TCP:127.0.0.1:8646; done` который перезапускает НЕПРАВИЛЬНЫЙ socat (в обход unified proxy) после каждого pkill.

Решение: `pkill -f "while true.*socat.*8643"` — убить цикл вместе с socat.

## Питфол: LiteLLM авторизация

LiteLLM требует ключ `sk-local` в заголовке `Authorization: Bearer sk-local`. Прокси добавляет его для chat-моделей. Для agent-моделей пробрасывает оригинальный ключ клиента (из AppSettings.apiKey).

## Питфол: rate-limit на DeepSeek

Модель `deepseek-chat` через LiteLLM упирается в 429 (Too Many Requests) при частых запросах. Использовать локальные модели: `openai/qwen3.6-35b-heretic` (LM Studio/llama.cpp, без лимитов).

## Порядок перезапуска после перезагрузки

1. `socat TCP-LISTEN:8643,reuseaddr,fork TCP:127.0.0.1:8647 &`
2. `python3 /home/user/unified_proxy.py 8647 &`
3. SSH reverse tunnel: `ssh -fN -R 0.0.0.0:8643:localhost:8643 root@<YOUR_VPS_IP>`
4. Tunnel keeper: `/home/user/tunnel_keeper.sh &`
