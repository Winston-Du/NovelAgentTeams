"""
Layer 2: Persistence - Token Usage Tracking

Tracks cumulative and per-turn token usage following agent-harness UsageTracker pattern.
"""
from dataclasses import dataclass, field
from typing import Optional

from .api_client import TokenUsage


@dataclass
class UsageTracker:
    latest_turn: TokenUsage = field(default_factory=TokenUsage)
    cumulative: TokenUsage = field(default_factory=TokenUsage)
    turns: int = 0

    def record(self, usage: TokenUsage):
        """Record usage from an API call."""
        self.latest_turn = usage
        self.cumulative = self.cumulative + usage
        self.turns += 1

    def cumulative_usage(self) -> TokenUsage:
        return self.cumulative

    def format_cost_report(self) -> str:
        """Format a human-readable cost report."""
        c = self.cumulative
        report = f"Token Usage ({self.turns} turns)\n"
        report += f"  Input:  {c.input_tokens:,}\n"
        report += f"  Output: {c.output_tokens:,}\n"
        report += f"  Total:  {c.total_tokens:,}\n"
        return report

    @classmethod
    def from_session(cls, session) -> "UsageTracker":
        """Rebuild usage tracker from session messages."""
        tracker = cls()
        for msg in session.messages:
            if msg.usage:
                tracker.record(msg.usage)
        return tracker
