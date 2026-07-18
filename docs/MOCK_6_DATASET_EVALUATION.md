# Đánh giá gói `mock_6_credit_cases`

## Kết quả

Đã chạy deterministic compatibility test bằng
`C:\Users\Hieu\Downloads\mock_6_credit_cases_full_package\mock_6_credit_cases_full.json`.
Kết quả JSON local là `evaluation-results/mock_6_credit_cases_compatibility.json`
(đã gitignore để tránh đưa dữ liệu case vào repository).

| Hạng mục | Kết quả |
|---|---:|
| Tổng record | 6 |
| Hồ sơ SME/corporate trong phạm vi | 3 |
| Hồ sơ individual ngoài phạm vi | 3 |
| Decision của 3 hồ sơ corporate | `NEEDS_INFO` |
| Tool call | 1/case (chỉ policy gate) |
| Fail-closed | Pass |
| Chặn case ngoài phạm vi | Pass |
| Accuracy so với nhãn | Không thể đánh giá hợp lệ |

Ba case corporate (`CR-A01`, `CR-B02`, `CR-C03`) đều dừng ở policy gate với
`NEEDS_INFO: applicable active credit policy`. Đây là hành vi đúng của agent:
không có policy active/versioned thì không được suy luận sang
`READY_FOR_APPROVAL_REVIEW`, `PASS_WITH_CONDITIONS`, hay `NOT_RECOMMENDED`.
Ba case `CR-I01`–`CR-I03` là `INDIVIDUAL`, nên không được gửi vào SME Credit
Agent.

## Vì sao không có điểm accuracy

Nhãn trong gói là `APPROVE`, `CONDITIONAL_APPROVE`, `REJECT_AND_ESCALATE`,
nhưng gói không cung cấp các input bắt buộc trong contract của Credit Agent:

- policy tín dụng active, có version và threshold;
- facility-level limit/outstanding/utilization/maturity;
- DPD, restructuring và kỳ coverage của repayment history;
- báo cáo tài chính kỳ hiện tại/kỳ trước, audit status;
- ngày định giá và valuation status của collateral.

Không đưa label, recommended limit, AML/fraud outcome hay số tài chính tự suy
diễn vào agent. Vì vậy không có dự đoán credit hợp lệ để tính accuracy; việc
chấm một tỷ lệ % ở đây sẽ đánh lừa về chất lượng thật.

## Chạy lại

```powershell
py scripts/evaluate_mock_bank_package.py `
  --input C:\Users\Hieu\Downloads\mock_6_credit_cases_full_package\mock_6_credit_cases_full.json `
  --output evaluation-results\mock_6_credit_cases_compatibility.json
```

Khi có adapter cung cấp đủ 8 tool với policy thật và reference label đã chuẩn
hóa theo decision của agent, có thể mở rộng script để đo decision accuracy,
risk-flag precision/recall và latency theo tập case.
