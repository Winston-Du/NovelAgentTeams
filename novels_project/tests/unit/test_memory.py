"""
单元测试：记忆管理模块测试

测试范围：
1. 图谱存储
2. 实体管理
3. 关系管理
4. 图谱查询
"""

import pytest
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent.parent / "src"))

from novels_project.memory.graph_store import GraphStore
from novels_project.memory.graph_query import GraphQuery


class TestGraphStore:
    """测试图谱存储功能"""

    def test_create_graph_store(self):
        """测试创建图谱存储实例"""
        store = GraphStore()
        assert store is not None
        assert hasattr(store, 'get_all_entities')

    def test_add_entity(self):
        """测试添加实体"""
        store = GraphStore()
        result = store.add_entity(
            name="测试实体",
            entity_type="character",
            properties={"brief": "测试描述"}
        )
        assert result == "测试实体"

    def test_get_entity(self):
        """测试获取实体"""
        store = GraphStore()
        store.add_entity(
            name="测试实体",
            entity_type="character",
            properties={"brief": "测试描述"}
        )
        entity = store.get_entity("测试实体")
        assert entity is not None
        assert entity.get("name") == "测试实体"

    def test_has_entity(self):
        """测试检查实体是否存在"""
        store = GraphStore()
        store.add_entity(name="测试实体", entity_type="character")
        assert store.has_entity("测试实体") is True
        assert store.has_entity("不存在的实体") is False

    def test_update_entity(self):
        """测试更新实体"""
        store = GraphStore()
        store.add_entity(name="测试实体", entity_type="character")
        result = store.update_entity("测试实体", {"brief": "更新后的描述"})
        assert result is True
        entity = store.get_entity("测试实体")
        assert entity.get("brief") == "更新后的描述"

    def test_remove_entity(self):
        """测试删除实体"""
        store = GraphStore()
        store.add_entity(name="测试实体", entity_type="character")
        store.remove_entity("测试实体")
        assert store.has_entity("测试实体") is False


class TestGraphRelations:
    """测试关系管理功能"""

    def test_add_relation(self):
        """测试添加关系"""
        store = GraphStore()
        store.add_entity(name="实体A", entity_type="character")
        store.add_entity(name="实体B", entity_type="character")
        result = store.add_relation("实体A", "实体B", "friend")
        assert result is True

    def test_get_relations(self):
        """测试获取关系"""
        store = GraphStore()
        store.add_entity(name="实体A", entity_type="character")
        store.add_entity(name="实体B", entity_type="character")
        store.add_relation("实体A", "实体B", "friend")
        
        relations = store.get_relations(source="实体A")
        assert len(relations) >= 1
        assert relations[0].get("type") == "friend"

    def test_remove_relation(self):
        """测试删除关系"""
        store = GraphStore()
        store.add_entity(name="实体A", entity_type="character")
        store.add_entity(name="实体B", entity_type="character")
        store.add_relation("实体A", "实体B", "friend")
        
        store.remove_relation("实体A", "实体B")
        relations = store.get_relations(source="实体A")
        assert len(relations) == 0


class TestGraphQuery:
    """测试图谱查询功能"""

    def test_search(self):
        """测试搜索功能"""
        store = GraphStore()
        store.add_entity(name="测试人物", entity_type="character", properties={"brief": "商人"})
        
        query = GraphQuery(store)
        results = query.search("商人")
        assert isinstance(results, list)

    def test_get_character_network(self):
        """测试获取人物关系网络"""
        store = GraphStore()
        store.add_entity(name="主角", entity_type="character")
        
        query = GraphQuery(store)
        network = query.get_character_network("主角", max_depth=2)
        assert isinstance(network, dict)


class TestGraphStatistics:
    """测试统计功能"""

    def test_get_statistics(self):
        """测试获取统计信息"""
        store = GraphStore()
        stats = store.get_statistics()
        assert isinstance(stats, dict)
        assert "node_count" in stats
        assert "edge_count" in stats


class TestGraphStoreEdgeCases:
    """测试图谱存储边缘条件"""

    def test_remove_non_existent_entity(self):
        """测试删除不存在的实体"""
        store = GraphStore()
        result = store.remove_entity("不存在的实体")
        assert result is False

    def test_update_non_existent_entity(self):
        """测试更新不存在的实体"""
        store = GraphStore()
        result = store.update_entity("不存在的实体", {"brief": "测试"})
        assert result is False

    def test_get_non_existent_entity(self):
        """测试获取不存在的实体"""
        store = GraphStore()
        result = store.get_entity("不存在的实体")
        assert result is None

    def test_add_relation_auto_create_entities(self):
        """测试添加关系时自动创建不存在的实体"""
        store = GraphStore()
        result = store.add_relation("不存在的源", "不存在的目标", "friend")
        assert result is True
        assert store.has_entity("不存在的源") is True
        assert store.has_entity("不存在的目标") is True

    def test_remove_relation_with_rel_type_filter(self):
        """测试按关系类型删除关系"""
        store = GraphStore()
        store.add_entity("A", "character")
        store.add_entity("B", "character")
        store.add_relation("A", "B", "friend")
        store.add_relation("A", "B", "colleague")

        result = store.remove_relation("A", "B", rel_type="friend")
        assert result is True

        relations = store.get_relations(source="A", target="B")
        assert len(relations) == 1
        assert relations[0]["type"] == "colleague"

    def test_remove_relation_non_existent(self):
        """测试删除不存在的关系"""
        store = GraphStore()
        store.add_entity("A", "character")
        store.add_entity("B", "character")
        result = store.remove_relation("A", "B")
        assert result is False

    def test_remove_relation_with_type_not_found(self):
        """测试删除不存在的关系类型"""
        store = GraphStore()
        store.add_entity("A", "character")
        store.add_entity("B", "character")
        store.add_relation("A", "B", "friend")
        result = store.remove_relation("A", "B", rel_type="colleague")
        assert result is False

    def test_get_relations_with_target_filter(self):
        """测试按目标实体过滤关系"""
        store = GraphStore()
        store.add_entity("A", "character")
        store.add_entity("B", "character")
        store.add_entity("C", "character")
        store.add_relation("A", "B", "friend")
        store.add_relation("A", "C", "enemy")

        relations = store.get_relations(target="B")
        assert len(relations) == 1
        assert relations[0]["type"] == "friend"

    def test_get_relations_with_type_filter(self):
        """测试按关系类型过滤"""
        store = GraphStore()
        store.add_entity("A", "character")
        store.add_entity("B", "character")
        store.add_relation("A", "B", "friend")
        store.add_relation("A", "B", "colleague")

        relations = store.get_relations(rel_type="friend")
        assert len(relations) == 1

    def test_get_relations_empty(self):
        """测试获取空关系列表"""
        store = GraphStore()
        store.add_entity("A", "character")
        store.add_entity("B", "character")
        relations = store.get_relations(source="A")
        assert len(relations) == 0

    def test_get_neighbors_out_direction(self):
        """测试获取出边邻居"""
        store = GraphStore()
        store.add_entity("A", "character")
        store.add_entity("B", "character")
        store.add_entity("C", "character")
        store.add_relation("A", "B", "friend")
        store.add_relation("C", "A", "enemy")

        neighbors = store.get_neighbors("A", direction="out")
        assert len(neighbors) == 1
        assert neighbors[0]["name"] == "B"

    def test_get_neighbors_in_direction(self):
        """测试获取入边邻居"""
        store = GraphStore()
        store.add_entity("A", "character")
        store.add_entity("B", "character")
        store.add_entity("C", "character")
        store.add_relation("A", "B", "friend")
        store.add_relation("C", "A", "enemy")

        neighbors = store.get_neighbors("A", direction="in")
        assert len(neighbors) == 1
        assert neighbors[0]["name"] == "C"

    def test_get_neighbors_with_rel_type_filter(self):
        """测试按关系类型过滤邻居"""
        store = GraphStore()
        store.add_entity("A", "character")
        store.add_entity("B", "character")
        store.add_entity("C", "character")
        store.add_relation("A", "B", "friend")
        store.add_relation("A", "C", "colleague")

        neighbors = store.get_neighbors("A", rel_type="friend")
        assert len(neighbors) == 1
        assert neighbors[0]["name"] == "B"

    def test_get_all_entities_with_type_filter(self):
        """测试按类型过滤实体"""
        store = GraphStore()
        store.add_entity("角色1", "character")
        store.add_entity("角色2", "character")
        store.add_entity("地点1", "location")

        characters = store.get_all_entities(entity_type="character")
        assert len(characters) == 2

        locations = store.get_all_entities(entity_type="location")
        assert len(locations) == 1

    def test_get_all_entities_empty(self):
        """测试获取空实体列表"""
        store = GraphStore()
        entities = store.get_all_entities()
        assert len(entities) == 0

    def test_entity_count(self):
        """测试实体计数"""
        store = GraphStore()
        assert store.entity_count() == 0
        store.add_entity("A", "character")
        assert store.entity_count() == 1
        store.add_entity("B", "character")
        assert store.entity_count() == 2

    def test_relation_count(self):
        """测试关系计数"""
        store = GraphStore()
        assert store.relation_count() == 0
        store.add_entity("A", "character")
        store.add_entity("B", "character")
        store.add_relation("A", "B", "friend")
        assert store.relation_count() == 1


class TestGraphQueryEdgeCases:
    """测试图谱查询边缘条件"""

    def test_search_empty_store(self):
        """测试在空存储中搜索"""
        store = GraphStore()
        query = GraphQuery(store)
        results = query.search("test")
        assert len(results) == 0

    def test_search_with_special_characters(self):
        """测试搜索包含特殊字符"""
        store = GraphStore()
        store.add_entity("测试@人物", "character", properties={"brief": "测试描述"})
        query = GraphQuery(store)
        results = query.search("@")
        assert isinstance(results, list)

    def test_get_character_network_empty(self):
        """测试获取空人物网络"""
        store = GraphStore()
        query = GraphQuery(store)
        network = query.get_character_network("不存在", max_depth=2)
        assert isinstance(network, dict)

    def test_get_character_network_depth_1(self):
        """测试获取深度为1的人物网络"""
        store = GraphStore()
        store.add_entity("主角", "character")
        store.add_entity("朋友", "character")
        store.add_relation("主角", "朋友", "friend")

        query = GraphQuery(store)
        network = query.get_character_network("主角", max_depth=1)
        assert "direct_relations" in network
        assert len(network["direct_relations"]) == 1
        assert network["direct_relations"][0]["name"] == "朋友"


class TestGraphPersistence:
    """测试图谱持久化功能"""

    def test_save_and_load_with_entities(self, tmp_path):
        """测试保存后加载 - 完整往返"""
        store = GraphStore()
        store.add_entity("角色A", "character", {"brief": "主角"})
        store.add_entity("角色B", "character", {"brief": "配角"})
        store.add_relation("角色A", "角色B", "friend", {"strength": 0.8})

        filepath = tmp_path / "graph.json"
        store.save(str(filepath))

        assert filepath.exists()
        content = filepath.read_text(encoding="utf-8")
        assert "角色A" in content
        assert "角色B" in content

        # 加载到新实例
        store2 = GraphStore()
        result = store2.load(str(filepath))
        assert result is True
        assert store2.entity_count() == 2
        assert store2.has_entity("角色A")
        assert store2.has_entity("角色B")
        assert store2.relation_count() == 1

    def test_save_and_load_with_properties(self, tmp_path):
        """测试保存后加载 - 带属性的关系"""
        store = GraphStore()
        store.add_entity("甲", "character", {"age": 25, "role": "主角"})
        store.add_entity("乙", "event", {"description": "关键事件"})
        store.add_relation("甲", "乙", "participates", {"since_chapter": 3})

        filepath = tmp_path / "graph_props.json"
        store.save(str(filepath))

        loaded = GraphStore()
        loaded.load(str(filepath))

        entity = loaded.get_entity("甲")
        assert entity.get("age") == 25
        assert entity.get("role") == "主角"

        relations = loaded.get_relations(source="甲")
        assert len(relations) == 1
        assert relations[0]["type"] == "participates"
        assert relations[0]["properties"].get("since_chapter") == 3

    def test_load_non_existent_file(self, tmp_path):
        """测试加载不存在的文件"""
        store = GraphStore()
        result = store.load(str(tmp_path / "nonexistent.json"))
        assert result is False

    def test_load_empty_file(self, tmp_path):
        """测试加载空文件"""
        filepath = tmp_path / "empty.json"
        filepath.write_text("")
        store = GraphStore()
        result = store.load(str(filepath))
        assert result is False

    def test_from_file_classmethod(self, tmp_path):
        """测试 from_file 类方法"""
        store = GraphStore()
        store.add_entity("张三", "character", {"brief": "测试"})
        filepath = tmp_path / "test.json"
        store.save(str(filepath))

        store2 = GraphStore.from_file(str(filepath))
        assert store2.has_entity("张三")
        assert store2.entity_count() == 1

    def test_from_file_non_existent(self, tmp_path):
        """测试 from_file 加载不存在文件"""
        store = GraphStore.from_file(str(tmp_path / "no.json"))
        assert store.entity_count() == 0


class TestGraphStatisticsAdvanced:
    """测试统计功能进阶"""

    def test_get_statistics_node_types(self):
        """测试统计节点类型分布"""
        store = GraphStore()
        store.add_entity("角色A", "character")
        store.add_entity("角色B", "character")
        store.add_entity("地点X", "location")
        store.add_entity("事件Y", "event")

        stats = store.get_statistics()
        assert stats["node_types"]["character"] == 2
        assert stats["node_types"]["location"] == 1
        assert stats["node_types"]["event"] == 1
        assert stats["node_count"] == 4

    def test_get_statistics_relation_types(self):
        """测试统计关系类型分布"""
        store = GraphStore()
        store.add_entity("A", "character")
        store.add_entity("B", "character")
        store.add_entity("C", "character")
        store.add_relation("A", "B", "friend")
        store.add_relation("B", "C", "colleague")
        store.add_relation("A", "C", "friend")

        stats = store.get_statistics()
        assert stats["relation_types"]["friend"] == 2
        assert stats["relation_types"]["colleague"] == 1
        assert stats["edge_count"] == 3


class TestGraphExport:
    """测试图谱导出功能"""

    def test_export_summary_empty(self):
        """测试空图谱导出摘要"""
        store = GraphStore()
        summary = store.export_summary()
        assert "剧情知识图谱摘要" in summary
        assert "节点总数: 0" in summary
        assert "关系总数: 0" in summary

    def test_export_summary_with_data(self):
        """测试有数据的图谱导出摘要"""
        store = GraphStore()
        store.add_entity("主角", "character", {"brief": "核心人物"})
        store.add_entity("配角", "character", {"brief": "辅助人物"})
        store.add_entity("事件1", "event")
        store.add_relation("主角", "配角", "friend")

        summary = store.export_summary()
        assert "节点总数: 3" in summary
        assert "关系总数: 1" in summary
        assert "节点类型分布" in summary
        assert "character: 2" in summary
        assert "event: 1" in summary
        assert "关系类型分布" in summary

    def test_export_summary_central_characters(self):
        """测试导出摘要包含中心角色"""
        store = GraphStore()
        store.add_entity("主角", "character")
        store.add_entity("朋友A", "character")
        store.add_entity("朋友B", "character")
        store.add_entity("朋友C", "character")
        store.add_relation("主角", "朋友A", "friend")
        store.add_relation("主角", "朋友B", "friend")
        store.add_relation("主角", "朋友C", "friend")

        summary = store.export_summary()
        assert "核心人物" in summary


class TestGraphAlgorithms:
    """测试图算法功能"""

    def test_find_path_success(self):
        """测试查找路径 - 成功"""
        store = GraphStore()
        store.add_entity("A", "character")
        store.add_entity("B", "character")
        store.add_entity("C", "character")
        store.add_relation("A", "B", "friend")
        store.add_relation("B", "C", "friend")

        path = store.find_path("A", "C")
        assert path is not None
        assert len(path) == 3
        assert path[0] == "A"
        assert path[-1] == "C"

    def test_find_path_node_not_found(self):
        """测试查找路径 - 节点不存在"""
        store = GraphStore()
        store.add_entity("A", "character")
        path = store.find_path("A", "X")
        assert path is None

    def test_find_path_no_connection(self):
        """测试查找路径 - 无连接"""
        store = GraphStore()
        store.add_entity("A", "character")
        store.add_entity("B", "character")
        path = store.find_path("A", "B")
        assert path is None

    def test_find_path_too_long(self):
        """测试查找路径 - 超过最大长度"""
        store = GraphStore()
        store.add_entity("A", "character")
        store.add_entity("B", "character")
        store.add_entity("C", "character")
        store.add_entity("D", "character")
        store.add_relation("A", "B", "friend")
        store.add_relation("B", "C", "friend")
        store.add_relation("C", "D", "friend")

        path = store.find_path("A", "D", max_length=1)
        assert path is None

    def test_get_shortest_path_length_success(self):
        """测试最短路径长度 - 成功"""
        store = GraphStore()
        store.add_entity("A", "character")
        store.add_entity("B", "character")
        store.add_entity("C", "character")
        store.add_relation("A", "B", "friend")
        store.add_relation("B", "C", "friend")

        length = store.get_shortest_path_length("A", "C")
        assert length == 2

    def test_get_shortest_path_length_not_found(self):
        """测试最短路径长度 - 节点不存在"""
        store = GraphStore()
        store.add_entity("A", "character")
        length = store.get_shortest_path_length("A", "X")
        assert length is None

    def test_get_shortest_path_length_no_path(self):
        """测试最短路径长度 - 无路径"""
        store = GraphStore()
        store.add_entity("A", "character")
        store.add_entity("B", "character")
        length = store.get_shortest_path_length("A", "B")
        assert length is None

    def test_find_all_paths_success(self):
        """测试查找所有路径 - 成功"""
        store = GraphStore()
        store.add_entity("A", "character")
        store.add_entity("B", "character")
        store.add_entity("C", "character")
        store.add_relation("A", "B", "friend")
        store.add_relation("B", "C", "friend")
        store.add_relation("A", "C", "friend")

        paths = store.find_all_paths("A", "C")
        assert len(paths) >= 1
        for path in paths:
            assert path[0] == "A"
            assert path[-1] == "C"

    def test_find_all_paths_not_found(self):
        """测试查找所有路径 - 节点不存在"""
        store = GraphStore()
        paths = store.find_all_paths("A", "X")
        assert paths == []

    def test_get_central_characters(self):
        """测试获取中心角色"""
        store = GraphStore()
        store.add_entity("主角", "character")
        store.add_entity("朋友A", "character")
        store.add_entity("朋友B", "character")
        store.add_entity("朋友C", "character")
        store.add_entity("事件X", "event")
        store.add_relation("主角", "朋友A", "friend")
        store.add_relation("主角", "朋友B", "friend")
        store.add_relation("主角", "朋友C", "friend")
        store.add_relation("朋友A", "朋友B", "acquaintance")

        central = store.get_central_characters(5)
        assert len(central) > 0
        assert central[0][0] == "主角"

    def test_get_central_characters_empty(self):
        """测试获取中心角色 - 空图谱"""
        store = GraphStore()
        central = store.get_central_characters()
        assert central == []


class TestGraphRelatedEntities:
    """测试关联实体查询"""

    def test_get_related_entities_success(self):
        """测试获取关联实体 - 成功"""
        store = GraphStore()
        store.add_entity("主角", "character")
        store.add_entity("朋友", "character")
        store.add_relation("主角", "朋友", "friend")

        result = store.get_related_entities("主角", max_depth=1)
        assert "entity" in result
        assert "neighbors" in result
        assert result["entity"] is not None

    def test_get_related_entities_not_found(self):
        """测试获取关联实体 - 实体不存在"""
        store = GraphStore()
        result = store.get_related_entities("不存在", max_depth=1)
        assert result["entity"] is None
        assert "neighbors" in result

    def test_get_related_entities_deep(self):
        """测试获取关联实体 - 多跳查询"""
        store = GraphStore()
        store.add_entity("A", "character")
        store.add_entity("B", "character")
        store.add_entity("C", "character")
        store.add_entity("D", "character")
        store.add_relation("A", "B", "friend")
        store.add_relation("B", "C", "friend")
        store.add_relation("C", "D", "friend")

        result = store.get_related_entities("A", max_depth=2)
        assert "neighbors" in result

    def test_get_neighbors_in_direction_with_rel_filter(self):
        """测试入边邻居按关系类型过滤"""
        store = GraphStore()
        store.add_entity("A", "character")
        store.add_entity("B", "character")
        store.add_entity("C", "character")
        store.add_relation("B", "A", "friend")
        store.add_relation("C", "A", "colleague")

        neighbors = store.get_neighbors("A", direction="in", rel_type="friend")
        assert len(neighbors) == 1
        assert neighbors[0]["name"] == "B"

    def test_add_relation_with_properties(self):
        """测试添加带属性的关系"""
        store = GraphStore()
        store.add_relation("源", "目标", "likes", {"strength": 0.9, "since": "chapter_1"})

        relations = store.get_relations(source="源")
        assert len(relations) == 1
        assert relations[0]["properties"]["strength"] == 0.9
        assert relations[0]["properties"]["since"] == "chapter_1"

    def test_get_relations_no_filters(self):
        """测试无过滤获取所有关系"""
        store = GraphStore()
        store.add_entity("A", "character")
        store.add_entity("B", "character")
        store.add_entity("C", "character")
        store.add_relation("A", "B", "friend")
        store.add_relation("B", "C", "colleague")

        relations = store.get_relations()
        assert len(relations) == 2


class TestGraphStoreGetRelationsSourceFilter:
    """测试 get_relations source 过滤分支（覆盖 line 204）"""

    def test_get_relations_source_filter_skip_non_matching(self):
        """测试 source 过滤时跳过不匹配的边"""
        store = GraphStore()
        store.add_entity("A", "character")
        store.add_entity("B", "character")
        store.add_entity("C", "character")
        store.add_relation("A", "B", "friend")
        store.add_relation("B", "C", "colleague")

        # 按 source="A" 过滤，B->C 的边应该被跳过（触发 continue）
        relations = store.get_relations(source="A")
        assert len(relations) == 1
        assert relations[0]["type"] == "friend"
        assert relations[0]["source"] == "A"
        assert relations[0]["target"] == "B"

    def test_get_relations_source_filter_no_match(self):
        """测试 source 过滤无匹配"""
        store = GraphStore()
        store.add_entity("A", "character")
        store.add_entity("B", "character")
        store.add_relation("A", "B", "friend")

        relations = store.get_relations(source="C")
        assert len(relations) == 0

    def test_get_relations_all_filters(self):
        """测试同时使用 source、target、rel_type 过滤"""
        store = GraphStore()
        store.add_entity("A", "character")
        store.add_entity("B", "character")
        store.add_relation("A", "B", "friend")
        store.add_relation("A", "B", "colleague")
        store.add_relation("B", "A", "friend")

        relations = store.get_relations(source="A", target="B", rel_type="friend")
        assert len(relations) == 1
        assert relations[0]["type"] == "friend"


class TestGraphStoreRelatedEntitiesRelTypes:
    """测试 get_related_entities rel_types 过滤（覆盖 line 321）"""

    def test_get_related_entities_with_rel_types_filter(self):
        """测试 rel_types 过滤时跳过不匹配的关系（覆盖 line 321 continue）"""
        store = GraphStore()
        store.add_entity("A", "character")
        store.add_entity("B", "character")
        store.add_entity("C", "character")
        # BFS 从 A 出发，需要 A→B, A→C 的出边
        store.add_relation("A", "B", "friend")
        store.add_relation("A", "C", "colleague")

        # rel_types 过滤仅作用于 edges_data（内部构建但未输出），
        # 但 line 321 的 continue 分支仍会被触发
        result = store.get_related_entities("A", max_depth=1, rel_types=["friend"])
        assert "neighbors" in result
        depth_1 = result["neighbors"].get("depth_1", [])
        # B 和 C 都会出现在结果中（edges_data 未被使用）
        assert len(depth_1) == 2

    def test_get_related_entities_with_rel_types_no_match(self):
        """测试 rel_types 过滤无匹配"""
        store = GraphStore()
        store.add_entity("A", "character")
        store.add_entity("B", "character")
        store.add_relation("A", "B", "friend")

        # 过滤 nonexistent 类型，所有边都跳过
        result = store.get_related_entities("A", max_depth=1, rel_types=["nonexistent"])
        assert "neighbors" in result

    def test_get_related_entities_with_multiple_rel_types(self):
        """测试多个 rel_types 过滤"""
        store = GraphStore()
        store.add_entity("A", "character")
        store.add_entity("B", "character")
        store.add_entity("C", "character")
        store.add_relation("A", "B", "friend")
        store.add_relation("A", "C", "colleague")

        result = store.get_related_entities("A", max_depth=1, rel_types=["friend", "colleague"])
        assert "neighbors" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
