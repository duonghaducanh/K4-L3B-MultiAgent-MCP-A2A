"""Reproduce _owner() attribution for archetypes 001-010 and check target captures."""
import json, pathlib
from datetime import datetime
ROOT=pathlib.Path('.')
learn=json.loads((ROOT/'tools/_learn1.json').read_text(encoding='utf-8'))
learn['L3B_CASE_001']=json.loads((ROOT/'tools/_case001.json').read_text(encoding='utf-8'))
def P(v): return datetime.fromisoformat(v) if v else None
def owner(ts, hist):
    m=P(ts)
    if m is None or not hist: return None
    for o in hist:
        d=P(o['order_delivered_customer_date'])
        if d is not None and abs((m-d).total_seconds())<3600: return o
    return min(hist,key=lambda o: abs((m-P(o['order_purchase_timestamp'])).total_seconds()))
out=[]; p=out.append
for i in range(1,11):
    cid='L3B_CASE_%03d'%i
    ev=learn[cid]
    hist=(ev['get_customer_history'].get('data') or {}).get('orders') or []
    pt=(ev['get_payment_timeline'].get('data') or {})
    events=pt.get('events') or []
    inp=json.loads((ROOT/f'inputs/{cid}.json').read_text(encoding='utf-8'))
    opened=P(inp['opened_at'])
    before=[o for o in hist if P(o['order_purchase_timestamp'])<=opened] or hist
    tgt=max(before,key=lambda o:P(o['order_purchase_timestamp']))
    p('%s opened=%s'%(cid,inp['opened_at']))
    for j,o in enumerate(hist):
        mark='TARGET' if o is tgt else 'other '
        p('   %s purch=%s deliv=%s'%(mark,o['order_purchase_timestamp'],o['order_delivered_customer_date']))
    tot=0.0; rows=[]
    for e in events:
        o=owner(e['event_at'],hist)
        who='TARGET' if o is tgt else 'other'
        rows.append('%s@%s %s %s'%(e['event_type'],e['event_at'][11:16],e['amount_brl'],who))
        if e['event_type']=='captured' and o is tgt: tot+=float(e['amount_brl'])
    p('   events: %s'%(' | '.join(rows)))
    p('   target captured = %.2f'%round(tot,2))
    p('')
(ROOT/'tools/_o_own.txt').write_text('\n'.join(out),encoding='utf-8')
print('ok')
