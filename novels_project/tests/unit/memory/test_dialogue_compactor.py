"""DialogueCompactor 主体逻辑测试。

覆盖 5 大场景：
1. should_compress 阈值判断
2. compact 主流程（不触发 / 触发 / 消息过少 no-op）
3. _llm_compress_with_retry 重试机制
4. _parse_summary_from_text JSON 解析（标准/损坏/语法错）
5. LLM fallback 路径（流中断/异常）
6. 端到端：标准流式 → DialogueSummary → render → CompactionResult
7. 日志验证（caplog）
"""
import json
import logging
import pytest

from novels_project.memory.dialogue_compactor import DialogueCompactor
from novels_project.memory.dialogue_summary import DialogueSummary
from novels_project.memory.memory_config import MemoryConfig
from novels_project.compaction import (
    CompactionResult, ConversationMessage, TextBlock, MessageRole, Session,
)
from novels_project.api_client import TextDelta, MessageStop


# === Mock LLM 工具 ===

def make_streaming_client(events: list):
    """构造返回 events 列表的 mock LLM 客户端。"""
    class MockLLM:
        default_model = "mock-llm"
        def __init__(self, evts):
            self._events = evts
        def stream(self, request, print_stream: bool = False):
            return list(self._events)
    return MockLLM(events)


def make_json_text_response(data: dict) -> str:
    """构造 LLM 风格的 JSON 响应（带 ```json 包裹）。"""
    return f"""好的，这是结构化摘要：

```json
{json.dumps(data, ensure_ascii=False, indent=2)}
```

以上。"""


def make_message_text(role: str, text: str) -> ConversationMessage:
    """构造会话消息。"""
    role_map = {"user": MessageRole.USER, "assistant": MessageRole.ASSISTANT, "system": MessageRole.SYSTEM}
    return ConversationMessage(role=role_map[role], blocks=[TextBlock(text=text)])


# === 场景 1: should_compress 阈值 ===

def test_should_compress_below_threshold():
    """estimated < threshold 时不触发。"""
    cfg = MemoryConfig(dialogue_compression_threshold=0.8)
    compactor = DialogueCompactor(config=cfg)
    session = Session(messages=[
        make_message_text("user", "短消息"),  # 2 chars → 0 tokens
    ])
    # max_tokens=1000 → 80% = 800 tokens 触发线
    # 0 < 800 → 不触发
    assert compactor.should_compress(session, max_tokens=1000) is False


def test_should_compress_above_threshold():
    """estimated >= threshold 时触发。"""
    cfg = MemoryConfig(dialogue_compression_threshold=0.8)
    compactor = DialogueCompactor(config=cfg)
    # 构造 2500 tokens 的消息（每条 100 字符 = 25 tokens × 100 = 2500）
    msgs = [
        make_message_text("user", "x" * 100) for _ in range(100)
    ]
    session = Session(messages=msgs)
    # max_tokens=3000 → 80% = 2400 < 2500 → 触发
    assert compactor.should_compress(session, max_tokens=3000) is True
    # max_tokens=5000 → 80% = 4000 < 2500 → 不触发
    assert compactor.should_compress(session, max_tokens=5000) is False


# === 场景 2: compact 主流程 ===

def test_compact_below_threshold_no_op():
    """未达阈值时 compact() 不应修改 session。"""
    cfg = MemoryConfig(dialogue_compression_threshold=0.8, preserve_recent_messages=4)
    compactor = DialogueCompactor(config=cfg)
    msgs = [make_message_text("user", "hi") for _ in range(3)]
    session = Session(messages=msgs)
    result = compactor.compact(session, max_tokens=10000)
    assert isinstance(result, CompactionResult)
    assert result.removed_message_count == 0
    assert result.summary_text == ""
    assert result.compacted_session is session


def test_compact_below_messages_count_no_op():
    """消息数 <= preserve_count 时不压缩。"""
    cfg = MemoryConfig(dialogue_compression_threshold=0.5, preserve_recent_messages=4)
    compactor = DialogueCompactor(config=cfg)
    msgs = [make_message_text("user", f"m{i}") for i in range(3)]
    session = Session(messages=msgs)
    # max_tokens=10 强制触发
    result = compactor.compact(session, max_tokens=10)
    assert result.removed_message_count == 0
    assert result.summary_text == ""


def test_compact_preserves_recent_messages():
    """压缩后保留最近 N 条原始消息。"""
    cfg = MemoryConfig(
        preserve_recent_messages=4,
        dialogue_compression_threshold=0.5,
    )
    compactor = DialogueCompactor(config=cfg)
    msgs = [make_message_text("user", f"msg {i}") for i in range(20)]
    session = Session(messages=msgs)
    result = compactor.compact(session, max_tokens=10)  # 强制触发
    # 20 - 4 = 16 移除，1 摘要 + 4 原始 = 5 总数
    assert result.removed_message_count == 16
    assert len(result.compacted_session.messages) == 5
    # 最后一条应是 msg 19
    last = result.compacted_session.messages[-1]
    assert last.get_text() == "msg 19"
    # 第一条应是 system 摘要
    first = result.compacted_session.messages[0]
    assert first.role == MessageRole.SYSTEM


def test_compact_no_llm_client_uses_fallback():
    """无 LLM 客户端时应直接走 fallback。"""
    cfg = MemoryConfig(
        preserve_recent_messages=4,
        dialogue_compression_threshold=0.5,
    )
    compactor = DialogueCompactor(config=cfg, llm_client=None)
    # 使用长消息确保 total_estimated_tokens() 触发阈值
    msgs = [make_message_text("user", f"m{i} " * 20) for i in range(20)]
    session = Session(messages=msgs)
    result = compactor.compact(session, max_tokens=10)
    # fallback 路径应仍能完成压缩
    assert result.removed_message_count == 16
    assert result.summary_text  # 非空


# === 场景 3: _llm_compress_with_retry 重试机制 ===

def test_llm_compress_succeeds_first_attempt():
    """第一次 LLM 调用成功。"""
    cfg = MemoryConfig()
    data = {"characters": ["陆商曜"], "context_summary": "脉络"}
    json_text = make_json_text_response(data)
    # 分片流
    events = [
        TextDelta(text=json_text[:30]),
        TextDelta(text=json_text[30:]),
        MessageStop(),
    ]
    mock = make_streaming_client(events)
    compactor = DialogueCompactor(config=cfg, llm_client=mock)
    summary = compactor._llm_compress_with_retry(conversation="对话文本")
    assert isinstance(summary, DialogueSummary)
    assert summary.characters == ["陆商曜"]


def test_llm_compress_retries_on_failure():
    """第一次 LLM 失败、第二次成功。"""
    cfg = MemoryConfig(dialogue_compression_max_retries=2)
    data = {"characters": ["周桓"], "context_summary": "脉络2"}
    json_text = make_json_text_response(data)

    call_count = {"n": 0}
    class FlakyLLM:
        default_model = "mock-llm"
        def stream(self, request, print_stream: bool = False):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise ConnectionError("网络抖动")
            return [
                TextDelta(text=json_text[:30]),
                TextDelta(text=json_text[30:]),
                MessageStop(),
            ]

    compactor = DialogueCompactor(config=cfg, llm_client=FlakyLLM())
    summary = compactor._llm_compress_with_retry(conversation="对话")
    assert call_count["n"] == 2  # 第二次成功
    assert summary.characters == ["周桓"]


def test_llm_compress_raises_after_max_retries():
    """达到最大重试次数后应抛 DialogueCompressionError。"""
    from novels_project.memory.compression_exceptions import DialogueCompressionError
    cfg = MemoryConfig(dialogue_compression_max_retries=2)

    class AlwaysFailLLM:
        default_model = "mock-llm"
        def stream(self, request, print_stream: bool = False):
            raise ConnectionError("持续失败")

    compactor = DialogueCompactor(config=cfg, llm_client=AlwaysFailLLM())
    with pytest.raises(DialogueCompressionError):
        compactor._llm_compress_with_retry(conversation="对话")


# === 场景 4: _parse_summary_from_text JSON 解析 ===

def test_parse_summary_from_text_standard():
    """标准 ```json {...} ``` 块。"""
    cfg = MemoryConfig()
    compactor = DialogueCompactor(config=cfg)
    data = {
        "characters": ["陆商曜", "周桓"],
        "active_topics": ["宗门合并"],
        "context_summary": "讨论框架",
    }
    text = make_json_text_response(data)
    summary = compactor._parse_summary_from_text(text)
    assert summary.characters == ["陆商曜", "周桓"]
    assert summary.context_summary == "讨论框架"


def test_parse_summary_from_text_no_json_block():
    """文本中无 JSON 块时应抛 ValueError。"""
    cfg = MemoryConfig()
    compactor = DialogueCompactor(config=cfg)
    with pytest.raises(ValueError):
        compactor._parse_summary_from_text("没有任何 JSON 内容")


def test_parse_summary_from_text_invalid_json():
    """JSON 语法错误时应抛 json.JSONDecodeError 或 ValueError。"""
    cfg = MemoryConfig()
    compactor = DialogueCompactor(config=cfg)
    broken = "```json\n{invalid json syntax}\n```"
    with pytest.raises((ValueError, json.JSONDecodeError)):
        compactor._parse_summary_from_text(broken)


def test_parse_summary_from_text_empty():
    """空文本应抛 ValueError。"""
    cfg = MemoryConfig()
    compactor = DialogueCompactor(config=cfg)
    with pytest.raises(ValueError):
        compactor._parse_summary_from_text("")


# === 场景 5: Fallback 路径 ===

def test_rule_compress_fallback_uses_from_fallback():
    """fallback 应使用 DialogueSummary.from_fallback。"""
    cfg = MemoryConfig(dialogue_summary_max_chars=500)
    compactor = DialogueCompactor(config=cfg)
    msgs = [
        make_message_text("user", f"m{i} " * 50)  # 长消息
        for i in range(5)
    ]
    summary = compactor._rule_compress_fallback(msgs)
    assert isinstance(summary, DialogueSummary)
    # from_fallback 留空结构化字段
    assert summary.characters == []
    # context_summary 来自 _build_summary
    assert summary.context_summary != ""


def test_compact_falls_back_on_llm_exception():
    """compact 在 LLM 异常时应降级到 fallback。"""
    cfg = MemoryConfig(
        preserve_recent_messages=4,
        dialogue_compression_threshold=0.5,
        dialogue_compression_max_retries=1,  # 加快测试
    )

    class FailLLM:
        default_model = "mock-llm"
        def stream(self, request, print_stream: bool = False):
            raise ConnectionError("LLM 不可用")

    compactor = DialogueCompactor(config=cfg, llm_client=FailLLM())
    msgs = [make_message_text("user", f"m{i} " * 20) for i in range(10)]
    session = Session(messages=msgs)
    result = compactor.compact(session, max_tokens=10)
    # fallback 路径应仍能完成
    assert result.removed_message_count == 6
    assert result.summary_text  # 非空（来自 _build_summary）


def test_compact_falls_back_on_no_json_in_llm_output():
    """LLM 输出无 JSON 块时应降级到 fallback。"""
    cfg = MemoryConfig(
        preserve_recent_messages=4,
        dialogue_compression_threshold=0.5,
        dialogue_compression_max_retries=1,
    )

    class NoJsonLLM:
        default_model = "mock-llm"
        def stream(self, request, print_stream: bool = False):
            return [
                TextDelta(text="我无法生成 JSON"),
                MessageStop(),
            ]

    compactor = DialogueCompactor(config=cfg, llm_client=NoJsonLLM())
    msgs = [make_message_text("user", f"m{i} " * 20) for i in range(10)]
    session = Session(messages=msgs)
    result = compactor.compact(session, max_tokens=10)
    assert result.removed_message_count == 6
    assert result.summary_text


# === 场景 6: _messages_to_text 转换 ===

def test_messages_to_text_format():
    """消息应被格式化为 [role] text 形式。"""
    cfg = MemoryConfig()
    compactor = DialogueCompactor(config=cfg)
    msgs = [
        make_message_text("user", "你好"),
        make_message_text("assistant", "你好"),
    ]
    text = compactor._messages_to_text(msgs)
    assert "[user] 你好" in text
    assert "[assistant] 你好" in text
    assert "\n\n" in text  # 双换行分隔


def test_messages_to_text_skips_empty_text():
    """空 text 的消息应被跳过。"""
    cfg = MemoryConfig()
    compactor = DialogueCompactor(config=cfg)
    msgs = [
        make_message_text("user", ""),  # 空
        make_message_text("user", "有效"),
    ]
    text = compactor._messages_to_text(msgs)
    assert "有效" in text
    # 不应有两个 [user] 标签
    assert text.count("[user]") == 1


# === 场景 7: 端到端 ===

def test_end_to_end_streaming_to_compaction():
    """完整流程：流式 LLM → JSON → DialogueSummary → render → CompactionResult。"""
    cfg = MemoryConfig(
        preserve_recent_messages=4,
        dialogue_compression_threshold=0.5,
        dialogue_summary_max_chars=4000,
    )
    data = {
        "characters": ["陆商曜", "周桓", "李墨"],
        "active_topics": ["宗门合并"],
        "pending_tasks": [{"owner": "agent1", "task": "查询", "status": "todo"}],
        "completed_tasks": ["建卡"],
        "key_decisions": ["用 LLM"],
        "unresolved_questions": ["何时调？"],
        "context_summary": "讨论小说框架",
    }
    json_text = make_json_text_response(data)
    # 分片流
    chunks = [json_text[i:i+50] for i in range(0, len(json_text), 50)]
    events = [TextDelta(text=c) for c in chunks] + [MessageStop()]
    mock = make_streaming_client(events)
    compactor = DialogueCompactor(config=cfg, llm_client=mock)

    msgs = [make_message_text("user", f"m{i} " * 20) for i in range(10)]
    session = Session(messages=msgs)
    result = compactor.compact(session, max_tokens=10)

    assert result.removed_message_count == 6
    assert result.summary_text.startswith("<dialogue_compression>")
    assert "陆商曜" in result.summary_text
    assert "宗门合并" in result.summary_text
    assert len(result.compacted_session.messages) == 5


# === 场景 8: 日志验证 ===

def test_logging_on_compression(caplog):
    """压缩时应输出结构化日志。"""
    cfg = MemoryConfig(
        preserve_recent_messages=4,
        dialogue_compression_threshold=0.5,
    )
    data = {"characters": ["陆"], "context_summary": "脉络"}
    json_text = make_json_text_response(data)
    events = [TextDelta(text=json_text[:30]), TextDelta(text=json_text[30:]), MessageStop()]
    mock = make_streaming_client(events)
    compactor = DialogueCompactor(config=cfg, llm_client=mock)

    msgs = [make_message_text("user", f"m{i}") for i in range(10)]
    session = Session(messages=msgs)

    with caplog.at_level(logging.INFO, logger="novels_project.memory.dialogue_compactor"):
        compactor.compact(session, max_tokens=10)

    # 至少应包含以下日志之一
    log_text = caplog.text
    assert "[DialogueCompactor]" in log_text or "DialogueCompactor" in log_text


def test_logging_on_fallback(caplog):
    """fallback 时应输出 warning 日志。"""
    cfg = MemoryConfig(
        preserve_recent_messages=4,
        dialogue_compression_threshold=0.5,
        dialogue_compression_max_retries=1,
    )

    class FailLLM:
        default_model = "mock-llm"
        def stream(self, request, print_stream: bool = False):
            raise ConnectionError("mock fail")

    compactor = DialogueCompactor(config=cfg, llm_client=FailLLM())
    msgs = [make_message_text("user", f"m{i} " * 20) for i in range(10)]
    session = Session(messages=msgs)

    with caplog.at_level(logging.WARNING, logger="novels_project.memory.dialogue_compactor"):
        compactor.compact(session, max_tokens=10)

    # 验证日志中含 "fallback" 或 "失败" 或 "回退"
    log_text = caplog.text.lower() if caplog.text else ""
    assert any(
        kw in log_text
        for kw in ["fallback", "失败", "回退", "fails", "fail"]
    ), f"未发现 fallback 日志: {caplog.text!r}"
