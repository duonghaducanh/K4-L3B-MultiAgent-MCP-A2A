import json, pathlib, collections
root = pathlib.Path("outputs")
rows = []
for p in sorted(root.glob("*.json")):
    o = json.loads(p.read_text(encoding="utf-8"))
    a = o.get("assessment") or {}
    rows.append((p.stem, a.get("primary_issue"), a.get("case_status"), a.get("confidence"),
                 (o.get("payment_analysis") or {}).get("verdict"),
                 (o.get("shipment_analysis") or {}).get("verdict"),
                 (o.get("payment_analysis") or {}).get("captured_total_brl"),
                 len(o.get("data_conflicts") or [])))
hist = collections.Counter(r[3] for r in rows)
print("confidence histogram:", dict(sorted(hist.items())))
print("by (confidence, primary_issue, status):")
c = collections.Counter((r[3], r[1], r[2]) for r in rows)
for k, v in sorted(c.items(), key=lambda kv: str(kv[0])):
    print("  ", k, v)
print()
print("cases with nonzero data_conflicts or odd captured:")
for r in rows:
    if r[7] or r[2] == "needs_investigation":
        print("  ", r)
