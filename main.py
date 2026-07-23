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

    async def _process_message(self, message: str):
        if not self.agent:
            return None 

        assistant_streaming = False
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
            elif event.type == AgentEventType.AGENT_ERROR:
                error = event.data["error"] or "Unknown error occurred"
                self.ui.assistant_error(error)

        return final_response


@click.command()
@click.argument("prompt", required=False)
def main(prompt: str):
    cli = CLI()
    # messages = [{"role": "user", "content": prompt}]

    if prompt:
        result = asyncio.run(cli.single_run(prompt))

        if result is None:
            sys.exit(1)
        

main()

