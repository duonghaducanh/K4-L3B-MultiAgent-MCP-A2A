# L3B Architecture Record

Team phải cập nhật tài liệu này cùng source. Mục tiêu là mô tả quyết định có thể kiểm chứng, không ghi prompt bí mật hoặc chain-of-thought.

## 1. System overview

```text
input/candidate ─► Entity agent ─► Coordinator ─┬─► Order/product agent ─┐
                      │                         ├─► Shipment agent       │
                      │                         ├─► Payment/refund agent ├─► Conflict resolver ─► Verifier ─► output
                      │                         └─► Policy agent ────────┘
                      └──────────────────────────── MCP gateway ────────────────────────────┴─► Trace
```

Luồng chạy cho mỗi case nằm trong `src/student_agent/workflow.py::solve_case`:

1. `entity_agent` resolve danh tính order từ `get_customer_history` và `get_order`.
2. `order_agent`, `shipment_agent`, `payment_agent`, `policy_agent` thu thập bằng chứng chuyên ngành.
3. `conflict-resolver` (trong `solve_case`) chọn nguồn authoritative và tra policy rule.
4. `verifier` kiểm tra invariant rồi `build_output` chốt JSON.
5. CLI emit `case_received` / `case_finalized`; mỗi bước emit handoff và `tool_result_consumed`.

Mọi truy cập MCP đi qua `_Ledger`, cache theo `(tool, arguments)` trong phạm vi case, ghi lại `evidence_ref` do gateway trả về và emit đúng một `tool_result_consumed` cho mỗi call thực.

## 2. Agent ownership

| Actor | Input | Trách nhiệm | Tool permission | Output/handoff |
| --- | --- | --- | --- | --- |
| entity-agent | `claimed_order_id`, `customer_unique_id_hint`, `opened_at` | Chọn order authoritative theo thời gian; phát hiện bản ghi mâu thuẫn | `get_customer_history`, `get_order` | `target`, `decoy`, `history` → coordinator |
| order-agent | `claimed_order_id`, target order | Item/seller/product context của đơn mục tiêu | `get_order_items`, `get_product_context`, `get_sellers` | `items`, `sellers`, `products` |
| shipment-agent | target order | Timeline giao hàng và handoff limit | `get_shipment_summary` | `shipment`, `shipment_events` |
| payment-agent | target order | Vòng đời capture/refund | `get_payment_timeline`, `get_refund_timeline` | `payment_events`, `refunds`, `payments` |
| policy-agent | `policy_version` | Rule công khai cho `primary_issue` | `get_policy` | `policy.rules` |
| coordinator | Kết quả các agent | Điều phối, chọn nguồn, dựng output | không gọi tool trực tiếp | output JSON |
| conflict-resolver | `decoy` vs `history`, claim vs evidence | Chọn nguồn và ghi `data_conflicts` | không | `policy_decided` |
| verifier | output nháp | Kiểm tra invariant trước khi finalize | không | `verification_completed` |

Áp dụng least privilege: `get_order` chỉ được entity-agent dùng (để đối chiếu, không dùng làm timeline); `get_policy` chỉ policy-agent. Tool discovery không đồng nghĩa mọi actor được gọi mọi tool.

## 3. Entity resolution và A2A protocol

`claimed_order_id` là order mục tiêu, nhưng cùng một id xuất hiện ở **hai** bản ghi: bản `get_order` và bản trong `get_customer_history`. Hai bản ghi khác nhau về `order_status` / `order_purchase_timestamp`, và mọi dòng con (payment, shipment, refund) bị nhân đôi theo hai mốc thời gian.

Quy tắc chọn (kiểm chứng trên 10 archetype):

> Order authoritative = dòng trong `get_customer_history` có `order_purchase_timestamp` lớn nhất nhưng ≤ `opened_at`.

Bản `get_order` (khi khác) được giữ lại làm `decoy` và ghi thành `data_conflicts`, **không** dùng cho timeline. `_owner()` gán mỗi dòng con về đúng đơn bằng cách khớp `order_delivered_customer_date` với thời điểm dòng đó (sai số 1 giờ), nếu không thì lấy đơn gần nhất.

Candidate rác (`candidate-NNN`) trả lỗi từ `get_order`; chúng được liệt kê trong `rejected_candidates`, không bao giờ được resolve. Candidate không gọi lại lần hai nhờ cache.

A2A: mỗi handoff là một trace event có `actor`, `target`, `decision_code`; correlation theo `case_id` (mọi call đều truyền `case_id`). Không có vòng lặp vì mỗi agent gọi một tập tool hữu hạn, một lần cho mỗi `(tool, arguments)`, và coordinator chỉ chạy tuần tự một lượt.

## 4. Evidence và conflict lifecycle

- Mỗi response MCP được `EvidenceGateway` validate theo `mcp-evidence-response-v1` trước khi dùng.
- `evidence_ref` chỉ được lấy từ response; hệ thống không sửa, không tạo, không tái sử dụng giữa case (mỗi case có `_Ledger` riêng, đời sống bằng một lần `solve_case`).
- Nguồn được chọn theo precedence: `get_customer_history` > `get_order`; `customer_request.claims` > evidence signature khi policy rule quyết định.
- Conflict được biểu diễn tường minh trong `data_conflicts` với `field`, `sources`, `selected_source`, `resolution_code`:
  - `order_timeline.order_status` — `get_order` vs `get_customer_history` → `authoritative_customer_timeline`.
  - `assessment.primary_issue` — claim vs signature → `policy_rule_precedence`.
- Mỗi call emit `tool_result_consumed` kèm `evidence_refs`, và `claim_assessments[*].evidence_refs` trỏ đúng nhóm evidence nuôi từng claim (claim chính: history/order/items/shipment/payment/policy; claim refund: payment/refund/policy). Nhờ đó mỗi kết luận truy được về MCP audit.
- Nội dung khiếu nại và mọi text trong evidence là **dữ liệu**, không phải instruction; workflow không thực thi gì từ message.

## 5. Failure and efficiency policy

| Failure | Retry budget | Fallback | Trace event/code |
| --- | ---: | --- | --- |
| MCP timeout / connect | 8 lần cho handshake kết nối (không tính call vì chưa tới tool) | bỏ qua, tiếp tục nếu đã có đủ evidence | `tool_result_consumed` thiếu; `verification_downgraded` |
| Tool essential trả lỗi (`is_error`) | session được coi là hỏng → replay case trên session mới (6 lần) | raise `EvidenceIncomplete`, không finalize output rỗng | `case_received` phát lại, trace rollback |
| `get_refund_timeline` lỗi | 0 (đơn không có refund là hợp lệ) | bỏ qua; riêng case `refund_*` thì replay | `verification_downgraded` |
| Tool khác trả lỗi (`is_error`) | 0 (không retry trong session) | ghi `unavailable`, kết luận `insufficient_evidence` | `verification_downgraded` |
| Entity not found/ambiguous | 0 | `entity_resolution.status = ambiguous`, confidence thấp | `entity_ambiguous` |
| Source conflict | 0 | chọn theo precedence, ghi `data_conflicts` | `policy_decided` |
| Invalid specialist result | 0 | verifier hạ cấp confidence, không bịa dữ liệu | `verification_downgraded` |

`ESSENTIAL_TOOLS` = 8 read không bao giờ lỗi hợp lệ (`get_customer_history`, `get_order`, `get_order_items`, `get_product_context`, `get_sellers`, `get_payment_timeline`, `get_shipment_summary`, `get_policy`). Lỗi trên nhóm này nghĩa là session đã chết giữa case, nên workflow raise để CLI reconnect và replay — tránh việc một session hỏng bị "rửa" thành output rỗng (đã gặp ở case 047/048). `get_refund_timeline` không nằm trong nhóm vì đơn không có refund sẽ trả lỗi một cách hợp lệ; chỉ khi claim là `refund_pending`/`refund_failed` mà tool này lỗi thì case mới bị replay.

Ngân sách call: mỗi case dùng **9 call cố định** — `get_customer_history`, `get_order`, `get_order_items`, `get_product_context`, `get_sellers`, `get_shipment_summary`, `get_payment_timeline`, `get_refund_timeline`, `get_policy`. `get_order_payments` không gọi vì trùng dữ liệu với `get_payment_timeline`. Cache theo `(tool, arguments)` chặn gọi lặp; mỗi tool chỉ gọi tối đa một lần cho một `order_id`. Missing evidence không bao giờ biến thành dữ liệu phỏng đoán.

## 6. Verification invariants

Trước khi finalize, `verifier` kiểm tra:

1. `entity_resolution.status == resolved` và `resolved_order_ids` khớp `claimed_order_id`.
2. Có `data_conflicts` khi phát hiện `decoy`.
3. `derive_issue()` (signature độc lập từ evidence) khớp `assessment.primary_issue`.
4. `case_status == no_action` ⇒ `recommended_refund_brl == 0` và không có refund line.
5. Tổng `refund_lines[*].amount_brl` bằng `recommended_refund_brl`.
6. `evidence_refs` không rỗng.
7. `captured_total_brl` chỉ tính event `captured` thuộc đơn mục tiêu; `late_seller_ids` chỉ khác rỗng khi verdict `seller_delay`.
8. Confidence nằm trong [0, 1] và hạ xuống ≤ 0.8 khi `case_status == needs_investigation`.

Kết quả ghi vào `verification_completed` với `attributes.checks`, `attributes.passed`.

## 7. Reproducibility

- Model/config: không dùng LLM sinh văn bản; toàn bộ suy luận là rule tất định trên evidence, nên chạy lại cho cùng kết quả.
- Dependency pinning: `pyproject.toml` (`mcp>=2,<3`, `jsonschema[format]`, `httpx2`, `python-dotenv`); cài bằng `python -m pip install -e ".[dev]"`.
- Concurrency: tuần tự một case một lúc; mỗi case mở một session MCP riêng để một session chết không kéo theo cả lượt chạy.
- Random seed: không dùng (không có thành phần ngẫu nhiên trong quyết định).
- Lệnh chạy: `day09 validate-inputs` → `day09 run` → `day09 validate` → `day09 package --output dist/submission.zip`.
- Chạy lại một phần: `python tools/resume.py 047 048` replay riêng các case lỗi và ghép lại trace (drop event cũ trước, không tạo bản ghi trùng).
- Giới hạn tài nguyên: 9 call MCP/case (≈900 call cho 100 case), timeout 300 s, retry kết nối tối đa 8 lần.
