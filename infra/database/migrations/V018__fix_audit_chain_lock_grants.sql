-- Chuỗi hash audit (audit_repository.append) khoá dòng cuối bằng
-- SELECT ... FOR UPDATE; PostgreSQL yêu cầu quyền UPDATE trên bảng cho mọi
-- mệnh đề khoá dòng, kể cả khi ứng dụng không bao giờ UPDATE nội dung.
GRANT UPDATE ON audit.audit_event TO bank_app;
GRANT SELECT, UPDATE ON audit.audit_event TO bank_worker;
