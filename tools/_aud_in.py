import json, glob, os

OUT = open('tools/_aud_in.txt','w',encoding='utf-8')
def p(*a): print(*a, file=OUT)

for f in sorted(glob.glob('inputs/L3B_CASE_*.json')):
    c = json.load(open(f,encoding='utf-8'))
    cid = c['case_id']
    req = c['customer_request']
    topics = [cl.get('topic') for cl in req.get('claims',[])]
    p('%s opened=%s claimed=%s topics=%s policy=%s hint=%s' % (
        cid, c['opened_at'], req['claimed_order_id'][:16], topics,
        c.get('policy_version'), c.get('customer_unique_id_hint')))
OUT.close()
print('done')
