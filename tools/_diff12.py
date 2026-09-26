"""Diff v1 (4593) vs v2 (live) on the fields the audit flagged."""
from __future__ import annotations
import json, pathlib
from collections import Counter
ROOT = pathlib.Path(__file__).resolve().parents[1]
V1 = ROOT/"tools/_bak/outputs_4593"; V2 = ROOT/"outputs"
lines=[]; p=lines.append

def prof(root, label):
    ship=Counter(); party=Counter(); ent=Counter(); dc=Counter(); refs=Counter()
    for f in sorted(root.glob("*.json")):
        o=json.loads(f.read_text(encoding="utf-8"))
        ship[json.dumps(o["affected_entities"]["shipment_ids"])]+=1
        for rp in o["root_cause_analysis"]["responsible_parties"]:
            party[json.dumps(rp)]+=1
        for rl in o["financial_resolution"]["refund_lines"]:
            ent[json.dumps(rl.get("entity_id"))]+=1
        dc[json.dumps(o["data_conflicts"])[:60]]+=1
        refs[len(o["evidence_refs"])]+=1
    p("===== %s =====" % label)
    p("shipment_ids: %s" % dict(ship))
    p("responsible_parties: %s" % dict(party.most_common(8)))
    p("refund entity_id: %s" % dict(ent))
    p("data_conflicts: %s" % dict(dc.most_common(4)))
    p("evidence_refs len: %s" % dict(refs))
    p("")

prof(V1, "V1 (scored 88.64)")
prof(V2, "V2 (scored 91.24)")
pathlib.Path(ROOT/"tools/_o_diff12.txt").write_text("\n".join(lines),encoding="utf-8")
print("ok")
