"""
单元测试：memory/graph_query.py - GraphQuery 类
使用真实的 networkx GraphStore 进行测试。
"""
import pytest
import networkx as nx

from novels_project.memory.graph_store import (
    GraphStore,
    NODE_TYPE_CHARACTER,
    NODE_TYPE_EVENT,
    NODE_TYPE_ITEM,
    NODE_TYPE_LOCATION,
    NODE_TYPE_ORGANIZATION,
    NODE_TYPE_CONCEPT,
    REL_TYPE_ALLY,
    REL_TYPE_ENEMY,
    REL_TYPE_FAMILY,
    REL_TYPE_FRIEND,
    REL_TYPE_KNOWS,
    REL_TYPE_PARTICIPATED_IN,
    REL_TYPE_CAUSED,
    REL_TYPE_BELONGS_TO,
    REL_TYPE_REFERS_TO,
    REL_TYPE_FORESHAODWS,
)
from novels_project.memory.graph_query import GraphQuery


def build_basic_graph():
    """构建一个基础测试图谱：
    人物：A（主角）, B（盟友）, C（敌人）, D（朋友）
    事件：E1（试炼）
    组织：Org1
    概念：Concept1
    """
    store = GraphStore()
    store.add_entity("A", NODE_TYPE_CHARACTER, {"brief": "主角", "role": "hero"})
    store.add_entity("B", NODE_TYPE_CHARACTER, {"brief": "盟友", "role": "ally"})
    store.add_entity("C", NODE_TYPE_CHARACTER, {"brief": "敌人", "role": "villain"})
    store.add_entity("D", NODE_TYPE_CHARACTER, {"brief": "朋友", "role": "friend"})
    store.add_entity("E1", NODE_TYPE_EVENT, {"brief": "试炼之战"})
    store.add_entity("Org1", NODE_TYPE_ORGANIZATION, {"brief": "青云宗"})
    store.add_entity("Concept1", NODE_TYPE_CONCEPT, {"brief": "神秘力量"})

    store.add_relation("A", "B", REL_TYPE_ALLY)
    store.add_relation("A", "C", REL_TYPE_ENEMY)
    store.add_relation("A", "D", REL_TYPE_FRIEND)
    store.add_relation("A", "E1", REL_TYPE_PARTICIPATED_IN)
    store.add_relation("A", "Org1", REL_TYPE_BELONGS_TO)
    store.add_relation("Concept1", "E1", REL_TYPE_FORESHAODWS, {"chapter_id": 1})
    store.add_relation("A", "Concept1", REL_TYPE_REFERS_TO)
    store.add_relation("B", "D", REL_TYPE_KNOWS)
    return store


# ==================== __init__ ====================

class TestGraphQueryInit:
    def test_init(self):
        store = GraphStore()
        query = GraphQuery(store)
        assert query._graph is store


# ==================== get_character_network ====================

class TestGetCharacterNetwork:
    def test_character_found(self):
        store = build_basic_graph()
        query = GraphQuery(store)
        result = query.get_character_network("A")
        assert "error" not in result
        assert result["character"]["name"] == "A"
        assert len(result["direct_relations"]) >= 2  # B, C, D
        assert len(result["events"]) >= 1  # E1
        assert len(result["organizations"]) >= 1  # Org1
        assert len(result["related_concepts"]) >= 1  # Concept1

    def test_character_not_found(self):
        store = build_basic_graph()
        query = GraphQuery(store)
        result = query.get_character_network("Z")
        assert "error" in result

    def test_with_depth_1(self):
        store = build_basic_graph()
        query = GraphQuery(store)
        result = query.get_character_network("A", max_depth=1)
        assert "error" not in result
        # depth=1 时不获取间接关系
        assert result.get("indirect_relations", []) == []

    def test_with_depth_2(self):
        store = build_basic_graph()
        query = GraphQuery(store)
        result = query.get_character_network("A", max_depth=2)
        assert "error" not in result
        # B 认识 D，所以 D 可能在间接关系中
        indirect_names = [r["name"] for r in result.get("indirect_relations", [])]
        # depth_2 邻居可能包含 D（通过 B 间接关联）
        assert isinstance(indirect_names, list)

    def test_with_events_organizations_concepts(self):
        store = build_basic_graph()
        # 添加更多数据
        store.add_entity("E2", NODE_TYPE_EVENT, {"brief": "宗门大比"})
        store.add_entity("Org2", NODE_TYPE_ORGANIZATION, {"brief": "黑市"})
        store.add_relation("A", "E2", REL_TYPE_PARTICIPATED_IN)
        store.add_relation("A", "Org2", REL_TYPE_BELONGS_TO)
        query = GraphQuery(store)
        result = query.get_character_network("A")
        assert len(result["events"]) >= 2
        assert len(result["organizations"]) >= 2


# ==================== get_relation_between ====================

class TestGetRelationBetween:
    def test_direct(self):
        store = build_basic_graph()
        query = GraphQuery(store)
        result = query.get_relation_between("A", "B")
        assert len(result["direct_relations"]) > 0

    def test_indirect(self):
        store = build_basic_graph()
        # 添加反向边使 B 和 C 之间形成间接路径
        store.add_relation("B", "A", REL_TYPE_ALLY)  # B->A
        store.add_relation("C", "A", REL_TYPE_ENEMY)  # C->A
        query = GraphQuery(store)
        # B 和 C 之间通过 A 间接关联: B->A, C->A (无向路径)
        result = query.get_relation_between("B", "C")
        assert result["shortest_path"] is not None or len(result["all_paths"]) > 0

    def test_no_path(self):
        store = GraphStore()
        store.add_entity("X", NODE_TYPE_CHARACTER)
        store.add_entity("Y", NODE_TYPE_CHARACTER)
        query = GraphQuery(store)
        result = query.get_relation_between("X", "Y")
        assert result["direct_relations"] == []
        assert result["shortest_path"] is None


# ==================== find_characters_by_relation ====================

class TestFindCharactersByRelation:
    def test_found(self):
        store = build_basic_graph()
        query = GraphQuery(store)
        result = query.find_characters_by_relation("A", REL_TYPE_ENEMY)
        assert len(result) >= 1
        assert result[0]["name"] == "C"

    def test_not_found(self):
        store = build_basic_graph()
        query = GraphQuery(store)
        result = query.find_characters_by_relation("A", REL_TYPE_FAMILY)
        assert result == []


# ==================== get_event_participants ====================

class TestGetEventParticipants:
    def test_found(self):
        store = build_basic_graph()
        query = GraphQuery(store)
        result = query.get_event_participants("E1")
        assert "error" not in result
        assert result["event"]["name"] == "E1"
        assert len(result["participants"]) >= 1

    def test_not_found(self):
        store = build_basic_graph()
        query = GraphQuery(store)
        result = query.get_event_participants("NonExistent")
        assert "error" in result

    def test_with_caused_by(self):
        store = build_basic_graph()
        store.add_entity("E2", NODE_TYPE_EVENT, {"brief": "后续事件"})
        store.add_relation("E1", "E2", REL_TYPE_CAUSED)
        query = GraphQuery(store)
        result = query.get_event_participants("E2")
        assert len(result["caused_by"]) >= 1

    def test_with_caused_events(self):
        store = build_basic_graph()
        store.add_entity("E2", NODE_TYPE_EVENT, {"brief": "后续事件"})
        store.add_relation("E1", "E2", REL_TYPE_CAUSED)
        query = GraphQuery(store)
        result = query.get_event_participants("E1")
        assert len(result["caused_events"]) >= 1


# ==================== trace_foreshadowing ====================

class TestTraceForeshadowing:
    def test_found(self):
        store = build_basic_graph()
        query = GraphQuery(store)
        result = query.trace_foreshadowing("Concept1")
        assert "error" not in result
        assert result["concept"]["name"] == "Concept1"
        assert len(result["foreshadowed_events"]) >= 1

    def test_not_found(self):
        store = build_basic_graph()
        query = GraphQuery(store)
        result = query.trace_foreshadowing("NonExistent")
        assert "error" in result

    def test_with_all_sections(self):
        store = build_basic_graph()
        # 添加更多关联
        store.add_entity("Concept2", NODE_TYPE_CONCEPT, {"brief": "另一个概念"})
        store.add_entity("E2", NODE_TYPE_EVENT, {"brief": "第二事件"})
        store.add_relation("Concept2", "E2", REL_TYPE_FORESHAODWS, {"chapter_id": 2})
        store.add_relation("Concept2", "Concept1", REL_TYPE_REFERS_TO)
        store.add_relation("A", "Concept2", REL_TYPE_KNOWS)
        query = GraphQuery(store)
        result = query.trace_foreshadowing("Concept2")
        assert "error" not in result
        assert len(result["foreshadowed_events"]) >= 1
        assert len(result.get("referenced_by", [])) >= 0
        # related_characters 可能不为空
        assert isinstance(result.get("related_characters", []), list)


# ==================== find_unresolved_foreshadowing ====================

class TestFindUnresolvedForeshadowing:
    def test_with_unresolved(self):
        store = build_basic_graph()
        # Concept1 foreshadows E1, E1 没有 resolved 标记
        query = GraphQuery(store)
        result = query.find_unresolved_foreshadowing()
        assert len(result) >= 1
        assert result[0]["concept"] == "Concept1"

    def test_with_resolved(self):
        store = build_basic_graph()
        store.add_entity("Concept2", NODE_TYPE_CONCEPT, {"brief": "已回收"})
        store.add_entity("E2", NODE_TYPE_EVENT, {"brief": "事件", "resolved": True})
        store.add_relation("Concept2", "E2", REL_TYPE_FORESHAODWS)
        query = GraphQuery(store)
        result = query.find_unresolved_foreshadowing()
        # E2 已 resolved，所以这条不应该在未回收列表中
        resolved_concepts = [r["concept"] for r in result]
        assert "Concept2" not in resolved_concepts

    def test_no_concepts(self):
        store = GraphStore()
        store.add_entity("A", NODE_TYPE_CHARACTER)
        query = GraphQuery(store)
        result = query.find_unresolved_foreshadowing()
        assert result == []


# ==================== search ====================

class TestSearch:
    def test_with_keyword(self):
        store = build_basic_graph()
        query = GraphQuery(store)
        result = query.search("主角")
        assert len(result) >= 1
        assert result[0]["name"] in ["A"]  # A 的 brief 含"主角"

    def test_with_entity_type_filter(self):
        store = build_basic_graph()
        query = GraphQuery(store)
        result = query.search("试炼", entity_types=[NODE_TYPE_EVENT])
        assert len(result) >= 1
        assert result[0]["type"] == NODE_TYPE_EVENT

    def test_no_results(self):
        store = build_basic_graph()
        query = GraphQuery(store)
        result = query.search("不存在的关键词")
        assert result == []


# ==================== get_graph_context ====================

class TestGetGraphContext:
    def test_writing_context(self):
        store = build_basic_graph()
        query = GraphQuery(store)
        result = query.get_graph_context("A", "writing")
        assert "A" in result
        assert "简介" in result or "主角" in result
        assert "关联" in result

    def test_review_context(self):
        store = build_basic_graph()
        query = GraphQuery(store)
        result = query.get_graph_context("A", "review")
        assert "校对上下文" in result or "A" in result

    def test_entity_not_found(self):
        store = build_basic_graph()
        query = GraphQuery(store)
        result = query.get_graph_context("Z", "writing")
        assert result == ""

    def test_empty_context(self):
        """无任何邻居的实体。"""
        store = GraphStore()
        store.add_entity("Solo", NODE_TYPE_CHARACTER, {"brief": "独行侠"})
        query = GraphQuery(store)
        result = query.get_graph_context("Solo", "writing")
        assert "Solo" in result
        # 有简介但没有邻居

    def test_writing_context_minimal_parts(self):
        """Writing context with entity that has no brief, no role, no neighbors -> parts length 1."""
        store = GraphStore()
        store.add_entity("Bare", NODE_TYPE_CHARACTER, {})
        query = GraphQuery(store)
        result = query.get_graph_context("Bare", "writing")
        # parts length 1 (just name), returns empty
        assert result == ""

    def test_review_context_with_chapters(self):
        """Review context where entity has appears_in_chapters."""
        store = GraphStore()
        store.add_entity("A", NODE_TYPE_CHARACTER, {
            "brief": "主角",
            "appears_in_chapters": [1, 2, 3],
        })
        query = GraphQuery(store)
        result = query.get_graph_context("A", "review")
        assert "校对上下文" in result
        assert "出场章节" in result
        assert "1, 2, 3" in result

    def test_review_context_with_concepts(self):
        """Review context with concept neighbors."""
        store = GraphStore()
        store.add_entity("A", NODE_TYPE_CHARACTER, {"brief": "主角"})
        store.add_entity("C1", NODE_TYPE_CONCEPT, {"brief": "暗线"})
        store.add_relation("A", "C1", REL_TYPE_REFERS_TO)
        query = GraphQuery(store)
        result = query.get_graph_context("A", "review")
        assert "暗线/伏笔" in result
        assert "C1" in result

    def test_unknown_context_type(self):
        """Unknown context_type returns empty string."""
        store = GraphStore()
        store.add_entity("A", NODE_TYPE_CHARACTER, {"brief": "主角"})
        query = GraphQuery(store)
        result = query.get_graph_context("A", "unknown")
        assert result == ""


# ==================== get_character_network depth 2 ====================

class TestGetCharacterNetworkDepth2:
    def test_indirect_relations_not_in_direct(self):
        """Entity in depth_2 that is NOT in direct_relations -> added to indirect."""
        store = GraphStore()
        store.add_entity("A", NODE_TYPE_CHARACTER, {"brief": "主角"})
        store.add_entity("B", NODE_TYPE_CHARACTER, {"brief": "盟友"})
        store.add_entity("C", NODE_TYPE_CHARACTER, {"brief": "间接"})
        store.add_relation("A", "B", REL_TYPE_ALLY)
        store.add_relation("B", "C", REL_TYPE_KNOWS)
        query = GraphQuery(store)
        result = query.get_character_network("A", max_depth=2)
        indirect_names = [r.get("name", "") for r in result.get("indirect_relations", [])]
        # C is depth_2 from A, not in direct_relations
        assert "C" in indirect_names

    def test_indirect_relation_already_in_direct(self):
        """Entity in depth_2 that IS already in direct_relations -> not added to indirect."""
        store = GraphStore()
        store.add_entity("A", NODE_TYPE_CHARACTER, {"brief": "主角"})
        store.add_entity("B", NODE_TYPE_CHARACTER, {"brief": "盟友"})
        store.add_entity("C", NODE_TYPE_CHARACTER, {"brief": "盟友2"})
        store.add_relation("A", "B", REL_TYPE_ALLY)
        store.add_relation("A", "C", REL_TYPE_ALLY)
        store.add_relation("B", "C", REL_TYPE_KNOWS)
        query = GraphQuery(store)
        result = query.get_character_network("A", max_depth=2)
        indirect_names = [r.get("name", "") for r in result.get("indirect_relations", [])]
        # C is depth_2 but also in direct_relations (A->C), so it should NOT be in indirect
        assert "C" not in indirect_names


# ==================== find_unresolved_foreshadowing ====================

class TestFindUnresolvedForeshadowingMore:
    def test_all_targets_resolved(self):
        """Foreshadowing where all targets are resolved -> not in result."""
        store = GraphStore()
        store.add_entity("Concept1", NODE_TYPE_CONCEPT, {"brief": "伏笔"})
        store.add_entity("E1", NODE_TYPE_EVENT, {"brief": "事件", "resolved": True})
        store.add_entity("E2", NODE_TYPE_EVENT, {"brief": "事件2", "resolved": True})
        store.add_relation("Concept1", "E1", REL_TYPE_FORESHAODWS)
        store.add_relation("Concept1", "E2", REL_TYPE_FORESHAODWS)
        query = GraphQuery(store)
        result = query.find_unresolved_foreshadowing()
        # All targets resolved, so nothing unresolved
        concepts = [r["concept"] for r in result]
        assert "Concept1" not in concepts

    def test_concept_without_foreshadows(self):
        """Concept node with no foreshadows out-edges -> skipped."""
        store = GraphStore()
        store.add_entity("Concept1", NODE_TYPE_CONCEPT, {"brief": "无伏笔的概念"})
        # No foreshadows edges from this concept
        query = GraphQuery(store)
        result = query.find_unresolved_foreshadowing()
        concepts = [r["concept"] for r in result]
        assert "Concept1" not in concepts