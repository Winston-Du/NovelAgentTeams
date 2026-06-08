# NovelAgentTeams 总编对话功能 + 架构升级 QA 测试方案

**日期**: 2025-06-05  
**项目版本**: 0.2.0 → 0.4.0（目标）  
**QA 负责人**: GStack QA Lead  
**现有测试基数**: 1,424 条测试函数 / 295 个测试类 / 20,601 行测试代码  
**现有覆盖率阈值**: 75%（分支覆盖）

---

## 1. 测试策略总览

### 1.1 测试金字塔分布

```
         ╱  E2E (8%)   ╲        ~55 条
        ╱  集成测试 (27%) ╲      ~185 条
       ╱  单元测试 (65%)   ╲     ~445 条
      ━━━━━━━━━━━━━━━━━━━━━━━━
            总计新增: ~685 条
```

| 层级 | 占比 | 新增预估 | 说明 |
|------|------|----------|------|
| **单元测试** | 65% | ~445 条 | 函数级，mock 所有外部依赖。覆盖异步化改造核心、提示词配置加载、SSE 解析 |
| **集成测试** | 27% | ~185 条 | FastAPI TestClient + 真实 LLM mock。覆盖 API 路由、Session 生命周期、工具调用链 |
| **E2E 测试** | 8% | ~55 条 | 全链路：前端 → API → Runtime → Agent → 工具。Playwright/Cypress + 录制回放 |

### 1.2 各功能测试分布矩阵

| 功能 | 单元 | 集成 | E2E | 合计 |
|------|------|------|-----|------|
| A. 异步化改造 | 180 | 60 | 10 | **250** |
| B. 总编对话 API | 120 | 75 | 30 | **225** |
| C. 可观测性 | 50 | 30 | 5 | **85** |
| D. 提示词配置化 | 95 | 20 | 10 | **125** |
| **合计** | **445** | **185** | **55** | **685** |

### 1.3 测试基础设施升级需求

| 项目 | 当前状态 | 目标状态 |
|------|----------|----------|
| `pytest-asyncio` | 已安装但 0 条 async 测试 | 全部异步测试启用 |
| `httpx.AsyncClient` | 未使用 | 集成测试标配 |
| `pytest-mock` | 已安装 | 扩展 `mocker.AsyncMock` 用法 |
| 前端测试 | 1 条 Vitest | 30+ 条 Vitest + 组件测试 |
| E2E 框架 | 无 | Playwright（推荐）或 Cypress |
| CI 超时 | 默认 | 异步测试需调整为 120s |
| `pytest-xdist` | 已安装 | 确保与 asyncio 兼容（`--dist loadscope`） |

---

## 2. 功能 A：异步化改造专项测试方案

### 2.1 改造范围分析

当前状态（全同步）：

```
ConversationRuntime.run_turn()         # 同步
  └─ api_client.stream()               # 同步迭代器
       └─ openai.chat.completions.create(stream=True)  # 同步迭代

AgentRunner.run_agent()                # 同步
  └─ ConversationRuntime(…).run_turn() # 同步

注册工具 handler                        # 同步函数
```

目标状态：

```python
async def run_turn(self, user_input: str) -> TurnSummary
async def stream(self, request: ApiRequest) -> AsyncIterator[AssistantEvent]
async def run_agent(self, agent_name: str, tool_input: str) -> str
```

### 2.2 并发调用正确性验证

#### 测试类：`TestAsyncConcurrency`

| 测试用例 | 验证点 | 优先级 |
|----------|--------|--------|
| `test_concurrent_sub_agents_no_race` | 3 个子 Agent 并发调用，各自 Session 独立不交叉污染 | P0 |
| `test_concurrent_sub_agents_session_isolation` | 并发下每个子 Agent 的 `session.messages` 严格隔离 | P0 |
| `test_parallel_tool_execution_order` | 同一 turn 内多个 tool_use 并发执行，结果按 tool_use_id 正确关联 | P0 |
| `test_concurrent_api_streams_independent` | 两个并发 `stream()` 调用的 SSE 事件流互不干扰 | P0 |
| `test_run_turn_reentrancy_prevention` | 同一 runtime 实例上并发调用 `run_turn()` 应报错或排队 | P1 |
| `test_asyncio_gather_multiple_agents` | `asyncio.gather()` 并发 3 个 Agent，验证全部结果完整性 | P1 |
| `test_concurrent_usage_tracking` | 并发调用下 `UsageTracker` 的 token 计数无竞态条件 | P1 |
| `test_high_concurrency_stress` | 10 个并发 Agent 调用，验证无死锁/超时 | P2 |
| `test_concurrent_with_different_models` | 不同模型的 Agent 并发调用，各自使用正确的 model 参数 | P2 |

#### 并发安全 Mock 策略

```python
# 异步 mock 模式
@pytest.fixture
def async_api_client():
    client = AsyncMock()
    client.stream.return_value = async_gen_from_events([...])
    return client

async def async_gen_from_events(events):
    for event in events:
        yield event
```

### 2.3 事件循环泄漏检测

| 测试用例 | 验证点 | 优先级 |
|----------|--------|--------|
| `test_no_event_loop_leak_after_run_turn` | `run_turn()` 完成后不持有未关闭的 event loop 引用 | P0 |
| `test_cleanup_after_exception` | 异步调用中途抛出异常后，stream 连接正确关闭 | P0 |
| `test_no_pending_tasks_after_completion` | `asyncio.all_tasks()` 在调用完成后无残留 | P1 |
| `test_cancellation_propagation` | `asyncio.Task.cancel()` 能正确传播到子协程 | P1 |
| `test_timeout_cleanup` | `asyncio.wait_for(timeout=...)` 超时后资源释放 | P2 |
| `test_event_loop_reuse` | 同一 event loop 上多次调用 run_turn 不会累积状态 | P2 |

#### 事件循环泄漏检测工具代码

```python
import asyncio
import gc
import pytest

@pytest.fixture
async def clean_event_loop():
    """确保每个测试从干净的 event loop 开始"""
    loop = asyncio.get_running_loop()
    initial_tasks = len(asyncio.all_tasks(loop))
    yield
    # 检查无泄漏
    remaining = asyncio.all_tasks(loop) - {asyncio.current_task()}
    assert len(remaining) == 0, f"Leaked tasks: {remaining}"

@pytest.mark.asyncio
async def test_no_leak_example(clean_event_loop):
    runtime = ConversationRuntime(...)
    await runtime.run_turn("test")
    # clean_event_loop fixture 自动验证
```

### 2.4 Async Mock 策略总览

| 场景 | Mock 工具 | 示例 |
|------|-----------|------|
| API stream | `AsyncMock` + `async_generator` | `mock.stream.return_value = async_gen(...)` |
| HTTP 调用 | `pytest-httpx` + `AsyncClient` | `httpx_mock.add_response()` |
| 文件 I/O | `aiofiles` mock 或 `pytest-mock` | `mocker.patch("aiofiles.open")` |
| LLM SDK | `AsyncMock` on `openai.AsyncOpenAI` | `mock_client.chat.completions.create = AsyncMock()` |
| 工具调用 | `AsyncMock` on handler | `mock_handler.return_value = coroutine_returning("result")` |
| 并发控制 | `asyncio.Semaphore` mock | 验证并发度限制逻辑 |

### 2.5 异步化改造回归检查清单

- [ ] 所有现有 1,424 条同步测试在 `pytest-asyncio` `auto` 模式下仍通过
- [ ] `ConversationRuntime` 公开 API 签名变更后，所有调用方（`AgentRunner`, `iterative_writer`）已更新
- [ ] `print_stream=True` 模式下流式输出行为不变
- [ ] `max_iterations` 限制在 async 路径下仍生效
- [ ] 异常类型不变（`RuntimeError` for loop exceeded 等）
- [ ] 向后兼容：如果可能，保留同步包装器用于 CLI 入口

---

## 3. 功能 B："与总编对话" API 测试用例清单

### 3.1 SSE 流式响应解析验证

#### 测试类：`TestChiefEditorSSE`

| # | 测试用例 | SSE 场景 | 优先级 |
|---|----------|----------|--------|
| 1 | `test_sse_text_delta_streaming` | 纯文本流，逐个 `data:` 块到达 | P0 |
| 2 | `test_sse_tool_call_delta` | `data: {"type":"tool_use","name":"update_story_outline",...}` | P0 |
| 3 | `test_sse_mixed_text_and_tools` | 文本 + 工具调用交错 | P0 |
| 4 | `test_sse_error_event` | `data: {"type":"error","message":"..."}` 正确处理 | P0 |
| 5 | `test_sse_done_event` | `data: [DONE]` 正确终止 | P0 |
| 6 | `test_sse_chunked_unicode` | 多字节 UTF-8 字符在 chunk 边界分割 | P1 |
| 7 | `test_sse_empty_data_line` | 空 `data:` 行正确处理（SSE 协议允许作为 keep-alive） | P1 |
| 8 | `test_sse_retry_field` | `retry:` 字段被正确解析 | P2 |
| 9 | `test_sse_missing_event_type_fallback` | 无 `event:` 字段时默认作为 `message` 处理 | P1 |
| 10 | `test_sse_client_disconnect_mid_stream` | 客户端断开时服务端正确清理 | P0 |
| 11 | `test_sse_heartbeat_keepalive` | 长对话间定期发送 `: heartbeat` 注释行 | P2 |

#### SSE 解析测试工具

```python
import httpx
import json

async def collect_sse_events(url: str, payload: dict):
    """收集 SSE 流的所有事件用于断言"""
    events = []
    async with httpx.AsyncClient(timeout=30) as client:
        async with client.stream("POST", url, json=payload) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    events.append(json.loads(data))
    return events
```

### 3.2 Session 生命周期测试

#### 测试类：`TestChiefEditorSession`

| # | 测试用例 | 验证点 | 优先级 |
|---|----------|--------|------|
| 12 | `test_session_create_new` | 首次对话创建新 session，返回 `session_id` | P0 |
| 13 | `test_session_resume_existing` | 传入已有 `session_id` 恢复对话上下文 | P0 |
| 14 | `test_session_resume_nonexistent` | 传入不存在的 `session_id` 返回 404 | P1 |
| 15 | `test_session_messages_persist` | 对话结束后 session 消息正确持久化到 JSON 文件 | P0 |
| 16 | `test_session_ttl_expiry` | Session 超过 TTL 后访问返回过期错误 | P1 |
| 17 | `test_session_concurrent_access` | 同一 session 并发请求不丢消息 | P1 |
| 18 | `test_session_max_messages_limit` | 超过最大消息数后触发 auto-compaction | P2 |
| 19 | `test_session_metadata_tracking` | Session 元数据（创建时间、最后活跃时间、消息数）正确 | P1 |
| 20 | `test_session_list_endpoint` | `GET /api/chat/sessions` 返回正确列表 | P1 |
| 21 | `test_session_delete` | `DELETE /api/chat/sessions/{id}` 正确删除 | P2 |
| 22 | `test_session_export` | 导出 session 为 JSON 格式完整可恢复 | P2 |

### 3.3 工具调用正确性测试

#### 测试类：`TestChiefEditorTools`

| # | 测试用例 | 验证点 | 优先级 |
|---|----------|--------|------|
| 23 | `test_tool_update_story_outline_success` | `update_story_outline` 调用成功，YAML 文件更新 | P0 |
| 24 | `test_tool_update_story_outline_invalid_yaml` | 传入非法 YAML 时返回错误而不崩溃 | P1 |
| 25 | `test_tool_update_story_outline_permission_denied` | 无写权限时返回错误 | P2 |
| 26 | `test_tool_query_knowledge_graph_basic` | `query_knowledge_graph` 基本查询返回图数据 | P0 |
| 27 | `test_tool_query_knowledge_graph_complex_cypher` | 复杂关系查询（多跳、过滤） | P1 |
| 28 | `test_tool_query_knowledge_graph_empty_result` | 查询无结果返回空集而非报错 | P1 |
| 29 | `test_tool_list_generated_chapters_empty` | 无已生成章节时返回空列表 | P0 |
| 30 | `test_tool_list_generated_chapters_with_data` | 有已生成章节时返回完整列表+元数据 | P0 |
| 31 | `test_tool_list_generated_chapters_pagination` | 分页参数正确生效 | P2 |
| 32 | `test_tool_call_badge_in_sse` | SSE 事件中包含 `tool_call` 类型事件供前端渲染徽章 | P0 |
| 33 | `test_tool_error_propagation_to_sse` | 工具执行异常通过 SSE error 事件传播 | P1 |
| 34 | `test_tool_timeout_handling` | 工具执行超时后优雅降级 | P1 |

### 3.4 上下文注入完整性测试

#### 测试类：`TestChiefEditorContextInjection`

| # | 测试用例 | 验证点 | 优先级 |
|---|----------|--------|------|
| 35 | `test_outline_injected_in_system_prompt` | 大纲内容出现在 System Prompt 中 | P0 |
| 36 | `test_character_cards_injected` | 角色卡内容出现在 System Prompt 中 | P0 |
| 37 | `test_previous_chapter_summary_injected` | 前章摘要在 System Prompt 中 | P0 |
| 38 | `test_empty_outline_graceful` | 大纲为空时 System Prompt 不含空占位符 | P1 |
| 39 | `test_large_outline_truncation` | 大纲超长（>10K tokens）时截断+标注 | P1 |
| 40 | `test_character_card_missing_fields` | 角色卡部分字段缺失时注入不报错 | P1 |
| 41 | `test_all_three_contexts_present` | 大纲 + 角色卡 + 前章摘要三者同时注入 | P0 |
| 42 | `test_context_injection_not_leaked_to_sub_agents` | 总编对话的上下文不泄漏到 chapter 生成子 Agent | P1 |
| 43 | `test_system_prompt_template_rendering` | Jinja2/YAML 模板渲染正确（变量替换、条件分支） | P0 |

### 3.5 前端集成测试（Chief Editor Drawer）

| # | 测试用例 | 验证点 | 优先级 |
|---|----------|--------|------|
| 44 | `test_drawer_open_close` | Drawer 展开/收起动画流畅 | P1 |
| 45 | `test_bubble_rendering_stream` | 流式文本逐字出现在气泡中 | P0 |
| 46 | `test_tool_call_badge_display` | 工具调用时显示徽章（名称 + 状态） | P0 |
| 47 | `test_multiple_tool_calls_badges` | 多个连续工具调用各有独立徽章 | P1 |
| 48 | `test_error_bubble_styling` | 错误消息气泡有视觉区分（红色/警告色） | P1 |
| 49 | `test_drawer_persists_across_navigation` | 切换页面后 Drawer 状态保持 | P2 |
| 50 | `test_drawer_responsive_mobile` | 移动端 Drawer 全屏显示 | P2 |

---

## 4. 功能 D：提示词配置化回归测试方案

### 4.1 改造范围

当前：
- 主 Agent 提示词：硬编码在 `system_prompt.py` 的 `build_main_agent_system_prompt()`
- 子 Agent 身份：硬编码在 `_get_agent_identity()`
- 子 Agent 提示词正文：`DESIGN/PROMPTS/*.md`

目标：
- 所有提示词模板移至 `config/prompts/*.yaml`
- 支持变量注入（`{{ variable }}`）
- 支持热更新（无需重启服务）

### 4.2 测试类：`TestPromptConfigRegression`

| # | 测试用例 | 验证点 | 优先级 |
|---|----------|--------|------|
| 51 | `test_prompt_yaml_loads_all_agents` | 所有 5 个 Agent（主控+4 子）的提示词 YAML 可正确加载 | P0 |
| 52 | `test_prompt_yaml_variable_interpolation` | `{{ outline }}` 等变量正确替换 | P0 |
| 53 | `test_prompt_yaml_missing_variable_graceful` | 变量缺失时使用默认值或报清晰错误 | P0 |
| 54 | `test_prompt_yaml_invalid_yaml_syntax` | 非法 YAML 文件加载时返回明确错误 | P1 |
| 55 | `test_prompt_rendering_identical_to_hardcoded` | 新 YAML 渲染结果与旧硬编码版本完全一致 | P0 |
| 56 | `test_prompt_yaml_default_fallback` | YAML 文件不存在时回退到硬编码默认值 | P0 |
| 57 | `test_prompt_hot_reload` | 修改 YAML 文件后下次请求使用新提示词 | P0 |
| 58 | `test_prompt_hot_reload_no_partial_update` | 热更新为原子操作——不出现半更新状态 | P1 |
| 59 | `test_prompt_yaml_schema_validation` | 验证 YAML 符合预期 schema（必填字段检查） | P1 |
| 60 | `test_prompt_cache_invalidation` | 热更新后缓存正确失效 | P1 |
| 61 | `test_prompt_encoding_utf8` | 中文/emoji 等 UTF-8 内容正确处理 | P0 |
| 62 | `test_prompt_yaml_multiline_strings` | 多行字符串（`|` / `>`）正确处理 | P1 |
| 63 | `test_prompt_version_tracking` | 提示词版本号随更新变化 | P2 |
| 64 | `test_prompt_config_api_endpoint` | `GET/PUT /api/prompts/{agent}` 端点正确 | P1 |
| 65 | `test_prompt_template_no_injection` | 用户输入不会被当作模板变量执行 | P0 |

### 4.3 回归对比策略

```python
class TestPromptMigrationParity:
    """确保新旧提示词输出完全一致"""

    @pytest.mark.parametrize("agent_name", [
        "master", "chief_editor", "character_designer",
        "plot_writer", "proofreader"
    ])
    def test_parity_with_hardcoded(self, agent_name, tmp_path):
        # 1. 加载旧硬编码提示词
        old_prompt = get_old_hardcoded_prompt(agent_name)
        # 2. 加载新 YAML 提示词
        new_prompt = load_prompt_from_yaml(agent_name, config_dir=tmp_path)
        # 3. 标准化空白后逐行对比
        assert normalize(old_prompt) == normalize(new_prompt), \
            f"Prompt mismatch for {agent_name}"
```

---

## 5. 功能 C：可观测性集成测试方案

### 5.1 测试类：`TestObservabilityIntegration`

| # | 测试用例 | 验证点 | 优先级 |
|---|----------|--------|------|
| 66 | `test_trace_id_injected_for_agent_call` | 每个 Agent 调用生成唯一 `trace_id` | P0 |
| 67 | `test_span_id_for_sub_agent` | 子 Agent 调用有 `span_id` 且与父 span 有父子关系 | P0 |
| 68 | `test_trace_propagation_across_agents` | 主 Agent → 子 Agent 链路上 trace_id 一致 | P0 |
| 69 | `test_tool_call_spans` | 工具调用创建独立 span | P1 |
| 70 | `test_llm_call_spans` | LLM API 调用创建 span 并记录 model/tokens | P0 |
| 71 | `test_span_attributes_correct` | span 属性：`agent.name`, `model`, `iteration`, `tool.name` | P1 |
| 72 | `test_error_span_status` | 异常时 span status 设为 ERROR 并记录异常信息 | P1 |
| 73 | `test_langfuse_exporter_config` | Langfuse exporter 正确初始化（host, public_key, secret_key） | P1 |
| 74 | `test_otel_no_block_on_export_failure` | 导出失败不影响主业务流程 | P0 |
| 75 | `test_otel_sampling_rate` | 采样率配置生效（如 0.1 = 10%） | P2 |
| 76 | `test_otel_resource_attributes` | Resource 属性包含 service.name, service.version | P1 |
| 77 | `test_otel_batch_export` | Span 批量导出而非逐条发送 | P2 |
| 78 | `test_otel_graceful_shutdown` | 服务关闭时等待 pending spans 导出完成 | P1 |

### 5.2 OpenTelemetry Mock 策略

```python
from opentelemetry.sdk.trace.export import InMemorySpanExporter

@pytest.fixture
def span_exporter():
    """内存中收集 span 用于断言"""
    exporter = InMemorySpanExporter()
    # 配置 tracer provider 使用此 exporter
    provider = TracerProvider()
    processor = SimpleSpanProcessor(exporter)
    provider.add_span_processor(processor)
    # ... 注入 provider
    yield exporter
    provider.shutdown()

def test_trace_chain(span_exporter):
    # 执行 agent 调用...
    spans = span_exporter.get_finished_spans()
    trace_ids = {s.context.trace_id for s in spans}
    assert len(trace_ids) == 1, "所有 span 应共享同一 trace_id"
```

---

## 6. 新增测试用例数量预估和覆盖率目标

### 6.1 新增测试统计

| 模块 | 单元测试 | 集成测试 | E2E | 测试文件 |
|------|----------|----------|-----|----------|
| **异步化改造** | | | | |
| └ `test_async_runtime.py` | 55 | — | — | 1 |
| └ `test_async_api_client.py` | 40 | — | — | 1 |
| └ `test_async_agent_runner.py` | 35 | — | — | 1 |
| └ `test_async_concurrency.py` | 30 | — | — | 1 |
| └ `test_event_loop_safety.py` | 20 | — | — | 1 |
| └ 异步集成测试 | — | 60 | — | 2 |
| └ 异步 E2E | — | — | 10 | 1 |
| **总编对话 API** | | | | |
| └ `test_chief_editor_sse.py` | 40 | — | — | 1 |
| └ `test_chief_editor_session.py` | 25 | — | — | 1 |
| └ `test_chief_editor_tools.py` | 30 | — | — | 1 |
| └ `test_chief_editor_context.py` | 25 | — | — | 1 |
| └ 总编 API 集成 | — | 75 | — | 2 |
| └ 总编 E2E | — | — | 30 | 2 |
| **可观测性** | | | | |
| └ `test_otel_tracing.py` | 30 | — | — | 1 |
| └ `test_langfuse_integration.py` | 20 | — | — | 1 |
| └ 可观测性集成 | — | 30 | — | 1 |
| └ 可观测性 E2E | — | — | 5 | 1 |
| **提示词配置化** | | | | |
| └ `test_prompt_yaml_loader.py` | 35 | — | — | 1 |
| └ `test_prompt_rendering.py` | 30 | — | — | 1 |
| └ `test_prompt_migration_parity.py` | 30 | — | — | 1 |
| └ 提示词 API 集成 | — | 20 | — | 1 |
| └ 提示词 E2E | — | — | 10 | 1 |
| **合计** | **445** | **185** | **55** | **25** |

### 6.2 覆盖率目标

| 指标 | 当前 | 目标 | 备注 |
|------|------|------|------|
| **总体行覆盖率** | ~75% | **≥ 82%** | 新增代码必须 ≥ 90% |
| **分支覆盖率** | ~70% (估) | **≥ 78%** | 所有异步分支路径 |
| **`async_runtime.py` (新)** | N/A | **≥ 92%** | 核心路径 100% |
| **`async_api_client.py` (新)** | N/A | **≥ 90%** | SSE 解析路径全覆盖 |
| **`api/chat.py` (新)** | N/A | **≥ 90%** | 所有路由+错误路径 |
| **`config/prompts/` (新)** | N/A | **≥ 95%** | 加载器+渲染器 |
| **`telemetry/` (新)** | N/A | **≥ 85%** | 导出失败路径 |
| **前端组件** | ~5% | **≥ 60%** | ChiefEditorDrawer 重点 |
| **E2E 关键路径** | 0% | **≥ 70%** | 核心用户旅程 |

### 6.3 覆盖率排除项（合理）

```toml
# pyproject.toml 新增排除
[tool.coverage.run]
omit = [
    # ... 现有排除 ...
    "src/novels_project/telemetry/exporters.py",  # Langfuse SDK 封装
    "src/novels_project/cli.py",                   # CLI 入口
]
```

---

## 7. 验收条件（上线前检查清单）

### 7.1 功能 A：异步化改造

- [ ] **A-01** 所有现有 1,424 条测试在 `pytest-asyncio` 模式下通过，无新增失败
- [ ] **A-02** `run_turn()` / `stream()` / `run_agent()` 签名已改为 `async def`
- [ ] **A-03** 并发测试套件（≥9 条）全部通过，无竞态条件
- [ ] **A-04** 事件循环泄漏检测套件（≥6 条）全部通过
- [ ] **A-05** `asyncio.gather()` 并发 3 Agent 的端到端场景通过
- [ ] **A-06** 异步化代码分支覆盖率 ≥ 90%
- [ ] **A-07** 性能基准：3 子 Agent 并发执行时间 ≤ 串行执行时间的 60%
- [ ] **A-08** 异常情况下无僵尸协程残留

### 7.2 功能 B：总编对话 API

- [ ] **B-01** `POST /api/chat/chief-editor` SSE 流式响应符合规范
- [ ] **B-02** Session 创建/恢复/列表/删除 CRUD 全部通过
- [ ] **B-03** 3 个工具（`update_story_outline` / `query_knowledge_graph` / `list_generated_chapters`）集成测试通过
- [ ] **B-04** 上下文注入完整性测试（大纲/角色卡/摘要）全部通过
- [ ] **B-05** SSE 解析测试（≥11 条）全部通过，含边界条件
- [ ] **B-06** 前端 Chief Editor Drawer 组件测试通过（≥7 条）
- [ ] **B-07** 工具调用徽章正确渲染
- [ ] **B-08** 客户端断连时服务端资源正确释放
- [ ] **B-09** API 路由覆盖率 ≥ 90%

### 7.3 功能 C：可观测性

- [ ] **C-01** trace_id 在 agent 调用链路上一致传播
- [ ] **C-02** span_id 正确建立父子关系
- [ ] **C-03** LLM 调用 span 包含 model name 和 token 使用量
- [ ] **C-04** 导出失败不影响主业务流程（no-block 验证）
- [ ] **C-05** Langfuse 导出配置正确加载
- [ ] **C-06** 服务优雅关闭时 pending spans 导出完成

### 7.4 功能 D：提示词配置化

- [ ] **D-01** 所有 5 个 Agent 的 YAML 提示词加载成功
- [ ] **D-02** 新旧提示词渲染结果逐字一致（迁移 parity）
- [ ] **D-03** 热更新功能正常（修改 YAML → 下次请求生效）
- [ ] **D-04** 变量缺失时有清晰错误而非静默失败
- [ ] **D-05** YAML schema 验证通过
- [ ] **D-06** 用户输入不会被当作模板变量执行（注入安全）
- [ ] **D-07** `GET/PUT /api/prompts/{agent}` API 端点正确

### 7.5 跨功能验收

- [ ] **X-01** 总体行覆盖率 ≥ 82%，分支覆盖率 ≥ 78%
- [ ] **X-02** 全量测试套件在 CI 中通过（目标 ≤ 5min）
- [ ] **X-03** `mypy` 类型检查通过（新增 async 代码）
- [ ] **X-04** `ruff` lint 通过
- [ ] **X-05** `bandit` 安全扫描通过（注意：SSE 注入、模板注入）
- [ ] **X-06** 前端 `npm run build` 成功
- [ ] **X-07** 前端 `npm test` 通过（≥ 30 条测试）
- [ ] **X-08** E2E smoke test（核心用户旅程）通过
- [ ] **X-09** 生产环境部署后 canary 验证通过（console 无新错误）

---

## 8. 风险与缓解

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 异步化引入竞态条件 | Agent 输出错误/丢失 | 中 | 详尽并发测试 + `asyncio.Semaphore` 保护共享状态 |
| SSE 实现不一致 | 前端解析失败 | 中 | 严格遵循 SSE 规范 + 前端/后端联调测试 |
| 提示词迁移遗漏 | Agent 行为退化 | 高 | Parity 测试逐字对比 + 人工 review |
| OpenTelemetry overhead | 性能下降 | 低 | Batch export + 采样率控制 + 性能基准测试 |
| Session 存储并发写 | 消息丢失 | 中 | 文件锁或数据库迁移（如发现） |
| 前端/后端 SSE 协议不匹配 | Drawer 空白 | 中 | E2E 测试覆盖关键场景 |

---

## 9. 建议实施顺序

```
Week 1-2:  功能 D（提示词配置化）— 风险低、可独立验证
Week 2-3:  功能 A（异步化改造）— 核心基础设施，影响面最广
Week 3-4:  功能 B 后端（总编对话 API）— 依赖 A 完成
Week 4-5:  功能 C（可观测性）— 可并行于 B
Week 5-6:  功能 B 前端（Chief Editor Drawer）— 依赖 B 后端
Week 6:    E2E 测试 + 性能回归 + 验收
```

策略理由：先做提示词配置化（风险最低、无依赖），再做异步化（影响最大、需要最多回归测试），然后基于异步基础设施构建总编对话 API，可观测性可以并行开发。

---

*本方案由 GStack QA Lead 基于项目代码库深度分析生成。所有测试用例数量基于代码复杂度、现有测试密度及功能边界估算。*
