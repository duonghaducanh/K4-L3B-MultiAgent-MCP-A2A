import json, glob
from collections import Counter

OUT = open('tools/_aud_tab.txt','w',encoding='utf-8')
def p(*a): print(*a, file=OUT)

POL = {'canceled_order_paid':79.0,'duplicate_charge':64.0,'late_delivery_logistics':16.0,
 'late_delivery_seller':18.0,'payment_mismatch':35.0,'refund_failed':52.0,'refund_pending':0.0,
 'unavailable_order_paid':89.0,'unsupported_claim':0.0,'valid_split_payment':0.0}
ACT = {'canceled_order_paid':'issue_refund','duplicate_charge':'refund_duplicate_charge',
 'late_delivery_logistics':'refund_freight','late_delivery_seller':'refund_freight',
 'payment_mismatch':'reconcile_payment','refund_failed':'retry_refund','refund_pending':'monitor_refund',
 'unavailable_order_paid':'issue_refund','unsupported_claim':'document_no_action','valid_split_payment':'document_no_action'}
STAT = {'refund_pending':'needs_investigation'}
for t in POL:
    STAT.setdefault(t, 'no_action' if POL[t]==0 else 'action_required')

p('%-15s %-24s %6s %8s %8s %6s %-16s %-14s %-14s %-5s %-5s' % (
 'case','topic','pol','cap','refd','refbl','verdict','ship','cause','conf','nref'))
files=sorted(glob.glob('tools/_bak/outputs_4593/L3B_CASE_*.json'))
for f in files:
    o=json.load(open(f,encoding='utf-8'))
    cid=o['case_id']; t=o['assessment']['primary_issue']
    pa=o['payment_analysis']
    p('%-15s %-24s %6s %8s %8s %6s %-16s %-14s %-14s %-5s %-5s' % (
      cid, t, POL[t], pa['captured_total_brl'], pa['refunded_total_brl'], pa['refundable_total_brl'],
      pa['verdict'], o['shipment_analysis']['verdict'],
      o['root_cause_analysis']['ranked_causes'][0]['cause_code'],
      len(o['data_conflicts']), len(o['evidence_refs'])))

p('\n--- mismatches vs expected policy/status/action ---')
for f in files:
    o=json.load(open(f,encoding='utf-8'))
    cid=o['case_id']; t=o['assessment']['primary_issue']
    a=o['assessment']
    if a['case_status']!=STAT[t]: p(' %s status=%s expected=%s'%(cid,a['case_status'],STAT[t]))
    if o['financial_resolution']['recommended_refund_brl']!=POL[t]:
        p(' %s rec=%s policy=%s'%(cid,o['financial_resolution']['recommended_refund_brl'],POL[t]))
    if o['resolution_actions']!=[ACT[t]]: p(' %s actions=%s expected=%s'%(cid,o['resolution_actions'],[ACT[t]]))

p('\n--- captured_total vs policy constant vs refundable ---')
for f in files:
    o=json.load(open(f,encoding='utf-8'))
    cid=o['case_id']; t=o['assessment']['primary_issue']
    pa=o['payment_analysis']
    p(' %s %-24s cap=%-8s refble=%-8s rec=%-6s verdict=%s' % (cid,t,pa['captured_total_brl'],pa['refundable_total_brl'],o['financial_resolution']['recommended_refund_brl'],pa['verdict']))
OUT.close()
print('files:',len(files))
