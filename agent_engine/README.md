# SHB Digital Expert Agents — Backend

Hệ thống multi-agent thẩm định & phê duyệt khoản vay SME end-to-end theo workflow
Final v1.0: Planner động → specialist agents (A2A) → Validation + challenge →
HITL + approval token → commit an toàn (idempotency + đối soát).

## Kiến trúc 3 tầng protocol

| Tầng | Protocol | Vai trò |
|---|---|---|
| Agent ↔ Agent | **A2A** (envelope chuẩn, agent card discovery) | task_request, info_request, challenge, verdict_revision |
| Agent ↔ Tool | **MCP** (streamable-http) | Mọi truy cập core banking đi qua MCP server, audit tập trung |
| Suy luận trong agent | Tool-calling loop (rules/LLM) | ReAct: nghĩ → gọi tool → verdict |

## Ranh giới LLM vs Rules (quyết định thiết kế cho ngân hàng)

Ngân hàng yêu cầu **determinism + auditability + zero-hallucination** ở các quyết định
số học, nhưng cần **trí tuệ linh hoạt** ở planning và đọc hiểu tài liệu. Vì vậy
`LLM_MODE=hybrid` (mặc định) đặt ranh giới:

| Thành phần | hybrid | Vì sao |
|---|---|---|
| DSCR / LTV / blacklist / CIC / ngưỡng chính sách | **Rules** | Con số & hard-stop phải chính xác, giải trình được, không được hallucinate |
| Planner sinh Task DAG | **LLM** (gpt-oss-120b) | Autonomy thật: DAG biến hình theo hồ sơ, re-plan động |
| Document đọc ảnh tài liệu | **LLM vision** (Qwen2.5-VL) | Trích xuất ĐKKD/BCTC/CCCD từ ảnh chụp |
| Validation → khuyến nghị điều hành | **LLM** (gpt-oss-120b) | Diễn giải facts đã chốt thành văn bản cho người duyệt (không đổi quyết định/số) |

`LLM_MODE=llm`: mọi specialist suy luận bằng LLM tool-loop (chứng minh năng lực agentic
đầy đủ, kém ổn định hơn). `LLM_MODE=rules`: thuần rule, baseline cho benchmark.

Endpoint mặc định: **FPT AI Marketplace** (OpenAI-compatible). Đổi model/endpoint qua `.env`.

## Service (7 process)

| Service | Port | Mô tả |
|---|---|---|
| Gateway | 8000 | Cases API, orchestrator + planner, HITL, token, SSE events, SLA watcher |
| Document Agent | 8101 | Vision-LLM trích xuất ĐKKD/BCTC/sao kê/CCCD + cross-check |
| Credit Agent | 8102 | DSCR, đòn bẩy, đề xuất hạn mức; nhận challenge tự điều chỉnh |
| Compliance Agent | 8103 | KYB/AML/blacklist/CIC, pháp lý TSĐB, giới hạn LTV |
| Operations Agent | 8104 | Dry-run (draft) / Commit (token + precondition + idempotency) |
| Validation Agent | 8105 | Fact-check, điều phối challenge A2A, tổng hợp khuyến nghị |
| MCP core-banking | 8200 | Mock core banking (SQLite) + audit trail |

## Chạy

```bash
cd backend
pip install mcp                     # thứ duy nhất cần cài thêm trên máy này
cp .env.example .env                # điền FPT_API_KEY; LLM_MODE=hybrid (khuyến nghị)
python run_all.py                   # khởi động 7 service + tự seed
python -m scripts.demo_run          # demo B001: luồng sạch + twist challenge hạn mức
python -m scripts.demo_run --b002   # demo B002: hồ sơ gài (DSCR thấp, lệch dòng tiền)
python -m scripts.reset_demo        # reset dữ liệu giữa 2 lượt demo
```

> Chạy offline / không cần key: đặt `LLM_MODE=rules` trong `.env`.

**Twist TOCTOU (demo #3):** khi case đang Pending Approval, chạy
`python -m scripts.demo_trigger_overdue` rồi mới bấm approve → commit bị chặn
bởi precondition re-check → tự re-plan → package mới có điều kiện bổ sung →
quay lại Pending Approval. Reset bằng `--reset`.

## Ba chế độ chạy (xem bảng ranh giới LLM vs Rules ở trên)

- `LLM_MODE=hybrid` (mặc định): rules cho số, LLM cho Planner/vision/narrative.
  Demo ổn định + dùng LLM thật ở đúng chỗ. Planner sinh DAG bằng LLM (validate
  schema + registry, fallback template có ghi event minh bạch).
- `LLM_MODE=llm`: mọi specialist suy luận bằng LLM tool-loop.
- `LLM_MODE=rules`: thuần rule, không cần mạng/API key — baseline benchmark.

## API chính (Swagger: http://127.0.0.1:8000/docs)

- `POST /cases` → tạo case (request + documents)
- `POST /cases/{id}/run` → chạy phân tích
- `GET  /cases/{id}` / `GET /cases/{id}/events?after=` / `GET /cases/{id}/stream` (SSE)
- `POST /cases/{id}/approve|reject|supplement` → HITL
- `POST /ask` → Direct Answer (FAQ RAG, chỉ đọc)
- `GET  /agents` → Agent Card registry
- `GET  /audit/mcp` → audit trail tầng MCP

## State machine

`Draft → In Analysis → (Needs Info ↔) Pending Approval → Executing → Completed`
với `Rejected` / `Escalated` là nhánh thoát; re-plan giới hạn `MAX_REPLAN_ROUNDS`.

## Cấu trúc

```
backend/
├── common/           # config, schemas (A2A/Plan/Verdict), llm, rag (BM25), pii, mcp_client
├── mcp_core_banking/ # MCP server + seed (B001 sạch / B002 gài)
├── agents/           # base (A2A service factory) + 5 specialist agents
├── gateway/          # main (API+SSE+SLA), orchestrator (DAG executor), planner, approval (token)
├── rag_corpus/       # chính sách tín dụng / tuân thủ / vận hành (tiếng Việt)
└── scripts/          # demo_run, demo_trigger_overdue, reset_demo
```
