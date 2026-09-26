import json
OUT=open('tools/_aud_tgt.txt','w',encoding='utf-8')
def p(*a): print(*a, file=OUT)
learn=json.load(open('tools/_learn1.json',encoding='utf-8'))
learn['L3B_CASE_001']=json.load(open('tools/_case001.json',encoding='utf-8'))
for num in range(1,11):
    cid='L3B_CASE_%03d'%num
    inp=json.load(open('inputs/%s.json'%cid,encoding='utf-8'))
    ev=learn[cid]; hist=ev['get_customer_history']['data']['orders']
    go=(ev.get('get_order') or {}).get('data') or {}
    p('== %s opened_at=%s claimed=%s'%(cid,inp['opened_at'],inp['customer_request']['claimed_order_id']))
    p('   history purchases: %s'%[h['order_purchase_timestamp'] for h in hist])
    p('   history statuses : %s'%[h['order_status'] for h in hist])
    p('   history deliv    : %s'%[h['order_delivered_customer_date'] for h in hist])
    p('   get_order status=%s purch=%s deliv=%s'%(go.get('order_status'),go.get('order_purchase_timestamp'),go.get('order_delivered_customer_date')))
    p('   get_order == hist[0]? %s ; == hist[1]? %s'%(go==hist[0] if hist else None, go==hist[1] if len(hist)>1 else None))
OUT.close(); print('ok')
