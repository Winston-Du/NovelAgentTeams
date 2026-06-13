"""
图存储引擎 - 基于 NetworkX 的轻量级图数据库封装

提供节点和边的 CRUD 操作，支持序列化持久化。
选择 NetworkX 原因：
1. 纯 Python 实现，无需外部服务，安装部署零成本
2. 丰富的图算法支持（BFS、最短路径、中心性分析等）
3. 成熟的社区和文档
4. 支持多种序列化格式（JSON、GEXF、GraphML）
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional
from collections.abc import Iterator

import networkx as nx


# ============================================================
# 常量定义
# ============================================================

# 节点类型
NODE_TYPE_CHARACTER = "character"       # 人物
NODE_TYPE_EVENT = "event"               # 事件
NODE_TYPE_ITEM = "item"                 # 物品/道具
NODE_TYPE_LOCATION = "location"         # 地点
NODE_TYPE_ORGANIZATION = "organization" # 组织/势力
NODE_TYPE_CONCEPT = "concept"           # 概念/设定（暗线、伏笔等）

# 关系类型
REL_TYPE_ALLY = "ally"                  # 同盟
REL_TYPE_ENEMY = "enemy"                # 敌对
REL_TYPE_FAMILY = "family"              # 亲属
REL_TYPE_MENTOR = "mentor"              # 师徒
REL_TYPE_FRIEND = "friend"              # 朋友
REL_TYPE_LOVER = "lover"                # 恋人
REL_TYPE_SUBORDINATE = "subordinate"    # 上下级
REL_TYPE_KNOWS = "knows"                # 认识
REL_TYPE_PARTICIPATED_IN = "participated_in"  # 参与事件
REL_TYPE_CAUSED = "caused"              # 引发/导致
REL_TYPE_OWNS = "owns"                  # 拥有
REL_TYPE_LOCATED_AT = "located_at"      # 位于
REL_TYPE_BELONGS_TO = "belongs_to"      # 属于（组织）
REL_TYPE_REFERS_TO = "refers_to"        # 引用/提及（暗线、伏笔关联）
REL_TYPE_FORESHAODWS = "foreshadows"    # 伏笔预示


class GraphStore:
    """
    图存储引擎。

    用法:
        store = GraphStore()
        store.add_entity("陆商曜", "character", {"role": "主角", "tier": "s"})
        store.add_entity("黑商周桓", "character", {"role": "反派"})
        store.add_relation("陆商曜", "黑商周桓", "enemy", {"since": "chapter_1"})

        # 持久化
        store.save("graph.json")

        # 加载
        store.load("graph.json")
    """

    def __init__(self, graph: Optional[nx.MultiDiGraph] = None):
        """
        Args:
            graph: 可传入已有的 NetworkX 图对象
        """
        self._graph = graph if graph is not None else nx.MultiDiGraph()

    # ============================================================
    # 实体（节点）操作
    # ============================================================

    def add_entity(
        self,
        name: str,
        entity_type: str,
        properties: Optional[dict[str, Any]] = None,
    ) -> str:
        """
        添加一个实体节点。

        Args:
            name: 实体名称（唯一标识）
            entity_type: 实体类型（character/event/item/location/organization/concept）
            properties: 实体属性

        Returns:
            节点 ID（即 name）
        """
        attrs = {"type": entity_type}
        if properties:
            attrs.update(properties)
        self._graph.add_node(name, **attrs)
        return name

    def remove_entity(self, name: str) -> bool:
        """删除实体节点。"""
        if name in self._graph:
            self._graph.remove_node(name)
            return True
        return False

    def get_entity(self, name: str) -> Optional[dict[str, Any]]:
        """获取实体节点属性。"""
        if name in self._graph:
            attrs = dict(self._graph.nodes[name])
            attrs["name"] = name
            return attrs
        return None

    def update_entity(self, name: str, properties: dict[str, Any]) -> bool:
        """更新实体属性。"""
        if name in self._graph:
            for key, value in properties.items():
                self._graph.nodes[name][key] = value
            return True
        return False

    def has_entity(self, name: str) -> bool:
        return name in self._graph

    def get_all_entities(self, entity_type: Optional[str] = None) -> list[dict[str, Any]]:
        """获取所有实体。可选按类型过滤。"""
        result = []
        for node, attrs in self._graph.nodes(data=True):
            if entity_type is None or attrs.get("type") == entity_type:
                item = dict(attrs)
                item["name"] = node
                result.append(item)
        return result

    def entity_count(self) -> int:
        return self._graph.number_of_nodes()

    # ============================================================
    # 关系（边）操作
    # ============================================================

    def add_relation(
        self,
        source: str,
        target: str,
        rel_type: str,
        properties: Optional[dict[str, Any]] = None,
    ) -> bool:
        """
        添加关系边。

        Args:
            source: 源实体名
            target: 目标实体名
            rel_type: 关系类型
            properties: 关系属性（如 since_chapter, strength 等）

        Returns:
            是否成功添加
        """
        if not self.has_entity(source):
            self.add_entity(source, NODE_TYPE_CHARACTER)
        if not self.has_entity(target):
            self.add_entity(target, NODE_TYPE_CHARACTER)

        attrs = {"type": rel_type}
        if properties:
            attrs.update(properties)

        self._graph.add_edge(source, target, **attrs)
        return True

    def remove_relation(self, source: str, target: str, rel_type: Optional[str] = None) -> bool:
        """删除关系。"""
        if not self._graph.has_edge(source, target):
            return False

        if rel_type is not None:
            # 删除特定类型的关系
            edges_to_remove = []
            for key, data in self._graph[source][target].items():
                if data.get("type") == rel_type:
                    edges_to_remove.append(key)
            for key in edges_to_remove:
                self._graph.remove_edge(source, target, key)
            return len(edges_to_remove) > 0
        else:
            self._graph.remove_edge(source, target)
            return True

    def get_relations(
        self,
        source: Optional[str] = None,
        target: Optional[str] = None,
        rel_type: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """查询关系。"""
        result = []
        for u, v, key, data in self._graph.edges(keys=True, data=True):
            if source and u != source:
                continue
            if target and v != target:
                continue
            if rel_type and data.get("type") != rel_type:
                continue
            result.append({
                "source": u,
                "target": v,
                "type": data.get("type"),
                "properties": {k: v for k, v in data.items() if k != "type"},
            })
        return result

    def relation_count(self) -> int:
        return self._graph.number_of_edges()

    # ============================================================
    # 邻居查询
    # ============================================================

    def get_neighbors(
        self,
        name: str,
        rel_type: Optional[str] = None,
        direction: str = "both",
    ) -> list[dict[str, Any]]:
        """
        获取实体的邻居节点。

        Args:
            name: 实体名
            rel_type: 关系类型过滤
            direction: "out" | "in" | "both"

        Returns:
            邻居列表，每个包含 name, type（关系类型）, entity_type, properties
        """
        result = []

        if direction in ("out", "both"):
            for _, neighbor, data in self._graph.out_edges(name, data=True):
                if rel_type and data.get("type") != rel_type:
                    continue
                entity = self.get_entity(neighbor)
                result.append({
                    "name": neighbor,
                    "relation_type": data.get("type"),
                    "relation_properties": {k: v for k, v in data.items() if k != "type"},
                    "entity_type": entity.get("type") if entity else None,
                    "entity_properties": {k: v for k, v in (entity or {}).items()
                                          if k not in ("name", "type")},
                })

        if direction in ("in", "both"):
            for neighbor, _, data in self._graph.in_edges(name, data=True):
                if rel_type and data.get("type") != rel_type:
                    continue
                entity = self.get_entity(neighbor)
                result.append({
                    "name": neighbor,
                    "relation_type": data.get("type"),
                    "relation_properties": {k: v for k, v in data.items() if k != "type"},
                    "entity_type": entity.get("type") if entity else None,
                    "entity_properties": {k: v for k, v in (entity or {}).items()
                                          if k not in ("name", "type")},
                })

        return result

    def get_related_entities(
        self,
        name: str,
        max_depth: int = 2,
        rel_types: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        获取与实体相关的所有实体（多跳查询）。

        Args:
            name: 起始实体名
            max_depth: 最大跳数
            rel_types: 关系类型过滤（None 表示全部）

        Returns:
            {
                "entity": {...},
                "neighbors": {
                    "depth_1": [...],
                    "depth_2": [...],
                }
            }
        """
        result = {
            "entity": self.get_entity(name),
            "neighbors": {},
        }

        for depth in range(1, max_depth + 1):
            cutoff = depth
            neighbors = []

            # 使用 BFS
            try:
                paths = nx.single_source_shortest_path_length(
                    self._graph, name, cutoff=cutoff
                )
            except nx.NodeNotFound:
                break

            for node, dist in paths.items():
                if node == name or dist != depth:
                    continue

                # 获取关系
                edges_data = []
                for _, _, data in self._graph.in_edges(node, data=True):
                    if rel_types and data.get("type") not in rel_types:
                        continue
                    edges_data.append({
                        **{k: v for k, v in data.items() if k != "type"},
                        "type": data.get("type"),
                        "pred": _,
                    })

                entity = self.get_entity(node)
                neighbors.append({
                    "name": node,
                    "distance": dist,
                    "entity_type": entity.get("type") if entity else None,
                    "entity_properties": {k: v for k, v in (entity or {}).items()
                                          if k not in ("name", "type")},
                })

            result["neighbors"][f"depth_{depth}"] = neighbors

        return result

    # ============================================================
    # 图算法
    # ============================================================

    def find_path(
        self,
        source: str,
        target: str,
        max_length: int = 5,
    ) -> Optional[list[str]]:
        """查找两个实体之间的最短路径。"""
        try:
            path = nx.shortest_path(self._graph, source, target)
            if len(path) - 1 <= max_length:
                return path
        except (nx.NodeNotFound, nx.NetworkXNoPath):
            pass
        return None

    def get_shortest_path_length(self, source: str, target: str) -> Optional[int]:
        """获取两个实体之间的最短路径长度。"""
        try:
            return nx.shortest_path_length(self._graph, source, target)
        except (nx.NodeNotFound, nx.NetworkXNoPath):
            return None

    def find_all_paths(
        self,
        source: str,
        target: str,
        max_length: int = 5,
    ) -> list[list[str]]:
        """查找两个实体之间的所有路径（限长）。"""
        try:
            return list(nx.all_simple_paths(self._graph, source, target, cutoff=max_length))
        except nx.NodeNotFound:
            return []

    def get_central_characters(self, top_n: int = 10) -> list[tuple[str, float]]:
        """获取中心度最高的人物（基于度中心性）。"""
        characters = [
            n for n, attrs in self._graph.nodes(data=True)
            if attrs.get("type") == NODE_TYPE_CHARACTER
        ]
        if not characters:
            return []

        centrality = nx.degree_centrality(self._graph)
        scores = [(c, centrality.get(c, 0)) for c in characters]
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_n]

    # ============================================================
    # 持久化
    # ============================================================

    def save(self, filepath: str) -> None:
        """保存图到 JSON 文件。"""
        data = nx.node_link_data(self._graph)
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self, filepath: str) -> bool:
        """从 JSON 文件加载图。

        Returns:
            True: 加载成功
            False: 文件不存在 / 为空 / 格式损坏（graph 保持上次状态）
        """
        path = Path(filepath)
        if not path.exists():
            return False

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return False
                data = json.loads(content)
            self._graph = nx.node_link_graph(data)
        except (KeyError, ValueError, json.JSONDecodeError, OSError):
            # 损坏/格式错误的图文件：保留现有 graph 状态，不抛异常。
            # 调用方（_init_graph）会捕获并回退到空图。
            return False
        return True

    @classmethod
    def from_file(cls, filepath: str) -> "GraphStore":
        store = cls()
        store.load(filepath)
        return store

    # ============================================================
    # 统计与导出
    # ============================================================

    def get_statistics(self) -> dict[str, Any]:
        """获取图统计信息。"""
        type_counts = {}
        for _, attrs in self._graph.nodes(data=True):
            t = attrs.get("type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1

        rel_type_counts = {}
        for _, _, data in self._graph.edges(data=True):
            t = data.get("type", "unknown")
            rel_type_counts[t] = rel_type_counts.get(t, 0) + 1

        return {
            "node_count": self._graph.number_of_nodes(),
            "edge_count": self._graph.number_of_edges(),
            "node_types": type_counts,
            "relation_types": rel_type_counts,
            "is_directed": self._graph.is_directed(),
        }

    def export_summary(self) -> str:
        """导出可读的图摘要。"""
        stats = self.get_statistics()
        lines = [
            "=" * 50,
            "  剧情知识图谱摘要",
            "=" * 50,
            f"  节点总数: {stats['node_count']}",
            f"  关系总数: {stats['edge_count']}",
            "",
        ]

        lines.append("  节点类型分布:")
        for t, count in sorted(stats["node_types"].items()):
            lines.append(f"    - {t}: {count}")

        lines.append("")
        lines.append("  关系类型分布:")
        for t, count in sorted(stats["relation_types"].items()):
            lines.append(f"    - {t}: {count}")

        # 中心角色
        central = self.get_central_characters(5)
        if central:
            lines.append("")
            lines.append("  核心人物 (Top 5):")
            for name, score in central:
                lines.append(f"    - {name}: {score:.4f}")

        lines.append("=" * 50)
        return "\n".join(lines)