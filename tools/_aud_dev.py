import json, glob, os
from collections import Counter, defaultdict

OUT = open('tools/_aud_dev.txt','w',encoding='utf-8')
def p(*a): print(*a, file=OUT)

TOPICS = ("late_delivery_logistics","valid_split_payment","payment_mismatch","duplicate_charge",
 "refund_pending","refund_failed","unsupported_claim","canceled_order_paid","unavailable_order_paid","late_delivery_seller")

# archetype baselines observed in cases 001-010 (raw evidence)
BASE_CAP = {"late_delivery_logistics":16.0,"valid_split_payment":89.0,"payment_mismatch":35.0,
 "duplicate_charge":128.0,"refund_pending":89.0,"refund_failed":52.0,"unsupported_claim":89.0,
 "canceled_order_paid":79.0,"unavailable_order_paid":89.0,"late_delivery_seller":18.0}
BASE_VERDICT = {"late_delivery_logistics":"reconciled","valid_split_payment":"reconciled",
 "payment_mismatch":"capture_mismatch","duplicate_charge":"duplicate_capture",
 "refund_pending":"refund_pending","refund_failed":"refund_failed","unsupported_claim":"reconciled",
 "canceled_order_paid":"reconciled","unavailable_order_paid":"reconciled","late_delivery_seller":"reconciled"}
BASE_SHIP = {"late_delivery_logistics":"logistics_delay","late_delivery_seller":"seller_delay",
 "valid_split_payment":"on_time","payment_mismatch":"on_time","duplicate_charge":"on_time",
 "refund_pending":"on_time","refund_failed":"on_time","unsupported_claim":"on_time",
 "canceled_order_paid":"insufficient_evidence","unavailable_order_paid":"insufficient_evidence"}

files=sorted(glob.glob('tools/_bak/outputs_4593/L3B_CASE_*.json'))
rows=[]
for f in files:
    o=json.load(open(f,encoding='utf-8'))
    cid=o['case_id']; n=int(cid[-3:])
    topic=TOPICS[(n-1)%10]
    rows.append((cid,topic,o))

p('total outputs: %d' % len(rows))

p('\n=== A. captured_total deviations from archetype baseline ===')
for cid,t,o in rows:
    cap=o['payment_analysis']['captured_total_brl']
    if cap != BASE_CAP[t]:
        p('  %s %-24s cap=%s baseline=%s  refundable=%s rec=%s verdict=%s' % (
          cid,t,cap,BASE_CAP[t],o['payment_analysis']['refundable_total_brl'],
          o['financial_resolution']['recommended_refund_brl'],o['payment_analysis']['verdict']))

p('\n=== B. no_action topics with refundable_total_brl > 0 ===')
for cid,t,o in rows:
    if o['assessment']['case_status']=='no_action' and o['payment_analysis']['refundable_total_brl']:
        p('  %s %-24s refundable=%s rec=%s verdict=%s cap=%s' % (
          cid,t,o['payment_analysis']['refundable_total_brl'],
          o['financial_resolution']['recommended_refund_brl'],
          o['payment_analysis']['verdict'],o['payment_analysis']['captured_total_brl']))

p('\n=== C. verdict != archetype baseline ===')
for cid,t,o in rows:
    if o['payment_analysis']['verdict']!=BASE_VERDICT[t]:
        p('  %s %-24s verdict=%s baseline=%s' % (cid,t,o['payment_analysis']['verdict'],BASE_VERDICT[t]))

p('\n=== D. shipment verdict != baseline ===')
for cid,t,o in rows:
    if o['shipment_analysis']['verdict']!=BASE_SHIP[t]:
        p('  %s %-24s ship=%s baseline=%s' % (cid,t,o['shipment_analysis']['verdict'],BASE_SHIP[t]))

p('\n=== E. data_conflicts count ===')
for cid,t,o in rows:
    if not o['data_conflicts']:
        p('  %s %-24s ZERO conflicts, cap=%s' % (cid,t,o['payment_analysis']['captured_total_brl']))
    else:
        for c in o['data_conflicts']:
            if c['field']!='order_timeline.order_status':
                p('  %s extra conflict: %s' % (cid,c))

p('\n=== F. shipment_ids ===')
p(Counter(tuple(o['affected_entities']['shipment_ids']) for _,_,o in rows))

p('\n=== G. payment_references length ===')
p(Counter(len(o['affected_entities']['payment_references']) for _,_,o in rows))

p('\n=== H. confidence values by topic ===')
c=defaultdict(Counter)
for cid,t,o in rows: c[t][o['assessment']['confidence']]+=1
for t in TOPICS: p('  %-24s %s' % (t,dict(c[t])))

p('\n=== I. claim verdicts by topic ===')
c=defaultdict(Counter)
for cid,t,o in rows:
    c[t][tuple((x['verdict'],x['confidence']) for x in o['claim_assessments'])]+=1
for t in TOPICS:
    for k,v in c[t].items(): p('  %-24s %s x%d' % (t,k,v))

p('\n=== J. cause codes ===')
p(Counter(o['root_cause_analysis']['ranked_causes'][0]['cause_code'] for _,_,o in rows))
OUT.close()
print('done')
