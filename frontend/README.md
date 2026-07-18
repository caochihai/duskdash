# SHB AI Assistant — Digital Expert Agents

> **Trọn tâm đồng hành – Thông minh trong từng tương tác**

Frontend demo cho **hệ chuyên gia số đa agent** phục vụ vận hành ngân hàng SHB.

## Người dùng là ai?

**Nhân viên ngân hàng (chuyên viên tín dụng), KHÔNG phải khách hàng cuối.**

Đây là quyết định sản phẩm quan trọng nhất, bám theo đề bài *"Digital Expert Agents – A Team of AI
Specialists for **Banking Operations**"*: các agent *"execute actions within SHB's **operational
systems**"*, đại diện cho *"multiple **specialist departments**"* (Credit, Legal/Compliance,
Operations, Products) và *"reduces dependence on individual **experts**"*.

Hệ quả trực tiếp: chức năng **phê duyệt khoản vay** chỉ có nghĩa với chuyên viên — khách hàng không
tự duyệt khoản vay của mình.

## Hệ 5 chuyên gia số

| Agent | Vai trò |
| --- | --- |
| **Planner** | Phân rã yêu cầu, giao việc, tổng hợp kết luận |
| **Credit** | Thẩm định năng lực trả nợ, lịch sử tín dụng |
| **Legal** | Pháp lý tài sản bảo đảm, sàng lọc AML/KYC |
| **Product** | Đối chiếu điều kiện sản phẩm (LTV, kỳ hạn) |
| **Operations** | Tính đầy đủ hồ sơ, chứng từ |

> ⚠️ Đây là **bản demo frontend**. Hệ thống **không kết nối core banking**, **không tạo ra quyết định
> tín dụng thật** và **không thực hiện giao dịch**. Toàn bộ dữ liệu khách hàng/hồ sơ là **hư cấu**.

---

## 1. Chạy dự án

```bash
npm install     # cài dependencies
npm run dev     # dev server  -> http://localhost:3000
npm run build   # production build (tsc -b && vite build)
npm run preview # xem thử bản build -> http://localhost:4173
npm run typecheck
```

Yêu cầu: Node.js ≥ 20 (đã kiểm thử trên Node 24).

---

## 2. Biến môi trường

Sao chép `.env.example` thành `.env`:

```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_USE_MOCK_API=false
VITE_KEYCLOAK_URL=http://localhost:8080
VITE_KEYCLOAK_REALM=bank-ai
VITE_KEYCLOAK_CLIENT_ID=bank-ai-frontend
VITE_APP_NAME=SHB AI Assistant
VITE_APP_ENV=development
```

| Biến | Ý nghĩa |
| --- | --- |
| `VITE_API_BASE_URL` | Base URL của backend. Chỉ dùng khi `VITE_USE_MOCK_API=false`. |
| `VITE_USE_MOCK_API` | `true` → dùng mock API; `false` → gọi backend thật qua Axios. |
| `VITE_KEYCLOAK_URL` | Public URL của Keycloak local. |
| `VITE_KEYCLOAK_REALM` | Realm public `bank-ai`. |
| `VITE_KEYCLOAK_CLIENT_ID` | Public PKCE client `bank-ai-frontend`; không có client secret. |
| `VITE_APP_NAME` | Tên hiển thị của ứng dụng. |
| `VITE_APP_ENV` | Môi trường chạy. |

Không lưu secret trong frontend.

### Bật / tắt mock API

- `VITE_USE_MOCK_API=true` *(mặc định)* → toàn bộ dữ liệu từ `src/services/mockApi.ts`.
  Ứng dụng chạy đầy đủ **không cần backend**.
- `VITE_USE_MOCK_API=false` → service gọi backend thật qua `src/services/apiClient.ts`.

Chuyển đổi được xử lý tập trung trong lớp service — hook và component **không cần thay đổi**.

---

## 3. Routing

| Route | Mô tả |
| --- | --- |
| `/` | Giao diện trò chuyện với hệ chuyên gia số |
| `/dashboard` | **Giám sát agent** — traces, task status, decisions, collaboration flows, so sánh hiệu năng |
| `/?view=foundation` | Foundation Page — kiểm chứng các thư viện nền tảng |
| `/foundation` | Foundation Page (đường dẫn trực tiếp) |
| `*` | Trang 404 |

Toàn bộ route khai báo tập trung tại `src/app/routes.tsx`.

---

## 4. Kiến trúc

```
src/
├── app/           # App, AppProviders, queryClient, routes
├── components/
│   ├── layout/    # AppShell, AppHeader, ConversationSidebar, MobileNavigationDrawer
│   ├── common/    # SHBLogo, AnimatedSHBLogo, LoadingScreen, QuickActionCard, ...
│   ├── ai/        # ChatWorkspace, MessageList, ChatComposer, SourceDrawer, ...
│   ├── charts/    # BaseChart adapter, LoanBreakdownChart, palette
│   └── tables/    # DataTable adapter
├── features/chat/ # constants (mock data, quick prompts, security keywords), utils
├── pages/         # ChatPage, FoundationPage, NotFoundPage
├── services/      # apiClient (Axios), mockApi, chat/conversation/attachment services
├── hooks/         # TanStack Query hooks + queryKeys
├── types/         # chat, conversation, attachment, source, user, api
├── theme/         # tokens, componentOverrides, chartTheme (ConfigProvider)
├── styles/        # reset, global (CSS variables), accessibility
└── utils/         # formatters, detectSensitiveContent
```

### Nguyên tắc phân tầng

```
Component → Hook (TanStack Query) → Service → apiClient (Axios)
```

- Component **không bao giờ** gọi Axios trực tiếp.
- TanStack Query chỉ quản lý **server state**. Trạng thái UI (sidebar, drawer, modal, input,
  hover) dùng **React local state**.
- Màu sắc đọc từ design token (`src/theme/tokens.ts`) hoặc CSS variable, không hard-code.

---

## 5. Thương hiệu

Logo SHB **chính thức** được tải từ website chính thức và lưu local trong `public/brand/`.
Ứng dụng không hotlink asset ở production. Chi tiết nguồn: [`public/brand/README.md`](public/brand/README.md).

Màu thương hiệu được **trích xuất trực tiếp từ file SVG chính thức**, không phải giá trị phỏng đoán:

| Token | Giá trị | Vai trò |
| --- | --- | --- |
| `orange.500` | `#F37021` | Màu nhấn, CTA |
| `navy.700` | `#2F2E79` | Heading, text thương hiệu |

---

## 6. Tính năng đã hoàn thiện

**Multi-agent (đề bài)**
- 5 chuyên gia số: Planner điều phối → Credit / Legal / Product / Operations thực thi → tổng hợp
- **Agent trace** mở/đóng được trên mỗi câu trả lời: từng bước, tag agent, **tool call** + kết quả
- **Tool use**: `query_credit_bureau`, `screen_aml_watchlist`, `match_product_policy`,
  `check_document_checklist`, `get_loan_application`
- **Dashboard** `/dashboard`: KPI, hiệu năng từng agent, luồng cộng tác, bảng traces
- **So sánh single-agent vs multi-agent** trên cùng hồ sơ HS-2026-0481

**Nghiệp vụ chuyên viên**
- Lệnh `/` tra cứu khách hàng (lọc không dấu, điều hướng bàn phím)
- Hồ sơ khách hàng: CCCD/SĐT **che sẵn**, thanh DTI kèm ngưỡng chính sách
- **Phê duyệt khoản vay**: Popconfirm 2 bước, **khoá khi vượt hạn mức**, cảnh báo phê duyệt ngoại lệ,
  từ chối bắt buộc nhập lý do

**Hội thoại**
- Sidebar nhóm theo Đã ghim / Hôm nay / Hôm qua / 7 ngày qua / Trước đó
- Tìm kiếm không dấu (`"vay mua nha"` tìm được `"Tư vấn vay mua nhà"`)
- Tạo, đổi tên, ghim, xoá (có optimistic update + rollback khi lỗi)
- Sidebar thu gọn / mở rộng, Drawer trên mobile

**AI UX**
- Welcome State + 6 quick prompt
- Trạng thái xử lý cấp cao (kết nối → xác định nhu cầu → tra cứu → tổng hợp)
- Streaming mock theo chunk, **dừng** giữa chừng, tạo lại, sao chép, đánh giá
- Nguồn tham khảo (Source Drawer), gợi ý câu hỏi tiếp theo
- Nội dung phong phú: markdown, bảng, biểu đồ, product card, loan card, alert, CTA, disclaimer

**Tài liệu**
- Upload PDF/DOCX/XLSX/PNG/JPG, tiến trình, xoá, lỗi định dạng, giới hạn 10 MB

**An toàn**
- Cảnh báo khi phát hiện từ khoá nhạy cảm (mật khẩu, PIN, OTP, CVV…)
- Disclaimer tư vấn tài chính; nêu rõ demo không thực hiện giao dịch
- Không log token/OTP/mật khẩu/nội dung file

---

## 7. Dữ liệu giả lập

Những phần sau đang dùng **dữ liệu minh hoạ**, cần thay bằng API thật:

- Danh sách hội thoại và tin nhắn (`src/features/chat/constants/`)
- Câu trả lời của AI (`src/services/mockApi.ts`) — chọn theo từ khoá, không phải mô hình thật
- Lãi suất giả định 9%/năm và công thức niên kim (`loanCalculator.ts`) — **không** phải chính sách
  tín dụng của SHB
- Nguồn tham khảo, upload attachment, hồ sơ người dùng demo (`DEMO_USER` trong `ChatPage.tsx`)

**Trigger mô phỏng lỗi** (gõ vào composer): `mô phỏng timeout`, `mô phỏng mất kết nối`,
`mô phỏng lỗi`. Upload file có chữ `loi` trong tên để mô phỏng upload thất bại.

---

## 8. API contract đang tích hợp

```
GET    /api/v1/me
GET    /api/v1/customers
GET    /api/v1/customers/:id/loan-applications
POST   /api/v1/customers/:id/assignment/claim

GET    /api/v1/conversations
POST   /api/v1/conversations
PATCH  /api/v1/conversations/:id
POST   /api/v1/conversations/:id/close
GET    /api/v1/conversations/:id/messages
POST   /api/v1/conversations/:id/messages

POST   /api/v1/documents/uploads
PUT    <MinIO presigned URL>
POST   /api/v1/documents/uploads/:uploadId/complete
```

Backend trả trực tiếp contract `snake_case`; adapter trong `src/services/backendAdapters.ts`
chuyển sang kiểu UI hiện có. Message endpoint trả đồng bộ user message và assistant message.
Streaming chỉ còn ở mock mode cho tới khi backend có stream contract chính thức.

---

## 9. Bảo mật khi render nội dung AI

Ứng dụng **không dùng `dangerouslySetInnerHTML` ở bất kỳ đâu**.

- Markdown được parse thành cấu trúc dữ liệu (`parseMarkdown.ts`), sau đó dựng thành React element
  (`MarkdownContent.tsx`) → không có đường cho script injection.
- Link chỉ chấp nhận `http`/`https` (chặn `javascript:`, `data:`); link ngoài dùng
  `rel="noopener noreferrer"`.
- Nội dung phong phú dùng union có kiểu rõ ràng (`MessageBlock`) thay vì HTML thô.

---

## 10. Accessibility

- Đúng **một `h1`** trên màn hình ở mọi trạng thái
- Focus ring cam rõ ràng, skip link tới nội dung chính
- `aria-label` cho mọi icon-only button, `aria-expanded` cho sidebar toggle
- `aria-live` cho trạng thái AI đang xử lý; `role="img"` + mô tả text cho biểu đồ
- Tôn trọng `prefers-reduced-motion`
- Không dùng màu làm tín hiệu duy nhất

---

## 11. Ghi chú kỹ thuật

- **Chart được lazy-load.** `@ant-design/charts` (~1,4 MB) chỉ tải khi câu trả lời có biểu đồ.
  `manualChunks` cố ý **không** gom thư viện chart, vì làm vậy sẽ tạo cạnh import tĩnh từ entry
  và kéo toàn bộ thư viện vào lần tải đầu.
- Nội dung hội thoại **không** lưu vào `localStorage` (có thể chứa dữ liệu nhạy cảm) — mock store
  nằm trong bộ nhớ và mất khi refresh.
- Stream bị huỷ khi unmount hoặc khi người dùng bấm dừng (`AbortController`), không setState sau unmount.
