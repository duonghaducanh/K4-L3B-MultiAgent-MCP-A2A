import json, pathlib
ROOT=pathlib.Path('.')
learn=json.loads((ROOT/'tools/_learn1.json').read_text(encoding='utf-8'))
out=[]
for cid in ['L3B_CASE_005']:
    ev=learn[cid]
    inp=json.loads((ROOT/f'inputs/{cid}.json').read_text(encoding='utf-8'))
    out.append('=== '+cid+' opened_at='+inp['opened_at'])
    out.append('claimed='+inp['customer_request']['claimed_order_id'])
    out.append('candidates='+json.dumps(inp['candidate_order_ids']))
    for tool in ['get_order','get_order_items','get_order_payments','get_payment_timeline','get_refund_timeline','get_shipment_summary','get_customer_history']:
        p=ev.get(tool)
        if not p: out.append('-- %s MISSING'%tool); continue
        d=p.get('data')
        out.append('-- '+tool)
        out.append('   '+json.dumps(d,ensure_ascii=False)[:1400])
(ROOT/'tools/_o_c5ev.txt').write_text('\n'.join(out),encoding='utf-8')
print('ok')
