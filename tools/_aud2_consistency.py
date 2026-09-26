"""Audit 2 - Task 4: consistency cross-field rules. Task 5: schema edge cases.

Usage: python tools/_aud2_consistency.py [outputs_dir]
"""
from __future__ import annotations

import collections
import glob
import json
import sys
from pathlib import Path

# expected payment verdict per primary_issue (from the workflow's own mapping)
PAYMENT_EXPECT = {
    "duplicate_charge": "duplicate_capture",
    "payment_mismatch": "capture_mismatch",
    "refund_pending": "refund_pending",
    "refund_failed": "refund_failed",
}
SHIP_EXPECT = {
    "late_delivery_seller": "seller_delay",
    "late_delivery_logistics": "logistics_delay",
}


def main():
    outs_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("outputs")
    paths = sorted(glob.glob(str(outs_dir / "*.json")))
    print(f"# outputs={outs_dir}  files={len(paths)}")

    findings = collections.defaultdict(list)   # rule -> [case]
    detail = collections.defaultdict(list)

    def flag(rule, cid, msg):
        findings[rule].append(cid)
        detail[rule].append((cid, msg))

    # ---- task 5 tallies ----
    t5 = collections.Counter()
    t5_cases = collections.defaultdict(list)

    for path in paths:
        o = json.loads(Path(path).read_text(encoding="utf-8"))
        cid = o["case_id"]
        a = o["assessment"]
        fr = o["financial_resolution"]
        pa = o["payment_analysis"]
        sa = o["shipment_analysis"]
        ae = o["affected_entities"]
        rc = o["root_cause_analysis"]
        er = o["entity_resolution"]
        cc = o["customer_context"]

        issue = a["primary_issue"]
        status = a["case_status"]
        refund = fr["recommended_refund_brl"]
        lines = fr["refund_lines"]

        # --- Task 4 rules ---
        # R1 no_action with nonzero refund
        if status == "no_action" and refund != 0:
            flag("R1 no_action_with_refund", cid,
                 f"case_status=no_action recommended_refund_brl={refund}")

        # R2 refund != sum(lines)
        line_sum = round(sum(float(l["amount_brl"]) for l in lines), 2)
        if abs(line_sum - refund) > 0.01:
            flag("R2 refund_lines_total_mismatch", cid,
                 f"recommended={refund} sum(lines)={line_sum} lines={lines}")

        # R3 payment verdict vs primary_issue
        exp = PAYMENT_EXPECT.get(issue)
        if exp is not None and pa["verdict"] != exp:
            flag("R3 payment_verdict_vs_issue", cid,
                 f"issue={issue} payment_verdict={pa['verdict']} expected={exp}")

        # R4 shipment verdict vs late_seller_ids / issue
        if sa["late_seller_ids"] and sa["verdict"] != "seller_delay":
            flag("R4a late_seller_ids_nonempty_but_verdict", cid,
                 f"late_seller_ids={sa['late_seller_ids']} verdict={sa['verdict']}")
        sexp = SHIP_EXPECT.get(issue)
        if sexp is not None and sa["verdict"] != sexp:
            flag("R4b shipment_verdict_vs_issue", cid,
                 f"issue={issue} shipment_verdict={sa['verdict']} expected={sexp}")
        if issue == "late_delivery_seller" and not sa["late_seller_ids"]:
            flag("R4c late_delivery_seller_without_late_seller_ids", cid,
                 f"issue=late_delivery_seller late_seller_ids={sa['late_seller_ids']}")

        # R5 duplicate resolution_actions (schema uniqueItems - check semantic dupes)
        acts = o.get("resolution_actions") or []
        if len(set(acts)) != len(acts):
            flag("R5a duplicate_resolution_actions_exact", cid, f"actions={acts}")
        norm = [str(x).strip().lower() for x in acts]
        if len(set(norm)) != len(norm):
            flag("R5b duplicate_resolution_actions_semantic", cid, f"actions={acts}")

        # R6 responsible_parties vs refund_lines entity_id
        parties = rc.get("responsible_parties") or []
        party_ids = {p.get("party_id") for p in parties}
        for l in lines:
            eid = l.get("entity_id")
            if eid is None:
                flag("R6a refund_line_null_entity", cid, f"line={l} parties={parties}")
            elif eid not in party_ids:
                flag("R6b refund_entity_not_in_responsible_parties", cid,
                     f"entity_id={eid!r} parties={parties}")

        # R7 affected_entities.seller_ids vs late_seller_ids
        if issue == "late_delivery_seller":
            if set(ae["seller_ids"]) != set(sa["late_seller_ids"]):
                flag("R7a seller_ids_vs_late_seller_ids", cid,
                     f"seller_ids={ae['seller_ids']} late_seller_ids={sa['late_seller_ids']}")

        # extra: refundable vs refund
        if refund > 0 and pa["refundable_total_brl"] != refund:
            flag("R8 refundable_vs_recommended", cid,
                 f"recommended={refund} refundable={pa['refundable_total_brl']}")

        # extra: confidence out of range or >1
        for label, val in (("assessment", a["confidence"]),
                           ("entity_resolution", er["confidence"])):
            if not isinstance(val, (int, float)) or not (0 <= val <= 1):
                flag("R9 confidence_out_of_range", cid, f"{label}={val}")

        # extra: primary_issue == insufficient_evidence (schema allows; likely wrong)
        if issue == "insufficient_evidence":
            flag("R10 primary_issue_insufficient_evidence", cid, "primary_issue=insufficient_evidence")

        # ---- Task 5 edge cases ----
        if er["status"] != "resolved":
            t5["entity_resolution_not_resolved"] += 1
            t5_cases["entity_resolution_not_resolved"].append(cid)
        if not o.get("evidence_refs"):
            t5["empty_evidence_refs"] += 1
            t5_cases["empty_evidence_refs"].append(cid)
        if cc.get("customer_unique_id") is None:
            t5["customer_unique_id_null"] += 1
            t5_cases["customer_unique_id_null"].append(cid)
        for k in ("captured_total_brl", "refunded_total_brl", "refundable_total_brl"):
            if pa.get(k) is None:
                t5[f"payment_null_{k}"] += 1
                t5_cases[f"payment_null_{k}"].append(cid)
        for k in ("order_ids", "item_ids", "seller_ids", "payment_references", "shipment_ids"):
            if not ae.get(k):
                t5[f"affected_empty_{k}"] += 1
                t5_cases[f"affected_empty_{k}"].append(cid)
        if not o.get("claim_assessments"):
            t5["empty_claim_assessments"] += 1
            t5_cases["empty_claim_assessments"].append(cid)
        for i, c in enumerate(o.get("claim_assessments") or []):
            if not c.get("evidence_refs"):
                t5["claim_with_empty_evidence"] += 1
                t5_cases["claim_with_empty_evidence"].append(cid)
        if not rc.get("ranked_causes"):
            t5["empty_ranked_causes"] += 1
            t5_cases["empty_ranked_causes"].append(cid)
        if not rc.get("responsible_parties"):
            t5["empty_responsible_parties"] += 1
            t5_cases["empty_responsible_parties"].append(cid)
        for p in rc.get("responsible_parties") or []:
            if p.get("party_id") is None:
                t5["responsible_party_null_id"] += 1
                t5_cases["responsible_party_null_id"].append(cid)
        if not sa.get("timeline_complete"):
            t5["timeline_incomplete"] += 1
            t5_cases["timeline_incomplete"].append(cid)
        if not o.get("data_conflicts"):
            t5["no_data_conflicts"] += 1
            t5_cases["no_data_conflicts"].append(cid)
        # numeric types
        for k in ("captured_total_brl", "refunded_total_brl", "refundable_total_brl"):
            v = pa.get(k)
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                t5[f"payment_nonnumber_{k}"] += 1
                t5_cases[f"payment_nonnumber_{k}"].append(cid)

    print("\n=== TASK 4: consistency contradictions ===")
    if not findings:
        print("  none")
    for rule in sorted(findings):
        cs = findings[rule]
        print(f"\n  {rule}: {len(cs)} case(s)")
        for cid, msg in detail[rule][:12]:
            print(f"      {cid}: {msg}")
        if len(cs) > 12:
            print(f"      ... and {len(cs)-12} more: {sorted(set(cs))[:40]}")

    print("\n=== TASK 5: schema edge cases (semantic) ===")
    for k, n in t5.most_common():
        print(f"  {k}: {n}  e.g. {sorted(set(t5_cases[k]))[:8]}")

    # distribution of issue/status/verdict
    print("\n=== distributions ===")
    dist = collections.defaultdict(collections.Counter)
    for path in paths:
        o = json.loads(Path(path).read_text(encoding="utf-8"))
        dist["primary_issue"][o["assessment"]["primary_issue"]] += 1
        dist["case_status"][o["assessment"]["case_status"]] += 1
        dist["shipment_verdict"][o["shipment_analysis"]["verdict"]] += 1
        dist["payment_verdict"][o["payment_analysis"]["verdict"]] += 1
        dist["n_resolution_actions"][len(o.get("resolution_actions") or [])] += 1
        dist["n_refund_lines"][len(o["financial_resolution"]["refund_lines"])] += 1
        dist["party_types"][tuple(p["party_type"] for p in o["root_cause_analysis"]["responsible_parties"])] += 1
    for k, c in dist.items():
        print(f"  {k}: {dict(c)}")


if __name__ == "__main__":
    main()
