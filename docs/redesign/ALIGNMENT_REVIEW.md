# Đối chiếu 3 phần: infra ↔ backend ↔ frontend ↔ services mới

> Rà soát khớp/lệch giữa hạ tầng có sẵn và kiến trúc redesign 3-máy. Ngày rà: phiên 2026-07-19.
> Kết luận nhanh: **infra khớp tốt (~90%)**; **backend trùng lặp logic với Engine mới** (đúng
> "2 lớp agent" đã ghi nhận); **frontend mới là scaffold**. Không có lệch nào chặn tiến độ;
> 1 lệch trong code Engine đã **sửa ngay** (tên bảng SQL).

## A. Infra (Postgres/Redis) ↔ services mới (OCR/Engine/Platform)

| Hạng mục | Trạng thái | Ghi chú |
|---|---|---|
| `document.document_line` (V019) | ✅ Khớp | Worker OCR ghi đúng 10 cột; `bbox` JSONB {x,y,w,h}, `page_number` tách riêng — khớp `_xywh()` của worker. |
| `identity.employee_scope` | ✅ Có sẵn | Đúng nguồn để Platform dựng `AuthorizedScope` (customer/loan nhân viên được phép). |
| `customer.*` (customer, organization_profile, person_profile, income_source, employment) | ✅ Khớp | Phủ cả 2 loại hồ sơ: doanh nghiệp (ratios) và cá nhân (income/DTI). |
| `banking.account_monthly_summary`, `banking.transaction_default`, `banking.account` | ✅ Có sẵn | Nguồn cho SQL tool của Credit agent. Summary keyed theo `account_id`. |
| Engine SQL whitelist | ⚠️→✅ **ĐÃ SỬA** | Ban đầu Engine bịa tên `banking.monthly_feature`. Đã đổi `banking.account_monthly_summary` + JOIN `banking.account` để **ép scope theo `customer_id`** (bảng keyed theo account). Cột khớp schema V005. |
| `document.document.processing_status` | ⚠️ Kiểm | Là `VARCHAR(30)` không có CHECK enum. Worker set `OCR_READY/OCR_FAILED` (string) — chạy được, nhưng **nên thêm CHECK** khớp `DocumentStatus` để chặn giá trị sai. |
| Kafka topics (document-events…) | ⚠️ Lệch chủ đích | Redesign **bỏ Kafka cho OCR**, dùng Redis `queue:ocr`. Topic Kafka cũ còn trong infra nhưng không dùng cho luồng OCR mới. Trên box demo: TẮT Kafka. |
| Producer đẩy `queue:ocr` | ❌ Chưa có | Worker (consumer) đã xong; **chưa có producer**. Đây là Mục 6 (Platform upload→enqueue). Loop OCR khép ở tầng producer khi làm Platform. |

## B. Backend cũ (`backend/app`) ↔ Engine mới (Máy 2)

- ⚠️ **Trùng lặp logic (đúng "2 lớp agent"):** `backend/app/agents/*` (orchestrator, credit_agent,
  compliance_agent, document_agent, synthesizer, validator, dynamic_planner) **lặp lại** thứ vừa
  build trong `services/engine/`. Citation hiện của backend đến từ `agent_simulation_service`
  (`NumberedCitation`, scenario MOCK) — tức **mô phỏng**, chưa phải phân tích thật.
  → **Hướng redesign:** backend giữ vai Platform (auth, data, conversation, calculations,
  document_processing) và **DELEGATE phân tích sang Engine qua HTTP**; gỡ dần agent in-process.

- ✅ **API surface tái dùng được:** backend đã có sẵn thứ Platform cần —
  `/customers/{id}/transactions|transaction-summary|accounts|documents`,
  `/loan-applications/{id}/analyses|calculations|decisions|policy-checks`,
  `/reports/{id}/claims|download-url`, `/conversations`, `/analysis-jobs/{id}/stream`.
  Platform mới có thể **giữ router, đổi tầng thực thi** (gọi Engine thay vì agent nội bộ).

- 🔌 **Điểm nối citation:** `NumberedCitation` có `source_type` + `source_id` + `source_locator: dict`
  + `quoted_text` → **map thẳng** được từ `Citation` của Engine (đặt `bbox` vào `source_locator`).
  Nhưng `ReportClaimResponse` (bản API/persisted) **chưa expose citation** cho FE → cần bổ sung khi nối Engine.

## C. Frontend ↔ backend

- Frontend hiện **chỉ là scaffold** (`src/main.tsx` + `vite.config`), chưa có màn hình thật.
  Env đã định: `VITE_API_BASE_URL` (`/api/v…`), Keycloak (`URL/REALM/CLIENT_ID`), `VITE_USE_MOCK_API`.
  → Hợp đồng FE↔BE: **REST versioned + Keycloak SSO** — khớp backend. Chưa thể nói "khớp UI" vì chưa có UI.
- ❌ **Thiếu endpoint citation-resolve** (Mục 6): `GET /citations/{id}/resolve` → trả `document_id`+`bbox`
  để FE highlight kiểu NotebookLM. Chưa có trong router backend. Cần thêm khi làm Platform (query `document.document_line`).

## Việc cần làm (dẫn xuất từ rà soát)

1. **[Platform/Mục 6]** Upload→enqueue `queue:ocr` (khép loop OCR) + `GET /citations/{id}/resolve`.
2. **[Platform/Mục 6]** Gỡ agent in-process ở backend, gọi Engine `POST /analyze`; map `Citation`→`NumberedCitation` (bbox vào `source_locator`); expose citation trong `ReportClaimResponse`.
3. **[infra, nhỏ]** Thêm CHECK cho `document.document.processing_status` khớp `DocumentStatus`.
4. **[deploy/Mục 7]** compose 1 box: TẮT Kafka/MinIO, bật Redis + ocr + worker + engine + platform.
