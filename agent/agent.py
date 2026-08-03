from pathlib import Path
from typing import AsyncGenerator, Callable
from agent.events import AgentEvent, AgentEventType
from agent.session import Session
from client.response import StreamEventType, TokenUsage, ToolCall, ToolResultMessage
from config.config import Config
import json

from prompts.system_prompt import create_loop_breaker_prompt
from tools.base import ToolConfirmation


class Agent:
    def __init__(
        self,
        config: Config,
        confirmation_callback: Callable[[ToolConfirmation], bool] | None = None,
    ):
        self.config = config
        self.session: Session | None = Session(config)
        self.session.approval_manager.confirmation_callback = confirmation_callback

    async def __aenter__(self):
        await self.session.initialize()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.session and self.session.client:
            await self.session.client.close()
            await self.session.mcp_manager.shutdown()
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

            # check for context overflow here before calling the LLM
            if self.session.context_manager.needs_compression():
                summary, usage = await self.session.chat_compactor.compress(
                    self.session.context_manager
                )

                if summary:
                    self.session.context_manager.replace_with_summary(summary)
                    self.session.context_manager.set_latest_usage(usage)
                    self.session.context_manager.add_usage(usage)

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
                self.session.loop_detector.record_action("response", text=response_text)

            if not tool_calls:
                if usage:
                    self.session.context_manager.add_usage(usage)
                    self.session.context_manager.set_latest_usage(usage)

                self.session.context_manager.prune_tool_outputs()
                return

            for tool_call in tool_calls:
                yield AgentEvent.tool_call_start(
                    call_id=tool_call.call_id,
                    name=tool_call.name,
                    arguments=tool_call.arguments,
                )

                self.session.loop_detector.record_action(
                    "tool_call", tool_name=tool_call.name, args=tool_call.arguments
                )

                result = await self.session.tool_registry.invoke(
                    name=tool_call.name,
                    params=tool_call.arguments,
                    cwd=Path.cwd(),
                    approval_manager=self.session.approval_manager,
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

            loop_detection_error = self.session.loop_detector.check_for_loop()
            if loop_detection_error:
                loop_prompt = create_loop_breaker_prompt(loop_detection_error)
                self.session.context_manager.add_user_message(loop_prompt)

            if usage:
                self.session.context_manager.set_latest_usage(usage)
                self.session.context_manager.add_usage(usage)

            self.session.context_manager.prune_tool_outputs()

        yield AgentEvent.agent_error(f"Maximum turns ({max_turns}) reached")
