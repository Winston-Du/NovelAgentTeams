"""
Layer 2: Persistence - Session Compaction

Rules-based context compression following agent-harness patterns.
When cumulative tokens exceed threshold, older messages are summarized
into a single system message, preserving recent context.
"""
from dataclasses import dataclass
from typing import Optional
from collections import Counter

from .session import (
    Session, ConversationMessage, MessageRole,
    TextBlock, ToolUseBlock, ToolResultBlock, ContentBlock,
)


@dataclass
class CompactionConfig:
    preserve_recent_messages: int = 4
    max_summary_chars: int = 4000


@dataclass
class CompactionResult:
    compacted_session: Session
    removed_message_count: int
    summary_text: str


def estimate_message_tokens(msg: ConversationMessage) -> int:
    """Estimate tokens using len/4 heuristic."""
    total = 0
    for block in msg.blocks:
        if isinstance(block, TextBlock):
            total += len(block.text) // 4
        elif isinstance(block, ToolUseBlock):
            total += len(block.input) // 4
        elif isinstance(block, ToolResultBlock):
            total += len(block.output) // 4
    return total


def compact_session(
    session: Session,
    config: CompactionConfig = CompactionConfig(),
) -> CompactionResult:
    """
    Rules-based compaction:
    1. Keep last N messages intact
    2. Summarize older messages into a System message

    Summary includes: message counts, tools used, recent user requests, key content.
    """
    messages = session.messages
    preserve_count = config.preserve_recent_messages

    if len(messages) <= preserve_count:
        return CompactionResult(
            compacted_session=session,
            removed_message_count=0,
            summary_text="",
        )

    # Split: older messages to summarize, recent to keep
    to_summarize = messages[:-preserve_count]
    to_keep = messages[-preserve_count:]

    # Build summary
    summary = _build_summary(to_summarize, config.max_summary_chars)

    # Create compacted session
    summary_msg = ConversationMessage(
        role=MessageRole.SYSTEM,
        blocks=[TextBlock(text=summary)],
    )

    compacted = Session(
        version=session.version,
        messages=[summary_msg] + to_keep,
    )

    return CompactionResult(
        compacted_session=compacted,
        removed_message_count=len(to_summarize),
        summary_text=summary,
    )


def _build_summary(messages: list[ConversationMessage], max_chars: int) -> str:
    """Build a rules-based summary of older messages."""
    role_counts = Counter()
    tools_mentioned = set()
    user_requests = []
    key_content_snippets = []

    for msg in messages:
        role_counts[msg.role.value] += 1

        for block in msg.blocks:
            if isinstance(block, TextBlock):
                text = block.text.strip()
                if msg.role == MessageRole.USER and text:
                    user_requests.append(text[:160])
                elif msg.role == MessageRole.ASSISTANT and text:
                    key_content_snippets.append(text[:200])
            elif isinstance(block, ToolUseBlock):
                tools_mentioned.add(block.name)
            elif isinstance(block, ToolResultBlock):
                tools_mentioned.add(block.tool_name)

    parts = []
    parts.append(f"<compaction_summary>")
    parts.append(f"Conversation summary ({len(messages)} earlier messages compacted):")

    # Message breakdown
    counts_str = ", ".join(f"{k}={v}" for k, v in sorted(role_counts.items()))
    parts.append(f"- Messages: {counts_str}")

    # Tools used
    if tools_mentioned:
        parts.append(f"- Tools used: {', '.join(sorted(tools_mentioned))}")

    # Recent user requests (last 3)
    if user_requests:
        parts.append("- User requests:")
        for req in user_requests[-3:]:
            parts.append(f"  - {req}")

    # Key content (last 2 assistant snippets)
    if key_content_snippets:
        parts.append("- Recent work:")
        for snippet in key_content_snippets[-2:]:
            parts.append(f"  - {snippet}")

    parts.append(f"</compaction_summary>")

    summary = "\n".join(parts)

    # Truncate if too long
    if len(summary) > max_chars:
        summary = summary[:max_chars] + "\n... (truncated)"

    return summary
