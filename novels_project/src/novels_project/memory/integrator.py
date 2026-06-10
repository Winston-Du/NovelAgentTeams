"""
图谱记忆集成模块 (Graph Memory Orchestrator)

将图谱记忆系统与现有 Agent 主循环（ConversationRuntime）对接的入口模块。

核心职责：
1. 系统启动时初始化图谱记忆各组件
2. 与 Agent Runtime 生命周期绑定（session start / turn end / shutdown）
3. 管理自动同步的触发时机和配置
4. 提供一键式的初始化接口

集成方式（3 步）:
    from novels_project.memory.integrator import GraphMemoryIntegrator

    # Step 1: 创建集成器
    integrator = GraphMemoryIntegrator(
        project_root=get_project_root(),
    )

    # Step 2: 初始化（系统启动时调用一次）
    integrator.initialize()

    # Step 3: 获取工具（注入到 ToolRegistry）
    tools = integrator.get_agent_tools()

    # Step 4（可选）: 绑定到 Runtime
    integrator.attach_to_runtime(my_conversation_runtime)
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Optional, Callable

from .graph_store import GraphStore
from .graph_query import GraphQuery
from .entity_extractor import EntityExtractor
from .sync_manager import SyncManager, AutoSyncConfig, SyncMode

logger = logging.getLogger("novels_project.memory.integrator")


class GraphMemoryIntegrator:
    """
    图谱记忆集成器。管理图谱记忆系统的完整生命周期。

    用法:
        integrator = GraphMemoryIntegrator(project_root)
        integrator.initialize()           # 启动时
        integrator.on_chapter_generated(1, text)  # 章节生成后
        integrator.shutdown()             # 关闭时
    """

    def __init__(
        self,
        project_root: str | Path,
        character_cards_path: Optional[str | Path] = None,
        chapters_dir: Optional[str | Path] = None,
        graph_dir: Optional[str | Path] = None,
        auto_sync_config: Optional[AutoSyncConfig] = None,
    ):
        """
        Args:
            project_root: 项目根目录（如 novel_xuanhuan_output/）
            character_cards_path: 人物卡路径（默认 project_root/config/character_base_cards.yaml）
            chapters_dir: 章节目录（默认 project_root/output/chapters/）
            graph_dir: 图谱存储目录（默认 project_root/graph/）
            auto_sync_config: 自动同步配置
        """
        self._project_root = Path(project_root)

        # 路径解析
        self._character_cards_path = (
            Path(character_cards_path) if character_cards_path
            else self._project_root / "config" / "character_base_cards.yaml"
        )
        self._chapters_dir = (
            Path(chapters_dir) if chapters_dir
            else self._project_root / "output" / "chapters"
        )
        self._graph_dir = (
            Path(graph_dir) if graph_dir
            else self._project_root / "graph"
        )

        # 图谱文件路径
        self._graph_path = self._graph_dir / "knowledge_graph.json"

        # 组件（延迟初始化）
        self._graph_store: Optional[GraphStore] = None
        self._graph_query: Optional[GraphQuery] = None
        self._entity_extractor: Optional[EntityExtractor] = None
        self._sync_manager: Optional[SyncManager] = None

        # 自动同步配置
        self._auto_sync_config = auto_sync_config or AutoSyncConfig()

        # 生命周期
        self._initialized: bool = False
        self._on_chapter_generated_callbacks: list[Callable] = []

        logger.info(
            "[GraphMemoryIntegrator] 创建集成器 | root=%s cards=%s chapters=%s graph=%s",
            self._project_root.name,
            self._character_cards_path.name if self._character_cards_path.exists() else "(not found)",
            self._chapters_dir.name,
            self._graph_dir.name,
        )

    # ============================================================
    # 生命周期管理
    # ============================================================

    def initialize(self, force_full_sync: bool = False) -> dict[str, Any]:
        """
        初始化图谱记忆系统（应在系统启动时调用一次）。

        Args:
            force_full_sync: 是否强制执行全量同步

        Returns:
            初始化状态
        """
        if self._initialized:
            logger.warning("[GraphMemoryIntegrator] 已初始化，跳过")
            return {"status": "already_initialized"}

        start_time = time.time()

        # Step 1: 创建组件
        self._graph_store = GraphStore()
        self._graph_query = GraphQuery(self._graph_store)
        self._entity_extractor = EntityExtractor(self._graph_store)
        self._sync_manager = SyncManager(self._graph_store, self._entity_extractor)

        # Step 2: 配置同步管理器
        self._sync_manager.set_watch_paths(
            character_cards=self._character_cards_path,
            chapters_dir=self._chapters_dir,
            sync_state_dir=self._graph_dir,
            graph_save_path=self._graph_path,
        )

        self._sync_manager.configure_auto_sync(self._auto_sync_config)
        if self._auto_sync_config.enabled:
            self._sync_manager.enable_auto_sync()

        # Step 3: 尝试加载已有图谱
        loaded = False
        if self._graph_path.exists():
            loaded = self._graph_store.load(str(self._graph_path))
            logger.info(
                "[GraphMemoryIntegrator] 加载已有图谱 | nodes=%d edges=%d",
                self._graph_store.entity_count(),
                self._graph_store.relation_count(),
            )

        # Step 4: 执行初始同步
        if force_full_sync or not loaded:
            logger.info(
                "[GraphMemoryIntegrator] 执行初始同步 | mode=%s",
                "full (强制)" if force_full_sync else "full (首次)",
            )
            sync_result = self._sync_manager.sync(mode=SyncMode.FULL)
        else:
            sync_result = self._sync_manager.sync(mode=SyncMode.INCREMENTAL)

        elapsed = round(time.time() - start_time, 2)
        self._initialized = True

        result = {
            "status": "initialized",
            "loaded_from_file": loaded,
            "elapsed": elapsed,
            "node_count": self._graph_store.entity_count(),
            "edge_count": self._graph_store.relation_count(),
            "sync_result": sync_result,
        }

        logger.info(
            "[GraphMemoryIntegrator] 初始化完成 | elapsed=%.2fs nodes=%d edges=%d",
            elapsed, result["node_count"], result["edge_count"],
        )

        return result

    def shutdown(self) -> dict[str, Any]:
        """
        关闭图谱记忆系统（应在系统关闭时调用）。

        Returns:
            关闭状态
        """
        if not self._initialized:
            return {"status": "not_initialized"}

        logger.info("[GraphMemoryIntegrator] 开始关闭")

        # 持久化图谱
        self._graph_dir.mkdir(parents=True, exist_ok=True)
        self._graph_store.save(str(self._graph_path))

        # 输出最终报告
        health = self._sync_manager.get_health_report()
        logger.info("[GraphMemoryIntegrator]\n%s", health)

        self._initialized = False

        return {
            "status": "shutdown",
            "final_nodes": self._graph_store.entity_count(),
            "final_edges": self._graph_store.relation_count(),
            "graph_path": str(self._graph_path),
        }

    # ============================================================
    # 与 Agent Runtime 集成
    # ============================================================

    def attach_to_runtime(self, runtime: Any):
        """
        将图谱记忆系统附加到 Agent 运行时。

        使用 ConversationRuntime 的 hook 系统，在每次 turn 结束后
        自动同步新生成的章节内容。优先使用 add_turn_hook()，
        对不支持 hook 的 runtime 降级使用 monkey-patch。

        Args:
            runtime: ConversationRuntime 实例
        """
        # 优先使用 hook 系统（新架构）
        if hasattr(runtime, "add_turn_hook"):
            runtime.add_turn_hook(self._on_turn_completed)
            logger.info(
                "[GraphMemoryIntegrator] 已通过 hook 附加到 ConversationRuntime | type=%s",
                type(runtime).__name__,
            )
            return

        # 降级方案：monkey-patch（兼容旧版 runtime）
        original_run_turn = runtime.run_turn

        def patched_run_turn(user_input: str):
            result = original_run_turn(user_input)
            if self._initialized and self._sync_manager:
                self._check_and_sync()
            return result

        runtime.run_turn = patched_run_turn
        logger.warning(
            "[GraphMemoryIntegrator] 降级使用 monkey-patch 附加到 ConversationRuntime | type=%s",
            type(runtime).__name__,
        )

    def _on_turn_completed(self, turn_summary: Any) -> None:
        """Hook callback: invoked after each conversation turn completes."""
        logger.info(
            "[GraphMemoryIntegrator] turn 结束 hook 触发 | iter=%d tool_calls=%d",
            getattr(turn_summary, "iterations", -1),
            len(getattr(turn_summary, "tool_results", []) or []),
        )
        if self._initialized and self._sync_manager:
            self._check_and_sync()

    def on_chapter_generated(self, chapter_id: int, chapter_text: str, llm_client: Any = None):
        """
        新章节生成后的回调（事件触发同步入口）。

        调用时机：在章节生成流程完成后，将章节内容同步到图谱。

        Args:
            chapter_id: 章节 ID
            chapter_text: 章节文本
            llm_client: LLM 客户端
        """
        if not self._initialized:
            logger.warning("[GraphMemoryIntegrator] 未初始化，跳过章节 %d 同步", chapter_id)
            return

        logger.info(
            "[GraphMemoryIntegrator] 章节生成事件 | chapter=%d text_len=%d auto_sync=%s",
            chapter_id, len(chapter_text),
            self._auto_sync_config.event_triggered,
        )

        # 触发同步管理器的事件回调（支持阈值控制）
        if self._sync_manager:
            self._sync_manager.on_chapter_generated(chapter_id, chapter_text, llm_client)

        # 执行用户自定义回调
        for callback in self._on_chapter_generated_callbacks:
            try:
                callback(chapter_id, chapter_text, self._graph_store)
            except Exception as e:
                logger.error(
                    "[GraphMemoryIntegrator] 章节回调执行失败 | chapter=%d error=%s",
                    chapter_id, e,
                )

        # 自动将章节摘要存入向量库（场景5）
        self._add_chapter_to_vector_db(chapter_id, chapter_text)

    def _add_chapter_to_vector_db(self, chapter_id: int, chapter_text: str):
        """将章节摘要添加到向量库，支持场景5：根据章节摘要创作新章节"""
        try:
            from ..context_injector import get_context_injector
            injector = get_context_injector()
            success = injector.add_chapter_to_vector_db(chapter_text, chapter_id)
            if success:
                logger.info(
                    "[GraphMemoryIntegrator] 章节摘要已存入向量库 | chapter=%d",
                    chapter_id,
                )
        except Exception as e:
            logger.error(
                "[GraphMemoryIntegrator] 添加章节摘要到向量库失败 | chapter=%d error=%s",
                chapter_id, e,
            )

    def register_chapter_callback(self, callback: Callable):
        """注册章节生成后的自定义回调。"""
        self._on_chapter_generated_callbacks.append(callback)

    def _check_and_sync(self):
        """检查并执行同步（用于定时/turn 触发）。"""
        if not self._auto_sync_config or not self._auto_sync_config.enabled:
            return

        if not self._sync_manager:
            return

        # 使用增量同步检查变更
        try:
            result = self._sync_manager.sync(mode=SyncMode.INCREMENTAL, force=False)
            logger.debug(
                "[GraphMemoryIntegrator] Turn 后同步完成 | entities=%d relations=%d",
                result.get("entities_added", 0),
                result.get("relations_added", 0),
            )
        except Exception as e:
            logger.warning("[GraphMemoryIntegrator] Turn 后同步失败 | error=%s", e)

    # ============================================================
    # 工具接口
    # ============================================================

    def get_agent_tools(self) -> dict[str, Callable]:
        """
        获取可注册到 Agent 的图谱记忆工具函数。

        返回字典可直接用于 ToolRegistry.register(ToolSpec(...))。

        Returns:
            {tool_name: handler_function} 字典
        """
        from .graph_memory_tool import (
            query_character_network,
            query_relation_between,
            search_graph,
            trace_foreshadowing,
            get_graph_context,
            build_knowledge_graph,
            get_graph_stats,
        )

        return {
            "query_character_network": query_character_network,
            "query_relation_between": query_relation_between,
            "search_graph": search_graph,
            "trace_foreshadowing": trace_foreshadowing,
            "get_graph_context": get_graph_context,
            "build_knowledge_graph": build_knowledge_graph,
            "get_graph_stats": get_graph_stats,
        }

    def inject_graph_context_into_prompt(
        self,
        entity_name: str,
        context_type: str = "writing",
    ) -> str:
        """
        将图谱上下文注入到 Agent 的 System Prompt 中。

        用法:
            context = integrator.inject_graph_context_into_prompt("陆商曜", "writing")
            system_prompt = f"{base_prompt}\n\n{context}"

        Args:
            entity_name: 实体名称
            context_type: "writing" 或 "review"

        Returns:
            格式化的上下文字符串
        """
        if not self._graph_query:
            return ""

        return self._graph_query.get_graph_context(entity_name, context_type)

    # ============================================================
    # 状态查询
    # ============================================================

    @property
    def graph_store(self) -> Optional[GraphStore]:
        return self._graph_store

    @property
    def graph_query(self) -> Optional[GraphQuery]:
        return self._graph_query

    @property
    def sync_manager(self) -> Optional[SyncManager]:
        return self._sync_manager

    def is_initialized(self) -> bool:
        return self._initialized

    def get_status(self) -> dict[str, Any]:
        """获取集成器状态。"""
        base = {
            "initialized": self._initialized,
            "project_root": str(self._project_root),
            "graph_path": str(self._graph_path),
        }

        if self._initialized and self._sync_manager:
            base["sync_status"] = self._sync_manager.get_sync_status()
            base["health_report"] = self._sync_manager.get_health_report()

        return base

    # ============================================================
    # 便捷方法：一键式初始化并注册
    # ============================================================

    @classmethod
    def setup_and_register(
        cls,
        project_root: str | Path,
        tool_registry: Any,
        auto_sync_config: Optional[AutoSyncConfig] = None,
        force_full_sync: bool = False,
        llm_client: Any = None,
    ) -> "GraphMemoryIntegrator":
        """
        一键式初始化并注册所有 Agent 工具。

        这是推荐的集成方式，适用于 CLI 入口或启动脚本。

        Args:
            project_root: 项目根目录
            tool_registry: ToolRegistry 实例
            auto_sync_config: 自动同步配置
            force_full_sync: 是否强制执行全量同步
            llm_client: LLM 客户端

        Returns:
            已初始化的 GraphMemoryIntegrator 实例

        用法:
            from novels_project.memory import GraphMemoryIntegrator
            from novels_project.tool_spec import build_builtin_tool_registry

            registry = build_builtin_tool_registry()
            integrator = GraphMemoryIntegrator.setup_and_register(
                project_root="/path/to/novel_xuanhuan_output",
                tool_registry=registry,
            )
        """
        integrator = cls(
            project_root=project_root,
            auto_sync_config=auto_sync_config,
        )

        init_result = integrator.initialize(force_full_sync=force_full_sync)
        logger.info(
            "[GraphMemoryIntegrator] 一键初始化完成 | %s",
            {k: v for k, v in init_result.items() if k != "sync_result"},
        )

        # 注册工具（工具已在 tool_spec.py 中注册，这里仅验证）

        # 将全局单例绑定到集成器实例
        store = integrator.graph_store
        if store:  # pragma: no branch
            import novels_project.memory.graph_memory_tool as gmt
            gmt._global_graph_store = store
            gmt._global_graph_query = integrator.graph_query
            gmt._global_sync_manager = integrator.sync_manager

        logger.info("[GraphMemoryIntegrator] 工具已注册到全局单例")

        return integrator