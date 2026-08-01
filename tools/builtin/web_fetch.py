from pathlib import Path
import trafilatura
from pydantic import BaseModel, Field
from tools.base import Tool, ToolInvocation, ToolKind, ToolResult
import httpx


class WebFetchToolParams(BaseModel):
    url: str = Field(..., description="URL to fetch (must be http:// or https://)")
    timeout: int = Field(
        30,
        ge=5,
        le=120,
        description="Request timeout in seconds (default: 120)",
    )


class WebFetchTool(Tool):
    name = "web_fetch"
    description = "Search the web for information. Returns search results with titles, URLs and snippets"
    kind = ToolKind.NETWORK
    schema = WebFetchToolParams

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        params = WebFetchToolParams(**invocation.params)

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(params.timeout), follow_redirects=True
            ) as client:
                response = await client.get(params.url)
                response.raise_for_status()
        except httpx.HTTPStatusError as e:
            return ToolResult.error_result(
                f"{e.response.status_code}:{e.response.reason_phrase}"
            )
        except Exception as e:
            return ToolResult.error_result(f"Request failed: {e}")

        text = trafilatura.extract(
            response.text,
            include_links=True,
            include_tables=True,
        )

        if len(text) > 100 * 1024:
            text = text[: 100 * 1024] + "\n [Output truncated]"

        return ToolResult.success_result(
            text,
            metadata={
                "status_code": response.status_code,
                "content_length": len(response.content),
            },
        )
