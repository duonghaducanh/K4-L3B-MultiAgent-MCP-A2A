import json, glob
from collections import Counter

OUT = open('tools/_aud_schema.txt','w',encoding='utf-8')
def p(*a): print(*a, file=OUT)

try:
    import jsonschema
    from jsonschema import Draft202012Validator
    HAVE=True
except Exception as e:
    p('no jsonschema:', e); HAVE=False

schema=json.load(open('contracts/schemas/l3b-output-v2.schema.json',encoding='utf-8'))
l3a=json.load(open('contracts/schemas/l3a-output-v2.schema.json',encoding='utf-8'))

if HAVE:
    import referencing, referencing.jsonschema
    from referencing import Registry, Resource
    reg = Registry().with_resource('l3a-output-v2.schema.json',
        Resource.from_contents(l3a, default_specification=referencing.jsonschema.DRAFT202012))
    v = Draft202012Validator(schema, registry=reg)
    bad=[]
    for f in sorted(glob.glob('outputs/L3B_CASE_*.json')):
        o=json.load(open(f,encoding='utf-8'))
        errs=sorted(v.iter_errors(o), key=lambda e: e.path)
        if errs:
            bad.append((o['case_id'], [ (list(e.path), e.message[:120]) for e in errs[:3]]))
    p('schema failures: %d' % len(bad))
    for b in bad: p('  ', b)

# consistency checks
p('\n--- consistency cross-checks ---')
issues=[]
for f in sorted(glob.glob('outputs/L3B_CASE_*.json')):
    o=json.load(open(f,encoding='utf-8'))
    cid=o['case_id']
    a=o['assessment']; fr=o['financial_resolution']; pa=o['payment_analysis']
    sa=o['shipment_analysis']; rca=o['root_cause_analysis']
    # status/refund
    if a['case_status']=='no_action' and fr['recommended_refund_brl']!=0:
        issues.append((cid,'no_action but refund != 0'))
    if fr['recommended_refund_brl']==0 and fr['refund_lines']:
        issues.append((cid,'refund 0 but lines nonempty'))
    if abs(sum(l['amount_brl'] for l in fr['refund_lines'])-fr['recommended_refund_brl'])>1e-9:
        issues.append((cid,'refund lines != total'))
    if sa['verdict']!='seller_delay' and sa['late_seller_ids']:
        issues.append((cid,'late_seller_ids nonempty w/o seller_delay'))
    if a['case_status']=='action_required' and not o['resolution_actions']:
        issues.append((cid,'action_required w/o action'))
    if len(o['resolution_actions'])!=len(set(o['resolution_actions'])):
        issues.append((cid,'dup actions'))
    # seller responsibility
    pt=[x['party_type'] for x in rca['responsible_parties']]
    if 'seller' in pt and not o['affected_entities']['seller_ids']:
        issues.append((cid,'seller party but no seller ids'))
    if rca['ranked_causes'][0]['cause_code']=='' :
        issues.append((cid,'empty cause'))
    if pa['captured_total_brl'] is None:
        issues.append((cid,'null captured'))
    # claim verdict vs status
    for c in o.get('claim_assessments',[]):
        if c['verdict']=='supported' and a['case_status']=='no_action' and c['claim_id'].endswith('-a'):
            issues.append((cid,'primary claim supported but no_action'))
p('consistency issues: %d' % len(issues))
for i in issues: p('  ',i)

p('\n--- cases with 0 data_conflicts ---')
for f in sorted(glob.glob('outputs/L3B_CASE_*.json')):
    o=json.load(open(f,encoding='utf-8'))
    if not o['data_conflicts']:
        p('  ', o['case_id'], o['assessment']['primary_issue'], o['assessment']['case_status'])
OUT.close()
print('done')
