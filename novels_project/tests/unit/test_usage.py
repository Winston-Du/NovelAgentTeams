"""
单元测试：用量追踪模块

测试范围：
1. UsageTracker dataclass 的所有方法
"""
from novels_project.api_client import TokenUsage
from novels_project.usage import UsageTracker
from novels_project.session import Session, ConversationMessage, MessageRole


class TestUsageTrackerInit:
    """测试 UsageTracker 初始化"""

    def test_default_init(self):
        """默认初始化"""
        tracker = UsageTracker()
        assert tracker.turns == 0
        assert tracker.latest_turn.input_tokens == 0
        assert tracker.latest_turn.output_tokens == 0
        assert tracker.latest_turn.total_tokens == 0
        assert tracker.cumulative.input_tokens == 0
        assert tracker.cumulative.output_tokens == 0
        assert tracker.cumulative.total_tokens == 0

    def test_custom_init(self):
        """自定义初始化"""
        usage = TokenUsage(input_tokens=10, output_tokens=20, total_tokens=30)
        tracker = UsageTracker(latest_turn=usage, cumulative=usage, turns=5)
        assert tracker.turns == 5
        assert tracker.latest_turn.total_tokens == 30
        assert tracker.cumulative.total_tokens == 30


class TestRecord:
    """测试 record"""

    def test_record_updates_latest_turn(self):
        """record 更新 latest_turn"""
        tracker = UsageTracker()
        usage = TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150)
        tracker.record(usage)
        assert tracker.latest_turn == usage

    def test_record_updates_cumulative(self):
        """record 累加累计用量"""
        tracker = UsageTracker()
        tracker.record(TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150))
        tracker.record(TokenUsage(input_tokens=200, output_tokens=100, total_tokens=300))
        assert tracker.cumulative.input_tokens == 300
        assert tracker.cumulative.output_tokens == 150
        assert tracker.cumulative.total_tokens == 450

    def test_record_increments_turns(self):
        """record 增加 turns 计数"""
        tracker = UsageTracker()
        assert tracker.turns == 0
        tracker.record(TokenUsage(total_tokens=100))
        assert tracker.turns == 1
        tracker.record(TokenUsage(total_tokens=200))
        assert tracker.turns == 2
        tracker.record(TokenUsage(total_tokens=300))
        assert tracker.turns == 3

    def test_record_with_zero_usage(self):
        """零用量"""
        tracker = UsageTracker()
        tracker.record(TokenUsage())
        assert tracker.turns == 1
        assert tracker.cumulative.total_tokens == 0


class TestCumulativeUsage:
    """测试 cumulative_usage"""

    def test_returns_cumulative(self):
        """返回累计用量"""
        tracker = UsageTracker()
        tracker.record(TokenUsage(input_tokens=10, output_tokens=20, total_tokens=30))
        tracker.record(TokenUsage(input_tokens=30, output_tokens=40, total_tokens=70))
        cum = tracker.cumulative_usage()
        assert cum.input_tokens == 40
        assert cum.output_tokens == 60
        assert cum.total_tokens == 100

    def test_empty_cumulative(self):
        """空累计"""
        tracker = UsageTracker()
        cum = tracker.cumulative_usage()
        assert cum.total_tokens == 0
        assert cum.input_tokens == 0
        assert cum.output_tokens == 0


class TestFormatCostReport:
    """测试 format_cost_report"""

    def test_format_basic(self):
        """基本格式化"""
        tracker = UsageTracker()
        tracker.record(TokenUsage(input_tokens=1000, output_tokens=500, total_tokens=1500))
        report = tracker.format_cost_report()
        assert "Token Usage (1 turns)" in report
        assert "Input:  1,000" in report
        assert "Output: 500" in report
        assert "Total:  1,500" in report

    def test_format_multiple_turns(self):
        """多轮格式化"""
        tracker = UsageTracker()
        tracker.record(TokenUsage(input_tokens=500, output_tokens=200, total_tokens=700))
        tracker.record(TokenUsage(input_tokens=500, output_tokens=300, total_tokens=800))
        report = tracker.format_cost_report()
        assert "Token Usage (2 turns)" in report
        assert "Input:  1,000" in report
        assert "Output: 500" in report
        assert "Total:  1,500" in report

    def test_format_empty(self):
        """空用量"""
        tracker = UsageTracker()
        report = tracker.format_cost_report()
        assert "Token Usage (0 turns)" in report
        assert "Input:  0" in report
        assert "Output: 0" in report
        assert "Total:  0" in report

    def test_format_returns_string(self):
        """返回字符串"""
        tracker = UsageTracker()
        result = tracker.format_cost_report()
        assert isinstance(result, str)

    def test_format_large_numbers(self):
        """大数字格式化"""
        tracker = UsageTracker()
        tracker.record(TokenUsage(
            input_tokens=1_000_000,
            output_tokens=500_000,
            total_tokens=1_500_000,
        ))
        report = tracker.format_cost_report()
        assert "Input:  1,000,000" in report
        assert "Total:  1,500,000" in report


class TestFromSession:
    """测试 from_session"""

    def test_from_session_basic(self):
        """从会话重建追踪器"""
        session = Session()
        msg1 = ConversationMessage(
            role=MessageRole.ASSISTANT,
            blocks=[],
            usage=TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150),
        )
        msg2 = ConversationMessage(
            role=MessageRole.ASSISTANT,
            blocks=[],
            usage=TokenUsage(input_tokens=200, output_tokens=100, total_tokens=300),
        )
        session.messages = [msg1, msg2]

        tracker = UsageTracker.from_session(session)
        assert tracker.turns == 2
        assert tracker.cumulative.input_tokens == 300
        assert tracker.cumulative.output_tokens == 150
        assert tracker.cumulative.total_tokens == 450

    def test_from_session_empty(self):
        """空会话"""
        session = Session()
        tracker = UsageTracker.from_session(session)
        assert tracker.turns == 0
        assert tracker.cumulative.total_tokens == 0

    def test_from_session_messages_without_usage(self):
        """消息无 usage"""
        session = Session()
        msg = ConversationMessage.user_text("hello")
        session.messages = [msg]
        tracker = UsageTracker.from_session(session)
        assert tracker.turns == 0
        assert tracker.cumulative.total_tokens == 0

    def test_from_session_mixed_messages(self):
        """混合消息（有 usage 和无 usage）"""
        session = Session()
        session.messages = [
            ConversationMessage.user_text("user message"),
            ConversationMessage(
                role=MessageRole.ASSISTANT,
                blocks=[],
                usage=TokenUsage(input_tokens=50, output_tokens=25, total_tokens=75),
            ),
            ConversationMessage.user_text("another user message"),
            ConversationMessage(
                role=MessageRole.ASSISTANT,
                blocks=[],
                usage=TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150),
            ),
        ]

        tracker = UsageTracker.from_session(session)
        assert tracker.turns == 2
        assert tracker.cumulative.total_tokens == 225

    def test_from_session_single_message(self):
        """单条消息"""
        session = Session()
        session.messages = [
            ConversationMessage(
                role=MessageRole.ASSISTANT,
                blocks=[],
                usage=TokenUsage(input_tokens=10, output_tokens=20, total_tokens=30),
            )
        ]
        tracker = UsageTracker.from_session(session)
        assert tracker.turns == 1
        assert tracker.latest_turn.total_tokens == 30

    def test_from_session_returns_usage_tracker(self):
        """返回 UsageTracker 实例"""
        session = Session()
        tracker = UsageTracker.from_session(session)
        assert isinstance(tracker, UsageTracker)


class TestUsageTrackerEdgeCases:
    """边缘情况"""

    def test_record_preserves_previous_latest(self):
        """record 保留每个 turn 的最新"""
        tracker = UsageTracker()
        usage1 = TokenUsage(input_tokens=10, output_tokens=20, total_tokens=30)
        usage2 = TokenUsage(input_tokens=40, output_tokens=50, total_tokens=90)
        tracker.record(usage1)
        tracker.record(usage2)
        assert tracker.latest_turn == usage2
        # cumulative should be sum
        assert tracker.cumulative.total_tokens == 120

    def test_cumulative_usage_is_independent(self):
        """cumulative_usage 返回同一累计对象（dataclass 可共享引用）"""
        tracker = UsageTracker()
        tracker.record(TokenUsage(total_tokens=100))
        cum = tracker.cumulative_usage()
        # 返回的是同一个 cumulative 对象（dataclass 非 frozen）
        assert cum is tracker.cumulative
        assert cum.total_tokens == 100