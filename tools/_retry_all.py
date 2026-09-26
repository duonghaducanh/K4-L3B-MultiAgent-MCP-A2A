"""Retry every tool several times to see if the gateway failure is transient."""
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

ARGS = {
    "get_customer_history": {"customer_unique_id": "customer-597dc70ef07b"},
    "get_order": {"order_id": "af0bbb47f125381ce9f3597dc70ef07b"},
    "get_order_items": {"order_id": "af0bbb47f125381ce9f3597dc70ef07b"},
    "get_order_payments": {"order_id": "af0bbb47f125381ce9f3597dc70ef07b"},
    "get_shipment_summary": {"order_id": "af0bbb47f125381ce9f3597dc70ef07b"},
    "get_payment_timeline": {"order_id": "af0bbb47f125381ce9f3597dc70ef07b"},
    "get_refund_timeline": {"order_id": "af0bbb47f125381ce9f3597dc70ef07b"},
    "get_sellers": {"order_id": "af0bbb47f125381ce9f3597dc70ef07b"},
    "get_product_context": {"order_id": "af0bbb47f125381ce9f3597dc70ef07b"},
    "get_policy": {"policy_version": "EC_POLICY_V2"},
}


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
                for tool, args in ARGS.items():
                    outcomes = []
                    for _ in range(2):
                        try:
                            res = await session.call_tool(
                                tool, arguments={"case_id": "L3B_CASE_001", **args}
                            )
                            outcomes.append("ERR" if getattr(res, "is_error", None) else "ok")
                        except BaseException as exc:  # noqa: BLE001
                            outcomes.append(f"EXC:{type(exc).__name__}")
                        await asyncio.sleep(0.5)
                    print(f"{tool:24s} {outcomes}")


asyncio.run(main())
