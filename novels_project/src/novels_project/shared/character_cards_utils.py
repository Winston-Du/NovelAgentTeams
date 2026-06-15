"""
统一人物卡工具函数 - 消除各模块间 YAML 解析的分裂

提供全项目唯一的人物卡扁平化和人物名提取实现，
替代 api/content.py 和 character_voice_checker.py 中的重复代码。
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger("novels_project.shared.character_cards_utils")

# 所有支持的层级
ALL_TIERS = ("s_tier", "a_tier", "b_tier", "c_tier")


def flatten_characters(
    data: dict,
    tiers: Optional[tuple[str, ...]] = None,
) -> list[dict]:
    """
    将层级结构的人物卡扁平化为列表。

    兼容两种 YAML 结构：
    1. { tier: { characters: { name: info } } }  ← 标准结构
    2. { tier: { name: info } }                    ← 无 characters 子键

    Args:
        data: 人物卡 YAML 解析后的字典
        tiers: 要处理的层级，默认 ALL_TIERS

    Returns:
        扁平化后的人物信息列表，每个元素包含 name、tier 字段
    """
    if tiers is None:
        tiers = ALL_TIERS

    result = []
    for tier_key in tiers:
        tier_data = data.get(tier_key, {})
        if not isinstance(tier_data, dict):
            continue

        # 兼容两种结构：有/无 "characters" 子键
        chars = tier_data.get("characters", tier_data)
        if not isinstance(chars, dict):
            logger.warning(
                "[character_cards_utils] 跳过非标准结构 | tier=%s type=%s",
                tier_key, type(chars).__name__,
            )
            continue

        for name, info in chars.items():
            if not isinstance(info, dict) or name.startswith("_"):
                continue
            info["tier"] = tier_key
            info["name"] = name
            result.append(info)

    return result


def get_character_names(data: dict) -> list[str]:
    """
    从人物卡数据中提取所有人物名称。

    替代 character_voice_checker.py 中的硬编码角色列表。

    Args:
        data: 人物卡 YAML 解析后的字典

    Returns:
        人物名称列表（按层级顺序）
    """
    names = []
    for tier_key in ALL_TIERS:
        tier_data = data.get(tier_key, {})
        if not isinstance(tier_data, dict):
            continue
        chars = tier_data.get("characters", tier_data)
        if not isinstance(chars, dict):
            continue
        for name, info in chars.items():
            if isinstance(info, dict) and not name.startswith("_"):
                names.append(name)
    return names


def load_character_cards_dict(
    yaml_path: str | Path,
    tiers: Optional[tuple[str, ...]] = None,
) -> dict[str, Any]:
    """
    从 YAML 文件加载人物卡，返回按名称索引的字典（用于对话校验等）。

    Args:
        yaml_path: 人物卡 YAML 文件路径
        tiers: 要加载的层级，默认 ALL_TIERS

    Returns:
        { "人物名": { ...人物卡数据... } }
    """
    if tiers is None:
        tiers = ALL_TIERS

    path = Path(yaml_path)
    if not path.exists():
        raise FileNotFoundError(f"人物卡文件不存在: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    result = {}
    for tier in tiers:
        if tier in data and "characters" in data[tier]:
            result.update(data[tier]["characters"])

    logger.info(
        "[character_cards_utils] 加载人物卡完成 | path=%s count=%d",
        path.name, len(result),
    )
    return result
