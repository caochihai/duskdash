# PROMPT DÀNH CHO CODING AGENT

# DỰNG INFRASTRUCTURE CHO AI CREDIT INTELLIGENCE WORKBENCH

## 0. Vai trò của bạn

Bạn là:

* Principal Infrastructure Architect.
* Senior DevOps Engineer.
* PostgreSQL Database Architect.
* Kafka Platform Engineer.
* Cloud Security Engineer.
* MinIO Object Storage Engineer.
* Keycloak Identity Engineer.

Nhiệm vụ của bạn là **trực tiếp tạo mã nguồn infrastructure chạy được**, không chỉ viết tài liệu, pseudo-code hoặc đưa ra hướng dẫn chung.

Hãy kiểm tra repository hiện tại, tạo mới hoặc chỉnh sửa các file cần thiết, chạy kiểm thử cấu hình, khởi động stack, sửa mọi lỗi phát sinh và chỉ kết thúc khi toàn bộ tiêu chí nghiệm thu được đáp ứng.

---

# 1. Bối cảnh hệ thống

Dự án có tên:

**AI Credit Intelligence Workbench**

Đây là trợ lý AI nội bộ dành cho nhân viên ngân hàng. Hệ thống hỗ trợ:

1. Tìm kiếm khách hàng và thông tin tài chính.
2. Truy vấn tài khoản và giao dịch.
3. Upload hồ sơ PDF hoặc ảnh.
4. OCR và phân loại tài liệu.
5. Trích xuất dữ liệu từ hồ sơ.
6. Đối chiếu dữ liệu giữa hồ sơ, giao dịch và thông tin khách hàng.
7. Phân tích khả năng trả nợ.
8. Kiểm tra chính sách tín dụng.
9. Điều phối các agent chuyên gia.
10. Kiểm tra bằng chứng, phép tính và citation.
11. Sinh báo cáo hỗ trợ thẩm định.
12. Cho phép người có thẩm quyền đưa ra quyết định cuối cùng.

Hệ thống không tự động phê duyệt khoản vay.

AI chỉ tạo:

* Finding.
* Cảnh báo.
* Phân tích.
* Khuyến nghị.
* Báo cáo.
* Evidence link.

Quyết định chính thức phải do nhân viên có thẩm quyền thực hiện.

---

# 2. Phạm vi được phép thực hiện

Bạn **chỉ được xây dựng lớp infrastructure**.

## 2.1. Được phép tạo

* Docker Compose.
* Docker networks.
* Docker volumes.
* PostgreSQL.
* pgvector.
* Database roles.
* Database schemas.
* SQL migrations.
* Seed data.
* Row-Level Security.
* MinIO.
* MinIO buckets.
* MinIO users, service accounts và policies.
* Redis.
* Kafka KRaft.
* Kafka topics.
* Kafka users và ACL.
* Kafka UI cho môi trường phát triển.
* Keycloak.
* Keycloak realm, clients, roles và demo users.
* Flyway migration runner.
* PgAdmin trong tools profile.
* Prometheus và Grafana trong observability profile.
* Health checks.
* Bootstrap scripts.
* Smoke tests.
* JSON Schema cho Kafka event.
* Data dictionary.
* Runbook.
* File `.env.example`.
* Makefile.
* PowerShell scripts cho Windows.
* Shell scripts cho Linux và WSL.

## 2.2. Không được phép tạo

Không xây dựng:

* Frontend React hoặc Next.js.
* Backend FastAPI.
* REST business endpoint.
* OCR implementation.
* LLM integration.
* Agent implementation.
* Prompt của agent.
* Financial calculator.
* Report generator.
* SSE endpoint.
* WebSocket endpoint.
* Business service.
* Repository layer của backend.
* Consumer nghiệp vụ.
* Producer nghiệp vụ.
* Quy trình tự động phê duyệt khoản vay.

Bạn chỉ chuẩn bị hạ tầng, database, event contract và connection contract để các lớp backend và frontend triển khai sau.

Có thể tạo các script smoke test nhỏ để:

* Publish event thử.
* Consume event thử.
* Upload object thử.
* Kiểm tra database.
* Kiểm tra token Keycloak.

Những script này không được chứa logic nghiệp vụ.

---

# 3. Kiến trúc tổng thể

Hệ thống hoàn chỉnh trong tương lai sẽ có cấu trúc:

```text
┌─────────────────────────────────────────────────────────┐
│                       FRONTEND                          │
│                                                       │
│  Next.js / TypeScript                                 │
│  - Đăng nhập bằng Keycloak                            │
│  - Gọi REST API backend                               │
│  - Nhận tiến độ qua SSE                               │
│  - Upload file bằng presigned URL                     │
└─────────────────────────┬───────────────────────────────┘
                          │ HTTPS REST / SSE
                          ▼
┌─────────────────────────────────────────────────────────┐
│                        BACKEND                          │
│                                                       │
│  - Authentication và authorization                    │
│  - Customer API                                       │
│  - Document API                                       │
│  - Loan API                                           │
│  - Chat API                                           │
│  - Presigned URL                                      │
│  - Ghi trạng thái vào PostgreSQL                      │
│  - Ghi event vào Outbox                               │
└───────┬─────────────┬──────────────┬────────────────────┘
        │             │              │
        ▼             ▼              ▼
 PostgreSQL          MinIO          Redis
        │
        │ Outbox Publisher
        ▼
      Kafka
        │
        ├── Document Workers
        ├── OCR Workers
        ├── Embedding Workers
        ├── Analysis Workers
        ├── Report Workers
        ├── Notification Gateway
        └── Audit Consumer
```

---

# 4. Vai trò của từng công nghệ

## 4.1. PostgreSQL

PostgreSQL là **nguồn sự thật nghiệp vụ**.

PostgreSQL lưu:

* Nhân viên.
* Vai trò và quyền.
* Khách hàng.
* KYC.
* Tài khoản.
* Giao dịch.
* Khoản vay.
* Metadata tài liệu.
* Metadata MinIO object.
* Trạng thái xử lý.
* Kết quả OCR đã chuẩn hóa.
* Các trường trích xuất.
* Embedding.
* Chính sách.
* Agent task.
* Finding.
* Evidence.
* Báo cáo.
* Background job.
* Outbox event.
* Inbox event.
* Idempotency record.
* Notification.
* Audit log.
* Retention rule.

Không lưu file PDF hoặc ảnh dạng binary lớn trong PostgreSQL.

---

## 4.2. pgvector

pgvector lưu embedding cho:

* Document chunks.
* Policy clauses.
* Các đoạn bằng chứng cần RAG.

Không dùng pgvector để:

* Tính tổng giao dịch.
* Tính thu nhập.
* Tính DTI.
* Lọc số tiền.
* Thay thế SQL quan hệ.

Vector search luôn phải được kết hợp với bộ lọc quyền truy cập và phạm vi khách hàng.

---

## 4.3. MinIO

MinIO lưu object binary:

* File upload tạm.
* PDF gốc.
* Ảnh gốc.
* Ảnh từng trang.
* OCR JSON.
* File đã che thông tin.
* Chính sách PDF.
* Báo cáo PDF.
* Audit archive.

PostgreSQL lưu metadata và vị trí của object.

Frontend không có MinIO access key.

Frontend upload/download qua presigned URL do backend cấp.

---

## 4.4. Kafka

Kafka là event bus bền vững cho các tác vụ dài:

* Xử lý tài liệu.
* OCR.
* Trích xuất dữ liệu.
* Tạo embedding.
* Phân tích khoản vay.
* Chạy agent.
* Validation.
* Sinh báo cáo.
* Notification.
* Audit projection.

Kafka không thực hiện công việc.

Worker là thành phần thực thi.

Kafka chỉ:

* Lưu event.
* Phân phối event.
* Cho phép consumer đọc lại.
* Tách producer khỏi consumer.
* Scale consumer group.
* Hỗ trợ replay.

Frontend không kết nối trực tiếp Kafka.

---

## 4.5. Redis

Redis chỉ dùng cho dữ liệu tạm thời:

* Cache.
* Distributed lock.
* Rate-limit counter.
* Session cache.
* SSE fan-out giữa nhiều backend instance.
* Presence hoặc connection metadata.
* Cache JWKS.
* Cache kết quả truy vấn ngắn hạn.

Không dùng Redis làm nguồn sự thật.

Không dùng Redis để lưu duy nhất:

* Trạng thái job.
* Kết quả OCR.
* Kết quả agent.
* Báo cáo.
* Quyết định.
* Audit log.

Các trạng thái này phải nằm trong PostgreSQL.

---

## 4.6. Keycloak

Keycloak quản lý:

* Đăng nhập.
* OIDC.
* Access token.
* Refresh token.
* Realm roles.
* Service accounts.
* Client frontend.
* Client backend.
* Client worker.

Keycloak không lưu hồ sơ nghiệp vụ nhân viên.

Thông tin nghiệp vụ nhân viên vẫn nằm trong PostgreSQL và được liên kết bằng JWT claim `sub`.

---

# 5. Luồng xử lý bất đồng bộ

## 5.1. Xử lý tài liệu

```text
Frontend upload file
    ↓
Backend tạo upload session
    ↓
Frontend PUT file qua presigned URL
    ↓
Backend xác nhận upload
    ↓
Trong cùng transaction PostgreSQL:
    - cập nhật upload status
    - tạo background_job
    - tạo event_outbox
    ↓
Outbox Publisher gửi event lên Kafka
    ↓
Document Worker nhận event
    ↓
Worker đọc file từ MinIO
    ↓
OCR / Classification / Extraction / Embedding
    ↓
Worker ghi kết quả PostgreSQL
    ↓
Worker ghi completed event vào Outbox
    ↓
Kafka
    ↓
Notification Gateway
    ↓
SSE tới Frontend
```

## 5.2. Phân tích khoản vay

```text
Frontend yêu cầu phân tích
    ↓
Backend tạo analysis_case và background_job
    ↓
Backend ghi analysis.requested vào Outbox
    ↓
Kafka
    ↓
Analysis Orchestrator
    ↓
Tạo task cho:
    - Document Agent
    - Credit Agent
    - Legal/Compliance Agent
    ↓
Các worker xử lý
    ↓
Validator
    ↓
Report Worker
    ↓
Ghi report PostgreSQL và MinIO
    ↓
Publish analysis.completed
    ↓
Notification Gateway
    ↓
Frontend nhận thông báo
```

---

# 6. Connection contract và cổng

Phải sử dụng các cổng sau trong môi trường local.

| Service          | Host URL                | Internal Docker URL    | Chức năng                |
| ---------------- | ----------------------- | ---------------------- | ------------------------ |
| PostgreSQL       | `localhost:5432`        | `postgres:5432`        | Database nghiệp vụ       |
| Redis            | `localhost:6379`        | `redis:6379`           | Cache và live fan-out    |
| Kafka external   | `localhost:29092`       | Không dùng nội bộ      | Client chạy ngoài Docker |
| Kafka internal   | Không expose trực tiếp  | `kafka:9092`           | Service nội bộ           |
| Kafka controller | Không expose            | `kafka:9093`           | KRaft controller         |
| Kafka UI         | `http://localhost:8085` | `kafka-ui:8080`        | Công cụ phát triển       |
| MinIO S3 API     | `http://localhost:9000` | `http://minio:9000`    | Object storage           |
| MinIO Console    | `http://localhost:9001` | `http://minio:9001`    | Quản trị local           |
| Keycloak         | `http://localhost:8080` | `http://keycloak:8080` | Identity Provider        |
| PgAdmin          | `http://localhost:5050` | `http://pgadmin:80`    | Công cụ DB               |
| Prometheus       | `http://localhost:9090` | `prometheus:9090`      | Metrics                  |
| Grafana          | `http://localhost:3001` | `grafana:3000`         | Dashboard                |

PgAdmin, Kafka UI, Prometheus và Grafana phải nằm trong Docker profile riêng.

---

# 7. URL contract cho backend sau này

Tạo file:

```text
infra/contracts/backend-connections.env.example
```

Nội dung:

```dotenv
# PostgreSQL
DATABASE_HOST=postgres
DATABASE_PORT=5432
DATABASE_NAME=bank_ai
DATABASE_USER=bank_app
DATABASE_PASSWORD=<secret>
DATABASE_URL=postgresql://bank_app:<secret>@postgres:5432/bank_ai

DATABASE_MIGRATION_USER=bank_migrator
DATABASE_MIGRATION_PASSWORD=<secret>
DATABASE_MIGRATION_URL=postgresql://bank_migrator:<secret>@postgres:5432/bank_ai

# Kafka
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
KAFKA_EXTERNAL_BOOTSTRAP_SERVERS=localhost:29092
KAFKA_SECURITY_PROTOCOL=SASL_PLAINTEXT
KAFKA_SASL_MECHANISM=SCRAM-SHA-512
KAFKA_SASL_USERNAME=bank-api
KAFKA_SASL_PASSWORD=<secret>
KAFKA_CLIENT_ID=bank-api

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=<secret>
REDIS_URL=redis://:<secret>@redis:6379/0
REDIS_KEY_PREFIX=bank-ai

# MinIO
MINIO_INTERNAL_ENDPOINT=http://minio:9000
MINIO_PUBLIC_ENDPOINT=http://localhost:9000
MINIO_ACCESS_KEY=bank-api
MINIO_SECRET_KEY=<secret>
MINIO_SECURE=false
MINIO_PRESIGNED_TTL_SECONDS=600

# Keycloak
KEYCLOAK_INTERNAL_URL=http://keycloak:8080
KEYCLOAK_PUBLIC_URL=http://localhost:8080
KEYCLOAK_REALM=bank-ai
KEYCLOAK_ISSUER_URL=http://localhost:8080/realms/bank-ai
KEYCLOAK_JWKS_INTERNAL_URL=http://keycloak:8080/realms/bank-ai/protocol/openid-connect/certs
KEYCLOAK_TOKEN_URL=http://localhost:8080/realms/bank-ai/protocol/openid-connect/token
OIDC_EXPECTED_AUDIENCE=bank-ai-api
```

---

# 8. Version pinning

Không sử dụng tag `latest`.

Tạo file:

```text
infra/versions.env
```

Tất cả version image phải được đặt ở đây.

Ví dụ cấu trúc:

```dotenv
POSTGRES_IMAGE=<verified-pgvector-postgresql-18-image-and-digest>
REDIS_IMAGE=<verified-official-redis-image-and-digest>
KAFKA_IMAGE=<verified-official-apache-kafka-image-and-digest>
MINIO_IMAGE=<verified-official-minio-image-and-digest>
MINIO_MC_IMAGE=<verified-official-minio-client-image-and-digest>
KEYCLOAK_IMAGE=<verified-official-keycloak-image-and-digest>
FLYWAY_IMAGE=<verified-official-flyway-image-and-digest>
KAFKA_UI_IMAGE=<verified-kafka-ui-image-and-digest>
PGADMIN_IMAGE=<verified-pgadmin-image-and-digest>
PROMETHEUS_IMAGE=<verified-prometheus-image-and-digest>
GRAFANA_IMAGE=<verified-grafana-image-and-digest>
```

Trước khi chọn image:

1. Kiểm tra official registry hoặc official documentation.
2. Chọn bản stable.
3. Pin exact version.
4. Khi có thể, pin image digest.
5. Ghi nguồn và ngày kiểm tra vào `docs/version-manifest.md`.
6. Không dùng beta hoặc release candidate.

---

# 9. Cấu trúc repository cần tạo

```text
bank-ai-workbench/
├── docker-compose.infra.yml
├── docker-compose.tools.yml
├── docker-compose.observability.yml
├── .env.example
├── .gitignore
├── Makefile
│
├── database/
│   ├── migrations/
│   │   ├── V001__create_databases_and_extensions.sql
│   │   ├── V002__create_schemas.sql
│   │   ├── V003__create_identity_tables.sql
│   │   ├── V004__create_customer_tables.sql
│   │   ├── V005__create_banking_tables.sql
│   │   ├── V006__create_storage_tables.sql
│   │   ├── V007__create_document_tables.sql
│   │   ├── V008__create_credit_tables.sql
│   │   ├── V009__create_policy_tables.sql
│   │   ├── V010__create_ai_tables.sql
│   │   ├── V011__create_integration_tables.sql
│   │   ├── V012__create_audit_tables.sql
│   │   ├── V013__create_indexes.sql
│   │   ├── V014__create_rls_functions.sql
│   │   ├── V015__create_rls_policies.sql
│   │   ├── V016__create_views.sql
│   │   └── V017__add_comments.sql
│   ├── seeds/
│   │   ├── R__seed_roles_permissions.sql
│   │   ├── R__seed_reference_data.sql
│   │   ├── R__seed_demo_customers.sql
│   │   └── R__seed_demo_transactions.sql
│   ├── bootstrap/
│   │   ├── create-databases.sh
│   │   └── create-roles.sh
│   └── README.md
│
├── infra/
│   ├── versions.env
│   ├── postgres/
│   │   ├── postgresql.conf
│   │   ├── pg_hba.conf
│   │   └── README.md
│   ├── redis/
│   │   ├── redis.conf
│   │   └── README.md
│   ├── kafka/
│   │   ├── config/
│   │   │   ├── server.properties
│   │   │   └── tools-client.properties
│   │   ├── topics/
│   │   │   └── topics.yaml
│   │   ├── acl/
│   │   │   └── acl.yaml
│   │   ├── schemas/
│   │   │   ├── event-envelope.v1.json
│   │   │   ├── document-events.v1.json
│   │   │   ├── analysis-events.v1.json
│   │   │   ├── report-events.v1.json
│   │   │   └── notification-events.v1.json
│   │   ├── scripts/
│   │   │   ├── format-storage.sh
│   │   │   ├── create-topics.sh
│   │   │   ├── create-users.sh
│   │   │   ├── create-acls.sh
│   │   │   └── smoke-test.sh
│   │   └── README.md
│   ├── minio/
│   │   ├── buckets.yaml
│   │   ├── lifecycle/
│   │   ├── policies/
│   │   ├── cors.json
│   │   ├── bootstrap.sh
│   │   └── README.md
│   ├── keycloak/
│   │   ├── realm-bank-ai.json
│   │   ├── bootstrap-users.sh
│   │   └── README.md
│   ├── monitoring/
│   │   ├── prometheus.yml
│   │   ├── grafana/
│   │   └── README.md
│   ├── contracts/
│   │   ├── backend-connections.env.example
│   │   ├── worker-connections.env.example
│   │   └── frontend-public.env.example
│   └── scripts/
│       ├── generate-secrets.sh
│       ├── generate-secrets.ps1
│       ├── bootstrap.sh
│       ├── bootstrap.ps1
│       ├── wait-for-service.sh
│       ├── verify-stack.sh
│       └── verify-stack.ps1
│
└── docs/
    ├── architecture.md
    ├── ports-and-urls.md
    ├── version-manifest.md
    ├── database-design.md
    ├── data-dictionary.md
    ├── kafka-contract.md
    ├── minio-layout.md
    ├── redis-usage.md
    ├── keycloak-setup.md
    ├── security.md
    └── runbook.md
```

---

# 10. Docker networks

Tạo ba network:

```text
bank-edge
bank-application
bank-data
```

## `bank-edge`

Dành cho service được truy cập từ host:

* Keycloak.
* MinIO.
* Kafka external listener.
* Kafka UI.
* PgAdmin.
* Prometheus.
* Grafana.

## `bank-application`

Dành cho:

* Backend trong tương lai.
* Workers trong tương lai.
* Kafka.
* Redis.
* MinIO.
* Keycloak.

## `bank-data`

Dành cho:

* PostgreSQL.
* Flyway.
* PgAdmin.
* Keycloak.
* Backend và worker khi được thêm sau.

PostgreSQL không được nằm trong `bank-edge`.

Redis không được nằm trong `bank-edge` ở production.

---

# 11. Docker volumes

Tạo named volumes:

```text
postgres_data
redis_data
kafka_data
minio_data
keycloak_data
pgadmin_data
prometheus_data
grafana_data
```

Các volume phải có tên rõ ràng, không sử dụng anonymous volume cho dữ liệu.

---

# 12. PostgreSQL setup

## 12.1. Database

Tạo hai database riêng trong cùng PostgreSQL instance:

```text
bank_ai
keycloak
```

## 12.2. Extensions trong `bank_ai`

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

## 12.3. Database roles

Tạo:

```text
bank_migrator
bank_app
bank_worker
bank_readonly
keycloak_app
```

### `bank_migrator`

Được phép:

* Tạo schema.
* Tạo table.
* Tạo index.
* Tạo function.
* Tạo policy.
* Chạy migration.

Không dùng cho runtime.

### `bank_app`

Được phép:

* Đọc và ghi dữ liệu nghiệp vụ.
* Không tạo database.
* Không tạo role.
* Không sửa schema.
* Không `BYPASSRLS`.
* Không sở hữu table.

### `bank_worker`

Được phép:

* Đọc job được phân công.
* Đọc metadata tài liệu cần xử lý.
* Ghi kết quả xử lý.
* Ghi agent finding.
* Ghi outbox event.
* Không tạo quyết định tín dụng.
* Không cập nhật quyền nhân viên.

### `bank_readonly`

Được phép:

* Đọc các view đã được cấp.
* Không được đọc cột mã hóa trực tiếp.
* Không ghi dữ liệu.

### `keycloak_app`

Chỉ được truy cập database `keycloak`.

Không được truy cập `bank_ai`.

Không role runtime nào được cấp:

```text
SUPERUSER
CREATEDB
CREATEROLE
REPLICATION
BYPASSRLS
```

---

# 13. Quy ước database

## 13.1. ID

* Dùng UUID cho business entity.
* Không dùng số CCCD, email hoặc mã khách hàng làm primary key.
* Không dùng ID tuần tự làm ID công khai.

## 13.2. Tiền

Dùng:

```sql
NUMERIC(24,4)
```

Không dùng:

```text
FLOAT
REAL
DOUBLE PRECISION
```

## 13.3. Tỷ lệ

Dùng:

```sql
NUMERIC(12,8)
```

Ví dụ:

```text
61,36% → 0.61360000
```

## 13.4. Timestamp

Dùng:

```sql
TIMESTAMPTZ
```

Lưu UTC.

## 13.5. Mã tiền

Dùng:

```sql
CHAR(3)
```

Ví dụ:

```text
VND
USD
EUR
```

## 13.6. Optimistic locking

Các bảng nghiệp vụ chỉnh sửa được phải có:

```text
version INTEGER NOT NULL DEFAULT 1
```

## 13.7. Audit columns

Các bảng nghiệp vụ nên có:

```text
created_at TIMESTAMPTZ NOT NULL
created_by UUID NULL
updated_at TIMESTAMPTZ NOT NULL
updated_by UUID NULL
version INTEGER NOT NULL DEFAULT 1
```

## 13.8. Soft delete

Không hard delete hồ sơ nghiệp vụ.

Sử dụng:

```text
status
archived_at
deleted_at
```

Audit event không được soft delete hoặc hard delete qua application role.

---

# 14. PostgreSQL schemas

Tạo:

```sql
CREATE SCHEMA identity;
CREATE SCHEMA customer;
CREATE SCHEMA banking;
CREATE SCHEMA storage;
CREATE SCHEMA document;
CREATE SCHEMA credit;
CREATE SCHEMA policy;
CREATE SCHEMA ai;
CREATE SCHEMA integration;
CREATE SCHEMA audit;
```

---

# 15. Database data dictionary

Phải tạo đầy đủ table, constraint, index, comment cho các bảng dưới đây.

Mỗi table và column phải có `COMMENT ON`.

---

## 15.1. `identity.branch`

Lưu thông tin chi nhánh.

```text
id UUID PK
branch_code CITEXT UNIQUE NOT NULL
branch_name TEXT NOT NULL
parent_branch_id UUID NULL FK identity.branch
status VARCHAR(20) NOT NULL
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
```

Constraints:

```text
status IN ('ACTIVE', 'INACTIVE')
parent_branch_id <> id
```

Indexes:

```text
branch_code unique
parent_branch_id
status
```

---

## 15.2. `identity.department`

Lưu phòng ban.

```text
id UUID PK
department_code CITEXT UNIQUE NOT NULL
department_name TEXT NOT NULL
branch_id UUID NULL FK identity.branch
status VARCHAR(20) NOT NULL
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
```

---

## 15.3. `identity.employee`

Lưu hồ sơ nghiệp vụ nhân viên.

Không lưu password.

```text
id UUID PK
identity_subject CITEXT UNIQUE NOT NULL
employee_code CITEXT UNIQUE NOT NULL
full_name TEXT NOT NULL
email CITEXT UNIQUE NOT NULL
branch_id UUID NOT NULL FK identity.branch
department_id UUID NOT NULL FK identity.department
job_title TEXT NULL
manager_id UUID NULL FK identity.employee
employment_status VARCHAR(20) NOT NULL
last_synced_at TIMESTAMPTZ NULL
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
version INTEGER NOT NULL DEFAULT 1
```

`identity_subject` là JWT claim `sub` từ Keycloak.

---

## 15.4. `identity.role`

```text
id UUID PK
role_code CITEXT UNIQUE NOT NULL
role_name TEXT NOT NULL
description TEXT NULL
is_system_role BOOLEAN NOT NULL DEFAULT TRUE
created_at TIMESTAMPTZ NOT NULL
```

Seed các role:

```text
credit_officer
credit_manager
document_reviewer
compliance_officer
risk_officer
loan_approver
auditor
admin
```

---

## 15.5. `identity.permission`

```text
id UUID PK
permission_code CITEXT UNIQUE NOT NULL
resource_type VARCHAR(50) NOT NULL
action VARCHAR(30) NOT NULL
description TEXT NULL
created_at TIMESTAMPTZ NOT NULL
```

Seed:

```text
customer:read
customer:search
account:read
transaction:read

document:read
document:upload
document:download
document:verify

loan:read
loan:create
loan:update
loan:analyze
loan:submit
loan:approve

policy:read

report:read
report:generate
report:review
report:export

audit:read
admin:manage
```

---

## 15.6. `identity.role_permission`

```text
role_id UUID NOT NULL FK identity.role
permission_id UUID NOT NULL FK identity.permission
created_at TIMESTAMPTZ NOT NULL
PRIMARY KEY (role_id, permission_id)
```

---

## 15.7. `identity.employee_role`

```text
id UUID PK
employee_id UUID NOT NULL FK identity.employee
role_id UUID NOT NULL FK identity.role
valid_from TIMESTAMPTZ NOT NULL
valid_until TIMESTAMPTZ NULL
assigned_by UUID NULL FK identity.employee
created_at TIMESTAMPTZ NOT NULL
```

Constraint:

```text
valid_until IS NULL OR valid_until > valid_from
```

---

## 15.8. `identity.employee_scope`

Cấp quyền theo phạm vi.

```text
id UUID PK
employee_id UUID NOT NULL FK identity.employee
scope_type VARCHAR(30) NOT NULL
scope_id UUID NOT NULL
permission_code CITEXT NOT NULL
valid_from TIMESTAMPTZ NOT NULL
valid_until TIMESTAMPTZ NULL
assigned_by UUID NULL FK identity.employee
reason TEXT NULL
created_at TIMESTAMPTZ NOT NULL
```

`scope_type`:

```text
BRANCH
CUSTOMER
LOAN_APPLICATION
ANALYSIS_CASE
```

---

# 16. Customer schema

## 16.1. `customer.party`

Đại diện cho một cá nhân hoặc tổ chức.

```text
id UUID PK
party_type VARCHAR(20) NOT NULL
display_name TEXT NOT NULL
status VARCHAR(20) NOT NULL
created_at TIMESTAMPTZ NOT NULL
created_by UUID NULL
updated_at TIMESTAMPTZ NOT NULL
updated_by UUID NULL
version INTEGER NOT NULL DEFAULT 1
```

`party_type`:

```text
PERSON
ORGANIZATION
```

---

## 16.2. `customer.person_profile`

```text
party_id UUID PK FK customer.party
full_name TEXT NOT NULL
date_of_birth DATE NULL
gender VARCHAR(20) NULL
nationality CHAR(2) NULL
marital_status VARCHAR(30) NULL
occupation TEXT NULL
updated_at TIMESTAMPTZ NOT NULL
```

Không lưu tuổi.

---

## 16.3. `customer.organization_profile`

```text
party_id UUID PK FK customer.party
legal_name TEXT NOT NULL
trading_name TEXT NULL
business_type VARCHAR(50) NULL
registration_number_hash CHAR(64) NULL
tax_code_hash CHAR(64) NULL
incorporation_date DATE NULL
industry_code VARCHAR(30) NULL
legal_representative_party_id UUID NULL FK customer.party
updated_at TIMESTAMPTZ NOT NULL
```

---

## 16.4. `customer.customer`

Lưu quan hệ của party với ngân hàng.

```text
id UUID PK
party_id UUID UNIQUE NOT NULL FK customer.party
customer_number CITEXT UNIQUE NOT NULL
customer_segment VARCHAR(30) NULL
home_branch_id UUID NOT NULL FK identity.branch
relationship_manager_id UUID NULL FK identity.employee
onboarding_date DATE NULL
kyc_status VARCHAR(30) NOT NULL
risk_rating VARCHAR(20) NULL
risk_rating_as_of DATE NULL
status VARCHAR(20) NOT NULL
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
version INTEGER NOT NULL DEFAULT 1
```

---

## 16.5. `customer.party_identifier`

Lưu CCCD, hộ chiếu hoặc mã số doanh nghiệp.

```text
id UUID PK
party_id UUID NOT NULL FK customer.party
identifier_type VARCHAR(30) NOT NULL
encrypted_value BYTEA NOT NULL
value_hash CHAR(64) NOT NULL
last4 VARCHAR(4) NULL
issued_date DATE NULL
expiry_date DATE NULL
issuing_authority TEXT NULL
country_code CHAR(2) NULL
verification_status VARCHAR(30) NOT NULL
source_document_id UUID NULL
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
```

Không trả `encrypted_value` qua view readonly.

Unique:

```text
(identifier_type, value_hash)
```

---

## 16.6. `customer.party_contact`

```text
id UUID PK
party_id UUID NOT NULL FK customer.party
contact_type VARCHAR(20) NOT NULL
encrypted_value BYTEA NOT NULL
value_hash CHAR(64) NOT NULL
masked_value TEXT NULL
is_primary BOOLEAN NOT NULL DEFAULT FALSE
verification_status VARCHAR(30) NOT NULL
verified_at TIMESTAMPTZ NULL
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
```

---

## 16.7. `customer.party_address`

```text
id UUID PK
party_id UUID NOT NULL FK customer.party
address_type VARCHAR(30) NOT NULL
address_line TEXT NOT NULL
ward TEXT NULL
district TEXT NULL
province TEXT NULL
country_code CHAR(2) NOT NULL
valid_from DATE NULL
valid_until DATE NULL
verification_status VARCHAR(30) NOT NULL
source_document_id UUID NULL
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
```

---

## 16.8. `customer.employment`

```text
id UUID PK
party_id UUID NOT NULL FK customer.party
employer_name TEXT NOT NULL
position TEXT NULL
employment_type VARCHAR(30) NULL
start_date DATE NULL
end_date DATE NULL
declared_monthly_income NUMERIC(24,4) NULL
currency CHAR(3) NOT NULL DEFAULT 'VND'
verification_status VARCHAR(30) NOT NULL
source_document_id UUID NULL
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
version INTEGER NOT NULL DEFAULT 1
```

---

## 16.9. `customer.income_source`

Phải tách riêng thu nhập khai báo, xác minh và được chấp nhận.

```text
id UUID PK
party_id UUID NOT NULL FK customer.party
income_type VARCHAR(30) NOT NULL
declared_amount NUMERIC(24,4) NULL
verified_amount NUMERIC(24,4) NULL
accepted_amount NUMERIC(24,4) NULL
frequency VARCHAR(20) NOT NULL
currency CHAR(3) NOT NULL
as_of_date DATE NOT NULL
verification_method VARCHAR(30) NULL
verification_status VARCHAR(30) NOT NULL
source_document_id UUID NULL
source_calculation_id UUID NULL
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
version INTEGER NOT NULL DEFAULT 1
```

Không áp dụng constraint cứng bắt buộc `accepted_amount <= verified_amount`, vì có thể tồn tại ngoại lệ nghiệp vụ.

Nếu `accepted_amount > verified_amount`, backend sau này phải yêu cầu approval record.

---

## 16.10. `customer.party_relationship`

```text
id UUID PK
from_party_id UUID NOT NULL FK customer.party
to_party_id UUID NOT NULL FK customer.party
relationship_type VARCHAR(40) NOT NULL
valid_from DATE NULL
valid_until DATE NULL
source_document_id UUID NULL
verification_status VARCHAR(30) NOT NULL
created_at TIMESTAMPTZ NOT NULL
```

Quan hệ:

```text
SPOUSE
CO_BORROWER
GUARANTOR
LEGAL_REPRESENTATIVE
DIRECTOR
SHAREHOLDER
RELATED_COMPANY
```

---

## 16.11. `customer.kyc_assessment`

```text
id UUID PK
customer_id UUID NOT NULL FK customer.customer
assessment_date TIMESTAMPTZ NOT NULL
kyc_status VARCHAR(30) NOT NULL
aml_risk_level VARCHAR(20) NULL
pep_status VARCHAR(20) NULL
sanction_status VARCHAR(20) NULL
beneficial_owner_verified BOOLEAN NULL
source_system TEXT NULL
assessment_payload JSONB NOT NULL DEFAULT '{}'
assessed_by UUID NULL FK identity.employee
created_at TIMESTAMPTZ NOT NULL
```

---

# 17. Banking schema

## 17.1. `banking.account`

```text
id UUID PK
account_number_masked TEXT NOT NULL
account_number_hash CHAR(64) UNIQUE NOT NULL
account_type VARCHAR(30) NOT NULL
currency CHAR(3) NOT NULL
branch_id UUID NULL FK identity.branch
status VARCHAR(20) NOT NULL
opened_at TIMESTAMPTZ NULL
closed_at TIMESTAMPTZ NULL
current_balance NUMERIC(24,4) NULL
balance_as_of TIMESTAMPTZ NULL
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
version INTEGER NOT NULL DEFAULT 1
```

---

## 17.2. `banking.account_holder`

```text
id UUID PK
account_id UUID NOT NULL FK banking.account
party_id UUID NOT NULL FK customer.party
holder_role VARCHAR(30) NOT NULL
valid_from DATE NULL
valid_until DATE NULL
created_at TIMESTAMPTZ NOT NULL
```

---

## 17.3. `banking.transaction`

Lưu giao dịch tài khoản.

```text
id UUID NOT NULL
account_id UUID NOT NULL FK banking.account
booking_time TIMESTAMPTZ NOT NULL
value_date DATE NULL
direction VARCHAR(10) NOT NULL
amount NUMERIC(24,4) NOT NULL
currency CHAR(3) NOT NULL
transaction_type VARCHAR(50) NULL
channel VARCHAR(30) NULL
description TEXT NULL
balance_after NUMERIC(24,4) NULL
counterparty_name_masked TEXT NULL
counterparty_account_hash CHAR(64) NULL
reference_number TEXT NULL
status VARCHAR(20) NOT NULL
raw_payload JSONB NOT NULL DEFAULT '{}'
created_at TIMESTAMPTZ NOT NULL
PRIMARY KEY (id, booking_time)
```

Thiết kế partition theo tháng bằng `booking_time`.

Tạo:

* Partition cho năm hiện tại.
* Partition cho năm trước.
* Default partition.
* Script tạo partition tương lai.

Indexes trên mỗi partition:

```text
(account_id, booking_time DESC)
(transaction_type, booking_time DESC)
(counterparty_account_hash)
BRIN (booking_time)
```

---

## 17.4. `banking.account_monthly_summary`

```text
account_id UUID NOT NULL FK banking.account
year_month DATE NOT NULL
total_inflow NUMERIC(24,4) NOT NULL
total_outflow NUMERIC(24,4) NOT NULL
salary_inflow NUMERIC(24,4) NOT NULL
loan_payment NUMERIC(24,4) NOT NULL
cash_deposit NUMERIC(24,4) NOT NULL
average_balance NUMERIC(24,4) NULL
minimum_balance NUMERIC(24,4) NULL
maximum_balance NUMERIC(24,4) NULL
transaction_count INTEGER NOT NULL
computed_at TIMESTAMPTZ NOT NULL
PRIMARY KEY (account_id, year_month)
```

---

## 17.5. `banking.credit_report`

```text
id UUID PK
customer_id UUID NOT NULL FK customer.customer
provider VARCHAR(50) NOT NULL
report_reference TEXT NULL
requested_at TIMESTAMPTZ NOT NULL
report_as_of_date DATE NOT NULL
risk_summary JSONB NOT NULL DEFAULT '{}'
storage_object_id UUID NULL
created_at TIMESTAMPTZ NOT NULL
```

---

## 17.6. `banking.credit_facility`

Dữ liệu khoản tín dụng lấy từ báo cáo CIC hoặc nguồn ngoài.

```text
id UUID PK
credit_report_id UUID NOT NULL FK banking.credit_report
lender_name TEXT NULL
facility_type VARCHAR(30) NOT NULL
credit_limit NUMERIC(24,4) NULL
outstanding_balance NUMERIC(24,4) NULL
monthly_obligation NUMERIC(24,4) NULL
overdue_days INTEGER NULL
debt_group VARCHAR(20) NULL
currency CHAR(3) NOT NULL
as_of_date DATE NOT NULL
created_at TIMESTAMPTZ NOT NULL
```

---

# 18. Storage schema

## 18.1. `storage.object_metadata`

Lưu metadata của mọi MinIO object.

```text
id UUID PK
bucket_name TEXT NOT NULL
object_key TEXT NOT NULL
object_version_id TEXT NULL
etag TEXT NULL
sha256 CHAR(64) NOT NULL
size_bytes BIGINT NOT NULL
mime_type TEXT NOT NULL
storage_class VARCHAR(30) NULL
encryption_type VARCHAR(30) NULL
retention_until TIMESTAMPTZ NULL
legal_hold BOOLEAN NOT NULL DEFAULT FALSE
created_by UUID NULL
created_at TIMESTAMPTZ NOT NULL
deleted_at TIMESTAMPTZ NULL
```

Unique:

```text
(bucket_name, object_key, object_version_id)
```

Không chứa PII trong `object_key`.

---

## 18.2. `storage.upload_session`

```text
id UUID PK
customer_id UUID NOT NULL FK customer.customer
loan_application_id UUID NULL
expected_document_type VARCHAR(50) NULL
original_filename TEXT NOT NULL
expected_mime_type TEXT NOT NULL
expected_size_bytes BIGINT NOT NULL
expected_sha256 CHAR(64) NOT NULL
quarantine_object_key TEXT NOT NULL
status VARCHAR(30) NOT NULL
expires_at TIMESTAMPTZ NOT NULL
completed_at TIMESTAMPTZ NULL
created_by UUID NOT NULL FK identity.employee
idempotency_key UUID NOT NULL
created_at TIMESTAMPTZ NOT NULL
```

Status:

```text
CREATED
UPLOADING
UPLOADED
VERIFYING
COMPLETED
EXPIRED
FAILED
```

---

## 18.3. `storage.retention_rule`

```text
id UUID PK
rule_code CITEXT UNIQUE NOT NULL
resource_type VARCHAR(50) NOT NULL
retention_years INTEGER NULL
retention_days INTEGER NULL
start_event VARCHAR(50) NOT NULL
description TEXT NULL
is_active BOOLEAN NOT NULL DEFAULT TRUE
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
```

---

## 18.4. `storage.resource_retention`

```text
id UUID PK
resource_type VARCHAR(50) NOT NULL
resource_id UUID NOT NULL
retention_rule_id UUID NOT NULL FK storage.retention_rule
retention_start_date DATE NULL
retention_until DATE NULL
legal_hold BOOLEAN NOT NULL DEFAULT FALSE
legal_hold_reason TEXT NULL
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
```

---

# 19. Document schema

## 19.1. `document.document`

Đại diện cho tài liệu logic.

```text
id UUID PK
document_type VARCHAR(50) NOT NULL
document_subtype VARCHAR(50) NULL
title TEXT NULL
owner_party_id UUID NULL FK customer.party
classification VARCHAR(30) NOT NULL
document_date DATE NULL
valid_from DATE NULL
valid_until DATE NULL
verification_status VARCHAR(30) NOT NULL
processing_status VARCHAR(30) NOT NULL
created_by UUID NOT NULL FK identity.employee
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
version INTEGER NOT NULL DEFAULT 1
```

---

## 19.2. `document.document_version`

```text
id UUID PK
document_id UUID NOT NULL FK document.document
version_number INTEGER NOT NULL
original_object_id UUID NOT NULL FK storage.object_metadata
original_filename TEXT NOT NULL
mime_type TEXT NOT NULL
file_size BIGINT NOT NULL
sha256 CHAR(64) NOT NULL
uploaded_by UUID NOT NULL FK identity.employee
uploaded_at TIMESTAMPTZ NOT NULL
scan_status VARCHAR(30) NOT NULL
is_current BOOLEAN NOT NULL DEFAULT TRUE
created_at TIMESTAMPTZ NOT NULL
UNIQUE (document_id, version_number)
```

Chỉ một version được `is_current = TRUE` cho mỗi document.

Tạo partial unique index.

---

## 19.3. `document.document_link`

Liên kết tài liệu với customer, loan hoặc collateral.

```text
id UUID PK
document_id UUID NOT NULL FK document.document
entity_type VARCHAR(40) NOT NULL
entity_id UUID NOT NULL
relationship_type VARCHAR(40) NOT NULL
created_at TIMESTAMPTZ NOT NULL
```

---

## 19.4. `document.processing_job`

```text
id UUID PK
document_version_id UUID NOT NULL FK document.document_version
job_type VARCHAR(40) NOT NULL
status VARCHAR(30) NOT NULL
model_name TEXT NULL
model_version TEXT NULL
attempt_count INTEGER NOT NULL DEFAULT 0
started_at TIMESTAMPTZ NULL
completed_at TIMESTAMPTZ NULL
error_code VARCHAR(50) NULL
error_message_safe TEXT NULL
correlation_id UUID NOT NULL
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
```

---

## 19.5. `document.document_page`

```text
id UUID PK
document_version_id UUID NOT NULL FK document.document_version
page_number INTEGER NOT NULL
text_content TEXT NULL
ocr_confidence NUMERIC(6,5) NULL
page_image_object_id UUID NULL FK storage.object_metadata
width INTEGER NULL
height INTEGER NULL
created_at TIMESTAMPTZ NOT NULL
UNIQUE (document_version_id, page_number)
```

---

## 19.6. `document.extracted_field`

Không ghi đè giá trị OCR khi người dùng sửa.

```text
id UUID PK
document_version_id UUID NOT NULL FK document.document_version
field_name CITEXT NOT NULL
value_type VARCHAR(20) NOT NULL
ocr_value_text TEXT NULL
normalized_value_text TEXT NULL
corrected_value_text TEXT NULL
value_number NUMERIC(24,4) NULL
value_date DATE NULL
page_number INTEGER NULL
bounding_box JSONB NULL
source_text TEXT NULL
confidence NUMERIC(6,5) NULL
verification_status VARCHAR(30) NOT NULL
verified_by UUID NULL FK identity.employee
verified_at TIMESTAMPTZ NULL
verification_reason TEXT NULL
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
```

---

## 19.7. `document.document_chunk`

```text
id UUID PK
document_version_id UUID NOT NULL FK document.document_version
page_from INTEGER NULL
page_to INTEGER NULL
chunk_index INTEGER NOT NULL
text_content TEXT NOT NULL
token_count INTEGER NULL
embedding VECTOR(1024) NULL
metadata JSONB NOT NULL DEFAULT '{}'
created_at TIMESTAMPTZ NOT NULL
UNIQUE (document_version_id, chunk_index)
```

Tạo HNSW index:

```sql
USING hnsw (embedding vector_cosine_ops)
```

Tạo index:

```text
document_version_id
metadata GIN
```

---

## 19.8. `document.document_issue`

```text
id UUID PK
document_version_id UUID NOT NULL FK document.document_version
issue_type VARCHAR(40) NOT NULL
severity VARCHAR(20) NOT NULL
title TEXT NOT NULL
description TEXT NOT NULL
field_id UUID NULL FK document.extracted_field
status VARCHAR(30) NOT NULL
detected_by VARCHAR(30) NOT NULL
resolved_by UUID NULL FK identity.employee
resolved_at TIMESTAMPTZ NULL
resolution_note TEXT NULL
created_at TIMESTAMPTZ NOT NULL
```

---

# 20. Credit schema

## 20.1. `credit.loan_product`

```text
id UUID PK
product_code CITEXT UNIQUE NOT NULL
product_name TEXT NOT NULL
customer_type VARCHAR(20) NOT NULL
loan_purpose VARCHAR(40) NULL
min_amount NUMERIC(24,4) NULL
max_amount NUMERIC(24,4) NULL
min_term_months INTEGER NULL
max_term_months INTEGER NULL
status VARCHAR(20) NOT NULL
effective_from DATE NOT NULL
effective_until DATE NULL
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
```

---

## 20.2. `credit.loan_application`

```text
id UUID PK
application_number CITEXT UNIQUE NOT NULL
primary_customer_id UUID NOT NULL FK customer.customer
product_id UUID NOT NULL FK credit.loan_product
requested_amount NUMERIC(24,4) NOT NULL
currency CHAR(3) NOT NULL
requested_term_months INTEGER NOT NULL
loan_purpose VARCHAR(40) NOT NULL
interest_rate_assumption NUMERIC(12,8) NULL
repayment_method VARCHAR(40) NULL
status VARCHAR(30) NOT NULL
assigned_employee_id UUID NULL FK identity.employee
submitted_at TIMESTAMPTZ NULL
created_at TIMESTAMPTZ NOT NULL
created_by UUID NOT NULL
updated_at TIMESTAMPTZ NOT NULL
updated_by UUID NULL
version INTEGER NOT NULL DEFAULT 1
```

Status:

```text
DRAFT
DOCUMENT_COLLECTION
UNDER_ANALYSIS
NEEDS_INFORMATION
READY_FOR_REVIEW
SUBMITTED_FOR_APPROVAL
APPROVED
APPROVED_WITH_CONDITIONS
REJECTED
WITHDRAWN
```

---

## 20.3. `credit.loan_party`

```text
id UUID PK
loan_application_id UUID NOT NULL FK credit.loan_application
party_id UUID NOT NULL FK customer.party
party_role VARCHAR(40) NOT NULL
created_at TIMESTAMPTZ NOT NULL
```

Role:

```text
PRIMARY_BORROWER
CO_BORROWER
GUARANTOR
SPOUSE
COLLATERAL_OWNER
LEGAL_REPRESENTATIVE
```

---

## 20.4. `credit.existing_obligation`

```text
id UUID PK
loan_application_id UUID NOT NULL FK credit.loan_application
party_id UUID NOT NULL FK customer.party
lender_name TEXT NULL
obligation_type VARCHAR(30) NOT NULL
outstanding_balance NUMERIC(24,4) NULL
monthly_payment NUMERIC(24,4) NULL
credit_limit NUMERIC(24,4) NULL
currency CHAR(3) NOT NULL
verified_status VARCHAR(30) NOT NULL
source_type VARCHAR(30) NOT NULL
source_id UUID NULL
as_of_date DATE NOT NULL
created_at TIMESTAMPTZ NOT NULL
```

---

## 20.5. `credit.collateral`

```text
id UUID PK
loan_application_id UUID NOT NULL FK credit.loan_application
owner_party_id UUID NOT NULL FK customer.party
collateral_type VARCHAR(40) NOT NULL
description TEXT NULL
declared_value NUMERIC(24,4) NULL
appraised_value NUMERIC(24,4) NULL
eligible_value NUMERIC(24,4) NULL
currency CHAR(3) NOT NULL
valuation_date DATE NULL
valuation_status VARCHAR(30) NULL
ownership_verification_status VARCHAR(30) NULL
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
version INTEGER NOT NULL DEFAULT 1
```

---

## 20.6. `credit.collateral_valuation`

```text
id UUID PK
collateral_id UUID NOT NULL FK credit.collateral
valuation_date DATE NOT NULL
market_value NUMERIC(24,4) NOT NULL
eligible_value NUMERIC(24,4) NULL
currency CHAR(3) NOT NULL
valuation_method VARCHAR(50) NULL
valuer_name TEXT NULL
source_document_id UUID NULL FK document.document
status VARCHAR(30) NOT NULL
created_at TIMESTAMPTZ NOT NULL
```

---

## 20.7. `credit.loan_checklist_item`

```text
id UUID PK
loan_application_id UUID NOT NULL FK credit.loan_application
requirement_code CITEXT NOT NULL
document_type VARCHAR(50) NULL
requirement_status VARCHAR(30) NOT NULL
mandatory_level VARCHAR(30) NOT NULL
source_policy_clause_id UUID NULL
linked_document_id UUID NULL FK document.document
waived_by UUID NULL FK identity.employee
waiver_reason TEXT NULL
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
```

Status:

```text
REQUIRED
RECEIVED
VALID
EXPIRED
INCOMPLETE
INCONSISTENT
WAIVED
NOT_APPLICABLE
```

---

## 20.8. `credit.calculation_record`

Mọi phép tính quan trọng phải được lưu.

```text
id UUID PK
loan_application_id UUID NOT NULL FK credit.loan_application
analysis_case_id UUID NULL
calculation_type VARCHAR(40) NOT NULL
calculation_version VARCHAR(20) NOT NULL
inputs JSONB NOT NULL
formula TEXT NOT NULL
result_value NUMERIC(30,10) NULL
result_payload JSONB NOT NULL DEFAULT '{}'
unit VARCHAR(30) NULL
calculated_at TIMESTAMPTZ NOT NULL
created_by_type VARCHAR(20) NOT NULL
created_by_id UUID NULL
```

---

## 20.9. `credit.affordability_assessment`

```text
id UUID PK
loan_application_id UUID NOT NULL FK credit.loan_application
calculation_version VARCHAR(20) NOT NULL
monthly_declared_income NUMERIC(24,4) NULL
monthly_verified_income NUMERIC(24,4) NULL
monthly_accepted_income NUMERIC(24,4) NULL
monthly_existing_obligations NUMERIC(24,4) NULL
projected_monthly_payment NUMERIC(24,4) NULL
dti NUMERIC(12,8) NULL
dscr NUMERIC(12,8) NULL
ltv NUMERIC(12,8) NULL
net_disposable_income NUMERIC(24,4) NULL
stress_interest_rate NUMERIC(12,8) NULL
stress_dti NUMERIC(12,8) NULL
result VARCHAR(30) NOT NULL
calculation_payload JSONB NOT NULL
calculated_at TIMESTAMPTZ NOT NULL
```

---

## 20.10. `credit.policy_check`

```text
id UUID PK
loan_application_id UUID NOT NULL FK credit.loan_application
analysis_case_id UUID NULL
policy_version_id UUID NOT NULL
clause_id UUID NULL
rule_code CITEXT NULL
status VARCHAR(30) NOT NULL
actual_value TEXT NULL
required_value TEXT NULL
explanation TEXT NOT NULL
checked_at TIMESTAMPTZ NOT NULL
```

Status:

```text
PASS
FAIL
CONDITIONAL
INSUFFICIENT_DATA
NOT_APPLICABLE
```

---

## 20.11. `credit.approval_request`

```text
id UUID PK
loan_application_id UUID NOT NULL FK credit.loan_application
requested_by UUID NOT NULL FK identity.employee
requested_at TIMESTAMPTZ NOT NULL
requested_authority_level VARCHAR(30) NULL
status VARCHAR(30) NOT NULL
request_note TEXT NULL
created_at TIMESTAMPTZ NOT NULL
```

---

## 20.12. `credit.loan_decision`

Chỉ người có thẩm quyền được ghi.

```text
id UUID PK
loan_application_id UUID NOT NULL FK credit.loan_application
approval_request_id UUID NULL FK credit.approval_request
decision_type VARCHAR(40) NOT NULL
approved_amount NUMERIC(24,4) NULL
approved_term_months INTEGER NULL
conditions JSONB NOT NULL DEFAULT '[]'
rationale TEXT NOT NULL
decision_maker_id UUID NOT NULL FK identity.employee
decision_at TIMESTAMPTZ NOT NULL
is_override BOOLEAN NOT NULL DEFAULT FALSE
override_reason TEXT NULL
created_at TIMESTAMPTZ NOT NULL
```

---

## 20.13. `credit.disbursement`

```text
id UUID PK
loan_application_id UUID NOT NULL FK credit.loan_application
drawdown_number INTEGER NOT NULL
amount NUMERIC(24,4) NOT NULL
currency CHAR(3) NOT NULL
beneficiary_name_masked TEXT NULL
beneficiary_account_hash CHAR(64) NULL
purpose_reference TEXT NULL
payment_transaction_id UUID NULL
status VARCHAR(30) NOT NULL
approved_by UUID NULL FK identity.employee
disbursed_at TIMESTAMPTZ NULL
created_at TIMESTAMPTZ NOT NULL
```

---

## 20.14. `credit.loan_account`

```text
id UUID PK
loan_application_id UUID UNIQUE NOT NULL FK credit.loan_application
account_number_masked TEXT NOT NULL
account_number_hash CHAR(64) UNIQUE NOT NULL
principal_amount NUMERIC(24,4) NOT NULL
outstanding_principal NUMERIC(24,4) NOT NULL
interest_rate NUMERIC(12,8) NOT NULL
disbursement_date DATE NOT NULL
maturity_date DATE NOT NULL
status VARCHAR(30) NOT NULL
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
```

---

## 20.15. `credit.repayment_schedule`

```text
id UUID PK
loan_account_id UUID NOT NULL FK credit.loan_account
installment_number INTEGER NOT NULL
due_date DATE NOT NULL
principal_due NUMERIC(24,4) NOT NULL
interest_due NUMERIC(24,4) NOT NULL
fee_due NUMERIC(24,4) NOT NULL DEFAULT 0
total_due NUMERIC(24,4) NOT NULL
payment_status VARCHAR(30) NOT NULL
created_at TIMESTAMPTZ NOT NULL
UNIQUE (loan_account_id, installment_number)
```

---

## 20.16. `credit.loan_payment`

```text
id UUID PK
loan_account_id UUID NOT NULL FK credit.loan_account
transaction_id UUID NULL
payment_date TIMESTAMPTZ NOT NULL
principal_paid NUMERIC(24,4) NOT NULL
interest_paid NUMERIC(24,4) NOT NULL
fee_paid NUMERIC(24,4) NOT NULL DEFAULT 0
created_at TIMESTAMPTZ NOT NULL
```

---

# 21. Policy schema

## 21.1. `policy.policy`

```text
id UUID PK
policy_code CITEXT UNIQUE NOT NULL
policy_name TEXT NOT NULL
policy_type VARCHAR(40) NOT NULL
owner_department_id UUID NULL FK identity.department
status VARCHAR(20) NOT NULL
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
```

---

## 21.2. `policy.policy_version`

```text
id UUID PK
policy_id UUID NOT NULL FK policy.policy
version_number VARCHAR(30) NOT NULL
effective_from DATE NOT NULL
effective_until DATE NULL
approved_by UUID NULL FK identity.employee
approved_at TIMESTAMPTZ NULL
source_document_id UUID NOT NULL FK document.document
status VARCHAR(20) NOT NULL
created_at TIMESTAMPTZ NOT NULL
UNIQUE (policy_id, version_number)
```

---

## 21.3. `policy.policy_clause`

```text
id UUID PK
policy_version_id UUID NOT NULL FK policy.policy_version
clause_number TEXT NOT NULL
title TEXT NULL
content TEXT NOT NULL
page_number INTEGER NULL
embedding VECTOR(1024) NULL
metadata JSONB NOT NULL DEFAULT '{}'
created_at TIMESTAMPTZ NOT NULL
UNIQUE (policy_version_id, clause_number)
```

Tạo HNSW cosine index.

---

## 21.4. `policy.checklist_rule`

```text
id UUID PK
policy_version_id UUID NOT NULL FK policy.policy_version
rule_code CITEXT NOT NULL
rule_name TEXT NOT NULL
conditions JSONB NOT NULL
status VARCHAR(20) NOT NULL
created_at TIMESTAMPTZ NOT NULL
UNIQUE (policy_version_id, rule_code)
```

---

## 21.5. `policy.checklist_rule_requirement`

```text
id UUID PK
checklist_rule_id UUID NOT NULL FK policy.checklist_rule
requirement_code CITEXT NOT NULL
document_type VARCHAR(50) NULL
mandatory_level VARCHAR(30) NOT NULL
requirement_description TEXT NOT NULL
created_at TIMESTAMPTZ NOT NULL
```

---

# 22. AI schema

## 22.1. `ai.conversation`

```text
id UUID PK
employee_id UUID NOT NULL FK identity.employee
active_customer_id UUID NULL FK customer.customer
active_loan_application_id UUID NULL FK credit.loan_application
title TEXT NULL
status VARCHAR(20) NOT NULL
started_at TIMESTAMPTZ NOT NULL
ended_at TIMESTAMPTZ NULL
```

---

## 22.2. `ai.message`

Không lưu private chain-of-thought.

```text
id UUID PK
conversation_id UUID NOT NULL FK ai.conversation
sender_type VARCHAR(20) NOT NULL
sender_id UUID NULL
content TEXT NOT NULL
created_at TIMESTAMPTZ NOT NULL
parent_message_id UUID NULL FK ai.message
route_type VARCHAR(30) NULL
complexity_level SMALLINT NULL
analysis_case_id UUID NULL
```

---

## 22.3. `ai.analysis_case`

```text
id UUID PK
case_type VARCHAR(40) NOT NULL
customer_id UUID NOT NULL FK customer.customer
loan_application_id UUID NULL FK credit.loan_application
conversation_id UUID NULL FK ai.conversation
created_by UUID NOT NULL FK identity.employee
status VARCHAR(30) NOT NULL
objective TEXT NOT NULL
correlation_id UUID NOT NULL
created_at TIMESTAMPTZ NOT NULL
completed_at TIMESTAMPTZ NULL
```

---

## 22.4. `ai.analysis_task`

```text
id UUID PK
analysis_case_id UUID NOT NULL FK ai.analysis_case
task_code CITEXT NOT NULL
agent_type VARCHAR(30) NOT NULL
objective TEXT NOT NULL
status VARCHAR(30) NOT NULL
depends_on JSONB NOT NULL DEFAULT '[]'
attempt_count INTEGER NOT NULL DEFAULT 0
started_at TIMESTAMPTZ NULL
completed_at TIMESTAMPTZ NULL
error_code VARCHAR(50) NULL
created_at TIMESTAMPTZ NOT NULL
```

---

## 22.5. `ai.agent_run`

```text
id UUID PK
analysis_case_id UUID NOT NULL FK ai.analysis_case
analysis_task_id UUID NOT NULL FK ai.analysis_task
agent_type VARCHAR(30) NOT NULL
status VARCHAR(30) NOT NULL
model_provider TEXT NULL
model_name TEXT NULL
model_version TEXT NULL
prompt_version TEXT NULL
input_hash CHAR(64) NULL
output_hash CHAR(64) NULL
started_at TIMESTAMPTZ NULL
completed_at TIMESTAMPTZ NULL
created_at TIMESTAMPTZ NOT NULL
```

Không lưu chain-of-thought.

---

## 22.6. `ai.finding`

```text
id UUID PK
analysis_case_id UUID NOT NULL FK ai.analysis_case
agent_run_id UUID NOT NULL FK ai.agent_run
finding_type VARCHAR(40) NOT NULL
title TEXT NOT NULL
description TEXT NOT NULL
severity VARCHAR(20) NOT NULL
status VARCHAR(30) NOT NULL
confidence NUMERIC(6,5) NULL
recommended_action TEXT NULL
created_at TIMESTAMPTZ NOT NULL
```

---

## 22.7. `ai.evidence_link`

```text
id UUID PK
finding_id UUID NOT NULL FK ai.finding
source_type VARCHAR(40) NOT NULL
source_id UUID NOT NULL
source_locator JSONB NOT NULL
quoted_text TEXT NULL
evidence_role VARCHAR(20) NOT NULL
created_at TIMESTAMPTZ NOT NULL
```

`source_type`:

```text
CUSTOMER_RECORD
TRANSACTION
TRANSACTION_QUERY
DOCUMENT_FIELD
DOCUMENT_PAGE
DOCUMENT_CHUNK
CALCULATION
POLICY_CLAUSE
LOAN_RECORD
```

`evidence_role`:

```text
PRIMARY
SUPPORTING
CONTRADICTING
```

---

## 22.8. `ai.validation_result`

```text
id UUID PK
analysis_case_id UUID NOT NULL FK ai.analysis_case
validation_status VARCHAR(30) NOT NULL
citation_coverage NUMERIC(6,5) NULL
unsupported_claims JSONB NOT NULL DEFAULT '[]'
calculation_errors JSONB NOT NULL DEFAULT '[]'
policy_conflicts JSONB NOT NULL DEFAULT '[]'
agent_contradictions JSONB NOT NULL DEFAULT '[]'
approved_for_synthesis BOOLEAN NOT NULL
created_at TIMESTAMPTZ NOT NULL
```

---

## 22.9. `ai.report`

```text
id UUID PK
analysis_case_id UUID NOT NULL FK ai.analysis_case
report_type VARCHAR(30) NOT NULL
status VARCHAR(30) NOT NULL
generated_by_agent_run_id UUID NULL FK ai.agent_run
reviewed_by UUID NULL FK identity.employee
approved_by UUID NULL FK identity.employee
version_number INTEGER NOT NULL
json_payload JSONB NOT NULL
pdf_object_id UUID NULL FK storage.object_metadata
created_at TIMESTAMPTZ NOT NULL
UNIQUE (analysis_case_id, version_number)
```

---

## 22.10. `ai.report_claim`

```text
id UUID PK
report_id UUID NOT NULL FK ai.report
section VARCHAR(50) NOT NULL
claim_text TEXT NOT NULL
claim_type VARCHAR(30) NOT NULL
confidence NUMERIC(6,5) NULL
validation_status VARCHAR(30) NOT NULL
created_at TIMESTAMPTZ NOT NULL
```

---

## 22.11. `ai.report_claim_evidence`

```text
claim_id UUID NOT NULL FK ai.report_claim
evidence_link_id UUID NOT NULL FK ai.evidence_link
support_type VARCHAR(20) NOT NULL
PRIMARY KEY (claim_id, evidence_link_id)
```

---

# 23. Integration schema

Đây là phần trung tâm kết nối PostgreSQL với Kafka.

## 23.1. `integration.background_job`

Nguồn sự thật về trạng thái tác vụ nền.

```text
id UUID PK
job_type VARCHAR(50) NOT NULL
resource_type VARCHAR(40) NOT NULL
resource_id UUID NOT NULL
status VARCHAR(30) NOT NULL
progress_percent SMALLINT NOT NULL DEFAULT 0
current_step VARCHAR(50) NULL
correlation_id UUID NOT NULL
requested_by UUID NULL FK identity.employee
priority SMALLINT NOT NULL DEFAULT 5
attempt_count INTEGER NOT NULL DEFAULT 0
max_attempts INTEGER NOT NULL DEFAULT 5
scheduled_at TIMESTAMPTZ NULL
started_at TIMESTAMPTZ NULL
completed_at TIMESTAMPTZ NULL
error_code VARCHAR(50) NULL
error_message_safe TEXT NULL
result_reference_type VARCHAR(40) NULL
result_reference_id UUID NULL
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
version INTEGER NOT NULL DEFAULT 1
```

Status:

```text
QUEUED
PUBLISHED
RUNNING
WAITING
RETRYING
COMPLETED
FAILED
CANCELLED
```

Constraint:

```text
progress_percent BETWEEN 0 AND 100
```

---

## 23.2. `integration.background_job_step`

```text
id UUID PK
job_id UUID NOT NULL FK integration.background_job
step_code CITEXT NOT NULL
step_order INTEGER NOT NULL
status VARCHAR(30) NOT NULL
progress_percent SMALLINT NOT NULL DEFAULT 0
attempt_count INTEGER NOT NULL DEFAULT 0
started_at TIMESTAMPTZ NULL
completed_at TIMESTAMPTZ NULL
error_code VARCHAR(50) NULL
error_message_safe TEXT NULL
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
UNIQUE (job_id, step_code)
```

---

## 23.3. `integration.job_event`

Lưu lịch sử tiến độ để SSE có thể reconnect.

```text
id BIGSERIAL PK
job_id UUID NOT NULL FK integration.background_job
event_type VARCHAR(50) NOT NULL
sequence_number BIGINT NOT NULL
payload JSONB NOT NULL
created_at TIMESTAMPTZ NOT NULL
UNIQUE (job_id, sequence_number)
```

---

## 23.4. `integration.event_outbox`

Bắt buộc dùng Outbox Pattern.

```text
id UUID PK
aggregate_type VARCHAR(50) NOT NULL
aggregate_id UUID NOT NULL
event_type VARCHAR(100) NOT NULL
event_version INTEGER NOT NULL
partition_key TEXT NOT NULL
payload JSONB NOT NULL
headers JSONB NOT NULL DEFAULT '{}'
status VARCHAR(20) NOT NULL DEFAULT 'PENDING'
attempt_count INTEGER NOT NULL DEFAULT 0
available_at TIMESTAMPTZ NOT NULL
locked_at TIMESTAMPTZ NULL
locked_by TEXT NULL
published_at TIMESTAMPTZ NULL
last_error TEXT NULL
created_at TIMESTAMPTZ NOT NULL
```

Status:

```text
PENDING
PROCESSING
PUBLISHED
FAILED
```

Index:

```text
(status, available_at, created_at)
```

Outbox publisher sau này phải lấy dữ liệu bằng:

```sql
SELECT *
FROM integration.event_outbox
WHERE status = 'PENDING'
  AND available_at <= now()
ORDER BY created_at
FOR UPDATE SKIP LOCKED
LIMIT 100;
```

---

## 23.5. `integration.event_inbox`

Dùng để consumer chống xử lý trùng.

```text
id UUID PK
event_id UUID NOT NULL
consumer_name TEXT NOT NULL
event_type VARCHAR(100) NOT NULL
received_at TIMESTAMPTZ NOT NULL
processed_at TIMESTAMPTZ NULL
status VARCHAR(20) NOT NULL
result_reference_id UUID NULL
error_code VARCHAR(50) NULL
created_at TIMESTAMPTZ NOT NULL
UNIQUE (event_id, consumer_name)
```

---

## 23.6. `integration.idempotency_record`

```text
id UUID PK
idempotency_key UUID NOT NULL
actor_id UUID NOT NULL
operation_name VARCHAR(100) NOT NULL
request_hash CHAR(64) NOT NULL
response_status INTEGER NULL
response_payload JSONB NULL
resource_type VARCHAR(40) NULL
resource_id UUID NULL
expires_at TIMESTAMPTZ NOT NULL
created_at TIMESTAMPTZ NOT NULL
UNIQUE (actor_id, operation_name, idempotency_key)
```

---

## 23.7. `integration.notification`

```text
id UUID PK
employee_id UUID NOT NULL FK identity.employee
notification_type VARCHAR(50) NOT NULL
title TEXT NOT NULL
message TEXT NOT NULL
resource_type VARCHAR(40) NULL
resource_id UUID NULL
status VARCHAR(20) NOT NULL
created_at TIMESTAMPTZ NOT NULL
read_at TIMESTAMPTZ NULL
```

Status:

```text
UNREAD
READ
DISMISSED
```

---

# 24. Audit schema

## 24.1. `audit.audit_event`

Append-only.

```text
id UUID PK
event_time TIMESTAMPTZ NOT NULL
actor_type VARCHAR(20) NOT NULL
actor_id UUID NULL
action VARCHAR(60) NOT NULL
resource_type VARCHAR(40) NOT NULL
resource_id UUID NULL
customer_id UUID NULL
loan_application_id UUID NULL
result VARCHAR(20) NOT NULL
ip_address INET NULL
user_agent TEXT NULL
session_id TEXT NULL
request_id UUID NULL
correlation_id UUID NULL
metadata JSONB NOT NULL DEFAULT '{}'
previous_hash CHAR(64) NULL
event_hash CHAR(64) NOT NULL
created_at TIMESTAMPTZ NOT NULL
```

Application role không được:

* Update.
* Delete.
* Truncate.

Tạo trigger từ chối update/delete cho mọi runtime role.

Không lưu:

* Access token.
* Refresh token.
* API key.
* Password.
* Toàn bộ nội dung tài liệu.
* CCCD đầy đủ.

---

# 25. Row-Level Security

Tạo RLS cho:

* `customer.customer`
* `customer.party_identifier`
* `customer.party_contact`
* `banking.account`
* `banking.transaction`
* `document.document`
* `document.document_version`
* `document.extracted_field`
* `credit.loan_application`
* `credit.loan_decision`
* `ai.conversation`
* `ai.analysis_case`
* `ai.finding`
* `ai.report`

Tạo helper functions:

```sql
identity.current_employee_id()
identity.current_branch_id()
identity.current_is_admin()
identity.can_access_customer(employee_id, customer_id)
identity.can_access_loan(employee_id, loan_application_id)
```

Backend sau này phải set trong mỗi transaction:

```sql
SET LOCAL app.employee_id = '<uuid>';
SET LOCAL app.branch_id = '<uuid>';
SET LOCAL app.is_admin = 'false';
```

Không được fallback cho phép truy cập khi session variable thiếu.

Nếu không có context hợp lệ, policy phải deny.

---

# 26. Readonly views

Tạo các view che dữ liệu:

```text
customer.v_customer_summary
banking.v_account_masked
banking.v_transaction_summary
document.v_document_summary
credit.v_loan_application_summary
ai.v_report_summary
```

Không đưa vào view:

* `encrypted_value`.
* Secret.
* API credential.
* Full account number.
* Raw payload nhạy cảm.

---

# 27. MinIO configuration

## 27.1. Buckets

Tạo:

```text
upload-quarantine
customer-doc-original
customer-doc-derived
policy-documents
generated-reports
audit-archive
```

## 27.2. Object keys

Không chứa:

* Tên khách hàng.
* CCCD.
* Số tài khoản.
* Email.
* Số điện thoại.

Sử dụng:

```text
upload-quarantine/
  uploads/{upload_id}/incoming

customer-doc-original/
  documents/{document_id}/versions/{document_version_id}/original

customer-doc-derived/
  documents/{document_id}/versions/{document_version_id}/ocr/result.json
  documents/{document_id}/versions/{document_version_id}/pages/0001.png
  documents/{document_id}/versions/{document_version_id}/redacted/preview.pdf

policy-documents/
  policies/{policy_id}/versions/{policy_version_id}/original.pdf
  policies/{policy_id}/versions/{policy_version_id}/parsed.json

generated-reports/
  analysis-cases/{analysis_case_id}/reports/{report_id}/v{version}/report.pdf
  analysis-cases/{analysis_case_id}/reports/{report_id}/v{version}/report.json

audit-archive/
  audit/{yyyy}/{mm}/{dd}/events-{batch_id}.jsonl
```

## 27.3. Versioning

Bật versioning cho:

```text
customer-doc-original
policy-documents
generated-reports
audit-archive
```

## 27.4. Lifecycle

### `upload-quarantine`

* Xóa object hiện tại sau 3 ngày.
* Abort incomplete multipart upload sau 1 ngày.

### `customer-doc-derived`

* Retention cấu hình bằng biến môi trường.
* Không tự xóa nếu object đang legal hold.

### `customer-doc-original`

* Không tự động xóa.
* Việc xóa phải dựa trên retention record trong PostgreSQL.

### `audit-archive`

* Không tự xóa trong local.
* Hỗ trợ Object Lock khi cấu hình.

## 27.5. CORS

Cho phép local frontend:

```text
Origin: http://localhost:3000
Methods: GET, PUT, HEAD
Headers: *
Expose: ETag, x-amz-version-id
```

Không cho phép public anonymous access.

## 27.6. MinIO users và policies

Tạo service account:

```text
bank-api
document-worker
policy-worker
report-worker
audit-writer
```

### `bank-api`

Được:

* Tạo presigned URL.
* Upload vào quarantine.
* Download object được phân quyền.
* Đọc report.

Không được:

* Xóa audit archive.
* Thay đổi bucket policy.

### `document-worker`

Được:

* Đọc quarantine.
* Copy sang original.
* Đọc original.
* Ghi derived.

### `policy-worker`

Được:

* Đọc policy document.
* Ghi parsed policy.

### `report-worker`

Được:

* Ghi generated-reports.
* Đọc evidence cần thiết qua backend/service contract.

### `audit-writer`

Chỉ được:

* Ghi audit archive.
* Không sửa object cũ khi Object Lock được bật.

Root credential chỉ dùng bootstrap.

---

# 28. Redis configuration

Redis sử dụng password.

Cấu hình:

```text
appendonly yes
appendfsync everysec
save 900 1
save 300 10
save 60 10000
maxmemory 512mb
maxmemory-policy allkeys-lru
```

Key namespace:

```text
bank-ai:cache:*
bank-ai:lock:*
bank-ai:rate-limit:*
bank-ai:sse:*
bank-ai:jwks:*
```

Distributed lock phải có:

* TTL.
* Owner token.
* Safe release bằng Lua script.

Redis Pub/Sub chỉ được dùng cho live fan-out.

Tên channel:

```text
bank-ai:sse:employee:{employee_id}
bank-ai:sse:job:{job_id}
bank-ai:sse:analysis:{analysis_case_id}
```

Không coi Pub/Sub là nguồn sự thật.

Nếu subscriber mất kết nối, backend phải lấy lại trạng thái từ PostgreSQL.

---

# 29. Kafka configuration

## 29.1. Chế độ

Sử dụng Kafka KRaft.

Môi trường local:

```text
1 node
process.roles=broker,controller
```

Tạo template HA:

```text
3 Kafka nodes
replication factor 3
min.insync.replicas 2
```

HA template không bắt buộc chạy mặc định, nhưng phải có tài liệu.

## 29.2. Listener

```text
INTERNAL  : kafka:9092
CONTROLLER: kafka:9093
EXTERNAL  : localhost:29092
```

Local security:

```text
INTERNAL = SASL_PLAINTEXT
EXTERNAL = SASL_PLAINTEXT
CONTROLLER = PLAINTEXT trên private network
SASL mechanism = SCRAM-SHA-512
```

Tạo template production:

```text
SASL_SSL
TLS certificates
hostname verification
```

## 29.3. Kafka credentials

Sinh secret cho:

```text
kafka-admin
bank-api
document-worker
analysis-orchestrator
credit-worker
compliance-worker
report-worker
notification-gateway
audit-consumer
```

Environment keys:

```dotenv
KAFKA_ADMIN_USERNAME=kafka-admin
KAFKA_ADMIN_PASSWORD=<generate>

KAFKA_BANK_API_USERNAME=bank-api
KAFKA_BANK_API_PASSWORD=<generate>

KAFKA_DOCUMENT_WORKER_USERNAME=document-worker
KAFKA_DOCUMENT_WORKER_PASSWORD=<generate>

KAFKA_ANALYSIS_ORCHESTRATOR_USERNAME=analysis-orchestrator
KAFKA_ANALYSIS_ORCHESTRATOR_PASSWORD=<generate>

KAFKA_CREDIT_WORKER_USERNAME=credit-worker
KAFKA_CREDIT_WORKER_PASSWORD=<generate>

KAFKA_COMPLIANCE_WORKER_USERNAME=compliance-worker
KAFKA_COMPLIANCE_WORKER_PASSWORD=<generate>

KAFKA_REPORT_WORKER_USERNAME=report-worker
KAFKA_REPORT_WORKER_PASSWORD=<generate>

KAFKA_NOTIFICATION_GATEWAY_USERNAME=notification-gateway
KAFKA_NOTIFICATION_GATEWAY_PASSWORD=<generate>

KAFKA_AUDIT_CONSUMER_USERNAME=audit-consumer
KAFKA_AUDIT_CONSUMER_PASSWORD=<generate>
```

Không commit giá trị thật.

---

# 30. Kafka topics

Tạo các topic sau.

## 30.1. Document topics

```text
bank.document.commands.v1
bank.document.events.v1
```

Commands:

```text
document.processing.requested
document.security-scan.requested
document.ocr.requested
document.classification.requested
document.extraction.requested
document.embedding.requested
```

Events:

```text
document.processing.started
document.security-scan.completed
document.ocr.completed
document.classification.completed
document.extraction.completed
document.embedding.completed
document.processing.completed
document.processing.failed
```

Partition key:

```text
document_version_id
```

---

## 30.2. Analysis topics

```text
bank.analysis.commands.v1
bank.analysis.events.v1
```

Commands:

```text
analysis.requested
analysis.document-agent.requested
analysis.credit-agent.requested
analysis.compliance-agent.requested
analysis.validation.requested
analysis.synthesis.requested
```

Events:

```text
analysis.started
analysis.plan.created
analysis.task.started
analysis.task.completed
finding.created
analysis.validation.completed
analysis.completed
analysis.failed
```

Partition key:

```text
analysis_case_id
```

---

## 30.3. Report topics

```text
bank.report.commands.v1
bank.report.events.v1
```

Commands:

```text
report.generation.requested
report.pdf.requested
```

Events:

```text
report.generation.started
report.generated
report.pdf.generated
report.generation.failed
```

Partition key:

```text
report_id
```

---

## 30.4. Notification topic

```text
bank.notification.events.v1
```

Events:

```text
job.progress.updated
job.completed
job.failed
notification.created
```

Partition key:

```text
employee_id hoặc job_id
```

---

## 30.5. Job status topic

```text
bank.job-status.v1
```

Cấu hình:

```text
cleanup.policy=compact,delete
```

Key:

```text
job_id
```

Giá trị mới nhất là trạng thái hiện tại.

PostgreSQL vẫn là nguồn sự thật.

---

## 30.6. Audit topic

```text
bank.audit.events.v1
```

Audit event phục vụ consumer ghi archive hoặc analytics.

Không thay thế bảng `audit.audit_event`.

---

## 30.7. Retry và DLQ

```text
bank.retry.1m.v1
bank.retry.10m.v1
bank.dead-letter.v1
```

Không retry vô hạn.

---

# 31. Topic configuration

Local:

```text
partitions=3
replication.factor=1
```

HA:

```text
partitions>=3
replication.factor=3
min.insync.replicas=2
```

Đề xuất retention:

| Topic               |        Retention |
| ------------------- | ---------------: |
| Commands            |           7 ngày |
| Document events     |          30 ngày |
| Analysis events     |          30 ngày |
| Report events       |          30 ngày |
| Notification events |           3 ngày |
| Audit events        |          30 ngày |
| Retry topics        |           7 ngày |
| DLQ                 |          30 ngày |
| Job status          | Compact + 7 ngày |

Giới hạn message:

```text
1 MiB mặc định
```

Không đưa file, ảnh hoặc OCR text lớn vào Kafka.

---

# 32. Kafka event envelope

Tạo JSON Schema:

```json
{
  "event_id": "uuid",
  "event_type": "document.processing.requested",
  "event_version": 1,
  "occurred_at": "2026-07-18T07:00:00Z",
  "producer": "bank-api",
  "correlation_id": "uuid",
  "causation_id": "uuid-or-null",
  "partition_key": "uuid",
  "actor": {
    "type": "EMPLOYEE|SERVICE|AGENT",
    "id": "uuid"
  },
  "resource": {
    "type": "DOCUMENT_VERSION",
    "id": "uuid"
  },
  "payload": {},
  "metadata": {
    "trace_id": "uuid",
    "schema": "document.processing.requested.v1"
  }
}
```

Mọi field bắt buộc phải được validate.

Không đưa vào event:

* Access token.
* Refresh token.
* API key.
* Password.
* CCCD đầy đủ.
* Số tài khoản đầy đủ.
* PDF.
* Ảnh base64.
* Toàn bộ OCR text.
* Toàn bộ hồ sơ khách hàng.

Event chỉ chứa:

* ID.
* Trạng thái.
* Metadata tối thiểu.
* Correlation.
* Resource reference.

---

# 33. Kafka ACL

## `bank-api`

Được produce:

```text
bank.document.commands.v1
bank.analysis.commands.v1
bank.report.commands.v1
```

Không được consume worker topics.

## `document-worker`

Consume:

```text
bank.document.commands.v1
```

Produce:

```text
bank.document.events.v1
bank.notification.events.v1
bank.job-status.v1
bank.retry.1m.v1
bank.retry.10m.v1
bank.dead-letter.v1
```

## `analysis-orchestrator`

Consume:

```text
bank.analysis.commands.v1
bank.document.events.v1
```

Produce:

```text
bank.analysis.commands.v1
bank.analysis.events.v1
bank.notification.events.v1
```

## `credit-worker` và `compliance-worker`

Consume:

```text
bank.analysis.commands.v1
```

Produce:

```text
bank.analysis.events.v1
bank.notification.events.v1
bank.dead-letter.v1
```

## `report-worker`

Consume:

```text
bank.report.commands.v1
bank.analysis.events.v1
```

Produce:

```text
bank.report.events.v1
bank.notification.events.v1
```

## `notification-gateway`

Consume:

```text
bank.notification.events.v1
bank.job-status.v1
```

Không produce business command.

## `audit-consumer`

Consume:

```text
bank.audit.events.v1
document events
analysis events
report events
```

Không được produce business command.

---

# 34. Kafka consumer groups

```text
document-worker-group
analysis-orchestrator-group
credit-worker-group
compliance-worker-group
report-worker-group
notification-gateway-group
audit-consumer-group
```

Mỗi consumer phải chống duplicate bằng `integration.event_inbox`.

---

# 35. Keycloak configuration

## 35.1. Realm

```text
bank-ai
```

## 35.2. Public endpoints

```text
Issuer:
http://localhost:8080/realms/bank-ai

Authorization:
http://localhost:8080/realms/bank-ai/protocol/openid-connect/auth

Token:
http://localhost:8080/realms/bank-ai/protocol/openid-connect/token

JWKS:
http://localhost:8080/realms/bank-ai/protocol/openid-connect/certs

Logout:
http://localhost:8080/realms/bank-ai/protocol/openid-connect/logout
```

## 35.3. Clients

### `bank-ai-frontend`

```text
Public client
Authorization Code Flow
PKCE S256
Direct Access Grants disabled
Redirect URI: http://localhost:3000/*
Web Origin: http://localhost:3000
```

Không có client secret.

### `bank-ai-backend`

```text
Confidential client
Service account enabled
Audience: bank-ai-api
```

### `bank-ai-worker`

```text
Confidential client
Service account enabled
Audience: bank-ai-api
```

## 35.4. Realm roles

```text
credit_officer
credit_manager
document_reviewer
compliance_officer
risk_officer
loan_approver
auditor
admin
```

## 35.5. Demo users

```text
credit.officer@example.local
credit.manager@example.local
document.reviewer@example.local
compliance@example.local
approver@example.local
auditor@example.local
admin@example.local
```

Password phải lấy từ `.env.local`.

Không ghi password vào realm JSON.

---

# 36. Secret generation

Tạo:

```text
infra/scripts/generate-secrets.sh
infra/scripts/generate-secrets.ps1
```

Phải sinh:

```text
POSTGRES_SUPERUSER_PASSWORD
POSTGRES_MIGRATOR_PASSWORD
POSTGRES_APP_PASSWORD
POSTGRES_WORKER_PASSWORD
POSTGRES_READONLY_PASSWORD
KEYCLOAK_DB_PASSWORD
REDIS_PASSWORD
MINIO_ROOT_PASSWORD
MINIO_BANK_API_SECRET_KEY
MINIO_DOCUMENT_WORKER_SECRET_KEY
MINIO_POLICY_WORKER_SECRET_KEY
MINIO_REPORT_WORKER_SECRET_KEY
MINIO_AUDIT_WRITER_SECRET_KEY
KEYCLOAK_ADMIN_PASSWORD
KEYCLOAK_BACKEND_CLIENT_SECRET
KEYCLOAK_WORKER_CLIENT_SECRET
KAFKA_ADMIN_PASSWORD
KAFKA_BANK_API_PASSWORD
KAFKA_DOCUMENT_WORKER_PASSWORD
KAFKA_ANALYSIS_ORCHESTRATOR_PASSWORD
KAFKA_CREDIT_WORKER_PASSWORD
KAFKA_COMPLIANCE_WORKER_PASSWORD
KAFKA_REPORT_WORKER_PASSWORD
KAFKA_NOTIFICATION_GATEWAY_PASSWORD
KAFKA_AUDIT_CONSUMER_PASSWORD
FIELD_ENCRYPTION_KEY
SEED_USER_PASSWORD
```

Yêu cầu:

* Dùng secure random.
* Không ghi đè file nếu chưa có `--force`.
* Không in toàn bộ secret ra console.
* `.env.local` phải nằm trong `.gitignore`.
* `.env.example` chỉ chứa placeholder.

---

# 37. Seed data

Tạo dữ liệu giả lập, không sử dụng người thật.

Seed:

* 3 chi nhánh.
* 4 phòng ban.
* Role và permission.
* 7 nhân viên demo.
* 3 khách hàng cá nhân.
* 2 tài khoản mỗi khách hàng.
* 12 tháng giao dịch.
* Một khách hàng có:

  * Thu nhập khai báo 30 triệu.
  * Phiếu lương 28 triệu.
  * Giao dịch lương bình quân 22 triệu.
  * Khoản nợ hiện hữu 6 triệu/tháng.
* Một sản phẩm vay.
* Một loan application 700 triệu, 60 tháng.
* Một policy.
* Các policy clause.
* Checklist tài liệu.
* Một background job mẫu.
* Một outbox event mẫu ở trạng thái PENDING.

Seed phải idempotent.

---

# 38. Makefile

Tạo target:

```text
make secrets
make infra-up
make infra-down
make infra-reset
make infra-logs
make infra-ps

make db-migrate
make db-seed
make db-shell
make db-verify

make kafka-init
make kafka-topics
make kafka-acls
make kafka-smoke
make kafka-describe

make minio-init
make minio-verify

make keycloak-init
make keycloak-verify

make tools-up
make observability-up

make verify
make clean
```

`infra-reset` phải cảnh báo và yêu cầu xác nhận trước khi xóa volume.

---

# 39. Health checks

## PostgreSQL

```text
pg_isready
```

Đồng thời kiểm tra:

* Database `bank_ai`.
* Database `keycloak`.
* Extension vector.
* Migration table.

## Redis

```text
redis-cli AUTH <password>
redis-cli PING
```

## Kafka

Kiểm tra:

* Broker reachable.
* Metadata query thành công.
* Topic tồn tại.
* Produce/consume smoke event thành công.

## MinIO

Kiểm tra:

* Health endpoint.
* Buckets.
* Versioning.
* Lifecycle.
* Service account policy.

## Keycloak

Kiểm tra:

* Realm endpoint.
* OIDC discovery.
* Token endpoint.
* Demo user login.
* Audience claim.

---

# 40. Smoke test bắt buộc

Tạo `verify-stack.sh` và `verify-stack.ps1`.

Kiểm tra:

1. `docker compose config` hợp lệ.
2. Không image nào dùng `latest`.
3. Không có placeholder `changeme`.
4. PostgreSQL healthy.
5. pgvector hoạt động.
6. Migrations chạy hết.
7. Seed chạy được hai lần.
8. Redis yêu cầu password.
9. Redis PING thành công.
10. Kafka KRaft healthy.
11. Tất cả topic tồn tại.
12. Topic có đúng partition và retention.
13. Kafka ACL hoạt động.
14. User không có quyền bị từ chối.
15. Produce/consume smoke test thành công.
16. MinIO buckets tồn tại.
17. Bucket versioning đúng.
18. Lifecycle đúng.
19. Anonymous access bị từ chối.
20. Service account có đúng quyền.
21. Keycloak realm tồn tại.
22. Clients tồn tại.
23. Roles tồn tại.
24. Demo token lấy được.
25. PgAdmin chỉ chạy trong tools profile.
26. Kafka UI chỉ chạy trong tools profile.
27. Prometheus/Grafana chỉ chạy trong observability profile.
28. `.env.local` không được Git track.
29. Không có secret trong source code.
30. README đủ để thành viên mới chạy stack.

---

# 41. Observability

Tạo profile `observability`.

Theo dõi tối thiểu:

## PostgreSQL

* Connections.
* Transaction rate.
* Slow query.
* Cache hit.
* Database size.

## Kafka

* Broker up.
* Under-replicated partition.
* Consumer lag.
* Request latency.
* Bytes in/out.
* Offline partition.

## Redis

* Memory.
* Hit rate.
* Evictions.
* Connections.
* Command latency.

## MinIO

* Storage usage.
* Request rate.
* Error rate.
* Object count.

Tạo Grafana dashboard cơ bản.

Không bắt buộc observability profile chạy mặc định.

---

# 42. Security requirements

1. Không commit `.env.local`.
2. Không dùng secret mặc định.
3. Không dùng image `latest`.
4. Không public PostgreSQL trong production.
5. Không public Redis trong production.
6. MinIO bucket phải private.
7. Frontend không có MinIO credential.
8. Frontend không có Kafka credential.
9. Frontend không có database credential.
10. Keycloak frontend client không có client secret.
11. Kafka local dùng SASL/SCRAM.
12. Production template dùng SASL_SSL.
13. Không đưa PII vào Kafka event.
14. Không đưa PII vào MinIO object key.
15. Không log token hoặc secret.
16. Runtime DB roles không được `BYPASSRLS`.
17. Audit table append-only.
18. Dữ liệu định danh phải được mã hóa hoặc hash.
19. Presigned URL mặc định hết hạn sau 10 phút.
20. Không cho anonymous MinIO access.
21. Không cho Kafka auto-create topic.
22. Kafka topic phải được bootstrap có kiểm soát.
23. Không dùng Redis làm nguồn sự thật.
24. Không dùng Kafka làm database nghiệp vụ.
25. Không lưu private chain-of-thought.

---

# 43. Anti-patterns bị cấm

Không được:

```text
Backend ghi PostgreSQL rồi publish Kafka trực tiếp mà không có Outbox.

Lưu PDF trong PostgreSQL BYTEA.

Đưa PDF base64 vào Kafka.

Dùng Redis Pub/Sub làm hàng đợi nghiệp vụ bền vững.

Dùng Kafka làm nguồn sự thật của trạng thái khoản vay.

Cho browser làm Kafka consumer.

Cho frontend giữ MinIO secret.

Dùng filename làm object key.

Đưa CCCD vào object key.

Dùng FLOAT cho tiền.

Cho bank_app sở hữu schema.

Cho worker ghi loan_decision.

Tắt kiểm tra JWT issuer hoặc audience.

Tạo topic tự động bằng broker.

Dùng cùng một Kafka user cho mọi service.

Dùng MinIO root credential ở runtime.

Hard-code password trong Docker Compose.

Để tất cả service nằm trong một Docker network public.
```

---

# 44. Tài liệu bắt buộc

## `docs/architecture.md`

Có Mermaid diagram cho:

* Toàn bộ topology.
* Document pipeline.
* Credit analysis pipeline.
* Kafka event flow.
* Notification flow.

## `docs/ports-and-urls.md`

Liệt kê:

* Public port.
* Internal hostname.
* Protocol.
* Credential key.
* Service sử dụng.

## `docs/data-dictionary.md`

Mô tả:

* Tất cả table.
* Tất cả column.
* Kiểu dữ liệu.
* Nullable.
* Default.
* FK.
* Index.
* Ý nghĩa nghiệp vụ.
* Dữ liệu nhạy cảm hay không.
* Retention class.

## `docs/kafka-contract.md`

Mô tả:

* Topic.
* Producer.
* Consumer group.
* Partition key.
* Retention.
* Event types.
* Retry.
* DLQ.
* Schema versioning.
* Idempotency.

## `docs/minio-layout.md`

Mô tả:

* Buckets.
* Object keys.
* Versioning.
* Lifecycle.
* Policy.
* Service accounts.
* Presigned URL flow.

## `docs/security.md`

Mô tả:

* Network isolation.
* Secret management.
* Encryption.
* Kafka ACL.
* MinIO policy.
* RLS.
* Keycloak.
* Audit.

## `docs/runbook.md`

Mô tả:

* Khởi động.
* Dừng.
* Reset.
* Backup.
* Restore.
* Rotate password.
* Add Kafka topic.
* Re-run migration.
* Xử lý Kafka lag.
* Xử lý MinIO đầy.
* Xử lý migration lỗi.
* Xử lý volume cũ.
* Xử lý port conflict.

---

# 45. README

README phải có hướng dẫn cho:

* Windows Docker Desktop.
* WSL2.
* Linux.
* Copy `.env.example`.
* Generate secret.
* Start infra.
* Run migration.
* Seed data.
* Start tools.
* Open Keycloak.
* Open MinIO Console.
* Open Kafka UI.
* Open PgAdmin.
* Run smoke tests.
* Reset local data.
* Troubleshooting.

Lệnh khởi động mong muốn:

```bash
make secrets
make infra-up
make db-migrate
make db-seed
make kafka-init
make minio-init
make keycloak-init
make verify
```

Hoặc:

```bash
make bootstrap
```

`make bootstrap` phải idempotent.

---

# 46. Definition of Done

Chỉ coi công việc hoàn thành khi:

1. Repository có đầy đủ cấu trúc yêu cầu.
2. `docker compose config` thành công.
3. Không dùng image `latest`.
4. `make bootstrap` chạy được trên môi trường sạch.
5. PostgreSQL khởi động.
6. Database `bank_ai` tồn tại.
7. Database `keycloak` tồn tại.
8. pgvector hoạt động.
9. Tất cả migration chạy thành công.
10. Tất cả schema và table tồn tại.
11. SQL comments tồn tại.
12. RLS được bật.
13. Runtime role không `BYPASSRLS`.
14. Seed data hoạt động và idempotent.
15. Redis yêu cầu authentication.
16. Kafka chạy KRaft.
17. Kafka listener nội bộ và external hoạt động.
18. Kafka SCRAM user tồn tại.
19. Kafka ACL hoạt động.
20. Tất cả topic tồn tại.
21. Produce/consume smoke test thành công.
22. MinIO buckets tồn tại.
23. Versioning đúng.
24. Lifecycle đúng.
25. MinIO policies đúng.
26. Anonymous access bị từ chối.
27. Keycloak realm tồn tại.
28. Keycloak clients và roles tồn tại.
29. Demo token lấy được.
30. Tool profiles hoạt động.
31. Observability profile hoạt động.
32. Không có secret trong Git.
33. Không có dữ liệu người thật.
34. Tài liệu đầy đủ.
35. `verify-stack` trả exit code 0.
36. Không service nào restart loop.
37. Không còn TODO quan trọng.
38. Không bỏ qua lỗi bằng cách tắt security.
39. Không thay đổi tên schema, table, topic, bucket và environment key đã quy định.
40. Cuối cùng, in ra báo cáo ngắn gồm:

    * Các file đã tạo.
    * Các service đã chạy.
    * Các port.
    * Credential lấy từ file nào.
    * Kết quả smoke test.
    * Những giới hạn còn lại.

---

# 47. Cách thực hiện

Hãy thực hiện theo thứ tự:

1. Kiểm tra repository.
2. Tạo kế hoạch file cần thay đổi.
3. Tạo `.env.example`.
4. Tạo script sinh secret.
5. Tạo Docker networks và volumes.
6. Dựng PostgreSQL.
7. Tạo roles và database.
8. Tạo Flyway migrations.
9. Tạo schemas và tables.
10. Tạo indexes.
11. Tạo RLS.
12. Tạo seed data.
13. Dựng Redis.
14. Dựng Kafka KRaft.
15. Tạo Kafka users, topics và ACL.
16. Dựng MinIO.
17. Tạo buckets, policies và lifecycle.
18. Dựng Keycloak.
19. Tạo realm, clients, roles và demo users.
20. Dựng tools profile.
21. Dựng observability profile.
22. Viết tài liệu.
23. Chạy toàn bộ stack.
24. Chạy smoke tests.
25. Sửa mọi lỗi.
26. Chạy lại trên volume sạch.
27. Báo cáo kết quả.

Không dừng lại sau khi chỉ tạo file. Phải chạy kiểm tra cấu hình và sửa lỗi có thể phát hiện trong môi trường hiện tại.