# BUILD STATUS — Redesign 3-máy (điểm dừng để tiếp tục sau)

> Cập nhật: phiên làm việc trước khi tắt máy. Đọc file này đầu tiên khi quay lại.
> Tài liệu liên quan: [`PLAN.md`](./PLAN.md), [`api-contracts.md`](./api-contracts.md).

## Quyết định kiến trúc đã chốt (không bàn lại)

- **3 service logic**: Platform (Máy 1) / Deep-Research Engine (Máy 2) / OCR (Máy 3),
  giao tiếp **HTTP API**. Nhưng **deploy chung 1 box** (AWS 2vCPU/8GB) cho demo.
- **OCR async qua Redis** (BỎ Kafka trên box demo). Storage dùng **S3** (BỎ MinIO).
- **LLM/OCR qua API remote** (không chạy model local). OCR = **Azure Document
  Intelligence `prebuilt-read`** (OCR truyền thống, trả bbox) — thay cho vision-LLM,
  để **lưu toạ độ** phục vụ highlight kiểu NotebookLM + bôi đen PII.
- **SQL agent gộp vào Credit** (tool NL→SQL, phải scope read-only theo quyền NV).
- **Legal + Document = MOCK** (đúng schema thật, cắm microservice sau).
- **Deep-research**: Credit/Legal/Document chạy **song song** → mỗi cái 1 báo cáo
  có nguồn → **Compose** tổng hợp + đánh nguồn (verify chống bịa) + eval/feedback.
- **Codebase**: làm lại sạch trong `services/` + `libs/`, tái dùng logic cũ khi hợp lý.

## 3 rủi ro phải khoá (nhắc lại mỗi lần code)
1. **SQL scoping**: Credit+SQL role chỉ-đọc + whitelist bảng + ép `WHERE` theo `authorized_scope`.
2. **Compose không bịa nguồn**: citation phải resolve về Citation thật của specialist.
3. **Mock = hợp đồng thật**: Legal/Document mock trả đúng `DomainReport` schema.

## ĐÃ LÀM XONG ✅ (mục 1–4) — đã verify

| Mục | Nội dung | File |
|---|---|---|
| 1 | Contracts dùng chung | `libs/contracts/` : `_enum.py`, `geometry.py` (BBox), `citation.py` (Citation/SourceType), `ocr.py` (DocumentOCR/OcrPage/OcrLine/OcrWord/OcrField + DTO extract/redact), `document.py` (DocumentStatus + `documents_ready()` gating + OcrJob), `__init__.py` |
| 2 | OCR service (Máy 3) | `services/ocr/` : `config.py`, `providers/base.py`, `providers/azure_read.py` (Azure REST poll), `providers/mock.py` (bbox giả hợp lệ), `redaction.py` (Pillow/PyMuPDF), `app.py` (FastAPI `/ocr/extract` `/ocr/redact` `/health`), `requirements.txt`, `Dockerfile`, `README.md` |
| 3 | OCR async Redis | `services/common/redis_queue.py` (BLMOVE reliable + retry + dead-letter), `services/common/db.py` (asyncpg pool), `services/worker/ocr_worker.py` (consume→OCR→lưu bbox→OCR_READY), `config.py`, `requirements.txt`, `Dockerfile` |
| 4 | Migration lưu bbox | `infra/database/migrations/V019__create_document_ocr_lines.sql` (bảng `document.document_line`: text + bbox JSONB + words JSONB, mức dòng/từ) |

**Đã kiểm chứng**: `py_compile` sạch toàn bộ file mới; smoke test mock OCR sinh bbox
hợp lệ, Citation trỏ document+bbox, `documents_ready()` gating đúng. (pydantic 2.13.4)

**Luồng async đã khép**:
`upload → OcrJob vào Redis → worker → OCR service → bbox vào Postgres → OCR_READY`
(tác vụ KHÔNG cần tài liệu chạy ngay, không chờ OCR).

## ĐÃ LÀM XONG ✅ (mục 5 — Engine) — đã verify trong container

| Mục | Nội dung | File |
|---|---|---|
| C1 | Contracts báo cáo/analysis | `libs/contracts/report.py` (Domain/Claim/DomainReport + bất biến chống bịa nguồn, ComposedReport, `collect_citations`), `libs/contracts/analysis.py` (AuthorizedScope, AnalysisRequest/Response, AgentRoute 5 mức, AnalysisMode) — export trong `__init__` (28 symbols) |
| 5a | SQL guard + data client | `services/engine/data_client.py`: `build_scoped_sql` (whitelist bảng/cột + ÉP `customer_id=ANY(scope)`, spec có cấu trúc thay NL→SQL tự do), `MockDataClient` fixture (An Phát) |
| 5b | 3 specialist | `services/engine/agents/`: `credit.py` (REAL: DSCR/LTV/SQL, citation RECORD+SQL), `legal.py` (MOCK: citation POLICY), `document.py` (MOCK: citation DOCUMENT+bbox) |
| 5c | Compose + verify | `services/engine/compose.py`: `verify_claim` loại citation không resolve → hạ cấp `unsupported` |
| 5d | Orchestrator | `services/engine/orchestrator.py`: fan-out `asyncio.gather` song song, partial-failure cô lập, eval/feedback loop giới hạn vòng |
| 5e | LLM + API + deploy | `llm.py` (narrate, **mock fallback** offline), `app.py` (`POST /analyze`, `/health`), `config.py`, `requirements.txt`, `Dockerfile`, `smoke_test.py` |

**Đã kiểm chứng**: `py_compile` sạch; `python -m services.engine.smoke_test` PASS 4 mục
(SQL scoping chặn ngoài scope + bảng lạ; compose loại citation bịa; deep-research 10 nguồn
/3 bbox; partial-failure). **Đã build `shb-engine:dev` (273MB) + chạy container**: `/health`
ok, `POST /analyze` trả ComposedReport có nguồn qua HTTP. Lệnh test:
`docker build -f services/engine/Dockerfile -t shb-engine:dev .` → `docker run -p 8200:8200`.

## ĐÃ LÀM XONG ✅ (OCR thật + data thật + đối chiếu) — phiên 2026-07-19 (2)

- **Azure OCR THẬT**: `services/engine/fixtures/build_ocr_fixtures.py` chạy `prebuilt-read`
  trên **66 tài liệu / 6 hồ sơ**, tự map thư mục↔case (CR-A01..CR-I03), cache resumable,
  xoay 2 Azure resource, retry 429 backoff (đã thêm vào `azure_read.py`). Fixture bbox thật ở
  `services/engine/fixtures/ocr/*.json` (gitignored). Key Azure ở `.env` (gitignored; file
  `Azure_Cognitive_Services_Resources.md` cũng đã gitignore — **rotate key sau demo**).
- **Data THẬT-cấu-trúc**: `fixtures/casebook.py` nạp `mock_6_credit_cases_full.json` (12 tháng
  features + giao dịch + metrics/DTI) → `customer_uuid = uuid5(customer_id)`. `data_client`
  rewrite dùng casebook; Credit agent xử lý cả doanh nghiệp (ratios) lẫn cá nhân (DTI); Document
  agent dùng **OCR bbox thật**. Smoke test chạy deep-research **cả 6 case**, mọi luận điểm có nguồn,
  0 bịa nguồn, runtime-scoping chặn KH ngoài quyền. Mapping case→uuid xem log phiên.
- **Đối chiếu 3 phần**: `docs/redesign/ALIGNMENT_REVIEW.md`. Infra khớp ~90%; **đã sửa** lệch
  tên bảng SQL Engine (`banking.account_monthly_summary` + JOIN account ép scope). Backend trùng
  agent (2 lớp) → Platform sẽ delegate sang Engine. Frontend mới là scaffold.

## ĐÃ LÀM XONG ✅ (Frontend demo chuyên viên) — phiên 2026-07-19 (3)

Kịch bản trình diễn + cách chạy: [`DEMO_SCRIPT.md`](./DEMO_SCRIPT.md).

- **Đăng nhập thật thay cho nút chuyển hướng**: `src/auth/demoAccounts.ts` (2 tài khoản
  `chuyenvien1`/`chuyenvien2`), `src/auth/demoSession.ts` (phiên lưu `sessionStorage`,
  `useSyncExternalStore`). `keycloak.ts` ở mock mode nay đọc phiên demo thay vì luôn trả
  `true` → luồng "chưa đăng nhập không vào được" mới demo được.
- **Trang đăng nhập dựng lại**: bố cục 2 cột (tấm thương hiệu + biểu mẫu), biểu mẫu
  antd có validate, thẻ tài khoản demo bấm-để-điền, gập 1 cột dưới 992px.
- **Phạm vi dữ liệu theo quyền** (bản thu nhỏ của `AuthorizedScope`): mỗi tài khoản được
  phân công 3 khách hàng rời nhau. Ép ở `customerService.listCustomers`, `mockApi`
  (từ chối kèm bước ghi vết `enforce_authorized_scope`), và chặn cả khi gõ thẳng
  `/customer/:id`. Hạn mức phê duyệt bám theo người đăng nhập (`approvalScope.ts`).
- **Nghiệm thu 14/14 kiểm thử tự động** trên logic đã bundle (6 phân quyền/phiên +
  8 hành vi agent), `npm run build` và `tsc --noEmit` sạch, dev server phục vụ 200.

> Đầu ra 3 agent vẫn là **mock** — chưa nối `services/engine/` vào frontend. Đây là
> việc của mục 6 (Platform) bên dưới.

## CÒN LẠI ⏳ — TIẾP TỤC TỪ ĐÂY

### Mục 6 — Platform (Máy 1) ← **LÀM TIẾP CÁI NÀY** (giờ Engine + OCR thật + data thật đã sẵn)
- [ ] Endpoint upload: lưu file gốc (S3) → **enqueue OcrJob** (Redis, kèm presigned `file_url`) → trả `OCR_PENDING`.
- [ ] **Agent User 5 mức**: LLM phân loại intent + rào tất định (auth-first, off-topic).
      Tham chiếu logic cũ `backend/app/agents/context_router.py` (đang là keyword thuần → nâng cấp LLM+guard).
- [ ] **Gating**: tác vụ cần tài liệu chờ `OCR_READY`; không cần thì chạy ngay.
- [ ] **Data API scoped** cho Engine gọi ngược (SQL read-only ép `authorized_scope`).
- [ ] **Citation-resolve API**: `GET /citations/{id}/resolve` → trả bbox/doc để UI highlight
      (query bảng `document.document_line`).

### Mục 5 — Engine (Máy 2)
- [ ] Orchestrator deep-research (fan-out song song 3 specialist) — tham chiếu
      `agent_engine/gateway/orchestrator.py` + `backend/app/agents/orchestrator.py`.
- [ ] Credit agent (+SQL tool có rào chắn) — tái dùng `agent_engine/agents/credit_agent.py`.
- [ ] Legal + Document agent MOCK trả `DomainReport`.
- [ ] Compose agent: tổng hợp + citation NotebookLM + **verify chống bịa nguồn**.
- [ ] Eval + feedback loop (giới hạn vòng).

### Mục 7 — Deploy 1 box
- [ ] `infra/docker-compose.app.yml`: redis + ocr + worker + engine + platform (dùng chung Postgres của infra).
- [ ] `.env.example` cho services (OCR_PROVIDER, AZURE_DI_*, REDIS_URL, DATABASE_URL, OCR_SERVICE_URL, FPT_API_KEY...).
- [ ] Ép heap Keycloak `-Xmx512m`, TẮT Kafka/MinIO container.

## Gotchas khi deploy (đã phân tích)
- `infra/docker-compose.infra.yml` bind `127.0.0.1` + network `internal: true`
  → chỉ chạy 1 box. Nếu sau này tách máy: bỏ 127.0.0.1, mở security group.
- **V019 phải nằm trong lần `flyway migrate` đầu** (báo trước khi migrate).
- Postgres cần extension `pgvector` + `citext` (đã có trong image infra).
- Bind mount / build context của Dockerfile services = **REPO ROOT** (cần cả `libs/`).

## Lệnh chạy nhanh (sau khi có infra)
```bash
# OCR service (mock, không cần Azure)
OCR_PROVIDER=mock uvicorn services.ocr.app:app --port 8300
# OCR worker
REDIS_URL=redis://localhost:6379/0 DATABASE_URL=postgresql://... \
  OCR_SERVICE_URL=http://localhost:8300 python -m services.worker.ocr_worker
```
