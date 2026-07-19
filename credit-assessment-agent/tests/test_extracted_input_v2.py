import json

from fastapi.testclient import TestClient

from app.main import create_app
from app.orchestration.pipeline import AssessmentPipeline
from app.schemas.input_extracted_bundle import ExtractedCaseBundle


def test_v2_contract_accepts_upstream_text_without_ocr_names(clean_bundle):
    legacy = clean_bundle.model_dump(mode="json")
    bundle = ExtractedCaseBundle.model_validate(legacy)
    payload = bundle.model_dump(mode="json")

    assert payload["schema_version"] == "2.0"
    assert "pages" in payload
    assert "ocr_pages" not in payload
    assert "text" in payload["pages"][0]
    assert "extracted_fields" in payload["pages"][0]
    assert "ocr_text" not in payload["pages"][0]

    client = TestClient(create_app(pipeline=AssessmentPipeline()))
    response = client.post("/v1/assess", json=payload)
    assert response.status_code == 200
    source = response.json()["report"]["banker_view"]["findings"]
    assert source == []


def test_v2_contract_rejects_binary_or_unknown_input(clean_bundle):
    payload = ExtractedCaseBundle.model_validate(
        clean_bundle.model_dump(mode="json")
    ).model_dump(mode="json")
    payload["pdf_bytes"] = "not-allowed"
    client = TestClient(create_app(pipeline=AssessmentPipeline()))
    response = client.post("/v1/assess", json=payload)
    assert response.status_code == 422
