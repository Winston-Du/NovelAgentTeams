"""任务规划模块。

支持基于规则的任务分解、递归展开以及优先级动态调整。
"""

from __future__ import annotations

import logging
from typing import Callable

from .task import Task, TaskPriority


class TaskPlanner:
    """任务规划器。

    支持：
    - 注册分解规则（predicate + decomposer）
    - 注册优先级调整器
    - 递归分解任务
    """

    def __init__(self, max_depth: int = 5) -> None:
        self._decomposers: list[
            tuple[Callable[[Task], bool], Callable[[Task], list[Task]], int]
        ] = []
        self._priority_adjusters: list[Callable[[Task], TaskPriority | None]] = []
        self._max_depth = max_depth
        self._logger = logging.getLogger("multi_agent_orchestration.task_planner")

    def register_decomposer(
        self,
        predicate: Callable[[Task], bool],
        decomposer: Callable[[Task], list[Task]],
        max_depth: int | None = None,
    ) -> None:
        """注册一条任务分解规则。

        当 ``predicate(task)`` 为 True 时，使用 ``decomposer(task)`` 生成子任务。
        ``max_depth`` 控制该规则递归分解的最大深度。
        """
        depth = max_depth if max_depth is not None else self._max_depth
        self._decomposers.append((predicate, decomposer, depth))
        self._logger.info("注册任务分解规则 | max_depth=%d", depth)

    def register_priority_adjuster(
        self, adjuster: Callable[[Task], TaskPriority | None]
    ) -> None:
        """注册一个优先级调整器。"""
        self._priority_adjusters.append(adjuster)
        self._logger.info("注册优先级调整器")

    def plan(self, root: Task) -> Task:
        """对根任务进行规划，返回规划后的根任务。"""
        self._decompose(root, 0)
        self._adjust_priority(root)
        return root

    def _decompose(self, task: Task, depth: int) -> None:
        """递归分解任务。"""
        for predicate, decomposer, max_depth in self._decomposers:
            if depth >= max_depth:
                continue
            if predicate(task):
                children = decomposer(task)
                if not children:
                    continue
                # 清空旧子任务并重新建立依赖
                task.subtasks = []
                task.dependencies = [
                    dep
                    for dep in task.dependencies
                    if dep not in {child.id for child in children}
                ]
                for child in children:
                    task.add_subtask(child)
                    self._decompose(child, depth + 1)
                break

    def _adjust_priority(self, task: Task) -> None:
        """递归应用优先级调整器。"""
        for adjuster in self._priority_adjusters:
            new_priority = adjuster(task)
            if new_priority is not None:
                task.priority = new_priority
                break
        for child in task.subtasks:
            self._adjust_priority(child)
