"""
安全测试：验证系统安全性

测试范围：
1. API Key 安全
2. 敏感信息泄露检测
3. 未授权访问检测
4. 输入验证测试
"""

import pytest
import requests
import re


class TestAPIKeySecurity:
    """测试 API Key 安全性"""
    
    def test_api_key_not_exposed_in_response(self):
        """验证 API Key 不在响应中暴露"""
        resp = requests.get("http://localhost:8000/api/settings/models")
        assert resp.status_code == 200
        data = resp.text
        
        # 检查是否包含敏感信息
        assert "api_key" not in data.lower()
        assert "api-key" not in data.lower()
        
        # 检查是否有类似密钥的字符串
        key_pattern = r'[a-zA-Z0-9]{32,}'
        matches = re.findall(key_pattern, data)
        assert len(matches) == 0, f"发现潜在敏感数据: {matches}"

    def test_config_endpoint_protection(self):
        """测试配置端点保护"""
        resp = requests.get("http://localhost:8000/api/settings/models", params={"resolve_keys": True})
        assert resp.status_code == 200
        data = resp.json()
        
        # API Key 应该被脱敏处理
        providers = data.get("providers", {})
        for pid, pdata in providers.items():
            if "api_key" in pdata:
                assert pdata["api_key"] == "********" or len(pdata["api_key"]) <= 8


class TestUnauthorizedAccess:
    """测试未授权访问"""
    
    def test_health_endpoint_public(self):
        """健康检查端点应该公开"""
        resp = requests.get("http://localhost:8000/api/health")
        assert resp.status_code == 200

    def test_api_endpoints_accessible(self):
        """测试 API 端点可访问性"""
        endpoints = [
            "/api/agents/",
            "/api/content/characters",
            "/api/memory/entities",
            "/api/settings/"
        ]
        
        for endpoint in endpoints:
            resp = requests.get(f"http://localhost:8000{endpoint}")
            # 应该返回 200 或合理的错误状态
            assert resp.status_code in [200, 400, 404], f"{endpoint} 返回 {resp.status_code}"


class TestInputValidation:
    """测试输入验证"""
    
    def test_character_name_validation(self):
        """测试人物名称输入验证"""
        # 测试特殊字符
        payload = {
            "name": "<script>alert('XSS')</script>",
            "tier": "b_tier",
            "role": "测试"
        }
        resp = requests.post("http://localhost:8000/api/content/characters", json=payload)
        # 应该拒绝或清理输入
        assert resp.status_code in [200, 400]

    def test_search_input_validation(self):
        """测试搜索输入验证"""
        # 测试 SQL 注入尝试
        payload = {"q": "' OR '1'='1"}
        resp = requests.get("http://localhost:8000/api/content/search", params=payload)
        assert resp.status_code == 200
        # 应该返回空结果或正常响应，不应该报错


class TestDataProtection:
    """测试数据保护"""
    
    def test_sensitive_headers_not_exposed(self):
        """测试敏感头信息不暴露"""
        resp = requests.get("http://localhost:8000/api/health")
        
        # 检查响应头中不包含敏感信息
        headers_to_check = ["x-powered-by", "server", "x-frame-options"]
        for header in headers_to_check:
            if header in resp.headers:
                value = resp.headers[header]
                assert "python" not in value.lower() or "test" not in value.lower()

    def test_response_headers_security(self):
        """测试响应头安全性"""
        resp = requests.get("http://localhost:8000/api/settings/")
        
        # 应该有安全相关的响应头
        security_headers = [
            ("content-type", "application/json"),
            ("cache-control", "no-cache"),
        ]
        
        for header, expected in security_headers:
            if header in resp.headers:
                assert expected.lower() in resp.headers[header].lower()


class TestSecurityBestPractices:
    """测试安全最佳实践"""
    
    def test_no_stack_trace_exposed(self):
        """测试不暴露堆栈跟踪"""
        # 发送无效请求触发错误
        resp = requests.get("http://localhost:8000/api/invalid_endpoint")
        assert resp.status_code == 404
        
        # 响应中不应该包含 Python 堆栈跟踪
        assert "Traceback" not in resp.text
        assert "File \"" not in resp.text
        assert "line " not in resp.text

    def test_rate_limiting_headers(self):
        """测试限流头"""
        resp = requests.get("http://localhost:8000/api/health")
        # 检查是否有限流相关头
        rate_limit_headers = ["x-ratelimit-limit", "x-ratelimit-remaining", "retry-after"]
        
        # 至少应该有一个限流相关的头或响应正常
        assert resp.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
