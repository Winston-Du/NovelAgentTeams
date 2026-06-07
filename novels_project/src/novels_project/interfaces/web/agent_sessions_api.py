"""
Agent Sessions API - Web 端统一对话接口

Web 创作助手通过此 API 接入主 Agent 统一服务层。
支持 SSE 流式输出，替换旧 /api/content/annotate 接口。
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ...application.contracts import (
    CreateSessionRequest, HandleTurnRequest, ErrorCode,
)
from ...application.main_agent_service import get_main_agent_service, MainAgentService

logger = logging.getLogger("novels_project.agent_sessions_api")

router = APIRouter(prefix="/api/agent-sessions", tags=["Agent 会话"])


# === Pydantic 请求模型 ===

class CreateSessionBody(BaseModel):
    client_type: str = "web"
    workspace: str = "default"
    user_id: str = "user-001"
    scene: str = "creative_assistant"
    metadata: dict = {}


class HandleTurnBody(BaseModel):
    input: str
    stream: bool = True
    context: dict = {}
    client: dict = {}


# === 获取服务实例 ===

def _get_service() -> MainAgentService:
    return get_main_agent_service()


# === API 路由 ===

@router.post("")
async def create_session(body: CreateSessionBody):
    """创建新的 Agent 会话。

    创作助手首次使用时调用，获取 session_id 用于后续对话。
    """
    service = _get_service()
    request = CreateSessionRequest(
        client_type=body.client_type,
        workspace=body.workspace,
        user_id=body.user_id,
        scene=body.scene,
        metadata=body.metadata,
    )
    session_id, session = service.create_session(request)
    return {
        "session_id": session_id,
        "status": "created",
        "workspace": request.workspace,
        "scene": request.scene,
    }


@router.post("/{session_id}/turns")
async def handle_turn(session_id: str, body: HandleTurnBody):
    """发起一轮对话，返回 SSE 事件流。

    前端通过 EventSource 或 fetch + ReadableStream 消费事件流。
    事件类型包括：message.delta, tool.called, usage.updated, turn.completed 等。
    """
    service = _get_service()
    request = HandleTurnRequest(
        input=body.input,
        stream=body.stream,
        context=body.context,
        client=body.client,
    )

    if body.stream:
        async def event_generator():
            async for sse in service.handle_turn(session_id, request, stream=True):
                yield sse

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        # 非流式模式：收集所有事件返回 JSON
        events = []
        async for sse in service.handle_turn(session_id, request, stream=False):
            events.append(sse)
        return {"events": events}


@router.get("/{session_id}")
async def get_session(session_id: str):
    """查询会话详情。"""
    service = _get_service()
    info = service.get_session(session_id)
    if info is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return info.__dict__


@router.get("/{session_id}/messages")
async def list_messages(session_id: str):
    """查询会话消息历史。"""
    service = _get_service()
    messages = service.list_messages(session_id)
    return {"session_id": session_id, "messages": messages}


@router.get("")
async def list_sessions():
    """列出所有会话。"""
    service = _get_service()
    sessions = service._sessions.list_sessions()
    return {"sessions": sessions}