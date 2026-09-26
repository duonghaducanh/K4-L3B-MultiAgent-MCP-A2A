"""Evidence citation census over the 100-case v1 outputs."""
from __future__ import annotations
import json, pathlib
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "tools/_bak/outputs_4593"
TRACE = ROOT / "tools/_bak/trace_4593.jsonl"

# map ref -> tool name from the trace
ref2tool = {}
for line in TRACE.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    e = json.loads(line)
    if e.get("event_type") == "tool_result_consumed":
        for r in (e.get("evidence_refs") or []):
            ref2tool.setdefault(r, (e.get("attributes") or {}).get("tool") or e.get("decision_code"))

lines = []
def p(s): lines.append(str(s))

p("refs mapped to tools: %d" % len(ref2tool))
tool_counts = Counter(t for t in ref2tool.values())
p("tool distribution over all consumed refs: %s" % tool_counts.most_common())

# per case: refs cited by outputs, grouped by claim
claim_sizes = Counter()
case_ref_tools = defaultdict(Counter)
n_out = 0
for f in sorted(OUT.glob("*.json")):
    o = json.loads(f.read_text(encoding="utf-8"))
    n_out += 1
    for ca in (o.get("claim_assessments") or []):
        refs = ca.get("evidence_refs") or []
        claim_sizes[len(refs)] += 1
        for r in refs:
            case_ref_tools[f.stem][ref2tool.get(r, "UNKNOWN")] += 1

p("outputs: %d" % n_out)
p("claim evidence_refs size distribution: %s" % sorted(claim_sizes.items()))
# most common tool-mix for a claim
mixes = Counter()
for f in sorted(OUT.glob("*.json")):
    o = json.loads(f.read_text(encoding="utf-8"))
    for ca in (o.get("claim_assessments") or []):
        refs = ca.get("evidence_refs") or []
        mix = tuple(sorted(Counter(ref2tool.get(r, "?") for r in refs).items()))
        mixes[mix] += 1
p("distinct claim ref-mixes: %d" % len(mixes))
for mix, n in mixes.most_common(10):
    p("  x%-4d %s" % (n, mix))

# how many total distinct refs cited per case
tot = Counter()
for f in sorted(OUT.glob("*.json")):
    o = json.loads(f.read_text(encoding="utf-8"))
    s = set()
    for ca in (o.get("claim_assessments") or []):
        s |= set(ca.get("evidence_refs") or [])
    s |= set(o.get("evidence_refs") or [])
    tot[len(s)] += 1
p("distinct refs per case: %s" % sorted(tot.items()))

pathlib.Path(ROOT / "tools/_o_ev3.txt").write_text("\n".join(lines), encoding="utf-8")
print("ok")
