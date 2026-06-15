"""cli.py MemoryManager wiring 测试骨架（Task 13 配套 - cli.py wiring 阶段）。

本测试套件覆盖 9 个核心场景：
1. _build_runtime 内部构造了 MemoryManager 实例
2. AgentRunner 接收了 MemoryManager
3. 主 Runtime 接收了 MemoryManager
4. 主 Runtime agent_id == "main"
5. 主 Runtime 接收了 MemoryConfig
6. auto_compaction_threshold 被显式传入（非默认值）
7. MemoryManager 构造失败时 runtime 仍可启动
8. 子 agent 路由使用 wired MemoryManager
9. 主 Runtime 与 AgentRunner 共享同一 MemoryManager 实例

⚠️ 当前状态：SKELETON - 所有测试应失败（红色），等待 cli.py 实施完成后转绿
"""
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# === 共享 Fixtures ===

@pytest.fixture
def project_with_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """构造最小可用项目结构，并将 cli.get_project_root 固定到该目录。
    ```
    tmp_path/
      config/
        memory_config.yaml    # MemoryManager 配置
    """
    import novels_project.cli as cli_module

    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "memory_config.yaml").write_text(
        """
global:
  dialogue_compression_threshold: 0.8
  subagent_compression_enabled: true
  subagent_max_messages: 30
  auto_compaction_threshold: 80000
agents:
  plot_writer:
    dialogue_compression_threshold: 0.5
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(cli_module, "get_project_root", lambda: tmp_path)
    return tmp_path


@pytest.fixture
def mock_llm_client():
    """Mock LLM client - 避免实际 LLM 调用"""
    client = MagicMock()
    client.stream.return_value = []
    return client


@pytest.fixture
def mock_graph_integrator():
    """Mock GraphMemoryIntegrator - 避免图谱初始化"""
    integrator = MagicMock()
    integrator.is_initialized.return_value = True
    return integrator


@pytest.fixture
def build_runtime_setup(project_with_config, mock_llm_client, mock_graph_integrator):
    """统一 patch _build_runtime 的外部依赖，配置项目根和 LLM client"""
    return {
        "project_root": project_with_config,
        "llm_client": mock_llm_client,
        "graph_integrator": mock_graph_integrator,
    }


# === 测试 1: _build_runtime 内部构造 MemoryManager ===

def test_build_runtime_constructs_memory_manager(project_with_config, mock_llm_client, mock_graph_integrator):
    """_build_runtime 内部构造了 MemoryManager 实例

    验收：返回的元组中包含 memory_manager，且不为 None
    """
    from novels_project.cli import _build_runtime

    with patch("novels_project.cli.create_llm_client", return_value=mock_llm_client), \
         patch("novels_project.cli.GraphMemoryIntegrator", return_value=mock_graph_integrator):
        result = _build_runtime()
        # 解构返回值 - 实施后应为 4-tuple
        assert len(result) == 4, f"期望 4-tuple，实际 {len(result)}-tuple"
        runtime, session_id, graph_integrator, memory_manager = result
        assert memory_manager is not None
        assert hasattr(memory_manager, "project_root")
        assert hasattr(memory_manager, "get_memory_config")


# === 测试 2: AgentRunner 接收 MemoryManager ===

def test_agent_runner_receives_memory_manager(project_with_config, mock_llm_client, mock_graph_integrator):
    """AgentRunner 接收了 memory_manager（不再为 None）

    验收：runtime 内置的 agent_runner.memory_manager 不为 None
    """
    from novels_project.cli import _build_runtime

    with patch("novels_project.cli.create_llm_client", return_value=mock_llm_client), \
         patch("novels_project.cli.GraphMemoryIntegrator", return_value=mock_graph_integrator):
        runtime, *_ = _build_runtime()
        # 主 Runtime 关联的 tool_executor 中持有 agent_runner
        agent_runner = runtime.tool_executor.agent_runner
        assert agent_runner.memory_manager is not None


# === 测试 3: 主 Runtime 接收 MemoryManager ===

def test_main_runtime_receives_memory_manager(project_with_config, mock_llm_client, mock_graph_integrator):
    """主 Runtime 接收了 memory_manager

    验收：runtime.memory_manager 不为 None
    """
    from novels_project.cli import _build_runtime

    with patch("novels_project.cli.create_llm_client", return_value=mock_llm_client), \
         patch("novels_project.cli.GraphMemoryIntegrator", return_value=mock_graph_integrator):
        runtime, *_ = _build_runtime()
        assert runtime.memory_manager is not None
        # 进一步验证是 MemoryManager 实例
        from novels_project.memory.memory_manager import MemoryManager
        assert isinstance(runtime.memory_manager, MemoryManager)


# === 测试 4: 主 Runtime agent_id == "main" ===

def test_main_runtime_uses_main_agent_id(project_with_config, mock_llm_client, mock_graph_integrator):
    """主 Runtime agent_id 显式为 "main"（非隐式默认）

    验收：runtime.agent_id == "main"
    """
    from novels_project.cli import _build_runtime

    with patch("novels_project.cli.create_llm_client", return_value=mock_llm_client), \
         patch("novels_project.cli.GraphMemoryIntegrator", return_value=mock_graph_integrator):
        runtime, *_ = _build_runtime()
        assert runtime.agent_id == "main"


# === 测试 5: 主 Runtime 接收 MemoryConfig ===

def test_main_runtime_receives_memory_config(project_with_config, mock_llm_client, mock_graph_integrator):
    """主 Runtime 接收了 memory_config（来自 MemoryManager.get_memory_config("main")）

    验收：runtime.memory_config 不为 None
         且是来自 wired MemoryManager 的实例（id 一致）
    """
    from novels_project.cli import _build_runtime
    from novels_project.memory.memory_config import MemoryConfig

    with patch("novels_project.cli.create_llm_client", return_value=mock_llm_client), \
         patch("novels_project.cli.GraphMemoryIntegrator", return_value=mock_graph_integrator):
        result = _build_runtime()
        # 实施后是 4-tuple，未实施是 3-tuple
        runtime, session_id, graph_integrator = result[:3]
        memory_manager = result[3] if len(result) >= 4 else None

        assert runtime.memory_config is not None
        assert isinstance(runtime.memory_config, MemoryConfig)
        # 关键断言：memory_config 来源于 wired MemoryManager
        # 通过比较同一 agent 的 config 来验证
        if memory_manager is not None:
            expected_cfg = memory_manager.get_memory_config("main")
            # dialogue_compression_threshold 应该一致
            assert runtime.memory_config.dialogue_compression_threshold == expected_cfg.dialogue_compression_threshold


# === 测试 6: auto_compaction_threshold 显式传入 ===

def test_auto_compaction_threshold_passed_explicitly(project_with_config, mock_llm_client, mock_graph_integrator):
    """auto_compaction_threshold 是显式传入的，不是 Runtime 隐式默认

    验收：runtime.auto_compaction_threshold 来自 memory_config（80000）
         而非 Runtime 的默认 100000
    """
    from novels_project.cli import _build_runtime

    with patch("novels_project.cli.create_llm_client", return_value=mock_llm_client), \
         patch("novels_project.cli.GraphMemoryIntegrator", return_value=mock_graph_integrator):
        runtime, *_ = _build_runtime()
        # YAML 中显式配置了 auto_compaction_threshold: 80000
        # 若 _build_runtime 没有读取此配置并传入，应为 Runtime 默认值 100000
        assert runtime.auto_compaction_threshold == 80000


# === 测试 7: MemoryManager 构造失败不阻塞 runtime ===

def test_memory_manager_init_failure_does_not_block_runtime(tmp_path, mock_llm_client, mock_graph_integrator, caplog, monkeypatch):
    """memory_config.yaml 不存在时，MemoryManager 仍使用默认配置，runtime 仍可启动

    验收：runtime 正常返回，agent_runner.memory_manager 不为 None
         日志记录 WARNING（未找到配置文件）
    """
    import novels_project.cli as cli_module

    # 关键：不创建 config/memory_config.yaml，但固定 project_root
    monkeypatch.setattr(cli_module, "get_project_root", lambda: tmp_path)

    with patch("novels_project.cli.create_llm_client", return_value=mock_llm_client), \
         patch("novels_project.cli.GraphMemoryIntegrator", return_value=mock_graph_integrator), \
         caplog.at_level(logging.WARNING):
        from novels_project.cli import _build_runtime
        runtime, *_ = _build_runtime()
        # 关键断言：runtime 仍可启动
        assert runtime is not None
        # 降级行为：没有配置时仍使用默认 MemoryManager
        agent_runner = runtime.tool_executor.agent_runner
        assert agent_runner.memory_manager is not None
        # 验证有降级日志
        assert any(
            "未找到 memory_config.yaml" in r.message
            for r in caplog.records
        )


# === 测试 7b: 显式验证无配置时仍使用默认 MemoryManager ===

def test_explicit_fallback_when_no_config(tmp_path, mock_llm_client, mock_graph_integrator, monkeypatch):
    """当 config 文件不存在时，验证 wiring 仍可降级

    验收：runtime 不崩溃，agent_runner.memory_manager 不为 None
         （使用默认 MemoryManager，而非 None）
    """
    import novels_project.cli as cli_module

    # 使用 tmp_path 作为 CWD，config/ 子目录不存在
    monkeypatch.setattr(cli_module, "get_project_root", lambda: tmp_path)
    with patch("novels_project.cli.create_llm_client", return_value=mock_llm_client), \
         patch("novels_project.cli.GraphMemoryIntegrator", return_value=mock_graph_integrator):
        from novels_project.cli import _build_runtime
        runtime, *_ = _build_runtime()
        # 关键断言：runtime.memory_manager 是默认 MemoryManager
        agent_runner = runtime.tool_executor.agent_runner
        assert agent_runner.memory_manager is not None
        assert runtime.memory_manager is agent_runner.memory_manager


# === 测试 8: 子 agent 路由使用 wired MemoryManager ===

def test_subagent_routing_uses_wired_memory_manager(project_with_config, mock_llm_client, mock_graph_integrator, monkeypatch):
    """子 agent 调用 → 拉取 wired MemoryManager 的 MemoryConfig

    验收：plot_writer agent 的 sub_runtime.memory_config.subagent_compression_enabled
         与 wired MemoryManager 中的配置一致
    """
    from novels_project.cli import _build_runtime
    from novels_project.runtime import ConversationRuntime

    with patch("novels_project.cli.create_llm_client", return_value=mock_llm_client), \
         patch("novels_project.cli.GraphMemoryIntegrator", return_value=mock_graph_integrator):
        runtime, *_ = _build_runtime()
        agent_runner = runtime.tool_executor.agent_runner

        # Mock run_turn 捕获子 runtime
        captured_configs = []
        original_run_turn = ConversationRuntime.run_turn

        def mock_run_turn(self, user_input):
            captured_configs.append(self.memory_config)
            # 构造最小返回
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
            agent_runner.run_agent("plot_writer", '{"prompt": "test"}')
        finally:
            ConversationRuntime.run_turn = original_run_turn

        # 子 runtime 应使用 wired memory_manager 的配置
        assert len(captured_configs) == 1
        assert captured_configs[0] is not None
        # 关键：plot_writer 的 subagent_compression_enabled 默认 True
        # 但 dialogue_compression_threshold 来自 plot_writer 覆盖（0.5）
        assert captured_configs[0].subagent_compression_enabled is True
        # 关键断言：覆盖生效（证明 wired MemoryManager 起作用）
        assert captured_configs[0].dialogue_compression_threshold == 0.5


# === 测试 9: 主 Runtime 与 AgentRunner 共享同一 MemoryManager 实例 ===

def test_runtime_memory_paths_consistent(project_with_config, mock_llm_client, mock_graph_integrator):
    """主 Runtime 的 memory_manager 与 agent_runner.memory_manager 是同一实例

    验收：id(runtime.memory_manager) == id(agent_runner.memory_manager)
         保证子 agent 写入的摘要能被主 agent 读到
    """
    from novels_project.cli import _build_runtime

    with patch("novels_project.cli.create_llm_client", return_value=mock_llm_client), \
         patch("novels_project.cli.GraphMemoryIntegrator", return_value=mock_graph_integrator):
        runtime, *_ = _build_runtime()
        agent_runner = runtime.tool_executor.agent_runner

        # 关键断言：两个 memory_manager 都不为 None（证明 wired 生效）
        assert runtime.memory_manager is not None, \
            "runtime.memory_manager 仍为 None，wiring 未生效"
        assert agent_runner.memory_manager is not None, \
            "agent_runner.memory_manager 仍为 None，wiring 未生效"
        # 进一步：两个 memory_manager 是同一实例
        assert runtime.memory_manager is agent_runner.memory_manager, \
            "两个 memory_manager 不是同一实例，wiring 不一致"


# === 辅助函数（供其他测试复用） ===

def _mock_create_llm_client(mock_client):
    """构造 create_llm_client 的 patch context"""
    return patch("novels_project.cli.create_llm_client", return_value=mock_client)


def _mock_graph_integrator_factory(mock_integrator):
    """构造 GraphMemoryIntegrator 的 patch context"""
    return patch("novels_project.cli.GraphMemoryIntegrator", return_value=mock_integrator)
