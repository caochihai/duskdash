-- Lưu toạ độ OCR mức DÒNG/TỪ để highlight kiểu NotebookLM.
-- Schema cũ chỉ có bbox cho extracted_field; bảng này cho phép highlight
-- một câu trích BẤT KỲ về đúng vùng trên trang tài liệu.
-- bbox lưu toạ độ CHUẨN HOÁ 0..1 (gốc trên-trái): {"x","y","w","h"}.

CREATE TABLE document.document_line (
    id UUID PRIMARY KEY,
    document_version_id UUID NOT NULL REFERENCES document.document_version(id),
    page_number INTEGER NOT NULL,
    line_index INTEGER NOT NULL,
    text_content TEXT NOT NULL,
    bbox JSONB NOT NULL,                       -- {"x":0..1,"y":0..1,"w":0..1,"h":0..1}
    confidence NUMERIC(6,5) NULL,
    words JSONB NOT NULL DEFAULT '[]'::jsonb,  -- [{"text","x","y","w","h","confidence"}]
    ocr_provider VARCHAR(40) NULL,
    ocr_model VARCHAR(80) NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_document_line UNIQUE (document_version_id, page_number, line_index),
    CONSTRAINT ck_document_line_page CHECK (page_number > 0),
    CONSTRAINT ck_document_line_index CHECK (line_index >= 0),
    CONSTRAINT ck_document_line_confidence CHECK (
        confidence IS NULL OR confidence BETWEEN 0 AND 1
    )
);

CREATE INDEX idx_document_line_version_page
    ON document.document_line (document_version_id, page_number, line_index);
