"""Scan all 100 outputs for captured_total anomalies vs deduped item totals."""
import json, pathlib
from collections import Counter
ROOT=pathlib.Path('.')
TOPICS=("late_delivery_logistics","valid_split_payment","payment_mismatch","duplicate_charge",
        "refund_pending","refund_failed","unsupported_claim","canceled_order_paid",
        "unavailable_order_paid","late_delivery_seller")
out=[]; p=out.append
rows=[]
for f in sorted((ROOT/'outputs').glob('*.json')):
    o=json.loads(f.read_text(encoding='utf-8'))
    n=int(f.stem.rsplit('_',1)[1]); topic=TOPICS[(n-1)%10]
    cap=o['payment_analysis']['captured_total_brl']
    ref=o['financial_resolution']['recommended_refund_brl']
    items=o['affected_entities']['item_ids']
    rows.append((f.stem,topic,cap,ref,len(items),o['payment_analysis']['refundable_total_brl'],o['assessment']['confidence']))
p('%-16s %-24s %8s %8s %3s %8s %5s'%('case','topic','captured','refund','ni','refundbl','conf'))
for r in rows:
    p('%-16s %-24s %8.2f %8.2f %3d %8.2f %5s'%r)
p('')
c=Counter((r[1],r[2]) for r in rows)
p('(topic, captured_total) frequencies:')
for k,v in sorted(c.items()):
    p('   %-24s %8.2f x%d'%(k[0],k[1],v))
pathlib.Path(ROOT/'tools/_o_cap.txt').write_text('\n'.join(out),encoding='utf-8')
print('ok')
