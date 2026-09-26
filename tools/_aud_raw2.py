import json
OUT=open('tools/_aud_raw2.txt','w',encoding='utf-8')
def p(*a): print(*a, file=OUT)
learn=json.load(open('tools/_learn1.json',encoding='utf-8'))
learn['L3B_CASE_001']=json.load(open('tools/_case001.json',encoding='utf-8'))
for num in (1,2,9):
    cid='L3B_CASE_%03d'%num
    ev=learn[cid]
    p('=== %s get_customer_history ==='%cid)
    p(json.dumps(ev['get_customer_history'],ensure_ascii=False,indent=1))
    p('=== %s get_payment_timeline ==='%cid)
    p(json.dumps(ev.get('get_payment_timeline'),ensure_ascii=False,indent=1))
    p('=== %s get_order ==='%cid)
    p(json.dumps(ev.get('get_order'),ensure_ascii=False,indent=1)[:1500])
OUT.close(); print('ok')
