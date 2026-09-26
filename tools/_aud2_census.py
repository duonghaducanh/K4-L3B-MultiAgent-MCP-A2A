"""Audit 2 - final consolidated defect census over a full case set.

Usage: python tools/_aud2_census.py [outputs_dir] [trace_path]
"""
from __future__ import annotations

import collections
import glob
import json
import os
import sys
from pathlib import Path

TOPICS = (
    "late_delivery_logistics", "valid_split_payment", "payment_mismatch",
    "duplicate_charge", "refund_pending", "refund_failed", "unsupported_claim",
    "canceled_order_paid", "unavailable_order_paid", "late_delivery_seller",
)
SHIP_EXPECT = {"late_delivery_seller": "seller_delay",
               "late_delivery_logistics": "logistics_delay"}
PAY_EXPECT = {"duplicate_charge": "duplicate_capture",
              "payment_mismatch": "capture_mismatch",
              "refund_pending": "refund_pending",
              "refund_failed": "refund_failed"}


def main():
    outs = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("outputs")
    tp = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("traces/trace.jsonl")
    print(f"# outputs={outs}  trace={tp}")

    # ---------- trace ----------
    by_case = collections.OrderedDict()
    for line in tp.read_text(encoding="utf-8").splitlines():
        if line.strip():
            e = json.loads(line)
            by_case.setdefault(e["case_id"], []).append(e)

    # ---------- outputs ----------
    outputs = {}
    for p in sorted(glob.glob(str(outs / "*.json"))):
        o = json.loads(Path(p).read_text(encoding="utf-8"))
        outputs[o["case_id"]] = o
    print(f"cases: outputs={len(outputs)} trace={len(by_case)}")
    print(f"outputs w/o trace: {sorted(set(outputs)-set(by_case))}")
    print(f"trace w/o output: {sorted(set(by_case)-set(outputs))}")

    defc = collections.defaultdict(list)

    # ================= DEFECT 1: null party_id / entity_id =================
    for cid, o in outputs.items():
        rc = o["root_cause_analysis"]["responsible_parties"]
        if any(p.get("party_id") is None for p in rc):
            defc["D1a responsible_parties[].party_id == null"].append(cid)
        if any(l.get("entity_id") is None for l in o["financial_resolution"]["refund_lines"]):
            defc["D1b refund_lines[].entity_id == null"].append(cid)

    # ================= DEFECT 2: derived-vs-claimed mismatch ===============
    for cid, o in outputs.items():
        n = int(cid.rsplit("_", 1)[1])
        exp = TOPICS[(n - 1) % 10]
        iss = o["assessment"]["primary_issue"]
        if iss != exp:
            defc["D2 primary_issue != case-number topic"].append(cid)
        # shipment verdict vs issue
        if iss in SHIP_EXPECT and o["shipment_analysis"]["verdict"] != SHIP_EXPECT[iss]:
            defc["D3 shipment_verdict contradicts primary_issue"].append(cid)
        if iss in PAY_EXPECT and o["payment_analysis"]["verdict"] != PAY_EXPECT[iss]:
            defc["D4 payment_verdict contradicts primary_issue"].append(cid)
        # late_seller_ids vs issue
        if iss == "late_delivery_seller" and not o["shipment_analysis"]["late_seller_ids"]:
            defc["D5 late_delivery_seller without late_seller_ids"].append(cid)
        if o["shipment_analysis"]["late_seller_ids"] and \
                o["shipment_analysis"]["verdict"] != "seller_delay":
            defc["D6 late_seller_ids set but verdict != seller_delay"].append(cid)
        if iss == "late_delivery_seller" and \
                set(o["affected_entities"]["seller_ids"]) != set(o["shipment_analysis"]["late_seller_ids"]):
            defc["D7 seller_ids != late_seller_ids"].append(cid)

    # ================= DEFECT 3: refund/status consistency =================
    for cid, o in outputs.items():
        st = o["assessment"]["case_status"]
        ref = o["financial_resolution"]["recommended_refund_brl"]
        if st == "no_action" and ref != 0:
            defc["D8 no_action with nonzero refund"].append(cid)
        s = round(sum(float(l["amount_brl"]) for l in o["financial_resolution"]["refund_lines"]), 2)
        if abs(s - ref) > 0.01:
            defc["D9 refund_lines sum != recommended"].append(cid)
        if (ref > 0) != bool(o["financial_resolution"]["refund_lines"]):
            defc["D10 refund>0 xor has refund_lines"].append(cid)
        acts = o.get("resolution_actions") or []
        if len(set(acts)) != len(acts):
            defc["D11 duplicate resolution_actions"].append(cid)
        if not acts:
            defc["D12 empty resolution_actions"].append(cid)

    # ================= DEFECT 4: data_conflicts ============================
    for cid, o in outputs.items():
        dc = o["data_conflicts"]
        if not dc:
            defc["D13 data_conflicts empty"].append(cid)
        fields = {c["field"] for c in dc}
        if "order_timeline.order_status" not in fields:
            defc["D14 no order_timeline.order_status conflict"].append(cid)

    # ================= DEFECT 5: trace<->output contradiction ==============
    for cid, o in outputs.items():
        evs = by_case.get(cid, [])
        pd = next((e for e in evs if e["event_type"] == "policy_decided"), None)
        if pd is None:
            defc["D15 no policy_decided event"].append(cid)
            continue
        if pd.get("decision_code") != o["assessment"]["primary_issue"]:
            defc["D16 policy_decided != primary_issue"].append(cid)
        sel_trace = (pd.get("attributes") or {}).get("selected_source")
        sel_out = [c["selected_source"] for c in o["data_conflicts"]
                   if c["field"] == "assessment.primary_issue"]
        if sel_out and sel_out[0] != sel_trace:
            defc["D17 trace selected_source != output selected_source"].append(cid)
        # verification
        vc = next((e for e in evs if e["event_type"] == "verification_completed"), None)
        if vc and vc.get("decision_code") != "verification_passed":
            defc["D18 verification_downgraded"].append(cid)

    # ================= DEFECT 6: workflow structure ========================
    REQ = ["case_received", "task_assigned", "handoff",
           "verification_completed", "case_finalized"]
    for cid, evs in by_case.items():
        types = [e["event_type"] for e in evs]
        if types and types[0] != "case_received":
            defc["D19 first event != case_received"].append(cid)
        if types and types[-1] != "case_finalized":
            defc["D20 last event != case_finalized"].append(cid)
        for r in REQ:
            if r not in types:
                defc[f"D21 missing {r}"].append(cid)
        if types.count("case_received") != 1:
            defc["D22 case_received count != 1"].append(cid)
        if types.count("case_finalized") != 1:
            defc["D23 case_finalized count != 1"].append(cid)
        if types.count("task_assigned") != 1:
            defc["D24 task_assigned count != 1"].append(cid)
        if types.count("handoff") != 1:
            defc["D25 handoff count != 1"].append(cid)
        if types.count("verification_completed") != 1:
            defc["D26 verification_completed count != 1"].append(cid)
        if "verification_completed" in types and "case_finalized" in types and \
                types.index("verification_completed") > types.index("case_finalized"):
            defc["D27 verification after finalize"].append(cid)
        ts = [e["occurred_at"] for e in evs]
        if ts != sorted(ts):
            defc["D28 occurred_at not monotonic"].append(cid)
        # task_assigned target must appear as a LATER HANDOFF actor (strict)
        for i, e in enumerate(evs):
            if e["event_type"] == "task_assigned" and e.get("target"):
                later_handoff_actors = {x.get("actor") for x in evs[i + 1:]
                                        if x["event_type"] == "handoff"}
                if e["target"] not in later_handoff_actors:
                    defc[f"D29 no handoff by assigned target {e['target']}"].append(cid)
        # handoff actor must have been assigned
        assigned = {e["target"] for e in evs if e["event_type"] == "task_assigned"}
        for e in evs:
            if e["event_type"] == "handoff" and e.get("actor") not in assigned:
                defc[f"D30 handoff actor {e.get('actor')} never assigned"].append(cid)

    # ================= DEFECT 7: schema edge cases =========================
    for cid, o in outputs.items():
        if o["entity_resolution"]["status"] != "resolved":
            defc["D31 entity_resolution != resolved"].append(cid)
        if not o.get("evidence_refs"):
            defc["D32 empty evidence_refs"].append(cid)
        if o["customer_context"]["customer_unique_id"] is None:
            defc["D33 customer_unique_id null"].append(cid)
        if not o["claim_assessments"]:
            defc["D34 empty claim_assessments"].append(cid)
        for c in o.get("claim_assessments") or []:
            if not c.get("evidence_refs"):
                defc["D35 claim with empty evidence_refs"].append(cid)
        for k in ("captured_total_brl", "refunded_total_brl", "refundable_total_brl"):
            if o["payment_analysis"].get(k) is None:
                defc[f"D36 payment null {k}"].append(cid)
        if not o["root_cause_analysis"]["ranked_causes"]:
            defc["D37 empty ranked_causes"].append(cid)
        if not o["root_cause_analysis"]["responsible_parties"]:
            defc["D38 empty responsible_parties"].append(cid)
        if not o["affected_entities"]["seller_ids"]:
            defc["D39 empty seller_ids"].append(cid)
        if not o["affected_entities"]["payment_references"]:
            defc["D40 empty payment_references"].append(cid)
        if not o["affected_entities"]["shipment_ids"]:
            defc["D41 empty shipment_ids"].append(cid)
        if not o["affected_entities"]["item_ids"]:
            defc["D42 empty item_ids"].append(cid)
        if not o["shipment_analysis"]["timeline_complete"]:
            defc["D43 timeline_complete false"].append(cid)

    print("\n================ DEFECT CENSUS ================")
    n = len(outputs)
    for k in sorted(defc, key=lambda x: (-len(defc[x]), x)):
        cs = defc[k]
        print(f"\n{k}: {len(cs)}/{n} cases")
        print(f"   {sorted(cs)}")


if __name__ == "__main__":
    main()
