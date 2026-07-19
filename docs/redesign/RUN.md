# CÁCH CHẠY HỆ THỐNG

> Mọi lệnh dưới đây đã được chạy thật và kiểm chứng trên máy này (2026-07-19).
> Hai phần **chạy độc lập**, chưa nối vào nhau — xem "Ranh giới hiện tại" ở cuối.

## A. Giao diện chuyên viên (dùng để demo) — không cần Docker

Đây là thứ dùng để trình diễn. Chạy hoàn toàn bằng dữ liệu mock trong trình duyệt,
không cần Postgres / Redis / Keycloak / Azure.

```bash
cd frontend
npm install          # chỉ lần đầu
npm run dev          # -> http://localhost:3000
```

Đăng nhập bằng `chuyenvien1 / chuyenvien1` hoặc `chuyenvien2 / chuyenvien2`.
Kịch bản trình diễn 8 phút: [`DEMO_SCRIPT.md`](./DEMO_SCRIPT.md).

**Lưu ý:** đừng tạo file `frontend/.env`. Không có `.env` thì mock mode tự bật.
Nếu tạo `.env` từ `.env.example`, biến `VITE_USE_MOCK_API=false` sẽ bắt frontend
gọi backend thật + Keycloak, và bản demo sẽ không đăng nhập được.

Lệnh kiểm tra: `npm run build` và `npx tsc -b --noEmit` (cả hai đều sạch).

## B. Deep-Research Engine (Máy 2) — cần Docker

Chạy được độc lập, không cần Platform, không cần mạng (LLM ở chế độ mock).

```bash
# 1. Build (build context = REPO ROOT, không phải thư mục services/engine)
docker build -f services/engine/Dockerfile -t shb-engine:dev .
```

```powershell
# 2. Chạy — dùng PowerShell, KHÔNG dùng Git Bash cho lệnh này.
#    Đường dẫn có dấu tiếng Việt bị Git Bash biến dạng nên bind mount sẽ trượt im lặng.
$repo = "d:\duskdush\duskdash\duskdash"
$data = Join-Path $repo "Hồ sơ Doanh nghiệp, Khách hàng"
docker run -d --rm -p 8200:8200 `
  -e LLM_PROVIDER=mock -e DATA_PROVIDER=mock `
  -v "${data}:/app/Hồ sơ Doanh nghiệp, Khách hàng:ro" `
  --name shb-engine shb-engine:dev
```

Bind mount là **bắt buộc** để có dữ liệu 6 hồ sơ thật: Dockerfile cố ý không COPY
thư mục hồ sơ khách hàng vào image. Fixture OCR (`services/engine/fixtures/ocr/`)
thì đã nằm trong image vì thuộc `services/engine`.

```bash
# 3. Kiểm tra
curl http://localhost:8200/health
# -> {"status":"ok","llm_provider":"mock","data_provider":"mock"}
```

### Gọi thử một lượt thẩm định

`customer_id` là `uuid5(namespace, customer_id)` — không phải `case_id`. Bảng tra:

| Case | customer_id | UUID dùng cho API |
|---|---|---|
| CR-A01 | CUST-AAD650D685505AC7 | `61eb47b2-6093-5e08-8eb0-45ddb18b30fd` |
| CR-B02 | CUST-05667ED9D57359DE | `e98141f4-b181-58bb-b3b5-da5d176addf1` |
| CR-C03 | CUST-EFA3D091B4FD59DE | `4a32c1ff-1ad1-5b8e-9fdc-9c802e20f029` |
| CR-I01 | CUST-B584464FD97D5D3D | `b5b26ba6-17f8-5065-bcc6-4493f2ea87ef` |
| CR-I02 | CUST-5585788E60685F83 | `596f226c-14d2-57ae-b419-17b9dc3e701b` |
| CR-I03 | CUST-83430494036E5B44 | `9849e86d-39b2-5bb3-8909-ce10d1642756` |

```bash
CID=61eb47b2-6093-5e08-8eb0-45ddb18b30fd
curl -s -X POST http://localhost:8200/analyze -H "Content-Type: application/json" -d "{
  \"correlation_id\": \"$(python -c 'import uuid;print(uuid.uuid4())')\",
  \"question\": \"Đánh giá khả năng trả nợ và rủi ro của khách hàng này.\",
  \"scope\": {\"employee_id\": \"$(python -c 'import uuid;print(uuid.uuid4())')\", \"customer_ids\": [\"$CID\"]},
  \"customer_id\": \"$CID\"
}"
```

**Kết quả đã kiểm chứng với CR-A01:** `domain_status` = CREDIT/LEGAL/DOCUMENT đều `OK`,
**16 trích dẫn**, trong đó **6 trích dẫn kèm bbox OCR Azure thật**, **0 luận điểm bịa
nguồn**, không cảnh báo.

Đưa một `customer_id` ngoài `scope.customer_ids` → CREDIT trả `FAILED` kèm cảnh báo
"không có hồ sơ cho customer …". Đây là rào phạm vi đang hoạt động đúng, không phải lỗi.

## Bẫy đã gặp (ghi lại để khỏi mất thời gian)

1. **Image cũ chạy nhầm dữ liệu.** Image `shb-engine:dev` build từ phiên trước không có
   thư mục `fixtures/`; nó im lặng rơi về fixture nội tuyến "An Phát" và vẫn trả kết quả
   trông rất thật (DSCR 1.63…). **Luôn build lại** trước khi demo, và kiểm chứng bằng
   `docker exec shb-engine ls /app/services/engine/fixtures/ocr/`.
2. **Bind mount trượt im lặng qua Git Bash** với đường dẫn `Hồ sơ Doanh nghiệp, Khách hàng`.
   Container vẫn khởi động bình thường, chỉ là không có dữ liệu. Dùng PowerShell.
3. **`ComposedReport` không có trường `claims`** — nó dùng `sections` + `citations`.

## Ranh giới hiện tại

- **Frontend chưa gọi Engine.** Giao diện dùng mock (`src/services/mockApi.ts`); Engine
  chạy riêng ở cổng 8200. Nối hai phần là việc của mục 6 (Platform) trong `BUILD_STATUS.md`.
- **Chưa chạy được**: Platform (Máy 1) chưa viết; OCR service + worker cần Redis/Postgres
  từ `infra/docker-compose.infra.yml` (chưa dựng trong phiên này); `docker-compose.app.yml`
  gộp cả 5 service chưa có (mục 7).
- **Key Azure trong `.env` cần rotate sau demo.**
