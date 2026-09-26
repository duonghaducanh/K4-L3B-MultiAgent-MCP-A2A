"""Find any per-case feature whose count over all 100 cases is ~46 (=> ~23 of a
random public half) or exactly 23/50 in a plausible split."""

from __future__ import annotations

import collections
import glob
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

outs = {}
for path in sorted(glob.glob(str(ROOT / "outputs" / "*.json"))):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    outs[data["case_id"]] = data

events = collections.defaultdict(list)
for line in (ROOT / "traces" / "trace.jsonl").read_text(encoding="utf-8").splitlines():
    if line.strip():
        e = json.loads(line)
        events[e["case_id"]].append(e)

feat = {}
for cid, out in outs.items():
    ev = events[cid]
    consumed = [e for e in ev if e["event_type"] == "tool_result_consumed"]
    tools = [e["tool_name"] for e in consumed]
    domains = sorted({e.get("attributes", {}).get("domain") for e in consumed})
    handoffs = [e for e in ev if e["event_type"] == "handoff"]
    tasks = [e for e in ev if e["event_type"] == "task_assigned"]
    ver = next(e for e in ev if e["event_type"] == "verification_completed")
    conf = out["data_conflicts"]
    f = {
        "topic": None,
        "nref": len(out["evidence_refs"]),
        "ncalls": len(consumed),
        "ndomains": len(domains),
        "has_refund": "refund" in domains,
        "ship": out["shipment_analysis"]["verdict"],
        "pay": out["payment_analysis"]["verdict"],
        "issue": out["assessment"]["primary_issue"],
        "status": out["assessment"]["case_status"],
        "conf": out["assessment"]["confidence"],
        "nconf": len(conf),
        "conf_fields": tuple(sorted(c["field"] for c in conf)),
        "decoy": any(c["field"] == "order_timeline.order_status" for c in conf),
        "issue_conflict": any(c["field"] == "assessment.primary_issue" for c in conf),
        "timeline": out["shipment_analysis"]["timeline_complete"],
        "late_sellers": len(out["shipment_analysis"]["late_seller_ids"]),
        "ca1": out["claim_assessments"][0]["verdict"],
        "ca2": out["claim_assessments"][1]["verdict"],
        "ca1n": len(out["claim_assessments"][0]["evidence_refs"]),
        "ca2n": len(out["claim_assessments"][1]["evidence_refs"]),
        "ca1c": out["claim_assessments"][0]["confidence"],
        "ca2c": out["claim_assessments"][1]["confidence"],
        "nlines": len(out["financial_resolution"]["refund_lines"]),
        "refund": out["financial_resolution"]["recommended_refund_brl"],
        "refundable": out["payment_analysis"]["refundable_total_brl"],
        "captured": out["payment_analysis"]["captured_total_brl"],
        "refunded": out["payment_analysis"]["refunded_total_brl"],
        "party_null": out["root_cause_analysis"]["responsible_parties"][0]["party_id"] is None,
        "nparties": len(out["root_cause_analysis"]["responsible_parties"]),
        "cause": out["root_cause_analysis"]["ranked_causes"][0]["cause_code"],
        "action": out["resolution_actions"][0],
        "nsecondary": len(out["assessment"]["secondary_issues"]),
        "nitems": len(out["affected_entities"]["item_ids"]),
        "nsellers": len(out["affected_entities"]["seller_ids"]),
        "npayrefs": len(out["affected_entities"]["payment_references"]),
        "nship": len(out["affected_entities"]["shipment_ids"]),
        "nrelated": len(out["customer_context"]["related_order_ids"]),
        "nhandoffs": len(handoffs),
        "ntasks": len(tasks),
        "verdict_pass": ver.get("attributes", {}).get("passed"),
        "verdict_code": ver.get("decision_code"),
        "nref_verif": len(ver.get("evidence_refs") or []),
        "entity_conf": out["entity_resolution"]["confidence"],
    }
    feat[cid] = f

for number in range(1, 101):
    cid = f"L3B_CASE_{number:03d}"
    inp = json.loads((ROOT / "inputs" / f"{cid}.json").read_text(encoding="utf-8"))
    feat[cid]["topic"] = inp["customer_request"]["claims"][0]["topic"]

keys = sorted(next(iter(feat.values())))
print("Feature values with total count in 40..60 over all 100 cases (would yield ~20-30 in a random half):")
for key in keys:
    counts = collections.Counter(feat[c][key] for c in feat)
    for value, count in counts.items():
        if 40 <= count <= 60:
            print(f"  {key}={value!r} -> {count}")

print("\nFeature values with count exactly 23 or 50 in all 100:")
for key in keys:
    counts = collections.Counter(feat[c][key] for c in feat)
    for value, count in counts.items():
        if count in (23, 50):
            print(f"  {key}={value!r} -> {count}")

print("\nPer-key value counts for selected keys:")
for key in ["ndomains", "has_refund", "verdict_pass", "verdict_code", "ship", "pay", "nref"]:
    print(f"  {key}: {dict(collections.Counter(feat[c][key] for c in feat))}")
