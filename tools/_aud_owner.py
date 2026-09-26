import json
from datetime import datetime
OUT=open('tools/_aud_owner.txt','w',encoding='utf-8')
def p(*a): print(*a, file=OUT)
def parse(v): return datetime.fromisoformat(v) if v else None

learn=json.load(open('tools/_learn1.json',encoding='utf-8'))
learn['L3B_CASE_001']=json.load(open('tools/_case001.json',encoding='utf-8'))

for num in (2,3,4,5,6,7,8,9,10):
    cid='L3B_CASE_%03d'%num
    ev=learn[cid]
    hist=ev['get_customer_history']['data']['orders']
    p('== %s'%cid)
    p('   history:')
    for i,o in enumerate(hist):
        p('     H%d purch=%s deliv=%s status=%-12s est=%s' % (
          i,o['order_purchase_timestamp'][:19],(o['order_delivered_customer_date'] or 'None')[:19],
          o['order_status'],(o.get('order_estimated_delivery_date') or 'None')[:19]))
    tl=(ev.get('get_payment_timeline') or {}).get('data') or {}
    p('   payment_timeline events:')
    for e in tl.get('events') or []:
        p('     %s %-24s amt=%-8s status=%-10s' % (e.get('event_at'),e.get('event_type'),e.get('amount_brl'),e.get('status')))
    p('   payment_timeline payments: %s'%json.dumps(tl.get('payments'),ensure_ascii=False))
    op=ev.get('get_order_payments') or {}
    p('   get_order_payments: %s'%json.dumps(op.get('data'),ensure_ascii=False))
    rt=ev.get('get_refund_timeline') or {}
    if rt.get('isError'): p('   refund: ERROR')
    else:
        for e in ((rt.get('data') or {}).get('events') or []):
            p('     REFUND %s %-20s amt=%-8s status=%s'%(e.get('event_at'),e.get('event_type'),e.get('amount_brl'),e.get('status')))
OUT.close(); print('ok')
