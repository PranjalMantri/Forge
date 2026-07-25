from typing import Any

from prompts.system_prompt import get_system_prompt
from dataclasses import dataclass
from util.text import count_tokens

@dataclass
class MessageItem:
    role: str 
    content: str 
    tokenCount: int | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"role": self.role}

        if self.content:
            result["content"] = self.content

        return result

class ContextManager:
    def __init__(self):
        self._system_prompt = get_system_prompt()
        self._messages: list[MessageItem] = []
        self._model_name = "openai/gpt-oss-20b:free"

    def add_user_message(self, content: str) -> None:
        item = MessageItem(
            role = "user",
            content = content,
            tokenCount=count_tokens(content, self._model_name)
        )

        self._messages.append(item)

    def add_assistant_message(self, content: str | None) -> None:
        item = MessageItem(
            role = "assitant",
            content = content or "",
            tokenCount=count_tokens(content, self._model_name)
        )

        self._messages.append(item)

    def get_messages(self) -> list[dict[str, Any]]:
        messages = []

        if self._system_prompt:
            messages.append(
                {
                    "role": "system",
                    "content": self._system_prompt
                }
            )

        for item in self._messages:
            messages.append(item.to_dict())

        return messages