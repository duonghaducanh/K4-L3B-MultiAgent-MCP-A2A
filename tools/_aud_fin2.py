import json, glob, os
from datetime import datetime
OUT=open('tools/_aud_fin2.txt','w',encoding='utf-8')
def p(*a): print(*a, file=OUT)
POL=json.load(open('tools/_policy.json',encoding='utf-8'))['data']['rules']
TOPICS=('late_delivery_logistics','valid_split_payment','payment_mismatch','duplicate_charge',
 'refund_pending','refund_failed','unsupported_claim','canceled_order_paid','unavailable_order_paid','late_delivery_seller')

def scan(dirpath,label):
    p('\n########## %s ##########'%label)
    files=sorted(glob.glob(dirpath+'/L3B_CASE_*.json'))
    p('files: %d'%len(files))
    issues=[]
    for f in files:
        o=json.load(open(f,encoding='utf-8')); cid=o['case_id']; n=int(cid[-3:]); topic=TOPICS[(n-1)%10]
        rec=o['financial_resolution']['recommended_refund_brl']; pol=float(POL[topic]['refund_brl'])
        pa=o['payment_analysis']; asm=o['assessment']
        if abs(float(rec)-pol)>.001: issues.append((cid,'REC!=POLICY',rec,pol))
        if asm['primary_issue']!=topic: issues.append((cid,'ISSUE!=TOPIC',asm['primary_issue'],topic))
        if asm['case_status']!=POL[topic]['case_status']: issues.append((cid,'STATUS!=POLICY',asm['case_status'],POL[topic]['case_status']))
        act=o['root_cause_analysis'].get('recommended_action') or (o.get('resolution_actions') or [{}])
        if len(o['data_conflicts'])==0: issues.append((cid,'NO_CONFLICT',0,'>=1 expected'))
        # refund lines sum
        rl=o['financial_resolution'].get('refund_lines') or []
        s=round(sum(float(l.get('amount_brl') or 0) for l in rl),2)
        if abs(s-float(rec))>.001: issues.append((cid,'LINES!=REC',s,rec))
        p('  %s %-24s rec=%-7s cap=%-8s refunded=%-8s refundable=%-8s verdict=%-18s ship=%-20s conf=%-5s nconf=%d nref=%d nlines=%d'%(
          cid,topic,rec,pa['captured_total_brl'],pa['refunded_total_brl'],pa['refundable_total_brl'],pa['verdict'],
          o['shipment_analysis']['verdict'],asm['confidence'],len(o['data_conflicts']),len(o['evidence_refs']),len(rl)))
    p('\n  ANOMALIES (%d):'%len(issues))
    for i in issues: p('    %s %s obs=%s exp=%s'%i)

scan('tools/_bak/outputs_4593','SCORED (4593)')
scan('outputs','CURRENT (regenerated)')
OUT.close(); print('ok')
