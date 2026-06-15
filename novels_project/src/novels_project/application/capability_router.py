"""
能力路由 - 统一请求分类与执行路径选择

决定每个 turn 的执行路径：
- chat_direct: 主 Agent 直接回复
- agent_orchestrated: 主 Agent 编排子 Agent
- toolbacked_action: 工具直接执行
- async_job: 异步任务
- crud_passthrough: CRUD 透传
"""
from __future__ import annotations

import logging
from typing import Optional

from .contracts import RouteType

logger = logging.getLogger("novels_project.capability_router")

# 创作相关关键词 → agent_orchestrated
_CREATION_KEYWORDS = [
    "创作", "写", "生成", "创作第", "写第", "生成第",
    "create", "write", "generate",
    "帮忙写", "帮我写", "帮我创作", "帮忙创作",
]

# 异步任务关键词 → async_job
_ASYNC_KEYWORDS = [
    "批量", "全部", "重建", "初始化",
    "batch", "rebuild", "initialize",
]


class CapabilityRouter:
    """统一请求分类器。"""

    def classify(self, user_input: str, context: Optional[dict] = None) -> RouteType:
        """根据用户输入和上下文分类路由类型。"""
        text = user_input.lower()

        # 异步任务检测
        for kw in _ASYNC_KEYWORDS:
            if kw in text:
                logger.info("[CapabilityRouter] route=%s input=%s", RouteType.ASYNC_JOB, user_input[:50])
                return RouteType.ASYNC_JOB

        # 创作编排检测
        for kw in _CREATION_KEYWORDS:
            if kw in text:
                logger.info("[CapabilityRouter] route=%s input=%s", RouteType.AGENT_ORCHESTRATED, user_input[:50])
                return RouteType.AGENT_ORCHESTRATED

        # 默认：直接对话
        logger.info("[CapabilityRouter] route=%s input=%s", RouteType.CHAT_DIRECT, user_input[:50])
        return RouteType.CHAT_DIRECT


# 全局单例
_capability_router: Optional[CapabilityRouter] = None


def get_capability_router() -> CapabilityRouter:
    global _capability_router
    if _capability_router is None:
        _capability_router = CapabilityRouter()
    return _capability_router