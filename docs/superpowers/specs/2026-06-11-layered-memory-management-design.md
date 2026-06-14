# 分层记忆管理系统设计方案

**版本**: 1.0
**日期**: 2026-06-11
**状态**: 已审阅待实施
**作者**: Winston

---

## 1. 背景与问题

当前 `NovelAgentTeams` 项目基于 `ConversationRuntime` + `GraphMemoryIntegrator` + `ContextInjector` 构建了多 agent 协作系统，面临以下规模化挑战：

### 1.1 容量问题
- 当小说累计达到 **10,000+ 章节**、**1M+ tokens** 时：
  - `ConversationRuntime.session.messages` 累积过长，单次 LLM 请求触发 token 上限
  - `ContextInjector.inject_context` 注入的图谱内容可能过大（角色关系网络 + 伏笔列表无上限）
  - `GraphStore` 中节点数爆炸后，邻居查询返回数据过多

### 1.2 现有方案的不足
- **`compaction.compact_session`**：基于规则提取消息数和最近请求，**LLM-based 语义压缩未实现**，无法保留"讨论事项、任务进度、决策"等关键信息
- **`ContextInjector.inject_context`**：仅做长度截断（`max_context_chars=8000`），**硬性截断会丢失历史或新内容**
- **章节摘要**：通过 `extract_chapter_summary` 提取后存入向量库，但**没有滚动压缩机制**——10K 章节时向量库会无限膨胀
- **暗线伏笔**：依赖 `GraphQuery.trace_all_foreshadowings()` 直接查询，**无状态管理**，可能被淹没在大量数据中
- **子 agent**：`AgentRunner.run_agent` 每次创建临时 session，但**无独立的压缩配置**，长任务也可能触发上下文爆炸

### 1.3 核心痛点
- **截断有损**：硬性截断会丢失关键信息（人物关系、新生成章节、待完成任务等）
- **无滚动淘汰**：摘要一旦生成永久保留，无 100 章级别的"渐进淡忘"机制
- **配置不可调**：所有阈值硬编码，无法在 web 端调整以适应不同项目规模
- **错误降级缺失**：LLM 压缩失败时无重试、无通知用户机制

---

## 2. 设计目标

本方案设计一个**分层、可滚动、可配置、可降级**的记忆管理系统，实现：

1. **4 层清晰分层**：活跃对话（L1） / 滚动摘要块（L2） / 剧情追踪（L3） / 人物与关系（L4）
2. **100 章触发 + 滑窗淘汰**：默认保留最近 3 块（300 章），web 端可调 100~1000 章（10 档）
3. **LLM 结构化对话压缩**：80% 阈值触发，JSON Schema 约束（角色、主题、待办、决策、问题）
4. **配置分层（global + per-agent）**：web 端可在 Agent 设置页调整
5. **子 agent 独立配置 + 销毁模式**：session_id 100% 不复用
6. **错误降级 + 用户决策**：LLM 失败重试 → 仍失败 → 对话压缩静默降级，章节压缩通知用户
7. **损坏自动恢复**：块 JSON 损坏时从原始章节文件（source of truth）恢复

---

## 3. 设计原则

- **章节文件是 source of truth**：任何块 JSON 损坏都能从 `chapter_*_final.md` 重新生成
- **伏笔/人物永不自动压缩**：L3/L4 是图谱持久层，**仅由人工/agent 显式标记删除**
- **配置分层优先级**：agents.{name}.xxx > global.xxx > MemoryConfig 字段默认值
- **错误永不阻塞主流程**：压缩失败 → 重试 → 降级 → 通知，最差情况保留原始数据
- **web 端与后端同步**：通过 PUT API + 重载机制实现准实时配置生效
- **测试覆盖率**：核心组件 > 95%

---

## 4. 目标架构

### 4.1 四层结构

| 层 | 数据类型 | 数据源 | 生命周期 | 压缩策略 |
|----|---------|--------|----------|----------|
| **L1 - 活跃对话** | `Session.messages` | `ConversationRuntime` | 短期/临时 | 80% token 阈值 → LLM 压缩 → 保留 K 条原文 |
| **L2 - 摘要块** | `SummaryBlock` 文件 | `SummaryCompressor` | 中期/滚动 | 100 章触发 → 滑窗淘汰（默认 3 块） |
| **L3 - 剧情追踪** | `concept` 节点 + `foreshadows` 边 | `GraphStore` | 长期/状态追踪 | **永不自动压缩**，仅标记 resolved |
| **L4 - 人物与关系** | `character`/`organization` 节点 + 边 | `GraphStore` + `character_base_cards.yaml` | 永久/仅更新 | **永不自动压缩**，仅字段更新 |

### 4.2 核心组件

| 组件 | 位置 | 职责 |
|------|------|------|
| `MemoryConfig` | `memory/memory_config.py` (新) | 配置数据类 + YAML 加载/合并/校验 |
| `SummaryCompressor` | `memory/summary_compressor.py` (新) | 100 章触发压缩 + 滑窗淘汰 + 持久化 |
| `DialogueCompactor` | `memory/dialogue_compactor.py` (新) | LLM 结构化对话压缩 + 重试 + 降级 |
| `MemoryManager` | `memory/memory_manager.py` (新) | 顶层门面/协调者 |
| `GraphMemoryIntegrator` | `memory/integrator.py` (不变) | L3/L4 实体与剧情追踪 |
| `ContextInjector` | `context_injector.py` (扩展) | 注入：角色 + 伏笔 + 历史摘要块 |
| `ConversationRuntime` | `runtime.py` (扩展) | 集成 `DialogueCompactor` 替换原 `compact_session` |
| `AgentRunner` | `agents.py` (扩展) | 子 agent 销毁模式 + 独立 `MemoryConfig` |

### 4.3 数据流

#### 4.3.1 章节生成流程
```
主 Agent 评估章节完成（经 Proofreader 校对）
   ↓
AgentRunner.on_chapter_generated()
   ↓
MemoryManager.on_chapter_generated(agent_id, chapter_id, text)
   ↓
ContextInjector.extract_chapter_summary(text)
   ↓
SummaryCompressor.add_chapter_summary(chapter_id, summary)
   ↓ 累积 < 100 章
SummaryCompressor._trigger_compression()  ← 100 章时触发
   ↓
LLM 压缩 (retry 2 次) → 失败 → 通知前端用户决定
   ↓
SummaryBlock 持久化到 memory/summary_blocks/{agent_id}/
   ↓
滑窗淘汰（> max_summary_blocks 时）
```

#### 4.3.2 对话压缩流程
```
ConversationRuntime.run_turn()
   ↓ Phase 1: _inject_context()
ContextInjector.inject_context()
   ├─ 角色上下文（≤ 2000 字/角色）
   ├─ 伏笔上下文（剩余预算）
   └─ 历史摘要块（剩余预算）← 新增
   ↓ Phase 2: agent loop
LLM 调用 + 工具执行
   ↓ Phase 3: _maybe_auto_compress()  ← 改造
DialogueCompactor.compact(session, max_tokens)
   ├─ 检查阈值（80% × max_tokens）
   ├─ 保留最近 K=4 条消息
   ├─ 早期消息 → 文本 → LLM 压缩 (JSON Schema)
   ├─ 失败重试 2 次 → 仍失败 → 回退规则（compaction._build_summary）
   └─ 替换为单个 system 消息
```

#### 4.3.3 配置热重载
```
Web 前端: 用户修改 Plot Writer 阈值 0.7 → 0.8
   ↓
PUT /api/agents/plot_writer/memory-config
   ↓
后端: 更新 memory_config.yaml
   ↓
MemoryManager.reload_config()
   ├─ 重新读取 YAML
   └─ 清空 compressor 缓存
   ↓
下次 plot_writer 被调用时
   ├─ AgentRunner.get_memory_config("plot_writer") → 新配置
   └─ DialogueCompactor 使用新阈值
```

---

## 5. 组件详细设计

### 5.1 `MemoryConfig` 配置类

```python
@dataclass
class MemoryConfig:
    chapter_window: int = 100              # 业务规则，不暴露 web
    max_summary_blocks: int = 3            # web 端 10 档控制
    summary_max_chars: int = 2000
    
    dialogue_compression_threshold: float = 0.8
    preserve_recent_messages: int = 4
    dialogue_summary_max_chars: int = 3000
    dialogue_llm_model: Optional[str] = None  # None=跟随运行时
    
    subagent_compression_enabled: bool = True
    subagent_max_messages: int = 30
```

**字段层级**：
```
agents.{name}.xxx  >  global.xxx  >  MemoryConfig 字段默认值
```

**合并算法** (`MemoryConfig.merge`)：agent 显式设置（非字段默认值）→ 覆盖 global。

**YAML 结构**：
```yaml
version: "1.0"
global:
  chapter_window: 100
  max_summary_blocks: 3
  summary_max_chars: 2000
  dialogue_compression_threshold: 0.8
  preserve_recent_messages: 4
  dialogue_summary_max_chars: 3000
  dialogue_llm_model: null
  subagent_compression_enabled: true

agents:
  main: {}
  plot_writer:
    dialogue_compression_threshold: 0.7
    preserve_recent_messages: 2
  proofreader:
    max_summary_blocks: 2
    dialogue_compression_threshold: 0.75
  character_designer:
    max_summary_blocks: 2
    dialogue_compression_threshold: 0.85
    preserve_recent_messages: 6
```

**YAML 位置**：`project_root/config/memory_config.yaml`

### 5.2 `SummaryCompressor` 100 章滚动压缩器

**职责**：每 100 章触发一次，把新生成的 100 章摘要压缩为 1 个块。

**核心数据结构**：
```python
@dataclass
class SummaryBlock:
    block_id: str                  # "block_{start:05d}_{end:05d}"
    start_chapter: int
    end_chapter: int
    chapter_count: int
    compressed_text: str
    key_events: list[str]
    character_changes: list[str]
    created_at: str
    char_count: int
```

**触发逻辑**：
```python
def add_chapter_summary(self, chapter_id, summary):
    self._accumulator.append((chapter_id, summary))
    if len(self._accumulator) >= self.config.chapter_window:
        return self._trigger_compression()
    return None
```

**滑窗淘汰**：
```python
def _evict_old_blocks(self):
    while len(self._blocks) > self.config.max_summary_blocks:
        evicted = self._blocks.pop(0)
        logger.info("淘汰旧块 | block_id=%s", evicted.block_id)
```

**LLM 压缩 + 重试**：
```python
def _llm_compress_with_retry(self, text, max_retries=2):
    for attempt in range(1, max_retries + 1):
        try:
            return self._llm_compress(text)
        except Exception as e:
            logger.warning("LLM 压缩失败 | attempt=%d/%d error=%s", attempt, max_retries, e)
            if attempt < max_retries:
                time.sleep(2 ** attempt)  # 指数退避
    
    # 通知前端
    if self.error_callback:
        self.error_callback(...)
    
    # 抛出异常，由用户决定
    raise SummaryCompressionError(...)
```

**块 JSON 损坏恢复**：
```python
def _load_existing_blocks_with_recovery(self):
    for block_path in self.storage_dir.glob("block_*.json"):
        try:
            data = json.loads(block_path.read_text())
            self._blocks.append(SummaryBlock.from_dict(data))
        except (json.JSONDecodeError, KeyError, UnicodeDecodeError) as e:
            logger.warning("块损坏，尝试恢复 | path=%s error=%s", block_path.name, e)
            recovered = self._recover_block(block_path)  # 从章节文件恢复
            if recovered:
                self._blocks.append(recovered)
                # 备份损坏文件
                shutil.move(block_path, block_path.with_suffix(".corrupted.json"))
```

**恢复算法**：从 `block_00001_00100.json` 解析章节范围 → 读取 `chapter_00001_final.md` ~ `chapter_00100_final.md` → 重新提取摘要 → 调用 LLM 重新压缩 → 生成新块。

**持久化**：每块独立 JSON + `index.json`（块 ID 列表）。
**存储位置**：`project_root/memory/summary_blocks/{agent_id}/`

### 5.3 `DialogueCompactor` LLM 对话压缩器

**职责**：当 session 达到 80% token 阈值时，用 LLM 把早期消息压缩为 1 个结构化 system 消息。

**JSON Schema（LLM Prompt 强制）**：
```json
{
  "characters": ["人物1", "人物2"],
  "active_topics": ["主题1", "主题2"],
  "pending_tasks": [
    {"task": "任务描述", "owner": "user|agent", "status": "状态"}
  ],
  "completed_tasks": ["已完成1"],
  "key_decisions": ["决策1"],
  "unresolved_questions": ["问题1"],
  "context_summary": "整体脉络（200字内）"
}
```

**压缩流程**：
1. 估算 `session.total_estimated_tokens()` 是否 ≥ `max_tokens × threshold`
2. 保留最近 K=4 条消息原文
3. 早期消息 → 文本 → LLM 压缩（带严格 JSON Schema Prompt）
4. 失败重试 2 次 → 仍失败 → **静默降级**到 `compaction._build_summary`
5. 解析 JSON 失败 → 重新调用 LLM（加强 prompt）→ 仍失败 → 返回空摘要
6. 替换早期消息为单个 system 消息

**渲染格式**（注入到 session）：
```xml
<dialogue_compression>
出场人物: 陆商曜, 黑商周桓
当前主题: 突破筑基期
待办任务:
  - [user] 完成第 5 章校对 (in_progress)
  - [agent] 生成第 6 章 (pending)
已完成: 撰写第 1-4 章
关键决策: 第 5 章采用伏笔回收
待解决: 主角身世之谜
对话脉络: 主角经过 4 章修炼，即将突破...
</dialogue_compression>
```

### 5.4 `MemoryManager` 顶层门面

**职责**：组合 3 个组件（`GraphMemoryIntegrator` + `SummaryCompressor` + `DialogueCompactor`）+ 配置管理。

**核心 API**：
```python
class MemoryManager:
    def get_memory_config(agent_id) -> MemoryConfig
    def get_summary_compressor(agent_id) -> SummaryCompressor
    def create_dialogue_compactor(agent_id) -> DialogueCompactor
    def on_chapter_generated(agent_id, chapter_id, text) -> Optional[SummaryBlock]
    def get_summary_for_injection(agent_id) -> str
    def reload_config() -> None
    def get_status() -> dict
```

**缓存策略**：
- `SummaryCompressor` 按 agent 缓存（持久化块加载耗时）
- `DialogueCompactor` 不缓存（配置可能变化，每次新建）
- `reload_config()` 清空缓存

---

## 6. 集成点

### 6.1 `ConversationRuntime` 改造

**新增参数**：
```python
def __init__(self, ..., agent_id="main",
             memory_config=None, memory_manager=None):
    self.agent_id = agent_id
    self.memory_config = memory_config or MemoryConfig()
    if memory_manager:
        self.dialogue_compactor = memory_manager.create_dialogue_compactor(agent_id)
```

**`_maybe_auto_compact` 改造**：
```python
def _maybe_auto_compact(self):
    estimated = self.session.total_estimated_tokens()
    max_tokens = self.auto_compaction_threshold
    threshold = self.memory_config.dialogue_compression_threshold
    trigger_tokens = int(max_tokens * threshold)
    
    if estimated < trigger_tokens:
        return None
    
    if self.dialogue_compactor:
        result = self.dialogue_compactor.compact(self.session, max_tokens)
    else:
        # fallback 旧规则
        from .compaction import compact_session
        result = compact_session(self.session)
    
    if result.removed_message_count > 0:
        self.session = result.compacted_session
        return AutoCompactionEvent(...)
    return None
```

### 6.2 `ContextInjector` 扩展

**新增 `MemoryManager` 依赖**：
```python
def __init__(self, ..., memory_manager=None):
    self.memory_manager = memory_manager

def inject_context(self, user_input, max_context_chars=8000, agent_id="main"):
    # 1. 角色上下文（≤ 2000 字/角色，最多 3 个）
    # 2. 伏笔上下文（剩余预算）
    # 3. 历史摘要块（剩余预算）  ← 新增
    if current_len < max_context_chars and self.memory_manager:
        summary_text = self.memory_manager.get_summary_for_injection(agent_id)
        if summary_text:
            summary_text = self._truncate_context(summary_text, remaining)
            context_parts.append(summary_text)
```

**注入优先级**：角色 → 伏笔 → 历史摘要块（剩余预算逐级递减）

### 6.3 `AgentRunner` 子 Agent 改造

**销毁模式（默认）**：
```python
def run_agent(self, agent_def, user_input, task_id=None, **kwargs):
    # 每次创建新 session，永不复用
    sub_session = Session()
    sub_session.id = str(uuid.uuid4())
    
    sub_runtime = ConversationRuntime(
        session=sub_session,
        agent_id=agent_def.name,
        memory_config=self.memory_manager.get_memory_config(agent_def.name) if self.memory_manager else None,
        memory_manager=self.memory_manager,
        # ... 现有参数 ...
    )
    
    # 子 agent 不触发 SummaryCompressor（章节是主 agent 产物）
    return sub_runtime.run_turn(user_input)
```

**关键约束**：
- `agent_id` = 逻辑角色（永久）
- `session_id` = 任务实例 UUID（**100% 永不复用**）
- 任务历史由**主 agent 的 `TaskTracker`** 维护

### 6.4 `GraphMemoryIntegrator` 集成

**不修改内部实现**，仅在 `MemoryManager` 构造时注入引用：
```python
def setup_memory_system(project_root, llm_client):
    graph_integrator = GraphMemoryIntegrator(project_root=project_root)
    graph_integrator.initialize()
    
    memory_manager = MemoryManager(
        project_root=project_root,
        llm_client=llm_client,
        graph_integrator=graph_integrator,
    )
    
    from .context_injector import set_memory_manager
    set_memory_manager(memory_manager)
    
    return memory_manager
```

---

## 7. 错误处理与降级链

| 场景 | 检测点 | 降级策略 |
|------|--------|----------|
| LLM 压缩章节失败 | `SummaryCompressor._llm_compress` 抛异常 | **重试 2 次** → 仍失败 → **通知前端用户**（不静默降级） |
| LLM 压缩对话失败 | `DialogueCompactor._llm_compress` 抛异常 | **重试 2 次** → 仍失败 → **静默降级**到 `compaction._build_summary` |
| LLM 输出非 JSON | `_parse_json_output` 解析失败 | **重试 2 次**（加强 prompt）→ 仍失败 → 返回空 `DialogueSummary` |
| YAML 配置文件不存在 | `MemoryConfigBundle.load_from_yaml` | 返回全默认 `MemoryConfig`（不阻塞启动） |
| 配置文件字段非法 | `MemoryConfig.validate` | logger.warning + 使用默认值（不抛异常） |
| 块 JSON 文件损坏 | `_load_existing_blocks_with_recovery` | 从原始章节文件自动恢复 + 备份损坏文件 |
| 持久化失败 | `persist()` IO 异常 | logger.error + 保留内存数据 + 下次启动重试 |
| 子 agent 配置缺失 | `get_memory_config(unknown_id)` | 返回 `global_config`（兜底） |

**核心原则**：任何压缩失败都不阻塞主流程，最多丢失压缩效果，原始数据保留在 `Session` / 章节文件中。

---

## 8. Web 端配置接口

### 8.1 Agent 设置页结构

```
┌─────────────────────────────────────────────────────┐
│  Agent Settings > Memory Management                 │
├─────────────────────────────────────────────────────┤
│  [Main] [Plot Writer] [Proofreader] [Char Designer] │  ← 4 个 Tab
├─────────────────────────────────────────────────────┤
│  当前 Tab: Main Agent                                │
│                                                     │
│  📚 摘要滑动窗口                                     │
│  ┌─────────────────────────────────────────┐       │
│  │ 滑窗档位:  [100][200][300*][400]...[1000] │       │
│  │ 当前: 3 块 (300 章)                       │       │
│  └─────────────────────────────────────────┘       │
│                                                     │
│  💬 对话压缩                                        │
│  ┌─────────────────────────────────────────┐       │
│  │ 触发阈值:  [====●=====] 80%              │       │
│  │ 保留消息:  [4]                           │       │
│  │ 摘要上限:  [3000] 字符                   │       │
│  │ LLM 模型:  [跟随运行时 ▾] (来自 global)  │       │
│  └─────────────────────────────────────────┘       │
│                                                     │
│  [重置为默认]  [保存]                                │
└─────────────────────────────────────────────────────┘
```

**滑窗档位（10 档固定）**：
100, 200, 300 (默认), 400, 500, 600, 700, 800, 900, 1000

### 8.2 后端 API

```
GET  /api/agents/{agent_id}/memory-config
PUT  /api/agents/{agent_id}/memory-config
POST /api/agents/{agent_id}/memory-config/reset
```

**响应体**：
```json
{
  "agent_id": "plot_writer",
  "config": {
    "max_summary_blocks": 3,
    "dialogue_compression_threshold": 0.7,
    "preserve_recent_messages": 2,
    "dialogue_summary_max_chars": 3000,
    "dialogue_llm_model": null,
    "inherited_from_global": ["chapter_window", "summary_max_chars"]
  },
  "global_config": { ... }
}
```

### 8.3 前端字段分组（每个 Agent tab 一致）

1. **摘要滑动窗口**：`max_summary_blocks` (10 档)
2. **对话压缩**：`dialogue_compression_threshold` + `preserve_recent_messages` + `dialogue_summary_max_chars`
3. **运行时模型**（只读）：`dialogue_llm_model`（来自 global）

---

## 9. 测试策略

### 9.1 测试金字塔

```
                    ┌─────────────┐
                    │   E2E 测试   │  ← 完整流程（5-10 个）
                    ├─────────────┤
                    │  集成测试    │  ← 多组件协作（15-20 个）
                    ├─────────────┤
                    │  单元测试    │  ← 单组件隔离（40-60 个）
                    └─────────────┘
```

**目标覆盖率**：核心组件 > **95%**

### 9.2 单元测试

**`MemoryConfig`**（10 用例）：
- 默认配置 / YAML 加载 / 文件缺失 / YAML 损坏
- 合并：global_only / agent_overrides / agent_inherits
- 校验：max_blocks 越界 / threshold 越界 / 保留消息 < 2
- 解析未知 agent → 返回 global

**`SummaryCompressor`**（13 用例）：
- 累加 < 阈值不触发 / 累加到阈值触发
- 块字段正确 / 滑窗淘汰
- 持久化 + 重新加载
- 规则压缩截断 / LLM 压缩成功 / LLM 失败回退
- LLM 重试机制 / 重试耗尽抛异常
- 注入文本格式 / **损坏块从章节文件恢复**

**`DialogueCompactor`**（10 用例）：
- 阈值检查（上下）
- 保留 K 条消息 / 消息数 < K 不压缩
- LLM 有效 JSON 解析 / 无效 JSON 重试 / 最大重试返回空
- LLM 失败回退 / 渲染格式 / 截断

**`MemoryManager`**（7 用例）：
- 已知/未知 agent 配置 / compressor 缓存
- 重载清空缓存 / 章节生成触发 / 状态报告

### 9.3 集成测试（5 个）

1. **章节生成 → 压缩 → 注入 完整流程**：250 章 → 2 个块 → 注入含 block_id
2. **对话压缩触发与降级**：mock LLM 失败 → 重试 2 次 → 静默回退
3. **子 agent 销毁模式**：5 次调用 → 5 个不同 session_id
4. **配置热重载**：修改 YAML → 重载 → 下次创建使用新配置
5. **块 JSON 损坏恢复**：损坏文件 + 完整章节 → 自动恢复 + 备份损坏文件

### 9.4 性能测试

| 指标 | 目标 |
|------|------|
| 10K 章节处理（mock LLM） | < 60s |
| 注入响应时间 | < 100ms |
| 对话压缩延迟（mock LLM） | < 5s |
| 1M token 内存增长 | < 200MB |
| 配置热重载生效 | < 1s |
| 子 agent session_id 重复率 | 0% |

### 9.5 E2E 测试

1. **完整章节写作流程**（mock LLM）：100 章连续生成 → 验证 1 个块
2. **1M+ Token 压力测试**（真实 LLM，可选）：10K 章连续运行 30-60 分钟

### 9.6 验收清单

- [ ] 单元测试覆盖率 > 95%
- [ ] 集成测试全部通过
- [ ] 性能测试：10K 章 < 60s（mock LLM）
- [ ] 注入响应 < 100ms
- [ ] LLM 压缩对话 < 5s
- [ ] 1M token 压力测试：内存增长 < 200MB
- [ ] 块 JSON 损坏自动恢复率 100%
- [ ] 配置热重载生效 < 1s
- [ ] 子 agent session_id 100% 不重复

---

## 10. 风险与权衡

### 10.1 已识别风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| LLM 压缩章节失败率高 | 用户体验差 | 重试 + 通知用户 + 累积到下一批 |
| 块文件 I/O 性能问题 | 10K 章节时加载慢 | 每块独立 JSON + 索引文件 + 缓存 |
| 配置热重载竞态 | 子 agent 读到旧/新配置混用 | 重载时清空缓存 + 下次访问重建 |
| 子 agent session 泄漏 | 内存增长 | 销毁模式 + 显式 GC |
| YAML 解析错误 | 系统启动失败 | 优雅降级到默认配置 |

### 10.2 设计权衡

- **保留最近 K=4 条原文** vs **更多压缩**：保留过多增加 token 占用，过少破坏对话连贯性
- **滑窗 3 块** vs **更多块**：更多块保留更多历史，但增加注入压力
- **每块独立 JSON** vs **单一索引 JSON**：独立文件支持部分恢复，单一文件加载更快
- **LLM 失败通知用户** vs **静默降级**：章节压缩质量要求高，通知用户；对话压缩是辅助功能，静默降级

---

## 11. 实施计划概要

**阶段 1 - 核心压缩器**（2-3 天）
- `MemoryConfig` 数据类 + YAML 加载
- `SummaryCompressor` 基础实现（不含 LLM 重试）
- 单元测试（覆盖率 > 95%）

**阶段 2 - 对话压缩**（1-2 天）
- `DialogueCompactor` LLM 压缩 + JSON Schema
- 集成到 `ConversationRuntime._maybe_auto_compact`
- 单元 + 集成测试

**阶段 3 - 协调与配置**（1-2 天）
- `MemoryManager` 顶层门面
- `ContextInjector` 集成历史摘要注入
- `AgentRunner` 子 agent 改造（销毁模式）
- 集成测试

**阶段 4 - 错误处理与恢复**（1 天）
- LLM 重试 + 用户通知机制
- 块 JSON 损坏自动恢复
- 边界场景测试

**阶段 5 - Web 端接入**（2-3 天）
- 后端 GET/PUT API
- 前端 Agent 设置页 Memory Management 区块
- 配置热重载端到端测试

**总计**：7-11 个工作日

---

## 12. 附录

### 12.1 关键文件位置

| 文件 | 状态 |
|------|------|
| `src/novels_project/memory/memory_config.py` | 新建 |
| `src/novels_project/memory/summary_compressor.py` | 新建 |
| `src/novels_project/memory/dialogue_compactor.py` | 新建 |
| `src/novels_project/memory/memory_manager.py` | 新建 |
| `src/novels_project/context_injector.py` | 扩展 |
| `src/novels_project/runtime.py` | 扩展 |
| `src/novels_project/agents.py` | 扩展 |
| `src/novels_project/memory/integrator.py` | 不变（仅引用） |
| `src/novels_project/compaction.py` | 保留（作为 DialogueCompactor 的 fallback） |
| `config/memory_config.yaml` | 新建（项目级配置） |
| `memory/summary_blocks/{agent_id}/` | 新建（运行时生成） |

### 12.2 关键依赖

- `pyyaml` - YAML 解析（已有）
- `langchain` - LLM 调用（已有）
- `networkx` - 图谱存储（已有）
- `chromadb` - 向量库（已有）

### 12.3 监控埋点（Logger 输出）

```
[SummaryCompressor] 触发压缩 | chapter_range=1-100 count=100
[SummaryCompressor] 压缩完成 | block_id=block_00001_00100 char_count=1500 total_blocks=3
[SummaryCompressor] 淘汰旧块 | block_id=block_00001_00100 chapters=1-100
[SummaryCompressor] 块损坏，尝试恢复 | path=block_00001_00100.json error=...
[DialogueCompactor] LLM 压缩完成 | agent=plot_writer removed=20 summary_len=2500
[DialogueCompactor] LLM 失败回退规则 | agent=main error=...
[ContextInjector] 注入历史摘要块 | agent=main summary_len=1500
[Runtime] 对话压缩完成 | agent=plot_writer removed=20 summary_len=2500
[MemoryManager] 配置重载 | path=config/memory_config.yaml
```

### 12.4 词汇表

- **SummaryBlock**：100 章压缩后的摘要块，独立 JSON 文件
- **Sliding Window**：滑窗机制，保留最近 N 个块
- **Destroy Mode**：子 agent session 销毁模式（默认）
- **Source of Truth**：原始章节文件 `chapter_*_final.md`，是块数据的权威源
- **JSON Schema Compression**：LLM 按 JSON Schema 输出的结构化对话压缩

---

**设计完成日期**: 2026-06-11
**待用户审阅**: ⏳
**审阅通过后进入**: writing-plans 技能 → 生成详细实施计划
