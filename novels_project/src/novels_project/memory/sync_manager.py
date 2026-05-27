"""
数据同步管理器

确保人物卡 YAML、章节内容等数据与图数据库保持同步。

同步策略：
1. 人物卡变更时，对应的实体节点和关系自动更新
2. 新章节生成后，自动提取实体和关系
3. 支持增量同步和全量重建
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, Optional
from datetime import datetime
from enum import Enum

import yaml

from .graph_store import GraphStore
from .entity_extractor import EntityExtractor

# 模块级 Logger
logger = logging.getLogger("novels_project.memory.sync_manager")


class SyncMode(str, Enum):
    """同步模式。"""
    INCREMENTAL = "incremental"
    FULL = "full"


class SyncStatus(str, Enum):
    """同步状态。"""
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"    # 部分成功（有错误但未完全失败）
    FAILED = "failed"


class AutoSyncConfig:
    """
    自动同步配置。

    Attributes:
        enabled: 是否启用自动同步
        interval_seconds: 定时同步间隔（秒），默认 300（5 分钟）
        event_triggered: 是否启用事件触发同步（新章节生成后自动同步）
        threshold_chapters: 阈值触发：新增章节数达到此值后触发同步，默认 1
        max_retries: 失败重试次数，默认 3
        retry_delay_seconds: 重试间隔（秒），默认 10
        persist_on_sync: 同步后是否自动持久化图谱
    """

    def __init__(
        self,
        enabled: bool = True,
        interval_seconds: int = 300,
        event_triggered: bool = True,
        threshold_chapters: int = 1,
        max_retries: int = 3,
        retry_delay_seconds: int = 10,
        persist_on_sync: bool = True,
    ):
        self.enabled = enabled
        self.interval_seconds = interval_seconds
        self.event_triggered = event_triggered
        self.threshold_chapters = threshold_chapters
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds
        self.persist_on_sync = persist_on_sync


class SyncManager:
    """
    数据同步管理器。

    用法:
        manager = SyncManager(graph_store, extractor)
        manager.set_watch_paths(
            character_cards="config/character_base_cards.yaml",
            chapters_dir="output/chapters/",
        )
        result = manager.sync()

        # 自动同步
        config = AutoSyncConfig(enabled=True, interval_seconds=300)
        manager.configure_auto_sync(config)
        manager.enable_auto_sync()
    """

    def __init__(
        self,
        graph_store: GraphStore,
        entity_extractor: Optional[EntityExtractor] = None,
    ):
        self._graph = graph_store
        self._extractor = entity_extractor or EntityExtractor(graph_store)

        # 监控路径
        self._character_cards_path: Optional[Path] = None
        self._chapters_dir: Optional[Path] = None

        # 变更追踪
        self._file_hashes: dict[str, str] = {}
        self._sync_state_path: Optional[Path] = None

        # 同步状态
        self._status: SyncStatus = SyncStatus.IDLE
        self._last_sync_time: Optional[datetime] = None
        self._sync_count: int = 0
        self._retry_count: int = 0
        self._consecutive_failures: int = 0

        # 自动同步
        self._auto_sync_config: Optional[AutoSyncConfig] = None
        self._auto_sync_enabled: bool = False
        self._last_auto_sync_time: Optional[datetime] = None
        self._pending_chapter_ids: set[int] = set()
        self._graph_save_path: Optional[Path] = None

        logger.info(
            "[SyncManager] 初始化完成 | nodes=%d edges=%d",
            graph_store.entity_count(), graph_store.relation_count(),
        )

    # ============================================================
    # 配置
    # ============================================================

    def set_watch_paths(
        self,
        character_cards: str | Path,
        chapters_dir: str | Path,
        sync_state_dir: Optional[str | Path] = None,
        graph_save_path: Optional[str | Path] = None,
    ):
        """
        设置监控路径。

        Args:
            character_cards: 人物卡 YAML 文件路径
            chapters_dir: 章节输出目录
            sync_state_dir: 同步状态文件存放目录
            graph_save_path: 图谱持久化文件路径
        """
        self._character_cards_path = Path(character_cards)
        self._chapters_dir = Path(chapters_dir)

        if sync_state_dir:
            self._sync_state_path = Path(sync_state_dir) / ".graph_sync_state.json"

        if graph_save_path:
            self._graph_save_path = Path(graph_save_path)

        logger.info(
            "[SyncManager] 监控路径已配置 | cards=%s chapters=%s state_dir=%s graph=%s",
            Path(character_cards).name, Path(chapters_dir).name,
            sync_state_dir or "(default)", graph_save_path or "(not set)",
        )

    def configure_auto_sync(self, config: AutoSyncConfig):
        """配置自动同步参数。"""
        self._auto_sync_config = config
        logger.info(
            "[SyncManager] 自动同步配置 | enabled=%s interval=%ds event=%s threshold=%d "
            "retries=%d retry_delay=%ds persist=%s",
            config.enabled, config.interval_seconds, config.event_triggered,
            config.threshold_chapters, config.max_retries,
            config.retry_delay_seconds, config.persist_on_sync,
        )

    def enable_auto_sync(self):
        """启用自动同步（事件触发模式）。"""
        if not self._auto_sync_config:
            logger.warning("[SyncManager] 未配置自动同步，使用默认配置")
            self._auto_sync_config = AutoSyncConfig()

        self._auto_sync_enabled = True
        logger.info("[SyncManager] 自动同步已启用")

    def disable_auto_sync(self):
        """禁用自动同步。"""
        self._auto_sync_enabled = False
        logger.info("[SyncManager] 自动同步已禁用")

    # ============================================================
    # 同步操作
    # ============================================================

    def sync(
        self,
        mode: str = SyncMode.INCREMENTAL,
        force: bool = False,
        llm_client: Any = None,
    ) -> dict[str, Any]:
        """
        执行数据同步。

        Args:
            mode: "incremental"（增量） 或 "full"（全量重建）
            force: 是否强制同步（忽略 hash 检查）
            llm_client: LLM 客户端（用于从文本提取实体）

        Returns:
            同步结果统计
        """
        start_time = time.time()

        logger.info(
            "[SyncManager] 同步开始 | mode=%s force=%s",
            mode, force,
        )

        try:
            self._status = SyncStatus.RUNNING

            if mode == SyncMode.FULL:
                result = self._full_sync(llm_client)
            else:
                result = self._incremental_sync(force, llm_client)

            elapsed = round(time.time() - start_time, 2)

            # 更新状态
            self._last_sync_time = datetime.now()
            self._sync_count += 1
            has_errors = len(result.get("errors", [])) > 0

            if has_errors:
                self._status = SyncStatus.PARTIAL
                self._consecutive_failures += 1
                logger.warning(
                    "[SyncManager] 同步部分完成（有错误）| mode=%s elapsed=%.2fs "
                    "errors=%d result=%s",
                    mode, elapsed, len(result["errors"]),
                    {k: v for k, v in result.items() if k != "errors"},
                )
            else:
                self._status = SyncStatus.SUCCESS
                self._consecutive_failures = 0
                logger.info(
                    "[SyncManager] 同步完成 | mode=%s elapsed=%.2fs %s",
                    mode, elapsed,
                    {k: v for k, v in result.items() if k != "errors"},
                )

            # 持久化图谱
            if self._auto_sync_config and self._auto_sync_config.persist_on_sync:
                self._persist_graph()

            return result

        except Exception as e:
            elapsed = round(time.time() - start_time, 2)
            self._status = SyncStatus.FAILED
            self._consecutive_failures += 1

            logger.error(
                "[SyncManager] 同步失败 | mode=%s elapsed=%.2fs error=%s",
                mode, elapsed, e,
            )

            return {
                "mode": mode,
                "status": SyncStatus.FAILED,
                "timestamp": datetime.now().isoformat(),
                "elapsed": elapsed,
                "error": str(e),
            }

    def sync_with_retry(
        self,
        mode: str = SyncMode.INCREMENTAL,
        force: bool = False,
        llm_client: Any = None,
        max_retries: Optional[int] = None,
        retry_delay: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        带重试机制的同步。

        Args:
            mode: 同步模式
            force: 是否强制同步
            llm_client: LLM 客户端
            max_retries: 最大重试次数（默认使用 AutoSyncConfig 配置）
            retry_delay: 重试间隔秒数

        Returns:
            同步结果
        """
        config = self._auto_sync_config or AutoSyncConfig()
        max_retries = max_retries if max_retries is not None else config.max_retries
        retry_delay = retry_delay if retry_delay is not None else config.retry_delay_seconds

        for attempt in range(max_retries + 1):
            if attempt > 0:
                logger.info(
                    "[SyncManager] 重试 #%d/%d | 等待 %ds",
                    attempt, max_retries, retry_delay,
                )
                time.sleep(retry_delay)

            result = self.sync(mode=mode, force=force, llm_client=llm_client)

            if result.get("status") != SyncStatus.FAILED and "error" not in result:
                return result

            logger.warning(
                "[SyncManager] 同步尝试 #%d 失败 | error=%s",
                attempt + 1, result.get("error", "unknown"),
            )

        logger.error(
            "[SyncManager] 所有重试均已失败 | attempts=%d",
            max_retries + 1,
        )
        return result

    def _full_sync(self, llm_client: Any = None) -> dict[str, Any]:
        """全量重建知识图谱。"""
        logger.info("[SyncManager] 全量同步：清空图谱并重建")

        # 清空现有图（保留同一个 GraphStore 实例，避免外部引用丢失）
        old_nodes = self._graph.entity_count()
        old_edges = self._graph.relation_count()
        self._graph._graph.clear()
        # extractor 始终使用同一个 graph 实例，无需重建

        logger.debug(
            "[SyncManager] 旧图谱已清空 | old_nodes=%d old_edges=%d",
            old_nodes, old_edges,
        )

        stats = {
            "mode": SyncMode.FULL,
            "timestamp": datetime.now().isoformat(),
            "characters_added": 0,
            "chapters_processed": 0,
            "entities_added": 0,
            "relations_added": 0,
            "errors": [],
            "old_nodes": old_nodes,
            "old_edges": old_edges,
        }

        # 构建同步状态（含文件哈希，供后续增量同步使用）
        sync_state = {"last_sync": datetime.now().isoformat()}

        # 1. 同步人物卡
        if self._character_cards_path and self._character_cards_path.exists():
            try:
                logger.info(
                    "[SyncManager] 全量同步：处理人物卡 | path=%s",
                    self._character_cards_path.name,
                )
                result = self._extractor.extract_from_character_cards(
                    str(self._character_cards_path),
                    llm_client=llm_client,
                )
                stats["characters_added"] = result
                # 保存人物卡哈希
                sync_state["character_cards_hash"] = self._compute_file_hash(
                    str(self._character_cards_path)
                )
                logger.info(
                    "[SyncManager] 全量同步：人物卡完成 | added=%d",
                    result,
                )
            except Exception as e:
                logger.error("[SyncManager] 人物卡同步失败 | error=%s", e)
                stats["errors"].append(f"人物卡同步失败: {e}")

        # 2. 同步章节
        chapter_hashes = {}
        if self._chapters_dir and self._chapters_dir.exists():
            chapter_files = sorted(self._chapters_dir.glob("chapter_*_final.md"))
            logger.info(
                "[SyncManager] 全量同步：处理章节 | count=%d",
                len(chapter_files),
            )

            for chapter_file in chapter_files:
                try:
                    chapter_id = self._extract_chapter_id(chapter_file.name)
                    with open(chapter_file, "r", encoding="utf-8") as f:
                        text = f.read()

                    logger.debug(
                        "[SyncManager] 全量同步：章节 %d | file=%s size=%d",
                        chapter_id, chapter_file.name, len(text),
                    )

                    result = self._extractor.extract_from_chapter_text(
                        text, chapter_id, llm_client,
                    )
                    stats["chapters_processed"] += 1
                    stats["entities_added"] += result["added_entities"]
                    stats["relations_added"] += result["added_relations"]
                    # 保存章节哈希
                    chapter_hashes[chapter_file.name] = self._compute_file_hash(
                        str(chapter_file)
                    )
                except Exception as e:
                    logger.error(
                        "[SyncManager] 章节 %s 同步失败 | error=%s",
                        chapter_file.name, e,
                    )
                    stats["errors"].append(f"章节 {chapter_file.name} 同步失败: {e}")

        sync_state["chapter_hashes"] = chapter_hashes

        # 保存同步状态（含哈希，确保后续增量同步准确）
        self._save_sync_state(sync_state)

        logger.info(
            "[SyncManager] 全量同步完成 | new_nodes=%d new_edges=%d",
            self._graph.entity_count(), self._graph.relation_count(),
        )

        return stats

    def _incremental_sync(self, force: bool = False, llm_client: Any = None) -> dict[str, Any]:
        """增量同步（仅更新已变更的文件）。"""
        logger.info("[SyncManager] 增量同步开始 | force=%s", force)

        stats = {
            "mode": SyncMode.INCREMENTAL,
            "timestamp": datetime.now().isoformat(),
            "characters_updated": 0,
            "chapters_processed": 0,
            "entities_added": 0,
            "relations_added": 0,
            "skipped": 0,
            "errors": [],
        }

        # 加载上次同步状态
        prev_state = self._load_sync_state()
        logger.debug(
            "[SyncManager] 上次同步状态 | last_sync=%s",
            prev_state.get("last_sync", "never"),
        )

        # 1. 检查人物卡变更
        if self._character_cards_path and self._character_cards_path.exists():
            file_hash = self._compute_file_hash(str(self._character_cards_path))
            prev_hash = prev_state.get("character_cards_hash", "")

            if force or file_hash != prev_hash:
                logger.info(
                    "[SyncManager] 检测到人物卡变更 | prev_hash=%s new_hash=%s",
                    prev_hash[:8] + "..." if prev_hash else "(none)",
                    file_hash[:8] + "...",
                )
                try:
                    result = self._extractor.extract_from_character_cards(
                        str(self._character_cards_path),
                        llm_client=llm_client,
                    )
                    stats["characters_updated"] = result
                    prev_state["character_cards_hash"] = file_hash
                    logger.info("[SyncManager] 人物卡更新完成 | added=%d", result)
                except Exception as e:
                    logger.error("[SyncManager] 人物卡同步失败 | error=%s", e)
                    stats["errors"].append(f"人物卡同步失败: {e}")
            else:
                stats["skipped"] += 1
                logger.debug("[SyncManager] 人物卡无变化，跳过")

        # 2. 检查新章节
        if self._chapters_dir and self._chapters_dir.exists():
            prev_chapter_hashes = prev_state.get("chapter_hashes", {})

            chapter_files = sorted(self._chapters_dir.glob("chapter_*_final.md"))
            logger.debug(
                "[SyncManager] 检查章节 | total=%d known=%d",
                len(chapter_files), len(prev_chapter_hashes),
            )

            for chapter_file in chapter_files:
                file_hash = self._compute_file_hash(str(chapter_file))
                prev_hash = prev_chapter_hashes.get(chapter_file.name, "")

                if force or file_hash != prev_hash:
                    logger.info(
                        "[SyncManager] 检测到章节变更 | file=%s",
                        chapter_file.name,
                    )
                    try:
                        chapter_id = self._extract_chapter_id(chapter_file.name)
                        with open(chapter_file, "r", encoding="utf-8") as f:
                            text = f.read()
                        result = self._extractor.extract_from_chapter_text(
                            text, chapter_id, llm_client,
                        )
                        stats["chapters_processed"] += 1
                        stats["entities_added"] += result["added_entities"]
                        stats["relations_added"] += result["added_relations"]
                        prev_chapter_hashes[chapter_file.name] = file_hash

                        logger.info(
                            "[SyncManager] 章节同步完成 | chapter=%d entities=%d relations=%d",
                            chapter_id, result["added_entities"], result["added_relations"],
                        )
                    except Exception as e:
                        logger.error(
                            "[SyncManager] 章节 %s 同步失败 | error=%s",
                            chapter_file.name, e,
                        )
                        stats["errors"].append(f"章节 {chapter_file.name} 同步失败: {e}")
                else:
                    stats["skipped"] += 1

            prev_state["chapter_hashes"] = prev_chapter_hashes

        # 保存状态
        self._save_sync_state(prev_state)

        logger.info(
            "[SyncManager] 增量同步完成 | processed=%d skipped=%d entities=%d relations=%d errors=%d",
            stats["chapters_processed"], stats["skipped"],
            stats["entities_added"], stats["relations_added"],
            len(stats["errors"]),
        )

        return stats

    # ============================================================
    # 单文件同步
    # ============================================================

    def sync_character_cards(self, llm_client: Any = None) -> dict[str, Any]:
        """同步人物卡变更到图谱。"""
        if not self._character_cards_path or not self._character_cards_path.exists():
            logger.error("[SyncManager] 人物卡路径未设置或文件不存在")
            return {"error": "人物卡路径未设置或文件不存在", "status": SyncStatus.FAILED}

        logger.info("[SyncManager] 人物卡即时同步开始")
        start = time.time()
        result = self._extractor.extract_from_character_cards(
            str(self._character_cards_path),
            llm_client=llm_client,
        )
        elapsed = round(time.time() - start, 2)

        logger.info(
            "[SyncManager] 人物卡即时同步完成 | synced=%d elapsed=%.2fs",
            result, elapsed,
        )
        return {"synced_characters": result, "status": SyncStatus.SUCCESS, "elapsed": elapsed}

    def sync_chapter(
        self,
        chapter_id: int,
        chapter_text: str,
        llm_client: Any = None,
    ) -> dict[str, Any]:
        """
        同步单个章节到图谱。

        Args:
            chapter_id: 章节 ID
            chapter_text: 章节文本
            llm_client: LLM 客户端
        """
        logger.info(
            "[SyncManager] 章节即时同步 | chapter=%d text_len=%d",
            chapter_id, len(chapter_text),
        )

        start = time.time()
        result = self._extractor.extract_from_chapter_text(chapter_text, chapter_id, llm_client)
        elapsed = round(time.time() - start, 2)

        sync_result = {
            "chapter_id": chapter_id,
            "entities_added": result["added_entities"],
            "relations_added": result["added_relations"],
            "status": SyncStatus.SUCCESS,
            "elapsed": elapsed,
        }

        logger.info(
            "[SyncManager] 章节即时同步完成 | chapter=%d entities=%d relations=%d elapsed=%.2fs",
            chapter_id, result["added_entities"], result["added_relations"], elapsed,
        )

        # 自动持久化
        if self._auto_sync_config and self._auto_sync_config.persist_on_sync:
            self._persist_graph()

        return sync_result

    def on_character_card_updated(self, character_name: str, field: str, value: Any):
        """
        人物卡字段更新时的回调。

        Args:
            character_name: 人物名
            field: 更新的字段
            value: 新值
        """
        logger.info(
            "[SyncManager] 人物卡字段更新 | character=%s field=%s",
            character_name, field,
        )

        if self._graph.has_entity(character_name):
            entity = self._graph.get_entity(character_name)
            if field == "core_personality":
                brief_parts = [entity.get("brief", "")]
                new_brief = " | ".join(filter(None, brief_parts + [", ".join(value)]))
                self._graph.update_entity(character_name, {"brief": new_brief})
                logger.debug(
                    "[SyncManager] 人物性格更新 | character=%s brief_len=%d",
                    character_name, len(new_brief),
                )
            else:
                self._graph.update_entity(character_name, {field: value})
                logger.debug(
                    "[SyncManager] 人物字段更新 | character=%s field=%s value=%s",
                    character_name, field, str(value)[:100],
                )
        else:
            logger.warning(
                "[SyncManager] 人物不在图谱中 | character=%s",
                character_name,
            )

    def on_chapter_generated(self, chapter_id: int, chapter_text: str, llm_client: Any = None):
        """
        新章节生成时的回调。

        当 AutoSyncConfig.event_triggered 为 True 时，会自动触发同步。
        支持阈值模式：累计章节数达到 threshold_chapters 时才执行同步。

        Args:
            chapter_id: 章节 ID
            chapter_text: 章节文本
            llm_client: LLM 客户端
        """
        if not self._auto_sync_enabled:
            logger.debug(
                "[SyncManager] 自动同步未启用，跳过章节 %d 同步",
                chapter_id,
            )
            return

        config = self._auto_sync_config
        if not config or not config.event_triggered:
            logger.debug("[SyncManager] 事件触发未启用")
            return

        self._pending_chapter_ids.add(chapter_id)

        logger.info(
            "[SyncManager] 章节生成事件 | chapter=%d pending_count=%d threshold=%d",
            chapter_id, len(self._pending_chapter_ids), config.threshold_chapters,
        )

        # 检查阈值
        if len(self._pending_chapter_ids) >= config.threshold_chapters:
            logger.info(
                "[SyncManager] 达到同步阈值，触发自动同步 | chapters=%s",
                sorted(self._pending_chapter_ids),
            )
            self.sync_chapter(chapter_id, chapter_text, llm_client)
            self._pending_chapter_ids.clear()
            self._last_auto_sync_time = datetime.now()

    # ============================================================
    # 持久化
    # ============================================================

    def _persist_graph(self):
        """持久化图谱到文件。"""
        if not self._graph_save_path:
            self._graph_save_path = self._get_default_graph_path()

        try:
            self._graph.save(str(self._graph_save_path))
            logger.debug(
                "[SyncManager] 图谱已持久化 | path=%s nodes=%d edges=%d",
                self._graph_save_path.name,
                self._graph.entity_count(),
                self._graph.relation_count(),
            )
        except Exception as e:
            logger.error("[SyncManager] 图谱持久化失败 | path=%s error=%s", self._graph_save_path, e)

    def _get_default_graph_path(self) -> Path:
        """获取默认图谱持久化路径。"""
        if self._sync_state_path:
            return self._sync_state_path.parent / "knowledge_graph.json"
        return Path.cwd() / "graph" / "knowledge_graph.json"

    # ============================================================
    # 状态监控
    # ============================================================

    def get_sync_status(self) -> dict[str, Any]:
        """获取当前同步状态。"""
        return {
            "status": self._status.value,
            "last_sync_time": self._last_sync_time.isoformat() if self._last_sync_time else None,
            "sync_count": self._sync_count,
            "consecutive_failures": self._consecutive_failures,
            "auto_sync_enabled": self._auto_sync_enabled,
            "last_auto_sync_time": (
                self._last_auto_sync_time.isoformat() if self._last_auto_sync_time else None
            ),
            "pending_chapters": sorted(self._pending_chapter_ids),
            "graph_nodes": self._graph.entity_count(),
            "graph_edges": self._graph.relation_count(),
        }

    def get_health_report(self) -> str:
        """生成同步健康报告。"""
        status = self.get_sync_status()
        lines = [
            "=" * 50,
            "  图谱同步健康报告",
            "=" * 50,
            f"  状态: {status['status']}",
            f"  上次同步: {status['last_sync_time'] or '从未'}",
            f"  同步次数: {status['sync_count']}",
            f"  连续失败: {status['consecutive_failures']}",
            f"  自动同步: {'启用' if status['auto_sync_enabled'] else '禁用'}",
            f"  上次自动同步: {status['last_auto_sync_time'] or '从未'}",
            f"  待处理章节: {status['pending_chapters']}",
            f"  图谱节点: {status['graph_nodes']}",
            f"  图谱边: {status['graph_edges']}",
        ]

        if status["consecutive_failures"] > 0:
            lines.append(f"\n  ⚠️ 警告: 连续 {status['consecutive_failures']} 次同步失败!")

        lines.append("=" * 50)
        return "\n".join(lines)

    # ============================================================
    # 工具方法
    # ============================================================

    @staticmethod
    def _compute_file_hash(filepath: str) -> str:
        """计算文件的 SHA256 哈希。"""
        try:
            with open(filepath, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception as e:
            logger.warning("[SyncManager] 文件哈希计算失败 | path=%s error=%s", filepath, e)
            return ""

    @staticmethod
    def _extract_chapter_id(filename: str) -> int:
        """从文件名中提取章节 ID (如 chapter_12_final.md -> 12)。"""
        import re
        match = re.search(r'chapter_(\d+)', filename)
        return int(match.group(1)) if match else 0

    def _get_sync_state_path(self) -> Path:
        """获取同步状态文件路径。"""
        if self._sync_state_path:
            return self._sync_state_path
        return Path.cwd() / ".graph_sync_state.json"

    def _load_sync_state(self) -> dict:
        """加载同步状态。"""
        path = self._get_sync_state_path()
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    state = json.load(f)
                logger.debug(
                    "[SyncManager] 同步状态已加载 | path=%s",
                    path.name,
                )
                return state
            except Exception as e:
                logger.warning("[SyncManager] 同步状态加载失败 | path=%s error=%s", path, e)
        return {}

    def _save_sync_state(self, state: Optional[dict] = None):
        """保存同步状态。"""
        if state is None:
            state = {"last_sync": datetime.now().isoformat()}

        state["last_sync"] = datetime.now().isoformat()

        path = self._get_sync_state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            logger.debug("[SyncManager] 同步状态已保存 | path=%s", path.name)
        except Exception as e:
            logger.error("[SyncManager] 同步状态保存失败 | path=%s error=%s", path, e)