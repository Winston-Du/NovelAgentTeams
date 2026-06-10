"""
图谱记忆工具模块

将图谱查询功能注册为 Agent 可用的工具，集成到现有工具系统中。

提供的工具：
- query_character_network: 查询人物关系网络
- query_relation_between: 查询两实体间的关系路径
- search_graph: 关键词搜索图谱实体
- trace_foreshadowing: 追踪暗线/伏笔
- get_graph_context: 获取实体的图谱上下文（用于 Prompt 注入）
- build_knowledge_graph: 构建/重建知识图谱
- get_graph_stats: 获取图谱统计信息
"""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

from .graph_store import GraphStore
from .graph_query import GraphQuery
from .entity_extractor import EntityExtractor
from .sync_manager import SyncManager

logger = logging.getLogger("novels_project.memory.graph_memory_tool")


# ============================================================
# 全局单例
# ============================================================

_global_graph_store: Optional[GraphStore] = None
_global_graph_query: Optional[GraphQuery] = None
_global_sync_manager: Optional[SyncManager] = None


def get_graph_store() -> GraphStore:
    """获取全局 GraphStore 实例。"""
    global _global_graph_store
    if _global_graph_store is None:
        _global_graph_store = GraphStore()
    return _global_graph_store


def get_graph_query() -> GraphQuery:
    """获取全局 GraphQuery 实例。"""
    global _global_graph_query
    if _global_graph_query is None:
        _global_graph_query = GraphQuery(get_graph_store())
    return _global_graph_query


def get_sync_manager() -> SyncManager:
    """获取全局 SyncManager 实例。"""
    global _global_sync_manager
    if _global_sync_manager is None:
        _global_sync_manager = SyncManager(get_graph_store())
    return _global_sync_manager


def init_graph_memory(
    graph_path: Optional[str] = None,
    character_cards_path: Optional[str] = None,
    chapters_dir: Optional[str] = None,
) -> dict[str, Any]:
    """
    初始化图谱记忆系统。应在系统启动时调用。

    Args:
        graph_path: 图谱持久化文件路径
        character_cards_path: 人物卡 YAML 路径
        chapters_dir: 章节目录路径

    Returns:
        初始化状态
    """
    store = get_graph_store()

    # 尝试加载已有图谱
    loaded = False
    if graph_path:
        loaded = store.load(graph_path)

    # 设置同步管理器
    sync_mgr = get_sync_manager()
    if character_cards_path and chapters_dir:
        sync_mgr.set_watch_paths(character_cards_path, chapters_dir)

    stats = store.get_statistics()

    return {
        "loaded_from_file": loaded,
        "graph_path": graph_path,
        "node_count": stats["node_count"],
        "edge_count": stats["edge_count"],
        "sync_configured": character_cards_path is not None and chapters_dir is not None,
    }


# ============================================================
# Agent 工具函数
# ============================================================

def query_character_network(
    character_name: str,
    max_depth: int = 2,
) -> str:
    """
    查询人物的关系网络，包括直接关系和间接关系。

    Args:
        character_name: 人物名称
        max_depth: 查询深度（1-3）

    Returns:
        关系网络的格式化文本
    """
    logger.info(
        "[GraphTool] query_character_network | name=%s max_depth=%d",
        character_name, max_depth,
    )
    start = time.time()
    query = get_graph_query()
    result = query.get_character_network(character_name, max_depth=min(max_depth, 3))

    if "error" in result:
        logger.warning(
            "[GraphTool] query_character_network 查询失败 | name=%s error=%s",
            character_name, result.get("error"),
        )
        return f"查询失败: {result['error']}"

    lines = [f"【{character_name} 的关系网络】\n"]

    char = result.get("character", {})
    if char.get("brief"):
        lines.append(f"简介: {char['brief']}")
    if char.get("role"):
        lines.append(f"角色: {char['role']}\n")

    # 直接关系
    direct = result.get("direct_relations", [])
    if direct:
        lines.append(f"直接关系 ({len(direct)} 人):")
        for r in direct:
            rel_type = r.get("relation", "")
            lines.append(f"  - {r['name']} [{rel_type}]")
        lines.append("")

    # 所属组织
    orgs = result.get("organizations", [])
    if orgs:
        lines.append(f"所属组织 ({len(orgs)}):")
        for o in orgs:
            lines.append(f"  - {o['name']}")
        lines.append("")

    # 相关事件
    events = result.get("events", [])
    if events:
        lines.append(f"相关事件 ({len(events)}):")
        for e in events:
            lines.append(f"  - {e['name']}")
        lines.append("")

    # 关联概念/暗线
    concepts = result.get("related_concepts", [])
    if concepts:
        lines.append(f"关联暗线/伏笔 ({len(concepts)}):")
        for c in concepts:
            lines.append(f"  - {c['name']}")
        lines.append("")

    # 间接关系
    indirect = result.get("indirect_relations", [])
    if indirect:
        lines.append(f"间接关系 ({len(indirect)} 条):")
        for r in indirect[:10]:  # 限制显示数量
            lines.append(f"  - {r.get('name', '')} (距离: {r.get('distance', '?')})")

    text = "\n".join(lines)
    logger.info(
        "[GraphTool] query_character_network 完成 | name=%s direct=%d indirect=%d events=%d orgs=%d elapsed=%.3fs",
        character_name,
        len(result.get("direct_relations", [])),
        len(result.get("indirect_relations", [])),
        len(result.get("events", [])),
        len(result.get("organizations", [])),
        time.time() - start,
    )
    return text


def query_relation_between(
    source: str,
    target: str,
) -> str:
    """
    查询两个实体之间的关系链路。

    Args:
        source: 源实体名称
        target: 目标实体名称

    Returns:
        关系链路的格式化文本
    """
    logger.info(
        "[GraphTool] query_relation_between | source=%s target=%s",
        source, target,
    )
    start = time.time()
    query = get_graph_query()
    result = query.get_relation_between(source, target)

    lines = [f"【{source} ↔ {target} 关系分析】\n"]

    direct = result.get("direct_relations", [])
    if direct:
        lines.append("直接关系:")
        for r in direct:
            lines.append(f"  - {r['source']} --[{r['type']}]--> {r['target']}")
    else:
        lines.append("无直接关系")

    path = result.get("shortest_path")
    if path:
        lines.append(f"\n最短关联路径 ({len(path)-1} 跳):")
        path_str = " → ".join(path)
        lines.append(f"  {path_str}")

    all_paths = result.get("all_paths", [])
    if all_paths:
        lines.append(f"\n其他关联路径 ({len(all_paths)} 条):")
        for p in all_paths[:3]:
            lines.append(f"  {' → '.join(p)}")

    text = "\n".join(lines)
    logger.info(
        "[GraphTool] query_relation_between 完成 | source=%s target=%s direct=%d paths=%d elapsed=%.3fs",
        source, target, len(result.get("direct_relations", [])),
        len(result.get("all_paths", [])),
        time.time() - start,
    )
    return text


def search_graph(keyword: str, entity_type: str = "all") -> str:
    """
    在图谱中搜索实体。

    Args:
        keyword: 搜索关键词
        entity_type: 实体类型过滤（all/character/event/concept/location/organization）

    Returns:
        搜索结果
    """
    logger.info(
        "[GraphTool] search_graph | keyword=%s type=%s",
        keyword, entity_type,
    )
    start = time.time()
    query = get_graph_query()
    types = None if entity_type == "all" else [entity_type]
    results = query.search(keyword, types)

    if not results:
        logger.info("[GraphTool] search_graph 无结果 | keyword=%s", keyword)
        return f"未找到与「{keyword}」相关的实体。"

    lines = [f"搜索「{keyword}」结果 ({len(results)} 条):\n"]
    for r in results:
        lines.append(f"  - {r['name']} [{r.get('type', '?')}]")
        if r.get("brief"):
            lines.append(f"    {r['brief']}")

    logger.info(
        "[GraphTool] search_graph 完成 | keyword=%s hits=%d elapsed=%.3fs",
        keyword, len(results), time.time() - start,
    )
    return "\n".join(lines)


def trace_foreshadowing(concept_name: str) -> str:
    """
    追踪暗线/伏笔的关联脉络。

    Args:
        concept_name: 概念/伏笔名称

    Returns:
        伏笔追踪结果
    """
    logger.info("[GraphTool] trace_foreshadowing | concept=%s", concept_name)
    start = time.time()
    query = get_graph_query()
    result = query.trace_foreshadowing(concept_name)

    if "error" in result:
        # 尝试搜索
        search_results = query.search(concept_name, [NODE_TYPE_CONCEPT])
        if search_results:
            names = [r["name"] for r in search_results]
            concept_name = names[0]
            result = query.trace_foreshadowing(concept_name)
        else:
            return f"未找到概念「{concept_name}」相关的伏笔信息。"

    lines = [f"【伏笔追踪: {concept_name}】\n"]

    concept = result.get("concept", {})
    if concept.get("brief"):
        lines.append(f"描述: {concept['brief']}\n")

    foreshadowed = result.get("foreshadowed_events", [])
    if foreshadowed:
        lines.append("预示的事件:")
        for f in foreshadowed:
            ch = f.get("chapter", "")
            lines.append(f"  - {f['name']} (第{ch}章)")
    else:
        lines.append("暂无预示的事件")

    refs = result.get("referenced_by", [])
    if refs:
        lines.append(f"\n被以下概念引用 ({len(refs)}):")
        for r in refs:
            ch = r.get("chapter", "")
            lines.append(f"  - {r['name']} (第{ch}章)")

    chars = result.get("related_characters", [])
    if chars:
        lines.append(f"\n关联人物 ({len(chars)}):")
        for c in chars:
            lines.append(f"  - {c['name']} [{c.get('relation', '')}]")

    text = "\n".join(lines)
    logger.info(
        "[GraphTool] trace_foreshadowing 完成 | concept=%s foreshadowed=%d refs=%d chars=%d elapsed=%.3fs",
        concept_name,
        len(result.get("foreshadowed_events", [])),
        len(result.get("referenced_by", [])),
        len(chars),
        time.time() - start,
    )
    return text


def get_graph_context(entity_name: str, context_type: str = "writing") -> str:
    """
    获取实体的图谱上下文（可注入 Prompt）。

    Args:
        entity_name: 实体名
        context_type: "writing"（写作上下文） 或 "review"（校对上下文）

    Returns:
        格式化的上下文字符串
    """
    logger.info(
        "[GraphTool] get_graph_context | entity=%s type=%s",
        entity_name, context_type,
    )
    query = get_graph_query()
    text = query.get_graph_context(entity_name, context_type)
    logger.info(
        "[GraphTool] get_graph_context 完成 | entity=%s text_len=%d",
        entity_name, len(text) if text else 0,
    )
    return text


def build_knowledge_graph(
    character_cards_path: str = "",
    full_sync: bool = False,
) -> str:
    """
    构建或重建知识图谱。

    Args:
        character_cards_path: 人物卡 YAML 路径（空字符串则使用默认配置）
        full_sync: 是否全量重建

    Returns:
        构建结果
    """
    from ..project_config import get_character_cards_path, get_chapters_dir, get_project_root

    logger.info(
        "[GraphTool] build_knowledge_graph 触发 | cards_path=%s full_sync=%s",
        character_cards_path or "(default)", full_sync,
    )
    start = time.time()

    if not character_cards_path:
        character_cards_path = str(get_character_cards_path())

    chapters_dir = str(get_chapters_dir())
    graph_dir = get_project_root() / "graph"

    store = get_graph_store()
    extractor = EntityExtractor(store)
    sync_mgr = get_sync_manager()
    sync_mgr.set_watch_paths(character_cards_path, chapters_dir, str(graph_dir))

    # 执行同步
    mode = "full" if full_sync else "incremental"
    stats = sync_mgr.sync(mode=mode, force=full_sync)

    # 持久化
    graph_dir.mkdir(parents=True, exist_ok=True)
    graph_path = graph_dir / "knowledge_graph.json"
    store.save(str(graph_path))

    result_text = (
        f"知识图谱构建完成: {stats['mode']} 模式\n"
        f"  - 人物: {stats.get('characters_added', stats.get('characters_updated', 0))} 个\n"
        f"  - 章节: {stats.get('chapters_processed', 0)} 章\n"
        f"  - 新增实体: {stats.get('entities_added', 0)} 个\n"
        f"  - 新增关系: {stats.get('relations_added', 0)} 条\n"
        f"  - 跳过: {stats.get('skipped', 0)}\n"
        f"图谱已保存至: {graph_path}"
    )
    logger.info(
        "[GraphTool] build_knowledge_graph 完成 | elapsed=%.3fs | %s",
        time.time() - start, result_text.replace("\n", " | "),
    )
    return result_text


def get_graph_stats() -> str:
    """获取知识图谱的统计信息。"""
    logger.info("[GraphTool] get_graph_stats 调用")
    store = get_graph_store()
    text = store.export_summary()
    logger.info("[GraphTool] get_graph_stats 完成 | text_len=%d", len(text) if text else 0)
    return text


# ============================================================
# 导入常量（供外部使用）
# ============================================================
from .graph_store import (  # noqa: E402
    NODE_TYPE_CHARACTER,
    NODE_TYPE_EVENT,
    NODE_TYPE_ITEM,
    NODE_TYPE_LOCATION,
    NODE_TYPE_ORGANIZATION,
    NODE_TYPE_CONCEPT,
)