#!/bin/sh
# Docker entrypoint: удалить Telegram из конфига (заблокирован в РФ), затем запустить Hermes
# Монтируется в docker-compose.yml: ./docker-entrypoint.sh:/docker-entrypoint.sh:ro
# Используется как: entrypoint: ["/bin/sh", "/docker-entrypoint.sh"]

cp /opt/data/config.yaml /opt/data/config.yaml.docker-bak 2>/dev/null

python3 -c "
import yaml
with open('/opt/data/config.yaml') as f:
    c = yaml.safe_load(f) or {}
gw = c.get('gateway', {})
gw.get('platforms', {}).pop('telegram', None)
gw.pop('telegram', None)
with open('/opt/data/config.yaml', 'w') as f:
    yaml.dump(c, f)
" 2>/dev/null || true

exec /init /opt/hermes/docker/main-wrapper.sh "$@"
