from rich.console import Console
from rich.theme import Theme
from rich.rule import Rule
from rich.text import Text
from rich.markdown import Markdown
from rich.live import Live

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
        _console = Console(theme=AGENT_THEME)

    return _console

class UI:
    def __init__(self, console: Console | None = None):
        self.console = console or get_console()
        self._assistant_stream_response = False
        self._assistant_reasoning = False
        self._assistant_buffer = ""
        self._live: Live | None = None

    def begin_assistant(self) -> None:
        self.console.print()
        self.console.print()
        self.console.print(Rule(Text("Assistant", style="assistant")))

        self._assistant_stream_response = True
        self._assistant_buffer = ""

        self._live = Live(
            Markdown(""), 
            console=self.console, 
            refresh_per_second=20,
            transient=False,
            auto_refresh=False
        )

        self._live.start()

    def stream_assistant_delta(self, content: str) -> None:
        self._assistant_buffer += content

        if self._live:
            self._live.update(Markdown(self._assistant_buffer), refresh=True)

    def end_assistant(self) -> None:
        if self._live:
            self._live.update(Markdown(self._assistant_buffer), refresh=True)
            self._live.stop()
            self._live = None 

        self._assistant_stream_response = False
        self.console.print()

    def assistant_error(self, error_message: str) -> None:
        if self._live:
            self._live.stop()
            self._live = None

        self.console.print()
        self.console.print(Text(error_message, style="error"))

    def begin_reasoning(self) -> None:
        self.console.print()
        self.console.print(Rule(Text("Reasoning", style="dim")))
        self._assistant_reasoning = True

    def stream_assistant_reasoning(self, content: str) -> None:
        self.console.print(Text(content, style="dim"), end="")