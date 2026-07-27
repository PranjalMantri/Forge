from pathlib import Path
import sys
from typing import Any
from ui.renderer import get_console
from agent.agent import Agent
import asyncio
import click
from agent.events import AgentEventType
from ui.renderer import UI

console = get_console()


class CLI:
    def __init__(self):
        self.agent: Agent | None = None
        self.ui = UI(console)

    async def single_run(self, message: str) -> str | None:
        async with Agent() as agent:
            self.agent = agent
            return await self._process_message(message)

    async def interactive_mode(self) -> str | None:
        self.ui.print_welcome(
            "AI Agent",
            lines=[
                f"model: model name",
                f"cwd: {Path.cwd()}",
                "commands: /help /config /approval /model /exit",
            ],
        )
        async with Agent() as agent:
            self.agent = agent

            while True:
                try:
                    user_input = console.input("\n[user]> ").strip()

                    if not user_input:
                        continue

                    if user_input == "/exit":
                        break

                    await self._process_message(user_input)
                except (KeyboardInterrupt, EOFError):
                    console.print("\n[dim]GoodBye![/dim]")
                    raise

    def _get_tool_kind(self, tool_name: str) -> str | None:
        tool_kind = None

        tool = self.agent.tool_registry.get_tool(tool_name)
        if tool:
            tool_kind = tool.kind.value

        return tool_kind

    async def _process_message(self, message: str):
        if not self.agent:
            return None

        assistant_streaming = False
        assistant_reasoning = False
        final_response: str | None = None

        async for event in self.agent.run(message):
            if event.type == AgentEventType.TEXT_DELTA:
                if assistant_streaming == False:
                    self.ui.begin_assistant()
                    assistant_streaming = True

                content = event.data.get("content", "")
                self.ui.stream_assistant_delta(content)
            elif event.type == AgentEventType.TEXT_COMPLETE:
                final_response = event.data.get("content", "")
                self.ui.end_assistant()
                assistant_streaming = False
            elif event.type == AgentEventType.REASONING_DELTA:
                if not assistant_reasoning:
                    self.ui.begin_reasoning()
                    assistant_reasoning = True

                reasoning = event.data.get("content", "")
                self.ui.stream_assistant_reasoning(reasoning)
            elif event.type == AgentEventType.AGENT_ERROR:
                error = event.data["error"] or "Unknown error occurred"
                self.ui.assistant_error(error)
            elif event.type == AgentEventType.TOOL_CALL_START:
                tool_name = event.data.get("name", "Unknown tool")
                tool_kind = self._get_tool_kind(tool_name)

                self.ui.tool_call_start(
                    call_id=event.data.get("call_id") or "",
                    name=tool_name,
                    tool_kind=tool_kind,
                    arguments=event.data.get("arguments", {}),
                )
            elif event.type == AgentEventType.TOOL_CALL_COMPLETE:
                tool_name = event.data.get("name", "Unknown tool")
                tool_kind = self._get_tool_kind(tool_name)

                self.ui.tool_call_complete(
                    call_id=event.data.get("call_id") or "",
                    name=tool_name,
                    tool_kind=tool_kind,
                    success=event.data.get("success", False),
                    output=event.data.get("output", ""),
                    truncated=event.data.get("truncated", False),
                    metadata=event.data.get("metadata"),
                    error=event.data.get("error"),
                )

        return final_response


@click.command()
@click.argument("prompt", required=False)
def main(prompt: str):
    cli = CLI()
    try:
        if prompt:
            asyncio.run(cli.single_run(prompt))
        else:
            asyncio.run(cli.interactive_mode())
    except (KeyboardInterrupt, EOFError, click.Abort):
        pass


main()


def test_function(message: str) -> None:
    return None
