# BACKEND IMPLEMENTATION INSTRUCTIONS

# AI CREDIT INTELLIGENCE WORKBENCH

## 1. Bối cảnh sản phẩm

AI Credit Intelligence Workbench là hệ thống AI nội bộ dành cho nhân viên ngân hàng.

Hệ thống hỗ trợ nhân viên:

1. Tìm kiếm khách hàng.
2. Xem thông tin tổng hợp khách hàng.
3. Truy vấn tài khoản và giao dịch.
4. Upload hồ sơ PDF hoặc ảnh.
5. Theo dõi tiến trình xử lý tài liệu.
6. OCR và phân loại tài liệu.
7. Trích xuất các trường dữ liệu.
8. Xác minh hoặc sửa dữ liệu OCR.
9. Kiểm tra bộ hồ sơ còn thiếu.
10. Đối chiếu thông tin giữa hồ sơ, giao dịch và dữ liệu khách hàng.
11. Phân tích thu nhập và khả năng trả nợ.
12. Tính DTI, DSCR, LTV và lịch trả nợ.
13. Kiểm tra chính sách tín dụng.
14. Điều phối các agent chuyên gia.
15. Kiểm tra bằng chứng và phép tính.
16. Sinh báo cáo hỗ trợ thẩm định.
17. Truy ngược từng kết luận tới nguồn dữ liệu.
18. Cho phép người có thẩm quyền đưa ra quyết định cuối cùng.

AI không được tự động phê duyệt hoặc từ chối khoản vay.

AI chỉ được tạo:

* Phân tích.
* Finding.
* Risk flag.
* Policy check.
* Khuyến nghị.
* Điều kiện cần bổ sung.
* Báo cáo hỗ trợ quyết định.

Quyết định chính thức phải được tạo bởi một nhân viên có quyền `loan:approve`.

---

# 2. Phạm vi backend

Backend chịu trách nhiệm:

* REST API cho frontend.
* SSE API để frontend theo dõi tiến trình.
* Xác thực JWT do Keycloak cấp.
* Phân quyền nhân viên.
* Truy cập PostgreSQL.
* Tạo presigned URL cho MinIO.
* Ghi trạng thái nghiệp vụ.
* Tạo background job.
* Ghi Kafka event vào Outbox.
* Publish Outbox event lên Kafka.
* Consume Kafka event.
* Chạy document worker.
* Chạy analysis orchestrator.
* Chạy các expert worker.
* Chạy validator.
* Chạy report worker.
* Dùng Redis cho cache, lock và live event fan-out.
* Ghi application log.
* Ghi audit event.
* Sinh OpenAPI.
* Cung cấp health và readiness endpoint.

Backend không chịu trách nhiệm dựng:

* PostgreSQL server.
* Kafka broker.
* Kafka topic.
* Redis server.
* MinIO server.
* MinIO bucket.
* Keycloak realm.
* Frontend.

Các thành phần trên do phần infrastructure cung cấp.

---

# 3. Công nghệ backend

Sử dụng:

```text
Python 3.12
FastAPI
Pydantic 2
Pydantic Settings
SQLAlchemy 2 async
asyncpg
Alembic chỉ khi cần migration bổ sung
HTTPX
aiokafka hoặc confluent-kafka-python
redis-py asyncio
boto3 hoặc MinIO Python SDK
pgvector
PyJWT, python-jose hoặc Authlib
structlog
OpenTelemetry-compatible tracing
pytest
pytest-asyncio
Ruff
mypy
```

Ưu tiên:

```text
FastAPI
SQLAlchemy async
asyncpg
aiokafka
redis.asyncio
boto3
structlog
pytest
```

Không sử dụng nhiều framework agent nếu chưa cần thiết. Các agent phải được triển khai dưới dạng application service có input/output schema rõ ràng.

---

# 4. Nguyên tắc kiến trúc

Backend phải tuân thủ kiến trúc phân lớp:

```text
API Router
    ↓
Application Service
    ↓
Domain Service
    ↓
Repository / External Adapter
    ↓
PostgreSQL / Kafka / Redis / MinIO / LLM / OCR
```

Không đặt business logic trong FastAPI router.

Không để SQL query trực tiếp rải rác trong router hoặc agent.

Không để LLM truy cập trực tiếp database.

Không cho LLM tự sinh SQL không kiểm soát.

Không cho frontend gọi trực tiếp Kafka, PostgreSQL, Redis hoặc MinIO bằng credential nội bộ.

---

# 5. Kiến trúc runtime

```text
Frontend
    │
    │ REST API + SSE
    ▼
FastAPI Backend
    │
    ├── Keycloak JWT verification
    ├── PostgreSQL
    ├── Redis
    ├── MinIO
    └── PostgreSQL Outbox
              │
              ▼
       Outbox Publisher
              │
              ▼
            Kafka
              │
      ┌───────┼──────────────────┐
      ▼       ▼                  ▼
Document   Analysis           Report
Workers    Workers            Workers
      │       │                  │
      └───────┴─────────┬────────┘
                        ▼
                  PostgreSQL
                        │
                        ▼
                 Kafka completion event
                        │
                        ▼
                Notification Consumer
                        │
                        ▼
                    Redis Pub/Sub
                        │
                        ▼
                  FastAPI SSE
                        │
                        ▼
                    Frontend
```

PostgreSQL lưu trạng thái chính thức.

Kafka vận chuyển event.

Redis chỉ chuyển tín hiệu thời gian thực và cache.

MinIO lưu file.

---

# 6. Cấu trúc source code

Tạo cấu trúc tương đương:

```text
backend/
├── agent.md
├── intructions.md
├── Dockerfile
├── pyproject.toml
├── README.md
├── .env.example
│
├── app/
│   ├── main.py
│   ├── config.py
│   ├── logging.py
│   ├── exceptions.py
│   ├── dependencies.py
│   │
│   ├── middleware/
│   │   ├── request_context.py
│   │   ├── audit.py
│   │   ├── security_headers.py
│   │   └── error_handler.py
│   │
│   ├── auth/
│   │   ├── jwt_validator.py
│   │   ├── principal.py
│   │   ├── permissions.py
│   │   ├── resource_access.py
│   │   └── dependencies.py
│   │
│   ├── api/
│   │   ├── router.py
│   │   └── v1/
│   │       ├── health.py
│   │       ├── me.py
│   │       ├── customers.py
│   │       ├── accounts.py
│   │       ├── transactions.py
│   │       ├── documents.py
│   │       ├── loans.py
│   │       ├── conversations.py
│   │       ├── analyses.py
│   │       ├── findings.py
│   │       ├── policies.py
│   │       ├── reports.py
│   │       ├── jobs.py
│   │       ├── notifications.py
│   │       └── audit.py
│   │
│   ├── schemas/
│   │   ├── common.py
│   │   ├── customer.py
│   │   ├── transaction.py
│   │   ├── document.py
│   │   ├── loan.py
│   │   ├── analysis.py
│   │   ├── evidence.py
│   │   ├── report.py
│   │   ├── job.py
│   │   └── event.py
│   │
│   ├── db/
│   │   ├── session.py
│   │   ├── transaction.py
│   │   ├── rls_context.py
│   │   └── models/
│   │
│   ├── repositories/
│   │   ├── customer_repository.py
│   │   ├── account_repository.py
│   │   ├── transaction_repository.py
│   │   ├── document_repository.py
│   │   ├── loan_repository.py
│   │   ├── policy_repository.py
│   │   ├── analysis_repository.py
│   │   ├── evidence_repository.py
│   │   ├── report_repository.py
│   │   ├── job_repository.py
│   │   ├── outbox_repository.py
│   │   ├── inbox_repository.py
│   │   └── audit_repository.py
│   │
│   ├── services/
│   │   ├── customer_service.py
│   │   ├── transaction_service.py
│   │   ├── upload_service.py
│   │   ├── document_service.py
│   │   ├── loan_service.py
│   │   ├── checklist_service.py
│   │   ├── calculation_service.py
│   │   ├── policy_service.py
│   │   ├── analysis_service.py
│   │   ├── evidence_service.py
│   │   ├── report_service.py
│   │   ├── job_service.py
│   │   └── notification_service.py
│   │
│   ├── storage/
│   │   ├── interface.py
│   │   └── minio_storage.py
│   │
│   ├── cache/
│   │   ├── redis_cache.py
│   │   ├── distributed_lock.py
│   │   └── pubsub.py
│   │
│   ├── messaging/
│   │   ├── event_envelope.py
│   │   ├── kafka_producer.py
│   │   ├── kafka_consumer.py
│   │   ├── outbox_publisher.py
│   │   ├── inbox_handler.py
│   │   └── topic_registry.py
│   │
│   ├── calculations/
│   │   ├── repayment.py
│   │   ├── affordability.py
│   │   ├── income.py
│   │   └── models.py
│   │
│   ├── document_processing/
│   │   ├── pipeline.py
│   │   ├── security_scan.py
│   │   ├── ocr.py
│   │   ├── classification.py
│   │   ├── extraction.py
│   │   ├── normalization.py
│   │   ├── validation.py
│   │   ├── chunking.py
│   │   └── embedding.py
│   │
│   ├── agents/
│   │   ├── base.py
│   │   ├── context_router.py
│   │   ├── orchestrator.py
│   │   ├── document_agent.py
│   │   ├── credit_agent.py
│   │   ├── compliance_agent.py
│   │   ├── validator.py
│   │   └── synthesizer.py
│   │
│   ├── providers/
│   │   ├── llm/
│   │   ├── embedding/
│   │   └── ocr/
│   │
│   ├── workers/
│   │   ├── document_worker.py
│   │   ├── analysis_orchestrator_worker.py
│   │   ├── credit_worker.py
│   │   ├── compliance_worker.py
│   │   ├── validation_worker.py
│   │   ├── report_worker.py
│   │   └── notification_worker.py
│   │
│   └── prompts/
│       ├── context-router/
│       ├── document-agent/
│       ├── credit-agent/
│       ├── compliance-agent/
│       ├── validator/
│       └── synthesizer/
│
└── tests/
    ├── unit/
    ├── integration/
    ├── contract/
    └── fixtures/
```

Có thể điều chỉnh cấu trúc nhỏ nếu repository đã có convention khác, nhưng không được phá vỡ các ranh giới module.

---

# 7. Configuration

Đọc environment variables do infrastructure cung cấp.

Không tự tạo tên mới khi đã có biến tương ứng trong:

```text
infra\intructions.md
infra\contracts\
.env.example
```

Backend cần ít nhất các nhóm cấu hình:

```text
APP
DATABASE
KEYCLOAK/OIDC
KAFKA
REDIS
MINIO
OCR
LLM
EMBEDDING
SECURITY
LOGGING
```

Sử dụng Pydantic Settings.

Không log giá trị secret.

Không cho production chạy nếu:

* Secret vẫn là placeholder.
* CORS dùng wildcard.
* JWT issuer bị thiếu.
* JWT audience bị thiếu.
* Database runtime user là superuser.
* MinIO sử dụng root credential.
* Kafka sử dụng admin credential.

---

# 8. Authentication flow

Luồng đăng nhập:

```text
Frontend
    ↓
Keycloak Authorization Code + PKCE
    ↓
Frontend nhận access token
    ↓
Frontend gọi Backend với Bearer token
    ↓
Backend tải hoặc dùng cached JWKS
    ↓
Backend kiểm tra JWT
    ↓
Backend ánh xạ JWT sub với identity.employee
    ↓
Backend tạo CurrentPrincipal
```

Backend phải kiểm tra:

* Signature.
* `iss`.
* `aud`.
* `exp`.
* `nbf`.
* `iat`.
* `sub`.
* Realm role.
* Employee status.

Không gọi token introspection cho mọi request nếu JWT có thể xác minh offline.

Khi gặp JWT `kid` mới:

1. Refresh JWKS cache.
2. Thử xác minh lại.
3. Từ chối nếu vẫn không hợp lệ.

---

# 9. Authorization flow

Authorization gồm hai lớp:

## Lớp quyền chức năng

Ví dụ:

```text
customer:read
transaction:read
document:upload
document:verify
loan:analyze
report:generate
loan:approve
```

## Lớp quyền tài nguyên

Nhân viên chỉ được truy cập:

* Khách hàng cùng chi nhánh.
* Khách hàng do mình quản lý.
* Loan application được phân công.
* Case được cấp scope.
* Tài nguyên mà role toàn cục cho phép.

Không chỉ kiểm tra role ở router.

Service layer phải kiểm tra lại quyền tài nguyên.

Trước mỗi database transaction có RLS, backend phải thiết lập:

```sql
SET LOCAL app.employee_id = '<employee_uuid>';
SET LOCAL app.branch_id = '<branch_uuid>';
SET LOCAL app.is_admin = 'false';
```

Thiếu context phải mặc định từ chối truy cập.

---

# 10. Luồng truy vấn đồng bộ

Ví dụ nhân viên hỏi tổng dòng tiền vào:

```text
Frontend
    ↓
GET transaction summary hoặc gửi chat message
    ↓
Backend xác thực
    ↓
Kiểm tra quyền khách hàng
    ↓
TransactionService
    ↓
TransactionRepository
    ↓
PostgreSQL
    ↓
Calculation bằng SQL hoặc code deterministic
    ↓
Response có dữ liệu và nguồn
```

Không gọi Kafka cho các truy vấn nhanh.

Không gọi agent nếu một tool deterministic có thể trả lời chính xác.

Không cho LLM cộng hàng nghìn giao dịch.

---

# 11. Document upload flow

## 11.1. Khởi tạo upload

Frontend gọi:

```http
POST /api/v1/documents/uploads
```

Backend:

1. Xác thực nhân viên.
2. Kiểm tra quyền với customer và loan application.
3. Kiểm tra filename, MIME khai báo và size.
4. Tạo `storage.upload_session`.
5. Tạo document metadata cần thiết.
6. Sinh object key UUID trong `upload-quarantine`.
7. Tạo presigned PUT URL.
8. Trả `upload_id`, URL, headers và thời hạn.

Frontend không nhận MinIO credential.

## 11.2. Frontend upload

Frontend PUT trực tiếp file vào presigned URL.

## 11.3. Hoàn tất upload

Frontend gọi:

```http
POST /api/v1/documents/uploads/{upload_id}/complete
```

Backend:

1. Kiểm tra upload session.
2. Kiểm tra hết hạn.
3. `HEAD` object trong MinIO.
4. Kiểm tra size.
5. Kiểm tra MIME thực tế ở bước worker.
6. Kiểm tra checksum.
7. Trong cùng một PostgreSQL transaction:

   * cập nhật upload session;
   * tạo `integration.background_job`;
   * tạo các job step;
   * tạo `integration.event_outbox`.
8. Commit.
9. Trả `202 Accepted`.

Không publish Kafka trực tiếp trong cùng request sau khi commit.

Outbox Publisher chịu trách nhiệm publish.

---

# 12. Outbox Publisher flow

Outbox Publisher là process riêng.

Luồng:

```text
SELECT PENDING event
    ↓
FOR UPDATE SKIP LOCKED
    ↓
Mark PROCESSING
    ↓
Publish Kafka
    ↓
Kafka acknowledge
    ↓
Mark PUBLISHED
```

Nếu publish thất bại:

* Tăng `attempt_count`.
* Đặt `available_at` cho retry.
* Lưu `last_error` an toàn.
* Không mất event.
* Không tạo event trùng ngoài ý muốn.

Outbox Publisher phải có:

* Batch size.
* Poll interval.
* Retry backoff.
* Graceful shutdown.
* Metrics.
* Structured log.

---

# 13. Kafka event contract

Mọi event phải tuân thủ schema trong infra.

Event envelope gồm:

```json
{
  "event_id": "uuid",
  "event_type": "document.processing.requested",
  "event_version": 1,
  "occurred_at": "ISO-8601",
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
    "schema": "event-name.v1"
  }
}
```

Không đưa vào Kafka:

* PDF.
* Ảnh.
* Base64.
* Toàn bộ OCR text.
* Access token.
* API key.
* Password.
* CCCD đầy đủ.
* Số tài khoản đầy đủ.
* Hồ sơ khách hàng đầy đủ.

Kafka event chỉ chứa ID và metadata cần thiết.

---

# 14. Consumer idempotency

Mọi Kafka consumer phải:

1. Validate event schema.
2. Kiểm tra `integration.event_inbox`.
3. Nếu `(event_id, consumer_name)` đã xử lý thành công, bỏ qua.
4. Nếu chưa xử lý:

   * tạo inbox record;
   * thực hiện business transaction;
   * cập nhật inbox thành completed.
5. Chỉ commit Kafka offset sau khi transaction thành công.

Consumer phải chịu được việc nhận lại cùng event.

Không giả định exactly-once ở cấp business.

---

# 15. Document processing pipeline

Document Worker nhận:

```text
document.processing.requested
```

Pipeline:

```text
VALIDATE_UPLOAD
    ↓
SECURITY_SCAN
    ↓
PERSIST_ORIGINAL
    ↓
OCR
    ↓
CLASSIFICATION
    ↓
FIELD_EXTRACTION
    ↓
NORMALIZATION
    ↓
FIELD_VALIDATION
    ↓
PAGE_GENERATION
    ↓
CHUNKING
    ↓
EMBEDDING
    ↓
MARK_READY
```

Mỗi bước phải:

* Cập nhật `background_job_step`.
* Cập nhật tiến độ.
* Có status.
* Có attempt count.
* Có thời gian bắt đầu và kết thúc.
* Có error code.
* Có thể chạy lại idempotently.
* Không ghi đè dữ liệu đã xác minh thủ công.
* Lưu provider/model version.

Kết quả:

* File gốc trong MinIO.
* OCR JSON trong MinIO hoặc metadata phù hợp.
* Page records trong PostgreSQL.
* Extracted fields trong PostgreSQL.
* Chunks và embeddings trong PostgreSQL.
* Document status thành READY hoặc NEEDS_HUMAN_REVIEW.

Nếu phân loại có confidence thấp:

```text
NEEDS_HUMAN_REVIEW
```

Không tự kết luận tài liệu giả.

Chỉ được tạo issue:

```text
POSSIBLE_TAMPERING
LOW_OCR_CONFIDENCE
INCONSISTENT_FIELD
MISSING_PAGE
EXPIRED_DOCUMENT
```

---

# 16. Tiến độ và notification flow

Worker không gửi trực tiếp SSE.

Worker thực hiện:

1. Cập nhật PostgreSQL job state.
2. Ghi job event.
3. Ghi notification event vào Outbox.
4. Outbox Publisher publish lên Kafka.
5. Notification Consumer nhận event.
6. Notification Consumer:

   * tạo notification nếu cần;
   * publish tín hiệu ngắn vào Redis Pub/Sub.
7. FastAPI SSE instance nhận Redis message.
8. FastAPI gửi SSE cho frontend.

Redis message chỉ chứa:

```json
{
  "job_id": "uuid",
  "status": "RUNNING",
  "progress_percent": 60,
  "current_step": "FIELD_EXTRACTION"
}
```

PostgreSQL vẫn là nguồn trạng thái chính thức.

Nếu SSE reconnect, frontend dùng:

```http
GET /api/v1/jobs/{job_id}
GET /api/v1/jobs/{job_id}/events
```

SSE phải hỗ trợ `Last-Event-ID`.

---

# 17. Luồng phân tích khoản vay

Frontend gọi:

```http
POST /api/v1/loan-applications/{loan_application_id}/analyses
```

Backend:

1. Xác thực.
2. Kiểm tra `loan:analyze`.
3. Kiểm tra quyền loan application.
4. Kiểm tra trạng thái hồ sơ.
5. Tạo `ai.analysis_case`.
6. Tạo `integration.background_job`.
7. Tạo `analysis.requested` trong Outbox.
8. Commit.
9. Trả `202 Accepted`.

Analysis Orchestrator nhận event và tạo task graph.

Ví dụ:

```text
DOCUMENT_REVIEW
    ↓
CREDIT_ASSESSMENT

DOCUMENT_REVIEW
    ↓
POLICY_CHECK

CREDIT_ASSESSMENT + POLICY_CHECK
    ↓
VALIDATION
    ↓
SYNTHESIS
    ↓
REPORT_GENERATION
```

Không chạy Credit Agent trước khi dữ liệu cần thiết từ tài liệu đã sẵn sàng.

---

# 18. Context Router

Context Router nhận:

* Nhân viên hiện tại.
* Conversation.
* Active customer.
* Active loan application.
* User message.
* Attachment IDs.

Output có schema:

```json
{
  "customer_id": "uuid-or-null",
  "loan_application_id": "uuid-or-null",
  "intent": "ASSESS_REPAYMENT_CAPACITY",
  "normalized_question": "...",
  "context_status": "SUFFICIENT",
  "complexity_level": 4,
  "route_type": "ORCHESTRATED",
  "missing_context": [],
  "required_agents": [
    "DOCUMENT",
    "CREDIT",
    "LEGAL_COMPLIANCE"
  ]
}
```

Độ phức tạp:

```text
1 = thiếu context
2 = direct tool hoặc query đơn giản
3 = một expert domain
4 = nhiều domain cần orchestration
```

Authorization phải chạy trước semantic routing.

LLM không được quyết định quyền truy cập.

---

# 19. Agent contracts

Mọi agent phải có input và output Pydantic schema.

Base output:

```json
{
  "agent_name": "CREDIT",
  "task_id": "uuid",
  "conclusion": "...",
  "findings": [],
  "calculations": [],
  "evidence_references": [],
  "policy_references": [],
  "assumptions": [],
  "missing_information": [],
  "contradictions": [],
  "risk_flags": [],
  "limitations": [],
  "recommended_action": "...",
  "confidence": 0.84
}
```

Không chấp nhận output text tự do làm kết quả chính thức.

Text tự do chỉ là phần diễn giải.

Structured output mới được ghi vào database.

---

# 20. Document Agent

Document Agent dùng:

* Document metadata.
* Extracted fields.
* Human verification status.
* Checklist.
* Customer master data.

Document Agent tạo:

* Tài liệu thiếu.
* Tài liệu hết hạn.
* Trường chưa xác minh.
* Mâu thuẫn dữ liệu.
* Finding có evidence.
* Yêu cầu human review.

Không được:

* Tự kết luận hồ sơ giả.
* Tự thay đổi extracted field.
* Tự xác minh trường dữ liệu.
* Tự bỏ qua tài liệu bắt buộc.

---

# 21. Credit Agent

Credit Agent dùng:

* Declared income.
* Verified income.
* Accepted income.
* Existing obligations.
* Loan parameters.
* Transaction summaries.
* Calculation records.
* Collateral information.

Credit Agent không tự tính bằng natural language.

Mọi phép tính phải qua `CalculationService`.

Credit Agent tạo:

* Positive factors.
* Risk factors.
* Stress findings.
* Missing data.
* Financial interpretation.
* Recommendation hỗ trợ quyết định.

Không tạo `loan_decision`.

---

# 22. Legal/Compliance Agent

Legal/Compliance Agent dùng:

* Customer type.
* Loan product.
* Loan purpose.
* Collateral type.
* Effective date.
* Policy version.
* Policy clauses.
* Checklist rules.

Output:

```text
PASS
FAIL
CONDITIONAL
INSUFFICIENT_DATA
NOT_APPLICABLE
```

Mỗi policy check phải có:

* Policy ID.
* Policy version ID.
* Clause ID.
* Clause number.
* Effective date.
* Actual value.
* Required value.
* Explanation.

Không sử dụng kiến thức pháp lý từ model nếu không có nguồn policy được phê duyệt.

---

# 23. Calculation Service

Calculation Service phải deterministic.

Sử dụng `Decimal`.

Không sử dụng float cho tiền.

Hỗ trợ tối thiểu:

* Average verified income.
* Income volatility.
* Existing monthly obligations.
* Monthly payment theo dư nợ giảm dần.
* Monthly payment theo annuity nếu sản phẩm cần.
* DTI.
* DSCR.
* LTV.
* Net disposable income.
* Stress interest rate.
* Stress DTI.

Mỗi phép tính phải lưu:

* Calculation type.
* Version.
* Input values.
* Formula.
* Result.
* Unit.
* Source references.
* Calculated time.

Không hard-code policy threshold trong calculator.

Calculator chỉ tính.

Policy service chịu trách nhiệm so sánh với threshold.

---

# 24. Validator

Validator chạy sau expert agents.

Deterministic validation:

* Calculation ID tồn tại.
* Calculation input có source.
* Evidence thuộc đúng customer/case.
* Policy version đúng ngày hiệu lực.
* Policy clause tồn tại.
* Finding có citation.
* Không sử dụng document version đã bị thay thế mà không ghi rõ.
* Không có numeric contradiction chưa được nêu.
* Required task đã hoàn thành.

Output:

```json
{
  "validation_status": "APPROVED",
  "citation_coverage": 0.95,
  "unsupported_claims": [],
  "calculation_errors": [],
  "policy_conflicts": [],
  "agent_contradictions": [],
  "tasks_to_retry": [],
  "approved_for_synthesis": true
}
```

Không gọi validator là công cụ bảo đảm tuyệt đối không hallucination.

Nếu thiếu evidence:

```text
INSUFFICIENT_EVIDENCE
```

---

# 25. Report generation

Chỉ sinh báo cáo chính thức khi:

```text
approved_for_synthesis = true
```

Hoặc sinh báo cáo nháp được đánh dấu rõ:

```text
INCOMPLETE
```

Report JSON là nguồn chính.

PDF là derived artifact.

Các section:

```text
EXECUTIVE_SUMMARY
LOAN_REQUEST
CUSTOMER_PROFILE
DOCUMENT_STATUS
FINANCIAL_ANALYSIS
POLICY_CHECK
POSITIVE_FACTORS
KEY_RISKS
CONTRADICTIONS
MISSING_INFORMATION
REQUIRED_CONDITIONS
ALTERNATIVE_OPTIONS
LIMITATIONS
HUMAN_DECISION_NOTICE
```

Mỗi claim phải được lưu riêng và liên kết evidence.

AI report không được tự ghi:

```text
APPROVED
REJECTED
```

vào bảng quyết định.

---

# 26. Human decision flow

Nhân viên có quyền `loan:approve` có thể tạo quyết định qua API riêng.

Backend phải:

1. Kiểm tra token.
2. Kiểm tra quyền `loan:approve`.
3. Kiểm tra scope.
4. Kiểm tra trạng thái loan application.
5. Ghi decision maker.
6. Ghi thời điểm.
7. Ghi rationale.
8. Ghi điều kiện.
9. Ghi audit event.
10. Sử dụng idempotency key.

Không cho worker, agent hoặc service account AI gọi thao tác này.

---

# 27. REST API groups

Base URL:

```text
/api/v1
```

## Health

```http
GET /health/live
GET /health/ready
```

## Current employee

```http
GET /api/v1/me
```

## Customers

```http
GET /api/v1/customers
GET /api/v1/customers/{customer_id}
GET /api/v1/customers/{customer_id}/overview
GET /api/v1/customers/{customer_id}/accounts
GET /api/v1/customers/{customer_id}/transactions
GET /api/v1/customers/{customer_id}/transaction-summary
GET /api/v1/customers/{customer_id}/documents
GET /api/v1/customers/{customer_id}/loan-applications
```

## Documents

```http
POST /api/v1/documents/uploads
POST /api/v1/documents/uploads/{upload_id}/complete

GET /api/v1/documents/{document_id}
GET /api/v1/documents/{document_id}/versions
GET /api/v1/document-versions/{document_version_id}
GET /api/v1/document-versions/{document_version_id}/processing
GET /api/v1/document-versions/{document_version_id}/fields
GET /api/v1/document-versions/{document_version_id}/download-url
GET /api/v1/document-versions/{document_version_id}/pages/{page_number}/preview-url

PATCH /api/v1/document-fields/{field_id}/verification
```

## Loan applications

```http
POST /api/v1/loan-applications
GET /api/v1/loan-applications/{loan_application_id}
PATCH /api/v1/loan-applications/{loan_application_id}

POST /api/v1/loan-applications/{loan_application_id}/parties
POST /api/v1/loan-applications/{loan_application_id}/documents/{document_id}

GET /api/v1/loan-applications/{loan_application_id}/checklist
GET /api/v1/loan-applications/{loan_application_id}/calculations
GET /api/v1/loan-applications/{loan_application_id}/policy-checks

POST /api/v1/loan-applications/{loan_application_id}/analyses
GET /api/v1/loan-applications/{loan_application_id}/analyses

POST /api/v1/loan-applications/{loan_application_id}/submit
POST /api/v1/loan-applications/{loan_application_id}/decisions
```

Decision endpoint chỉ dành cho nhân viên có thẩm quyền.

## Conversations

```http
POST /api/v1/conversations
GET /api/v1/conversations/{conversation_id}
GET /api/v1/conversations/{conversation_id}/messages
POST /api/v1/conversations/{conversation_id}/messages
```

## Analysis

```http
GET /api/v1/analysis-cases/{analysis_case_id}
GET /api/v1/analysis-cases/{analysis_case_id}/tasks
GET /api/v1/analysis-cases/{analysis_case_id}/findings
GET /api/v1/analysis-cases/{analysis_case_id}/events
POST /api/v1/analysis-cases/{analysis_case_id}/retry
```

## Findings

```http
GET /api/v1/findings/{finding_id}
GET /api/v1/findings/{finding_id}/evidence
```

## Reports

```http
POST /api/v1/analysis-cases/{analysis_case_id}/reports
GET /api/v1/reports/{report_id}
GET /api/v1/reports/{report_id}/claims
GET /api/v1/reports/{report_id}/download-url
PATCH /api/v1/reports/{report_id}/review
```

## Jobs

```http
GET /api/v1/jobs/{job_id}
GET /api/v1/jobs/{job_id}/steps
GET /api/v1/jobs/{job_id}/events
```

## Notifications

```http
GET /api/v1/notifications
PATCH /api/v1/notifications/{notification_id}/read
```

## Policy

```http
GET /api/v1/policies
GET /api/v1/policies/search
GET /api/v1/policy-clauses/{clause_id}
```

## Audit

```http
GET /api/v1/audit-events
```

Chỉ auditor hoặc admin.

---

# 28. API response conventions

Tiền phải serialize thành string:

```json
{
  "amount": "700000000.0000",
  "currency": "VND"
}
```

Không trả tiền bằng binary float.

Collection response:

```json
{
  "items": [],
  "meta": {
    "page": 1,
    "page_size": 20,
    "total": 0
  }
}
```

Error response:

```json
{
  "error": {
    "code": "DOCUMENT_NOT_READY",
    "message": "Tài liệu chưa hoàn tất xử lý.",
    "details": {},
    "trace_id": "uuid"
  }
}
```

Mọi response có:

```text
X-Request-ID
```

---

# 29. Idempotency

Bắt buộc với:

* Create upload.
* Complete upload.
* Create loan application.
* Request analysis.
* Generate report.
* Submit loan.
* Create loan decision.

Header:

```http
Idempotency-Key: <uuid>
```

Quy tắc:

* Cùng key, cùng actor, cùng operation và cùng request: trả kết quả cũ.
* Cùng key nhưng request khác: trả `409`.
* Không reuse key giữa actor khác nhau.

---

# 30. MinIO integration

Backend chỉ sử dụng service account được cấp.

Không dùng root credential.

Storage adapter phải hỗ trợ:

```text
create_presigned_put
create_presigned_get
stat_object
get_object
put_object
copy_object
remove_object
```

Object key phải tuân thủ contract infra.

Không dùng filename người dùng làm object key.

Không đưa PII vào object key.

Presigned URL:

* Hết hạn ngắn.
* Chỉ cấp sau authorization.
* Audit việc tạo download URL.
* Không log toàn bộ URL có chữ ký.

---

# 31. Redis usage

Redis chỉ dùng cho:

* Cache.
* Distributed lock.
* JWKS cache.
* Rate limit.
* SSE Pub/Sub.
* Temporary lookup.

Không lưu duy nhất trong Redis:

* Job status.
* OCR result.
* Agent finding.
* Report.
* Loan decision.
* Audit event.

Distributed lock phải có:

* TTL.
* Owner token.
* Lua safe release.

---

# 32. Logging

Application log dùng JSON một dòng.

Các trường:

```text
timestamp
level
service
environment
event
message
trace_id
span_id
request_id
correlation_id
job_id
resource_type
resource_id
duration_ms
status
error_code
error_message_safe
```

Không log:

* Access token.
* Refresh token.
* Password.
* API key.
* MinIO secret.
* Kafka password.
* Database password.
* CCCD đầy đủ.
* Số tài khoản đầy đủ.
* Toàn bộ tài liệu.
* Toàn bộ prompt runtime chứa PII.
* Private chain-of-thought.

---

# 33. Audit

Audit trả lời:

* Ai làm?
* Làm gì?
* Với tài nguyên nào?
* Khi nào?
* Thành công hay thất bại?
* Liên quan khách hàng hoặc khoản vay nào?

Các hành động cần audit:

```text
CUSTOMER_VIEWED
TRANSACTIONS_VIEWED
DOCUMENT_UPLOAD_CREATED
DOCUMENT_UPLOADED
DOCUMENT_DOWNLOADED
DOCUMENT_FIELD_CORRECTED
ANALYSIS_REQUESTED
ANALYSIS_RETRIED
FINDING_VIEWED
REPORT_GENERATED
REPORT_REVIEWED
LOAN_SUBMITTED
LOAN_DECISION_CREATED
```

Không lưu full payload nhạy cảm vào audit metadata.

---

# 34. AI execution record

Phải lưu:

* Agent type.
* Model provider.
* Model name.
* Model version.
* Prompt version.
* Prompt hash.
* Input references.
* Input hash.
* Output hash.
* Tool executions.
* Token usage.
* Duration.
* Error code.
* Correlation ID.
* Finding IDs.

Không lưu private chain-of-thought.

Prompt file đặt tên:

```text
system-prompt.v1.md
system-prompt.v2.md
```

Không dùng:

```text
final-prompt.md
new-prompt.md
latest-prompt.md
```

---

# 35. Testing

## Unit tests

Bắt buộc có:

* JWT validation.
* Permission mapping.
* Customer access.
* RLS context.
* Money serialization.
* Object key generation.
* Checksum validation.
* Outbox retry.
* Inbox deduplication.
* DTI calculation.
* Payment calculation.
* Income average.
* Policy effective-date selection.
* Context routing.
* Evidence ownership.
* State transition.
* Idempotency.

## Integration tests

Bắt buộc có:

* PostgreSQL connection.
* Customer query.
* Transaction summary.
* Presigned upload.
* Upload completion.
* Outbox publish.
* Kafka consume.
* Document pipeline với mock OCR.
* Analysis orchestration với mock LLM.
* SSE reconnect.
* Policy retrieval.
* Report creation.
* Authorization deny.
* Audit creation.
* Redis Pub/Sub.
* MinIO read/write.

## Contract tests

Kiểm tra:

* Endpoint tồn tại.
* Request schema.
* Response schema.
* Error schema.
* Decimal serialize string.
* Pagination.
* SSE event.
* Kafka event envelope.
* Topic mapping.
* MinIO object-key format.

Test không phụ thuộc LLM hoặc OCR thật.

Dùng mock provider.

---

# 36. Health và readiness

## Live

```http
GET /health/live
```

Chỉ kiểm tra process đang chạy.

## Ready

```http
GET /health/ready
```

Kiểm tra:

* PostgreSQL.
* Kafka.
* Redis.
* MinIO.
* Keycloak JWKS.

OCR và LLM có thể được đánh dấu degraded nếu không cấu hình, nhưng chức năng phụ thuộc chúng phải trả lỗi rõ ràng.

Response:

```json
{
  "status": "ready",
  "dependencies": {
    "postgres": "up",
    "kafka": "up",
    "redis": "up",
    "minio": "up",
    "keycloak": "up",
    "ocr": "mock",
    "llm": "mock"
  }
}
```

---

# 37. Windows execution

Môi trường người dùng là Windows.

Ưu tiên:

* Docker Desktop.
* PowerShell.
* Đường dẫn Windows.
* Không yêu cầu macOS.
* Không yêu cầu người dùng chạy shell script Linux trực tiếp.

Tạo các lệnh PowerShell hoặc Makefile tương đương:

```text
backend-install
backend-run
backend-test
backend-lint
backend-worker-document
backend-worker-analysis
backend-worker-report
backend-outbox-publisher
backend-consumer-notification
```

Ví dụ chạy local:

```powershell
cd D:\dushdask\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Không hard-code đường dẫn dự án trong code.

---

# 38. Security requirements

Bắt buộc:

1. Không hard-code secret.
2. Không commit `.env.local`.
3. JWT phải kiểm tra issuer và audience.
4. Không sử dụng admin credential ở runtime.
5. Không đưa token vào log.
6. Không gửi toàn bộ hồ sơ vào LLM nếu không cần.
7. RAG phải lọc authorization scope trước.
8. Presigned URL chỉ tạo sau permission check.
9. Không lưu PII trong Kafka.
10. Không lưu PII trong MinIO object key.
11. Không dùng float cho tiền.
12. Không cho agent ghi loan decision.
13. Không lưu chain-of-thought.
14. Không cho worker dùng database role có `BYPASSRLS`.
15. Không để CORS wildcard trong production.
16. Validate MIME bằng nội dung.
17. Giới hạn kích thước upload.
18. Rate limit các endpoint nhạy cảm.
19. Mọi download tài liệu phải audit.
20. Mọi correction OCR phải version và audit.

---

# 39. Anti-patterns bị cấm

Không được:

```text
Đặt business logic trong router.

Cho LLM chạy SQL tùy ý.

Cho frontend kết nối Kafka.

Cho frontend giữ MinIO credential.

Publish Kafka trực tiếp sau database commit mà không dùng Outbox.

Dùng Redis làm nguồn sự thật của job.

Lưu PDF trong PostgreSQL.

Đưa PDF vào Kafka.

Dùng filename làm object key.

Dùng float cho tiền.

Ghi đè OCR value khi nhân viên sửa.

Chỉ lưu báo cáo cuối mà không lưu finding và evidence.

Lưu chain-of-thought.

Cho AI tự động phê duyệt.

Dùng một database session không thiết lập RLS context.

Commit Kafka offset trước khi database transaction thành công.

Bỏ qua duplicate event.

Tắt authorization để test dễ hơn.
```

---

# 40. Definition of Done

Chỉ coi backend hoàn thành khi:

1. Agent đã đọc cả hai tài liệu infra và backend.
2. Backend khởi động được.
3. OpenAPI tải được.
4. Health endpoint hoạt động.
5. Readiness kiểm tra dependency.
6. JWT hợp lệ được chấp nhận.
7. JWT sai issuer hoặc audience bị từ chối.
8. Resource authorization hoạt động.
9. RLS context được thiết lập.
10. Customer query hoạt động.
11. Transaction summary hoạt động.
12. Presigned upload hoạt động.
13. Upload completion tạo background job và Outbox.
14. Outbox Publisher publish Kafka.
15. Consumer chống duplicate bằng Inbox.
16. Document pipeline chạy được với mock OCR.
17. Embedding pipeline chạy được với mock provider.
18. Analysis orchestration tạo task graph.
19. Calculation Service dùng Decimal.
20. Policy retrieval lọc đúng version.
21. Validator kiểm tra evidence.
22. Report claim liên kết evidence.
23. SSE gửi progress.
24. SSE reconnect lấy lại event.
25. Audit event được tạo.
26. Application log không lộ secret.
27. Unit test pass.
28. Integration test pass.
29. Contract test pass.
30. Ruff pass.
31. mypy pass hoặc có exception được giải thích.
32. Không có secret trong Git.
33. Không có dữ liệu người thật.
34. Không có endpoint AI tự động phê duyệt.
35. Không có private chain-of-thought được lưu.
36. Các tên schema, table, topic, bucket và environment variable khớp infrastructure.
37. Backend Dockerfile build thành công.
38. Worker process chạy được.
39. Không process nào restart loop.
40. Báo cáo cuối nêu rõ những kiểm tra đã thực sự chạy.

---

# 41. Quy trình coding agent phải thực hiện

1. Đọc `infra\intructions.md`.
2. Đọc file backend này.
3. Kiểm tra repository.
4. Kiểm tra contract thực tế của infrastructure.
5. Liệt kê module đã có.
6. Lập kế hoạch ngắn.
7. Tạo cấu trúc backend.
8. Tạo configuration.
9. Tạo database session và models mapping.
10. Tạo authentication.
11. Tạo authorization.
12. Tạo repository layer.
13. Tạo service layer.
14. Tạo REST API.
15. Tạo MinIO adapter.
16. Tạo Redis adapter.
17. Tạo Kafka producer và consumer.
18. Tạo Outbox Publisher.
19. Tạo Inbox deduplication.
20. Tạo background job API.
21. Tạo document pipeline.
22. Tạo calculation service.
23. Tạo policy retrieval.
24. Tạo agent contracts.
25. Tạo analysis orchestration.
26. Tạo validator.
27. Tạo report generation.
28. Tạo SSE.
29. Tạo logging.
30. Tạo audit.
31. Tạo unit tests.
32. Tạo integration tests.
33. Tạo contract tests.
34. Chạy backend.
35. Chạy worker.
36. Chạy test.
37. Đọc lỗi.
38. Sửa lỗi.
39. Chạy lại.
40. Báo cáo kết quả trung thực.

Không dừng lại ở việc chỉ tạo skeleton.

Không cần chờ người dùng xác nhận từng giai đoạn.

Hãy trực tiếp triển khai trong repository theo phạm vi đã quy định.
