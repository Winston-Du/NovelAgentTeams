"""
Tests for update_character_card tool.
TDD: Write failing test first.
"""
import pytest
import tempfile
import shutil
from pathlib import Path
import yaml


class TestUpdateCharacterCard:
    """Test suite for update_character_card tool."""

    @pytest.fixture
    def temp_config_dir(self, tmp_path):
        """Create a temporary config directory with a test character cards file."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # Create a minimal test character cards file
        test_cards = {
            "metadata": {
                "version": "0.3",
                "total_characters": 2,
            },
            "s_tier": {
                "count": 2,
                "characters": {
                    "测试角色A": {
                        "name": "测试角色A",
                        "role": "主角",
                        "core_personality": ["勇敢", "聪明"],
                        "unique_speaking_style": {
                            "tone": "平静",
                            "example_dialogues": ["测试对话1"],
                        },
                    },
                    "测试角色B": {
                        "name": "测试角色B",
                        "role": "反派",
                        "core_personality": ["狡诈"],
                    },
                },
            },
        }

        cards_file = config_dir / "character_base_cards.yaml"
        with open(cards_file, "w", encoding="utf-8") as f:
            yaml.dump(test_cards, f, allow_unicode=True, default_flow_style=False)

        return tmp_path

    def test_update_character_personality(self, temp_config_dir):
        """Test updating a character's personality trait."""
        from novels_project.tools.character_card_tools import update_character_card

        result = update_character_card(
            character_name="测试角色A",
            field="core_personality",
            value=["勇敢", "聪明", "谨慎"],  # Add new trait
            config_path=str(temp_config_dir / "config" / "character_base_cards.yaml"),
        )

        assert "成功" in result or "updated" in result.lower()

        # Verify the change was persisted
        with open(temp_config_dir / "config" / "character_base_cards.yaml", "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        assert "谨慎" in data["s_tier"]["characters"]["测试角色A"]["core_personality"]

    def test_update_character_speaking_style(self, temp_config_dir):
        """Test updating a character's speaking style."""
        from novels_project.tools.character_card_tools import update_character_card

        result = update_character_card(
            character_name="测试角色A",
            field="unique_speaking_style.tone",
            value="冷酷",
            config_path=str(temp_config_dir / "config" / "character_base_cards.yaml"),
        )

        assert "成功" in result or "updated" in result.lower()

        # Verify the change
        with open(temp_config_dir / "config" / "character_base_cards.yaml", "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        assert data["s_tier"]["characters"]["测试角色A"]["unique_speaking_style"]["tone"] == "冷酷"

    def test_update_nonexistent_character(self, temp_config_dir):
        """Test updating a character that doesn't exist."""
        from novels_project.tools.character_card_tools import update_character_card

        result = update_character_card(
            character_name="不存在的角色",
            field="core_personality",
            value=["测试"],
            config_path=str(temp_config_dir / "config" / "character_base_cards.yaml"),
        )

        assert "未找到" in result or "not found" in result.lower()

    def test_add_new_field(self, temp_config_dir):
        """Test adding a new field to a character."""
        from novels_project.tools.character_card_tools import update_character_card

        result = update_character_card(
            character_name="测试角色B",
            field="unique_speaking_style",
            value={"tone": "阴险", "example_dialogues": ["嘿嘿"]},
            config_path=str(temp_config_dir / "config" / "character_base_cards.yaml"),
        )

        assert "成功" in result or "updated" in result.lower()

        # Verify the new field was added
        with open(temp_config_dir / "config" / "character_base_cards.yaml", "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        assert data["s_tier"]["characters"]["测试角色B"]["unique_speaking_style"]["tone"] == "阴险"

    def test_add_dialogue_example(self, temp_config_dir):
        """Test adding a new dialogue example."""
        from novels_project.tools.character_card_tools import add_character_dialogue_example

        result = add_character_dialogue_example(
            character_name="测试角色A",
            dialogue="这是新添加的测试对话",
            config_path=str(temp_config_dir / "config" / "character_base_cards.yaml"),
        )

        assert "成功" in result or "added" in result.lower()

        # Verify
        with open(temp_config_dir / "config" / "character_base_cards.yaml", "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        dialogues = data["s_tier"]["characters"]["测试角色A"]["unique_speaking_style"]["example_dialogues"]
        assert "这是新添加的测试对话" in dialogues

    def test_get_character_card(self, temp_config_dir):
        """Test retrieving a character card."""
        from novels_project.tools.character_card_tools import get_character_card

        result = get_character_card(
            character_name="测试角色A",
            config_path=str(temp_config_dir / "config" / "character_base_cards.yaml"),
        )

        assert "测试角色A" in result
        assert "勇敢" in result or "主角" in result
