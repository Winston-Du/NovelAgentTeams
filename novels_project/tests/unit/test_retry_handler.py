"""
单元测试：重试处理器模块

测试范围：
1. RateLimitHandler 类的所有方法
2. retry_on_rate_limit 便捷函数
"""
import pytest
from unittest.mock import patch, MagicMock

from novels_project.retry_handler import RateLimitHandler, retry_on_rate_limit


class TestRateLimitHandlerInit:
    """测试 RateLimitHandler 初始化"""

    def test_default_params(self):
        """默认参数初始化"""
        handler = RateLimitHandler()
        assert handler.max_retries == 3
        assert handler.base_delay == 1.0

    def test_custom_params(self):
        """自定义参数初始化"""
        handler = RateLimitHandler(max_retries=5, base_delay=2.0)
        assert handler.max_retries == 5
        assert handler.base_delay == 2.0


class TestParseRetryAfter:
    """测试 parse_retry_after"""

    def test_with_retry_after_header(self):
        """异常有 Retry-After 头"""
        handler = RateLimitHandler()
        mock_response = MagicMock()
        mock_response.headers = {"Retry-After": "30"}
        error = Exception("429 error")
        error.response = mock_response
        result = handler.parse_retry_after(error)
        assert result == 30

    def test_with_lowercase_retry_after(self):
        """异常有小写 retry-after 头"""
        handler = RateLimitHandler()
        mock_response = MagicMock()
        mock_response.headers = {"retry-after": "15"}
        error = Exception("429 error")
        error.response = mock_response
        result = handler.parse_retry_after(error)
        assert result == 15

    def test_with_x_ratelimit_reset_requests(self):
        """异常有 X-Ratelimit-Reset-Requests 头"""
        handler = RateLimitHandler()
        mock_response = MagicMock()
        mock_response.headers = {"X-Ratelimit-Reset-Requests": "60"}
        error = Exception("429 error")
        error.response = mock_response
        result = handler.parse_retry_after(error)
        assert result == 60

    def test_with_lowercase_x_ratelimit_reset(self):
        """异常有小写 x-ratelimit-reset-requests 头"""
        handler = RateLimitHandler()
        mock_response = MagicMock()
        mock_response.headers = {"x-ratelimit-reset-requests": "45"}
        error = Exception("429 error")
        error.response = mock_response
        result = handler.parse_retry_after(error)
        assert result == 45

    def test_retry_after_takes_priority(self):
        """Retry-After 优先级高于 X-Ratelimit-Reset-Requests"""
        handler = RateLimitHandler()
        mock_response = MagicMock()
        mock_response.headers = {
            "Retry-After": "30",
            "X-Ratelimit-Reset-Requests": "60",
        }
        error = Exception("429 error")
        error.response = mock_response
        result = handler.parse_retry_after(error)
        assert result == 30

    def test_no_response(self):
        """异常没有 response 属性"""
        handler = RateLimitHandler()
        error = Exception("some error")
        result = handler.parse_retry_after(error)
        assert result is None

    def test_response_without_headers(self):
        """response 没有 headers 属性"""
        handler = RateLimitHandler()
        mock_response = MagicMock(spec=[])
        error = Exception("429 error")
        error.response = mock_response
        result = handler.parse_retry_after(error)
        assert result is None

    def test_malformed_response(self):
        """response 格式异常"""
        handler = RateLimitHandler()
        # 创建一个没有 headers 属性的 response
        class BadResponse:
            pass
        error = Exception("429 error")
        error.response = BadResponse()
        result = handler.parse_retry_after(error)
        assert result is None

    def test_non_numeric_header_value(self):
        """header 值不是数字时返回 None（被内部 try/except 捕获）"""
        handler = RateLimitHandler()
        class MockResponse:
            def __init__(self):
                self.headers = {"Retry-After": "invalid"}
        error = Exception("429 error")
        error.response = MockResponse()
        result = handler.parse_retry_after(error)
        assert result is None


class TestExponentialBackoff:
    """测试 exponential_backoff"""

    def test_with_retry_after(self):
        """有 retry_after 参数"""
        handler = RateLimitHandler(base_delay=1.0)
        delay = handler.exponential_backoff(attempt=2, retry_after=10)
        # retry_after + 2 = 12
        assert delay == 12

    def test_without_retry_after_first_attempt(self):
        """无 retry_after，第1次尝试"""
        handler = RateLimitHandler(base_delay=1.0)
        with patch("random.uniform", return_value=0.05):
            delay = handler.exponential_backoff(attempt=0)
        # base_delay * (2^0) + jitter = 1.0 + 0.05 = 1.05
        assert delay == pytest.approx(1.05)

    def test_without_retry_after_second_attempt(self):
        """无 retry_after，第2次尝试"""
        handler = RateLimitHandler(base_delay=1.0)
        with patch("random.uniform", return_value=0.1):
            delay = handler.exponential_backoff(attempt=1)
        # base_delay * (2^1) + jitter = 2.0 + 0.1 = 2.1
        assert delay == pytest.approx(2.1)

    def test_with_custom_base_delay(self):
        """自定义 base_delay"""
        handler = RateLimitHandler(base_delay=3.0)
        with patch("random.uniform", return_value=0.05):
            delay = handler.exponential_backoff(attempt=0)
        # 3.0 * (2^0) + 0.05 = 3.05
        assert delay == pytest.approx(3.05)


class TestRetryOnRateLimitDecorator:
    """测试 retry_on_rate_limit 装饰器"""

    def test_function_succeeds_first_try(self):
        """函数第一次就成功"""
        handler = RateLimitHandler(max_retries=3)

        @handler.retry_on_rate_limit
        def good_func():
            return "success"

        result = good_func()
        assert result == "success"

    def test_retry_then_succeed(self):
        """先失败429然后成功"""
        handler = RateLimitHandler(max_retries=3)
        call_count = [0]

        @handler.retry_on_rate_limit
        def flaky_func():
            call_count[0] += 1
            if call_count[0] < 2:
                raise Exception("429 Too Many Requests")
            return "success"

        with patch.object(handler, "parse_retry_after", return_value=5):
            with patch("time.sleep"):
                with patch.object(handler, "exponential_backoff", return_value=1.0):
                    result = flaky_func()
        assert result == "success"
        assert call_count[0] == 2

    def test_non_rate_limit_error_raises_immediately(self):
        """非限流错误立即抛出"""
        handler = RateLimitHandler(max_retries=3)

        @handler.retry_on_rate_limit
        def bad_func():
            raise ValueError("not a rate limit error")

        with pytest.raises(ValueError, match="not a rate limit error"):
            bad_func()

    def test_non_rate_limit_error_caught(self):
        """非限流错误通过 try/except 捕获验证"""
        handler = RateLimitHandler(max_retries=3)

        @handler.retry_on_rate_limit
        def bad_func():
            raise RuntimeError("some other error")

        caught = False
        try:
            bad_func()
        except RuntimeError:
            caught = True
        assert caught

    def test_exceeds_max_retries(self):
        """超过最大重试次数"""
        handler = RateLimitHandler(max_retries=2)

        @handler.retry_on_rate_limit
        def always_fail():
            raise Exception("429 rate limit exceeded")

        with patch.object(handler, "parse_retry_after", return_value=None):
            with patch("time.sleep"):
                with patch.object(handler, "exponential_backoff", return_value=0.01):
                    with pytest.raises(Exception, match="429 rate limit exceeded"):
                        always_fail()

    def test_max_retries_zero(self):
        """max_retries=0 时立即失败"""
        handler = RateLimitHandler(max_retries=0)

        @handler.retry_on_rate_limit
        def always_fail():
            raise Exception("429 rate limit exceeded")

        with patch.object(handler, "parse_retry_after", return_value=None):
            with patch("time.sleep"):
                with patch.object(handler, "exponential_backoff", return_value=0.01):
                    with pytest.raises(Exception, match="429 rate limit exceeded"):
                        always_fail()

    def test_rate_limit_in_message(self):
        """错误消息中包含 'rate limit'"""
        handler = RateLimitHandler(max_retries=1)
        call_count = [0]

        @handler.retry_on_rate_limit
        def func():
            call_count[0] += 1
            if call_count[0] < 2:
                raise Exception("Rate limit reached, please wait")
            return "ok"

        with patch.object(handler, "parse_retry_after", return_value=None):
            with patch("time.sleep"):
                with patch.object(handler, "exponential_backoff", return_value=0.01):
                    result = func()
        assert result == "ok"

    def test_decorator_preserves_func_name(self):
        """装饰器保留函数名"""
        handler = RateLimitHandler()

        @handler.retry_on_rate_limit
        def my_function():
            pass

        assert my_function.__name__ == "my_function"

    def test_last_attempt_does_not_retry(self):
        """最后一次尝试失败不再重试"""
        handler = RateLimitHandler(max_retries=0)

        @handler.retry_on_rate_limit
        def func():
            raise Exception("429 error")

        with pytest.raises(Exception, match="429 error"):
            func()

    def test_with_retry_after_in_headers(self):
        """有 Retry-After 头的重试（覆盖日志分支）"""
        handler = RateLimitHandler(max_retries=1)
        call_count = [0]

        @handler.retry_on_rate_limit
        def func():
            call_count[0] += 1
            if call_count[0] < 2:
                raise Exception("429 Too Many Requests")
            return "ok"

        with patch.object(handler, "parse_retry_after", return_value=10):
            with patch("time.sleep"):
                with patch.object(handler, "exponential_backoff", return_value=12.0):
                    result = func()
        assert result == "ok"


class TestConvenienceFunction:
    """测试 retry_on_rate_limit 便捷函数"""

    def test_convenience_function_works(self):
        """便捷函数可用"""
        @retry_on_rate_limit
        def good_func():
            return "hello"

        assert good_func.__name__ == "good_func"
        result = good_func()
        assert result == "hello"

    def test_convenience_function_retries(self):
        """便捷函数可重试"""
        call_count = [0]

        @retry_on_rate_limit
        def flaky():
            call_count[0] += 1
            if call_count[0] < 2:
                raise Exception("429 rate limit")
            return "done"

        import novels_project.retry_handler as rh
        with patch.object(rh._default_handler, "parse_retry_after", return_value=None):
            with patch("time.sleep"):
                with patch.object(rh._default_handler, "exponential_backoff", return_value=0.01):
                    result = flaky()
        assert result == "done"
        assert call_count[0] == 2