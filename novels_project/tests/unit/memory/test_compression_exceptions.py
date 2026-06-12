"""Test custom exception hierarchy for memory compression.

继承自 shared.exceptions.NovelAgentError，便于统一异常处理。
"""
import pytest
from novels_project.memory.compression_exceptions import (
    SummaryCompressionError,
    DialogueCompressionError,
    BlockRecoveryError,
)
from novels_project.shared.exceptions import NovelAgentError


def test_summary_compression_error_includes_chapter_range():
    err = SummaryCompressionError(
        "LLM failed",
        chapter_range=(1, 100),
    )
    assert err.chapter_range == (1, 100)
    assert "LLM failed" in str(err)


def test_block_recovery_error_includes_block_path():
    err = BlockRecoveryError(
        "Recovery failed",
        block_path="/tmp/block_00001_00100.json",
    )
    assert err.block_path == "/tmp/block_00001_00100.json"
    assert "Recovery failed" in str(err)


def test_all_compression_errors_inherit_novel_agent_error():
    """所有压缩异常必须是 NovelAgentError 子类（统一异常处理）。"""
    assert issubclass(SummaryCompressionError, NovelAgentError)
    assert issubclass(DialogueCompressionError, NovelAgentError)
    assert issubclass(BlockRecoveryError, NovelAgentError)
