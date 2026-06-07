"""
图谱查询模块

提供基于节点关系的记忆查询功能，支持：
1. 直接关联查询（一度邻居）
2. 间接关联查询（多跳路径）
3. 关系链路查询（找到两个实体间的关联路径）
4. 模式匹配查询（如"找出所有敌对关系"）
5. 暗线/伏笔追踪
"""
from __future__ import annotations

from typing import Any, Optional

from .graph_store import (
    GraphStore,
    NODE_TYPE_CHARACTER,
    NODE_TYPE_EVENT,
    NODE_TYPE_ITEM,
    NODE_TYPE_CONCEPT,
    REL_TYPE_ENEMY,
    REL_TYPE_ALLY,
    REL_TYPE_FORESHAODWS,
    REL_TYPE_REFERS_TO,
    REL_TYPE_PARTICIPATED_IN,
)


class GraphQuery:
    """
    图谱查询器。提供面向 Agent 的高层查询接口。

    用法:
        query = GraphQuery(graph_store)
        result = query.get_character_network("陆商曜")
        result = query.trace_foreshadowing("神秘玉简")
    """

    def __init__(self, graph_store: GraphStore):
        self._graph = graph_store

    # ============================================================
    # 人物网络查询
    # ============================================================

    def get_character_network(
        self,
        name: str,
        max_depth: int = 2,
    ) -> dict[str, Any]:
        """
        获取人物关系网络。

        Args:
            name: 人物名
            max_depth: 最大关系深度

        Returns:
            该人物的完整关系网络
        """
        entity = self._graph.get_entity(name)
        if not entity:
            return {"error": f"未找到人物「{name}」"}

        result = {
            "character": entity,
            "direct_relations": [],    # 一度关系
            "indirect_relations": [],  # 二度及以上关系
            "events": [],              # 相关事件
            "organizations": [],       # 所属组织
            "related_concepts": [],    # 关联概念/暗线
        }

        neighbors = self._graph.get_neighbors(name)

        for n in neighbors:
            neighbor_name = n["name"]
            neighbor_type = n.get("entity_type", "")
            rel = {
                "name": neighbor_name,
                "type": neighbor_type,
                "relation": n["relation_type"],
                "relation_detail": n.get("relation_properties", {}),
            }

            # 分类
            if neighbor_type == NODE_TYPE_EVENT:
                result["events"].append(rel)
            elif neighbor_type == "organization":
                result["organizations"].append(rel)
            elif neighbor_type == NODE_TYPE_CONCEPT:
                result["related_concepts"].append(rel)
            else:
                result["direct_relations"].append(rel)

        # 二度关系
        if max_depth >= 2:
            related = self._graph.get_related_entities(name, max_depth=2)
            for depth_key in ["depth_2"]:
                for item in related.get("neighbors", {}).get(depth_key, []):
                    if item["name"] not in {r["name"] for r in result["direct_relations"]}:  # pragma: no branch
                        result["indirect_relations"].append(item)

        return result

    def get_relation_between(
        self,
        source: str,
        target: str,
    ) -> dict[str, Any]:
        """
        查询两个实体之间的所有关系。

        Args:
            source: 源实体
            target: 目标实体

        Returns:
            两个实体之间的关系分析
        """
        result = {
            "source": source,
            "target": target,
            "direct_relations": [],
            "shortest_path": None,
            "all_paths": [],
        }

        # 直接关系
        direct = self._graph.get_relations(source=source, target=target)
        direct_reverse = self._graph.get_relations(source=target, target=source)
        result["direct_relations"] = direct + direct_reverse

        # 最短路径
        path = self._graph.find_path(source, target)
        if path and len(path) > 2:  # 长度 > 2 说明不是直接相连
            result["shortest_path"] = path

        # 所有路径
        all_paths = self._graph.find_all_paths(source, target, max_length=4)
        result["all_paths"] = [p for p in all_paths if len(p) > 2][:5]

        return result

    def find_characters_by_relation(
        self,
        name: str,
        rel_type: str,
    ) -> list[dict[str, Any]]:
        """
        查找与指定人物有特定关系的角色。

        Args:
            name: 人物名
            rel_type: 关系类型（ally/enemy/family 等）

        Returns:
            符合条件的角色列表
        """
        neighbors = self._graph.get_neighbors(name, rel_type=rel_type)
        return [
            {
                "name": n["name"],
                "type": n.get("entity_type", ""),
                "relation_detail": n.get("relation_properties", {}),
            }
            for n in neighbors
        ]

    # ============================================================
    # 事件查询
    # ============================================================

    def get_event_participants(self, event_name: str) -> dict[str, Any]:
        """
        查询事件的参与人物。

        Args:
            event_name: 事件名称

        Returns:
            事件信息及参与人物列表
        """
        entity = self._graph.get_entity(event_name)
        if not entity:
            return {"error": f"未找到事件「{event_name}」"}

        neighbors = self._graph.get_neighbors(event_name, rel_type=REL_TYPE_PARTICIPATED_IN, direction="in")

        return {
            "event": entity,
            "participants": [
                {"name": n["name"], "details": n.get("relation_properties", {})}
                for n in neighbors
                if n.get("entity_type") == NODE_TYPE_CHARACTER
            ],
            "caused_by": [
                {"name": n["name"], "details": n.get("relation_properties", {})}
                for n in self._graph.get_neighbors(event_name, rel_type="caused", direction="in")
            ],
            "caused_events": [
                {"name": n["name"], "details": n.get("relation_properties", {})}
                for n in self._graph.get_neighbors(event_name, rel_type="caused", direction="out")
            ],
        }

    # ============================================================
    # 暗线/伏笔追踪
    # ============================================================

    def trace_foreshadowing(self, concept_name: str) -> dict[str, Any]:
        """
        追踪暗线/伏笔的关联脉络。

        Args:
            concept_name: 概念/伏笔名称

        Returns:
            伏笔关联图
        """
        entity = self._graph.get_entity(concept_name)
        if not entity:
            return {"error": f"未找到概念「{concept_name}」"}

        result = {
            "concept": entity,
            "foreshadowed_events": [],  # 预示的事件
            "referenced_by": [],        # 引用此概念的其他概念
            "related_characters": [],   # 相关人物
        }

        # 查找伏笔关系
        for rel in self._graph.get_relations(source=concept_name, rel_type=REL_TYPE_FORESHAODWS):
            target_entity = self._graph.get_entity(rel["target"])
            result["foreshadowed_events"].append({
                "name": rel["target"],
                "type": target_entity.get("type") if target_entity else None,
                "chapter": rel.get("properties", {}).get("chapter_id"),
            })

        # 查找引用关系
        for rel in self._graph.get_relations(target=concept_name, rel_type=REL_TYPE_REFERS_TO):
            result["referenced_by"].append({
                "name": rel["source"],
                "chapter": rel.get("properties", {}).get("chapter_id"),
            })

        # 查找关联人物
        neighbors = self._graph.get_neighbors(concept_name)
        for n in neighbors:
            if n.get("entity_type") == NODE_TYPE_CHARACTER:
                result["related_characters"].append({
                    "name": n["name"],
                    "relation": n["relation_type"],
                })

        return result

    def find_unresolved_foreshadowing(self) -> list[dict[str, Any]]:
        """
        查找未回收的伏笔（只有 foreshadows 出边，没有对应的事件回收）。

        Returns:
            未回收的伏笔列表
        """
        unresolved = []

        for node, attrs in self._graph._graph.nodes(data=True):
            if attrs.get("type") != NODE_TYPE_CONCEPT:
                continue

            # 检查是否有 foreshadows 出边
            out_edges = list(self._graph._graph.out_edges(node, data=True))
            foreshadows = [(u, v, d) for u, v, d in out_edges if d.get("type") == REL_TYPE_FORESHAODWS]

            if foreshadows:
                # 检查被预示的事件是否已有完结标记
                unresolved_targets = []
                for _, target, data in foreshadows:
                    target_entity = self._graph.get_entity(target)
                    if target_entity and not target_entity.get("resolved"):
                        unresolved_targets.append({
                            "name": target,
                            "chapter": data.get("chapter_id"),
                        })

                if unresolved_targets:
                    unresolved.append({
                        "concept": node,
                        "brief": attrs.get("brief", ""),
                        "unresolved_targets": unresolved_targets,
                    })

        return unresolved

    def trace_all_foreshadowings(self) -> list[str]:
        """
        获取所有未完成的伏笔列表，返回格式化的字符串列表。
        
        Returns:
            未完成伏笔的描述列表
        """
        unresolved = self.find_unresolved_foreshadowing()
        result = []
        
        for item in unresolved:
            concept = item.get("concept", "")
            brief = item.get("brief", "")
            targets = item.get("unresolved_targets", [])
            
            if targets:
                for target in targets:
                    target_name = target.get("name", "")
                    chapter = target.get("chapter", "")
                    if chapter:
                        desc = f"「{concept}」预示了「{target_name}」（第{chapter}章）"
                    else:
                        desc = f"「{concept}」预示了「{target_name}」"
                    result.append(desc)
            elif brief:
                result.append(f"「{concept}」: {brief}")
            else:
                result.append(f"「{concept}」")
        
        return result

    # ============================================================
    # 综合查询
    # ============================================================

    def search(
        self,
        keyword: str,
        entity_types: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        """
        关键词搜索实体。

        Args:
            keyword: 搜索关键词
            entity_types: 实体类型过滤

        Returns:
            匹配的实体列表
        """
        results = []
        for node, attrs in self._graph._graph.nodes(data=True):
            if entity_types and attrs.get("type") not in entity_types:
                continue

            # 在名称和 brief 中搜索
            search_text = f"{node} {attrs.get('brief', '')} {attrs.get('role', '')}"
            if keyword.lower() in search_text.lower():
                results.append({
                    "name": node,
                    "type": attrs.get("type"),
                    "brief": attrs.get("brief", ""),
                    "role": attrs.get("role", ""),
                })

        return results

    def get_graph_context(
        self,
        name: str,
        context_type: str = "writing",
    ) -> str:
        """
        获取实体的图谱上下文信息（格式化字符串，可直接注入 Prompt）。

        Args:
            name: 实体名
            context_type: 上下文类型
                - "writing": 写作上下文（关系、组织、事件）
                - "review": 校对上下文（暗线、伏笔状态）

        Returns:
            格式化的上下文字符串
        """
        entity = self._graph.get_entity(name)
        if not entity:
            return f""

        parts = []

        if context_type == "writing":
            parts.append(f"【{name}】")
            if entity.get("brief"):
                parts.append(f"  简介: {entity['brief']}")
            if entity.get("role"):
                parts.append(f"  角色: {entity['role']}")

            # 关系
            neighbors = self._graph.get_neighbors(name)
            if neighbors:
                parts.append("  关联:")
                for n in neighbors:
                    rel_name = n.get("relation_type", "")
                    parts.append(f"    - {n['name']} ({rel_name})")

            # 所属组织
            orgs = self._graph.get_neighbors(name, rel_type="belongs_to")
            if orgs:
                parts.append(f"  组织: {', '.join(n['name'] for n in orgs)}")

        elif context_type == "review":
            parts.append(f"【{name}】校对上下文")

            # 暗线关联
            concept_neighbors = [
                n for n in self._graph.get_neighbors(name)
                if n.get("entity_type") == NODE_TYPE_CONCEPT
            ]
            if concept_neighbors:
                parts.append("  关联暗线/伏笔:")
                for n in concept_neighbors:
                    parts.append(f"    - {n['name']} ({n.get('relation_type', '')})")

            # 已出场章节
            chapters = entity.get("appears_in_chapters", [])
            if chapters:
                parts.append(f"  出场章节: {', '.join(map(str, sorted(set(chapters))))}")

        return "\n".join(parts) if len(parts) > 1 else ""