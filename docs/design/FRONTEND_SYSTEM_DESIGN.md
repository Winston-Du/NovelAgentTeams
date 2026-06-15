# NovelAgentTeams 前端管理系统 - 总体设计方案

## 一、技术栈选型

| 层级 | 技术 | 选型理由 |
|------|------|---------|
| 后端框架 | FastAPI + Uvicorn | 与现有 Python 生态无缝集成，异步支持，自动生成 Swagger 文档 |
| 前端框架 | React 18 + TypeScript | 成熟的组件化生态，类型安全，社区活跃 |
| 构建工具 | Vite 5 | 极速 HMR，原生 ESM 支持 |
| UI 组件库 | Ant Design 5 | 企业级组件库，丰富的表单/表格/布局组件 |
| 状态管理 | Zustand | 轻量级，无 boilerplate，适合中大型项目 |
| 路由 | React Router 6 | 标准的 React 路由方案 |
| Markdown 渲染 | react-markdown + rehype-highlight | 支持代码高亮的 Markdown 展示 |
| 网络请求 | axios | 拦截器支持，请求/响应转换 |
| 图表可视化 | @ant-design/charts | 图谱/关系网络可视化 |
| 打包产物 | 单页应用 (SPA) | 最终打包为静态文件，由 FastAPI 托管 |

## 二、项目目录结构

```
NovelAgentTeams/
├── novels_project/
│   ├── src/novels_project/
│   │   ├── api/                      # [新增] API 路由层
│   │   │   ├── __init__.py
│   │   │   ├── workspace.py          # 工作空间 API
│   │   │   ├── content.py            # 内容管理 API
│   │   │   ├── agent.py              # Agent 配置 API
│   │   │   ├── settings.py           # 系统设置 API
│   │   │   └── memory.py             # 记忆管理 API
│   │   ├── server.py                 # [新增] FastAPI 入口
│   │   ├── cli.py                    # [修改] CLI 入口（保留）
│   │   ├── memory/                   # 已有 - 图谱记忆系统
│   │   ├── tools/                    # 已有 - 工具函数
│   │   └── ...
│   ├── frontend/                     # [新增] 前端项目
│   │   ├── src/
│   │   │   ├── layouts/              # 布局组件
│   │   │   ├── pages/                # 页面组件
│   │   │   │   ├── Workspace/        # 工作空间管理
│   │   │   │   ├── Content/          # 内容管理
│   │   │   │   ├── AgentConfig/      # Agent 配置
│   │   │   │   ├── Settings/         # 系统设置
│   │   │   │   └── Memory/           # 记忆管理
│   │   │   ├── components/           # 通用组件
│   │   │   ├── stores/               # 状态管理 (Zustand)
│   │   │   ├── services/             # API 服务层
│   │   │   ├── hooks/                # 自定义 Hooks
│   │   │   ├── router/               # 路由配置
│   │   │   └── types/                # TypeScript 类型定义
│   │   ├── package.json
│   │   ├── vite.config.ts
│   │   └── tsconfig.json
│   └── pyproject.toml                # [修改] 添加 FastAPI 依赖
```

## 三、系统架构图

```
┌──────────────────────────────────────────────────────────────┐
│                     浏览器 (127.0.0.1:8000)                   │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              React SPA (Vite Build)                     │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │  │
│  │  │Workspace │ │ Content  │ │  Agent   │ │ Settings │  │  │
│  │  │ 工作空间  │ │ 内容管理  │ │  配置     │ │ 系统设置  │  │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │  │
│  │  ┌──────────┐                                          │  │
│  │  │ Memory   │  Zustand Store / React Router            │  │
│  │  │ 记忆管理  │                                          │  │
│  │  └──────────┘                                          │  │
│  └────────────────────────────────────────────────────────┘  │
│                          │ axios (REST API)                   │
├──────────────────────────┼───────────────────────────────────┤
│                          ▼                                    │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              FastAPI Server (novels-server)              │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │  │
│  │  │/api/     │ │/api/     │ │/api/     │ │/api/     │  │  │
│  │  │workspaces│ │content   │ │agents    │ │settings  │  │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │  │
│  │  ┌──────────┐ ┌──────────────────────────────────┐    │  │
│  │  │/api/     │ │ Static Files (frontend/dist/)     │    │  │
│  │  │memory    │ │                                  │    │  │
│  │  └──────────┘ └──────────────────────────────────┘    │  │
│  └────────────────────────────────────────────────────────┘  │
│                          │                                    │
│  ┌───────────────────────┼───────────────────────────────┐  │
│  │         现有 novels_project 核心模块                    │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────────────────┐  │  │
│  │  │project_  │ │ memory/  │ │ runtime / agents /   │  │  │
│  │  │config    │ │ 图谱系统  │ │ tools                │  │  │
│  │  └──────────┘ └──────────┘ └──────────────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
│                          │                                    │
│                          ▼                                    │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              文件系统 (novel_xuanhuan_output)            │  │
│  │  config/  output/  graph/  sessions/  feedback/         │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

## 四、API 接口设计

### 4.1 工作空间 API (`/api/workspaces`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 获取所有工作空间列表 |
| POST | `/` | 创建新工作空间 |
| GET | `/{id}` | 获取工作空间详情 |
| PUT | `/{id}` | 更新工作空间（重命名） |
| DELETE | `/{id}` | 删除工作空间 |
| POST | `/{id}/switch` | 切换到指定工作空间 |

### 4.2 内容管理 API (`/api/content`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/characters` | 获取人物卡列表 |
| POST | `/characters` | 添加人物 |
| PUT | `/characters/{name}` | 更新人物信息 |
| DELETE | `/characters/{name}` | 删除人物 |
| GET | `/chapters` | 获取章节列表 |
| GET | `/chapters/{id}` | 获取章节完整内容 |
| GET | `/chapters/{id}/summary` | 获取章节摘要 |
| GET | `/plotlines` | 获取暗线列表 |
| POST | `/plotlines` | 创建暗线 |
| PUT | `/plotlines/{id}` | 更新暗线 |
| DELETE | `/plotlines/{id}` | 删除暗线 |
| GET | `/search?q=keyword` | 全局搜索 |
| POST | `/annotate` | 对内容进行批注并调用 Agent 修改 |

### 4.3 Agent 配置 API (`/api/agents`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 获取所有 Agent 配置 |
| PUT | `/{name}` | 更新指定 Agent 配置 |
| PUT | `/{name}/toggle` | 启用/禁用 Agent |
| GET | `/{name}/status` | 获取 Agent 运行状态 |

### 4.4 系统设置 API (`/api/settings`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 获取系统设置 |
| PUT | `/` | 更新系统设置 |
| POST | `/backup` | 创建数据备份 |
| POST | `/restore` | 恢复数据备份 |
| GET | `/backups` | 获取备份列表 |

### 4.5 记忆管理 API (`/api/memory`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/entities` | 获取图谱实体列表 |
| GET | `/relations` | 获取关系列表 |
| GET | `/network/{name}` | 获取人物关系网络 |
| GET | `/foreshadow` | 获取未回收伏笔 |
| PUT | `/entities/{id}` | 更新实体信息 |
| DELETE | `/entities/{id}` | 删除实体 |
| POST | `/sync` | 手动触发同步 |

## 五、前端页面路由设计

```
/                          → 重定向到 /workspace
/workspace                 → 工作空间管理（列表 + 创建/切换）
/content                   → 内容管理总览
/content/characters        → 人物卡管理
/content/characters/:name  → 人物详情编辑
/content/chapters          → 章节列表
/content/chapters/:id      → 章节详情（Markdown 渲染）
/content/plotlines         → 暗线管理
/content/search            → 全局搜索
/agents                    → Agent 配置
/settings                  → 系统设置
/memory                    → 记忆管理
```

## 六、关键组件树

```
App
├── MainLayout (侧边导航 + 顶栏 + 内容区)
│   ├── Sidebar
│   │   ├── WorkspaceSwitcher     # 工作空间切换下拉
│   │   ├── NavMenu               # 导航菜单
│   │   └── WorkspaceActions      # 新建/重命名/删除工作空间
│   ├── Header
│   │   ├── Breadcrumb
│   │   ├── GlobalSearch
│   │   └── UserMenu
│   └── Content
│       ├── WorkspacePage
│       │   ├── WorkspaceList
│       │   └── CreateWorkspaceModal
│       ├── CharactersPage
│       │   ├── CharacterTable
│       │   ├── CharacterDetailDrawer
│       │   └── RelationGraph      # 人物关系图谱可视化
│       ├── ChaptersPage
│       │   ├── ChapterList
│       │   └── ChapterViewer       # Markdown 渲染器
│       ├── PlotLinesPage
│       │   ├── PlotLineTimeline
│       │   └── PlotLineEditor
│       ├── AgentConfigPage
│       │   ├── AgentCard           # 单个 Agent 配置卡片
│       │   └── AgentStatusBadge
│       ├── SettingsPage
│       │   ├── ThemeSelector
│       │   ├── LanguageSelector
│       │   └── BackupManager
│       └── MemoryPage
│           ├── EntityList
│           ├── RelationGraph       # 复用图谱可视化
│           ├── ForeshadowList
│           └── MemoryEditor
└── Shared Components
    ├── MarkdownViewer
    ├── SearchBar
    ├── ConfirmDialog
    ├── LoadingSpinner
    └── ErrorBoundary
```

## 七、状态管理设计 (Zustand)

```typescript
// 主要 Store
workspaceStore: {
  workspaces: Workspace[],
  currentWorkspace: Workspace | null,
  loading: boolean,
  // actions: fetchWorkspaces, createWorkspace, switchWorkspace, ...
}

contentStore: {
  characters: Character[],
  chapters: Chapter[],
  plotLines: PlotLine[],
  selectedChapter: Chapter | null,
  // actions: fetchCharacters, updateCharacter, ...
}

agentStore: {
  agents: AgentConfig[],
  // actions: updateAgentConfig, toggleAgent, ...
}

settingsStore: {
  theme: 'light' | 'dark',
  language: 'zh' | 'en',
  // actions: updateSettings, ...
}

memoryStore: {
  entities: Entity[],
  relations: Relation[],
  foreshadowing: Foreshadow[],
  // actions: fetchEntities, updateEntity, syncMemory, ...
}
```

## 八、多 Agent 任务拆分

### Agent 1: 后端 API 服务器 (`novels_project/src/novels_project/api/`)
**职责**: 搭建 FastAPI 服务器，实现所有 REST API 端点

**子任务**:
1.1 创建 FastAPI 入口 (`server.py`) 和 API 路由结构
1.2 实现工作空间 API (`api/workspace.py`) - CRUD + 切换
1.3 实现内容管理 API (`api/content.py`) - 人物/章节/暗线/搜索/批注
1.4 实现 Agent 配置 API (`api/agent.py`) - 配置读写
1.5 实现系统设置 API (`api/settings.py`) - 设置/备份/恢复
1.6 实现记忆管理 API (`api/memory.py`) - 图谱 CRUD + 同步
1.7 更新 `pyproject.toml` 添加 FastAPI 依赖和启动命令

**预估工时**: 4-6h

---

### Agent 2: 前端基础框架 (`novels_project/frontend/`)
**职责**: 搭建 React 项目，实现布局、路由、状态管理、API 客户端

**子任务**:
2.1 初始化 Vite + React + TypeScript 项目
2.2 安装依赖 (antd, zustand, react-router, axios, react-markdown 等)
2.3 实现 MainLayout（侧边导航 + 顶栏 + 内容区）
2.4 实现路由配置和页面占位组件
2.5 实现 Zustand Store 模板和 API 服务层
2.6 实现通用组件（MarkdownViewer, SearchBar, ErrorBoundary 等）

**预估工时**: 3-4h

---

### Agent 3: 工作空间 + 内容管理页面
**职责**: 实现工作空间管理和小说内容管理的前端页面

**子任务**:
3.1 工作空间管理页面（列表/创建/切换/重命名/删除）
3.2 人物卡管理页面（表格/详情/编辑/删除）
3.3 人物关系图谱可视化
3.4 章节列表页面 + 章节 Markdown 阅读器
3.5 暗线管理页面（时间线/编辑）
3.6 全局搜索页面
3.7 内容批注与 Agent 修改交互

**预估工时**: 5-6h

---

### Agent 4: Agent 配置 + 系统设置 + 记忆管理页面
**职责**: 实现 Agent 配置、系统设置、记忆管理的前端页面

**子任务**:
4.1 Agent 配置页面（卡片式配置/启用禁用/状态显示）
4.2 系统设置页面（主题/语言/通知/备份恢复）
4.3 记忆管理页面（实体列表/关系图谱/伏笔列表）
4.4 记忆编辑器（实体/关系 CRUD）
4.5 记忆同步触发与状态显示

**预估工时**: 4-5h

---

## 九、执行顺序与依赖关系

```
Phase 1: Agent 1 (后端 API)  ← 先行，其他 Agent 依赖 API
Phase 2: Agent 2 (前端框架)  ← 与 Agent 1 可并行
Phase 3: Agent 3 + Agent 4  ← 依赖 Agent 1 + Agent 2 完成
Phase 4: 联调测试           ← 全部完成后
```

```
Agent 1 (后端API) ──────────────────┐
                                     ├──→ Agent 3 (工作空间+内容)
Agent 2 (前端框架) ──────────────────┘
                                     ├──→ Agent 4 (配置+设置+记忆)
                                     └──→ 联调测试
```

## 十、启动方式

### 开发模式
```bash
# 终端 1: 启动后端 API 服务
cd novels_project
PYTHONPATH=src novels-server

# 终端 2: 启动前端开发服务器
cd novels_project/frontend
npm run dev
# 访问 http://localhost:5173 （Vite 代理到后端 8000）
```

### 生产模式
```bash
# 构建前端
cd novels_project/frontend
npm run build

# 启动后端（自动托管前端静态文件）
cd novels_project
PYTHONPATH=src novels-server
# 访问 http://127.0.0.1:8000
```