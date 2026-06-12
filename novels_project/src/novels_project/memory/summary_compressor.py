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
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Any, Callable

import logging

from .memory_config import MemoryConfig
from .chapter_summary_block import ChapterSummaryBlock
from .compression_exceptions import BlockRecoveryError

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
        self._load_existing_blocks_with_recovery()
        logger.info(
            "[SummaryCompressor] 初始化完成 | storage=%s window=%d max_blocks=%d "
            "rule_compress_only=%s has_llm_client=%s has_chapters_dir=%s loaded_blocks=%d",
            self.storage_dir, self.config.chapter_window, self.config.max_summary_blocks,
            self.llm_client is None, self.llm_client is not None,
            self.chapters_dir is not None, len(self._blocks),
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
        logger.debug(
            "[SummaryCompressor] 拼接完成 | combined_len=%d chapters=%d",
            len(combined), len(chapters),
        )

        # 2. 压缩（Task 5: 规则压缩；Task 6 替换为 LLM 压缩 + 重试）
        if self.llm_client:
            logger.info(
                "[SummaryCompressor] 使用 LLM 压缩 | combined_len=%d",
                len(combined),
            )
            # Task 6: compressed = self._llm_compress_with_retry(combined)
            compressed = self._rule_compress(combined)  # 临时 fallback
        else:
            logger.info(
                "[SummaryCompressor] LLM 不可用，使用规则压缩 | combined_len=%d",
                len(combined),
            )
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

        # 8. 持久化
        self.persist()

        logger.info(
            "[SummaryCompressor] 压缩完成 | block_id=%s char_count=%d total_blocks=%d",
            block.block_id, block.char_count, len(self._blocks),
        )
        return block

    def _evict_old_blocks(self) -> None:
        """滑窗淘汰：保留最近 max_summary_blocks 个块。"""
        evicted_count = 0
        while len(self._blocks) > self.config.max_summary_blocks:
            evicted = self._blocks.pop(0)
            evicted_count += 1
            logger.info(
                "[SummaryCompressor] 淘汰旧块 | block_id=%s chapters=%d-%d",
                evicted.block_id, evicted.start_chapter, evicted.end_chapter,
            )
        if evicted_count > 0:
            logger.info(
                "[SummaryCompressor] 滑窗淘汰完成 | evicted_count=%d remaining=%d",
                evicted_count, len(self._blocks),
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
            logger.warning(
                "[SummaryCompressor] _rule_compress max_chars 过小 | "
                "max_chars=%d each_side=%d, 退化为纯截断",
                max_chars, each_side,
            )
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
        result = "\n".join(parts)
        logger.info(
            "[SummaryCompressor] 生成注入文本 | blocks=%d total_len=%d",
            len(self._blocks), len(result),
        )
        return result

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

    # ============================================================
    # Task 6: 持久化与恢复
    # ============================================================

    def persist(self) -> None:
        """持久化所有块到磁盘。

        - _dirty=False 时跳过（无操作）
        - 每个块写一个独立 JSON 文件
        - 写 index.json 索引所有 block_id
        """
        if not self._dirty:
            logger.debug(
                "[SummaryCompressor] persist 跳过（无脏数据） | blocks=%d",
                len(self._blocks),
            )
            return

        logger.info(
            "[SummaryCompressor] 开始持久化 | blocks=%d storage=%s",
            len(self._blocks), self.storage_dir,
        )

        # 写每个块
        for block in self._blocks:
            block_path = self.storage_dir / f"{block.block_id}.json"
            with open(block_path, "w", encoding="utf-8") as f:
                json.dump(block.to_dict(), f, ensure_ascii=False, indent=2)

        # 写索引
        index_path = self.storage_dir / "index.json"
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump({
                "blocks": [b.block_id for b in self._blocks],
                "last_update": datetime.now().isoformat(),
            }, f, ensure_ascii=False, indent=2)

        self._dirty = False
        logger.info(
            "[SummaryCompressor] 持久化完成 | blocks=%d index=%s",
            len(self._blocks), index_path,
        )

    def _load_existing_blocks_with_recovery(self) -> None:
        """启动时加载已有块（含损坏恢复）。

        - index.json 不存在 → 不加载（首次启动）
        - index.json 损坏 → 跳过（不阻塞启动）
        - 每个块文件损坏 → 尝试从 chapters_dir 恢复，失败则跳过
        """
        index_path = self.storage_dir / "index.json"
        if not index_path.exists():
            logger.debug(
                "[SummaryCompressor] 无 index.json，跳过加载 | path=%s",
                index_path,
            )
            return

        try:
            with open(index_path, "r", encoding="utf-8") as f:
                index = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(
                "[SummaryCompressor] index.json 损坏，跳过加载 | path=%s error=%s",
                index_path, e,
            )
            return

        for block_id in index.get("blocks", []):
            block_path = self.storage_dir / f"{block_id}.json"
            if not block_path.exists():
                logger.warning(
                    "[SummaryCompressor] 块文件缺失 | block_id=%s path=%s",
                    block_id, block_path,
                )
                continue

            try:
                with open(block_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._blocks.append(ChapterSummaryBlock.from_dict(data))
                logger.debug(
                    "[SummaryCompressor] 块加载成功 | block_id=%s", block_id,
                )
            except (
                json.JSONDecodeError, KeyError, UnicodeDecodeError, TypeError
            ) as e:
                logger.warning(
                    "[SummaryCompressor] 块损坏，尝试恢复 | block_id=%s error=%s",
                    block_id, e,
                )
                recovered = self._try_recover_block(block_path)
                if recovered:
                    self._blocks.append(recovered)
                    # 备份损坏文件
                    backup_path = block_path.with_suffix(".corrupted.json")
                    try:
                        shutil.move(str(block_path), str(backup_path))
                        logger.info(
                            "[SummaryCompressor] 块已恢复并备份损坏文件 | "
                            "block_id=%s backup=%s",
                            recovered.block_id, backup_path.name,
                        )
                    except OSError as move_err:
                        logger.error(
                            "[SummaryCompressor] 备份损坏文件失败 | "
                            "block_id=%s error=%s",
                            block_id, move_err,
                        )

        logger.info(
            "[SummaryCompressor] 启动加载完成 | loaded=%d",
            len(self._blocks),
        )

    def _try_recover_block(
        self, block_path: Path,
    ) -> Optional[ChapterSummaryBlock]:
        """尝试从原始章节文件重新生成块。

        返回 None 表示恢复失败（块会被跳过）。
        不抛异常（避免阻塞启动）。
        """
        try:
            return self._recover_block(block_path)
        except BlockRecoveryError as e:
            logger.error(
                "[SummaryCompressor] 块恢复失败，跳过 | path=%s error=%s",
                block_path.name, e,
            )
            return None
        except Exception as e:
            logger.error(
                "[SummaryCompressor] 块恢复异常，跳过 | path=%s error=%s",
                block_path.name, e,
            )
            return None

    def _recover_block(
        self, block_path: Path,
    ) -> ChapterSummaryBlock:
        """从原始章节文件重新生成块。

        项目约定：章节文件为 `chapter_{id}_final.md`（非 5 位补零）。
        """
        match = re.match(r"block_(\d+)_(\d+)\.json", block_path.name)
        if not match:
            raise BlockRecoveryError(
                f"无法解析块 ID: {block_path.name}",
                block_path=str(block_path),
            )
        start, end = int(match.group(1)), int(match.group(2))

        if not self.chapters_dir or not self.chapters_dir.exists():
            raise BlockRecoveryError(
                f"chapters_dir 未配置或不存在: {self.chapters_dir}",
                block_path=str(block_path),
            )

        # 从章节文件提取（项目约定：chapter_{id}_final.md）
        summaries: list[tuple[int, str]] = []
        for ch_id in range(start, end + 1):
            chapter_file = self.chapters_dir / f"chapter_{ch_id}_final.md"
            if chapter_file.exists():
                text = chapter_file.read_text(encoding="utf-8")
                summary = self._extract_chapter_summary(text)
                summaries.append((ch_id, summary))
                logger.debug(
                    "[SummaryCompressor] 块恢复读取章节 | ch_id=%d len=%d",
                    ch_id, len(summary),
                )

        if not summaries:
            raise BlockRecoveryError(
                f"未找到任何章节文件（chapter_{start}_final.md ~ chapter_{end}_final.md）",
                block_path=str(block_path),
            )

        # 重新压缩（恢复时使用规则压缩，避免再次依赖 LLM）
        combined = "\n\n".join(
            f"【第{ch}章】\n{s}" for ch, s in summaries
        )
        compressed = self._rule_compress(combined)
        compressed = self._truncate(compressed, self.config.summary_max_chars)

        logger.info(
            "[SummaryCompressor] 块从章节文件恢复 | block_id=%s range=%d-%d "
            "chapters_found=%d/%d compressed_len=%d",
            block_path.stem, start, end, len(summaries), end - start + 1,
            len(compressed),
        )

        return ChapterSummaryBlock(
            block_id=block_path.stem,
            start_chapter=start,
            end_chapter=end,
            chapter_count=len(summaries),
            compressed_text=compressed,
            key_events=[],
            character_changes=[],
            created_at=datetime.now().isoformat() + " (recovered)",
            char_count=len(compressed),
        )

    def _extract_chapter_summary(self, chapter_text: str) -> str:
        """从章节文本中提取简单摘要（首段 + 末段）。

        用于块恢复时的快速摘要重建（不调用 LLM）。
        """
        if not chapter_text:
            return ""
        paragraphs = [
            p.strip() for p in chapter_text.split("\n\n") if p.strip()
        ]
        if not paragraphs:
            return ""
        if len(paragraphs) <= 2:
            return "\n\n".join(paragraphs)
        return paragraphs[0] + "\n\n" + paragraphs[-1]
