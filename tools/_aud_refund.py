import json
from datetime import datetime

OUT=open('tools/_aud_refund.txt','w',encoding='utf-8')
def p(*a): print(*a, file=OUT)
def parse(v): return datetime.fromisoformat(v) if v else None
def money(x): return round(float(x),2)

def select_target(history, opened_at):
    opened=parse(opened_at)
    before=[o for o in history if (parse(o['order_purchase_timestamp']) or opened)<=opened]
    pool=before or history
    return max(pool,key=lambda o: parse(o['order_purchase_timestamp']))

def owner(ts, history):
    m=parse(ts)
    if m is None: return None
    for o in history:
        d=parse(o['order_delivered_customer_date'])
        if d is not None and abs((m-d).total_seconds())<3600: return o
    return min(history,key=lambda o: abs((m-parse(o['order_purchase_timestamp'])).total_seconds()))

POL=json.load(open("tools/_policy.json",encoding="utf-8"))["data"]["rules"]
learn=json.load(open('tools/_learn1.json',encoding='utf-8'))
learn['L3B_CASE_001']=json.load(open('tools/_case001.json',encoding='utf-8'))
TOPICS=("late_delivery_logistics","valid_split_payment","payment_mismatch","duplicate_charge",
 "refund_pending","refund_failed","unsupported_claim","canceled_order_paid","unavailable_order_paid","late_delivery_seller")

p('=== REFUND-AMOUNT DECOMPOSITION (raw MCP payloads, cases 001-010) ===')
p('%-15s %-24s %8s %8s %8s %8s %8s %8s %8s %8s' % (
  'case','topic','policy','tgt_frt','tgt_price','tgt_ordtot','tgt_capt','tgt_refnd','tgt_refbl','out_rec'))
for num in range(1,11):
    cid='L3B_CASE_%03d'%num
    case=json.load(open('inputs/%s.json'%cid,encoding='utf-8'))
    t=case['customer_request']['claims'][0]['topic']
    ev=learn[cid]
    hist=ev['get_customer_history']['data']['orders']
    tgt=select_target(hist, case['opened_at'])
    tid=tgt['order_id']
    # items for target
    items=[r for r in (ev['get_order_items'].get('data') or []) if owner(r.get('shipping_limit_date'),hist) is tgt]
    frt=sum(float(r['freight_value']) for r in items)
    prc=sum(float(r['price']) for r in items)
    # order row from get_order (may be decoy!) and history
    gotot=tgt.get('order_total_brl') or tgt.get('total_brl') or tgt.get('payment_total_brl')
    # payments for target via timeline
    payev=[r for r in ((ev.get('get_payment_timeline') or {}).get('data') or {}).get('events',[]) if owner(r.get('event_at'),hist) is tgt]
    capt=sum(float(r.get('amount_brl') or 0) for r in payev if r.get('event_type') in ('capture','payment_captured','captured'))
    if capt==0:
        capt=sum(float(r.get('amount_brl') or 0) for r in payev if 'captur' in (r.get('event_type') or ''))
    # refunds
    rt=ev.get('get_refund_timeline') or {}
    refev=[r for r in ((rt.get('data') or {}) if not rt.get('isError') else {}).get('events',[]) if owner(r.get('event_at'),hist) is tgt]
    refnd=sum(float(r.get('amount_brl') or 0) for r in refev if (r.get('status') or '') in ('succeeded','completed','refunded'))
    # output
    out=json.load(open('outputs/%s.json'%cid,encoding='utf-8'))
    orec=out['financial_resolution']['recommended_refund_brl']
    p('%-15s %-24s %8s %8s %8s %8s %8s %8s %8s %8s' % (
      cid,t,POL[t]['refund_brl'],money(frt),money(prc),gotot if gotot is not None else '-',
      money(capt),money(refnd),'?',orec))
    p('    payment events (target): '+json.dumps([(r.get('event_type'),r.get('amount_brl'),r.get('status')) for r in payev],ensure_ascii=False))
    p('    refund events (target): '+json.dumps([(r.get('event_type'),r.get('amount_brl'),r.get('status')) for r in refev],ensure_ascii=False))
    p('    policy row: '+json.dumps(POL[t],ensure_ascii=False))
OUT.close()
print('done')
