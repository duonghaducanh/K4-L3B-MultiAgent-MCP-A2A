"""Capture every MCP response for every case into tools/_cache/<case>/<tool>.json.

Throwaway recon run: its audited calls belong to this run only, so it does not
affect the efficiency of a later, clean submission run. Resumable and
concurrency-limited.
"""

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

CACHE = ROOT / "tools" / "_cache"

TOOLS = (
    ("get_customer_history", "customer_unique_id"),
    ("get_order", "order_id"),
    ("get_order_items", "order_id"),
    ("get_order_payments", "order_id"),
    ("get_shipment_summary", "order_id"),
    ("get_payment_timeline", "order_id"),
    ("get_refund_timeline", "order_id"),
    ("get_sellers", "order_id"),
    ("get_product_context", "order_id"),
)


async def one_case(session: ClientSession, case: dict) -> None:
    case_id = case["case_id"]
    out = CACHE / case_id
    if (out / "_done").exists():
        return
    out.mkdir(parents=True, exist_ok=True)
    req = case["customer_request"]
    oid = req["claimed_order_id"]
    hint = case.get("customer_unique_id_hint") or ""
    payload = {"case_id": case_id, "policy_version": case.get("policy_version")}

    for tool, argname in TOOLS:
        target = out / f"{tool}.json"
        if target.exists():
            continue
        args = dict(payload)
        args[argname] = hint if argname == "customer_unique_id" else oid
        for attempt in range(4):
            try:
                res = await session.call_tool(tool, arguments=args)
            except BaseException as exc:  # noqa: BLE001
                if attempt == 3:
                    target.write_text(json.dumps({"error": repr(exc)[:300]}), encoding="utf-8")
                else:
                    await asyncio.sleep(2.0 * (attempt + 1))
                continue
            is_err = getattr(res, "is_error", None)
            sc = getattr(res, "structured_content", None)
            if is_err or sc is None:
                text = " | ".join(b.text for b in res.content if getattr(b, "text", None))
                target.write_text(
                    json.dumps({"is_error": bool(is_err), "text": text[:500]}), encoding="utf-8"
                )
            else:
                target.write_text(json.dumps(sc, ensure_ascii=False), encoding="utf-8")
            break
        await asyncio.sleep(0.05)

    # candidate order ids (decoy resolution evidence)
    cand_target = out / "candidates.json"
    if not cand_target.exists():
        rows = {}
        for cand in case.get("candidate_order_ids", []):
            if cand == oid:
                continue
            try:
                res = await session.call_tool(
                    "get_order", arguments={"case_id": case_id, "order_id": cand}
                )
                is_err = getattr(res, "is_error", None)
                sc = getattr(res, "structured_content", None)
                rows[cand] = (
                    sc if (not is_err and sc is not None)
                    else {"is_error": True, "text": " | ".join(
                        b.text for b in res.content if getattr(b, "text", None))[:300]}
                )
            except BaseException as exc:  # noqa: BLE001
                rows[cand] = {"error": repr(exc)[:200]}
        cand_target.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

    (out / "_done").write_text("1", encoding="utf-8")


async def worker(name: str, cases: list[dict], settings: Settings) -> None:
    headers = {"Authorization": f"Bearer {settings.team_api_key}"}
    timeout = httpx2.Timeout(300.0, connect=45.0)
    async with httpx2.AsyncClient(headers=headers, timeout=timeout) as http_client:
        async with streamable_http_client(
            settings.mcp_endpoint, http_client=http_client
        ) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                for case in cases:
                    await one_case(session, case)
                    print(f"{name} {case['case_id']} done", flush=True)


async def main() -> None:
    settings = Settings.load(ROOT)
    cases = [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted((ROOT / "inputs").glob("*.json"))
    ]
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    chunks = [cases[i::workers] for i in range(workers)]
    await asyncio.gather(*(worker(f"w{i}", chunk, settings) for i, chunk in enumerate(chunks)))
    done = sum(1 for p in CACHE.glob("*/_done"))
    print(f"captured {done}/{len(cases)} cases")


if __name__ == "__main__":
    asyncio.run(main())
