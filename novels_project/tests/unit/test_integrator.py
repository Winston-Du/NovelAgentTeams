"""
单元测试：memory/integrator.py - GraphMemoryIntegrator 类
"""
import pytest
from unittest import mock
from pathlib import Path

from novels_project.memory.graph_store import GraphStore
from novels_project.memory.integrator import GraphMemoryIntegrator
from novels_project.memory.sync_manager import AutoSyncConfig, SyncMode


# ---- helpers ----

def make_integrator(tmp_path, **kwargs):
    """创建带有临时目录的 GraphMemoryIntegrator。"""
    return GraphMemoryIntegrator(
        project_root=str(tmp_path),
        **kwargs,
    )


# ==================== __init__ ====================

class TestGraphMemoryIntegratorInit:
    def test_default_paths(self, tmp_path):
        integrator = GraphMemoryIntegrator(str(tmp_path))
        assert integrator._project_root == tmp_path
        assert integrator._character_cards_path == tmp_path / "config" / "character_base_cards.yaml"
        assert integrator._chapters_dir == tmp_path / "output" / "chapters"
        assert integrator._graph_dir == tmp_path / "graph"
        assert integrator._graph_path == tmp_path / "graph" / "knowledge_graph.json"
        assert integrator._initialized is False

    def test_custom_paths(self, tmp_path):
        integrator = GraphMemoryIntegrator(
            str(tmp_path),
            character_cards_path=str(tmp_path / "custom" / "cards.yaml"),
            chapters_dir=str(tmp_path / "custom" / "chapters"),
            graph_dir=str(tmp_path / "custom" / "graph"),
        )
        assert integrator._character_cards_path == tmp_path / "custom" / "cards.yaml"
        assert integrator._chapters_dir == tmp_path / "custom" / "chapters"
        assert integrator._graph_dir == tmp_path / "custom" / "graph"

    def test_with_auto_sync_config(self, tmp_path):
        config = AutoSyncConfig()
        config.enabled = True
        integrator = GraphMemoryIntegrator(str(tmp_path), auto_sync_config=config)
        assert integrator._auto_sync_config.enabled is True


# ==================== initialize ====================

class TestInitialize:
    def test_first_initialization(self, tmp_path):
        integrator = make_integrator(tmp_path)
        result = integrator.initialize()
        assert result["status"] == "initialized"
        assert integrator._initialized is True
        assert "node_count" in result
        assert "edge_count" in result

    def test_already_initialized(self, tmp_path):
        integrator = make_integrator(tmp_path)
        integrator.initialize()
        result = integrator.initialize()
        assert result["status"] == "already_initialized"

    def test_force_full_sync(self, tmp_path):
        integrator = make_integrator(tmp_path)
        integrator.initialize(force_full_sync=True)
        assert integrator._initialized is True

    def test_loads_existing_graph(self, tmp_path):
        """如果 graph 文件已存在，应加载已有图谱。"""
        # 先创建一个有效的图谱文件
        store = GraphStore()
        store.add_entity("TestChar", "character", {"brief": "test"})
        graph_dir = tmp_path / "graph"
        graph_dir.mkdir(parents=True)
        store.save(str(graph_dir / "knowledge_graph.json"))

        integrator = make_integrator(tmp_path)
        result = integrator.initialize()
        assert result["loaded_from_file"] is True


# ==================== shutdown ====================

class TestShutdown:
    def test_shutdown_saves_graph(self, tmp_path):
        integrator = make_integrator(tmp_path)
        integrator.initialize()
        result = integrator.shutdown()
        assert result["status"] == "shutdown"
        assert integrator._initialized is False
        assert integrator._graph_path.exists()

    def test_shutdown_not_initialized(self, tmp_path):
        integrator = make_integrator(tmp_path)
        result = integrator.shutdown()
        assert result["status"] == "not_initialized"


# ==================== on_chapter_generated ====================

class TestOnChapterGenerated:
    def test_not_initialized(self, tmp_path):
        integrator = make_integrator(tmp_path)
        integrator.on_chapter_generated(1, "章节文本")
        # 不应该抛出异常

    def test_initialized(self, tmp_path):
        integrator = make_integrator(tmp_path)
        integrator.initialize()
        integrator.on_chapter_generated(1, "章节文本")
        # 同步管理器应被调用

    def test_with_llm_client(self, tmp_path):
        integrator = make_integrator(tmp_path)
        integrator.initialize()
        llm_client = mock.MagicMock()
        integrator.on_chapter_generated(1, "章节文本", llm_client=llm_client)


# ==================== register_chapter_callback ====================

class TestRegisterChapterCallback:
    def test_callback_called(self, tmp_path):
        integrator = make_integrator(tmp_path)
        integrator.initialize()

        callback_called = []

        def my_callback(chapter_id, chapter_text, graph_store):
            callback_called.append((chapter_id, chapter_text))

        integrator.register_chapter_callback(my_callback)
        integrator.on_chapter_generated(1, "测试章节")
        assert len(callback_called) == 1
        assert callback_called[0][0] == 1
        assert callback_called[0][1] == "测试章节"

    def test_callback_error_handled(self, tmp_path):
        integrator = make_integrator(tmp_path)
        integrator.initialize()

        def bad_callback(chapter_id, chapter_text, graph_store):
            raise RuntimeError("callback error")

        integrator.register_chapter_callback(bad_callback)
        # 不应该抛出异常
        integrator.on_chapter_generated(1, "测试章节")


# ==================== get_agent_tools ====================

class TestGetAgentTools:
    def test_returns_expected_tools(self):
        integrator = GraphMemoryIntegrator(str("/tmp/test"))
        tools = integrator.get_agent_tools()
        expected_tools = [
            "query_character_network",
            "query_relation_between",
            "search_graph",
            "trace_foreshadowing",
            "get_graph_context",
            "build_knowledge_graph",
            "get_graph_stats",
        ]
        for tool_name in expected_tools:
            assert tool_name in tools
            assert callable(tools[tool_name])


# ==================== inject_graph_context_into_prompt ====================

class TestInjectGraphContext:
    def test_not_initialized(self, tmp_path):
        integrator = make_integrator(tmp_path)
        result = integrator.inject_graph_context_into_prompt("陆商曜", "writing")
        assert result == ""

    def test_initialized(self, tmp_path):
        integrator = make_integrator(tmp_path)
        integrator.initialize()
        result = integrator.inject_graph_context_into_prompt("陆商曜", "writing")
        assert result == ""  # 没有该实体
        result2 = integrator.inject_graph_context_into_prompt("陆商曜", "review")
        assert result2 == ""


# ==================== properties ====================

class TestProperties:
    def test_graph_store(self, tmp_path):
        integrator = make_integrator(tmp_path)
        assert integrator.graph_store is None
        integrator.initialize()
        assert integrator.graph_store is not None

    def test_graph_query(self, tmp_path):
        integrator = make_integrator(tmp_path)
        assert integrator.graph_query is None
        integrator.initialize()
        assert integrator.graph_query is not None

    def test_sync_manager(self, tmp_path):
        integrator = make_integrator(tmp_path)
        assert integrator.sync_manager is None
        integrator.initialize()
        assert integrator.sync_manager is not None


# ==================== is_initialized / get_status ====================

class TestStatus:
    def test_is_initialized(self, tmp_path):
        integrator = make_integrator(tmp_path)
        assert integrator.is_initialized() is False
        integrator.initialize()
        assert integrator.is_initialized() is True

    def test_get_status(self, tmp_path):
        integrator = make_integrator(tmp_path)
        status = integrator.get_status()
        assert status["initialized"] is False
        assert status["project_root"] == str(tmp_path)

        integrator.initialize()
        status = integrator.get_status()
        assert status["initialized"] is True


# ==================== setup_and_register ====================

class TestSetupAndRegister:
    def test_setup_and_register(self, tmp_path):
        mock_registry = mock.MagicMock()
        integrator = GraphMemoryIntegrator.setup_and_register(
            project_root=str(tmp_path),
            tool_registry=mock_registry,
        )
        assert integrator.is_initialized() is True
        assert integrator.graph_store is not None

    def test_setup_and_register_with_force_sync(self, tmp_path):
        mock_registry = mock.MagicMock()
        integrator = GraphMemoryIntegrator.setup_and_register(
            project_root=str(tmp_path),
            tool_registry=mock_registry,
            force_full_sync=True,
        )
        assert integrator.is_initialized() is True


# ==================== attach_to_runtime ====================

class TestAttachToRuntime:
    def test_patches_run_turn(self, tmp_path):
        integrator = make_integrator(tmp_path)
        integrator.initialize()

        mock_runtime = mock.MagicMock()
        original_run = mock.MagicMock(return_value="result")
        mock_runtime.run_turn = original_run

        integrator.attach_to_runtime(mock_runtime)

        # 调用 patched run_turn
        result = mock_runtime.run_turn("user input")
        assert result == "result"
        original_run.assert_called_once_with("user input")

    def test_attach_runtime_when_auto_sync_disabled(self, tmp_path):
        """attach_to_runtime with auto_sync disabled -> _check_and_sync returns early."""
        integrator = make_integrator(tmp_path)
        integrator._auto_sync_config.enabled = False
        integrator.initialize()

        mock_runtime = mock.MagicMock()
        original_run = mock.MagicMock(return_value="result")
        mock_runtime.run_turn = original_run

        integrator.attach_to_runtime(mock_runtime)
        result = mock_runtime.run_turn("user input")
        assert result == "result"
        original_run.assert_called_once_with("user input")

    def test_attach_runtime_not_initialized(self, tmp_path):
        """attach_to_runtime when not initialized -> _check_and_sync returns early."""
        integrator = make_integrator(tmp_path)
        # Not calling initialize()

        mock_runtime = mock.MagicMock()
        original_run = mock.MagicMock(return_value="result")
        mock_runtime.run_turn = original_run

        integrator.attach_to_runtime(mock_runtime)
        result = mock_runtime.run_turn("user input")
        assert result == "result"
        original_run.assert_called_once_with("user input")


# ==================== initialize with auto_sync ====================

class TestInitializeAutoSync:
    def test_initialize_with_auto_sync_enabled(self, tmp_path):
        """initialize with auto_sync_config.enabled = True."""
        config = AutoSyncConfig()
        config.enabled = True
        integrator = GraphMemoryIntegrator(str(tmp_path), auto_sync_config=config)
        result = integrator.initialize()
        assert result["status"] == "initialized"
        assert integrator._initialized is True


# ==================== on_chapter_generated edge cases ====================

class TestOnChapterGeneratedEdgeCases:
    def test_sync_manager_none(self, tmp_path):
        """on_chapter_generated when _sync_manager is None."""
        integrator = make_integrator(tmp_path)
        integrator._initialized = True
        integrator._sync_manager = None
        # Should not raise
        integrator.on_chapter_generated(1, "文本")

    def test_no_event_triggered_path(self, tmp_path):
        """on_chapter_generated with event_triggered disabled."""
        integrator = make_integrator(tmp_path)
        integrator._auto_sync_config.event_triggered = False
        integrator.initialize()
        # Should not raise
        integrator.on_chapter_generated(1, "文本")


# ==================== register_chapter_callback ====================

class TestRegisterChapterCallbackMore:
    def test_register_multiple_callbacks(self, tmp_path):
        """Multiple callbacks called in order."""
        integrator = make_integrator(tmp_path)
        integrator.initialize()

        calls = []
        integrator.register_chapter_callback(lambda cid, txt, gs: calls.append(("a", cid)))
        integrator.register_chapter_callback(lambda cid, txt, gs: calls.append(("b", cid)))

        integrator.on_chapter_generated(1, "test")
        assert calls == [("a", 1), ("b", 1)]


# ==================== _check_and_sync ====================

class TestCheckAndSync:
    def test_sync_manager_none(self, tmp_path):
        """_check_and_sync when _sync_manager is None."""
        integrator = make_integrator(tmp_path)
        integrator._initialized = True
        integrator._auto_sync_config.enabled = True
        integrator._sync_manager = None
        # Should not raise
        integrator._check_and_sync()

    def test_sync_raises_exception(self, tmp_path):
        """_check_and_sync when sync raises exception."""
        integrator = make_integrator(tmp_path)
        integrator.initialize()
        integrator._auto_sync_config.enabled = True
        integrator._sync_manager.sync = mock.MagicMock(side_effect=RuntimeError("sync failed"))
        # Should not raise
        integrator._check_and_sync()


# ==================== setup_and_register with store ====================

class TestSetupAndRegisterMore:
    def test_setup_and_register_with_llm_client(self, tmp_path):
        """setup_and_register with llm_client parameter."""
        mock_registry = mock.MagicMock()
        llm_client = mock.MagicMock()
        integrator = GraphMemoryIntegrator.setup_and_register(
            project_root=str(tmp_path),
            tool_registry=mock_registry,
            llm_client=llm_client,
        )
        assert integrator.is_initialized() is True