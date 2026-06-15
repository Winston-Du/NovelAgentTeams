"""
统一链路追踪服务 - trace_id 生成、span 记录、结构化日志

每次 turn 可追到 trace_id，每次子 Agent、工具、能力服务调用均有 span。
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from .contracts import (
    ErrorCode, EventType, RouteType, TurnStatus,
    UnifiedEvent,
)

logger = logging.getLogger("novels_project.trace")


# === Span ===

class Span:
    """一次执行跨度记录。"""

    def __init__(
        self,
        span_id: str,
        parent_span_id: Optional[str],
        span_type: str,
        name: str,
        trace_id: str,
        session_id: str = "",
        turn_id: str = "",
    ):
        self.span_id = span_id
        self.parent_span_id = parent_span_id
        self.span_type = span_type
        self.name = name
        self.trace_id = trace_id
        self.session_id = session_id
        self.turn_id = turn_id
        self.input_summary: str = ""
        self.output_summary: str = ""
        self.status: str = "started"
        self.started_at: str = datetime.now(timezone.utc).isoformat()
        self.ended_at: Optional[str] = None
        self.error: Optional[str] = None
        self.duration_ms: float = 0

    def complete(self, output_summary: str = "", error: Optional[str] = None):
        self.ended_at = datetime.now(timezone.utc).isoformat()
        self.output_summary = output_summary
        if error:
            self.status = "failed"
            self.error = error
        else:
            self.status = "completed"
        self.duration_ms = (
            datetime.fromisoformat(self.ended_at) - datetime.fromisoformat(self.started_at)
        ).total_seconds() * 1000

        logger.info(
            "[Trace] span=%s type=%s name=%s status=%s duration_ms=%.0f",
            self.span_id, self.span_type, self.name, self.status, self.duration_ms,
        )


# === TraceService ===

class TraceService:
    """统一链路追踪服务。"""

    def __init__(self):
        self._traces: dict[str, list[Span]] = {}

    def generate_trace_id(self) -> str:
        return f"tr_{uuid.uuid4().hex[:12]}"

    def generate_turn_id(self) -> str:
        return f"turn_{uuid.uuid4().hex[:12]}"

    def generate_span_id(self) -> str:
        return f"sp_{uuid.uuid4().hex[:8]}"

    def start_span(
        self,
        span_type: str,
        name: str,
        trace_id: str,
        parent_span_id: Optional[str] = None,
        session_id: str = "",
        turn_id: str = "",
        input_summary: str = "",
    ) -> Span:
        span = Span(
            span_id=self.generate_span_id(),
            parent_span_id=parent_span_id,
            span_type=span_type,
            name=name,
            trace_id=trace_id,
            session_id=session_id,
            turn_id=turn_id,
        )
        span.input_summary = input_summary
        if trace_id not in self._traces:
            self._traces[trace_id] = []
        self._traces[trace_id].append(span)

        logger.info(
            "[Trace] trace_id=%s span=%s type=%s name=%s started",
            trace_id, span.span_id, span_type, name,
        )
        return span

    def get_trace(self, trace_id: str) -> list[Span]:
        return self._traces.get(trace_id, [])

    def build_event(
        self,
        event_type: EventType,
        trace_id: str,
        session_id: str = "",
        turn_id: str = "",
        payload: Optional[dict] = None,
    ) -> UnifiedEvent:
        return UnifiedEvent(
            event=event_type,
            trace_id=trace_id,
            session_id=session_id,
            turn_id=turn_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            payload=payload or {},
        )


# 全局单例
_trace_service: Optional[TraceService] = None


def get_trace_service() -> TraceService:
    global _trace_service
    if _trace_service is None:
        _trace_service = TraceService()
    return _trace_service