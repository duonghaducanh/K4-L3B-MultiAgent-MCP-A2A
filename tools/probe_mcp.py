"""Ad-hoc MCP probe (not part of the submission).

Usage:
  .venv/Scripts/python.exe tools/probe_mcp.py schemas
  .venv/Scripts/python.exe tools/probe_mcp.py call <tool> '<json args>'
  .venv/Scripts/python.exe tools/probe_mcp.py sweep <case_id>
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx2
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
URL = os.environ["MCP_ENDPOINT"]
KEY = os.environ["COMPETITION_TEAM_API_KEY"]


def _schema(tool: Any) -> Any:
    for attr in ("input_schema", "inputSchema"):
        value = getattr(tool, attr, None)
        if value is not None:
            return value.model_dump() if hasattr(value, "model_dump") else value
    return None


async def with_session(work, attempts: int = 10):
    last: BaseException | None = None
    for i in range(attempts):
        try:
            async with httpx2.AsyncClient(
                headers={"Authorization": f"Bearer {KEY}"},
                timeout=httpx2.Timeout(180.0, connect=45.0, read=180.0, write=45.0),
            ) as hc:
                async with streamable_http_client(URL, http_client=hc) as (r, w):
                    async with ClientSession(r, w) as s:
                        await s.initialize()
                        return await work(s)
        except BaseException as e:  # noqa: BLE001 - probe tool
            last = e
            print(f"  attempt {i}: {type(e).__name__}", file=sys.stderr, flush=True)
            await asyncio.sleep(min(1.5 * (i + 1), 6.0))
    raise RuntimeError(f"probe gave up: {last!r}")


async def _call(s: ClientSession, tool: str, args: dict[str, Any]) -> Any:
    res = await s.call_tool(tool, arguments=args)
    if getattr(res, "is_error", getattr(res, "isError", False)):
        return {"isError": True, "text": [b.text for b in res.content if getattr(b, "text", None)]}
    structured = getattr(res, "structuredContent", None) or getattr(res, "structured_content", None)
    if structured is not None:
        return structured
    return json.loads([b.text for b in res.content if getattr(b, "text", None)][0])


async def dump_schemas() -> None:
    async def work(s: ClientSession) -> Any:
        t = await s.list_tools()
        return [{"name": tool.name, "desc": tool.description or "", "schema": _schema(tool)} for tool in t.tools]

    print(json.dumps(await with_session(work), ensure_ascii=False, indent=1))


async def call_tool(tool: str, args: dict[str, Any]) -> None:
    print(json.dumps(await with_session(lambda s: _call(s, tool, args)), ensure_ascii=False, indent=1))


async def sweep(case_id: str) -> None:
    case = json.loads((ROOT / "inputs" / f"{case_id}.json").read_text(encoding="utf-8"))
    claimed = case["customer_request"]["claimed_order_id"]
    hint = case.get("customer_unique_id_hint")
    plan: list[tuple[str, dict[str, Any]]] = [
        ("get_order", {"case_id": case_id, "order_id": claimed}),
        ("get_order_items", {"case_id": case_id, "order_id": claimed}),
        ("get_order_payments", {"case_id": case_id, "order_id": claimed}),
        ("get_shipment_summary", {"case_id": case_id, "order_id": claimed}),
        ("get_sellers", {"case_id": case_id, "order_id": claimed}),
        ("get_payment_timeline", {"case_id": case_id, "order_id": claimed}),
        ("get_refund_timeline", {"case_id": case_id, "order_id": claimed}),
        ("get_customer_history", {"case_id": case_id, "customer_unique_id": hint}),
        ("get_product_context", {"case_id": case_id, "order_id": claimed}),
        ("get_policy", {"case_id": case_id, "policy_version": case.get("policy_version", "EC_POLICY_V2")}),
    ]

    async def work(s: ClientSession) -> Any:
        out: dict[str, Any] = {}
        for tool, args in plan:
            try:
                out[tool] = await _call(s, tool, args)
            except BaseException as e:  # noqa: BLE001
                out[tool] = {"call_error": f"{type(e).__name__}: {e}"[:300]}
        return out

    print(json.dumps(await with_session(work), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "schemas"
    if cmd == "schemas":
        asyncio.run(dump_schemas())
    elif cmd == "call":
        asyncio.run(call_tool(sys.argv[2], json.loads(sys.argv[3])))
    elif cmd == "sweep":
        asyncio.run(sweep(sys.argv[2]))
