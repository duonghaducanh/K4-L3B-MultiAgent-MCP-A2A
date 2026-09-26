import json, glob, os
from collections import Counter, defaultdict

# map evidence_ref -> (case, tool, domain) from the SCORED trace
ref2=  {}
case_tools=defaultdict(dict)
for line in open('tools/_bak/trace_4593.jsonl',encoding='utf-8'):
    line=line.strip()
    if not line: continue
    try: e=json.loads(line)
    except: continue
    if e.get('event_type')!='tool_result_consumed': continue
    cid=e['case_id']; tool=e.get('tool_name'); dom=(e.get('attributes') or {}).get('domain')
    for r in (e.get('evidence_refs') or []):
        ref2[r]=(cid,tool,dom)
    case_tools[cid][tool]=dom

OUT=open('tools/_aud_ev2.txt','w',encoding='utf-8')
def p(*a): print(*a, file=OUT)

p('=== SCORED RUN (4593): evidence_refs coverage per output ===')
miss=Counter(); unknown=Counter(); nref=Counter()
for f in sorted(glob.glob('tools/_bak/outputs_4593/L3B_CASE_*.json')):
    o=json.load(open(f,encoding='utf-8')); cid=o['case_id']
    refs=o['evidence_refs']
    doms=set()
    unk=0
    for r in refs:
        if r in ref2:
            if ref2[r][0]!=cid: p(' !! CROSS-CASE ref %s in %s belongs to %s'%(r,cid,ref2[r][0]))
            doms.add(ref2[r][2])
        else:
            unk+=1
    called=set(case_tools[cid].values())
    uncited=sorted(called-doms)
    miss[tuple(uncited)]+=1
    nref[len(refs)]+=1
    unknown[unk]+=1
    if uncited or unk:
        p(' %s nref=%-2d called=%s cited=%s UNCITED=%s unknown=%d' % (
          cid,len(refs),sorted(called),sorted(doms),uncited,unk))
p('\nnref distribution:',dict(nref))
p('unknown-ref counts:',dict(unknown))
p('\n=== UNCITED-DOMAIN signatures across all 100 ===')
for k,v in miss.most_common(): p('  x%-3d %s'%(v,k))

p('\n=== is the product ref present anywhere in any output? ===')
prodcited=0
for f in sorted(glob.glob('tools/_bak/outputs_4593/L3B_CASE_*.json')):
    o=json.load(open(f,encoding='utf-8'))
    for r in o['evidence_refs']:
        if r in ref2 and ref2[r][2]=='product': prodcited+=1
p('product refs cited:',prodcited,'of 100 product calls')

p('\n=== refund-domain citation ===')
refcited=0; refund_cases=0
for f in sorted(glob.glob('tools/_bak/outputs_4593/L3B_CASE_*.json')):
    o=json.load(open(f,encoding='utf-8')); cid=o['case_id']
    if 'get_refund_timeline' in case_tools[cid]:
        refund_cases+=1
        if any(r in ref2 and ref2[r][2]=='refund' for r in o['evidence_refs']): refcited+=1
p('cases that called get_refund_timeline:',refund_cases,'| of those citing a refund ref:',refcited)
OUT.close(); print('ok')
