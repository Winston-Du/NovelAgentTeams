"""重试机制模块。

提供带退避策略的重试执行器，支持 transient 失败判断与失败隔离。
"""

from __future__ import annotations

import logging
import time
from typing import Callable

from .task import RetryPolicy, TaskResult


class RetryExecutor:
    """重试执行器。

    支持：
    - 固定 / 线性 / 指数退避
    - transient 异常判断
    - 失败隔离（单个任务失败不会抛出异常）
    """

    def __init__(self, default_policy: RetryPolicy | None = None) -> None:
        self.default_policy = default_policy or RetryPolicy()
        self._logger = logging.getLogger("multi_agent_orchestration.retry")

    def is_transient(self, exception: Exception, policy: RetryPolicy | None = None) -> bool:
        """判断异常是否属于可重试的 transient 失败。"""
        policy = policy or self.default_policy
        return isinstance(exception, policy.transient_exceptions)

    def execute(
        self,
        callable_obj: Callable[[], TaskResult],
        policy: RetryPolicy | None = None,
        task_id: str = "",
    ) -> TaskResult:
        """执行可调用对象，按策略进行重试。

        即使最终失败也返回 ``TaskResult``，不会将异常抛出到调用方。
        """
        policy = policy or self.default_policy
        last_exception: Exception | None = None

        for attempt in range(policy.max_retries + 1):
            try:
                return callable_obj()
            except Exception as exc:
                last_exception = exc
                if not self.is_transient(exc, policy):
                    self._logger.debug(
                        "非 transient 异常，停止重试 | task=%s error=%s",
                        task_id,
                        exc,
                    )
                    break

                if attempt == policy.max_retries:
                    break

                delay = policy.compute_backoff(attempt)
                self._logger.info(
                    "任务重试 | task=%s attempt=%d/%d delay=%.2fs",
                    task_id,
                    attempt + 1,
                    policy.max_retries,
                    delay,
                )
                if delay > 0:
                    time.sleep(delay)

        return TaskResult(
            success=False,
            error=str(last_exception) if last_exception else "未知错误",
        )
