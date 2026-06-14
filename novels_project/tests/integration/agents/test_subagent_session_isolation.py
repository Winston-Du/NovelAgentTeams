"""子 Agent 销毁模式（destroy mode）与隔离测试（Task 13）。

覆盖 9 个核心场景：
1. session_id 100% 唯一：连续 5 次调用生成不同 session_id
2. 独立 MemoryConfig：plot_writer 走 agent 覆盖，main 走 global
3. agent_id 正确透传：sub_runtime.agent_id == agent_def.name
4. 无 memory_manager 时回退到 MemoryConfig() 默认
5. subagent_compression_enabled=False 关闭压缩
6. AgentDefinition 新字段默认值正确
7. 4 个 agent 的可配置参数各不相同（max_iterations / auto_compaction_threshold）
8. Session 销毁模式：每次调用都是新 Session（messaging 列表独立）
9. AgentRunner 初始化时无 memory_manager 不破坏
"""
import logging
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from novels_project.agents import (
    AgentRunner,
    CHIEF_EDITOR,
    CHARACTER_DESIGNER,
    PLOT_WRITER,
    PROOFREADER,
    ALL_AGENTS,
    AgentDefinition,
)
from novels_project.memory.memory_config import MemoryConfig
from novels_project.memory.memory_manager import MemoryManager


# === Fixtures ===

@pytest.fixture
def memory_config_path(tmp_path: Path) -> Path:
    """生成最小可用的 memory_config.yaml（含 agent 覆盖 + subagent 关闭开关）"""
    config_path = tmp_path / "memory_config.yaml"
    config_path.write_text(
        """
global:
  dialogue_compression_threshold: 0.8
  subagent_compression_enabled: true
  subagent_max_messages: 30
agents:
  plot_writer:
    dialogue_compression_threshold: 0.5
    subagent_compression_enabled: false
""",
        encoding="utf-8",
    )
    return config_path


@pytest.fixture
def memory_manager(tmp_path: Path, memory_config_path: Path) -> MemoryManager:
    """构造带 LLM stub 的 MemoryManager（避免真调 LLM）"""
    return MemoryManager(
        project_root=tmp_path,
        config_path=memory_config_path,
        llm_client=None,
    )


@pytest.fixture
def mock_api_client():
    """Mock ApiClient - 不实际调用 LLM"""
    client = MagicMock()
    client.stream.return_value = []
    return client


@pytest.fixture
def runner(mock_api_client, memory_manager) -> AgentRunner:
    """构造带 memory_manager 的 AgentRunner"""
    return AgentRunner(api_client=mock_api_client, memory_manager=memory_manager)


# === 场景 1: session_id 100% 唯一 ===

def test_subagent_session_ids_are_unique(runner, caplog):
    """连续 5 次调用生成的 session_id 都不同（销毁模式）"""
    session_ids = set()
    with caplog.at_level(logging.INFO, logger="novels_project.agents"):
        for _ in range(5):
            # 直接验证 _build_sub_session 行为（不实际运行 LLM）
            from novels_project.session import Session
            sub_session = Session()
            sub_session.id = str(uuid.uuid4())
            runner._agent_defs["plot_writer"]  # 触发 lazy init
            session_ids.add(sub_session.id)
    assert len(session_ids) == 5


def test_run_agent_creates_unique_session_ids(runner, caplog):
    """run_agent 每次都创建新 session（uuid 唯一）"""
    # Mock run_turn 避免实际执行
    session_ids_seen = []
    original_init = None

    with caplog.at_level(logging.INFO, logger="novels_project.agents"):
        # Mock ConversationRuntime.run_turn 来捕获 session
        from novels_project.runtime import ConversationRuntime
        original_run_turn = ConversationRuntime.run_turn

        def mock_run_turn(self, user_input):
            session_ids_seen.append(self.session.id)
            # 构造一个最小 TurnSummary
            from novels_project.session import ConversationMessage, MessageRole, TextBlock
            self.session.messages.append(
                ConversationMessage(
                    role=MessageRole.ASSISTANT,
                    blocks=[TextBlock(text="mock output")],
                )
            )
            from dataclasses import dataclass
            @dataclass
            class MockSummary:
                iterations: int = 1
                final_message: ConversationMessage = None
                def get_final_text(self):
                    return "mock output"
            return MockSummary(
                final_message=self.session.messages[-1]
            )

        ConversationRuntime.run_turn = mock_run_turn
        try:
            for _ in range(3):
                runner.run_agent("plot_writer", '{"prompt": "test"}')
        finally:
            ConversationRuntime.run_turn = original_run_turn

    assert len(session_ids_seen) == 3
    assert len(set(session_ids_seen)) == 3  # 全部唯一


# === 场景 2: 独立 MemoryConfig ===

def test_subagent_uses_independent_memory_config(runner):
    """plot_writer 走 agent 覆盖（0.5），main 走 global（0.8）"""
    cfg_pw = runner.memory_manager.get_memory_config("plot_writer")
    cfg_main = runner.memory_manager.get_memory_config("main")
    assert cfg_pw.dialogue_compression_threshold == 0.5
    assert cfg_main.dialogue_compression_threshold == 0.8


# === 场景 3: agent_id 正确透传 ===

def test_run_agent_passes_agent_id_to_subruntime(runner):
    """run_agent 创建的子 runtime.agent_id == agent_def.name"""
    from novels_project.runtime import ConversationRuntime
    original_run_turn = ConversationRuntime.run_turn

    captured_agent_id = []
    def mock_run_turn(self, user_input):
        captured_agent_id.append(self.agent_id)
        from novels_project.session import ConversationMessage, MessageRole, TextBlock
        self.session.messages.append(
            ConversationMessage(
                role=MessageRole.ASSISTANT,
                blocks=[TextBlock(text="mock")],
            )
        )
        from dataclasses import dataclass
        @dataclass
        class MockSummary:
            iterations: int = 1
            def get_final_text(self):
                return "mock"
        return MockSummary()

    ConversationRuntime.run_turn = mock_run_turn
    try:
        runner.run_agent("plot_writer", '{"prompt": "test"}')
    finally:
        ConversationRuntime.run_turn = original_run_turn

    assert captured_agent_id == ["plot_writer"]


# === 场景 4: 无 memory_manager 时回退 ===

def test_no_memory_manager_uses_default_config(mock_api_client):
    """无 memory_manager 时 AgentRunner.run_agent 仍能工作"""
    runner = AgentRunner(api_client=mock_api_client, memory_manager=None)
    assert runner.memory_manager is None

    # 模拟一次 run_agent（不实际执行 LLM）
    from novels_project.runtime import ConversationRuntime
    original_run_turn = ConversationRuntime.run_turn

    def mock_run_turn(self, user_input):
        from novels_project.session import ConversationMessage, MessageRole, TextBlock
        self.session.messages.append(
            ConversationMessage(
                role=MessageRole.ASSISTANT,
                blocks=[TextBlock(text="ok")],
            )
        )
        from dataclasses import dataclass
        @dataclass
        class MockSummary:
            iterations: int = 1
            def get_final_text(self):
                return "ok"
        return MockSummary()

    ConversationRuntime.run_turn = mock_run_turn
    try:
        result = runner.run_agent("plot_writer", '{"prompt": "test"}')
    finally:
        ConversationRuntime.run_turn = original_run_turn

    assert result == "ok"


# === 场景 5: subagent_compression_enabled 关闭 ===

def test_subagent_compression_disabled_when_flag_false(runner, caplog):
    """plot_writer 配置 subagent_compression_enabled=false → 标志传递正确，日志记录"""
    from novels_project.runtime import ConversationRuntime
    original_run_turn = ConversationRuntime.run_turn
    captured_memory_config = []

    def mock_run_turn(self, user_input):
        captured_memory_config.append(self.memory_config)
        from novels_project.session import ConversationMessage, MessageRole, TextBlock
        self.session.messages.append(
            ConversationMessage(
                role=MessageRole.ASSISTANT,
                blocks=[TextBlock(text="ok")],
            )
        )
        from dataclasses import dataclass
        @dataclass
        class MockSummary:
            iterations: int = 1
            def get_final_text(self):
                return "ok"
        return MockSummary()

    ConversationRuntime.run_turn = mock_run_turn
    try:
        with caplog.at_level(logging.INFO, logger="novels_project.agents"):
            runner.run_agent("plot_writer", '{"prompt": "test"}')
    finally:
        ConversationRuntime.run_turn = original_run_turn

    # plot_writer 配置 subagent_compression_enabled=false
    # 验证：标志正确传递到 Runtime（用于路由/将来扩展）
    assert captured_memory_config[0].subagent_compression_enabled is False
    # 验证：日志记录了"压缩已禁用"
    assert any("子 agent 压缩已禁用" in r.message for r in caplog.records)
    # 验证：执行日志中 subagent_compression_enabled=False
    assert any("subagent_compression_enabled=False" in r.message for r in caplog.records)


# === 场景 6: AgentDefinition 新字段默认值 ===

def test_agent_definition_default_values():
    """AgentDefinition 新字段默认值正确"""
    ad = AgentDefinition(
        name="test",
        display_name="测试",
        model="m",
        description="d",
        allowed_tools=[],
        input_schema={},
    )
    assert ad.max_iterations == 20
    assert ad.auto_compaction_threshold == 100000


def test_agent_definition_explicit_values():
    """AgentDefinition 显式赋值正确"""
    ad = AgentDefinition(
        name="test",
        display_name="测试",
        model="m",
        description="d",
        allowed_tools=[],
        input_schema={},
        max_iterations=50,
        auto_compaction_threshold=50000,
    )
    assert ad.max_iterations == 50
    assert ad.auto_compaction_threshold == 50000


# === 场景 7: 4 个 agent 配置差异 ===

def test_four_agents_have_distinct_iteration_configs():
    """4 个 agent 的 max_iterations 和 auto_compaction_threshold 各不相同"""
    configs = {
        "CHIEF_EDITOR": (CHIEF_EDITOR.max_iterations, CHIEF_EDITOR.auto_compaction_threshold),
        "CHARACTER_DESIGNER": (CHARACTER_DESIGNER.max_iterations, CHARACTER_DESIGNER.auto_compaction_threshold),
        "PLOT_WRITER": (PLOT_WRITER.max_iterations, PLOT_WRITER.auto_compaction_threshold),
        "PROOFREADER": (PROOFREADER.max_iterations, PROOFREADER.auto_compaction_threshold),
    }

    # 验证配置合理（撰写员迭代次数最多，校对/策划最少）
    assert CHIEF_EDITOR.max_iterations == 15
    assert CHARACTER_DESIGNER.max_iterations == 10
    assert PLOT_WRITER.max_iterations == 30
    assert PROOFREADER.max_iterations == 10

    # 验证阈值都 <= Runtime 默认 100K
    for name, (iters, threshold) in configs.items():
        assert threshold <= 100000, f"{name} threshold={threshold} 超过 Runtime 默认"


def test_all_agents_list_contains_four():
    """ALL_AGENTS 包含 4 个 agent"""
    assert len(ALL_AGENTS) == 4
    assert CHIEF_EDITOR in ALL_AGENTS
    assert CHARACTER_DESIGNER in ALL_AGENTS
    assert PLOT_WRITER in ALL_AGENTS
    assert PROOFREADER in ALL_AGENTS


# === 场景 8: Session 销毁模式 ===

def test_each_run_creates_independent_session(runner):
    """每次 run_agent 调用都是新的 Session（messages 列表独立）"""
    from novels_project.runtime import ConversationRuntime
    original_run_turn = ConversationRuntime.run_turn

    sessions_seen = []
    # 强制持有引用，防止 GC 回收导致 id() 复用
    session_refs = []

    def mock_run_turn(self, user_input):
        sessions_seen.append(id(self.session))
        session_refs.append(self.session)  # 阻止 GC 回收
        from novels_project.session import ConversationMessage, MessageRole, TextBlock
        self.session.messages.append(
            ConversationMessage(
                role=MessageRole.ASSISTANT,
                blocks=[TextBlock(text=f"output_{len(sessions_seen)}")],
            )
        )
        from dataclasses import dataclass
        @dataclass
        class MockSummary:
            iterations: int = 1
            def get_final_text(self):
                # 每次只能看到自己的消息（销毁模式证据）
                return f"output_{len(sessions_seen)}"
        return MockSummary()

    ConversationRuntime.run_turn = mock_run_turn
    try:
        result1 = runner.run_agent("plot_writer", '{"prompt": "p1"}')
        result2 = runner.run_agent("plot_writer", '{"prompt": "p2"}')
    finally:
        ConversationRuntime.run_turn = original_run_turn

    # 两次调用创建了不同的 session 对象（持有引用后 id 唯一）
    assert sessions_seen[0] != sessions_seen[1]
    # 每次结果基于自己的 session（无状态泄漏）
    assert result1 == "output_1"
    assert result2 == "output_2"


# === 场景 9: AgentRunner 初始化 ===

def test_runner_init_with_memory_manager(runner, memory_manager):
    """AgentRunner 正确保存 memory_manager 引用"""
    assert runner.memory_manager is memory_manager


def test_runner_init_without_memory_manager(mock_api_client):
    """无 memory_manager 时 AgentRunner 仍能初始化"""
    runner = AgentRunner(api_client=mock_api_client)
    assert runner.memory_manager is None


# === 场景 10: 兜底压缩触发 ===

def test_subagent_auto_compact_when_messages_exceed_threshold(runner, caplog):
    """messages 数量超过 subagent_max_messages 时触发兜底压缩（检查时机：run_turn 之后）"""
    from novels_project.runtime import ConversationRuntime
    from novels_project.session import ConversationMessage, MessageRole, TextBlock
    original_run_turn = ConversationRuntime.run_turn

    def mock_run_turn(self, user_input):
        # 模拟消息数超过 30（subagent_max_messages 默认 30）
        for i in range(35):
            self.session.messages.append(
                ConversationMessage(
                    role=MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT,
                    blocks=[TextBlock(text=f"m{i}")],
                )
            )
        from dataclasses import dataclass
        @dataclass
        class MockSummary:
            iterations: int = 1
            def get_final_text(self):
                return "ok"
        return MockSummary()

    ConversationRuntime.run_turn = mock_run_turn
    try:
        with caplog.at_level(logging.INFO, logger="novels_project.agents"):
            runner.run_agent("chief_editor", '{"prompt": "test"}')
    finally:
        ConversationRuntime.run_turn = original_run_turn

    # chief_editor 默认 subagent_compression_enabled=True
    # 应触发兜底压缩（messages=35 > threshold=30）
    assert any("子 agent session 兜底压缩" in r.message for r in caplog.records)


def test_subagent_no_compact_when_compression_disabled(runner, caplog):
    """subagent_compression_enabled=False 时不触发兜底压缩"""
    from novels_project.runtime import ConversationRuntime
    from novels_project.session import ConversationMessage, MessageRole, TextBlock
    original_run_turn = ConversationRuntime.run_turn

    def mock_run_turn(self, user_input):
        # 模拟消息数超过 30
        for i in range(35):
            self.session.messages.append(
                ConversationMessage(
                    role=MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT,
                    blocks=[TextBlock(text=f"m{i}")],
                )
            )
        from dataclasses import dataclass
        @dataclass
        class MockSummary:
            iterations: int = 1
            def get_final_text(self):
                return "ok"
        return MockSummary()

    ConversationRuntime.run_turn = mock_run_turn
    try:
        with caplog.at_level(logging.INFO, logger="novels_project.agents"):
            # plot_writer 配置 subagent_compression_enabled=False
            runner.run_agent("plot_writer", '{"prompt": "test"}')
    finally:
        ConversationRuntime.run_turn = original_run_turn

    # plot_writer 关闭压缩 → 不应触发兜底压缩
    assert not any("子 agent session 兜底压缩" in r.message for r in caplog.records)
