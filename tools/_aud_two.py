import json, os
OUT=open('tools/_aud_two.txt','w',encoding='utf-8')
def p(*a): print(*a, file=OUT)
for cid in ('L3B_CASE_012','L3B_CASE_039','L3B_CASE_062','L3B_CASE_071','L3B_CASE_089','L3B_CASE_098',
            'L3B_CASE_002','L3B_CASE_001','L3B_CASE_005','L3B_CASE_008'):
    p('== '+cid)
    for lbl,path in (('4593','tools/_bak/outputs_4593/%s.json'%cid),
                     ('v1_88','tools/_bak/outputs_v1_88/%s.json'%cid)):
        if not os.path.exists(path):
            p('   %-6s (absent)'%lbl); continue
        o=json.load(open(path,encoding='utf-8'))
        pa=o['payment_analysis']
        p('   %-6s issue=%-24s status=%-18s cap=%-7s refble=%-7s rec=%-6s payv=%-16s ship=%-20s nconf=%d conf=%s'%(
          lbl,o['assessment']['primary_issue'],o['assessment']['case_status'],pa['captured_total_brl'],
          pa['refundable_total_brl'],o['financial_resolution']['recommended_refund_brl'],pa['verdict'],
          o['shipment_analysis']['verdict'],len(o['data_conflicts']),o['assessment']['confidence']))
OUT.close()
print('done')
