"""Task 18: Memory Config API 端点集成测试。

验证:
1. GET /api/memory-config/agents/{agent_id} - 获取合并后配置
2. PUT /api/memory-config/agents/{agent_id} - 更新配置
3. POST /api/memory-config/agents/{agent_id}/reset - 重置配置
4. GET /api/memory-config/agents - 列出所有配置
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from novels_project.server import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    """创建测试客户端，使用临时目录作为项目根。"""
    # 创建临时配置目录和文件
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    # 写入初始配置
    config_path = config_dir / "memory_config.yaml"
    config_path.write_text(
        "global:\n"
        "  chapter_window: 100\n"
        "  max_summary_blocks: 3\n"
        "  dialogue_compression_threshold: 0.5\n"
        "  preserve_recent_messages: 4\n"
        "agents:\n"
        "  plot_writer:\n"
        "    max_summary_blocks: 5\n"
        "    dialogue_compression_threshold: 0.6\n",
        encoding="utf-8",
    )

    # 修改项目根目录 - 必须在导入模块前 patch
    # patch novels_project.api.memory_config.get_config_dir (实际使用的位置)
    import novels_project.api.memory_config as mc
    monkeypatch.setattr(mc, "get_config_dir", lambda: config_dir)
    # 也 patch project_config 以防其他地方用
    import novels_project.project_config as pc
    monkeypatch.setattr(pc, "get_config_dir", lambda: config_dir)

    app = create_app()
    yield TestClient(app)


class TestMemoryConfigAPI:
    """Memory Config API 测试。"""

    def test_get_memory_config(self, client):
        """GET /api/memory-config/agents/{agent_id} - 获取 agent 合并配置。"""
        response = client.get("/api/memory-config/agents/plot_writer")
        assert response.status_code == 200
        data = response.json()

        assert data["agent_id"] == "plot_writer"
        assert "config" in data
        assert "global_config" in data
        assert data["has_override"] is True
        # 验证合并：global + agent 覆盖
        assert data["config"]["max_summary_blocks"] == 5  # agent 覆盖
        assert data["config"]["chapter_window"] == 100  # global 默认

    def test_get_memory_config_no_override(self, client):
        """未配置 agent 时返回 global_config。"""
        response = client.get("/api/memory-config/agents/unknown_agent")
        assert response.status_code == 200
        data = response.json()

        assert data["agent_id"] == "unknown_agent"
        assert data["has_override"] is False
        assert data["config"] == data["global_config"]

    def test_put_memory_config(self, client):
        """PUT /api/memory-config/agents/{agent_id} - 更新 agent 配置。"""
        new_config = {
            "max_summary_blocks": 8,
            "dialogue_compression_threshold": 0.75,
        }
        response = client.put(
            "/api/memory-config/agents/proofreader",
            json={"config": new_config},
        )
        assert response.status_code == 200
        data = response.json()

        assert data["agent_id"] == "proofreader"
        assert data["config"]["max_summary_blocks"] == 8
        assert data["config"]["dialogue_compression_threshold"] == 0.75
        assert data["status"] == "updated"

        # 验证持久化：再次 GET
        response2 = client.get("/api/memory-config/agents/proofreader")
        assert response2.json()["config"]["max_summary_blocks"] == 8

    def test_put_memory_config_invalid_field(self, client):
        """无效字段被忽略，返回 400 当无有效字段时。"""
        response = client.put(
            "/api/memory-config/agents/test_agent",
            json={"config": {"invalid_field": 123}},
        )
        assert response.status_code == 400

    def test_reset_memory_config(self, client):
        """POST /api/memory-config/agents/{agent_id}/reset - 重置为 global。"""
        # 先确认有覆盖
        assert client.get("/api/memory-config/agents/plot_writer").json()["has_override"] is True

        # 重置
        response = client.post("/api/memory-config/agents/plot_writer/reset")
        assert response.status_code == 200
        data = response.json()

        assert data["agent_id"] == "plot_writer"
        assert data["status"] == "reset"
        assert data["config"] == client.get("/api/memory-config/agents/plot_writer").json()["global_config"]

        # 验证持久化：再次 GET
        response2 = client.get("/api/memory-config/agents/plot_writer")
        assert response2.json()["has_override"] is False

    def test_reset_already_default(self, client):
        """重置未配置的 agent 返回 already_default。"""
        response = client.post("/api/memory-config/agents/unknown/reset")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "already_default"

    def test_list_agent_configs(self, client):
        """GET /api/memory-config/agents - 列出所有配置。"""
        response = client.get("/api/memory-config/agents")
        assert response.status_code == 200
        data = response.json()

        assert "global_config" in data
        assert "agents" in data
        assert "plot_writer" in data["agents"]
        assert data["agents"]["plot_writer"]["max_summary_blocks"] == 5
