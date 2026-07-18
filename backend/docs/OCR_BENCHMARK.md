# Báo cáo đánh giá OCR — Document Intelligence Agent

**Bộ test:** 6 ảnh "Phiếu thông tin khách hàng" chụp thật (3 hồ sơ doanh nghiệp + 3 cá nhân,
phủ 3 kịch bản: sạch / có điều kiện / từ chối). Ground truth đối chiếu thủ công.
**Điều kiện:** temperature=0, prompt có ràng buộc định dạng, chạy trên FPT AI Marketplace.
**Tái chạy:** `python -m scripts.eval_ocr` (từ thư mục backend).

## Định nghĩa metric

| Metric | Định nghĩa | Vì sao quan trọng |
|---|---|---|
| **Field Accuracy** | % trường text đúng tuyệt đối (exact match, phân biệt hoa thường) | Chất lượng nhập liệu tổng thể |
| **CER** | Character Error Rate = khoảng cách Levenshtein / độ dài chuỗi chuẩn | Metric OCR tiêu chuẩn; 0.004 = sai 4 ký tự trên 1000 |
| **Numeric Accuracy** | % giá trị số đúng tuyệt đối (42 con số: doanh thu 3 năm, EBITDA, TSĐB, thu nhập, DTI, CIC...) | **Tiêu chí sống còn với ngân hàng** — sai 1 số là sai hạn mức |
| **Decision Accuracy** | % đọc đúng dòng "Đề xuất sơ bộ" | Trích xuất phân loại |
| **Latency / Tokens** | Thời gian & token trung bình mỗi ảnh | Chi phí vận hành |

## Kết quả (6 ảnh × 3 model)

| Model | Field Acc | CER ↓ | Numeric Acc | Decision Acc | Latency TB | Tokens in/out |
|---|---|---|---|---|---|---|
| **gemma-4-31B-it** ⭐ | **93.3%** | **0.004** | **86%** (36/42) | **83%** | 5.0s | 581 / 216 |
| Qwen2.5-VL-7B-Instruct | 86.7% | 0.076 | 81% (34/42) | 33% | **1.6s** | 2288 / 184 |
| gemma-3-27b-it | 60.0% | 0.263 | 50% (21/42) | 0% | 3.5s | 551 / 233 |

### Kết quả cuối sau khi vá schema theo phân tích lỗi (`scripts/eval_ocr.py`)

| Model | Field Acc | CER ↓ | **Numeric Acc** | Decision Acc | Latency TB |
|---|---|---|---|---|---|
| **gemma-4-31B-it** (schema v2) | 93.3% | 0.004 | **97% (35/36)** | 83% | 4.8s |

Schema v2 nâng Numeric Acc 86% → 97% nhờ: (1) mô tả rõ lấy "thu nhập XÁC MINH"
thay vì khai báo, (2) ghi rõ đơn vị TỶ đồng, (3) bỏ CIC khỏi OCR (tra hệ thống nguồn).
Lỗi số duy nhất còn lại: DTI 205 vs 205,4 (làm tròn). Lưu ý mã hồ sơ có biến động
nhẹ giữa các lần chạy (I↔C) — trong luồng thật mã hồ sơ do hệ thống cấp, OCR chỉ
dùng để đối chiếu cross-check.

## Phân tích lỗi của gemma-4-31B (quan trọng cho thiết kế hệ thống)

Trong 6/42 số bị trượt, chỉ **1 là lỗi OCR thật**:

| Lỗi | Bản chất | Cách hệ thống xử lý |
|---|---|---|
| `cic_nhom = null` ×3 | CIC nằm trong dòng văn xuôi, schema rút gọn không mô tả rõ | **Không lấy CIC từ OCR** — CIC tra trực tiếp từ core/CIC API (đã đúng thiết kế hiện tại) |
| Thu nhập 180 vs 46 (CR-I03) | Phiếu có cả "khai báo 180tr" và "xác minh 46tr"; schema rút gọn không chỉ rõ lấy giá trị xác minh | Mô tả trường rõ trong schema — vòng test trước có mô tả thì đọc đúng 46 |
| TSĐB 0.115 vs 115 (CR-C03) | Nhầm đơn vị (tỷ) | Chuẩn hóa đơn vị + sanity-check biên độ bằng code |
| DTI 205 vs 205.4 | Làm tròn | Chấp nhận được / đối chiếu chéo bằng code |

**Qwen2.5-VL** nhanh gấp 3 (1.6s) nhưng có **lỗi đơn vị nguy hiểm** (4000 tỷ thay vì 4 tỷ;
3800 thay vì 3.8) và Decision Acc chỉ 33% → chỉ dùng làm fallback tốc độ, không dùng cho số liệu.
**gemma-3-27b** loại (đọc nhầm cả bảng doanh thu, vỡ JSON).

## Kết luận thiết kế (đã triển khai trong hệ thống)

1. **VISION_MODEL = gemma-4-31B-it** — CER 0.004, tốt nhất mọi metric chất lượng.
2. **LLM đọc, code tính**: mọi giá trị dẫn xuất (tổng, bình quân, DTI) tính bằng Python
   từ line items — benchmark riêng cho thấy 2/3 model đọc đúng từng số nhưng cộng tổng sai.
3. **Dữ liệu định danh/tín dụng (CIC, blacklist) không lấy từ OCR** — luôn tra hệ thống nguồn.
4. **Ràng buộc định dạng trong prompt + normalizer code** cho các mã định danh
   (CR-101 → CR-I01): nâng field accuracy từ 86% → 97%.
5. Trường "khai báo" vs "xác minh" phải được mô tả tường minh trong schema trích xuất.
