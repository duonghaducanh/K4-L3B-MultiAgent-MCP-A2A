import json, collections
OUT='tools/_bak/outputs_4593'; TR='tools/_bak/trace_4593.jsonl'
ev=collections.defaultdict(list)
for l in open(TR,encoding='utf-8'):
    e=json.loads(l); ev[e['case_id']].append(e)

# 1) cases with no order_timeline conflict -> was there a decoy?
print("== cases with NO order_timeline.order_status conflict ==")
for cid in ['L3B_CASE_039','L3B_CASE_089','L3B_CASE_012','L3B_CASE_062','L3B_CASE_071','L3B_CASE_098']:
    o=json.load(open(f'{OUT}/{cid}.json',encoding='utf-8'))
    fields=[c['field'] for c in o['data_conflicts']]
    pd=[e for e in ev[cid] if e['event_type']=='policy_decided']
    ent=[e for e in ev[cid] if e['event_type']=='handoff' and e.get('actor')=='entity-agent']
    print(f"  {cid} issue={o['assessment']['primary_issue']:24s} conflicts={fields} "
          f"entity_dc={ent[0].get('decision_code') if ent else None} pd_dc={pd[0].get('decision_code') if pd else None}")

# 2) derived mismatch cases: what does policy_decided say vs output
print("\n== derived != claimed cases ==")
for cid in ['L3B_CASE_012','L3B_CASE_062','L3B_CASE_071','L3B_CASE_098']:
    o=json.load(open(f'{OUT}/{cid}.json',encoding='utf-8'))
    pd=[e for e in ev[cid] if e['event_type']=='policy_decided'][0]
    vc=[e for e in ev[cid] if e['event_type']=='verification_completed'][0]
    print(f"  {cid} out_issue={o['assessment']['primary_issue']} out_status={o['assessment']['case_status']} "
          f"conf={o['assessment']['confidence']} pd_dc={pd.get('decision_code')} "
          f"pd_attr={pd.get('attributes')} verify={vc.get('decision_code')}")

# 3) empty shipment_ids
print("\n== affected_entities empty sets ==")
cnt=collections.Counter()
for cid in sorted(ev):
    o=json.load(open(f'{OUT}/{cid}.json',encoding='utf-8'))
    for k in ('order_ids','item_ids','seller_ids','payment_references','shipment_ids'):
        if not o['affected_entities'][k]: cnt[k]+=1
print("  ",dict(cnt))
