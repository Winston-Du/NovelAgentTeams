"""MemoryConfigBundle - 配置包：global + 各 agent 配置 + resolved 合并结果。

提供 YAML 文件加载、自动合并、未指定 agent 的兜底能力。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from .memory_config import MemoryConfig


@dataclass
class MemoryConfigBundle:
    """配置包：global + 各 agent 配置 + resolved 合并结果。

    Attributes:
        global_config: 全局默认配置
        agent_configs: 原始 agent 配置（字段可能未全显式）
        resolved: 合并后的最终配置（agent 显式值覆盖 global）
    """
    global_config: MemoryConfig
    agent_configs: dict[str, MemoryConfig] = field(default_factory=dict)
    resolved: dict[str, MemoryConfig] = field(default_factory=dict)

    @classmethod
    def load_from_yaml(cls, path: Path) -> "MemoryConfigBundle":
        """从 YAML 加载并自动 merge。

        行为：
        - 文件不存在 → 返回全默认配置
        - 文件为空 → 返回全默认配置
        - YAML 格式错误 → 抛 yaml.YAMLError
        - 未知字段 → 静默忽略
        - 未指定 agent → 兜底为 global_config
        """
        if not path.exists():
            return cls(global_config=MemoryConfig())

        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

        # 1. 解析 global
        global_dict = raw.get("global", {}) or {}
        global_cfg = _build_config_from_dict(global_dict)

        # 2. 解析各 agent
        agent_cfgs: dict[str, MemoryConfig] = {}
        resolved: dict[str, MemoryConfig] = {}
        agents_dict = raw.get("agents", {}) or {}
        for agent_name, agent_dict in agents_dict.items():
            agent_cfg = _build_config_from_dict(agent_dict or {})
            agent_cfgs[agent_name] = agent_cfg
            resolved[agent_name] = MemoryConfig.merge(global_cfg, agent_cfg)

        return cls(
            global_config=global_cfg,
            agent_configs=agent_cfgs,
            resolved=resolved,
        )

    def get_resolved(self, agent_id: str) -> MemoryConfig:
        """获取 agent 的最终合并配置。

        未指定 agent 时返回 global_config（兜底）。
        """
        return self.resolved.get(agent_id, self.global_config)


def _build_config_from_dict(d: dict) -> MemoryConfig:
    """从 dict 构建 MemoryConfig，仅接受已知字段。

    未知字段静默忽略（不抛异常）。
    """
    valid_fields = set(MemoryConfig.__dataclass_fields__.keys())
    filtered = {k: v for k, v in d.items() if k in valid_fields}
    return MemoryConfig(**filtered)
