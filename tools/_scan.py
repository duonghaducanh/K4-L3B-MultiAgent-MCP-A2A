"""Scan every observable per-case feature looking for one that matches the
reported hard_gate_count (23 of 50 public cases)."""

from __future__ import annotations

import collections
import glob
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TOPICS = (
    "late_delivery_logistics",
    "valid_split_payment",
    "payment_mismatch",
    "duplicate_charge",
    "refund_pending",
    "refund_failed",
    "unsupported_claim",
    "canceled_order_paid",
    "unavailable_order_paid",
    "late_delivery_seller",
)

outs = {}
for path in sorted(glob.glob(str(ROOT / "outputs" / "*.json"))):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    outs[data["case_id"]] = data

trace_events = collections.defaultdict(list)
for line in (ROOT / "traces" / "trace.jsonl").read_text(encoding="utf-8").splitlines():
    if line.strip():
        event = json.loads(line)
        trace_events[event["case_id"]].append(event)

topic = {}
for number in range(1, 101):
    case_id = f"L3B_CASE_{number:03d}"
    inp = json.loads((ROOT / "inputs" / f"{case_id}.json").read_text(encoding="utf-8"))
    topic[case_id] = inp["customer_request"]["claims"][0]["topic"]

features = collections.defaultdict(dict)
for case_id, out in outs.items():
    events = trace_events[case_id]
    consumed = [e for e in events if e["event_type"] == "tool_result_consumed"]
    domains = [e.get("attributes", {}).get("domain") for e in consumed]
    tools = [e["tool_name"] for e in consumed]
    f = {
        "topic": topic[case_id],
        "nref": len(out["evidence_refs"]),
        "ncalls": len(consumed),
        "ndomains": len(set(domains)),
        "has_refund_domain": "refund" in domains,
        "ship": out["shipment_analysis"]["verdict"],
        "pay": out["payment_analysis"]["verdict"],
        "issue": out["assessment"]["primary_issue"],
        "status": out["assessment"]["case_status"],
        "conf": out["assessment"]["confidence"],
        "nconf": len(out["data_conflicts"]),
        "decoy": any(c["field"] == "order_timeline.order_status" for c in out["data_conflicts"]),
        "nitems": len(out["affected_entities"]["item_ids"]),
        "nsellers": len(out["affected_entities"]["seller_ids"]),
        "npayrefs": len(out["affected_entities"]["payment_references"]),
        "nship": len(out["affected_entities"]["shipment_ids"]),
        "nrelated": len(out["customer_context"]["related_order_ids"]),
        "nlines": len(out["financial_resolution"]["refund_lines"]),
        "refund": out["financial_resolution"]["recommended_refund_brl"],
        "refundable": out["payment_analysis"]["refundable_total_brl"],
        "captured": out["payment_analysis"]["captured_total_brl"],
        "refunded": out["payment_analysis"]["refunded_total_brl"],
        "party_null": out["root_cause_analysis"]["responsible_parties"][0]["party_id"] is None,
        "nparties": len(out["root_cause_analysis"]["responsible_parties"]),
        "cause": out["root_cause_analysis"]["ranked_causes"][0]["cause_code"],
        "action": out["resolution_actions"][0],
        "timeline": out["shipment_analysis"]["timeline_complete"],
        "ca1": out["claim_assessments"][0]["verdict"],
        "ca2": out["claim_assessments"][1]["verdict"],
        "ca1n": len(out["claim_assessments"][0]["evidence_refs"]),
        "ca2n": len(out["claim_assessments"][1]["evidence_refs"]),
        "ca1c": out["claim_assessments"][0]["confidence"],
        "ca2c": out["claim_assessments"][1]["confidence"],
        "ntools": len(set(tools)),
        "dup_tools": len(tools) - len(set(tools)),
    }
    features[case_id] = f

HALVES = {
    "1-50": [f"L3B_CASE_{n:03d}" for n in range(1, 51)],
    "51-100": [f"L3B_CASE_{n:03d}" for n in range(51, 101)],
    "odd": [f"L3B_CASE_{n:03d}" for n in range(1, 101, 2)],
    "even": [f"L3B_CASE_{n:03d}" for n in range(2, 101, 2)],
    "all": [f"L3B_CASE_{n:03d}" for n in range(1, 101)],
}

keys = sorted(next(iter(features.values())))
for name, ids in HALVES.items():
    print(f"===== subset {name} (n={len(ids)}) =====")
    for key in keys:
        counts = collections.Counter(features[c][key] for c in ids)
        for value, count in counts.items():
            if count in (23, 22, 24, 27, 28):
                print(f"  {key}={value!r} -> {count} cases")
    print()

# Also: which topics dominate each half
for name, ids in HALVES.items():
    print(name, collections.Counter(features[c]["topic"] for c in ids))
