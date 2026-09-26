"""Audit 2 - Tasks 2 & 3: workflow/trace structure + trace-event schema.

Usage: python tools/_aud2_workflow.py [outputs_dir] [trace_path]
"""
from __future__ import annotations

import collections
import glob
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

REQUIRED = [
    "case_received",
    "task_assigned",
    "handoff",
    "verification_completed",
    "case_finalized",
]


def main():
    outs_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("outputs")
    trace_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("traces/trace.jsonl")
    schema_path = Path("contracts/schemas/trace-event-v1.schema.json")

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    events = []
    for lineno, line in enumerate(trace_path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            events.append((lineno, json.loads(line)))
    print(f"# trace={trace_path}  events={len(events)}")

    # ---------------- Task 3: schema validation ----------------------------
    print("\n=== TASK 3: trace-event-v1 schema ===")
    failures = collections.Counter()
    fail_examples = collections.defaultdict(list)
    for lineno, e in events:
        errs = sorted(validator.iter_errors(e), key=lambda x: list(x.absolute_path))
        if errs:
            key = (errs[0].validator, errs[0].message.split("'")[0][:60])
            failures[key] += 1
            if len(fail_examples[key]) < 5:
                fail_examples[key].append((lineno, e.get("case_id"), e.get("event_type"),
                                           errs[0].json_path, errs[0].message[:160]))
    if not failures:
        print("  all events schema-valid")
    for key, n in failures.most_common():
        print(f"  FAIL x{n}: validator={key[0]} msg~{key[1]!r}")
        for ex in fail_examples[key]:
            print(f"      line {ex[0]} {ex[1]} {ex[2]} at {ex[3]}: {ex[4]}")

    # evidence_refs maxItems / uniqueness on each event (schema also covers, but explicit)
    over20 = [(ln, e.get("case_id"), len(e["evidence_refs"]))
              for ln, e in events
              if isinstance(e.get("evidence_refs"), list) and len(e["evidence_refs"]) > 20]
    dupes = [(ln, e.get("case_id"), e["evidence_refs"])
             for ln, e in events
             if isinstance(e.get("evidence_refs"), list)
             and len(set(e["evidence_refs"])) != len(e["evidence_refs"])]
    empty = [(ln, e.get("case_id"), e.get("event_type"))
             for ln, e in events
             if e.get("event_type") == "tool_result_consumed"
             and not (e.get("evidence_refs") or [])]
    print(f"  events with >20 evidence_refs: {len(over20)} {over20[:5]}")
    print(f"  events with duplicate evidence_refs: {len(dupes)} {dupes[:5]}")
    print(f"  tool_result_consumed with empty refs: {len(empty)} {empty[:5]}")

    # duplicate event_id
    ids = collections.Counter(e["event_id"] for _, e in events)
    dup_ids = [i for i, n in ids.items() if n > 1]
    print(f"  duplicate event_id: {len(dup_ids)} {dup_ids[:5]}")

    # ---------------- Task 2: workflow structure --------------------------
    print("\n=== TASK 2: workflow / lifecycle structure ===")
    by_case = collections.OrderedDict()
    for lineno, e in events:
        by_case.setdefault(e["case_id"], []).append((lineno, e))

    print(f"cases in trace: {len(by_case)}")
    outs = {}
    for p in sorted(glob.glob(str(outs_dir / "*.json"))):
        o = json.loads(Path(p).read_text(encoding="utf-8"))
        outs[o["case_id"]] = o
    print(f"cases in outputs: {len(outs)}")
    only_trace = sorted(set(by_case) - set(outs))
    only_out = sorted(set(outs) - set(by_case))
    print(f"  in trace but no output: {len(only_trace)} {only_trace[:10]}")
    print(f"  in output but no trace: {len(only_out)} {only_out[:10]}")

    problems = collections.defaultdict(list)   # case -> [issue strings]
    ev_count = collections.Counter()
    first_last = []
    for cid, evs in by_case.items():
        types = [e["event_type"] for _, e in evs]
        ev_count[tuple(types)] += 1
        if types[0] != "case_received":
            problems[cid].append(f"first event is {types[0]!r}, not case_received")
        if types[-1] != "case_finalized":
            problems[cid].append(f"last event is {types[-1]!r}, not case_finalized")
        for req in REQUIRED:
            n = types.count(req)
            if n == 0:
                problems[cid].append(f"missing required event {req!r}")
            elif n > 1:
                problems[cid].append(f"required event {req!r} occurs {n} times")
        if "verification_completed" in types and "case_finalized" in types:
            if types.index("verification_completed") > types.index("case_finalized"):
                problems[cid].append("verification_completed after case_finalized")
        if "case_received" in types and "case_finalized" in types:
            if types.index("case_received") > types.index("case_finalized"):
                problems[cid].append("case_received after case_finalized")
        # ordering: all events should be non-decreasing in occurred_at
        ts = [e["occurred_at"] for _, e in evs]
        if ts != sorted(ts):
            problems[cid].append("occurred_at not monotonic")
        # actor collaboration: every task_assigned target must appear as a handoff actor later
        for idx, (ln, e) in enumerate(evs):
            if e["event_type"] == "task_assigned" and e.get("target"):
                tgt = e["target"]
                later_actors = {x.get("actor") for _, x in evs[idx + 1:]}
                if tgt not in later_actors:
                    problems[cid].append(
                        f"task_assigned target {tgt!r} never appears as a later handoff actor"
                    )
        # handoff chain: consecutive handoff actors should chain via target
        chain = [(e.get("actor"), e.get("target")) for _, e in evs if e["event_type"] == "handoff"]
        for a, b in chain:
            if b is None:
                problems[cid].append(f"handoff by {a!r} has null target")
        first_last.append((cid, types))

    print(f"\ncases with structural problems: {len(problems)}")
    kind = collections.Counter()
    for cid, iss in problems.items():
        for i in iss:
            kind[i.split("(")[0].strip()] += 1
    for k, n in kind.most_common():
        print(f"  {n:>4}  {k}")
    print("\n  examples:")
    for cid, iss in list(problems.items())[:8]:
        print(f"    {cid}: {iss}")

    # event-type sequence distribution
    print("\n  event-type sequences seen (count):")
    for seq, n in ev_count.most_common(12):
        print(f"    n={n:<4} {list(seq)}")

    # ---------------- actor / tool coverage -------------------------------
    print("\n=== actor & tool summary ===")
    actors = collections.Counter(e.get("actor") for _, e in events)
    print("  actors:", dict(actors))
    tools = collections.Counter(e.get("tool_name") for _, e in events
                                if e["event_type"] == "tool_result_consumed")
    print("  tools:", dict(tools))
    calls_per_case = collections.Counter()
    for cid, evs in by_case.items():
        calls_per_case[sum(1 for _, e in evs if e["event_type"] == "tool_result_consumed")] += 1
    print("  calls/case distribution:", dict(sorted(calls_per_case.items())))
    doms = collections.Counter()
    for _, e in events:
        if e["event_type"] == "tool_result_consumed":
            doms[(e.get("attributes") or {}).get("domain")] += 1
    print("  domains:", dict(doms))
    ncase = collections.Counter()
    for cid, evs in by_case.items():
        ncase[len(evs)] += 1
    print("  events/case distribution:", dict(sorted(ncase.items())))


if __name__ == "__main__":
    main()
