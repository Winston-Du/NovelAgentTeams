"""
单元测试：人物卡管理工具 (character_card_tools)

测试覆盖:
- _load_character_cards, _save_character_cards, _find_character
- _set_nested_value, update_character_card, add_character_dialogue_example
- get_character_card, _list_all_characters, list_all_characters
"""
import pytest
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# 测试用的 YAML 数据
# ---------------------------------------------------------------------------
SAMPLE_CARDS = {
    "metadata": {
        "version": "1.0",
        "protagonist": "陆商曜",
    },
    "s_tier": {
        "characters": {
            "陆商曜": {
                "name": "陆商曜",
                "role": "主角",
                "core_personality": ["腹黑果决"],
                "unique_speaking_style": {
                    "tone": "冷静沉着",
                    "example_dialogues": ["三成换一个安稳，贵了。"],
                },
            },
        },
    },
    "a_tier": {
        "characters": {
            "黑商周桓": {
                "name": "黑商周桓",
                "role": "反派",
                "core_personality": ["霸道蛮横"],
            },
        },
    },
    "b_tier": {
        "characters": {
            "木九公": {
                "name": "木九公",
                "role": "配角",
                "core_personality": ["沉默寡言"],
            },
        },
    },
}


@pytest.fixture
def sample_yaml_file(tmp_path):
    """Create a sample YAML character cards file in tmp_path."""
    file_path = tmp_path / "character_base_cards.yaml"
    with open(file_path, "w", encoding="utf-8") as f:
        yaml.dump(SAMPLE_CARDS, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    return file_path


# =========================================================================
#  _load_character_cards
# =========================================================================
class TestLoadCharacterCards:
    """Tests for _load_character_cards."""

    def test_load_valid_yaml(self, sample_yaml_file):
        """_load_character_cards with a valid YAML file."""
        from novels_project.tools.character_card_tools import _load_character_cards

        data, path = _load_character_cards(config_path=str(sample_yaml_file))

        assert path == sample_yaml_file
        assert data["metadata"]["version"] == "1.0"
        assert "陆商曜" in data["s_tier"]["characters"]
        assert "黑商周桓" in data["a_tier"]["characters"]
        assert "木九公" in data["b_tier"]["characters"]

    def test_load_nonexistent_file(self, tmp_path):
        """_load_character_cards with a non-existent file raises FileNotFoundError."""
        from novels_project.tools.character_card_tools import _load_character_cards

        nonexistent = tmp_path / "nonexistent.yaml"
        with pytest.raises(FileNotFoundError, match="人物卡文件不存在"):
            _load_character_cards(config_path=str(nonexistent))

    def test_load_with_custom_path(self, tmp_path):
        """_load_character_cards with a custom path."""
        from novels_project.tools.character_card_tools import _load_character_cards

        custom_file = tmp_path / "custom_cards.yaml"
        custom_data = {
            "metadata": {"version": "2.0"},
            "s_tier": {"characters": {"测试角色": {"name": "测试角色", "role": "测试"}}},
        }
        with open(custom_file, "w", encoding="utf-8") as f:
            yaml.dump(custom_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        data, path = _load_character_cards(config_path=str(custom_file))
        assert path == custom_file
        assert data["metadata"]["version"] == "2.0"
        assert "测试角色" in data["s_tier"]["characters"]

    def test_load_without_config_path_uses_default(self, tmp_path):
        """_load_character_cards without config_path falls back to project_config."""
        from novels_project.tools.character_card_tools import _load_character_cards

        test_file = tmp_path / "default_cards.yaml"
        with open(test_file, "w", encoding="utf-8") as f:
            yaml.dump(SAMPLE_CARDS, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        with patch("novels_project.tools.character_card_tools.get_character_cards_path", return_value=test_file):
            data, path = _load_character_cards()
            assert path == test_file
            assert data["metadata"]["protagonist"] == "陆商曜"


# =========================================================================
#  _save_character_cards
# =========================================================================
class TestSaveCharacterCards:
    """Tests for _save_character_cards."""

    def test_save_correctly(self, sample_yaml_file):
        """_save_character_cards saves data correctly."""
        from novels_project.tools.character_card_tools import _save_character_cards, _load_character_cards

        data, path = _load_character_cards(config_path=str(sample_yaml_file))
        # Modify something
        data["s_tier"]["characters"]["陆商曜"]["core_personality"].append("能屈能伸")

        _save_character_cards(data, path)

        # Reload and verify
        reloaded, _ = _load_character_cards(config_path=str(sample_yaml_file))
        assert "能屈能伸" in reloaded["s_tier"]["characters"]["陆商曜"]["core_personality"]

    def test_save_new_file(self, tmp_path):
        """_save_character_cards can create a new file."""
        from novels_project.tools.character_card_tools import _save_character_cards

        new_file = tmp_path / "new_cards.yaml"
        data = {"metadata": {"version": "1.0"}, "s_tier": {"characters": {}}}
        _save_character_cards(data, new_file)

        assert new_file.exists()
        with open(new_file, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f)
        assert loaded["metadata"]["version"] == "1.0"


# =========================================================================
#  _find_character
# =========================================================================
class TestFindCharacter:
    """Tests for _find_character."""

    def test_find_in_s_tier(self, sample_yaml_file):
        """_find_character locates a character in s_tier."""
        from novels_project.tools.character_card_tools import _load_character_cards, _find_character

        data, _ = _load_character_cards(config_path=str(sample_yaml_file))
        tier, char = _find_character(data, "陆商曜")

        assert tier == "s_tier"
        assert char["name"] == "陆商曜"
        assert char["role"] == "主角"

    def test_find_in_a_tier(self, sample_yaml_file):
        """_find_character locates a character in a_tier."""
        from novels_project.tools.character_card_tools import _load_character_cards, _find_character

        data, _ = _load_character_cards(config_path=str(sample_yaml_file))
        tier, char = _find_character(data, "黑商周桓")

        assert tier == "a_tier"
        assert char["name"] == "黑商周桓"

    def test_find_in_b_tier(self, sample_yaml_file):
        """_find_character locates a character in b_tier."""
        from novels_project.tools.character_card_tools import _load_character_cards, _find_character

        data, _ = _load_character_cards(config_path=str(sample_yaml_file))
        tier, char = _find_character(data, "木九公")

        assert tier == "b_tier"
        assert char["name"] == "木九公"

    def test_character_not_found(self, sample_yaml_file):
        """_find_character returns (None, None) for unknown characters."""
        from novels_project.tools.character_card_tools import _load_character_cards, _find_character

        data, _ = _load_character_cards(config_path=str(sample_yaml_file))
        tier, char = _find_character(data, "不存在的人物")

        assert tier is None
        assert char is None

    def test_find_in_data_without_characters_key(self):
        """_find_character handles data without 'characters' key gracefully."""
        from novels_project.tools.character_card_tools import _find_character

        data = {"s_tier": {}}
        tier, char = _find_character(data, "陆商曜")
        assert tier is None
        assert char is None

    def test_find_in_empty_data(self):
        """_find_character handles empty data gracefully."""
        from novels_project.tools.character_card_tools import _find_character

        data = {}
        tier, char = _find_character(data, "陆商曜")
        assert tier is None
        assert char is None


# =========================================================================
#  _set_nested_value
# =========================================================================
class TestSetNestedValue:
    """Tests for _set_nested_value."""

    def test_simple_field(self):
        """_set_nested_value sets a top-level field."""
        from novels_project.tools.character_card_tools import _set_nested_value

        obj = {"a": 1}
        _set_nested_value(obj, "b", 2)
        assert obj["b"] == 2

    def test_nested_field_dot_notation(self):
        """_set_nested_value sets a nested field using dot notation."""
        from novels_project.tools.character_card_tools import _set_nested_value

        obj = {"a": {"b": 1}}
        _set_nested_value(obj, "a.b", 42)
        assert obj["a"]["b"] == 42

    def test_create_intermediate_dicts(self):
        """_set_nested_value creates intermediate dictionaries when keys are missing."""
        from novels_project.tools.character_card_tools import _set_nested_value

        obj = {}
        _set_nested_value(obj, "x.y.z", "value")
        assert obj["x"]["y"]["z"] == "value"

    def test_deeply_nested_creates_intermediate(self):
        """_set_nested_value creates all intermediate dicts for deep nesting."""
        from novels_project.tools.character_card_tools import _set_nested_value

        obj = {}
        _set_nested_value(obj, "a.b.c.d.e", 99)
        assert obj["a"]["b"]["c"]["d"]["e"] == 99

    def test_overwrite_existing_value(self):
        """_set_nested_value overwrites an existing value."""
        from novels_project.tools.character_card_tools import _set_nested_value

        obj = {"a": {"b": "old"}}
        _set_nested_value(obj, "a.b", "new")
        assert obj["a"]["b"] == "new"


# =========================================================================
#  update_character_card
# =========================================================================
class TestUpdateCharacterCard:
    """Tests for update_character_card."""

    def test_success(self, sample_yaml_file):
        """update_character_card successfully updates a field."""
        from novels_project.tools.character_card_tools import update_character_card

        result = update_character_card(
            character_name="陆商曜",
            field="core_personality",
            value=["腹黑果决", "能屈能伸", "守底线"],
            config_path=str(sample_yaml_file),
        )
        assert "成功更新" in result
        assert "陆商曜" in result

    def test_character_not_found(self, sample_yaml_file):
        """update_character_card returns error when character is not found."""
        from novels_project.tools.character_card_tools import update_character_card

        result = update_character_card(
            character_name="不存在",
            field="core_personality",
            value=["测试"],
            config_path=str(sample_yaml_file),
        )
        assert "未找到人物" in result

    def test_file_not_found_error(self, tmp_path):
        """update_character_card handles FileNotFoundError."""
        from novels_project.tools.character_card_tools import update_character_card

        result = update_character_card(
            character_name="陆商曜",
            field="core_personality",
            value=["测试"],
            config_path=str(tmp_path / "no_such_file.yaml"),
        )
        assert "错误" in result or "不存在" in result

    def test_nested_field_update(self, sample_yaml_file):
        """update_character_card updates nested fields via dot notation."""
        from novels_project.tools.character_card_tools import update_character_card

        result = update_character_card(
            character_name="陆商曜",
            field="unique_speaking_style.tone",
            value="阴险狡诈",
            config_path=str(sample_yaml_file),
        )
        assert "成功更新" in result
        # Verify persistence
        with open(sample_yaml_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert data["s_tier"]["characters"]["陆商曜"]["unique_speaking_style"]["tone"] == "阴险狡诈"

    def test_generic_exception(self, sample_yaml_file):
        """update_character_card catches generic exceptions."""
        from novels_project.tools.character_card_tools import update_character_card

        with patch("novels_project.tools.character_card_tools._load_character_cards",
                   side_effect=RuntimeError("Unexpected error")):
            result = update_character_card(
                character_name="陆商曜",
                field="core_personality",
                value=[],
                config_path=str(sample_yaml_file),
            )
            assert "更新失败" in result


# =========================================================================
#  add_character_dialogue_example
# =========================================================================
class TestAddCharacterDialogueExample:
    """Tests for add_character_dialogue_example."""

    def test_new_dialogue(self, sample_yaml_file):
        """add_character_dialogue_example adds a new dialogue to a character."""
        from novels_project.tools.character_card_tools import add_character_dialogue_example

        result = add_character_dialogue_example(
            character_name="陆商曜",
            dialogue="这是我的新台词。",
            config_path=str(sample_yaml_file),
        )
        assert "成功" in result
        # Verify persistence
        with open(sample_yaml_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        dialogues = data["s_tier"]["characters"]["陆商曜"]["unique_speaking_style"]["example_dialogues"]
        assert "这是我的新台词。" in dialogues

    def test_existing_dialogue_duplicate(self, sample_yaml_file):
        """add_character_dialogue_example detects duplicates."""
        from novels_project.tools.character_card_tools import add_character_dialogue_example

        # Add once
        add_character_dialogue_example(
            character_name="陆商曜",
            dialogue="重复台词。",
            config_path=str(sample_yaml_file),
        )
        # Add same again
        result = add_character_dialogue_example(
            character_name="陆商曜",
            dialogue="重复台词。",
            config_path=str(sample_yaml_file),
        )
        assert "已存在" in result or "重复" in result

    def test_character_not_found(self, sample_yaml_file):
        """add_character_dialogue_example returns error for unknown character."""
        from novels_project.tools.character_card_tools import add_character_dialogue_example

        result = add_character_dialogue_example(
            character_name="不存在",
            dialogue="某台词",
            config_path=str(sample_yaml_file),
        )
        assert "未找到人物" in result

    def test_no_unique_speaking_style_yet(self, sample_yaml_file):
        """add_character_dialogue_example creates unique_speaking_style if missing."""
        from novels_project.tools.character_card_tools import add_character_dialogue_example

        # 黑商周桓 has no unique_speaking_style in the sample
        result = add_character_dialogue_example(
            character_name="黑商周桓",
            dialogue="敢惹我？",
            config_path=str(sample_yaml_file),
        )
        assert "成功" in result
        with open(sample_yaml_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        char = data["a_tier"]["characters"]["黑商周桓"]
        assert "unique_speaking_style" in char
        assert "example_dialogues" in char["unique_speaking_style"]

    def test_no_example_dialogues_yet(self, tmp_path):
        """add_character_dialogue_example creates example_dialogues list if missing."""
        from novels_project.tools.character_card_tools import add_character_dialogue_example

        # Create a character with unique_speaking_style but no example_dialogues
        file_path = tmp_path / "cards.yaml"
        data = {
            "s_tier": {
                "characters": {
                    "测试": {
                        "name": "测试",
                        "role": "test",
                        "unique_speaking_style": {"tone": "平静"},
                    },
                },
            },
        }
        with open(file_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        result = add_character_dialogue_example(
            character_name="测试",
            dialogue="新台词",
            config_path=str(file_path),
        )
        assert "成功" in result

    def test_exception_handling(self, sample_yaml_file):
        """add_character_dialogue_example catches generic exceptions."""
        from novels_project.tools.character_card_tools import add_character_dialogue_example

        with patch("novels_project.tools.character_card_tools._load_character_cards",
                   side_effect=ValueError("Boom")):
            result = add_character_dialogue_example(
                character_name="陆商曜",
                dialogue="测试",
                config_path=str(sample_yaml_file),
            )
            assert "添加失败" in result


# =========================================================================
#  get_character_card
# =========================================================================
class TestGetCharacterCard:
    """Tests for get_character_card."""

    def test_success(self, sample_yaml_file):
        """get_character_card returns the character's card."""
        from novels_project.tools.character_card_tools import get_character_card

        result = get_character_card(
            character_name="陆商曜",
            config_path=str(sample_yaml_file),
        )
        assert "人物卡: 陆商曜" in result
        assert "主角" in result

    def test_character_not_found(self, sample_yaml_file):
        """get_character_card returns available characters when not found."""
        from novels_project.tools.character_card_tools import get_character_card

        result = get_character_card(
            character_name="不存在",
            config_path=str(sample_yaml_file),
        )
        assert "未找到人物" in result
        assert "可用人物" in result
        assert "陆商曜" in result  # listed as available

    def test_exception_handling(self, sample_yaml_file):
        """get_character_card catches generic exceptions."""
        from novels_project.tools.character_card_tools import get_character_card

        with patch("novels_project.tools.character_card_tools._load_character_cards",
                   side_effect=OSError("Disk error")):
            result = get_character_card(
                character_name="陆商曜",
                config_path=str(sample_yaml_file),
            )
            assert "获取失败" in result


# =========================================================================
#  _list_all_characters
# =========================================================================
class TestListAllCharactersInternal:
    """Tests for _list_all_characters."""

    def test_returns_all_names(self, sample_yaml_file):
        """_list_all_characters returns all character names from all tiers."""
        from novels_project.tools.character_card_tools import _load_character_cards, _list_all_characters

        data, _ = _load_character_cards(config_path=str(sample_yaml_file))
        names = _list_all_characters(data)

        assert "陆商曜" in names
        assert "黑商周桓" in names
        assert "木九公" in names
        assert len(names) == 3

    def test_empty_data(self):
        """_list_all_characters returns empty list for empty data."""
        from novels_project.tools.character_card_tools import _list_all_characters

        names = _list_all_characters({})
        assert names == []

    def test_data_without_characters_key(self):
        """_list_all_characters handles tiers without 'characters' key."""
        from novels_project.tools.character_card_tools import _list_all_characters

        data = {"s_tier": {}, "a_tier": {}, "b_tier": {}}
        names = _list_all_characters(data)
        assert names == []

    def test_only_some_tiers_populated(self):
        """_list_all_characters works when only some tiers have characters."""
        from novels_project.tools.character_card_tools import _list_all_characters

        data = {
            "s_tier": {"characters": {"A": {}}},
            "a_tier": {},
            "b_tier": {"characters": {"B": {}, "C": {}}},
        }
        names = _list_all_characters(data)
        assert names == ["A", "B", "C"]


# =========================================================================
#  list_all_characters
# =========================================================================
class TestListAllCharacters:
    """Tests for list_all_characters."""

    def test_success(self, sample_yaml_file):
        """list_all_characters returns a formatted list of all characters."""
        from novels_project.tools.character_card_tools import list_all_characters

        result = list_all_characters(config_path=str(sample_yaml_file))
        assert "人物卡库" in result
        assert "陆商曜" in result
        assert "黑商周桓" in result
        assert "木九公" in result

    def test_exception(self, sample_yaml_file):
        """list_all_characters catches generic exceptions."""
        from novels_project.tools.character_card_tools import list_all_characters

        with patch("novels_project.tools.character_card_tools._load_character_cards",
                   side_effect=Exception("Something broke")):
            result = list_all_characters(config_path=str(sample_yaml_file))
            assert "获取失败" in result

    def test_missing_tier(self, sample_yaml_file):
        """list_all_characters handles missing tiers gracefully."""
        from novels_project.tools.character_card_tools import list_all_characters

        # Only s_tier has characters, a_tier and b_tier are missing entirely
        data_with_missing_tiers = {
            "s_tier": {"characters": {"A": {"role": "人物"}}},
        }
        cards_path = sample_yaml_file.parent / "partial_cards.yaml"
        with open(cards_path, "w", encoding="utf-8") as f:
            yaml.dump(data_with_missing_tiers, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        result = list_all_characters(config_path=str(cards_path))
        assert "A" in result
        assert "人物卡库" in result

    def test_tier_without_characters_key(self, sample_yaml_file):
        """list_all_characters handles tiers without 'characters' key."""
        from novels_project.tools.character_card_tools import list_all_characters

        # Tier exists but has no 'characters' key
        data_without_chars = {
            "s_tier": {"characters": {"A": {"role": "人物"}}},
            "a_tier": {"tier_name": "次要"},
            "b_tier": {},
        }
        cards_path = sample_yaml_file.parent / "no_chars_key.yaml"
        with open(cards_path, "w", encoding="utf-8") as f:
            yaml.dump(data_without_chars, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        result = list_all_characters(config_path=str(cards_path))
        assert "A" in result