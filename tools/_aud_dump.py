import json

OUT = open('tools/_aud_dump.txt','w',encoding='utf-8')

def p(*a):
    print(*a, file=OUT)

learn = json.load(open('tools/_learn1.json'))
learn['L3B_CASE_001'] = json.load(open('tools/_case001.json'))

for case in sorted(learn):
    v = learn[case]
    p('#'*60)
    p(case, 'claimed=', v.get('claimed'), 'cands=', v.get('candidates'))
    hist = v['get_customer_history']['data']['orders']
    p(' HISTORY:')
    for o in hist:
        p('  ', o['order_id'][:16], o['order_status'], 'P', o['order_purchase_timestamp'][:10],
          'D', (o['order_delivered_customer_date'] or 'None')[:10],
          'E', o['order_estimated_delivery_date'][:10])
    go = v['get_order'].get('data') or {}
    p(' GET_ORDER: status=%s P=%s D=%s E=%s' % (go.get('order_status'),
        (go.get('order_purchase_timestamp') or '')[:10],
        (go.get('order_delivered_customer_date') or 'None')[:10],
        (go.get('order_estimated_delivery_date') or '')[:10]))
    p(' ITEMS:')
    for it in (v['get_order_items'].get('data') or []):
        p('   item=%s seller=%s ship_limit=%s price=%s freight=%s' % (
            it.get('order_item_id'), it.get('seller_id'), (it.get('shipping_limit_date') or '')[:10],
            it.get('price'), it.get('freight_value')))
    sh = v['get_shipment_summary'].get('data') or {}
    p(' SHIP: status=%s dcarr=%s dcust=%s est=%s' % (sh.get('order_status'),
        (sh.get('delivered_carrier_at') or '')[:10], (sh.get('delivered_customer_at') or '')[:10],
        (sh.get('estimated_delivery_at') or '')[:10]))
    for lim in (sh.get('shipping_limits') or []):
        p('   lim item=%s seller=%s at=%s' % (lim.get('order_item_id'), lim.get('seller_id'), (lim.get('shipping_limit_at') or '')[:10]))
    for ev in (sh.get('events') or []):
        p('   ev at=%s type=%s actor=%s status=%s' % ((ev.get('event_at') or '')[:10], ev.get('event_type'), ev.get('actor'), ev.get('status')))
    pt = v['get_payment_timeline'].get('data') or {}
    p(' PAY_TIMELINE events:')
    for ev in (pt.get('events') or []):
        p('   ev at=%s type=%s amt=%s status=%s' % ((ev.get('event_at') or '')[:10], ev.get('event_type'), ev.get('amount_brl'), ev.get('status')))
    p(' PAY_TIMELINE payments:')
    for pm in (pt.get('payments') or []):
        p('   pm seq=%s type=%s val=%s' % (pm.get('payment_sequential'), pm.get('payment_type'), pm.get('payment_value')))
    rt = v['get_refund_timeline']
    if rt.get('isError'):
        p(' REFUND: ERROR')
    else:
        for ev in ((rt.get('data') or {}).get('events') or []):
            p('   ref at=%s type=%s amt=%s status=%s' % ((ev.get('event_at') or '')[:10], ev.get('event_type'), ev.get('amount_brl'), ev.get('status')))
    p(' PAYMENTS(get_order_payments):')
    for pm in (v['get_order_payments'].get('data') or []):
        p('   pm seq=%s type=%s val=%s' % (pm.get('payment_sequential'), pm.get('payment_type'), pm.get('payment_value')))
OUT.close()
print('done')
