from typing import Any
import os
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

class LLMClient:
    def __init__(self) -> None:
        self._client: AsyncOpenAI | None = None
        self._api_key = os.getenv("API_KEY")
        self._base_url = os.getenv("BASE_URL")

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self._api_key, 
                base_url=self._base_url
            )
            pass
        
        return self._client

    async def _close(self) -> None:
        if self._client:
            self._client.close()
            self._client = None
    
    async def _chat_completion(self, message: list[dict[str, Any]], stream: bool = False):
        if stream:
            self._stream_response()
        else:
            self._non_stream_response()
    
    async def _stream_response(self):
        pass

    async def _non_stream_response(self):
        pass 



