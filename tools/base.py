from __future__ import annotations
import abc
from enum import Enum
from pathlib import Path
from typing import Any
from pydantic import BaseModel, ValidationError
from dataclasses import dataclass, field
from pydantic.json_schema import model_json_schema

from config.config import Config


class ToolKind(str, Enum):
    READ = "read"
    WRITE = "write"
    SHELL = "shell"
    NETWORK = "network"
    MEMORY = "memory"
    MCP = "mcp"


@dataclass
class ToolInvocation:
    cwd: Path
    params: dict[str, Any]


@dataclass
class FileDiff:
    path: Path
    old_content: str
    new_content: str

    is_new_file: bool = False
    is_deletion: bool = False

    def create_diff(self):
        import difflib

        old_lines = self.old_content.splitlines(keepends=True)
        new_lines = self.new_content.splitlines(keepends=True)

        if old_lines and not old_lines[-1].endswith("\n"):
            old_lines[-1] += "\n"

        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] += "\n"

        old_name = "/dev/null" if self.is_new_file else str(self.path)
        new_name = "/dev/null" if self.is_deletion else str(self.path)

        diff = difflib.unified_diff(
            old_lines, new_lines, fromfile=old_name, tofile=new_name
        )

        return "".join(diff)


@dataclass
class ToolResult:
    success: bool
    output: str
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    truncated: bool = False

    exit_code: int | None = None
    diff: FileDiff | None = None

    @classmethod
    def error_result(cls, error_message: str, output: str = "", **kwargs) -> ToolResult:
        return cls(success=False, output=output, error=error_message, **kwargs)

    @classmethod
    def success_result(
        cls, output: str, truncated: bool = False, **kwargs
    ) -> ToolResult:
        return cls(success=True, output=output, truncated=truncated, **kwargs)

    def to_model_output(self) -> str:
        if self.success:
            return self.output

        if self.error:
            return f"Error: {self.error}\n\n Output: {self.output}"


@dataclass
class ToolConfirmation:
    tool_name: str
    params: dict[str, Any]
    description: str


class Tool(abc.ABC):
    name: str = "base_tool"
    description: str = "Base Tool"
    kind: ToolKind = ToolKind.READ

    def __init__(self, config: Config) -> None:
        self.config = config

    @property
    def schema(self) -> dict[str, Any] | type["BaseModel"]:
        raise NotImplementedError("Tool must define schema property")

    @abc.abstractmethod
    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        pass

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        schema = self.schema

        if isinstance(schema, type) and issubclass(schema, BaseModel):
            try:
                schema(**params)
            except ValidationError as e:
                errors = []

                for error in e.errors():
                    field = ".".join(str(x) for x in error.get("loc", []))
                    msg = error.get("msg", "Validation error")
                    errors.append(f"Parameter '{field}': {msg}")
            except Exception as e:
                return [str(e)]

        return []

    def is_mutating(self, params: dict[str, Any]) -> bool:
        return (
            True
            if self.kind
            in {ToolKind.WRITE, ToolKind.SHELL, ToolKind.MEMORY, ToolKind.NETWORK}
            else False
        )

    async def get_confirmation(
        self, invocation: ToolInvocation
    ) -> ToolConfirmation | None:
        if not self.is_mutating(invocation.params):
            return None

        return ToolConfirmation(
            tool_name=self.name,
            params=invocation.params,
            description=f"Execute {self.name}",
        )

    def to_openai_schema(self) -> dict[str, Any]:
        schema = self.schema

        if isinstance(schema, type) and issubclass(schema, BaseModel):
            json_schema = model_json_schema(schema)

            return {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": json_schema.get("properties", []),
                    "required": json_schema.get("required", []),
                },
            }

        if isinstance(schema, dict):
            result = {"name": self.name, "description": self.description}

            if "parameters" in schema:
                result["parameters"] = schema["parameters"]

            return result

        raise ValueError(f"Invalid schema type for tool {self.name}: {type(schema)}")
