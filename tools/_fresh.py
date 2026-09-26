"""Solve cases fresh into an isolated dir, then build a minimal ZIP for probing.

Usage: .venv/Scripts/python.exe tools/_fresh.py 001 002 003
Writes tools/_fresh/<case>.json, tools/_fresh/trace.jsonl and tools/_fresh/probe.zip
"""

from __future__ import annotations

import asyncio
import json
import sys
import zipfile
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
    out_dir = ROOT / "tools" / "_fresh"
    out_dir.mkdir(parents=True, exist_ok=True)
    trace_path = out_dir / "trace.jsonl"
    trace_path.unlink(missing_ok=True)
    trace = TraceWriter(trace_path, contracts)

    async with connect_gateway(settings.mcp_endpoint, settings.team_api_key, contracts) as gw:
        for num in numbers:
            case_id = f"L3B_CASE_{num}"
            case = case_set.cases[case_id]
            trace.emit(case_id=case_id, event_type="case_received", actor="coordinator")
            output = await solve_case(case, gw, trace)
            contracts.validate_output(output, f"outputs/{case_id}.json")
            trace.emit(case_id=case_id, event_type="case_finalized", actor="coordinator")
            (out_dir / f"{case_id}.json").write_text(
                json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(
                f"{case_id}: {output['assessment']['primary_issue']:24s} "
                f"refs={len(output['evidence_refs'])}",
                flush=True,
            )

    manifest = {
        "schema_version": "day09-submission-manifest-v2",
        "competition_id": "day09-multiagent-mcp-a2a",
        "variant_id": "l3b",
        "case_set_version": case_set.version,
        "output_schema_version": "day09-l3b-output-v2",
        "trace_schema_version": "day09-trace-event-v1",
        "generated_at": "2026-09-25T00:00:00Z",
        "client": {"name": "probe", "version": "0"},
    }
    lines = trace_path.read_text(encoding="utf-8").splitlines()
    zip_path = out_dir / "probe.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest, separators=(",", ":")))
        z.writestr("trace.jsonl", "\n".join(lines) + "\n")
        for num in numbers:
            case_id = f"L3B_CASE_{num}"
            z.writestr(
                f"outputs/{case_id}.json",
                json.dumps(
                    json.loads((out_dir / f"{case_id}.json").read_text(encoding="utf-8")),
                    separators=(",", ":"),
                ),
            )
    print(f"wrote {zip_path} with {len(numbers)} outputs / {len(lines)} trace events")


asyncio.run(main(sys.argv[1:]))
