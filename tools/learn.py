"""Ad-hoc learning probe across several cases in one MCP session (not part of submission).

Usage: .venv/Scripts/python.exe tools/learn.py 001 002 003 ...
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_mcp import ROOT, _call, with_session  # noqa: E402


async def learn(case_numbers: list[str]) -> None:
    cases: list[dict[str, Any]] = []
    for num in case_numbers:
        case_id = f"L3B_CASE_{num}"
        case = json.loads((ROOT / "inputs" / f"{case_id}.json").read_text(encoding="utf-8"))
        cases.append(case)

    async def work(s) -> Any:
        out: dict[str, Any] = {}
        for case in cases:
            case_id = case["case_id"]
            claimed = case["customer_request"]["claimed_order_id"]
            hint = case.get("customer_unique_id_hint")
            candidates = [c for c in case["candidate_order_ids"] if c != claimed]
            entry: dict[str, Any] = {"claimed": claimed, "candidates": candidates}
            for tool, args in [
                ("get_order", {"case_id": case_id, "order_id": claimed}),
                ("get_order_items", {"case_id": case_id, "order_id": claimed}),
                ("get_order_payments", {"case_id": case_id, "order_id": claimed}),
                ("get_shipment_summary", {"case_id": case_id, "order_id": claimed}),
                ("get_payment_timeline", {"case_id": case_id, "order_id": claimed}),
                ("get_refund_timeline", {"case_id": case_id, "order_id": claimed}),
                ("get_customer_history", {"case_id": case_id, "customer_unique_id": hint}),
            ]:
                try:
                    entry[tool] = await _call(s, tool, args)
                except BaseException as e:  # noqa: BLE001
                    entry[tool] = {"call_error": f"{type(e).__name__}: {e}"[:200]}
            # probe a rejected candidate too
            if candidates:
                try:
                    entry["candidate_get_order"] = await _call(
                        s, "get_order", {"case_id": case_id, "order_id": candidates[0]}
                    )
                except BaseException as e:  # noqa: BLE001
                    entry["candidate_get_order"] = {"call_error": f"{type(e).__name__}: {e}"[:200]}
            out[case_id] = entry
        return out

    result = await with_session(work)
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    asyncio.run(learn(sys.argv[1:]))
