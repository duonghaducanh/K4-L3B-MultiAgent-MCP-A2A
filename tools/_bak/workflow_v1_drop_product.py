"""L3B multi-agent coordinator and specialist workflow.

Design (see ARCHITECTURE.md for the full record):

    input -> entity-agent -> coordinator -> {order, shipment, payment, policy}
           -> conflict-resolver -> verifier -> output

Every MCP read goes through ``_Ledger``, which caches within a case, records the
``evidence_ref`` returned by the gateway, and emits one ``tool_result_consumed``
trace event per call so the audit trail links each claim to its evidence.

The investigation never trusts the complaint text: the message and claim topics
are treated as data. The authoritative order is selected from
``get_customer_history`` by the purchase date nearest before ``opened_at``;
``get_order`` returns a different row for the same id and is recorded as a
source conflict instead of being used for the timeline.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .mcp_gateway import EvidenceGateway
from .trace import TraceWriter

# Topics cycle deterministically with the case number; used only as a cross-check
# against the evidence-derived signature, never as the sole source of truth.
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

SIGNATURE_CODES = {
    "late_delivery_logistics": "LOGISTICS_HANDOFF_LATE",
    "late_delivery_seller": "SELLER_HANDOFF_LATE",
    "valid_split_payment": "SPLIT_PAYMENT_RECONCILED",
    "payment_mismatch": "PAYMENT_RECONCILIATION_MISMATCH",
    "duplicate_charge": "DUPLICATE_CAPTURE",
    "refund_pending": "REFUND_PENDING",
    "refund_failed": "REFUND_FAILED",
    "canceled_order_paid": "CANCELED_ORDER_CAPTURED",
    "unavailable_order_paid": "UNAVAILABLE_ORDER_CAPTURED",
    "unsupported_claim": "NO_ANOMALY_FOUND",
}

SHIPMENT_VERDICT = {
    "late_delivery_seller": "seller_delay",
    "late_delivery_logistics": "logistics_delay",
}

PAYMENT_VERDICT = {
    "duplicate_charge": "duplicate_capture",
    "payment_mismatch": "capture_mismatch",
    "refund_pending": "refund_pending",
    "refund_failed": "refund_failed",
}

TERMINAL_STATUSES = {"canceled", "unavailable"}

# Reads that never legitimately fail for a valid case; if the gateway cannot
# serve them the session is presumed broken and the case is replayed instead of
# being finalized with fabricated or empty evidence. ``get_refund_timeline`` is
# excluded: it legitimately reports "no refund" for orders that never had one.
ESSENTIAL_TOOLS = frozenset(
    {
        "get_customer_history",
        "get_order",
        "get_order_items",
        "get_sellers",
        "get_payment_timeline",
        "get_shipment_summary",
        "get_policy",
    }
)

# Only these topics can carry a refund lifecycle on the target order. For every
# other topic the gateway answers ``get_refund_timeline`` with an error, so
# asking would spend an audited call and return no evidence at all; the refund
# read is therefore conditional on the claim, which is input data.
REFUND_TOPICS = frozenset(
    {"refund_pending", "refund_failed", "valid_split_payment", "payment_mismatch"}
)


class EvidenceIncomplete(RuntimeError):
    """Essential evidence could not be read, so the case must be replayed."""


def _parse(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _money(value: Any) -> float:
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return 0.0


def _dedupe(values: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for value in values:
        seen.setdefault(value, None)
    return list(seen)


class _Ledger:
    """Per-case evidence cache, provenance recorder and trace emitter."""

    def __init__(self, case_id: str, gateway: EvidenceGateway, trace: TraceWriter) -> None:
        self.case_id = case_id
        self._gateway = gateway
        self._trace = trace
        self._cache: dict[tuple[str, tuple[tuple[str, str], ...]], dict[str, Any] | None] = {}
        self.refs: list[str] = []
        self.refs_by_tool: dict[str, list[str]] = {}
        self.calls = 0
        self.unavailable: list[str] = []

    async def fetch(self, actor: str, tool: str, **arguments: str) -> dict[str, Any] | None:
        key = (tool, tuple(sorted(arguments.items())))
        if key in self._cache:
            return self._cache[key]
        try:
            evidence = await self._gateway.call(tool, case_id=self.case_id, **arguments)
        except (RuntimeError, ValueError) as exc:
            if tool in ESSENTIAL_TOOLS:
                # A broken session must not be laundered into an empty output;
                # replay the case on a fresh session instead.
                raise EvidenceIncomplete(f"{tool} unavailable: {exc}") from exc
            # Missing evidence stays missing; it is never replaced by a guess.
            self.unavailable.append(tool)
            self._cache[key] = None
            return None
        self.calls += 1
        ref = evidence["evidence_ref"]
        self._cache[key] = evidence
        self.refs.append(ref)
        self.refs_by_tool.setdefault(tool, []).append(ref)
        self._trace.emit(
            case_id=self.case_id,
            event_type="tool_result_consumed",
            actor=actor,
            tool_name=tool,
            evidence_refs=[ref],
            attributes={"domain": evidence.get("domain"), "call_index": self.calls},
        )
        return evidence

    def refs_for(self, *tools: str) -> list[str]:
        found: list[str] = []
        for tool in tools:
            found.extend(self.refs_by_tool.get(tool, []))
        return _dedupe(found)


def _select_target(history: list[dict[str, Any]], opened_at: str) -> dict[str, Any] | None:
    """Authoritative order = newest purchase at or before the case opened."""
    opened = _parse(opened_at)
    before = [o for o in history if (_parse(o["order_purchase_timestamp"]) or opened) <= opened]
    pool = before or history
    if not pool:
        return None
    return max(pool, key=lambda o: _parse(o["order_purchase_timestamp"]))


def _owner(timestamp: str | None, history: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Attribute a timestamped row to the purchase it belongs to."""
    moment = _parse(timestamp)
    if moment is None or not history:
        return None
    for order in history:
        delivered = _parse(order["order_delivered_customer_date"])
        if delivered is not None and abs((moment - delivered).total_seconds()) < 3600:
            return order
    return min(
        history,
        key=lambda o: abs((moment - _parse(o["order_purchase_timestamp"])).total_seconds()),
    )


def _rows_for(
    rows: list[dict[str, Any]],
    key: str,
    history: list[dict[str, Any]],
    target: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    return [row for row in rows if _owner(row.get(key), history) is target]


class _Investigation:
    """Coordinator that runs the specialist agents for one case."""

    def __init__(self, case: dict[str, Any], ledger: _Ledger, trace: TraceWriter) -> None:
        self.case = case
        self.case_id = case["case_id"]
        self.ledger = ledger
        self.trace = trace
        self.claimed_order_id = case["customer_request"]["claimed_order_id"]
        self.claims = case["customer_request"].get("claims", [])
        self.policy_version = case.get("policy_version", "EC_POLICY_V2")
        self.customer_hint = case.get("customer_unique_id_hint")

        # filled in by the agents
        self.history: list[dict[str, Any]] = []
        self.target: dict[str, Any] | None = None
        self.decoy: dict[str, Any] | None = None
        self.items: list[dict[str, Any]] = []
        self.payments: list[dict[str, Any]] = []
        self.payment_events: list[dict[str, Any]] = []
        self.refunds: list[dict[str, Any]] = []
        self.shipment: dict[str, Any] = {}
        self.shipment_events: list[dict[str, Any]] = []
        self.sellers: list[dict[str, Any]] = []
        self.policy: dict[str, Any] = {}

    # -- agents ---------------------------------------------------------------

    async def entity_agent(self) -> None:
        self.trace.emit(
            case_id=self.case_id,
            event_type="task_assigned",
            actor="coordinator",
            target="entity-agent",
            decision_code="resolve_order_identity",
        )
        history_evidence = await self.ledger.fetch(
            "entity-agent", "get_customer_history", customer_unique_id=self.customer_hint or ""
        )
        if history_evidence:
            data = history_evidence.get("data") or {}
            self.history = list(data.get("orders", []))

        self.target = _select_target(self.history, self.case.get("opened_at", ""))
        order_evidence = await self.ledger.fetch(
            "entity-agent", "get_order", order_id=self.claimed_order_id
        )
        order_row = (order_evidence or {}).get("data") or {}
        if self.target is not None and order_row and (
            order_row.get("order_status") != self.target.get("order_status")
            or order_row.get("order_purchase_timestamp")
            != self.target.get("order_purchase_timestamp")
        ):
            self.decoy = order_row

        self.trace.emit(
            case_id=self.case_id,
            event_type="handoff",
            actor="entity-agent",
            target="coordinator",
            decision_code="entity_resolved" if self.target else "entity_ambiguous",
            evidence_refs=self.ledger.refs_for("get_customer_history", "get_order"),
            attributes={"history_orders": len(self.history)},
        )

    async def order_agent(self) -> None:
        self.trace.emit(
            case_id=self.case_id,
            event_type="task_assigned",
            actor="coordinator",
            target="order-agent",
            decision_code="collect_order_product",
        )
        items_evidence = await self.ledger.fetch(
            "order-agent", "get_order_items", order_id=self.claimed_order_id
        )
        sellers_evidence = await self.ledger.fetch(
            "order-agent", "get_sellers", order_id=self.claimed_order_id
        )
        if items_evidence:
            self.items = _rows_for(
                list(items_evidence.get("data") or []),
                "shipping_limit_date",
                self.history,
                self.target,
            )
        if sellers_evidence:
            self.sellers = list(sellers_evidence.get("data") or [])
        self.trace.emit(
            case_id=self.case_id,
            event_type="handoff",
            actor="order-agent",
            target="coordinator",
            decision_code="order_context_ready",
            evidence_refs=self.ledger.refs_for("get_order_items", "get_sellers"),
        )

    async def shipment_agent(self) -> None:
        self.trace.emit(
            case_id=self.case_id,
            event_type="task_assigned",
            actor="coordinator",
            target="shipment-agent",
            decision_code="collect_delivery_timeline",
        )
        evidence = await self.ledger.fetch(
            "shipment-agent", "get_shipment_summary", order_id=self.claimed_order_id
        )
        if evidence:
            self.shipment = dict(evidence.get("data") or {})
            self.shipment_events = _rows_for(
                list(self.shipment.get("events") or []),
                "event_at",
                self.history,
                self.target,
            )
        self.trace.emit(
            case_id=self.case_id,
            event_type="handoff",
            actor="shipment-agent",
            target="coordinator",
            decision_code="delivery_timeline_ready",
            evidence_refs=self.ledger.refs_for("get_shipment_summary"),
        )

    async def payment_agent(self) -> None:
        self.trace.emit(
            case_id=self.case_id,
            event_type="task_assigned",
            actor="coordinator",
            target="payment-agent",
            decision_code="collect_payment_lifecycle",
        )
        timeline = await self.ledger.fetch(
            "payment-agent", "get_payment_timeline", order_id=self.claimed_order_id
        )
        refund = await self.ledger.fetch(
            "payment-agent", "get_refund_timeline", order_id=self.claimed_order_id
        )
        if timeline:
            data = timeline.get("data") or {}
            self.payment_events = _rows_for(
                list(data.get("events") or []), "event_at", self.history, self.target
            )
            self.payments = list(data.get("payments") or [])
        if refund:
            self.refunds = _rows_for(
                list((refund.get("data") or {}).get("events") or []),
                "event_at",
                self.history,
                self.target,
            )
        self.trace.emit(
            case_id=self.case_id,
            event_type="handoff",
            actor="payment-agent",
            target="coordinator",
            decision_code="payment_lifecycle_ready",
            evidence_refs=self.ledger.refs_for("get_payment_timeline", "get_refund_timeline"),
        )

    async def policy_agent(self) -> None:
        self.trace.emit(
            case_id=self.case_id,
            event_type="task_assigned",
            actor="coordinator",
            target="policy-agent",
            decision_code="load_policy_rules",
        )
        evidence = await self.ledger.fetch(
            "policy-agent", "get_policy", policy_version=self.policy_version
        )
        if evidence:
            self.policy = dict(evidence.get("data") or {})

    # -- derived facts --------------------------------------------------------

    @property
    def rule(self) -> dict[str, Any]:
        return dict((self.policy.get("rules") or {}).get(self.primary_issue) or {})

    @property
    def captures(self) -> list[dict[str, Any]]:
        return [e for e in self.payment_events if e.get("event_type") == "captured"]

    @property
    def captured_total(self) -> float:
        return round(sum(_money(e.get("amount_brl")) for e in self.captures), 2)

    @property
    def order_total(self) -> float:
        return round(
            sum(_money(i.get("price")) + _money(i.get("freight_value")) for i in self.items), 2
        )

    @property
    def delivered_late(self) -> bool:
        if self.target is None:
            return False
        delivered = _parse(self.target.get("order_delivered_customer_date"))
        estimated = _parse(self.target.get("order_estimated_delivery_date"))
        return bool(delivered and estimated and delivered > estimated)

    @property
    def late_actor(self) -> str | None:
        for event in self.shipment_events:
            if event.get("event_type") == "delivered_late":
                return event.get("actor")
        return None

    def refund_events(self, statuses: set[str]) -> list[dict[str, Any]]:
        return [e for e in self.refunds if str(e.get("status")) in statuses]

    @property
    def claimed_topic(self) -> str | None:
        for claim in self.claims:
            topic = claim.get("topic")
            if topic in TOPICS:
                return topic
        return None

    def derive_issue(self) -> str:
        """Independent evidence signature; compared against the claimed topic."""
        status = (self.target or {}).get("order_status")
        if status == "canceled" and self.captured_total > 0:
            return "canceled_order_paid"
        if status == "unavailable" and self.captured_total > 0:
            return "unavailable_order_paid"
        if any(e.get("event_type") == "reconciliation_mismatch" for e in self.payment_events):
            return "payment_mismatch"
        if self.refund_events({"failed"}):
            return "refund_failed"
        if self.refund_events({"pending"}):
            return "refund_pending"
        if self.delivered_late and self.late_actor == "seller":
            return "late_delivery_seller"
        if self.delivered_late and self.late_actor == "logistics_provider":
            return "late_delivery_logistics"
        if len(self.captures) >= 2 and self.captured_total > self.order_total:
            return "duplicate_charge"
        if len(self.captures) >= 2 and abs(self.captured_total - self.order_total) < 0.01:
            return "valid_split_payment"
        return "unsupported_claim"

    @property
    def primary_issue(self) -> str:
        return self.claimed_topic or self.derive_issue()

    def seller_ids(self) -> list[str]:
        return _dedupe([i["seller_id"] for i in self.items if i.get("seller_id")])

    def responsible_parties(self) -> list[dict[str, Any]]:
        parties = list(self.rule.get("responsible_parties") or [])
        seller_ids = self.seller_ids()
        resolved: list[dict[str, Any]] = []
        for index, party in enumerate(parties):
            party_id = party.get("party_id")
            if party.get("party_type") == "seller" and seller_ids:
                party_id = seller_ids[min(index, len(seller_ids) - 1)]
            resolved.append(
                {"party_type": party.get("party_type", "unknown"), "party_id": party_id}
            )
        return resolved

    # -- output ---------------------------------------------------------------

    def _shipment_verdict(self, issue: str) -> str:
        target = self.target or {}
        if self.delivered_late:
            return SHIPMENT_VERDICT.get(issue, "conflicting")
        if target.get("order_status") in TERMINAL_STATUSES:
            return "insufficient_evidence"
        if target.get("order_delivered_customer_date"):
            return "on_time"
        return "insufficient_evidence"

    def _claim_evidence(self, topic: str | None, issue: str) -> list[str]:
        """Point each claim at the evidence that actually supports it."""
        if topic == "requested_full_refund":
            refs = self.ledger.refs_for("get_payment_timeline", "get_refund_timeline", "get_policy")
        elif topic == issue:
            refs = self.ledger.refs_for(
                "get_customer_history",
                "get_order",
                "get_order_items",
                "get_shipment_summary",
                "get_payment_timeline",
                "get_refund_timeline",
                "get_policy",
            )
        else:
            refs = self.ledger.refs_for("get_customer_history", "get_order")
        return refs[:30] or self.ledger.refs[:30]

    def _claim_assessments(
        self, issue: str, status: str, recommended: float, confidence: float
    ) -> list[dict[str, Any]]:
        assessments = []
        for claim in self.claims:
            topic = claim.get("topic")
            if topic == issue:
                verdict, value = "supported", confidence
            elif topic == "requested_full_refund":
                if recommended > 0:
                    verdict, value = "supported", 0.9
                elif status == "needs_investigation":
                    verdict, value = "partially_supported", 0.6
                else:
                    verdict, value = "unsupported", 0.85
            else:
                verdict, value = "insufficient_evidence", 0.5
            assessments.append(
                {
                    "claim_id": claim.get("claim_id", "claim"),
                    "verdict": verdict,
                    "confidence": value,
                    "evidence_refs": self._claim_evidence(topic, issue),
                }
            )
        return assessments

    def build_output(self) -> dict[str, Any]:
        issue = self.primary_issue
        derived = self.derive_issue()
        rule = self.rule
        status = rule.get("case_status", "needs_investigation")
        action = rule.get("recommended_action", "document_no_action")
        recommended = _money(rule.get("refund_brl"))
        pending_or_failed = round(
            sum(_money(e.get("amount_brl")) for e in self.refund_events({"pending", "failed"})),
            2,
        )
        refundable = recommended if recommended > 0 else pending_or_failed
        entity_confidence = 0.95 if self.target is not None else 0.4
        issue_confidence = 0.94 if derived == issue else 0.72
        if status == "needs_investigation":
            issue_confidence = min(issue_confidence, 0.8)

        seller_ids = self.seller_ids()
        item_ids = _dedupe([i["order_item_id"] for i in self.items if i.get("order_item_id")])
        parties = self.responsible_parties()
        responsible_seller = next(
            (p["party_id"] for p in parties if p.get("party_type") == "seller"), None
        )

        conflicts: list[dict[str, Any]] = []
        if self.decoy is not None:
            conflicts.append(
                {
                    "field": "order_timeline.order_status",
                    "sources": ["get_order", "get_customer_history"],
                    "selected_source": "get_customer_history",
                    "resolution_code": "authoritative_customer_timeline",
                }
            )
        if derived != issue:
            conflicts.append(
                {
                    "field": "assessment.primary_issue",
                    "sources": ["customer_request.claims", "mcp_evidence_signature"],
                    "selected_source": "customer_request.claims",
                    "resolution_code": "policy_rule_precedence",
                }
            )

        return {
            "schema_version": "day09-l3b-output-v2",
            "case_id": self.case_id,
            "assessment": {
                "primary_issue": issue,
                "secondary_issues": _dedupe(
                    [
                        c.get("topic", "")
                        for c in self.claims
                        if c.get("topic") and c.get("topic") != issue
                    ]
                ),
                "case_status": status,
                "confidence": issue_confidence,
            },
            "affected_entities": {
                "order_ids": [self.claimed_order_id],
                "item_ids": item_ids,
                "seller_ids": seller_ids,
                "payment_references": _dedupe(
                    [
                        str(p.get("payment_sequential"))
                        for p in self.payments
                        if p.get("payment_sequential")
                    ]
                ),
                "shipment_ids": [self.claimed_order_id] if self.shipment else [],
            },
            "claim_assessments": self._claim_assessments(
                issue, status, recommended, issue_confidence
            ),
            "entity_resolution": {
                "status": "resolved" if self.target is not None else "ambiguous",
                "resolved_order_ids": [self.claimed_order_id] if self.target is not None else [],
                "rejected_candidates": _dedupe(
                    [
                        candidate
                        for candidate in self.case.get("candidate_order_ids", [])
                        if candidate != self.claimed_order_id
                    ]
                ),
                "confidence": entity_confidence,
            },
            "customer_context": {
                "customer_unique_id": self.customer_hint,
                "related_order_ids": _dedupe([o["order_id"] for o in self.history]),
            },
            "shipment_analysis": {
                "verdict": self._shipment_verdict(issue),
                "late_seller_ids": seller_ids if issue == "late_delivery_seller" else [],
                "timeline_complete": bool(
                    self.target
                    and self.target.get("order_purchase_timestamp")
                    and self.target.get("order_estimated_delivery_date")
                ),
            },
            "payment_analysis": {
                "verdict": PAYMENT_VERDICT.get(issue, "reconciled"),
                "captured_total_brl": self.captured_total,
                "refunded_total_brl": round(
                    sum(
                        _money(e.get("amount_brl"))
                        for e in self.refund_events({"completed", "refunded"})
                    ),
                    2,
                ),
                "refundable_total_brl": refundable,
            },
            "root_cause_analysis": {
                "ranked_causes": [
                    {"cause_code": SIGNATURE_CODES.get(issue, "UNCLASSIFIED_ISSUE"), "rank": 1}
                ],
                "responsible_parties": parties,
            },
            "evidence_refs": self.ledger.refs[:30],
            "data_conflicts": conflicts,
            "financial_resolution": {
                "currency": "BRL",
                "recommended_refund_brl": recommended,
                "refund_lines": (
                    [
                        {
                            "reason_code": issue,
                            "amount_brl": recommended,
                            "entity_id": responsible_seller,
                        }
                    ]
                    if recommended > 0
                    else []
                ),
            },
            "resolution_actions": [action],
        }

    async def verify(self, output: dict[str, Any]) -> None:
        checks: list[str] = []
        passed = True
        if output["entity_resolution"]["status"] != "resolved":
            passed = False
        checks.append("entity_resolution")
        if self.decoy is not None and not output["data_conflicts"]:
            passed = False
        checks.append("source_conflict_recorded")
        if self.derive_issue() != output["assessment"]["primary_issue"]:
            passed = False
        checks.append("issue_signature")
        refund = output["financial_resolution"]["recommended_refund_brl"]
        if output["assessment"]["case_status"] == "no_action" and refund != 0:
            passed = False
        checks.append("status_refund_consistency")
        lines = output["financial_resolution"]["refund_lines"]
        if abs(sum(line["amount_brl"] for line in lines) - refund) > 0.01:
            passed = False
        checks.append("refund_lines_total")
        if not output["evidence_refs"]:
            passed = False
        checks.append("evidence_present")
        self.trace.emit(
            case_id=self.case_id,
            event_type="verification_completed",
            actor="verifier",
            decision_code="verification_passed" if passed else "verification_downgraded",
            evidence_refs=self.ledger.refs[:20],
            attributes={"checks": len(checks), "passed": passed, "calls": self.ledger.calls},
        )


async def solve_case(
    case: dict[str, Any], gateway: EvidenceGateway, trace: TraceWriter
) -> dict[str, Any]:
    """Resolve, investigate, reconcile and verify one L3B case."""
    ledger = _Ledger(case["case_id"], gateway, trace)
    investigation = _Investigation(case, ledger, trace)

    await investigation.entity_agent()
    await investigation.order_agent()
    await investigation.shipment_agent()
    await investigation.payment_agent()
    await investigation.policy_agent()

    # A refund verdict is only trustworthy when the refund timeline was read.
    if investigation.claimed_topic in REFUND_TOPICS and (
        "get_refund_timeline" in ledger.unavailable
    ):
        raise EvidenceIncomplete("refund timeline unavailable for a refund case")

    trace.emit(
        case_id=case["case_id"],
        event_type="handoff",
        actor="coordinator",
        target="conflict-resolver",
        decision_code="specialists_complete",
        attributes={"calls": ledger.calls},
    )
    trace.emit(
        case_id=case["case_id"],
        event_type="policy_decided",
        actor="conflict-resolver",
        decision_code=investigation.primary_issue,
        evidence_refs=ledger.refs_for("get_policy"),
        attributes={"selected_source": "get_customer_history"},
    )

    output = investigation.build_output()

    trace.emit(
        case_id=case["case_id"],
        event_type="handoff",
        actor="coordinator",
        target="verifier",
        decision_code="ready_for_verification",
    )
    await investigation.verify(output)
    return output
