"""
单元测试：runtime 模块测试

测试范围：
1. AutoCompactionEvent 创建
2. TurnSummary: get_final_text
3. ConversationRuntime.__init__
4. _build_assistant_message: TextDelta / ToolUseEvent / UsageEvent / MessageStop / mixed / empty
5. _maybe_auto_compact: under threshold / over with compaction / over but nothing removed
6. run_turn: basic flow / tool calls / exceeding max_iterations / auto compaction
"""

from unittest.mock import MagicMock, patch, PropertyMock, Mock, call

import pytest

from novels_project.runtime import (
    AutoCompactionEvent,
    TurnSummary,
    ConversationRuntime,
)
from novels_project.api_client import (
    TokenUsage,
    TextDelta,
    ToolUseEvent,
    UsageEvent,
    MessageStop,
    ApiRequest,
)
from novels_project.session import (
    Session,
    ConversationMessage,
    MessageRole,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_api_client():
    """Return a mock ApiClient."""
    client = MagicMock()
    client.stream.return_value = []
    return client


@pytest.fixture
def mock_session():
    """Return a Session with mocked methods."""
    session = MagicMock(spec=Session)
    session.messages = []
    session.total_estimated_tokens.return_value = 100
    return session


@pytest.fixture
def mock_tool_executor():
    """Return a mock ToolExecutor."""
    executor = MagicMock()
    executor.execute.return_value = ("result", False)
    return executor


@pytest.fixture
def mock_tool_registry():
    """Return a mock ToolRegistry."""
    registry = MagicMock()
    registry.all_specs.return_value = []
    return registry


def make_text_event(text):
    return TextDelta(text=text)


def make_tool_event(id="t1", name="search", input_str='{"q":"x"}'):
    return ToolUseEvent(id=id, name=name, input=input_str)


def make_usage_event(input_tokens=10, output_tokens=20, total_tokens=30):
    return UsageEvent(usage=TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
    ))


def make_stop_event():
    return MessageStop()


# ---------------------------------------------------------------------------
# AutoCompactionEvent
# ---------------------------------------------------------------------------

class TestAutoCompactionEvent:
    """测试 AutoCompactionEvent"""

    def test_creation(self):
        event = AutoCompactionEvent(removed_message_count=5)
        assert event.removed_message_count == 5

    def test_creation_zero(self):
        event = AutoCompactionEvent(removed_message_count=0)
        assert event.removed_message_count == 0


# ---------------------------------------------------------------------------
# TurnSummary
# ---------------------------------------------------------------------------

class TestTurnSummary:
    """测试 TurnSummary"""

    def test_get_final_text_with_assistant_messages(self):
        msg1 = ConversationMessage.assistant([TextBlock(text="First response")])
        msg2 = ConversationMessage.assistant([TextBlock(text="Final answer")])
        summary = TurnSummary(assistant_messages=[msg1, msg2])

        assert summary.get_final_text() == "Final answer"

    def test_get_final_text_without_assistant_messages(self):
        summary = TurnSummary()

        assert summary.get_final_text() == ""

    def test_get_final_text_multiline(self):
        msg = ConversationMessage.assistant([
            TextBlock(text="Line 1"),
            TextBlock(text="Line 2"),
        ])
        summary = TurnSummary(assistant_messages=[msg])

        assert summary.get_final_text() == "Line 1\nLine 2"

    def test_default_values(self):
        summary = TurnSummary()
        assert summary.assistant_messages == []
        assert summary.tool_results == []
        assert summary.iterations == 0
        assert summary.usage == TokenUsage()
        assert summary.auto_compaction is None


# ---------------------------------------------------------------------------
# ConversationRuntime.__init__
# ---------------------------------------------------------------------------

class TestConversationRuntimeInit:
    """测试 ConversationRuntime.__init__"""

    def test_init_with_all_params(
        self, mock_session, mock_api_client, mock_tool_executor, mock_tool_registry
    ):
        runtime = ConversationRuntime(
            session=mock_session,
            api_client=mock_api_client,
            tool_executor=mock_tool_executor,
            tool_registry=mock_tool_registry,
            system_prompt="You are helpful.",
            model="gpt-4",
            max_iterations=30,
            auto_compaction_threshold=80000,
            print_stream=False,
        )

        assert runtime.session is mock_session
        assert runtime.api_client is mock_api_client
        assert runtime.tool_executor is mock_tool_executor
        assert runtime.tool_registry is mock_tool_registry
        assert runtime.system_prompt == "You are helpful."
        assert runtime.model == "gpt-4"
        assert runtime.max_iterations == 30
        assert runtime.auto_compaction_threshold == 80000
        assert runtime.print_stream is False
        assert runtime.usage_tracker is not None

    def test_init_defaults(
        self, mock_session, mock_api_client, mock_tool_executor, mock_tool_registry
    ):
        runtime = ConversationRuntime(
            session=mock_session,
            api_client=mock_api_client,
            tool_executor=mock_tool_executor,
            tool_registry=mock_tool_registry,
            system_prompt="sys",
            model="m",
        )

        assert runtime.max_iterations == 50
        assert runtime.auto_compaction_threshold == 100000
        assert runtime.print_stream is True


# ---------------------------------------------------------------------------
# _build_assistant_message
# ---------------------------------------------------------------------------

class TestBuildAssistantMessage:
    """测试 _build_assistant_message"""

    @pytest.fixture
    def runtime(self, mock_session, mock_api_client, mock_tool_executor, mock_tool_registry):
        return ConversationRuntime(
            session=mock_session,
            api_client=mock_api_client,
            tool_executor=mock_tool_executor,
            tool_registry=mock_tool_registry,
            system_prompt="sys",
            model="m",
            print_stream=False,
        )

    def test_with_text_delta(self, runtime):
        events = [make_text_event("Hello"), make_text_event(" world")]
        msg, usage = runtime._build_assistant_message(events)

        assert usage is None
        assert msg.role == MessageRole.ASSISTANT
        assert len(msg.blocks) == 1  # single TextBlock with concatenated text
        assert msg.blocks[0].text == "Hello world"
        assert len(msg.get_tool_uses()) == 0

    def test_with_tool_use_event(self, runtime):
        events = [make_tool_event(id="tu_01", name="search", input_str='{"q":"test"}')]
        msg, usage = runtime._build_assistant_message(events)

        assert usage is None
        assert msg.role == MessageRole.ASSISTANT
        tool_uses = msg.get_tool_uses()
        assert len(tool_uses) == 1
        assert tool_uses[0].id == "tu_01"
        assert tool_uses[0].name == "search"
        assert tool_uses[0].input == '{"q":"test"}'
        # No text block since no text events
        text_blocks = [b for b in msg.blocks if isinstance(b, TextBlock)]
        assert len(text_blocks) == 0

    def test_with_usage_event(self, runtime):
        events = [make_usage_event(input_tokens=5, output_tokens=15, total_tokens=20)]
        msg, usage = runtime._build_assistant_message(events)

        assert usage is not None
        assert usage.input_tokens == 5
        assert usage.output_tokens == 15
        assert usage.total_tokens == 20
        assert msg.role == MessageRole.ASSISTANT
        assert len(msg.blocks) == 0

    def test_with_message_stop(self, runtime):
        events = [make_stop_event()]
        msg, usage = runtime._build_assistant_message(events)

        assert usage is None
        assert msg.role == MessageRole.ASSISTANT
        assert len(msg.blocks) == 0

    def test_with_mixed_events(self, runtime):
        events = [
            make_text_event("I will search."),
            make_tool_event(id="t1", name="search", input_str="{}"),
            make_usage_event(input_tokens=10, output_tokens=20, total_tokens=30),
            make_stop_event(),
        ]
        msg, usage = runtime._build_assistant_message(events)

        assert usage is not None
        assert usage.input_tokens == 10

        # TextBlock inserted at front
        assert isinstance(msg.blocks[0], TextBlock)
        assert msg.blocks[0].text == "I will search."

        # ToolUseBlock follows
        tool_uses = msg.get_tool_uses()
        assert len(tool_uses) == 1
        assert tool_uses[0].id == "t1"

    def test_with_empty_text_not_inserted(self, runtime):
        """Whitespace-only text should not create a TextBlock."""
        events = [
            make_text_event("   "),
            make_tool_event(id="t1", name="s", input_str="{}"),
        ]
        msg, usage = runtime._build_assistant_message(events)

        text_blocks = [b for b in msg.blocks if isinstance(b, TextBlock)]
        assert len(text_blocks) == 0

    def test_multiple_tool_uses(self, runtime):
        events = [
            make_tool_event(id="t1", name="fn1", input_str='{"a":1}'),
            make_tool_event(id="t2", name="fn2", input_str='{"b":2}'),
            make_tool_event(id="t3", name="fn3", input_str='{"c":3}'),
        ]
        msg, _ = runtime._build_assistant_message(events)

        tool_uses = msg.get_tool_uses()
        assert len(tool_uses) == 3
        assert tool_uses[0].id == "t1"
        assert tool_uses[1].id == "t2"
        assert tool_uses[2].id == "t3"


# ---------------------------------------------------------------------------
# _maybe_auto_compact
# ---------------------------------------------------------------------------

class TestMaybeAutoCompact:
    """测试 _maybe_auto_compact"""

    @pytest.fixture
    def runtime(self, mock_session, mock_api_client, mock_tool_executor, mock_tool_registry):
        return ConversationRuntime(
            session=mock_session,
            api_client=mock_api_client,
            tool_executor=mock_tool_executor,
            tool_registry=mock_tool_registry,
            system_prompt="sys",
            model="m",
            auto_compaction_threshold=1000,
            print_stream=False,
        )

    def test_under_threshold(self, runtime):
        runtime.session.total_estimated_tokens.return_value = 500  # < 1000

        result = runtime._maybe_auto_compact()

        assert result is None

    def test_over_threshold_with_compaction(self, runtime):
        runtime.session.total_estimated_tokens.return_value = 1500  # > 1000

        mock_compacted_session = MagicMock(spec=Session)
        compaction_result = MagicMock()
        compaction_result.removed_message_count = 3
        compaction_result.compacted_session = mock_compacted_session

        with patch('novels_project.runtime.compact_session', return_value=compaction_result):
            result = runtime._maybe_auto_compact()

        assert result is not None
        assert result.removed_message_count == 3
        assert runtime.session is mock_compacted_session

    def test_over_threshold_but_no_messages_removed(self, runtime):
        runtime.session.total_estimated_tokens.return_value = 1500

        compaction_result = MagicMock()
        compaction_result.removed_message_count = 0
        compaction_result.compacted_session = runtime.session  # same session

        with patch('novels_project.runtime.compact_session', return_value=compaction_result):
            result = runtime._maybe_auto_compact()

        assert result is None


# ---------------------------------------------------------------------------
# run_turn
# ---------------------------------------------------------------------------

class TestRunTurn:
    """测试 run_turn"""

    @pytest.fixture
    def runtime(self, mock_session, mock_api_client, mock_tool_executor, mock_tool_registry):
        rt = ConversationRuntime(
            session=mock_session,
            api_client=mock_api_client,
            tool_executor=mock_tool_executor,
            tool_registry=mock_tool_registry,
            system_prompt="You are helpful.",
            model="test-model",
            max_iterations=10,
            print_stream=False,
        )
        return rt

    def test_basic_flow_single_llm_call(self, runtime):
        """User message -> one LLM response without tools -> done."""
        runtime.api_client.stream.return_value = [
            make_text_event("Hello!"),
            make_usage_event(input_tokens=5, output_tokens=3, total_tokens=8),
            make_stop_event(),
        ]

        summary = runtime.run_turn("Hi there")

        # Verify user message was pushed
        assert len(runtime.session.messages) >= 2  # user + assistant
        assert runtime.session.messages[0].role == MessageRole.USER
        assert runtime.session.messages[0].get_text() == "Hi there"

        # Verify assistant message was pushed
        assert runtime.session.messages[1].role == MessageRole.ASSISTANT

        # Verify summary
        assert summary.iterations == 1
        assert len(summary.assistant_messages) == 1
        assert summary.assistant_messages[0].get_text() == "Hello!"
        assert len(summary.tool_results) == 0
        assert summary.usage.total_tokens == 8

    def test_with_tool_calls(self, runtime):
        """User message -> LLM calls tool -> executor runs -> LLM final response."""
        # First LLM call: tool use
        stream_call_count = [0]

        def stream_side_effect(request, print_stream=False):
            stream_call_count[0] += 1
            if stream_call_count[0] == 1:
                return [
                    make_text_event("Let me search."),
                    make_tool_event(id="tu_01", name="search", input_str='{"q":"test"}'),
                    make_usage_event(5, 10, 15),
                    make_stop_event(),
                ]
            else:
                return [
                    make_text_event("Found results: ..."),
                    make_usage_event(10, 20, 30),
                    make_stop_event(),
                ]

        runtime.api_client.stream.side_effect = stream_side_effect

        summary = runtime.run_turn("Search for something")

        # Should have 2 iterations
        assert summary.iterations == 2
        assert len(summary.assistant_messages) == 2
        assert len(summary.tool_results) == 1

        # Tool executor should have been called
        runtime.tool_executor.execute.assert_called_once_with("search", '{"q":"test"}')

        # Verify tool result was pushed to session
        tool_msgs = [m for m in runtime.session.messages if m.role == MessageRole.TOOL]
        assert len(tool_msgs) == 1

    def test_multiple_tool_calls_in_one_turn(self, runtime):
        """Single LLM response with multiple tool calls."""
        stream_call_count = [0]

        def stream_side_effect(request, print_stream=False):
            stream_call_count[0] += 1
            if stream_call_count[0] == 1:
                return [
                    make_tool_event(id="t1", name="tool_a", input_str='{"a":1}'),
                    make_tool_event(id="t2", name="tool_b", input_str='{"b":2}'),
                    make_stop_event(),
                ]
            else:
                return [make_text_event("done"), make_stop_event()]

        runtime.api_client.stream.side_effect = stream_side_effect

        summary = runtime.run_turn("do stuff")

        assert summary.iterations == 2
        assert len(summary.tool_results) == 2
        assert runtime.tool_executor.execute.call_count == 2
        runtime.tool_executor.execute.assert_any_call("tool_a", '{"a":1}')
        runtime.tool_executor.execute.assert_any_call("tool_b", '{"b":2}')

    def test_exceeding_max_iterations(self, runtime):
        """When loop exceeds max_iterations, raises RuntimeError."""
        runtime.max_iterations = 3

        # Always return tool calls to force infinite loop
        def stream_side_effect(request, print_stream=False):
            return [
                make_tool_event(id="t1", name="loop_tool", input_str="{}"),
                make_stop_event(),
            ]

        runtime.api_client.stream.side_effect = stream_side_effect

        with pytest.raises(RuntimeError, match="exceeded.*iterations"):
            runtime.run_turn("start infinite loop")

    def test_auto_compaction_triggered(self, runtime):
        """Auto compaction is triggered when tokens exceed threshold."""
        runtime.auto_compaction_threshold = 50
        runtime.session.total_estimated_tokens.return_value = 100

        runtime.api_client.stream.return_value = [
            make_text_event("Short"),
            make_stop_event(),
        ]

        compaction_result = MagicMock()
        compaction_result.removed_message_count = 2
        # 10b: 经验信号是 session 引用是否变化
        # 必须 mock 一个不同的 Session 实例才能触发 auto_compaction
        compaction_result.compacted_session = MagicMock()  # 新 Session 实例

        with patch('novels_project.runtime.compact_session', return_value=compaction_result):
            summary = runtime.run_turn("hi")

        assert summary.auto_compaction is not None
        assert summary.auto_compaction.removed_message_count == 2

    def test_tool_error_handling(self, runtime):
        """Tool execution error should still push result and continue."""
        runtime.tool_executor.execute.return_value = ("Error: something failed", True)

        stream_call_count = [0]

        def stream_side_effect(request, print_stream=False):
            stream_call_count[0] += 1
            if stream_call_count[0] == 1:
                return [
                    make_tool_event(id="t1", name="failing_tool", input_str="{}"),
                    make_stop_event(),
                ]
            else:
                return [make_text_event("I encountered an error"), make_stop_event()]

        runtime.api_client.stream.side_effect = stream_side_effect

        summary = runtime.run_turn("do it")

        # Should continue after error
        assert summary.iterations == 2
        assert len(summary.tool_results) == 1

    def test_large_tool_output_truncation(self, runtime):
        """Tool output > 50000 chars should be truncated."""
        long_output = "x" * 60000
        runtime.tool_executor.execute.return_value = (long_output, False)

        stream_call_count = [0]

        def stream_side_effect(request, print_stream=False):
            stream_call_count[0] += 1
            if stream_call_count[0] == 1:
                return [
                    make_tool_event(id="t1", name="big_tool", input_str="{}"),
                    make_stop_event(),
                ]
            else:
                return [make_text_event("ok"), make_stop_event()]

        runtime.api_client.stream.side_effect = stream_side_effect

        summary = runtime.run_turn("go")

        # Find the tool result message
        tool_msgs = [m for m in runtime.session.messages if m.role == MessageRole.TOOL]
        assert len(tool_msgs) == 1
        output_block = tool_msgs[0].blocks[0]
        assert len(output_block.output) <= 50000 + len("\n... (output truncated at 50000 chars)")
        assert "truncated" in output_block.output

    def test_api_request_uses_correct_params(self, runtime):
        """Verify ApiRequest is built with correct parameters."""
        runtime.tool_registry.all_specs.return_value = ["spec1", "spec2"]
        runtime.api_client.stream.return_value = [
            make_text_event("ok"),
            make_stop_event(),
        ]

        runtime.run_turn("test")

        # Check the ApiRequest passed to stream
        call_args = runtime.api_client.stream.call_args[0]
        request = call_args[0]
        assert request.system_prompt == "You are helpful."
        assert request.model == "test-model"
        assert request.tools == ["spec1", "spec2"]

    def test_print_stream_passed_to_api_client(self, runtime):
        """Verify print_stream is forwarded to api_client.stream."""
        runtime.print_stream = True
        runtime.api_client.stream.return_value = [
            make_text_event("ok"),
            make_stop_event(),
        ]

        runtime.run_turn("test")

        call_kwargs = runtime.api_client.stream.call_args[1]
        assert call_kwargs["print_stream"] is True

    def test_run_turn_respects_print_stream(self, runtime):
        """When print_stream=False, print statements are suppressed."""
        runtime.print_stream = False
        runtime.api_client.stream.return_value = [
            make_text_event("ok"),
            make_stop_event(),
        ]

        with patch('builtins.print') as mock_print:
            runtime.run_turn("test")

        # print should not be called for tool info
        tool_print_calls = [c for c in mock_print.call_args_list
                            if 'Tool:' in str(c)]
        assert len(tool_print_calls) == 0


# ==================== run_turn with print_stream=True ====================

class TestRunTurnPrintStream:
    """Tests that verify print_stream=True behavior."""

    @pytest.fixture
    def runtime(self, mock_session, mock_api_client, mock_tool_executor, mock_tool_registry):
        rt = ConversationRuntime(
            session=mock_session,
            api_client=mock_api_client,
            tool_executor=mock_tool_executor,
            tool_registry=mock_tool_registry,
            system_prompt="You are helpful.",
            model="test-model",
            max_iterations=10,
            print_stream=True,  # key difference
        )
        return rt

    def test_tool_execution_prints(self, runtime):
        """When print_stream=True, tool name is printed."""
        stream_call_count = [0]

        def stream_side_effect(request, print_stream=False):
            stream_call_count[0] += 1
            if stream_call_count[0] == 1:
                return [
                    make_tool_event(id="t1", name="my_tool", input_str="{}"),
                    make_stop_event(),
                ]
            else:
                return [make_text_event("done"), make_stop_event()]

        runtime.api_client.stream.side_effect = stream_side_effect

        with patch('builtins.print') as mock_print:
            runtime.run_turn("test")

        tool_print_calls = [c for c in mock_print.call_args_list
                            if 'Tool:' in str(c)]
        assert len(tool_print_calls) >= 1

    def test_tool_error_prints(self, runtime):
        """When print_stream=True and tool errors, error is printed."""
        runtime.tool_executor.execute.return_value = ("Error: something failed", True)

        stream_call_count = [0]

        def stream_side_effect(request, print_stream=False):
            stream_call_count[0] += 1
            if stream_call_count[0] == 1:
                return [
                    make_tool_event(id="t1", name="failing_tool", input_str="{}"),
                    make_stop_event(),
                ]
            else:
                return [make_text_event("error handled"), make_stop_event()]

        runtime.api_client.stream.side_effect = stream_side_effect

        with patch('builtins.print') as mock_print:
            runtime.run_turn("test")

        error_print_calls = [c for c in mock_print.call_args_list
                             if 'Tool Error' in str(c)]
        assert len(error_print_calls) >= 1


# ==================== _maybe_auto_compact with print_stream=True ====================

class TestMaybeAutoCompactPrintStream:
    """Test _maybe_auto_compact when print_stream=True."""

    @pytest.fixture
    def runtime(self, mock_session, mock_api_client, mock_tool_executor, mock_tool_registry):
        return ConversationRuntime(
            session=mock_session,
            api_client=mock_api_client,
            tool_executor=mock_tool_executor,
            tool_registry=mock_tool_registry,
            system_prompt="sys",
            model="m",
            auto_compaction_threshold=1000,
            print_stream=True,  # key difference
        )

    def test_auto_compact_prints(self, runtime):
        """When print_stream=True, auto-compaction prints message."""
        runtime.session.total_estimated_tokens.return_value = 1500

        mock_compacted_session = MagicMock(spec=Session)
        compaction_result = MagicMock()
        compaction_result.removed_message_count = 3
        compaction_result.compacted_session = mock_compacted_session

        with patch('novels_project.runtime.compact_session', return_value=compaction_result):
            with patch('builtins.print') as mock_print:
                result = runtime._maybe_auto_compact()

        assert result is not None
        assert result.removed_message_count == 3
        compaction_calls = [c for c in mock_print.call_args_list
                            if 'Auto-compaction' in str(c)]
        assert len(compaction_calls) >= 1