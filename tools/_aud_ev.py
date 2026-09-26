import json, glob
from collections import Counter, defaultdict

# evidence_ref -> (tool, domain) from trace
ref2tool={}; ref2dom={}
case_calls=defaultdict(list)   # case -> [(tool, [refs])]
for line in open('traces/trace.jsonl',encoding='utf-8'):
    line=line.strip()
    if not line: continue
    try: e=json.loads(line)
    except: continue
    if e.get('event_type')!='tool_result_consumed': continue
    cid=e.get('case_id'); tool=e.get('tool_name')
    dom=(e.get('attributes') or {}).get('domain')
    case_calls[cid].append((tool,dom,e.get('evidence_refs') or []))
    for r in (e.get('evidence_refs') or []):
        ref2tool[r]=tool; ref2dom[r]=dom

OUT=open('tools/_aud_ev.txt','w',encoding='utf-8')
def p(*a): print(*a, file=OUT)

p('=== tools called per case (current trace, 57 cases) ===')
tc=Counter()
for cid,calls in case_calls.items():
    tc[tuple(sorted(t for t,_,_ in calls))]+=1
for k,v in tc.most_common(): p('  x%-3d %s'%(v,k))

p('\n=== distinct tools ===')
p(dict(Counter(t for c in case_calls.values() for t,_,_ in c)))

p('\n=== per-case evidence domains ===')
domcov=Counter()
for cid in sorted(case_calls):
    doms=[d for _,d,_ in case_calls[cid]]
    domcov[tuple(sorted(doms))]+=1
for k,v in domcov.most_common(): p('  x%-3d %s'%(v,k))

p('\n=== evidence_refs in output vs domains (all outputs) ===')
TOPICS=("late_delivery_logistics","valid_split_payment","payment_mismatch","duplicate_charge",
 "refund_pending","refund_failed","unsupported_claim","canceled_order_paid","unavailable_order_paid","late_delivery_seller")
ALLDOM={'order','item','payment','shipment','seller','policy','customer','product','refund'}
miss=Counter()
for f in sorted(glob.glob('tools/_bak/outputs_4593/L3B_CASE_*.json')):
    o=json.load(open(f,encoding='utf-8'))
    cid=o['case_id']
    refs=o['evidence_refs']
    doms=set(ref2dom.get(r,'?') for r in refs)
    unknown=[r for r in refs if r not in ref2dom]
    missing=sorted(ALLDOM-doms)
    miss[tuple(missing)]+=1
    p(' %s nref=%-2d doms=%s missing=%s unknown=%d' % (cid,len(refs),sorted(doms),missing,len(unknown)))
p('\n=== missing-domain signatures ===')
for k,v in miss.most_common(): p('  x%-3d %s'%(v,k))
OUT.close(); print('ok')
