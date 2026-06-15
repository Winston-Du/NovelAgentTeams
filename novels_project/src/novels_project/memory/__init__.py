"""
图谱记忆模块 (Graph-Based Agent Memory)

基于 NetworkX 图数据库的 Agent 记忆存储与检索系统，用于高效查询
人物关系、暗线、伏笔及事件关联。

核心组件:
- GraphStore: 图存储引擎（CRUD + 持久化）
- EntityExtractor: 实体识别与关系抽取（规则 + LLM）
- GraphQuery: 图谱查询接口（关系网络、路径、暗线追踪）
- SyncManager: 数据同步管理器（增量 + 全量 + 自动同步）
- GraphMemoryIntegrator: 集成编排器（与 Agent Runtime 对接）
"""
from .graph_store import GraphStore
from .entity_extractor import EntityExtractor
from .graph_query import GraphQuery
from .sync_manager import SyncManager, AutoSyncConfig, SyncMode, SyncStatus
from .integrator import GraphMemoryIntegrator

__all__ = [
    "GraphStore",
    "EntityExtractor",
    "GraphQuery",
    "SyncManager",
    "AutoSyncConfig",
    "SyncMode",
    "SyncStatus",
    "GraphMemoryIntegrator",
]