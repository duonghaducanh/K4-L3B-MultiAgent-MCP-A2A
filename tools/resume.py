"""Re-solve specific cases and splice them into outputs/ and traces/trace.jsonl.

Usage: .venv/Scripts/python.exe tools/resume.py 047 048

Existing trace events for those cases are dropped first, then each case is
replayed through the same retry/rollback path the CLI uses, so the resulting
trace stays free of duplicates and partial attempts.
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


async def main(numbers: list[str]) -> None:
    settings = Settings.load(ROOT)
    case_set = load_case_set(ROOT)
    contracts = Contracts(ROOT / "contracts" / "schemas")
    output_root = ROOT / "outputs"
    trace = TraceWriter(ROOT / "traces" / "trace.jsonl", contracts)

    for num in numbers:
        case_id = f"L3B_CASE_{num}"
        trace.drop_case(case_id)
        await _solve_case(case_set.cases[case_id], settings, contracts, trace, output_root)
        print(f"{case_id}: replayed", flush=True)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
