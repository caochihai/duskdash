# Credit Agent — Tools và chức năng

## Vị trí trong workflow

```text
Planner → Plan Executor → Credit Agent → Validation → Human approval
```

Credit Agent là specialist cho SME credit renewal/review. Input là
`CreditTaskInputV1`; output thống nhất là `CreditAnalysisResultV1`, kể cả khi
dừng sớm do thiếu dữ liệu hoặc lỗi hệ thống.

## 8 read-only tools

| Tool | Dữ liệu trả về | Agent sử dụng để |
|---|---|---|
| `retrieve_credit_policy` | Policy, scope, ngưỡng, treatment, hiệu lực | Kiểm tra policy active/effective/applicable trước khi đọc hồ sơ khác. |
| `get_customer_360` | Segment, rating nội bộ, quan hệ với ngân hàng | Kiểm tra segment, độ mới của rating và relationship status. |
| `get_credit_facilities` | Hạn mức, dư nợ, utilization, facility theo product | Đối chiếu hạn mức/dư nợ/utilization và xác định facility khớp sản phẩm yêu cầu. |
| `get_repayment_history` | DPD, số lần trễ hạn, tái cơ cấu, kỳ quan sát | Phát hiện delinquency hoặc restructuring. |
| `get_transaction_summary` | Inflow/outflow, volatility, concentration, currency | Đánh giá cashflow, related-party flow và currency consistency. |
| `get_financial_statements` | Báo cáo hiện tại/kỳ trước, audit status | Kiểm tra freshness, báo cáo đủ kỳ và điều kiện audited. |
| `calculate_financial_metrics` | DSCR, leverage, liquidity, margins, working capital | Tính/đọc metric có formula, unit và input provenance. Chỉ gọi sau khi có báo cáo tài chính. |
| `get_collateral_snapshot` | Giá trị tài sản bảo đảm, IDs, coverage ratio/basis/denominator, valuation status | Chỉ gọi khi task yêu cầu collateral; đối chiếu ratio với eligible value/denominator, sau đó kiểm tra coverage/freshness/status theo policy. |

Các tool không được phép ghi dữ liệu, tạo facility, giải ngân hoặc phê duyệt.
Mỗi kết quả bị kiểm tra context binding (`task_id`, `case_id`, `customer_id`,
`as_of_date`) trước khi được dùng.

## Chức năng nghiệp vụ

- Đọc policy trước, xác thực policy có hiệu lực và phù hợp product/segment.
- Tổng hợp quan hệ khách hàng, facility, trả nợ, dòng tiền, báo cáo tài chính,
  metrics và collateral.
- Kiểm tra stale data, conflicting balances, currency mismatch, late payments,
  cash stress, concentration, rating/collateral status và policy threshold.
- Gắn evidence/source reference/tool run ID cho nhận định.
- Sinh policy citations, risk flags, conditions, missing information và tối đa
  5 câu hỏi follow-up có evidence.
- Trả một trong các decision: `READY_FOR_APPROVAL_REVIEW`,
  `PASS_WITH_CONDITIONS`, `NEEDS_INFO`, `MANUAL_REVIEW`,
  `NOT_RECOMMENDED`, `SYSTEM_EXCEPTION`.

## Cơ chế an toàn và kiểm soát

- Fail-closed khi thiếu scope, policy không hợp lệ, tool lỗi, context sai, data
  thiếu hoặc conflict trọng yếu.
- Tối đa 20 tool calls, deadline 30 giây, có per-tool timeout.
- Không có auto-approval: `human_approval_required=true` ở mọi output.
- Không tự sizing lại khoản vay: kết quả positive chỉ chuyển tiếp limit/tenor
  mà Supervisor yêu cầu.
- Production yêu cầu trusted scope resolver, record-level authorization và
  durable audit sink.

## Không làm trong MVP

- Không OCR/chấm chứng từ, AML/KYC/legal conclusion hoặc fraud investigation.
- Không thay thế underwriter/credit committee.
- Không ghi vào core banking/CRM, tạo hợp đồng, giải ngân hay thay đổi hạn mức.
- Không coi LLM judge hoặc fixture demo là policy/quyết định tín dụng thật.
