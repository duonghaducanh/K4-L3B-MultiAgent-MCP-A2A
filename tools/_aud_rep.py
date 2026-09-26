import json, glob
OUT=open('tools/_aud_rep.txt','w',encoding='utf-8')
def p(*a): print(*a, file=OUT)
TOPICS=('late_delivery_logistics','valid_split_payment','payment_mismatch','duplicate_charge',
 'refund_pending','refund_failed','unsupported_claim','canceled_order_paid','unavailable_order_paid','late_delivery_seller')
POL=json.load(open('tools/_policy.json',encoding='utf-8'))['data']['rules']
outs={}
for f in sorted(glob.glob('outputs/L3B_CASE_*.json')):
    o=json.load(open(f,encoding='utf-8')); outs[o['case_id']]=o

p('=== 6 ANOMALY CASES (current outputs = submitted V2) ===')
for cid in ('L3B_CASE_012','L3B_CASE_062','L3B_CASE_071','L3B_CASE_098','L3B_CASE_039','L3B_CASE_089'):
    o=outs[cid]; n=int(cid[-3:]); claimed=TOPICS[(n-1)%10]
    pa=o['payment_analysis']; asm=o['assessment']
    p('\n%s  claimed/out issue=%s  conf=%s  status=%s'%(cid,asm['primary_issue'],asm['confidence'],asm['case_status']))
    p('   payment: verdict=%s cap=%s refunded=%s refundable=%s'%(pa['verdict'],pa['captured_total_brl'],pa['refunded_total_brl'],pa['refundable_total_brl']))
    p('   shipment: %s'%json.dumps(o['shipment_analysis'],ensure_ascii=False))
    p('   financial: rec=%s lines=%s'%(o['financial_resolution']['recommended_refund_brl'],json.dumps(o['financial_resolution']['refund_lines'],ensure_ascii=False)))
    p('   root_cause: %s'%json.dumps(o['root_cause_analysis'],ensure_ascii=False))
    p('   conflicts: %s'%json.dumps(o['data_conflicts'],ensure_ascii=False))
    p('   claims: %s'%json.dumps([(c['claim_id'],c['verdict'],c['confidence']) for c in o['claim_assessments']],ensure_ascii=False))
    p('   actions=%s entities=%s'%(o['resolution_actions'],json.dumps(o['affected_entities'],ensure_ascii=False)))
    p('   claimed-topic policy: rec=%s status=%s action=%s'%(POL[claimed]['refund_brl'],POL[claimed]['case_status'],POL[claimed]['recommended_action']))

p('\n\n=== claim-*-b verdict vs refund-vs-captured (all 100) ===')
from collections import defaultdict
g=defaultdict(list)
for cid,o in sorted(outs.items()):
    n=int(cid[-3:]); t=TOPICS[(n-1)%10]
    cap=o['payment_analysis']['captured_total_brl']; rec=o['financial_resolution']['recommended_refund_brl']
    b=[c for c in o['claim_assessments'] if c['claim_id'].endswith('-b')][0]
    g[(t,b['verdict'],b['confidence'],'rec<cap' if rec<cap else ('rec==cap' if abs(rec-cap)<.01 else ('rec>cap' if rec>cap else 'rec=cap=0')))].append(cid[-3:])
for k in sorted(g): p('  %-24s %-20s conf=%-5s %-9s n=%d %s'%(k[0],k[1],k[2],k[3],len(g[k]),g[k] if len(g[k])<=12 else g[k][:12]+['...']))

p('\n=== duplicate_charge cases (rec vs cap) ===')
for cid,o in sorted(outs.items()):
    if TOPICS[(int(cid[-3:])-1)%10]!='duplicate_charge': continue
    b=[c for c in o['claim_assessments'] if c['claim_id'].endswith('-b')][0]
    p('  %s cap=%s rec=%s refundable=%s claim_b=%s/%s'%(cid,o['payment_analysis']['captured_total_brl'],o['financial_resolution']['recommended_refund_brl'],o['payment_analysis']['refundable_total_brl'],b['verdict'],b['confidence']))
OUT.close(); print('ok')
