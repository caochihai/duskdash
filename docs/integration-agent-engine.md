# Tích hợp Agentic Core Engine vào Platform

## Vì sao ghép

Hai hệ bổ khuyết nhau: platform (`backend/` + `infra/` + `frontend/`) mạnh về vỏ
production (Postgres/Redis/MinIO/Keycloak, CI, tests, contracts); engine
(`agent_engine/`) mạnh về **lõi agentic mà đề bài chấm điểm tường minh**:

| Năng lực | Platform hiện tại | Engine mang vào |
|---|---|---|
| Planner | `create_plan()` tĩnh (tuple cứng) | **LLM sinh DAG động** theo hồ sơ + re-plan giới hạn, fallback minh bạch |
| MCP (đề bài nêu nguyên văn) | Không có | **MCP server** `core-banking` — mọi tool call qua MCP, audit tập trung |
| A2A / agent độc lập | Class in-process | **5 A2A service** + Agent Card discovery + challenge loop máy-tự-giải |
| LLM / OCR | `LLM_PROVIDER=mock` | **FPT thật**: gpt-oss-120b (planner/narrative), Llama-3.3-70B (tool-loop), gemma-4-31B-it vision — benchmark CER 0.004, Numeric Acc 97% (`agent_engine/docs/OCR_BENCHMARK.md`) |
| Commit an toàn | Idempotency API | **Approval token** (hash package + policy version + expiry, single-use) + **TOCTOU re-check** preconditions + **đối soát in-doubt** + retry đúng 1 lần |

## Kiến trúc sau ghép

```
frontend (:3000)
   └── platform backend (:8000)  — auth, DB, hồ sơ, conversation, report
         └── AgentEngineClient (backend/app/services/agent_engine_client.py)
               └── agent engine gateway (:8010) — planner LLM + executor + HITL + token
                     ├── document agent (:8101)  ─┐
                     ├── credit agent   (:8102)  ─┤ A2A (info_request/challenge)
                     ├── compliance     (:8103)  ─┤
                     ├── operations     (:8104)  ─┤ dry-run / commit an toàn
                     └── validation     (:8105)  ─┘
                           └── MCP core-banking (:8200) — tool + audit tập trung
```

Engine đổi cổng gateway sang **:8010** để chạy song song với platform (:8000).

## Chạy engine

```bash
cd agent_engine
pip install mcp rank_bm25            # phần còn thiếu so với env chuẩn
cp .env.example .env                  # điền FPT_API_KEY
python run_all.py                     # MCP + 5 agents + gateway :8010
python -m scripts.demo_run            # E2E B001 (challenge hạ hạn mức 5→4.2 tỷ)
python -m scripts.demo_tran_quoc_bao  # 10 ảnh hồ sơ gian lận CR-I03, ~62s
```

## Hai điểm wire cho team (đã viết sẵn, chưa import ở đâu — không phá gì)

1. **`backend/app/services/agent_engine_client.py`** — client HTTP đầy đủ:
   `create_case → run → wait_final → get_case().package → approve`. Gọi từ
   `multi_agent_analysis_service` / analysis worker khi case cần phân tích sâu
   (mức 5 trong `multiagent_architecture.md`). Trace cho dashboard lấy từ
   `get_events()` (plan DAG, task status, mũi tên A2A, verdicts) hoặc SSE
   `GET :8010/cases/{id}/stream`.

2. **`backend/app/agents/dynamic_planner.py`** — nếu muốn giữ pipeline in-process
   của platform nhưng có planner động: `create_dynamic_plan(orchestrator, case_id,
   case_context)` thay cho `orchestrator.create_plan(case_id)`. LLM đề xuất
   cấu trúc, code ép bất biến dependency, sai thì fallback plan tĩnh (source
   được trả về để log minh bạch).

Khuyến nghị: dùng đường (1) cho demo — engine đã chạy thật end-to-end có đo đạc;
đường (2) là nâng cấp dần cho pipeline nội bộ của platform.

## Kết quả engine đã kiểm chứng (trên máy thật, LLM thật)

- B001 sạch: Planner LLM sinh DAG → Credit ∥ Compliance → Validation **challenge**
  Credit tự hạ hạn mức 5 → 4.2 tỷ (LTV 70%) → HITL approve → token → commit
  idempotent → Completed.
- TOCTOU: phát sinh nợ quá hạn SAU phê duyệt → precondition re-check chặn commit
  → re-plan → package mới kèm điều kiện → chờ phê duyệt lại.
- Bộ 10 ảnh hồ sơ gian lận CR-I03: **62.4s full luồng**, Rejected (đúng),
  46 findings, tự phát hiện **3 số CCCD khác nhau** giữa các tài liệu.

## Việc còn lại sau khi ghép

- [ ] Gọi `AgentEngineClient` từ analysis service/worker (mức 5) + đổ events vào UI
- [ ] Map schema hồ sơ platform (Postgres) → `LoanRequest` của engine
- [ ] Chuyển mock core-banking phía sau MCP server sang đọc Postgres của platform
      (agent không đổi — chỉ đổi implementation trong `mcp_core_banking/server.py`)
- [ ] Personal-flow cho hồ sơ cá nhân (hiện engine mạnh nhất ở luồng SME)
- [ ] Giảm latency planner (~20s với gpt-oss-120b): đổi PLANNER_MODEL hoặc
      LLM_MODE=rules khi demo cần tốc độ
