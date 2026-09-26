"""Offline analysis of cached evidence (not part of the submission).

Verifies the target-order selection rule: target = customer order with the
greatest purchase date <= opened_at.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOPIC = {
    "001": "late_delivery_logistics", "002": "valid_split_payment", "003": "payment_mismatch",
    "004": "duplicate_charge", "005": "refund_pending", "006": "refund_failed",
    "007": "unsupported_claim", "008": "canceled_order_paid", "009": "unavailable_order_paid",
    "010": "late_delivery_seller",
}


def load_cached() -> dict:
    data = json.loads((ROOT / "tools" / "_learn1.json").read_text(encoding="utf-8"))
    data["L3B_CASE_001"] = json.loads((ROOT / "tools" / "_case001.json").read_text(encoding="utf-8"))
    return data


def ts(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def main() -> None:
    data = load_cached()
    for num, topic in TOPIC.items():
        case_id = f"L3B_CASE_{num}"
        case = json.loads((ROOT / "inputs" / f"{case_id}.json").read_text(encoding="utf-8"))
        opened = ts(case["opened_at"])
        ev = data[case_id]
        hist = ev["get_customer_history"]["data"]["orders"]
        before = [o for o in hist if ts(o["order_purchase_timestamp"]) <= opened]
        target = max(before, key=lambda o: ts(o["order_purchase_timestamp"])) if before else min(
            hist, key=lambda o: ts(o["order_purchase_timestamp"])
        )
        t_purchase = ts(target["order_purchase_timestamp"])

        def near(value: str | None) -> bool:
            v = ts(value)
            return v is not None and abs((v - t_purchase).days) <= 15

        print("=" * 72)
        print(f"{case_id}  topic={topic}  opened={opened.date()}")
        print(f"  TARGET purchase={t_purchase.date()} status={target['order_status']} "
              f"est={target['order_estimated_delivery_date']} deliv={target['order_delivered_customer_date']}")
        for o in hist:
            mark = "  <-- target" if o is target else ""
            print(f"    hist {o['order_purchase_timestamp'][:10]} {o['order_status']}{mark}")
        it = ev["get_order_items"]["data"]
        print("  items(near):", [(x["shipping_limit_date"][:10], x["price"], x["freight_value"]) for x in it if near(x["shipping_limit_date"])])
        pt = ev["get_payment_timeline"]["data"]
        print("  pay(near):", [(x["event_type"], x["amount_brl"], x["status"], x["event_at"][:10]) for x in pt["events"] if near(x["event_at"])])
        print("  pay(ALL):", [(x["event_type"], x["amount_brl"], x["status"], x["event_at"][:10]) for x in pt["events"]])
        sh = ev["get_shipment_summary"]["data"]
        print("  ship events:", [(x["event_type"], x["actor"], x["event_at"][:10]) for x in sh["events"]])
        rf = ev.get("get_refund_timeline")
        if isinstance(rf, dict) and "data" in rf:
            print("  refund:", [(x["event_type"], x["amount_brl"], x["status"], x["event_at"][:10]) for x in rf["data"]["events"]])


if __name__ == "__main__":
    main()
