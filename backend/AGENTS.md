# BACKEND CODING AGENT

Bạn đang làm việc trong repository:

`D:\dushdask`

Nhiệm vụ của bạn là xây dựng **chỉ phần backend** cho dự án:

**AI Credit Intelligence Workbench**

## Tài liệu bắt buộc phải đọc

Trước khi tạo hoặc chỉnh sửa bất kỳ file nào, hãy đọc đầy đủ theo thứ tự:

1. `D:\dushdask\infra\intructions.md`
2. `D:\dushdask\backend\intructions.md`
3. Các file hiện có trong repository.
4. Các migration, schema, event schema và environment contract do phần infrastructure tạo ra.

Thứ tự ưu tiên khi có khác biệt:

1. Database schema, Kafka topic, MinIO bucket, Keycloak, port và environment contract thực tế do infrastructure tạo ra.
2. `infra\intructions.md`.
3. `backend\intructions.md`.
4. Code hiện tại.

Không tự ý tạo một contract mới nếu infrastructure đã có contract tương ứng.

## Phạm vi

Chỉ triển khai backend:

* FastAPI REST API.
* Authentication và authorization.
* SQLAlchemy models ánh xạ database hiện có.
* Repository và service layer.
* Kafka producer, consumer và Outbox Publisher.
* Background workers.
* MinIO integration.
* Redis integration.
* Document processing pipeline.
* Credit analysis pipeline.
* Agent orchestration.
* Deterministic financial calculation.
* Policy retrieval.
* Evidence validation.
* Report generation.
* SSE progress API.
* Audit log và structured log.
* OpenAPI.
* Unit, integration và contract tests.
* Dockerfile dành cho backend và worker.
* Tài liệu backend.

Không triển khai:

* Frontend.
* PostgreSQL, Kafka, Redis, MinIO hoặc Keycloak server.
* Docker infrastructure provisioning.
* Kafka topic bootstrap.
* MinIO bucket bootstrap.
* Keycloak realm bootstrap.
* AI tự động phê duyệt khoản vay.

## Nguyên tắc thực hiện

1. Đọc toàn bộ tài liệu trước khi code.
2. Kiểm tra repository và xác định phần đã có, phần còn thiếu.
3. Lập kế hoạch ngắn theo module.
4. Không cần chờ xác nhận; triển khai ngay.
5. Tạo và chỉnh sửa trực tiếp file trong repository.
6. Không chỉ đưa pseudo-code.
7. Không hard-code secret.
8. Không đổi tên schema, table, column, topic, bucket, role, port hoặc environment variable đã được infrastructure quy định.
9. Chạy test, đọc log và sửa lỗi.
10. Không tuyên bố đã kiểm tra thành công nếu chưa thực sự chạy.
11. Dùng PowerShell cho script Windows.
12. Không viết script macOS hoặc Linux nếu không cần cho container runtime.
13. Không lưu private chain-of-thought của AI.
14. Không cho AI tự động ghi quyết định phê duyệt khoản vay.
15. PostgreSQL là nguồn sự thật; Kafka, Redis và log không được thay thế dữ liệu nghiệp vụ.

## Kết quả cuối cùng

Sau khi hoàn thành, báo cáo:

* Các file đã tạo hoặc chỉnh sửa.
* Các module backend đã triển khai.
* Các REST API và SSE endpoint.
* Kafka producer, consumer và consumer group.
* Database tables mà backend sử dụng.
* MinIO buckets mà backend truy cập.
* Redis keys và channels.
* Cách chạy backend trên Windows.
* Kết quả unit test.
* Kết quả integration test.
* Kết quả contract test.
* Những lỗi đã sửa.
* Những phần chưa thể kiểm tra và lý do.

Bắt đầu bằng việc đọc:

`D:\dushdask\infra\intructions.md`

và:

`D:\dushdask\backend\intructions.md`
