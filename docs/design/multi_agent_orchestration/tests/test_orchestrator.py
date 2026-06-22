import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest

from core.dependency_manager import DependencyManager
from core.orchestrator import Orchestrator
from core.retry import RetryExecutor
from core.scheduler import QueueMode, Scheduler
from core.sub_agent import BaseSubAgent
from core.task import (
    RetryPolicy,
    RetryPolicyType,
    Task,
    TaskPriority,
    TaskResult,
    TaskStatus,
)
from core.task_planner import TaskPlanner


class DummyAgent(BaseSubAgent):
    """测试用 Dummy Agent，直接返回成功结果。"""

    @property
    def agent_type(self) -> str:
        return "dummy"

    def _run_task(self, task: Task) -> TaskResult:
        return TaskResult(success=True, output=f"executed {task.name}")


class TestTaskPlanner(unittest.TestCase):
    """任务规划器测试。"""

    def test_decompose(self) -> None:
        planner = TaskPlanner()
        planner.register_decomposer(
            predicate=lambda t: t.name == "root",
            decomposer=lambda t: [Task(name="sub1"), Task(name="sub2")],
        )
        root = Task(name="root")
        planned = planner.plan(root)

        self.assertEqual(len(planned.subtasks), 2)
        self.assertIn(planned.subtasks[0].id, planned.dependencies)
        self.assertIn(planned.subtasks[1].id, planned.dependencies)


class TestDependencyManager(unittest.TestCase):
    """依赖管理器测试。"""

    def test_execution_order(self) -> None:
        dm = DependencyManager()
        a = Task(name="A")
        b = Task(name="B")
        c = Task(name="C")
        b.add_dependency(a)
        c.add_dependency(b)
        dm.add_task(a)
        dm.add_task(b)
        dm.add_task(c)

        order = dm.get_execution_order()
        names = [t.name for t in order]
        self.assertEqual(names, ["A", "B", "C"])

    def test_cycle_detection(self) -> None:
        dm = DependencyManager()
        a = Task(name="A")
        b = Task(name="B")
        a.add_dependency(b)
        b.add_dependency(a)
        dm.add_task(a)
        dm.add_task(b)

        cycle = dm.detect_cycles()
        self.assertIsNotNone(cycle)
        self.assertIn(a.id, cycle)
        self.assertIn(b.id, cycle)


class TestRetryExecutor(unittest.TestCase):
    """重试执行器测试。"""

    def test_retry_until_success(self) -> None:
        executor = RetryExecutor()
        counter = [0]

        def work() -> TaskResult:
            counter[0] += 1
            if counter[0] < 3:
                raise TimeoutError("transient failure")
            return TaskResult(success=True, output="ok")

        policy = RetryPolicy(
            max_retries=3,
            delay=0.01,
            policy_type=RetryPolicyType.FIXED,
            transient_exceptions=(TimeoutError,),
        )
        result = executor.execute(work, policy)
        self.assertTrue(result.success)
        self.assertEqual(counter[0], 3)

    def test_non_transient_no_retry(self) -> None:
        executor = RetryExecutor()

        def work() -> TaskResult:
            raise ValueError("permanent failure")

        policy = RetryPolicy(
            max_retries=3,
            delay=0.01,
            transient_exceptions=(TimeoutError,),
        )
        result = executor.execute(work, policy)
        self.assertFalse(result.success)
        self.assertIn("permanent failure", result.error)


class TestSchedulerQueue(unittest.TestCase):
    """调度器队列测试。"""

    def test_fifo_order(self) -> None:
        scheduler = Scheduler(mode=QueueMode.FIFO)
        t1 = Task(name="t1", priority=TaskPriority.LOW)
        t2 = Task(name="t2", priority=TaskPriority.HIGH)
        t3 = Task(name="t3", priority=TaskPriority.NORMAL)
        scheduler.submit_task(t1)
        scheduler.submit_task(t2)
        scheduler.submit_task(t3)

        items = []
        while True:
            try:
                items.append(scheduler._queue.get(block=False))
            except Exception:
                break

        ids = [item if isinstance(item, str) else item[2] for item in items]
        self.assertEqual(ids, [t1.id, t2.id, t3.id])

    def test_priority_order(self) -> None:
        scheduler = Scheduler(mode=QueueMode.PRIORITY)
        tasks = {
            "low": Task(name="low", priority=TaskPriority.LOW),
            "critical": Task(name="critical", priority=TaskPriority.CRITICAL),
            "high": Task(name="high", priority=TaskPriority.HIGH),
            "normal": Task(name="normal", priority=TaskPriority.NORMAL),
        }
        for task in tasks.values():
            scheduler.submit_task(task)

        items = []
        while True:
            try:
                items.append(scheduler._queue.get(block=False))
            except Exception:
                break

        ids = [item[2] for item in items]
        name_map = {t.id: name for name, t in tasks.items()}
        ordered_names = [name_map[tid] for tid in ids]
        self.assertEqual(ordered_names, ["critical", "high", "normal", "low"])


class TestOrchestrator(unittest.TestCase):
    """编排器端到端测试。"""

    def test_execute_simple_task(self) -> None:
        orch = Orchestrator()
        agent = DummyAgent("dummy_1", capabilities=["dummy"])
        orch.register_agent(agent)

        root = Task(name="root", capabilities_required=["dummy"])
        result = orch.execute(root)

        self.assertTrue(result.success)
        self.assertIn("executed root", result.output)
        self.assertEqual(root.status, TaskStatus.COMPLETED)

    def test_execute_with_decomposition(self) -> None:
        orch = Orchestrator()
        orch.task_planner.register_decomposer(
            predicate=lambda t: t.name == "chapter",
            decomposer=lambda t: [
                Task(name="outline", capabilities_required=["writer"]),
                Task(name="draft", capabilities_required=["writer"]),
            ],
        )
        agent = DummyAgent("writer_1", capabilities=["writer"])
        orch.register_agent(agent)

        root = Task(name="chapter", capabilities_required=["writer"])
        result = orch.execute(root)

        self.assertTrue(result.success)
        self.assertEqual(root.status, TaskStatus.COMPLETED)

    def test_execute_container_root(self) -> None:
        """测试根任务作为容器（无 capabilities_required），由子任务结果汇总。"""
        orch = Orchestrator()
        orch.task_planner.register_decomposer(
            predicate=lambda t: t.name == "write_chapter",
            decomposer=lambda t: [
                Task(name=f"{t.name}_outline", capabilities_required=["writer"]),
                Task(name=f"{t.name}_draft", capabilities_required=["writer"]),
            ],
        )
        agent = DummyAgent("writer_1", capabilities=["writer"])
        orch.register_agent(agent)

        root = Task(name="write_chapter")
        result = orch.execute(root)

        self.assertTrue(result.success)
        self.assertIn("write_chapter_outline", result.output)
        self.assertIn("write_chapter_draft", result.output)


if __name__ == "__main__":
    unittest.main()
