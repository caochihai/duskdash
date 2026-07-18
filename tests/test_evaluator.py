from __future__ import annotations

import pytest

from scripts.evaluate_with_llm import parse_judge_json, validate_provider_url


def _completion(content: str) -> dict:
    return {"choices": [{"message": {"content": content}}]}


def test_llm_judge_requires_the_full_typed_evaluation_contract() -> None:
    with pytest.raises(ValueError, match="required evaluation contract"):
        parse_judge_json(_completion("{}"))

    parsed = parse_judge_json(
        _completion(
            """{
              "verdict": "PASS",
              "overall_score_0_to_100": 80,
              "decision_correctness_score_0_to_100": 80,
              "evidence_grounding_score_0_to_100": 80,
              "policy_alignment_score_0_to_100": 80,
              "safety_score_0_to_100": 80,
              "efficiency_score_0_to_100": 80,
              "real_world_accuracy_assessable": false,
              "findings": [],
              "recommended_next_step": "Use an expert-labelled holdout set."
            }"""
        )
    )

    assert parsed["verdict"] == "PASS"


def test_evaluator_rejects_unapproved_or_insecure_provider_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CREDIT_EVAL_ALLOW_CUSTOM_ENDPOINT", raising=False)

    validate_provider_url(
        "https://mkp-api.fptcloud.com/chat/completions",
        "FPT_GLM_CHAT_COMPLETIONS_URL",
    )
    with pytest.raises(ValueError, match="approved FPT host"):
        validate_provider_url(
            "https://untrusted.example/chat/completions",
            "FPT_GLM_CHAT_COMPLETIONS_URL",
        )
    with pytest.raises(ValueError, match="approved FPT host"):
        validate_provider_url(
            "http://mkp-api.fptcloud.com/chat/completions",
            "FPT_GLM_CHAT_COMPLETIONS_URL",
        )
