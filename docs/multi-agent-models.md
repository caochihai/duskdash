# Multi-Agent — Model nào cho vai trò nào

Tài liệu này ghi rõ **từng agent / thành phần AI đang gọi model gì**, để đồng đội
nắm nhanh khi vận hành, debug hay đổi model. Toàn bộ chạy trên **FPT AI Marketplace**
(endpoint OpenAI-compatible): `https://mkp-api.fptcloud.com/v1`, key = `FPT_API_KEY`.

## Nguyên tắc phân vai

Model được chọn theo **loại việc**, không phải "một model cho tất cả":

- Việc cần **suy luận + JSON có cấu trúc** (lập kế hoạch, phản biện) → model mạnh nhất.
- Việc **gọi tool lặp nhiều vòng** (chuyên gia tra cứu core-banking) → model nhanh/rẻ, tool-calling ổn định.
- Việc **đọc ảnh tài liệu** (OCR/trích xuất) → vision model thắng benchmark nội bộ.

## Agentic Core Engine (`agent_engine/`)

| Agent / Vai trò | Việc | Đường gọi | **Model** | Biến env |
|---|---|---|---|---|
| **Planner** (gateway) | Sinh Task DAG động theo hồ sơ, re-plan | `llm.chat_json` | **gpt-oss-120b** | `PLANNER_MODEL` |
| **Document Agent** (:8101) | OCR/trích xuất ĐKKD, BCTC, sao kê, CCCD, sổ đỏ + đối chiếu chéo | `llm.vision_extract` | **gemma-4-31B-it** | `VISION_MODEL` |
| **Credit Agent** (:8102) | Phân tích BCTC, DSCR, đòn bẩy, đề xuất hạn mức | `llm.tool_loop` | **Llama-3.3-70B-Instruct** | `SPECIALIST_MODEL` |
| **Compliance Agent** (:8103) | KYB/AML/blacklist, pháp lý tài sản đảm bảo | `llm.tool_loop` | **Llama-3.3-70B-Instruct** | `SPECIALIST_MODEL` |
| **Operations Agent** (:8104) | Dry-run / commit an toàn (approval token, TOCTOU) | luật (rules) | **Không dùng LLM** | — |
| **Validation Agent** (:8105) | Kiểm chứng chéo verdict, challenge, tổng hợp khuyến nghị | `llm.chat_json` | **gpt-oss-120b** | `PLANNER_MODEL` |

`LLM_MODE=hybrid` (khuyến nghị demo). Đặt `LLM_MODE=rules` để chạy baseline không tốn LLM,
`LLM_MODE=llm` để full-LLM.

## Platform backend (`backend/`) — luồng chat

| Thành phần | Việc | **Model** | Biến env |
|---|---|---|---|
| **Chat responder** (tra cứu nhanh) | Trả lời câu hỏi trên dữ liệu thật từ Postgres, có trích nguồn | **gpt-oss-120b** | `LLM_MODEL_NAME` |
| **Document Highlighter** (1-click hồ sơ) | Đọc ảnh hồ sơ, highlight 4 mức có căn cứ pháp lý, checklist thiếu | **gemma-4-31B-it** | `VISION_MODEL_NAME` |
| **Phân tích sâu** (route ORCHESTRATED) | Chuyển sang Agent Engine ở trên | (theo bảng engine) | `AGENT_ENGINE_URL` |
| OCR / Embedding (workers) | Pipeline tài liệu qua Kafka | **mock** (workers chưa deploy cloud) | `OCR_PROVIDER`, `EMBEDDING_PROVIDER` |

## Vì sao chọn gemma-4-31B-it cho vision (benchmark nội bộ)

6 ảnh × 3 model (chi tiết: [`agent_engine/docs/OCR_BENCHMARK.md`](../agent_engine/docs/OCR_BENCHMARK.md)):

| Model | Field Acc | CER ↓ | Numeric Acc | Latency |
|---|---|---|---|---|
| **gemma-4-31B-it** ⭐ | 93.3% | **0.004** | **97%** | ~4.8s |
| Qwen2.5-VL-7B | 86.7% | 0.076 | 81% | 1.6s (nhanh nhưng **lỗi đơn vị tiền tệ**: 4000 tỷ ↔ 4 tỷ) |
| gemma-3-27b-it | 60.0% | 0.263 | 50% | 3.5s (loại — vỡ JSON) |

> ⚠️ Mặc định trong code là `Qwen2.5-VL-7B-Instruct` (nhẹ), nhưng **cloud đã override
> sang `gemma-4-31B-it`** ở cả `agent-engine` và `backend`. Khi chạy local nhớ set
> `VISION_MODEL=gemma-4-31B-it` để có độ chính xác như bản deploy.

## Đổi model ở đâu

- **Local**: sửa `agent_engine/.env` (PLANNER/SPECIALIST/VISION_MODEL) và `backend/.env.local`.
- **Cloud (Railway)**: `railway variables --service agent-engine --set VISION_MODEL=...`
  và `--service backend --set VISION_MODEL_NAME=...` rồi redeploy.
