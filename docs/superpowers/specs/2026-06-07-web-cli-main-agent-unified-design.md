# Web端与CLI端主Agent统一架构设计方案

## 1. 背景与问题

当前项目已经具备完整的主 Agent 运行时能力，但存在明显的端侧能力分裂：

- CLI 端直接通过 `ConversationRuntime`、`AgentRunner`、`ToolRegistry`、`GraphMemoryIntegrator` 形成完整主链，支持直接调用模型、子 Agent 协作、工具执行与会话持久化。
- Web 端“创作助手”并未接入同一主链，而是走 `/api/content/annotate` 的提交式接口，只做批注文件持久化，不直接触发主 Agent。
- 各类能力分散在 `content`、`memory`、`settings`、`workspace`、`export` 等 API 模块中，缺少统一的应用服务层、统一事件协议、统一链路日志和统一错误模型。

这导致如下问题：

- Web 与 CLI 能力不一致，维护成本高。
- 主 Agent 编排逻辑无法成为全局唯一入口。
- 新增能力时容易在端侧重复实现业务逻辑。
- 异步任务、日志追踪、会话管理、错误处理缺少统一治理。

## 2. 设计目标

本方案的目标是建立“核心统一层 + 端侧适配层”的统一架构，实现：

- Web 与 CLI 共享全局唯一的主 Agent 核心逻辑。
- 主 Agent 统一负责意图识别、上下文管理、任务拆解、子 Agent 调度、结果聚合和异常兜底。
- Web 与 CLI 仅保留端侧协议和交互适配，不再保留任何业务编排逻辑。
- 对话型能力、动作型能力、CRUD 能力全部纳入统一治理体系。
- 建立统一的会话模型、事件协议、错误模型、日志链路和异步任务模型。

## 3. 设计原则

- 核心统一层只维护一套代码，Web 与 CLI 100% 复用。
- 现有 `ConversationRuntime`、`AgentRunner`、`ToolRegistry` 等核心执行资产保留，不推倒重来。
- 在运行时之上新增统一应用服务层，屏蔽 Web/CLI/各类 API 差异。
- 所有端侧都通过统一应用服务入口访问主 Agent。
- 所有关键路径必须具备结构化日志、trace id 和可测试的契约边界。
- 旧接口采用“兼容壳层 -> 切流 -> 废弃”的渐进迁移方式。

## 4. 目标架构

### 4.1 分层结构

#### 端侧适配层

- Web Adapter
  - 接收前端对话请求
  - 建立 SSE 或 WebSocket 流
  - 管理浏览器会话标识与端侧上下文
  - 渲染统一事件协议
- CLI Adapter
  - 处理 REPL 和命令行参数
  - 将统一事件流渲染为终端输出
  - 处理本地会话恢复、终端交互和命令兼容

#### 统一应用服务层

- `MainAgentService`
  - 全局唯一主入口
  - 负责一次 turn 的完整生命周期
- `SessionFacade`
  - 统一会话管理、上下文恢复、session compaction、usage 持久化
- `CapabilityRouter`
  - 统一请求分类与执行路径选择
- `StreamBridge`
  - 将运行时输出转换为统一事件协议
- `TraceService`
  - 统一 trace、span、结构化日志与指标输出
- `contracts.py`
  - 统一契约对象、枚举和错误码

#### 统一核心执行层

- `ConversationRuntime`
  - LLM 主循环
- `AgentRunner`
  - 子 Agent 运行时
- `MainToolExecutor` / `SubAgentToolExecutor`
  - 工具执行和子 Agent 工具路由
- `ToolRegistry`
  - 工具与子 Agent 注册中心
- `GraphMemoryIntegrator`
  - 图谱记忆、上下文注入、同步治理
- 检索、反馈、迭代控制、向量库等基础能力

#### 领域能力层

- `ContentCapabilityService`
- `CharacterCapabilityService`
- `MemoryCapabilityService`
- `ExportCapabilityService`
- `WorkspaceCapabilityService`
- `SettingsCapabilityService`

### 4.2 统一调用主链

#### Web 主链

1. 前端聊天 UI 调用 `/api/agent-sessions/{session_id}/turns`
2. Web Adapter 接收请求并构造统一 turn request
3. `MainAgentService.handle_turn()` 执行主流程
4. `SessionFacade` 恢复会话和上下文
5. `CapabilityRouter` 决定路径：
   - 主 Agent 直接回复
   - 主 Agent 编排子 Agent
   - 能力服务执行
   - 异步任务下发
6. 若进入主 Agent 主链，则调用 `ConversationRuntime`
7. runtime 内部按需通过 `MainToolExecutor` 调起 `AgentRunner`
8. `StreamBridge` 将输出转换为统一事件流
9. Web 端按事件流更新 UI
10. `TraceService` 记录完整链路

#### CLI 主链

1. CLI 输入经 CLI Adapter 标准化
2. CLI Adapter 调用 `MainAgentService.handle_turn()`
3. 后续执行路径与 Web 完全一致
4. 差异只体现在事件渲染方式：CLI 映射为终端输出

## 5. 模块职责

### 5.1 MainAgentService

职责：

- 统一接收 Web/CLI 对话请求
- 标准化请求上下文
- 组织一次 turn 的完整生命周期
- 触发会话恢复、路径路由、执行、流式输出和收尾

建议公开方法：

- `create_session(request)`
- `handle_turn(request)`
- `get_session(session_id)`
- `list_messages(session_id)`
- `cancel_turn(session_id, turn_id)`

约束：

- 这是 Web 与 CLI 唯一允许直接调用的主 Agent 服务
- 不允许端侧绕过它直接操作 runtime

### 5.2 SessionFacade

职责：

- 统一屏蔽 CLI `Session + SessionStore` 与未来 Web session 存储差异
- 统一会话创建、恢复、消息追加、turn 元数据写入、usage 汇总、workspace 绑定
- 管理自动压缩、恢复失败兜底和跨端会话兼容

### 5.3 CapabilityRouter

职责：

- 统一识别请求执行路径，不承担具体执行

推荐路径类型：

- `chat_direct`
- `agent_orchestrated`
- `toolbacked_action`
- `async_job`
- `crud_passthrough`

### 5.4 StreamBridge

职责：

- 将 runtime 内部输出转换成统一事件协议
- 为 Web 生成 SSE/WebSocket 事件
- 为 CLI 生成终端可渲染事件

### 5.5 TraceService

职责：

- 生成 `trace_id`、`turn_id`
- 记录入口、路由、主 Agent、子 Agent、工具、能力服务、结束日志
- 输出结构化日志和指标

### 5.6 Capability Services

职责：

- 承接原分散在内容、导出、记忆、设置、工作空间等模块内的领域能力
- 为 `CapabilityRouter` 提供统一执行目标
- 避免复杂能力直接散落在 API 层

## 6. 统一接口设计

### 6.1 创建会话

`POST /api/agent-sessions`

请求示例：

```json
{
  "client_type": "web",
  "workspace": "default",
  "user_id": "user-001",
  "scene": "creative_assistant",
  "metadata": {
    "entry": "chapters_page"
  }
}
```

### 6.2 发起一轮对话

`POST /api/agent-sessions/{session_id}/turns`

请求示例：

```json
{
  "input": "帮我创作第3章，并保持上一章的情绪延续",
  "stream": true,
  "context": {
    "chapter_id": 3,
    "entry": "creative_assistant"
  },
  "client": {
    "type": "web"
  }
}
```

### 6.3 查询会话详情

`GET /api/agent-sessions/{session_id}`

### 6.4 查询消息历史

`GET /api/agent-sessions/{session_id}/messages`

### 6.5 查询链路详情

`GET /api/agent-sessions/{session_id}/turns/{turn_id}/trace`

## 7. 统一事件协议

建议统一事件结构：

```json
{
  "event": "agent.called",
  "trace_id": "tr_123",
  "session_id": "sess_123",
  "turn_id": "turn_456",
  "timestamp": "2026-06-07T12:00:00Z",
  "payload": {
    "agent_name": "plot_writer",
    "status": "started"
  }
}
```

建议事件集合：

- `turn.started`
- `context.loaded`
- `route.selected`
- `message.delta`
- `message.completed`
- `tool.called`
- `tool.completed`
- `agent.called`
- `agent.completed`
- `usage.updated`
- `turn.completed`
- `turn.failed`

## 8. 数据模型

### 8.1 AgentSession

核心字段：

- `session_id`
- `workspace`
- `user_id`
- `client_type`
- `scene`
- `status`
- `created_at`
- `updated_at`
- `last_turn_id`
- `usage_summary`
- `metadata`

### 8.2 AgentTurn

核心字段：

- `turn_id`
- `session_id`
- `trace_id`
- `input`
- `route_type`
- `status`
- `started_at`
- `completed_at`
- `error_code`
- `error_message`
- `client_context`

### 8.3 AgentMessage

核心字段：

- `message_id`
- `session_id`
- `turn_id`
- `role`
- `content`
- `content_blocks`
- `usage`
- `created_at`

### 8.4 ExecutionTrace

核心字段：

- `trace_id`
- `session_id`
- `turn_id`
- `root_span`
- `spans`
- `metrics`
- `status`

### 8.5 ExecutionSpan

核心字段：

- `span_id`
- `parent_span_id`
- `span_type`
- `name`
- `input_summary`
- `output_summary`
- `status`
- `started_at`
- `ended_at`
- `error`

## 9. 状态流转

### 9.1 Session 状态

- `created`
- `active`
- `compacted`
- `archived`
- `failed`

### 9.2 Turn 状态

- `queued`
- `routing`
- `running`
- `streaming`
- `awaiting_async`
- `completed`
- `partial_failed`
- `failed`
- `cancelled`

推荐主流转：

```text
queued -> routing -> running -> streaming -> completed
queued -> routing -> running -> awaiting_async
queued -> routing -> running -> partial_failed
queued -> routing -> running -> failed
```

## 10. 同步与异步执行边界

### 10.1 同步执行

- 通用问答
- 中短文本创作建议
- 单轮主 Agent 协调
- 人物字段优化
- 搜索、查询、轻量导出校验
- 会话恢复和历史读取

### 10.2 异步执行

- 超长章节创作
- 批量章节生成
- 图谱重建
- 向量库初始化或重建
- 批量导出
- 明确的复杂多阶段后台任务

### 10.3 路由原则

- Web 默认优先同步流式返回
- 命中异步策略时返回 `job_id + accepted`
- CLI 支持 `--wait` 或 `--async`

## 11. 异步任务模型

建议新增 `AsyncJob`：

- `job_id`
- `job_type`
- `source_session_id`
- `source_turn_id`
- `status`
- `progress`
- `created_at`
- `started_at`
- `completed_at`
- `result_ref`
- `error`

适用场景：

- 长文生成
- 批量修订
- 图谱或向量重建
- 导出批处理

## 12. 错误处理与降级策略

### 12.1 统一错误码

- `AUTH_ERROR`
- `VALIDATION_ERROR`
- `SESSION_ERROR`
- `ROUTING_ERROR`
- `MODEL_ERROR`
- `TOOL_ERROR`
- `SUB_AGENT_ERROR`
- `CAPABILITY_ERROR`
- `TIMEOUT_ERROR`
- `INTERNAL_ERROR`

### 12.2 统一错误响应

```json
{
  "error": {
    "code": "SUB_AGENT_ERROR",
    "message": "plot_writer 执行失败",
    "trace_id": "tr_123",
    "retryable": true,
    "details": {
      "agent_name": "plot_writer"
    }
  }
}
```

### 12.3 降级原则

- 子 Agent 失败但主 Agent 可总结已有结果时，返回 `partial_failed`
- 流式中断但已有部分文本时，保留部分结果并标记未完成
- 非关键能力失败不拖垮主对话
- session 持久化失败时，CLI 可退回内存 session，Web 返回可恢复错误

## 13. 调用链日志与可观测性

### 13.1 日志层次

- 入口日志
- 路由日志
- 主 Agent 日志
- 子 Agent 日志
- 工具日志
- 能力服务日志
- 结束日志

### 13.2 结构化日志格式

```json
{
  "timestamp": "2026-06-07T12:00:00Z",
  "level": "INFO",
  "trace_id": "tr_123",
  "session_id": "sess_123",
  "turn_id": "turn_456",
  "span_type": "sub_agent",
  "name": "plot_writer",
  "status": "completed",
  "duration_ms": 1840
}
```

### 13.3 指标建议

- `turn_total`
- `turn_success_total`
- `turn_failed_total`
- `turn_partial_failed_total`
- `sub_agent_invocation_total`
- `sub_agent_success_rate`
- `tool_error_rate`
- `avg_turn_latency_ms`
- `p95_turn_latency_ms`
- `async_job_total`
- `async_job_success_rate`
- `stream_interrupt_total`

## 14. 现有 API 全量并入策略

### A 类：直接并入主 Agent 主链

- Web 创作助手
- 所有聊天式请求
- 章节创作、润色、分析、改写、世界观咨询

### B 类：并入 CapabilityRouter

- 人物优化
- 搜索
- 导出
- 图谱同步
- 向量初始化

### C 类：保留 CRUD API，但接统一基础设施

- 角色 CRUD
- 章节读取
- 工作空间切换
- 设置管理

统一接入：

- 鉴权
- trace id
- error schema
- audit log
- workspace 上下文

### D 类：废弃或降级旧接口

- `/api/content/annotate`

处理策略：

- 短期：deprecated
- 中期：前端完全切换到 `agent-sessions`
- 长期：删除或仅保留兼容壳层

## 15. 目录重构建议

```text
src/novels_project/
  application/
    main_agent_service.py
    session_facade.py
    capability_router.py
    stream_bridge.py
    trace_service.py
    contracts.py
  capabilities/
    content_service.py
    character_service.py
    export_service.py
    memory_service.py
    settings_service.py
    workspace_service.py
  interfaces/
    web/
      agent_sessions_api.py
      adapters.py
    cli/
      cli_adapter.py
      renderers.py
  runtime.py
  agents.py
  tool_executor.py
  tool_spec.py
```

## 16. 现有文件改造建议

- `src/novels_project/cli.py`
  - 保留命令入口
  - 业务主链迁移到 CLI Adapter + `MainAgentService`
- `src/novels_project/server.py`
  - 注册 `agent-sessions` 路由
  - 增加统一 trace middleware
- `src/novels_project/api/content.py`
  - 保留 CRUD
  - `/annotate` 废弃
  - `optimize` 下沉到 capability service
- `frontend/src/pages/Content/ChaptersPage.tsx`
  - 创作助手改接统一会话 API
- `frontend/src/services/api.ts`
  - 新增 `agentSessionsApi`
  - 旧 `annotate` 仅保兼容

## 17. 测试矩阵

### 17.1 单元测试

- `MainAgentService`
- `SessionFacade`
- `CapabilityRouter`
- `StreamBridge`
- `TraceService`
- 各 `CapabilityService`

### 17.2 集成测试

- Web API -> `MainAgentService` -> runtime -> tool -> sub-agent
- CLI Adapter -> `MainAgentService`
- session 持久化与恢复
- 异步 job 状态流转
- 统一错误模型

### 17.3 端到端测试

- Web 创作助手完整链路
- CLI 单轮、REPL、多轮、命令兼容
- 跨端一致性验证

### 17.4 性能与稳定性测试

- 平均耗时、P95、P99
- 跨端延迟差异
- 子 Agent 成功率
- SSE 稳定性
- 异步任务高并发状态一致性

## 18. 验收标准

### 18.1 架构验收

- Web 与 CLI 均只通过 `MainAgentService` 调用主 Agent
- 端侧不存在重复主 Agent 编排逻辑
- 所有对话型能力统一使用 `agent-sessions` 协议

### 18.2 功能验收

- Web 创作助手不再调用旧 `/annotate`
- Web 与 CLI 共享同一 session/turn 模型和事件协议
- 内容、记忆、导出、设置、工作空间能力完成统一分层接入

### 18.3 质量验收

- 核心层单元、集成、E2E 全通过
- `application` 层覆盖率建议不低于 85%
- `session/router/trace` 关键模块覆盖率建议不低于 90%
- 子 Agent 成功率不低于 99.5%
- 跨端延迟差异不超过 100ms

### 18.4 可观测性验收

- 每次 turn 可追到 `trace_id`
- 每次子 Agent、工具、能力服务调用均有 span
- 错误日志可定位到 session、turn、span

## 19. 迁移路线

### Phase 0：基建补齐

- 新建 `application/`、`capabilities/`、`interfaces/`
- 建立 `contracts.py`、`TraceService`、`SessionFacade` 骨架

### Phase 1：统一主 Agent 服务落地

- 实现 `MainAgentService`
- CLI 先接统一服务层
- 保留现有 CLI 外观

### Phase 2：Web 对话主链切换

- 新增 `/api/agent-sessions`
- 前端章节页助手切换到新接口
- `/annotate` 标记 deprecated

### Phase 3：外围能力全量并入

- `optimize`、memory、export、workspace、settings 下沉到 capability service
- 旧 API 外壳保留，内部改调统一能力服务

### Phase 4：异步任务与治理收口

- 引入正式 `AsyncJob`
- 大任务切换到 job 模型
- 完成 trace、指标、降级和治理收口
- 删除或仅保留兼容壳层的旧入口

## 20. 多智能体并行开发分工

### A 组：统一应用服务层

- `MainAgentService`
- `SessionFacade`
- `CapabilityRouter`
- `contracts.py`

### B 组：链路与观测

- `TraceService`
- 统一错误模型
- 结构化日志
- 指标埋点

### C 组：Web 适配层

- `agent-sessions` API
- SSE
- 前端 chat API
- 章节页助手接入

### D 组：CLI 适配层

- CLI Adapter
- renderers
- 旧命令兼容
- 统一 session 接入

### E 组：Capability 收口

- content
- export
- memory
- settings
- workspace

### F 组：测试与验收

- 测试基建
- 集成测试
- E2E
- 性能基线
- 回归清单

## 21. 协作规则

- 统一以 `contracts.py` 为协议真源
- 禁止各组私自扩字段
- 所有新增接口先补契约文档，再写实现
- 所有 trace/event/error code 使用统一枚举
- 旧 API 改造必须先保兼容，再逐步切流
- 每个工作流提交都必须附：
  - 影响模块
  - 是否改协议
  - 是否影响 Web/CLI 一致性
  - 测试结果

## 22. 最终交付物

### 22.1 Markdown 主文档

文件路径：

`docs/superpowers/specs/2026-06-07-web-cli-main-agent-unified-design.md`

### 22.2 JSON 索引

文件路径：

`docs/superpowers/specs/2026-06-07-web-cli-main-agent-unified-index.json`

用于提供：

- 模块清单
- 文件建议路径
- API 列表
- 事件类型
- 错误码
- phase 拆解
- workstream 依赖

## 23. 治理规则

- 核心统一层变更，必须同步验证 Web/CLI 两端
- 端侧层只允许处理展示和协议适配，不允许新增业务编排
- 新增 Agent 能力必须先接入统一层，再暴露给具体端侧
- 旧接口废弃遵循：
  1. 标记 deprecated
  2. 端侧切换
  3. 回归通过后删除

## 24. 附录：常见错误排查

### 24.1 `net::ERR_ABORTED` 错误（Agent 会话 SSE 流中断）

**错误表现**：
前端浏览器控制台显示 `net::ERR_ABORTED http://localhost:5174/api/agent-sessions/{session_id}/turns`，创作助手显示"发送失败，请稍后重试"。

**根因分析**：

1. **后端并发安全问题**：`MainAgentService` 使用全局单例 `_api_client`，并发请求会互相覆盖 `set_event_callback`，导致 SSE 事件流混乱或中断。
2. **前端缺少请求取消机制**：关闭浮窗或组件卸载时未取消进行中的 `fetch` 请求，可能导致 `ERR_ABORTED`。
3. **Vite 代理缓冲 SSE**：开发服务器代理默认可能缓冲流式响应，导致连接异常。

**修复方案**：

1. **后端**：每个 `handle_turn` 调用创建独立的 `StreamingApiClient` 实例，避免并发回调覆盖：
   ```python
   turn_client = StreamingApiClient(
       base_url=self._api_client.base_url,
       api_key=self._api_client.api_key,
       default_model=self._api_client.default_model or self._model,
   )
   turn_client.set_event_callback(on_event)
   ```

2. **前端**：使用 `AbortController` 管理请求生命周期：
   ```typescript
   const abortController = new AbortController();
   agentAbortRef.current = abortController;
   const response = await agentSessionsApi.handleTurn(sessionId, text, {}, abortController.signal);
   ```
   关闭浮窗或组件卸载时调用 `abortController.abort()`。

3. **Vite 配置**：为 SSE 端点禁用代理缓冲：
   ```typescript
   proxy: {
     '/api': {
       target: 'http://127.0.0.1:8000',
       changeOrigin: true,
       configure: (proxy, _options) => {
         proxy.on('proxyRes', (proxyRes, req) => {
           if (req.url?.includes('/agent-sessions') && req.url?.includes('/turns')) {
             proxyRes.headers['cache-control'] = 'no-cache';
             proxyRes.headers['connection'] = 'keep-alive';
           }
         });
       },
     },
   }
   ```

### 24.2 405 Method Not Allowed（API 路径末尾斜杠）

**根因**：前端 `api.ts` 中部分路径以 `/` 结尾（如 `/agent-sessions/`），与 FastAPI 路由不匹配。

**修复**：移除所有 API 路径末尾的斜杠，统一为 `/agent-sessions`。

## 25. 结论

本方案以"统一应用服务层"作为当前项目最适合的统一基线，在最大限度复用现有 runtime/agent/tool/memory 资产的前提下，将 Web 与 CLI 的主 Agent 能力收口为一条全局唯一主链，并通过统一协议、统一日志、统一错误模型、统一异步任务机制实现跨端一致、可观测、可演进的系统架构。
