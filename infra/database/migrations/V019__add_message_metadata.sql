-- Metadata trả lời của assistant (highlight_segments, highlight_documents,
-- citations, suggested_questions, missing_documents...) trước đây chỉ nằm
-- trong response của lượt gửi — mở lại phiên chat là mất nút ảnh highlight
-- và trích dẫn. Cột này lưu phần metadata inspectable đó; suy luận nội bộ
-- của model không bao giờ được ghi vào đây.
ALTER TABLE ai.message ADD COLUMN metadata JSONB NULL;

COMMENT ON COLUMN ai.message.metadata IS
    'Metadata inspectable của câu trả lời assistant (citations, highlight, gợi ý); NULL với tin nhắn nhân viên.';
