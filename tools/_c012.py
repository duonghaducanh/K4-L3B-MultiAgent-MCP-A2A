import json, pathlib
ROOT=pathlib.Path('.')
out=[]
for cid in ['L3B_CASE_012','L3B_CASE_062','L3B_CASE_071','L3B_CASE_098']:
    out.append('########## '+cid)
    for line in (ROOT/'traces/trace.jsonl').read_text(encoding='utf-8').splitlines():
        if not line.strip(): continue
        e=json.loads(line)
        if e.get('case_id')!=cid: continue
        et=e.get('event_type')
        if et=='tool_result_consumed':
            out.append('  CALL %-24s refs=%d attrs=%s'%(e.get('tool_name'),len(e.get('evidence_refs') or []),json.dumps(e.get('attributes'),ensure_ascii=False)))
        elif et in ('policy_decided','conflict_resolved','verification_completed','handoff'):
            out.append('  %-22s %-18s %-26s %s'%(et,e.get('actor'),e.get('decision_code'),json.dumps(e.get('attributes'),ensure_ascii=False)[:220]))
    o=json.loads((ROOT/f'outputs/{cid}.json').read_text(encoding='utf-8'))
    out.append('  OUT primary=%s conf=%s status=%s'%(o['assessment']['primary_issue'],o['assessment']['confidence'],o['assessment']['case_status']))
    out.append('  OUT payment=%s'%json.dumps(o['payment_analysis'],ensure_ascii=False))
    out.append('  OUT shipment=%s'%json.dumps(o['shipment_analysis'],ensure_ascii=False))
    out.append('  OUT conflicts=%s'%json.dumps(o['data_conflicts'],ensure_ascii=False))
    out.append('  OUT financial=%s'%json.dumps(o['financial_resolution'],ensure_ascii=False))
    out.append('')
(ROOT/'tools/_o_c012.txt').write_text('\n'.join(out),encoding='utf-8')
print('ok')
