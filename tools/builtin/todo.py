from pathlib import Path
import uuid

from pydantic import BaseModel, Field
import os
from config.config import Config
from tools.base import Tool, ToolInvocation, ToolKind, ToolResult
from util.paths import is_binary_file, resolve_path
import re
import os


class TodoToolParams(BaseModel):
    action: str = Field(..., description="Action: 'add', 'complete', 'list', 'clear'")
    id: str | None = Field(None, description="Todo ID (for complete)")
    content: str | None = Field(None, description="Todo content (for add)")


class TodoTool(Tool):
    name = "todo"
    description = "Manage a task list for the current session. Use this to track progress on multi-step tasks."
    kind = ToolKind.MEMORY
    schema = TodoToolParams

    def __init__(self, config: Config) -> None:
        super().__init__(config)
        self._todos: dict[str, str] = {}

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        params = TodoToolParams(**invocation.params)

        if params.action.lower() == "add":
            if not params.content:
                return ToolResult.error_result(
                    f"`content` is required for action `add`"
                )

            id = str(uuid.uuid4())[:8]
            self._todos[id] = params.content

            return ToolResult.success_result(f"Added todo: [{id}]: {params.content}")
        elif params.action == "complete":
            if not params.id:
                return ToolResult.error_result(
                    f"`id` is required for action `complete`"
                )

            if params.id not in self._todos:
                return ToolResult.error_result(f"Invalid todo id: {params.id}")

            content = self._todos.pop(params.id)
            return ToolResult.success_result(
                f"Todo complete: [{params.id}]: {self._todos[params.id]}"
            )
        elif params.action.lower() == "list":
            if len(self._todos) == 0:
                return ToolResult.success_result(f"No todos")

            todos = [f"Todos:"]

            for todo_id, content in self._todos:
                todos.append(f"{todo_id}: {content}")

            return ToolResult.success_result("\n".join(todos))
        elif params.action.lower() == "clear":
            count = len(self._todos)
            self._todos.clear()

            return ToolResult.success_result(f"Cleared {count} todos")
        else:
            ToolResult.error_result(f"Unknown action: {params.action}")
