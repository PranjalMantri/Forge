from typing import AsyncGenerator
from agent.events import AgentEvent, AgentEventType
from client.llm_client import LLMClient
from client.response import StreamEventType, TokenUsage


class Agent:
    def __init__(self):
        self.client = LLMClient()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.client:
            await self.client.close()
            self.client = None

    async def run(self, message: str):
        yield AgentEvent.agent_start(message)


        final_response: str | None = None
        usage: TokenUsage | None = None

        async for event in self._agentic_loop():
            yield event

            if event.type == AgentEventType.TEXT_COMPLETE:
                final_response = event.data.get("content")
                usage = event.data.get("usage")

        yield AgentEvent.agent_end(final_response, usage)

    async def _agentic_loop(self) -> AsyncGenerator[AgentEvent, None]:
        messages = [{"role": "user", "content": "How are you doing"}]
        response_text = ""
        async for event in self.client.chat_completion(messages, True):

            if event.type == StreamEventType.TEXT_DELTA:
                if event.text_delta:
                    content = event.text_delta.content
                    response_text += content
                    yield AgentEvent.text_delta(content)
            elif event.type == StreamEventType.ERROR:
                yield AgentEvent.agent_error(event.error or "Unknown error occurred")

        if response_text:
            yield AgentEvent.text_complete(response_text)