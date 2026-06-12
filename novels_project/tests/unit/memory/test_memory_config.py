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
    assert cfg.dialogue_summary_max_chars == 3000
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


def test_validate_summary_max_chars_too_low():
    """summary_max_chars < 500 报错。"""
    cfg = MemoryConfig(summary_max_chars=100)
    errors = cfg.validate()
    assert any("summary_max_chars" in e for e in errors)


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
    merged = MemoryConfig.merge(global_cfg, agent_cfg)
    # agent 显式值覆盖
    assert merged.dialogue_compression_threshold == 0.5
    # 未显式设置继承 global
    assert merged.max_summary_blocks == 3


def test_merge_agent_inherits_global_for_default_value():
    """agent 未显式设置（值==默认）时继承 global。"""
    global_cfg = MemoryConfig(
        dialogue_compression_threshold=0.6,
        max_summary_blocks=7,
    )
    # agent_cfg 用默认值（==字段默认）
    agent_cfg = MemoryConfig()
    merged = MemoryConfig.merge(global_cfg, agent_cfg)
    # 全继承 global
    assert merged.dialogue_compression_threshold == 0.6
    assert merged.max_summary_blocks == 7


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
    merged = MemoryConfig.merge(global_cfg, plot_writer_cfg)
    assert merged.dialogue_compression_threshold == 0.5
    assert merged.preserve_recent_messages == 2
