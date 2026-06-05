"""
记忆管理 API

管理图谱记忆内容：实体查询、关系查询、可视化数据、编辑同步。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..memory.graph_store import GraphStore
from ..memory.graph_query import GraphQuery
from ..project_config import get_project_root

router = APIRouter()

# 全局图谱实例（延迟初始化）
_graph_store: Optional[GraphStore] = None
_graph_query: Optional[GraphQuery] = None


def _get_graph_path() -> str:
    """获取图谱文件路径。"""
    return str(get_project_root() / "graph" / "knowledge_graph.json")


def _init_graph():
    """初始化图谱实例。"""
    global _graph_store, _graph_query
    if _graph_store is None:
        graph_path = _get_graph_path()
        _graph_store = GraphStore()
        _graph_store.load(graph_path)
        _graph_query = GraphQuery(_graph_store)


def _reload_graph():
    """重新加载图谱（用于同步后刷新）。"""
    global _graph_store, _graph_query
    _graph_store = None
    _graph_query = None
    _init_graph()


# ============================================================
# Pydantic 模型
# ============================================================

class EntityUpdate(BaseModel):
    entity_type: Optional[str] = None
    brief: Optional[str] = None
    role: Optional[str] = None
    tier: Optional[str] = None
    attributes: Optional[dict] = None


class RelationCreate(BaseModel):
    source: str
    target: str
    relation_type: str
    attributes: Optional[dict] = None


# ============================================================
# API 端点
# ============================================================

@router.get("/entities")
async def get_entities(
    entity_type: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
):
    """获取图谱实体列表。"""
    _init_graph()

    entities = _graph_store.get_all_entities(entity_type=entity_type)

    # 搜索过滤
    if search:
        search_lower = search.lower()
        entities = [
            n for n in entities
            if search_lower in n.get("name", "").lower()
            or search_lower in str(n.get("brief", "")).lower()
        ]

    total = len(entities)
    page = entities[offset:offset + limit]

    return {"total": total, "offset": offset, "limit": limit, "entities": page}


@router.get("/entities/{entity_id}")
async def get_entity_detail(entity_id: str):
    """获取单个实体详情。"""
    _init_graph()
    entity = _graph_store.get_entity(entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail=f"实体 '{entity_id}' 不存在")

    # 获取关联关系
    relations = _graph_store.get_relations(source=entity_id)
    relations += _graph_store.get_relations(target=entity_id)
    return {"entity": entity, "relations": relations}


@router.put("/entities/{entity_id}")
async def update_entity(entity_id: str, update: EntityUpdate):
    """更新实体信息。"""
    _init_graph()
    if not _graph_store.has_entity(entity_id):
        raise HTTPException(status_code=404, detail=f"实体 '{entity_id}' 不存在")

    attrs = update.model_dump(exclude_none=True)
    success = _graph_store.update_entity(entity_id, attrs)
    if not success:
        raise HTTPException(status_code=500, detail="更新失败")

    graph_path = _get_graph_path()
    _graph_store.save(graph_path)
    return {"entity_id": entity_id, "status": "updated"}


@router.delete("/entities/{entity_id}")
async def delete_entity(entity_id: str):
    """删除实体。"""
    _init_graph()
    if not _graph_store.has_entity(entity_id):
        raise HTTPException(status_code=404, detail=f"实体 '{entity_id}' 不存在")

    _graph_store.remove_entity(entity_id)
    graph_path = _get_graph_path()
    _graph_store.save(graph_path)
    return {"entity_id": entity_id, "status": "deleted"}


@router.get("/relations")
async def get_relations(
    entity_id: Optional[str] = None,
    relation_type: Optional[str] = None,
):
    """获取关系列表。"""
    _init_graph()

    if entity_id:
        relations = _graph_store.get_relations(source=entity_id)
        relations += _graph_store.get_relations(target=entity_id)
    else:
        relations = _graph_store.get_relations()

    if relation_type:
        relations = [r for r in relations if r.get("type") == relation_type]

    return {"total": len(relations), "relations": relations}


@router.post("/relations")
async def create_relation(rel: RelationCreate):
    """创建关系。"""
    _init_graph()

    success = _graph_store.add_relation(
        rel.source, rel.target, rel.relation_type,
        properties=rel.attributes,
    )
    if not success:
        raise HTTPException(status_code=500, detail="创建关系失败")

    graph_path = _get_graph_path()
    _graph_store.save(graph_path)
    return {
        "source": rel.source, "target": rel.target,
        "type": rel.relation_type, "status": "created",
    }


@router.delete("/relations")
async def delete_relation(source: str, target: str):
    """删除关系。"""
    _init_graph()
    _graph_store.remove_relation(source, target)
    graph_path = _get_graph_path()
    _graph_store.save(graph_path)
    return {"source": source, "target": target, "status": "deleted"}


@router.get("/network/{name}")
async def get_character_network(name: str, depth: int = Query(default=2, ge=1, le=5)):
    """获取人物关系网络（用于可视化）。"""
    _init_graph()

    network = _graph_query.get_character_network(name, max_depth=depth)
    if "error" in network:
        raise HTTPException(status_code=404, detail=network["error"])

    return {"center": name, "depth": depth, "network": network}


@router.get("/foreshadow")
async def get_foreshadowing():
    """获取未回收伏笔。"""
    _init_graph()
    unresolved = _graph_query.find_unresolved_foreshadowing()
    return {"total": len(unresolved), "unresolved": unresolved}


@router.get("/stats")
async def get_memory_stats():
    """获取记忆统计信息。"""
    _init_graph()
    stats = _graph_store.get_statistics()
    return stats


@router.get("/search")
async def search_memory(q: str = Query(..., min_length=1)):
    """搜索记忆内容。"""
    _init_graph()
    results = _graph_query.search(q)
    return {"query": q, "results": results}


@router.post("/sync")
async def sync_memory():
    """手动触发记忆同步。"""
    _init_graph()

    try:
        from ..memory.sync_manager import SyncManager
        from ..memory.entity_extractor import EntityExtractor
    except ImportError as e:
        raise HTTPException(status_code=501, detail=f"同步模块不可用: {str(e)}")

    try:
        extractor = EntityExtractor(_graph_store)
        sync_mgr = SyncManager(
            graph_store=_graph_store,
            entity_extractor=extractor,
        )
        
        # 设置监控路径
        project_root = get_project_root()
        sync_mgr.set_watch_paths(
            character_cards=str(project_root / "config" / "character_base_cards.yaml"),
            chapters_dir=str(project_root / "novel_output" / "chapters"),
            sync_state_dir=str(project_root / "graph"),
            graph_save_path=str(project_root / "graph" / "knowledge_graph.json"),
        )

        result = sync_mgr.sync(mode="incremental", force=True)
        _reload_graph()

        return {"status": "synced", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"同步失败: {str(e)}")


@router.post("/init")
async def init_graph_from_workspace():
    """从工作空间数据初始化图谱（导入人物卡等）。"""
    _init_graph()
    try:
        from ..api.content import _load_character_cards, _flatten_characters

        cards = _load_character_cards()
        chars = _flatten_characters(cards)
        imported = 0
        for char in chars:
            name = char.get("name", "")
            if name and not _graph_store.has_entity(name):
                _graph_store.add_entity(
                    name=name,
                    entity_type="character",
                    properties={
                        "brief": char.get("brief", ""),
                        "role": char.get("role", ""),
                        "tier": char.get("tier", ""),
                        **{k: v for k, v in char.items() if k not in ("name", "brief", "role", "tier")},
                    },
                )
                imported += 1
        graph_path = _get_graph_path()
        _graph_store.save(graph_path)
        return {"status": "initialized", "imported": imported}
    except ImportError as e:
        raise HTTPException(status_code=501, detail=f"初始化模块不可用: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"初始化失败: {str(e)}")