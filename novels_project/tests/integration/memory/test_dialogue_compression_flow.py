"""Task 16: 对话压缩与降级流程端到端集成测试。

验证:
1. LLM 总是失败时 → 重试后降级为规则压缩
2. LLM 成功时 → 不降级，一次调用完成
3. LLM 部分失败时 → 重试后成功，不降级
"""
from __future__ import annotations

import pytest
from novels_project.memory.dialogue_compactor import DialogueCompactor
from novels_project.memory.memory_config import MemoryConfig
from novels_project.session import Session, ConversationMessage, MessageRole, TextBlock
from novels_project.api_client import TextDelta


# ---------------------------------------------------------------------------
# Mock
# ---------------------------------------------------------------------------

class FailingLLM:
    """前 N 次调用抛异常，之后成功的模拟 LLM。"""

    def __init__(self, fail_count: int = 2):
        self.call_count = 0
        self.fail_count = fail_count

    def stream(self, request, print_stream=False):
        self.call_count += 1
        if self.call_count <= self.fail_count:
            raise RuntimeError("Mock LLM failure")
        return [
            TextDelta(text='{"characters": [], "active_topics": [], '
                       '"pending_tasks": [], "completed_tasks": [], '
                       '"key_decisions": [], "unresolved_questions": [], '
                       '"context_summary": "ok"}'),
        ]


def _make_session(msg_count: int) -> Session:
    """构造一个包含 N 条消息的 Session，每条消息长度确保 token 估算充足。"""
    messages = [
        ConversationMessage(
            role=MessageRole.USER,
            blocks=[TextBlock(text=f"message {i}: " + "word " * 10)],
        )
        for i in range(msg_count)
    ]
    return Session(messages=messages)


# ---------------------------------------------------------------------------
# 场景 1: LLM 总是失败 → 重试后降级为规则压缩
# ---------------------------------------------------------------------------

def test_failing_llm_retries_then_falls_back():
    """LLM 始终失败时，重试后降级为规则压缩，仍能移除消息。"""
    config = MemoryConfig(
        preserve_recent_messages=4,
        dialogue_compression_threshold=0.1,  # 低阈值确保触发
    )
    failing_llm = FailingLLM(fail_count=10)  # 总是失败
    compactor = DialogueCompactor(config=config, llm_client=failing_llm)
    session = _make_session(20)

    result = compactor.compact(session, max_tokens=100)

    # 应回退到规则压缩
    assert result.removed_message_count > 0
    # 应重试 2 次（dialogue_compression_max_retries 默认值）
    assert failing_llm.call_count == 2


# ---------------------------------------------------------------------------
# 场景 2: LLM 一次成功 → 不降级
# ---------------------------------------------------------------------------

def test_successful_llm_does_not_fallback():
    """LLM 一次成功时，不会触发重试或降级。"""
    config = MemoryConfig(
        preserve_recent_messages=4,
        dialogue_compression_threshold=0.1,
    )
    success_llm = FailingLLM(fail_count=0)  # 不失败
    compactor = DialogueCompactor(config=config, llm_client=success_llm)
    session = _make_session(20)

    result = compactor.compact(session, max_tokens=100)

    assert result.removed_message_count > 0
    assert success_llm.call_count == 1  # 只调用一次


# ---------------------------------------------------------------------------
# 场景 3: LLM 第 2 次成功 → 重试后成功，不降级
# ---------------------------------------------------------------------------

def test_retry_then_succeed_does_not_fallback():
    """LLM 第 1 次失败、第 2 次成功时，通过重试恢复，不降级。"""
    config = MemoryConfig(
        preserve_recent_messages=4,
        dialogue_compression_threshold=0.1,
    )
    retry_llm = FailingLLM(fail_count=1)  # 第 1 次失败
    compactor = DialogueCompactor(config=config, llm_client=retry_llm)
    session = _make_session(20)

    result = compactor.compact(session, max_tokens=100)

    assert result.removed_message_count > 0
    assert retry_llm.call_count == 2  # 第 1 次失败 + 第 2 次成功
