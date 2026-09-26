"""Dump the full raw MCP result for one call, to see the real error detail."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import httpx2  # noqa: E402
from mcp import ClientSession  # noqa: E402
from mcp.client.streamable_http import streamable_http_client  # noqa: E402

from student_agent.config import Settings  # noqa: E402


async def main() -> None:
    settings = Settings.load(ROOT)
    headers = {"Authorization": f"Bearer {settings.team_api_key}"}
    timeout = httpx2.Timeout(120.0, connect=45.0)
    async with httpx2.AsyncClient(headers=headers, timeout=timeout) as http_client:
        async with streamable_http_client(settings.mcp_endpoint, http_client=http_client) as (
            read_stream,
            write_stream,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                res = await session.call_tool(
                    "get_order",
                    arguments={"case_id": "L3B_CASE_001", "order_id": "af0bbb47f125381ce9f3597dc70ef07b"},
                )
                print("isError:", getattr(res, "is_error", None))
                print("structuredContent:", getattr(res, "structured_content", None))
                print("meta:", getattr(res, "meta", None))
                for b in res.content:
                    print("block type:", type(b).__name__, "|", repr(getattr(b, "text", None))[:400])


asyncio.run(main())
