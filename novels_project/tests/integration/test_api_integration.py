"""
集成测试：API 集成测试

测试范围：
1. Agent 配置 API
2. 内容管理 API
3. 记忆管理 API
4. 系统设置 API

前置条件：
- 后端服务已启动 (http://localhost:8000)
"""

import pytest
import requests
import json


class TestAgentAPI:
    """测试 Agent 配置 API"""
    
    BASE_URL = "http://localhost:8000/api/agents"

    def test_get_agents(self):
        """测试获取所有 Agent 配置"""
        resp = requests.get(f"{self.BASE_URL}/")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)
        assert "master" in data
        assert "character_designer" in data
        assert "plot_writer" in data
        assert "proofreader" in data

    def test_get_single_agent(self):
        """测试获取单个 Agent"""
        resp = requests.get(f"{self.BASE_URL}/master")
        assert resp.status_code == 200
        data = resp.json()
        assert "name" in data
        assert "model" in data
        assert "enabled" in data

    def test_update_agent(self):
        """测试更新 Agent 配置"""
        payload = {"temperature": 0.8}
        resp = requests.put(f"{self.BASE_URL}/master", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "updated"
        config = data.get("config", {})
        assert config.get("temperature") == 0.8

    def test_toggle_agent(self):
        """测试启用/禁用 Agent"""
        # 禁用
        resp = requests.put(f"{self.BASE_URL}/proofreader/toggle", json={"enabled": False})
        assert resp.status_code == 200
        assert resp.json()["enabled"] == False
        
        # 重新启用
        resp = requests.put(f"{self.BASE_URL}/proofreader/toggle", json={"enabled": True})
        assert resp.status_code == 200
        assert resp.json()["enabled"] == True

    def test_get_agent_status(self):
        """测试获取 Agent 状态"""
        resp = requests.get(f"{self.BASE_URL}/master/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "name" in data
        assert "enabled" in data
        assert "model" in data
        assert "status" in data


class TestContentAPI:
    """测试内容管理 API"""
    
    BASE_URL = "http://localhost:8000/api/content"

    def test_get_characters(self):
        """测试获取人物卡列表"""
        resp = requests.get(f"{self.BASE_URL}/characters")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_create_and_delete_character(self):
        """测试创建和删除人物卡"""
        # 创建
        payload = {
            "name": "测试人物_集成测试",
            "tier": "b_tier",
            "role": "测试角色",
            "brief": "集成测试人物"
        }
        resp = requests.post(f"{self.BASE_URL}/characters", json=payload)
        assert resp.status_code == 200
        assert resp.json()["status"] == "created"
        
        # 删除
        resp = requests.delete(f"{self.BASE_URL}/characters/测试人物_集成测试")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    def test_get_chapters(self):
        """测试获取章节列表"""
        resp = requests.get(f"{self.BASE_URL}/chapters")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_global_search(self):
        """测试全局搜索"""
        resp = requests.get(f"{self.BASE_URL}/search", params={"q": "测试"})
        assert resp.status_code == 200
        data = resp.json()
        assert "query" in data
        assert "count" in data
        assert "results" in data


class TestMemoryAPI:
    """测试记忆管理 API"""
    
    BASE_URL = "http://localhost:8000/api/memory"

    def test_get_entities(self):
        """测试获取实体列表"""
        resp = requests.get(f"{self.BASE_URL}/entities")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "entities" in data

    def test_get_memory_stats(self):
        """测试获取记忆统计"""
        resp = requests.get(f"{self.BASE_URL}/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)
        assert "node_count" in data
        assert "edge_count" in data

    def test_search_memory(self):
        """测试记忆搜索"""
        resp = requests.get(f"{self.BASE_URL}/search", params={"q": "人物"})
        assert resp.status_code == 200
        data = resp.json()
        assert "query" in data
        assert "results" in data


class TestSettingsAPI:
    """测试系统设置 API"""
    
    BASE_URL = "http://localhost:8000/api/settings"

    def test_get_settings(self):
        """测试获取系统设置"""
        resp = requests.get(f"{self.BASE_URL}/")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    def test_get_model_providers(self):
        """测试获取模型供应商配置"""
        resp = requests.get(f"{self.BASE_URL}/models")
        assert resp.status_code == 200
        data = resp.json()
        assert "providers" in data


class TestHealthCheck:
    """测试健康检查"""
    
    def test_health_check(self):
        """测试服务健康检查"""
        resp = requests.get("http://localhost:8000/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
