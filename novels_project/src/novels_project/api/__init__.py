"""
API 路由模块 - 统一导出
"""
from .workspace import router as workspace_router
from .content import router as content_router
from .agent import router as agent_router
from .settings import router as settings_router
from .memory import router as memory_router

__all__ = [
    "workspace_router",
    "content_router",
    "agent_router",
    "settings_router",
    "memory_router",
]