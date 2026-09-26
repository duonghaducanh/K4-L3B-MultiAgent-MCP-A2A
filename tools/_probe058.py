"""Diagnose case 058: is the gateway erroring for that case, or is it down?

Probes case 058 and case 001 (control) for the two tools that failed.
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
                tools = await session.list_tools()
                print("tools:", sorted(t.name for t in tools.tools))
                for case_id, oid, hint in (
                    ("L3B_CASE_058", None, None),
                    ("L3B_CASE_001", "af0bbb47f125381ce9f3597dc70ef07b", "customer-597dc70ef07b"),
                ):
                    import json

                    case = json.loads(
                        (ROOT / "inputs" / f"{case_id}.json").read_text(encoding="utf-8")
                    )
                    oid = case["customer_request"]["claimed_order_id"]
                    hint = case["customer_unique_id_hint"]
                    for tool, args in (
                        ("get_customer_history", {"customer_unique_id": hint}),
                        ("get_policy", {"policy_version": case["policy_version"]}),
                        ("get_order", {"order_id": oid}),
                    ):
                        res = await session.call_tool(tool, arguments={"case_id": case_id, **args})
                        err = getattr(res, "is_error", None)
                        text = " | ".join(
                            b.text for b in res.content if getattr(b, "text", None)
                        )
                        print(f"  {case_id} {tool}: is_error={err} text={text[:120]!r}")


asyncio.run(main())
