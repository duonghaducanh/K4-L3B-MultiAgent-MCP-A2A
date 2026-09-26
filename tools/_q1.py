"""Probe cached evidence: refund domain coverage + minimal call set questions."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
d = json.loads((ROOT / "tools" / "_learn1.json").read_text(encoding="utf-8"))
print("KEYS", sorted(d.keys()))


def show(cid):
    e = d[cid]
    inp = json.loads((ROOT / "inputs" / f"{cid}.json").read_text(encoding="utf-8"))
    topics = [c.get("topic") for c in inp["customer_request"]["claims"]]
    print("=" * 70)
    print(cid, "claims=", topics, "opened=", inp["opened_at"][:10])
    h = (e.get("get_customer_history") or {}).get("data", {}).get("orders", [])
    for o in h:
        print("  hist", o["order_id"][:14], o["order_purchase_timestamp"][:10],
              o["order_status"], "deliv", str(o.get("order_delivered_customer_date"))[:10],
              "est", str(o.get("order_estimated_delivery_date"))[:10])
    go = (e.get("get_order") or {}).get("data") or {}
    if go:
        print("  get_order ->", go.get("order_status"), go.get("order_purchase_timestamp"))
    pt = (e.get("get_payment_timeline") or {}).get("data") or {}
    for ev in pt.get("events", []):
        print("  pay_ev", ev.get("event_type"), ev.get("amount_brl"), ev.get("status"),
              str(ev.get("event_at"))[:10])
    for p in pt.get("payments", []):
        print("  pay_row", p.get("payment_sequential"), p.get("payment_type"), p.get("payment_value"))
    rf = e.get("get_refund_timeline")
    print("  refund:", json.dumps(rf, ensure_ascii=False)[:500] if rf else None)
    sh = (e.get("get_shipment_summary") or {}).get("data") or {}
    for ev in sh.get("events", []):
        print("  ship_ev", ev.get("event_type"), ev.get("actor"),
              str(ev.get("event_at"))[:10], ev.get("status"))


for k in sorted(d)[:6]:
    show(k)
