"""
单元测试：Compaction 模块测试

测试范围：
1. estimate_message_tokens
2. compact_session
3. _build_summary
"""

from novels_project.compaction import (
    CompactionConfig,
    CompactionResult,
    estimate_message_tokens,
    compact_session,
    _build_summary,
)
from novels_project.session import (
    Session,
    ConversationMessage,
    MessageRole,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock,
    ContentBlock,
)


# ==================== estimate_message_tokens ====================

class TestEstimateMessageTokens:
    """测试 estimate_message_tokens"""

    def test_text_block(self):
        msg = ConversationMessage.user_text("Hello world")  # 11//4 = 2
        assert estimate_message_tokens(msg) == 2

    def test_tool_use_block(self):
        msg = ConversationMessage(
            role=MessageRole.ASSISTANT,
            blocks=[ToolUseBlock(id="t1", name="search", input='{"query":"test"}')],  # 16//4 = 4
        )
        assert estimate_message_tokens(msg) == 4

    def test_tool_result_block(self):
        msg = ConversationMessage.tool_result("t1", "search", "results found")  # 13//4 = 3
        assert estimate_message_tokens(msg) == 3

    def test_mixed_blocks(self):
        msg = ConversationMessage(
            role=MessageRole.ASSISTANT,
            blocks=[
                TextBlock(text="Let me search."),  # 13//4 = 3
                ToolUseBlock(id="t1", name="s", input='{"q":"x"}'),  # 9//4 = 2
            ],
        )
        assert estimate_message_tokens(msg) == 5

    def test_short_text_rounds_down(self):
        msg = ConversationMessage.user_text("abc")  # 3//4 = 0
        assert estimate_message_tokens(msg) == 0

    def test_empty_text(self):
        msg = ConversationMessage.user_text("")
        assert estimate_message_tokens(msg) == 0

    def test_multiple_tool_uses(self):
        msg = ConversationMessage(
            role=MessageRole.ASSISTANT,
            blocks=[
                ToolUseBlock(id="t1", name="a", input="x" * 8),   # 8//4 = 2
                ToolUseBlock(id="t2", name="b", input="y" * 12),  # 12//4 = 3
            ],
        )
        assert estimate_message_tokens(msg) == 5

    def test_multiple_tool_results(self):
        msg = ConversationMessage(
            role=MessageRole.TOOL,
            blocks=[
                ToolResultBlock(tool_use_id="t1", tool_name="a", output="A" * 16),  # 4
                ToolResultBlock(tool_use_id="t2", tool_name="b", output="B" * 20),  # 5
            ],
        )
        assert estimate_message_tokens(msg) == 9

    def test_unknown_block_skipped(self):
        """Blocks that are not TextBlock, ToolUseBlock, or ToolResultBlock are skipped."""
        class CustomBlock(ContentBlock):
            pass

        msg = ConversationMessage(
            role=MessageRole.USER,
            blocks=[CustomBlock(), TextBlock(text="hello")],  # 5//4 = 1
        )
        assert estimate_message_tokens(msg) == 1


# ==================== compact_session ====================

def _make_session(msg_count: int) -> Session:
    """Helper: create a session with N user messages."""
    messages = [
        ConversationMessage.user_text(f"Message {i}") for i in range(msg_count)
    ]
    return Session(messages=messages)


class TestCompactSession:
    """测试 compact_session"""

    def test_no_compaction_needed(self):
        """Messages <= preserve_count: no compaction."""
        session = _make_session(3)
        config = CompactionConfig(preserve_recent_messages=4)
        result = compact_session(session, config)
        assert result.removed_message_count == 0
        assert result.summary_text == ""
        assert result.compacted_session is session  # Same object
        assert result.compacted_session.message_count() == 3

    def test_compaction_exactly_at_threshold(self):
        """Messages == preserve_count: no compaction."""
        session = _make_session(4)
        config = CompactionConfig(preserve_recent_messages=4)
        result = compact_session(session, config)
        assert result.removed_message_count == 0
        assert result.compacted_session is session

    def test_compaction_one_extra(self):
        """5 messages, preserve 4: 1 compacted."""
        session = _make_session(5)
        config = CompactionConfig(preserve_recent_messages=4)
        result = compact_session(session, config)
        assert result.removed_message_count == 1
        assert result.summary_text != ""
        assert result.compacted_session is not session
        # Structure: 1 summary (SYSTEM) + 4 recent messages
        assert result.compacted_session.message_count() == 5
        assert result.compacted_session.messages[0].role == MessageRole.SYSTEM
        assert result.compacted_session.messages[1].role == MessageRole.USER
        assert result.compacted_session.messages[4].role == MessageRole.USER

    def test_compaction_many_extra(self):
        """10 messages, preserve 2: 8 compacted."""
        session = _make_session(10)
        config = CompactionConfig(preserve_recent_messages=2)
        result = compact_session(session, config)
        assert result.removed_message_count == 8
        assert result.compacted_session.message_count() == 3  # 1 summary + 2 recent
        assert result.compacted_session.messages[0].role == MessageRole.SYSTEM
        # Recent messages preserved
        assert result.compacted_session.messages[1].get_text() == "Message 8"
        assert result.compacted_session.messages[2].get_text() == "Message 9"

    def test_compaction_version_preserved(self):
        session = Session(version=5, messages=[
            ConversationMessage.user_text(f"Msg {i}") for i in range(6)
        ])
        config = CompactionConfig(preserve_recent_messages=3)
        result = compact_session(session, config)
        assert result.compacted_session.version == 5

    def test_compaction_default_config(self):
        """With default config: preserve_recent_messages=4."""
        session = _make_session(6)
        result = compact_session(session)
        assert result.removed_message_count == 2
        # 1 summary + 4 recent = 5
        assert result.compacted_session.message_count() == 5

    def test_summary_includes_role_counts(self):
        # Place tool_result earlier so it falls into the summarized set
        session = Session(messages=[
            ConversationMessage.user_text("User request 1"),
            ConversationMessage.user_text("User request 2"),
            ConversationMessage.tool_result("t1", "search", "results"),
            ConversationMessage(
                role=MessageRole.ASSISTANT,
                blocks=[TextBlock(text="Assistant response")],
            ),
            ConversationMessage.user_text("User request 3"),
            ConversationMessage.user_text("User request 4"),
            ConversationMessage.user_text("User request 5"),
        ])
        config = CompactionConfig(preserve_recent_messages=2)
        result = compact_session(session, config)
        summary = result.summary_text
        # Should mention role counts
        assert "user" in summary.lower() or "Messages" in summary
        assert "assistant" in summary.lower()
        assert "tool" in summary.lower()
        assert "<compaction_summary>" in summary
        assert "</compaction_summary>" in summary

    def test_summary_includes_tool_names(self):
        session = Session(messages=[
            ConversationMessage(
                role=MessageRole.ASSISTANT,
                blocks=[ToolUseBlock(id="t1", name="search", input='{"q":"x"}')],
            ),
            ConversationMessage.tool_result("t1", "search", "found"),
            ConversationMessage(
                role=MessageRole.ASSISTANT,
                blocks=[ToolUseBlock(id="t2", name="get_weather", input='{"city":"NY"}')],
            ),
            ConversationMessage.tool_result("t2", "get_weather", "sunny"),
            ConversationMessage.user_text("Final message"),
        ])
        config = CompactionConfig(preserve_recent_messages=1)
        result = compact_session(session, config)
        summary = result.summary_text
        assert "search" in summary
        assert "get_weather" in summary

    def test_summary_includes_user_requests(self):
        session = Session(messages=[
            ConversationMessage.user_text("Write chapter 1"),
            ConversationMessage.user_text("Add more detail"),
            ConversationMessage.user_text("Fix the grammar"),
            ConversationMessage.user_text("Keep message"),
        ])
        config = CompactionConfig(preserve_recent_messages=1)
        result = compact_session(session, config)
        summary = result.summary_text
        assert "User requests" in summary
        # Only last 3 user requests from compacted messages
        assert "Write chapter 1" in summary
        assert "Add more detail" in summary
        assert "Fix the grammar" in summary
        # Last one is preserved, not summarized
        assert "Keep message" not in summary

    def test_summary_includes_key_content(self):
        session = Session(messages=[
            ConversationMessage(
                role=MessageRole.ASSISTANT,
                blocks=[TextBlock(text="First assistant snippet with some key output.")],
            ),
            ConversationMessage(
                role=MessageRole.ASSISTANT,
                blocks=[TextBlock(text="Second assistant snippet here.")],
            ),
            ConversationMessage.user_text("Final"),
        ])
        config = CompactionConfig(preserve_recent_messages=1)
        result = compact_session(session, config)
        summary = result.summary_text
        assert "Recent work" in summary
        assert "key output" in summary

    def test_summary_truncation_when_exceeding_max_chars(self):
        """When summary exceeds max_summary_chars, it gets truncated."""
        # Create many long messages to generate a large summary
        messages = []
        for i in range(20):
            messages.append(ConversationMessage.user_text(f"Long user message number {i}: " + "Hello world " * 80))
            messages.append(ConversationMessage(
                role=MessageRole.ASSISTANT,
                blocks=[TextBlock(text=f"Long assistant response number {i}: " + "Result found " * 60)],
            ))
            messages.append(ConversationMessage(
                role=MessageRole.ASSISTANT,
                blocks=[ToolUseBlock(id=f"t{i}a", name=f"tool_{i}", input=f'{{"data_{i}":"{"x"*50}"}}')],
            ))
            messages.append(ConversationMessage.tool_result(f"t{i}a", f"tool_{i}", f"Output_{i} " * 30))
        session = Session(messages=messages)
        config = CompactionConfig(preserve_recent_messages=1, max_summary_chars=500)
        result = compact_session(session, config)
        summary = result.summary_text
        assert len(summary) <= 500 + len("\n... (truncated)")
        assert summary.endswith("... (truncated)")

    def test_short_summary_no_truncation(self):
        """Summary within max_chars should not be truncated."""
        session = Session(messages=[
            ConversationMessage.user_text("Hi"),
            ConversationMessage.user_text("Keep"),
        ])
        config = CompactionConfig(preserve_recent_messages=1, max_summary_chars=4000)
        result = compact_session(session, config)
        summary = result.summary_text
        assert "... (truncated)" not in summary


# ==================== _build_summary ====================

class TestBuildSummary:
    """测试 _build_summary"""

    def test_user_messages(self):
        messages = [
            ConversationMessage.user_text("Write a story"),
            ConversationMessage.user_text("About dragons"),
        ]
        summary = _build_summary(messages, 4000)
        assert "user=2" in summary
        assert "Write a story" in summary
        assert "About dragons" in summary

    def test_assistant_messages(self):
        messages = [
            ConversationMessage(
                role=MessageRole.ASSISTANT,
                blocks=[TextBlock(text="Here is the chapter content.")],
            ),
        ]
        summary = _build_summary(messages, 4000)
        assert "assistant=1" in summary
        assert "Recent work" in summary
        assert "Here is the chapter content." in summary

    def test_tool_use_tool_results(self):
        messages = [
            ConversationMessage(
                role=MessageRole.ASSISTANT,
                blocks=[ToolUseBlock(id="t1", name="search", input='{}')],
            ),
            ConversationMessage.tool_result("t1", "search", "found"),
            ConversationMessage(
                role=MessageRole.ASSISTANT,
                blocks=[ToolUseBlock(id="t2", name="get_weather", input='{}')],
            ),
            ConversationMessage.tool_result("t2", "get_weather", "sunny"),
        ]
        summary = _build_summary(messages, 4000)
        assert "assistant=2" in summary
        assert "tool=2" in summary
        assert "Tools used" in summary
        assert "get_weather" in summary
        assert "search" in summary

    def test_mixed_messages(self):
        messages = [
            ConversationMessage.user_text("Write chapter 1"),
            ConversationMessage(
                role=MessageRole.ASSISTANT,
                blocks=[
                    TextBlock(text="Writing chapter 1 content."),
                    ToolUseBlock(id="t1", name="check_voice", input='{}'),
                ],
            ),
            ConversationMessage.tool_result("t1", "check_voice", "OK"),
            ConversationMessage(
                role=MessageRole.ASSISTANT,
                blocks=[TextBlock(text="Content finished.")],
            ),
        ]
        summary = _build_summary(messages, 4000)
        assert "user=1" in summary
        assert "assistant=2" in summary
        assert "tool=1" in summary
        assert "check_voice" in summary
        assert "Write chapter 1" in summary
        assert "Writing chapter" in summary
        assert "Content finished" in summary

    def test_empty_messages(self):
        summary = _build_summary([], 4000)
        assert "0 earlier messages" in summary
        assert "user" not in summary.split("- Messages: ")[1] if "- Messages:" in summary else True

    def test_no_tools_used(self):
        messages = [
            ConversationMessage.user_text("Hello"),
            ConversationMessage.assistant([TextBlock(text="Hi there!")]),
        ]
        summary = _build_summary(messages, 4000)
        assert "Tools used" not in summary

    def test_no_user_requests(self):
        messages = [
            ConversationMessage.assistant([TextBlock(text="Auto response")]),
        ]
        summary = _build_summary(messages, 4000)
        assert "User requests" not in summary

    def test_no_assistant_snippets(self):
        messages = [
            ConversationMessage.user_text("Query only"),
        ]
        summary = _build_summary(messages, 4000)
        assert "Recent work" not in summary

    def test_user_text_truncation(self):
        """User messages are truncated to 160 chars in summary."""
        long_text = "A" * 200
        messages = [ConversationMessage.user_text(long_text)]
        summary = _build_summary(messages, 4000)
        assert "A" * 160 in summary
        assert "A" * 161 not in summary

    def test_assistant_text_truncation(self):
        """Assistant messages are truncated to 200 chars in summary."""
        long_text = "B" * 300
        messages = [
            ConversationMessage(
                role=MessageRole.ASSISTANT,
                blocks=[TextBlock(text=long_text)],
            ),
        ]
        summary = _build_summary(messages, 4000)
        assert "B" * 200 in summary
        assert "B" * 201 not in summary

    def test_truncation_with_max_chars(self):
        long_text = "X" * 500
        messages = [ConversationMessage.user_text(long_text)]
        summary = _build_summary(messages, max_chars=50)
        assert len(summary) <= 50 + len("\n... (truncated)")
        assert "... (truncated)" in summary

    def test_structure_format(self):
        messages = [
            ConversationMessage.user_text("Hello"),
            ConversationMessage.assistant([TextBlock(text="Response")]),
        ]
        summary = _build_summary(messages, 4000)
        assert summary.startswith("<compaction_summary>")
        assert summary.endswith("</compaction_summary>")
        assert "Conversation summary" in summary
        assert "- Messages:" in summary

    def test_non_user_assistant_text_block(self):
        """TextBlock with role that is not USER and not ASSISTANT (e.g. SYSTEM)."""
        messages = [
            ConversationMessage(
                role=MessageRole.SYSTEM,
                blocks=[TextBlock(text="System prompt text")],
            ),
            ConversationMessage(
                role=MessageRole.TOOL,
                blocks=[TextBlock(text="Tool text")],
            ),
        ]
        summary = _build_summary(messages, 4000)
        assert "system=1" in summary
        assert "tool=1" in summary

    def test_unknown_block_skipped_in_summary(self):
        """Blocks that are not TextBlock, ToolUseBlock, or ToolResultBlock are skipped."""
        class CustomBlock(ContentBlock):
            pass

        messages = [
            ConversationMessage(
                role=MessageRole.USER,
                blocks=[CustomBlock(), TextBlock(text="Hello")],
            ),
        ]
        summary = _build_summary(messages, 4000)
        assert "user=1" in summary


# ==================== CompactionConfig ====================

class TestCompactionConfig:
    """测试 CompactionConfig"""

    def test_default_values(self):
        config = CompactionConfig()
        assert config.preserve_recent_messages == 4
        assert config.max_summary_chars == 4000

    def test_custom_values(self):
        config = CompactionConfig(preserve_recent_messages=10, max_summary_chars=8000)
        assert config.preserve_recent_messages == 10
        assert config.max_summary_chars == 8000


# ==================== CompactionResult ====================

class TestCompactionResult:
    """测试 CompactionResult"""

    def test_result_fields(self):
        session = Session()
        result = CompactionResult(
            compacted_session=session,
            removed_message_count=5,
            summary_text="Summary of 5 messages.",
        )
        assert result.compacted_session is session
        assert result.removed_message_count == 5
        assert result.summary_text == "Summary of 5 messages."

    def test_result_zero_removed(self):
        session = Session()
        result = CompactionResult(
            compacted_session=session,
            removed_message_count=0,
            summary_text="",
        )
        assert result.removed_message_count == 0
        assert result.summary_text == ""