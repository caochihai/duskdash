from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.schemas.input_ocr_bundle import OCRBundle


FIXTURES = Path(__file__).parent / "fixtures"


def load_bundle(name: str) -> OCRBundle:
    return OCRBundle.model_validate(json.loads((FIXTURES / name).read_text(encoding="utf-8")))


@pytest.fixture
def clean_bundle() -> OCRBundle:
    return load_bundle("clean_bundle.json")


@pytest.fixture
def borderline_bundle() -> OCRBundle:
    return load_bundle("borderline_bundle.json")


@pytest.fixture
def multi_issue_bundle() -> OCRBundle:
    return load_bundle("multi_issue_bundle.json")


@pytest.fixture
def missing_page_bundle() -> OCRBundle:
    return load_bundle("missing_page_bundle.json")

