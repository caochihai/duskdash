# DuskDash Credit Agent

DuskDash Credit Agent là một prototype AI thực tế dùng để hỗ trợ đánh giá và gia hạn hạn mức tín dụng cho khách hàng SME. Repo này cung cấp một agent chuyên biệt, có thể chạy như thư viện Python, API demo, hoặc thành phần trong quy trình đánh giá tín dụng.

## Tóm tắt nhanh

- Đánh giá hồ sơ tín dụng theo luồng có cấu trúc và có evidence.
- Gắn kết quả với policy, audit trail và các hard-stop rules.
- Có thể dùng trực tiếp trong Python hoặc qua FastAPI demo API.
- Dự án này tập trung vào phần core agent và contract dữ liệu, không thay thế quyết định tín dụng cuối cùng của con người.

```text
Planner → Plan Executor → CreditAgent.run(...) → Validation → Human approval
```

## Các khả năng chính

- Xử lý đầu vào theo schema chuẩn hóa.
- Dùng pipeline quyết định xác định với các bước kiểm tra dữ liệu, policy và evidence.
- Trả về kết quả có cấu trúc cho workflow validation và review.
- Hỗ trợ demo mode và evaluator dùng LLM làm judge độc lập.

## Cài đặt

Yêu cầu Python 3.11 trở lên.

```bash
python -m venv .venv
pip install -e .[api,dev]
```

## Chạy demo

```bash
python examples/run_demo.py
```

## Chạy API demo

```powershell
$env:CREDIT_AGENT_DEMO_MODE = "1"
uvicorn credit_agent.api:app --reload
```

Sau khi dùng xong, có thể xóa biến môi trường:

```powershell
Remove-Item Env:CREDIT_AGENT_DEMO_MODE
```

## Sử dụng từ Python

```python
from credit_agent import AgentConfig, CreditAgent, CreditTaskInputV1

agent = CreditAgent(
    tools=tools,
    audit_sink=audit_sink,
    config=AgentConfig(require_audit_sink=True),
)

task = CreditTaskInputV1.model_validate(payload)
result = await agent.run(task)
```

## Tài liệu liên quan

- [docs/CREDIT_AGENT.md](docs/CREDIT_AGENT.md)
- [docs/REFERENCE_SYSTEM_PROMPT.md](docs/REFERENCE_SYSTEM_PROMPT.md)
- [docs/MOCK_6_DATASET_EVALUATION.md](docs/MOCK_6_DATASET_EVALUATION.md)

## Giới hạn và cảnh báo

- Đây là prototype, không phải hệ thống cấp tín dụng production.
- Policy và dữ liệu production phải được inject từ nguồn đã được phân quyền và kiểm toán.
- Kết quả của agent là khuyến nghị có cấu trúc để con người và validation kiểm tra, không phải quyết định cuối cùng.

## Đánh giá

```bash
pytest
```

Nếu muốn chạy evaluator với LLM judge, hãy xem thêm script trong [scripts/evaluate_with_llm.py](scripts/evaluate_with_llm.py).
