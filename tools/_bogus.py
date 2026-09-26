"""Is the gateway outage global, or specific to our key (quota lockout)?

Opens a session and calls one tool with a bogus key and with no key. The
handshake succeeds without auth, so if a bogus key gets real data back the
failure is ours; if it also errors, the outage is server-wide.
"""
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


async def probe(label: str, key: str | None) -> None:
    settings = Settings.load(ROOT)
    headers = {} if key is None else {"Authorization": f"Bearer {key}"}
    timeout = httpx2.Timeout(60.0, connect=30.0)
    try:
        async with httpx2.AsyncClient(headers=headers, timeout=timeout) as http_client:
            async with streamable_http_client(settings.mcp_endpoint, http_client=http_client) as (
                read_stream,
                write_stream,
            ):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    res = await session.call_tool(
                        "get_order",
                        arguments={
                            "case_id": "L3B_CASE_001",
                            "order_id": "af0bbb47f125381ce9f3597dc70ef07b",
                        },
                    )
                    err = getattr(res, "is_error", None)
                    text = " | ".join(b.text for b in res.content if getattr(b, "text", None))
                    print(f"{label}: is_error={err} text={text[:160]!r}")
    except BaseException as exc:  # noqa: BLE001
        print(f"{label}: EXC {type(exc).__name__}: {str(exc)[:160]}")


async def main() -> None:
    settings = Settings.load(ROOT)
    await probe("OURS", settings.team_api_key)
    await probe("BOGUS", "sk-team-000000000000")
    await probe("NONE", None)


asyncio.run(main())
