from rich.console import Console, Theme

AGENT_THEME = Theme(
    {
        # General
        "info": "cyan",
        "warning": "yellow",
        "error": "bright_red bold",
        "success": "green",
        "dim": "dim",
        "muted": "grey50",
        "border": "grey35",
        "highlight": "bold cyan",
        # Roles
        "user": "bright_blue bold",
        "assistant": "bright_white",
        # Tools
        "tool": "bright_magenta bold",
        "tool.read": "cyan",
        "tool.write": "yellow",
        "tool.shell": "magenta",
        "tool.network": "bright_blue",
        "tool.memory": "green",
        "tool.mcp": "bright_cyan",
        # Code / blocks
        "code": "white",
    }
)

_console: Console | None = None

def get_console():
    global _console
    if _console is None:
        _console = Console(theme=AGENT_THEME, highlight=False)

class UI:
    def __init__(self, console: Console | None = None):
        self.console = console or get_console()

    def stream_assistant_delta(self, content: str) -> None:
        self.console.print(content, end="")