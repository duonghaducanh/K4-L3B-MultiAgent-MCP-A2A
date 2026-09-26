import json, glob, re
OUT=open('tools/_aud_last.txt','w',encoding='utf-8')
def p(*a): print(*a, file=OUT)
# 1) any shipment id anywhere in captured evidence?
blob=open('tools/_learn1.json',encoding='utf-8').read()+open('tools/_case001.json',encoding='utf-8').read()+open('tools/_o_probe3.txt',encoding='utf-8').read()
p('occurrences of "shipment_id" in captured evidence: %d'%len(re.findall(r'shipment_id',blob)))
p('keys seen in shipment data: %s'%sorted(set(re.findall(r'"([a-z_]+)":',blob))))
# 2) payments owner filtering in workflow
src=open('src/student_agent/workflow.py',encoding='utf-8').read()
i=src.find('self.payments')
p('\nworkflow lines mentioning self.payments:')
for n,l in enumerate(src.splitlines(),1):
    if 'self.payments' in l: p('  %d: %s'%(n,l.strip()))
p('\n_payment_agent excerpt:')
a=src.find('async def payment_agent')
p(src[a:a+1500])
OUT.close(); print('ok')
