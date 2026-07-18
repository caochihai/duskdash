# SHB Credit Agent — SME Credit Renewal MVP

Package này triển khai **một Credit Agent độc lập** để phân tích hồ sơ gia hạn/đánh giá lại hạn mức tín dụng SME. Agent là specialist building block nằm giữa **Plan Executor** và **Validation** trong workflow ExpertFlow; đây **không phải** toàn bộ lời giải hackathon multi-agent, dashboard hay lớp phê duyệt/vận hành.

```text
Planner → Plan Executor → CreditAgent.run(...) → Validation → Human approval
```

Agent chỉ đọc dữ liệu qua 8 tool trong `CreditTools`, chạy pipeline bất đồng bộ có thứ tự quyết định xác định, gắn evidence/policy vào kết quả và luôn để `human_approval_required = true`. Agent không OCR, không kết luận AML/pháp lý, không phê duyệt, không giải ngân và không ghi vào hệ thống nghiệp vụ.

## Cài đặt và kiểm thử

Yêu cầu Python 3.11 trở lên.

```bash
python -m venv .venv
pip install -e .[api,dev]
pytest
```

Xuất JSON Schema để đăng ký với Planner/Validation hoặc tạo client type:

```bash
python scripts/export_schemas.py
```

Schema xuất ra có các ràng buộc shape, Decimal wire format và decision/status chính; metadata `x-credit-agent-runtime-invariants` liệt kê các invariant còn lại. Planner/Validation **vẫn phải** gọi Pydantic/core validator, không dùng JSON Schema đơn lẻ như bộ quyết định nghiệp vụ hoặc kiểm tra toàn vẹn evidence.

Chạy demo bằng dữ liệu và adapter giả lập:

```bash
python examples/run_demo.py
```

Adapter demo chỉ phục vụ minh họa, không đại diện cho dữ liệu, chính sách hay kết luận production. Khi tích hợp thật, phải inject một implementation `CreditTools` đọc từ các nguồn đã được phân quyền và kiểm toán.

Nội dung system prompt tham chiếu do bạn cung cấp được lưu dạng lưu trữ tại [docs/REFERENCE_SYSTEM_PROMPT.md](docs/REFERENCE_SYSTEM_PROMPT.md). Header cảnh báo được thêm để tránh dùng nhầm schema minh họa cũ như contract chạy thật. Core hiện thực các hard-stop/rule quan trọng bằng code; không phụ thuộc model tự tuân thủ prompt.

## Dùng trực tiếp trong Python

```python
from credit_agent import AgentConfig, CreditAgent, CreditTaskInputV1

# tools là implementation production của CreditTools.
agent = CreditAgent(
    tools=tools,
    audit_sink=durable_audit_sink,
    config=AgentConfig(require_audit_sink=True),
)
task = CreditTaskInputV1.model_validate(payload)
result = await agent.run(task)

result_json = result.model_dump(mode="json")
```

Điểm vào public là `CreditAgent.run`, input là `CreditTaskInputV1`, output thống nhất là `CreditAnalysisResultV1`, kể cả khi dừng sớm vì thiếu dữ liệu hay lỗi tool.
Các giá trị `Decimal` (tiền và tỷ lệ) được serialize thành **chuỗi thập phân chính xác** trong JSON, ví dụ `"1000000"`, để không mất độ chính xác qua số thực nhị phân.

## Chạy API

Module-level app mặc định **không được cấu hình** và trả `503`; demo chỉ bật bằng cờ tường minh. Với PowerShell:

```powershell
$env:CREDIT_AGENT_DEMO_MODE = "1"
uvicorn credit_agent.api:app --reload
```

Lệnh trên khởi động **demo mode** với dữ liệu tổng hợp và policy placeholder. Sau khi chạy xong, xóa biến bằng `Remove-Item Env:CREDIT_AGENT_DEMO_MODE` nếu cần.

Production phải tạo app riêng bằng `create_app(agent, scope_resolver=..., task_authorizer=...)`. `scope_resolver` lấy quyền thô từ principal đã xác thực; `task_authorizer` ràng buộc chính principal đó với đúng `case_id`/`customer_id`/tenant của task. API bỏ qua `permissions.allowed_scopes` do client tự khai. Agent production cũng yêu cầu audit sink được cấu hình:

```python
from credit_agent import AgentConfig, CreditAgent
from credit_agent.api import create_app

agent = CreditAgent(
    tools=production_tools,
    audit_sink=durable_audit_sink,
    config=AgentConfig(
        require_audit_sink=True,
        fail_on_audit_error=True,
    ),
)
app = create_app(
    agent,
    scope_resolver=scopes_from_authenticated_request,
    task_authorizer=principal_can_access_task,
)
```

Hai callback authorization có timeout 2 giây mặc định (cấu hình bằng
`authorization_timeout_seconds`, tối đa 5 giây). Timeout hoặc lỗi dependency
trả `503` an toàn trước khi agent/tool được gọi. Mọi response kèm header
`X-Credit-Agent-Mode` để tránh nhầm API demo với môi trường injected.

`durable_audit_sink` phải khai báo capability `durable = True` và thực sự ghi append-only theo thiết kế triển khai. Production wrapper từ chối policy có `placeholder_data=true`; chỉ demo tường minh mới bật `allow_placeholder_policy`. Không public demo app như một dịch vụ ra quyết định thật.

Package không tự chọn OAuth/JWT/mTLS cho dự án đích, nên OpenAPI không tuyên bố một security scheme giả định. Top-level extension `x-authentication-boundary` ghi rõ AuthN thuộc host gateway; deployment phải bổ sung security scheme thật của mình và các callback chỉ được dùng principal do gateway xác thực.

Các endpoint dự kiến:

- `POST /v1/credit-analysis`: chạy một credit task.
- `GET /agent-card`: xem năng lực, task và tool được phép.
- `GET /health`: kiểm tra tiến trình API; không thay thế kiểm tra kết nối tới toàn bộ nguồn production.

Ví dụ:

```bash
curl -X POST http://127.0.0.1:8000/v1/credit-analysis \
  -H "Content-Type: application/json" \
  --data @examples/credit_task.json
```

Xem [tài liệu Credit Agent](docs/CREDIT_AGENT.md) để hiểu pipeline, contract, evidence/policy gates, cách nối FastAPI/LangGraph và checklist adapter production.

## Phạm vi an toàn

Mọi ngưỡng tín dụng, thời hạn dữ liệu và nội dung chính sách phải đến từ `retrieve_credit_policy` với phiên bản/hiệu lực phù hợp `as_of_date`; không coi fixture hoặc giá trị demo là quy định production. Kết quả của agent là khuyến nghị có cấu trúc để Validation và con người kiểm tra, không phải quyết định cấp tín dụng.

MVP chưa có tool sizing hạn mức riêng. Với `READY_FOR_APPROVAL_REVIEW` hoặc `PASS_WITH_CONDITIONS`, agent chỉ chuyển tiếp đúng `requested_limit` và `requested_tenor_months` đã được Supervisor cung cấp; các decision còn lại trả `null`. Muốn đề xuất một con số khác, adapter production phải bổ sung kết quả sizing xác định vào calculator/policy contract trước khi mở rộng core.

## Đánh giá bằng GLM 5.2 ngoài hệ thống

`CreditAgent` vẫn giữ tính quyết định xác định; mô hình ngoài chỉ đóng vai trò
judge độc lập. Sao chép `.env.example` sang `.env` (file `.env` rỗng cũng đã
được gitignore), nhập FPT key, URL chat-completions chính xác FPT cấp cho tenant
của bạn và tên model. Tài liệu FPT công khai không công bố một endpoint GLM 5.2
dùng chung, vì vậy URL và header xác thực đều được cấu hình qua biến môi trường.

Với FPT AI Marketplace global, URL POST trực tiếp là
`https://mkp-api.fptcloud.com/chat/completions`; không dùng
`https://mkp-api.fptcloud.com/v1` cho biến `FPT_GLM_CHAT_COMPLETIONS_URL` vì đó
là base URL của một số SDK, không phải chat endpoint đầy đủ.

Mặc định evaluator chỉ chấp nhận HTTPS tới `mkp-api.fptcloud.com` hoặc
`mkp-api.fptcloud.jp`. Chỉ bật `CREDIT_EVAL_ALLOW_CUSTOM_ENDPOINT=true` khi
gateway HTTPS tùy chỉnh đã được tổ chức phê duyệt.

Evaluator gửi task được chọn cùng kết quả agent tới nhà cung cấp ngoài. Chỉ đặt
`CREDIT_EVAL_ALLOW_EXTERNAL_CASE_DATA=true` sau khi quy trình privacy,
data-governance và vendor-review cho phép chia sẻ dữ liệu. Task demo trong repo
là dữ liệu synthetic. Report được ghi vào `evaluation-results/`, thư mục đã
được gitignore; không commit output của case thật. Judge response phải vượt qua
contract có score `0..100`, verdict/finding hợp lệ; output JSON tuỳ ý bị từ chối.

```powershell
Copy-Item .env.example .env
# Sửa .env, sau đó bật xác nhận chia sẻ dữ liệu cho case đã chọn.
py -m pip install -e ".[api,dev,eval]"
py scripts/evaluate_with_llm.py --output evaluation-results\demo-glm52.json
```

Thêm `--reference path\to\expert-labelled-case.json` để so với quyết định do
chuyên gia gán nhãn. LLM-as-judge chấm evidence grounding, policy alignment,
safety và runtime/tool-call efficiency; nó không thể chứng minh độ chính xác
tín dụng trong thực tế nếu không có tập lịch sử đại diện, đã gán nhãn và cơ chế
review của chuyên gia tín dụng.

Để chấm output từ adapter production thay vì demo fixture, lưu request và
`CreditAnalysisResultV1` response rồi chạy:

```powershell
py scripts/evaluate_with_llm.py --task cases\case-001.json --agent-result results\case-001.json --reference labels\case-001.json
```

Script xác thực contract và ràng buộc `task_id`/`case_id`/`as_of_date` trước khi
gửi sang judge, nhưng không thay thế việc ẩn danh hoá hoặc phê duyệt chia sẻ dữ
liệu của tổ chức.
