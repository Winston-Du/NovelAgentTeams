"""记忆压缩子系统异常类。

继承自 shared.exceptions.NovelAgentError，便于统一异常处理。
"""
from __future__ import annotations
from ..shared.exceptions import NovelAgentError


class SummaryCompressionError(NovelAgentError):
    """100 章摘要压缩失败（重试耗尽后抛出）。"""

    def __init__(self, message: str, chapter_range: tuple[int, int]):
        super().__init__(message)
        self.chapter_range = chapter_range


class DialogueCompressionError(NovelAgentError):
    """LLM 对话压缩失败。"""


class BlockRecoveryError(NovelAgentError):
    """块 JSON 损坏后从章节文件恢复失败。"""

    def __init__(self, message: str, block_path: str):
        super().__init__(message)
        self.block_path = block_path
