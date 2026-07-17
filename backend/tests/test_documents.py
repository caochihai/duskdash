from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from common import config
from documents import pipeline
from documents import extractors, validators
from gateway import db


class DocumentIngestionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db, self.original_uploads = config.GATEWAY_DB, config.UPLOADS_DIR
        config.GATEWAY_DB = Path(self.temp_dir.name) / "gateway.db"
        config.UPLOADS_DIR = Path(self.temp_dir.name) / "uploads"
        config.UPLOADS_DIR.mkdir()
        db.init()
        db.create_case("case_document", {"request": {}, "documents": []})

    def tearDown(self) -> None:
        config.GATEWAY_DB, config.UPLOADS_DIR = self.original_db, self.original_uploads
        self.temp_dir.cleanup()

    def test_ingest_detects_pdf_from_content_and_uses_internal_filename(self) -> None:
        document = pipeline.ingest("case_document", "bctc", "../../report.pdf", b"%PDF-1.4\n")
        self.assertEqual(document["mime_type"], "application/pdf")
        self.assertNotIn("report.pdf", document["storage_path"])
        self.assertTrue(Path(document["storage_path"]).exists())
        self.assertEqual(db.list_documents("case_document")[0]["file_hash"], document["file_hash"])

    def test_ingest_rejects_untrusted_file_type(self) -> None:
        with self.assertRaises(pipeline.DocumentValidationError):
            pipeline.ingest("case_document", "bctc", "payload.exe", b"MZ\x00\x01")

    def test_native_text_pdf_keeps_page_and_bounding_box_provenance(self) -> None:
        import fitz

        source = fitz.open()
        page = source.new_page()
        page.insert_text((72, 72), "Revenue for reporting period 2025 is 20 billion VND.")
        content = source.tobytes()
        source.close()

        document = pipeline.ingest("case_document", "bctc", "statement.pdf", content)
        processed = pipeline.process(document["document_id"])
        self.assertEqual(processed["processing_status"], "completed")
        self.assertGreater(processed["metadata"]["native_text_blocks"], 0)
        with db._conn() as connection:  # noqa: SLF001 - verifies persisted provenance
            fact = connection.execute(
                "SELECT page, bbox_json, evidence_text FROM extracted_facts WHERE document_id=?",
                (document["document_id"],),
            ).fetchone()
        self.assertEqual(fact["page"], 1)
        self.assertTrue(fact["bbox_json"])
        self.assertIn("Revenue", fact["evidence_text"])

    def test_cross_document_conflict_is_flagged_without_overwriting_facts(self) -> None:
        first = pipeline.ingest("case_document", "dkkd", "a.pdf", b"%PDF-1.4\nfirst")
        second = pipeline.ingest("case_document", "dkkd", "b.pdf", b"%PDF-1.4\nsecond")
        block_a = {"text": "Mã số doanh nghiệp: 0101234567", "page": 1, "bbox": [0, 0, 1, 1]}
        block_b = {"text": "Mã số doanh nghiệp: 0109999999", "page": 1, "bbox": [0, 0, 1, 1]}
        db.save_extracted_facts(first["document_id"], extractors.extract("dkkd", [block_a]))
        db.save_extracted_facts(second["document_id"], extractors.extract("dkkd", [block_b]))
        findings = validators.cross_validate("case_document")
        self.assertEqual(findings[0]["key"], "enterprise_id")
        self.assertEqual(len(findings[0]["values"]), 2)

    def test_scanned_pdf_routes_to_ocr_and_preserves_ocr_provenance(self) -> None:
        from unittest.mock import patch
        import fitz

        source = fitz.open()
        source.new_page()  # blank page simulates a scanned PDF without a text layer
        document = pipeline.ingest("case_document", "cccd", "scan.pdf", source.tobytes())
        source.close()
        with patch("documents.pipeline.ocr.extract_image", return_value=[{
            "text": "Số CCCD: 079088001234", "confidence": 0.95, "bbox": [2, 3, 4, 5],
        }]):
            processed = pipeline.process(document["document_id"])
        self.assertEqual(processed["processing_status"], "completed")
        self.assertEqual(processed["metadata"]["ocr_required_pages"], [1])
        facts = db.list_case_facts("case_document")
        self.assertTrue(any(f["key"] == "id_number" for f in facts))


if __name__ == "__main__":
    unittest.main()
