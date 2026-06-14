"""Task 14: MemoryManager 配置热重载端到端集成测试。

验证:
1. reload_config() 后新配置传播到 SummaryCompressor
2. reload_config() 清空压缩器缓存，后续访问用新实例
3. 无配置文件时 reload_config 不崩溃
4. 损坏的 YAML 不影响旧配置
"""
from __future__ import annotations

import pytest
from novels_project.memory.memory_manager import MemoryManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def config_path(tmp_path):
    """返回临时目录中的 memory_config.yaml 路径。"""
    return tmp_path / "config" / "memory_config.yaml"


@pytest.fixture
def mgr(tmp_path, config_path):
    """构造一个 MemoryManager（不持久化、不调用 LLM）。"""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        "global:\n"
        "  chapter_window: 100\n"
        "  max_summary_blocks: 10\n"
        "agents:\n"
        "  plot_writer:\n"
        "    max_summary_blocks: 5\n",
        encoding="utf-8",
    )
    return MemoryManager(project_root=tmp_path, config_path=str(config_path))


# ---------------------------------------------------------------------------
# 场景 1: 重载后配置传播到新压缩器
# ---------------------------------------------------------------------------

def test_config_reload_propagates_to_new_compressor(config_path, mgr):
    """修改 YAML 后 reload_config，新配置应生效。"""
    # 初始值
    assert mgr.get_memory_config("plot_writer").max_summary_blocks == 5

    # 修改 YAML
    config_path.write_text(
        "global:\n"
        "  chapter_window: 100\n"
        "  max_summary_blocks: 10\n"
        "agents:\n"
        "  plot_writer:\n"
        "    max_summary_blocks: 7\n",
        encoding="utf-8",
    )

    # reload 前仍然是旧值
    assert mgr.get_memory_config("plot_writer").max_summary_blocks == 5

    # 重载
    mgr.reload_config()

    # reload 后新值生效
    assert mgr.get_memory_config("plot_writer").max_summary_blocks == 7


# ---------------------------------------------------------------------------
# 场景 2: 重载清空 SummaryCompressor 缓存
# ---------------------------------------------------------------------------

def test_reload_clears_summary_compressor_cache(mgr):
    """reload_config 后压缩器缓存应清空，再次访问创建新实例。"""
    # 获取并缓存 compressor 实例
    c1 = mgr.get_summary_compressor("main")

    # 重载
    mgr.reload_config()

    # 再次获取应是新实例
    c2 = mgr.get_summary_compressor("main")
    assert c1 is not c2


# ---------------------------------------------------------------------------
# 场景 3: 无配置文件时 reload 不崩溃
# ---------------------------------------------------------------------------

def test_reload_without_config_file_does_not_crash(tmp_path):
    """配置文件不存在时 reload_config 应回退到默认值。"""
    missing_path = tmp_path / "nonexistent" / "memory_config.yaml"
    mgr = MemoryManager(project_root=tmp_path, config_path=str(missing_path))

    # 不崩溃
    mgr.reload_config()

    # 使用默认配置
    cfg = mgr.get_memory_config("main")
    assert cfg.chapter_window == 100  # 默认值


# ---------------------------------------------------------------------------
# 场景 4: 损坏的 YAML 不影响旧配置（回退到默认值）
# ---------------------------------------------------------------------------

def test_reload_corrupted_yaml_falls_back_to_defaults(config_path, mgr):
    """YAML 格式错误时 reload_config 回退到默认值而非崩溃。"""
    # 写入损坏的 YAML
    config_path.write_text("{{invalid yaml: [}", encoding="utf-8")

    # 重新加载不会崩溃，回退到默认值
    mgr.reload_config()

    cfg = mgr.get_memory_config("plot_writer")
    # plot_writer 没有 agent 覆盖了，使用 global 默认
    assert cfg.max_summary_blocks == 3  # MemoryConfig 默认值
