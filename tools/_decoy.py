"""Is the decoy row visible inside get_customer_history (making get_order redundant)?"""
import json, pathlib
ROOT=pathlib.Path('.')
out=[]; p=out.append
learn=json.loads((ROOT/'tools/_learn1.json').read_text(encoding='utf-8'))
learn['L3B_CASE_001']=json.loads((ROOT/'tools/_case001.json').read_text(encoding='utf-8'))
for cid in sorted(learn):
    ev=learn[cid]
    ch=ev.get('get_customer_history')
    go=ev.get('get_order')
    if not ch: p('%s: no history'%cid); continue
    orders=(ch.get('data') or {}).get('orders') or []
    claimed=None
    inp=json.loads((ROOT/f'inputs/{cid}.json').read_text(encoding='utf-8'))
    claimed=inp['customer_request']['claimed_order_id']
    same=[o for o in orders if o.get('order_id')==claimed]
    go_data=(go or {}).get('data') or {}
    go_purch=go_data.get('order_purchase_timestamp')
    hist_purchs=[o.get('order_purchase_timestamp') for o in same]
    p('%s rows=%d same_id=%d hist_purch=%s get_order_purch=%s decoy_in_hist=%s'
      %(cid,len(orders),len(same),hist_purchs,go_purch, go_purch in hist_purchs))
(ROOT/'tools/_o_decoy.txt').write_text('\n'.join(out),encoding='utf-8')
print('ok')
