"""ContextInjector 与历史摘要块注入的集成测试（Task 12）。

覆盖场景：
1. 注入历史摘要块：传入 memory_manager + 触发压缩 → 注入文本含 "历史剧情摘要" 和 block_id
2. 无 memory_manager 时行为不变：旧调用方式不破坏
3. 摘要块受 max_context_chars 预算控制（截断/不截断）
4. 摘要块在角色/伏笔之后（最低优先级）
5. 不同 agent_id 隔离
6. memory_manager.get_summary_for_injection 异常时不阻塞注入
7. 摘要为空时不注入（无块）
"""
import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from novels_project.context_injector import ContextInjector
from novels_project.memory.memory_manager import MemoryManager


# === Fixtures ===

@pytest.fixture
def memory_config_path(tmp_path: Path) -> Path:
    """生成最小可用的 memory_config.yaml。"""
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
    return config_path


@pytest.fixture
def memory_manager(
    tmp_path: Path, memory_config_path: Path
) -> MemoryManager:
    """构造一个可用的 MemoryManager（无 LLM → 走规则压缩）。"""
    return MemoryManager(
        project_root=tmp_path,
        config_path=memory_config_path,
        llm_client=None,
    )


def _populate_chapters(mgr: MemoryManager, n: int, agent_id: str = "main") -> None:
    """向 MemoryManager 注入 n 章，触发压缩（默认 100 章 1 块）。"""
    for i in range(1, n + 1):
        mgr.on_chapter_generated(
            agent_id, i, f"# 第{i}章\n\n这是第{i}章的内容摘要。",
        )


# === 场景 1: 注入历史摘要块 ===

def test_context_injector_injects_summary_blocks(tmp_path, memory_manager):
    """传入 memory_manager + 100 章 → 注入结果含历史剧情摘要与 block_id。"""
    _populate_chapters(memory_manager, 100)

    injector = ContextInjector(memory_manager=memory_manager)
    result = injector.inject_context(
        "请继续", max_context_chars=8000, agent_id="main",
    )

    assert "历史剧情摘要" in result
    assert "block_00001_00100" in result
    # 注入应包含原始 user_input
    assert "请继续" in result
    # 注入应包含上下文包裹
    assert "【上下文信息】" in result
    assert "【用户输入】" in result


def test_context_injector_default_agent_id(memory_manager):
    """未传 agent_id 时默认为 "main"。"""
    _populate_chapters(memory_manager, 100)
    injector = ContextInjector(memory_manager=memory_manager)

    result = injector.inject_context("test_input", max_context_chars=8000)

    assert "历史剧情摘要" in result
    assert "block_00001_00100" in result


# === 场景 2: 无 memory_manager 时行为不变 ===

def test_context_injector_without_memory_manager_unchanged():
    """未传 memory_manager → "历史剧情摘要" 不在结果中。"""
    injector = ContextInjector()  # memory_manager 默认 None
    result = injector.inject_context("请继续", max_context_chars=8000)

    assert "历史剧情摘要" not in result


def test_context_injector_old_signature_works():
    """旧的 (user_input, max_context_chars) 调用方式不破坏。"""
    injector = ContextInjector()
    # 旧调用方式：仅传位置参数
    result = injector.inject_context("test_input")
    assert "test_input" in result


# === 场景 3: 摘要块受预算控制 ===

def test_summary_block_truncated_by_budget(tmp_path, memory_manager):
    """max_context_chars 较小时，摘要块被截断。"""
    _populate_chapters(memory_manager, 100)
    injector = ContextInjector(memory_manager=memory_manager)

    # 极小预算：截断后应包含省略号标记
    result_small = injector.inject_context(
        "test", max_context_chars=200, agent_id="main",
    )
    assert "..." in result_small or "[内容已截断]" in result_small

    # 充足预算：包含完整 block_id
    result_large = injector.inject_context(
        "test", max_context_chars=8000, agent_id="main",
    )
    assert "block_00001_00100" in result_large


# === 场景 4: 摘要块为空时不注入 ===

def test_no_summary_no_injection(memory_manager):
    """未触发任何压缩时，不注入历史摘要块。"""
    # 仅添加 5 章，远未达到 chapter_window=100
    _populate_chapters(memory_manager, 5)
    injector = ContextInjector(memory_manager=memory_manager)

    result = injector.inject_context("test", max_context_chars=8000, agent_id="main")

    assert "历史剧情摘要" not in result


# === 场景 5: agent_id 隔离 ===

def test_different_agents_use_independent_blocks(
    tmp_path, memory_config_path,
):
    """不同 agent_id 的摘要块互相隔离。"""
    mgr = MemoryManager(
        project_root=tmp_path,
        config_path=memory_config_path,
        llm_client=None,
    )
    # 仅给 plot_writer 添加 100 章
    _populate_chapters(mgr, 100, agent_id="plot_writer")

    injector = ContextInjector(memory_manager=mgr)
    # main 没有块 → 无摘要注入
    result_main = injector.inject_context(
        "test", max_context_chars=8000, agent_id="main",
    )
    assert "历史剧情摘要" not in result_main

    # plot_writer 有块 → 有摘要注入
    result_pw = injector.inject_context(
        "test", max_context_chars=8000, agent_id="plot_writer",
    )
    assert "历史剧情摘要" in result_pw
    assert "block_00001_00100" in result_pw


# === 场景 6: memory_manager 异常时不阻塞注入 ===

def test_memory_manager_failure_does_not_block_injection(
    tmp_path, memory_config_path, caplog,
):
    """MemoryManager.get_summary_for_injection 抛异常时，注入仍可完成。"""
    mgr = MemoryManager(
        project_root=tmp_path,
        config_path=memory_config_path,
        llm_client=None,
    )
    _populate_chapters(mgr, 100)

    # 替换 get_summary_for_injection 抛异常
    mgr.get_summary_for_injection = MagicMock(
        side_effect=RuntimeError("mocked failure"),
    )

    injector = ContextInjector(memory_manager=mgr)
    with caplog.at_level(logging.WARNING, logger="novels_project.context_injector"):
        result = injector.inject_context(
            "test", max_context_chars=8000, agent_id="main",
        )

    # 注入仍应返回 user_input
    assert "test" in result
    # 警告日志应有记录
    assert any("获取历史摘要块失败" in r.message for r in caplog.records)


# === 场景 7: __init__ 接受 memory_manager 参数 ===

def test_init_accepts_memory_manager(memory_manager):
    """ContextInjector(memory_manager=mgr) 应正确保存引用。"""
    injector = ContextInjector(memory_manager=memory_manager)
    assert injector.memory_manager is memory_manager
    assert injector.enabled is True


def test_init_default_memory_manager_is_none():
    """未传 memory_manager 时默认为 None。"""
    injector = ContextInjector()
    assert injector.memory_manager is None


# === 场景 8: Logger 埋点验证 ===

def test_logger_emits_injection_event(
    tmp_path, memory_manager, caplog,
):
    """成功注入时应记录 [ContextInjector] 注入历史摘要块 日志。"""
    _populate_chapters(memory_manager, 100)
    injector = ContextInjector(memory_manager=memory_manager)

    with caplog.at_level(logging.INFO, logger="novels_project.context_injector"):
        injector.inject_context("test", max_context_chars=8000, agent_id="main")

    log_messages = [r.message for r in caplog.records]
    assert any("注入历史摘要块" in msg for msg in log_messages)
    # 应包含 agent_id 与 summary_len
    matched = [m for m in log_messages if "注入历史摘要块" in m]
    assert any("agent=main" in m for m in matched)


def test_logger_emits_skip_event_when_no_memory_manager(caplog):
    """未配置 memory_manager 时应记录跳过日志。"""
    injector = ContextInjector()
    with caplog.at_level(logging.INFO, logger="novels_project.context_injector"):
        injector.inject_context("test", max_context_chars=8000, agent_id="main")

    log_messages = [r.message for r in caplog.records]
    assert any(
        "未配置 memory_manager" in msg and "跳过历史摘要块注入" in msg
        for msg in log_messages
    )
