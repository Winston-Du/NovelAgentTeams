# NovelAgentTeams 服务启动指南

> **最后更新**: 2026-06-08
> **适用版本**: v0.2.0+
> **关联分支**: `feature/graph-agent-memory`

---

## 🚀 快速开始（一行命令）

```bash
bash scripts/start.sh
```

启动成功后，你将看到服务面板：
- **前端**: http://localhost:5174
- **后端**: http://127.0.0.1:8000
- **API 文档**: http://127.0.0.1:8000/docs

## 🛑 停止服务

```bash
bash scripts/stop.sh
```

## 📋 系统要求

| 工具 | 推荐版本 | 验证命令 |
|------|----------|----------|
| Python | 3.12+ | `python --version` |
| Node.js | 18+ | `node --version` |
| npm | 9+ | `npm --version` |
| Git | 2.30+ | `git --version` |

## ⚙️ 环境变量

### 必需

| 变量 | 用途 | 设置位置 |
|------|------|----------|
| `OPENROUTER_API_KEY` | LLM API 密钥 | `~/.zshrc` |

### 加载环境变量

```bash
# 方法 1: 加载 shell 配置
source ~/.zshrc

# 方法 2: 当前会话中导出
export OPENROUTER_API_KEY=sk-or-v1-xxx

# 方法 3: 验证
echo $OPENROUTER_API_KEY
```

## 🔍 启动脚本检查项

`start.sh` 会自动检查以下 5 项：

1. **工具检查**: Python、Node.js、npm、git
2. **环境变量检查**: `OPENROUTER_API_KEY`
3. **端口检查**: 8000（后端）、5174（前端）
4. **依赖检查**: `novels_project` Python 包、`frontend/node_modules`
5. **服务启动**: 顺序启动并健康检查

## 📁 目录结构

```
NovelAgentTeams/
├── scripts/
│   ├── start.sh          # 启动脚本
│   └── stop.sh           # 停止脚本
├── novels_project/
│   ├── frontend/         # 前端项目
│   │   └── node_modules/ # 前端依赖
│   ├── src/novels_project/  # 后端代码
│   └── pyproject.toml
└── docs/
    └── analysis/
        └── 2026-06-08-startup-reflection.md
```

## 📂 日志文件位置

| 日志 | 路径 |
|------|------|
| 启动日志 | `/tmp/novels-startup/startup.log` |
| 后端日志 | `/tmp/novels-startup/backend.log` |
| 前端日志 | `/tmp/novels-startup/frontend.log` |

查看实时日志：
```bash
tail -f /tmp/novels-startup/backend.log
tail -f /tmp/novels-startup/frontend.log
```

## 🔧 手动启动（高级用户）

如果自动脚本不满足需求，可以手动启动：

### 后端
```bash
cd /Users/Winston/Documents/WorkSpace/NovelAgentTeams
pip install -e ./novels_project
novels-server
```

### 前端
```bash
cd /Users/Winston/Documents/WorkSpace/NovelAgentTeams/novels_project/frontend
npm install  # 首次启动需要
npm run dev -- --port 5174 --host 0.0.0.0
```

## 🆘 常见问题

### Q1: 端口被占用

**错误**: `port 8000 already in use`

**解决**:
```bash
bash scripts/stop.sh
# 或手动清理
lsof -ti:8000 | xargs kill -9
```

### Q2: novels_project 未安装

**错误**: `ModuleNotFoundError: No module named 'novels_project'`

**解决**:
```bash
cd novels_project
pip install -e .
```

### Q3: npm/node 找不到

**错误**: `env: node: No such file or directory`

**解决**: 确保 `~/.zshrc` 中包含：
```bash
export PATH="/opt/anaconda3/bin:$PATH"
```

### Q4: OPENROUTER_API_KEY 未设置

**解决**:
```bash
echo 'export OPENROUTER_API_KEY="sk-or-v1-xxx"' >> ~/.zshrc
source ~/.zshrc
```

### Q5: editable install 指向已销毁的 worktree

**错误**: `Editable project location: /Users/Winston/.qoder/...`

**解决**:
```bash
cd /Users/Winston/Documents/WorkSpace/NovelAgentTeams/novels_project
pip install -e .
```

## 🔄 开发工作流

```bash
# 1. 拉取最新代码
git pull origin feature/graph-agent-memory

# 2. 启动服务
bash scripts/start.sh

# 3. 开发（修改代码会自动热重载）

# 4. 停止服务
bash scripts/stop.sh
```

## 📚 相关文档

- [服务启动反思报告](../analysis/2026-06-08-startup-reflection.md)
- [故障排除指南](troubleshooting.md)
- [环境配置指南](environment-setup.md)

---

**遇到问题？** 查看日志或参考 `docs/analysis/2026-06-08-startup-reflection.md` 的故障排除章节。
