from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field
from config.config import Config
from config.loader import get_config_dir
from tools.base import Tool, ToolInvocation, ToolKind, ToolResult
from util.paths import is_binary_file, resolve_path
import json


class MemoryToolParams(BaseModel):
    action: str = Field(
        ..., description="Action: 'set', 'get', 'delete', 'list', 'clear'"
    )
    key: str | None = Field(
        None, description="Memory key (required for `set`, `get`, `delete`)"
    )
    value: str | None = Field(None, description="Value to store (required for `set`)")


class MemoryTool(Tool):
    name = "memory"
    description = "Store and retrieve persistent memory. Use this to remember user preferences, important context or notes."
    kind = ToolKind.MEMORY
    schema = MemoryToolParams

    def _load_memory(self) -> dict[str, Any]:
        config_dir = get_config_dir()
        config_dir.mkdir(parents=True, exist_ok=True)
        path = config_dir / "user_memory.json"

        if not path.exists():
            return {"entries": {}}

        try:
            content = path.read_text(encoding="utf-8")
            return json.loads(content)
        except:
            return {"entries": {}}

    def _save_memory(self, memory: dict) -> None:
        config_dir = get_config_dir()
        config_dir.mkdir(parents=True, exist_ok=True)
        path = config_dir / "user_memory.json"

        try:
            path.write_text(json.dumps(memory, indent=2, ensure_ascii=False))
        except:
            pass

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        params = MemoryToolParams(**invocation.params)

        if params.action.lower() == "set":
            if not params.key:
                return ToolResult.error_result(f"`key` is required for `set`")

            if not params.value:
                return ToolResult.error_result(f"`value` is required for `set`")

            memory = self._load_memory()
            memory["entries"][params.key] = params.value
            self._save_memory(memory)

            return ToolResult.success_result(f"Set memory: {params.key}")
        elif params.action.lower() == "get":
            if not params.key:
                return ToolResult.error_result(f"`key` is required for `get`")

            memory = self._load_memory()

            if params.key not in memory["entries"]:
                return ToolResult.error_result(
                    f"Memory item not found: {params.key}", metadata={"found": False}
                )

            return ToolResult.success_result(
                f"Memory found {params.key}: {memory['entries'][params.key]}",
                metadata={"found": True},
            )
        elif params.action.lower() == "delete":
            if not params.key:
                return ToolResult.error_result(f"`key` is required for `delete`")

            memory = self._load_memory()

            if params.key not in memory["entries"]:
                return ToolResult.error_result(f"Memory item not found: {params.key}")

            value = memory["entries"][params.key]
            del memory["entries"][params.key]
            self._save_memory(memory)

            return ToolResult.success_result(f"Memory delete {params.key}: {value}")
        elif params.action.lower() == "list":
            memory = self._load_memory()
            entries = memory.get("entries", {})

            if not entries:
                return ToolResult.success_result(
                    f"No memory found", metadata={"found": False}
                )

            lines = [f"Stored Memories"]

            for key, value in sorted(entries.items()):
                lines.append(f" {key}: {value}")

            return ToolResult.success_result("\n".join(lines), metadata={"found": True})
        elif params.action.lower() == "clear":
            memory = self._load_memory()
            count = len(memory.get("entries", {}))
            memory["entries"] = {}
            self._save_memory(memory)
            return ToolResult.success_result(f"Cleared {count} memory entries")
        else:
            return ToolResult.error_result(f"Unknown action: {params.action}")
