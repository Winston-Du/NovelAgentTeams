"""ChapterSummaryBlock 数据类。

100 章压缩后的剧情摘要块，按 5 位补零的章节号生成唯一 block_id。
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional


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
            self.char_count = len(self.compressed_text)

    def to_dict(self) -> dict:
        """序列化为字典（用于 JSON 持久化）。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ChapterSummaryBlock":
        """从字典反序列化（用于加载 JSON）。"""
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
        return cls(
            block_id=f"block_{start:05d}_{end:05d}",
            start_chapter=start,
            end_chapter=end,
            chapter_count=end - start + 1,
            compressed_text=compressed_text,
            key_events=list(key_events) if key_events else [],
            character_changes=list(character_changes) if character_changes else [],
            created_at=created_at if created_at else datetime.now().isoformat(),
        )
