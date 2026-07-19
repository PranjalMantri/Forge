from client.llm_client import LLMClient
import asyncio

async def main():
    client = LLMClient()

    messages = [{"role": "user", "content": "Hi how are you"}]
    async for event in client.chat_completion(messages, False):
        print(event)

asyncio.run(main())