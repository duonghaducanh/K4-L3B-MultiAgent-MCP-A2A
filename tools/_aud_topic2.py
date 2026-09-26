import json, glob
from collections import defaultdict
OUT=open('tools/_aud_topic2.txt','w',encoding='utf-8')
def p(*a): print(*a, file=OUT)
TOPICS=('late_delivery_logistics','valid_split_payment','payment_mismatch','duplicate_charge',
 'refund_pending','refund_failed','unsupported_claim','canceled_order_paid','unavailable_order_paid','late_delivery_seller')
outs={}
for f in sorted(glob.glob('tools/_bak/outputs_4593/L3B_CASE_*.json')):
    o=json.load(open(f,encoding='utf-8')); outs[o['case_id']]=o
g=defaultdict(list)
for cid,o in outs.items():
    n=int(cid[-3:]); g[TOPICS[(n-1)%10]].append((cid,o))
for t in TOPICS:
    p('=== %s (%d cases)'%(t,len(g[t])))
    recs=set(); caps=[]; refs=[]
    for cid,o in sorted(g[t]):
        rec=o['financial_resolution']['recommended_refund_brl']; cap=o['payment_analysis']['captured_total_brl']
        rf=o['payment_analysis']['refundable_total_brl']; v=o['payment_analysis']['verdict']
        st=o['assessment']['case_status']; conf=o['assessment']['confidence']; nc=len(o['data_conflicts'])
        recs.add(rec); caps.append(cap); refs.append(rf)
        p('  %s rec=%-7s cap=%-8s refundable=%-8s verdict=%-18s status=%-22s conf=%-5s nconf=%d'%(cid,rec,cap,rf,v,st,conf,nc))
    p('  --> distinct rec: %s | captured spread: %s | refundable spread: %s'%(sorted(recs),sorted(set(caps)),sorted(set(refs))))
OUT.close(); print('ok')
