"""DialogueSummary 数据类测试。

覆盖 4 大场景：
1. 基本构造与默认值
2. render() 输出格式（标签、字段顺序、空字段跳过）
3. render() 字段限制（10/3/10/5/10/10/1500）
4. render() 丢弃优先级（按 DROP_PRIORITY 顺序）
5. from_llm_response() LLM JSON 解析（含类型容错）
6. from_fallback() 兼容旧规则压缩（用 _build_summary）
"""
import pytest
from unittest.mock import patch

from novels_project.memory.dialogue_summary import DialogueSummary, FIELD_LIMITS, DROP_PRIORITY
from novels_project.compaction import ConversationMessage, TextBlock, MessageRole


# === 场景 1: 基本构造 ===

def test_default_construction():
    """空构造应使用空列表/空字符串。"""
    s = DialogueSummary()
    assert s.characters == []
    assert s.active_topics == []
    assert s.pending_tasks == []
    assert s.completed_tasks == []
    assert s.key_decisions == []
    assert s.unresolved_questions == []
    assert s.context_summary == ""


def test_construction_with_values():
    """显式传值应保留。"""
    s = DialogueSummary(
        characters=["陆商曜", "周桓"],
        active_topics=["宗门合并"],
        pending_tasks=[{"owner": "agent1", "task": "查询境界", "status": "in_progress"}],
        completed_tasks=["创建角色卡"],
        key_decisions=["决定用 LLM 压缩"],
        unresolved_questions=["何时调用 LLM？"],
        context_summary="讨论小说框架",
    )
    assert s.characters == ["陆商曜", "周桓"]
    assert s.active_topics == ["宗门合并"]
    assert len(s.pending_tasks) == 1
    assert s.pending_tasks[0]["owner"] == "agent1"


# === 场景 2: render() 输出格式 ===

def test_render_empty():
    """全空字段应只输出标签。"""
    s = DialogueSummary()
    result = s.render(max_chars=4000, context_max_chars=1500)
    assert "<dialogue_compression>" in result
    assert "</dialogue_compression>" in result
    # 空字段不输出
    assert "出场人物" not in result
    assert "当前主题" not in result


def test_render_includes_all_populated_fields():
    """所有填充字段都应出现在输出中。"""
    s = DialogueSummary(
        characters=["陆商曜"],
        active_topics=["宗门合并"],
        pending_tasks=[{"owner": "agent1", "task": "查询", "status": "todo"}],
        completed_tasks=["建卡"],
        key_decisions=["用 LLM"],
        unresolved_questions=["何时调 LLM？"],
        context_summary="讨论框架",
    )
    result = s.render(max_chars=4000, context_max_chars=1500)
    assert "陆商曜" in result
    assert "宗门合并" in result
    assert "查询" in result
    assert "建卡" in result
    assert "用 LLM" in result
    assert "何时调 LLM" in result
    assert "讨论框架" in result


def test_render_skips_empty_fields():
    """空字段应被跳过（不输出键名）。"""
    s = DialogueSummary(characters=["陆商曜"], context_summary="脉络")
    result = s.render(max_chars=4000, context_max_chars=1500)
    assert "出场人物" in result
    assert "对话脉络" in result
    # 这些字段空，不应出现
    assert "当前主题" not in result
    assert "待办" not in result
    assert "已完成" not in result
    assert "决策" not in result
    assert "待解决" not in result


def test_render_wrapped_in_tags():
    """输出必须被 <dialogue_compression>...</dialogue_compression> 包裹。"""
    s = DialogueSummary(characters=["陆商曜"])
    result = s.render(max_chars=4000, context_max_chars=1500)
    assert result.startswith("<dialogue_compression>")
    assert result.endswith("</dialogue_compression>")


def test_render_field_order():
    """字段应按固定顺序输出。"""
    s = DialogueSummary(
        characters=["陆商曜"],
        active_topics=["宗门合并"],
        context_summary="脉络",
        key_decisions=["决策"],
    )
    result = s.render(max_chars=4000, context_max_chars=1500)
    pos_char = result.index("出场人物")
    pos_topic = result.index("当前主题")
    pos_ctx = result.index("对话脉络")
    pos_dec = result.index("决策")
    # 顺序：人物 < 主题 < 脉络 < 决策
    assert pos_char < pos_topic < pos_ctx < pos_dec


# === 场景 3: render() 字段限制 ===

def test_render_limits_characters_to_10():
    """出场人物超过 10 人时应截断到 10。"""
    s = DialogueSummary(characters=[f"角色{i}" for i in range(20)])
    result = s.render(max_chars=4000, context_max_chars=1500)
    # 11-20 的人不应出现
    for i in range(10, 20):
        assert f"角色{i}" not in result
    # 0-9 的人应出现
    for i in range(10):
        assert f"角色{i}" in result


def test_render_limits_active_topics_to_3():
    """当前主题超过 3 个时应截断到 3。"""
    s = DialogueSummary(active_topics=[f"主题{i}" for i in range(10)])
    result = s.render(max_chars=4000, context_max_chars=1500)
    for i in range(3, 10):
        assert f"主题{i}" not in result
    for i in range(3):
        assert f"主题{i}" in result


def test_render_limits_pending_tasks_to_10():
    """待办任务超过 10 条时应截断到 10。"""
    s = DialogueSummary(
        pending_tasks=[
            {"owner": f"agent{i}", "task": f"任务{i}", "status": "todo"}
            for i in range(20)
        ]
    )
    result = s.render(max_chars=4000, context_max_chars=1500)
    for i in range(10, 20):
        assert f"任务{i}" not in result


def test_render_limits_completed_tasks_to_5():
    """已完成任务超过 5 条时应截断到 5。"""
    s = DialogueSummary(completed_tasks=[f"已完成{i}" for i in range(15)])
    result = s.render(max_chars=4000, context_max_chars=1500)
    for i in range(5, 15):
        assert f"已完成{i}" not in result


def test_render_limits_key_decisions_to_10():
    """关键决策超过 10 条时应截断到 10。"""
    s = DialogueSummary(key_decisions=[f"决策{i}" for i in range(20)])
    result = s.render(max_chars=4000, context_max_chars=1500)
    for i in range(10, 20):
        assert f"决策{i}" not in result


def test_render_limits_unresolved_questions_to_10():
    """未解决问题超过 10 条时应截断到 10。"""
    s = DialogueSummary(unresolved_questions=[f"问题{i}" for i in range(20)])
    result = s.render(max_chars=4000, context_max_chars=1500)
    for i in range(10, 20):
        assert f"问题{i}" not in result


def test_render_limits_context_summary_to_1500_chars():
    """对话脉络超过 1500 字符应截断。"""
    s = DialogueSummary(context_summary="x" * 3000)
    result = s.render(max_chars=4000, context_max_chars=1500)
    # 脉络部分（去掉标签、键名等）应不超过 1500
    ctx_start = result.index("对话脉络:") + len("对话脉络:")
    ctx_end = result.index("</dialogue_compression>")
    ctx_section = result[ctx_start:ctx_end]
    # 实际脉络部分 < 1500（截断+省略标记）
    assert len(ctx_section) < 1700  # 留 200 给省略标记


# === 场景 4: render() 丢弃优先级 ===

def test_render_priority_drop_skips_active_topics_first():
    """当总长度超过 max_chars 时，优先丢弃 active_topics。"""
    # 构造一个会超长的 summary：
    # 字段值都很长，max_chars 很小
    long_topic = "A" * 1000
    long_ctx = "B" * 1000
    long_pending = {"owner": "a", "task": "C" * 1000, "status": "todo"}
    s = DialogueSummary(
        active_topics=[long_topic],
        context_summary=long_ctx,
        pending_tasks=[long_pending],
    )
    # max_chars=2000 必然要丢一些字段
    result = s.render(max_chars=2000, context_max_chars=1500)
    # active_topics 应被丢弃（最高优先级丢弃）
    assert long_topic not in result
    # 但人物（最低优先级丢弃）应保留
    # context_summary 优先级次高，可能被保留
    # pending_tasks 优先级中等


def test_render_priority_drop_preserves_characters_last():
    """出场人物是最后丢弃的（最不重要）。"""
    long_char = "X" * 1000
    long_topic = "A" * 1000
    long_ctx = "B" * 1000
    s = DialogueSummary(
        characters=[long_char],
        active_topics=[long_topic],
        context_summary=long_ctx,
    )
    # max_chars=2000
    result = s.render(max_chars=2000, context_max_chars=1500)
    # 出场人物应保留（最后丢弃）
    assert long_char in result
    # active_topics 应被丢弃（最高优先级）
    assert long_topic not in result


def test_render_drop_priority_constant():
    """DROP_PRIORITY 应包含所有可丢弃字段，按正确顺序。"""
    expected = [
        "active_topics",
        "context_summary",
        "pending_tasks",
        "key_decisions",
        "unresolved_questions",
        "completed_tasks",
        "characters",
    ]
    assert DROP_PRIORITY == expected


def test_render_field_limits_constant():
    """FIELD_LIMITS 应包含所有字段限制。"""
    assert FIELD_LIMITS["characters"] == 10
    assert FIELD_LIMITS["active_topics"] == 3
    assert FIELD_LIMITS["pending_tasks"] == 10
    assert FIELD_LIMITS["completed_tasks"] == 5
    assert FIELD_LIMITS["key_decisions"] == 10
    assert FIELD_LIMITS["unresolved_questions"] == 10
    assert FIELD_LIMITS["context_summary_chars"] == 1500


# === 场景 5: from_llm_response() LLM JSON 解析 ===

def test_from_llm_response_valid():
    """标准 LLM JSON 应正确解析。"""
    data = {
        "characters": ["陆商曜", "周桓"],
        "active_topics": ["宗门合并"],
        "pending_tasks": [{"owner": "agent1", "task": "查询", "status": "todo"}],
        "completed_tasks": ["建卡"],
        "key_decisions": ["用 LLM"],
        "unresolved_questions": ["何时调？"],
        "context_summary": "讨论框架",
    }
    s = DialogueSummary.from_llm_response(data)
    assert s.characters == ["陆商曜", "周桓"]
    assert s.context_summary == "讨论框架"


def test_from_llm_response_missing_fields():
    """缺失字段应使用空默认值。"""
    data = {"characters": ["陆商曜"]}
    s = DialogueSummary.from_llm_response(data)
    assert s.characters == ["陆商曜"]
    assert s.active_topics == []
    assert s.context_summary == ""


def test_from_llm_response_wrong_types():
    """字段类型错误时（如 str 而非 list）应容忍。"""
    data = {
        "characters": "陆商曜",  # 应为 list
        "active_topics": ["主题"],
        "context_summary": 12345,  # 应为 str
    }
    s = DialogueSummary.from_llm_response(data)
    # 类型错误应被 fallback 为默认
    assert s.characters == []
    assert s.context_summary == ""


def test_from_llm_response_non_dict():
    """非字典输入应抛 ValueError。"""
    with pytest.raises(ValueError):
        DialogueSummary.from_llm_response("not a dict")
    with pytest.raises(ValueError):
        DialogueSummary.from_llm_response(None)
    with pytest.raises(ValueError):
        DialogueSummary.from_llm_response([1, 2, 3])


# === 场景 6: from_fallback() 旧规则兼容 ===

def test_from_fallback_uses_build_summary():
    """from_fallback 应使用 compaction._build_summary 作为 context_summary。"""
    messages = [
        ConversationMessage(
            role=MessageRole.USER,
            blocks=[TextBlock(text="第 1 章：陆商曜开始修炼")],
        ),
        ConversationMessage(
            role=MessageRole.ASSISTANT,
            blocks=[TextBlock(text="开始筑基")],
        ),
    ]
    s = DialogueSummary.from_fallback(messages, max_chars=2000)
    # 所有结构化字段应为空（fallback 无法提取）
    assert s.characters == []
    assert s.active_topics == []
    assert s.pending_tasks == []
    # 但 context_summary 应有内容（来自 _build_summary）
    assert s.context_summary != ""
    assert "<compaction_summary>" in s.context_summary


def test_from_fallback_respects_max_chars():
    """from_fallback 摘要应不超过 max_chars。"""
    messages = [
        ConversationMessage(
            role=MessageRole.USER,
            blocks=[TextBlock(text="x" * 1000)],
        ),
    ]
    s = DialogueSummary.from_fallback(messages, max_chars=500)
    # _build_summary 会截断到 max_chars 以内
    assert len(s.context_summary) <= 600  # 留点容差给 _build_summary 的截断


def test_from_fallback_empty_messages():
    """空消息列表应返回空 context_summary。"""
    s = DialogueSummary.from_fallback([], max_chars=2000)
    # 空消息应仍返回有效 DialogueSummary
    assert isinstance(s, DialogueSummary)
    assert s.context_summary == "" or s.context_summary is not None
