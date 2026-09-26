"""Why does get_refund_timeline error for some cases? Print the raw MCP error."""
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
from student_agent.contracts import Contracts  # noqa: E402


async def main(numbers: list[str]) -> None:
    settings = Settings.load(ROOT)
    contracts = Contracts(ROOT / "contracts" / "schemas")
    headers = {"Authorization": f"Bearer {settings.team_api_key}"}
    timeout = httpx2.Timeout(120.0, connect=45.0)
    async with httpx2.AsyncClient(headers=headers, timeout=timeout) as http_client:
        async with streamable_http_client(settings.mcp_endpoint, http_client=http_client) as (
            read_stream,
            write_stream,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                for num in numbers:
                    case_id = f"L3B_CASE_{num}"
                    case = json.loads((ROOT / "inputs" / f"{case_id}.json").read_text(encoding="utf-8"))
                    oid = case["customer_request"]["claimed_order_id"]
                    res = await session.call_tool(
                        "get_refund_timeline", arguments={"case_id": case_id, "order_id": oid}
                    )
                    err = getattr(res, "is_error", None)
                    text = " | ".join(
                        b.text for b in res.content if getattr(b, "text", None)
                    )
                    sc = getattr(res, "structured_content", None)
                    print(f"{case_id} is_error={err} structured={'yes' if sc else 'no'}")
                    print(f"   text: {text[:400]}")
                    if sc:
                        print("   sc:", json.dumps(sc, ensure_ascii=False)[:400])
                    sys.stdout.flush()


asyncio.run(main(sys.argv[1:] or ["001", "004", "007", "008", "010"]))
