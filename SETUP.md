# Hướng dẫn cài đặt và khởi chạy dự án — SHB AI Assistant

## Tổng quan

Dự án **AI Credit Intelligence Workbench** (SHB AI Assistant) gồm 3 phần:

| Phần | Công nghệ | Cổng |
|---|---|---|
| **Infrastructure** | Docker (PostgreSQL 18 + pgvector, Redis, Kafka KRaft, MinIO, Keycloak) | 5432, 6379, 29092, 9000, 8080 |
| **Backend** | Python 3.12 + FastAPI + SQLAlchemy + Pydantic v2 | 8000 |
| **Frontend** | React 19 + TypeScript + Vite + Ant Design 6 | 3000 |

---

## Yêu cầu hệ thống

| Phần mềm | Phiên bản | Ghi chú |
|---|---|---|
| **Docker Desktop** | ≥ 4.x (WSL2 backend) | Chạy trước khi khởi động infra |
| **Python** | 3.12.x | Cài `py.exe` launcher từ python.org |
| **Node.js** | ≥ 20 (khuyến nghị 24) | Bao gồm npm |
| **Git** | ≥ 2.x | Quản lý mã nguồn |

> [!IMPORTANT]
> Docker Desktop phải chạy ở chế độ **WSL2 backend** (không phải Hyper-V).
> Dự án yêu cầu khoảng **4 GB RAM** cho Docker containers.

---

## Khởi chạy nhanh (1 lệnh)

```powershell
# Clone và khởi động toàn bộ dự án
cd D:\dushdask
.\Activate.ps1
```

Script `Activate.ps1` sẽ tự động:
1. ✅ Kiểm tra Docker, Python 3.12, Node.js
2. ✅ Sinh secrets cho infrastructure (`infra/.env.local`)
3. ✅ Khởi động Docker containers (PostgreSQL, Redis, Kafka, MinIO, Keycloak)
4. ✅ Chạy database migrations + seed data
5. ✅ Sinh `backend/.env.local` từ secrets của infrastructure
6. ✅ Cài đặt Python dependencies + tạo virtual environment
7. ✅ Khởi động FastAPI server (port 8000)
8. ✅ Sinh `frontend/.env.local`
9. ✅ Cài đặt npm dependencies
10. ✅ Khởi động Vite dev server (port 3000)

---

## Các chế độ chạy

### Chế độ đầy đủ (Full Stack)
```powershell
.\Activate.ps1
```
Chạy cả 3 phần. Yêu cầu Docker Desktop đang hoạt động.

### Chế độ Mock (Frontend Only — Không cần Docker)
```powershell
.\Activate.ps1 -MockMode
```
Chỉ chạy frontend với dữ liệu demo. **Không cần Docker, Python, hay backend**.
Phù hợp để xem giao diện và demo nhanh.

### Bỏ qua Infrastructure (Infra đã chạy sẵn)
```powershell
.\Activate.ps1 -SkipInfra
```

### Bỏ qua Backend
```powershell
.\Activate.ps1 -SkipBackend
```

---

## Cài đặt thủ công (từng bước)

### Bước 1: Infrastructure

```powershell
cd D:\dushdask\infra

# 1.1 Sinh secrets (chạy 1 lần)
.\scripts\generate-secrets.ps1

# 1.2 Khởi động toàn bộ infrastructure
.\scripts\bootstrap.ps1

# 1.3 (Tuỳ chọn) Kiểm tra trạng thái
.\scripts\stack.ps1 infra-ps

# 1.4 (Tuỳ chọn) Bật dev tools
.\scripts\stack.ps1 tools-up            # PgAdmin :5050, Kafka UI :8085
.\scripts\stack.ps1 observability-up     # Prometheus :9090, Grafana :3001
```

### Bước 2: Backend

```powershell
cd D:\dushdask\backend

# 2.1 Tạo .env.local (copy từ .env.example rồi điền secrets từ infra/.env.local)
# Hoặc dùng Activate.ps1 để tự sinh.

# 2.2 Cài đặt Python dependencies
.\scripts\install.ps1

# 2.3 Chạy backend API server
.\scripts\run.ps1              # Chạy bình thường
.\scripts\run.ps1 -Reload      # Hot-reload khi sửa code

# 2.4 (Tuỳ chọn) Chạy tests
.\scripts\test.ps1              # Unit tests
.\scripts\test.ps1 -Integration # Bao gồm integration tests

# 2.5 (Tuỳ chọn) Kiểm tra code quality
.\scripts\lint.ps1              # ruff + mypy
```

### Bước 3: Frontend

```powershell
cd D:\dushdask\frontend

# 3.1 Tạo .env.local
Copy-Item .env.example .env.local
# Sửa VITE_USE_MOCK_API=true nếu muốn chạy demo không cần backend

# 3.2 Cài đặt npm dependencies
npm install

# 3.3 Chạy dev server
npm run dev                     # → http://localhost:3000

# 3.4 (Tuỳ chọn) Build production
npm run build
npm run preview                 # Preview build → http://localhost:4173
```

---

## Mapping secrets từ Infrastructure → Backend

Khi tạo `backend/.env.local` thủ công, cần lấy giá trị từ `infra/.env.local`:

| Backend `.env.local` | ← Lấy từ `infra/.env.local` |
|---|---|
| `DATABASE_PASSWORD` | `POSTGRES_APP_PASSWORD` |
| `DATABASE_USER` | `POSTGRES_APP_USER` |
| `DATABASE_URL` | `postgresql://{POSTGRES_APP_USER}:{POSTGRES_APP_PASSWORD}@localhost:5432/bank_ai` |
| `KAFKA_SASL_PASSWORD` | `KAFKA_BANK_API_PASSWORD` |
| `REDIS_PASSWORD` | `REDIS_PASSWORD` |
| `REDIS_URL` | `redis://:{REDIS_PASSWORD}@localhost:6379/0` |
| `MINIO_SECRET_KEY` | `MINIO_BANK_API_SECRET_KEY` |
| `FIELD_ENCRYPTION_KEY` | `FIELD_ENCRYPTION_KEY` |

> [!TIP]
> Sử dụng `.\Activate.ps1` ở thư mục gốc để tự động tạo `backend/.env.local` từ infra secrets.

---

## Tài khoản demo

Sau khi bootstrap, Keycloak tự tạo các tài khoản demo:

| Tài khoản | Vai trò | Mật khẩu |
|---|---|---|
| `credit.officer@example.local` | Credit Officer | Lấy từ `SEED_USER_PASSWORD` trong `infra/.env.local` |
| `credit.manager@example.local` | Credit Manager | — nt — |
| `document.reviewer@example.local` | Document Reviewer | — nt — |
| `compliance@example.local` | Compliance Officer | — nt — |
| `approver@example.local` | Loan Approver | — nt — |
| `auditor@example.local` | Auditor | — nt — |
| `admin@example.local` | Admin | — nt — |

---

## Các dịch vụ và cổng

### Core Services (luôn chạy)
| Dịch vụ | Cổng | URL |
|---|---|---|
| PostgreSQL | `localhost:5432` | — |
| Redis | `localhost:6379` | — |
| Kafka (external) | `localhost:29092` | — |
| MinIO S3 API | `localhost:9000` | http://localhost:9000 |
| MinIO Console | `localhost:9001` | http://localhost:9001 |
| Keycloak | `localhost:8080` | http://localhost:8080 |
| Backend API | `localhost:8000` | http://localhost:8000/docs |
| Frontend | `localhost:3000` | http://localhost:3000 |

### Dev Tools (tuỳ chọn)
| Dịch vụ | Cổng | Cách bật |
|---|---|---|
| PgAdmin | `localhost:5050` | `.\infra\scripts\stack.ps1 tools-up` |
| Kafka UI | `localhost:8085` | — nt — |
| Prometheus | `localhost:9090` | `.\infra\scripts\stack.ps1 observability-up` |
| Grafana | `localhost:3001` | — nt — |

---

## Quản lý Infrastructure

```powershell
cd D:\dushdask\infra

.\scripts\stack.ps1 infra-ps        # Xem trạng thái containers
.\scripts\stack.ps1 infra-logs       # Xem logs (tail -f)
.\scripts\stack.ps1 infra-down       # Tắt containers (giữ data)
.\scripts\stack.ps1 infra-reset -Force  # Xoá toàn bộ data + containers
.\scripts\stack.ps1 db-shell         # Truy cập PostgreSQL shell
.\scripts\stack.ps1 verify           # Kiểm tra toàn bộ stack
```

---

## Xử lý sự cố

### Docker Desktop không khởi động
- Kiểm tra WSL2 đã cài đặt: `wsl --status`
- Khởi động lại Docker Desktop
- Dùng `-MockMode` để chạy frontend demo trong khi chờ

### Backend không kết nối được database
- Kiểm tra infra đang chạy: `.\infra\scripts\stack.ps1 infra-ps`
- Kiểm tra `backend/.env.local` có đúng credentials
- Thử xoá và tạo lại: xoá `backend/.env.local`, chạy lại `.\Activate.ps1`

### Frontend lỗi kết nối Keycloak
- Kiểm tra Keycloak đang chạy: http://localhost:8080
- Nếu chỉ muốn xem UI: sửa `VITE_USE_MOCK_API=true` trong `frontend/.env.local`
- Hoặc chạy `.\Activate.ps1 -MockMode`

### Port đã bị chiếm
```powershell
# Kiểm tra port nào đang bị dùng
netstat -ano | findstr :8000   # Backend
netstat -ano | findstr :3000   # Frontend
netstat -ano | findstr :5432   # PostgreSQL
```

### Reset toàn bộ
```powershell
# Xoá infrastructure data
.\infra\scripts\stack.ps1 infra-reset -Force

# Xoá backend venv
Remove-Item -Recurse backend\.venv

# Xoá frontend node_modules
Remove-Item -Recurse frontend\node_modules

# Xoá generated env files
Remove-Item backend\.env.local
Remove-Item frontend\.env.local

# Chạy lại từ đầu
.\Activate.ps1
```
