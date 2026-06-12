"""DialogueCompactor 主体逻辑（Task 8）。

职责：
- 检查对话是否超过阈值（should_compress）
- 主流程 compact：切分消息 → LLM 压缩 → 替换为单条 system 消息
- 失败兜底：fallback 到 DialogueSummary.from_fallback（复用 compaction._build_summary）
- 重试机制：max_retries 次，指数退避
- 复用 entity_extractor.py 的流式 LLM 调用模式
"""
from __future__ import annotations
import json
import logging
import re
import time
from typing import Any, Optional, List

from .memory_config import MemoryConfig
from .dialogue_summary import DialogueSummary
from .compression_exceptions import DialogueCompressionError
from ..compaction import (
    CompactionResult, ConversationMessage, TextBlock, MessageRole, Session,
)

logger = logging.getLogger("novels_project.memory.dialogue_compactor")


# LLM 提示词：要求输出严格 JSON（带 7 个字段）
# 注意：JSON Schema 示例中的 {} 必须用 {{ }} 转义，否则 str.format 会尝试解析为占位符
DIALOGUE_COMPRESSION_PROMPT = """你是一个对话分析助手。请分析以下多 Agent 对话历史，并按 JSON Schema 输出结构化摘要。

要求：
- 严格输出一个 JSON 对象（可被 ```json ... ``` 包裹）
- 7 个字段必须存在，缺失时填空字符串/空数组
- 列表字段必须是数组，单值时包成 ["x"]
- 不要输出 JSON 之外的解释性文字

JSON Schema：
{{
  "characters": ["string"],
  "active_topics": ["string"],
  "pending_tasks": [{{"owner": "string", "task": "string", "status": "string"}}],
  "completed_tasks": ["string"],
  "key_decisions": ["string"],
  "unresolved_questions": ["string"],
  "context_summary": "string"
}}

对话历史：
{conversation}
"""


class DialogueCompactor:
    """LLM 对话压缩器。

    用法：
        compactor = DialogueCompactor(config=MemoryConfig(), llm_client=client)
        if compactor.should_compress(session, max_tokens=100000):
            result = compactor.compact(session, max_tokens=100000)
            session = result.compacted_session
    """

    def __init__(
        self,
        config: MemoryConfig,
        llm_client: Optional[Any] = None,
    ):
        self.config = config
        self.llm_client = llm_client
        if llm_client:
            logger.info(
                "[DialogueCompactor] 初始化 | llm_model=%s threshold=%.2f preserve_recent=%d max_retries=%d",
                getattr(llm_client, "default_model", "?"),
                config.dialogue_compression_threshold,
                config.preserve_recent_messages,
                config.dialogue_compression_max_retries,
            )
        else:
            logger.info(
                "[DialogueCompactor] 初始化（无 LLM 客户端，将走 fallback） | threshold=%.2f preserve_recent=%d",
                config.dialogue_compression_threshold,
                config.preserve_recent_messages,
            )

    def should_compress(self, session: Session, max_tokens: int) -> bool:
        """检查是否需要压缩。"""
        estimated = session.total_estimated_tokens()
        trigger = int(max_tokens * self.config.dialogue_compression_threshold)
        result = estimated >= trigger
        logger.info(
            "[DialogueCompactor] should_compress 检查 | estimated=%d trigger=%d max=%d result=%s",
            estimated, trigger, max_tokens, result,
        )
        return result

    def compact(
        self,
        session: Session,
        max_tokens: int,
    ) -> CompactionResult:
        """压缩对话历史。"""
        # 1. 阈值检查
        if not self.should_compress(session, max_tokens):
            return CompactionResult(
                compacted_session=session,
                removed_message_count=0,
                summary_text="",
            )

        messages = session.messages
        preserve_count = self.config.preserve_recent_messages
        # 2. 消息数检查
        if len(messages) <= preserve_count:
            logger.info(
                "[DialogueCompactor] 消息数不足 | len=%d preserve=%d no_op",
                len(messages), preserve_count,
            )
            return CompactionResult(
                compacted_session=session,
                removed_message_count=0,
                summary_text="",
            )

        # 3. 切分消息
        to_summarize = messages[:-preserve_count]
        to_keep = messages[-preserve_count:]
        conversation_text = self._messages_to_text(to_summarize)
        logger.info(
            "[DialogueCompactor] 压缩开始 | total=%d summarize=%d keep=%d conv_len=%d",
            len(messages), len(to_summarize), len(to_keep), len(conversation_text),
        )

        # 4. LLM 压缩 + fallback
        try:
            summary = self._llm_compress_with_retry(conversation_text)
            logger.info(
                "[DialogueCompactor] LLM 压缩成功 | characters=%d topics=%d pending=%d",
                len(summary.characters), len(summary.active_topics), len(summary.pending_tasks),
            )
        except DialogueCompressionError as e:
            logger.warning(
                "[DialogueCompactor] LLM 压缩失败，fallback 规则压缩 | error=%s",
                e,
            )
            summary = self._rule_compress_fallback(to_summarize)

        # 5. 渲染
        rendered = summary.render(
            max_chars=self.config.dialogue_summary_max_chars,
            context_max_chars=self.config.dialogue_context_summary_max_chars,
        )
        logger.info(
            "[DialogueCompactor] 渲染完成 | summary_len=%d",
            len(rendered),
        )

        # 6. 替换为单条 system 消息
        summary_msg = ConversationMessage(
            role=MessageRole.SYSTEM,
            blocks=[TextBlock(text=rendered)],
        )
        compacted = Session(
            version=session.version,
            messages=[summary_msg] + to_keep,
        )

        logger.info(
            "[DialogueCompactor] 压缩完成 | removed=%d summary_len=%d final_msgs=%d",
            len(to_summarize), len(rendered), len(compacted.messages),
        )
        return CompactionResult(
            compacted_session=compacted,
            removed_message_count=len(to_summarize),
            summary_text=rendered,
        )

    # === 内部方法 ===

    def _messages_to_text(self, messages: list) -> str:
        """将消息列表序列化为 [role] text 格式。"""
        lines: List[str] = []
        for msg in messages:
            text = msg.get_text()
            if not text:
                continue
            role = msg.role.value
            lines.append(f"[{role}] {text}")
        result = "\n\n".join(lines)
        logger.debug(
            "[DialogueCompactor] _messages_to_text | input=%d output_len=%d",
            len(messages), len(result),
        )
        return result

    def _llm_compress_with_retry(
        self,
        conversation: str,
    ) -> DialogueSummary:
        """LLM 压缩 + 重试 + 静默降级。"""
        max_retries = self.config.dialogue_compression_max_retries
        last_error: Optional[Exception] = None
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(
                    "[DialogueCompactor] LLM 压缩尝试 | attempt=%d/%d conv_len=%d",
                    attempt, max_retries, len(conversation),
                )
                raw_text = self._llm_compress_raw(conversation)
                logger.info(
                    "[DialogueCompactor] LLM 响应成功 | attempt=%d text_len=%d",
                    attempt, len(raw_text),
                )
                return self._parse_summary_from_text(raw_text)
            except Exception as e:
                last_error = e
                logger.warning(
                    "[DialogueCompactor] LLM 压缩失败 | attempt=%d/%d error=%s: %s",
                    attempt, max_retries, type(e).__name__, e,
                )
                if attempt < max_retries:
                    sleep_sec = 2 ** attempt
                    logger.info(
                        "[DialogueCompactor] 等待重试 | sleep=%.1fs",
                        sleep_sec,
                    )
                    time.sleep(sleep_sec)
        # 重试耗尽
        raise DialogueCompressionError(
            f"LLM 压缩失败，重试 {max_retries} 次后放弃: {last_error}"
        )

    def _llm_compress_raw(self, conversation: str) -> str:
        """调用 LLM 流式接口，提取完整文本。"""
        if not self.llm_client:
            raise DialogueCompressionError("无 LLM 客户端")

        from ..api_client import ApiRequest, TextDelta

        request = self._build_api_request(conversation)
        logger.debug(
            "[DialogueCompactor] _llm_compress_raw | model=%s max_tokens=%d",
            request.model, request.max_tokens,
        )

        try:
            events = self.llm_client.stream(request, print_stream=False) \
                if hasattr(self.llm_client, "stream") else []
            logger.debug(
                "[DialogueCompactor] LLM stream 返回 | event_count=%d",
                len(events),
            )
        except Exception as e:
            logger.warning(
                "[DialogueCompactor] LLM stream 异常 | error=%s: %s",
                type(e).__name__, e,
            )
            raise DialogueCompressionError(f"LLM stream 失败: {e}") from e

        full_text = self._extract_text_from_events(events)
        if not full_text.strip():
            logger.warning("[DialogueCompactor] LLM 响应为空 | events=%d", len(events))
            raise DialogueCompressionError("LLM 响应为空")
        return full_text

    def _extract_text_from_events(self, events: list) -> str:
        """从 events 列表中提取完整文本（TextDelta 拼接）。"""
        from ..api_client import TextDelta
        chunks: List[str] = []
        for event in events:
            if isinstance(event, TextDelta):
                chunks.append(event.text)
        full_text = "".join(chunks)
        logger.debug(
            "[DialogueCompactor] _extract_text_from_events | chunks=%d total_len=%d",
            len(chunks), len(full_text),
        )
        return full_text

    def _build_api_request(self, conversation: str):
        """构造 ApiRequest。"""
        from ..api_client import ApiRequest
        prompt = DIALOGUE_COMPRESSION_PROMPT.format(conversation=conversation)
        return ApiRequest(
            system_prompt=prompt,
            messages=[],
            tools=[],
            model=getattr(self.llm_client, "default_model", "") if self.llm_client else "",
            max_tokens=4096,
        )

    def _parse_summary_from_text(self, text: str) -> DialogueSummary:
        """从 LLM 输出文本中提取 JSON 并构造 DialogueSummary。"""
        if not text or not text.strip():
            logger.warning("[DialogueCompactor] _parse 输入为空 | text_len=0")
            raise ValueError("LLM 输出文本为空")

        # 1. 提取 JSON 块
        json_match = re.search(r'\{[\s\S]*\}', text)
        if not json_match:
            logger.warning(
                "[DialogueCompactor] 未找到 JSON 块 | text_len=%d preview=%s",
                len(text), self._truncate_text(text, 200),
            )
            raise ValueError(f"LLM 输出中未找到 JSON 块 (text_len={len(text)})")

        # 2. 解析 JSON
        raw = json_match.group()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.warning(
                "[DialogueCompactor] JSON 解析失败 | error=%s text_preview=%s",
                e, self._truncate_text(raw, 200),
            )
            raise

        # 3. 构造 DialogueSummary（严格类型容错）
        summary = DialogueSummary.from_llm_response(data)
        logger.info(
            "[DialogueCompactor] DialogueSummary 构造完成 | characters=%d topics=%d pending=%d",
            len(summary.characters), len(summary.active_topics), len(summary.pending_tasks),
        )
        return summary

    def _rule_compress_fallback(self, messages: list) -> DialogueSummary:
        """规则压缩 fallback（复用 DialogueSummary.from_fallback）。"""
        logger.info(
            "[DialogueCompactor] 规则压缩 fallback | messages=%d",
            len(messages),
        )
        return DialogueSummary.from_fallback(
            messages=messages,
            max_chars=self.config.dialogue_summary_max_chars,
        )

    @staticmethod
    def _truncate_text(text: str, max_len: int = 100) -> str:
        """截断文本用于日志预览。"""
        if len(text) <= max_len:
            return text
        return text[:max_len] + "..."
