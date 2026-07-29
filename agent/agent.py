from pathlib import Path
from typing import AsyncGenerator
from agent.events import AgentEvent, AgentEventType
from agent.session import Session
from client.response import StreamEventType, TokenUsage, ToolCall, ToolResultMessage
from config.config import Config
import json


class Agent:
    def __init__(self, config: Config):
        self.config = config
        self.session: Session | None = Session(config)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.session and self.session.client:
            await self.session.client.close()
            self.session = None

    async def run(self, message: str):
        yield AgentEvent.agent_start(message)
        self.session.context_manager.add_user_message(message)

        final_response: str | None = None
        usage: TokenUsage | None = None

        async for event in self._agentic_loop():
            yield event

            if event.type == AgentEventType.TEXT_COMPLETE:
                final_response = event.data.get("content")
                usage = event.data.get("usage")

        yield AgentEvent.agent_end(final_response, usage)

    async def _agentic_loop(self) -> AsyncGenerator[AgentEvent, None]:
        max_turns = self.config.max_turns

        for i in range(max_turns):
            self.session.increment_turn()
            response_text = ""
            usage: TokenUsage | None = None

            tools_schema = self.session.tool_registry.get_schemas()
            tool_calls: list[ToolCall] = []
            tool_call_results: list[ToolResultMessage] = []

            async for event in self.session.client.chat_completion(
                self.session.context_manager.get_messages(),
                tools=tools_schema if tools_schema else None,
            ):
                if event.type == StreamEventType.TEXT_DELTA:
                    if event.text_delta:
                        content = event.text_delta.content
                        response_text += content

                        yield AgentEvent.text_delta(content)
                elif event.type == StreamEventType.ERROR:
                    yield AgentEvent.agent_error(
                        event.error or "Unknown error occurred"
                    )
                elif event.type == StreamEventType.TOOL_CALL_COMPLETE:
                    if event.tool_call:
                        tool_calls.append(event.tool_call)
                elif event.type == StreamEventType.REASONING_DELTA:
                    if event.reasoning:
                        yield AgentEvent.reasoning_delta(event.reasoning)
                elif event.type == StreamEventType.MESSAGE_COMPLETE:
                    if event.usage:
                        usage = event.usage

            self.session.context_manager.add_assistant_message(
                content=response_text or None,
                tool_calls=(
                    [
                        {
                            "id": tc.call_id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments),
                            },
                        }
                        for tc in tool_calls
                    ]
                    if tool_calls
                    else None
                ),
            )

            if response_text or usage:
                yield AgentEvent.text_complete(response_text, usage)

            if not tool_calls:
                return

            for tool_call in tool_calls:
                yield AgentEvent.tool_call_start(
                    call_id=tool_call.call_id,
                    name=tool_call.name,
                    arguments=tool_call.arguments,
                )

                result = await self.session.tool_registry.invoke(
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
                self.session.context_manager.add_tool_result(
                    call_id=tool_result.tool_call_id, content=tool_result.content
                )
