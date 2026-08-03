from pathlib import Path
import sys
from typing import Any
from config.config import ApprovalPolicy, Config
from config.loader import load_config
from ui.renderer import get_console
from agent.agent import Agent
import asyncio
import click
from agent.events import AgentEventType
from ui.renderer import UI

console = get_console()


class CLI:
    def __init__(self, config: Config):
        self.agent: Agent | None = None
        self.ui = UI(config, console)
        self.config = config

    async def single_run(self, message: str) -> str | None:
        async with Agent(self.config) as agent:
            self.agent = agent
            return await self._process_message(message)

    async def interactive_mode(self) -> str | None:
        self.ui.print_welcome(
            "AI Agent",
            lines=[
                f"model: {self.config.model_name}",
                f"cwd: {self.config.cwd}",
                "commands: /help /config /approval /model /exit",
            ],
        )
        async with Agent(
            self.config, confirmation_callback=self.ui.handle_confirmation
        ) as agent:
            self.agent = agent

            while True:
                try:
                    user_input = console.input("\n[user]> ").strip()

                    if not user_input:
                        continue

                    if user_input.startswith("/"):
                        should_continue = await self._handle_command(user_input)

                        if not should_continue:
                            break
                        continue

                    await self._process_message(user_input)
                except (KeyboardInterrupt, EOFError):
                    console.print("\n[dim]GoodBye![/dim]")
                    raise

    def _get_tool_kind(self, tool_name: str) -> str | None:
        tool_kind = None

        tool = self.agent.session.tool_registry.get_tool(tool_name)
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
                    diff=event.data.get("diff"),
                    exit_code=event.data.get("exit_code"),
                )

        return final_response

    async def _handle_command(self, command: str) -> bool:
        cmd = command.lower().strip()
        parts = cmd.split(maxsplit=1)
        cmd_name = parts[0]
        cmd_args = parts[1] if len(parts) > 1 else ""
        if cmd_name == "/exit" or cmd_name == "/quit":
            return False
        elif command == "/help":
            self.ui.show_help()
        elif command == "/clear":
            self.agent.session.context_manager.clear()
            self.agent.session.loop_detector.clear()
            console.print("[success]Conversation cleared [/success]")
        elif command == "/config":
            console.print("\n[bold]Current Configuration[/bold]")
            console.print(f"  Model: {self.config.model_name}")
            console.print(f"  Temperature: {self.config.temperature}")
            console.print(f"  Approval: {self.config.approval.value}")
            console.print(f"  Working Dir: {self.config.cwd}")
            console.print(f"  Max Turns: {self.config.max_turns}")
        elif cmd_name == "/model":
            if cmd_args:
                self.config.model_name = cmd_args
                console.print(f"[success]Model changed to: {cmd_args} [/success]")
            else:
                console.print(f"Current model: {self.config.model_name}")
        elif cmd_name == "/approval":
            if cmd_args:
                try:
                    approval = ApprovalPolicy(cmd_args)
                    self.config.approval = approval
                    console.print(
                        f"[success]Approval policy changed to: {cmd_args} [/success]"
                    )
                except:
                    console.print(
                        f"[error]Incorrect approval policy: {cmd_args} [/error]"
                    )
                    console.print(
                        f"Valid options: {', '.join(p for p in ApprovalPolicy)}"
                    )
            else:
                console.print(f"Current approval policy: {self.config.approval.value}")
        elif cmd_name == "/stats":
            stats = self.agent.session.get_stats()
            console.print("\n[bold]Session Statistics [/bold]")
            for key, value in stats.items():
                console.print(f"   {key}: {value}")
        elif cmd_name == "/tools":
            tools = self.agent.session.tool_registry.get_tools()
            console.print(f"\n[bold]Available tools ({len(tools)}) [/bold]")
            for tool in tools:
                console.print(f"  • {tool.name}")
        elif cmd_name == "/mcp":
            mcp_servers = self.agent.session.mcp_manager.get_all_servers()
            console.print(f"\n[bold]MCP Servers ({len(mcp_servers)}) [/bold]")
            for server in mcp_servers:
                status = server["status"]
                status_color = "green" if status == "connected" else "red"
                console.print(
                    f"  • {server['name']}: [{status_color}]{status}[/{status_color}] ({server['tools']} tools)"
                )
        # elif cmd_name == "/save":
        #     persistence_manager = PersistenceManager()
        #     session_snapshot = SessionSnapshot(
        #         session_id=self.agent.session.session_id,
        #         created_at=self.agent.session.created_at,
        #         updated_at=self.agent.session.updated_at,
        #         turn_count=self.agent.session.turn_count,
        #         messages=self.agent.session.context_manager.get_messages(),
        #         total_usage=self.agent.session.context_manager.total_usage,
        #     )
        #     persistence_manager.save_session(session_snapshot)
        #     console.print(
        #         f"[success]Session saved: {self.agent.session.session_id}[/success]"
        #     )
        # elif cmd_name == "/sessions":
        #     persistence_manager = PersistenceManager()
        #     sessions = persistence_manager.list_sessions()
        #     console.print("\n[bold]Saved Sessions[/bold]")
        #     for s in sessions:
        #         console.print(
        #             f"  • {s['session_id']} (turns: {s['turn_count']}, updated: {s['updated_at']})"
        #         )
        # elif cmd_name == "/resume":
        #     if not cmd_args:
        #         console.print(f"[error]Usage: /resume <session_id> [/error]")
        #     else:
        #         persistence_manager = PersistenceManager()
        #         snapshot = persistence_manager.load_session(cmd_args)
        #         if not snapshot:
        #             console.print(f"[error]Session does not exist [/error]")
        #         else:
        #             session = Session(
        #                 config=self.config,
        #             )
        #             await session.initialize()
        #             session.session_id = snapshot.session_id
        #             session.created_at = snapshot.created_at
        #             session.updated_at = snapshot.updated_at
        #             session.turn_count = snapshot.turn_count
        #             session.context_manager.total_usage = snapshot.total_usage

        #             for msg in snapshot.messages:
        #                 if msg.get("role") == "system":
        #                     continue
        #                 elif msg["role"] == "user":
        #                     session.context_manager.add_user_message(
        #                         msg.get("content", "")
        #                     )
        #                 elif msg["role"] == "assistant":
        #                     session.context_manager.add_assistant_message(
        #                         msg.get("content", ""), msg.get("tool_calls")
        #                     )
        #                 elif msg["role"] == "tool":
        #                     session.context_manager.add_tool_result(
        #                         msg.get("tool_call_id", ""), msg.get("content", "")
        #                     )

        #             await self.agent.session.client.close()
        #             await self.agent.session.mcp_manager.shutdown()

        #             self.agent.session = session
        #             console.print(
        #                 f"[success]Resumed session: {session.session_id}[/success]"
        #             )
        # elif cmd_name == "/checkpoint":
        #     persistence_manager = PersistenceManager()
        #     session_snapshot = SessionSnapshot(
        #         session_id=self.agent.session.session_id,
        #         created_at=self.agent.session.created_at,
        #         updated_at=self.agent.session.updated_at,
        #         turn_count=self.agent.session.turn_count,
        #         messages=self.agent.session.context_manager.get_messages(),
        #         total_usage=self.agent.session.context_manager.total_usage,
        #     )
        #     checkpoint_id = persistence_manager.save_checkpoint(session_snapshot)
        #     console.print(f"[success]Checkpoint created: {checkpoint_id}[/success]")
        # elif cmd_name == "/restore":
        #     if not cmd_args:
        #         console.print(f"[error]Usage: /restire <checkpoint_id> [/error]")
        #     else:
        #         persistence_manager = PersistenceManager()
        #         snapshot = persistence_manager.load_checkpoint(cmd_args)
        #         if not snapshot:
        #             console.print(f"[error]Checkpoint does not exist [/error]")
        #         else:
        #             session = Session(
        #                 config=self.config,
        #             )
        #             await session.initialize()
        #             session.session_id = snapshot.session_id
        #             session.created_at = snapshot.created_at
        #             session.updated_at = snapshot.updated_at
        #             session.turn_count = snapshot.turn_count
        #             session.context_manager.total_usage = snapshot.total_usage

        #             for msg in snapshot.messages:
        #                 if msg.get("role") == "system":
        #                     continue
        #                 elif msg["role"] == "user":
        #                     session.context_manager.add_user_message(
        #                         msg.get("content", "")
        #                     )
        #                 elif msg["role"] == "assistant":
        #                     session.context_manager.add_assistant_message(
        #                         msg.get("content", ""), msg.get("tool_calls")
        #                     )
        #                 elif msg["role"] == "tool":
        #                     session.context_manager.add_tool_result(
        #                         msg.get("tool_call_id", ""), msg.get("content", "")
        #                     )

        #             await self.agent.session.client.close()
        #             await self.agent.session.mcp_manager.shutdown()

        #             self.agent.session = session
        #             console.print(
        #                 f"[success]Resumed session: {session.session_id}, checkpoint: {checkpoint_id}[/success]"
        #             )
        else:
            console.print(f"[error]Unknown command: {cmd_name}[/error]")

        return True

@click.command()
@click.argument("prompt", required=False)
@click.option(
    "--cwd",
    "-c",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Current working directory",
)
def main(prompt: str, cwd: Path | None):
    try:
        config = load_config(cwd)
    except Exception as e:
        console.print(f"\n[error]Configuration error: {e}[/error]")

    validation_errors = config.validate()

    if validation_errors:
        for error in validation_errors:
            console.print(f"\n[error]{error}[/error]")

        sys.exit(1)

    cli = CLI(config)
    try:
        if prompt:
            asyncio.run(cli.single_run(prompt))
        else:
            asyncio.run(cli.interactive_mode())
    except (KeyboardInterrupt, EOFError, click.Abort):
        pass




main()


