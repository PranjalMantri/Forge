from typing import Any

from rich import get_console
from agent.agent import Agent
from client.llm_client import LLMClient
import asyncio
import click 
from agent.events import AgentEventType
from ui.renderer import UI

console = get_console()

class CLI:
    def __init__(self):
        self.agent: Agent | None = None
        self.ui = UI(console)
    
    async def single_run(self, message: str):
        async with Agent() as agent:
            self.agent = agent
            await self._process_message(message)

    async def _process_message(self, message: str):
        if not self.agent:
            return None 

        async for event in self.agent.run(message):
            if event.type == AgentEventType.TEXT_DELTA:
                content = event.data.get("content", "")
                self.ui.stream_assistant_delta(content)
            elif event.type == AgentEventType.AGENT_ERROR:
                self.ui.stream_assistant_delta(f"Something went wrong: {event.data["error"]}")
            


@click.command()
@click.argument("prompt", required=False)
def main(prompt: str):
    cli = CLI()
    # messages = [{"role": "user", "content": prompt}]

    if prompt:
        asyncio.run(cli.single_run(prompt))
        

main()

