import json
from typing import Any
import uuid
from datetime import datetime
from client.llm_client import LLMClient
from config.config import Config
from config.loader import get_config_dir
from context.context_manager import ContextManager
from tools.mcp.mcp_manager import MCPManager
from tools.registry import create_default_registry
from tools.discovery import ToolDiscoveryManager
from context.compactor import ChatCompactor
from safety.approval import ApprovalManager


class Session:
    def __init__(self, config: Config):
        self.client = LLMClient(config)
        self.config = config
        self.tool_registry = create_default_registry(self.config)

        self.discovery_manager = ToolDiscoveryManager(self.config, self.tool_registry)
        self.mcp_manager = MCPManager(self.config)
        self.chat_compactor = ChatCompactor(self.client)
        self.approval_manager = ApprovalManager(self.config.approval, self.config.cwd)
        self.config = config
        self.session_id = str(uuid.uuid4())
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

        self._turn_count: int = 0

    async def initialize(self) -> None:
        await self.mcp_manager.initialize()
        self.mcp_manager.register_tools(self.tool_registry)

        self.discovery_manager.discover_all()

        self.context_manager = ContextManager(
            self.config,
            user_memory=self._load_memory(),
            tools=self.tool_registry.get_tools(),
        )

    def _load_memory(self) -> str | None:
        config_dir = get_config_dir()
        config_dir.mkdir(parents=True, exist_ok=True)
        path = config_dir / "user_memory.json"

        if not path.exists():
            return None

        try:
            content = path.read_text(encoding="utf-8")
            data = json.loads(content)
            entries = data.get("entries")

            if not entries:
                return None

            lines = ["User preferences and notes: "]
            for key, value in entries.items():
                lines.append(f"- {key}: {value}")

            return "\n".join(lines)
        except:
            return None

    def increment_turn(self) -> int:
        self._turn_count += 1
        self.updated_at = datetime.now()

        return self._turn_count
