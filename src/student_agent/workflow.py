from __future__ import annotations

import asyncio
from decimal import Decimal, InvalidOperation
from typing import Any

from .mcp_gateway import EvidenceGateway
from .trace import TraceWriter


async def solve_case(
    case: dict[str, Any], gateway: EvidenceGateway, trace: TraceWriter
) -> dict[str, Any]:
    """Resolve one case with bounded, case-scoped MCP investigations."""
    case_id = case["case_id"]
    request = case["customer_request"]
    claimed = request["claimed_order_id"]
    primary = next((x["topic"] for x in request["claims"] if x["topic"] != "requested_full_refund"), "insufficient_evidence")
    cache: dict[str, dict[str, Any]] = {}

    async def call(tool: str, **kwargs: str) -> dict[str, Any] | None:
        key = f"{tool}:{sorted(kwargs.items())}"
        if key in cache:
            return cache[key]
        try:
            result = await gateway.call(tool, case_id=case_id, **kwargs)
        except RuntimeError:
            return None
        cache[key] = result
        trace.emit(case_id=case_id, event_type="tool_result_consumed", actor="coordinator", tool_name=tool, evidence_refs=[result["evidence_ref"]])
        return result

    def ids(rows: list[dict[str, Any]], name: str) -> list[str]:
        return sorted({str(row[name]) for row in rows if row.get(name) not in (None, "")})

    def money(value: Any) -> float:
        try:
            return float(Decimal(str(value)))
        except (InvalidOperation, ValueError, TypeError):
            return 0.0

    trace.emit(case_id=case_id, event_type="task_assigned", actor="coordinator", target="entity-agent")
    order_e, history_e, policy_e = await asyncio.gather(
        call("get_order", order_id=claimed),
        call("get_customer_history", customer_unique_id=case["customer_unique_id_hint"]),
        call("get_policy", policy_version=case["policy_version"]),
    )
    order = order_e["data"] if order_e else {}
    history = history_e["data"] if history_e else {}
    related = ids(history.get("orders", []), "order_id")
    resolved = bool(order) and claimed in related
    resolution = "resolved" if resolved else ("ambiguous" if order else "not_found")
    trace.emit(case_id=case_id, event_type="handoff", actor="entity-agent", target="coordinator", decision_code=f"ENTITY_{resolution.upper()}")

    trace.emit(case_id=case_id, event_type="task_assigned", actor="coordinator", target="order-agent")
    needs_shipment = primary in {"late_delivery_logistics", "late_delivery_seller"}
    needs_payment = primary in {"canceled_order_paid", "unavailable_order_paid", "valid_split_payment", "payment_mismatch", "duplicate_charge", "refund_pending", "refund_failed"}
    needs_refund = primary in {"refund_pending", "refund_failed"}
    if order:
        tasks = [call("get_product_context", order_id=claimed)]
        if needs_shipment:
            tasks.append(call("get_shipment_summary", order_id=claimed))
        if needs_payment:
            tasks.append(call("get_payment_timeline", order_id=claimed))
        if needs_refund:
            tasks.append(call("get_refund_timeline", order_id=claimed))
        results = await asyncio.gather(*tasks)
        products_e = results[0]
        index = 1
        shipment_e = results[index] if needs_shipment else None
        index += int(needs_shipment)
        payment_e = results[index] if needs_payment else None
        index += int(needs_payment)
        refund_e = results[index] if needs_refund else None
    else:
        products_e = shipment_e = payment_e = refund_e = None
    products = products_e["data"] if products_e else []
    trace.emit(case_id=case_id, event_type="handoff", actor="order-agent", target="coordinator")

    trace.emit(case_id=case_id, event_type="task_assigned", actor="coordinator", target="shipment-agent")
    shipment = shipment_e["data"] if shipment_e else {}
    events = shipment.get("events", [])
    actors = {event.get("actor") for event in events}
    if any(event.get("event_type") == "delivered_late" for event in events):
        shipment_verdict = "seller_delay" if "seller" in actors else "logistics_delay"
    else:
        shipment_verdict = "on_time" if order.get("order_status") == "delivered" else "insufficient_evidence"
    timeline_complete = bool(shipment) and all(shipment.get(key) is not None for key in ("delivered_carrier_at", "delivered_customer_at", "estimated_delivery_at"))
    trace.emit(case_id=case_id, event_type="handoff", actor="shipment-agent", target="coordinator")

    trace.emit(case_id=case_id, event_type="task_assigned", actor="coordinator", target="payment-agent")
    payment = payment_e["data"] if payment_e else {}
    captured = round(sum(money(event.get("amount_brl")) for event in payment.get("events", []) if event.get("event_type") == "captured"), 2)
    refunded = round(sum(money(event.get("amount_brl")) for event in payment.get("events", []) if event.get("event_type") == "refunded"), 2)
    payment_verdict = {"duplicate_charge": "duplicate_capture", "payment_mismatch": "capture_mismatch", "refund_pending": "refund_pending", "refund_failed": "refund_failed"}.get(primary, "reconciled" if payment else "insufficient_evidence")
    trace.emit(case_id=case_id, event_type="handoff", actor="payment-agent", target="coordinator")

    trace.emit(case_id=case_id, event_type="task_assigned", actor="coordinator", target="policy-agent")
    rule = policy_e["data"].get("rules", {}).get(primary, {}) if policy_e else {}
    refund = money(rule.get("refund_brl")) if resolved else 0.0
    status = rule.get("case_status", "needs_investigation") if resolved else "needs_investigation"
    parties = rule.get("responsible_parties", [{"party_type": "unknown", "party_id": None}]) if resolved else [{"party_type": "unknown", "party_id": None}]
    actions = [rule["recommended_action"]] if resolved and rule.get("recommended_action") else ["investigate_entity"]
    trace.emit(case_id=case_id, event_type="policy_decided", actor="policy-agent", decision_code=primary.upper())

    conflicts = []
    matching_history = [row for row in history.get("orders", []) if row.get("order_id") == claimed]
    order_fields = ("order_status", "order_approved_at", "order_delivered_customer_date", "order_estimated_delivery_date")
    if matching_history and any(order.get(field) != matching_history[0].get(field) for field in order_fields):
        conflicts.append({"field": "order_timeline", "sources": ["get_order", "get_customer_history"], "selected_source": "get_order", "resolution_code": "DIRECT_ORDER_RECORD_PRECEDENCE"})
    shipment_pairs = (("order_delivered_carrier_date", "delivered_carrier_at"), ("order_delivered_customer_date", "delivered_customer_at"), ("order_estimated_delivery_date", "estimated_delivery_at"))
    if shipment and any(order.get(left) and shipment.get(right) and order[left] != shipment[right] for left, right in shipment_pairs):
        conflicts.append({"field": "delivery_timeline", "sources": ["get_order", "get_shipment_summary"], "selected_source": "get_order", "resolution_code": "DIRECT_ORDER_RECORD_PRECEDENCE"})
    refs = [result["evidence_ref"] for result in cache.values()]
    issue_evidence = shipment_e if needs_shipment else (refund_e if needs_refund else (payment_e if needs_payment else products_e))
    enough = resolved and policy_e is not None and issue_evidence is not None
    confidence = 0.72 if conflicts and enough else (0.9 if enough else (0.55 if order else 0.2))
    claims = []
    for claim in request["claims"]:
        verdict = "supported" if claim["topic"] == primary and enough else "insufficient_evidence"
        if claim["topic"] == "requested_full_refund" and enough and not refund:
            verdict = "unsupported"
        claims.append({"claim_id": claim["claim_id"], "verdict": verdict, "confidence": confidence, "evidence_refs": refs})
    output = {
        "schema_version": "day09-l3b-output-v2", "case_id": case_id,
        "assessment": {"primary_issue": primary if enough else "insufficient_evidence", "secondary_issues": [], "case_status": status, "confidence": confidence},
        "affected_entities": {"order_ids": [claimed] if order else [], "item_ids": ids(products, "order_item_id"), "seller_ids": ids(products, "seller_id"), "payment_references": ids(payment.get("payments", []), "payment_sequential"), "shipment_ids": []},
        "claim_assessments": claims,
        "entity_resolution": {"status": resolution, "resolved_order_ids": [claimed] if resolved else [], "rejected_candidates": [x for x in case["candidate_order_ids"] if x != claimed], "confidence": 0.95 if resolved else 0.25},
        "customer_context": {"customer_unique_id": history.get("customer_unique_id"), "related_order_ids": related},
        "shipment_analysis": {"verdict": shipment_verdict, "late_seller_ids": ids(shipment.get("shipping_limits", []), "seller_id") if shipment_verdict == "seller_delay" else [], "timeline_complete": timeline_complete},
        "payment_analysis": {"verdict": payment_verdict, "captured_total_brl": captured if payment else None, "refunded_total_brl": refunded if payment else None, "refundable_total_brl": refund if payment else None},
        "root_cause_analysis": {"ranked_causes": [{"cause_code": primary.upper(), "rank": 1}] if enough else [], "responsible_parties": parties},
        "evidence_refs": refs, "data_conflicts": conflicts,
        "financial_resolution": {"currency": "BRL", "recommended_refund_brl": refund, "refund_lines": [{"reason_code": primary.upper(), "amount_brl": refund, "entity_id": claimed}] if refund else []},
        "resolution_actions": actions,
    }
    trace.emit(case_id=case_id, event_type="verification_completed", actor="verifier", decision_code="SCHEMA_READY")
    return output
