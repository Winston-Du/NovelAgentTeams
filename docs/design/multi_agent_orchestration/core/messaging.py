"""Agent 通信模块。

提供标准化的消息传递协议，支持发布/订阅、广播以及同步的请求-响应模式。
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class MessageType(str, Enum):
    """消息类型枚举。"""

    REQUEST = "request"
    RESPONSE = "response"
    BROADCAST = "broadcast"
    EVENT = "event"


class MessageStatus(str, Enum):
    """消息状态枚举。"""

    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"


@dataclass
class Message:
    """标准消息结构。

    Attributes:
        id: 消息唯一标识。
        type: 消息类型。
        sender: 发送方标识。
        recipient: 接收方标识，None 表示广播。
        topic: 主题，用于发布/订阅路由。
        payload: 消息负载。
        correlation_id: 用于 request-response 的关联 ID。
        status: 消息状态。
        timestamp: 消息时间戳（秒级时间戳）。
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: MessageType = MessageType.EVENT
    sender: str = "system"
    recipient: str | None = None
    topic: str = "default"
    payload: Any = None
    correlation_id: str | None = None
    status: MessageStatus = MessageStatus.PENDING
    timestamp: float = field(default_factory=time.time)


class MessageBus:
    """Agent 消息总线。

    支持：
    - 发布/订阅（subscribe / publish）
    - 广播（broadcast）
    - 同步请求-响应（request / response）
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._subscribers: dict[str, list[Callable[[Message], None]]] = {}
        self._response_events: dict[str, threading.Event] = {}
        self._responses: dict[str, Message] = {}
        self._logger = logging.getLogger("multi_agent_orchestration.messaging")

    def subscribe(self, topic: str, callback: Callable[[Message], None]) -> None:
        """订阅某个主题，当该主题收到消息时调用 ``callback``。"""
        with self._lock:
            self._subscribers.setdefault(topic, []).append(callback)

    def publish(self, message: Message) -> None:
        """发布消息到对应主题，并触发订阅者回调。"""
        with self._lock:
            subscribers = list(self._subscribers.get(message.topic, []))

        for callback in subscribers:
            try:
                callback(message)
            except Exception:
                self._logger.exception("消息处理失败 | topic=%s", message.topic)

        message.status = MessageStatus.DELIVERED

        # 处理 request-response 的响应消息
        if message.correlation_id and message.type == MessageType.RESPONSE:
            with self._lock:
                self._responses[message.correlation_id] = message
                event = self._response_events.get(message.correlation_id)
                if event is not None:
                    event.set()

    def request(self, request_message: Message, timeout: float = 5.0) -> Message | None:
        """发送请求消息并阻塞等待响应。

        需要在订阅者中回复一条 ``MessageType.RESPONSE`` 且 ``correlation_id`` 一致的消息。
        超时返回 ``None``。
        """
        if request_message.correlation_id is None:
            request_message.correlation_id = str(uuid.uuid4())

        event = threading.Event()
        with self._lock:
            self._response_events[request_message.correlation_id] = event

        try:
            self.publish(request_message)
            if event.wait(timeout):
                with self._lock:
                    return self._responses.pop(request_message.correlation_id, None)
            request_message.status = MessageStatus.FAILED
            return None
        finally:
            with self._lock:
                self._response_events.pop(request_message.correlation_id, None)

    def broadcast(self, sender: str, topic: str, payload: Any) -> None:
        """向指定主题广播消息（接收方为 None）。"""
        message = Message(
            type=MessageType.BROADCAST,
            sender=sender,
            recipient=None,
            topic=topic,
            payload=payload,
        )
        self.publish(message)
