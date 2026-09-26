"""Audit 2 - Task 1: provenance / evidence-to-trace linkage.

Usage: python tools/_aud2_prov.py [outputs_dir] [trace_path]
Defaults: outputs/ and traces/trace.jsonl
"""
from __future__ import annotations

import collections
import glob
import json
import re
import sys
from pathlib import Path

REF_RE = re.compile(r"^ev_[A-Za-z0-9_-]{20,96}$")


def load_trace(path: Path):
    events = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError as exc:
            print(f"  !! trace line {lineno}: invalid JSON: {exc}")
    return events


def out_refs(o):
    """(ref, where) for every evidence ref used anywhere in an output."""
    found = []
    for r in o.get("evidence_refs") or []:
        found.append((r, "evidence_refs"))
    for i, c in enumerate(o.get("claim_assessments") or []):
        for r in c.get("evidence_refs") or []:
            found.append((r, f"claim_assessments[{i}].evidence_refs"))
    return found


def main():
    outs_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("outputs")
    trace_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("traces/trace.jsonl")
    print(f"# outputs_dir={outs_dir}  trace={trace_path}")

    events = load_trace(trace_path)
    print(f"trace events: {len(events)}")

    # ---- trace side -------------------------------------------------------
    consumed = [e for e in events if e.get("event_type") == "tool_result_consumed"]
    ref_in_consumed = collections.defaultdict(set)   # ref -> {case_id}
    case_consumed_refs = collections.defaultdict(set)  # case_id -> {ref}
    ref_tools = collections.defaultdict(set)
    consumed_no_refs = []
    consumed_bad_refs = []
    consumed_dupe_refs = []
    consumed_over_20 = []
    per_case_consumed = collections.Counter()

    for e in consumed:
        cid = e.get("case_id")
        refs = e.get("evidence_refs")
        per_case_consumed[cid] += 1
        if not refs:
            consumed_no_refs.append(e)
            continue
        if len(refs) > 20:
            consumed_over_20.append((cid, len(refs)))
        if len(set(refs)) != len(refs):
            consumed_dupe_refs.append((cid, refs))
        for r in refs:
            if not REF_RE.match(r):
                consumed_bad_refs.append((cid, e.get("tool_name"), r))
            ref_in_consumed[r].add(cid)
            case_consumed_refs[cid].add(r)
            ref_tools[r].add(e.get("tool_name"))

    # any event (not only consumed) carrying refs -> for "used in output but never traced"
    ref_anywhere = collections.defaultdict(set)
    for e in events:
        for r in e.get("evidence_refs") or []:
            ref_anywhere[r].add(e.get("case_id"))

    print(f"tool_result_consumed events: {len(consumed)}")
    print(f"consumed events with EMPTY evidence_refs: {len(consumed_no_refs)}")
    for e in consumed_no_refs[:20]:
        print(f"    {e.get('case_id')} tool={e.get('tool_name')} actor={e.get('actor')}")
    print(f"consumed events with MALFORMED refs: {len(consumed_bad_refs)}")
    for cid, tool, r in consumed_bad_refs[:20]:
        print(f"    {cid} tool={tool} ref={r!r} len={len(r)}")
    print(f"consumed events with DUPLICATE refs in one event: {len(consumed_dupe_refs)}")
    for cid, refs in consumed_dupe_refs[:10]:
        print(f"    {cid} {refs}")
    print(f"consumed events with >20 refs (schema maxItems): {len(consumed_over_20)}")
    for cid, n in consumed_over_20[:10]:
        print(f"    {cid} n={n}")

    # ---- cross-case reuse -------------------------------------------------
    shared = {r: sorted(cs) for r, cs in ref_in_consumed.items() if len(cs) > 1}
    print(f"\nrefs appearing under >1 case_id in consumed events: {len(shared)}")
    for r, cs in list(shared.items())[:20]:
        print(f"    {r} tools={sorted(str(t) for t in ref_tools[r])} cases={cs}")

    # ---- output side ------------------------------------------------------
    rows = []
    out_only = []
    claim_only = []
    for path in sorted(glob.glob(str(outs_dir / "*.json"))):
        o = json.loads(Path(path).read_text(encoding="utf-8"))
        cid = o.get("case_id")
        refs = out_refs(o)
        uniq = {r for r, _ in refs}
        case_refs = case_consumed_refs.get(cid, set())
        missing = sorted(r for r in uniq if r not in case_refs)
        # refs used in this output but only traced under a different case
        wrong_case = sorted(
            r for r in uniq
            if r not in case_refs and r in ref_anywhere
        )
        rows.append({
            "case": cid,
            "n_out_refs": len(o.get("evidence_refs") or []),
            "n_out_refs_uniq": len(set(o.get("evidence_refs") or [])),
            "n_claim_refs": sum(len(c.get("evidence_refs") or []) for c in o.get("claim_assessments") or []),
            "n_uniq_all": len(uniq),
            "n_traced": len(case_refs),
            "n_consumed": per_case_consumed.get(cid, 0),
            "missing": missing,
            "wrong_case": wrong_case,
        })

    bad = [r for r in rows if r["missing"] or r["wrong_case"]]
    print(f"\ncases audited: {len(rows)}")
    print(f"cases with refs NOT traced in the same case: {len(bad)}")
    for r in bad[:20]:
        print(f"    {r['case']} missing={r['missing']} wrong_case={r['wrong_case']}")
    n_zero = [r["case"] for r in rows if r["n_consumed"] == 0]
    print(f"cases with ZERO tool_result_consumed events: {len(n_zero)} {n_zero[:10]}")
    print(f"cases whose output has EMPTY evidence_refs: "
          f"{sum(1 for r in rows if r['n_out_refs'] == 0)}")
    print(f"cases where output refs are NOT unique (dupes): "
          f"{sum(1 for r in rows if r['n_out_refs'] != r['n_out_refs_uniq'])}")

    # trace-only refs (in trace but never in the case's output) - informational
    print("\n-- per-case ref counts (out_top, out_all_uniq, traced, consumed) --")
    dist = collections.Counter((r["n_out_refs"], r["n_uniq_all"], r["n_traced"], r["n_consumed"]) for r in rows)
    for k, n in sorted(dist.items()):
        print(f"    out_top={k[0]:>2} uniq_all={k[1]:>2} traced={k[2]:>2} consumed={k[3]:>2}  n={n}")

    # refs in output but never traced anywhere
    never = collections.defaultdict(list)
    for r in rows:
        for ref in r["missing"]:
            if ref not in ref_anywhere:
                never[r["case"]].append(ref)
    print(f"\ncases with a ref used in output but NEVER in any trace event: {len(never)}")
    for cid, refs in list(never.items())[:10]:
        print(f"    {cid} {refs}")


if __name__ == "__main__":
    main()
