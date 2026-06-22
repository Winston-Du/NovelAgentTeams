"""SubAgent 抽象基类与工具规格定义。

所有具体子 Agent 必须继承 ``BaseSubAgent``，并实现 ``agent_type``、``capabilities`` 和 ``_run_task``。
"""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from .task import Task, TaskResult


@dataclass
class ToolSpec:
    """工具规格定义。

    Attributes:
        name: 工具名称。
        description: 工具描述。
        parameters: 工具参数模式（如 JSON Schema 字典）。
    """

    name: str
    description: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)


class BaseSubAgent(ABC):
    """子 Agent 抽象基类。

    子类需要实现：
    - ``agent_type`` 属性
    - ``capabilities`` 属性
    - ``_run_task`` 方法
    """

    def __init__(
        self,
        agent_id: str,
        capabilities: list[str],
        tools: list[ToolSpec] | None = None,
        max_load: int = 1,
    ):
        self.agent_id = agent_id
        self._capabilities = list(capabilities)
        self.tools = list(tools) if tools else []
        self.max_load = max_load
        self._load = 0
        self._lock = threading.Lock()
        self._task_count = 0
        self._failure_count = 0

    @property
    @abstractmethod
    def agent_type(self) -> str:
        """返回 Agent 类型标识，用于任务匹配与日志。"""
        raise NotImplementedError

    @property
    def capabilities(self) -> list[str]:
        """返回 Agent 支持的能力列表。"""
        return list(self._capabilities)

    @abstractmethod
    def _run_task(self, task: Task) -> TaskResult:
        """子类实现的具体任务执行逻辑。"""
        raise NotImplementedError

    def run_task(self, task: Task) -> TaskResult:
        """执行任务入口。

        内部负责负载计数、异常捕获和结果包装，确保单个任务失败不会传播到编排层。
        """
        with self._lock:
            if self._load >= self.max_load:
                return TaskResult(success=False, error="Agent 负载已满")
            self._load += 1

        task.mark_running()
        self._task_count += 1
        start = time.time()

        try:
            result = self._run_task(task)
            if not isinstance(result, TaskResult):
                result = TaskResult(success=True, output=result)
            result.duration = time.time() - start
            if not result.success:
                self._failure_count += 1
            return result
        except Exception as exc:
            self._failure_count += 1
            return TaskResult(
                success=False,
                error=str(exc),
                duration=time.time() - start,
            )
        finally:
            with self._lock:
                self._load -= 1

    def can_handle(self, task: Task) -> bool:
        """判断当前 Agent 是否具备任务要求的所有能力。"""
        return all(cap in self._capabilities for cap in task.capabilities_required)

    @property
    def is_available(self) -> bool:
        """Agent 是否仍有可用执行槽。"""
        with self._lock:
            return self._load < self.max_load

    @property
    def current_load(self) -> int:
        """当前负载数。"""
        with self._lock:
            return self._load

    @property
    def failure_rate(self) -> float:
        """历史任务失败率。"""
        if self._task_count == 0:
            return 0.0
        return self._failure_count / self._task_count
