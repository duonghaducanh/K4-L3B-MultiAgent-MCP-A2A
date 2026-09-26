"""List MCP resources/prompts — the gateway may publish its required evidence set."""
from __future__ import annotations

import asyncio
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
                init = await session.initialize()
                print("server:", init.server_info)
                print("instructions:", repr(getattr(init, "instructions", None))[:3000])
                try:
                    res = await session.list_resources()
                    print("\nRESOURCES:", res)
                except BaseException as exc:  # noqa: BLE001
                    print("\nresources error:", repr(exc)[:200])
                try:
                    tmpl = await session.list_resource_templates()
                    print("\nRESOURCE TEMPLATES:", tmpl)
                except BaseException as exc:  # noqa: BLE001
                    print("\ntemplates error:", repr(exc)[:200])
                try:
                    pr = await session.list_prompts()
                    print("\nPROMPTS:", pr)
                except BaseException as exc:  # noqa: BLE001
                    print("\nprompts error:", repr(exc)[:200])


asyncio.run(main())
