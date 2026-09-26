"""Replay the real workflow against cached payloads — zero audited MCP calls.

Serves whatever raw payloads we have captured (tools/_case001.json,
tools/_learn1.json) through a fake gateway whose failure semantics match the
live one (an errored payload raises RuntimeError, exactly as EvidenceGateway
does when is_error is set).  Used to test output changes offline before
spending a submission.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from student_agent.contracts import Contracts  # noqa: E402
from student_agent.trace import TraceWriter  # noqa: E402
from student_agent.workflow import solve_case  # noqa: E402

CONTRACTS = Contracts(ROOT / "contracts" / "schemas")


def load_cache() -> dict[str, dict[str, Any]]:
    cache: dict[str, dict[str, Any]] = {}
    c1 = json.loads((ROOT / "tools" / "_case001.json").read_text(encoding="utf-8"))
    cache["L3B_CASE_001"] = c1
    learn = json.loads((ROOT / "tools" / "_learn1.json").read_text(encoding="utf-8"))
    for case_id, payloads in learn.items():
        cache[case_id] = payloads
    return cache


def _is_error(payload: Any) -> bool:
    return isinstance(payload, dict) and (
        payload.get("isError") is True or payload.get("is_error") is True
    )


class FakeGateway:
    def __init__(self, case_id: str, payloads: dict[str, Any]) -> None:
        self.case_id = case_id
        self.payloads = payloads
        self.calls: list[str] = []

    async def list_tools(self) -> list[str]:
        return sorted(self.payloads)

    async def call(self, tool_name: str, *, case_id: str, **arguments: str) -> dict[str, Any]:
        assert case_id == self.case_id, f"cross-case call: {case_id} != {self.case_id}"
        payload = self.payloads.get(tool_name)
        self.calls.append(tool_name)
        if payload is None or _is_error(payload):
            raise RuntimeError(f"MCP tool {tool_name} failed")
        CONTRACTS.validate_evidence(payload, f"MCP tool {tool_name}")
        return payload


async def replay(case: dict[str, Any], payloads: dict[str, Any], trace: TraceWriter) -> dict:
    gateway = FakeGateway(case["case_id"], payloads)
    return await solve_case(case, gateway, trace)


async def main() -> None:
    cache = load_cache()
    case_dir = ROOT / "inputs"
    out_dir = ROOT / "tools" / "_replay_out"
    out_dir.mkdir(exist_ok=True)
    trace_path = ROOT / "tools" / "_replay_trace.jsonl"
    trace_path.unlink(missing_ok=True)
    trace = TraceWriter(trace_path, CONTRACTS)

    for case_id in sorted(cache):
        path = case_dir / f"{case_id}.json"
        if not path.exists():
            continue
        case = json.loads(path.read_text(encoding="utf-8"))
        try:
            output = await replay(case, cache[case_id], trace)
        except Exception as exc:  # noqa: BLE001
            print(f"{case_id}: FAILED {exc!r}")
            continue
        try:
            CONTRACTS.validate_output(output, f"outputs/{case_id}.json")
            ok = "schema-ok"
        except Exception as exc:  # noqa: BLE001
            ok = f"SCHEMA-FAIL {exc}"
        (out_dir / f"{case_id}.json").write_text(
            json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"{case_id}: {ok} calls={len(cache[case_id])}")

    # compare against the submitted outputs where both exist
    print("\n=== diff vs submitted outputs ===")
    for case_id in sorted(cache):
        a = out_dir / f"{case_id}.json"
        b = ROOT / "outputs" / f"{case_id}.json"
        if not (a.exists() and b.exists()):
            continue
        ra = json.loads(a.read_text(encoding="utf-8"))
        rb = json.loads(b.read_text(encoding="utf-8"))
        diff = {
            k: (ra.get(k), rb.get(k))
            for k in set(ra) | set(rb)
            if ra.get(k) != rb.get(k)
        }
        print(f"{case_id}: {'IDENTICAL' if not diff else 'differs: ' + str(list(diff))}")


if __name__ == "__main__":
    asyncio.run(main())
