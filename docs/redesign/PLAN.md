# Redesign — Kiến trúc Multi-Agent 3 máy (Platform / Engine / OCR)

> Trạng thái: **PLAN — chờ duyệt**. Chưa sửa code ứng dụng.
> Tài liệu đi kèm: [`api-contracts.md`](./api-contracts.md) (schema I/O giữa các máy).

## 0. Quyết định đã chốt

| Vấn đề | Chốt |
|---|---|
| Chia 3 máy | **Platform / Engine / OCR** (mỗi phần 1 máy, gọi nhau qua HTTP API) |
| Codebase | **Làm lại sạch** trong `services/`, tham chiếu logic cũ khi hợp lý |
| Bắt đầu | **Chốt kế hoạch trước** — giao PLAN + contracts, duyệt xong mới code |
| SQL agent | **Gộp vào Credit** (tool NL→SQL có rào chắn) |
| Legal, Document | **Mock** đúng schema thật, cắm microservice sau |
| OCR | **Azure Read / Document Intelligence** (OCR truyền thống, có bbox) thay vision-LLM |
| Đánh nguồn | Kiểu **NotebookLM**: click luận điểm → highlight đúng vùng trên tài liệu |

## 1. Tổng quan

```
┌─────────────────────────── MÁY 1: PLATFORM (public) ───────────────────────────┐
│ Frontend ◄──► Backend                                                          │
│   • Auth (Keycloak) • Postgres (system of record) • Redis • MinIO • Conversation│
│   • AGENT USER (5 mức): phân loại intent + rào auth + kiểm đủ ngữ cảnh          │
│   • Data API có scope (Engine gọi ngược để lấy dữ liệu khách theo quyền)        │
└───────────────┬────────────────────────────────────────────────────────────────┘
                │  API (analysis request + authorized_scope)     ▲ API (scoped data)
                ▼                                                 │
┌─────────────────────── MÁY 2: DEEP-RESEARCH ENGINE ────────────────────────────┐
│  Orchestrator (deep-research: fan-out song song → gom báo cáo)                  │
│    ├─ Credit  Agent (+SQL)   REAL   → báo cáo tài chính có nguồn                │
│    ├─ Legal   Agent          MOCK   → báo cáo pháp lý có nguồn                  │
│    ├─ Document Agent         MOCK   → báo cáo hồ sơ có nguồn (bbox)             │
│    └─ Compose Agent  → tổng hợp + đánh nguồn (verify chống bịa) + eval/feedback │
└───────────────┬────────────────────────────────────────────────────────────────┘
                │  API (extract / redact)
                ▼
┌─────────────────────────── MÁY 3: OCR SERVICE ─────────────────────────────────┐
│  Azure Read/Document Intelligence → text + bbox + confidence (per line/word)   │
│  Redaction (bôi đen theo bbox)  • (tuỳ chọn) trích field giữ nguyên toạ độ      │
└────────────────────────────────────────────────────────────────────────────────┘
```

Nguyên tắc: **mọi giao tiếp giữa 3 máy là HTTP API có hợp đồng schema** (không chia sẻ process/DB trực tiếp), để deploy độc lập 3 cloud.

## 2. Trách nhiệm từng máy

### Máy 1 — Platform + Agent User (5 mức)

Agent User là **cửa duy nhất** tiếp xúc nhân viên. Thứ tự xử lý: **auth trước → phân loại sau** (giữ triết lý authorization-first của code hiện tại).

| Mức | Tình huống | Route | Hành vi |
|---|---|---|---|
| **1** | Lệch chủ đề | `REFUSE` | Không trả lời, giải thích ngắn phạm vi hỗ trợ |
| **2** | Đúng chủ đề, **thiếu ngữ cảnh** | `NEEDS_CONTEXT` | Hỏi lại đúng thứ còn thiếu (customer_id / loan_id / câu hỏi) |
| **3** | Đơn giản, trả lời ngay | `DIRECT` | Trả lời + **kèm citation** (định nghĩa/FAQ từ RAG, hoặc tra cứu nhanh) |
| **4** | Đủ ngữ cảnh, **1 lĩnh vực** | `SINGLE_AGENT` | Gọi Engine chạy **1 specialist** → trả kết quả có nguồn |
| **5** | Phức tạp, **đa lĩnh vực** | `DEEP_RESEARCH` | Gọi Engine chạy **full deep-research** (3 specialist ∥ + compose) |

**Nâng cấp so với code cũ:** phân loại mức bằng **LLM intent classifier**, nhưng mức 1 (off-topic) và auth vẫn có **rào chắn tất định** để audit được. Đây là điểm code hiện tại (keyword thuần) chưa đạt.

Platform còn cung cấp **Data API có scope** cho Engine gọi ngược: Engine không tự nối DB tuỳ ý; nó nhận `authorized_scope` (danh sách customer/loan nhân viên được phép) và mọi truy vấn của Credit+SQL bị ép theo scope này.

### Máy 2 — Deep-Research Engine

Mô hình **deep research**: fan-out 3 chuyên gia **song song**, mỗi chuyên gia tự nghiên cứu và xuất **một báo cáo lĩnh vực có nguồn đầy đủ**, sau đó **Compose** tổng hợp.

- **Credit Agent (+SQL) — REAL**
  - Phân tích tài chính: DSCR, đòn bẩy, dòng tiền (tái dùng logic `credit_agent.py` cũ).
  - **SQL tool (gộp từ SQL agent)**: NL→SQL cho câu hỏi thống kê ("tổng thanh toán tháng 12", "số giao dịch tháng này"). **Bắt buộc**: role chỉ-đọc + whitelist bảng + ép `WHERE customer_id IN authorized_scope`.
  - Xuất `DomainReport` với `Citation` trỏ tới bản ghi tài chính / kết quả SQL.

- **Legal Agent — MOCK** (contract-compatible)
  - Trả `DomainReport` pháp lý (KYB/AML/policy) với citation trỏ tới điều khoản chính sách (`policy_clause_id` + quote).
  - Mock đọc từ fixture, **trả đúng schema** microservice thật sẽ trả.

- **Document Agent — MOCK** (contract-compatible)
  - Nhận **kết quả OCR (text + bbox)** từ Máy 3, kiểm tra đủ/thiếu/mâu thuẫn hồ sơ.
  - Xuất `Citation` mang **bbox** — đây là nguồn cho highlight-on-document.

- **Compose Agent**
  - Gom 3 báo cáo → báo cáo tổng hợp có cấu trúc cho người duyệt.
  - **Đánh nguồn kiểu NotebookLM**: mỗi luận điểm mang `citation_ids` trỏ về `Citation` gốc của specialist.
  - **Verify chống bịa nguồn**: từ chối/hạ cấp bất kỳ citation nào không khớp một `Citation` thật do specialist tạo.
  - **Eval + feedback loop** (đúng ý thiết kế gốc): kiểm mâu thuẫn chéo + luận điểm không nguồn → gửi feedback cho specialist chạy lại (giới hạn số vòng), rồi mới chốt.

### Máy 3 — OCR Service

- **Azure Read / Document Intelligence**: ảnh/PDF → `DocumentOCR` (page → line/word + bbox + confidence).
- **Redaction API**: nhận danh sách bbox (PII) → trả ảnh/PDF đã bôi đen.
- **(Tuỳ chọn) Field extraction**: map layout → field có cấu trúc **giữ nguyên bbox** (Azure prebuilt/custom, hoặc để Document Agent tự map — xem mục 7).

## 3. Chuỗi provenance (xương sống của citation)

```
OCR (bbox)  ──►  Document Agent Citation{doc_id,page,bbox,quote}
Postgres    ──►  Credit  Agent Citation{source=SQL/record, value, query_id}
Policy RAG  ──►  Legal   Agent Citation{policy_clause_id, quote}
                         │
                         ▼
                 Compose gom + verify  ──►  ComposedReport (mỗi câu có citation_ids)
                         │
                         ▼
                 Frontend: click câu → resolve citation → highlight bbox trên tài liệu
```

Bất biến bắt buộc: **không citation nào được tồn tại ở Compose nếu không truy được về một `Citation` gốc của specialist.** Đây là thứ ngăn "ảo giác nguồn".

## 4. Ba rủi ro phải khóa ngay từ contract

1. **SQL scoping (bảo mật):** Credit+SQL chạy trên role chỉ-đọc, whitelist schema, **ép row-level theo `authorized_scope`** Platform cấp. Không cho LLM ghép SQL tự do vào FROM/JOIN ngoài whitelist.
2. **Compose không bịa nguồn:** bước verify bắt buộc, citation không resolve được → loại khỏi báo cáo + đánh dấu "chưa có nguồn".
3. **Mock = hợp đồng thật:** Legal/Document mock trả **đúng `DomainReport` schema**; khi cắm microservice thật, Compose/Orchestrator **không đổi một dòng**.

## 5. Cấu trúc thư mục "làm lại sạch"

```
services/
  platform/            # MÁY 1 — có thể bọc/tái dùng backend hiện tại
    agent_user/        #   router 5 mức (LLM intent + guard tất định)
    data_api/          #   Data API có scope cho Engine gọi ngược
  engine/              # MÁY 2
    orchestrator/      #   deep-research fan-out + eval/feedback
    agents/
      credit/          #   REAL (+SQL tool có rào chắn)
      legal/           #   MOCK
      document/        #   MOCK
    compose/           #   tổng hợp + verify citation
  ocr/                 # MÁY 3
    azure_read/        #   client Azure + chuẩn hoá DocumentOCR
    redaction/         #   bôi đen theo bbox
libs/
  contracts/           # schema DÙNG CHUNG cả 3 máy (Citation, reports, OCR, ...)
                       # publish như package nội bộ hoặc copy khi deploy
```

`libs/contracts` là **nguồn chân lý duy nhất** cho schema I/O; cả 3 service import từ đây để không lệch hợp đồng.

## 6. Lộ trình theo phase

| Phase | Nội dung | Đầu ra kiểm chứng được |
|---|---|---|
| **0** (bản này) | Kiến trúc + hợp đồng API + schema | `PLAN.md`, `api-contracts.md` |
| **1** | `libs/contracts` + skeleton 3 service + auth service-to-service | 3 service `/health` ok, gọi nhau bằng stub |
| **2** | Máy 1 Agent User 5 mức (LLM intent + guard) | Test 5 mức; mức 4/5 gọi Engine (Engine còn stub) |
| **3** | Máy 2 Engine: orchestrator + Credit+SQL (REAL) + Legal/Document (MOCK) + Compose + eval | Deep-research chạy end-to-end với OCR stub, báo cáo có citation |
| **4** | Máy 3 OCR: Azure Read + redaction; nối Document Agent vào OCR thật | Upload ảnh → OCR bbox → Document citation → highlight |
| **5** | Citation-resolve API cho UI + hardening (SQL scope, compose verify, partial-failure) | Click câu → highlight đúng vùng; test bảo mật scope |

## 7. Điểm cần bạn xác nhận trước khi qua Phase 1

1. **Vị trí Compose:** tôi đặt ở **Máy 2 (Engine)** theo Q1. Nếu bạn muốn Compose ở gateway Máy 1 (như preview Q2), báo tôi.
2. **Cách Engine lấy dữ liệu khách:**
   - (a) **Engine gọi Data API của Platform** (khuyến nghị — Platform giữ auth, boundary sạch), hoặc
   - (b) Engine nối thẳng Postgres bằng role chỉ-đọc + scope truyền qua request.
3. **Ai trích field từ OCR:** Máy 3 (Azure Document Intelligence trả field) hay Document Agent tự map từ text+bbox? Ảnh hưởng ranh giới Máy 2/3.
4. **LLM cho Agent User & Compose:** giữ FPT gpt-oss-120b như hiện tại, hay đổi provider?
