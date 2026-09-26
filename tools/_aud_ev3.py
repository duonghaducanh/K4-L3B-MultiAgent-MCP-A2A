import json, glob, os
from collections import Counter, defaultdict

# ref -> (case, tool, domain) for BOTH traces
def load(path):
    m={}; per=defaultdict(dict)
    for line in open(path,encoding='utf-8'):
        line=line.strip()
        if not line: continue
        try: e=json.loads(line)
        except: continue
        if e.get('event_type')!='tool_result_consumed': continue
        cid=e['case_id']; t=e.get('tool_name'); d=(e.get('attributes') or {}).get('domain')
        per[cid][t]=d
        for r in (e.get('evidence_refs') or []): m[r]=(cid,t,d)
    return m,per

OUT=open('tools/_aud_ev3.txt','w',encoding='utf-8')
def p(*a): print(*a, file=OUT)

for label,tpath,odir in (('SCORED 4593','tools/_bak/trace_4593.jsonl','tools/_bak/outputs_4593'),
                         ('CURRENT','traces/trace.jsonl','outputs')):
    ref2,per=load(tpath)
    files=sorted(glob.glob(odir+'/L3B_CASE_*.json'))
    p('=== %s (%d outputs) ==='%(label,len(files)))
    nref=Counter(); doms=Counter(); uncited=Counter()
    for f in files:
        o=json.load(open(f,encoding='utf-8')); cid=o['case_id']
        refs=o['evidence_refs']; nref[len(refs)]+=1
        dset=set(ref2[r][2] for r in refs if r in ref2)
        doms[tuple(sorted(dset))]+=1
        called=set(per[cid].values())
        uncited[tuple(sorted(called-dset))]+=1
    p('  nref distribution: %s'%dict(sorted(nref.items())))
    p('  cited-domain sets: %s'%dict(doms))
    p('  uncited domains:   %s'%dict(uncited))
    p('  tools per case:    %s'%dict(Counter(tuple(sorted(v)) for v in per.values())))
    p('')

p('=== CURRENT case 001 output refs ===')
o=json.load(open('outputs/L3B_CASE_001.json',encoding='utf-8'))
ref2,_=load('traces/trace.jsonl')
for r in o['evidence_refs']:
    p('  %s -> %s'%(r, ref2.get(r)))
p('  shipment_ids=%s'%o['affected_entities']['shipment_ids'])
p('  refundable=%s rec=%s'%(o['payment_analysis']['refundable_total_brl'],o['financial_resolution']['recommended_refund_brl']))
OUT.close(); print('ok')
