"""记忆子系统配置类。

MemoryConfig 是单 agent 的记忆配置（已合并 global + agent 覆盖）。
MemoryConfigBundle 是配置包：global + 各 agent 配置 + resolved 合并结果。
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class MemoryConfig:
    """单 agent 的记忆配置（已合并 global + agent 覆盖）。

    字段分三组：
    - 摘要滑窗配置
    - 对话压缩配置
    - 子 agent 配置
    """
    # === 摘要滑窗配置 ===
    chapter_window: int = 100           # 每次压缩覆盖章节数（业务规则，不暴露 web）
    max_summary_blocks: int = 3         # web 端 10 档控制（默认保留 300 章）
    summary_max_chars: int = 2000       # 单块压缩后最大字符

    # === 对话压缩配置 ===
    dialogue_compression_threshold: float = 0.8  # 输入 80% 触发
    preserve_recent_messages: int = 4            # 保留最近 K 条
    dialogue_summary_max_chars: int = 4000       # 对话摘要最大字符（对齐 compaction.py 默认）
    dialogue_context_summary_max_chars: int = 1500  # 对话脉络字段单独字符上限
    dialogue_llm_model: Optional[str] = None     # None=跟随运行时

    # === 子 agent 配置 ===
    subagent_compression_enabled: bool = True
    subagent_max_messages: int = 30     # 子 agent 独立阈值

    def validate(self) -> list[str]:
        """配置校验，返回错误列表（空=通过）。"""
        errors = []
        if self.max_summary_blocks < 1 or self.max_summary_blocks > 10:
            errors.append(
                f"max_summary_blocks={self.max_summary_blocks} 超出 1-10 范围"
            )
        if not 0.5 <= self.dialogue_compression_threshold <= 0.95:
            errors.append(
                f"dialogue_compression_threshold={self.dialogue_compression_threshold} "
                f"超出 0.5-0.95 范围"
            )
        if self.preserve_recent_messages < 2:
            errors.append(
                f"preserve_recent_messages={self.preserve_recent_messages} "
                f"不能小于 2（避免破坏对话连贯性）"
            )
        if self.summary_max_chars < 500:
            errors.append(
                f"summary_max_chars={self.summary_max_chars} 至少 500 字符"
            )
        if self.dialogue_summary_max_chars < 1000:
            errors.append(
                f"dialogue_summary_max_chars={self.dialogue_summary_max_chars} "
                f"至少 1000 字符（结构化压缩需要足够空间）"
            )
        if self.dialogue_context_summary_max_chars < 200:
            errors.append(
                f"dialogue_context_summary_max_chars="
                f"{self.dialogue_context_summary_max_chars} 至少 200 字符"
            )
        if (
            self.dialogue_context_summary_max_chars
            > self.dialogue_summary_max_chars
        ):
            errors.append(
                f"dialogue_context_summary_max_chars="
                f"{self.dialogue_context_summary_max_chars} "
                f"不能超过 dialogue_summary_max_chars="
                f"{self.dialogue_summary_max_chars}"
            )
        return errors

    @classmethod
    def merge(
        cls,
        global_cfg: "MemoryConfig",
        agent_cfg: Optional["MemoryConfig"],
    ) -> "MemoryConfig":
        """合并 global + agent 配置（agent 显式值覆盖 global）。

        规则：
        - agent_cfg=None → 返回 global
        - agent_cfg.字段 == 字段默认值 → 继承 global
        - agent_cfg.字段 != 字段默认值 → 覆盖 global
        """
        if agent_cfg is None:
            return global_cfg

        merged = cls()
        for field_name in cls.__dataclass_fields__:
            agent_value = getattr(agent_cfg, field_name)
            global_value = getattr(global_cfg, field_name)
            field_default = cls.__dataclass_fields__[field_name].default

            # agent 显式设置（非默认）则覆盖
            if agent_value != field_default:
                setattr(merged, field_name, agent_value)
            else:
                setattr(merged, field_name, global_value)
        return merged
