import json, collections, glob, os
OUT='tools/_bak/outputs_4593'; TR='tools/_bak/trace_4593.jsonl'
ev=collections.defaultdict(list)
for l in open(TR,encoding='utf-8'):
    e=json.loads(l); ev[e['case_id']].append(e)
outs={}
for p in sorted(glob.glob(OUT+'/*.json')):
    o=json.load(open(p,encoding='utf-8')); outs[o['case_id']]=o
print("cases:",len(outs))

D=collections.defaultdict(list)
for cid,o in outs.items():
    rc=o['root_cause_analysis']['responsible_parties']
    if any(p.get('party_id') is None for p in rc): D['null_party_id'].append(cid)
    if any(l.get('entity_id') is None for l in o['financial_resolution']['refund_lines']):
        D['null_refund_entity'].append(cid)
    if not o['data_conflicts']: D['no_data_conflicts'].append(cid)
    dc=[c['field'] for c in o['data_conflicts']]
    if 'order_timeline.order_status' not in dc: D['no_order_conflict'].append(cid)
    iss=o['assessment']['primary_issue']; sv=o['shipment_analysis']['verdict']
    if iss=='late_delivery_logistics' and sv!='logistics_delay': D['ship_vs_issue'].append(cid)
    if iss=='late_delivery_seller' and sv!='seller_delay': D['ship_vs_issue'].append(cid)
    # trace/output mismatch
    pd=[e for e in ev[cid] if e['event_type']=='policy_decided'][0]
    sel=[c['selected_source'] for c in o['data_conflicts'] if c['field']=='assessment.primary_issue']
    if sel and sel[0]!=pd.get('attributes',{}).get('selected_source'):
        D['trace_out_selected_source'].append(cid)
    vc=[e for e in ev[cid] if e['event_type']=='verification_completed'][0]
    if vc.get('decision_code')!='verification_passed': D['verification_downgraded'].append(cid)
    # trace structure
    types=[e['event_type'] for e in ev[cid]]
    if types.count('task_assigned')!=1: D['task_assigned_x5'].append(cid)
    if types.count('handoff')!=1: D['handoff_x6'].append(cid)
    assigned={e['target'] for e in ev[cid] if e['event_type']=='task_assigned'}
    for e in ev[cid]:
        if e['event_type']=='handoff' and e.get('target') not in (None,):
            pass
    # policy-agent never hands off
    if 'policy-agent' not in {e.get('actor') for e in ev[cid] if e['event_type']=='handoff'}:
        D['policy_agent_no_handoff'].append(cid)

print()
for k in sorted(D,key=lambda x:-len(D[x])):
    print(f"{k:32s} {len(D[k]):>4}/100  {sorted(D[k])[:12]}{' ...' if len(D[k])>12 else ''}")

# final structural facts
print("\n-- trace structural facts --")
print("task_assigned count per case:", collections.Counter(
    sum(1 for e in ev[c] if e['event_type']=='task_assigned') for c in ev))
print("handoff count per case:", collections.Counter(
    sum(1 for e in ev[c] if e['event_type']=='handoff') for c in ev))
print("case_received count per case:", collections.Counter(
    sum(1 for e in ev[c] if e['event_type']=='case_received') for c in ev))
print("case_finalized count per case:", collections.Counter(
    sum(1 for e in ev[c] if e['event_type']=='case_finalized') for c in ev))
print("first event == case_received:", all(ev[c][0]['event_type']=='case_received' for c in ev))
print("last event == case_finalized:", all(ev[c][-1]['event_type']=='case_finalized' for c in ev))
