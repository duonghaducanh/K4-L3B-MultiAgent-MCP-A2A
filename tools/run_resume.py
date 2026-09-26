"""Solve only the cases that do not yet have an output, then stop.

Safe to re-run: it never re-solves a case that already produced an output, so a
gateway outage mid-run does not waste the audited calls already spent. The
trace is left intact for the cases already solved.

Usage: .venv/Scripts/python.exe tools/run_resume.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from student_agent.cases import load_case_set  # noqa: E402
from student_agent.cli import _solve_case  # noqa: E402
from student_agent.config import Settings  # noqa: E402
from student_agent.contracts import Contracts  # noqa: E402
from student_agent.trace import TraceWriter  # noqa: E402


async def main() -> None:
    settings = Settings.load(ROOT)
    case_set = load_case_set(ROOT)
    contracts = Contracts(ROOT / "contracts" / "schemas")
    output_root = ROOT / "outputs"
    output_root.mkdir(parents=True, exist_ok=True)
    trace = TraceWriter(ROOT / "traces" / "trace.jsonl", contracts)

    pending = [
        cid
        for cid in case_set.case_ids
        if not (output_root / f"{cid}.json").exists()
    ]
    print(f"pending: {len(pending)} cases", flush=True)
    for case_id in pending:
        try:
            await _solve_case(case_set.cases[case_id], settings, contracts, trace, output_root)
        except Exception as exc:  # noqa: BLE001
            print(f"{case_id}: giving up ({exc!r})", flush=True)
            raise
        print(f"{case_id}: done", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
