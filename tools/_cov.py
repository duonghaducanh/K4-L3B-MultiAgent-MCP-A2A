import json, collections
# map case -> {tool: domain} from trace
case_dom = collections.defaultdict(dict)
case_tools = collections.defaultdict(set)
for line in open("traces/trace.jsonl", encoding="utf-8"):
    e = json.loads(line)
    if e["event_type"] == "tool_result_consumed":
        d = (e.get("attributes") or {}).get("domain")
        case_dom[e["case_id"]][e["tool_name"]] = d
        case_tools[e["case_id"]].add(e["tool_name"])

ALL = {"order","item","payment","shipment","seller","customer","product","refund","policy"}
rows = []
for p in sorted(__import__("glob").glob("outputs/*.json")):
    o = json.load(open(p, encoding="utf-8"))
    cid = o["case_id"]
    doms = set(v for v in case_dom[cid].values() if v)
    missing = ALL - doms
    rows.append((cid, o["assessment"]["primary_issue"], len(o["evidence_refs"]),
                 sorted(missing), len(case_tools[cid])))
print("cases missing refund domain:", sum(1 for r in rows if "refund" in r[3]))
print("cases missing >1 domain:", [r[0] for r in rows if len(r[3])>1])
print("cases missing exactly 1 domain:", sum(1 for r in rows if len(r[3])==1))
print()
print("domain-set frequency:")
for ds, n in collections.Counter(tuple(r[3]) for r in rows).most_common():
    print(f"  missing={list(ds)}  n={n}")
print()
print("by issue, avg domains missing:")
by = collections.defaultdict(list)
for r in rows: by[r[1]].append(len(r[3]))
for k, v in sorted(by.items()): print(f"  {k:26s} {sum(v)/len(v):.2f}")
