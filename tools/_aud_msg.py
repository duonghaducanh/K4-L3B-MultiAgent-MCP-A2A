import json, glob
from collections import Counter, defaultdict
OUT=open('tools/_aud_msg.txt','w',encoding='utf-8')
def p(*a): print(*a, file=OUT)
TOPICS=('late_delivery_logistics','valid_split_payment','payment_mismatch','duplicate_charge',
 'refund_pending','refund_failed','unsupported_claim','canceled_order_paid','unavailable_order_paid','late_delivery_seller')
msgs=Counter(); bytopic=defaultdict(Counter); cases=defaultdict(list)
for f in sorted(glob.glob('inputs/L3B_CASE_*.json')):
    inp=json.load(open(f,encoding='utf-8')); cid=inp['case_id']; n=int(cid[-3:]); t=TOPICS[(n-1)%10]
    m=inp['customer_request']['message']
    msgs[m]+=1; bytopic[t][m]+=1; cases[m].append(cid)
p('=== distinct messages (%d) ==='%len(msgs))
for m,c in msgs.most_common():
    p('  x%-3d %s'%(c,m))
    p('        topics=%s'%dict(Counter(TOPICS[(int(x[-3:])-1)%10] for x in cases[m])))
    p('        cases=%s'%[x[-3:] for x in sorted(cases[m])])
# flag "distrust" messages
p('\n=== cases whose message warns about claims/conflict ===')
KEYS=('không tin','mâu thuẫn','loại trừ','xử lý nguồn mâu thuẫn','claim mâu thuẫn')
flag=[cid for m,cs in cases.items() for cid in cs if any(k in m for k in KEYS)]
p('  count=%d  %s'%(len(flag),sorted(x[-3:] for x in flag)))
# compare with observed conflict cases
OUT.close(); print('ok')
