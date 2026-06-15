"""
单元测试：Session 模块测试

测试范围：
1. MessageRole 枚举
2. Content block 创建
3. ConversationMessage 工厂方法、查询方法、序列化/反序列化
4. Session 序列化/反序列化、消息计数、token 估算
"""

import json
import pytest

from novels_project.session import (
    MessageRole,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock,
    ContentBlock,
    ConversationMessage,
    Session,
)
from novels_project.api_client import TokenUsage


# ==================== MessageRole ====================

class TestMessageRole:
    """测试 MessageRole 枚举值"""

    def test_enum_values(self):
        assert MessageRole.SYSTEM.value == "system"
        assert MessageRole.USER.value == "user"
        assert MessageRole.ASSISTANT.value == "assistant"
        assert MessageRole.TOOL.value == "tool"

    def test_enum_str_inheritance(self):
        assert isinstance(MessageRole.SYSTEM, str)
        assert MessageRole.USER == "user"


# ==================== Content Blocks ====================

class TestContentBlocks:
    """测试 content block 创建"""

    def test_text_block_creation(self):
        block = TextBlock(text="Hello world")
        assert block.text == "Hello world"

    def test_text_block_empty(self):
        block = TextBlock(text="")
        assert block.text == ""

    def test_tool_use_block_creation(self):
        block = ToolUseBlock(id="toolu_01", name="search", input='{"q": "test"}')
        assert block.id == "toolu_01"
        assert block.name == "search"
        assert block.input == '{"q": "test"}'

    def test_tool_result_block_creation(self):
        block = ToolResultBlock(
            tool_use_id="toolu_01",
            tool_name="search",
            output="results here",
            is_error=False,
        )
        assert block.tool_use_id == "toolu_01"
        assert block.tool_name == "search"
        assert block.output == "results here"
        assert block.is_error is False

    def test_tool_result_block_is_error_default(self):
        block = ToolResultBlock(
            tool_use_id="toolu_02",
            tool_name="bad_tool",
            output="error occurred",
        )
        assert block.is_error is False

    def test_tool_result_block_is_error_true(self):
        block = ToolResultBlock(
            tool_use_id="toolu_03",
            tool_name="fail",
            output="something went wrong",
            is_error=True,
        )
        assert block.is_error is True


# ==================== ConversationMessage ====================

class TestConversationMessageFactories:
    """测试 ConversationMessage 工厂方法"""

    def test_user_text_factory(self):
        msg = ConversationMessage.user_text("Hello, can you help?")
        assert msg.role == MessageRole.USER
        assert len(msg.blocks) == 1
        assert isinstance(msg.blocks[0], TextBlock)
        assert msg.blocks[0].text == "Hello, can you help?"

    def test_user_text_factory_empty(self):
        msg = ConversationMessage.user_text("")
        assert msg.role == MessageRole.USER
        assert msg.blocks[0].text == ""

    def test_assistant_factory(self):
        blocks = [TextBlock(text="Sure, here you go.")]
        msg = ConversationMessage.assistant(blocks)
        assert msg.role == MessageRole.ASSISTANT
        assert len(msg.blocks) == 1
        assert isinstance(msg.blocks[0], TextBlock)
        assert msg.usage is None

    def test_assistant_factory_with_usage(self):
        blocks = [TextBlock(text="response")]
        usage = TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150)
        msg = ConversationMessage.assistant(blocks, usage=usage)
        assert msg.role == MessageRole.ASSISTANT
        assert msg.usage == usage
        assert msg.usage.input_tokens == 100
        assert msg.usage.output_tokens == 50
        assert msg.usage.total_tokens == 150

    def test_assistant_factory_multiple_blocks(self):
        blocks = [
            TextBlock(text="Let me search for that."),
            ToolUseBlock(id="tu_1", name="search", input='{"q": "python"}'),
        ]
        msg = ConversationMessage.assistant(blocks)
        assert len(msg.blocks) == 2
        assert isinstance(msg.blocks[0], TextBlock)
        assert isinstance(msg.blocks[1], ToolUseBlock)

    def test_tool_result_factory(self):
        msg = ConversationMessage.tool_result(
            tool_use_id="tu_1",
            tool_name="search",
            output="Found 3 results",
        )
        assert msg.role == MessageRole.TOOL
        assert len(msg.blocks) == 1
        block = msg.blocks[0]
        assert isinstance(block, ToolResultBlock)
        assert block.tool_use_id == "tu_1"
        assert block.tool_name == "search"
        assert block.output == "Found 3 results"
        assert block.is_error is False

    def test_tool_result_factory_error(self):
        msg = ConversationMessage.tool_result(
            tool_use_id="tu_2",
            tool_name="bad_search",
            output="Timeout",
            is_error=True,
        )
        assert msg.role == MessageRole.TOOL
        block = msg.blocks[0]
        assert isinstance(block, ToolResultBlock)
        assert block.is_error is True
        assert block.output == "Timeout"


class TestConversationMessageQueries:
    """测试 ConversationMessage 查询方法"""

    def test_get_text_single_block(self):
        msg = ConversationMessage.user_text("Hello world")
        assert msg.get_text() == "Hello world"

    def test_get_text_multiple_text_blocks(self):
        msg = ConversationMessage(
            role=MessageRole.ASSISTANT,
            blocks=[
                TextBlock(text="Part one."),
                TextBlock(text="Part two."),
            ],
        )
        assert msg.get_text() == "Part one.\nPart two."

    def test_get_text_mixed_blocks(self):
        msg = ConversationMessage(
            role=MessageRole.ASSISTANT,
            blocks=[
                TextBlock(text="I'll search."),
                ToolUseBlock(id="tu_1", name="search", input='{"q":"test"}'),
                ToolResultBlock(tool_use_id="tu_1", tool_name="search", output="results"),
                TextBlock(text="Found results."),
            ],
        )
        text = msg.get_text()
        assert "I'll search." in text
        assert "Found results." in text
        # Tool blocks should not appear in text
        assert "ToolUseBlock" not in text

    def test_get_text_no_text_blocks(self):
        msg = ConversationMessage(
            role=MessageRole.TOOL,
            blocks=[ToolResultBlock(tool_use_id="tu_1", tool_name="search", output="data")],
        )
        assert msg.get_text() == ""

    def test_get_tool_uses_empty(self):
        msg = ConversationMessage.user_text("Just text")
        assert msg.get_tool_uses() == []

    def test_get_tool_uses_multiple(self):
        tool1 = ToolUseBlock(id="tu_1", name="search", input='{"q":"a"}')
        tool2 = ToolUseBlock(id="tu_2", name="calc", input='{"expr":"1+1"}')
        msg = ConversationMessage(
            role=MessageRole.ASSISTANT,
            blocks=[
                TextBlock(text="Let me search and calc."),
                tool1,
                tool2,
            ],
        )
        tool_uses = msg.get_tool_uses()
        assert len(tool_uses) == 2
        assert tool_uses[0] == tool1
        assert tool_uses[1] == tool2

    def test_get_tool_uses_filters_tool_results(self):
        tool_use = ToolUseBlock(id="tu_1", name="search", input='{"q":"x"}')
        tool_result = ToolResultBlock(tool_use_id="tu_1", tool_name="search", output="data")
        msg = ConversationMessage(
            role=MessageRole.ASSISTANT,
            blocks=[tool_use, tool_result],
        )
        uses = msg.get_tool_uses()
        assert len(uses) == 1
        assert isinstance(uses[0], ToolUseBlock)


class TestConversationMessageSerialization:
    """测试 ConversationMessage to_dict / from_dict"""

    def test_to_dict_user_text(self):
        msg = ConversationMessage.user_text("Hello")
        d = msg.to_dict()
        assert d["role"] == "user"
        assert d["blocks"] == [{"type": "text", "text": "Hello"}]
        assert "usage" not in d

    def test_to_dict_assistant_with_tool_use(self):
        msg = ConversationMessage(
            role=MessageRole.ASSISTANT,
            blocks=[
                TextBlock(text="Searching..."),
                ToolUseBlock(id="tu_01", name="web_search", input='{"q":"test"}'),
            ],
        )
        d = msg.to_dict()
        assert d["role"] == "assistant"
        assert d["blocks"] == [
            {"type": "text", "text": "Searching..."},
            {"type": "tool_use", "id": "tu_01", "name": "web_search", "input": '{"q":"test"}'},
        ]

    def test_to_dict_tool_result(self):
        msg = ConversationMessage.tool_result(
            tool_use_id="tu_01",
            tool_name="web_search",
            output="3 results found",
            is_error=False,
        )
        d = msg.to_dict()
        assert d["role"] == "tool"
        assert d["blocks"] == [
            {
                "type": "tool_result",
                "tool_use_id": "tu_01",
                "tool_name": "web_search",
                "output": "3 results found",
                "is_error": False,
            }
        ]

    def test_to_dict_tool_result_error(self):
        msg = ConversationMessage.tool_result(
            tool_use_id="tu_x",
            tool_name="fail",
            output="error",
            is_error=True,
        )
        d = msg.to_dict()
        assert d["blocks"][0]["is_error"] is True

    def test_to_dict_with_usage(self):
        msg = ConversationMessage.assistant(
            [TextBlock(text="Done.")],
            usage=TokenUsage(input_tokens=10, output_tokens=20, total_tokens=30),
        )
        d = msg.to_dict()
        assert "usage" in d
        assert d["usage"] == {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30}

    def test_to_dict_all_block_types(self):
        msg = ConversationMessage(
            role=MessageRole.ASSISTANT,
            blocks=[
                TextBlock(text="Let me check."),
                ToolUseBlock(id="tu_a", name="tool_a", input='{"x":1}'),
                ToolResultBlock(tool_use_id="tu_a", tool_name="tool_a", output="ok"),
            ],
        )
        d = msg.to_dict()
        types = [b["type"] for b in d["blocks"]]
        assert types == ["text", "tool_use", "tool_result"]

    def test_to_dict_unknown_block_skipped(self):
        """Blocks that are not TextBlock, ToolUseBlock, or ToolResultBlock are skipped."""
        class CustomBlock(ContentBlock):
            pass

        msg = ConversationMessage(
            role=MessageRole.USER,
            blocks=[CustomBlock(), TextBlock(text="Hello")],
        )
        d = msg.to_dict()
        assert len(d["blocks"]) == 1
        assert d["blocks"][0]["type"] == "text"

    # === from_dict ===

    def test_from_dict_user_text(self):
        data = {"role": "user", "blocks": [{"type": "text", "text": "Hello"}]}
        msg = ConversationMessage.from_dict(data)
        assert msg.role == MessageRole.USER
        assert len(msg.blocks) == 1
        assert isinstance(msg.blocks[0], TextBlock)
        assert msg.blocks[0].text == "Hello"

    def test_from_dict_assistant_with_tool_use(self):
        data = {
            "role": "assistant",
            "blocks": [
                {"type": "text", "text": "Searching..."},
                {"type": "tool_use", "id": "tu_01", "name": "web_search", "input": '{"q":"test"}'},
            ],
        }
        msg = ConversationMessage.from_dict(data)
        assert msg.role == MessageRole.ASSISTANT
        assert len(msg.blocks) == 2
        assert isinstance(msg.blocks[0], TextBlock)
        assert isinstance(msg.blocks[1], ToolUseBlock)
        assert msg.blocks[1].id == "tu_01"
        assert msg.blocks[1].name == "web_search"

    def test_from_dict_tool_result(self):
        data = {
            "role": "tool",
            "blocks": [
                {
                    "type": "tool_result",
                    "tool_use_id": "tu_01",
                    "tool_name": "search",
                    "output": "results",
                    "is_error": False,
                }
            ],
        }
        msg = ConversationMessage.from_dict(data)
        assert msg.role == MessageRole.TOOL
        block = msg.blocks[0]
        assert isinstance(block, ToolResultBlock)
        assert block.tool_use_id == "tu_01"
        assert block.tool_name == "search"
        assert block.output == "results"
        assert block.is_error is False

    def test_from_dict_tool_result_default_is_error(self):
        data = {
            "role": "tool",
            "blocks": [
                {
                    "type": "tool_result",
                    "tool_use_id": "tu_x",
                    "tool_name": "x",
                    "output": "ok",
                }
            ],
        }
        msg = ConversationMessage.from_dict(data)
        assert msg.blocks[0].is_error is False

    def test_from_dict_with_usage(self):
        data = {
            "role": "assistant",
            "blocks": [{"type": "text", "text": "Done."}],
            "usage": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
        }
        msg = ConversationMessage.from_dict(data)
        assert msg.usage is not None
        assert msg.usage.input_tokens == 100
        assert msg.usage.output_tokens == 50
        assert msg.usage.total_tokens == 150

    def test_from_dict_usage_defaults(self):
        data = {
            "role": "assistant",
            "blocks": [{"type": "text", "text": "x"}],
            "usage": {},
        }
        msg = ConversationMessage.from_dict(data)
        assert msg.usage.input_tokens == 0
        assert msg.usage.output_tokens == 0
        assert msg.usage.total_tokens == 0

    def test_from_dict_empty_blocks(self):
        data = {"role": "user", "blocks": []}
        msg = ConversationMessage.from_dict(data)
        assert msg.role == MessageRole.USER
        assert msg.blocks == []

    def test_from_dict_no_blocks(self):
        data = {"role": "system"}
        msg = ConversationMessage.from_dict(data)
        assert msg.role == MessageRole.SYSTEM
        assert msg.blocks == []

    def test_from_dict_unknown_block_type(self):
        """Blocks with unknown type are skipped."""
        data = {
            "role": "user",
            "blocks": [
                {"type": "unknown_type", "data": "some"},
                {"type": "text", "text": "Hello"},
            ],
        }
        msg = ConversationMessage.from_dict(data)
        assert len(msg.blocks) == 1
        assert isinstance(msg.blocks[0], TextBlock)
        assert msg.blocks[0].text == "Hello"

    def test_roundtrip_user_text(self):
        original = ConversationMessage.user_text("Hello world")
        data = original.to_dict()
        restored = ConversationMessage.from_dict(data)
        assert restored.role == original.role
        assert restored.get_text() == original.get_text()

    def test_roundtrip_all_block_types(self):
        original = ConversationMessage(
            role=MessageRole.ASSISTANT,
            blocks=[
                TextBlock(text="Let me check."),
                ToolUseBlock(id="tu_a", name="tool_a", input='{"x": 1}'),
                ToolResultBlock(tool_use_id="tu_a", tool_name="tool_a", output="ok", is_error=False),
            ],
        )
        restored = ConversationMessage.from_dict(original.to_dict())
        assert restored.role == original.role
        assert len(restored.blocks) == 3
        assert isinstance(restored.blocks[0], TextBlock)
        assert isinstance(restored.blocks[1], ToolUseBlock)
        assert isinstance(restored.blocks[2], ToolResultBlock)
        assert restored.blocks[0].text == "Let me check."
        assert restored.blocks[1].id == "tu_a"
        assert restored.blocks[2].output == "ok"

    def test_roundtrip_with_usage(self):
        usage = TokenUsage(input_tokens=42, output_tokens=99, total_tokens=141)
        original = ConversationMessage.assistant(
            [TextBlock(text="Done"), ToolUseBlock(id="t1", name="n", input="{}")],
            usage=usage,
        )
        restored = ConversationMessage.from_dict(original.to_dict())
        assert restored.usage.input_tokens == 42
        assert restored.usage.output_tokens == 99
        assert restored.usage.total_tokens == 141
        assert restored.get_tool_uses()[0].id == "t1"

    def test_roundtrip_tool_result_error(self):
        original = ConversationMessage.tool_result("tu_e", "bad", "fail", is_error=True)
        restored = ConversationMessage.from_dict(original.to_dict())
        assert restored.blocks[0].is_error is True

    def test_roundtrip_system_message(self):
        original = ConversationMessage(
            role=MessageRole.SYSTEM,
            blocks=[TextBlock(text="System prompt here.")],
        )
        restored = ConversationMessage.from_dict(original.to_dict())
        assert restored.role == MessageRole.SYSTEM
        assert restored.get_text() == "System prompt here."


# ==================== Session ====================

class TestSessionBasics:
    """测试 Session 基础功能"""

    def test_default_session(self):
        session = Session()
        assert session.version == 1
        assert session.messages == []
        assert session.message_count() == 0

    def test_session_with_messages(self):
        msg = ConversationMessage.user_text("Hello")
        session = Session(messages=[msg])
        assert session.message_count() == 1
        assert session.messages[0] == msg

    def test_empty_to_json(self):
        session = Session()
        json_str = session.to_json()
        data = json.loads(json_str)
        assert data["version"] == 1
        assert data["messages"] == []

    def test_empty_to_dict(self):
        session = Session()
        d = session.to_dict()
        assert d == {"version": 1, "messages": []}

    def test_empty_from_json(self):
        session = Session.from_json('{"version": 1, "messages": []}')
        assert session.version == 1
        assert session.messages == []

    def test_empty_from_dict(self):
        session = Session.from_dict({"version": 1, "messages": []})
        assert session.version == 1
        assert session.messages == []

    def test_from_json_with_messages(self):
        json_str = json.dumps({
            "version": 1,
            "messages": [
                {"role": "user", "blocks": [{"type": "text", "text": "Hi"}]},
                {"role": "assistant", "blocks": [{"type": "text", "text": "Hello!"}]},
            ],
        })
        session = Session.from_json(json_str)
        assert session.message_count() == 2
        assert session.messages[0].role == MessageRole.USER
        assert session.messages[0].get_text() == "Hi"
        assert session.messages[1].role == MessageRole.ASSISTANT
        assert session.messages[1].get_text() == "Hello!"

    def test_from_dict_default_version(self):
        session = Session.from_dict({})
        assert session.version == 1

    def test_from_dict_default_messages(self):
        session = Session.from_dict({"version": 1})
        assert session.messages == []

    def test_from_json_default_version(self):
        session = Session.from_json("{}")
        assert session.version == 1
        assert session.messages == []

    def test_version_preserved(self):
        session = Session(version=3, messages=[ConversationMessage.user_text("H")])
        d = session.to_dict()
        assert d["version"] == 3
        restored = Session.from_dict(d)
        assert restored.version == 3

    def test_from_dict_zero_messages(self):
        session = Session.from_dict({"version": 2, "messages": []})
        assert session.message_count() == 0

    def test_roundtrip_empty(self):
        session = Session(version=2)
        restored = Session.from_json(session.to_json())
        assert restored.version == 2
        assert restored.message_count() == 0

    def test_roundtrip_with_all_message_types(self):
        session = Session(version=1, messages=[
            ConversationMessage(
                role=MessageRole.SYSTEM,
                blocks=[TextBlock(text="You are a helpful assistant.")],
            ),
            ConversationMessage.user_text("Search for Python."),
            ConversationMessage(
                role=MessageRole.ASSISTANT,
                blocks=[
                    TextBlock(text="Let me search."),
                    ToolUseBlock(id="tu_1", name="search", input='{"q": "Python"}'),
                ],
                usage=TokenUsage(10, 5, 15),
            ),
            ConversationMessage.tool_result("tu_1", "search", "Python is a language"),
            ConversationMessage.assistant(
                [TextBlock(text="Python is great.")],
                usage=TokenUsage(5, 10, 15),
            ),
        ])
        restored = Session.from_json(session.to_json())
        assert restored.message_count() == 5
        assert restored.messages[0].role == MessageRole.SYSTEM
        assert restored.messages[1].role == MessageRole.USER
        assert restored.messages[2].role == MessageRole.ASSISTANT
        assert restored.messages[3].role == MessageRole.TOOL
        assert restored.messages[4].role == MessageRole.ASSISTANT
        # Check tool use survived
        tool_uses = restored.messages[2].get_tool_uses()
        assert len(tool_uses) == 1
        assert tool_uses[0].name == "search"
        # Check usage survived
        assert restored.messages[2].usage.input_tokens == 10
        assert restored.messages[4].usage.output_tokens == 10

    def test_roundtrip_to_json_to_from_json(self):
        session = Session(messages=[ConversationMessage.user_text("Hello world")])
        json_str = session.to_json()
        assert isinstance(json_str, str)
        restored = Session.from_json(json_str)
        assert restored.message_count() == 1
        assert restored.messages[0].get_text() == "Hello world"


class TestSessionTokenEstimation:
    """测试 Session total_estimated_tokens"""

    def test_no_messages(self):
        session = Session()
        assert session.total_estimated_tokens() == 0

    def test_text_block_only(self):
        session = Session(messages=[
            ConversationMessage.user_text("Hello world"),  # 11 chars -> 11//4 = 2
            ConversationMessage.assistant([TextBlock(text="Hi there friend")]),  # 15 chars -> 15//4 = 3
        ])
        # 11//4 = 2, 15//4 = 3 => 5
        assert session.total_estimated_tokens() == 5

    def test_tool_use_block(self):
        session = Session(messages=[
            ConversationMessage(
                role=MessageRole.ASSISTANT,
                blocks=[ToolUseBlock(id="t1", name="search", input='{"query":"test"}')],  # 16 chars -> 4
            ),
        ])
        assert session.total_estimated_tokens() == 16 // 4

    def test_tool_result_block(self):
        session = Session(messages=[
            ConversationMessage.tool_result("t1", "search", "results found"),  # 13 chars -> 3
        ])
        assert session.total_estimated_tokens() == 13 // 4

    def test_mixed_blocks_message(self):
        session = Session(messages=[
            ConversationMessage(
                role=MessageRole.ASSISTANT,
                blocks=[
                    TextBlock(text="Let me search."),  # 13 -> 3
                    ToolUseBlock(id="t1", name="s", input='{"q":"x"}'),  # 9 -> 2
                ],
            ),
        ])
        assert session.total_estimated_tokens() == 5

    def test_multiple_messages_various_blocks(self):
        session = Session(messages=[
            ConversationMessage.user_text("A" * 40),          # 40//4 = 10
            ConversationMessage.assistant([TextBlock(text="B" * 20)]),  # 20//4 = 5
            ConversationMessage(
                role=MessageRole.ASSISTANT,
                blocks=[ToolUseBlock(id="t1", name="tool", input="C" * 16)],  # 16//4 = 4
            ),
            ConversationMessage.tool_result("t1", "tool", "D" * 32),  # 32//4 = 8
        ])
        assert session.total_estimated_tokens() == 10 + 5 + 4 + 8

    def test_very_short_text(self):
        """Text shorter than 4 characters should yield 0"""
        session = Session(messages=[
            ConversationMessage.user_text("abc"),  # 3//4 = 0
            ConversationMessage(
                role=MessageRole.ASSISTANT,
                blocks=[ToolUseBlock(id="t1", name="s", input="x")],  # 1//4 = 0
            ),
            ConversationMessage.tool_result("t1", "s", "ok"),  # 2//4 = 0
        ])
        assert session.total_estimated_tokens() == 0

    def test_unknown_block_skipped(self):
        """Blocks that are not TextBlock, ToolUseBlock, or ToolResultBlock are skipped."""
        class CustomBlock(ContentBlock):
            pass

        session = Session(messages=[
            ConversationMessage(
                role=MessageRole.USER,
                blocks=[CustomBlock(), TextBlock(text="ABCD")],  # 4//4 = 1
            ),
        ])
        assert session.total_estimated_tokens() == 1


class TestConversationMessageEdgeCases:
    """测试 ConversationMessage 边缘情况"""

    def test_unicode_text(self):
        msg = ConversationMessage.user_text("你好世界！🌍")
        d = msg.to_dict()
        restored = ConversationMessage.from_dict(d)
        assert restored.get_text() == "你好世界！🌍"

    def test_long_tool_input(self):
        long_input = '{"data": "' + "x" * 1000 + '"}'
        block = ToolUseBlock(id="t1", name="big", input=long_input)
        msg = ConversationMessage(role=MessageRole.ASSISTANT, blocks=[block])
        restored = ConversationMessage.from_dict(msg.to_dict())
        assert restored.blocks[0].input == long_input

    def test_tool_result_with_special_chars(self):
        msg = ConversationMessage.tool_result("t1", "tool", "line1\nline2\nline3")
        d = msg.to_dict()
        restored = ConversationMessage.from_dict(d)
        assert restored.blocks[0].output == "line1\nline2\nline3"

    def test_message_with_none_usage(self):
        msg = ConversationMessage(
            role=MessageRole.ASSISTANT,
            blocks=[TextBlock(text="ok")],
            usage=None,
        )
        d = msg.to_dict()
        assert "usage" not in d
        restored = ConversationMessage.from_dict(d)
        assert restored.usage is None