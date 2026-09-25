# L3B Architecture Record

Team phải cập nhật tài liệu này cùng source. Mục tiêu là mô tả quyết định có thể kiểm chứng, không ghi prompt bí mật hoặc chain-of-thought.

## 1. System overview

Vẽ hoặc mô tả luồng từ input/candidate resolution đến MCP investigation, specialist agents, conflict resolver, verifier, output và trace.

```text
Input → Entity Resolver → Coordinator → Specialists → Conflict Resolver → Verifier → Output
            │                              │                  │             │
            └──────────────────────────── MCP ────────────────┴──────────── Trace
```

## 2. Agent ownership

| Actor | Input | Trách nhiệm | Tool permission | Output/handoff |
| --- | --- | --- | --- | --- |
| Entity/customer | claimed ID and customer hint | Resolve order against customer history | `get_order`, `get_customer_history` | resolution |
| Coordinator | case and handoffs | Assign bounded work and assemble evidence | routes only | output draft |
| Order/product | resolved order | Identify item and seller context | `get_order_items`, `get_product_context` | entities |
| Shipment | resolved order | Classify delivery timing | `get_shipment_summary` | shipment verdict |
| Payment/refund | resolved order | Reconcile payment totals | `get_payment_timeline` | payment verdict |
| Policy | issue and policy version | Select action, refund and party | `get_policy` | policy decision |
| Conflict resolver | specialist results | Preserve unresolved data | none | investigation state |
| Verifier | output draft | Validate evidence linkage and schema-facing fields | none | verification event |

Áp dụng least privilege; tool discovery không đồng nghĩa mọi actor đều được gọi mọi tool.

## 3. Entity resolution và A2A protocol

Mô tả cách xếp hạng/reject candidate, confidence threshold, message envelope, correlation theo `case_id`, điều kiện handoff, timeout và cách tránh vòng lặp. Không trace nội dung suy luận riêng.

## 4. Evidence và conflict lifecycle

Mô tả cách validate MCP response, lưu `evidence_ref`, chọn source theo policy, biểu diễn unresolved conflict, map evidence vào claim/output và emit `tool_result_consumed`. Evidence không được tái sử dụng giữa các case.

## 5. Failure and efficiency policy

| Failure | Retry budget | Fallback | Trace event/code |
| --- | ---: | --- | --- |
| MCP timeout/error | 0 automatic retries | Continue with missing evidence and lower confidence | no consumed-evidence event |
| Entity not found/ambiguous | 0 | `needs_investigation` with `investigate_entity` | entity handoff decision |
| Source conflict | 0 | Preserve the conflict and apply direct-order precedence | policy decision / conflict output |
| Invalid specialist result | 0 | Do not consume or cite it | no tool-consumed event |

Nêu query budget/cache strategy để tránh gọi lặp và quét rộng. Retry phải có giới hạn, idempotent và không biến missing evidence thành dữ liệu phỏng đoán.

## 6. Verification invariants

Liệt kê kiểm tra trước finalize: schema, entity scope, rejected candidates, evidence ownership, claim linkage, timeline, payment/refund totals, source precedence, responsibility/action consistency và confidence bounds.

## 7. Reproducibility

Ghi model/config, dependency pinning, concurrency limit, random seed (nếu có), lệnh chạy và giới hạn tài nguyên. Không ghi API key.
