"""Raw HTTP against the MCP endpoint: see headers and body for quota/rate-limit."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import httpx2  # noqa: E402

from student_agent.config import Settings  # noqa: E402


def main() -> None:
    settings = Settings.load(ROOT)
    url = settings.mcp_endpoint
    headers = {
        "Authorization": f"Bearer {settings.team_api_key}",
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "get_order",
            "arguments": {
                "case_id": "L3B_CASE_001",
                "order_id": "af0bbb47f125381ce9f3597dc70ef07b",
            },
        },
    }
    with httpx2.Client(timeout=60.0) as c:
        r = c.post(url, headers=headers, json=body)
        print("status:", r.status_code)
        for k, v in r.headers.items():
            if any(t in k.lower() for t in ("rate", "limit", "quota", "retry", "remain")):
                print(f"  header {k}: {v}")
        print("body:", r.text[:1500])


main()
