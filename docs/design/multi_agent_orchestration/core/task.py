"""任务模型定义。

提供任务状态、优先级、重试策略、执行结果以及任务实体的基础数据结构。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, IntEnum
from typing import Any


class TaskStatus(str, Enum):
    """任务状态枚举。"""

    PENDING = "pending"       # 等待执行
    RUNNING = "running"       # 执行中
    COMPLETED = "completed"   # 已完成
    FAILED = "failed"         # 已失败
    CANCELLED = "cancelled"   # 已取消


class TaskPriority(IntEnum):
    """任务优先级枚举，数值越大优先级越高。"""

    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class RetryPolicyType(str, Enum):
    """重试策略类型枚举。"""

    NONE = "none"
    FIXED = "fixed"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"


@dataclass
class RetryPolicy:
    """任务重试策略配置。

    Attributes:
        max_retries: 最大重试次数。
        delay: 基础退避时间（秒）。
        policy_type: 退避策略类型。
        transient_exceptions: 被认为是 transient 可重试的异常类型元组。
        max_delay: 最大退避时间（秒），None 表示不限制。
    """

    max_retries: int = 0
    delay: float = 1.0
    policy_type: RetryPolicyType = RetryPolicyType.FIXED
    transient_exceptions: tuple[type[Exception], ...] = field(
        default_factory=lambda: (Exception,)
    )
    max_delay: float | None = None

    def compute_backoff(self, retry_attempt: int) -> float:
        """根据策略计算第 ``retry_attempt`` 次重试的等待时间。

        ``retry_attempt`` 从 0 开始计数，表示第一次重试。
        """
        if self.policy_type == RetryPolicyType.NONE:
            return 0.0

        if self.policy_type == RetryPolicyType.FIXED:
            delay = self.delay
        elif self.policy_type == RetryPolicyType.LINEAR:
            delay = self.delay * (retry_attempt + 1)
        elif self.policy_type == RetryPolicyType.EXPONENTIAL:
            delay = self.delay * (2**retry_attempt)
        else:
            delay = self.delay

        if self.max_delay is not None:
            delay = min(delay, self.max_delay)
        return delay


@dataclass
class TaskResult:
    """任务执行结果。

    Attributes:
        success: 是否执行成功。
        output: 执行输出，可为任意类型。
        error: 失败时的错误信息。
        duration: 执行耗时（秒）。
        metadata: 附加元数据。
    """

    success: bool = False
    output: Any = None
    error: str | None = None
    duration: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Task:
    """任务实体。

    Attributes:
        id: 全局唯一任务标识。
        name: 任务名称。
        description: 任务描述。
        status: 当前状态。
        priority: 任务优先级。
        capabilities_required: 执行该任务所需的 Agent 能力列表。
        dependencies: 依赖的任务 ID 列表。
        subtasks: 子任务列表。
        retry_policy: 重试策略。
        created_at: 创建时间。
        started_at: 开始执行时间。
        completed_at: 完成时间。
        result: 执行结果。
        payload: 任务负载数据。
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "未命名任务"
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    capabilities_required: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    subtasks: list[Task] = field(default_factory=list)
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: TaskResult | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    def add_dependency(self, task: Task | str) -> None:
        """添加一个依赖任务或依赖任务 ID。"""
        dep_id = task.id if isinstance(task, Task) else str(task)
        if dep_id not in self.dependencies:
            self.dependencies.append(dep_id)

    def add_subtask(self, task: Task) -> None:
        """添加子任务，并自动建立根任务到子任务的依赖关系。"""
        if task not in self.subtasks:
            self.subtasks.append(task)
            self.add_dependency(task)

    def mark_running(self) -> None:
        """将任务标记为执行中。"""
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.now()

    def mark_completed(self, result: TaskResult | None = None) -> None:
        """将任务标记为已完成。"""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.now()
        self.result = result or TaskResult(success=True)

    def mark_failed(self, result: TaskResult | None = None) -> None:
        """将任务标记为已失败。"""
        self.status = TaskStatus.FAILED
        self.completed_at = datetime.now()
        self.result = result or TaskResult(success=False, error="任务执行失败")

    def is_ready(self, completed_ids: set[str]) -> bool:
        """判断该任务是否已满足执行条件。

        条件为：状态为 ``PENDING`` 且所有依赖任务都已完成。
        """
        if self.status != TaskStatus.PENDING:
            return False
        return all(dep_id in completed_ids for dep_id in self.dependencies)

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Task):
            return self.id == other.id
        return NotImplemented
