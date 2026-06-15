"""
单元测试：System Prompt 模块测试

测试范围：
1. build_main_agent_system_prompt
2. _load_world_info
3. build_sub_agent_system_prompt
4. _get_agent_identity
"""

from pathlib import Path
from unittest.mock import patch, MagicMock


# ==================== _get_agent_identity ====================

class TestGetAgentIdentity:
    """测试 _get_agent_identity"""

    def test_chief_editor(self):
        from novels_project.system_prompt import _get_agent_identity
        result = _get_agent_identity("chief_editor")
        assert "资深小说编辑" in result
        assert "20年经验" in result
        assert "YAML 格式" in result

    def test_character_designer(self):
        from novels_project.system_prompt import _get_agent_identity
        result = _get_agent_identity("character_designer")
        assert "人物塑造专家" in result
        assert "人物策划设计师" in result
        assert "YAML 格式" in result

    def test_plot_writer(self):
        from novels_project.system_prompt import _get_agent_identity
        result = _get_agent_identity("plot_writer")
        assert "文学创意大师" in result
        assert "剧情撰写员" in result
        assert "3000-5000" in result

    def test_proofreader(self):
        from novels_project.system_prompt import _get_agent_identity
        result = _get_agent_identity("proofreader")
        assert "质量把关官" in result
        assert "资深校对" in result
        assert "YAML 格式" in result

    def test_unknown_agent(self):
        from novels_project.system_prompt import _get_agent_identity
        result = _get_agent_identity("random_agent")
        assert "random_agent agent" in result


# ==================== _load_world_info ====================

def _make_mock_path(exists=True):
    """Create a mock Path that returns `exists` for .exists()."""
    mock_path = MagicMock(spec=Path)
    mock_path.exists.return_value = exists
    return mock_path


class TestLoadWorldInfo:
    """测试 _load_world_info"""

    @patch("novels_project.system_prompt.get_character_cards_path")
    def test_no_cards_file(self, mock_cards_path):
        mock_cards_path.return_value = _make_mock_path(exists=False)
        from novels_project.system_prompt import _load_world_info
        result = _load_world_info()
        assert "未设置" in result
        assert "世界观" in result

    @patch("novels_project.system_prompt.get_character_cards_path")
    @patch("yaml.safe_load")
    @patch("builtins.open")
    def test_with_valid_cards(self, _mock_open, mock_yaml_load, mock_cards_path):
        mock_cards_path.return_value = _make_mock_path(exists=True)
        mock_yaml_load.return_value = {
            "metadata": {
                "story_world": "修真世界",
                "protagonist": "陆商曜",
            },
            "s_tier": {"characters": {}},
        }
        from novels_project.system_prompt import _load_world_info
        result = _load_world_info()
        assert "修真世界" in result
        assert "陆商曜" in result
        assert "主角：" in result

    @patch("novels_project.system_prompt.get_character_cards_path")
    @patch("yaml.safe_load")
    @patch("builtins.open")
    def test_without_metadata(self, _mock_open, mock_yaml_load, mock_cards_path):
        mock_cards_path.return_value = _make_mock_path(exists=True)
        mock_yaml_load.return_value = {}
        from novels_project.system_prompt import _load_world_info
        result = _load_world_info()
        assert "未设置" in result

    @patch("novels_project.system_prompt.get_character_cards_path")
    @patch("yaml.safe_load")
    @patch("builtins.open")
    def test_without_story_world(self, _mock_open, mock_yaml_load, mock_cards_path):
        mock_cards_path.return_value = _make_mock_path(exists=True)
        mock_yaml_load.return_value = {
            "metadata": {"protagonist": "主角"},
        }
        from novels_project.system_prompt import _load_world_info
        result = _load_world_info()
        assert "主角" in result
        assert "故事世界" not in result

    @patch("novels_project.system_prompt.get_character_cards_path")
    @patch("yaml.safe_load")
    @patch("builtins.open")
    def test_protagonist_in_s_tier(self, _mock_open, mock_yaml_load, mock_cards_path):
        mock_cards_path.return_value = _make_mock_path(exists=True)
        mock_yaml_load.return_value = {
            "metadata": {
                "story_world": "仙侠世界",
                "protagonist": "陆商曜",
            },
            "s_tier": {
                "characters": {
                    "陆商曜": {
                        "name": "陆商曜",
                        "identity": "天才剑修",
                    }
                }
            },
        }
        from novels_project.system_prompt import _load_world_info
        result = _load_world_info()
        assert "天才剑修" in result
        assert "主角身份" in result
        assert "仙侠世界" in result
        assert "陆商曜" in result

    @patch("novels_project.system_prompt.get_character_cards_path")
    @patch("yaml.safe_load")
    @patch("builtins.open")
    def test_protagonist_not_in_s_tier(self, _mock_open, mock_yaml_load, mock_cards_path):
        mock_cards_path.return_value = _make_mock_path(exists=True)
        mock_yaml_load.return_value = {
            "metadata": {
                "story_world": "武侠世界",
                "protagonist": "张三",
            },
            "s_tier": {
                "characters": {
                    "李四": {
                        "name": "李四",
                        "identity": "侠客",
                    }
                }
            },
        }
        from novels_project.system_prompt import _load_world_info
        result = _load_world_info()
        assert "武侠世界" in result
        assert "张三" in result
        assert "主角身份" not in result  # Protagonist not in s_tier

    @patch("novels_project.system_prompt.get_character_cards_path")
    @patch("yaml.safe_load")
    @patch("builtins.open")
    def test_protagonist_in_s_tier_no_identity(self, _mock_open, mock_yaml_load, mock_cards_path):
        mock_cards_path.return_value = _make_mock_path(exists=True)
        mock_yaml_load.return_value = {
            "metadata": {
                "story_world": "奇幻世界",
                "protagonist": "英雄",
            },
            "s_tier": {
                "characters": {
                    "英雄": {
                        "name": "英雄",
                    }
                }
            },
        }
        from novels_project.system_prompt import _load_world_info
        result = _load_world_info()
        assert "奇幻世界" in result
        assert "英雄" in result
        assert "主角身份" not in result  # No identity field

    @patch("novels_project.system_prompt.get_character_cards_path")
    @patch("yaml.safe_load")
    @patch("builtins.open")
    def test_load_failure(self, _mock_open, mock_yaml_load, mock_cards_path):
        mock_cards_path.return_value = _make_mock_path(exists=True)
        mock_yaml_load.side_effect = Exception("Parse error")
        from novels_project.system_prompt import _load_world_info
        result = _load_world_info()
        assert "加载失败" in result


# ==================== build_main_agent_system_prompt ====================

class TestBuildMainAgentSystemPrompt:
    """测试 build_main_agent_system_prompt"""

    def test_returns_string(self):
        from novels_project.system_prompt import build_main_agent_system_prompt
        prompt = build_main_agent_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_contains_key_sections(self):
        from novels_project.system_prompt import build_main_agent_system_prompt
        prompt = build_main_agent_system_prompt()
        assert "总协调人" in prompt or "Orchestrator" in prompt
        assert "chief_editor" in prompt
        assert "character_designer" in prompt
        assert "plot_writer" in prompt
        assert "proofreader" in prompt
        assert "你的团队" in prompt
        assert "标准章节创作流程" in prompt
        assert "迭代模式" in prompt
        assert "世界观" in prompt

    def test_without_character_cards_file(self):
        """When character cards file doesn't exist, world info fallback is shown."""
        with patch("novels_project.system_prompt.get_character_cards_path") as mock_path:
            mock_path.return_value = Path("/nonexistent/cards.yaml")
            from novels_project.system_prompt import build_main_agent_system_prompt
            prompt = build_main_agent_system_prompt()
            assert "未设置" in prompt

    def test_with_character_cards(self):
        with patch("novels_project.system_prompt._load_world_info") as mock_load:
            mock_load.return_value = "## 世界观\n- 故事世界：修真世界\n- 主角：陆商曜"
            from novels_project.system_prompt import build_main_agent_system_prompt
            prompt = build_main_agent_system_prompt()
            assert "修真世界" in prompt
            assert "陆商曜" in prompt

    def test_includes_sub_agent_models(self):
        from novels_project.system_prompt import build_main_agent_system_prompt
        prompt = build_main_agent_system_prompt()
        assert "gemini-3-pro" in prompt
        assert "glm-5" in prompt

    def test_includes_output_save_instruction(self):
        from novels_project.system_prompt import build_main_agent_system_prompt
        prompt = build_main_agent_system_prompt()
        assert "save_chapter" in prompt


# ==================== build_sub_agent_system_prompt ====================

class TestBuildSubAgentSystemPrompt:
    """测试 build_sub_agent_system_prompt"""

    def test_chief_editor_without_prompt_file(self):
        """When prompt file doesn't exist, returns identity only."""
        with patch("novels_project.system_prompt.get_prompts_dir") as mock_dir:
            mock_dir.return_value = Path("/nonexistent/prompts")
            from novels_project.system_prompt import build_sub_agent_system_prompt
            result = build_sub_agent_system_prompt("chief_editor")
            assert "资深小说编辑" in result
            assert "20年经验" in result

    def test_character_designer_without_prompt_file(self):
        with patch("novels_project.system_prompt.get_prompts_dir") as mock_dir:
            mock_dir.return_value = Path("/nonexistent/prompts")
            from novels_project.system_prompt import build_sub_agent_system_prompt
            result = build_sub_agent_system_prompt("character_designer")
            assert "人物塑造专家" in result

    def test_plot_writer_without_prompt_file(self):
        with patch("novels_project.system_prompt.get_prompts_dir") as mock_dir:
            mock_dir.return_value = Path("/nonexistent/prompts")
            from novels_project.system_prompt import build_sub_agent_system_prompt
            result = build_sub_agent_system_prompt("plot_writer")
            assert "文学创意大师" in result
            assert "3000-5000" in result

    def test_proofreader_without_prompt_file(self):
        with patch("novels_project.system_prompt.get_prompts_dir") as mock_dir:
            mock_dir.return_value = Path("/nonexistent/prompts")
            from novels_project.system_prompt import build_sub_agent_system_prompt
            result = build_sub_agent_system_prompt("proofreader")
            assert "质量把关官" in result

    def test_with_prompt_file(self):
        """When prompt file exists, returns identity + file content."""
        fake_dir = MagicMock()
        fake_path = MagicMock()
        fake_path.exists.return_value = True
        fake_path.read_text.return_value = "# Custom Prompt Content"
        fake_dir.__truediv__.return_value = fake_path

        with patch("novels_project.system_prompt.get_prompts_dir") as mock_dir:
            mock_dir.return_value = fake_dir
            from novels_project.system_prompt import build_sub_agent_system_prompt
            result = build_sub_agent_system_prompt("chief_editor")
            assert "资深小说编辑" in result
            assert "Custom Prompt Content" in result

    def test_unknown_agent_without_file(self):
        with patch("novels_project.system_prompt.get_prompts_dir") as mock_dir:
            mock_dir.return_value = Path("/nonexistent/prompts")
            from novels_project.system_prompt import build_sub_agent_system_prompt
            result = build_sub_agent_system_prompt("unknown_bot")
            assert "unknown_bot agent" in result

    def test_prompt_file_not_found_fallback(self):
        """prompt file exists in mapping but not on disk, falls back to identity."""
        fake_dir = MagicMock()
        fake_path = MagicMock()
        fake_path.exists.return_value = False
        fake_dir.__truediv__.return_value = fake_path

        with patch("novels_project.system_prompt.get_prompts_dir") as mock_dir:
            mock_dir.return_value = fake_dir
            from novels_project.system_prompt import build_sub_agent_system_prompt
            result = build_sub_agent_system_prompt("chief_editor")
            assert "资深小说编辑" in result
            # Should only be identity, no extra content
            assert "YAML 格式" in result