from __future__ import annotations
from dataclasses import dataclass
from enum import Enum


class StreamEventType(str, Enum):
    TEXT_DELTA = "text_delta"
    MESSAGE_COMPLETE = "message_complete"
    ERROR = "error"


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
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.cached_tokens += other.cached_tokens
        self.total_tokens += other.total_tokens


@dataclass
class StreamEvent:
    type: StreamEventType
    text_delta: TextDelta | None = None
    finish_reason: str | None = None
    usage: TokenUsage | None = None
    error: str | None = None
    reasoning: str | None = None


    @classmethod
    def stream_error(cls, error: str):
        return StreamEvent(
            type = StreamEventType.ERROR,
            error = error 
    )