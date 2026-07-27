from pathlib import Path
from typing import AsyncGenerator
from agent.events import AgentEvent, AgentEventType
from client.llm_client import LLMClient
from client.response import StreamEventType, TokenUsage, ToolCall, ToolResultMessage
from context.context_manager import ContextManager
from tools.registry import create_default_registry


class Agent:
    def __init__(self):
        self.client = LLMClient()
        self.context_manager = ContextManager()
        self.tool_registry = create_default_registry()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.client:
            await self.client.close()
            self.client = None

    async def run(self, message: str):
        yield AgentEvent.agent_start(message)
        self.context_manager.add_user_message(message)

        final_response: str | None = None
        usage: TokenUsage | None = None

        async for event in self._agentic_loop():
            yield event

            if event.type == AgentEventType.TEXT_COMPLETE:
                final_response = event.data.get("content")
                usage = event.data.get("usage")

        yield AgentEvent.agent_end(final_response, usage)

    async def _agentic_loop(self) -> AsyncGenerator[AgentEvent, None]:
        response_text = ""
        usage: TokenUsage | None = None

        tools_schema = self.tool_registry.get_schemas()
        tool_calls: list[ToolCall] = []
        tool_call_results: list[ToolResultMessage] = []

        async for event in self.client.chat_completion(
            self.context_manager.get_messages(),
            tools=tools_schema if tools_schema else None,
        ):
            if event.type == StreamEventType.TEXT_DELTA:
                if event.text_delta:
                    content = event.text_delta.content
                    response_text += content

                    yield AgentEvent.text_delta(content)
            elif event.type == StreamEventType.ERROR:
                yield AgentEvent.agent_error(event.error or "Unknown error occurred")
            elif event.type == StreamEventType.TOOL_CALL_COMPLETE:
                if event.tool_call:
                    tool_calls.append(event.tool_call)
            elif event.type == StreamEventType.REASONING_DELTA:
                if event.reasoning:
                    yield AgentEvent.reasoning_delta(event.reasoning)
            elif event.type == StreamEventType.MESSAGE_COMPLETE:
                if event.usage:
                    usage = event.usage

        self.context_manager.add_assistant_message(response_text or None)

        if response_text or usage:
            yield AgentEvent.text_complete(response_text, usage)

        for tool_call in tool_calls:
            yield AgentEvent.tool_call_start(
                call_id=tool_call.call_id,
                name=tool_call.name,
                arguments=tool_call.arguments,
            )

            result = await self.tool_registry.invoke(
                name=tool_call.name, params=tool_call.arguments, cwd=Path.cwd()
            )

            yield AgentEvent.tool_call_complete(
                call_id=tool_call.call_id, name=tool_call.name, result=result
            )

            tool_call_results.append(
                ToolResultMessage(
                    tool_call_id=tool_call.call_id,
                    content=result.to_model_output(),
                    is_error=not result.success,
                )
            )

        for tool_result in tool_call_results:
            self.context_manager.add_tool_result(
                call_id=tool_result.tool_call_id, content=tool_result.content
            )
