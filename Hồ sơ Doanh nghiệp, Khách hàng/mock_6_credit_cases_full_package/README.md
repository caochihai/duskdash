# MOCK BANK DATA — 6 HỒ SƠ TÍN DỤNG

Bộ dữ liệu dùng để test hệ thống Credit Risk / AML / Fraud.

## Hồ sơ
- CR-A01: doanh nghiệp tốt — APPROVE
- CR-B02: doanh nghiệp trung bình — CONDITIONAL_APPROVE
- CR-C03: doanh nghiệp thảm họa — REJECT_AND_ESCALATE
- CR-I01: cá nhân tốt — APPROVE
- CR-I02: cá nhân trung bình — CONDITIONAL_APPROVE
- CR-I03: cá nhân thảm họa — REJECT_AND_ESCALATE

## Cấu trúc mỗi hồ sơ
- `credit_case`
- `customer`
- `accounts`
- `monthly_features` — 12 tháng
- `representative_transactions` — mỗi giao dịch chứa:
  - transaction
  - accounts
  - parties
  - ledger_entries
  - status_history
  - channel_context
  - risk_assessment
  - reconciliation
  - document
  - audit_logs

## Quy ước
- Tiền là số nguyên VND.
- Mọi bản ghi có cờ `is_simulated=true` ở các lớp chính.
- Số tài khoản được token hóa/masked.
- Giao dịch chi tiết là mẫu đại diện; tổng hợp chuẩn nằm trong `monthly_features`.
- Không sử dụng cho nghiệp vụ thật hoặc xác minh danh tính.
