"""SummaryCompressor 100 章滚动压缩器。

工作流：
1. add_chapter_summary 累加到 accumulator
2. 累积到 chapter_window 时触发 _trigger_compression
3. _rule_compress 规则压缩（Task 5）；Task 6 升级为 LLM 压缩
4. 滑窗淘汰（超过 max_blocks 时）
5. 持久化到 storage_dir（Task 6 实现）

Task 5 范围：累加 + 触发 + 滑窗 + 规则压缩 + get_blocks_for_injection
Task 6 范围：persist() + _load_existing_blocks_with_recovery() + _recover_block() + LLM 压缩
"""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Optional, Any, Callable

import logging

from .memory_config import MemoryConfig
from .chapter_summary_block import ChapterSummaryBlock

logger = logging.getLogger("novels_project.memory.summary_compressor")


class SummaryCompressor:
    """100 章滚动压缩器。"""

    def __init__(
        self,
        config: MemoryConfig,
        storage_dir: Path,
        llm_client: Optional[Any] = None,
        error_callback: Optional[Callable] = None,
        chapters_dir: Optional[Path] = None,
    ):
        self.config = config
        self.storage_dir = Path(storage_dir)
        self.llm_client = llm_client
        self.error_callback = error_callback
        self.chapters_dir = Path(chapters_dir) if chapters_dir else None

        # 状态
        self._blocks: list[ChapterSummaryBlock] = []
        self._accumulator: list[tuple[int, str]] = []
        self._dirty = False

        self.storage_dir.mkdir(parents=True, exist_ok=True)
        # Task 6: _load_existing_blocks_with_recovery()
        logger.info(
            "[SummaryCompressor] 初始化完成 | storage=%s window=%d max_blocks=%d",
            self.storage_dir, self.config.chapter_window, self.config.max_summary_blocks,
        )

    def add_chapter_summary(
        self,
        chapter_id: int,
        summary: str,
    ) -> Optional[ChapterSummaryBlock]:
        """累加单章摘要，达到窗口时触发压缩。"""
        self._accumulator.append((chapter_id, summary))
        logger.info(
            "[SummaryCompressor] 累加摘要 | chapter=%d accumulator=%d/%d",
            chapter_id, len(self._accumulator), self.config.chapter_window,
        )
        if len(self._accumulator) >= self.config.chapter_window:
            return self._trigger_compression()
        return None

    def _trigger_compression(self) -> ChapterSummaryBlock:
        """触发压缩：accumulator → 1 个 ChapterSummaryBlock。"""
        chapters = self._accumulator
        start = chapters[0][0]
        end = chapters[-1][0]
        logger.info(
            "[SummaryCompressor] 触发压缩 | chapter_range=%d-%d count=%d",
            start, end, len(chapters),
        )

        # 1. 拼接
        combined = "\n\n".join(
            f"【第{ch_id}章】\n{summary}"
            for ch_id, summary in chapters
        )

        # 2. 压缩（Task 5: 规则压缩；Task 6 替换为 LLM 压缩 + 重试）
        compressed = self._rule_compress(combined)

        # 3. 截断
        compressed = self._truncate(compressed, self.config.summary_max_chars)

        # 4. 提取元数据
        key_events, char_changes = self._extract_metadata(compressed)

        # 5. 创建块
        block = ChapterSummaryBlock(
            block_id=f"block_{start:05d}_{end:05d}",
            start_chapter=start,
            end_chapter=end,
            chapter_count=len(chapters),
            compressed_text=compressed,
            key_events=key_events,
            character_changes=char_changes,
            created_at=datetime.now().isoformat(),
            char_count=len(compressed),
        )

        # 6. 添加到块列表 + 滑窗淘汰
        self._blocks.append(block)
        self._evict_old_blocks()

        # 7. 清空 accumulator
        self._accumulator.clear()
        self._dirty = True

        # Task 6: self.persist()

        logger.info(
            "[SummaryCompressor] 压缩完成 | block_id=%s char_count=%d total_blocks=%d",
            block.block_id, block.char_count, len(self._blocks),
        )
        return block

    def _evict_old_blocks(self) -> None:
        """滑窗淘汰：保留最近 max_summary_blocks 个块。"""
        while len(self._blocks) > self.config.max_summary_blocks:
            evicted = self._blocks.pop(0)
            logger.info(
                "[SummaryCompressor] 淘汰旧块 | block_id=%s chapters=%d-%d",
                evicted.block_id, evicted.start_chapter, evicted.end_chapter,
            )

    def _truncate(self, text: str, max_len: int) -> str:
        """截断到 max_len 字符以内。"""
        if len(text) <= max_len:
            return text
        return text[: max_len - 20] + "\n\n[内容已截断]"

    def _rule_compress(self, text: str) -> str:
        """规则压缩：取首尾各 1/3，输出总长不超过 summary_max_chars。

        用于 LLM 不可用时的降级方案，或 Task 6 块恢复时的快速重建。
        """
        n = len(text)
        max_chars = self.config.summary_max_chars
        if n <= max_chars:
            return text
        # 预算：首 + "[中间章节省略]" (7 字符) + 末 ≤ max_chars
        marker = "\n\n[中间章节省略]\n\n"
        each_side = (max_chars - len(marker)) // 2
        if each_side < 1:
            # 极端情况：max_chars 极小，只截前 max_chars
            return text[:max_chars]
        return text[:each_side] + marker + text[-each_side:]

    def _extract_metadata(self, text: str) -> tuple[list[str], list[str]]:
        """从压缩文本提取关键事件和人物变化（规则方法）。"""
        events: list[str] = []
        changes: list[str] = []
        keywords_events = ["击败", "杀死", "获得", "突破", "发现"]
        keywords_changes = ["加入", "离开", "背叛", "受伤", "死亡"]
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            if any(kw in line for kw in keywords_events):
                events.append(line[:100])
            if any(kw in line for kw in keywords_changes):
                changes.append(line[:100])
        return events[:20], changes[:20]

    def get_blocks_for_injection(self) -> str:
        """生成用于注入 prompt 的文本（所有块的拼接）。"""
        if not self._blocks:
            return ""
        parts = ["【历史剧情摘要（滑窗保留）】"]
        for block in self._blocks:
            parts.append(
                f"\n### {block.block_id} (第 {block.start_chapter}-{block.end_chapter} 章)\n"
                f"{block.compressed_text}"
            )
        return "\n".join(parts)

    def get_status(self) -> dict:
        """状态报告（用于监控和 web 端展示）。"""
        return {
            "total_blocks": len(self._blocks),
            "accumulator_size": len(self._accumulator),
            "accumulator_chapters": [ch for ch, _ in self._accumulator],
            "blocks": [
                {
                    "block_id": b.block_id,
                    "start": b.start_chapter,
                    "end": b.end_chapter,
                    "char_count": b.char_count,
                }
                for b in self._blocks
            ],
            "is_dirty": self._dirty,
        }
