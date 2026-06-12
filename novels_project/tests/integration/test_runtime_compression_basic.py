"""ConversationRuntime 与 MemoryConfig 基础集成测试（Task 10a）。

10a 范围：验证 MemoryConfig 阈值和 agent_id 集成。
10a 不引入 DialogueCompactor（留到 10b）。

覆盖 5 个核心场景：
1. MemoryConfig 参数传入
2. 默认配置
3. agent_id 参数
4. _maybe_auto_compact 使用 MemoryConfig 阈值
5. 低于阈值时不压缩
"""
from novels_project.runtime import ConversationRuntime
from novels_project.session import Session, ConversationMessage, MessageRole, TextBlock
from novels_project.memory.memory_config import MemoryConfig
from novels_project.tool_spec import ToolRegistry


class _MockApiClient:
    """不实际调用的 ApiClient stub。"""
    def stream(self, *args, **kwargs):
        del args, kwargs
        return []


class _MockToolExecutor:
    """不实际执行的 ToolExecutor stub。"""
    def execute(self, tool_name: str, tool_input: str):
        del tool_name, tool_input
        return ("", False)


def _make_runtime(**overrides):
    """构造最小可用的 ConversationRuntime（不调用 LLM）。"""
    kwargs = dict(
        session=Session(),
        api_client=_MockApiClient(),
        tool_executor=_MockToolExecutor(),
        tool_registry=ToolRegistry(),
        system_prompt="test",
        model="test-model",
        max_iterations=1,
    )
    kwargs.update(overrides)
    return ConversationRuntime(**kwargs)


# === 场景 1: MemoryConfig 参数 ===

def test_runtime_accepts_memory_config_parameter():
    """MemoryConfig 应作为可选参数传入。"""
    cfg = MemoryConfig(dialogue_compression_threshold=0.7)
    runtime = _make_runtime(memory_config=cfg)
    assert runtime.memory_config.dialogue_compression_threshold == 0.7


# === 场景 2: 默认配置 ===

def test_runtime_has_default_memory_config():
    """未传 memory_config 时使用默认配置。"""
    runtime = _make_runtime()
    assert runtime.memory_config is not None
    assert runtime.memory_config.dialogue_compression_threshold == 0.8
    assert runtime.agent_id == "main"


# === 场景 3: agent_id 参数 ===

def test_runtime_accepts_agent_id_parameter():
    """agent_id 应作为参数传入。"""
    runtime = _make_runtime(agent_id="plot_writer")
    assert runtime.agent_id == "plot_writer"


# === 场景 4: 阈值触发压缩 ===

def test_maybe_auto_compact_uses_memory_config_threshold():
    """_maybe_auto_compact 应使用 MemoryConfig.dialogue_compression_threshold。"""
    cfg = MemoryConfig(dialogue_compression_threshold=0.5)  # 50% 触发
    runtime = _make_runtime(
        memory_config=cfg,
        auto_compaction_threshold=1000,
    )

    # 注入消息使 estimated tokens 达到 600（> 500 trigger）
    for _ in range(10):
        runtime.session.messages.append(
            ConversationMessage(
                role=MessageRole.USER,
                blocks=[TextBlock(text="x" * 240)],  # 60 tokens
            )
        )

    # 估算 ~600 tokens, 50% of 1000 = 500 → 触发
    event = runtime._maybe_auto_compact()
    assert event is not None
    assert event.removed_message_count > 0


# === 场景 5: 低于阈值不压缩 ===

def test_maybe_auto_compact_below_threshold_no_action():
    """未达阈值时不压缩。"""
    cfg = MemoryConfig(dialogue_compression_threshold=0.95)
    runtime = _make_runtime(
        memory_config=cfg,
        auto_compaction_threshold=10000,
    )
    # 仅少量 tokens
    runtime.session.messages.append(
        ConversationMessage(
            role=MessageRole.USER,
            blocks=[TextBlock(text="hello")],
        )
    )
    event = runtime._maybe_auto_compact()
    assert event is None
