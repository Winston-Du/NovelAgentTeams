"""
Layer 2: Persistence - Session Data Model

Core data structures for conversation history following agent-harness patterns.
"""
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


# === Content Blocks ===

class ContentBlock:
    """Base class for message content blocks."""
    pass


@dataclass
class TextBlock(ContentBlock):
    text: str


@dataclass
class ToolUseBlock(ContentBlock):
    id: str
    name: str
    input: str  # JSON string


@dataclass
class ToolResultBlock(ContentBlock):
    tool_use_id: str
    tool_name: str
    output: str
    is_error: bool = False


# === Conversation Message ===

@dataclass
class ConversationMessage:
    role: MessageRole
    blocks: list[ContentBlock] = field(default_factory=list)
    usage: Optional["TokenUsage"] = None  # Only for Assistant messages

    @staticmethod
    def user_text(text: str) -> "ConversationMessage":
        return ConversationMessage(role=MessageRole.USER, blocks=[TextBlock(text)])

    @staticmethod
    def assistant(blocks: list[ContentBlock], usage=None) -> "ConversationMessage":
        return ConversationMessage(role=MessageRole.ASSISTANT, blocks=blocks, usage=usage)

    @staticmethod
    def tool_result(tool_use_id: str, tool_name: str, output: str,
                    is_error: bool = False) -> "ConversationMessage":
        return ConversationMessage(
            role=MessageRole.TOOL,
            blocks=[ToolResultBlock(tool_use_id, tool_name, output, is_error)]
        )

    def get_text(self) -> str:
        """Extract all text content from this message."""
        parts = []
        for block in self.blocks:
            if isinstance(block, TextBlock):
                parts.append(block.text)
        return "\n".join(parts)

    def get_tool_uses(self) -> list[ToolUseBlock]:
        """Extract all tool use blocks."""
        return [b for b in self.blocks if isinstance(b, ToolUseBlock)]

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict."""
        blocks_data = []
        for block in self.blocks:
            if isinstance(block, TextBlock):
                blocks_data.append({"type": "text", "text": block.text})
            elif isinstance(block, ToolUseBlock):
                blocks_data.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })
            elif isinstance(block, ToolResultBlock):
                blocks_data.append({
                    "type": "tool_result",
                    "tool_use_id": block.tool_use_id,
                    "tool_name": block.tool_name,
                    "output": block.output,
                    "is_error": block.is_error,
                })

        result = {"role": self.role.value, "blocks": blocks_data}
        if self.usage:
            result["usage"] = {
                "input_tokens": self.usage.input_tokens,
                "output_tokens": self.usage.output_tokens,
                "total_tokens": self.usage.total_tokens,
            }
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "ConversationMessage":
        """Deserialize from JSON-compatible dict."""
        from .api_client import TokenUsage

        role = MessageRole(data["role"])
        blocks = []
        for b in data.get("blocks", []):
            btype = b["type"]
            if btype == "text":
                blocks.append(TextBlock(text=b["text"]))
            elif btype == "tool_use":
                blocks.append(ToolUseBlock(id=b["id"], name=b["name"], input=b["input"]))
            elif btype == "tool_result":
                blocks.append(ToolResultBlock(
                    tool_use_id=b["tool_use_id"],
                    tool_name=b["tool_name"],
                    output=b["output"],
                    is_error=b.get("is_error", False),
                ))

        usage = None
        if "usage" in data:
            u = data["usage"]
            usage = TokenUsage(
                input_tokens=u.get("input_tokens", 0),
                output_tokens=u.get("output_tokens", 0),
                total_tokens=u.get("total_tokens", 0),
            )

        return cls(role=role, blocks=blocks, usage=usage)


# === Session ===

@dataclass
class Session:
    version: int = 1
    messages: list[ConversationMessage] = field(default_factory=list)

    def to_json(self) -> str:
        """Serialize session to JSON string."""
        data = {
            "version": self.version,
            "messages": [msg.to_dict() for msg in self.messages],
        }
        return json.dumps(data, ensure_ascii=False, indent=2)

    def to_dict(self) -> dict:
        """Serialize session to dict."""
        return {
            "version": self.version,
            "messages": [msg.to_dict() for msg in self.messages],
        }

    @classmethod
    def from_json(cls, json_str: str) -> "Session":
        """Deserialize session from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        """Deserialize session from dict."""
        return cls(
            version=data.get("version", 1),
            messages=[ConversationMessage.from_dict(m) for m in data.get("messages", [])],
        )

    def message_count(self) -> int:
        return len(self.messages)

    def total_estimated_tokens(self) -> int:
        """Estimate total tokens using len/4 heuristic."""
        total = 0
        for msg in self.messages:
            for block in msg.blocks:
                if isinstance(block, TextBlock):
                    total += len(block.text) // 4
                elif isinstance(block, ToolUseBlock):
                    total += len(block.input) // 4
                elif isinstance(block, ToolResultBlock):
                    total += len(block.output) // 4
        return total
