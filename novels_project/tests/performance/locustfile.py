"""
性能测试配置文件

使用 Locust 进行性能测试

安装依赖:
    pip install locust

运行命令:
    locust -f tests/performance/locustfile.py --host=http://localhost:8000
"""

from locust import HttpUser, task, between, TaskSet, events
import time


class UserBehavior(TaskSet):
    """用户行为模拟"""

    @task(3)
    def get_agents(self):
        """获取 Agent 配置"""
        self.client.get("/api/agents/")

    @task(3)
    def get_characters(self):
        """获取人物卡列表"""
        self.client.get("/api/content/characters")

    @task(2)
    def get_chapters(self):
        """获取章节列表"""
        self.client.get("/api/content/chapters")

    @task(2)
    def get_entities(self):
        """获取实体列表"""
        self.client.get("/api/memory/entities")

    @task(1)
    def global_search(self):
        """全局搜索"""
        self.client.get("/api/content/search?q=测试")

    @task(1)
    def health_check(self):
        """健康检查"""
        self.client.get("/api/health")


class WebsiteUser(HttpUser):
    """网站用户模拟"""
    tasks = [UserBehavior]
    wait_time = between(1, 3)  # 每次请求间隔 1-3 秒
    host = "http://localhost:8000"


# 性能指标监控
def on_request_success(request_type, name, response_time, response_length):
    """请求成功回调"""
    print(f"✅ {request_type} {name} - {response_time:.2f}ms - {response_length} bytes")


def on_request_failure(request_type, name, response_time, exception):
    """请求失败回调"""
    print(f"❌ {request_type} {name} - {response_time:.2f}ms - {exception}")


# 注册事件监听器
events.request_success.add_listener(on_request_success)
events.request_failure.add_listener(on_request_failure)


class PerformanceTestMetrics:
    """性能测试指标"""
    
    PERFORMANCE_TARGETS = {
        "api_response_time": 500,      # 毫秒
        "ai_response_time": 10000,     # 毫秒
        "error_rate": 0.01,            # 1%
        "requests_per_second": 10,     # QPS
    }
    
    @staticmethod
    def check_performance(response_time_ms: float, endpoint: str) -> bool:
        """检查性能是否达标"""
        if "optimize" in endpoint.lower():
            return response_time_ms <= PerformanceTestMetrics.PERFORMANCE_TARGETS["ai_response_time"]
        return response_time_ms <= PerformanceTestMetrics.PERFORMANCE_TARGETS["api_response_time"]
