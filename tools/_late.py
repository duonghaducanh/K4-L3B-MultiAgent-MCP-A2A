"""Compare the shipment-event actor against the date-derivation fallback, archetypes 1-10."""
import json, pathlib
from datetime import datetime
ROOT=pathlib.Path('.')
learn=json.loads((ROOT/'tools/_learn1.json').read_text(encoding='utf-8'))
learn['L3B_CASE_001']=json.loads((ROOT/'tools/_case001.json').read_text(encoding='utf-8'))
def D(v):
    if isinstance(v,dict) and 'data' in v: return v['data']
    return v
def P(v): return datetime.fromisoformat(v) if v else None
def owner(ts,h):
    m=P(ts)
    if m is None or not h: return None
    for o in h:
        d=P(o['order_delivered_customer_date'])
        if d is not None and abs((m-d).total_seconds())<3600: return o
    return min(h,key=lambda o:abs((m-P(o['order_purchase_timestamp'])).total_seconds()))
out=[]; p=out.append
agree=0
for i in range(1,11):
    cid='L3B_CASE_%03d'%i
    ev=learn[cid]
    h=D(ev['get_customer_history']).get('orders') or []
    inp=json.loads((ROOT/f'inputs/{cid}.json').read_text(encoding='utf-8'))
    op=P(inp['opened_at'])
    before=[o for o in h if P(o['order_purchase_timestamp'])<=op] or h
    tgt=max(before,key=lambda o:P(o['order_purchase_timestamp']))
    ss=D(ev.get('get_shipment_summary')) or {}
    ev_actor=None
    for e in ss.get('events') or []:
        if e.get('event_type')=='delivered_late' and owner(e['event_at'],h) is tgt:
            ev_actor=e.get('actor')
    items=[r for r in (D(ev.get('get_order_items')) or []) if owner(r.get('shipping_limit_date'),h) is tgt]
    carrier=P(tgt.get('order_delivered_carrier_date'))
    limits=[P(r['shipping_limit_date']) for r in items if r.get('shipping_limit_date')]
    fb=None
    if carrier and limits: fb='seller' if carrier>min(limits) else 'logistics_provider'
    ok=(ev_actor==fb)
    if ok: agree+=1
    p('%s purch=%s carrier=%s minlimit=%s event=%s fallback=%s %s'
      %(cid,tgt['order_purchase_timestamp'][:10],
        (tgt.get('order_delivered_carrier_date') or 'None')[:10],
        (min(limits).isoformat()[:10] if limits else 'None'),
        ev_actor,fb,'OK' if ok else 'MISMATCH'))
p('')
p('agreement: %d/10'%agree)
pathlib.Path(ROOT/'tools/_o_late.txt').write_text('\n'.join(out),encoding='utf-8')
print('ok')
