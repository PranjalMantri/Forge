from pathlib import Path

from pydantic import BaseModel, Field
import os
from tools.base import Tool, ToolConfirmation, ToolInvocation, ToolKind, ToolResult
from util.paths import resolve_path
import fnmatch
import sys
import asyncio

BLOCKED_COMMANDS = {
    "rm -rf /",
    "rm -rf ~",
    "rm -rf /*",
    "dd if=/dev/zero",
    "dd if=/dev/random",
    "mkfs",
    "fdisk",
    "parted",
    ":(){ :|:& };:",
    "chmod 777 /",
    "chmod -R 777",
    "shutdown",
    "reboot",
    "halt",
    "poweroff",
    "init 0",
    "init 6",
}


class ShellToolParams(BaseModel):
    command: str = Field(..., description="The shell command to execute")
    timeout: int = Field(
        120, ge=1, le=600, description="Timeout in seconds (default: 120)"
    )
    cwd: str | None = Field(None, description="Working directory for the command")


class ShellTool(Tool):
    name = "shell"
    description = "Execute a shell command. Use this for running system commands, scripts and CLI tools."
    kind = ToolKind.SHELL
    schema = ShellToolParams

    async def get_confirmation(
        self, invocation: ToolInvocation
    ) -> ToolConfirmation | None:
        params = ShellToolParams(**invocation.params)

        for blocked in BLOCKED_COMMANDS:
            if blocked in params.command:
                return ToolConfirmation(
                    tool_name=self.name,
                    params=invocation.params,
                    description=f"Execute (BLOCKED): {params.command}",
                    command=params.command,
                    is_dangerous=True,
                )

        return ToolConfirmation(
            tool_name=self.name,
            params=invocation.params,
            description=f"Execute: {params.command}",
            command=params.command,
            is_dangerous=False,
        )

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        params = ShellToolParams(**invocation.params)

        command = params.command.strip().lower()
        for blocked in BLOCKED_COMMANDS:
            if blocked in command:
                return ToolResult.error_result(
                    f"Command blocked for safety reasons: {params.command}"
                )

        if params.cwd:
            cwd = Path(params.cwd)
            if not cwd.is_absolute():
                cwd = invocation.cwd / params.cwd
        else:
            cwd = invocation.cwd

        if not cwd.exists():
            return ToolResult.error(f"Current working directory does not exist: {cwd}")

        env = self._build_env()

        if sys.platform == "win32":
            shell_cmd = ["cmd.exe", "/c", params.command]
        else:
            shell_cmd = ["/bin/bash", "-c", params.command]

        process = await asyncio.create_subprocess_exec(
            *shell_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=env,
            start_new_session=True,
        )

        try:
            stdout_data, stderr_data = await asyncio.wait_for(
                process.communicate(), timeout=params.timeout
            )
        except asyncio.TimeoutError:
            if sys.platform == "win32":
                process.kill()
            else:
                os.killpg(os.getpid(process.id), signal.SIGKILL)

        stdout = stdout_data.decode(encoding="utf-8", errors="replace")
        stderr = stderr_data.decode(encoding="utf-8", errors="replace")
        exit_code = process.returncode

        output = ""
        if stdout.strip():
            output += stdout

        if stderr.strip():
            output += "\n--- stderr ---\n"
            output += stderr

        if exit_code != 0:
            output += f"\n Exit code: {exit_code}"

        if len(output) > 100 * 1024:
            output = output[: 100 * 1024] + "\n [output truncated]"

        return ToolResult(
            success=exit_code == 0,
            output=output,
            error=stderr if exit_code != 0 else None,
            exit_code=exit_code,
        )

    def _build_env(self) -> dict[str, str]:
        env = os.environ.copy()

        shell_policy = self.config.shell_environment

        if not shell_policy.ignore_default_excludes:
            for pattern in shell_policy.exclude_patterns:
                keys_to_remove = [
                    k for k in env.keys() if fnmatch.fnmatch(k.upper(), pattern.upper())
                ]

                for key in keys_to_remove:
                    del env[key]

        if shell_policy.set_vars:
            env.update(shell_policy.set_vars)

        return env
