#!/usr/bin/env bash
#=============================================================================
# <Project> — стартовый скрипт для всего стека
#
# ОДИН СКРИПТ поднимает всё:
#   N. Health-check + статус всех сервисов
#
# ═══════════════════════════════════════════════════════════════════════════
#  НАСТРОЙКИ — все через переменные окружения (export перед запуском)
# ═══════════════════════════════════════════════════════════════════════════
#
#  <VAR_NAME>   — описание (default: <value>)
#
# ═══════════════════════════════════════════════════════════════════════════
#  ИСПОЛЬЗОВАНИЕ
# ═══════════════════════════════════════════════════════════════════════════
#
#   bash start.sh              — полный запуск
#   bash start.sh --no-<flag>  — без опционального сервиса
#   bash start.sh --status     — проверить что работает
#   bash start.sh --stop       — остановить всё
#
# ═══════════════════════════════════════════════════════════════════════════
#  ЧТО ДЕЛАЕТ КАЖДЫЙ ШАГ
# ═══════════════════════════════════════════════════════════════════════════
#
#  §2  Docker:     ...
#  §3  Model:      ...
#  §N  Status:     Выводит сводку что запущено, порты, команды, логи
#
#  Логи: /tmp/<service>.log
#=============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'; BOLD='\033[1m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; }
info() { echo -e "${BOLD}[→]${NC} $1"; }

# ── Config (override via environment) ────────────────────────────────────────
# <VAR>="${<ENV_VAR>:-<default>}"

# ── Parse args ───────────────────────────────────────────────────────────────
ACTION=start
for arg in "$@"; do
    case "$arg" in
        --status) ACTION=status ;;
        --stop)   ACTION=stop ;;
        -h|--help)
            echo "Usage: bash start.sh [--status] [--stop]"
            exit 0 ;;
    esac
done

# ── Stop ─────────────────────────────────────────────────────────────────────
if [ "$ACTION" = "stop" ]; then
    info "Stopping all services..."
    # pkill / docker stop / systemctl stop
    log "All services stopped."
    exit 0
fi

# ── Status ───────────────────────────────────────────────────────────────────
if [ "$ACTION" = "status" ]; then
    echo "=== Services ==="
    # pgrep / curl health checks
    exit 0
fi

# ── 1. Prerequisites ─────────────────────────────────────────────────────────
info "Checking prerequisites..."
# command -v checks

# ── 2-N. Services ────────────────────────────────────────────────────────────
# Start each service with:
# if pgrep -f "<service>" >/dev/null; then
#     log "<Service> already running"
# else
#     info "Starting <Service>..."
#     nohup <command> > /tmp/<service>.log 2>&1 &
#     sleep N
#     curl health check || warn "may not be ready"
# fi

# ── Final status ─────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}═══════════════════════════════════════════════${NC}"
echo -e "${BOLD}  Stack — Status${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════${NC}"
# Print service URLs, slash commands, log locations
