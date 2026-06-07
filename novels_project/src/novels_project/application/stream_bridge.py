"""
流式桥接 - 将 ConversationRuntime 输出转换为统一事件流

为 Web 生成 SSE 事件，为 CLI 生成终端可渲染事件。
"""
from __future__ import annotations

import asyncio
import logging
import queue
import threading
from typing import Optional, AsyncIterator

from ..api_client import (
    OpenAICompatibleClient, ApiRequest, TokenUsage,
    AssistantEvent, TextDelta, ToolUseEvent, UsageEvent, MessageStop,
)
from ..runtime import ConversationRuntime, TurnSummary
from .contracts import EventType, UnifiedEvent
from .trace_service import get_trace_service

logger = logging.getLogger("novels_project.stream_bridge")


class StreamingApiClient(OpenAICompatibleClient):
    """支持事件回调的流式 API 客户端。

    扩展 OpenAICompatibleClient，在流式处理过程中将每个事件
    通过回调函数实时发送出去，用于 SSE 流式输出。
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._event_callback = None

    def set_event_callback(self, callback):
        """设置事件回调，每个 AssistantEvent 生成时都会调用。"""
        self._event_callback = callback

    def stream(self, request: ApiRequest, print_stream: bool = True) -> list[AssistantEvent]:
        """带回调的流式调用。"""
        from ..session import TextBlock, ToolUseBlock, ToolResultBlock, MessageRole

        events: list[AssistantEvent] = []
        full_text = ""
        tool_calls: dict[int, dict] = {}

        # Build OpenAI messages format
        openai_messages = []
        if request.system_prompt:
            openai_messages.append({"role": "system", "content": request.system_prompt})
        for msg in request.messages:
            openai_msg = self._convert_message(msg)
            if openai_msg:
                if isinstance(openai_msg, list):
                    openai_messages.extend(openai_msg)
                else:
                    openai_messages.append(openai_msg)

        openai_tools = None
        if request.tools:
            openai_tools = [
                {"type": "function", "function": {
                    "name": spec.name, "description": spec.description,
                    "parameters": spec.input_schema,
                }}
                for spec in request.tools
            ]

        kwargs = {
            "model": request.model or self.default_model,
            "messages": openai_messages,
            "max_tokens": request.max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if openai_tools:
            kwargs["tools"] = openai_tools

        response = self.client.chat.completions.create(**kwargs)

        for chunk in response:
            if not chunk.choices and chunk.usage:
                evt = UsageEvent(usage=TokenUsage(
                    input_tokens=chunk.usage.prompt_tokens or 0,
                    output_tokens=chunk.usage.completion_tokens or 0,
                    total_tokens=chunk.usage.total_tokens or 0,
                ))
                events.append(evt)
                self._emit(evt)
                continue

            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta

            if delta.content:
                full_text += delta.content
                evt = TextDelta(text=delta.content)
                events.append(evt)
                self._emit(evt)

            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls:
                        tool_calls[idx] = {"id": tc.id or "", "name": "", "arguments": ""}
                    if tc.id:
                        tool_calls[idx]["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            tool_calls[idx]["name"] = tc.function.name
                        if tc.function.arguments:
                            tool_calls[idx]["arguments"] += tc.function.arguments

            if chunk.choices[0].finish_reason:
                break

        for idx in sorted(tool_calls.keys()):
            tc = tool_calls[idx]
            evt = ToolUseEvent(id=tc["id"], name=tc["name"], input=tc["arguments"])
            events.append(evt)
            self._emit(evt)

        evt = MessageStop()
        events.append(evt)
        self._emit(evt)
        return events

    def _emit(self, event: AssistantEvent):
        if self._event_callback:
            try:
                self._event_callback(event)
            except Exception as e:
                logger.warning("Event callback failed: %s", e)


class StreamBridge:
    """将运行时输出转换为统一事件流。

    用于 Web SSE 流式输出和 CLI 终端渲染。
    """

    def __init__(self, trace_service=None):
        self._trace = trace_service or get_trace_service()
        self._queue: asyncio.Queue = asyncio.Queue()

    def get_queue(self) -> asyncio.Queue:
        return self._queue

    async def put_event(self, event: UnifiedEvent):
        await self._queue.put(event)

    def create_event(
        self,
        event_type: EventType,
        trace_id: str,
        session_id: str = "",
        turn_id: str = "",
        payload: Optional[dict] = None,
    ) -> UnifiedEvent:
        return self._trace.build_event(event_type, trace_id, session_id, turn_id, payload)

    async def stream_sse(self) -> AsyncIterator[str]:
        """异步生成器，从队列中读取事件并生成 SSE 格式。"""
        while True:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=0.1)
                yield event.to_sse()
                if event.event in (EventType.TURN_COMPLETED, EventType.TURN_FAILED):
                    break
            except asyncio.TimeoutError:
                continue

    async def send_delta(self, text: str, trace_id: str, session_id: str, turn_id: str):
        await self.put_event(self.create_event(
            EventType.MESSAGE_DELTA, trace_id, session_id, turn_id,
            {"text": text},
        ))

    async def send_completed(self, trace_id: str, session_id: str, turn_id: str, usage: dict):
        await self.put_event(self.create_event(
            EventType.TURN_COMPLETED, trace_id, session_id, turn_id,
            {"usage": usage},
        ))

    async def send_failed(self, trace_id: str, session_id: str, turn_id: str, error: str):
        await self.put_event(self.create_event(
            EventType.TURN_FAILED, trace_id, session_id, turn_id,
            {"error": error},
        ))