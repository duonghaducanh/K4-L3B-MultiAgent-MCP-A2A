import json, glob
from collections import Counter
OUT=open('tools/_aud_ent.txt','w',encoding='utf-8')
def p(*a): print(*a, file=OUT)

outs=[json.load(open(f,encoding='utf-8')) for f in sorted(glob.glob('tools/_bak/outputs_4593/L3B_CASE_*.json'))]
p('=== item_ids shape ===')
p(Counter(len(o['affected_entities']['item_ids']) for o in outs))
p(' samples:',[o['affected_entities']['item_ids'] for o in outs[:3]])
p('\n=== payment_references values ===')
p(Counter(tuple(o['affected_entities']['payment_references']) for o in outs).most_common(8))
p('\n=== order_ids always == claimed ===')
bad=[o['case_id'] for o in outs if len(o['affected_entities']['order_ids'])!=1]
p(' non-singleton order_ids:',bad or 'none')
p('\n=== seller_ids ===')
p(Counter(len(o['affected_entities']['seller_ids']) for o in outs))
p('\n=== root_cause ranked_causes length ===')
p(Counter(len(o['root_cause_analysis']['ranked_causes']) for o in outs))
p('\n=== responsible_parties by topic ===')
from collections import defaultdict
TOPICS=('late_delivery_logistics','valid_split_payment','payment_mismatch','duplicate_charge',
 'refund_pending','refund_failed','unsupported_claim','canceled_order_paid','unavailable_order_paid','late_delivery_seller')
g=defaultdict(Counter)
for o in outs:
    n=int(o['case_id'][-3:]); t=TOPICS[(n-1)%10]
    g[t][json.dumps(o['root_cause_analysis']['responsible_parties'],ensure_ascii=False)]+=1
for t in TOPICS:
    for k,v in g[t].items(): p('  %-24s x%d %s'%(t,v,k))
p('\n=== claim_assessments count ===')
p(Counter(len(o['claim_assessments']) for o in outs))
p('\n=== claim ids ===')
p(Counter(tuple(c['claim_id'] for c in o['claim_assessments']) for o in outs).most_common(4))
OUT.close(); print('ok')
