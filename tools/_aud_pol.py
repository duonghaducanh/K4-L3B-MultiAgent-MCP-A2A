import json, glob
OUT=open('tools/_aud_pol.txt','w',encoding='utf-8')
def p(*a): print(*a, file=OUT)

cases={}
c1=json.load(open('tools/_case001.json',encoding='utf-8'))
cases['L3B_CASE_001']=c1
for k,v in json.load(open('tools/_learn1.json',encoding='utf-8')).items():
    cases[k]=v

p('=== get_policy result_hash / refund_brl per case (cases 001-010) ===')
hashes={}
for cid in sorted(cases):
    gp=cases[cid].get('get_policy')
    if not gp: p(' %s NO get_policy'%cid); continue
    h=gp.get('result_hash'); ref=gp.get('evidence_ref')
    rules=(gp.get('data') or {}).get('rules') or {}
    rb={t:rules[t].get('refund_brl') for t in rules}
    hashes.setdefault(h,[]).append(cid)
    p(' %s hash=%s' % (cid,(h or '')[:40]))
    p('     refunds=%s'%json.dumps(rb,ensure_ascii=False))
p('\n=== distinct policy hashes ===')
for h,cs in hashes.items(): p('  %s -> %s'%(str(h)[:50],cs))

p('\n=== full policy payload from 001 (canonical) ===')
p(json.dumps(cases['L3B_CASE_001']['get_policy'],ensure_ascii=False,indent=1)[:2500])

p('\n=== compare 001 policy vs 005 policy (rules diff) ===')
a=(cases['L3B_CASE_001']['get_policy'].get('data') or {}).get('rules')
b=(cases['L3B_CASE_005']['get_policy'].get('data') or {}).get('rules')
p('identical rules object: %s' % (a==b))
OUT.close(); print('ok')
