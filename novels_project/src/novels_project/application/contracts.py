"""
统一契约对象 - 错误码、事件类型、请求/响应模型

这是 Web 与 CLI 共享的协议真源，所有新增接口必须先补契约文档。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# === 错误码 ===

class ErrorCode(str, Enum):
    AUTH_ERROR = "AUTH_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    SESSION_ERROR = "SESSION_ERROR"
    ROUTING_ERROR = "ROUTING_ERROR"
    MODEL_ERROR = "MODEL_ERROR"
    TOOL_ERROR = "TOOL_ERROR"
    SUB_AGENT_ERROR = "SUB_AGENT_ERROR"
    CAPABILITY_ERROR = "CAPABILITY_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


# === Session 状态 ===

class SessionStatus(str, Enum):
    CREATED = "created"
    ACTIVE = "active"
    COMPACTED = "compacted"
    ARCHIVED = "archived"
    FAILED = "failed"


# === Turn 状态 ===

class TurnStatus(str, Enum):
    QUEUED = "queued"
    ROUTING = "routing"
    RUNNING = "running"
    STREAMING = "streaming"
    AWAITING_ASYNC = "awaiting_async"
    COMPLETED = "completed"
    PARTIAL_FAILED = "partial_failed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# === 路由类型 ===

class RouteType(str, Enum):
    CHAT_DIRECT = "chat_direct"
    AGENT_ORCHESTRATED = "agent_orchestrated"
    TOOLBACKED_ACTION = "toolbacked_action"
    ASYNC_JOB = "async_job"
    CRUD_PASSTHROUGH = "crud_passthrough"


# === 统一事件协议 ===

class EventType(str, Enum):
    TURN_STARTED = "turn.started"
    CONTEXT_LOADED = "context.loaded"
    ROUTE_SELECTED = "route.selected"
    MESSAGE_DELTA = "message.delta"
    MESSAGE_COMPLETED = "message.completed"
    TOOL_CALLED = "tool.called"
    TOOL_COMPLETED = "tool.completed"
    AGENT_CALLED = "agent.called"
    AGENT_COMPLETED = "agent.completed"
    USAGE_UPDATED = "usage.updated"
    TURN_COMPLETED = "turn.completed"
    TURN_FAILED = "turn.failed"


@dataclass
class UnifiedEvent:
    """统一事件结构，Web/CLI 共享。"""
    event: EventType
    trace_id: str = ""
    session_id: str = ""
    turn_id: str = ""
    timestamp: str = ""
    payload: dict = field(default_factory=dict)

    def to_sse(self) -> str:
        """转换为 SSE 格式。"""
        import json
        from datetime import datetime, timezone
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        return f"data: {json.dumps(self.__dict__, ensure_ascii=False)}\n\n"


# === 请求/响应模型 ===

@dataclass
class CreateSessionRequest:
    client_type: str = "web"
    workspace: str = "default"
    user_id: str = "user-001"
    scene: str = "creative_assistant"
    metadata: dict = field(default_factory=dict)


@dataclass
class HandleTurnRequest:
    input: str
    stream: bool = True
    context: dict = field(default_factory=dict)
    client: dict = field(default_factory=dict)


@dataclass
class SessionInfo:
    session_id: str
    workspace: str
    client_type: str
    scene: str
    status: SessionStatus
    created_at: str
    updated_at: str
    message_count: int
    usage_summary: dict = field(default_factory=dict)


@dataclass
class TurnInfo:
    turn_id: str
    session_id: str
    trace_id: str
    input: str
    route_type: RouteType
    status: TurnStatus
    started_at: str
    completed_at: Optional[str] = None
    error_code: Optional[ErrorCode] = None
    error_message: Optional[str] = None


@dataclass
class UnifiedErrorResponse:
    error: dict