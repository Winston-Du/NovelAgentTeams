# NovelAgentTeams 故障排除指南

> **最后更新**: 2026-06-08

本文档汇总服务启动与运行中常见问题的解决方案。

---

## 🔥 紧急情况快速索引

| 问题 ID | 类别 | 标题 | 跳转 |
|---------|------|------|------|
| TRB-001 | 启动 | API key 未加载 | [→](#trb-001) |
| TRB-002 | 启动 | uvicorn 找不到 app | [→](#trb-002) |
| TRB-003 | 启动 | editable install 失效 | [→](#trb-003) |
| TRB-004 | 启动 | npm/node 找不到 | [→](#trb-004) |
| TRB-005 | 启动 | 端口被占用 | [→](#trb-005) |
| TRB-006 | 启动 | 前端无法外部访问 | [→](#trb-006) |
| TRB-007 | 进程 | 进程残留 | [→](#trb-007) |
| TRB-008 | Worktree | 废弃 worktree 残留 | [→](#trb-008) |
| TRB-009 | 依赖 | pydantic 代码签名错误 | [→](#trb-009) |
| TRB-010 | API | API 405 错误 | [→](#trb-010) |
| TRB-011 | 环境 | No module named uvicorn（环境错位）| [→](#trb-011) |

---

## <a id="trb-001"></a>TRB-001: API key 未加载

### 症状
```
Error: COMPANY_API_KEY environment variable not set
```
或 LLM 调用返回 401/403。

### 原因
- IDE 集成的终端是非交互式 shell
- `~/.zshrc` 中的 `export` 在非登录 shell 中不自动执行

### 解决方案

**方案 1: 加载 shell 配置**
```bash
source ~/.zshrc
echo $OPENROUTER_API_KEY  # 验证
```

**方案 2: 当前会话导出**
```bash
export OPENROUTER_API_KEY=sk-or-v1-xxx
```

**方案 3: 永久设置**
```bash
echo 'export OPENROUTER_API_KEY="sk-or-v1-xxx"' >> ~/.zshrc
source ~/.zshrc
```

---

## <a id="trb-002"></a>TRB-002: uvicorn 找不到 app

### 症状
```
ERROR: Error loading ASGI app. Attribute "app" not found in module "novels_project.server".
```

### 原因
`server.py` 使用**工厂模式**（`create_app()` 函数），没有模块级 `app` 变量。

### 解决方案

**使用 `novels-server` 命令（推荐）**:
```bash
novels-server
```

**或使用工厂调用**:
```bash
uvicorn novels_project.server:create_app --factory --port 8000
```

❌ 错误: `uvicorn novels_project.server:app`  
✅ 正确: `uvicorn novels_project.server:create_app --factory`

---

## <a id="trb-003"></a>TRB-003: editable install 失效

### 症状
```
ModuleNotFoundError: No module named 'novels_project'
```

**或**:
```
Editable project location: /Users/Winston/.qoder/worktree/.../i0lbGo
# 路径不存在
```

### 原因
- 之前 `pip install -e` 时使用的是 worktree 路径
- worktree 被销毁后，符号链接失效

### 解决方案

```bash
cd /Users/Winston/Documents/WorkSpace/NovelAgentTeams/novels_project
pip install -e .
```

**预防**: 销毁 worktree 前先 `pip uninstall novels_project`，销毁后再 `pip install -e .`

---

## <a id="trb-004"></a>TRB-004: npm/node 找不到

### 症状
```
$ which npm
npm not found
$ nohup npm run dev
nohup: npm: No such file or directory
env: node: No such file or directory
```

### 原因
- npm 脚本内部调用 `node` 时使用系统默认 PATH
- 系统 PATH 优先级问题

### 解决方案

**方法 1: 设置 PATH**
```bash
export PATH="/opt/anaconda3/bin:/opt/anaconda3/pkgs/nodejs-*/bin:$PATH"
```

**方法 2: 在 `~/.zshrc` 中固化**
```bash
echo 'export PATH="/opt/anaconda3/bin:/opt/anaconda3/pkgs/nodejs-22.6.0-h3fe1c63_0/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

**方法 3: 使用完整路径**
```bash
/opt/anaconda3/bin/npm run dev
```

---

## <a id="trb-005"></a>TRB-005: 端口被占用

### 症状
```
ERROR: [Errno 48] Address already in use
```

### 解决方案

**使用停止脚本**:
```bash
bash scripts/stop.sh
```

**手动清理**:
```bash
# 清理 8000（后端）
lsof -ti:8000 | xargs kill -9

# 清理 5174（前端）
lsof -ti:5174 | xargs kill -9

# 清理所有相关进程
pkill -f "novels-server"
pkill -f "vite"
pkill -f "npm run dev"
```

---

## <a id="trb-006"></a>TRB-006: 前端无法外部访问

### 症状
Vite 启动后只能通过 `localhost` 访问，从外部 IP 访问失败。

### 原因
Vite 默认绑定 `localhost` 而非 `0.0.0.0`。

### 解决方案

```bash
npm run dev -- --host 0.0.0.0
```

**或修改 `vite.config.ts`**:
```typescript
export default defineConfig({
  server: {
    host: '0.0.0.0',
    port: 5174,
  },
});
```

---

## <a id="trb-007"></a>TRB-007: 进程残留

### 症状
- 关闭终端后服务仍在运行
- 重新启动时报端口冲突

### 解决方案

**查找并清理**:
```bash
# 查找 novels-server 进程
ps aux | grep novels-server | grep -v grep

# 查找 vite 进程
ps aux | grep vite | grep -v grep

# 批量清理
pkill -9 -f "novels-server"
pkill -9 -f "vite"
pkill -9 -f "npm run dev"
```

**预防**: 使用 `bash scripts/stop.sh` 规范化停止。

---

## <a id="trb-008"></a>TRB-008: 废弃 worktree 残留

### 症状
```
git worktree list
/Users/Winston/.qoder/worktree/.../i0lbGo  <detached HEAD>
```

### 风险
- 24K+ 未提交文件占用磁盘
- editable install 指向已删除路径

### 解决方案

```bash
# 1. 列出 worktree
git worktree list

# 2. 销毁指定 worktree
git worktree remove /Users/Winston/.qoder/worktree/.../i0lbGo --force

# 3. 重新安装包
cd novels_project
pip install -e .
```

**定期清理建议**:
```bash
# 查找超过 7 天未使用的 worktree
find ~/.qoder/worktree -maxdepth 4 -type d -mtime +7
```

---

## <a id="trb-009"></a>TRB-009: pydantic 代码签名错误

### 症状
```
ImportError: dlopen(.../pydantic_core/_pydantic_core.cpython-313-darwin.so):
code signature in ... not valid for use in process:
mapping process and mapped file (non-platform) have different Team IDs
```

### 原因
macOS 的 Team ID 校验，常见于：
- 从 workbuddy 目录运行的 Python
- 跨环境的 C 扩展包

### 解决方案

**使用 anaconda 环境**:
```bash
/opt/anaconda3/bin/python -m uvicorn ...
```

**或重装包**:
```bash
/opt/anaconda3/bin/pip install --force-reinstall pydantic-core
```

---

## <a id="trb-010"></a>TRB-010: API 405 错误

### 症状
```
405 Method Not Allowed
net::ERR_ABORTED http://localhost:5174/api/agent-sessions/.../turns
```

### 原因
前端 URL 路径末尾多余斜杠或缺少 `/api` 前缀。

### 解决方案

**检查前端 API 调用**:
```typescript
// 错误
api.post('/agent-sessions/', data)
api.get('/agent-sessions/')

// 正确
api.post('/agent-sessions', data)
api.get('/agent-sessions')
```

**检查后端路由前缀**:
```python
# 后端
router = APIRouter(prefix="/api/agent-sessions", tags=["Agent 会话"])

@router.post("")  # 实际路径: /api/agent-sessions
async def create_session(...):
    ...
```

---

## <a id="trb-011"></a>TRB-011: No module named uvicorn（环境错位）

### 症状
```bash
$ PYTHONPATH=src python -m uvicorn novels_project.server:create_app ...
/opt/miniconda3/bin/python: No module named uvicorn
```

### 原因
**`python` 命令和 `novels-server` 指向不同的 Python 环境**：

| 组件 | 路径 | 环境 |
|------|------|------|
| 直接调用的 `python` | `/opt/miniconda3/bin/python` | miniconda |
| `novels-server` 内嵌的 python | `/opt/anaconda3/bin/python` | anaconda |

uvicorn 实际安装在 **anaconda** 环境，但用户用 miniconda 的 `python` 调用，所以报模块未找到。

### 解决方案

**方案 1（推荐）**：使用 `start.sh` 自动管理环境

```bash
bash scripts/start.sh
# 脚本内部已绑定 anaconda 环境，不再有环境错位问题
```

**方案 2**：手动指定 anaconda 的 python

```bash
# 使用 anaconda 的 python（已安装 uvicorn 的环境）
PYTHONPATH=src /opt/anaconda3/bin/python -m uvicorn novels_project.server:create_app --host 0.0.0.0 --port 8000 --factory
```

**方案 3**：在 miniconda 环境中安装 uvicorn

```bash
/opt/miniconda3/bin/python -m pip install uvicorn fastapi
```

**方案 4**：使用 `novels-server` 命令

```bash
nohup /opt/anaconda3/bin/python /Users/Winston/.local/bin/novels-server > backend.log 2>&1 &
```

### 预防

- ✅ **统一使用 `scripts/start.sh` 启动** —— 已通过 `find_backend_cmd` 函数动态绑定正确的 Python 环境
- ❌ **避免直接调用 `python`** —— 不同 conda 环境会指向不同 Python
- ✅ **如需手动启动**，先用 `which novels-server` 确认命令路径

---

## 🛠 诊断工具

### 一键健康检查

```bash
# 后端健康
curl -s http://127.0.0.1:8000/health | jq

# 前端健康
curl -sI http://127.0.0.1:5174/ | head -n 1

# 进程状态
ps aux | grep -E "novels-server|vite" | grep -v grep

# 端口状态
lsof -i:8000,5174
```

### 完整诊断报告

```bash
bash scripts/start.sh 2>&1 | tee /tmp/diagnose.log
```

---

## 📞 获取更多帮助

1. 查看 [服务启动反思报告](../analysis/2026-06-08-startup-reflection.md)
2. 查看服务启动日志：`/tmp/novels-startup/*.log`
3. 查看 GitHub Issues
4. 联系项目维护者

---

**最后更新**: 2026-06-08
