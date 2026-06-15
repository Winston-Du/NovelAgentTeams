"""DialogueSummary 数据类（对话级结构化摘要）。

Task 7 范围：纯 dataclass + render/from_llm_response/from_fallback，无业务逻辑。
Task 8 范围：DialogueCompactor 主体（业务逻辑）。

设计要点：
- 7 个结构化字段 + 1 个脉络字段
- render() 输出：<dialogue_compression>...</dialogue_compression> 包裹
- render() 字段限制：类常量 FIELD_LIMITS（不在 MemoryConfig）
- render() 丢弃优先级：类常量 DROP_PRIORITY
- 兼容旧规则压缩：from_fallback() 复用 compaction._build_summary
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

logger = logging.getLogger("novels_project.memory.dialogue_summary")


# === 类常量（输出格式约束，非性能配置）===

FIELD_LIMITS: Dict[str, int] = {
    "characters": 10,                # 出场人物：前 10 人
    "active_topics": 3,              # 当前主题：前 3 个
    "pending_tasks": 10,             # 待办任务：最多 10 条
    "completed_tasks": 5,            # 已完成任务：5 条
    "key_decisions": 10,             # 关键决策：最多 10 条
    "unresolved_questions": 10,      # 未解决问题：最多 10 条
    "context_summary_chars": 1500,   # 对话脉络：1500 字符
}

# 丢弃优先级（高 → 低，先丢先头）
DROP_PRIORITY: List[str] = [
    "active_topics",          # 当前主题
    "context_summary",        # 对话脉络
    "pending_tasks",          # 待办任务
    "key_decisions",          # 关键决策
    "unresolved_questions",   # 未解决问题
    "completed_tasks",        # 已完成任务
    "characters",             # 出场人物（最后保留）
]


@dataclass
class DialogueSummary:
    """对话级结构化摘要。

    字段语义：
    - characters: 本次对话涉及的角色名（对话级，非章节级）
    - active_topics: 当前正在讨论的主题
    - pending_tasks: 待办任务（含 owner/status 元数据）
    - completed_tasks: 已完成事项
    - key_decisions: 关键决策
    - unresolved_questions: 未解决问题
    - context_summary: 对话脉络（短文）
    """
    characters: List[str] = field(default_factory=list)
    active_topics: List[str] = field(default_factory=list)
    pending_tasks: List[Dict[str, str]] = field(default_factory=list)
    completed_tasks: List[str] = field(default_factory=list)
    key_decisions: List[str] = field(default_factory=list)
    unresolved_questions: List[str] = field(default_factory=list)
    context_summary: str = ""

    def render(self, max_chars: int, context_max_chars: int) -> str:
        """渲染为可注入的 system 消息文本。

        流程：
        1. 应用字段限制（FIELD_LIMITS）
        2. 检查总长度：超过 max_chars 时按 DROP_PRIORITY 丢字段
        3. 包裹在 <dialogue_compression>...</dialogue_compression> 中
        """
        # 1. 限制每个字段的长度
        sections = self._build_sections(context_max_chars=context_max_chars)

        # 2. 拼装 + 长度控制（按优先级丢字段）
        while sections:
            parts = ["<dialogue_compression>"]
            for section in sections:
                parts.append(section)
            parts.append("</dialogue_compression>")
            result = "\n".join(parts)
            if len(result) <= max_chars:
                return result
            # 超过长度，丢弃最高优先级字段
            dropped = DROP_PRIORITY[0]
            sections = self._build_sections(
                context_max_chars=context_max_chars,
                skip_fields={dropped},
            )
            logger.info(
                "[DialogueSummary] render 超限丢字段 | dropped=%s current_len=%d max=%d",
                dropped, len(result), max_chars,
            )
            # 如果只剩 characters 仍然超长（极端情况），强制截断
            if all(
                f not in {f for f in DROP_PRIORITY[len(DROP_PRIORITY) - 1:]}
                for f in []
            ):
                # 只剩 characters
                break

        # 3. 极端情况：所有可丢字段都丢完还超长 → 硬截断
        parts = ["<dialogue_compression>"]
        for section in sections:
            parts.append(section)
        parts.append("</dialogue_compression>")
        result = "\n".join(parts)
        if len(result) > max_chars:
            truncated_body = result[len("<dialogue_compression>"):][:max_chars - 60]
            result = (
                f"<dialogue_compression>\n{truncated_body}\n"
                f"... (内容已截断) ...\n</dialogue_compression>"
            )
        return result

    def _build_sections(
        self,
        context_max_chars: int,
        skip_fields: Optional[set] = None,
    ) -> List[str]:
        """构建字段 section 列表（不拼装标签）。"""
        skip = skip_fields or set()
        sections: List[str] = []

        # 1. 出场人物（必含，前 10 人）
        if "characters" not in skip and self.characters:
            chars = self.characters[: FIELD_LIMITS["characters"]]
            sections.append(f"出场人物: {', '.join(chars)}")

        # 2. 当前主题（必含，前 3 个）
        if "active_topics" not in skip and self.active_topics:
            topics = self.active_topics[: FIELD_LIMITS["active_topics"]]
            sections.append(f"当前主题: {'; '.join(topics)}")

        # 3. 对话脉络（最重要上下文）
        if "context_summary" not in skip and self.context_summary:
            ctx_limit = min(
                context_max_chars, FIELD_LIMITS["context_summary_chars"]
            )
            ctx_text = self.context_summary
            if len(ctx_text) > ctx_limit:
                ctx_text = ctx_text[: ctx_limit - 20] + " ...（内容已截断）"
            sections.append(f"对话脉络: {ctx_text}")

        # 4. 待办任务
        if "pending_tasks" not in skip and self.pending_tasks:
            tasks = self.pending_tasks[: FIELD_LIMITS["pending_tasks"]]
            task_strs = " | ".join(
                f"[{t.get('owner', '?')}] {t.get('task', '')}"
                for t in tasks
            )
            sections.append(f"待办: {task_strs}")

        # 5. 已完成任务
        if "completed_tasks" not in skip and self.completed_tasks:
            completed = self.completed_tasks[: FIELD_LIMITS["completed_tasks"]]
            sections.append(f"已完成: {'; '.join(completed)}")

        # 6. 关键决策
        if "key_decisions" not in skip and self.key_decisions:
            decisions = self.key_decisions[: FIELD_LIMITS["key_decisions"]]
            sections.append(f"决策: {'; '.join(decisions)}")

        # 7. 未解决问题
        if "unresolved_questions" not in skip and self.unresolved_questions:
            questions = self.unresolved_questions[: FIELD_LIMITS["unresolved_questions"]]
            sections.append(f"待解决: {'; '.join(questions)}")

        return sections

    @classmethod
    def from_llm_response(cls, data: Any) -> "DialogueSummary":
        """从 LLM 返回的 dict 创建实例（严格类型容错）。

        - data 非 dict：抛 ValueError
        - 字段缺失：使用空默认值
        - 字段类型错误：fallback 到空默认（严格策略，宁可丢数据不要脏数据）

        严格类型规则：
        - list 字段遇到非 list → []（不接受 str 替代 list）
        - str 字段遇到非 str → ""（不接受 int/none 替代 str）
        - list of dict 字段遇到非 dict 元素 → 过滤
        """
        if not isinstance(data, dict):
            logger.warning(
                "[DialogueSummary] from_llm_response 非 dict 输入 | type=%s",
                type(data).__name__,
            )
            raise ValueError(f"LLM response must be dict, got {type(data).__name__}")

        def _list_of_str(v: Any) -> List[str]:
            if not isinstance(v, list):
                return []
            return [str(x) for x in v if x]

        def _list_of_dict(v: Any) -> List[Dict[str, str]]:
            if not isinstance(v, list):
                return []
            return [x for x in v if isinstance(x, dict)]

        ctx_raw = data.get("context_summary")
        if not isinstance(ctx_raw, str):
            ctx = ""
        else:
            ctx = ctx_raw

        return cls(
            characters=_list_of_str(data.get("characters")),
            active_topics=_list_of_str(data.get("active_topics")),
            pending_tasks=_list_of_dict(data.get("pending_tasks")),
            completed_tasks=_list_of_str(data.get("completed_tasks")),
            key_decisions=_list_of_str(data.get("key_decisions")),
            unresolved_questions=_list_of_str(data.get("unresolved_questions")),
            context_summary=ctx,
        )

    @classmethod
    def from_fallback(
        cls,
        messages: list,
        max_chars: int = 2000,
    ) -> "DialogueSummary":
        """从旧规则压缩创建（用于 LLM 失败时的降级路径）。

        复用 compaction._build_summary 的输出作为 context_summary。
        其他结构化字段留空（旧规则无法提取）。
        """
        try:
            from ..compaction import _build_summary
            context_text = _build_summary(messages, max_chars)
            logger.info(
                "[DialogueSummary] from_fallback 复用规则压缩 | "
                "messages=%d context_len=%d max=%d",
                len(messages), len(context_text), max_chars,
            )
            return cls(context_summary=context_text)
        except Exception as e:
            logger.warning(
                "[DialogueSummary] from_fallback 失败 | error=%s", e,
            )
            return cls()
