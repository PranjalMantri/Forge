import uuid
from datetime import datetime
from client.llm_client import LLMClient
from config.config import Config
from context.context_manager import ContextManager
from tools.registry import create_default_registry


class Session:
    def __init__(self, config: Config):
        self.client = LLMClient(config)
        self.context_manager = ContextManager(config)
        self.tool_registry = create_default_registry(config)
        self.config = config
        self.session_id = str(uuid.uuid4())
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

        self._turn_count: int = 0

    def increment_turn(self) -> int:
        self._turn_count += 1
        self.updated_at = datetime.now()

        return self._turn_count
