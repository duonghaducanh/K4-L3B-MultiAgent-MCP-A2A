import json
from datetime import datetime

OUT = open('tools/_aud_attr.txt','w',encoding='utf-8')
def p(*a): print(*a, file=OUT)
def parse(v): return datetime.fromisoformat(v) if v else None

def select_target(history, opened_at):
    opened = parse(opened_at)
    before = [o for o in history if (parse(o['order_purchase_timestamp']) or opened) <= opened]
    pool = before or history
    return max(pool, key=lambda o: parse(o['order_purchase_timestamp'])) if pool else None

def owner(ts, history):
    m = parse(ts)
    if m is None or not history: return None
    for o in history:
        d = parse(o['order_delivered_customer_date'])
        if d is not None and abs((m-d).total_seconds()) < 3600:
            return o
    return min(history, key=lambda o: abs((m-parse(o['order_purchase_timestamp'])).total_seconds()))

learn = json.load(open('tools/_learn1.json',encoding='utf-8'))
learn['L3B_CASE_001'] = json.load(open('tools/_case001.json',encoding='utf-8'))

for num in range(1,11):
    cid='L3B_CASE_%03d'%num
    case=json.load(open('inputs/%s.json'%cid,encoding='utf-8'))
    ev=learn[cid]
    hist=ev['get_customer_history']['data']['orders']
    tgt=select_target(hist, case['opened_at'])
    # identify target/decoy by index
    p('='*70)
    p('%s topic=%s opened=%s' % (cid, case['customer_request']['claims'][0]['topic'], case['opened_at'][:10]))
    for i,o in enumerate(hist):
        p('  H%d purch=%s deliv=%s status=%s %s' % (i, o['order_purchase_timestamp'][:10],
            (o['order_delivered_customer_date'] or 'None')[:10], o['order_status'],
            'TARGET' if o is tgt else 'decoy'))
    for label, key, rows in [
        ('ITEM', 'shipping_limit_date', ev['get_order_items'].get('data') or []),
        ('SHIPLIM', 'shipping_limit_at', (ev['get_shipment_summary'].get('data') or {}).get('shipping_limits') or []),
        ('SHEVENT', 'event_at', (ev['get_shipment_summary'].get('data') or {}).get('events') or []),
        ('PAYEVENT', 'event_at', (ev['get_payment_timeline'].get('data') or {}).get('events') or []),
    ]:
        for r in rows:
            ow=owner(r.get(key), hist)
            tag = 'TARGET' if ow is tgt else ('decoy' if ow else '?')
            extra=''
            if label=='ITEM': extra=' freight=%s price=%s' % (r.get('freight_value'), r.get('price'))
            if label in ('PAYEVENT',): extra=' %s amt=%s' % (r.get('event_type'), r.get('amount_brl'))
            if label in ('SHEVENT',): extra=' %s actor=%s' % (r.get('event_type'), r.get('actor'))
            p('  %-8s %s -> %s%s' % (label, (r.get(key) or 'None')[:19], tag, extra))
    rt=ev['get_refund_timeline']
    if rt.get('isError'):
        p('  REFUND   ERROR')
    else:
        for r in (rt.get('data') or {}).get('events') or []:
            ow=owner(r.get('event_at'), hist)
            tag='TARGET' if ow is tgt else 'decoy'
            p('  REFUND   %s -> %s %s amt=%s status=%s' % (r.get('event_at')[:19], tag, r.get('event_type'), r.get('amount_brl'), r.get('status')))
OUT.close()
print('done')
