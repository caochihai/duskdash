# Báo cáo ngắn — Microservice Credit Assessment v2

## Kết quả triển khai

Microservice đã được điều chỉnh đúng ranh giới mới:

```text
Tool tiếp nhận PDF/ảnh
  → Tool trích xuất text/dữ liệu
  → ExtractedCaseBundle v2
  → Credit Assessment Microservice
  → Finding có nguồn/trang
  → Policy & Action Registry
  → Hành động tiếp theo có căn cứ
```

Service không nhận hoặc xử lý PDF/ảnh. Đầu vào công khai chỉ còn `text`, `tables`,
`extracted_fields`, `extraction_confidence`, `quality_flag`, cùng metadata
`document_id`, tên file và số trang để truy vết.

## Đầu ra mới

Mỗi hành động trong `banker_view.action_plan.next_actions` có:

- Finding kích hoạt hành động.
- Người/bộ phận xử lý.
- Việc cần làm.
- Mức bắt buộc.
- Căn cứ pháp lý và link nguồn chính thức.
- Căn cứ policy nội bộ ngân hàng, nếu đã cung cấp.
- Bằng chứng cần kiểm tra.
- Điều kiện hoàn thành.
- Giai đoạn hồ sơ bị chặn.
- Rule ID, version và trạng thái hiệu lực.

LLM chỉ phát hiện/diễn giải finding. `Policy & Action Engine` quyết định hành động;
LLM không được tự đặt điều luật, người xử lý, SLA hoặc yêu cầu khách hàng.

Nếu thiếu policy nội bộ đủ `policy_id`, `version`, `effective_from` và `section`, hệ thống trả
`MANUAL_POLICY_REVIEW_REQUIRED`, giữ decision ở `PENDING` và không tự gửi yêu cầu cho khách hàng.

## Kết quả chạy một hồ sơ thật

Hồ sơ thử nghiệm: **Công ty Cổ phần Bao bì VinaNova**.

| Chỉ số | Kết quả |
|---|---:|
| Tài liệu/trang nhận từ upstream | 11/11 |
| Trang đã rà soát | 11/11 |
| Thời gian end-to-end | 272.029 giây |
| Lượt gọi GLM-5.2 | 6 |
| Tổng token | 86.094 |
| Finding | 9 |
| Grounding đầy đủ | 2 |
| Cần chuyên viên xác minh nguồn | 7 |
| Hành động sinh từ registry | 10 |
| Customer action được phép gửi | 0 |
| Decision | `PENDING` |
| Có thể trình phê duyệt | Không |

Lượt gọi GLM đầu tiên trả sai schema và bị validator chặn. Lượt repair thành công; không có
kết quả lỗi nào được phát hành thành báo cáo.

## Findings chính

| ID | Phát hiện | Nguồn/trang | Trạng thái |
|---|---|---|---|
| ISSUE-001 | Mã số `0301234562` ở phiếu tóm tắt không khớp mã doanh nghiệp `0318888888`; giá trị đầu chưa có nhãn đủ mạnh | DOC-001 trang 1 và DOC-002 trang 1 | `PARTIALLY_VERIFIED` — mở nguồn xác minh |
| ISSUE-002 | Tên đơn vị kiểm toán giữa hai trang BCTC không nhất quán | DOC-005 trang 1 và DOC-007 trang 1 | `PARTIALLY_VERIFIED` |
| ISSUE-003 | Hệ số thanh toán hiện hành và nợ/vốn chủ sở hữu không khớp | DOC-005 trang 1 và DOC-006 trang 1 | `PARTIALLY_VERIFIED` |
| ISSUE-004 | Giá trị vốn chủ sở hữu 270 tỷ và 1.018,5 tỷ có khả năng khác khái niệm | DOC-005 trang 1 và DOC-006 trang 1 | `PARTIALLY_VERIFIED` |
| ISSUE-005 | Agent ban đầu so vay dài hạn với tổng dư nợ CIC; guard đã sửa thành cảnh báo phép so sánh khác phạm vi, không kết luận thiếu 42 tỷ | DOC-006 trang 1 và DOC-008 trang 1 | `VERIFIED` |
| ISSUE-006 | Sao kê 06/2023–05/2024 không cùng kỳ BCTC 2025/6T2026 | DOC-011 trang 1 và DOC-010 trang 1 | `VERIFIED` |
| ISSUE-007 | Claim thiếu BCTC chi tiết chưa được phép gửi khách hàng vì chưa có checklist sản phẩm | DOC-001 trang 1 | `NEEDS_HUMAN_VERIFICATION` |
| ISSUE-008 | Claim thiếu BCTC quản trị 6T2025 chưa có căn cứ checklist nội bộ | DOC-009 trang 1 | `NEEDS_HUMAN_VERIFICATION` |
| ISSUE-009 | Chênh lệch doanh thu BCTC/HĐĐT/VAT dưới 1% cần xác minh thời điểm ghi nhận | DOC-010 trang 1 | `NEEDS_HUMAN_VERIFICATION` |

## Chuyên viên cần làm gì lúc này?

1. Mở đúng các file/trang của 7 finding chưa grounding đầy đủ; xác nhận nhãn, kỳ báo cáo,
   chủ thể và trích đoạn trước khi xem đó là lỗi hồ sơ.
2. Với ISSUE-005, tính lại tổng vay ngắn hạn + dài hạn trên BCTC và so với CIC tại cùng ngày.
3. Với ISSUE-006, xác định theo policy sản phẩm có bắt buộc sao kê cùng kỳ hay cần sao kê mới.
4. Nạp quy định tín dụng nội bộ, checklist sản phẩm và ma trận thẩm quyền vào `policy_context`.
5. Chạy lại assessment. Chỉ khi action chuyển sang `READY_FOR_HUMAN_EXECUTION` mới tạo yêu cầu
   chính thức cho khách hàng hoặc trình cấp phê duyệt.

## Kiểm thử

- `41 passed`.
- Có test contract text/data v2 và từ chối binary/field lạ.
- Có test cùng finding + cùng registry luôn cho cùng action.
- Có test rule hết hiệu lực không được sử dụng.
- Có test thiếu policy nội bộ không được tạo customer action.
- Có test giữ chính xác file, trang và nhiều nguồn cho một finding.

## Tệp kết quả

- Input chuẩn hóa: `artifacts/single-case-v2-vinanova/cty-cp-vinanova.ocr-bundle.extracted-v2.json`
- Báo cáo nghiệp vụ: `artifacts/single-case-v2-vinanova/cty-cp-vinanova.ocr-bundle.assessment-v2.md`
- Kết quả đầy đủ: `artifacts/single-case-v2-vinanova/cty-cp-vinanova.ocr-bundle.assessment-v2.json`

Kết luận: luồng kỹ thuật đã hoạt động đúng hướng mới. Kết quả hiện tại cố ý dừng ở `PENDING`
vì chưa có quy định nội bộ ngân hàng; đây là hành vi an toàn và đúng căn cứ hơn việc dùng ngưỡng
hard-code để tự động chấp thuận hoặc từ chối.
