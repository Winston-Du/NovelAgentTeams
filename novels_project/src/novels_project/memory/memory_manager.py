"""记忆系统顶层门面（Task 9）。

职责：
- 加载 MemoryConfigBundle（global + 各 agent 配置）
- 提供按 agent 的配置查询接口
- 缓存 SummaryCompressor（每个 agent 一个实例）
- 提供 DialogueCompactor 工厂（不缓存）
- 提供章节生成回调与摘要注入接口
- 支持配置热重载（清缓存 + 重新加载 YAML）

Logger 埋点（11 处）：
1.  __init__ 入口 - 项目根/config 路径/llm_client/integrator
2.  YAML 加载完成 - global/agent 数/耗时
3.  global config validate - 错误数/错误列表
4.  agent 路由初始化 - known/unknown agent 分布
5.  缓存初始化 - 缓存字典清空
6.  get_memory_config - 命中 global/agent 覆盖
7.  get_summary_compressor - 命中缓存 / 创建新实例
8.  create_dialogue_compactor - 每次 new（不缓存）
9.  on_chapter_generated - 章节回调入口
10. get_summary_for_injection - 注入数据来源
11. reload_config - 缓存清空 + 重新加载
"""
from __future__ import annotations
import logging
import time
from pathlib import Path
from typing import Optional, Any

from .memory_config import MemoryConfig
from .memory_config_bundle import MemoryConfigBundle
from .summary_compressor import SummaryCompressor, ChapterSummaryBlock
from .dialogue_compactor import DialogueCompactor

logger = logging.getLogger("novels_project.memory.memory_manager")


class MemoryManager:
    """记忆系统顶层门面。

    用法：
        mgr = MemoryManager(
            project_root=Path("."),
            config_path=Path("config/memory_config.yaml"),
            llm_client=client,
        )
        # 配置查询
        cfg = mgr.get_memory_config("plot_writer")

        # 章节摘要压缩（带缓存）
        compressor = mgr.get_summary_compressor("main")
        compressor.add_chapter_summary(chapter_id=1, summary="...")

        # 对话压缩（每次新建）
        compactor = mgr.create_dialogue_compactor("main")
        if compactor.should_compress(session, max_tokens=100000):
            result = compactor.compact(session, max_tokens=100000)

        # 热重载
        mgr.reload_config()
    """

    def __init__(
        self,
        project_root: Path,
        config_path: Optional[Path] = None,
        llm_client: Optional[Any] = None,
        graph_integrator: Optional[Any] = None,  # GraphMemoryIntegrator（可选）
        chapters_dir: Optional[Path] = None,
    ):
        # === [1] 入口日志：项目根 / config 路径 / 依赖 ===
        logger.info(
            "[MemoryManager] __init__ 入口 | project_root=%s config_path=%s "
            "has_llm_client=%s has_graph_integrator=%s has_chapters_dir=%s",
            project_root,
            config_path or (Path(project_root) / "config" / "memory_config.yaml"),
            llm_client is not None,
            graph_integrator is not None,
            chapters_dir is not None,
        )

        self.project_root = Path(project_root)
        self.config_path = (
            Path(config_path)
            if config_path
            else self.project_root / "config" / "memory_config.yaml"
        )
        self.llm_client = llm_client
        self.graph_integrator = graph_integrator
        self.chapters_dir = Path(chapters_dir) if chapters_dir else None

        # === [5] 缓存初始化 ===
        self._summary_compressors: dict[str, SummaryCompressor] = {}
        logger.info(
            "[MemoryManager] 缓存初始化完成 | cache_size=%d",
            len(self._summary_compressors),
        )

        # === [2] 加载 YAML 配置 ===
        self._load_config()

    def _load_config(self) -> None:
        """加载/重载 YAML 配置（含耗时统计与校验）。"""
        load_start = time.time()
        self.config_bundle = MemoryConfigBundle.load_from_yaml(self.config_path)
        load_elapsed = round(time.time() - load_start, 3)

        # === [2] YAML 加载完成日志 ===
        agent_ids = list(self.config_bundle.agent_configs.keys())
        logger.info(
            "[MemoryManager] YAML 加载完成 | config_path=%s elapsed=%.3fs "
            "global_loaded=%s agent_count=%d",
            self.config_path, load_elapsed,
            self.config_bundle.global_config is not None,
            len(agent_ids),
        )

        # === [3] global config 校验日志 ===
        if self.config_bundle.global_config:
            errors = self.config_bundle.global_config.validate()
            if errors:
                logger.warning(
                    "[MemoryManager] global 配置校验失败 | error_count=%d errors=%s",
                    len(errors), errors,
                )
            else:
                logger.info(
                    "[MemoryManager] global 配置校验通过 | threshold=%.2f max_blocks=%d",
                    self.config_bundle.global_config.dialogue_compression_threshold,
                    self.config_bundle.global_config.max_summary_blocks,
                )

        # === [4] agent 路由初始化日志 ===
        for agent_id, agent_cfg in self.config_bundle.agent_configs.items():
            if agent_cfg and agent_cfg.validate():
                logger.warning(
                    "[MemoryManager] agent[%s] 配置校验失败 | errors=%s",
                    agent_id, agent_cfg.validate(),
                )
        logger.info(
            "[MemoryManager] agent 路由初始化完成 | known_agents=%s",
            agent_ids,
        )

    def get_memory_config(self, agent_id: str) -> MemoryConfig:
        """获取 agent 的最终合并配置（agent 覆盖 + global fallback）。"""
        resolved = self.config_bundle.get_resolved(agent_id)
        # === [6] 路由分发日志 ===
        has_agent_override = agent_id in self.config_bundle.agent_configs
        logger.info(
            "[MemoryManager] get_memory_config 路由 | agent_id=%s "
            "has_agent_override=%s threshold=%.2f max_blocks=%d",
            agent_id, has_agent_override,
            resolved.dialogue_compression_threshold,
            resolved.max_summary_blocks,
        )
        return resolved

    def get_summary_compressor(self, agent_id: str) -> SummaryCompressor:
        """获取/创建 agent 的 SummaryCompressor（带缓存）。"""
        if agent_id not in self._summary_compressors:
            # === [7] 缓存未命中：创建新实例 ===
            cfg = self.get_memory_config(agent_id)
            storage_dir = self.project_root / "memory" / "summary_blocks" / agent_id
            logger.info(
                "[MemoryManager] SummaryCompressor 缓存未命中，创建实例 | "
                "agent_id=%s storage_dir=%s",
                agent_id, storage_dir,
            )
            self._summary_compressors[agent_id] = SummaryCompressor(
                config=cfg,
                storage_dir=storage_dir,
                llm_client=self.llm_client,
                chapters_dir=self.chapters_dir,
            )
        else:
            # === [7] 缓存命中 ===
            logger.info(
                "[MemoryManager] SummaryCompressor 缓存命中 | agent_id=%s "
                "cache_size=%d",
                agent_id, len(self._summary_compressors),
            )
        return self._summary_compressors[agent_id]

    def create_dialogue_compactor(self, agent_id: str) -> DialogueCompactor:
        """为 agent 创建 DialogueCompactor（不缓存，每次新建）。"""
        cfg = self.get_memory_config(agent_id)
        # === [8] DialogueCompactor 工厂日志 ===
        logger.info(
            "[MemoryManager] create_dialogue_compactor | agent_id=%s "
            "preserve_recent=%d max_retries=%d has_llm_client=%s",
            agent_id, cfg.preserve_recent_messages,
            cfg.dialogue_compression_max_retries,
            self.llm_client is not None,
        )
        return DialogueCompactor(config=cfg, llm_client=self.llm_client)

    def on_chapter_generated(
        self,
        agent_id: str,
        chapter_id: int,
        chapter_text: str,
    ) -> Optional[ChapterSummaryBlock]:
        """章节生成回调：提取摘要并累加到 SummaryCompressor。

        返回：
        - 若触发压缩：返回新生成的 ChapterSummaryBlock
        - 若未触发：返回 None
        """
        # === [9] 章节生成回调入口日志 ===
        logger.info(
            "[MemoryManager] on_chapter_generated 回调 | agent_id=%s chapter=%d "
            "chapter_text_len=%d",
            agent_id, chapter_id, len(chapter_text),
        )

        # 提取章节摘要（来自 context_injector）
        from ..context_injector import get_context_injector
        injector = get_context_injector()
        summary = injector.extract_chapter_summary(chapter_text)
        logger.info(
            "[MemoryManager] 章节摘要提取完成 | chapter=%d summary_len=%d",
            chapter_id, len(summary),
        )

        compressor = self.get_summary_compressor(agent_id)
        result = compressor.add_chapter_summary(chapter_id, summary)
        if result:
            logger.info(
                "[MemoryManager] 章节触发压缩完成 | agent_id=%s chapter=%d "
                "block_id=%s",
                agent_id, chapter_id, result.block_id,
            )
        return result

    def get_summary_for_injection(self, agent_id: str) -> str:
        """获取 agent 的章节摘要（用于上下文注入）。"""
        compressor = self.get_summary_compressor(agent_id)
        text = compressor.get_blocks_for_injection()
        # === [10] 注入数据来源日志 ===
        logger.info(
            "[MemoryManager] get_summary_for_injection | agent_id=%s "
            "block_count=%d total_chars=%d",
            agent_id, len(compressor._blocks), len(text),
        )
        return text

    def reload_config(self) -> None:
        """热重载：清空 SummaryCompressor 缓存 + 重新加载 YAML。

        YAML 格式错误或文件丢失时保留原有配置（不崩溃、不丢失 agent 配置）。
        """
        # === [11] reload_config 日志 ===
        old_cache_size = len(self._summary_compressors)
        old_bundle = self.config_bundle
        logger.info(
            "[MemoryManager] reload_config 开始 | cleared_compressors=%d "
            "old_config_path=%s",
            old_cache_size, self.config_path,
        )
        self._summary_compressors.clear()

        # 配置文件被删除或不存在时，直接保留旧配置
        if not self.config_path.exists():
            logger.warning(
                "[MemoryManager] reload_config 配置文件不存在，保留原有配置 | "
                "config_path=%s",
                self.config_path,
            )
            return

        try:
            self._load_config()
        except Exception as exc:
            logger.warning(
                "[MemoryManager] reload_config YAML 加载失败，保留原有配置 | "
                "error=%s",
                exc,
            )
            self.config_bundle = old_bundle
        logger.info(
            "[MemoryManager] reload_config 完成 | new_cache_size=%d",
            len(self._summary_compressors),
        )
