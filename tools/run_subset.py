"""Run solve_case for a subset of cases without touching outputs/ or traces/.

Usage: .venv/Scripts/python.exe tools/run_subset.py 001 002 003
Writes tools/_subset/<case>.json plus a combined trace.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from student_agent.cases import load_case_set  # noqa: E402
from student_agent.config import Settings  # noqa: E402
from student_agent.contracts import Contracts  # noqa: E402
from student_agent.mcp_gateway import connect_gateway  # noqa: E402
from student_agent.trace import TraceWriter  # noqa: E402
from student_agent.workflow import solve_case  # noqa: E402


async def main(numbers: list[str]) -> None:
    settings = Settings.load(ROOT)
    case_set = load_case_set(ROOT)
    contracts = Contracts(ROOT / "contracts" / "schemas")
    out_dir = ROOT / "tools" / "_subset"
    out_dir.mkdir(parents=True, exist_ok=True)
    trace_path = out_dir / "trace.jsonl"
    trace_path.unlink(missing_ok=True)
    trace = TraceWriter(trace_path, contracts)

    async with connect_gateway(settings.mcp_endpoint, settings.team_api_key, contracts) as gateway:
        for num in numbers:
            case_id = f"L3B_CASE_{num}"
            case = case_set.cases[case_id]
            trace.emit(case_id=case_id, event_type="case_received", actor="coordinator")
            output = await solve_case(case, gateway, trace)
            contracts.validate_output(output, f"outputs/{case_id}.json")
            trace.emit(case_id=case_id, event_type="case_finalized", actor="coordinator")
            (out_dir / f"{case_id}.json").write_text(
                json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"{case_id}: {output['assessment']['primary_issue']:24s} "
                  f"{output['assessment']['case_status']:20s} refund={output['financial_resolution']['recommended_refund_brl']}",
                  flush=True)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
