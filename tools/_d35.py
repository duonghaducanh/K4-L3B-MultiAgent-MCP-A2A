"""Diff the full cached evidence of case 003 (payment_mismatch) vs 005 (refund_pending)."""
import json, pathlib
ROOT=pathlib.Path('.')
learn=json.loads((ROOT/'tools/_learn1.json').read_text(encoding='utf-8'))
a=learn['L3B_CASE_003']; b=learn['L3B_CASE_005']
out=[]; p=out.append
def data(v):
    if isinstance(v,dict) and 'data' in v: return v['data']
    return v
for t in sorted(set(a)|set(b)):
    if t in ('claimed','candidates'): continue
    da=data(a.get(t)); db=data(b.get(t))
    sa=json.dumps(da,ensure_ascii=False,sort_keys=True)
    sb=json.dumps(db,ensure_ascii=False,sort_keys=True)
    p('== %-24s same=%s'%(t, sa==sb))
    if sa!=sb:
        p('   003: %s'%sa[:1200])
        p('   005: %s'%sb[:1200])
p('')
p('claims 003: %s'%json.dumps(a['claimed'],ensure_ascii=False))
p('claims 005: %s'%json.dumps(b['claimed'],ensure_ascii=False))
(ROOT/'tools/_o_d35.txt').write_text('\n'.join(out),encoding='utf-8')
print('ok')
