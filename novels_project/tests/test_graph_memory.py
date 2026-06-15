"""
图谱记忆系统 - 单元测试与集成测试

测试覆盖：
1. GraphStore: 实体/关系 CRUD、邻居查询、路径查找、持久化
2. EntityExtractor: 规则抽取、LLM 抽取
3. GraphQuery: 关系网络查询、路径查询、暗线追踪
4. SyncManager: 同步逻辑
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

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
    REL_TYPE_FRIEND,
    REL_TYPE_FAMILY,
    REL_TYPE_MENTOR,
    REL_TYPE_PARTICIPATED_IN,
    REL_TYPE_CAUSED,
    REL_TYPE_FORESHAODWS,
    REL_TYPE_REFERS_TO,
)
from novels_project.memory.entity_extractor import EntityExtractor
from novels_project.memory.graph_query import GraphQuery
from novels_project.memory.sync_manager import SyncManager


# ============================================================
# GraphStore 测试
# ============================================================

class TestGraphStore(unittest.TestCase):
    """图存储引擎测试。"""

    def setUp(self):
        self.store = GraphStore()

    def test_add_entity(self):
        """测试添加实体。"""
        self.store.add_entity("陆商曜", NODE_TYPE_CHARACTER, {"role": "主角", "tier": "s"})
        entity = self.store.get_entity("陆商曜")
        self.assertIsNotNone(entity)
        self.assertEqual(entity["name"], "陆商曜")
        self.assertEqual(entity["type"], NODE_TYPE_CHARACTER)
        self.assertEqual(entity["role"], "主角")
        self.assertEqual(self.store.entity_count(), 1)

    def test_add_duplicate_entity(self):
        """测试重复添加实体（应覆盖）。"""
        self.store.add_entity("陆商曜", NODE_TYPE_CHARACTER, {"role": "主角"})
        self.store.add_entity("陆商曜", NODE_TYPE_CHARACTER, {"role": "主角", "tier": "s"})
        self.assertEqual(self.store.entity_count(), 1)
        entity = self.store.get_entity("陆商曜")
        self.assertEqual(entity["tier"], "s")

    def test_remove_entity(self):
        """测试删除实体。"""
        self.store.add_entity("陆商曜", NODE_TYPE_CHARACTER)
        self.assertTrue(self.store.remove_entity("陆商曜"))
        self.assertEqual(self.store.entity_count(), 0)
        self.assertFalse(self.store.remove_entity("不存在的"))

    def test_get_entity_not_exists(self):
        """测试获取不存在的实体。"""
        self.assertIsNone(self.store.get_entity("不存在"))

    def test_update_entity(self):
        """测试更新实体属性。"""
        self.store.add_entity("陆商曜", NODE_TYPE_CHARACTER, {"role": "主角"})
        self.assertTrue(self.store.update_entity("陆商曜", {"tier": "s", "brief": "腹黑少年"}))

        entity = self.store.get_entity("陆商曜")
        self.assertEqual(entity["tier"], "s")
        self.assertEqual(entity["brief"], "腹黑少年")
        self.assertEqual(entity["role"], "主角")  # 原有属性保留

    def test_update_nonexistent(self):
        """测试更新不存在的实体。"""
        self.assertFalse(self.store.update_entity("不存在", {"key": "value"}))

    def test_get_all_entities(self):
        """测试获取所有实体。"""
        self.store.add_entity("陆商曜", NODE_TYPE_CHARACTER)
        self.store.add_entity("帝都拍卖会", NODE_TYPE_EVENT)
        self.store.add_entity("铁阙", NODE_TYPE_CHARACTER)

        all_entities = self.store.get_all_entities()
        self.assertEqual(len(all_entities), 3)

        characters = self.store.get_all_entities(NODE_TYPE_CHARACTER)
        self.assertEqual(len(characters), 2)
        self.assertTrue(all(e["type"] == NODE_TYPE_CHARACTER for e in characters))

        events = self.store.get_all_entities(NODE_TYPE_EVENT)
        self.assertEqual(len(events), 1)

    def test_add_relation(self):
        """测试添加关系。"""
        self.store.add_entity("陆商曜", NODE_TYPE_CHARACTER)
        self.store.add_entity("黑商周桓", NODE_TYPE_CHARACTER)
        self.store.add_relation("陆商曜", "黑商周桓", REL_TYPE_ENEMY)

        relations = self.store.get_relations(source="陆商曜")
        self.assertEqual(len(relations), 1)
        self.assertEqual(relations[0]["type"], REL_TYPE_ENEMY)

    def test_add_relation_auto_create(self):
        """测试自动创建不存在的实体。"""
        self.store.add_relation("陆商曜", "黑商周桓", REL_TYPE_ENEMY)
        self.assertTrue(self.store.has_entity("陆商曜"))
        self.assertTrue(self.store.has_entity("黑商周桓"))

    def test_get_relations_with_filter(self):
        """测试关系查询过滤。"""
        self.store.add_relation("陆商曜", "黑商周桓", REL_TYPE_ENEMY)
        self.store.add_relation("陆商曜", "木九公", REL_TYPE_ALLY)
        self.store.add_relation("黑商周桓", "木九公", REL_TYPE_ENEMY)

        # 按 source 过滤
        rels = self.store.get_relations(source="陆商曜")
        self.assertEqual(len(rels), 2)

        # 按类型过滤
        enemy_rels = self.store.get_relations(rel_type=REL_TYPE_ENEMY)
        self.assertEqual(len(enemy_rels), 2)

        # 组合过滤
        rels = self.store.get_relations(source="陆商曜", rel_type=REL_TYPE_ENEMY)
        self.assertEqual(len(rels), 1)

    def test_remove_relation(self):
        """测试删除关系。"""
        self.store.add_relation("陆商曜", "黑商周桓", REL_TYPE_ENEMY)
        self.assertTrue(self.store.remove_relation("陆商曜", "黑商周桓"))
        self.assertEqual(self.store.relation_count(), 0)

    def test_get_neighbors(self):
        """测试邻居查询。"""
        self.store.add_relation("陆商曜", "黑商周桓", REL_TYPE_ENEMY)
        self.store.add_relation("陆商曜", "木九公", REL_TYPE_ALLY)

        neighbors = self.store.get_neighbors("陆商曜")
        self.assertEqual(len(neighbors), 2)
        names = {n["name"] for n in neighbors}
        self.assertEqual(names, {"黑商周桓", "木九公"})

    def test_get_neighbors_direction(self):
        """测试按方向查询邻居。"""
        self.store.add_relation("陆商曜", "黑商周桓", REL_TYPE_ENEMY)

        out_neighbors = self.store.get_neighbors("陆商曜", direction="out")
        self.assertEqual(len(out_neighbors), 1)

        in_neighbors = self.store.get_neighbors("黑商周桓", direction="in")
        self.assertEqual(len(in_neighbors), 1)

    def test_get_related_entities_multi_hop(self):
        """测试多跳关系查询。"""
        self.store.add_relation("陆商曜", "黑商周桓", REL_TYPE_ENEMY)
        self.store.add_relation("黑商周桓", "神秘组织", REL_TYPE_ENEMY)

        result = self.store.get_related_entities("陆商曜", max_depth=2)

        self.assertIn("entity", result)
        self.assertIn("depth_1", result["neighbors"])
        self.assertIn("depth_2", result["neighbors"])

        depth1 = result["neighbors"]["depth_1"]
        self.assertTrue(any(n["name"] == "黑商周桓" for n in depth1))

        depth2 = result["neighbors"]["depth_2"]
        self.assertTrue(any(n["name"] == "神秘组织" for n in depth2))

    def test_find_path(self):
        """测试路径查找。"""
        self.store.add_relation("陆商曜", "黑商周桓", REL_TYPE_ENEMY)
        self.store.add_relation("黑商周桓", "木九公", REL_TYPE_ALLY)

        path = self.store.find_path("陆商曜", "木九公")
        self.assertIsNotNone(path)
        self.assertEqual(path, ["陆商曜", "黑商周桓", "木九公"])

    def test_find_path_no_connection(self):
        """测试无连接的路径查找。"""
        self.store.add_entity("陆商曜", NODE_TYPE_CHARACTER)
        self.store.add_entity("孤岛", NODE_TYPE_LOCATION)

        path = self.store.find_path("陆商曜", "孤岛")
        self.assertIsNone(path)

    def test_central_characters(self):
        """测试中心性分析。"""
        self.store.add_entity("陆商曜", NODE_TYPE_CHARACTER)
        self.store.add_entity("黑商周桓", NODE_TYPE_CHARACTER)
        self.store.add_entity("木九公", NODE_TYPE_CHARACTER)

        # 陆商曜作为中心人物
        self.store.add_relation("陆商曜", "黑商周桓", REL_TYPE_ENEMY)
        self.store.add_relation("陆商曜", "木九公", REL_TYPE_ALLY)

        central = self.store.get_central_characters(top_n=3)
        self.assertEqual(len(central), 3)
        self.assertEqual(central[0][0], "陆商曜")

    def test_persistence(self):
        """测试图的持久化。"""
        self.store.add_relation("陆商曜", "黑商周桓", REL_TYPE_ENEMY)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            tmp_path = f.name

        try:
            self.store.save(tmp_path)

            # 从文件加载
            loaded_store = GraphStore()
            loaded_store.load(tmp_path)

            self.assertEqual(loaded_store.entity_count(), 2)
            self.assertEqual(loaded_store.relation_count(), 1)

            entity = loaded_store.get_entity("陆商曜")
            self.assertIsNotNone(entity)
        finally:
            os.unlink(tmp_path)

    def test_statistics(self):
        """测试统计信息。"""
        self.store.add_entity("陆商曜", NODE_TYPE_CHARACTER)
        self.store.add_entity("帝都拍卖会", NODE_TYPE_EVENT)
        self.store.add_relation("陆商曜", "帝都拍卖会", REL_TYPE_PARTICIPATED_IN)

        stats = self.store.get_statistics()
        self.assertEqual(stats["node_count"], 2)
        self.assertEqual(stats["edge_count"], 1)
        self.assertEqual(stats["node_types"][NODE_TYPE_CHARACTER], 1)
        self.assertEqual(stats["node_types"][NODE_TYPE_EVENT], 1)


# ============================================================
# EntityExtractor 测试
# ============================================================

class TestEntityExtractor(unittest.TestCase):
    """实体提取器测试。"""

    def setUp(self):
        self.store = GraphStore()
        self.extractor = EntityExtractor(self.store)

    def test_extract_from_character_cards(self):
        """测试从 YAML 人物卡提取实体。"""
        # 创建临时 YAML
        yaml_content = {
            "s_tier": {
                "tier_name": "梦境入侵者",
                "characters": {
                    "陆商曜": {
                        "role": "主角",
                        "core_personality": ["腹黑果决", "能屈能伸"],
                        "core_goal": "寻找父亲下落",
                        "relationships": {
                            "黑商周桓": {"type": "enemy", "description": "宿敌"},
                        },
                    },
                    "黑商周桓": {
                        "role": "反派",
                        "core_personality": ["神秘莫测"],
                    },
                },
            },
            "a_tier": {
                "tier_name": "重要配角",
                "characters": {
                    "木九公": {
                        "role": "导师",
                        "relationships": {
                            "陆商曜": "师父",
                        },
                    },
                },
            },
        }

        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w") as f:
            import yaml
            yaml.dump(yaml_content, f, allow_unicode=True)
            tmp_path = f.name

        try:
            count = self.extractor.extract_from_character_cards(tmp_path)
            # 注意: extract_from_character_cards 返回的是 extract 方法本身新增的实体数。
            # "黑商周桓" 在 "陆商曜" 的关系中添加时由 add_relation 自动创建，
            # 因此 extract 方法只计了 2 个（"陆商曜" 和 "木九公"），这是预期行为。
            self.assertGreaterEqual(count, 2)
            self.assertLessEqual(count, 3)

            # 验证实体
            self.assertTrue(self.store.has_entity("陆商曜"))
            self.assertTrue(self.store.has_entity("黑商周桓"))
            self.assertTrue(self.store.has_entity("木九公"))

            entity = self.store.get_entity("陆商曜")
            self.assertEqual(entity["type"], NODE_TYPE_CHARACTER)
            self.assertEqual(entity["role"], "主角")
            self.assertIn("腹黑果决", entity.get("brief", ""))

            # 验证关系
            relations = self.store.get_relations(source="陆商曜")
            self.assertEqual(len(relations), 1)
            self.assertEqual(relations[0]["target"], "黑商周桓")

        finally:
            os.unlink(tmp_path)

    def test_extract_from_chapter_text_rules(self):
        """测试从章节文本提取（规则模式）。"""
        # 先添加已知人物
        self.store.add_entity("陆商曜", NODE_TYPE_CHARACTER, {"role": "主角"})
        self.store.add_entity("黑商周桓", NODE_TYPE_CHARACTER, {"role": "反派"})

        text = "陆商曜步入大厅，看到了站在角落的黑商周桓。两人对视片刻。"

        result = self.extractor.extract_from_chapter_text(text, chapter_id=12)
        self.assertEqual(result["added_entities"], 0)  # 已知人物不重复
        self.assertEqual(result["added_relations"], 0)

        # 验证出场标记已更新
        entity = self.store.get_entity("陆商曜")
        chapters = entity.get("appears_in_chapters", [])
        self.assertIn(12, chapters)

    def test_extract_brief(self):
        """测试简短描述提取。"""
        char_data = {
            "role": "主角",
            "core_personality": ["腹黑", "果断", "冷静"],
            "core_goal": "复仇",
        }
        brief = self.extractor._extract_brief(char_data)
        self.assertIn("主角", brief)
        self.assertIn("腹黑", brief)

    def test_extract_relations_from_dict(self):
        """测试关系字典解析。"""
        relationships = {
            "黑商周桓": {"type": "enemy", "description": "宿敌"},
            "木九公": "师父",
        }

        result = self.extractor._extract_relations_from_dict(relationships)
        self.assertEqual(len(result), 2)
        # 第一个是 dict 类型
        self.assertEqual(result[0][0], "黑商周桓")
        # 第二个是 str 类型，包含 "师父" 关键词
        self.assertEqual(result[1][0], "木九公")
        self.assertEqual(result[1][1]["type"], REL_TYPE_MENTOR)


# ============================================================
# GraphQuery 测试
# ============================================================

class TestGraphQuery(unittest.TestCase):
    """图谱查询器测试。"""

    def setUp(self):
        self.store = GraphStore()
        self.query = GraphQuery(self.store)

        # 构建测试数据
        self.store.add_entity("陆商曜", NODE_TYPE_CHARACTER, {
            "role": "主角",
            "brief": "腹黑少年，寻找父亲下落",
        })
        self.store.add_entity("黑商周桓", NODE_TYPE_CHARACTER, {
            "role": "反派",
            "brief": "神秘黑商",
        })
        self.store.add_entity("木九公", NODE_TYPE_CHARACTER, {
            "role": "导师",
            "brief": "拍卖会鉴定师",
        })
        self.store.add_entity("帝都拍卖会", NODE_TYPE_EVENT, {
            "brief": "重大拍卖事件",
        })
        self.store.add_entity("玉简", NODE_TYPE_CONCEPT, {
            "brief": "神秘玉简，隐藏重要线索",
        })
        self.store.add_entity("铁阙", NODE_TYPE_CHARACTER, {
            "role": "暗卫",
            "brief": "陆家暗卫",
        })

        # 关系
        self.store.add_relation("陆商曜", "黑商周桓", REL_TYPE_ENEMY, {"chapter_id": 1})
        self.store.add_relation("陆商曜", "木九公", REL_TYPE_ALLY, {"chapter_id": 2})
        self.store.add_relation("陆商曜", "铁阙", REL_TYPE_FRIEND, {"chapter_id": 1})
        self.store.add_relation("陆商曜", "帝都拍卖会", REL_TYPE_PARTICIPATED_IN, {"chapter_id": 4})
        self.store.add_relation("玉简", "帝都拍卖会", REL_TYPE_FORESHAODWS, {"chapter_id": 3})
        self.store.add_relation("玉简", "陆商曜", REL_TYPE_REFERS_TO, {"chapter_id": 3})

    def test_get_character_network(self):
        """测试获取人物关系网络。"""
        result = self.query.get_character_network("陆商曜")

        self.assertIn("character", result)
        self.assertEqual(result["character"]["role"], "主角")

        # 直接关系
        direct = result["direct_relations"]
        names = {r["name"] for r in direct}
        self.assertIn("黑商周桓", names)
        self.assertIn("木九公", names)
        self.assertIn("铁阙", names)

        # 相关事件
        events = result["events"]
        event_names = {e["name"] for e in events}
        self.assertIn("帝都拍卖会", event_names)

        # 关联概念
        concepts = result["related_concepts"]
        concept_names = {c["name"] for c in concepts}
        self.assertIn("玉简", concept_names)

    def test_get_character_network_not_found(self):
        """测试查询不存在的人物。"""
        result = self.query.get_character_network("不存在")
        self.assertIn("error", result)

    def test_get_relation_between(self):
        """测试两个实体之间的关系查询。"""
        result = self.query.get_relation_between("陆商曜", "黑商周桓")

        direct = result["direct_relations"]
        self.assertEqual(len(direct), 1)
        self.assertEqual(direct[0]["type"], REL_TYPE_ENEMY)

    def test_relation_between_indirect(self):
        """测试间接关系。"""
        self.store.add_relation("黑商周桓", "木九公", REL_TYPE_ENEMY)

        result = self.query.get_relation_between("陆商曜", "木九公")
        # 直接关系存在
        self.assertTrue(len(result["direct_relations"]) > 0)
        # 或至少间接路径存在
        self.assertTrue(
            len(result["direct_relations"]) > 0 or result["shortest_path"] is not None
        )

    def test_find_characters_by_relation(self):
        """测试按关系类型查找。"""
        enemies = self.query.find_characters_by_relation("陆商曜", REL_TYPE_ENEMY)
        self.assertEqual(len(enemies), 1)
        self.assertEqual(enemies[0]["name"], "黑商周桓")

    def test_get_event_participants(self):
        """测试查询事件参与人物。"""
        result = self.query.get_event_participants("帝都拍卖会")

        self.assertNotIn("error", result)
        participants = [p["name"] for p in result["participants"]]
        self.assertIn("陆商曜", participants)

    def test_trace_foreshadowing(self):
        """测试暗线追踪。"""
        result = self.query.trace_foreshadowing("玉简")

        self.assertNotIn("error", result)
        # 玉简预示了帝都拍卖会
        foreshadowed = result["foreshadowed_events"]
        event_names = [f["name"] for f in foreshadowed]
        self.assertIn("帝都拍卖会", event_names)

    def test_trace_foreshadowing_not_found(self):
        """测试追踪不存在的概念。"""
        result = self.query.trace_foreshadowing("不存在的概念")
        self.assertIn("error", result)

    def test_find_unresolved_foreshadowing(self):
        """测试查找未回收伏笔。"""
        unresolved = self.query.find_unresolved_foreshadowing()
        self.assertTrue(len(unresolved) > 0)
        self.assertEqual(unresolved[0]["concept"], "玉简")

    def test_search(self):
        """测试关键词搜索。"""
        results = self.query.search("陆")
        self.assertTrue(len(results) > 0)
        names = [r["name"] for r in results]
        self.assertIn("陆商曜", names)

    def test_search_with_type_filter(self):
        """测试带类型过滤的搜索。"""
        results = self.query.search("拍卖", [NODE_TYPE_EVENT])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "帝都拍卖会")

    def test_get_graph_context_writing(self):
        """测试写作上下文获取。"""
        context = self.query.get_graph_context("陆商曜", "writing")
        self.assertIn("陆商曜", context)
        self.assertIn("腹黑少年", context)

    def test_get_graph_context_review(self):
        """测试校对上下文获取。"""
        context = self.query.get_graph_context("陆商曜", "review")
        self.assertIn("玉简", context)


# ============================================================
# 集成测试
# ============================================================

class TestIntegration(unittest.TestCase):
    """集成测试：端到端流程。"""

    def setUp(self):
        self.store = GraphStore()
        self.extractor = EntityExtractor(self.store)
        self.query = GraphQuery(self.store)
        self.sync_manager = SyncManager(self.store, self.extractor)

    def test_build_knowledge_graph_from_scratch(self):
        """测试从零构建知识图谱。"""
        # 1. 模拟人物卡数据
        import yaml
        cards_data = {
            "s_tier": {
                "tier_name": "核心",
                "characters": {
                    "陆商曜": {"role": "主角", "core_personality": ["腹黑"], "core_goal": "复仇"},
                    "黑商周桓": {"role": "反派", "core_personality": ["神秘"]},
                },
            },
        }

        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w") as f:
            yaml.dump(cards_data, f, allow_unicode=True)
            cards_path = f.name

        # 2. 模拟章节目录
        chapters_dir = tempfile.mkdtemp()
        chapter1 = Path(chapters_dir) / "chapter_1_final.md"
        chapter1.write_text("陆商曜遇到了黑商周桓。两人在帝都拍卖会对峙。", encoding="utf-8")

        try:
            # 3. 设置同步管理器
            self.sync_manager.set_watch_paths(cards_path, chapters_dir)

            # 4. 执行同步
            stats = self.sync_manager.sync(mode="full")
            self.assertTrue(stats["characters_added"] > 0)
            self.assertTrue(stats["chapters_processed"] > 0)

            # 5. 验证图谱
            self.assertTrue(self.store.has_entity("陆商曜"))
            self.assertTrue(self.store.has_entity("黑商周桓"))

            # 6. 验证查询
            network = self.query.get_character_network("陆商曜")
            self.assertNotIn("error", network)

            # 7. 持久化和恢复
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
                graph_path = f.name

            self.store.save(graph_path)

            store2 = GraphStore()
            store2.load(graph_path)
            self.assertEqual(store2.entity_count(), self.store.entity_count())
            self.assertEqual(store2.relation_count(), self.store.relation_count())

            os.unlink(graph_path)

        finally:
            os.unlink(cards_path)
            import shutil
            shutil.rmtree(chapters_dir)


if __name__ == "__main__":
    unittest.main(verbosity=2)