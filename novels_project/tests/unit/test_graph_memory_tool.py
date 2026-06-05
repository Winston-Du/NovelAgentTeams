"""
单元测试：memory/graph_memory_tool.py
"""
import pytest
from pathlib import Path
from unittest import mock

import novels_project.memory.graph_memory_tool as gmt


# ---- helpers ----

@pytest.fixture(autouse=True)
def reset_globals():
    """每个测试前后重置全局单例。"""
    gmt._global_graph_store = None
    gmt._global_graph_query = None
    gmt._global_sync_manager = None
    yield
    gmt._global_graph_store = None
    gmt._global_graph_query = None
    gmt._global_sync_manager = None


def make_mock_store(node_count=5, edge_count=3):
    store = mock.MagicMock()
    store.get_statistics.return_value = {"node_count": node_count, "edge_count": edge_count}
    store.load.return_value = True
    store.entity_count.return_value = node_count
    store.relation_count.return_value = edge_count
    store.export_summary.return_value = "summary"
    return store


def make_mock_query():
    query = mock.MagicMock()
    return query


def make_mock_sync_mgr():
    mgr = mock.MagicMock()
    return mgr


# ==================== 单例函数 ====================

class TestGlobalSingletons:
    def test_get_graph_store_first_call_creates(self):
        with mock.patch.object(gmt, "GraphStore") as MockStore:
            store = gmt.get_graph_store()
            MockStore.assert_called_once()
            assert store is MockStore.return_value

    def test_get_graph_store_second_call_returns_same(self):
        with mock.patch.object(gmt, "GraphStore") as MockStore:
            store1 = gmt.get_graph_store()
            store2 = gmt.get_graph_store()
            MockStore.assert_called_once()
            assert store1 is store2

    def test_get_graph_query_first_call_creates(self):
        with mock.patch.object(gmt, "GraphQuery") as MockQuery, \
             mock.patch.object(gmt, "GraphStore"):
            gmt._global_graph_store = mock.MagicMock()
            query = gmt.get_graph_query()
            MockQuery.assert_called_once()
            assert query is MockQuery.return_value

    def test_get_graph_query_second_call_returns_same(self):
        with mock.patch.object(gmt, "GraphQuery") as MockQuery, \
             mock.patch.object(gmt, "GraphStore"):
            gmt._global_graph_store = mock.MagicMock()
            q1 = gmt.get_graph_query()
            q2 = gmt.get_graph_query()
            MockQuery.assert_called_once()
            assert q1 is q2

    def test_get_sync_manager_first_call_creates(self):
        with mock.patch.object(gmt, "SyncManager") as MockSM, \
             mock.patch.object(gmt, "GraphStore"):
            gmt._global_graph_store = mock.MagicMock()
            mgr = gmt.get_sync_manager()
            MockSM.assert_called_once()
            assert mgr is MockSM.return_value

    def test_get_sync_manager_second_call_returns_same(self):
        with mock.patch.object(gmt, "SyncManager") as MockSM, \
             mock.patch.object(gmt, "GraphStore"):
            gmt._global_graph_store = mock.MagicMock()
            m1 = gmt.get_sync_manager()
            m2 = gmt.get_sync_manager()
            MockSM.assert_called_once()
            assert m1 is m2


# ==================== init_graph_memory ====================

class TestInitGraphMemory:
    def test_with_all_params(self):
        store = make_mock_store()
        sync_mgr = make_mock_sync_mgr()
        gmt._global_graph_store = store
        gmt._global_sync_manager = sync_mgr
        result = gmt.init_graph_memory(
            graph_path="/tmp/graph.json",
            character_cards_path="/tmp/cards.yaml",
            chapters_dir="/tmp/chapters",
        )
        store.load.assert_called_once_with("/tmp/graph.json")
        sync_mgr.set_watch_paths.assert_called_once_with("/tmp/cards.yaml", "/tmp/chapters")
        assert result["loaded_from_file"] is True
        assert result["sync_configured"] is True

    def test_without_params(self):
        store = make_mock_store()
        sync_mgr = make_mock_sync_mgr()
        gmt._global_graph_store = store
        gmt._global_sync_manager = sync_mgr
        result = gmt.init_graph_memory()
        store.load.assert_not_called()
        assert result["sync_configured"] is False

    def test_with_graph_path_only(self):
        store = make_mock_store()
        sync_mgr = make_mock_sync_mgr()
        gmt._global_graph_store = store
        gmt._global_sync_manager = sync_mgr
        result = gmt.init_graph_memory(graph_path="/tmp/g.json")
        store.load.assert_called_once_with("/tmp/g.json")
        assert result["sync_configured"] is False


# ==================== query_character_network ====================

class TestQueryCharacterNetwork:
    def test_success(self):
        query = mock.MagicMock()
        query.get_character_network.return_value = {
            "character": {"name": "陆商曜", "brief": "主角", "role": "hero"},
            "direct_relations": [{"name": "周桓", "relation": "enemy"}],
            "organizations": [{"name": "青云宗"}],
            "events": [{"name": "试炼之战"}],
            "related_concepts": [{"name": "神秘玉简"}],
            "indirect_relations": [{"name": "路人甲", "distance": 2}],
        }
        gmt._global_graph_query = query
        result = gmt.query_character_network("陆商曜")
        assert "陆商曜" in result
        assert "周桓" in result
        assert "青云宗" in result
        assert "试炼之战" in result
        assert "神秘玉简" in result
        assert "路人甲" in result

    def test_error_from_query(self):
        query = mock.MagicMock()
        query.get_character_network.return_value = {"error": "未找到人物"}
        gmt._global_graph_query = query
        result = gmt.query_character_network("不存在")
        assert "查询失败" in result

    def test_with_all_sections(self):
        query = mock.MagicMock()
        query.get_character_network.return_value = {
            "character": {"brief": "desc", "role": "hero"},
            "direct_relations": [{"name": "A", "relation": "ally"}],
            "organizations": [{"name": "Org"}],
            "events": [{"name": "Event"}],
            "related_concepts": [{"name": "Concept"}],
            "indirect_relations": [{"name": "Indirect", "distance": 3}],
        }
        gmt._global_graph_query = query
        result = gmt.query_character_network("X")
        assert "简介" in result
        assert "角色" in result
        assert "直接关系" in result
        assert "所属组织" in result
        assert "相关事件" in result
        assert "关联暗线/伏笔" in result
        assert "间接关系" in result

    def test_character_without_brief(self):
        """Character without brief field -> no 简介 printed."""
        query = mock.MagicMock()
        query.get_character_network.return_value = {
            "character": {"name": "X"},
            "direct_relations": [],
            "organizations": [],
            "events": [],
            "related_concepts": [],
            "indirect_relations": [],
        }
        gmt._global_graph_query = query
        result = gmt.query_character_network("X")
        assert "关系网络" in result
        assert "简介" not in result

    def test_character_without_role(self):
        """Character without role field -> no 角色 printed."""
        query = mock.MagicMock()
        query.get_character_network.return_value = {
            "character": {"brief": "desc"},
            "direct_relations": [],
            "organizations": [],
            "events": [],
            "related_concepts": [],
            "indirect_relations": [],
        }
        gmt._global_graph_query = query
        result = gmt.query_character_network("X")
        assert "关系网络" in result
        assert "角色" not in result


# ==================== query_relation_between ====================

class TestQueryRelationBetween:
    def test_direct_relation(self):
        query = mock.MagicMock()
        query.get_relation_between.return_value = {
            "direct_relations": [{"source": "A", "target": "B", "type": "ally"}],
            "shortest_path": None,
            "all_paths": [],
        }
        gmt._global_graph_query = query
        result = gmt.query_relation_between("A", "B")
        assert "直接关系" in result
        assert "A" in result and "B" in result

    def test_no_direct(self):
        query = mock.MagicMock()
        query.get_relation_between.return_value = {
            "direct_relations": [],
            "shortest_path": None,
            "all_paths": [],
        }
        gmt._global_graph_query = query
        result = gmt.query_relation_between("A", "B")
        assert "无直接关系" in result

    def test_with_path(self):
        query = mock.MagicMock()
        query.get_relation_between.return_value = {
            "direct_relations": [],
            "shortest_path": ["A", "C", "B"],
            "all_paths": [],
        }
        gmt._global_graph_query = query
        result = gmt.query_relation_between("A", "B")
        assert "最短关联路径" in result

    def test_with_all_paths(self):
        query = mock.MagicMock()
        query.get_relation_between.return_value = {
            "direct_relations": [],
            "shortest_path": None,
            "all_paths": [["A", "C", "D", "B"]],
        }
        gmt._global_graph_query = query
        result = gmt.query_relation_between("A", "B")
        assert "其他关联路径" in result


# ==================== search_graph ====================

class TestSearchGraph:
    def test_found_results(self):
        query = mock.MagicMock()
        query.search.return_value = [
            {"name": "陆商曜", "type": "character", "brief": "主角"},
        ]
        gmt._global_graph_query = query
        result = gmt.search_graph("陆")
        assert "陆商曜" in result
        assert "主角" in result

    def test_no_results(self):
        query = mock.MagicMock()
        query.search.return_value = []
        gmt._global_graph_query = query
        result = gmt.search_graph("不存在")
        assert "未找到" in result

    def test_with_entity_type_filter(self):
        query = mock.MagicMock()
        query.search.return_value = [{"name": "X", "type": "event"}]
        gmt._global_graph_query = query
        gmt.search_graph("X", entity_type="event")
        query.search.assert_called_once_with("X", ["event"])


# ==================== trace_foreshadowing ====================

class TestTraceForeshadowing:
    def test_success(self):
        query = mock.MagicMock()
        query.trace_foreshadowing.return_value = {
            "concept": {"brief": "神秘力量"},
            "foreshadowed_events": [{"name": "决战", "chapter": "10"}],
            "referenced_by": [{"name": "预言", "chapter": "1"}],
            "related_characters": [{"name": "主角", "relation": "knows"}],
        }
        gmt._global_graph_query = query
        result = gmt.trace_foreshadowing("神秘力量")
        assert "神秘力量" in result
        assert "决战" in result
        assert "预言" in result

    def test_error_with_search_fallback(self):
        query = mock.MagicMock()
        query.trace_foreshadowing.side_effect = [
            {"error": "未找到"},
            {"concept": {"brief": "desc"}, "foreshadowed_events": [], "referenced_by": [], "related_characters": []},
        ]
        query.search.return_value = [{"name": "actually_exists"}]
        gmt._global_graph_query = query
        result = gmt.trace_foreshadowing("搜索词")
        assert "追踪" in result

    def test_concept_without_brief(self):
        """trace_foreshadowing with concept that has no brief."""
        query = mock.MagicMock()
        query.trace_foreshadowing.return_value = {
            "concept": {"name": "C"},
            "foreshadowed_events": [],
            "referenced_by": [],
            "related_characters": [],
        }
        gmt._global_graph_query = query
        result = gmt.trace_foreshadowing("C")
        assert "伏笔追踪" in result
        assert "描述" not in result

    def test_error_no_fallback(self):
        query = mock.MagicMock()
        query.trace_foreshadowing.return_value = {"error": "未找到"}
        query.search.return_value = []
        gmt._global_graph_query = query
        result = gmt.trace_foreshadowing("不存在")
        assert "未找到" in result


# ==================== get_graph_context ====================

class TestGetGraphContext:
    def test_writing_context(self):
        query = mock.MagicMock()
        query.get_graph_context.return_value = "writing context string"
        gmt._global_graph_query = query
        result = gmt.get_graph_context("陆商曜", "writing")
        assert result == "writing context string"
        query.get_graph_context.assert_called_once_with("陆商曜", "writing")

    def test_review_context(self):
        query = mock.MagicMock()
        query.get_graph_context.return_value = "review context string"
        gmt._global_graph_query = query
        result = gmt.get_graph_context("陆商曜", "review")
        assert result == "review context string"


# ==================== build_knowledge_graph ====================

class TestBuildKnowledgeGraph:
    def test_full_sync(self):
        store = make_mock_store()
        sync_mgr = make_mock_sync_mgr()
        sync_mgr.sync.return_value = {
            "mode": "full",
            "characters_added": 5,
            "chapters_processed": 3,
            "entities_added": 10,
            "relations_added": 8,
            "skipped": 0,
        }
        gmt._global_graph_store = store
        gmt._global_sync_manager = sync_mgr

        with mock.patch("novels_project.project_config.get_character_cards_path") as mock_cards, \
             mock.patch("novels_project.project_config.get_chapters_dir") as mock_chapters, \
             mock.patch("novels_project.project_config.get_project_root") as mock_root, \
             mock.patch.object(gmt, "EntityExtractor") as MockExtractor:
            mock_cards.return_value = "/tmp/cards.yaml"
            mock_chapters.return_value = "/tmp/chapters"
            mock_root.return_value = Path("/tmp/project")

            result = gmt.build_knowledge_graph(full_sync=True)
            assert "知识图谱构建完成" in result
            assert "full" in result
            store.save.assert_called_once()

    def test_incremental_sync(self):
        store = make_mock_store()
        sync_mgr = make_mock_sync_mgr()
        sync_mgr.sync.return_value = {
            "mode": "incremental",
            "characters_added": 1,
            "chapters_processed": 1,
            "entities_added": 2,
            "relations_added": 1,
            "skipped": 0,
        }
        gmt._global_graph_store = store
        gmt._global_sync_manager = sync_mgr

        with mock.patch("novels_project.project_config.get_character_cards_path") as mock_cards, \
             mock.patch("novels_project.project_config.get_chapters_dir") as mock_chapters, \
             mock.patch("novels_project.project_config.get_project_root") as mock_root, \
             mock.patch.object(gmt, "EntityExtractor") as MockExtractor:
            mock_cards.return_value = "/tmp/cards.yaml"
            mock_chapters.return_value = "/tmp/chapters"
            mock_root.return_value = Path("/tmp/project")

            result = gmt.build_knowledge_graph()
            assert "知识图谱构建完成" in result
            assert "incremental" in result

    def test_with_default_paths(self, tmp_path):
        """不传 character_cards_path 时使用默认路径。"""
        store = make_mock_store()
        sync_mgr = make_mock_sync_mgr()
        sync_mgr.sync.return_value = {"mode": "full", "skipped": 0}
        gmt._global_graph_store = store
        gmt._global_sync_manager = sync_mgr

        default_root = tmp_path / "default"
        default_root.mkdir(parents=True, exist_ok=True)

        with mock.patch("novels_project.project_config.get_character_cards_path") as mock_cards, \
             mock.patch("novels_project.project_config.get_chapters_dir") as mock_chapters, \
             mock.patch("novels_project.project_config.get_project_root") as mock_root, \
             mock.patch.object(gmt, "EntityExtractor") as MockExtractor:
            mock_cards.return_value = "/default/cards.yaml"
            mock_chapters.return_value = "/default/chapters"
            mock_root.return_value = default_root

            gmt.build_knowledge_graph()
            mock_cards.assert_called_once()

    def test_with_custom_cards_path(self, tmp_path):
        """build_knowledge_graph with explicit character_cards_path."""
        store = make_mock_store()
        sync_mgr = make_mock_sync_mgr()
        sync_mgr.sync.return_value = {"mode": "full", "skipped": 0}
        gmt._global_graph_store = store
        gmt._global_sync_manager = sync_mgr

        default_root = tmp_path / "default"
        default_root.mkdir(parents=True, exist_ok=True)

        with mock.patch("novels_project.project_config.get_character_cards_path") as mock_cards, \
             mock.patch("novels_project.project_config.get_chapters_dir") as mock_chapters, \
             mock.patch("novels_project.project_config.get_project_root") as mock_root, \
             mock.patch.object(gmt, "EntityExtractor") as MockExtractor:
            mock_cards.return_value = "/default/cards.yaml"
            mock_chapters.return_value = "/default/chapters"
            mock_root.return_value = default_root

            gmt.build_knowledge_graph(character_cards_path="/custom/cards.yaml")
            # cards_path should NOT be called because we provided custom path
            mock_cards.assert_not_called()


# ==================== get_graph_stats ====================

class TestGetGraphStats:
    def test_success(self):
        store = make_mock_store()
        store.export_summary.return_value = "Graph Summary Content"
        gmt._global_graph_store = store
        result = gmt.get_graph_stats()
        assert result == "Graph Summary Content"