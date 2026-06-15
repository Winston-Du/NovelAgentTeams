"""
单元测试：API 模块路由

测试覆盖:
- agent.py: GET/POST/PUT 端点，错误响应
- content.py: 人物卡 CRUD、章节查询、暗线管理、搜索、批注
- memory.py: 实体/关系查询、图谱操作
- settings.py: 系统设置、模型供应商、备份
- workspace.py: 工作空间管理
"""
import json
import yaml
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock

from fastapi.testclient import TestClient


# =========================================================================
#  Fixtures
# =========================================================================

@pytest.fixture
def temp_project(tmp_path):
    """Create a temporary project directory structure."""
    project_root = tmp_path / "test_project"
    project_root.mkdir()

    # Create subdirectories
    (project_root / "config").mkdir()
    (project_root / "output" / "chapters").mkdir(parents=True)
    (project_root / "output" / "chapter_summaries").mkdir(parents=True)
    (project_root / "graph").mkdir()
    (project_root / "feedback").mkdir()
    (project_root / "sessions").mkdir()

    return project_root


@pytest.fixture
def system_config_dir(tmp_path):
    """Create a temporary system config directory."""
    config_dir = tmp_path / "system_config"
    config_dir.mkdir()
    return config_dir


@pytest.fixture
def client(temp_project, system_config_dir):
    """Create a FastAPI TestClient with mocked project config."""
    with patch("novels_project.project_config.get_project_root", return_value=temp_project), \
         patch("novels_project.project_config.get_system_config_dir", return_value=system_config_dir), \
         patch("novels_project.api.agent.get_system_config_dir", return_value=system_config_dir), \
         patch("novels_project.api.settings.get_system_config_dir", return_value=system_config_dir), \
         patch("novels_project.api.settings.get_project_root", return_value=temp_project), \
         patch("novels_project.api.settings.get_output_dir", return_value=temp_project / "output"), \
         patch("novels_project.api.content.get_project_root", return_value=temp_project), \
         patch("novels_project.api.content.get_character_cards_path", return_value=temp_project / "config" / "character_base_cards.yaml"), \
         patch("novels_project.api.content.get_chapters_dir", return_value=temp_project / "output" / "chapters"), \
         patch("novels_project.api.content.get_summaries_dir", return_value=temp_project / "output" / "chapter_summaries"), \
         patch("novels_project.api.content.get_output_dir", return_value=temp_project / "output"), \
         patch("novels_project.api.memory.get_project_root", return_value=temp_project), \
         patch("novels_project.api.workspace.get_project_root", return_value=temp_project):
        from novels_project.server import create_app
        app = create_app()
        yield TestClient(app)


# =========================================================================
#  Agent API
# =========================================================================

class TestAgentAPI:
    """Tests for /api/agents endpoints."""

    def test_get_agents(self, client):
        """GET /api/agents/ returns all agent configs."""
        resp = client.get("/api/agents/")
        assert resp.status_code == 200
        data = resp.json()
        assert "master" in data
        assert "character_designer" in data
        assert "plot_writer" in data
        assert "proofreader" in data

    def test_get_agent_models(self, client):
        """GET /api/agents/models returns available models."""
        resp = client.get("/api/agents/models")
        assert resp.status_code == 200
        data = resp.json()
        assert "providers" in data

    def test_get_single_agent(self, client):
        """GET /api/agents/{name} returns specific agent."""
        resp = client.get("/api/agents/master")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "主控 Agent"
        assert "model" in data

    def test_get_single_agent_404(self, client):
        """GET /api/agents/{name} returns 404 for unknown agent."""
        resp = client.get("/api/agents/nonexistent")
        assert resp.status_code == 404

    def test_update_agent(self, client, system_config_dir):
        """PUT /api/agents/{name} updates agent config."""
        resp = client.put("/api/agents/master", json={"temperature": 0.5})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "updated"

    def test_update_agent_404(self, client):
        """PUT /api/agents/{name} returns 404 for unknown agent."""
        resp = client.put("/api/agents/nonexistent", json={"temperature": 0.5})
        assert resp.status_code == 404

    def test_toggle_agent(self, client, system_config_dir):
        """PUT /api/agents/{name}/toggle enables/disables agent."""
        resp = client.put("/api/agents/master/toggle", json={"enabled": False})
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

    def test_toggle_agent_404(self, client):
        """PUT /api/agents/{name}/toggle returns 404 for unknown agent."""
        resp = client.put("/api/agents/nonexistent/toggle", json={"enabled": True})
        assert resp.status_code == 404

    def test_get_agent_status(self, client):
        """GET /api/agents/{name}/status returns agent status."""
        resp = client.get("/api/agents/master/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "master"
        assert "enabled" in data
        assert "model" in data
        assert "status" in data

    def test_get_agent_status_404(self, client):
        """GET /api/agents/{name}/status returns 404 for unknown agent."""
        resp = client.get("/api/agents/nonexistent/status")
        assert resp.status_code == 404

    def test_get_agents_with_custom(self, client, system_config_dir):
        """GET /api/agents/ includes custom agents from user config (covers line 115)."""
        agent_config_path = system_config_dir / "agent_config.yaml"
        with open(agent_config_path, "w", encoding="utf-8") as f:
            yaml.dump({"custom_agent": {"name": "Custom", "role": "custom"}}, f, allow_unicode=True)
        resp = client.get("/api/agents/")
        assert resp.status_code == 200
        data = resp.json()
        assert "custom_agent" in data
        assert "master" in data

    def test_update_agent_twice(self, client, system_config_dir):
        """PUT /api/agents/{name} twice covers both branches (name in/not in user_config)."""
        resp = client.put("/api/agents/master", json={"temperature": 0.3})
        assert resp.status_code == 200
        # Second update — agent already in user_config, skips if-block (170->173)
        resp = client.put("/api/agents/master", json={"temperature": 0.9})
        assert resp.status_code == 200
        assert resp.json()["config"]["temperature"] == 0.9

    def test_toggle_agent_twice(self, client, system_config_dir):
        """PUT /api/agents/{name}/toggle twice covers both branches (188->190)."""
        resp = client.put("/api/agents/master/toggle", json={"enabled": False})
        assert resp.status_code == 200
        # Second toggle — agent already in user_config
        resp = client.put("/api/agents/master/toggle", json={"enabled": True})
        assert resp.status_code == 200
        assert resp.json()["enabled"] is True


# =========================================================================
#  Content API - Characters
# =========================================================================

class TestContentCharactersAPI:
    """Tests for /api/content/characters endpoints."""

    SAMPLE_CHARACTER_CARDS = {
        "s_tier": {
            "characters": {
                "测试角色": {
                    "name": "测试角色",
                    "brief": "测试简介",
                    "role": "主角",
                    "personality": "勇敢",
                },
            },
        },
        "a_tier": {
            "characters": {
                "配角甲": {
                    "name": "配角甲",
                    "brief": "配角简介",
                },
            },
        },
    }

    def _write_character_cards(self, temp_project):
        """Write sample character cards to the project config."""
        cards_path = temp_project / "config" / "character_base_cards.yaml"
        with open(cards_path, "w", encoding="utf-8") as f:
            yaml.dump(self.SAMPLE_CHARACTER_CARDS, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    def test_get_characters_empty(self, client):
        """GET /api/content/characters returns empty list when no cards exist."""
        resp = client.get("/api/content/characters")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_characters_with_data(self, client, temp_project):
        """GET /api/content/characters returns character list."""
        self._write_character_cards(temp_project)
        resp = client.get("/api/content/characters")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        names = [c["name"] for c in data]
        assert "测试角色" in names

    def test_get_single_character(self, client, temp_project):
        """GET /api/content/characters/{name} returns character detail."""
        self._write_character_cards(temp_project)
        resp = client.get("/api/content/characters/测试角色")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "测试角色"
        assert data["tier"] == "s_tier"

    def test_get_single_character_404(self, client):
        """GET /api/content/characters/{name} returns 404 for unknown."""
        resp = client.get("/api/content/characters/不存在")
        assert resp.status_code == 404

    def test_create_character(self, client, temp_project):
        """POST /api/content/characters creates a new character."""
        self._write_character_cards(temp_project)
        resp = client.post("/api/content/characters", json={
            "name": "新角色",
            "tier": "b_tier",
            "brief": "新角色简介",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "新角色"
        assert data["status"] == "created"

    def test_update_character(self, client, temp_project):
        """PUT /api/content/characters/{name} updates a character."""
        self._write_character_cards(temp_project)
        resp = client.put("/api/content/characters/测试角色", json={
            "name": "测试角色",
            "brief": "更新后的简介",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "updated"

    def test_update_character_404(self, client):
        """PUT /api/content/characters/{name} returns 404 for unknown."""
        resp = client.put("/api/content/characters/不存在", json={
            "name": "不存在",
            "brief": "简介",
        })
        assert resp.status_code == 404

    def test_delete_character(self, client, temp_project):
        """DELETE /api/content/characters/{name} deletes a character."""
        self._write_character_cards(temp_project)
        resp = client.delete("/api/content/characters/配角甲")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    def test_delete_character_404(self, client):
        """DELETE /api/content/characters/{name} returns 404 for unknown."""
        resp = client.delete("/api/content/characters/不存在")
        assert resp.status_code == 404

    # --- Direct nested structure (no "characters" sub-key) ---

    DIRECT_NESTED_CARDS = {
        "s_tier": {
            "直接角色": {
                "name": "直接角色",
                "brief": "直接嵌套简介",
                "role": "主角",
                "personality": "勇敢",
            },
        },
    }

    def _write_direct_cards(self, temp_project):
        cards_path = temp_project / "config" / "character_base_cards.yaml"
        with open(cards_path, "w", encoding="utf-8") as f:
            yaml.dump(self.DIRECT_NESTED_CARDS, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    def test_get_characters_direct_nested(self, client, temp_project):
        """GET /api/content/characters with direct nested structure (no characters sub-key)."""
        self._write_direct_cards(temp_project)
        resp = client.get("/api/content/characters")
        assert resp.status_code == 200
        names = [c["name"] for c in resp.json()]
        assert "直接角色" in names

    def test_get_character_direct_nested(self, client, temp_project):
        """GET /api/content/characters/{name} with direct nested structure."""
        self._write_direct_cards(temp_project)
        resp = client.get("/api/content/characters/直接角色")
        assert resp.status_code == 200
        assert resp.json()["name"] == "直接角色"
        assert resp.json()["tier"] == "s_tier"

    def test_update_character_direct_nested(self, client, temp_project):
        """PUT /api/content/characters/{name} with direct nested structure."""
        self._write_direct_cards(temp_project)
        resp = client.put("/api/content/characters/直接角色", json={
            "name": "直接角色",
            "brief": "更新后的简介",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "updated"

    def test_delete_character_direct_nested(self, client, temp_project):
        """DELETE /api/content/characters/{name} with direct nested structure."""
        self._write_direct_cards(temp_project)
        resp = client.delete("/api/content/characters/直接角色")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    def test_create_character_in_existing_tier(self, client, temp_project):
        """POST /api/content/characters into a tier that already has characters sub-key (covers line 165)."""
        self._write_character_cards(temp_project)
        resp = client.post("/api/content/characters", json={
            "name": "新S级角色",
            "tier": "s_tier",
            "brief": "S级新角色",
        })
        assert resp.status_code == 200
        assert resp.json()["tier"] == "s_tier"
        assert resp.json()["status"] == "created"

    def test_create_character_tier_non_dict(self, client, temp_project):
        """POST /api/content/characters replaces non-dict tier with dict (covers 155->157, 159-160)."""
        cards_path = temp_project / "config" / "character_base_cards.yaml"
        with open(cards_path, "w", encoding="utf-8") as f:
            yaml.dump({"b_tier": None}, f, allow_unicode=True)
        resp = client.post("/api/content/characters", json={
            "name": "新角色",
            "tier": "b_tier",
            "brief": "简介",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "created"

    def test_get_characters_with_null_tier(self, client, temp_project):
        """GET /api/content/characters skips null tiers (covers 109->107)."""
        cards_path = temp_project / "config" / "character_base_cards.yaml"
        with open(cards_path, "w", encoding="utf-8") as f:
            yaml.dump({
                "s_tier": None,
                "a_tier": {
                    "characters": {
                        "角色A": {"name": "角色A", "brief": "简介"},
                    },
                },
            }, f, allow_unicode=True)
        resp = client.get("/api/content/characters")
        assert resp.status_code == 200
        names = [c["name"] for c in resp.json()]
        assert "角色A" in names

    def test_get_characters_skip_non_dict_chars(self, client, temp_project):
        """GET /api/content/characters skips non-dict chars values (covers 114->107, 116->115)."""
        cards_path = temp_project / "config" / "character_base_cards.yaml"
        with open(cards_path, "w", encoding="utf-8") as f:
            yaml.dump({
                "s_tier": {
                    "characters": "not_a_dict",
                    "_meta": "metadata",
                },
                "a_tier": {
                    "characters": {
                        "_internal": "skip_me",
                        "角色B": {"name": "角色B", "brief": "简介"},
                    },
                },
            }, f, allow_unicode=True)
        resp = client.get("/api/content/characters")
        assert resp.status_code == 200
        names = [c["name"] for c in resp.json()]
        assert "角色B" in names
        # _internal and _meta should be skipped
        assert "_internal" not in names
        assert "_meta" not in names

    def test_get_character_skip_non_dict_info(self, client, temp_project):
        """GET /api/content/characters/{name} skips non-dict character entries (covers 143->134)."""
        cards_path = temp_project / "config" / "character_base_cards.yaml"
        with open(cards_path, "w", encoding="utf-8") as f:
            yaml.dump({
                "s_tier": {
                    "角色A": "not_a_dict",
                    "characters": {
                        "角色B": {"name": "角色B", "brief": "简介"},
                    },
                },
            }, f, allow_unicode=True)
        resp = client.get("/api/content/characters/角色B")
        assert resp.status_code == 200
        assert resp.json()["name"] == "角色B"

    def test_get_character_skip_null_tier(self, client, temp_project):
        """GET /api/content/characters/{name} skips null tiers (covers 136->134)."""
        cards_path = temp_project / "config" / "character_base_cards.yaml"
        with open(cards_path, "w", encoding="utf-8") as f:
            yaml.dump({
                "s_tier": None,
                "a_tier": {
                    "characters": {
                        "角色C": {"name": "角色C", "brief": "简介"},
                    },
                },
            }, f, allow_unicode=True)
        resp = client.get("/api/content/characters/角色C")
        assert resp.status_code == 200
        assert resp.json()["name"] == "角色C"

    def test_get_character_non_dict_value(self, client, temp_project):
        """GET /api/content/characters/{name} returns 404 for non-dict char value (covers 143->134)."""
        cards_path = temp_project / "config" / "character_base_cards.yaml"
        with open(cards_path, "w", encoding="utf-8") as f:
            yaml.dump({
                "s_tier": {
                    "角色A": "not_a_dict",
                },
            }, f, allow_unicode=True)
        resp = client.get("/api/content/characters/角色A")
        assert resp.status_code == 404


# =========================================================================
#  Content API - Chapters
# =========================================================================

class TestContentChaptersAPI:
    """Tests for /api/content/chapters endpoints."""

    def _create_chapter(self, temp_project, chapter_id, title="测试章节", content="测试内容"):
        """Helper to create a chapter file."""
        chapters_dir = temp_project / "output" / "chapters"
        chapters_dir.mkdir(parents=True, exist_ok=True)
        chapter_file = chapters_dir / f"chapter_{chapter_id}_final.md"
        chapter_file.write_text(f"# {title}\n\n{content}", encoding="utf-8")

    def _create_summary(self, temp_project, chapter_id, title="测试章节"):
        """Helper to create a chapter summary file."""
        summaries_dir = temp_project / "output" / "chapter_summaries"
        summaries_dir.mkdir(parents=True, exist_ok=True)
        summary_file = summaries_dir / f"chapter_{chapter_id}_summary.yaml"
        with open(summary_file, "w", encoding="utf-8") as f:
            yaml.dump({"title": title, "summary": "章节摘要", "key_events": ["事件1"]}, f, allow_unicode=True)

    def test_get_chapters_empty(self, client):
        """GET /api/content/chapters returns empty when no chapters."""
        resp = client.get("/api/content/chapters")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_chapters_with_data(self, client, temp_project):
        """GET /api/content/chapters returns chapter list."""
        self._create_chapter(temp_project, "01")
        self._create_summary(temp_project, "01")
        resp = client.get("/api/content/chapters")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["chapter_id"] == "01"

    def test_get_single_chapter(self, client, temp_project):
        """GET /api/content/chapters/{id} returns chapter content."""
        self._create_chapter(temp_project, "01", "第一章", "这是第一章的内容。")
        resp = client.get("/api/content/chapters/01")
        assert resp.status_code == 200
        data = resp.json()
        assert data["chapter_id"] == "01"
        assert "第一章" in data["content"]

    def test_get_single_chapter_404(self, client):
        """GET /api/content/chapters/{id} returns 404 for unknown."""
        resp = client.get("/api/content/chapters/99")
        assert resp.status_code == 404

    def test_get_chapter_summary(self, client, temp_project):
        """GET /api/content/chapters/{id}/summary returns chapter summary."""
        self._create_summary(temp_project, "01")
        resp = client.get("/api/content/chapters/01/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "测试章节"

    def test_get_chapter_summary_404(self, client):
        """GET /api/content/chapters/{id}/summary returns 404 for unknown."""
        resp = client.get("/api/content/chapters/99/summary")
        assert resp.status_code == 404

    def test_get_chapters_no_dir(self, client, temp_project):
        """GET /api/content/chapters returns empty when chapters dir doesn't exist (covers 229)."""
        # Remove the chapters dir
        chapters_dir = temp_project / "output" / "chapters"
        if chapters_dir.exists():
            import shutil
            shutil.rmtree(chapters_dir)
        resp = client.get("/api/content/chapters")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_chapter_glob_fallback(self, client, temp_project):
        """GET /api/content/chapters/{id} finds chapter via glob when exact name missing (covers 276)."""
        chapters_dir = temp_project / "output" / "chapters"
        chapters_dir.mkdir(parents=True, exist_ok=True)
        chapter_file = chapters_dir / "chapter_01_v2.md"
        chapter_file.write_text("# 第一章\n\n内容", encoding="utf-8")
        resp = client.get("/api/content/chapters/01")
        assert resp.status_code == 200
        data = resp.json()
        assert data["chapter_id"] == "01"

    def test_get_chapter_with_summary(self, client, temp_project):
        """GET /api/content/chapters/{id} includes summary when available (covers 285-288)."""
        self._create_chapter(temp_project, "01", "第一章", "内容")
        self._create_summary(temp_project, "01", "第一章")
        resp = client.get("/api/content/chapters/01")
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"] is not None
        assert data["summary"]["summary"] == "章节摘要"

    def test_get_chapters_corrupt_summary(self, client, temp_project):
        """GET /api/content/chapters handles corrupt summary yaml (covers 241)."""
        self._create_chapter(temp_project, "01", "第一章", "内容")
        summaries_dir = temp_project / "output" / "chapter_summaries"
        summaries_dir.mkdir(parents=True, exist_ok=True)
        (summaries_dir / "chapter_01_summary.yaml").write_text("::: invalid yaml :::", encoding="utf-8")
        resp = client.get("/api/content/chapters")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_get_chapters_corrupt_chapter(self, client, temp_project):
        """GET /api/content/chapters handles unreadable chapter file (covers 251)."""
        chapters_dir = temp_project / "output" / "chapters"
        chapters_dir.mkdir(parents=True, exist_ok=True)
        # Create a directory instead of a file to cause read error
        (chapters_dir / "chapter_01_final.md").mkdir(exist_ok=True)
        resp = client.get("/api/content/chapters")
        assert resp.status_code == 200

    def test_get_chapter_corrupt_summary(self, client, temp_project):
        """GET /api/content/chapters/{id} handles corrupt summary (covers 288)."""
        self._create_chapter(temp_project, "01", "第一章", "内容")
        summaries_dir = temp_project / "output" / "chapter_summaries"
        summaries_dir.mkdir(parents=True, exist_ok=True)
        (summaries_dir / "chapter_01_summary.yaml").write_text("::: invalid yaml :::", encoding="utf-8")
        resp = client.get("/api/content/chapters/01")
        assert resp.status_code == 200
        assert "第一章" in resp.json()["content"]

    def test_get_chapter_no_title(self, client, temp_project):
        """GET /api/content/chapters/{id} returns None title when no # header (covers 293->298, 294->293)."""
        chapters_dir = temp_project / "output" / "chapters"
        chapters_dir.mkdir(parents=True, exist_ok=True)
        chapter_file = chapters_dir / "chapter_01_final.md"
        chapter_file.write_text("没有标题的内容\n\n普通文本", encoding="utf-8")
        resp = client.get("/api/content/chapters/01")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] is None
        assert "没有标题的内容" in data["content"]

    def test_get_chapters_non_title_first_line(self, client, temp_project):
        """GET /api/content/chapters handles chapter with no # in first line (covers 249->254)."""
        chapters_dir = temp_project / "output" / "chapters"
        chapters_dir.mkdir(parents=True, exist_ok=True)
        chapter_file = chapters_dir / "chapter_01_final.md"
        chapter_file.write_text("普通文本\n\n# 这个标题不会被提取", encoding="utf-8")
        resp = client.get("/api/content/chapters")
        assert resp.status_code == 200
        chapters = resp.json()
        assert len(chapters) >= 1


# =========================================================================
#  Content API - Plotlines
# =========================================================================

class TestContentPlotlinesAPI:
    """Tests for /api/content/plotlines endpoints."""

    def test_get_plotlines_empty(self, client):
        """GET /api/content/plotlines returns empty when no plotlines."""
        resp = client.get("/api/content/plotlines")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create_plotline(self, client, temp_project):
        """POST /api/content/plotlines creates a plotline."""
        resp = client.post("/api/content/plotlines", json={
            "name": "测试暗线",
            "description": "一条测试暗线",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "测试暗线"
        assert "id" in data

    def test_update_plotline(self, client, temp_project):
        """PUT /api/content/plotlines/{id} updates a plotline."""
        # Create first
        create_resp = client.post("/api/content/plotlines", json={
            "name": "测试暗线",
            "description": "描述",
        })
        pl_id = create_resp.json()["id"]

        resp = client.put(f"/api/content/plotlines/{pl_id}", json={
            "name": "更新后的暗线",
            "description": "更新后的描述",
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == "更新后的暗线"

    def test_update_plotline_404(self, client):
        """PUT /api/content/plotlines/{id} returns 404 for unknown."""
        resp = client.put("/api/content/plotlines/nonexistent", json={
            "name": "不存在",
            "description": "描述",
        })
        assert resp.status_code == 404

    def test_delete_plotline(self, client, temp_project):
        """DELETE /api/content/plotlines/{id} deletes a plotline."""
        create_resp = client.post("/api/content/plotlines", json={
            "name": "待删除暗线",
            "description": "描述",
        })
        pl_id = create_resp.json()["id"]

        resp = client.delete(f"/api/content/plotlines/{pl_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    def test_delete_plotline_404(self, client):
        """DELETE /api/content/plotlines/{id} returns 404 for unknown."""
        resp = client.delete("/api/content/plotlines/nonexistent")
        assert resp.status_code == 404

    def test_update_plotline_not_first(self, client, temp_project):
        """PUT /api/content/plotlines/{id} with multiple entries finds the right one (covers 371->370)."""
        # Create two plotlines
        client.post("/api/content/plotlines", json={
            "name": "暗线1",
            "description": "描述1",
        })
        create_resp = client.post("/api/content/plotlines", json={
            "name": "暗线2",
            "description": "描述2",
        })
        pl_id = create_resp.json()["id"]
        # Update the second one (not the first)
        resp = client.put(f"/api/content/plotlines/{pl_id}", json={
            "name": "更新后的暗线2",
            "description": "更新后的描述",
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == "更新后的暗线2"

    def test_delete_plotline_not_first(self, client, temp_project):
        """DELETE /api/content/plotlines/{id} with multiple entries finds the right one (covers 385->384)."""
        client.post("/api/content/plotlines", json={
            "name": "暗线1",
            "description": "描述1",
        })
        create_resp = client.post("/api/content/plotlines", json={
            "name": "暗线2",
            "description": "描述2",
        })
        pl_id = create_resp.json()["id"]
        resp = client.delete(f"/api/content/plotlines/{pl_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"


# =========================================================================
#  Content API - Search & Annotate
# =========================================================================

class TestContentSearchAPI:
    """Tests for /api/content/search."""

    def test_search_empty(self, client):
        """GET /api/content/search returns empty results."""
        resp = client.get("/api/content/search", params={"q": "测试"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "测试"
        assert "results" in data

    def test_search_missing_query(self, client):
        """GET /api/content/search returns 422 without query."""
        resp = client.get("/api/content/search")
        assert resp.status_code == 422

    def test_search_with_results(self, client, temp_project):
        """GET /api/content/search returns results across all content types."""
        # Characters
        cards_path = temp_project / "config" / "character_base_cards.yaml"
        with open(cards_path, "w", encoding="utf-8") as f:
            yaml.dump({
                "s_tier": {
                    "characters": {
                        "英雄角色": {"name": "英雄角色", "brief": "英雄简介", "role": "主角", "personality": "勇敢"},
                    },
                },
            }, f, allow_unicode=True)
        # Chapter summaries
        summaries_dir = temp_project / "output" / "chapter_summaries"
        summaries_dir.mkdir(parents=True, exist_ok=True)
        with open(summaries_dir / "chapter_01_summary.yaml", "w", encoding="utf-8") as f:
            yaml.dump({"title": "第一章", "summary": "英雄出场", "key_events": ["事件1"], "characters_appeared": ["英雄角色"]}, f, allow_unicode=True)
        # Plotlines
        plotlines_path = temp_project / "output" / "plotlines.yaml"
        with open(plotlines_path, "w", encoding="utf-8") as f:
            yaml.dump([{"id": "pl1", "name": "英雄暗线", "description": "英雄的成长之路", "related_characters": ["英雄角色"]}], f, allow_unicode=True)

        resp = client.get("/api/content/search", params={"q": "英雄"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "英雄"
        assert data["count"] >= 2
        types = [r["type"] for r in data["results"]]
        assert "character" in types
        assert "chapter" in types
        assert "plotline" in types

    def test_search_with_corrupt_summary(self, client, temp_project):
        """GET /api/content/search handles corrupt chapter summary (covers 442-443)."""
        summaries_dir = temp_project / "output" / "chapter_summaries"
        summaries_dir.mkdir(parents=True, exist_ok=True)
        (summaries_dir / "chapter_01_summary.yaml").write_text("::: invalid yaml :::", encoding="utf-8")
        resp = client.get("/api/content/search", params={"q": "英雄"})
        assert resp.status_code == 200
        assert resp.json()["query"] == "英雄"

    def test_search_no_match(self, client, temp_project):
        """GET /api/content/search returns empty when no match (covers 449->447)."""
        plots_path = temp_project / "output" / "plotlines.yaml"
        with open(plots_path, "w", encoding="utf-8") as f:
            yaml.dump([{"id": "pl1", "name": "无关情节", "description": "无关内容"}], f, allow_unicode=True)
        resp = client.get("/api/content/search", params={"q": "不存在的关键词"})
        assert resp.status_code == 200
        assert resp.json()["count"] == 0


class TestContentAnnotateAPI:
    """Tests for /api/content/annotate."""

    def test_annotate_content(self, client, temp_project):
        """POST /api/content/annotate submits an annotation."""
        resp = client.post("/api/content/annotate", json={
            "content_type": "character",
            "content_id": "测试角色",
            "note": "需要改进性格描述",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "submitted"
        assert "annotation_id" in data


# =========================================================================
#  Content API - Optimize
# =========================================================================

class TestContentOptimizeAPI:
    """Tests for /api/content/characters/optimize."""

    def _setup_provider(self, system_config_dir):
        """Set up a mock model provider."""
        providers_path = system_config_dir / "model_providers.yaml"
        with open(providers_path, "w", encoding="utf-8") as f:
            yaml.dump({
                "providers": {
                    "test": {
                        "name": "Test Provider",
                        "base_url": "https://test.api.com/v1",
                        "api_key": "test-key",
                        "models": [
                            {"id": "test-model", "name": "Test Model", "max_tokens": 4096, "context_window": 128000},
                        ],
                    },
                },
            }, f)

    def test_optimize_no_providers(self, client, temp_project, system_config_dir):
        """POST /api/content/characters/optimize returns 503 when no providers."""
        # Create an empty model providers file so load_model_providers returns empty
        providers_path = system_config_dir / "model_providers.yaml"
        with open(providers_path, "w", encoding="utf-8") as f:
            yaml.dump({"providers": {}}, f)
        resp = client.post("/api/content/characters/optimize", json={
            "field": "brief",
            "current_value": "测试内容",
            "character_name": "测试角色",
        })
        assert resp.status_code == 503
        assert "没有配置任何模型供应商" in resp.json()["detail"]

    def test_optimize_no_valid_client(self, client, system_config_dir):
        """POST /api/content/characters/optimize returns 503 when no valid client (covers 522)."""
        providers_path = system_config_dir / "model_providers.yaml"
        with open(providers_path, "w", encoding="utf-8") as f:
            yaml.dump({
                "providers": {
                    "bad": {
                        "name": "Bad Provider",
                        "base_url": "",
                        "api_key": "",
                        "models": [],
                    },
                },
            }, f)
        resp = client.post("/api/content/characters/optimize", json={
            "field": "brief",
            "current_value": "测试内容",
            "character_name": "测试角色",
        })
        assert resp.status_code == 503
        assert "没有可用的模型供应商" in resp.json()["detail"]

    def test_optimize_success(self, client, system_config_dir):
        """POST /api/content/characters/optimize returns optimized content (covers 499-589)."""
        self._setup_provider(system_config_dir)

        # Mock the OpenAI client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "优化后的简介内容"
        mock_openai_client = MagicMock()
        mock_openai_client.chat.completions.create.return_value = mock_response

        mock_oc_client = MagicMock()
        mock_oc_client.client = mock_openai_client

        with patch("novels_project.api_client.OpenAICompatibleClient", return_value=mock_oc_client):
            resp = client.post("/api/content/characters/optimize", json={
                "field": "brief",
                "current_value": "原始简介",
                "character_name": "测试角色",
                "context": {"role": "主角", "personality": "勇敢"},
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["field"] == "brief"
            assert data["optimized_value"] == "优化后的简介内容"

    def test_optimize_api_error(self, client, system_config_dir):
        """POST /api/content/characters/optimize returns 502 on API error (covers 589-590)."""
        self._setup_provider(system_config_dir)

        mock_openai_client = MagicMock()
        mock_openai_client.chat.completions.create.side_effect = Exception("API error")
        mock_oc_client = MagicMock()
        mock_oc_client.client = mock_openai_client

        with patch("novels_project.api_client.OpenAICompatibleClient", return_value=mock_oc_client):
            resp = client.post("/api/content/characters/optimize", json={
                "field": "brief",
                "current_value": "原始简介",
                "character_name": "测试角色",
            })
            assert resp.status_code == 502
            assert "模型调用失败" in resp.json()["detail"]

    def test_optimize_skip_empty_base_url(self, client, system_config_dir):
        """POST /api/content/characters/optimize skips providers with empty base_url (covers 503)."""
        providers_path = system_config_dir / "model_providers.yaml"
        with open(providers_path, "w", encoding="utf-8") as f:
            yaml.dump({
                "providers": {
                    "bad": {
                        "name": "Bad",
                        "base_url": "",
                        "api_key": "key",
                        "models": [{"id": "m", "name": "M", "max_tokens": 4096, "context_window": 128000}],
                    },
                },
            }, f)
        resp = client.post("/api/content/characters/optimize", json={
            "field": "brief",
            "current_value": "测试",
            "character_name": "角色",
        })
        assert resp.status_code == 503
        assert "没有可用的模型供应商" in resp.json()["detail"]

    def test_optimize_skip_empty_api_key(self, client, system_config_dir):
        """POST /api/content/characters/optimize skips providers with empty api_key (covers 511)."""
        providers_path = system_config_dir / "model_providers.yaml"
        with open(providers_path, "w", encoding="utf-8") as f:
            yaml.dump({
                "providers": {
                    "bad": {
                        "name": "Bad",
                        "base_url": "https://test.com/v1",
                        "api_key": "",
                        "models": [{"id": "m", "name": "M", "max_tokens": 4096, "context_window": 128000}],
                    },
                },
            }, f)
        resp = client.post("/api/content/characters/optimize", json={
            "field": "brief",
            "current_value": "测试",
            "character_name": "角色",
        })
        assert resp.status_code == 503
        assert "没有可用的模型供应商" in resp.json()["detail"]

    def test_optimize_skip_empty_models(self, client, system_config_dir):
        """POST /api/content/characters/optimize skips providers with empty models (covers 511)."""
        providers_path = system_config_dir / "model_providers.yaml"
        with open(providers_path, "w", encoding="utf-8") as f:
            yaml.dump({
                "providers": {
                    "bad": {
                        "name": "Bad",
                        "base_url": "https://test.com/v1",
                        "api_key": "key",
                        "models": [],
                    },
                },
            }, f)
        resp = client.post("/api/content/characters/optimize", json={
            "field": "brief",
            "current_value": "测试",
            "character_name": "角色",
        })
        assert resp.status_code == 503
        assert "没有可用的模型供应商" in resp.json()["detail"]

    def test_optimize_skip_client_exception(self, client, system_config_dir):
        """POST /api/content/characters/optimize skips providers with client creation error (covers 519-520)."""
        self._setup_provider(system_config_dir)
        with patch("novels_project.api_client.OpenAICompatibleClient", side_effect=Exception("Init error")):
            resp = client.post("/api/content/characters/optimize", json={
                "field": "brief",
                "current_value": "测试",
                "character_name": "角色",
            })
        assert resp.status_code == 503
        assert "没有可用的模型供应商" in resp.json()["detail"]

    def test_optimize_skip_non_dict_provider(self, client, system_config_dir):
        """POST /api/content/characters/optimize skips non-dict providers (covers 503)."""
        providers_path = system_config_dir / "model_providers.yaml"
        with open(providers_path, "w", encoding="utf-8") as f:
            yaml.dump({
                "providers": {
                    "string_provider": "not_a_dict",
                    "good": {
                        "name": "Good",
                        "base_url": "",
                        "api_key": "",
                        "models": [],
                    },
                },
            }, f)
        resp = client.post("/api/content/characters/optimize", json={
            "field": "brief",
            "current_value": "测试",
            "character_name": "角色",
        })
        assert resp.status_code == 503

    def test_optimize_skip_empty_model_id(self, client, system_config_dir):
        """POST /api/content/characters/optimize skips model with empty id (covers 511)."""
        providers_path = system_config_dir / "model_providers.yaml"
        with open(providers_path, "w", encoding="utf-8") as f:
            yaml.dump({
                "providers": {
                    "bad": {
                        "name": "Bad",
                        "base_url": "https://test.com/v1",
                        "api_key": "key",
                        "models": [{"id": "", "name": "Empty", "max_tokens": 4096, "context_window": 128000}],
                    },
                },
            }, f)
        resp = client.post("/api/content/characters/optimize", json={
            "field": "brief",
            "current_value": "测试",
            "character_name": "角色",
        })
        assert resp.status_code == 503
        assert "没有可用的模型供应商" in resp.json()["detail"]

    def test_optimize_with_context_skip(self, client, system_config_dir):
        """POST /api/content/characters/optimize skips falsy context fields (covers 546->545)."""
        self._setup_provider(system_config_dir)
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "优化后"
        mock_openai_client = MagicMock()
        mock_openai_client.chat.completions.create.return_value = mock_response
        mock_oc_client = MagicMock()
        mock_oc_client.client = mock_openai_client

        with patch("novels_project.api_client.OpenAICompatibleClient", return_value=mock_oc_client):
            resp = client.post("/api/content/characters/optimize", json={
                "field": "brief",
                "current_value": "原始",
                "character_name": "角色",
                "context": {"role": "", "brief": "should_skip", "unknown_field": "x"},
            })
            assert resp.status_code == 200


# =========================================================================
#  Memory API
# =========================================================================

class TestMemoryAPI:
    """Tests for /api/memory endpoints."""

    @pytest.fixture(autouse=True)
    def mock_graph(self):
        """Mock GraphStore and GraphQuery to avoid file system dependencies."""
        with patch("novels_project.api.memory.GraphStore") as mock_store_cls, \
             patch("novels_project.api.memory.GraphQuery") as mock_query_cls:
            mock_store = MagicMock()
            mock_query = MagicMock()

            # Configure mock store
            mock_store.get_all_entities.return_value = [
                {"name": "陆商曜", "type": "character", "brief": "主角"},
                {"name": "黑商周桓", "type": "character", "brief": "反派"},
            ]
            mock_store.get_entity.return_value = {"name": "陆商曜", "type": "character", "brief": "主角"}
            mock_store.has_entity.return_value = True
            mock_store.update_entity.return_value = True
            mock_store.remove_entity.return_value = None
            mock_store.get_relations.return_value = [
                {"source": "陆商曜", "target": "黑商周桓", "type": "enemy"},
            ]
            mock_store.add_relation.return_value = True
            mock_store.remove_relation.return_value = None
            mock_store.get_statistics.return_value = {
                "node_count": 2, "edge_count": 1,
                "node_types": {"character": 2},
                "relation_types": {"enemy": 1},
                "is_directed": True,
            }
            mock_store.load.return_value = True
            mock_store.save.return_value = None

            # Configure mock query
            mock_query.get_character_network.return_value = {
                "character": {"name": "陆商曜", "type": "character"},
                "direct_relations": [],
                "indirect_relations": [],
                "events": [],
                "organizations": [],
                "related_concepts": [],
            }
            mock_query.find_unresolved_foreshadowing.return_value = []
            mock_query.search.return_value = [
                {"name": "陆商曜", "type": "character", "brief": "主角", "role": "主角"},
            ]

            mock_store_cls.return_value = mock_store
            mock_query_cls.return_value = mock_query

            # Also need to reset global state in memory module
            import novels_project.api.memory as mem_mod
            mem_mod._graph_store = None
            mem_mod._graph_query = None

            yield mock_store, mock_query

    def test_get_entities(self, client):
        """GET /api/memory/entities returns entity list."""
        resp = client.get("/api/memory/entities")
        assert resp.status_code == 200
        data = resp.json()
        assert "entities" in data
        assert data["total"] >= 0

    def test_get_entities_with_search(self, client):
        """GET /api/memory/entities with search filter."""
        resp = client.get("/api/memory/entities", params={"search": "陆商曜"})
        assert resp.status_code == 200

    def test_get_entity_detail(self, client):
        """GET /api/memory/entities/{id} returns entity detail."""
        resp = client.get("/api/memory/entities/陆商曜")
        assert resp.status_code == 200
        data = resp.json()
        assert "entity" in data
        assert "relations" in data

    def test_get_entity_detail_404(self, client, mock_graph):
        """GET /api/memory/entities/{id} returns 404 for unknown."""
        mock_store, _ = mock_graph
        mock_store.get_entity.return_value = None
        resp = client.get("/api/memory/entities/不存在")
        assert resp.status_code == 404

    def test_update_entity(self, client):
        """PUT /api/memory/entities/{id} updates entity."""
        resp = client.put("/api/memory/entities/陆商曜", json={
            "brief": "更新后的简介",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "updated"

    def test_update_entity_404(self, client, mock_graph):
        """PUT /api/memory/entities/{id} returns 404 for unknown."""
        mock_store, _ = mock_graph
        mock_store.has_entity.return_value = False
        resp = client.put("/api/memory/entities/不存在", json={"brief": "简介"})
        assert resp.status_code == 404

    def test_delete_entity(self, client):
        """DELETE /api/memory/entities/{id} deletes entity."""
        resp = client.delete("/api/memory/entities/陆商曜")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    def test_delete_entity_404(self, client, mock_graph):
        """DELETE /api/memory/entities/{id} returns 404 for unknown."""
        mock_store, _ = mock_graph
        mock_store.has_entity.return_value = False
        resp = client.delete("/api/memory/entities/不存在")
        assert resp.status_code == 404

    def test_get_relations(self, client):
        """GET /api/memory/relations returns relations list."""
        resp = client.get("/api/memory/relations")
        assert resp.status_code == 200
        data = resp.json()
        assert "relations" in data

    def test_get_relations_with_entity(self, client):
        """GET /api/memory/relations filtered by entity."""
        resp = client.get("/api/memory/relations", params={"entity_id": "陆商曜"})
        assert resp.status_code == 200

    def test_create_relation(self, client):
        """POST /api/memory/relations creates a relation."""
        resp = client.post("/api/memory/relations", json={
            "source": "陆商曜",
            "target": "黑商周桓",
            "relation_type": "enemy",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "created"

    def test_delete_relation(self, client):
        """DELETE /api/memory/relations deletes a relation."""
        resp = client.delete("/api/memory/relations", params={
            "source": "陆商曜",
            "target": "黑商周桓",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    def test_get_character_network(self, client):
        """GET /api/memory/network/{name} returns character network."""
        resp = client.get("/api/memory/network/陆商曜")
        assert resp.status_code == 200
        data = resp.json()
        assert data["center"] == "陆商曜"
        assert "network" in data

    def test_get_character_network_404(self, client, mock_graph):
        """GET /api/memory/network/{name} returns 404 for unknown."""
        _, mock_query = mock_graph
        mock_query.get_character_network.return_value = {"error": "未找到人物「不存在」"}
        resp = client.get("/api/memory/network/不存在")
        assert resp.status_code == 404

    def test_get_foreshadowing(self, client):
        """GET /api/memory/foreshadow returns unresolved foreshadowing."""
        resp = client.get("/api/memory/foreshadow")
        assert resp.status_code == 200
        data = resp.json()
        assert "unresolved" in data

    def test_get_memory_stats(self, client):
        """GET /api/memory/stats returns memory statistics."""
        resp = client.get("/api/memory/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "node_count" in data

    def test_search_memory(self, client):
        """GET /api/memory/search searches memory."""
        resp = client.get("/api/memory/search", params={"q": "陆商曜"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "陆商曜"
        assert "results" in data

    def test_search_memory_missing_query(self, client):
        """GET /api/memory/search returns 422 without query."""
        resp = client.get("/api/memory/search")
        assert resp.status_code == 422

    def test_init_graph(self, client, temp_project):
        """POST /api/memory/init initializes graph from workspace."""
        # Create character cards for init
        cards_path = temp_project / "config" / "character_base_cards.yaml"
        with open(cards_path, "w", encoding="utf-8") as f:
            yaml.dump({
                "s_tier": {
                    "characters": {
                        "测试角色": {"name": "测试角色", "brief": "简介"},
                    },
                },
            }, f, allow_unicode=True)

        resp = client.post("/api/memory/init")
        assert resp.status_code in (200, 501)  # 501 if import fails

    def test_get_relations_by_type(self, client):
        """GET /api/memory/relations filters by relation_type (covers 156)."""
        resp = client.get("/api/memory/relations", params={"relation_type": "enemy"})
        assert resp.status_code == 200
        data = resp.json()
        assert "relations" in data

    def test_sync_memory(self, client, mock_graph):
        """POST /api/memory/sync triggers sync (covers 230-258)."""
        mock_store, _ = mock_graph
        with patch("novels_project.memory.sync_manager.SyncManager") as mock_sync_mgr_cls, \
             patch("novels_project.memory.entity_extractor.EntityExtractor") as mock_extractor_cls:
            mock_sync_mgr = MagicMock()
            mock_sync_mgr.sync.return_value = {"synced": 5}
            mock_sync_mgr_cls.return_value = mock_sync_mgr
            mock_extractor_cls.return_value = MagicMock()

            resp = client.post("/api/memory/sync")
            assert resp.status_code == 200
            assert resp.json()["status"] == "synced"

    def test_sync_memory_error(self, client, mock_graph):
        """POST /api/memory/sync returns 500 on sync failure (covers 258-259)."""
        mock_store, _ = mock_graph
        with patch("novels_project.memory.sync_manager.SyncManager") as mock_sync_mgr_cls, \
             patch("novels_project.memory.entity_extractor.EntityExtractor") as mock_extractor_cls:
            mock_sync_mgr = MagicMock()
            mock_sync_mgr.sync.side_effect = RuntimeError("Sync failed")
            mock_sync_mgr_cls.return_value = mock_sync_mgr
            mock_extractor_cls.return_value = MagicMock()

            resp = client.post("/api/memory/sync")
            assert resp.status_code == 500
            assert "同步失败" in resp.json()["detail"]

    def test_init_graph_success(self, client, temp_project, mock_graph):
        """POST /api/memory/init imports characters into graph (covers 275-285)."""
        mock_store, _ = mock_graph
        mock_store.has_entity.return_value = False

        cards_path = temp_project / "config" / "character_base_cards.yaml"
        with open(cards_path, "w", encoding="utf-8") as f:
            yaml.dump({
                "s_tier": {
                    "characters": {
                        "新角色": {"name": "新角色", "brief": "简介", "role": "主角", "tier": "s_tier"},
                    },
                },
            }, f, allow_unicode=True)

        resp = client.post("/api/memory/init")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "initialized"
        assert data["imported"] >= 1

    def test_init_graph_import_error(self, client, mock_graph):
        """POST /api/memory/init returns 501 on import error (covers 289)."""
        with patch("novels_project.api.content._load_character_cards", side_effect=ImportError("No module")):
            resp = client.post("/api/memory/init")
            assert resp.status_code == 501

    def test_init_graph_exception(self, client, temp_project, mock_graph):
        """POST /api/memory/init returns 500 on general exception (covers 291)."""
        # Create character cards so _flatten_characters returns non-empty list
        cards_path = temp_project / "config" / "character_base_cards.yaml"
        with open(cards_path, "w", encoding="utf-8") as f:
            yaml.dump({
                "s_tier": {
                    "characters": {
                        "测试角色": {"name": "测试角色", "brief": "简介"},
                    },
                },
            }, f, allow_unicode=True)
        mock_store, _ = mock_graph
        mock_store.has_entity.side_effect = RuntimeError("Unexpected error")
        resp = client.post("/api/memory/init")
        assert resp.status_code == 500
        assert "初始化失败" in resp.json()["detail"]


# =========================================================================
#  Settings API
# =========================================================================

class TestSettingsAPI:
    """Tests for /api/settings endpoints."""

    def test_get_settings(self, client):
        """GET /api/settings/ returns system settings."""
        resp = client.get("/api/settings/")
        assert resp.status_code == 200
        data = resp.json()
        assert "theme" in data
        assert "language" in data

    def test_update_settings(self, client, system_config_dir):
        """PUT /api/settings/ updates system settings."""
        resp = client.put("/api/settings/", json={"theme": "dark"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "updated"
        assert data["settings"]["theme"] == "dark"

    def test_get_model_providers(self, client):
        """GET /api/settings/models returns model providers."""
        resp = client.get("/api/settings/models")
        assert resp.status_code == 200
        data = resp.json()
        assert "providers" in data

    def test_create_model_provider(self, client, system_config_dir):
        """POST /api/settings/models creates a provider."""
        resp = client.post("/api/settings/models", json={
            "name": "Test Provider",
            "base_url": "https://test.api.com/v1",
            "api_key": "test-key",
            "models": [
                {"id": "test-model", "name": "Test Model", "max_tokens": 4096, "context_window": 128000},
            ],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "created"

    def test_update_model_provider(self, client, system_config_dir):
        """PUT /api/settings/models/{name} updates a provider."""
        # Create first
        client.post("/api/settings/models", json={
            "name": "Test Provider",
            "base_url": "https://test.api.com/v1",
            "api_key": "test-key",
            "models": [
                {"id": "test-model", "name": "Test Model", "max_tokens": 4096, "context_window": 128000},
            ],
        })
        resp = client.put("/api/settings/models/test_provider", json={
            "name": "Updated Provider",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "updated"

    def test_update_model_provider_404(self, client):
        """PUT /api/settings/models/{name} returns 404 for unknown."""
        resp = client.put("/api/settings/models/nonexistent", json={"name": "Updated"})
        assert resp.status_code == 404

    def test_delete_model_provider(self, client, system_config_dir):
        """DELETE /api/settings/models/{name} deletes a provider."""
        client.post("/api/settings/models", json={
            "name": "To Delete",
            "base_url": "https://test.api.com/v1",
            "api_key": "test-key",
            "models": [
                {"id": "test-model", "name": "Test Model", "max_tokens": 4096, "context_window": 128000},
            ],
        })
        resp = client.delete("/api/settings/models/to_delete")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    def test_delete_model_provider_404(self, client):
        """DELETE /api/settings/models/{name} returns 404 for unknown."""
        resp = client.delete("/api/settings/models/nonexistent")
        assert resp.status_code == 404

    def test_test_model_provider_missing_url(self, client):
        """POST /api/settings/models/test returns 400 for missing URL."""
        resp = client.post("/api/settings/models/test", json={
            "base_url": "",
            "api_key": "test-key",
        })
        assert resp.status_code == 400

    def test_list_backups(self, client):
        """GET /api/settings/backups returns backup list."""
        resp = client.get("/api/settings/backups")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_create_backup(self, client, temp_project):
        """POST /api/settings/backup creates a backup."""
        resp = client.post("/api/settings/backup")
        assert resp.status_code == 200
        data = resp.json()
        assert "name" in data

    def test_restore_backup_404(self, client):
        """POST /api/settings/restore returns 404 for unknown backup."""
        resp = client.post("/api/settings/restore", params={"backup_name": "nonexistent.zip"})
        assert resp.status_code == 404

    def test_get_settings_with_file(self, client, system_config_dir):
        """GET /api/settings/ returns settings from existing file (covers 35-40)."""
        settings_path = system_config_dir / "system_settings.yaml"
        with open(settings_path, "w", encoding="utf-8") as f:
            yaml.dump({"theme": "dark", "language": "en"}, f, allow_unicode=True)
        resp = client.get("/api/settings/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["theme"] == "dark"
        assert data["language"] == "en"
        assert "notifications" in data  # default merged in

    def test_update_settings_nested(self, client, system_config_dir):
        """PUT /api/settings/ with nested dict merges (covers 114)."""
        resp = client.put("/api/settings/", json={
            "notifications": {"enabled": False}
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["settings"]["notifications"]["enabled"] is False
        # Other notification settings preserved
        assert data["settings"]["notifications"]["chapter_complete"] is True

    def test_list_backups_with_files(self, client, temp_project):
        """GET /api/settings/backups returns files when backups exist (covers 142-152)."""
        backup_dir = temp_project / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        (backup_dir / "backup_20240101_120000.zip").write_text("dummy")
        (backup_dir / "backup_20240102_120000.zip").write_text("dummy")
        resp = client.get("/api/settings/backups")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["name"] == "backup_20240102_120000.zip"

    def test_create_model_provider_with_advanced(self, client, system_config_dir):
        """POST /api/settings/models with advanced config (covers 420)."""
        resp = client.post("/api/settings/models", json={
            "name": "Advanced Provider",
            "base_url": "https://test.api.com/v1",
            "api_key": "test-key",
            "models": [
                {"id": "test-model", "name": "Test Model", "max_tokens": 4096, "context_window": 128000},
            ],
            "advanced": {
                "temperature": 0.5,
                "top_p": 0.9,
                "max_tokens": 2048,
                "frequency_penalty": 0.0,
                "presence_penalty": 0.0,
                "timeout": 60,
                "system_prompt": "",
            },
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "created"
        assert "advanced" in data["provider"]
        assert data["provider"]["advanced"]["temperature"] == 0.5

    def test_update_model_provider_with_models(self, client, system_config_dir):
        """PUT /api/settings/models/{name} with models field (covers 439, 441)."""
        client.post("/api/settings/models", json={
            "name": "Test Provider",
            "base_url": "https://test.api.com/v1",
            "api_key": "test-key",
            "models": [
                {"id": "test-model", "name": "Test Model", "max_tokens": 4096, "context_window": 128000},
            ],
        })
        resp = client.put("/api/settings/models/test_provider", json={
            "models": [
                {"id": "new-model", "name": "New Model", "max_tokens": 8192, "context_window": 256000},
            ],
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "updated"

    def test_get_model_providers_resolve_keys(self, client, system_config_dir):
        """GET /api/settings/models?resolve_keys=true resolves env vars (covers 330-333, 252)."""
        providers_path = system_config_dir / "model_providers.yaml"
        with open(providers_path, "w", encoding="utf-8") as f:
            yaml.dump({
                "providers": {
                    "test": {
                        "name": "Test",
                        "base_url": "https://test.api.com/v1",
                        "api_key": "${TEST_API_KEY}",
                        "models": [],
                    },
                },
            }, f)
        with patch.dict("os.environ", {"TEST_API_KEY": "resolved-key"}):
            resp = client.get("/api/settings/models", params={"resolve_keys": "true"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["providers"]["test"]["api_key"] == "resolved-key"

    def test_restore_backup_success(self, client, temp_project):
        """POST /api/settings/restore restores a backup (covers 212-235)."""
        import zipfile
        backup_dir = temp_project / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        zip_path = backup_dir / "test_backup.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("config/test.txt", "test content")

        resp = client.post("/api/settings/restore", params={"backup_name": "test_backup.zip"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "restored"

    def test_test_model_connection_success(self, client):
        """POST /api/settings/models/test returns success (covers 474-527)."""
        mock_http_response = MagicMock()
        mock_http_response.status = 200
        mock_http_response.read.return_value = json.dumps({
            "choices": [{"message": {"content": "测试成功"}}],
            "usage": {"total_tokens": 10},
            "model": "test-model",
        }).encode("utf-8")

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value = mock_http_response
            resp = client.post("/api/settings/models/test", json={
                "base_url": "https://test.api.com/v1",
                "api_key": "test-key",
                "model_id": "test-model",
            })
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_test_model_connection_http_error(self, client):
        """POST /api/settings/models/test handles HTTP error (covers 517-524)."""
        import urllib.error
        mock_http_error = urllib.error.HTTPError(
            "https://test.api.com/v1/chat/completions", 401, "Unauthorized", {}, None
        )
        with patch("urllib.request.urlopen", side_effect=mock_http_error):
            resp = client.post("/api/settings/models/test", json={
                "base_url": "https://test.api.com/v1",
                "api_key": "bad-key",
                "model_id": "test-model",
            })
        assert resp.status_code == 401

    def test_test_model_connection_url_error(self, client):
        """POST /api/settings/models/test handles URL error (covers 525-526)."""
        import urllib.error
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("connection refused")):
            resp = client.post("/api/settings/models/test", json={
                "base_url": "https://test.api.com/v1",
                "api_key": "test-key",
            })
        assert resp.status_code == 502
        assert "连接失败" in resp.json()["detail"]

    def test_test_model_connection_response_error(self, client):
        """POST /api/settings/models/test handles malformed response (covers 505-506)."""
        mock_http_response = MagicMock()
        mock_http_response.status = 200
        mock_http_response.read.return_value = b"not valid json"

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value = mock_http_response
            resp = client.post("/api/settings/models/test", json={
                "base_url": "https://test.api.com/v1",
                "api_key": "test-key",
                "model_id": "test-model",
            })
        assert resp.status_code == 500

    def test_test_model_connection_bad_response_structure(self, client):
        """POST /api/settings/models/test handles valid JSON with wrong structure (covers 505-506)."""
        mock_http_response = MagicMock()
        mock_http_response.status = 200
        mock_http_response.read.return_value = json.dumps({"not_choices": []}).encode("utf-8")

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value = mock_http_response
            resp = client.post("/api/settings/models/test", json={
                "base_url": "https://test.api.com/v1",
                "api_key": "test-key",
                "model_id": "test-model",
            })
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        assert resp.json()["response"] == "响应格式异常"

    def test_test_model_connection_http_error_with_body(self, client):
        """POST /api/settings/models/test handles HTTPError with JSON body (covers 521)."""
        import urllib.error
        mock_http_error = urllib.error.HTTPError(
            "https://test.api.com/v1/chat/completions", 400, "Bad Request", {}, None
        )
        mock_http_error.read = MagicMock(return_value=json.dumps({
            "error": {"message": "Invalid model"}
        }).encode("utf-8"))
        with patch("urllib.request.urlopen", side_effect=mock_http_error):
            resp = client.post("/api/settings/models/test", json={
                "base_url": "https://test.api.com/v1",
                "api_key": "test-key",
                "model_id": "bad-model",
            })
        assert resp.status_code == 400
        assert "Invalid model" in resp.json()["detail"]

    def test_get_model_providers_resolve_keys_no_env(self, client, system_config_dir):
        """GET /api/settings/models?resolve_keys=true with no api_key env (covers 332->331)."""
        providers_path = system_config_dir / "model_providers.yaml"
        with open(providers_path, "w", encoding="utf-8") as f:
            yaml.dump({
                "providers": {
                    "no_api_key": {
                        "name": "No Key",
                        "base_url": "https://test.com/v1",
                        "models": [],
                    },
                    "with_key": {
                        "name": "With Key",
                        "base_url": "https://test.com/v1",
                        "api_key": "${TEST_KEY}",
                        "models": [],
                    },
                },
            }, f)
        with patch.dict("os.environ", {"TEST_KEY": "resolved"}, clear=True):
            resp = client.get("/api/settings/models", params={"resolve_keys": "true"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["providers"]["with_key"]["api_key"] == "resolved"
        # no_api_key provider should not have api_key key added
        assert "api_key" not in data["providers"]["no_api_key"]

    def test_test_model_connection_general_error(self, client):
        """POST /api/settings/models/test handles general exception (covers 527)."""
        with patch("urllib.request.urlopen", side_effect=Exception("Unexpected error")):
            resp = client.post("/api/settings/models/test", json={
                "base_url": "https://test.api.com/v1",
                "api_key": "test-key",
            })
        assert resp.status_code == 500

    def test_update_model_provider_with_advanced(self, client, system_config_dir):
        """PUT /api/settings/models/{name} with advanced field (covers 441)."""
        client.post("/api/settings/models", json={
            "name": "Adv Provider",
            "base_url": "https://test.api.com/v1",
            "api_key": "test-key",
            "models": [
                {"id": "test-model", "name": "Test Model", "max_tokens": 4096, "context_window": 128000},
            ],
        })
        resp = client.put("/api/settings/models/adv_provider", json={
            "advanced": {
                "temperature": 0.7,
                "max_tokens": 4096,
            },
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "updated"

    def test_restore_backup_skip_missing_dir(self, client, temp_project):
        """POST /api/settings/restore skips non-existent dirs in zip (covers 229->231)."""
        import zipfile
        backup_dir = temp_project / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        zip_path = backup_dir / "sparse_backup.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("nonexistent_dir/file.txt", "content")

        resp = client.post("/api/settings/restore", params={"backup_name": "sparse_backup.zip"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "restored"

    def test_create_backup_file_exists(self, client, temp_project):
        """POST /api/settings/backup creates backup with existing file (covers 174->172, 188-189)."""
        backup_dir = temp_project / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        # Create some content so the backup has something to copy
        config_dir = temp_project / "config"
        config_dir.mkdir(exist_ok=True)
        (config_dir / "test.txt").write_text("test", encoding="utf-8")
        resp = client.post("/api/settings/backup")
        assert resp.status_code == 200

    def test_create_backup_with_content(self, client, temp_project, system_config_dir):
        """POST /api/settings/backup creates backup with content (covers 188-189)."""
        backup_dir = temp_project / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        (temp_project / "config").mkdir(exist_ok=True)
        (temp_project / "config" / "test.txt").write_text("test", encoding="utf-8")
        (temp_project / "output").mkdir(exist_ok=True)
        resp = client.post("/api/settings/backup")
        assert resp.status_code == 200

    def test_get_backup_dir_fallback(self, client, system_config_dir):
        """GET /api/settings/backups uses fallback backup_dir when not in settings (covers 132)."""
        settings_path = system_config_dir / "system_settings.yaml"
        with open(settings_path, "w", encoding="utf-8") as f:
            yaml.dump({"backup": {}}, f)
        resp = client.get("/api/settings/backups")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_create_backup_cleanup_error(self, client, temp_project, system_config_dir):
        """POST /api/settings/backup cleans up temp dir on error (covers 197-199)."""
        with patch("shutil.copytree", side_effect=RuntimeError("Copy failed")):
            resp = client.post("/api/settings/backup")
            assert resp.status_code == 500
            assert "备份失败" in resp.json()["detail"]


# =========================================================================
#  Workspace API
# =========================================================================

class TestWorkspaceAPI:
    """Tests for /api/workspaces endpoints."""

    @pytest.fixture(autouse=True)
    def mock_workspace_registry(self, tmp_path):
        """Mock the workspace registry directory."""
        reg_dir = tmp_path / "workspaces_registry"
        reg_dir.mkdir()
        with patch("novels_project.api.workspace.WORKSPACE_REGISTRY_DIR", reg_dir):
            yield reg_dir

    def test_list_workspaces(self, client):
        """GET /api/workspaces/ returns workspace list."""
        resp = client.get("/api/workspaces/")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_create_workspace(self, client, tmp_path):
        """POST /api/workspaces/ creates a new workspace."""
        base = tmp_path / "novels"
        resp = client.post("/api/workspaces/", json={
            "name": "test_workspace",
            "base_path": str(base),
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "test_workspace"
        assert data["status"] == "created"

    def test_create_workspace_duplicate(self, client, tmp_path):
        """POST /api/workspaces/ returns 400 for duplicate."""
        base = tmp_path / "novels"
        client.post("/api/workspaces/", json={
            "name": "test_ws",
            "base_path": str(base),
        })
        resp = client.post("/api/workspaces/", json={
            "name": "test_ws",
            "base_path": str(base),
        })
        assert resp.status_code == 400

    def test_rename_workspace(self, client, tmp_path):
        """PUT /api/workspaces/{name} renames a workspace."""
        base = tmp_path / "novels"
        client.post("/api/workspaces/", json={
            "name": "old_name",
            "base_path": str(base),
        })
        resp = client.put("/api/workspaces/old_name", json={"new_name": "new_name"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "new_name"

    def test_rename_workspace_404(self, client):
        """PUT /api/workspaces/{name} returns 404 for unknown."""
        resp = client.put("/api/workspaces/nonexistent", json={"new_name": "new"})
        assert resp.status_code == 404

    def test_delete_workspace(self, client, tmp_path):
        """DELETE /api/workspaces/{name} deletes a workspace."""
        base = tmp_path / "novels"
        client.post("/api/workspaces/", json={
            "name": "to_delete",
            "base_path": str(base),
        })
        resp = client.delete("/api/workspaces/to_delete")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    def test_delete_workspace_404(self, client):
        """DELETE /api/workspaces/{name} returns 404 for unknown."""
        resp = client.delete("/api/workspaces/nonexistent")
        assert resp.status_code == 404

    def test_switch_workspace(self, client, tmp_path):
        """POST /api/workspaces/{name}/switch switches workspace."""
        base = tmp_path / "novels"
        client.post("/api/workspaces/", json={
            "name": "target_ws",
            "base_path": str(base),
        })
        resp = client.post("/api/workspaces/target_ws/switch")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "switched"

    def test_switch_workspace_404(self, client):
        """POST /api/workspaces/{name}/switch returns 404 for unknown."""
        resp = client.post("/api/workspaces/nonexistent/switch")
        assert resp.status_code == 404

    def test_workspace_status(self, client, tmp_path):
        """GET /api/workspaces/{name}/status returns workspace status."""
        base = tmp_path / "novels"
        client.post("/api/workspaces/", json={
            "name": "status_ws",
            "base_path": str(base),
        })
        resp = client.get("/api/workspaces/status_ws/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "status_ws"

    def test_workspace_status_404(self, client):
        """GET /api/workspaces/{name}/status returns 404 for unknown."""
        resp = client.get("/api/workspaces/nonexistent/status")
        assert resp.status_code == 404

    def test_list_workspaces_current_in_registry(self, client, temp_project, mock_workspace_registry):
        """GET /api/workspaces/ when current is in registry (covers 125->136)."""
        import json
        ws_path = mock_workspace_registry / "current_project.json"
        ws_path.write_text(json.dumps({
            "name": "current_project",
            "path": str(temp_project),
            "created_at": "2024-01-01T00:00:00",
        }), encoding="utf-8")
        resp = client.get("/api/workspaces/")
        assert resp.status_code == 200
        # current project should appear, not duplicated
        data = resp.json()
        paths = [w["path"] for w in data]
        assert len(data) == 1

    def test_delete_workspace_no_path(self, client, mock_workspace_registry):
        """DELETE /api/workspaces/{name} deletes even when path missing on disk (covers 210->213)."""
        import json
        ws_path = mock_workspace_registry / "ghost_ws.json"
        ws_path.write_text(json.dumps({
            "name": "ghost_ws",
            "path": "/nonexistent/path/that/does/not/exist",
            "created_at": "2024-01-01T00:00:00",
        }), encoding="utf-8")
        resp = client.delete("/api/workspaces/ghost_ws")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    def test_rename_workspace_target_exists(self, client, tmp_path):
        """PUT /api/workspaces/{name} returns 400 when target name exists."""
        base = tmp_path / "novels"
        client.post("/api/workspaces/", json={"name": "ws1", "base_path": str(base)})
        client.post("/api/workspaces/", json={"name": "ws2", "base_path": str(base)})
        resp = client.put("/api/workspaces/ws1", json={"new_name": "ws2"})
        assert resp.status_code == 400

    def test_rename_workspace_dir_missing(self, client, mock_workspace_registry):
        """PUT /api/workspaces/{name} returns 404 when dir doesn't exist on disk."""
        import json
        ws_path = mock_workspace_registry / "ghost_ws.json"
        ws_path.write_text(json.dumps({
            "name": "ghost_ws",
            "path": "/nonexistent/path",
            "created_at": "2024-01-01T00:00:00",
        }), encoding="utf-8")
        resp = client.put("/api/workspaces/ghost_ws", json={"new_name": "new_ghost"})
        assert resp.status_code == 404

    def test_switch_workspace_dir_missing(self, client, mock_workspace_registry):
        """POST /api/workspaces/{name}/switch returns 404 when dir missing."""
        import json
        ws_path = mock_workspace_registry / "ghost_ws.json"
        ws_path.write_text(json.dumps({
            "name": "ghost_ws",
            "path": "/nonexistent/path",
            "created_at": "2024-01-01T00:00:00",
        }), encoding="utf-8")
        resp = client.post("/api/workspaces/ghost_ws/switch")
        assert resp.status_code == 404

    def test_workspace_status_dir_missing(self, client, mock_workspace_registry):
        """GET /api/workspaces/{name}/status returns 404 when dir missing."""
        import json
        ws_path = mock_workspace_registry / "ghost_ws.json"
        ws_path.write_text(json.dumps({
            "name": "ghost_ws",
            "path": "/nonexistent/path",
            "created_at": "2024-01-01T00:00:00",
        }), encoding="utf-8")
        resp = client.get("/api/workspaces/ghost_ws/status")
        assert resp.status_code == 404

    def test_list_workspaces_with_content(self, client, temp_project):
        """GET /api/workspaces/ includes workspace content info (covers 110->116, 112->114)."""
        # Create a workspace with actual content
        chapters_dir = temp_project / "output" / "chapters"
        chapters_dir.mkdir(parents=True, exist_ok=True)
        (chapters_dir / "chapter_01_final.md").write_text("# Title\nContent", encoding="utf-8")
        resp = client.get("/api/workspaces/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        current = data[0]
        assert "chapters_count" in current
        assert current["chapters_count"] >= 1

    def test_delete_workspace_remove_registry_not_found(self, client, mock_workspace_registry):
        """DELETE /api/workspaces/{name} handles registry file not found (covers 68->exit)."""
        import json
        # Create a workspace entry, then delete it
        ws_path = mock_workspace_registry / "ghost_ws.json"
        ws_path.write_text(json.dumps({
            "name": "ghost_ws",
            "path": "/nonexistent/path",
            "created_at": "2024-01-01T00:00:00",
        }), encoding="utf-8")
        resp = client.delete("/api/workspaces/ghost_ws")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"
        # Now delete again — registry file already removed, should still return 404
        resp2 = client.delete("/api/workspaces/ghost_ws")
        assert resp2.status_code == 404

    def test_list_registered_workspaces_error(self, client, mock_workspace_registry):
        """GET /api/workspaces/ handles corrupt registry file (covers 47-48)."""
        import json
        ws_path = mock_workspace_registry / "corrupt.json"
        ws_path.write_text("{invalid json", encoding="utf-8")
        resp = client.get("/api/workspaces/")
        assert resp.status_code == 200


# =========================================================================
#  Health Check
# =========================================================================

class TestHealthCheck:
    """Tests for /api/health."""

    def test_health_check(self, client):
        """GET /api/health returns ok."""
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"