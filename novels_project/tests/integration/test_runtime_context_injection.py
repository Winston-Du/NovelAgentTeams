"""Runtime._inject_context 端到端集成测试（Task 12 链路验证）。

真实场景链路：
    章节生成 → MemoryManager.on_chapter_generated → SummaryCompressor 压缩
    → Runtime._inject_context → ContextInjector → 注入历史摘要块

覆盖 6 个核心场景：
1. 端到端：100 章触发压缩 → Runtime._inject_context 返回含摘要块的 enriched text
2. 子 agent：不同 agent_id 的摘要块正确隔离
3. 失败兜底：MemoryManager 异常时 _inject_context 仍返回原始 user_input
4. 优先级：摘要块在「上下文信息」包裹内正确出现
5. 无 memory_manager：回退到全局 injector（行为兼容）
6. 真实 run_turn 链路：注入的消息含摘要块（不仅 _inject_context 单独调用）
"""
from pathlib import Path

import pytest

from novels_project.runtime import ConversationRuntime
from novels_project.session import Session
from novels_project.tool_spec import ToolRegistry
from novels_project.memory.memory_manager import MemoryManager


# === Fixtures ===

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


def _make_memory_manager(tmp_path: Path) -> MemoryManager:
    """构造一个最小可用的 MemoryManager（无 LLM → 走规则压缩）。"""
    config_path = tmp_path / "memory_config.yaml"
    config_path.write_text(
        """
global:
  chapter_window: 100
  max_summary_blocks: 3
  summary_max_chars: 2000
agents: {}
""",
        encoding="utf-8",
    )
    return MemoryManager(
        project_root=tmp_path,
        config_path=config_path,
        llm_client=None,
    )


def _populate_chapters(mgr: MemoryManager, n: int, agent_id: str = "main") -> None:
    """向 MemoryManager 注入 n 章，触发压缩。"""
    for i in range(1, n + 1):
        mgr.on_chapter_generated(
            agent_id, i, f"# 第{i}章\n\n第{i}章内容摘要。",
        )


def _make_runtime(
    *,
    memory_manager: MemoryManager = None,
    agent_id: str = "main",
    max_iterations: int = 1,
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
        memory_manager=memory_manager,
        max_iterations=max_iterations,
    )


# === 场景 1: 端到端真实场景 ===

def test_runtime_inject_context_injects_summary_block_end_to_end(tmp_path):
    """端到端：100 章 → Runtime._inject_context 返回含摘要块。"""
    mgr = _make_memory_manager(tmp_path)
    _populate_chapters(mgr, 100)
    runtime = _make_runtime(memory_manager=mgr, agent_id="main")

    enriched = runtime._inject_context("请写第101章")

    # 真实场景：摘要块必须注入
    assert "历史剧情摘要" in enriched
    assert "block_00001_00100" in enriched
    # 用户原始输入保留
    assert "请写第101章" in enriched
    # 上下文包裹标签存在
    assert "【上下文信息】" in enriched
    assert "【用户输入】" in enriched


# === 场景 2: 子 agent 隔离 ===

def test_subagent_gets_its_own_summary_block(tmp_path):
    """子 agent 应获取自己的 agent_id 对应的摘要块。"""
    mgr = _make_memory_manager(tmp_path)
    # 只给 plot_writer 灌 100 章
    _populate_chapters(mgr, 100, agent_id="plot_writer")

    # main agent：没有块 → 无摘要注入
    runtime_main = _make_runtime(memory_manager=mgr, agent_id="main")
    enriched_main = runtime_main._inject_context("test")
    assert "历史剧情摘要" not in enriched_main

    # plot_writer agent：有块 → 摘要注入
    runtime_pw = _make_runtime(memory_manager=mgr, agent_id="plot_writer")
    enriched_pw = runtime_pw._inject_context("test")
    assert "历史剧情摘要" in enriched_pw
    assert "block_00001_00100" in enriched_pw


# === 场景 3: 失败兜底 ===

def test_memory_manager_failure_does_not_break_inject_context(tmp_path):
    """MemoryManager 异常时 _inject_context 仍返回原始 user_input。"""
    mgr = _make_memory_manager(tmp_path)
    _populate_chapters(mgr, 100)
    runtime = _make_runtime(memory_manager=mgr)

    # 模拟 get_summary_for_injection 抛异常
    from unittest.mock import MagicMock
    mgr.get_summary_for_injection = MagicMock(
        side_effect=RuntimeError("mocked memory failure"),
    )

    enriched = runtime._inject_context("user_input_text")
    # 注入失败时至少返回原始输入
    assert "user_input_text" in enriched
    # 不应包含上下文包裹（因为注入失败）
    assert "【上下文信息】" not in enriched


# === 场景 4: 注入位置正确 ===

def test_summary_block_inside_context_envelope(tmp_path):
    """摘要块应在【上下文信息】包裹内（不是出现在 user_input 之后）。"""
    mgr = _make_memory_manager(tmp_path)
    _populate_chapters(mgr, 100)
    runtime = _make_runtime(memory_manager=mgr)

    enriched = runtime._inject_context("user_input")

    # 找到 【上下文信息】和【用户输入】的索引
    ctx_start = enriched.find("【上下文信息】")
    user_start = enriched.find("【用户输入】")
    summary_start = enriched.find("历史剧情摘要")

    # 摘要应在 ctx 之后、user 之前
    assert ctx_start >= 0
    assert user_start > ctx_start
    assert summary_start > ctx_start
    assert summary_start < user_start


# === 场景 5: 无 memory_manager 时回退 ===

def test_no_memory_manager_uses_fallback_injector():
    """无 memory_manager 时回退到全局 injector（行为兼容）。"""
    runtime = _make_runtime(memory_manager=None)
    enriched = runtime._inject_context("user_input")

    # 不应崩溃；至少包含原始输入
    assert "user_input" in enriched
    # 全局 injector 在测试环境下没有真实图数据，所以无上下文注入
    # 但调用本身应成功
    assert enriched == "user_input" or "user_input" in enriched


# === 场景 6: 真实 run_turn 链路 ===

def test_run_turn_session_contains_summary_in_enriched_message(tmp_path):
    """真实 run_turn 链路：注入后的 user 消息应含摘要块（不仅是 _inject_context）。"""
    mgr = _make_memory_manager(tmp_path)
    _populate_chapters(mgr, 100)
    runtime = _make_runtime(
        memory_manager=mgr,
        max_iterations=0,  # 立即退出 agent 循环
    )

    # 调用 run_turn（虽然 max_iterations=0，但 _inject_context 在 Phase 1 已执行）
    try:
        runtime.run_turn("真实场景输入")
    except Exception:
        # max_iterations=0 可能会抛错，但 Phase 1 的 _inject_context 已完成
        pass

    # 验证 session 中第一条 user 消息含摘要块
    # Phase 1: enriched_input = self._inject_context(user_input) 后追加到 session
    assert len(runtime.session.messages) >= 1
    first_msg_text = runtime.session.messages[0].get_text()
    assert "历史剧情摘要" in first_msg_text
    assert "block_00001_00100" in first_msg_text
    assert "真实场景输入" in first_msg_text
