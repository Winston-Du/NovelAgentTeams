"""MemoryConfigBundle YAML 加载单元测试。

覆盖 7 个核心场景：
1. 空 / 不存在文件 → 默认配置
2. 仅 global 配置
3. global + agents 多 agent
4. agent 字段缺失 → 继承 global
5. 非法字段被忽略
6. YAML 格式错误
7. get_resolved() 返回合并后配置
"""
import pytest
from pathlib import Path

from novels_project.memory.memory_config import MemoryConfig
from novels_project.memory.memory_config_bundle import MemoryConfigBundle


# === 场景 1: 文件不存在 / 空文件 ===

def test_load_from_nonexistent_path_returns_defaults(tmp_path):
    """YAML 文件不存在时返回默认配置（不抛异常）。"""
    bundle = MemoryConfigBundle.load_from_yaml(tmp_path / "nope.yaml")
    assert bundle.global_config.chapter_window == 100
    assert bundle.global_config.dialogue_compression_threshold == 0.8
    assert bundle.agent_configs == {}
    assert bundle.resolved == {}


def test_load_from_empty_file_returns_defaults(tmp_path):
    """YAML 文件为空时返回默认配置。"""
    f = tmp_path / "empty.yaml"
    f.write_text("", encoding="utf-8")
    bundle = MemoryConfigBundle.load_from_yaml(f)
    assert bundle.global_config.chapter_window == 100
    assert bundle.agent_configs == {}


# === 场景 2: 仅 global ===

def test_load_global_only(tmp_path):
    """YAML 仅有 global 时正确加载。"""
    f = tmp_path / "config.yaml"
    f.write_text("""
global:
  chapter_window: 100
  max_summary_blocks: 5
  dialogue_compression_threshold: 0.85
""", encoding="utf-8")
    bundle = MemoryConfigBundle.load_from_yaml(f)
    assert bundle.global_config.max_summary_blocks == 5
    assert bundle.global_config.dialogue_compression_threshold == 0.85
    assert bundle.agent_configs == {}


# === 场景 3: global + agents ===

def test_load_global_and_multiple_agents(tmp_path):
    """YAML 含 global + 多个 agents 时正确加载。"""
    f = tmp_path / "config.yaml"
    f.write_text("""
global:
  max_summary_blocks: 3
  dialogue_compression_threshold: 0.8

agents:
  plot_writer:
    dialogue_compression_threshold: 0.5
    preserve_recent_messages: 2

  proofreader:
    max_summary_blocks: 2
""", encoding="utf-8")
    bundle = MemoryConfigBundle.load_from_yaml(f)
    assert "plot_writer" in bundle.agent_configs
    assert "proofreader" in bundle.agent_configs
    assert bundle.agent_configs["plot_writer"].dialogue_compression_threshold == 0.5
    assert bundle.agent_configs["plot_writer"].preserve_recent_messages == 2
    assert bundle.agent_configs["proofreader"].max_summary_blocks == 2


# === 场景 4: agent 字段缺失 → 继承 global ===

def test_resolved_merges_agent_with_global(tmp_path):
    """resolved 配置合并 agent 显式值与 global。"""
    f = tmp_path / "config.yaml"
    f.write_text("""
global:
  max_summary_blocks: 3
  dialogue_compression_threshold: 0.8
  preserve_recent_messages: 4

agents:
  plot_writer:
    dialogue_compression_threshold: 0.5
    # preserve_recent_messages 未显式设置 → 继承 global
""", encoding="utf-8")
    bundle = MemoryConfigBundle.load_from_yaml(f)
    resolved = bundle.get_resolved("plot_writer")
    # agent 显式覆盖
    assert resolved.dialogue_compression_threshold == 0.5
    # 继承 global
    assert resolved.preserve_recent_messages == 4
    assert resolved.max_summary_blocks == 3


# === 场景 5: 非法字段被忽略 ===

def test_unknown_fields_are_ignored(tmp_path):
    """YAML 中未识别的字段应被忽略（不抛异常）。"""
    f = tmp_path / "config.yaml"
    f.write_text("""
global:
  chapter_window: 100
  unknown_field: 12345

agents:
  plot_writer:
    dialogue_compression_threshold: 0.5
    bogus_field: "whatever"
""", encoding="utf-8")
    # 不应抛异常
    bundle = MemoryConfigBundle.load_from_yaml(f)
    assert bundle.global_config.chapter_window == 100
    assert bundle.agent_configs["plot_writer"].dialogue_compression_threshold == 0.5


# === 场景 6: get_resolved() ===

def test_get_resolved_known_agent(tmp_path):
    """已知 agent 返回合并后的配置。"""
    f = tmp_path / "config.yaml"
    f.write_text("""
global:
  max_summary_blocks: 3

agents:
  plot_writer:
    max_summary_blocks: 5
""", encoding="utf-8")
    bundle = MemoryConfigBundle.load_from_yaml(f)
    cfg = bundle.get_resolved("plot_writer")
    assert isinstance(cfg, MemoryConfig)
    assert cfg.max_summary_blocks == 5


def test_get_resolved_unknown_agent_returns_global(tmp_path):
    """未知 agent 返回 global_config（兜底）。"""
    f = tmp_path / "config.yaml"
    f.write_text("""
global:
  max_summary_blocks: 3
""", encoding="utf-8")
    bundle = MemoryConfigBundle.load_from_yaml(f)
    cfg = bundle.get_resolved("nonexistent_agent")
    assert cfg is bundle.global_config
    assert cfg.max_summary_blocks == 3


# === 场景 7: 空 agents 块 ===

def test_load_with_empty_agents_block(tmp_path):
    """YAML 含 agents: {} 时不报错。"""
    f = tmp_path / "config.yaml"
    f.write_text("""
global:
  chapter_window: 100

agents: {}
""", encoding="utf-8")
    bundle = MemoryConfigBundle.load_from_yaml(f)
    assert bundle.agent_configs == {}
    assert bundle.resolved == {}
