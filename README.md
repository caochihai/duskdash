Đây là hệ thống trợ lý cho nhân viên ngân hàng với các chức năng như sau:

1. Nhân viên ngân hàng có thể đăng nhập
2. Nhân viên ngân hàng có thể tra cứu và tìm kiếm nhanh thông tin của khách hàng
3. Nhân viên có thể thống kê dữ liệu có khách hàng một cách nhanh hơn chẳng hạn như khách hàng này đã thanh toán tổng bao nhiêu tiền trong tháng 12 hay khách hàng này có bao nhiêu lần giao dịch trong thánh này,...
3. Nhân viên có thể upload hồ sơ khách hàng đơn giản hơn. AI sẽ tự động đọc và hiểu hồ sơ của khách hàng. Kiểm tra các hồ sơ thiếu cho khoản vay và các điều kiện hồ sơ đầy đủ để gửi thông tin lại cho khách hàng chẳng hạn như sau:
Khách hàng đến để làm hồ sơ. 1 hệ thống các agent sẽ phân tích thiếu hồ sơ gì hay hồ sơ sai ở đâu ngoiaf ra hồ sơ này đã được sửa đúng rồi còn hồ sơ kia thì sao đã đúng chưa,... Tức là không còng xử lý tuần tự nữa các agent sẽ đề xuất ra 1 loại các case để khách hàng lần sau có thể đến ngân hàng làm thủ tục được luôn
4. Có thể đánh giá các khoản vay. Với 1 nhóm chuyên gia gồm 3 các chuyên gia (1. Chuyên gia đánh giá creadit, chuyên gia pháp lý, chuyên gia kiểm tra hồ sơ đã được upload) các agent chuyển  gia này sẽ làm việc sau đó 1 agent sẽ tổng hợp lại 1 bản báo cáo được nghiên cứu kỹ về credit, pháp luật và tài liệu để hỗ trợ lãnh đạo quyết định có nêm duyệt khoản vay hay không ?
5. về độ chính xác khi trả lời của agent là chính xác tuyệt đối có thể chỉ cần nhấn vào những câu agent nói để truy xuất ra nguồn xem câu nói đó dựa vào đâu mà agent nói. Các thông tin được truy xuất sẽ được lấy từ hồ sơ của khách hàng
---

## Agentic Core Engine (`agent_engine/`)

Lõi multi-agent cấy từ nhánh `dev`, chạy song song với platform backend
(gateway engine ở cổng **:8010**, platform giữ :8000):

- **Planner LLM sinh Task DAG động** theo đặc điểm hồ sơ + re-plan có giới hạn
- **MCP layer** (`core-banking` :8200) — mọi tool call qua MCP, audit tập trung
- **5 chuyên gia A2A độc lập** (:8101–:8105) — Document/Credit/Compliance/
  Operations/Validation, có challenge loop máy-tự-giải
- **LLM/OCR thật trên FPT Marketplace** — vision gemma-4-31B-it, benchmark
  CER 0.004 / Numeric Acc 97% (`agent_engine/docs/OCR_BENCHMARK.md`)
- **Commit an toàn** — approval token (hash+policy+expiry), TOCTOU re-check,
  idempotency, đối soát in-doubt + retry đúng 1 lần

Chạy nhanh: `cd agent_engine && python run_all.py` rồi
`python -m scripts.demo_run`. Hướng dẫn ghép vào platform:
[docs/integration-agent-engine.md](docs/integration-agent-engine.md) —
2 điểm wire có sẵn: `backend/app/services/agent_engine_client.py` và
`backend/app/agents/dynamic_planner.py`.
