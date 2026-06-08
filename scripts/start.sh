#!/usr/bin/env bash
#
# NovelAgentTeams 统一启动脚本
#
# 功能:
#   1. 前置检查（环境变量、端口、依赖）
#   2. 清理旧进程
#   3. 启动后端 FastAPI 服务（novels-server，端口 8000）
#   4. 启动前端 Vite 开发服务器（端口 5174）
#   5. 健康检查
#   6. 展示服务面板
#
# 使用:
#   bash scripts/start.sh
#   或: ./scripts/start.sh
#
# 退出码:
#   0 - 成功
#   1 - 前置检查失败
#   2 - 后端启动失败
#   3 - 前端启动失败
#

set -euo pipefail

# ============================================================================
# 配置区
# ============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
NOVELS_PROJECT_DIR="${PROJECT_ROOT}/novels_project"
FRONTEND_DIR="${NOVELS_PROJECT_DIR}/frontend"

BACKEND_PORT=8000
FRONTEND_PORT=5174
BACKEND_HOST="127.0.0.1"

LOG_DIR="/tmp/novels-startup"
BACKEND_LOG="${LOG_DIR}/backend.log"
FRONTEND_LOG="${LOG_DIR}/frontend.log"
STARTUP_LOG="${LOG_DIR}/startup.log"

# 必需的环境变量
REQUIRED_ENV_VARS=("OPENROUTER_API_KEY")

# 后端启动命令（动态查找）
BACKEND_CMD=""

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ============================================================================
# 工具函数
# ============================================================================
log_info() {
    echo -e "${BLUE}[INFO]${NC} $*" | tee -a "${STARTUP_LOG}"
}

log_success() {
    echo -e "${GREEN}[OK]${NC}  $*" | tee -a "${STARTUP_LOG}"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*" | tee -a "${STARTUP_LOG}"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*" | tee -a "${STARTUP_LOG}"
}

print_header() {
    echo -e "${CYAN}============================================================${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}============================================================${NC}"
}

print_separator() {
    echo -e "${CYAN}------------------------------------------------------------${NC}"
}

# 动态查找 novels-server 命令路径
# 优先查找策略: 显式路径 > which 查找 > Python 模块调用
find_backend_cmd() {
    # 1. 优先查找已安装的命令（兼容 conda、homebrew、系统安装等多种方式）
    if command -v novels-server >/dev/null 2>&1; then
        BACKEND_CMD="$(command -v novels-server)"
        return 0
    fi

    # 2. 尝试常见路径
    local candidates=(
        "/opt/anaconda3/bin/novels-server"
        "/usr/local/bin/novels-server"
        "${HOME}/.local/bin/novels-server"
    )
    for cmd in "${candidates[@]}"; do
        if [ -x "${cmd}" ]; then
            BACKEND_CMD="${cmd}"
            return 0
        fi
    done

    # 3. 兜底：使用 Python 模块方式调用（不依赖脚本安装）
    if command -v python3 >/dev/null 2>&1 || [ -x "/opt/anaconda3/bin/python" ]; then
        local py
        py="$(command -v python3 || echo /opt/anaconda3/bin/python)"
        BACKEND_CMD="${py} -m novels_project.server"
        return 0
    fi

    return 1
}

# ============================================================================
# 初始化
# ============================================================================
init() {
    mkdir -p "${LOG_DIR}"
    : > "${STARTUP_LOG}"
    log_info "启动时间: $(date '+%Y-%m-%d %H:%M:%S')"
    log_info "项目根: ${PROJECT_ROOT}"

    # 动态查找后端启动命令
    if find_backend_cmd; then
        log_info "后端启动命令: ${BACKEND_CMD}"
    else
        log_warn "未能找到 novels-server 命令，将在启动阶段报错"
    fi
}

# ============================================================================
# 前置检查
# ============================================================================
check_tools() {
    print_header "1/5  工具检查"
    local missing_tools=()

    # 检查 Python
    if command -v /opt/anaconda3/bin/python >/dev/null 2>&1; then
        PYTHON=/opt/anaconda3/bin/python
        log_success "Python: $($PYTHON --version 2>&1) @ ${PYTHON}"
    elif command -v python3 >/dev/null 2>&1; then
        PYTHON=python3
        log_warn "Python: $($PYTHON --version 2>&1) @ ${PYTHON} (非 anaconda 环境)"
    else
        missing_tools+=("python3")
    fi

    # 检查 npm（必须在 anaconda bin 中查找）
    if [ -x "/opt/anaconda3/bin/npm" ]; then
        NPM=/opt/anaconda3/bin/npm
        log_success "npm: $($NPM --version) @ ${NPM}"
    elif command -v npm >/dev/null 2>&1; then
        NPM=npm
        log_warn "npm: $($NPM --version) @ ${NPM}"
    else
        missing_tools+=("npm")
    fi

    # 检查 node
    if [ -x "/opt/anaconda3/bin/node" ]; then
        NODE=/opt/anaconda3/bin/node
        log_success "node: $($NODE --version) @ ${NODE}"
    elif command -v node >/dev/null 2>&1; then
        NODE=node
        log_warn "node: $($NODE --version) @ ${NODE}"
    else
        missing_tools+=("node")
    fi

    # 检查 git
    if command -v git >/dev/null 2>&1; then
        log_success "git: $(git --version)"
    else
        missing_tools+=("git")
    fi

    if [ ${#missing_tools[@]} -ne 0 ]; then
        log_error "缺少必要工具: ${missing_tools[*]}"
        echo ""
        echo "  解决方案:"
        echo "    1. 加载 conda: source /opt/anaconda3/etc/profile.d/conda.sh && conda activate base"
        echo "    2. 安装 Node.js: brew install node 或访问 https://nodejs.org/"
        echo "    3. 安装 git: xcode-select --install"
        return 1
    fi

    export PATH="/opt/anaconda3/bin:/opt/anaconda3/pkgs/nodejs-*/bin:${PATH}"
    return 0
}

check_env_vars() {
    print_header "2/5  环境变量检查"
    local missing_vars=()

    for var in "${REQUIRED_ENV_VARS[@]}"; do
        if [ -n "${!var:-}" ]; then
            local var_value="${!var}"
            log_success "${var}: 已设置 (长度: ${#var_value})"
        else
            log_warn "${var}: 未设置"
            missing_vars+=("${var}")
        fi
    done

    if [ ${#missing_vars[@]} -ne 0 ]; then
        log_warn "环境变量 ${missing_vars[*]} 未设置"
        echo ""
        echo "  解决方案:"
        echo "    source ~/.zshrc  # 加载 shell 配置"
        echo "    或:"
        echo "    export ${missing_vars[0]}=your-api-key"
        echo ""
        read -p "  是否继续启动（无 API key 也能启动但 LLM 调用会失败）？[y/N] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_error "用户取消启动"
            return 1
        fi
    fi
    return 0
}

check_ports() {
    print_header "3/5  端口检查"

    for port in "${BACKEND_PORT}" "${FRONTEND_PORT}"; do
        if lsof -iTCP:${port} -sTCP:LISTEN -P -n >/dev/null 2>&1; then
            local pid
            pid=$(lsof -tiTCP:${port} -sTCP:LISTEN -P -n 2>/dev/null | head -n1)
            log_warn "端口 ${port} 被占用（PID: ${pid}）"

            # 尝试识别是什么进程
            local proc_name
            proc_name=$(ps -p ${pid} -o command= 2>/dev/null | head -c 80)
            log_info "  占用进程: ${proc_name}"

            read -p "  是否自动清理并继续？[y/N] " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                log_info "清理端口 ${port}..."
                lsof -tiTCP:${port} -sTCP:LISTEN -P -n 2>/dev/null | xargs -r kill -9 2>/dev/null || true
                sleep 1
                log_success "端口 ${port} 已释放"
            else
                log_error "用户取消启动"
                return 1
            fi
        else
            log_success "端口 ${port}: 可用"
        fi
    done
    return 0
}

check_dependencies() {
    print_header "4/5  依赖检查"

    # 检查 novels_project 包
    if ${PYTHON} -c "import novels_project" 2>/dev/null; then
        local pkg_path
        pkg_path=$(${PYTHON} -c "import novels_project; print(novels_project.__file__)" 2>/dev/null)
        log_success "novels_project: 已安装 @ ${pkg_path}"
    else
        log_warn "novels_project 未安装，尝试自动安装..."
        cd "${NOVELS_PROJECT_DIR}"
        if /opt/anaconda3/bin/pip install -e . 2>&1 | tee -a "${STARTUP_LOG}" | tail -n 5; then
            log_success "novels_project 已安装"
        else
            log_error "novels_project 安装失败"
            echo "  解决方案:"
            echo "    cd ${NOVELS_PROJECT_DIR}"
            echo "    pip install -e ."
            return 1
        fi
    fi

    # 检查前端 node_modules
    if [ -d "${FRONTEND_DIR}/node_modules" ]; then
        local nm_size
        nm_size=$(du -sh "${FRONTEND_DIR}/node_modules" 2>/dev/null | awk '{print $1}')
        log_success "frontend/node_modules: 已安装 (${nm_size})"
    else
        log_warn "frontend/node_modules 不存在，正在安装..."
        cd "${FRONTEND_DIR}"
        if ${NPM} install 2>&1 | tee -a "${STARTUP_LOG}" | tail -n 10; then
            log_success "前端依赖已安装"
        else
            log_error "前端依赖安装失败"
            return 1
        fi
    fi
    return 0
}

# ============================================================================
# 服务启动
# ============================================================================
start_backend() {
    print_header "5/5  启动服务"

    # 检查后端命令是否已找到
    if [ -z "${BACKEND_CMD}" ]; then
        log_error "后端命令未配置，请先安装 novels_project"
        echo "  解决方案:"
        echo "    cd ${NOVELS_PROJECT_DIR}"
        echo "    pip install -e ."
        return 2
    fi

    # 启动后端
    log_info "启动后端 (端口 ${BACKEND_PORT})..."
    cd "${PROJECT_ROOT}"
    # 使用动态查找到的命令（支持 novel-server 脚本或 python -m 方式）
    nohup ${BACKEND_CMD} > "${BACKEND_LOG}" 2>&1 &
    BACKEND_PID=$!
    log_info "后端 PID: ${BACKEND_PID}"

    # 等待后端就绪（最多 15 秒）
    log_info "等待后端就绪..."
    for i in {1..15}; do
        sleep 1
        if curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${BACKEND_PORT}/" 2>/dev/null | grep -q "200"; then
            log_success "后端就绪 (${i}s)"
            break
        fi
        if [ $i -eq 15 ]; then
            log_error "后端启动超时"
            echo "  错误日志（最后 20 行）:"
            tail -n 20 "${BACKEND_LOG}" | sed 's/^/    /'
            return 2
        fi
    done

    # 启动前端
    log_info "启动前端 (端口 ${FRONTEND_PORT})..."
    cd "${FRONTEND_DIR}"
    nohup ${NPM} run dev -- --port ${FRONTEND_PORT} --host 0.0.0.0 > "${FRONTEND_LOG}" 2>&1 &
    FRONTEND_PID=$!
    log_info "前端 PID: ${FRONTEND_PID}"

    # 等待前端就绪（最多 20 秒）
    log_info "等待前端就绪..."
    for i in {1..20}; do
        sleep 1
        if curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${FRONTEND_PORT}/" 2>/dev/null | grep -q "200"; then
            log_success "前端就绪 (${i}s)"
            break
        fi
        if [ $i -eq 20 ]; then
            log_warn "前端启动超时（可能仍在编译中）"
            echo "  日志（最后 10 行）:"
            tail -n 10 "${FRONTEND_LOG}" | sed 's/^/    /'
            return 3
        fi
    done

    return 0
}

# ============================================================================
# 状态展示
# ============================================================================
print_dashboard() {
    print_header "服务启动成功"

    echo -e "${GREEN}┌────────────────────────────────────────────────────────┐${NC}"
    echo -e "${GREEN}│${NC}             ${CYAN}NovelAgentTeams 服务面板${NC}                  ${GREEN}│${NC}"
    echo -e "${GREEN}├────────────────────────────────────────────────────────┤${NC}"
    echo -e "${GREEN}│${NC}  ${YELLOW}前端 (Frontend)${NC}                                      ${GREEN}│${NC}"
    echo -e "${GREEN}│${NC}    地址: ${CYAN}http://localhost:${FRONTEND_PORT}${NC}                       ${GREEN}│${NC}"
    echo -e "${GREEN}│${NC}    局域网: ${CYAN}http://$(ipconfig getifaddr en0 2>/dev/null || echo 'N/A'):${FRONTEND_PORT}${NC}        ${GREEN}│${NC}"
    echo -e "${GREEN}│${NC}    PID:  ${FRONTEND_PID:-N/A}                                            ${GREEN}│${NC}"
    echo -e "${GREEN}│${NC}  ${YELLOW}后端 (Backend)${NC}                                       ${GREEN}│${NC}"
    echo -e "${GREEN}│${NC}    地址: ${CYAN}http://127.0.0.1:${BACKEND_PORT}${NC}                        ${GREEN}│${NC}"
    echo -e "${GREEN}│${NC}    API 文档: ${CYAN}http://127.0.0.1:${BACKEND_PORT}/docs${NC}              ${GREEN}│${NC}"
    echo -e "${GREEN}│${NC}    PID:  ${BACKEND_PID:-N/A}                                            ${GREEN}│${NC}"
    echo -e "${GREEN}├────────────────────────────────────────────────────────┤${NC}"
    echo -e "${GREEN}│${NC}  ${YELLOW}日志文件${NC}                                            ${GREEN}│${NC}"
    echo -e "${GREEN}│${NC}    后端: ${LOG_DIR}/backend.log                          ${GREEN}│${NC}"
    echo -e "${GREEN}│${NC}    前端: ${LOG_DIR}/frontend.log                         ${GREEN}│${NC}"
    echo -e "${GREEN}│${NC}    启动: ${LOG_DIR}/startup.log                          ${GREEN}│${NC}"
    echo -e "${GREEN}├────────────────────────────────────────────────────────┤${NC}"
    echo -e "${GREEN}│${NC}  ${YELLOW}停止服务${NC}                                            ${GREEN}│${NC}"
    echo -e "${GREEN}│${NC}    bash scripts/stop.sh                                ${GREEN}│${NC}"
    echo -e "${GREEN}└────────────────────────────────────────────────────────┘${NC}"
}

# ============================================================================
# 主流程
# ============================================================================
main() {
    init

    # 前置检查
    check_tools || exit 1
    check_env_vars || exit 1
    check_ports || exit 1
    check_dependencies || exit 1

    # 启动服务
    if ! start_backend; then
        log_error "服务启动失败"
        exit 2
    fi

    # 状态面板
    print_dashboard

    # 实时日志提示
    echo ""
    log_info "实时跟踪日志："
    echo "    tail -f ${LOG_DIR}/backend.log"
    echo "    tail -f ${LOG_DIR}/frontend.log"
    echo ""
    log_info "停止服务：bash scripts/stop.sh"
}

main "$@"
