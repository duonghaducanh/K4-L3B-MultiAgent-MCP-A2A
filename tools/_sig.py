"""Per-archetype evidence signature: which discriminator fires for cases 001-010."""
import json, pathlib
ROOT=pathlib.Path('.')
learn=json.loads((ROOT/'tools/_learn1.json').read_text(encoding='utf-8'))
learn['L3B_CASE_001']=json.loads((ROOT/'tools/_case001.json').read_text(encoding='utf-8'))
TOPICS=("late_delivery_logistics","valid_split_payment","payment_mismatch","duplicate_charge",
        "refund_pending","refund_failed","unsupported_claim","canceled_order_paid",
        "unavailable_order_paid","late_delivery_seller")
out=[]; p=out.append
for i in range(1,11):
    cid='L3B_CASE_%03d'%i
    ev=learn[cid]
    topic=TOPICS[(i-1)%10]
    pt=((ev.get('get_payment_timeline') or {}).get('data') or {})
    rt=((ev.get('get_refund_timeline') or {}).get('data') or {})
    pmts=pt.get('payments') or []
    pev=pt.get('events') or []
    rev=rt.get('events') or []
    caps=[e for e in pev if e.get('event_type')=='captured']
    mism=[e for e in pev if e.get('event_type')=='reconciliation_mismatch']
    vals=sorted({float(x.get('payment_value',0)) for x in pmts})
    p('%s topic=%-24s payments=%s caps=%d mismatch=%d refund_events=%s'
      %(cid,topic,vals,len(caps),len(mism),
        [(e.get('event_type'),e.get('status'),e.get('amount_brl')) for e in rev]))
(ROOT/'tools/_o_sig.txt').write_text('\n'.join(out),encoding='utf-8')
print('ok')
