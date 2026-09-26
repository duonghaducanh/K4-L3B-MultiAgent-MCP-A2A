"""Decisive: does tools/call fail for a bogus key too (outage) or only ours (quota)?"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import httpx2  # noqa: E402

from student_agent.config import Settings  # noqa: E402


def call(label: str, key: str | None) -> None:
    settings = Settings.load(ROOT)
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    if key is not None:
        headers["Authorization"] = f"Bearer {key}"
    body = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "get_order",
            "arguments": {
                "case_id": "L3B_CASE_001",
                "order_id": "af0bbb47f125381ce9f3597dc70ef07b",
            },
        },
    }
    try:
        with httpx2.Client(timeout=45.0) as c:
            r = c.post(settings.mcp_endpoint, headers=headers, json=body)
            txt = r.text.replace("\r", " ").replace("\n", " ")
            print(f"{label}: status={r.status_code} {txt[:300]}")
    except Exception as exc:  # noqa: BLE001
        print(f"{label}: EXC {type(exc).__name__}: {str(exc)[:160]}")


def main() -> None:
    settings = Settings.load(ROOT)
    call("OURS", settings.team_api_key)
    call("BOGUS", "sk-team-000000000000")
    call("NONE", None)


main()
