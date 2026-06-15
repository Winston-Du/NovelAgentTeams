"""MemoryManager 顶层门面单元测试。

覆盖 5 个核心场景：
1. 初始化（缺失文件/含 agent 覆盖）
2. get_memory_config 路由分发（agent 覆盖 + global fallback）
3. get_summary_compressor 缓存（命中/未命中）
4. create_dialogue_compactor 工厂（每次新建）
5. reload_config 热重载
6. 11 处 logger 埋点验证
"""
import logging

import pytest

from novels_project.memory.memory_manager import MemoryManager
from novels_project.memory.dialogue_compactor import DialogueCompactor


MM_LOGGER = "novels_project.memory.memory_manager"


# === Fixtures ===

@pytest.fixture
def tmp_project(tmp_path):
    """构造一个临时项目根（含 YAML 配置文件）。"""
    config_path = tmp_path / "config" / "memory_config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        """
global:
  max_summary_blocks: 3
  dialogue_compression_threshold: 0.8
  preserve_recent_messages: 4
  summary_max_chars: 2000
agents:
  plot_writer:
    dialogue_compression_threshold: 0.7
    preserve_recent_messages: 6
  character_agent:
    max_summary_blocks: 5
""",
        encoding="utf-8",
    )
    return tmp_path, config_path


@pytest.fixture
def tmp_project_no_yaml(tmp_path):
    """无 YAML 配置的临时项目根。"""
    return tmp_path, tmp_path / "config" / "memory_config.yaml"


@pytest.fixture
def empty_yaml_project(tmp_path):
    """YAML 文件存在但为空的临时项目根。"""
    config_path = tmp_path / "config" / "memory_config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("", encoding="utf-8")
    return tmp_path, config_path


# === 场景 1: 初始化 ===

def test_init_with_yaml_file(tmp_project, caplog):
    """正常初始化：加载 YAML 成功。"""
    caplog.set_level(logging.INFO, logger=MM_LOGGER)
    project_root, config_path = tmp_project
    mgr = MemoryManager(project_root=project_root, config_path=config_path)
    assert mgr.config_bundle is not None
    assert mgr.config_bundle.global_config is not None
    # 验证缓存初始化为空
    assert mgr._summary_compressors == {}
    # 验证日志
    log_messages = [r.message for r in caplog.records]
    assert any("__init__ 入口" in m for m in log_messages)
    assert any("YAML 加载完成" in m for m in log_messages)
    assert any("agent 路由初始化完成" in m for m in log_messages)


def test_init_with_missing_yaml(tmp_project_no_yaml, caplog):
    """YAML 文件缺失时回落到默认值（不抛异常）。"""
    caplog.set_level(logging.INFO, logger=MM_LOGGER)
    project_root, config_path = tmp_project_no_yaml
    mgr = MemoryManager(project_root=project_root, config_path=config_path)
    # global_config 应该是 MemoryConfig 的默认值
    assert mgr.config_bundle.global_config is not None
    # 缺失文件 → 0 个 agent
    assert mgr.config_bundle.agent_configs == {}


def test_init_with_empty_yaml(empty_yaml_project, caplog):
    """YAML 文件为空时不应抛异常。"""
    caplog.set_level(logging.INFO, logger=MM_LOGGER)
    project_root, config_path = empty_yaml_project
    mgr = MemoryManager(project_root=project_root, config_path=config_path)
    # 应该是默认值
    assert mgr.config_bundle.global_config is not None


def test_init_logs_cache_size(tmp_project, caplog):
    """初始化时记录缓存初始大小。"""
    caplog.set_level(logging.INFO, logger=MM_LOGGER)
    project_root, config_path = tmp_project
    MemoryManager(project_root=project_root, config_path=config_path)
    log_messages = [r.message for r in caplog.records]
    assert any("缓存初始化完成" in m and "cache_size=0" in m for m in log_messages)


# === 场景 2: get_memory_config 路由分发 ===

def test_get_memory_config_uses_agent_override(tmp_project):
    """get_memory_config 返回 agent 覆盖后的配置。"""
    project_root, config_path = tmp_project
    mgr = MemoryManager(project_root=project_root, config_path=config_path)
    cfg = mgr.get_memory_config("plot_writer")
    # plot_writer 覆盖了 threshold=0.7, preserve=6
    assert cfg.dialogue_compression_threshold == 0.7
    assert cfg.preserve_recent_messages == 6


def test_get_memory_config_uses_global_fallback(tmp_project):
    """未知 agent 应回落到 global 配置。"""
    project_root, config_path = tmp_project
    mgr = MemoryManager(project_root=project_root, config_path=config_path)
    cfg = mgr.get_memory_config("unknown_agent")
    # global 的 threshold=0.8, preserve=4
    assert cfg.dialogue_compression_threshold == 0.8
    assert cfg.preserve_recent_messages == 4


def test_get_memory_config_logs_routing(tmp_project, caplog):
    """get_memory_config 记录路由日志。"""
    caplog.set_level(logging.INFO, logger=MM_LOGGER)
    project_root, config_path = tmp_project
    mgr = MemoryManager(project_root=project_root, config_path=config_path)
    mgr.get_memory_config("plot_writer")  # 命中
    mgr.get_memory_config("unknown")      # 未命中

    log_messages = [r.message for r in caplog.records]
    override_logs = [m for m in log_messages if "has_agent_override=True" in m]
    fallback_logs = [m for m in log_messages if "has_agent_override=False" in m]
    assert len(override_logs) >= 1
    assert len(fallback_logs) >= 1


# === 场景 3: get_summary_compressor 缓存 ===

def test_summary_compressor_cache_hit(tmp_project, caplog):
    """同一 agent 多次调用 get_summary_compressor 应返回同一实例。"""
    caplog.set_level(logging.INFO, logger=MM_LOGGER)
    project_root, config_path = tmp_project
    mgr = MemoryManager(project_root=project_root, config_path=config_path)
    c1 = mgr.get_summary_compressor("plot_writer")
    c2 = mgr.get_summary_compressor("plot_writer")
    assert c1 is c2

    log_messages = [r.message for r in caplog.records]
    assert any("缓存未命中，创建实例" in m for m in log_messages)
    assert any("缓存命中" in m for m in log_messages)


def test_summary_compressor_different_agents(tmp_project):
    """不同 agent 应创建不同的 SummaryCompressor 实例。"""
    project_root, config_path = tmp_project
    mgr = MemoryManager(project_root=project_root, config_path=config_path)
    c1 = mgr.get_summary_compressor("plot_writer")
    c2 = mgr.get_summary_compressor("character_agent")
    assert c1 is not c2


def test_summary_compressor_uses_config(tmp_project):
    """SummaryCompressor 应使用 get_memory_config 的结果。"""
    project_root, config_path = tmp_project
    mgr = MemoryManager(project_root=project_root, config_path=config_path)
    c = mgr.get_summary_compressor("plot_writer")
    # plot_writer 的配置合并
    assert c.config.dialogue_compression_threshold == 0.7
    assert c.config.preserve_recent_messages == 6
    # storage_dir 应基于 agent_id
    assert c.storage_dir.name == "plot_writer"


# === 场景 4: create_dialogue_compactor 工厂 ===

def test_dialogue_compactor_creates_new_instance_each_time(tmp_project):
    """create_dialogue_compactor 每次调用都创建新实例（不缓存）。"""
    project_root, config_path = tmp_project
    mgr = MemoryManager(project_root=project_root, config_path=config_path)
    d1 = mgr.create_dialogue_compactor("plot_writer")
    d2 = mgr.create_dialogue_compactor("plot_writer")
    assert d1 is not d2
    assert isinstance(d1, DialogueCompactor)


def test_dialogue_compactor_uses_config(tmp_project):
    """DialogueCompactor 应使用 agent 的配置。"""
    project_root, config_path = tmp_project
    mgr = MemoryManager(project_root=project_root, config_path=config_path)
    d = mgr.create_dialogue_compactor("plot_writer")
    assert d.config.preserve_recent_messages == 6
    assert d.config.dialogue_compression_threshold == 0.7


def test_dialogue_compactor_logs_creation(tmp_project, caplog):
    """create_dialogue_compactor 记录创建日志。"""
    caplog.set_level(logging.INFO, logger=MM_LOGGER)
    project_root, config_path = tmp_project
    mgr = MemoryManager(project_root=project_root, config_path=config_path)
    mgr.create_dialogue_compactor("plot_writer")
    log_messages = [r.message for r in caplog.records]
    assert any("create_dialogue_compactor" in m for m in log_messages)


# === 场景 5: get_summary_for_injection ===

def test_get_summary_for_injection_returns_empty_when_no_blocks(tmp_project):
    """无块时返回空字符串（不抛异常）。"""
    project_root, config_path = tmp_project
    mgr = MemoryManager(project_root=project_root, config_path=config_path)
    text = mgr.get_summary_for_injection("plot_writer")
    assert text == ""


def test_get_summary_for_injection_logs(tmp_project, caplog):
    """get_summary_for_injection 记录日志。"""
    caplog.set_level(logging.INFO, logger=MM_LOGGER)
    project_root, config_path = tmp_project
    mgr = MemoryManager(project_root=project_root, config_path=config_path)
    mgr.get_summary_for_injection("plot_writer")
    log_messages = [r.message for r in caplog.records]
    assert any("get_summary_for_injection" in m for m in log_messages)


# === 场景 6: reload_config 热重载 ===

def test_reload_config_clears_cache(tmp_project, caplog):
    """reload_config 应清空 SummaryCompressor 缓存。"""
    caplog.set_level(logging.INFO, logger=MM_LOGGER)
    project_root, config_path = tmp_project
    mgr = MemoryManager(project_root=project_root, config_path=config_path)
    c1 = mgr.get_summary_compressor("plot_writer")
    assert "plot_writer" in mgr._summary_compressors

    mgr.reload_config()
    assert mgr._summary_compressors == {}

    # 重新调用应创建新实例
    c2 = mgr.get_summary_compressor("plot_writer")
    assert c1 is not c2


def test_reload_config_logs(tmp_project, caplog):
    """reload_config 记录清理数量与重新加载日志。"""
    caplog.set_level(logging.INFO, logger=MM_LOGGER)
    project_root, config_path = tmp_project
    mgr = MemoryManager(project_root=project_root, config_path=config_path)
    mgr.get_summary_compressor("plot_writer")
    mgr.get_summary_compressor("character_agent")

    caplog.clear()
    mgr.reload_config()
    log_messages = [r.message for r in caplog.records]
    assert any("reload_config 开始" in m and "cleared_compressors=2" in m
               for m in log_messages)
    assert any("reload_config 完成" in m for m in log_messages)


# === 场景 7: 11 处 logger 埋点集成验证 ===

def test_all_eleven_logger_points_trigger(tmp_project, caplog):
    """验证 11 处关键 logger 埋点全部可触发。

    触发路径：
    1. __init__ 入口
    2. YAML 加载完成
    3. global config validate
    4. agent 路由初始化
    5. 缓存初始化
    6. get_memory_config 路由
    7. SummaryCompressor 缓存
    8. create_dialogue_compactor 工厂
    9. on_chapter_generated 回调（用直接调 _add 不行，此处跳过）
    10. get_summary_for_injection
    11. reload_config
    """
    caplog.set_level(logging.INFO, logger=MM_LOGGER)
    project_root, config_path = tmp_project

    # 1-5: __init__
    mgr = MemoryManager(project_root=project_root, config_path=config_path)

    # 6: get_memory_config
    mgr.get_memory_config("plot_writer")
    mgr.get_memory_config("unknown")

    # 7: SummaryCompressor 缓存
    mgr.get_summary_compressor("plot_writer")  # 命中缓存
    mgr.get_summary_compressor("character_agent")  # 未命中

    # 8: create_dialogue_compactor
    mgr.create_dialogue_compactor("plot_writer")

    # 10: get_summary_for_injection
    mgr.get_summary_for_injection("plot_writer")

    # 11: reload_config
    mgr.reload_config()

    # 验证所有日志点都出现
    log_messages = [r.message for r in caplog.records]
    log_text = " ".join(log_messages)

    expected_phrases = [
        "__init__ 入口",              # 1
        "YAML 加载完成",               # 2
        "global 配置校验",             # 3
        "agent 路由初始化完成",        # 4
        "缓存初始化完成",              # 5
        "get_memory_config 路由",      # 6
        "SummaryCompressor 缓存",      # 7
        "create_dialogue_compactor",   # 8
        "get_summary_for_injection",   # 10
        "reload_config",               # 11
    ]
    for phrase in expected_phrases:
        assert phrase in log_text, f"Missing log phrase: {phrase}"


# === 场景 8: on_chapter_generated 回调 ===

def test_on_chapter_generated_no_trigger(tmp_project, caplog):
    """on_chapter_generated 累加但不触发压缩。"""
    caplog.set_level(logging.INFO, logger=MM_LOGGER)
    project_root, config_path = tmp_project
    mgr = MemoryManager(project_root=project_root, config_path=config_path)

    # 1 章不会触发压缩（chapter_window=100）
    result = mgr.on_chapter_generated("plot_writer", 1, "# 第1章\n第一章内容")
    assert result is None

    log_messages = [r.message for r in caplog.records]
    assert any("on_chapter_generated 回调" in m for m in log_messages)
    assert any("章节摘要提取完成" in m for m in log_messages)


def test_on_chapter_generated_triggers_compression(tmp_path, caplog):
    """on_chapter_generated 达到 chapter_window 时触发压缩。"""
    caplog.set_level(logging.INFO, logger=MM_LOGGER)
    config_path = tmp_path / "config" / "memory_config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        """
global:
  chapter_window: 3
""",
        encoding="utf-8",
    )
    mgr = MemoryManager(project_root=tmp_path, config_path=config_path)

    result1 = mgr.on_chapter_generated("main", 1, "# 第1章\nA")
    result2 = mgr.on_chapter_generated("main", 2, "# 第2章\nB")
    result3 = mgr.on_chapter_generated("main", 3, "# 第3章\nC")  # 触发
    assert result1 is None
    assert result2 is None
    assert result3 is not None
    assert result3.start_chapter == 1
    assert result3.end_chapter == 3

    log_messages = [r.message for r in caplog.records]
    assert any("章节触发压缩完成" in m and "block_id=" in m for m in log_messages)


# === 场景 9: agent 配置校验失败 ===

def test_agent_config_validation_warns(tmp_path, caplog):
    """agent 配置不合法时记录警告日志。"""
    caplog.set_level(logging.INFO, logger=MM_LOGGER)
    config_path = tmp_path / "config" / "memory_config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    # threshold=-1 不合法
    config_path.write_text(
        """
global:
  dialogue_compression_threshold: 0.8
agents:
  bad_agent:
    dialogue_compression_threshold: -0.1
""",
        encoding="utf-8",
    )
    MemoryManager(project_root=tmp_path, config_path=config_path)

    log_messages = [r.message for r in caplog.records]
    assert any("agent[bad_agent] 配置校验失败" in m for m in log_messages)


def test_global_config_validation_warns(tmp_path, caplog):
    """global 配置不合法时记录警告日志。"""
    caplog.set_level(logging.INFO, logger=MM_LOGGER)
    config_path = tmp_path / "config" / "memory_config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    # threshold=-1 不合法
    config_path.write_text(
        """
global:
  dialogue_compression_threshold: -0.1
""",
        encoding="utf-8",
    )
    MemoryManager(project_root=tmp_path, config_path=config_path)

    log_messages = [r.message for r in caplog.records]
    assert any("global 配置校验失败" in m for m in log_messages)


# === 场景 10: 附加参数传递 ===

def test_init_with_llm_client_and_chapters_dir(tmp_project, caplog):
    """传入 llm_client 和 chapters_dir 时应正确传递。"""
    caplog.set_level(logging.INFO, logger=MM_LOGGER)
    project_root, config_path = tmp_project

    class MockLLM:
        default_model = "test-model"

    chapters_dir = project_root / "chapters"
    mgr = MemoryManager(
        project_root=project_root,
        config_path=config_path,
        llm_client=MockLLM(),
        chapters_dir=chapters_dir,
    )
    assert mgr.llm_client is not None
    assert mgr.chapters_dir == chapters_dir

    # compressor 应能取到 llm_client 和 chapters_dir
    compressor = mgr.get_summary_compressor("plot_writer")
    assert compressor.llm_client is not None
    assert compressor.chapters_dir == chapters_dir
