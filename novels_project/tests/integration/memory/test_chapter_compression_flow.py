"""Task 15: 章节压缩完整流程端到端集成测试。

验证 250 章节的完整链路：
  章节生成 → MemoryManager.on_chapter_generated
  → SummaryCompressor 累加到 100 章触发压缩
  → 生成 ChapterSummaryBlock（含 block_id）
  → get_summary_for_injection 输出块引用
"""
from __future__ import annotations

import pytest
from novels_project.memory.memory_manager import MemoryManager


# ---------------------------------------------------------------------------
# Mock
# ---------------------------------------------------------------------------

class MockLLMClient:
    """模拟 LLM 客户端，返回固定压缩摘要。"""

    def __init__(self):
        self.call_count = 0

    def stream(self, request, print_stream=False):
        self.call_count += 1
        return [type("Event", (), {"text": f"压缩摘要 {self.call_count}"})()]


# ---------------------------------------------------------------------------
# 场景 1: 250 章产生 2 个 block + 50 条未压缩累加
# ---------------------------------------------------------------------------

def test_250_chapters_produces_2_blocks(tmp_path):
    """chapter_window=100, max_summary_blocks=3 → 250 章应产生 2 个 block。"""
    config_path = tmp_path / "memory_config.yaml"
    config_path.write_text(
        "global:\n"
        "  chapter_window: 100\n"
        "  max_summary_blocks: 3\n",
        encoding="utf-8",
    )
    mgr = MemoryManager(
        project_root=tmp_path,
        config_path=config_path,
        llm_client=MockLLMClient(),
    )

    # 模拟 250 章生成
    for i in range(1, 251):
        mgr.on_chapter_generated("main", i, f"第{i}章内容")

    compressor = mgr.get_summary_compressor("main")

    # 250/100 = 2 次触发压缩（第 100、200 章）
    assert len(compressor._blocks) == 2
    assert compressor._blocks[0].end_chapter == 100
    assert compressor._blocks[1].end_chapter == 200
    # 201-250 章在累加器中
    assert len(compressor._accumulator) == 50


# ---------------------------------------------------------------------------
# 场景 2: 注入文本包含 block_id 引用
# ---------------------------------------------------------------------------

def test_summary_injection_contains_block_ids(tmp_path):
    """100 章压缩后，注入文本应包含 block_00001_00100。"""
    config_path = tmp_path / "memory_config.yaml"
    config_path.write_text("global: {}", encoding="utf-8")
    mgr = MemoryManager(
        project_root=tmp_path,
        config_path=config_path,
        llm_client=MockLLMClient(),
    )

    for i in range(1, 101):
        mgr.on_chapter_generated("main", i, f"第{i}章")

    injected = mgr.get_summary_for_injection("main")
    assert "block_00001_00100" in injected
