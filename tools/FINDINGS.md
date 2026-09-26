# L3B — Findings from probing the MCP gateway (working notes)

Internal notes, not part of the submission.

## Tools (10)

| tool | args | domain | returns |
| --- | --- | --- | --- |
| get_order | order_id | order | one order row (POISONED — see conflict) |
| get_order_items | order_id | item | item/seller rows, `shipping_limit_date`, price, freight |
| get_order_payments | order_id | payment | payment rows |
| get_shipment_summary | order_id | shipment | carrier/customer/estimated dates, `shipping_limits[]`, `events[]` |
| get_sellers | order_id | seller | seller rows (city/state) |
| get_policy | policy_version | policy | full rules map for the version |
| get_customer_history | customer_unique_id | customer | customer orders (the authoritative timeline) |
| get_product_context | order_id | product | products + translated category |
| get_payment_timeline | order_id | payment | payments + lifecycle events (captured, reconciliation_mismatch) |
| get_refund_timeline | order_id | refund | refund lifecycle events |

`mcp` 2.2.0 uses snake_case: `is_error`, `structured_content`, `input_schema`. The starter's
`mcp_gateway.py` used camelCase and crashed on the first call — fixed.

## Case structure

- 100 cases; `inputs/L3B_CASE_NNN.json`, `case-set.json` at repo root.
- Each case: `opened_at`, `customer_request.claims[]` (one topic + `requested_full_refund`),
  `claimed_order_id` (32-hex, == target order id), `candidate_order_ids` (claimed + `candidate-NNN`
  which errors in `get_order` → reject), `policy_version`, `customer_unique_id_hint`.
- Topic cycles deterministically: `case N -> TOPICS[(N-1) % 10]`:
  1 late_delivery_logistics, 2 valid_split_payment, 3 payment_mismatch, 4 duplicate_charge,
  5 refund_pending, 6 refund_failed, 7 unsupported_claim, 8 canceled_order_paid,
  9 unavailable_order_paid, 10 late_delivery_seller.

## The core rule (verified on all 10 archetypes)

**Target order = the `get_customer_history` row with the greatest
`order_purchase_timestamp <= opened_at`.**

Every order id carries TWO rows (the target plus a decoy from another purchase). `get_order`
returns the DECOY row, while `get_customer_history` carries the authoritative one. This is the
planted source conflict; `get_customer_history` wins (it is consistent with `opened_at`).

Evidence rows for the target are the ones near the target purchase date (~±15 days); the decoy
rows (payments, shipping limits, refunds) sit near the other purchase date.

## Policy is the answer key

`get_policy` returns, per topic: `case_status`, `recommended_action`, `refund_brl`,
`responsible_parties[].party_type`. Values observed:

| topic | case_status | action | refund_brl | party_type |
| --- | --- | --- | ---: | --- |
| canceled_order_paid | action_required | issue_refund | 79.0 | platform |
| duplicate_charge | action_required | refund_duplicate_charge | 64.0 | payment_provider |
| late_delivery_logistics | action_required | refund_freight | 16.0 | logistics_provider |
| late_delivery_seller | action_required | refund_freight | 18.0 | seller |
| payment_mismatch | action_required | reconcile_payment | 35.0 | payment_provider |
| refund_failed | action_required | retry_refund | 52.0 | payment_provider |
| refund_pending | needs_investigation | monitor_refund | 0.0 | payment_provider |
| unavailable_order_paid | action_required | issue_refund | 89.0 | seller |
| unsupported_claim | no_action | document_no_action | 0.0 | customer |
| valid_split_payment | no_action | document_no_action | 0.0 | customer |

The template `party_id` for `late_delivery_seller` is a fixed placeholder, so the real seller id
must come from the target order's items.

## Per-topic evidence signature (target row)

| topic | signature |
| --- | --- |
| late_delivery_logistics | delivered > estimated, shipment event actor=logistics_provider |
| late_delivery_seller | delivered > estimated, shipment event actor=seller |
| valid_split_payment | >=2 captures summing to the order total, no mismatch |
| payment_mismatch | `reconciliation_mismatch` event (status open) |
| duplicate_charge | >=2 captures of the same amount at the same timestamp |
| refund_pending | refund_requested with status pending |
| refund_failed | refund_requested with status failed |
| canceled_order_paid | target order_status=canceled and captured > 0 |
| unavailable_order_paid | target order_status=unavailable and captured > 0 |
| unsupported_claim | target delivered on time / no anomaly |

## Call budget

9 calls per case is the minimum that covers the schema:
history, order, items, payment_timeline, shipment, refund, policy, product, sellers.
`get_order_payments` is redundant with `get_payment_timeline`.

---

# Reading the score (competition API)

The competition backend is a **FastAPI app behind Cloudflare Pages**, base
`https://n7-competition.pages.dev`. The real API surface is **`/api/v2/...`**;
the `/api/l3b/...` paths are the legacy v1 surface and mostly 404.

## OpenAPI is disabled

`/api/openapi.json`, `/openapi.json`, `/api/docs`, `/api/redoc`, `/docs`, `/redoc`
all return `404 {"detail":"Not Found"}`. The route list was recovered instead from
the frontend bundle `https://n7-competition.pages.dev/assets/index-BBesytlK.js`.

## Endpoints (confirmed live)

| method | path | returns |
| --- | --- | --- |
| GET | `/api/health` | `{"status":"ok"}` |
| GET | `/api/v2/me` | team_code, display_name, members, class_id, credential_id |
| GET | `/api/v2/me/submissions` | list: submission_id, status, variant_id, score, submitted_at |
| GET | `/api/v2/competitions` | list of `{variant_id, status, submission_quota, case_set_version}` |
| GET | `/api/v2/leaderboard/{variant}` | `{variant_id, generated_at, entries[]}` (no components) |
| **GET** | **`/api/v2/leaderboard/{variant}/teams/{team_code}`** | **full score + component breakdown** |
| POST | `/api/v2/submissions` | upload a submission |
| POST | `/api/v2/teams/register` | register |
| POST | `/api/v2/runs` | 405 on GET (exists) |
| GET | `/api/submissions/{id}` | legacy, 404 for our own ids |

`/api/l3b/submissions`, `/api/me/submissions`, `/api/team/submissions` are POST-only
(`GET` → `405`, `Allow: POST`). POST body schema (from the 422 validation error):
`class_id` (str), `student_last5` (str), `file` (multipart).

## The breakdown endpoint — this is the answer

```
GET /api/v2/leaderboard/l3b/teams/{team_code}
```

```json
{"rank":76,"team_code":"h209-02859","display_name":"Soopi","class_id":"H209",
 "score":45.9335,"submitted_at":"...",
 "components":{"semantic":46.8777,"evidence":43.8019,"mcp":48.6807,
   "consistency":48.6807,"schema":48.6807,"calibration":48.0389,
   "workflow":48.6807,"efficiency":23.4389},
 "weighted_components":{"semantic":18.7511,"evidence":6.5703,"mcp":7.3021,
   "consistency":4.8681,"schema":2.434,"calibration":2.4019,
   "workflow":2.434,"efficiency":1.1719},
 "hard_gate_count":23}
```

Note the key is **`mcp`**, not `provenance` (label "MCP provenance"). Weights are
semantic .40, evidence .15, mcp .15, consistency .10, schema .05, calibration .05,
workflow .05, efficiency .05 — `score` == sum of `weighted_components`.

`hard_gate_count` is public; the private score only appears after the competition
closes (per the UI: "Điểm private chỉ hiển thị sau khi competition kết thúc").

## Tooling

`tools/score.py` reads it: `./.venv/Scripts/python.exe tools/score.py [--top N] [--team <code>]`.
Use `httpx2` (installed) — plain `httpx` is **not** in the venv.

