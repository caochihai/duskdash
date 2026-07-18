# Quy trình vận hành tín dụng (trích) — phiên bản 2026.07

## Mục 3. Điều kiện tác nghiệp trước giải ngân
Khách hàng phải có tài khoản thanh toán còn hoạt động tại ngân hàng để nhận vốn giải ngân. Hồ sơ vay chỉ được khởi tạo chính thức trên hệ thống sau khi có phê duyệt của cấp thẩm quyền còn hiệu lực; bản nháp (draft) không phát sinh hiệu lực nghiệp vụ.

## Mục 4. Nguyên tắc thực thi
Mọi giao dịch khởi tạo khoản vay phải gắn khóa chống trùng lặp (idempotency key). Giao dịch có kết quả không xác định phải được đối soát bằng khóa tham chiếu trước khi thực hiện lại; nghiêm cấm tự động thực hiện lại giao dịch ghi khi chưa đối soát. Giao dịch thất bại rõ ràng sau một lần thực hiện lại: chuyển xử lý ngoại lệ, không tiếp tục tự động.

## Mục 5. Lịch giải ngân
Hạn mức dưới 10 tỷ đồng giải ngân tối đa 2 đợt, các đợt cách nhau tối thiểu 30 ngày theo tiến độ sử dụng vốn. Lịch giải ngân được hệ thống khởi tạo tự động ngay sau khi khoản vay có hiệu lực.

## Mục 6. Thẩm quyền phê duyệt
Hạn mức đến 8 tỷ đồng: giám đốc chi nhánh phê duyệt. Trên 8 tỷ đồng: chuyển hội sở. Người phê duyệt không phản hồi trong SLA quy định: hệ thống nhắc việc, ghi nhận audit và chuyển cấp dự phòng theo ma trận thẩm quyền.
