# 下一迭代计划（v2）

> 范围：在现有 **分层记忆管理**（Phase 13）基础上继续推进。  
> 周期：**4 周**，分为 3 个 Sprint。

---

## 1. 目标概览

| 目标 | 关键产出 |
|------|----------|
| **提升生产可靠性** | 流式响应持久化、章节自动归档 |
| **扩展能力** | Anthropic Skills 集成（`.md` / `.json`） |
| **优化性能** | 增量索引、全文搜索高亮 |
| **技术债清零** | 清理 `any`、测试覆盖率 ≥ 95%（含前端）、完善文档、性能基准 |

---

## 2. 优先级调整（与上一版对比）

| 旧 | 新 | 需求点 |
|------|------|------|
| P0 | P0 | 流式响应持久化 |
| ~~P0~~ | ❌ | ~~多用户协作锁定~~（已移除） |
| **新** | **P0** | **Anthropic Skills 集成** |
| P1 | **P0** | **章节自动归档**（已升级） |
| P1 | **P0** | **增量索引**（已升级） |
| P2 | **P0** | **全文搜索高亮定位**（已升级） |
| P1 | P1 | 记忆图谱可视化 |
| P1 | P1 | Agent 性能监控面板 |
| **P2** | **P1** | **暗线 / 伏笔时间线视图**（已升级） |
| P0 | P2 | Agent 配置版本控制（已降级） |
| ~~P2~~ | ❌ | ~~导出 Markdown → EPUB~~（已移除） |
| ~~P3~~ | ❌ | ~~多语言切换~~（已移除） |
| ~~P3~~ | ❌ | ~~WebSocket 实时同步~~（已移除） |
| ~~P3~~ | ❌ | ~~插件系统~~（已移除） |

> **本期不考虑 MCP**，但 Tool 调用函数**已支持**（沿用现有系统），Anthropic Skills 仅作为**技能知识库**附加到 Agent。

---

## 3. 详细需求

### 3.1 P0 — 必须做

#### 3.1.1 流式响应持久化
- **背景**：`/api/agent-sessions/.../turns` 当前是实时流，未持久化，崩溃后丢失。
- **范围**：
  - 每次 `handleTurn` 时把每个 `message.delta` 事件写入 `agent_session_messages` 表（可选用 SQLite + WAL）。
  - 客户端可通过 `?since=msg_id` 拉取已持久化的部分，断线重连后从上次 `msg_id` 继续。
  - 持久化失败时**不影响**流式返回（fallback 到内存）。
- **验收**：
  - 模拟 `kill -9` 后重新调用 API，能恢复最近 50 条事件。
  - 性能：单轮 P95 延迟增加 ≤ 5 ms。
- **估时**：2‑3 天

#### 3.1.2 Anthropic Skills 集成
- **背景**：Anthropic Skills（[claude-skills](https://docs.claude.com/en/docs/build-with-claude/skills)）采用 **Markdown 知识文件 + JSON 元数据**。本期仅集成**技能加载与注入**，不涉及 MCP。
- **格式**：
  - `.md`：技能说明、示例、最佳实践（注入到 System Prompt）。
  - `.json`：技能元数据
    ```json
    {
      "name": "novel-character-design",
      "version": "1.0.0",
      "description": "为小说设计人物性格与背景",
      "tags": ["character", "design"],
      "applies_to": ["novelist", "character-designer"]
    }
    ```
- **Tool 调用**：复用现有 `tool_calls` 体系（已支持），Skills 不再额外实现工具函数。
- **存储**：`/agents/{agent_id}/skills/*.md` + `/agents/{agent_id}/skills/index.json`。
- **API**：
  - `GET    /api/agents/{id}/skills`
  - `POST   /api/agents/{id}/skills`（上传 .md / .json）
  - `DELETE /api/agents/{id}/skills/{name}`
  - `POST   /api/agents/{id}/skills/reload`（重新解析）
- **前端**：`AgentConfigPage` 增 `技能管理` Tab，支持拖拽上传 / 启用 / 停用。
- **验收**：
  - 上传 `novel-character-design.md` + 对应 `index.json` 后，`handleTurn` 的 system prompt 中包含技能内容。
  - 关闭技能后，prompt 长度下降 ≥ 30%。
- **估时**：3‑4 天

#### 3.1.3 章节自动归档
- **触发条件**：**章节总数 > 50**（按章数触发，不考虑时间）。
- **行为**：
  - 当工作区中章节数超过 50 时，提示用户「即将归档最早 N 章（默认 10），是否继续？」
  - 用户确认后，将最早 N 章的原文 + 摘要移到 `archive/` 子目录，标记 `archived=true`。
  - 列表 UI 增加 `已归档` 过滤项，默认隐藏归档章节。
- **API**：
  - `GET    /api/content/chapters/archive/list`
  - `POST   /api/content/chapters/archive`（body: `{count: 10}`）
  - `POST   /api/content/chapters/{id}/restore`
- **验收**：
  - 60 章工作区点击归档按钮后，列表显示 50 章，归档目录存在 10 个 `.md`。
  - 归档/恢复操作幂等。
- **估时**：1‑2 天

#### 3.1.4 增量索引
- **背景**：当前 `memoryApi.sync()` 是全量重建实体/关系，章节更新时浪费算力。
- **范围**：
  - 在 `chapter_id` 维度记录 `last_indexed_at` 时间戳。
  - 章节更新时只对**该章**做 NER 与关系抽取，合并到图谱。
  - 删除章节时清理其所有实体、关系、伏笔。
- **验收**：
  - 单章更新耗时 < 全量的 1/10（50 章工作区）。
  - 关系抽取的 F1 得分在测试集上不下降。
- **估时**：2 天

#### 3.1.5 全文搜索高亮定位
- **背景**：当前 `search` API 返回 `chapter_id + snippet`，但前端无法跳转定位。
- **范围**：
  - 搜索结果增加 `match_positions: [{chapter_id, start, end, text}]` 字段。
  - 前端跳转时把 `?hl=start-end` 写入 URL，在章节详情页用 `<mark>` 包裹命中区间。
- **验收**：
  - 搜索「伏笔」后跳转到对应章节并高亮所有命中位置。
  - 刷新页面时高亮位置保持。
- **估时**：1 天

### 3.2 P1 — 高价值

| # | 功能 | 描述 | 估时 |
|---|------|------|------|
| 3.2.1 | 记忆图谱可视化 | 集成 `react-flow`，展示实体/关系节点，支持拖拽、缩放、按角色过滤 | 2‑3 天 |
| 3.2.2 | Agent 性能监控 | 后端埋点调用次数/token/P95；前端 `Dashboard` 折线图 | 1‑2 天 |
| 3.2.3 | 暗线 / 伏笔时间线视图 | 按章节 X 轴展示伏笔布置/回收节点，鼠标悬停查看详情 | 1‑2 天 |

### 3.3 P2 — 体验优化

| # | 功能 | 描述 | 估时 |
|---|------|------|------|
| 3.3.1 | Agent 配置版本控制 | YAML 文件加版本号，UI 显示历史，支持回滚 | 1‑2 天 |

---

## 4. 技术债务

| 任务 | 指标 | 估时 |
|------|------|------|
| **清理 `any`** | 96 → 0 条 warning | 2‑3 天 |
| **测试覆盖率** | 80% → **≥ 95%**（含前端 vitest --coverage） | 1 周 |
| **完善文档** | OpenAPI、架构图、部署指南、ADR | 2 天 |
| **性能基准** | API P95、压缩耗时、查询延迟、索引增量耗时 | 2 天 |

---

## 5. Sprint 排期

### Sprint 1（第 1‑2 周）— P0 主线 + 技术债启动
| 任务 | 内容 | 天数 |
|------|------|------|
| 1.1 | 流式响应持久化 | 3 |
| 1.2 | 章节自动归档（> 50 触发） | 1 |
| 1.3 | 全文搜索高亮定位 | 1 |
| 1.4 | 清理 `any`（按模块） | 1 |
| 1.5 | 性能基准脚本（`pytest-benchmark`） | 1 |
| 1.6 | 测试覆盖率达 90% | 1 |

### Sprint 2（第 2‑3 周）— P0 进阶 + 文档
| 任务 | 内容 | 天数 |
|------|------|------|
| 2.1 | 增量索引 | 2 |
| 2.2 | Anthropic Skills 集成 | 4 |
| 2.3 | 文档补全（OpenAPI / 架构图 / 部署） | 2 |

### Sprint 3（第 3‑4 周）— P1 收尾 + P2 + 收尾
| 任务 | 内容 | 天数 |
|------|------|------|
| 3.1 | 记忆图谱可视化（react-flow） | 3 |
| 3.2 | Agent 性能监控面板 | 2 |
| 3.3 | 暗线 / 伏笔时间线视图 | 2 |
| 3.4 | 测试覆盖率达 95%+ | 1 |
| 3.5 | Agent 配置版本控制（P2） | 1 |

---

## 6. 关键路径（Critical Path）

1. **流式响应持久化** → **Anthropic Skills 集成**（后者依赖前者提供的会话存储）  
2. **增量索引** → **记忆图谱可视化**（后者依赖增量数据）  
3. **清理 `any`** 与 **测试覆盖率** 需贯穿整个迭代，不能压在最后  

---

## 7. 风险与对策

| 风险 | 影响 | 对策 |
|------|------|------|
| 流式持久化引入 I/O 抖动 | P95 上升 | 异步批量写入 + 监控报警 |
| Anthropic Skills 格式不规范 | 上传失败 | 严格 JSON Schema 校验 + 友好错误提示 |
| 章节归档误删 | 用户数据丢失 | **强制二次确认** + `dry-run` 预览 |
| 增量索引一致性 | 关系缺失 | 启动时仍做一次全量校验 |
| 测试覆盖率达 95% 投入大 | 进度延后 | 先覆盖核心模块（API、记忆、配置） |

---

## 8. 验收清单（Definition of Done）

- [ ] 所有 P0 功能通过集成测试  
- [ ] `pytest --cov` ≥ 95%，`vitest --coverage` ≥ 95%  
- [ ] `npm run lint:strict` 0 error，`ruff` 0 error  
- [ ] 文档：OpenAPI、架构图、部署指南、ADR 已发布  
- [ ] 性能基准报告已生成（`docs/perf/baseline.md`）  
- [ ] CI 全部绿灯（lint / test / build / coverage）  
- [ ] 已归档章节可恢复，已删除技能可重新上传  

---

## 9. 不在范围

- 多用户协作 / 多端实时同步
- MCP（Model Context Protocol）集成
- 多语言切换（i18n）
- 插件市场 / 第三方扩展
- EPUB / PDF 导出

---

## 10. 参考资料

- 现有分层记忆管理计划：`docs/superpowers/plans/2026-06-11-layered-memory-management.md`  
- Lint 规范：`docs/lint-guidelines.md`  
- Anthropic Skills 概念：https://docs.claude.com/en/docs/build-with-claude/skills
