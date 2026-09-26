import json, os
from datetime import datetime, timedelta
OUT=open('tools/_aud_decomp2.txt','w',encoding='utf-8')
def p(*a): print(*a, file=OUT)
def P(v): return datetime.fromisoformat(v) if v else None

learn=json.load(open('tools/_learn1.json',encoding='utf-8'))
learn['L3B_CASE_001']=json.load(open('tools/_case001.json',encoding='utf-8'))
POL=json.load(open('tools/_policy.json',encoding='utf-8'))['data']['rules']
TOPICS=('late_delivery_logistics','valid_split_payment','payment_mismatch','duplicate_charge',
 'refund_pending','refund_failed','unsupported_claim','canceled_order_paid','unavailable_order_paid','late_delivery_seller')

def hist_rows(ev): return ev['get_customer_history']['data']['orders']
def pick_target(hist,opened):
    c=[h for h in hist if P(h['order_purchase_timestamp'])<=opened]
    return max(c,key=lambda h:P(h['order_purchase_timestamp'])) if c else None
def row_index(h,hist): return hist.index(h)  # 0/1

p('%-15s %-23s %6s %6s | target(row) purch          | freight  price  captured | policy | out_rec out_cap'%('case','topic','pol','outrec'))
for num in range(1,11):
    cid='L3B_CASE_%03d'%num; topic=TOPICS[(num-1)%10]
    inp=json.load(open('inputs/%s.json'%cid,encoding='utf-8')); opened=P(inp['opened_at'])
    ev=learn[cid]; hist=hist_rows(ev)
    tgt=pick_target(hist,opened)
    ti=row_index(tgt,hist)
    # items: assign each row to the history row whose purch+3d == shipping_limit (nearest)
    rows=ev.get('get_order_items',{}).get('data') or []
    tf=tp=0.0; nitem=0
    for r in rows:
        sl=P(r.get('shipping_limit_date'))
        best=None;bd=None
        for i,h in enumerate(hist):
            d=abs((sl-(P(h['order_purchase_timestamp'])+timedelta(days=3))).total_seconds())
            if bd is None or d<bd: bd=d;best=i
        if best==ti:
            tf+=float(r.get('freight_value') or 0); tp+=float(r.get('price') or 0); nitem+=1
    # payments: match event_at to the same history row (delivery within 1h, else nearest purchase)
    tl=ev.get('get_payment_timeline',{}).get('data') or {}
    cap=0.0; ncap=0
    for e in tl.get('events') or []:
        if e.get('event_type')!='captured': continue
        t=P(e['event_at']); best=None;bd=None
        for i,h in enumerate(hist):
            d=P(h.get('order_delivered_customer_date'))
            dd=abs((t-d).total_seconds()) if d else None
            if dd is not None and dd<=3600: best=i;bd=0;break
            dd2=abs((t-P(h['order_purchase_timestamp'])).total_seconds())
            if bd is None or dd2<bd: bd=dd2;best=i
        if best==ti: cap+=float(e.get('amount_brl') or 0); ncap+=1
    out=json.load(open('tools/_bak/outputs_4593/%s.json'%cid,encoding='utf-8'))
    rec=float(POL[topic]['refund_brl']); orec=float(out['financial_resolution']['recommended_refund_brl'])
    oc=float(out['payment_analysis']['captured_total_brl'])
    p('%-15s %-23s %6.2f %6.2f | row%d %s | %6.2f %6.2f %8.2f | %6.2f | %6.2f %7.2f  items=%d caps=%d'%(
      cid,topic,rec,orec,ti,tgt['order_purchase_timestamp'][:19],tf,tp,cap,rec,orec,oc,nitem,ncap))
    p('      match: rec==freight %s | rec==price %s | rec==captured %s | rec==outcap %s'%(
      abs(rec-tf)<.01,abs(rec-tp)<.01,abs(rec-cap)<.01,abs(rec-oc)<.01))
OUT.close(); print('ok')
