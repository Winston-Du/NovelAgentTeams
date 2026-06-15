"""记忆子系统配置类。

MemoryConfig 是单 agent 的记忆配置（已合并 global + agent 覆盖）。
MemoryConfigBundle 是配置包：global + 各 agent 配置 + resolved 合并结果。
"""
from __future__ import annotations
import inspect
from dataclasses import dataclass, field, fields
from typing import Optional, Set


@dataclass
class MemoryConfig:
    """单 agent 的记忆配置（已合并 global + agent 覆盖）。

    字段分三组：
    - 摘要滑窗配置
    - 对话压缩配置
    - 子 agent 配置

    "显式字段"语义：
    构造时显式传入的 kwargs 被记录到 _explicit_fields，用于 merge() 中
    判断哪些字段是"显式设置"的。
    通过 __post_init__ 配合 inspect.currentframe() 自动捕获调用方
    传入的 kwargs，向后兼容现有 `MemoryConfig(field=value)` 调用。
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
    dialogue_compression_max_retries: int = 2     # LLM 压缩重试次数
    dialogue_llm_model: Optional[str] = None     # None=跟随运行时

    # === 子 agent 配置 ===
    subagent_compression_enabled: bool = True
    subagent_max_messages: int = 30     # 子 agent 独立阈值
    auto_compaction_threshold: int = 100000  # 对话上下文自动压缩阈值（tokens）

    # === 内部追踪：构造时显式提供的字段集 ===
    # 不参与序列化、不参与 validate、不参与 hash
    _explicit_fields: Set[str] = field(
        default_factory=set,
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        """捕获构造时显式提供的字段。

        重要说明：dataclass 合成 __init__ 的 f_locals 包含所有字段
        （含字段默认值），无法通过 frame inspection 可靠地区分
        "显式 kwargs" 和 "字段默认"。
        因此采用"显式注册"模式：调用方在构造后调用
        `MemoryConfig.mark_explicit(cfg, {fields})` 标记显式字段。
        未标记的字段视为"未设置"，merge() 中全继承 global。

        兼容性：
        - MemoryConfig() → 显式字段集默认空 → 全继承 global
        - MemoryConfig(field=value) + mark_explicit({field}) → 覆盖 global
        - YAML 反序列化时，出现的字段全部 mark_explicit
        """
        # _explicit_fields 默认为空集（由 default_factory=set 提供）
        # 调用方通过 mark_explicit() 显式注册"显式字段"
        pass

    @classmethod
    def mark_explicit(cls, cfg: "MemoryConfig", field_names: Set[str]) -> "MemoryConfig":
        """手动注册 cfg 中哪些字段是"显式"提供的（用于 merge() 判断）。

        典型用法（YAML 反序列化、API 入口）：
            cfg = MemoryConfig.from_yaml(...)
            MemoryConfig.mark_explicit(cfg, set(cfg.__dict__.keys()))

        注意：正常使用 MemoryConfig(field=value) 时，__post_init__ 会
        自动捕获 kwargs，无需再调用本方法。
        """
        object.__setattr__(cfg, "_explicit_fields", set(field_names))
        return cfg

    @property
    def explicit_fields(self) -> Set[str]:
        """只读访问构造时显式提供的字段集合。"""
        return set(self._explicit_fields)

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
        if self.dialogue_compression_max_retries < 0 or self.dialogue_compression_max_retries > 5:
            errors.append(
                f"dialogue_compression_max_retries="
                f"{self.dialogue_compression_max_retries} 超出 0-5 范围"
            )
        if self.auto_compaction_threshold < 10000 or self.auto_compaction_threshold > 500000:
            errors.append(
                f"auto_compaction_threshold={self.auto_compaction_threshold} "
                "超出 10000-500000 范围"
            )
        return errors

    @classmethod
    def merge(
        cls,
        global_cfg: "MemoryConfig",
        agent_cfg: Optional["MemoryConfig"],
    ) -> "MemoryConfig":
        """合并 global + agent 配置。

        合并规则（v4 - 混合策略，向后兼容）：
        - agent_cfg=None → 返回 global
        - agent_cfg 字段被 mark_explicit 标记 → 一律覆盖 global
        - agent_cfg 字段是 Optional 且值为 None → 继承 global
        - agent_cfg 字段非 None 且 != 字段默认 → 覆盖 global
        - agent_cfg 字段 == 字段默认 → 继承 global（与 v1 一致）

        新增能力（v2/v3 改进）：
        通过 mark_explicit() 显式标记的字段（即使值==字段默认），会
        覆盖 global。这解决了"agent 想显式恢复字段默认，但 global 是
        非默认值时无法生效"的问题。

        Optional 字段特例（dialogue_llm_model: Optional[str] = None）：
        - None 视为"跟随 global"
        """
        if agent_cfg is None:
            return global_cfg

        explicit_fields = set(getattr(agent_cfg, "_explicit_fields", set()))

        merged = cls()
        for field_name in cls.__dataclass_fields__:
            if field_name.startswith("_"):  # 跳过内部字段
                continue
            global_value = getattr(global_cfg, field_name)
            agent_value = getattr(agent_cfg, field_name)
            field_default = cls.__dataclass_fields__[field_name].default

            # Optional 字段：None 视为"跟随 global"
            field_type = cls.__dataclass_fields__[field_name].type
            is_optional = field_type is not None and (
                "Optional" in str(field_type) or "None" in str(field_type)
            )
            if is_optional and agent_value is None:
                setattr(merged, field_name, global_value)
                continue

            # 已被 mark_explicit 标记 → 显式覆盖
            if field_name in explicit_fields:
                setattr(merged, field_name, agent_value)
                continue

            # 默认行为：值 != 字段默认 → 覆盖
            if agent_value != field_default:
                setattr(merged, field_name, agent_value)
            else:
                # 值 == 字段默认 → 继承 global（与 v1 行为一致）
                setattr(merged, field_name, global_value)
        return merged
