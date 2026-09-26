import json, glob, os
from collections import Counter, defaultdict
OUT=open('tools/_aud_cmp2.txt','w',encoding='utf-8')
def p(*a): print(*a, file=OUT)

def load(dirpath):
    d={}
    for f in sorted(glob.glob(dirpath+'/L3B_CASE_*.json')):
        o=json.load(open(f,encoding='utf-8')); d[o['case_id']]=o
    return d
A=load('tools/_bak/outputs_4593'); B=load('outputs')
p('scored=%d current=%d'%(len(A),len(B)))
keys=sorted(set(A)&set(B))
p('\n=== per-field differences (scored -> current) ===')
fields=[('assessment.primary_issue',lambda o:o['assessment']['primary_issue']),
        ('assessment.case_status',lambda o:o['assessment']['case_status']),
        ('assessment.confidence',lambda o:o['assessment']['confidence']),
        ('payment.verdict',lambda o:o['payment_analysis']['verdict']),
        ('payment.captured',lambda o:o['payment_analysis']['captured_total_brl']),
        ('payment.refunded',lambda o:o['payment_analysis']['refunded_total_brl']),
        ('payment.refundable',lambda o:o['payment_analysis']['refundable_total_brl']),
        ('ship.verdict',lambda o:o['shipment_analysis']['verdict']),
        ('ship.late_seller_ids',lambda o:json.dumps(o['shipment_analysis']['late_seller_ids'])),
        ('ship.timeline_complete',lambda o:o['shipment_analysis']['timeline_complete']),
        ('fin.rec',lambda o:o['financial_resolution']['recommended_refund_brl']),
        ('fin.nlines',lambda o:len(o['financial_resolution']['refund_lines'])),
        ('fin.line_entity',lambda o:json.dumps([l.get('entity_id') for l in o['financial_resolution']['refund_lines']])),
        ('ent.order_ids',lambda o:len(o['affected_entities']['order_ids'])),
        ('ent.item_ids',lambda o:len(o['affected_entities']['item_ids'])),
        ('ent.seller_ids',lambda o:len(o['affected_entities']['seller_ids'])),
        ('ent.payment_refs',lambda o:json.dumps(o['affected_entities']['payment_references'])),
        ('ent.shipment_ids',lambda o:json.dumps(o['affected_entities']['shipment_ids'])),
        ('n_evidence_refs',lambda o:len(o['evidence_refs'])),
        ('n_conflicts',lambda o:len(o['data_conflicts'])),
        ('n_claims',lambda o:len(o['claim_assessments'])),
        ('claim_verdicts',lambda o:json.dumps([(c['claim_id'],c['verdict']) for c in o['claim_assessments']])),
        ('cause_codes',lambda o:json.dumps([c['cause_code'] for c in o['root_cause_analysis']['ranked_causes']])),
        ('parties',lambda o:json.dumps(o['root_cause_analysis']['responsible_parties'])),
        ('actions',lambda o:json.dumps(o['resolution_actions'])),
        ('secondary',lambda o:json.dumps(o['assessment']['secondary_issues'])),
        ('rejected',lambda o:json.dumps(o['entity_resolution']['rejected_candidates'])),
        ('related',lambda o:json.dumps(o['customer_context']['related_order_ids'])),
        ]
for name,fn in fields:
    diffs=[(c,fn(A[c]),fn(B[c])) for c in keys if fn(A[c])!=fn(B[c])]
    p('\n-- %s : %d diffs'%(name,len(diffs)))
    for c,a,b in diffs[:14]: p('     %s  scored=%s  current=%s'%(c,a,b))
    if len(diffs)>14: p('     ... %d more'%(len(diffs)-14))

p('\n=== current trace tool usage ===')
tp='traces/trace.jsonl'
if os.path.exists(tp):
    c=Counter(); per=defaultdict(list)
    for line in open(tp,encoding='utf-8'):
        line=line.strip()
        if not line: continue
        e=json.loads(line)
        if e.get('event_type')=='tool_result_consumed':
            c[e['case_id']]+=1; per[e['case_id']].append(e.get('tool_name'))
    p('cases=%d total=%d avg=%.2f dist=%s'%(len(c),sum(c.values()),sum(c.values())/max(1,len(c)),dict(sorted(Counter(c.values()).items()))))
    p('toolset counts: %s'%dict(Counter(tuple(sorted(v)) for v in per.values())))
else:
    p('no current trace')
OUT.close(); print('ok')
