"""
人物卡管理工具 - 更新、查询人物设定
"""
import yaml
from pathlib import Path
from typing import Any, Optional

from ..project_config import get_character_cards_path


def _load_character_cards(config_path: Optional[str] = None) -> tuple[dict, Path]:
    """Load character cards from YAML file."""
    if config_path is None:
        path = get_character_cards_path()
    else:
        path = Path(config_path)

    if not path.exists():
        raise FileNotFoundError(f"人物卡文件不存在: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return data, path


def _save_character_cards(data: dict, path: Path):
    """Save character cards to YAML file."""
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def _find_character(data: dict, character_name: str) -> tuple[Optional[str], Optional[dict]]:
    """Find a character in the data structure. Returns (tier_key, character_data)."""
    for tier in ["s_tier", "a_tier", "b_tier"]:
        if tier in data and "characters" in data[tier]:
            if character_name in data[tier]["characters"]:
                return tier, data[tier]["characters"][character_name]
    return None, None


def _set_nested_value(obj: dict, field_path: str, value: Any):
    """Set a nested value using dot notation (e.g., 'unique_speaking_style.tone')."""
    keys = field_path.split(".")
    for key in keys[:-1]:
        if key not in obj:
            obj[key] = {}
        obj = obj[key]
    obj[keys[-1]] = value


def update_character_card(
    character_name: str,
    field: str,
    value: Any,
    config_path: Optional[str] = None,
) -> str:
    """
    更新人物卡的指定字段。

    Args:
        character_name: 人物名称（如：陆商曜、黑商周桓）
        field: 要更新的字段，支持点号嵌套（如：unique_speaking_style.tone）
        value: 新的值
        config_path: 配置文件路径（可选，默认使用当前项目的配置）

    Returns:
        操作结果信息

    Examples:
        update_character_card("陆商曜", "core_personality", ["腹黑果决", "能屈能伸", "守底线"])
        update_character_card("黑商周桓", "unique_speaking_style.tone", "阴险狡诈")
    """
    try:
        data, path = _load_character_cards(config_path)
        tier, character = _find_character(data, character_name)

        if character is None:
            return f"未找到人物「{character_name}」。请检查人物名称是否正确。"

        # Update the field
        _set_nested_value(character, field, value)

        # Save
        _save_character_cards(data, path)

        return f"成功更新人物「{character_name}」的 {field} 字段。"

    except FileNotFoundError as e:
        return f"错误: {e}"
    except Exception as e:
        return f"更新失败: {e}"


def add_character_dialogue_example(
    character_name: str,
    dialogue: str,
    config_path: Optional[str] = None,
) -> str:
    """
    为人物添加新的对话示例。

    Args:
        character_name: 人物名称
        dialogue: 新的对话示例
        config_path: 配置文件路径（可选）

    Returns:
        操作结果信息

    Examples:
        add_character_dialogue_example("陆商曜", "三成换一个安稳，贵了。")
    """
    try:
        data, path = _load_character_cards(config_path)
        tier, character = _find_character(data, character_name)

        if character is None:
            return f"未找到人物「{character_name}」"

        # Ensure unique_speaking_style exists
        if "unique_speaking_style" not in character:
            character["unique_speaking_style"] = {}

        if "example_dialogues" not in character["unique_speaking_style"]:
            character["unique_speaking_style"]["example_dialogues"] = []

        # Add dialogue if not already present
        dialogues = character["unique_speaking_style"]["example_dialogues"]
        if dialogue not in dialogues:
            dialogues.append(dialogue)
            _save_character_cards(data, path)
            return f"成功为「{character_name}」添加对话示例: \"{dialogue}\""
        else:
            return f"该对话示例已存在，无需重复添加。"

    except Exception as e:
        return f"添加失败: {e}"


def get_character_card(
    character_name: str,
    config_path: Optional[str] = None,
) -> str:
    """
    获取人物的完整设定卡。

    Args:
        character_name: 人物名称
        config_path: 配置文件路径（可选）

    Returns:
        人物卡的 YAML 格式字符串

    Examples:
        get_character_card("陆商曜")
    """
    try:
        data, _ = _load_character_cards(config_path)
        tier, character = _find_character(data, character_name)

        if character is None:
            return f"未找到人物「{character_name}」\n\n可用人物: {', '.join(_list_all_characters(data))}"

        # Format as readable output
        result = f"人物卡: {character_name}\n"
        result += "=" * 40 + "\n\n"
        result += yaml.dump(character, allow_unicode=True, default_flow_style=False, sort_keys=False)

        return result

    except Exception as e:
        return f"获取失败: {e}"


def _list_all_characters(data: dict) -> list[str]:
    """List all character names."""
    names = []
    for tier in ["s_tier", "a_tier", "b_tier"]:
        if tier in data and "characters" in data[tier]:
            names.extend(data[tier]["characters"].keys())
    return names


def list_all_characters(config_path: Optional[str] = None) -> str:
    """
    列出所有可用的人物。

    Args:
        config_path: 配置文件路径（可选）

    Returns:
        人物列表
    """
    try:
        data, _ = _load_character_cards(config_path)
        names = _list_all_characters(data)

        result = f"人物卡库 ({len(names)} 人)\n"
        result += "=" * 40 + "\n\n"

        for tier in ["s_tier", "a_tier", "b_tier"]:
            if tier in data and "characters" in data[tier]:
                tier_names = list(data[tier]["characters"].keys())
                if tier_names:
                    result += f"【{tier.replace('_', ' ').upper()}】\n"
                    for name in tier_names:
                        char = data[tier]["characters"][name]
                        role = char.get("role", "未知")
                        result += f"  - {name} ({role})\n"
                    result += "\n"

        return result

    except Exception as e:
        return f"获取失败: {e}"
