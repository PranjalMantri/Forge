from pathlib import Path
from typing import Any
from config.config import Config
from tools.builtin import get_all_tools
from tools.base import Tool, ToolInvocation, ToolResult
import logging
from tools.subagent import get_default_subagent_definitions, SubAgentTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    def __init__(self, config: Config):
        self._tools: dict[str, Tool] = {}
        self._mcp_tools: dict[str, Tool] = {}
        self.config = config

    def register(self, tool: Tool) -> None:
        if tool in self._tools:
            logger.warning(f"Overwriting an existing tool: {tool.name}")

        self._tools[tool.name] = tool
        logger.debug(f"Registered tool: {tool.name}")

    def register_mcp_tools(self, tool: Tool) -> None:
        if tool in self._mcp_tools:
            logger.warning(f"Overwriting an existing tool: {tool.name}")

        self._mcp_tools[tool.name] = tool
        logger.debug(f"Registered MCP tool: {tool.name}")

    def unregister(self, tool: Tool) -> bool:
        if tool.name in self._tools:
            del self._tools[tool.name]
            return True

        return False

    def get_tool(self, name: str) -> Tool | None:
        if name in self._tools:
            return self._tools[name]
        elif name in self._mcp_tools:
            return self._mcp_tools[name]

        return None

    def get_tools(self) -> list[Tool]:
        tools = []

        for tool in self._tools.values():
            tools.append(tool)

        for mcp_tool in self._mcp_tools.values():
            tools.append(mcp_tool)

        if self.config.allowed_tools:
            allowed_tools = set(self.config.allowed_tools)
            tools = [t for t in tools if t.name in allowed_tools]

        return tools

    def get_schemas(self):
        return [tool.to_openai_schema() for tool in self.get_tools()]

    async def invoke(self, name: str, params: dict[str, Any], cwd: Path) -> ToolResult:
        tool = self.get_tool(name)

        if not tool:
            return ToolResult.error_result(
                f"Unknown tool called: {name}", metadata={"tool_name": name}
            )

        validation_errors = tool.validate_params(params)

        if validation_errors:
            return ToolResult.error_result(
                f"Invalid parameters: ({";".join(validation_errors)})",
                metadata={"tool_name": name, "validation_errors": validation_errors},
            )

        invocation = ToolInvocation(params=params, cwd=cwd)

        try:
            result = await tool.execute(invocation)
        except Exception as e:
            logger.exception(f"Tool {name} raised unexpected error")
            result = ToolResult.error_result(
                f"Error while executing tool: {str(e)}",
                metadata={"tool_name": tool.name},
            )

        return result


def create_default_registry(config: Config):
    registry = ToolRegistry(config)

    for tool in get_all_tools():
        registry.register(tool(config))

    for subagent_definition in get_default_subagent_definitions():
        registry.register(SubAgentTool(config=config, definition=subagent_definition))

    return registry
