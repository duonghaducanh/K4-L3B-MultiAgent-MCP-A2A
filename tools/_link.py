import json, collections, glob
trace_refs = collections.defaultdict(set)   # case -> refs in trace
trace_ref_events = collections.defaultdict(int)
for line in open("traces/trace.jsonl", encoding="utf-8"):
    e = json.loads(line)
    for r in (e.get("evidence_refs") or []):
        trace_refs[e["case_id"]].add(r)
        if e["event_type"] == "tool_result_consumed":
            trace_ref_events[e["case_id"]] += 1
rows=[]
for p in sorted(glob.glob("outputs/*.json")):
    o = json.load(open(p, encoding="utf-8")); cid=o["case_id"]
    out_refs = set(o["evidence_refs"])
    claim_refs = set()
    for c in o.get("claim_assessments",[]): claim_refs |= set(c.get("evidence_refs",[]))
    missing = out_refs - trace_refs[cid]
    claim_missing = claim_refs - trace_refs[cid]
    rows.append((cid, len(out_refs), len(trace_refs[cid]), len(missing), len(claim_missing)))
bad_out = [r for r in rows if r[3]]
bad_clm = [r for r in rows if r[4]]
print("cases whose OUTPUT refs are not all in trace:", len(bad_out), bad_out[:5])
print("cases whose CLAIM refs are not all in trace:", len(bad_clm), bad_clm[:5])
print("cases with 0 trace refs:", [r[0] for r in rows if r[2]==0])
print()
print("output refs count distribution:", dict(collections.Counter(r[1] for r in rows)))
print("trace refs count distribution:", dict(collections.Counter(r[2] for r in rows)))
