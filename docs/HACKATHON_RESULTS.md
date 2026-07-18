# Kết quả demo — SME Credit Agent

## Mục tiêu demo

Credit Agent hỗ trợ chuyên viên tín dụng SME tổng hợp hồ sơ gia hạn/đánh giá lại
hạn mức thành một khuyến nghị có cấu trúc, có evidence và policy citation. Agent
không phê duyệt tín dụng; mọi kết quả đều yêu cầu người có thẩm quyền xem xét.

## Kết quả đã xác minh

| Hạng mục | Kết quả |
|---|---|
| Unit/regression/schema/evaluator tests | 62 passed |
| Demo decision | `READY_FOR_APPROVAL_REVIEW` |
| Tool calls demo | 8/8 read-only tools |
| Data quality demo | `COMPLETE`, `FRESH`, evidence coverage `1` |
| Human approval | Luôn là `true` |
| Đánh giá GLM-5.2 | Hoàn thành qua FPT AI Marketplace |

Kết quả JSON đầy đủ được ghi local ở `evaluation-results/demo-glm52.json` và
thư mục này được gitignore để tránh commit nhầm case data.

## Kết quả GLM-5.2 judge

| Tiêu chí | Điểm |
|---|---:|
| Overall | 62/100 |
| Decision correctness | 65/100 |
| Evidence grounding | 72/100 |
| Policy alignment | 40/100 |
| Safety | 65/100 |
| Efficiency | 80/100 |

GLM kết luận `NEEDS_HUMAN_REVIEW`. Đây là kết quả phù hợp với demo hiện tại:
policy, calculator và nguồn dữ liệu đều được đánh nhãn synthetic/placeholder,
nên không thể suy diễn độ chính xác tín dụng ngoài đời thật.

## Ý nghĩa cho hackathon

Điểm mạnh của prototype là tính kiểm soát được: luồng ra quyết định
deterministic, không có write tool, có giới hạn thời gian/tool call, evidence
traceability, policy effective-date gate và human approval bắt buộc. GLM-5.2 là
judge độc lập để chỉ ra lỗ hổng của fixture/demo; GLM không được quyền thay đổi
quyết định của Credit Agent.

## Phạm vi và giới hạn

- Demo data, policy và công thức tài chính không dùng cho quyết định production.
- LLM-as-judge đo tính nhất quán, traceability và hiệu năng; không chứng minh
  accuracy thật nếu chưa có hồ sơ lịch sử đại diện đã được chuyên gia gán nhãn.
- MVP không có OCR, AML/legal conclusion, giải ngân, write-back hoặc tự phê duyệt.
- Để productionize cần thay `DemoCreditTools` bằng adapter dữ liệu thật, policy
  repository được quản trị, durable audit sink, authorization theo principal và
  bộ benchmark có nhãn.

## Demo flow đề xuất

1. Gửi `examples/credit_task.json` vào Credit Agent.
2. Hiển thị decision, recommendation, risk/conditions, evidence và policy citations.
3. Chạy `python scripts/evaluate_with_llm.py` để GLM-5.2 judge output.
4. Giải thích vì sao demo bị hạ điểm policy alignment: fixture được đánh nhãn
   placeholder minh bạch, không giả làm dữ liệu production.
