"""Compare our numeric/set fields against the policy answer key, per topic."""
from __future__ import annotations
import json, pathlib
from collections import Counter, defaultdict
ROOT = pathlib.Path(__file__).resolve().parents[1]
policy = json.loads((ROOT / "tools/_policy.json").read_text(encoding="utf-8"))["data"]["rules"]
TOPICS = ("late_delivery_logistics","valid_split_payment","payment_mismatch","duplicate_charge",
          "refund_pending","refund_failed","unsupported_claim","canceled_order_paid",
          "unavailable_order_paid","late_delivery_seller")
lines=[]; p=lines.append
by_topic=defaultdict(list)
for f in sorted((ROOT/"outputs").glob("*.json")):
    o=json.loads(f.read_text(encoding="utf-8"))
    n=int(f.stem.rsplit("_",1)[1]); topic=TOPICS[(n-1)%10]
    ref=o["financial_resolution"]["recommended_refund_brl"]
    by_topic[topic].append(ref)

p("%-24s %8s   ours(distinct)" % ("topic","policy"))
for t in TOPICS:
    c=Counter(by_topic[t])
    p("%-24s %8.2f   %s" % (t, policy[t]["refund_brl"], dict(c)))
p("")
# affected_entities sanity
keys=Counter(); ship_empty=0; seller_empty=0
for f in sorted((ROOT/"outputs").glob("*.json")):
    o=json.loads(f.read_text(encoding="utf-8"))
    ae=o["affected_entities"]
    for k in ae: keys[k]+=1
    if not ae.get("shipment_ids"): ship_empty+=1
    if not ae.get("seller_ids"): seller_empty+=1
p("affected_entities keys seen: %s" % dict(keys))
p("cases with empty shipment_ids: %d" % ship_empty)
p("cases with empty seller_ids: %d" % seller_empty)
# entity_resolution / customer_context / payment
pv=Counter(); sv=Counter(); er=Counter()
for f in sorted((ROOT/"outputs").glob("*.json")):
    o=json.loads(f.read_text(encoding="utf-8"))
    pv[o["payment_analysis"]["verdict"]]+=1
    sv[o["shipment_analysis"]["verdict"]]+=1
    er[o["entity_resolution"]["status"]]+=1
p("payment_analysis.verdict: %s" % dict(pv))
p("shipment_analysis.verdict: %s" % dict(sv))
p("entity_resolution.status: %s" % dict(er))
pathlib.Path(ROOT/"tools/_o_num.txt").write_text("\n".join(lines),encoding="utf-8")
print("ok")
