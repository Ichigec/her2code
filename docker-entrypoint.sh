#!/bin/sh
# Docker entrypoint: убрать Telegram из конфига (заблокирован в РФ)

CONFIG=/opt/data/config.yaml
while [ ! -f "$CONFIG" ]; do sleep 1; done

# Безопасно удалить Telegram через Python (уже в venv контейнера)
/opt/hermes/.venv/bin/python3 -c "
import yaml, os
cfg = yaml.safe_load(open(os.environ.get('CONFIG_FILE', '$CONFIG'))) or {}
gw = cfg.get('gateway', {})
gw.get('platforms', {}).pop('telegram', None)
gw.pop('telegram', None)
yaml.dump(cfg, open(os.environ.get('CONFIG_FILE', '$CONFIG'), 'w'), default_flow_style=False)
" 2>/dev/null && echo "[entrypoint] Telegram removed from config" || echo "[entrypoint] Could not strip Telegram (non-fatal)"

exec /init /opt/hermes/docker/main-wrapper.sh "$@"
