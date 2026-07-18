from fastapi.testclient import TestClient

from app.main import create_app
from app.orchestration.pipeline import AssessmentPipeline


def test_health():
    client = TestClient(create_app(pipeline=AssessmentPipeline()))
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_post_and_poll(clean_bundle):
    client = TestClient(create_app(pipeline=AssessmentPipeline()))
    posted = client.post("/v1/assess", json=clean_bundle.model_dump(mode="json"))
    assert posted.status_code == 200
    body = posted.json()
    assert body["report"]["decision_recommendation"] == "APPROVE"

    polled = client.get(f"/v1/assess/{body['job_id']}")
    assert polled.status_code == 200
    assert polled.json() == body["report"]


def test_invalid_input_returns_422():
    client = TestClient(create_app(pipeline=AssessmentPipeline()))
    response = client.post("/v1/assess", json={"case_id": "x"})
    assert response.status_code == 422

