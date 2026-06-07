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
    Session, ConversationMessage, MessageRole,
    TextBlock, ToolUseBlock, ToolResultBlock,
)
from .tool_spec import ToolExecutor, ToolRegistry
from .usage import UsageTracker
from .compaction import compact_session, CompactionConfig

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
            return injector.inject_context(user_input)
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
        enriched_input = self._inject_context(user_input)
        self.session.messages.append(ConversationMessage.user_text(enriched_input))

        assistant_messages = []
        tool_results = []
        iterations = 0

        # Phase 2: agent loop
        truncation_limit = self.output_truncation_limit
        while True:
            iterations += 1
            if iterations > self.max_iterations:
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

            # Call LLM
            events = self.api_client.stream(request, print_stream=self.print_stream)

            # Parse events into structured message
            assistant_msg, usage = self._build_assistant_message(events)
            if usage:
                self.usage_tracker.record(usage)
                assistant_msg.usage = usage

            # Add to session
            self.session.messages.append(assistant_msg)
            assistant_messages.append(assistant_msg)

            # Extract pending tool uses
            pending_tools = assistant_msg.get_tool_uses()

            # No tools = conversation turn complete
            if not pending_tools:
                break

            # Execute each tool
            for tool_block in pending_tools:
                if self.print_stream:
                    logger.debug("Tool: %s", tool_block.name)

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

                if is_error:
                    logger.warning("Tool error [%s]: %s", tool_block.name, output[:200])

        # Phase 3: auto-compact
        auto_compaction = self._maybe_auto_compact()

        # Phase 4: build summary
        summary = TurnSummary(
            assistant_messages=assistant_messages,
            tool_results=tool_results,
            iterations=iterations,
            usage=self.usage_tracker.cumulative_usage(),
            auto_compaction=auto_compaction,
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
        """Check cumulative tokens and compact if over threshold."""
        estimated_tokens = self.session.total_estimated_tokens()
        if estimated_tokens < self.auto_compaction_threshold:
            return None

        result = compact_session(self.session)
        if result.removed_message_count > 0:
            self.session = result.compacted_session
            logger.info(
                "Auto-compaction: %d messages compressed",
                result.removed_message_count,
            )
            return AutoCompactionEvent(removed_message_count=result.removed_message_count)

        return None
