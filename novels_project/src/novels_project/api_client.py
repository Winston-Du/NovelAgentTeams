"""
Layer 1: Transport - OpenAI-compatible API Client

Wraps the OpenAI Python SDK to provide streaming LLM communication.
Follows agent-harness ApiClient protocol pattern.
"""
import sys
import json
from dataclasses import dataclass, field
from typing import Protocol, Optional, runtime_checkable


# === Data Types ===

@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )


# === Assistant Events ===

class AssistantEvent:
    """Base class for LLM response events."""
    pass


@dataclass
class TextDelta(AssistantEvent):
    text: str


@dataclass
class ToolUseEvent(AssistantEvent):
    id: str
    name: str
    input: str  # JSON string


@dataclass
class UsageEvent(AssistantEvent):
    usage: TokenUsage


@dataclass
class MessageStop(AssistantEvent):
    pass


# === API Request ===

@dataclass
class ApiRequest:
    system_prompt: str
    messages: list  # list[ConversationMessage] - forward ref to avoid circular import
    tools: list     # list[ToolSpec]
    model: str
    max_tokens: int = 16384


# === ApiClient Protocol ===

@runtime_checkable
class ApiClient(Protocol):
    def stream(self, request: ApiRequest) -> list[AssistantEvent]:
        """Send a request to the LLM and return collected events."""
        ...  # pragma: no cover


# === OpenAI SDK Implementation ===

class OpenAICompatibleClient:
    """
    LLM API client using the OpenAI Python SDK.
    Supports any OpenAI-compatible endpoint (custom base_url).
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        default_model: str = "gemini-3-pro",
        max_retries: int = 3,
        timeout: float = 300.0,
    ):
        import openai
        self.client = openai.OpenAI(
            base_url=base_url,
            api_key=api_key,
            max_retries=max_retries,
            timeout=timeout,
        )
        self.default_model = default_model

    def stream(self, request: ApiRequest, print_stream: bool = True) -> list[AssistantEvent]:
        """
        Call the LLM with streaming. Collects all SSE events into AssistantEvent list.
        Prints text deltas in real-time for UX when print_stream=True.
        """
        from .session import MessageRole, TextBlock, ToolUseBlock, ToolResultBlock

        # Build OpenAI messages format
        openai_messages = []

        # System prompt as first message
        if request.system_prompt:
            openai_messages.append({
                "role": "system",
                "content": request.system_prompt,
            })

        # Convert session messages
        for msg in request.messages:
            openai_msg = self._convert_message(msg)
            if openai_msg:
                if isinstance(openai_msg, list):
                    openai_messages.extend(openai_msg)
                else:
                    openai_messages.append(openai_msg)

        # Build tools parameter
        openai_tools = None
        if request.tools:
            openai_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": spec.name,
                        "description": spec.description,
                        "parameters": spec.input_schema,
                    }
                }
                for spec in request.tools
            ]

        # Make streaming API call
        kwargs = {
            "model": request.model or self.default_model,
            "messages": openai_messages,
            "max_tokens": request.max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if openai_tools:
            kwargs["tools"] = openai_tools

        response = self.client.chat.completions.create(**kwargs)

        # Collect events from SSE stream
        events: list[AssistantEvent] = []
        full_text = ""
        tool_calls: dict[int, dict] = {}  # index -> {id, name, arguments}

        for chunk in response:
            if not chunk.choices and chunk.usage:
                # Final usage chunk (stream_options.include_usage)
                events.append(UsageEvent(usage=TokenUsage(
                    input_tokens=chunk.usage.prompt_tokens or 0,
                    output_tokens=chunk.usage.completion_tokens or 0,
                    total_tokens=chunk.usage.total_tokens or 0,
                )))
                continue

            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta

            # Text content
            if delta.content:
                full_text += delta.content
                events.append(TextDelta(text=delta.content))
                if print_stream:
                    sys.stdout.write(delta.content)
                    sys.stdout.flush()

            # Tool calls (arguments arrive as fragments across chunks)
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls:
                        tool_calls[idx] = {
                            "id": tc.id or "",
                            "name": tc.function.name if tc.function and tc.function.name else "",
                            "arguments": "",
                        }
                    if tc.id:
                        tool_calls[idx]["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            tool_calls[idx]["name"] = tc.function.name
                        if tc.function.arguments:
                            tool_calls[idx]["arguments"] += tc.function.arguments

            # Check for finish
            if chunk.choices[0].finish_reason:
                break

        # Print newline after streamed text
        if print_stream and full_text:
            sys.stdout.write("\n")
            sys.stdout.flush()

        # Convert accumulated tool calls to events
        for idx in sorted(tool_calls.keys()):
            tc = tool_calls[idx]
            events.append(ToolUseEvent(
                id=tc["id"],
                name=tc["name"],
                input=tc["arguments"],
            ))

        events.append(MessageStop())
        return events

    def _convert_message(self, msg) -> Optional[dict | list[dict]]:
        """Convert a ConversationMessage to OpenAI format."""
        from .session import MessageRole, TextBlock, ToolUseBlock, ToolResultBlock

        if msg.role == MessageRole.USER:
            text_parts = [b.text for b in msg.blocks if isinstance(b, TextBlock)]
            if text_parts:
                return {"role": "user", "content": "\n".join(text_parts)}
            return None

        elif msg.role == MessageRole.ASSISTANT:
            content = None
            tool_calls_list = []

            text_parts = [b.text for b in msg.blocks if isinstance(b, TextBlock)]
            if text_parts:
                content = "\n".join(text_parts)

            for b in msg.blocks:
                if isinstance(b, ToolUseBlock):
                    tool_calls_list.append({
                        "id": b.id,
                        "type": "function",
                        "function": {
                            "name": b.name,
                            "arguments": b.input,
                        }
                    })

            result = {"role": "assistant"}
            if content:
                result["content"] = content
            if tool_calls_list:
                result["tool_calls"] = tool_calls_list
            if not content and not tool_calls_list:
                return None
            return result

        elif msg.role == MessageRole.TOOL:
            # Each ToolResultBlock becomes a separate tool message
            results = []
            for b in msg.blocks:
                if isinstance(b, ToolResultBlock):
                    results.append({
                        "role": "tool",
                        "tool_call_id": b.tool_use_id,
                        "content": b.output,
                    })
            return results if results else None

        return None
