from __future__ import annotations
from pathlib import Path
import os
from typing import Any
from pydantic import BaseModel, Field, model_validator
from dotenv import load_dotenv

load_dotenv()


class ModelConfig(BaseModel):
    name: str = "openai/gpt-oss-20b:free"
    temperature: float = Field(default=0.7, ge=0, le=2.0)
    context_window: int = 256_000

class MCPServerConfig(BaseModel):
    enabled: bool = True
    startup_timeout_sec: float = 10

    # stdio
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    env: dict[str, Any] = Field(default_factory=dict)
    cwd: Path | None = None

    # http/sse
    url: str | None = None

    @model_validator(mode="after")
    def validate_transport(self) -> MCPServerConfig:
        has_command = self.command is not None 
        has_url = self.url is not None

        if not has_command and not has_url:
            raise ValueError(f"MCP Server requires either command(stdio) or url(http/sse)")

        if has_command and has_url:
            raise ValueError(f"MCP Server cannot have both command(stdio) or url(http/sse)")
        
        return self


class ShellEnvironmentPolicy(BaseModel):
    ignore_default_excludes: bool = False
    exclude_patterns: list[str] = Field(
        default_factory=lambda: ["*KEY*", "*TOKEN*", "*SECRET*", "*URL*"]
    )
    set_vars: dict[str, str] = Field(default_factory=dict)


class Config(BaseModel):
    model: ModelConfig = Field(default_factory=ModelConfig)
    cwd: Path = Field(default_factory=Path.cwd)
    shell_environment: ShellEnvironmentPolicy = Field(
        default_factory=ShellEnvironmentPolicy
    )
    max_turns: int = 100
    mcp_servers: dict[str, MCPServerConfig] = Field(default_factory=dict)

    allowed_tools: list[str] | None = Field(
        None, description="If set, only these tools will be available to the agent"
    )

    developer_instructions: str | None = None
    user_instructions: str | None = None

    debug: bool = False

    @property
    def api_key(self):
        return os.environ.get("API_KEY")

    @property
    def base_url(self):
        return os.environ.get("BASE_URL")

    @property
    def model_name(self):
        return self.model.name

    @model_name.setter
    def model_name(self, value: str) -> None:
        self.model.name = value

    @property
    def temperature(self):
        return self.model.temperature

    @temperature.setter
    def temperature(self, value: float) -> None:
        self.model.temperature = value

    def validate(self) -> list[str]:
        errors: list[str] = []

        if not self.api_key:
            errors.append(f"No API Key found. Set API_KEY environment variable")

        if not self.base_url:
            errors.append(f"No base url found. Set BASE_URL environment variable")

        if not self.cwd.exists():
            errors.append(f"Working directory does not exist: {self.cwd}")

        return errors

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
