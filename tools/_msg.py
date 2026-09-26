import json, pathlib
from collections import Counter
ROOT=pathlib.Path('.')
msgs=Counter(); scopes=Counter(); hints=Counter()
for f in sorted((ROOT/'inputs').glob('*.json')):
    d=json.loads(f.read_text(encoding='utf-8'))
    msgs[d['customer_request']['message']]+=1
    scopes[json.dumps(d['investigation_scope'],sort_keys=True)]+=1
    hints[d.get('customer_unique_id_hint') is not None]+=1
out=[]; p=out.append
p('distinct messages: %d'%len(msgs))
for m,n in msgs.most_common():
    p('  x%-4d %s'%(n,m))
p('')
p('scopes: %s'%dict(scopes))
p('hint present: %s'%dict(hints))
pathlib.Path(ROOT/'tools/_o_msg.txt').write_text('\n'.join(out),encoding='utf-8')
print('ok')
