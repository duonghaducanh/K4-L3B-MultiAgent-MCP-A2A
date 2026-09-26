"""Probe: does get_refund_timeline error for non-refund cases? What does it return?

Also compare get_order_payments vs get_payment_timeline, and dump product context.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mcp import ClientSession  # noqa: E402
from mcp.client.streamable_http import streamable_http_client  # noqa: E402
import httpx2  # noqa: E402

from student_agent.config import Settings  # noqa: E402

NUMBERS = ["001", "002", "003", "005", "007", "008", "010"]


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
                for num in NUMBERS:
                    case_id = f"L3B_CASE_{num}"
                    case = json.loads(
                        (ROOT / "inputs" / f"{case_id}.json").read_text(encoding="utf-8")
                    )
                    oid = case["customer_request"]["claimed_order_id"]
                    hint = case["customer_unique_id_hint"]
                    topics = [c["topic"] for c in case["customer_request"]["claims"]]
                    print("=" * 78)
                    print(f"{case_id} topics={topics}")

                    for tool, args in (
                        ("get_refund_timeline", {"order_id": oid}),
                        ("get_order_payments", {"order_id": oid}),
                        ("get_product_context", {"order_id": oid}),
                        ("get_sellers", {"order_id": oid}),
                    ):
                        res = await session.call_tool(
                            tool, arguments={"case_id": case_id, **args}
                        )
                        is_err = getattr(res, "is_error", None)
                        sc = getattr(res, "structured_content", None)
                        text = " | ".join(
                            b.text for b in res.content if getattr(b, "text", None)
                        )
                        print(f"  {tool}: is_error={is_err}")
                        if sc:
                            print(f"     data={json.dumps(sc.get('data'), ensure_ascii=False)[:400]}")
                        elif text:
                            print(f"     text={text[:300]}")
                    sys.stdout.flush()


asyncio.run(main())
