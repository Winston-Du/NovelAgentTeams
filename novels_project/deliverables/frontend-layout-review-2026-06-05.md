# NovelAgentTeams 前端布局与交互审查报告

**日期**: 2026-06-05  
**审查范围**: frontend/ 全部源文件（15 个 TSX + 1 个 CSS）  

---

## TL;DR

前端整体架构清晰：React + Ant Design + React Router，15 个页面组件覆盖了从人物卡、章节、暗线到 Agent 配置、记忆管理的完整工作流。无严重布局缺陷，但存在 **5 个中优先级改进点**：全局样式单文件过薄（仅 75 行）、页面间缺乏共享卡片组件、状态管理仅靠单 store、无 loading skeleton、无响应式断点适配。

---

## 架构概览

| 层次 | 技术选型 | 文件数 |
|------|---------|--------|
| 路由 | React Router v6 `useRoutes` | App.tsx |
| UI 框架 | Ant Design 5.x | 全局 |
| 状态管理 | 自建 `workspaceStore` (zustand?) | 1 store |
| 样式 | 全局 CSS + Ant Design token | index.css (75行) |
| API | Axios 封装 `services/api` | 1 service |

**路由结构**：
```
/ → /content/chapters (默认)
├── /content/characters
├── /content/chapters
├── /content/chapters/:chapterId
├── /content/plotlines
├── /agents
├── /memory
├── /settings
└── /settings/workspace
```

---

## 页面清单

| 页面 | 文件 | 核心交互 | 状态 |
|------|------|---------|------|
| 主布局 | `MainLayout.tsx` | 可折叠侧边栏 + 顶栏 | ✅ |
| 工作空间管理 | `WorkspacePage.tsx` | 工作空间选择 | ⚠️ |
| 人物卡管理 | `CharactersPage.tsx` | 表格+新建/编辑/删除/详情抽屉 | ✅ |
| 章节管理 | `ChaptersPage.tsx` | 章节列表 | ✅ |
| 章节详情 | `ChapterDetailPage.tsx` | 章节编辑器 | ✅ |
| 暗线管理 | `PlotLinesPage.tsx` | 暗线列表 | ✅ |
| 全局搜索 | `SearchPage.tsx` | 全文搜索 | ✅ |
| 记忆管理 | `MemoryPage.tsx` | 知识图谱可视化 | ⚠️ |
| Agent 配置 | `AgentConfigPage.tsx` | Agent 参数配置 | ✅ |
| 基础设置 | `SettingsPage.tsx` | 全局设置 | ✅ |

---

## 发现的问题

### 🔴 P0 - 阻塞（0 项）
无。

### 🟠 P1 - 建议修复（3 项）

| # | 问题 | 位置 | 严重度 | 建议 |
|---|------|------|--------|------|
| 1 | 全局 CSS 过薄 | `index.css` (75行) | 中 | 拆分为 `variables.css`、`layout.css`、`markdown.css`，或迁移到 CSS Modules |
| 2 | 缺少 Loading Skeleton | 所有列表页 | 中 | 用 `<Skeleton>` 替代 `Spin`，改善加载体验 |
| 3 | 无响应式断点 | `MainLayout.tsx` | 中 | 移动端 Sider 自动隐藏，Content 区域 100% 宽度 |

### 🟡 P2 - 优化建议（2 项）

| # | 问题 | 位置 | 建议 |
|---|------|------|------|
| 4 | 人物卡表单字段硬编码 | `CharactersPage.tsx` | `FIELD_LABELS` 可迁移到 `shared/` 与后端对齐 |
| 5 | 状态管理单一 store | `stores/workspaceStore.ts` | 可按 domain 拆分：`characterStore`、`chapterStore`、`memoryStore` |

---

## MainLayout 详细分析

```
┌─────────────────────────────────────────────┐
│ Sider (220px)          │  Header            │
│ ┌─────────────────┐    │  [折叠] [工作空间]  │
│ │ NovelAgentTeams  │    │         [新建]     │
│ ├─────────────────┤    ├────────────────────┤
│ │ 内容管理         │    │                    │
│ │  人物卡管理       │    │  Content (24px)   │
│ │  章节管理         │    │  margin: 24px     │
│ │  暗线管理         │    │  padding: 24px    │
│ │                  │    │  radius: token     │
│ │ Agent 配置       │    │                    │
│ │ 记忆管理         │    │                    │
│ │ 基础设置         │    │                    │
│ └─────────────────┘    │                    │
└─────────────────────────────────────────────┘
```

**评分**：
- 导航逻辑：✅ 选中高亮 + 打开折叠正确
- 主题一致性：✅ 全用 `token.color*` 变量
- 可访问性：⚠️ 无 `aria-label`、无键盘导航支持
- 折叠状态：⚠️ 标题缩写为 "NA" 可读性稍差

---

## CharactersPage 交互流程

```
页面加载 → fetchCharacters()
    ↓
表格显示（name + tier + role + 操作按钮）
    ↓
[查看] → Drawer（Descriptions 详情）
[编辑] → Modal（Form + AI 优化按钮）
[删除] → Popconfirm → fetchCharacters()
[新建] → Modal（Form，16 个字段下拉选择）
```

**评分**：
- CRUD 完整性：✅
- AI 优化集成：✅（`BulbOutlined` 图标触发 LLM 优化）
- 数组/对象字段处理：⚠️ 编辑时将数组 join('、') 再存为字符串 — 需确保后端能反序列化
- 错误处理：⚠️ 创建失败仅 `message.error`，无表单回填

---

## 视觉一致性

| 元素 | 现状 | 评分 |
|------|------|------|
| 配色 | Ant Design 默认 + token 主题变量 | ✅ |
| 字体 | 系统字体栈（-apple-system, BlinkMacSystemFont...） | ✅ |
| 间距 | 统一 24px margin + padding | ✅ |
| 圆角 | `token.borderRadiusLG` | ✅ |
| 分割线 | `token.colorBorderSecondary` | ✅ |
| 图标 | `@ant-design/icons` | ✅ |

---

## 综合结论

**🟢 Go — 前端无需重大重构**。当前架构满足功能需求，建议按 P1/P2 优先级逐步优化响应式、Loading 骨架和共享组件抽取。
