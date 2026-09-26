import json, glob, os
OUT=open('tools/_aud_diff.txt','w',encoding='utf-8')
def p(*a): print(*a, file=OUT)

def flat(o, pre=''):
    r={}
    if isinstance(o,dict):
        for k,v in o.items(): r.update(flat(v,pre+'.'+k))
    elif isinstance(o,list):
        for i,v in enumerate(o): r.update(flat(v,pre+'[%d]'%i))
    else: r[pre]=o
    return r

# scope across all inputs
p('=== investigation_scope across all 100 inputs ===')
from collections import Counter
sc=Counter()
for f in sorted(glob.glob('inputs/L3B_CASE_*.json')):
    c=json.load(open(f,encoding='utf-8'))
    s=c.get('investigation_scope') or {}
    sc[(s.get('include_customer_history'),s.get('include_product_context'),s.get('require_independent_verification'))]+=1
for k,v in sc.items(): p('  x%-3d %s'%(v,k))

# full diff of overlapping cases
p('\n=== full field diff: 4593 (scored) vs current ===')
overlap=0; fields=Counter()
for f in sorted(glob.glob('tools/_bak/outputs_4593/L3B_CASE_*.json')):
    b=os.path.basename(f); nf='outputs/'+b
    if not os.path.exists(nf): continue
    overlap+=1
    a=flat(json.load(open(f,encoding='utf-8')))
    c=flat(json.load(open(nf,encoding='utf-8')))
    keys=set(a)|set(c)
    for k in sorted(keys):
        if a.get(k,'<MISSING>')!=c.get(k,'<MISSING>'):
            # normalise evidence-ref paths to a counter key
            kk=k.split('[')[0] if '.evidence_refs' in k else k
            fields[kk]+=1
p('overlapping cases:',overlap)
for k,v in fields.most_common(40): p('  %-60s x%d'%(k,v))

# show one concrete evidence_refs diff
a=json.load(open('tools/_bak/outputs_4593/L3B_CASE_001.json',encoding='utf-8'))
c=json.load(open('outputs/L3B_CASE_001.json',encoding='utf-8'))
p('\n=== 001 evidence_refs 4593 vs now ===')
p('4593: '+json.dumps(a['evidence_refs'],ensure_ascii=False))
p('now : '+json.dumps(c['evidence_refs'],ensure_ascii=False))
p('4593 claim refs: '+json.dumps([x['evidence_refs'] for x in a['claim_assessments']],ensure_ascii=False))
p('now  claim refs: '+json.dumps([x['evidence_refs'] for x in c['claim_assessments']],ensure_ascii=False))
OUT.close(); print('ok')
