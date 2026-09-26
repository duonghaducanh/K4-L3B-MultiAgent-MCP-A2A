"""Dump the full policy evidence document (one audited MCP call)."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from student_agent.config import Settings  # noqa: E402
from student_agent.contracts import Contracts  # noqa: E402
from student_agent.mcp_gateway import connect_gateway  # noqa: E402


async def main() -> None:
    settings = Settings.load(ROOT)
    contracts = Contracts(ROOT / "contracts" / "schemas")
    async with connect_gateway(settings.mcp_endpoint, settings.team_api_key, contracts) as gw:
        ev = await gw.call("get_policy", case_id="L3B_CASE_001", policy_version="EC_POLICY_V2")
    (ROOT / "tools" / "_policy.json").write_text(
        json.dumps(ev, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(json.dumps(ev, ensure_ascii=False, indent=1)[:6000])


asyncio.run(main())
