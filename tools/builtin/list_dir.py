from pathlib import Path

from pydantic import BaseModel, Field
import os
from tools.base import Tool, ToolInvocation, ToolKind, ToolResult
from util.paths import resolve_path
import fnmatch
import sys
import asyncio


class ListDirToolParams(BaseModel):
    path: str = Field(
        ".", description="Directory path to list (default: current directory)"
    )
    include_hidden: bool = Field(
        False,
        description="Whether to include hidden files and directories (default: false)",
    )


class ListDirTool(Tool):
    name = "list_dir"
    description = "List contents of a directory"
    kind = ToolKind.READ
    schema = ListDirToolParams

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        params = ListDirToolParams(**invocation.params)
        dir_path = resolve_path(invocation.cwd, params.path)

        if not dir_path.exists() or not dir_path.is_dir():
            return ToolResult.error_result(f"Invalid path to directory: {dir_path}")

        try:
            items = sorted(
                dir_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())
            )
        except Exception as e:
            return ToolResult.error_result(f"Error listing directory: {e}")

        if not params.include_hidden:
            items = [item for item in items if not item.name.startswith(".")]

        if not items:
            return ToolResult.success_result(
                f"Directory is empty: {str(dir_path)}",
                metadata={"path": str(dir_path), "entires": 0},
            )

        lines = []

        for item in items:
            if item.is_dir():
                lines.append(f"{item.name}/")
            else:
                lines.append(item.name)

        return ToolResult.success_result(
            "\n".join(lines),
            metadata={
                "path": str(dir_path),
                "entries": len(items),
            },
        )
