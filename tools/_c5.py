import json, pathlib
ROOT=pathlib.Path('.')
out=[]
for n in ['005','015','025']:
    cid=f'L3B_CASE_{n}'
    inp=json.loads((ROOT/f'inputs/{cid}.json').read_text(encoding='utf-8'))
    o=json.loads((ROOT/f'outputs/{cid}.json').read_text(encoding='utf-8'))
    out.append('===== '+cid)
    out.append('claims: '+json.dumps(inp['customer_request']['claims'],ensure_ascii=False))
    out.append('opened_at: '+inp['opened_at'])
    out.append('assessment: '+json.dumps(o['assessment'],ensure_ascii=False))
    out.append('shipment: '+json.dumps(o['shipment_analysis'],ensure_ascii=False))
    out.append('payment: '+json.dumps(o['payment_analysis'],ensure_ascii=False))
    out.append('financial: '+json.dumps(o['financial_resolution'],ensure_ascii=False))
    out.append('causes: '+json.dumps(o['root_cause_analysis'],ensure_ascii=False))
    out.append('actions: '+json.dumps(o['resolution_actions'],ensure_ascii=False))
    out.append('')
(ROOT/'tools/_o_c5.txt').write_text('\n'.join(out),encoding='utf-8')
print('ok')
