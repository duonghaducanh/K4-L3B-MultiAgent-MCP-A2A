import json, glob
from datetime import datetime
from collections import Counter

OUT = open('tools/_aud_all.txt','w',encoding='utf-8')
def p(*a): print(*a, file=OUT)

def parse(v): return datetime.fromisoformat(v) if v else None
def money(v):
    try: return round(float(v),2)
    except: return 0.0

TOPICS = ("late_delivery_logistics","valid_split_payment","payment_mismatch","duplicate_charge",
 "refund_pending","refund_failed","unsupported_claim","canceled_order_paid","unavailable_order_paid","late_delivery_seller")

rows=[]
for f in sorted(glob.glob('outputs/L3B_CASE_*.json')):
    o=json.load(open(f,encoding='utf-8'))
    cid=o['case_id']
    inp=json.load(open('inputs/%s.json'%cid,encoding='utf-8'))
    topic=inp['customer_request']['claims'][0]['topic']
    exp_topic=TOPICS[(int(cid[-3:])-1)%10]
    a=o['assessment']; pa=o['payment_analysis']; fr=o['financial_resolution']
    rows.append(dict(cid=cid, topic=topic, exp=exp_topic, issue=a['primary_issue'],
        status=a['case_status'], conf=a['confidence'],
        verdict=pa['verdict'], cap=pa['captured_total_brl'], refd=pa['refunded_total_brl'], refble=pa['refundable_total_brl'],
        rec=fr['recommended_refund_brl'], lines=fr['refund_lines'],
        ship=o['shipment_analysis']['verdict'], latesell=o['shipment_analysis']['late_seller_ids'],
        nconf=len(o['data_conflicts']), cause=o['root_cause_analysis']['ranked_causes'][0]['cause_code'],
        parties=o['root_cause_analysis']['responsible_parties'],
        ent=o['affected_entities'], related=o['customer_context']['related_order_ids'],
        sec=a['secondary_issues'], actions=o['resolution_actions'],
        nrefs=len(o['evidence_refs']), nclaims=len(o.get('claim_assessments',[])),
        claimverds=[(c['claim_id'],c['verdict'],c['confidence'],len(c['evidence_refs'])) for c in o.get('claim_assessments',[])],
        rej=o['entity_resolution']['rejected_candidates'], erconf=o['entity_resolution']['confidence'],
        o=o))

p('topic cycle mismatch: %s' % [(r['cid'],r['topic'],r['exp']) for r in rows if r['topic']!=r['exp']])
p('issue != topic: %s' % [(r['cid'],r['issue'],r['topic']) for r in rows if r['issue']!=r['topic']])
p('status counts: %s' % Counter(r['status'] for r in rows))
p('verdict counts: %s' % Counter(r['verdict'] for r in rows))
p('ship counts: %s' % Counter(r['ship'] for r in rows))
p('cause counts: %s' % Counter(r['cause'] for r in rows))
p('conf counts: %s' % Counter(r['nconf'] for r in rows))
p('cases with 0 conflicts: %s' % [(r['cid'],r['topic'],r['issue']) for r in rows if r['nconf']==0])
p('rec refund counts: %s' % Counter(r['rec'] for r in rows))
p('refundable counts: %s' % Counter(r['refble'] for r in rows))
p('conf counts: %s' % Counter(r['conf'] for r in rows))
p('nrefs: %s' % Counter(r['nrefs'] for r in rows))
p('related len: %s' % Counter(len(r['related']) for r in rows))
p('related == [claimed]? %s' % all(r['related']==r['ent']['order_ids'] for r in rows))

p('\n--- refundable != rec (should be 0 vs pending) ---')
for r in rows:
    if r['refble'] != r['rec']:
        p('  %s topic=%s rec=%s refundable=%s verdict=%s' % (r['cid'],r['topic'],r['rec'],r['refble'],r['verdict']))

p('\n--- refund_lines entity_id by topic ---')
for r in rows:
    if r['lines']:
        eid=r['lines'][0]['entity_id']
        if r['topic'] in ('late_delivery_seller','unavailable_order_paid') or eid is None:
            p('  %s topic=%s amt=%s entity_id=%s' % (r['cid'],r['topic'],r['lines'][0]['amount_brl'],eid))
p('\n--- all refund_lines ---')
c=Counter()
for r in rows:
    key=(r['topic'], r['lines'][0]['entity_id'] if r['lines'] else None, r['lines'][0]['reason_code'] if r['lines'] else None)
    c[key]+=1
for k,v in sorted(c.items(), key=lambda x:str(x)):
    p('  %s x%d' % (str(k),v))

p('\n--- secondary_issues ---')
p(Counter(tuple(r['sec']) for r in rows))
p('\n--- actions ---')
p(Counter(tuple(r['actions']) for r in rows))
p('\n--- parties by topic ---')
c=Counter()
for r in rows:
    c[(r['topic'], tuple((x['party_type'], x['party_id']) for x in r['parties']))]+=1
for k,v in sorted(c.items(),key=lambda x:str(x)): p('  %s x%d'%(str(k),v))

p('\n--- claim verdicts by topic ---')
c=Counter()
for r in rows:
    c[(r['topic'], tuple((v[1],v[2]) for v in r['claimverds']))]+=1
for k,v in sorted(c.items(),key=lambda x:str(x)): p('  %s x%d'%(str(k),v))

p('\n--- payment refs / item ids / sellers sample ---')
for r in rows[:20]:
    p('  %s items=%s sellers=%s payrefs=%s ship=%s' % (r['cid'],r['ent']['item_ids'],r['ent']['seller_ids'],r['ent']['payment_references'],r['ent']['shipment_ids']))

p('\n--- late_seller_ids nonempty ---')
for r in rows:
    if r['latesell']: p('  %s topic=%s latesell=%s ship=%s' % (r['cid'],r['topic'],r['latesell'],r['ship']))
OUT.close()
print('done')
