import json, glob, re
from collections import Counter, defaultdict

POL={'canceled_order_paid':79.0,'duplicate_charge':64.0,'late_delivery_logistics':16.0,
 'late_delivery_seller':18.0,'payment_mismatch':35.0,'refund_failed':52.0,'refund_pending':0.0,
 'unavailable_order_paid':89.0,'unsupported_claim':0.0,'valid_split_payment':0.0}
TOPICS=('late_delivery_logistics','valid_split_payment','payment_mismatch','duplicate_charge',
 'refund_pending','refund_failed','unsupported_claim','canceled_order_paid','unavailable_order_paid','late_delivery_seller')

OUT=open('tools/_aud_verify.txt','w',encoding='utf-8')
def p(*a): print(*a, file=OUT)

p('=== derived-vs-claimed disagreement (extra primary_issue conflict) & conf 0.72 ===')
for f in sorted(glob.glob('tools/_bak/outputs_4593/L3B_CASE_*.json')):
    o=json.load(open(f,encoding='utf-8')); cid=o['case_id']; n=int(cid[-3:]); t=TOPICS[(n-1)%10]
    extra=[c for c in o['data_conflicts'] if c['field']=='assessment.primary_issue']
    if extra:
        p(' %s topic=%-22s conf=%-5s ship=%-20s cap=%-7s rec=%-6s' % (
          cid,t,o['assessment']['confidence'],o['shipment_analysis']['verdict'],
          o['payment_analysis']['captured_total_brl'],o['financial_resolution']['recommended_refund_brl']))

p('\n=== rec == policy constant for all 100? ===')
bad=[]
for f in sorted(glob.glob('tools/_bak/outputs_4593/L3B_CASE_*.json')):
    o=json.load(open(f,encoding='utf-8')); n=int(o['case_id'][-3:]); t=TOPICS[(n-1)%10]
    if o['financial_resolution']['recommended_refund_brl']!=POL[t]:
        bad.append((o['case_id'],t,o['financial_resolution']['recommended_refund_brl'],POL[t]))
p(' mismatches:',bad if bad else 'NONE (all 100 match the policy constant)')

p('\n=== refund_lines vs rec ===')
for f in sorted(glob.glob('tools/_bak/outputs_4593/L3B_CASE_*.json')):
    o=json.load(open(f,encoding='utf-8')); fr=o['financial_resolution']
    tot=round(sum(l['amount_brl'] for l in fr['refund_lines']),2)
    if tot!=fr['recommended_refund_brl']:
        p(' MISMATCH %s rec=%s lines_total=%s'%(o['case_id'],fr['recommended_refund_brl'],tot))
p(' (no output above => refund_lines always sum to rec)')

p('\n=== refundable_total_brl vs rec, grouped ===')
g=defaultdict(Counter)
for f in sorted(glob.glob('tools/_bak/outputs_4593/L3B_CASE_*.json')):
    o=json.load(open(f,encoding='utf-8')); n=int(o['case_id'][-3:]); t=TOPICS[(n-1)%10]
    pa=o['payment_analysis']
    g[t][(pa['refundable_total_brl'],o['financial_resolution']['recommended_refund_brl'])]+=1
for t in TOPICS: p('  %-24s %s'%(t,dict(g[t])))

p('\n=== shipment_ids ===')
p(Counter(tuple(o['affected_entities']['shipment_ids']) for o in
          (json.load(open(f,encoding='utf-8')) for f in sorted(glob.glob('tools/_bak/outputs_4593/L3B_CASE_*.json')))).most_common(3)[:1])
same=sum(1 for f in sorted(glob.glob('tools/_bak/outputs_4593/L3B_CASE_*.json'))
         if json.load(open(f,encoding='utf-8'))['affected_entities']['shipment_ids']==[json.load(open(f,encoding='utf-8'))['affected_entities']['order_ids'][0]])
p('  outputs where shipment_ids == order_ids: %d/100'%same)

p('\n=== secondary_issues values ===')
p(Counter(tuple(o['assessment']['secondary_issues']) for o in
          (json.load(open(f,encoding='utf-8')) for f in sorted(glob.glob('tools/_bak/outputs_4593/L3B_CASE_*.json')))))

p('\n=== resolution_actions values ===')
p(Counter(tuple(o['resolution_actions']) for o in
          (json.load(open(f,encoding='utf-8')) for f in sorted(glob.glob('tools/_bak/outputs_4593/L3B_CASE_*.json')))))

p('\n=== rejected_candidates ===')
p(Counter(tuple(o['entity_resolution']['rejected_candidates']) for o in
          (json.load(open(f,encoding='utf-8')) for f in sorted(glob.glob('tools/_bak/outputs_4593/L3B_CASE_*.json')))))

p('\n=== related_order_ids length ===')
p(Counter(len(o['customer_context']['related_order_ids']) for o in
          (json.load(open(f,encoding='utf-8')) for f in sorted(glob.glob('tools/_bak/outputs_4593/L3B_CASE_*.json')))))
OUT.close(); print('ok')
