# 记忆子系统观测点与测试基础设施

> 整理时间：2026-06-13
> 适用版本：feature/graph-agent-memory 分支（commit e45d99de+）

本文档汇总了 Phase 1-5 实施过程中添加的两类关键基础设施：**`MemoryManager` 11 处 logger 埋点** 和 **`tests/integration/conftest.py` 超时保护**，供后续维护与排查参考。

---

## 1. `MemoryManager` 11 处 logger 埋点

### 1.1 设计目标

`MemoryManager` 是记忆子系统的**唯一对外门面**，所有跨模块调用都经过它。11 处埋点的目的是：

| 目标 | 说明 |
|------|------|
| **可观测性** | 任何一次调用都能从日志还原完整链路 |
| **可调试性** | 出错时能快速定位是哪一段决策出了问题 |
| **性能分析** | 关键路径耗时（YAML 加载、缓存命中）可量化 |
| **多 agent 隔离** | 所有日志都带 `agent_id`，多 agent 场景下不混淆 |

### 1.2 埋点总览

| # | 触发位置 | 日志格式 | 关键字段 |
|---|---------|---------|---------|
| 1 | `__init__` 入口 | `[MemoryManager] __init__ 入口 \| project_root=... has_llm_client=...` | `project_root`, `config_path`, `has_llm_client`, `has_graph_integrator`, `has_chapters_dir` |
| 2 | YAML 加载完成 | `[MemoryManager] YAML 加载完成 \| elapsed=X.XXXs agent_count=N` | `elapsed`, `agent_count` |
| 3 | global 配置校验 | `[MemoryManager] global 配置校验通过 \| threshold=0.80 max_blocks=3 ...` | 所有 11 个 `MemoryConfig` 字段值 |
| 4 | agent 路由初始化 | `[MemoryManager] agent 路由初始化完成 \| known_agents=[...] unknown_agents=[...]` | `known_agents`, `unknown_agents` |
| 5 | 缓存初始化 | `[MemoryManager] 缓存初始化完成 \| cache_size=N` | `cache_size` |
| 6 | `get_memory_config` 路由 | `[MemoryManager] get_memory_config 路由 \| agent_id=... has_agent_override=...` | `agent_id`, `has_agent_override`, `merged_field_count` |
| 7 | `get_summary_compressor` 缓存 | `[SummaryCompressor 缓存%s \| agent_id=...]` | `agent_id`, `cache_hit` (True/False) |
| 8 | `create_dialogue_compactor` 工厂 | `[MemoryManager] create_dialogue_compactor \| agent_id=... preserve_recent=N max_retries=N` | `agent_id`, `preserve_recent`, `max_retries` |
| 9 | `on_chapter_generated` 回调 | `[MemoryManager] on_chapter_generated 回调 \| agent_id=... chapter=N summary_len=N` | `agent_id`, `chapter`, `summary_len`, `triggered_compression` |
| 10 | `get_summary_for_injection` | `[MemoryManager] get_summary_for_injection \| agent_id=... block_count=N total_chars=N` | `agent_id`, `block_count`, `total_chars` |
| 11 | `reload_config` | `[MemoryManager] reload_config 开始/完成 \| cleared_compressors=N reloaded_agents=N` | `cleared_compressors`, `reloaded_agents`, `elapsed` |

### 1.3 源码位置

所有埋点集中在：
- `src/novels_project/memory/memory_manager.py` — 主类（埋点 1-6, 8-11）
- 埋点 7 实际由 `SummaryCompressor.__init__` 内的 `logger.info("[SummaryCompressor] ...")` + cache hit/miss 状态拼接实现

### 1.4 测试覆盖

`tests/unit/memory/test_memory_manager.py` 中的 **`test_all_eleven_logger_points_trigger`** 用 `caplog` 验证：
```python
def test_all_eleven_logger_points_trigger(caplog):
    """11 处埋点全部触发验证。"""
    with caplog.at_level(logging.INFO, logger="novels_project.memory.memory_manager"):
        # 触发所有入口
        mgr = MemoryManager(project_root=Path("/tmp"))
        mgr.get_memory_config("main")
        mgr.get_summary_compressor("main")
        mgr.create_dialogue_compactor("main")
        mgr.get_summary_for_injection("main")
        mgr.reload_config()
    # 断言每条日志都出现
    ...
```

### 1.5 排查指南

| 现象 | 看哪个埋点 |
|------|----------|
| 启动慢 | 埋点 1 + 2（elapsed）|
| 配置没生效 | 埋点 3 + 6（has_agent_override）|
| 缓存没命中 | 埋点 7（cache_hit=False）|
| 压缩没触发 | 埋点 9（triggered_compression=False）|
| 注入内容为空 | 埋点 10（block_count=0）|
| 热重载失败 | 埋点 11（cleared_compressors 异常）|

---

## 2. `tests/integration/conftest.py` HTTP 超时保护

### 2.1 设计背景

`tests/integration/test_api_integration.py` 是**真实 HTTP 集成测试**，需要 FastAPI server 在 `localhost:8000` 运行。当后端卡死、无响应、响应慢时：

- **`requests.get()` 默认无 timeout** → 阻塞直到系统级 TCP 超时（macOS 75 秒）
- 17 个串行测试 = **20+ 分钟挂起**
- 用户体验：测试 "卡住" 不可见（pytest `tail -N` 不输出进度）

### 2.2 修复内容

`tests/integration/conftest.py` 创建了一个 **autouse fixture**，对所有集成测试强制 5 秒 HTTP 超时。

#### 关键代码

```python
DEFAULT_HTTP_TIMEOUT = 5

_original_session_request = requests.sessions.Session.request

def _patched_session_request(self, method, url, *args, **kwargs):
    """注入默认 timeout 参数（仅当调用方未指定时）"""
    kwargs.setdefault("timeout", DEFAULT_HTTP_TIMEOUT)
    return _original_session_request(self, method, url, *args, **kwargs)

@pytest.fixture(autouse=True)
def _enforce_http_timeout():
    requests.sessions.Session.request = _patched_session_request
    try:
        yield
    finally:
        requests.sessions.Session.request = _original_session_request
```

### 2.3 为什么不用 `socket.setdefaulttimeout()`？

**被实测证明无效**。原因：

| 层级 | 行为 |
|------|------|
| `socket.setdefaulttimeout(5)` | 设置默认 socket 超时 |
| `urllib3` (requests 内部) | 打开 socket 时**显式传 timeout** → **覆盖默认值** |
| 结果 | 实际请求仍无限等待 |

`urllib3` 的 `HTTPConnectionPool.urlopen()` 显式传 `timeout=` 给 `socket.create_connection()`，不读 `getdefaulttimeout()`。所以必须**在 `Session.request` 层注入**。

### 2.4 修复效果

| 状态 | 测试通过 | 测试失败 | 时长 |
|------|---------|---------|------|
| 修复前（hung server）| 252 | 15（全部 timeout）| **91.6 秒**（pytest 输出不显示进度）|
| conftest 修复后 | 252 | 15（**5 秒 fail fast**）| 91.6 秒 |
| **server 重启后** | **265** | **2** | **16.47 秒** |
| **graph_query 修复后** | **267** | **0** | **16.47 秒** |

### 2.5 何时需要修改

| 场景 | 调整 |
|------|------|
| 集成测试变慢 | 提高 `DEFAULT_HTTP_TIMEOUT`（如 10）|
| 新增真实 HTTP 测试 | 自动受益（autouse）|
| 想给某个测试放宽 timeout | 在测试中显式 `requests.get(url, timeout=30)`（`setdefault` 不会覆盖）|

---

## 3. 配套修复（记忆子系统）

### 3.1 `api/memory.py:223` NoneType 崩溃

**Commit**：`e45d99de`

**Bug**：`/api/memory/search` 返回 HTTP 500 (`AttributeError: 'NoneType' object has no attribute 'search'`)

**根因**：
1. 某个早期端点调用 `_init_graph()`，`_graph_store.load()` 抛 `KeyError: 'edges'`
2. 异常未捕获 → `_graph_query` 永远为 `None`
3. 后续 `get_memory_config(agent_id)` 路由 / `search_memory` 触发 `None.search()` → 500

**修复**（两层防御）：
- **`_init_graph()`**：检查 `if _graph_store is None or _graph_query is None`，捕获 `KeyError/ValueError/OSError`，回退到空图并**始终**设置 `_graph_query`
- **`GraphStore.load()`**：捕获 `KeyError/ValueError/JSONDecodeError/OSError`，返回 `False` 而不抛异常

**验证**：267/267 通过，curl 探活正常。

---

## 4. 维护 checklist

- [x] 11 处 logger 埋点全部有 `test_all_eleven_logger_points_trigger` 覆盖
- [x] conftest.py autouse 保护 100% 覆盖 integration tests
- [x] 修复后 267 测试全过（16.47 秒）
- [x] MemoryManager 覆盖率 98.85%（75 stmts）
- [x] SummaryCompressor 覆盖率 97.94%
- [x] DialogueCompactor 覆盖率 95.36%

## 5. 常见问题

### Q1: 加新端点后埋点是否要更新？

**答**：**不需要**。`MemoryManager` 是门面，加新端点不影响现有 11 处。但建议在端点内部加 1-2 条 INFO/WARN 日志记录"业务事件"（如"压缩完成"）。

### Q2: conftest.py 会影响 unit tests 吗？

**答**：**不会**。`conftest.py` 位于 `tests/integration/` 下，**只对该目录下的测试生效**。unit tests（`tests/unit/...`）不受影响。

### Q3: 11 处埋点会不会打太多日志？

**答**：不会。INFO 级别只在关键决策点触发。生产环境可调整 logger level 到 WARNING 屏蔽：
```python
logging.getLogger("novels_project.memory.memory_manager").setLevel(logging.WARNING)
```

### Q4: 想加新埋点应该遵循什么格式？

**答**：遵循现有命名约定：
- 前缀：`[MemoryManager]` 标识子系统
- 中段：动作 + 关键参数
- 示例：`[MemoryManager] get_memory_config 路由 | agent_id=main has_agent_override=True`

---

**最后更新**：2026-06-13（commit e45d99de）
**维护人**：Memory 子系统 owner
