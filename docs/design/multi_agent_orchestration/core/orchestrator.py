"""Multi-Agent Orchestrator。

顶层编排器，整合 TaskPlanner、DependencyManager、Scheduler、RetryExecutor 和 MessageBus，
提供 ``execute(root_task)`` 统一入口。
"""

from __future__ import annotations

import logging
import time
from typing import Any

from .dependency_manager import DependencyManager
from .messaging import MessageBus
from .retry import RetryExecutor
from .scheduler import QueueMode, Scheduler
from .sub_agent import BaseSubAgent
from .task import Task, TaskResult, TaskStatus
from .task_planner import TaskPlanner


class Orchestrator:
    """多 Agent 编排器。

    使用示例：
        orchestrator = Orchestrator()
        orchestrator.register_agent(MyAgent("agent_1", capabilities=["writer"]))

        # 根任务作为容器，不设置 capabilities_required，由子任务结果汇总
        root = Task(name="write_chapter")
        result = orchestrator.execute(root)
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        self.message_bus = MessageBus()
        self.task_planner = TaskPlanner(
            max_depth=self.config.get("planner", {}).get("max_depth", 5)
        )
        self.dependency_manager = DependencyManager()
        self.retry_executor = RetryExecutor()

        scheduler_config = self.config.get("scheduler", {})
        mode_name = scheduler_config.get("mode", "FIFO").upper()
        self.scheduler = Scheduler(
            message_bus=self.message_bus,
            mode=QueueMode[mode_name],
            poll_interval=scheduler_config.get("poll_interval", 0.05),
            retry_executor=self.retry_executor,
        )
        self.scheduler.set_callbacks(
            on_start=self._on_task_start,
            on_complete=self._on_task_complete,
        )

        self._agents: list[BaseSubAgent] = []
        self._logger = logging.getLogger("multi_agent_orchestration.orchestrator")

    def register_agent(self, agent: BaseSubAgent) -> None:
        """注册 SubAgent 到编排器。"""
        self._agents.append(agent)
        self.scheduler.register_agent(agent)
        self._logger.info(
            "注册 Agent | id=%s type=%s", agent.agent_id, agent.agent_type
        )

    def _on_task_start(self, task: Task) -> None:
        """任务开始执行时回调。"""
        self.dependency_manager.update_task_status(task.id, TaskStatus.RUNNING)

    def _on_task_complete(self, task: Task, result: TaskResult) -> None:
        """任务完成时回调。"""
        status = TaskStatus.COMPLETED if result.success else TaskStatus.FAILED
        self.dependency_manager.update_task_status(task.id, status, result)

    @staticmethod
    def _is_container_task(task: Task) -> bool:
        """判断任务是否为容器任务（仅有子任务而无执行能力）。"""
        return len(task.subtasks) > 0 and len(task.capabilities_required) == 0

    def execute(self, root_task: Task) -> TaskResult:
        """执行一个根任务并返回最终执行结果。

        流程：
        1. 任务规划（分解 + 优先级调整）
        2. 建立依赖图并检测循环依赖
        3. 启动调度器循环
        4. 持续提交可执行任务到调度器
        5. 等待所有任务完成
        6. 停止调度器并返回根任务结果
        """
        self._logger.info("开始执行任务 | task=%s", root_task.name)

        planned_root = self.task_planner.plan(root_task)
        self.dependency_manager.add_task(planned_root)

        cycle = self.dependency_manager.detect_cycles()
        if cycle is not None:
            raise ValueError(f"检测到循环依赖: {cycle}")

        self.scheduler.start()
        try:
            exec_config = self.config.get("execution", {})
            poll_interval = exec_config.get("poll_interval", 0.05)
            stop_on_failure = exec_config.get("stop_on_failure", False)

            while True:
                ready_tasks = self.dependency_manager.get_ready_tasks()
                for task in ready_tasks:
                    if self._is_container_task(task):
                        # 容器任务不需要执行，仅更新状态，结果由最后汇总逻辑生成
                        task.status = TaskStatus.COMPLETED
                        continue
                    if not self.scheduler.is_scheduled(task.id):
                        self.scheduler.submit_task(task)

                time.sleep(poll_interval)

                all_tasks = self.dependency_manager.get_all_tasks()
                active_states = (TaskStatus.PENDING, TaskStatus.RUNNING)
                active_exists = any(t.status in active_states for t in all_tasks)

                if stop_on_failure and any(
                    t.status == TaskStatus.FAILED for t in all_tasks
                ):
                    break

                if not active_exists and self.scheduler.is_idle():
                    break
        finally:
            self.scheduler.stop()

        root = self.dependency_manager._tasks.get(root_task.id, root_task)
        if root.result is not None:
            return root.result

        # 对容器根任务，根据子任务结果汇总
        if self._is_container_task(root):
            failed_children = [
                child for child in root.subtasks if child.status == TaskStatus.FAILED
            ]
            success = len(failed_children) == 0 and all(
                child.status == TaskStatus.COMPLETED for child in root.subtasks
            )
            return TaskResult(
                success=success,
                output={child.name: child.result.output for child in root.subtasks if child.result},
                error=None if success else f"子任务失败: {[c.name for c in failed_children]}",
            )

        success = root.status == TaskStatus.COMPLETED
        return TaskResult(
            success=success,
            output=root.payload,
            error=None if success else "任务未完成或执行失败",
        )
