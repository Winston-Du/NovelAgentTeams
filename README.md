# NovelAgentTeams - AI 小说创作系统

基于 Agent Runtime 架构的 AI 小说创作系统，支持交互式对话创作、多项目管理和基于图谱的智能记忆系统。

## 特性

- **对话式创作**: 通过 CLI 与 AI Agent 自然对话，协作完成小说创作
- **多项目支持**: 在不同目录下运行，每个故事独立管理配置和输出
- **专业分工**: 4 个专业 Agent 协作（总编、人物设计师、剧情撰写员、校对）
- **全局命令**: 安装后可在任意目录直接运行 `novels` 命令
- **记忆系统**: 自动记录校对反馈，避免重复错误
- **向量检索**: 基于样例库的写作风格检索
- **知识图谱记忆**: 基于 NetworkX 的实体关系图谱，支持伏笔追踪、人物关系查询、智能上下文注入
- **Web 界面**: 提供 React 前端界面，支持可视化管理

## 技术栈

- **后端**: Python 3.10+ / FastAPI / Uvicorn
- **前端**: React 18+ / TypeScript / Vite / Ant Design
- **数据库**: SQLite (开发) / PostgreSQL (生产)
- **测试**: pytest / pytest-cov

## 快速开始

### 1. 环境要求

- Python >= 3.10, < 3.14
- Node.js 20+
- pip 或 uv

### 2. 安装

```bash
# 克隆仓库
git clone https://github.com/only891/novels.git
cd NovelAgentTeams/novels_project

# 安装为全局命令
pip install -e .

# 安装开发依赖（包含测试工具）
pip install -e ".[dev]"
```

安装完成后，`novels` 命令将在全局可用。

### 3. 配置环境变量

在 `~/.zshrc` 或 `~/.bashrc` 中添加：

```bash
# LLM API 配置
export API_KEY="your_api_key_here"
export API_BASE_URL="http://ai-service.tal.com/openai-compatible/v1"  # 可选，有默认值
export MODEL_NAME="gemini-3-pro"  # 可选，默认 gemini-3-pro

# 向量检索 API（可选，用于样例检索）
export siliconflow_api="your_siliconflow_key"

# 小说内容根目录（可选，优先级最高）
# export NOVEL_PROJECT_ROOT="/path/to/your/novel/output"
```

重新加载配置：
```bash
source ~/.zshrc  # 或 source ~/.bashrc
```

### 4. 配置项目根目录

在 `novels_project/novels.yaml` 中配置默认小说内容目录：

```yaml
# NovelsProject 项目配置
# 优先级：环境变量 NOVEL_PROJECT_ROOT > 本配置 > 当前工作目录

# 默认项目根目录（小说内容目录）
project_root: /Users/Winston/Documents/WorkSpace/novel_xuanhuan_output
```

### 5. 创建新故事项目

```bash
# 创建故事目录结构（推荐）
mkdir -p ~/novels/我的故事/{config,DESIGN/PROMPTS,samples,output/chapters,graph}

# 创建人物卡（必需）
cat > ~/novels/我的故事/config/character_base_cards.yaml << 'EOF'
s_tier:
  tier_name: 核心角色
  characters:
    主角:
      role: hero
      brief: 一个普通的少年，身怀神秘血脉
      relationships:
        反派: enemy
        师父: mentor
      core_personality:
        - 坚韧
        - 善良
        - 重情义
    反派:
      role: villain
      brief: 邪恶组织的首领
      relationships:
        主角: enemy
      core_personality:
        - 阴险
        - 野心勃勃
    师父:
      role: mentor
      brief: 退隐的绝世高手
      relationships:
        主角: mentor
EOF

# 设置项目根目录并启动
export NOVEL_PROJECT_ROOT=~/novels/我的故事
novels
```

### 6. 启动 Web 界面（可选）

```bash
# 启动后端服务（开发模式，热重载）
cd novels_project
PYTHONPATH=src python -m uvicorn novels_project.server:create_app --host 0.0.0.0 --port 8000 --reload --factory

# 新开终端，启动前端服务
cd novels_project/frontend
npm install
npm run dev
```

访问地址：
- 前端界面: http://localhost:5173
- 后端 API: http://localhost:8000
- API 文档: http://localhost:8000/docs

## 使用方法

### 交互模式（推荐）

```bash
cd ~/novels/我的故事
novels
```

进入交互式 REPL，与 Agent 对话创作：
```
novels> 请创作第1章
novels> 修改第1章的结尾，让主角更果断
novels> 查看人物卡
novels> /graph status
```

### 命令行参数

```bash
# 快速创作指定章节
novels --chapter 1

# 单次对话模式
novels --prompt "帮我构思第1章的大纲"

# 使用指定模型
novels --model glm-5

# 恢复之前的会话
novels --resume <session_id>

# 初始化向量库
novels --init-vectordb

# 启动时强制全量重建知识图谱
novels --build-graph

# 禁用图谱记忆功能
novels --no-graph
```

### REPL 内置命令

| 命令 | 说明 |
|------|------|
| `/help` | 显示帮助 |
| `/status` | 显示当前项目状态 |
| `/chapter <N>` | 快速创作第N章 |
| `/cost` | 显示 Token 使用统计 |
| `/session` | 显示当前会话信息 |
| `/sessions` | 列出所有保存的会话 |
| `/resume <id>` | 恢复已保存的会话 |
| `/compact` | 手动压缩上下文 |
| `/clear` | 清空当前对话 |
| `/quit` | 退出 |
| `/graph` | 显示图谱状态 |
| `/graph health` | 显示同步健康报告 |
| `/graph sync` | 手动触发增量同步 |
| `/graph network <人物>` | 查询人物关系网络 |
| `/graph search <关键词>` | 搜索图谱实体 |
| `/graph foreshadow` | 查看未回收的伏笔 |

## 知识图谱记忆系统

系统内置基于 NetworkX 的知识图谱，自动构建人物关系、事件关联和伏笔追踪。

### 实体类型

| 类型 | 说明 | 示例 |
|------|------|------|
| character | 人物角色 | 主角、反派、师父 |
| event | 事件 | 最终决战、神器觉醒 |
| item | 物品/道具 | 陨星碎片、上古神器 |
| location | 地点 | 拍卖会场、秘境 |
| organization | 组织/势力 | 暗影组织、正道联盟 |
| concept | 概念/设定 | 伏笔、暗线、阴谋 |

### 关系类型

| 类型 | 说明 |
|------|------|
| ally | 同盟 |
| enemy | 敌对 |
| family | 亲属 |
| mentor | 师徒 |
| friend | 朋友 |
| lover | 恋人 |
| subordinate | 上下级 |
| knows | 认识 |
| participated_in | 参与事件 |
| caused | 引发/导致 |
| owns | 拥有 |
| located_at | 位于 |
| belongs_to | 属于（组织） |
| refers_to | 引用/提及 |
| foreshadows | 伏笔预示 |

### 自动同步配置

系统支持三种同步模式：

- **事件触发**: 章节生成后自动同步
- **阈值触发**: 达到指定章节数后同步
- **定时触发**: 定期自动同步

配置参数（默认）：
- `enabled`: True（启用自动同步）
- `event_triggered`: True（事件触发）
- `threshold_chapters`: 1（每章同步）
- `max_retries`: 3（最大重试次数）
- `retry_delay_seconds`: 10（重试间隔）
- `persist_on_sync`: True（同步时持久化）

## 项目结构

### 代码结构（NovelAgentTeams）

```
NovelAgentTeams/
├── novels_project/
│   ├── src/novels_project/
│   │   ├── cli.py                    # CLI 入口
│   │   ├── server.py                 # FastAPI 入口
│   │   ├── agents.py                 # Agent 模块
│   │   ├── project_config.py         # 项目配置管理
│   │   ├── api/                      # REST API 路由
│   │   │   ├── agent.py              # Agent 配置 API
│   │   │   ├── content.py            # 内容管理 API
│   │   │   ├── memory.py             # 记忆系统 API
│   │   │   ├── settings.py           # 设置 API
│   │   │   └── workspace.py          # 工作空间 API
│   │   ├── tools/                    # 工具定义
│   │   ├── memory/                   # 记忆系统
│   │   │   ├── integrator.py         # 图谱记忆集成器
│   │   │   ├── graph_store.py        # 图存储
│   │   │   ├── graph_query.py        # 图查询
│   │   │   ├── entity_extractor.py   # 实体提取器
│   │   │   ├── sync_manager.py       # 同步管理器
│   │   │   └── graph_memory_tool.py  # 图谱工具函数
│   │   └── api_client.py             # API 客户端
│   ├── frontend/                     # React 前端
│   ├── novels.yaml                   # 项目配置文件
│   ├── pyproject.toml                # 依赖配置
│   └── tests/                        # 测试用例
└── README.md
```

### 小说内容结构（novel_xuanhuan_output）

```
novel_xuanhuan_output/
├── config/
│   └── character_base_cards.yaml     # 人物卡（必需）
├── DESIGN/
│   └── PROMPTS/                      # 自定义提示模板（可选）
├── samples/                          # 写作样例（可选）
├── output/
│   ├── chapters/                     # 生成的章节
│   └── chapter_summaries/            # 章节摘要
├── sessions/                         # 会话记录
├── feedback/                         # 校对反馈
├── vector_db/                        # 向量库
└── graph/
    └── knowledge_graph.json          # 知识图谱持久化文件
```

## Agent 架构

系统采用 5 层架构：

```
用户 <-> CLI/REPL / Web UI
         │
    ConversationRuntime (主 Agent)
         │
         ├── chief_editor (总编) - gemini-3-pro
         ├── character_designer (人物设计师) - glm-5
         ├── plot_writer (剧情撰写员) - glm-5
         └── proofreader (校对) - gemini-3-pro
         │
         └── GraphMemoryIntegrator (图谱记忆)
```

- **主 Agent**: 负责理解用户意图，协调子 Agent 工作
- **子 Agent**: 各司其职，完成专业任务
- **图谱记忆**: 自动构建和查询知识图谱

## 工具列表

### 核心工具

| 工具 | 说明 |
|------|------|
| `chief_editor` | 制定章节规划和大纲 |
| `character_designer` | 设计人物细节和对话风格 |
| `plot_writer` | 撰写章节正文 |
| `proofreader` | 校对并记录问题 |
| `update_character_card` | 修改人物卡 |
| `fix_chapter_issue` | 记录章节问题并获取修正指导 |
| `save_chapter` | 保存章节到文件 |
| `load_chapter_data` | 加载章节数据 |

### 图谱记忆工具

| 工具 | 说明 |
|------|------|
| `query_character_network` | 查询人物关系网络 |
| `query_relation_between` | 查询两人之间的关系 |
| `search_graph` | 搜索图谱中的实体 |
| `trace_foreshadowing` | 追踪伏笔脉络 |
| `get_graph_context` | 获取图谱上下文用于提示词 |
| `build_knowledge_graph` | 手动构建/重建知识图谱 |
| `get_graph_stats` | 获取图谱统计信息 |

## 测试

```bash
cd NovelAgentTeams/novels_project

# 运行所有测试
PYTHONPATH=src pytest tests/ -v

# 运行单元测试和集成测试
PYTHONPATH=src pytest tests/unit/ tests/integration/ -v

# 生成覆盖率报告
PYTHONPATH=src pytest tests/unit/ tests/integration/ --cov=novels_project --cov-report=html

# 查看覆盖率报告
open coverage_html_report/index.html
```

## CI/CD 流水线

项目已配置 GitHub Actions CI 流水线，自动执行：

1. **代码质量检查** - Ruff 静态分析
2. **单元测试** - Python 3.10/3.11/3.12
3. **覆盖率报告** - 95% 阈值检查
4. **前端构建** - Vite 构建验证
5. **安全扫描** - safety + bandit

## API 文档

启动后端后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 常见问题

### 端口被占用

```bash
# 查找占用端口的进程
lsof -i :8000  # 后端
lsof -i :5173  # 前端

# 杀死进程
kill -9 <PID>
```

### 依赖安装失败

```bash
# 更新 pip
pip install --upgrade pip

# 清理缓存
pip cache purge
rm -rf node_modules package-lock.json  # 前端
```

### 测试失败

```bash
# 查看详细错误
PYTHONPATH=src pytest tests/unit/test_example.py -v --tb=long
```

## License

MIT