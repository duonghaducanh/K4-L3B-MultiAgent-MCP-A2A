import json, glob, os
from datetime import datetime, timedelta
OUT=open('tools/_aud_decomp.txt','w',encoding='utf-8')
def p(*a): print(*a, file=OUT)
def P(v): return datetime.fromisoformat(v) if v else None

learn=json.load(open('tools/_learn1.json',encoding='utf-8'))
learn['L3B_CASE_001']=json.load(open('tools/_case001.json',encoding='utf-8'))
POL=json.load(open('tools/_policy.json',encoding='utf-8'))['data']['rules']
TOPICS=('late_delivery_logistics','valid_split_payment','payment_mismatch','duplicate_charge',
 'refund_pending','refund_failed','unsupported_claim','canceled_order_paid','unavailable_order_paid','late_delivery_seller')

def owner_ts(ts,hist):
    t=P(ts)
    for h in hist:
        d=P(h.get('order_delivered_customer_date'))
        if d and abs((t-d).total_seconds())<=3600: return h['order_id']
    best=None;bd=None
    for h in hist:
        dd=abs((t-P(h['order_purchase_timestamp'])).total_seconds())
        if bd is None or dd<bd: bd=dd;best=h
    return best['order_id']

def owner_item(row,hist):
    sl=P(row.get('shipping_limit_date'))
    if sl is None: return None
    best=None;bd=None
    for h in hist:
        d=abs((sl-(P(h['order_purchase_timestamp'])+timedelta(days=3))).total_seconds())
        if bd is None or d<bd: bd=d;best=h
    return best['order_id']

p('%-16s %-24s %7s %9s %8s %8s %8s %8s %8s  %s'%('case','topic','polrec','tgtfreight','tgtprice','tgtcap','outrec','outcap','outrefble','match'))
nfree=0; ncap=0; nprice=0
for num in range(1,101):
    cid='L3B_CASE_%03d'%num
    topic=TOPICS[(num-1)%10]
    inp=json.load(open('inputs/%s.json'%cid,encoding='utf-8'))
    opened=P(inp['opened_at'])
    ev=learn.get(cid)
    if ev is None:
        p('%-16s %-24s  (no captured evidence)'%(cid,topic)); continue
    hist=ev['get_customer_history']['data']['orders']
    cand=[h for h in hist if P(h['order_purchase_timestamp'])<=opened]
    tgt=max(cand,key=lambda h:P(h['order_purchase_timestamp'])) if cand else min(hist,key=lambda h:P(h['order_purchase_timestamp']))
    rows=ev.get('get_order_items',{}).get('data') or []
    if isinstance(rows,dict): rows=rows.get('items') or []
    mine=[r for r in rows if owner_item(r,hist)==tgt['order_id']]
    tf=sum(float(r.get('freight_value') or 0) for r in mine)
    tp=sum(float(r.get('price') or 0) for r in mine)
    tl=ev.get('get_payment_timeline',{}).get('data') or {}
    cap=0.0
    for e in tl.get('events') or []:
        if e.get('event_type')!='captured': continue
        if owner_ts(e['event_at'],hist)==tgt['order_id']: cap+=float(e.get('amount_brl') or 0)
    out=json.load(open('tools/_bak/outputs_4593/%s.json'%cid,encoding='utf-8'))
    rec=float(POL[topic]['refund_brl']); orec=float(out['financial_resolution']['recommended_refund_brl'])
    oc=float(out['payment_analysis']['captured_total_brl']); orf=float(out['payment_analysis']['refundable_total_brl'])
    m=[]
    if abs(rec-tf)<.01: m.append('=FREIGHT'); nfree+=1
    if abs(rec-tp)<.01: m.append('=PRICE'); nprice+=1
    if abs(rec-cap)<.01: m.append('=TGT_CAP'); ncap+=1
    if abs(rec-oc)<.01: m.append('=OUT_CAP')
    if abs(orec-rec)<.01: m.append('OUTREC=POL')
    p('%-16s %-24s %7.2f %9.2f %8.2f %8.2f %8.2f %8.2f %8.2f  %s'%(cid,topic,rec,tf,tp,cap,orec,oc,orf,'|'.join(m) or '-'))
p('\ncounts: policy==freight %d/10 topics, ==price %d, ==target_captured %d'%(nfree,nprice,ncap))
OUT.close(); print('ok')
