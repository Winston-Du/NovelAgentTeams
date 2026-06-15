"""MemoryConfig 数据类单元测试。

覆盖 4 个核心场景：
1. 默认值正确（向后兼容）
2. 字段赋值正确
3. validate() 校验
4. merge() 配置合并（agent 覆盖 global）
"""
from novels_project.memory.memory_config import MemoryConfig


# === 场景 1: 默认值 ===

def test_default_values():
    """未传参数时所有字段使用默认值。"""
    cfg = MemoryConfig()
    assert cfg.chapter_window == 100
    assert cfg.max_summary_blocks == 3
    assert cfg.summary_max_chars == 2000
    assert cfg.dialogue_compression_threshold == 0.8
    assert cfg.preserve_recent_messages == 4
    assert cfg.dialogue_summary_max_chars == 4000
    assert cfg.dialogue_context_summary_max_chars == 1500
    assert cfg.dialogue_llm_model is None
    assert cfg.subagent_compression_enabled is True
    assert cfg.subagent_max_messages == 30


# === 场景 2: 字段赋值 ===

def test_custom_field_assignment():
    """所有字段可被显式赋值。"""
    cfg = MemoryConfig(
        chapter_window=200,
        max_summary_blocks=5,
        summary_max_chars=3000,
        dialogue_compression_threshold=0.7,
        preserve_recent_messages=6,
        dialogue_summary_max_chars=4000,
        dialogue_llm_model="custom/model",
        subagent_compression_enabled=False,
        subagent_max_messages=50,
    )
    assert cfg.chapter_window == 200
    assert cfg.max_summary_blocks == 5
    assert cfg.dialogue_llm_model == "custom/model"
    assert cfg.subagent_compression_enabled is False


# === 场景 3: validate() ===

def test_validate_default_config_passes():
    """默认配置应通过校验。"""
    cfg = MemoryConfig()
    errors = cfg.validate()
    assert errors == []


def test_validate_max_summary_blocks_out_of_range():
    """max_summary_blocks 超出 1-10 范围时报错。"""
    cfg = MemoryConfig(max_summary_blocks=15)
    errors = cfg.validate()
    assert any("max_summary_blocks" in e for e in errors)


def test_validate_max_summary_blocks_too_low():
    """max_summary_blocks < 1 报错。"""
    cfg = MemoryConfig(max_summary_blocks=0)
    errors = cfg.validate()
    assert any("max_summary_blocks" in e for e in errors)


def test_validate_threshold_out_of_range_low():
    """dialogue_compression_threshold < 0.5 报错。"""
    cfg = MemoryConfig(dialogue_compression_threshold=0.3)
    errors = cfg.validate()
    assert any("dialogue_compression_threshold" in e for e in errors)


def test_validate_threshold_out_of_range_high():
    """dialogue_compression_threshold > 0.95 报错。"""
    cfg = MemoryConfig(dialogue_compression_threshold=0.99)
    errors = cfg.validate()
    assert any("dialogue_compression_threshold" in e for e in errors)


def test_validate_preserve_recent_messages_too_low():
    """preserve_recent_messages < 2 报错（避免破坏对话连贯性）。"""
    cfg = MemoryConfig(preserve_recent_messages=1)
    errors = cfg.validate()
    assert any("preserve_recent_messages" in e for e in errors)


def test_validate_summary_max_chars_too_small():
    """summary_max_chars < 500 应被拒绝。"""
    cfg = MemoryConfig(summary_max_chars=499)
    errors = cfg.validate()
    assert any("summary_max_chars" in e for e in errors)


def test_validate_dialogue_summary_max_chars_too_small():
    """dialogue_summary_max_chars < 1000 应被拒绝。"""
    cfg = MemoryConfig(dialogue_summary_max_chars=500)
    errors = cfg.validate()
    assert any("dialogue_summary_max_chars" in e for e in errors)


def test_validate_context_summary_exceeds_total():
    """context_summary > total 应被拒绝。"""
    cfg = MemoryConfig(
        dialogue_summary_max_chars=2000,
        dialogue_context_summary_max_chars=3000,
    )
    errors = cfg.validate()
    assert any("不能超过" in e for e in errors)


def test_validate_returns_empty_for_valid_config():
    """合法配置 validate() 返回空列表。"""
    cfg = MemoryConfig(
        max_summary_blocks=5,
        dialogue_compression_threshold=0.85,
        preserve_recent_messages=4,
        summary_max_chars=1500,
    )
    assert cfg.validate() == []


# === 场景 4: merge() ===

def test_merge_with_none_agent_uses_global():
    """agent_cfg=None 时返回 global。"""
    global_cfg = MemoryConfig(dialogue_compression_threshold=0.7)
    merged = MemoryConfig.merge(global_cfg, None)
    assert merged.dialogue_compression_threshold == 0.7


def test_merge_agent_overrides_global_explicit_value():
    """agent 显式设置的值覆盖 global。"""
    global_cfg = MemoryConfig(
        dialogue_compression_threshold=0.8,
        max_summary_blocks=3,
    )
    agent_cfg = MemoryConfig(dialogue_compression_threshold=0.5)  # 显式覆盖
    MemoryConfig.mark_explicit(agent_cfg, {"dialogue_compression_threshold"})
    merged = MemoryConfig.merge(global_cfg, agent_cfg)
    # agent 显式值覆盖
    assert merged.dialogue_compression_threshold == 0.5
    # 未显式设置继承 global
    assert merged.max_summary_blocks == 3


def test_merge_agent_explicit_default_overrides_global():
    """agent 显式标记为"显式"的字段（即使值==字段默认）应覆盖 global。

    设计动机：原实现用"是否等于字段默认值"判断，会导致 agent 显式
    设为默认值时无法覆盖 global 中的非默认值。
    新实现（v3）：通过 mark_explicit() 显式注册"显式字段集"，调用方
    在 YAML 反序列化/API 入口处标记，merge() 据此判断。
    """
    global_cfg = MemoryConfig(
        dialogue_compression_threshold=0.6,
        max_summary_blocks=7,
    )
    # agent_cfg 用字段默认（0.8/3），但通过 mark_explicit 标记为"显式"
    agent_cfg = MemoryConfig(
        dialogue_compression_threshold=0.8,    # 显式（值==默认）
        max_summary_blocks=3,                  # 显式（值==默认）
    )
    MemoryConfig.mark_explicit(
        agent_cfg,
        {"dialogue_compression_threshold", "max_summary_blocks"},
    )
    merged = MemoryConfig.merge(global_cfg, agent_cfg)
    assert merged.dialogue_compression_threshold == 0.8  # 来自 agent（显式）
    assert merged.max_summary_blocks == 3                # 来自 agent（显式）


def test_merge_agent_inherits_global_when_not_marked_explicit():
    """agent 字段未通过 mark_explicit 标记 → 继承 global。

    注意：frame inspection 现在会通过 __post_init__ 自动捕获 kwargs，
    所以 `MemoryConfig()` 显式字段集为空，merge() 会全继承 global。
    """
    global_cfg = MemoryConfig(
        dialogue_compression_threshold=0.6,
        max_summary_blocks=7,
        dialogue_llm_model="gpt-4",
    )
    # agent 字段为字段默认，且未调用 mark_explicit → 显式字段集为空
    agent_cfg = MemoryConfig()
    merged = MemoryConfig.merge(global_cfg, agent_cfg)
    # 所有字段均继承 global
    assert merged.dialogue_compression_threshold == 0.6
    assert merged.max_summary_blocks == 7
    assert merged.dialogue_llm_model == "gpt-4"


def test_merge_optional_none_field_inherits_global():
    """dialogue_llm_model 显式 None → 继承 global（仅限 Optional 字段）。"""
    global_cfg = MemoryConfig(
        dialogue_llm_model="gpt-4",
        max_summary_blocks=5,
    )
    # agent 显式设置 dialogue_llm_model=None
    agent_cfg = MemoryConfig(dialogue_llm_model=None, max_summary_blocks=10)
    MemoryConfig.mark_explicit(
        agent_cfg,
        {"dialogue_llm_model", "max_summary_blocks"},
    )
    merged = MemoryConfig.merge(global_cfg, agent_cfg)
    # None 表示"跟随 global"
    assert merged.dialogue_llm_model == "gpt-4"
    # 其他显式字段正常覆盖
    assert merged.max_summary_blocks == 10


def test_merge_subagent_config():
    """子 agent 独立配置场景。"""
    global_cfg = MemoryConfig(
        dialogue_compression_threshold=0.8,
        preserve_recent_messages=4,
    )
    plot_writer_cfg = MemoryConfig(
        dialogue_compression_threshold=0.5,  # 显式覆盖
        preserve_recent_messages=2,          # 显式覆盖
    )
    MemoryConfig.mark_explicit(
        plot_writer_cfg,
        {"dialogue_compression_threshold", "preserve_recent_messages"},
    )
    merged = MemoryConfig.merge(global_cfg, plot_writer_cfg)
    assert merged.dialogue_compression_threshold == 0.5
    assert merged.preserve_recent_messages == 2


# === 真实场景：显式默认值 vs 全局非默认值 ===

def test_scenario_explicit_default_overrides_global():
    """场景 A：global 为非默认值，agent 显式设为默认值 → 应覆盖。

    业务背景：主编习惯沿用系统默认阈值 0.8，但全公司统一调高到 0.95
    以减少压缩次数。主编希望自己恢复默认 0.8。
    """
    global_cfg = MemoryConfig(
        dialogue_compression_threshold=0.95,   # 全公司统一调高
        max_summary_blocks=5,                  # 全公司统一 5
    )
    # 主编 agent 显式设置（值==字段默认 0.8）→ 应覆盖 global
    main_editor_cfg = MemoryConfig(
        dialogue_compression_threshold=0.8,    # 显式恢复默认
    )
    MemoryConfig.mark_explicit(
        main_editor_cfg,
        {"dialogue_compression_threshold"},
    )
    merged = MemoryConfig.merge(global_cfg, main_editor_cfg)
    # 关键断言：agent 显式 0.8 覆盖了 global 的 0.95
    assert merged.dialogue_compression_threshold == 0.8, \
        f"agent 显式默认值应覆盖 global 的非默认值，实际={merged.dialogue_compression_threshold}"
    # max_summary_blocks 未在 agent 中显式标记 → 继承 global
    assert merged.max_summary_blocks == 5


def test_scenario_partial_override_with_optional_none():
    """场景 B：agent 部分字段覆盖，None 字段继承 global。

    业务背景：剧情撰写 agent 单独调整摘要块数与对话阈值，
    但 LLM 模型字段设为 None（跟随运行时 default），应继承 global。
    """
    global_cfg = MemoryConfig(
        max_summary_blocks=10,                 # global 调高
        dialogue_compression_threshold=0.6,    # global 调低
        dialogue_llm_model="gpt-4",            # global 指定
        chapter_window=500,
    )
    plot_writer_cfg = MemoryConfig(
        max_summary_blocks=4,                  # 显式覆盖
        dialogue_compression_threshold=0.6,    # 与 global 同值（显式）
        dialogue_llm_model=None,               # 显式 None → 继承 global
    )
    MemoryConfig.mark_explicit(
        plot_writer_cfg,
        {"max_summary_blocks", "dialogue_compression_threshold", "dialogue_llm_model"},
    )
    merged = MemoryConfig.merge(global_cfg, plot_writer_cfg)
    assert merged.max_summary_blocks == 4           # 来自 agent
    assert merged.dialogue_compression_threshold == 0.6  # 来自 agent
    assert merged.dialogue_llm_model == "gpt-4"      # 继承 global
    assert merged.chapter_window == 500              # 继承 global（未标记）


def test_scenario_all_fields_inherit_when_agent_is_minimal():
    """场景 C：agent 几乎没设置（空配置）→ 应继承 global。

    业务背景：新加的"人物设计" agent 暂时沿用全部 global 配置。
    """
    global_cfg = MemoryConfig(
        chapter_window=300,
        max_summary_blocks=8,
        dialogue_compression_threshold=0.7,
        preserve_recent_messages=6,
        dialogue_summary_max_chars=5000,
        subagent_max_messages=40,
    )
    # agent 几乎为"空配置"：仅显式标记一个 None
    character_designer_cfg = MemoryConfig()
    # 不调用 mark_explicit → 显式字段集为空 → 全继承 global
    merged = MemoryConfig.merge(global_cfg, character_designer_cfg)
    # 所有 numeric 字段都应继承 global
    assert merged.chapter_window == 300
    assert merged.max_summary_blocks == 8
    assert merged.dialogue_compression_threshold == 0.7
    assert merged.preserve_recent_messages == 6
    assert merged.dialogue_summary_max_chars == 5000
    assert merged.subagent_max_messages == 40
    # None 字段继承 global（global 也是 None）
    assert merged.dialogue_llm_model is None


def test_scenario_global_changes_after_agent_set():
    """场景 D：global 调整后，已配置的 agent 行为是否符合预期。

    业务背景：业务方将 global 对话阈值从 0.8 调到 0.6，
    检查已存在的 agent 配置（显式设了 0.95）是否仍为 0.95。
    """
    # 初始：global=0.8, agent=0.95（已标记显式）
    old_global = MemoryConfig(dialogue_compression_threshold=0.8)
    agent = MemoryConfig(dialogue_compression_threshold=0.95)
    MemoryConfig.mark_explicit(agent, {"dialogue_compression_threshold"})
    merged_v1 = MemoryConfig.merge(old_global, agent)
    assert merged_v1.dialogue_compression_threshold == 0.95

    # 业务方调整：global=0.6
    new_global = MemoryConfig(dialogue_compression_threshold=0.6)
    merged_v2 = MemoryConfig.merge(new_global, agent)
    # agent 仍显式 0.95 → 不受 global 变化影响
    assert merged_v2.dialogue_compression_threshold == 0.95, \
        "agent 显式覆盖应独立于 global 变化"


def test_scenario_optional_field_override_chain():
    """场景 E：Optional 字段（dialogue_llm_model）覆盖链。

    业务背景：
    - global 设为 gpt-4
    - agent A 显式设为 claude-3-opus
    - agent B 显式设为 None → 回到 global（gpt-4）
    """
    global_cfg = MemoryConfig(dialogue_llm_model="gpt-4")
    agent_a = MemoryConfig(dialogue_llm_model="claude-3-opus")
    MemoryConfig.mark_explicit(agent_a, {"dialogue_llm_model"})
    agent_b = MemoryConfig(dialogue_llm_model=None)
    MemoryConfig.mark_explicit(agent_b, {"dialogue_llm_model"})

    merged_a = MemoryConfig.merge(global_cfg, agent_a)
    merged_b = MemoryConfig.merge(global_cfg, agent_b)

    assert merged_a.dialogue_llm_model == "claude-3-opus"
    assert merged_b.dialogue_llm_model == "gpt-4"   # 继承 global


def test_scenario_explicit_same_value_as_global():
    """场景 F：agent 显式设置与 global 相同值 → 仍算覆盖（应一致）。

    业务背景：有时运维会"显式重写"配置以表明意图，即使值未变。
    """
    global_cfg = MemoryConfig(
        max_summary_blocks=5,
        dialogue_compression_threshold=0.7,
    )
    agent = MemoryConfig(
        max_summary_blocks=5,             # 显式 5（与 global 同）
        dialogue_compression_threshold=0.7, # 显式 0.7（与 global 同）
    )
    MemoryConfig.mark_explicit(
        agent,
        {"max_summary_blocks", "dialogue_compression_threshold"},
    )
    merged = MemoryConfig.merge(global_cfg, agent)
    # 显式值与 global 同值，结果仍为 5/0.7（无歧义）
    assert merged.max_summary_blocks == 5
    assert merged.dialogue_compression_threshold == 0.7


def test_scenario_boolean_and_int_override():
    """场景 G：bool / int 字段覆盖（含 subagent）。"""
    global_cfg = MemoryConfig(
        subagent_compression_enabled=False,   # global 关闭
        subagent_max_messages=50,             # global 大窗口
        auto_compaction_threshold=200000,
    )
    agent = MemoryConfig(
        subagent_compression_enabled=True,    # 显式开启
        subagent_max_messages=10,             # 显式小窗口
    )
    MemoryConfig.mark_explicit(
        agent,
        {"subagent_compression_enabled", "subagent_max_messages"},
    )
    merged = MemoryConfig.merge(global_cfg, agent)
    # bool 与 int 字段均按"显式覆盖"语义处理
    assert merged.subagent_compression_enabled is True
    assert merged.subagent_max_messages == 10
    # 未在 agent 中显式标记的字段继承 global
    assert merged.auto_compaction_threshold == 200000


def test_scenario_none_agent_returns_global_unchanged():
    """场景 H：agent_cfg=None → 直接返回 global（不变）。"""
    global_cfg = MemoryConfig(
        dialogue_compression_threshold=0.5,
        max_summary_blocks=12,
        dialogue_llm_model="gpt-4o",
    )
    merged = MemoryConfig.merge(global_cfg, None)
    assert merged.dialogue_compression_threshold == 0.5
    assert merged.max_summary_blocks == 12
    assert merged.dialogue_llm_model == "gpt-4o"


# === 边界场景 ===

def test_scenario_empty_explicit_set_inherits_everything():
    """agent_cfg 显式字段集为空 → 全继承 global（包括 bool 字段）。"""
    global_cfg = MemoryConfig(
        subagent_compression_enabled=False,
        subagent_max_messages=50,
    )
    agent_cfg = MemoryConfig()  # 显式字段集为空
    merged = MemoryConfig.merge(global_cfg, agent_cfg)
    # bool 与 int 均继承 global
    assert merged.subagent_compression_enabled is False
    assert merged.subagent_max_messages == 50


def test_scenario_mark_explicit_empty_set_falls_back_to_default_rule():
    """mark_explicit(空集) 退化到"默认值判断"规则。

    v4 混合策略：当 agent_cfg 字段未被 mark_explicit 标记时，仍使用
    v1 的"值==字段默认→继承 global"行为。
    """
    global_cfg = MemoryConfig(
        dialogue_compression_threshold=0.6,
        max_summary_blocks=7,
    )
    agent_cfg = MemoryConfig(
        dialogue_compression_threshold=0.95,  # != 字段默认 0.8 → 覆盖
        max_summary_blocks=12,                  # != 字段默认 3 → 覆盖
    )
    # 显式标记为空 → 退回到默认值判断
    MemoryConfig.mark_explicit(agent_cfg, set())
    merged = MemoryConfig.merge(global_cfg, agent_cfg)
    # 字段值 != 字段默认 → 仍覆盖 global
    assert merged.dialogue_compression_threshold == 0.95
    assert merged.max_summary_blocks == 12


def test_scenario_mark_explicit_partial_then_inherit():
    """agent 部分标记显式：标记的覆盖 global，未标记的按 v1 规则。"""
    global_cfg = MemoryConfig(
        dialogue_compression_threshold=0.6,
        max_summary_blocks=7,
        chapter_window=500,
    )
    agent_cfg = MemoryConfig(
        dialogue_compression_threshold=0.95,  # 显式
        max_summary_blocks=12,                  # 显式
        chapter_window=300,                     # 显式
    )
    # 只标记 1 个为显式
    MemoryConfig.mark_explicit(agent_cfg, {"dialogue_compression_threshold"})
    merged = MemoryConfig.merge(global_cfg, agent_cfg)
    # 标记的字段覆盖
    assert merged.dialogue_compression_threshold == 0.95
    # 未标记的字段按 v1 规则：值 != 字段默认 → 覆盖
    assert merged.max_summary_blocks == 12
    assert merged.chapter_window == 300


def test_scenario_explicit_fields_property():
    """explicit_fields 属性正确反映 mark_explicit 注册的字段。"""
    cfg = MemoryConfig(
        dialogue_compression_threshold=0.6,
        max_summary_blocks=5,
    )
    MemoryConfig.mark_explicit(cfg, {"dialogue_compression_threshold", "max_summary_blocks"})
    assert "dialogue_compression_threshold" in cfg.explicit_fields
    assert "max_summary_blocks" in cfg.explicit_fields
    assert "chapter_window" not in cfg.explicit_fields
