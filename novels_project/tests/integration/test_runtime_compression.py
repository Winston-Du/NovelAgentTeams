"""ConversationRuntime 与 DialogueCompactor 集成测试（Task 10b）。

10b 范围：验证 Runtime 集成 DialogueCompactor 后的端到端行为。
- memory_manager 参数（创建 dialogue_compactor）
- 综合分数（token 比例 + 增长率）
- 经验信号（session 引用是否变化）
- 链路 logger

覆盖 4 个核心场景：
1. 接受 memory_manager 参数
2. 自动创建 dialogue_compactor
3. 综合分数触发压缩
4. 增长率与比例共同决定
"""
import logging

import pytest

from novels_project.runtime import ConversationRuntime
from novels_project.session import Session, ConversationMessage, MessageRole, TextBlock
from novels_project.memory.memory_config import MemoryConfig
from novels_project.memory.memory_manager import MemoryManager
from novels_project.memory.dialogue_compactor import DialogueCompactor
from novels_project.tool_spec import ToolRegistry
from novels_project.compaction import compact_session


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


def _make_runtime(
    *,
    memory_config: MemoryConfig = None,
    memory_manager: MemoryManager = None,
    auto_compaction_threshold: int = 1000,
    agent_id: str = "main",
) -> ConversationRuntime:
    """构造最小可用的 ConversationRuntime。"""
    return ConversationRuntime(
        session=Session(),
        api_client=_MockApiClient(),
        tool_executor=_MockToolExecutor(),
        tool_registry=ToolRegistry(),
        system_prompt="test",
        model="test-model",
        agent_id=agent_id,
        memory_config=memory_config or MemoryConfig(),
        memory_manager=memory_manager,
        auto_compaction_threshold=auto_compaction_threshold,
    )


def _fill_session_with_messages(runtime: ConversationRuntime, n: int, msg_len: int = 240) -> None:
    """向 session 注入 n 条用户消息。"""
    for _ in range(n):
        runtime.session.messages.append(
            ConversationMessage(
                role=MessageRole.USER,
                blocks=[TextBlock(text="x" * msg_len)],
            )
        )


# === 场景 1: memory_manager 参数 ===

def test_runtime_accepts_memory_manager_parameter():
    """Runtime 应接受 memory_manager 参数并保存。"""
    mgr = MemoryManager(project_root="/tmp/test")
    runtime = _make_runtime(memory_manager=mgr)
    assert runtime.memory_manager is mgr


def test_runtime_memory_manager_default_none():
    """未传 memory_manager 时默认为 None。"""
    runtime = _make_runtime()
    assert runtime.memory_manager is None


# === 场景 2: dialogue_compactor 工厂 ===

def test_runtime_creates_dialogue_compactor_from_manager():
    """传入 memory_manager 时 Runtime 应能创建 dialogue_compactor。"""
    mgr = MemoryManager(project_root="/tmp/test")
    runtime = _make_runtime(memory_manager=mgr, agent_id="plot_writer")

    # 通过 _create_dialogue_compactor 方法创建
    compactor = runtime._create_dialogue_compactor()
    assert isinstance(compactor, DialogueCompactor)


def test_runtime_create_dialogue_compactor_without_manager():
    """未传 memory_manager 时调用 _create_dialogue_compactor 报错。"""
    runtime = _make_runtime()
    with pytest.raises(RuntimeError, match="memory_manager"):
        runtime._create_dialogue_compactor()


# === 场景 3: 综合分数（token 比例 + 增长率）===

def test_compute_compression_score_token_ratio_dominant():
    """综合分数应以 token 比例为主（权重 0.7）。"""
    runtime = _make_runtime(auto_compaction_threshold=1000)
    # 比例 1.0, 增长率 0 → 综合 0.7
    score = runtime._compute_compression_score(estimated=1000, max_tokens=1000)
    assert 0.65 <= score <= 0.75


def test_compute_compression_score_combines_ratio_and_growth():
    """综合分数应同时考虑比例和增长率。"""
    runtime = _make_runtime(auto_compaction_threshold=1000)
    # 第一次压缩后更新状态：上次 0 tokens, 0 turns
    # 模拟 5 turns 后到 800 tokens（比例 0.8, 增长率 160/turn）
    runtime._last_compress_estimated = 0
    runtime._turns_since_last_compress = 5
    score = runtime._compute_compression_score(estimated=800, max_tokens=1000)
    # score = 0.8 * 0.7 + min(160/2000, 1.0) * 0.3 = 0.56 + 0.024 = 0.584
    assert 0.55 <= score <= 0.62


def test_compute_compression_score_below_threshold_no_action():
    """综合分数低于阈值时返回 None。"""
    runtime = _make_runtime(auto_compaction_threshold=1000)
    # 比例 0.5, 增长率 0 → 综合 0.35
    event = runtime._maybe_auto_compact()
    assert event is None


def test_compute_compression_score_above_threshold_triggers():
    """综合分数高于阈值时触发压缩。"""
    runtime = _make_runtime(auto_compaction_threshold=1000)
    # 比例 0.9, 增长率 0 → 综合 0.63 > 0.6 阈值
    _fill_session_with_messages(runtime, 20, msg_len=300)  # ~1800 tokens
    event = runtime._maybe_auto_compact()
    assert event is not None
    assert event.removed_message_count > 0


# === 场景 4: 经验信号（session 引用是否变化）===

def test_compaction_uses_session_identity_signal(tmp_path, caplog):
    """压缩决策应使用 session 引用变化作经验信号（不是 removed_message_count）。"""
    cfg = MemoryConfig(
        dialogue_compression_threshold=0.5,
        preserve_recent_messages=2,
    )
    mgr = MemoryManager(project_root=str(tmp_path))
    runtime = _make_runtime(
        memory_config=cfg,
        memory_manager=mgr,
        auto_compaction_threshold=100,
    )
    _fill_session_with_messages(runtime, 10, msg_len=240)
    original_session = runtime.session

    with caplog.at_level(logging.INFO, logger="novels_project.runtime"):
        event = runtime._maybe_auto_compact()

    # 经验信号：runtime.session 不再是原 session
    assert event is not None
    assert runtime.session is not original_session
    # 链路 logger 出现
    assert "调用压缩接口" in caplog.text
    # backend 应为 dialogue_compactor（因为有 memory_manager）
    assert "backend=dialogue_compactor" in caplog.text


def test_compaction_updates_growth_state():
    """压缩成功后应更新 last_compress_estimated 和 turns_since_last_compress。"""
    runtime = _make_runtime(auto_compaction_threshold=1000)
    _fill_session_with_messages(runtime, 20, msg_len=300)
    runtime._turns_since_last_compress = 5  # 模拟 5 turns

    event = runtime._maybe_auto_compact()
    assert event is not None
    # 状态已更新
    assert runtime._turns_since_last_compress == 0
    assert runtime._last_compress_estimated > 0


# === 场景 5: 降级路径（无 memory_manager）===

def test_runtime_falls_back_to_compact_session_without_manager():
    """未传 memory_manager 时 Runtime 应回退到 compact_session。"""
    runtime = _make_runtime(
        auto_compaction_threshold=1000,
        memory_config=MemoryConfig(),
    )
    _fill_session_with_messages(runtime, 20, msg_len=300)

    with pytest.raises(RuntimeError):
        # 没有 compactor 也能工作（用 compact_session）
        # 但 _create_dialogue_compactor 会报错
        runtime._create_dialogue_compactor()

    # _maybe_auto_compact 不依赖 compactor
    event = runtime._maybe_auto_compact()
    assert event is not None  # 走 compact_session fallback
