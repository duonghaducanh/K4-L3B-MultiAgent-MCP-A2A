import json, glob
from datetime import datetime, timezone
OUT=open('tools/_aud_cap.txt','w',encoding='utf-8')
def p(*a): print(*a, file=OUT)
def P(v):
    if not v: return None
    return datetime.fromisoformat(v)
def owner(ts, hist):
    t=P(ts)
    for h in hist:
        d=P(h.get('order_delivered_customer_date'))
        if d and abs((t-d).total_seconds())<=3600: return h['order_id']
    best=None; bd=None
    for h in hist:
        pp=P(h['order_purchase_timestamp'])
        dd=abs((t-pp).total_seconds())
        if bd is None or dd<bd: bd=dd; best=h['order_id']
    return best

learn=json.load(open('tools/_learn1.json',encoding='utf-8'))
learn['L3B_CASE_001']=json.load(open('tools/_case001.json',encoding='utf-8'))
p('=== case001 top-level keys ===')
p(sorted(learn['L3B_CASE_001'].keys()))
for num in range(1,11):
    cid='L3B_CASE_%03d'%num
    ev=learn[cid]
    hist=ev['get_customer_history']['data']['orders']
    claim=ev.get('claimed') or ev.get('claim') or {}
    p('\n== %s  claimed=%s'%(cid,json.dumps(claim,ensure_ascii=False)[:300]))
    p('   candidate_get_order=%s'%json.dumps(ev.get('candidate_get_order'),ensure_ascii=False)[:200])
    tl=(ev.get('get_payment_timeline') or {}).get('data') or {}
    by={}
    for e in tl.get('events') or []:
        if e.get('event_type')!='captured': continue
        o=owner(e['event_at'],hist)
        by.setdefault(o,0.0); by[o]+=float(e.get('amount_brl') or 0)
    p('   per-owner captured: %s'%json.dumps(by,ensure_ascii=False))
    for h in hist:
        p('      %s purch=%s deliv=%s status=%-11s cap=%s'%(h['order_id'][:8],h['order_purchase_timestamp'][:19],(h.get('order_delivered_customer_date') or 'None')[:19],h['order_status'],by.get(h['order_id'],0.0)))
    o=json.load(open('tools/_bak/outputs_4593/%s.json'%cid,encoding='utf-8'))
    p('   OUTPUT captured=%s refundable=%s rec=%s verdict=%s issue=%s'%(o['payment_analysis']['captured_total_brl'],o['payment_analysis']['refundable_total_brl'],o['financial_resolution']['recommended_refund_brl'],o['payment_analysis']['verdict'],o['assessment']['primary_issue']))
OUT.close(); print('ok')
