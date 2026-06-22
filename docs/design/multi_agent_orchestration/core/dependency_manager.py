"""依赖管理模块。

负责任务依赖关系维护、循环依赖检测、可执行任务发现以及拓扑执行顺序生成。
"""

from __future__ import annotations

import logging
import threading
from collections import deque
from datetime import datetime
from typing import Iterable

from .task import Task, TaskResult, TaskStatus


class DependencyManager:
    """任务依赖管理器。

    支持：
    - 添加任务及其子任务
    - 循环依赖检测
    - 获取可执行（依赖已完成）任务
    - 获取拓扑执行顺序
    - 更新任务状态与结果
    """

    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}
        self._lock = threading.RLock()
        self._logger = logging.getLogger("multi_agent_orchestration.dependency_manager")

    def add_task(self, task: Task) -> None:
        """添加任务，同时递归添加其所有子任务。"""
        with self._lock:
            self._add_recursive(task)

    def _add_recursive(self, task: Task) -> None:
        self._tasks[task.id] = task
        for child in task.subtasks:
            self._add_recursive(child)

    def detect_cycles(self) -> list[str] | None:
        """检测依赖图中是否存在循环依赖。

        返回构成环路的任务 ID 列表；无环返回 ``None``。
        """
        with self._lock:
            visited: set[str] = set()
            rec_stack: set[str] = set()
            path: list[str] = []

            def dfs(node: str) -> list[str] | None:
                visited.add(node)
                rec_stack.add(node)
                path.append(node)

                for dep in self._tasks.get(node, Task()).dependencies:
                    if dep not in visited:
                        cycle = dfs(dep)
                        if cycle is not None:
                            return cycle
                    elif dep in rec_stack:
                        idx = path.index(dep)
                        return path[idx:] + [dep]

                path.pop()
                rec_stack.remove(node)
                return None

            for task_id in self._tasks:
                if task_id not in visited:
                    cycle = dfs(task_id)
                    if cycle is not None:
                        return cycle
            return None

    def get_ready_tasks(self) -> list[Task]:
        """获取所有依赖已满足、可以执行的任务。"""
        with self._lock:
            completed_ids = {
                tid for tid, t in self._tasks.items() if t.status == TaskStatus.COMPLETED
            }
            return [t for t in self._tasks.values() if t.is_ready(completed_ids)]

    def get_execution_order(self) -> list[Task]:
        """基于拓扑排序返回任务的执行顺序。

        若存在循环依赖则抛出 ``ValueError``。
        """
        with self._lock:
            in_degree = {tid: 0 for tid in self._tasks}
            for task in self._tasks.values():
                for dep in task.dependencies:
                    if dep in self._tasks:
                        in_degree[task.id] += 1

            queue = deque([tid for tid, degree in in_degree.items() if degree == 0])
            order: list[str] = []

            while queue:
                tid = queue.popleft()
                order.append(tid)
                for task in self._tasks.values():
                    if tid in task.dependencies:
                        in_degree[task.id] -= 1
                        if in_degree[task.id] == 0:
                            queue.append(task.id)

            if len(order) != len(self._tasks):
                raise ValueError("存在循环依赖，无法生成执行顺序")

            return [self._tasks[tid] for tid in order]

    def update_task_status(
        self, task_id: str, status: TaskStatus, result: TaskResult | None = None
    ) -> None:
        """更新任务状态，可选地设置执行结果。"""
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                self._logger.warning("更新状态时发现未知任务: %s", task_id)
                return

            task.status = status
            if result is not None:
                task.result = result

            if status == TaskStatus.RUNNING and task.started_at is None:
                task.started_at = datetime.now()
            if status in (
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
                TaskStatus.CANCELLED,
            ):
                task.completed_at = datetime.now()

    def get_all_tasks(self) -> list[Task]:
        """返回所有已注册的任务。"""
        with self._lock:
            return list(self._tasks.values())
