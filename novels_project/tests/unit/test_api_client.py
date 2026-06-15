"""
单元测试：api_client 模块测试

测试范围：
1. TokenUsage: __init__, __add__
2. AssistantEvent 子类: TextDelta, ToolUseEvent, UsageEvent, MessageStop
3. ApiRequest 创建
4. OpenAICompatibleClient.__init__
5. _convert_message: 各种消息类型转换
6. stream: 文本流、工具调用累积、usage chunk、print_stream 开关
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

# Mock openai in sys.modules so that OpenAICompatibleClient.__init__ can import it
_mock_openai_module = MagicMock()
sys.modules['openai'] = _mock_openai_module

from novels_project.api_client import (
    TokenUsage,
    AssistantEvent,
    TextDelta,
    ToolUseEvent,
    UsageEvent,
    MessageStop,
    ApiRequest,
    ApiClient,
    OpenAICompatibleClient,
)
from novels_project.session import (
    MessageRole,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock,
    ConversationMessage,
)


# ---------------------------------------------------------------------------
# TokenUsage
# ---------------------------------------------------------------------------

class TestTokenUsage:
    """测试 TokenUsage"""

    def test_init_defaults(self):
        usage = TokenUsage()
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
        assert usage.total_tokens == 0

    def test_init_with_values(self):
        usage = TokenUsage(input_tokens=100, output_tokens=200, total_tokens=300)
        assert usage.input_tokens == 100
        assert usage.output_tokens == 200
        assert usage.total_tokens == 300

    def test_add(self):
        u1 = TokenUsage(input_tokens=10, output_tokens=20, total_tokens=30)
        u2 = TokenUsage(input_tokens=5, output_tokens=15, total_tokens=20)
        result = u1 + u2

        assert isinstance(result, TokenUsage)
        assert result.input_tokens == 15
        assert result.output_tokens == 35
        assert result.total_tokens == 50

    def test_add_with_zeros(self):
        u1 = TokenUsage()
        u2 = TokenUsage(input_tokens=5, output_tokens=10, total_tokens=15)
        result = u1 + u2

        assert result.input_tokens == 5
        assert result.output_tokens == 10
        assert result.total_tokens == 15

    def test_add_returns_new_object(self):
        u1 = TokenUsage(input_tokens=1, output_tokens=1, total_tokens=2)
        u2 = TokenUsage(input_tokens=1, output_tokens=1, total_tokens=2)
        result = u1 + u2

        assert result is not u1
        assert result is not u2


# ---------------------------------------------------------------------------
# AssistantEvent 子类
# ---------------------------------------------------------------------------

class TestAssistantEvents:
    """测试 AssistantEvent 及其子类"""

    def test_text_delta_creation(self):
        event = TextDelta(text="Hello")
        assert isinstance(event, AssistantEvent)
        assert event.text == "Hello"

    def test_text_delta_empty(self):
        event = TextDelta(text="")
        assert event.text == ""

    def test_tool_use_event_creation(self):
        event = ToolUseEvent(id="tool_01", name="search", input='{"q":"test"}')
        assert isinstance(event, AssistantEvent)
        assert event.id == "tool_01"
        assert event.name == "search"
        assert event.input == '{"q":"test"}'

    def test_usage_event_creation(self):
        usage = TokenUsage(input_tokens=10, output_tokens=20, total_tokens=30)
        event = UsageEvent(usage=usage)
        assert isinstance(event, AssistantEvent)
        assert event.usage is usage
        assert event.usage.input_tokens == 10

    def test_message_stop_creation(self):
        event = MessageStop()
        assert isinstance(event, AssistantEvent)

    def test_message_stop_no_fields(self):
        event = MessageStop()
        assert event.__dataclass_fields__ == {}


# ---------------------------------------------------------------------------
# ApiRequest
# ---------------------------------------------------------------------------

class TestApiRequest:
    """测试 ApiRequest"""

    def test_creation_with_defaults(self):
        req = ApiRequest(
            system_prompt="You are an assistant.",
            messages=[],
            tools=[],
            model="gpt-4",
        )
        assert req.system_prompt == "You are an assistant."
        assert req.messages == []
        assert req.tools == []
        assert req.model == "gpt-4"
        assert req.max_tokens == 16384

    def test_creation_with_custom_max_tokens(self):
        req = ApiRequest(
            system_prompt="sys",
            messages=[],
            tools=[],
            model="test-model",
            max_tokens=8000,
        )
        assert req.max_tokens == 8000

    def test_creation_with_messages_and_tools(self):
        msg = ConversationMessage.user_text("hi")
        req = ApiRequest(
            system_prompt="sys",
            messages=[msg],
            tools=["tool1"],
            model="m",
        )
        assert len(req.messages) == 1
        assert req.tools == ["tool1"]


# ---------------------------------------------------------------------------
# ApiClient Protocol
# ---------------------------------------------------------------------------

class TestApiClientProtocol:
    """测试 ApiClient Protocol"""

    def test_api_client_is_protocol(self):
        assert hasattr(ApiClient, '_is_protocol')
        assert ApiClient._is_protocol is True

    def test_openai_client_isinstance_api_client(self):
        """OpenAICompatibleClient satisfies the ApiClient Protocol."""
        client = OpenAICompatibleClient(base_url="http://x", api_key="k")
        assert isinstance(client, ApiClient)

    def test_openai_client_has_stream_method(self):
        assert hasattr(OpenAICompatibleClient, 'stream')

    def test_mock_isinstance_api_client(self):
        """Mock with stream method satisfies the ApiClient Protocol."""
        mock_obj = MagicMock()
        mock_obj.stream = MagicMock(return_value=[])
        assert isinstance(mock_obj, ApiClient)


# ---------------------------------------------------------------------------
# OpenAICompatibleClient.__init__
# ---------------------------------------------------------------------------

class TestOpenAICompatibleClientInit:
    """测试 OpenAICompatibleClient.__init__"""

    def test_init_creates_openai_client(self):
        mock_client = MagicMock()
        _mock_openai_module.OpenAI.return_value = mock_client
        _mock_openai_module.OpenAI.reset_mock()

        client = OpenAICompatibleClient(
            base_url="https://api.example.com/v1",
            api_key="test-key",
            default_model="my-model",
            max_retries=5,
            timeout=120.0,
        )

        _mock_openai_module.OpenAI.assert_called_once_with(
            base_url="https://api.example.com/v1",
            api_key="test-key",
            max_retries=5,
            timeout=120.0,
        )
        assert client.client is mock_client
        assert client.default_model == "my-model"

    def test_init_defaults(self):
        _mock_openai_module.OpenAI.return_value = MagicMock()
        _mock_openai_module.OpenAI.reset_mock()

        client = OpenAICompatibleClient(
            base_url="http://localhost",
            api_key="key",
        )

        call_kwargs = _mock_openai_module.OpenAI.call_args[1]
        assert call_kwargs["max_retries"] == 3
        assert call_kwargs["timeout"] == 300.0
        assert client.default_model == "gemini-3-pro"


# ---------------------------------------------------------------------------
# _convert_message
# ---------------------------------------------------------------------------

class TestConvertMessage:
    """测试 _convert_message"""

    @pytest.fixture
    def client(self):
        _mock_openai_module.OpenAI.return_value = MagicMock()
        return OpenAICompatibleClient(base_url="http://x", api_key="k")

    def test_user_with_text(self, client):
        msg = ConversationMessage.user_text("Hello world")
        result = client._convert_message(msg)
        assert result == {"role": "user", "content": "Hello world"}

    def test_user_with_multiple_text_blocks(self, client):
        msg = ConversationMessage(
            role=MessageRole.USER,
            blocks=[TextBlock(text="Hello"), TextBlock(text="World")],
        )
        result = client._convert_message(msg)
        assert result == {"role": "user", "content": "Hello\nWorld"}

    def test_user_without_text(self, client):
        msg = ConversationMessage(role=MessageRole.USER, blocks=[])
        result = client._convert_message(msg)
        assert result is None

    def test_user_with_non_text_blocks_only(self, client):
        msg = ConversationMessage(
            role=MessageRole.USER,
            blocks=[ToolUseBlock(id="t1", name="s", input="{}")],
        )
        result = client._convert_message(msg)
        assert result is None

    def test_assistant_with_text_only(self, client):
        msg = ConversationMessage(
            role=MessageRole.ASSISTANT,
            blocks=[TextBlock(text="I can help.")],
        )
        result = client._convert_message(msg)
        assert result == {"role": "assistant", "content": "I can help."}

    def test_assistant_with_tool_calls_only(self, client):
        msg = ConversationMessage(
            role=MessageRole.ASSISTANT,
            blocks=[ToolUseBlock(id="tool_01", name="search", input='{"q":"x"}')],
        )
        result = client._convert_message(msg)
        assert result == {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "tool_01",
                    "type": "function",
                    "function": {"name": "search", "arguments": '{"q":"x"}'},
                }
            ],
        }

    def test_assistant_with_both_text_and_tools(self, client):
        msg = ConversationMessage(
            role=MessageRole.ASSISTANT,
            blocks=[
                TextBlock(text="Let me search."),
                ToolUseBlock(id="t1", name="search", input='{"q":"test"}'),
            ],
        )
        result = client._convert_message(msg)
        assert result["role"] == "assistant"
        assert result["content"] == "Let me search."
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["id"] == "t1"

    def test_assistant_with_neither_text_nor_tools(self, client):
        msg = ConversationMessage(role=MessageRole.ASSISTANT, blocks=[])
        result = client._convert_message(msg)
        assert result is None

    def test_tool_with_results(self, client):
        msg = ConversationMessage(
            role=MessageRole.TOOL,
            blocks=[
                ToolResultBlock(
                    tool_use_id="tu_01",
                    tool_name="search",
                    output="Found 5 results",
                ),
            ],
        )
        result = client._convert_message(msg)
        assert result == [
            {
                "role": "tool",
                "tool_call_id": "tu_01",
                "content": "Found 5 results",
            }
        ]

    def test_tool_with_multiple_results(self, client):
        msg = ConversationMessage(
            role=MessageRole.TOOL,
            blocks=[
                ToolResultBlock(tool_use_id="t1", tool_name="a", output="r1"),
                ToolResultBlock(tool_use_id="t2", tool_name="b", output="r2"),
            ],
        )
        result = client._convert_message(msg)
        assert len(result) == 2
        assert result[0]["tool_call_id"] == "t1"
        assert result[1]["tool_call_id"] == "t2"

    def test_tool_without_results(self, client):
        msg = ConversationMessage(role=MessageRole.TOOL, blocks=[])
        result = client._convert_message(msg)
        assert result is None

    def test_tool_with_non_result_blocks(self, client):
        msg = ConversationMessage(
            role=MessageRole.TOOL,
            blocks=[TextBlock(text="not a tool result")],
        )
        result = client._convert_message(msg)
        assert result is None

    def test_system_message(self, client):
        msg = ConversationMessage(
            role=MessageRole.SYSTEM,
            blocks=[TextBlock(text="system info")],
        )
        result = client._convert_message(msg)
        assert result is None


# ---------------------------------------------------------------------------
# stream
# ---------------------------------------------------------------------------

class TestStream:
    """测试 OpenAICompatibleClient.stream"""

    @pytest.fixture
    def client(self):
        _mock_openai_module.OpenAI.return_value = MagicMock()
        return OpenAICompatibleClient(base_url="http://x", api_key="k")

    def _make_chunk(self, content=None, tool_calls=None, finish_reason=None,
                    usage=None, has_choices=True):
        chunk = MagicMock()

        if not has_choices:
            chunk.choices = []
        else:
            choice = MagicMock()
            delta = MagicMock()
            delta.content = content
            delta.tool_calls = tool_calls
            choice.delta = delta
            choice.finish_reason = finish_reason
            chunk.choices = [choice]

        chunk.usage = usage
        return chunk

    def _make_usage_chunk(self, prompt=100, completion=200, total=300):
        chunk = MagicMock()
        chunk.choices = []
        usage = MagicMock()
        usage.prompt_tokens = prompt
        usage.completion_tokens = completion
        usage.total_tokens = total
        chunk.usage = usage
        return chunk

    def _make_tool_call_delta(self, index=0, id=None, name=None, arguments=None):
        tc = MagicMock()
        tc.index = index
        tc.id = id
        tc.function = MagicMock()
        tc.function.name = name
        tc.function.arguments = arguments
        return tc

    def test_text_streaming(self, client):
        chunks = [
            self._make_chunk(content="Hello "),
            self._make_chunk(content="world!"),
            self._make_chunk(finish_reason="stop"),
        ]
        client.client.chat.completions.create.return_value = chunks

        req = ApiRequest(
            system_prompt="",
            messages=[ConversationMessage.user_text("hi")],
            tools=[],
            model="test",
        )

        events = client.stream(req, print_stream=False)

        text_events = [e for e in events if isinstance(e, TextDelta)]
        assert len(text_events) == 2
        assert text_events[0].text == "Hello "
        assert text_events[1].text == "world!"

        stop_events = [e for e in events if isinstance(e, MessageStop)]
        assert len(stop_events) == 1

    def test_tool_call_accumulation(self, client):
        chunks = [
            self._make_chunk(tool_calls=[
                self._make_tool_call_delta(index=0, id="tool_01", name="search"),
            ]),
            self._make_chunk(tool_calls=[
                self._make_tool_call_delta(index=0, arguments='{"q":'),
            ]),
            self._make_chunk(tool_calls=[
                self._make_tool_call_delta(index=0, arguments='"test"}'),
            ]),
            self._make_chunk(finish_reason="tool_calls"),
        ]
        client.client.chat.completions.create.return_value = chunks

        req = ApiRequest(
            system_prompt="",
            messages=[ConversationMessage.user_text("hi")],
            tools=[],
            model="test",
        )

        events = client.stream(req, print_stream=False)

        tool_events = [e for e in events if isinstance(e, ToolUseEvent)]
        assert len(tool_events) == 1
        assert tool_events[0].id == "tool_01"
        assert tool_events[0].name == "search"
        assert tool_events[0].input == '{"q":"test"}'

    def test_multiple_tool_calls(self, client):
        chunks = [
            self._make_chunk(tool_calls=[
                self._make_tool_call_delta(index=0, id="t1", name="fn1"),
                self._make_tool_call_delta(index=1, id="t2", name="fn2"),
            ]),
            self._make_chunk(tool_calls=[
                self._make_tool_call_delta(index=0, arguments='{"a":1}'),
            ]),
            self._make_chunk(tool_calls=[
                self._make_tool_call_delta(index=1, arguments='{"b":2}'),
            ]),
            self._make_chunk(finish_reason="tool_calls"),
        ]
        client.client.chat.completions.create.return_value = chunks

        req = ApiRequest(
            system_prompt="",
            messages=[ConversationMessage.user_text("hi")],
            tools=[],
            model="test",
        )

        events = client.stream(req, print_stream=False)

        tool_events = [e for e in events if isinstance(e, ToolUseEvent)]
        assert len(tool_events) == 2
        assert tool_events[0].id == "t1"
        assert tool_events[0].name == "fn1"
        assert tool_events[0].input == '{"a":1}'
        assert tool_events[1].id == "t2"
        assert tool_events[1].name == "fn2"
        assert tool_events[1].input == '{"b":2}'

    def test_usage_chunk_handling(self, client):
        # Usage chunk must come before stop since loop breaks on finish_reason
        chunks = [
            self._make_chunk(content="text"),
            self._make_usage_chunk(prompt=50, completion=100, total=150),
            self._make_chunk(finish_reason="stop"),
        ]
        client.client.chat.completions.create.return_value = chunks

        req = ApiRequest(
            system_prompt="",
            messages=[ConversationMessage.user_text("hi")],
            tools=[],
            model="test",
        )

        events = client.stream(req, print_stream=False)

        usage_events = [e for e in events if isinstance(e, UsageEvent)]
        assert len(usage_events) == 1
        assert usage_events[0].usage.input_tokens == 50
        assert usage_events[0].usage.output_tokens == 100
        assert usage_events[0].usage.total_tokens == 150

        stop_events = [e for e in events if isinstance(e, MessageStop)]
        assert len(stop_events) == 1

    def test_mixed_text_and_tool_calls(self, client):
        chunks = [
            self._make_chunk(content="I will "),
            self._make_chunk(content="search."),
            self._make_chunk(tool_calls=[
                self._make_tool_call_delta(index=0, id="t1", name="s", arguments='{}'),
            ]),
            self._make_chunk(finish_reason="tool_calls"),
        ]
        client.client.chat.completions.create.return_value = chunks

        req = ApiRequest(
            system_prompt="",
            messages=[ConversationMessage.user_text("hi")],
            tools=[],
            model="test",
        )

        events = client.stream(req, print_stream=False)

        text_events = [e for e in events if isinstance(e, TextDelta)]
        tool_events = [e for e in events if isinstance(e, ToolUseEvent)]
        stop_events = [e for e in events if isinstance(e, MessageStop)]

        assert len(text_events) == 2
        assert len(tool_events) == 1
        assert len(stop_events) == 1

    def test_stream_with_tools_parameter(self, client):
        chunks = [
            self._make_chunk(content="ok"),
            self._make_chunk(finish_reason="stop"),
        ]
        client.client.chat.completions.create.return_value = chunks

        mock_tool_spec = MagicMock()
        mock_tool_spec.name = "my_tool"
        mock_tool_spec.description = "A tool"
        mock_tool_spec.input_schema = {"type": "object"}

        req = ApiRequest(
            system_prompt="sys",
            messages=[ConversationMessage.user_text("hi")],
            tools=[mock_tool_spec],
            model="test",
        )

        _ = client.stream(req, print_stream=False)

        call_kwargs = client.client.chat.completions.create.call_args[1]
        assert "tools" in call_kwargs
        assert len(call_kwargs["tools"]) == 1
        assert call_kwargs["tools"][0]["type"] == "function"
        assert call_kwargs["tools"][0]["function"]["name"] == "my_tool"

    def test_stream_uses_default_model_when_request_model_empty(self, client):
        chunks = [
            self._make_chunk(content="ok"),
            self._make_chunk(finish_reason="stop"),
        ]
        client.client.chat.completions.create.return_value = chunks
        client.default_model = "default-model"

        req = ApiRequest(
            system_prompt="sys",
            messages=[ConversationMessage.user_text("hi")],
            tools=[],
            model="",
        )

        client.stream(req, print_stream=False)

        call_kwargs = client.client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "default-model"

    def test_print_stream_on_writes_to_stdout(self, client):
        chunks = [
            self._make_chunk(content="Hello"),
            self._make_chunk(finish_reason="stop"),
        ]
        client.client.chat.completions.create.return_value = chunks

        req = ApiRequest(
            system_prompt="",
            messages=[ConversationMessage.user_text("hi")],
            tools=[],
            model="test",
        )

        with patch('sys.stdout.write') as mock_write:
            with patch('sys.stdout.flush'):
                client.stream(req, print_stream=True)

        mock_write.assert_any_call("Hello")
        mock_write.assert_any_call("\n")

    def test_print_stream_off_does_not_write(self, client):
        chunks = [
            self._make_chunk(content="Hello"),
            self._make_chunk(finish_reason="stop"),
        ]
        client.client.chat.completions.create.return_value = chunks

        req = ApiRequest(
            system_prompt="",
            messages=[ConversationMessage.user_text("hi")],
            tools=[],
            model="test",
        )

        with patch('sys.stdout.write') as mock_write:
            with patch('sys.stdout.flush'):
                client.stream(req, print_stream=False)

        mock_write.assert_not_called()

    def test_stream_empty_choices_skip(self, client):
        chunks = [
            self._make_chunk(has_choices=False),
            self._make_chunk(content="actual"),
            self._make_chunk(finish_reason="stop"),
        ]
        client.client.chat.completions.create.return_value = chunks

        req = ApiRequest(
            system_prompt="",
            messages=[ConversationMessage.user_text("hi")],
            tools=[],
            model="test",
        )

        events = client.stream(req, print_stream=False)

        text_events = [e for e in events if isinstance(e, TextDelta)]
        assert len(text_events) == 1
        assert text_events[0].text == "actual"

    def test_stream_system_prompt_included(self, client):
        chunks = [
            self._make_chunk(content="ok"),
            self._make_chunk(finish_reason="stop"),
        ]
        client.client.chat.completions.create.return_value = chunks

        req = ApiRequest(
            system_prompt="You are helpful.",
            messages=[ConversationMessage.user_text("hi")],
            tools=[],
            model="test",
        )

        client.stream(req, print_stream=False)

        call_kwargs = client.client.chat.completions.create.call_args[1]
        messages = call_kwargs["messages"]
        assert messages[0] == {"role": "system", "content": "You are helpful."}
        assert messages[1] == {"role": "user", "content": "hi"}

    def test_stream_no_system_prompt(self, client):
        chunks = [
            self._make_chunk(content="ok"),
            self._make_chunk(finish_reason="stop"),
        ]
        client.client.chat.completions.create.return_value = chunks

        req = ApiRequest(
            system_prompt="",
            messages=[ConversationMessage.user_text("hi")],
            tools=[],
            model="test",
        )

        client.stream(req, print_stream=False)

        call_kwargs = client.client.chat.completions.create.call_args[1]
        messages = call_kwargs["messages"]
        assert messages[0] == {"role": "user", "content": "hi"}

    def test_stream_always_includes_message_stop(self, client):
        chunks = [
            self._make_chunk(finish_reason="stop"),
        ]
        client.client.chat.completions.create.return_value = chunks

        req = ApiRequest(
            system_prompt="",
            messages=[ConversationMessage.user_text("hi")],
            tools=[],
            model="test",
        )

        events = client.stream(req, print_stream=False)

        assert isinstance(events[-1], MessageStop)

    def test_stream_stream_options_include_usage(self, client):
        chunks = [
            self._make_chunk(content="ok"),
            self._make_chunk(finish_reason="stop"),
        ]
        client.client.chat.completions.create.return_value = chunks

        req = ApiRequest(
            system_prompt="",
            messages=[ConversationMessage.user_text("hi")],
            tools=[],
            model="test",
        )

        client.stream(req, print_stream=False)

        call_kwargs = client.client.chat.completions.create.call_args[1]
        assert call_kwargs["stream"] is True
        assert call_kwargs["stream_options"] == {"include_usage": True}

    def test_stream_tool_call_without_name_or_id(self, client):
        chunks = [
            self._make_chunk(tool_calls=[
                self._make_tool_call_delta(index=0, arguments='{"x":1}'),
            ]),
            self._make_chunk(finish_reason="tool_calls"),
        ]
        client.client.chat.completions.create.return_value = chunks

        req = ApiRequest(
            system_prompt="",
            messages=[ConversationMessage.user_text("hi")],
            tools=[],
            model="test",
        )

        events = client.stream(req, print_stream=False)

        tool_events = [e for e in events if isinstance(e, ToolUseEvent)]
        assert len(tool_events) == 1
        assert tool_events[0].id == ""
        assert tool_events[0].name == ""
        assert tool_events[0].input == '{"x":1}'

    def test_stream_preserves_event_order(self, client):
        # Usage chunk must come before stop since loop breaks on finish_reason
        chunks = [
            self._make_chunk(content="A"),
            self._make_chunk(content="B"),
            self._make_usage_chunk(prompt=1, completion=2, total=3),
            self._make_chunk(finish_reason="stop"),
        ]
        client.client.chat.completions.create.return_value = chunks

        req = ApiRequest(
            system_prompt="",
            messages=[ConversationMessage.user_text("hi")],
            tools=[],
            model="test",
        )

        events = client.stream(req, print_stream=False)

        types = [type(e).__name__ for e in events]
        # TextDelta, TextDelta, UsageEvent, MessageStop
        assert types == ['TextDelta', 'TextDelta', 'UsageEvent', 'MessageStop']

    def test_stream_message_convert_returns_none(self, client):
        """Message that _convert_message returns None for -> skipped."""
        chunks = [
            self._make_chunk(content="ok"),
            self._make_chunk(finish_reason="stop"),
        ]
        client.client.chat.completions.create.return_value = chunks

        # User message with no text blocks -> _convert_message returns None
        empty_msg = ConversationMessage(role=MessageRole.USER, blocks=[])

        req = ApiRequest(
            system_prompt="sys",
            messages=[empty_msg, ConversationMessage.user_text("hi")],
            tools=[],
            model="test",
        )

        events = client.stream(req, print_stream=False)
        text_events = [e for e in events if isinstance(e, TextDelta)]
        assert len(text_events) == 1

    def test_stream_message_convert_returns_list(self, client):
        """Message that _convert_message returns a list -> extended."""
        chunks = [
            self._make_chunk(content="ok"),
            self._make_chunk(finish_reason="stop"),
        ]
        client.client.chat.completions.create.return_value = chunks

        # Tool message with results -> _convert_message returns list
        tool_msg = ConversationMessage(
            role=MessageRole.TOOL,
            blocks=[
                ToolResultBlock(tool_use_id="tu_01", tool_name="s", output="result1"),
                ToolResultBlock(tool_use_id="tu_02", tool_name="s", output="result2"),
            ],
        )

        req = ApiRequest(
            system_prompt="sys",
            messages=[ConversationMessage.user_text("hi"), tool_msg],
            tools=[],
            model="test",
        )

        events = client.stream(req, print_stream=False)
        text_events = [e for e in events if isinstance(e, TextDelta)]
        assert len(text_events) == 1

    def test_stream_empty_response(self, client):
        """Empty response iterator -> covers loop-exit branch."""
        client.client.chat.completions.create.return_value = iter([])

        req = ApiRequest(
            system_prompt="",
            messages=[ConversationMessage.user_text("hi")],
            tools=[],
            model="test",
        )

        events = client.stream(req, print_stream=False)
        # Should still include MessageStop
        assert isinstance(events[-1], MessageStop)
        # No TextDelta events
        assert len([e for e in events if isinstance(e, TextDelta)]) == 0

    def test_tool_call_without_function(self, client):
        """Tool call delta where tc.function is falsy."""
        chunks = [
            self._make_chunk(tool_calls=[
                self._make_tool_call_delta(index=0, id="t1", name="fn"),
            ]),
            self._make_chunk(tool_calls=[
                self._make_tool_call_delta(index=0, arguments='{"x":1}'),
            ]),
            self._make_chunk(finish_reason="tool_calls"),
        ]
        # Make function None for one of the chunks
        for tc in chunks[0].choices[0].delta.tool_calls:
            tc.function = None
        client.client.chat.completions.create.return_value = chunks

        req = ApiRequest(
            system_prompt="",
            messages=[ConversationMessage.user_text("hi")],
            tools=[],
            model="test",
        )

        events = client.stream(req, print_stream=False)
        tool_events = [e for e in events if isinstance(e, ToolUseEvent)]
        assert len(tool_events) == 1
        # Name/arguments should be accumulated from the chunk with arguments
        assert tool_events[0].input == '{"x":1}'