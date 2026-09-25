# L3B Architecture Record

Tài liệu này mô tả quyết định thiết kế kiến trúc, phân quyền tác tử, cơ chế phân giải thực thể, quản lý vòng đời bằng chứng và các ràng buộc bất biến (invariants) cho hệ thống điều tra tranh chấp thương mại điện tử Day09 L3B.

## 1. System overview

Luồng điều tra đi theo mô hình hướng đồ thị có hướng (DAG), phân chia rõ ranh giới trách nhiệm giữa các Specialist Agents, giao tiếp qua Agent-to-Agent (A2A) protocol và kiểm soát nghiêm ngặt thẩm quyền truy vấn MCP Evidence Gateway:

```text
Input (Case JSON)
       │
       ▼
┌──────────────┐      task_assigned
│ Coordinator  ├───────────────────────┐
└──────┬───────┘                       │
       │                               ▼
       │ handoff             ┌──────────────────┐
       │                     │ Entity Resolver  │ ◄─── MCP (get_customer_history, get_order)
       │                     └─────────┬────────┘
       │                               │ handoff
       ▼                               ▼
┌────────────────────────────────────────────────────────┐
│                   Specialist Agents                    │
│  ├─ Order & Product Specialist (get_order_items, ...)  │ ◄─── MCP Gateway
│  ├─ Shipment Specialist (get_shipment_summary)         │      (Audited Evidence)
│  └─ Payment/Refund Specialist (get_order_payments, ...)│
└──────────────────────────┬─────────────────────────────┘
                           │ handoff
                           ▼
┌────────────────────────────────────────────────────────┐
│             Policy & Conflict Resolver                 │ ◄─── MCP (get_policy)
│  ├─ Data Conflict Detection (Carrier vs Claim)         │
│  ├─ Primary/Secondary Issue & Responsibility Mapping   │
│  └─ Financial Resolution & Action Formulation          │
└──────────────────────────┬─────────────────────────────┘
                           │ handoff
                           ▼
┌────────────────────────────────────────────────────────┐
│                    Verifier Agent                      │
│  ├─ Cross-field Consistency Checks                     │
│  ├─ Confidence Calibration & Schema Validation         │
│  └─ Verification Completed Event                       │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
              Validated Output & Trace Logs

```

* **Trace Audit Trail**: Mọi quyết định và tương tác công cụ đều được ghi nhận thời gian thực vào `traces/trace.jsonl` theo chuẩn `trace-event-v1.schema.json`.
* **In-Case Cache & Efficiency**: Toàn bộ dữ liệu trích xuất từ MCP Gateway được lưu tạm trong phạm vi từng case để tối ưu điểm hiệu quả (`efficiency`).

---

## 2. Agent ownership

Áp dụng nguyên tắc đặc quyền tối thiểu (Least Privilege). Việc phát hiện công cụ (tool discovery) không đồng nghĩa mọi agent đều được quyền gọi mọi tool:

| Actor | Input | Trách nhiệm | Tool permission | Output / handoff |
| --- | --- | --- | --- | --- |
| **Coordinator** | `case` object từ `inputs/<case_id>.json` | Quản lý vòng đời điều tra, kích hoạt Entity Resolver, điều phối handoff giữa các pha | Không gọi tool MCP trực tiếp (chỉ Discovery) | Phát `case_received`, `task_assigned` cho Entity Agent, `case_finalized` |
| **Entity / customer** | `claimed_order_id`, `candidate_order_ids`, `customer_unique_id_hint` | Phân giải thực thể (Entity Resolution), đối chiếu lịch sử khách hàng, xếp hạng và loại bỏ candidate giả mạo | `get_customer_history`, `get_order` | `entity_resolution`, `customer_context`, handoff sang Specialist Agents |
| **Order / product** | `resolved_order_ids`, `investigation_scope` | Trích xuất danh sách sản phẩm, giá bán, thời hạn giao hàng cam kết (`shipping_limit_date`), ngữ cảnh mặt hàng | `get_order_items`, `get_product_context`, `get_sellers` | `affected_entities.item_ids`, `affected_entities.seller_ids` |
| **Shipment** | `resolved_order_id`, `shipping_limit_date` | Đối soát hành trình vận chuyển, so sánh mốc giao hàng thực tế với lịch hẹn (`estimated_delivery`) và hạn gửi của seller | `get_shipment_summary` | `shipment_analysis` (`verdict`, `late_seller_ids`, `timeline_complete`) |
| **Payment / refund** | `resolved_order_id` | Đối soát dòng tiền thu (`captured_total_brl`), phát hiện thanh toán trùng lặp (`duplicate_capture`), kiểm tra lịch sử hoàn trả | `get_order_payments`, `get_payment_timeline`, `get_refund_timeline` | `payment_analysis` (`verdict`, captured/refunded/refundable totals) |
| **Policy** | Kết quả từ các Specialist Agents, `claims`, `policy_version` | Áp dụng chính sách trọng tài, phân định mã lỗi cốt lõi (`primary_issue`), quy trách nhiệm (`responsible_parties`), tính tiền hoàn (`financial_resolution`) | `get_policy` | Dự thảo đánh giá, `policy_decided`, handoff sang Verifier |
| **Conflict resolver** | Tuyên bố của khách hàng (`claims`) đối chiếu với dữ liệu thẩm quyền từ MCP | Phát hiện mâu thuẫn giữa lời khai khách hàng và dữ liệu hệ thống/vận chuyển, chọn nguồn có thẩm quyền cao hơn | Không gọi tool (phân tích chéo trên bằng chứng đã thu thập) | Mảng `data_conflicts` ghi rõ trường xung đột, nguồn và resolution code |
| **Verifier** | Toàn bộ dự thảo output, danh sách `evidence_refs`, trace audit | Kiểm tra tính nhất quán chéo (Invariants), hiệu chuẩn confidence, xác thực JSON Schema trước khi xuất bản | Không gọi tool | `verification_completed` event, tệp `outputs/<case_id>.json` |

---

## 3. Entity resolution và A2A protocol

### Cơ chế xếp hạng và loại trừ Candidate:

1. **Đối chiếu lịch sử khách hàng (Contextual Lookup)**: Nếu có `customer_unique_id_hint`, truy vấn `get_customer_history` để lấy danh sách các đơn hàng thực tế của khách hàng.
2. **Xếp hạng mức độ ưu tiên (Candidate Ranking)**:
* *Ưu tiên 1*: Candidate trùng với `claimed_order_id` đồng thời xuất hiện trong `customer_history`.
* *Ưu tiên 2*: Candidate trùng với `claimed_order_id` hoặc nằm trong `customer_history`.
* *Ưu tiên 3*: Các candidate còn lại trong `candidate_order_ids`.


3. **Thẩm định thực thể (Verification)**:
* Duyệt tuần tự theo mức độ ưu tiên và gọi `get_order(order_id=candidate)`.
* Candidate đầu tiên trả về dữ liệu đơn hàng hợp lệ sẽ được chấp thuận đưa vào `resolved_order_ids`.
* Toàn bộ candidate còn lại bị đưa vào `rejected_candidates`.
* Nếu không có candidate nào hợp lệ: gán trạng thái `not_found`, `resolved_order_ids = []`, toàn bộ candidate chuyển thành `rejected_candidates`.


4. **Ngưỡng tin cậy (Confidence Threshold)**:
* Gán `0.95` nếu đơn hàng được xác thực và khớp với lịch sử khách hàng.
* Gán `0.85` nếu đơn hàng được xác thực nhưng không có dữ liệu lịch sử đối chiếu.
* Gán `0.50` nếu rơi vào trạng thái `not_found` hoặc thông tin mâu thuẫn/ambiguous.



### Giao thức A2A và Ngăn ngừa Vòng lặp:

* **Pipeline cấu trúc tuyến tính một chiều (DAG)**: Không sử dụng phản hồi lặp vô tận (no circular loops). Các agent giao tiếp qua state dict có cấu trúc.
* **Trace Audit**: Tuyệt đối không ghi chain-of-thought hay prompt nội bộ vào trace log; chỉ phát sinh các sự kiện trạng thái observable (`task_assigned`, `handoff`, `policy_decided`, `verification_completed`) tương thích `trace-event-v1.schema.json`.

---

## 4. Evidence và conflict lifecycle

1. **Thẩm định Envelope từ MCP**:
* Mọi phản hồi từ `gateway.call` đều được kiểm tra tính hợp lệ qua schema `mcp-evidence-response-v1.schema.json`.
* Trích xuất `evidence_ref` bắt buộc phải khớp regex `^ev_[A-Za-z0-9_-]{20,96}$`. Tuyệt đối không can thiệp, không sinh mã giả lập và không dùng chéo giữa các case.


2. **Nguyên tắc phân cấp thẩm quyền dữ liệu (Source Precedence)**:
* `Carrier / Logistics Tracking` & `Payment Gateway Audit` > `Order Database` > `Customer Claim Message`.


3. **Quản lý xung đột (Conflict Lifecycle)**:
* Khi khách hàng khiếu nại giao trễ nhưng tracking của đơn vị vận chuyển xác nhận giao đúng hẹn (hoặc trước `order_estimated_delivery_date`):
* Xác định xung đột trên trường `shipment_delivery_date`.
* Nguồn được chọn (`selected_source`): `carrier_shipment_summary`.
* Mã phân giải (`resolution_code`): `TRACKING_PROVES_ON_TIME`.
* Kết luận claim của khách hàng là `unsupported`.




4. **Phát sự kiện tiêu thụ bằng chứng**:
* Khi một agent trích xuất thông tin từ evidence để đưa vào kết luận, ngay lập tức phát sự kiện `tool_result_consumed` với định danh của actor đó kèm mảng `evidence_refs`.



---

## 5. Failure and efficiency policy

### Ma trận xử lý sự cố:

| Sự cố | Ngân sách Retry | Phương án Fallback | Trace Event / Code |
| --- | --- | --- | --- |
| **MCP timeout / HTTP 5xx** | 2 lần (exponential backoff 0.5s, 1.0s) | Bỏ qua endpoint lỗi, chuyển sang trạng thái `insufficient_evidence`, không tự suy đoán dữ liệu | `decision_code: MCP_TIMEOUT_FALLBACK` |
| **Entity not found / ambiguous** | 0 lần (đã duyệt cạn candidate) | Gán `entity_resolution.status = "not_found"`, `primary_issue = "insufficient_evidence"`, `case_status = "needs_investigation"` | `decision_code: ENTITY_NOT_RESOLVED` |
| **Source conflict** | 0 lần | Áp dụng ma trận ưu tiên thẩm quyền dữ liệu, ghi nhận `data_conflicts`, hạ điểm tin cậy `confidence` | `decision_code: CONFLICT_RESOLVED` |
| **Sai lệch cấu trúc specialist** | 1 lần | Chuẩn hóa về giá trị mặc định an toàn (`0.0`, rỗng `[]`), ngăn ngừa crash toàn pipeline | `decision_code: PARSE_FALLBACK` |

### Chiến lược tối ưu ngân sách gọi tool (Efficiency Budget):

* **Dynamic Tool Discovery**: Phân tích `inputSchema` của các công cụ MCP khi khởi tạo để truyền chính xác tên tham số, ngăn chặn hoàn toàn các lệnh gọi lỗi 400 Bad Request.
* **In-Case Evidence Cache**: Bộ nhớ đệm key-value theo cấu trúc `(tool_name, frozenset(args))` lưu trữ kết quả trong suốt vòng đời xử lý của từng case. Các agent tái sử dụng bằng chứng mà không cần gọi lại Gateway.
* **Truy vấn theo phạm vi (Scope-based Execution)**: Chỉ gọi `get_product_context` khi `investigation_scope.include_product_context == true`.

---

## 6. Verification invariants

Trước khi xuất bản tệp `outputs/<case_id>.json` và phát sự kiện `verification_completed`, Verifier Agent kiểm chứng nghiêm ngặt các điều kiện bất biến sau:

1. **Schema Compliance**: Đạt 100% kiểm tra hợp lệ của schema `day09-l3b-output-v2`.
2. **Entity Consistency**:
* `affected_entities.order_ids` phải đồng nhất với `entity_resolution.resolved_order_ids`.
* `rejected_candidates` không được chứa bất kỳ mã đơn hàng nào nằm trong `resolved_order_ids`.


3. **Evidence Provenance & Scope**:
* Tất cả các mã bằng chứng trong `assessment`, `claim_assessments`, `root_cause_analysis` phải nằm trong mảng `evidence_refs` tổng.
* 100% `evidence_refs` phải được phát sinh từ MCP Gateway trong chính case hiện tại và đã ghi nhận trong trace.


4. **Financial & Action Consistency**:
* Nếu `assessment.case_status == "no_action"`: Bắt buộc `recommended_refund_brl == 0.0` và `refund_lines` phải rỗng.
* Nếu `recommended_refund_brl > 0.0`: Bắt buộc `case_status == "action_required"` và tổng các dòng hoàn tiền trong `refund_lines` phải bằng đúng `recommended_refund_brl`.
* Mức hoàn tiền khuyến nghị không vượt quá số tiền có thể hoàn (`refundable_total_brl`), trừ trường hợp thu trùng tiền (`duplicate_charge`).


5. **Responsibility & Issue Alignment**:
* Lỗi `late_delivery_seller` hoặc `unavailable_order_paid`: Bên chịu trách nhiệm bắt buộc phải là `seller`.
* Lỗi `late_delivery_logistics`: Bên chịu trách nhiệm bắt buộc phải là `logistics_provider`.
* Lỗi `canceled_order_paid`: Bên chịu trách nhiệm là `platform`.
* Lỗi `unsupported_claim` hoặc `valid_split_payment`: Bên chịu trách nhiệm là `customer`.


6. **Confidence Calibration**: Điểm tin cậy nằm trong khoảng `[0.0, 1.0]`. Hạ confidence về `0.75` khi phát hiện xung đột dữ liệu và về `0.50` khi thiếu bằng chứng hoặc không giải quyết được thực thể.

---

## 7. Reproducibility

* **Môi trường & Ngôn ngữ**: Python 3.11+.
* **Dependencies**: Được cố định chính xác qua `pyproject.toml` (gồm `httpx2`, `mcp`, `jsonschema`, `referencing`, `pytest`).
* **Mô hình thực thi**: Hệ thống chuyên gia dựa trên luật và đối soát bằng chứng tất định (Deterministic Evidence-Driven Expert Workflow). Không sử dụng ngẫu nhiên seed hoặc phụ thuộc vào tính ngẫu nhiên của nhiệt độ LLM đối với việc ra quyết định tài chính.
* **Giới hạn luồng (Concurrency Limit)**: 1 worker tiến trình đảm bảo trace tuần tự, không nghẽn gateway.
* **Quy trình thực thi chuẩn hóa**:
```bash
day09 validate-inputs
day09 run
day09 validate
day09 package --output dist/submission.zip

```