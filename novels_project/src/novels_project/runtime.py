"""
Layer 4: Agent Runtime - ConversationRuntime

The core agent loop following agent-harness run_turn() lifecycle:
User → LLM → Tools → Results → LLM (loop) → auto-compact → TurnSummary
"""
import logging
from dataclasses import dataclass, field
from typing import Optional, Callable

from .api_client import (
    ApiClient, ApiRequest, TokenUsage,
    AssistantEvent, TextDelta, ToolUseEvent, UsageEvent, MessageStop,
)
from .session import (
    Session, ConversationMessage,
    TextBlock, ToolUseBlock,
)
from .tool_spec import ToolExecutor, ToolRegistry
from .usage import UsageTracker
from .compaction import compact_session
from .memory.memory_config import MemoryConfig  # 10a: 记忆子系统基础支持

logger = logging.getLogger("novels_project.runtime")

# 延迟导入上下文注入器
_context_injector = None

def _get_context_injector():
    global _context_injector
    if _context_injector is None:
        from .context_injector import get_context_injector
        _context_injector = get_context_injector()
    return _context_injector


@dataclass
class AutoCompactionEvent:
    removed_message_count: int


@dataclass
class TurnSummary:
    assistant_messages: list[ConversationMessage] = field(default_factory=list)
    tool_results: list[ConversationMessage] = field(default_factory=list)
    iterations: int = 0
    usage: TokenUsage = field(default_factory=TokenUsage)
    auto_compaction: Optional[AutoCompactionEvent] = None

    def get_final_text(self) -> str:
        """Get the final assistant text from the last message."""
        if self.assistant_messages:
            return self.assistant_messages[-1].get_text()
        return ""


class ConversationRuntime:
    """
    Core agent loop. Handles the User → LLM → Tools → Results cycle.

    This is the heart of the system. Both the main agent and sub-agents
    use the same ConversationRuntime, differing only in their tools,
    system prompt, and model — following the agent-harness generic runtime pattern.
    """

    # 可配置的输出截断限制（默认 50000 字符）
    OUTPUT_TRUNCATION_LIMIT: int = 50000

    def __init__(
        self,
        session: Session,
        api_client: ApiClient,
        tool_executor: ToolExecutor,
        tool_registry: ToolRegistry,
        system_prompt: str,
        model: str,
        max_iterations: int = 50,
        auto_compaction_threshold: int = 100000,
        print_stream: bool = True,
        output_truncation_limit: int = 50000,
        # === 10a: 记忆子系统基础支持 ===
        agent_id: str = "main",
        memory_config: Optional[MemoryConfig] = None,
    ):
        self.session = session
        self.api_client = api_client
        self.tool_executor = tool_executor
        self.tool_registry = tool_registry
        self.system_prompt = system_prompt
        self.model = model
        self.max_iterations = max_iterations
        self.auto_compaction_threshold = auto_compaction_threshold
        self.print_stream = print_stream
        self.output_truncation_limit = output_truncation_limit
        self.usage_tracker = UsageTracker.from_session(session)

        # === 10a 新增属性 ===
        self.agent_id = agent_id
        self.memory_config = memory_config or MemoryConfig()
        # 注：dialogue_compactor 在 Task 10b 中添加（依赖 DialogueCompactor + MemoryManager）

        # Hook system for post-turn processing (replaces monkey-patching)
        self._turn_hooks: list[Callable[[TurnSummary], None]] = []

    def add_turn_hook(self, hook: Callable[[TurnSummary], None]) -> None:
        """Register a callback invoked after each turn completes.

        Args:
            hook: Callable that receives the TurnSummary of the completed turn.
        """
        self._turn_hooks.append(hook)

    def _inject_context(self, user_input: str) -> str:
        """
        自动注入上下文信息：
        1. 从图谱中查询角色信息（境界、喜好等）
        2. 查询未完成的伏笔
        3. 查询人物历史信息保证一致性
        """
        try:
            injector = _get_context_injector()
            logger.info(
                "[Runtime] 上下文注入开始 | input_len=%d",
                len(user_input) if user_input else 0,
            )
            enriched = injector.inject_context(user_input)
            if enriched != user_input:
                logger.info(
                    "[Runtime] 上下文注入完成 | enriched_len=%d delta=%d",
                    len(enriched), len(enriched) - len(user_input),
                )
            else:
                logger.info("[Runtime] 上下文注入完成 | 无补充信息")
            return enriched
        except Exception as e:
            logger.warning("上下文注入失败: %s", e)
            return user_input

    def run_turn(self, user_input: str) -> TurnSummary:
        """
        Core agent loop lifecycle:

        1. Push user message to session
        2. Loop:
           a. Build ApiRequest from session + system_prompt + tools
           b. Call api_client.stream(request) -> events
           c. build_assistant_message(events) -> ConversationMessage
           d. Push assistant message to session
           e. Extract pending tool_uses
           f. If no tool_uses: break
           g. For each tool_use: execute, build ToolResult, push to session
           h. Loop back to (a)
        3. maybe_auto_compact()
        4. Invoke registered turn hooks
        5. Return TurnSummary
        """
        # Phase 1: user input
        # 自动注入上下文信息（角色信息、伏笔等）
        logger.info(
            "[Runtime] run_turn 启动 | model=%s max_iter=%d history_msgs=%d input_preview=%s",
            self.model, self.max_iterations, len(self.session.messages),
            (user_input or "")[:80],
        )
        enriched_input = self._inject_context(user_input)
        self.session.messages.append(ConversationMessage.user_text(enriched_input))

        assistant_messages = []
        tool_results = []
        iterations = 0

        # Phase 2: agent loop
        truncation_limit = self.output_truncation_limit
        logger.info(
            "[Runtime] 进入 Agent 循环 | truncation_limit=%d",
            truncation_limit,
        )
        while True:
            iterations += 1
            if iterations > self.max_iterations:
                logger.error(
                    "[Runtime] Agent 循环超过最大迭代次数 | max=%d",
                    self.max_iterations,
                )
                raise RuntimeError(
                    f"Agent loop exceeded {self.max_iterations} iterations. "
                    f"This likely indicates an infinite tool-calling loop."
                )

            # Build API request
            request = ApiRequest(
                system_prompt=self.system_prompt,
                messages=self.session.messages,
                tools=self.tool_registry.all_specs(),
                model=self.model,
            )
            logger.info(
                "[Runtime] iter=%d 调用 LLM | tools=%d msgs=%d",
                iterations, len(self.tool_registry.all_specs()),
                len(self.session.messages),
            )

            # Call LLM
            events = self.api_client.stream(request, print_stream=self.print_stream)

            # Parse events into structured message
            assistant_msg, usage = self._build_assistant_message(events)
            if usage:
                self.usage_tracker.record(usage)
                assistant_msg.usage = usage
                logger.info(
                    "[Runtime] iter=%d LLM 返回 | input_tokens=%d output_tokens=%d",
                    iterations, usage.input_tokens, usage.output_tokens,
                )

            # Add to session
            self.session.messages.append(assistant_msg)
            assistant_messages.append(assistant_msg)

            # Extract pending tool uses
            pending_tools = assistant_msg.get_tool_uses()
            logger.info(
                "[Runtime] iter=%d 解析工具调用 | count=%d names=%s",
                iterations, len(pending_tools),
                [t.name for t in pending_tools],
            )

            # No tools = conversation turn complete
            if not pending_tools:
                logger.info(
                    "[Runtime] iter=%d 无工具调用，本轮结束 | total_iter=%d",
                    iterations, iterations,
                )
                break

            # Execute each tool
            for tool_block in pending_tools:
                if self.print_stream:
                    logger.debug("Tool: %s", tool_block.name)
                logger.info(
                    "[Runtime] iter=%d 执行工具 | name=%s input=%s",
                    iterations, tool_block.name,
                    str(tool_block.input)[:200],
                )

                output, is_error = self.tool_executor.execute(
                    tool_block.name, tool_block.input
                )

                # Truncate very large outputs to prevent context bloat
                if len(output) > truncation_limit:
                    logger.info(
                        "Tool output truncated: %s (%d chars → %d)",
                        tool_block.name, len(output), truncation_limit,
                    )
                    output = output[:truncation_limit] + f"\n... (output truncated at {truncation_limit} chars)"

                result_msg = ConversationMessage.tool_result(
                    tool_use_id=tool_block.id,
                    tool_name=tool_block.name,
                    output=output,
                    is_error=is_error,
                )
                self.session.messages.append(result_msg)
                tool_results.append(result_msg)

                logger.info(
                    "[Runtime] iter=%d 工具完成 | name=%s is_error=%s output_len=%d preview=%s",
                    iterations, tool_block.name, is_error, len(output),
                    output[:120].replace("\n", " "),
                )

                if is_error:
                    logger.warning("Tool error [%s]: %s", tool_block.name, output[:200])

        # Phase 3: auto-compact
        auto_compaction = self._maybe_auto_compact()
        if auto_compaction:
            logger.info(
                "[Runtime] 触发自动压缩 | 移除消息数=%d",
                auto_compaction.removed_message_count,
            )

        # Phase 4: build summary
        summary = TurnSummary(
            assistant_messages=assistant_messages,
            tool_results=tool_results,
            iterations=iterations,
            usage=self.usage_tracker.cumulative_usage(),
            auto_compaction=auto_compaction,
        )
        logger.info(
            "[Runtime] turn 总结 | iterations=%d tool_calls=%d final_text_len=%d total_in=%d total_out=%d",
            iterations, len(tool_results),
            len(summary.get_final_text()),
            summary.usage.input_tokens, summary.usage.output_tokens,
        )

        # Phase 5: invoke turn hooks (replaces monkey-patching)
        for hook in self._turn_hooks:
            try:
                hook(summary)
            except Exception as e:
                logger.warning("Turn hook failed: %s", e, exc_info=True)

        return summary

    def _build_assistant_message(
        self, events: list[AssistantEvent]
    ) -> tuple[ConversationMessage, Optional[TokenUsage]]:
        """Convert event list to structured ConversationMessage."""
        blocks = []
        full_text = ""
        usage = None

        for event in events:
            if isinstance(event, TextDelta):
                full_text += event.text
            elif isinstance(event, ToolUseEvent):
                blocks.append(ToolUseBlock(
                    id=event.id,
                    name=event.name,
                    input=event.input,
                ))
            elif isinstance(event, UsageEvent):
                usage = event.usage
            elif isinstance(event, MessageStop):
                pass

        # Add text block if there was any text content
        if full_text.strip():
            blocks.insert(0, TextBlock(text=full_text))

        return ConversationMessage.assistant(blocks, usage), usage

    def _maybe_auto_compact(self) -> Optional[AutoCompactionEvent]:
        """Check cumulative tokens and compact if over threshold.

        10a: 使用 MemoryConfig.dialogue_compression_threshold（比例）作为触发比例。
        实际触发 token 数 = auto_compaction_threshold * dialogue_compression_threshold。
        10a 阶段回退到 compact_session（规则压缩），10b 阶段优先使用 dialogue_compactor。
        """
        estimated_tokens = self.session.total_estimated_tokens()
        max_tokens = self.auto_compaction_threshold

        # 从 MemoryConfig 读取阈值（10a）
        threshold = self.memory_config.dialogue_compression_threshold
        trigger_tokens = int(max_tokens * threshold)

        logger.info(
            "[Runtime] 评估是否需要自动压缩 | est_tokens=%d trigger=%d threshold=%.2f agent=%s",
            estimated_tokens, trigger_tokens, threshold, self.agent_id,
        )
        if estimated_tokens < trigger_tokens:
            return None

        # 10a 阶段：直接使用 compact_session（规则压缩）
        # 10b 阶段：优先 dialogue_compactor
        result = compact_session(self.session)
        if result.removed_message_count > 0:
            self.session = result.compacted_session
            logger.info(
                "Auto-compaction: %d messages compressed",
                result.removed_message_count,
            )
            logger.info(
                "[Runtime] 对话压缩完成 | agent=%s removed=%d summary_len=%d (10a: rule)",
                self.agent_id, result.removed_message_count, len(result.summary_text),
            )
            return AutoCompactionEvent(removed_message_count=result.removed_message_count)
        return None
