import json, glob
from collections import Counter, defaultdict
OUT=open('tools/_aud_cov2.txt','w',encoding='utf-8')
def p(*a): print(*a, file=OUT)
TOPICS=('late_delivery_logistics','valid_split_payment','payment_mismatch','duplicate_charge',
 'refund_pending','refund_failed','unsupported_claim','canceled_order_paid','unavailable_order_paid','late_delivery_seller')
def load(tp,od):
    ref2={}; per=defaultdict(set)
    for l in open(tp,encoding='utf-8'):
        l=l.strip()
        if not l: continue
        e=json.loads(l)
        if e.get('event_type')!='tool_result_consumed': continue
        per[e['case_id']].add((e.get('tool_name'),(e.get('attributes') or {}).get('domain')))
        for r in e.get('evidence_refs') or []: ref2[r]=(e['case_id'],e.get('tool_name'),(e.get('attributes') or {}).get('domain'))
    outs={}
    for f in sorted(glob.glob(od+'/L3B_CASE_*.json')):
        o=json.load(open(f,encoding='utf-8')); outs[o['case_id']]=o
    return ref2,per,outs
for lbl,tp,od in (('SCORED-4593','tools/_bak/trace_4593.jsonl','tools/_bak/outputs_4593'),
                  ('CURRENT-V2','traces/trace.jsonl','outputs')):
    ref2,per,outs=load(tp,od)
    p('\n########## %s'%lbl)
    # per-topic: which tools called & cited
    bytopic=defaultdict(Counter)
    for cid,o in outs.items():
        t=TOPICS[(int(cid[-3:])-1)%10]
        called=set(x[0] for x in per[cid])
        cited=set(ref2[r][1] for r in o['evidence_refs'] if r in ref2)
        bytopic[t][(tuple(sorted(called)),tuple(sorted(cited)))]+=1
    for t in TOPICS:
        for k,v in bytopic[t].items(): p('  %-24s x%-2d called=%s'%(t,v,k[0])); p('                          cited =%s'%(k[1],))
    # evidence refs of late_delivery_seller / unavailable cases in current run
    p('  -- current-run seller-topic outputs (seller-domain cited?) --')
    for cid,o in sorted(outs.items()):
        t=TOPICS[(int(cid[-3:])-1)%10]
        if t not in ('late_delivery_seller','unavailable_order_paid'): continue
        doms=sorted(set(ref2[r][2] for r in o['evidence_refs'] if r in ref2))
        p('     %s %-24s refs=%d doms=%s'%(cid,t,len(o['evidence_refs']),doms))
OUT.close(); print('ok')
