"""ChapterSummaryBlock 数据类。

100 章压缩后的剧情摘要块，按 5 位补零的章节号生成唯一 block_id。
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional
import logging

logger = logging.getLogger("novels_project.memory.chapter_summary_block")


@dataclass
class ChapterSummaryBlock:
    """100 章压缩后的剧情摘要块。

    持久化到 JSON 文件，key_events / character_changes 由 SummaryCompressor
    在压缩时填充（任务 5-6），char_count 由 __post_init__ 自动计算。
    """
    block_id: str                                          # "block_{start:05d}_{end:05d}"
    start_chapter: int                                     # 起始章节号
    end_chapter: int                                       # 结束章节号
    chapter_count: int                                     # 实际章节数（end - start + 1）
    compressed_text: str                                   # 压缩后的文本
    key_events: List[str] = field(default_factory=list)    # 关键事件列表
    character_changes: List[str] = field(default_factory=list)  # 人物状态变化
    created_at: str = ""                                   # ISO 8601 时间戳
    char_count: int = 0                                    # 压缩后字符数（自动计算）

    def __post_init__(self) -> None:
        """自动计算 char_count（仅在显式为 0 且 compressed_text 非空时）。"""
        if self.char_count == 0 and self.compressed_text:
            old = self.char_count
            self.char_count = len(self.compressed_text)
            logger.info(
                "[ChapterSummaryBlock] 自动计算 char_count | block_id=%s old=%d new=%d text_len=%d",
                self.block_id, old, self.char_count, len(self.compressed_text),
            )
        elif self.char_count > 0 and self.compressed_text:
            logger.debug(
                "[ChapterSummaryBlock] 保留显式 char_count | block_id=%s char_count=%d text_len=%d",
                self.block_id, self.char_count, len(self.compressed_text),
            )
        elif not self.compressed_text:
            logger.warning(
                "[ChapterSummaryBlock] compressed_text 为空，char_count 保持 0 | block_id=%s",
                self.block_id,
            )

    def to_dict(self) -> dict:
        """序列化为字典（用于 JSON 持久化）。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ChapterSummaryBlock":
        """从字典反序列化（用于加载 JSON）。"""
        logger.info(
            "[ChapterSummaryBlock] from_dict | block_id=%s start=%s end=%s",
            data.get("block_id"), data.get("start_chapter"), data.get("end_chapter"),
        )
        return cls(**data)

    @classmethod
    def from_chapters(
        cls,
        start: int,
        end: int,
        compressed_text: str,
        key_events: Optional[List[str]] = None,
        character_changes: Optional[List[str]] = None,
        created_at: Optional[str] = None,
    ) -> "ChapterSummaryBlock":
        """工厂方法：自动生成 block_id、chapter_count、created_at。"""
        block_id = f"block_{start:05d}_{end:05d}"
        chapter_count = end - start + 1
        logger.info(
            "[ChapterSummaryBlock] from_chapters | block_id=%s range=%d-%d count=%d text_len=%d",
            block_id, start, end, chapter_count, len(compressed_text),
        )
        return cls(
            block_id=block_id,
            start_chapter=start,
            end_chapter=end,
            chapter_count=chapter_count,
            compressed_text=compressed_text,
            key_events=list(key_events) if key_events else [],
            character_changes=list(character_changes) if character_changes else [],
            created_at=created_at if created_at else datetime.now().isoformat(),
        )
