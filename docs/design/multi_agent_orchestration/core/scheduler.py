"""调度模块。

负责任务队列管理、Agent 能力匹配、负载均衡以及调度循环。
"""

from __future__ import annotations

import logging
import threading
from enum import Enum
from queue import Empty, PriorityQueue, Queue
from typing import Callable

from .messaging import Message, MessageBus, MessageType
from .retry import RetryExecutor
from .sub_agent import BaseSubAgent
from .task import Task, TaskResult, TaskStatus


class QueueMode(str, Enum):
    """调度队列模式。"""

    FIFO = "fifo"
    PRIORITY = "priority"


class Scheduler:
    """任务调度器。

    支持：
    - FIFO / PRIORITY 队列
    - Agent 能力匹配
    - 负载均衡（选择负载最低且失败率最低的 Agent）
    - 后台调度循环
    """

    def __init__(
        self,
        message_bus: MessageBus | None = None,
        mode: QueueMode = QueueMode.FIFO,
        poll_interval: float = 0.05,
        retry_executor: RetryExecutor | None = None,
    ) -> None:
        self.message_bus = message_bus
        self.mode = mode
        self.poll_interval = poll_interval
        self.retry_executor = retry_executor or RetryExecutor()

        self._agents: list[BaseSubAgent] = []
        self._lock = threading.Lock()
        self._counter = 0
        self._queue: Queue | PriorityQueue = (
            PriorityQueue() if mode == QueueMode.PRIORITY else Queue()
        )
        self._task_map: dict[str, Task] = {}
        self._queued: set[str] = set()
        self._in_flight: set[str] = set()

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._on_start: Callable[[Task], None] | None = None
        self._on_complete: Callable[[Task, TaskResult], None] | None = None
        self._logger = logging.getLogger("multi_agent_orchestration.scheduler")

    def register_agent(self, agent: BaseSubAgent) -> None:
        """注册一个 SubAgent。"""
        with self._lock:
            self._agents.append(agent)

    def set_callbacks(
        self,
        on_start: Callable[[Task], None] | None = None,
        on_complete: Callable[[Task, TaskResult], None] | None = None,
    ) -> None:
        """设置任务开始与完成回调，通常由 Orchestrator 注入。"""
        self._on_start = on_start
        self._on_complete = on_complete

    def submit_task(self, task: Task) -> None:
        """将任务提交到调度队列。"""
        with self._lock:
            if task.id in self._queued or task.id in self._in_flight:
                return
            self._task_map[task.id] = task
            self._queued.add(task.id)
            if self.mode == QueueMode.PRIORITY:
                self._queue.put((-task.priority.value, self._counter, task.id))
            else:
                self._queue.put(task.id)
            self._counter += 1

        if self.message_bus is not None:
            self.message_bus.publish(
                Message(
                    type=MessageType.EVENT,
                    sender="scheduler",
                    topic="task.submitted",
                    payload={"task_id": task.id, "name": task.name},
                )
            )

    def is_scheduled(self, task_id: str) -> bool:
        """判断任务是否已在队列中或正在执行。"""
        with self._lock:
            return task_id in self._queued or task_id in self._in_flight

    def start(self) -> None:
        """启动后台调度线程。"""
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """停止后台调度线程。"""
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout)

    def is_idle(self) -> bool:
        """判断调度器是否空闲（队列为空且无执行中任务）。"""
        with self._lock:
            return self._queue.empty() and len(self._in_flight) == 0

    def _loop(self) -> None:
        """调度主循环。"""
        while not self._stop_event.is_set():
            try:
                dispatched = self._dispatch_once()
                if not dispatched:
                    self._stop_event.wait(self.poll_interval)
            except Exception:
                self._logger.exception("调度循环异常")

    def _dispatch_once(self) -> bool:
        """尝试从队列中取出一个任务并派发。"""
        try:
            if self.mode == QueueMode.PRIORITY:
                _, _, task_id = self._queue.get(block=False)
            else:
                task_id = self._queue.get(block=False)
        except Empty:
            return False

        with self._lock:
            self._queued.discard(task_id)

        task = self._task_map.get(task_id)
        if task is None:
            return True

        agent = self._select_agent(task)
        if agent is None:
            # 暂时无可用 Agent，重新入队等待
            self.submit_task(task)
            return True

        with self._lock:
            self._in_flight.add(task.id)

        threading.Thread(
            target=self._execute_on_agent, args=(task, agent), daemon=True
        ).start()
        return True

    def _select_agent(self, task: Task) -> BaseSubAgent | None:
        """根据能力匹配和负载均衡为任务选择 Agent。"""
        with self._lock:
            candidates = [
                agent for agent in self._agents
                if agent.can_handle(task) and agent.is_available
            ]

        if not candidates:
            return None

        # 优先选择负载低、失败率低的 Agent
        candidates.sort(key=lambda a: (a.current_load, a.failure_rate))
        return candidates[0]

    def _execute_on_agent(self, task: Task, agent: BaseSubAgent) -> None:
        """在指定 Agent 上执行任务并触发回调。"""
        if self._on_start is not None:
            try:
                self._on_start(task)
            except Exception:
                self._logger.exception("on_start 回调异常")

        if self.message_bus is not None:
            self.message_bus.publish(
                Message(
                    type=MessageType.EVENT,
                    sender="scheduler",
                    topic="task.running",
                    payload={"task_id": task.id, "agent_id": agent.agent_id},
                )
            )

        result = self.retry_executor.execute(
            lambda: agent.run_task(task),
            task.retry_policy,
            task.id,
        )

        if self.message_bus is not None:
            self.message_bus.publish(
                Message(
                    type=MessageType.EVENT,
                    sender="scheduler",
                    topic="task.completed",
                    payload={
                        "task_id": task.id,
                        "success": result.success,
                        "agent_id": agent.agent_id,
                    },
                )
            )

        if self._on_complete is not None:
            try:
                self._on_complete(task, result)
            except Exception:
                self._logger.exception("on_complete 回调异常")

        with self._lock:
            self._in_flight.discard(task.id)
