import json, glob
OUT=open('tools/_aud_final.txt','w',encoding='utf-8')
def p(*a): print(*a, file=OUT)

# 1. input claim structure
c=json.load(open('inputs/L3B_CASE_001.json',encoding='utf-8'))
p('=== input case 001 keys ===', list(c.keys()))
p('claims:', json.dumps(c['customer_request'],ensure_ascii=False))
p('claimed_order_id:', c.get('claimed_order_id'))
p('candidate_order_ids:', c.get('candidate_order_ids'))
p('customer_unique_id_hint:', c.get('customer_unique_id_hint'))
p('policy_version:', c.get('policy_version'))
p('')

# 2. output case 001 full
o=json.load(open('outputs/L3B_CASE_001.json',encoding='utf-8'))
p('=== output 001 (full) ===')
p(json.dumps(o,ensure_ascii=False,indent=1))
p('')

# 3. the two anomalies
for cid in ('L3B_CASE_012','L3B_CASE_039'):
    o=json.load(open('outputs/%s.json'%cid,encoding='utf-8'))
    p('=== %s (full) ==='%cid)
    p(json.dumps(o,ensure_ascii=False,indent=1))
    p('')
    inp=json.load(open('inputs/%s.json'%cid,encoding='utf-8'))
    p('--- %s input claims ---'%cid)
    p(json.dumps(inp['customer_request'],ensure_ascii=False))
    p('candidates:', inp.get('candidate_order_ids'))
    p('')

# 4. refund_lines / entity_id across all
p('=== refund_lines across all outputs ===')
for f in sorted(glob.glob('tools/_bak/outputs_4593/L3B_CASE_*.json')):
    o=json.load(open(f,encoding='utf-8'))
    fr=o['financial_resolution']
    p(' %s rec=%-7s lines=%s' % (o['case_id'],fr['recommended_refund_brl'],json.dumps(fr['refund_lines'],ensure_ascii=False)))

# 5. secondary_issues / resolution_actions / rejected_candidates / related_order_ids
p('')
p('=== secondary_issues / actions / rejected / related ===')
for f in sorted(glob.glob('tools/_bak/outputs_4593/L3B_CASE_*.json')):
    o=json.load(open(f,encoding='utf-8'))
    p(' %s sec=%s act=%s rej=%s rel=%d resolved=%s' % (
      o['case_id'], o['assessment']['secondary_issues'], o['resolution_actions'],
      o['entity_resolution']['rejected_candidates'],
      len(o['customer_context']['related_order_ids']),
      o['entity_resolution']['resolved_order_ids']))
OUT.close(); print('ok')
