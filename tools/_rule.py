"""Test attribution rules against the archetypes' known-correct target captures."""
import json, pathlib
from datetime import datetime
ROOT=pathlib.Path('.')
learn=json.loads((ROOT/'tools/_learn1.json').read_text(encoding='utf-8'))
learn['L3B_CASE_001']=json.loads((ROOT/'tools/_case001.json').read_text(encoding='utf-8'))
def P(v): return datetime.fromisoformat(v) if v else None
EXP={1:16.0,2:89.0,3:35.0,4:128.0,5:89.0,6:52.0,7:89.0,8:79.0,9:89.0,10:18.0}
def cur(ts,h):
    m=P(ts)
    if m is None or not h: return None
    for o in h:
        d=P(o['order_delivered_customer_date'])
        if d is not None and abs((m-d).total_seconds())<3600: return o
    return min(h,key=lambda o:abs((m-P(o['order_purchase_timestamp'])).total_seconds()))
def le(ts,h):
    m=P(ts)
    if m is None or not h: return None
    c=[o for o in h if P(o['order_purchase_timestamp'])<=m]
    return max(c,key=lambda o:P(o['order_purchase_timestamp'])) if c else min(h,key=lambda o:P(o['order_purchase_timestamp']))
def near(ts,h):
    m=P(ts)
    if m is None or not h: return None
    return min(h,key=lambda o:abs((m-P(o['order_purchase_timestamp'])).total_seconds()))
def dle(ts,h):
    m=P(ts)
    if m is None or not h: return None
    for o in h:
        d=P(o['order_delivered_customer_date'])
        if d is not None and abs((m-d).total_seconds())<3600: return o
    return le(ts,h)
RULES=[('current',cur),('purchase<=t',le),('nearest',near),('deliv|purchase<=t',dle)]
out=[]; p=out.append
p('%-5s %-22s %8s  %s'%('case','topic','expected','  '.join('%-16s'%r[0] for r in RULES)))
tot={r[0]:0 for r in RULES}
for i in range(1,11):
    cid='L3B_CASE_%03d'%i
    ev=learn[cid]
    h=(ev['get_customer_history'].get('data') or {}).get('orders') or []
    evs=(ev['get_payment_timeline'].get('data') or {}).get('events') or []
    inp=json.loads((ROOT/f'inputs/{cid}.json').read_text(encoding='utf-8'))
    op=P(inp['opened_at'])
    before=[o for o in h if P(o['order_purchase_timestamp'])<=op] or h
    tgt=max(before,key=lambda o:P(o['order_purchase_timestamp']))
    cells=[]
    for name,fn in RULES:
        s=round(sum(float(e['amount_brl']) for e in evs if e['event_type']=='captured' and fn(e['event_at'],h) is tgt),2)
        ok='OK' if abs(s-EXP[i])<0.01 else 'XX'
        if ok=='OK': tot[name]+=1
        cells.append('%6.2f %s'%(s,ok))
    p('%-5d %-22s %8.2f  %s'%(i,'',EXP[i],'  '.join('%-16s'%c for c in cells)))
p('')
p('correct counts: '+', '.join('%s=%d/10'%(k,v) for k,v in tot.items()))
p('')
p('--- event detail ---')
for i in range(1,11):
    cid='L3B_CASE_%03d'%i
    ev=learn[cid]
    h=(ev['get_customer_history'].get('data') or {}).get('orders') or []
    evs=(ev['get_payment_timeline'].get('data') or {}).get('events') or []
    inp=json.loads((ROOT/f'inputs/{cid}.json').read_text(encoding='utf-8'))
    op=P(inp['opened_at'])
    before=[o for o in h if P(o['order_purchase_timestamp'])<=op] or h
    tgt=max(before,key=lambda o:P(o['order_purchase_timestamp']))
    p('%d: rows purch=%s'%(i,[o['order_purchase_timestamp'][:10] for o in h]))
    for e in evs:
        if e['event_type']!='captured': continue
        p('    %s %s %s -> cur=%s le=%s'%(e['event_at'],e['amount_brl'],
          'TGT' if cur(e['event_at'],h) is tgt else 'oth',
          'TGT' if cur(e['event_at'],h) is tgt else 'oth',
          'TGT' if le(e['event_at'],h) is tgt else 'oth'))
(ROOT/'tools/_o_rule.txt').write_text('\n'.join(out),encoding='utf-8')
print('ok')
