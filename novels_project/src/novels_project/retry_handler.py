"""
重试处理器 - 处理 API 限流和重试逻辑
"""
import time
import logging
from typing import Callable, Any, Optional
from functools import wraps

logger = logging.getLogger(__name__)


class RateLimitHandler:
    """处理 API 速率限制和重试逻辑"""

    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        """
        初始化重试处理器

        Args:
            max_retries: 最大重试次数
            base_delay: 基础延迟时间（秒）
        """
        self.max_retries = max_retries
        self.base_delay = base_delay

    def parse_retry_after(self, error: Exception) -> Optional[int]:
        """
        从异常中解析 Retry-After 时间

        Args:
            error: 异常对象

        Returns:
            重试等待时间（秒），如果无法解析则返回 None
        """
        error_str = str(error)

        # 尝试从错误消息中提取响应信息
        # OpenAI SDK 的 429 错误通常包含完整响应
        try:
            # 检查是否有 openai 的错误对象
            if hasattr(error, 'response'):
                response = error.response
                if hasattr(response, 'headers'):
                    # 优先使用 Retry-After
                    retry_after = response.headers.get('Retry-After') or \
                                  response.headers.get('retry-after')
                    if retry_after:
                        return int(retry_after)

                    # 尝试 X-Ratelimit-Reset-Requests
                    reset_time = response.headers.get('X-Ratelimit-Reset-Requests') or \
                                 response.headers.get('x-ratelimit-reset-requests')
                    if reset_time:
                        return int(reset_time)
        except Exception as e:
            logger.debug(f"无法解析重试时间: {e}")

        return None

    def exponential_backoff(self, attempt: int, retry_after: Optional[int] = None) -> float:
        """
        计算指数退避延迟时间

        Args:
            attempt: 当前尝试次数（从0开始）
            retry_after: 服务器指定的重试时间

        Returns:
            延迟时间（秒）
        """
        if retry_after is not None:
            # 如果服务器指定了重试时间，使用它（加一点缓冲）
            return retry_after + 2

        # 否则使用指数退避：1s, 2s, 4s, 8s, ...
        delay = self.base_delay * (2 ** attempt)

        # 添加抖动，避免惊群效应
        import random
        jitter = random.uniform(0, 0.1 * delay)

        return delay + jitter

    def retry_on_rate_limit(self, func: Callable) -> Callable:
        """
        装饰器：在遇到速率限制时自动重试

        Args:
            func: 要包装的函数

        Returns:
            包装后的函数
        """
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(self.max_retries + 1):
                try:
                    return func(*args, **kwargs)

                except Exception as e:
                    error_str = str(e).lower()

                    # 检查是否是 429 速率限制错误
                    if '429' not in error_str and 'rate limit' not in error_str:
                        # 不是速率限制错误，直接抛出
                        raise

                    last_exception = e

                    # 如果已经是最后一次尝试，不再重试
                    if attempt >= self.max_retries:
                        logger.warning(f"达到最大重试次数 {self.max_retries}，放弃重试")
                        break

                    # 解析重试时间
                    retry_after = self.parse_retry_after(e)
                    delay = self.exponential_backoff(attempt, retry_after)

                    if retry_after:
                        logger.info(
                            f"遇到速率限制，服务器要求 {retry_after}秒后重试 "
                            f"(实际等待 {delay:.1f}秒，尝试 {attempt + 1}/{self.max_retries})"
                        )
                    else:
                        logger.info(
                            f"遇到速率限制，使用指数退避 "
                            f"(等待 {delay:.1f}秒，尝试 {attempt + 1}/{self.max_retries})"
                        )

                    time.sleep(delay)

            # 所有重试都失败了，抛出最后一个异常
            logger.error(f"重试失败: {last_exception}")
            raise last_exception

        return wrapper


# 全局实例
_default_handler = RateLimitHandler(max_retries=3, base_delay=1.0)


def retry_on_rate_limit(func: Callable) -> Callable:
    """
    便捷装饰器：使用默认配置的重试处理器

    用法:
        @retry_on_rate_limit
        def my_api_call():
            ...
    """
    return _default_handler.retry_on_rate_limit(func)
