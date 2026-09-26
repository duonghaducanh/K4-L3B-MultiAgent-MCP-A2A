"""Audit 2 - deep dump of per-case facts used to rank defects.

Usage: python tools/_aud2_dump.py [outputs_dir] [trace_path]
"""
from __future__ import annotations

import collections
import glob
import json
import sys
from pathlib import Path

TOPICS = (
    "late_delivery_logistics", "valid_split_payment", "payment_mismatch",
    "duplicate_charge", "refund_pending", "refund_failed", "unsupported_claim",
    "canceled_order_paid", "unavailable_order_paid", "late_delivery_seller",
)
# policy-provided responsible party type per topic (from tools/_policy.json)
NULL_PARTY_TOPICS = {
    "canceled_order_paid", "duplicate_charge", "late_delivery_logistics",
    "payment_mismatch", "refund_failed", "refund_pending", "unsupported_claim",
    "valid_split_payment", "unavailable_order_paid",
}


def main():
    outs_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("outputs")
    trace_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("traces/trace.jsonl")
    print(f"# outputs={outs_dir} trace={trace_path}")

    # trace facts
    trace_events = collections.defaultdict(list)
    for line in trace_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            e = json.loads(line)
            trace_events[e["case_id"]].append(e)

    rows = []
    for p in sorted(glob.glob(str(outs_dir / "*.json"))):
        o = json.loads(Path(p).read_text(encoding="utf-8"))
        cid = o["case_id"]
        n = int(cid.rsplit("_", 1)[1])
        expected_topic = TOPICS[(n - 1) % 10]
        a, pa, sa, ae, rc = (o["assessment"], o["payment_analysis"],
                             o["shipment_analysis"], o["affected_entities"],
                             o["root_cause_analysis"])
        fr = o["financial_resolution"]
        evs = trace_events.get(cid, [])
        types = [e["event_type"] for e in evs]
        rows.append({
            "case": cid,
            "n": n,
            "issue": a["primary_issue"],
            "expected_topic": expected_topic,
            "topic_match": a["primary_issue"] == expected_topic,
            "status": a["case_status"],
            "conf": a["confidence"],
            "ship": sa["verdict"],
            "late_sellers": len(sa["late_seller_ids"]),
            "pay": pa["verdict"],
            "refund": fr["recommended_refund_brl"],
            "refundable": pa["refundable_total_brl"],
            "nlines": len(fr["refund_lines"]),
            "line_entity_null": any(l["entity_id"] is None for l in fr["refund_lines"]),
            "party_null": any(x["party_id"] is None for x in rc["responsible_parties"]),
            "party_types": tuple(x["party_type"] for x in rc["responsible_parties"]),
            "nconflicts": len(o["data_conflicts"]),
            "conflict_fields": tuple(c["field"] for c in o["data_conflicts"]),
            "nrefs": len(o["evidence_refs"]),
            "nclaims": len(o.get("claim_assessments") or []),
            "claim_verdicts": tuple(c["verdict"] for c in o.get("claim_assessments") or []),
            "n_task_assigned": types.count("task_assigned"),
            "n_handoff": types.count("handoff"),
            "n_consumed": types.count("tool_result_consumed"),
            "er_status": o["entity_resolution"]["status"],
            "cust_null": o["customer_context"]["customer_unique_id"] is None,
            "seller_ids": tuple(ae["seller_ids"]),
            "n_actions": len(o.get("resolution_actions") or []),
        })

    print(f"cases: {len(rows)}\n")

    # 1) topic mismatch
    bad = [r for r in rows if not r["topic_match"]]
    print(f"[1] primary_issue != expected topic for case number: {len(bad)}")
    for r in bad[:15]:
        print(f"    {r['case']} issue={r['issue']} expected={r['expected_topic']}")

    # 2) null party / entity
    pn = [r for r in rows if r["party_null"]]
    en = [r for r in rows if r["line_entity_null"]]
    print(f"\n[2] responsible_parties has a null party_id: {len(pn)}")
    print("    by issue:", dict(collections.Counter(r["issue"] for r in pn)))
    print(f"    refund_lines has null entity_id: {len(en)}")
    print("    by issue:", dict(collections.Counter(r["issue"] for r in en)))

    # 3) data_conflicts
    nc = [r for r in rows if r["nconflicts"] == 0]
    print(f"\n[3] data_conflicts empty: {len(nc)} -> {[r['case'] for r in nc]}")
    print("    conflict field distribution:",
          dict(collections.Counter(r["conflict_fields"] for r in rows)))

    # 4) shipment verdict conflicting
    conf = [r for r in rows if r["ship"] == "conflicting"]
    print(f"\n[4] shipment_analysis.verdict == 'conflicting': {len(conf)}")
    for r in conf:
        print(f"    {r['case']} issue={r['issue']} ship={r['ship']} "
              f"late_sellers={r['late_sellers']}")

    # 5) status/verdict distributions
    print("\n[5] status x issue:")
    for issue in TOPICS:
        sub = [r for r in rows if r["issue"] == issue]
        if not sub:
            continue
        print(f"    {issue:26s} n={len(sub):<3} status={dict(collections.Counter(x['status'] for x in sub))} "
              f"ship={dict(collections.Counter(x['ship'] for x in sub))} "
              f"pay={dict(collections.Counter(x['pay'] for x in sub))} "
              f"party={dict(collections.Counter(x['party_types'] for x in sub))}")

    # 6) refundable vs refund mismatch
    rm = [r for r in rows if r["refund"] > 0 and r["refundable"] != r["refund"]]
    print(f"\n[6] refundable_total_brl != recommended_refund_brl (refund>0): {len(rm)}")
    for r in rm[:10]:
        print(f"    {r['case']} refund={r['refund']} refundable={r['refundable']}")

    # 7) claim verdicts
    print("\n[7] claim_verdicts distribution:",
          dict(collections.Counter(r["claim_verdicts"] for r in rows)))
    print("    nclaims distribution:", dict(collections.Counter(r["nclaims"] for r in rows)))

    # 8) workflow counts
    print("\n[8] per-case event counts: task_assigned/handoff/consumed")
    print("    ", dict(collections.Counter((r["n_task_assigned"], r["n_handoff"], r["n_consumed"]) for r in rows)))

    # 9) other edge
    print(f"\n[9] entity_resolution != resolved: {sum(1 for r in rows if r['er_status'] != 'resolved')}")
    print(f"    customer_unique_id null: {sum(1 for r in rows if r['cust_null'])}")
    print(f"    resolution_actions count != 1: {sum(1 for r in rows if r['n_actions'] != 1)}")

    # 10) issues where refund>0 but no refund line, or vice versa
    bad2 = [r for r in rows if (r["refund"] > 0) != (r["nlines"] > 0)]
    print(f"\n[10] (refund>0) != (has refund_lines): {len(bad2)}")
    for r in bad2[:10]:
        print(f"    {r['case']} refund={r['refund']} nlines={r['nlines']}")

    # 11) confidence values
    print("\n[11] confidence distribution:", dict(collections.Counter(r["conf"] for r in rows)))


if __name__ == "__main__":
    main()
