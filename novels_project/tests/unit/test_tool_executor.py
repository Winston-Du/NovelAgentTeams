"""
单元测试：ToolExecutor 模块测试

测试范围：
1. MainToolExecutor.execute
2. SubAgentToolExecutor.execute
"""

import pytest
from unittest.mock import MagicMock

from novels_project.tool_executor import MainToolExecutor, SubAgentToolExecutor
from novels_project.tool_spec import ToolSpec, ToolRegistry


# ==================== Helpers ====================

def _make_mock_agent_runner(is_agent_tool=False, run_agent_return="agent result"):
    """Create a mock AgentRunner."""
    runner = MagicMock()
    runner.is_agent_tool.return_value = is_agent_tool
    runner.run_agent.return_value = run_agent_return
    return runner


def _make_registry_with_tool(name="test_tool", handler=None):
    """Create a ToolRegistry with a single tool."""
    registry = ToolRegistry()
    if handler is None:
        handler = lambda **kwargs: "handler result"
    spec = ToolSpec(
        name=name,
        description=f"Tool: {name}",
        input_schema={"type": "object", "properties": {}},
        handler=handler,
    )
    registry.register(spec)
    return registry


# ==================== MainToolExecutor ====================

class TestMainToolExecutor:
    """测试 MainToolExecutor"""

    # --- Agent tool ---

    def test_agent_tool_success(self):
        runner = _make_mock_agent_runner(is_agent_tool=True, run_agent_return="Agent output text")
        registry = ToolRegistry()
        executor = MainToolExecutor(registry, runner)
        output, is_error = executor.execute("chief_editor", '{"prompt": "Write"}')
        assert is_error is False
        assert output == "Agent output text"
        runner.run_agent.assert_called_once_with("chief_editor", '{"prompt": "Write"}')

    def test_agent_tool_failure(self):
        runner = _make_mock_agent_runner(is_agent_tool=True)
        runner.run_agent.side_effect = RuntimeError("Agent crashed")
        registry = ToolRegistry()
        executor = MainToolExecutor(registry, runner)
        output, is_error = executor.execute("plot_writer", '{"prompt": "Write"}')
        assert is_error is True
        assert "Sub-agent execution failed" in output
        assert "Agent crashed" in output

    # --- Built-in tool ---

    def test_builtin_tool_success(self):
        registry = _make_registry_with_tool("search")
        runner = _make_mock_agent_runner(is_agent_tool=False)
        executor = MainToolExecutor(registry, runner)
        output, is_error = executor.execute("search", '{"q": "python"}')
        assert is_error is False
        assert output == "handler result"

    def test_builtin_tool_empty_input(self):
        registry = _make_registry_with_tool("search", handler=lambda **kwargs: str(kwargs))
        runner = _make_mock_agent_runner(is_agent_tool=False)
        executor = MainToolExecutor(registry, runner)
        output, is_error = executor.execute("search", "")
        assert is_error is False
        assert output == "{}"

    def test_builtin_tool_empty_string_input(self):
        registry = _make_registry_with_tool("search", handler=lambda **kwargs: str(kwargs))
        runner = _make_mock_agent_runner(is_agent_tool=False)
        executor = MainToolExecutor(registry, runner)
        output, is_error = executor.execute("search", "")
        assert is_error is False

    # --- Unknown tool ---

    def test_unknown_tool(self):
        runner = _make_mock_agent_runner(is_agent_tool=False)
        registry = ToolRegistry()
        executor = MainToolExecutor(registry, runner)
        output, is_error = executor.execute("nonexistent", '{"x": 1}')
        assert is_error is True
        assert "Unknown tool" in output
        assert "nonexistent" in output

    # --- Tool without handler ---

    def test_tool_without_handler(self):
        registry = _make_registry_with_tool("no_handler_tool", handler=None)
        # Override the handler to None
        spec = registry.get_spec("no_handler_tool")
        # Actually let's just register one without handler
        registry2 = ToolRegistry()
        registry2.register(ToolSpec(name="no_handler", description="d", input_schema={}, handler=None))
        runner = _make_mock_agent_runner(is_agent_tool=False)
        executor = MainToolExecutor(registry2, runner)
        output, is_error = executor.execute("no_handler", '{"x": 1}')
        assert is_error is True
        assert "has no handler" in output

    # --- Tool execution error ---

    def test_tool_execution_error(self):
        def failing_handler(**kwargs):
            raise ValueError("Something went wrong")

        registry = _make_registry_with_tool("bad_tool", handler=failing_handler)
        runner = _make_mock_agent_runner(is_agent_tool=False)
        executor = MainToolExecutor(registry, runner)
        output, is_error = executor.execute("bad_tool", '{"x": 1}')
        assert is_error is True
        assert "Tool execution error" in output
        assert "Something went wrong" in output

    def test_tool_invalid_json_input(self):
        registry = _make_registry_with_tool("search")
        runner = _make_mock_agent_runner(is_agent_tool=False)
        executor = MainToolExecutor(registry, runner)
        output, is_error = executor.execute("search", "not valid json")
        assert is_error is True
        assert "Tool execution error" in output

    def test_tool_with_positional_args(self):
        """Handler receives kwargs from parsed JSON."""
        captured_kwargs = {}

        def capture_handler(**kwargs):
            captured_kwargs.update(kwargs)
            return "ok"

        registry = _make_registry_with_tool("capture", handler=capture_handler)
        runner = _make_mock_agent_runner(is_agent_tool=False)
        executor = MainToolExecutor(registry, runner)
        output, is_error = executor.execute("capture", '{"a": 1, "b": "hello"}')
        assert is_error is False
        assert captured_kwargs == {"a": 1, "b": "hello"}


# ==================== SubAgentToolExecutor ====================

class TestSubAgentToolExecutor:
    """测试 SubAgentToolExecutor"""

    def test_allowed_tool_success(self):
        registry = _make_registry_with_tool("search")
        executor = SubAgentToolExecutor(registry, allowed_tools={"search", "get_weather"})
        output, is_error = executor.execute("search", '{"q": "python"}')
        assert is_error is False
        assert output == "handler result"

    def test_allowed_tool_empty_input(self):
        registry = _make_registry_with_tool("search", handler=lambda **kwargs: str(kwargs))
        executor = SubAgentToolExecutor(registry, allowed_tools={"search"})
        output, is_error = executor.execute("search", "")
        assert is_error is False
        assert output == "{}"

    # --- Not allowed tool ---

    def test_not_allowed_tool(self):
        registry = _make_registry_with_tool("secret_tool")
        executor = SubAgentToolExecutor(registry, allowed_tools={"search"})
        output, is_error = executor.execute("secret_tool", '{}')
        assert is_error is True
        assert "not available" in output
        assert "secret_tool" in output

    def test_empty_allowed_set(self):
        registry = _make_registry_with_tool("search")
        executor = SubAgentToolExecutor(registry, allowed_tools=set())
        output, is_error = executor.execute("search", '{}')
        assert is_error is True
        assert "not available" in output

    # --- Unknown tool in allowed set ---

    def test_allowed_but_unknown_tool(self):
        """Tool name is in allowed set but not in registry."""
        registry = ToolRegistry()
        executor = SubAgentToolExecutor(registry, allowed_tools={"search"})
        output, is_error = executor.execute("search", '{}')
        assert is_error is True
        assert "Unknown tool" in output

    # --- Tool without handler ---

    def test_tool_without_handler(self):
        registry = ToolRegistry()
        registry.register(ToolSpec(name="no_handler", description="d", input_schema={}, handler=None))
        executor = SubAgentToolExecutor(registry, allowed_tools={"no_handler"})
        output, is_error = executor.execute("no_handler", '{}')
        assert is_error is True
        assert "has no handler" in output

    # --- Tool execution error ---

    def test_tool_execution_error(self):
        def failing_handler(**kwargs):
            raise RuntimeError("Boom!")

        registry = _make_registry_with_tool("explode", handler=failing_handler)
        executor = SubAgentToolExecutor(registry, allowed_tools={"explode"})
        output, is_error = executor.execute("explode", '{}')
        assert is_error is True
        assert "Tool execution error" in output
        assert "Boom!" in output

    def test_tool_invalid_json_input(self):
        registry = _make_registry_with_tool("search")
        executor = SubAgentToolExecutor(registry, allowed_tools={"search"})
        output, is_error = executor.execute("search", "{invalid json")
        assert is_error is True
        assert "Tool execution error" in output

    def test_allowed_tool_kwargs_passthrough(self):
        captured = {}

        def cap(**kwargs):
            captured.update(kwargs)
            return "done"

        registry = _make_registry_with_tool("cap", handler=cap)
        executor = SubAgentToolExecutor(registry, allowed_tools={"cap"})
        output, is_error = executor.execute("cap", '{"x": 42, "y": "z"}')
        assert is_error is False
        assert captured == {"x": 42, "y": "z"}

    def test_multiple_allowed_tools(self):
        registry = ToolRegistry()
        registry.register(ToolSpec(name="a", description="A", input_schema={}, handler=lambda **k: "A_result"))
        registry.register(ToolSpec(name="b", description="B", input_schema={}, handler=lambda **k: "B_result"))
        executor = SubAgentToolExecutor(registry, allowed_tools={"a", "b"})
        out1, err1 = executor.execute("a", "{}")
        out2, err2 = executor.execute("b", "{}")
        assert out1 == "A_result"
        assert out2 == "B_result"
        assert err1 is False
        assert err2 is False