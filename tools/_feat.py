import json, glob, collections
cases=[]
for p in sorted(glob.glob("outputs/*.json")):
    o=json.load(open(p,encoding="utf-8")); cases.append(o)

def feat(o):
    f={}
    f["issue"]=o["assessment"]["primary_issue"]
    f["nrefs"]=len(o["evidence_refs"])
    f["nconf"]=len(o["data_conflicts"])
    f["conf"]=o["assessment"]["confidence"]
    f["ship"]=o["shipment_analysis"]["verdict"]
    f["pay"]=o["payment_analysis"]["verdict"]
    f["captured"]=o["payment_analysis"]["captured_total_brl"]
    f["refundable"]=o["payment_analysis"]["refundable_total_brl"]
    f["refund"]=o["financial_resolution"]["recommended_refund_brl"]
    f["nclaims"]=len(o.get("claim_assessments",[]))
    f["party"]=tuple(p["party_type"] for p in o["root_cause_analysis"]["responsible_parties"])
    f["timeline"]=o["shipment_analysis"]["timeline_complete"]
    f["nsellers"]=len(o["affected_entities"]["seller_ids"])
    return f

for half,name in [(cases[:50],"1-50"),(cases[50:],"51-100"),(cases,"all100")]:
    print("="*20,name)
    feats=[feat(o) for o in half]
    for key in feats[0]:
        vals=collections.Counter(str(f[key]) for f in feats)
        if len(vals)<=8:
            print(f"  {key}: {dict(vals)}")
