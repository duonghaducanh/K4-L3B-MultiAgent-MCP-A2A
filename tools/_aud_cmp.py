import json, glob
from datetime import datetime

OUT = open('tools/_aud_cmp.txt','w',encoding='utf-8')
def p(*a): print(*a, file=OUT)

def parse(v):
    return datetime.fromisoformat(v) if v else None

def select_target(history, opened_at):
    opened = parse(opened_at)
    before = [o for o in history if (parse(o['order_purchase_timestamp']) or opened) <= opened]
    pool = before or history
    if not pool: return None
    return max(pool, key=lambda o: parse(o['order_purchase_timestamp']))

def owner(ts, history):
    m = parse(ts)
    if m is None or not history: return None
    for o in history:
        d = parse(o['order_delivered_customer_date'])
        if d is not None and abs((m-d).total_seconds()) < 3600:
            return o
    return min(history, key=lambda o: abs((m-parse(o['order_purchase_timestamp'])).total_seconds()))

def rows_for(rows, key, history, target):
    return [r for r in rows if owner(r.get(key), history) is target]

def money(v):
    try: return round(float(v),2)
    except: return 0.0

learn = json.load(open('tools/_learn1.json',encoding='utf-8'))
learn['L3B_CASE_001'] = json.load(open('tools/_case001.json',encoding='utf-8'))
policy = json.load(open('tools/_policy.json',encoding='utf-8'))['data']['rules']

for num in range(1,11):
    cid = 'L3B_CASE_%03d' % num
    case = json.load(open('inputs/%s.json'%cid,encoding='utf-8'))
    ev = learn[cid]
    out = json.load(open('outputs/%s.json'%cid,encoding='utf-8'))
    hist = ev['get_customer_history']['data']['orders']
    opened = case['opened_at']
    tgt = select_target(hist, opened)
    decoy = [o for o in hist if o is not tgt][0] if len(hist)>1 else None
    topic = case['customer_request']['claims'][0]['topic']
    rule = policy.get(topic, {})
    p('='*70)
    p('%s topic=%s opened=%s' % (cid, topic, opened[:10]))
    p('  target purch=%s status=%s deliv=%s est=%s' % (
        tgt['order_purchase_timestamp'][:10], tgt['order_status'],
        (tgt['order_delivered_customer_date'] or 'None')[:10], tgt['order_estimated_delivery_date'][:10]))
    if decoy:
        p('  decoy  purch=%s status=%s' % (decoy['order_purchase_timestamp'][:10], decoy['order_status']))
    # items
    items = rows_for(ev['get_order_items']['data'] or [], 'shipping_limit_date', hist, tgt)
    allitems = ev['get_order_items']['data'] or []
    tgt_freight = round(sum(money(i.get('freight_value')) for i in items),2)
    tgt_price = round(sum(money(i.get('price')) for i in items),2)
    p('  items total rows=%d, target rows=%d: freight=%s price=%s order_total=%s' % (
        len(allitems), len(items), tgt_freight, tgt_price, round(tgt_freight+tgt_price,2)))
    # payments
    pte = ev['get_payment_timeline']['data']
    all_events = pte.get('events') or []
    tgt_events = rows_for(all_events, 'event_at', hist, tgt)
    all_caps = [e for e in all_events if e.get('event_type')=='captured']
    tgt_caps = [e for e in tgt_events if e.get('event_type')=='captured']
    solver_caps = [e for e in all_events if e.get('event_type')=='captured']  # solver uses rows_for
    p('  captured events ALL: %s' % [(e['event_at'][:10], e['amount_brl']) for e in all_caps])
    p('  captured events TARGET(manual): %s sum=%s' % (
        [(e['event_at'][:10], e['amount_brl']) for e in tgt_caps],
        round(sum(money(e['amount_brl']) for e in tgt_caps),2)))
    p('  other payment events TARGET: %s' % [(e['event_at'][:10], e['event_type'], e.get('amount_brl'), e.get('status')) for e in tgt_events if e.get('event_type')!='captured'])
    # refund
    rt = ev['get_refund_timeline']
    if rt.get('isError'):
        p('  refund: ERROR')
        tgt_refunds = []
    else:
        allr = (rt.get('data') or {}).get('events') or []
        tgt_refunds = rows_for(allr, 'event_at', hist, tgt)
        p('  refund events ALL: %s' % [(e['event_at'][:10], e['event_type'], e.get('amount_brl'), e.get('status')) for e in allr])
        p('  refund events TARGET: %s' % [(e['event_at'][:10], e['event_type'], e.get('amount_brl'), e.get('status')) for e in tgt_refunds])
    # shipment events
    shev = (ev['get_shipment_summary'].get('data') or {}).get('events') or []
    tgt_shev = rows_for(shev, 'event_at', hist, tgt)
    p('  shipment events ALL: %s' % [(e['event_at'][:10], e['event_type'], e.get('actor')) for e in shev])
    p('  shipment events TARGET: %s' % [(e['event_at'][:10], e['event_type'], e.get('actor')) for e in tgt_shev])
    # output
    pa = out['payment_analysis']
    p('  POLICY: status=%s action=%s refund_brl=%s parties=%s' % (
        rule.get('case_status'), rule.get('recommended_action'), rule.get('refund_brl'),
        [(x['party_type'], x['party_id']) for x in rule.get('responsible_parties',[])]))
    p('  OUT: verdict=%s captured=%s refunded=%s refundable=%s rec_refund=%s' % (
        pa['verdict'], pa['captured_total_brl'], pa['refunded_total_brl'], pa['refundable_total_brl'],
        out['financial_resolution']['recommended_refund_brl']))
    p('  OUT shipment: %s late_seller=%s' % (out['shipment_analysis']['verdict'], out['shipment_analysis']['late_seller_ids']))
    p('  OUT entities: items=%s sellers=%s payrefs=%s ship=%s' % (
        out['affected_entities']['item_ids'], out['affected_entities']['seller_ids'],
        out['affected_entities']['payment_references'], out['affected_entities']['shipment_ids']))
    p('  OUT related_orders=%s' % out['customer_context']['related_order_ids'])
    p('  OUT refund_lines=%s' % out['financial_resolution']['refund_lines'])
    p('  OUT conflicts=%s' % [(c['field'], c['selected_source']) for c in out['data_conflicts']])
OUT.close()
print('done')
