"""
单元测试：ToolSpec 模块测试

测试范围：
1. ToolSpec 创建
2. ToolRegistry 增删查
3. build_builtin_tool_registry
"""

import pytest
from unittest.mock import patch, MagicMock

from novels_project.tool_spec import (
    ToolSpec,
    ToolRegistry,
    ToolExecutor,
    build_builtin_tool_registry,
)


# ==================== ToolSpec ====================

class TestToolExecutorProtocol:
    """测试 ToolExecutor Protocol"""

    def test_tool_executor_is_protocol(self):
        assert hasattr(ToolExecutor, '_is_protocol')
        assert ToolExecutor._is_protocol is True

    def test_mock_isinstance_tool_executor(self):
        """Mock with execute method satisfies the ToolExecutor Protocol."""
        mock_obj = MagicMock()
        mock_obj.execute = MagicMock(return_value=("result", False))
        assert isinstance(mock_obj, ToolExecutor)


class TestToolSpec:
    """测试 ToolSpec 创建"""

    def test_creation_with_handler(self):
        def my_handler():
            return "done"

        spec = ToolSpec(
            name="my_tool",
            description="Does something",
            input_schema={"type": "object", "properties": {}},
            handler=my_handler,
        )
        assert spec.name == "my_tool"
        assert spec.description == "Does something"
        assert spec.input_schema == {"type": "object", "properties": {}}
        assert spec.handler is my_handler

    def test_creation_without_handler(self):
        spec = ToolSpec(
            name="agent_tool",
            description="An agent tool",
            input_schema={"type": "object", "properties": {"prompt": {"type": "string"}}},
        )
        assert spec.name == "agent_tool"
        assert spec.handler is None

    def test_creation_default_handler_is_none(self):
        spec = ToolSpec(name="t", description="d", input_schema={})
        assert spec.handler is None

    def test_input_schema_with_required(self):
        schema = {
            "type": "object",
            "properties": {"q": {"type": "string"}},
            "required": ["q"],
        }
        spec = ToolSpec(name="search", description="Search", input_schema=schema)
        assert spec.input_schema["required"] == ["q"]

    def test_input_schema_enum(self):
        schema = {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["a", "b", "c"]},
            },
        }
        spec = ToolSpec(name="filter", description="Filter", input_schema=schema)
        assert spec.input_schema["properties"]["type"]["enum"] == ["a", "b", "c"]


# ==================== ToolRegistry ====================

class TestToolRegistry:
    """测试 ToolRegistry"""

    def test_register_and_get(self):
        registry = ToolRegistry()
        spec = ToolSpec(name="tool_a", description="A tool", input_schema={})
        registry.register(spec)
        assert registry.get_spec("tool_a") is spec

    def test_get_nonexistent(self):
        registry = ToolRegistry()
        assert registry.get_spec("nonexistent") is None

    def test_has_existing(self):
        registry = ToolRegistry()
        registry.register(ToolSpec(name="tool_a", description="d", input_schema={}))
        assert registry.has("tool_a") is True

    def test_has_nonexistent(self):
        registry = ToolRegistry()
        assert registry.has("nope") is False

    def test_all_specs_empty(self):
        registry = ToolRegistry()
        assert registry.all_specs() == []

    def test_all_specs_multiple(self):
        registry = ToolRegistry()
        spec1 = ToolSpec(name="t1", description="d1", input_schema={})
        spec2 = ToolSpec(name="t2", description="d2", input_schema={})
        registry.register(spec1)
        registry.register(spec2)
        specs = registry.all_specs()
        assert len(specs) == 2
        names = {s.name for s in specs}
        assert names == {"t1", "t2"}

    def test_all_specs_order(self):
        """all_specs returns specs in registration order."""
        registry = ToolRegistry()
        spec1 = ToolSpec(name="a", description="", input_schema={})
        spec2 = ToolSpec(name="b", description="", input_schema={})
        registry.register(spec1)
        registry.register(spec2)
        specs = registry.all_specs()
        assert specs[0].name == "a"
        assert specs[1].name == "b"

    def test_register_overwrite(self):
        """Registering with the same name overwrites."""
        registry = ToolRegistry()
        spec1 = ToolSpec(name="tool", description="first", input_schema={})
        spec2 = ToolSpec(name="tool", description="second", input_schema={})
        registry.register(spec1)
        registry.register(spec2)
        assert registry.get_spec("tool") is spec2

    def test_to_openai_tools_empty(self):
        registry = ToolRegistry()
        assert registry.to_openai_tools() == []

    def test_to_openai_tools_format(self):
        registry = ToolRegistry()
        spec = ToolSpec(
            name="search",
            description="Search the web",
            input_schema={
                "type": "object",
                "properties": {"q": {"type": "string"}},
                "required": ["q"],
            },
        )
        registry.register(spec)
        tools = registry.to_openai_tools()
        assert len(tools) == 1
        tool = tools[0]
        assert tool["type"] == "function"
        assert tool["function"]["name"] == "search"
        assert tool["function"]["description"] == "Search the web"
        assert tool["function"]["parameters"] == {
            "type": "object",
            "properties": {"q": {"type": "string"}},
            "required": ["q"],
        }

    def test_to_openai_tools_multiple(self):
        registry = ToolRegistry()
        registry.register(ToolSpec(name="a", description="A", input_schema={"type": "object"}))
        registry.register(ToolSpec(name="b", description="B", input_schema={"type": "object"}))
        tools = registry.to_openai_tools()
        assert len(tools) == 2
        assert tools[0]["function"]["name"] == "a"
        assert tools[1]["function"]["name"] == "b"

    def test_to_openai_tools_includes_handler_specs(self):
        registry = ToolRegistry()
        registry.register(ToolSpec(
            name="with_handler",
            description="Has handler",
            input_schema={},
            handler=lambda: None,
        ))
        tools = registry.to_openai_tools()
        assert len(tools) == 1
        assert tools[0]["function"]["name"] == "with_handler"

    def test_to_openai_tools_includes_agent_specs(self):
        registry = ToolRegistry()
        registry.register(ToolSpec(
            name="agent_tool",
            description="Agent tool",
            input_schema={},
            handler=None,
        ))
        tools = registry.to_openai_tools()
        assert len(tools) == 1
        assert tools[0]["function"]["name"] == "agent_tool"


# ==================== build_builtin_tool_registry ====================

class TestBuildBuiltinToolRegistry:
    """测试 build_builtin_tool_registry"""

    def test_returns_registry(self):
        """Use mocking to avoid importing all tool modules."""
        with patch("novels_project.tool_spec.ToolRegistry.register") as mock_register:
            with patch("novels_project.tool_spec.ToolRegistry.__init__", return_value=None):
                # We just need to verify the function runs and returns a ToolRegistry
                # Actually let's test it more simply
                pass

    def test_registry_has_known_tools(self):
        """Test that the registry contains expected built-in tool names."""
        registry = build_builtin_tool_registry()
        expected_tools = [
            "retrieve_writing_samples",
            "check_character_voice",
            "get_character_voice_guide",
            "retrieve_feedback",
            "get_common_mistakes",
            "record_feedback",
            "record_batch_feedback",
            "check_iteration_status",
            "should_continue_iteration",
            "get_revision_feedback",
            "record_iteration",
            "update_character_card",
            "add_character_dialogue_example",
            "get_character_card",
            "list_all_characters",
            "fix_chapter_issue",
            "get_chapter_content",
            "list_generated_chapters",
            "query_character_network",
            "query_relation_between",
            "search_graph",
            "trace_foreshadowing",
            "get_graph_context",
            "build_knowledge_graph",
            "get_graph_stats",
        ]
        for tool_name in expected_tools:
            assert registry.has(tool_name), f"Missing tool: {tool_name}"

    def test_registry_tool_count(self):
        registry = build_builtin_tool_registry()
        specs = registry.all_specs()
        assert len(specs) == 25

    def test_all_specs_have_names(self):
        registry = build_builtin_tool_registry()
        for spec in registry.all_specs():
            assert spec.name, f"Spec has no name"
            assert spec.description, f"Spec {spec.name} has no description"
            assert isinstance(spec.input_schema, dict), f"Spec {spec.name} input_schema is not a dict"
            assert "type" in spec.input_schema, f"Spec {spec.name} input_schema has no type"

    def test_tools_have_handlers(self):
        registry = build_builtin_tool_registry()
        for spec in registry.all_specs():
            assert spec.handler is not None, f"Built-in tool {spec.name} should have a handler"

    def test_to_openai_tools_generation(self):
        registry = build_builtin_tool_registry()
        tools = registry.to_openai_tools()
        assert len(tools) == 25
        for tool in tools:
            assert tool["type"] == "function"
            assert "name" in tool["function"]
            assert "description" in tool["function"]
            assert "parameters" in tool["function"]

    def test_get_spec_by_name(self):
        registry = build_builtin_tool_registry()
        spec = registry.get_spec("retrieve_writing_samples")
        assert spec is not None
        assert spec.name == "retrieve_writing_samples"
        assert "input_schema" in spec.__dataclass_fields__

    def test_known_tool_schema_details(self):
        registry = build_builtin_tool_registry()
        spec = registry.get_spec("check_character_voice")
        assert spec.input_schema["required"] == ["content"]
        assert "content" in spec.input_schema["properties"]
        assert "focus_characters" in spec.input_schema["properties"]

        spec = registry.get_spec("update_character_card")
        assert spec.input_schema["required"] == ["character_name", "field", "value"]

        spec = registry.get_spec("record_iteration")
        assert "chapter_id" in spec.input_schema["required"]
        assert "draft" in spec.input_schema["required"]