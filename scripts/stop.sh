#!/usr/bin/env bash
#
# NovelAgentTeams 统一停止脚本
#
# 功能:
#   1. 停止后端 FastAPI 服务
#   2. 停止前端 Vite 开发服务器
#   3. 释放端口 8000 和 5174
#   4. 清理相关日志
#
# 使用:
#   bash scripts/stop.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

BACKEND_PORT=8000
FRONTEND_PORT=5174

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[OK]${NC}  $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

print_header() {
    echo -e "${BLUE}============================================================${NC}"
    echo -e "${BLUE}  NovelAgentTeams 服务停止${NC}"
    echo -e "${BLUE}============================================================${NC}"
}

# 停止端口上的进程
stop_port() {
    local port=$1
    local name=$2
    local pids
    pids=$(lsof -tiTCP:${port} -sTCP:LISTEN -P -n 2>/dev/null || true)

    if [ -z "${pids}" ]; then
        log_info "${name} (端口 ${port}): 未运行"
        return 0
    fi

    log_info "${name} (端口 ${port}): 停止进程 ${pids}..."
    echo "${pids}" | xargs -r kill -TERM 2>/dev/null || true
    sleep 2

    # 强制清理残留
    pids=$(lsof -tiTCP:${port} -sTCP:LISTEN -P -n 2>/dev/null || true)
    if [ -n "${pids}" ]; then
        log_warn "${name}: 强制终止残留进程 ${pids}"
        echo "${pids}" | xargs -r kill -9 2>/dev/null || true
        sleep 1
    fi

    log_success "${name}: 已停止"
}

# 停止命名进程
stop_process() {
    local pattern=$1
    local name=$2
    local pids
    pids=$(pgrep -f "${pattern}" 2>/dev/null || true)

    if [ -z "${pids}" ]; then
        log_info "${name}: 未运行"
        return 0
    fi

    log_info "${name}: 停止进程 ${pids}..."
    echo "${pids}" | xargs -r kill -TERM 2>/dev/null || true
    sleep 1

    pids=$(pgrep -f "${pattern}" 2>/dev/null || true)
    if [ -n "${pids}" ]; then
        log_warn "${name}: 强制终止残留进程 ${pids}"
        echo "${pids}" | xargs -r kill -9 2>/dev/null || true
    fi

    log_success "${name}: 已停止"
}

main() {
    print_header

    log_info "停止后端服务..."
    stop_port "${BACKEND_PORT}" "后端 novels-server"
    stop_process "novels-server" "novels-server 进程"

    log_info "停止前端服务..."
    stop_port "${FRONTEND_PORT}" "前端 Vite"
    stop_process "vite" "Vite 进程"
    stop_process "npm run dev" "npm run dev 进程"

    echo ""
    log_success "所有服务已停止"
    echo ""
    log_info "重启服务: bash scripts/start.sh"
}

main "$@"
