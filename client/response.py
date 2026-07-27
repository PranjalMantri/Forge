from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class StreamEventType(str, Enum):
    TEXT_DELTA = "text_delta"
    MESSAGE_COMPLETE = "message_complete"
    ERROR = "error"
    REASONING_DELTA = "reasoning_delta"

    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_DELTA = "tool_call_delta"
    TOOL_CALL_COMPLETE = "tool_call_complete"


@dataclass
class TextDelta:
    content: str

    def __str__(self):
        return self.content


@dataclass
class TokenUsage:
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    total_tokens: int = 0

    def __add__(self, other: TokenUsage):
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            cached_tokens=self.cached_tokens + other.cached_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )


@dataclass
class ToolCallDelta:
    call_id: str
    name: str | None = None
    arguments_delta: str = ""


@dataclass
class ToolCall:
    call_id: str
    name: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResultMessage:
    tool_call_id: str
    content: str
    is_error: bool

    def to_openai_message(self) -> dict[str, Any]:
        return {
            "role": "tool",
            "tool_call_id": self.tool_call_id,
            "content": self.content,
        }


@dataclass
class StreamEvent:
    type: StreamEventType
    text_delta: TextDelta | None = None
    finish_reason: str | None = None
    usage: TokenUsage | None = None
    error: str | None = None
    reasoning: str | None = None
    tool_call_delta: ToolCallDelta | None = None
    tool_call: ToolCall | None = None

    @classmethod
    def stream_error(cls, error: str):
        return StreamEvent(type=StreamEventType.ERROR, error=error)


def parse_tool_call_arguments(arguments: str | None) -> dict[str, Any]:
    import json

    if not arguments:
        return {}

    try:
        return json.loads(arguments)
    except json.JSONDecodeError as e:
        return {"raw_arguments": arguments}
