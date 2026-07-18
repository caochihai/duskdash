"""Unit tests for the rule-based account gate."""

from __future__ import annotations

from datetime import datetime, time, timezone

import pytest

from app.auth.login_rules import LoginRuleEngine


class _RuleSettings:
    login_rules_deny_usernames = ""
    login_rules_allow_username_patterns = ""
    login_rules_required_roles = ""
    login_rules_access_window_utc = ""


def test_empty_engine_allows_everyone() -> None:
    engine = LoginRuleEngine()
    verdict = engine.evaluate(username="anyone@example.local", roles=frozenset())
    assert verdict.allowed


def test_deny_list_blocks_username_case_insensitively() -> None:
    engine = LoginRuleEngine(deny_usernames=frozenset({"blocked@example.local"}))
    verdict = engine.evaluate(username="Blocked@Example.local", roles=frozenset({"admin"}))
    assert not verdict.allowed
    assert verdict.rule == "deny_usernames"


def test_allow_patterns_reject_unmatched_usernames() -> None:
    engine = LoginRuleEngine(allow_username_patterns=("*@example.local",))
    assert engine.evaluate(username="ok@example.local", roles=frozenset()).allowed
    verdict = engine.evaluate(username="intruder@evil.test", roles=frozenset())
    assert not verdict.allowed
    assert verdict.rule == "allow_username_patterns"


def test_required_roles_need_at_least_one_match() -> None:
    engine = LoginRuleEngine(required_roles=frozenset({"credit_officer", "admin"}))
    assert engine.evaluate(username="u", roles=frozenset({"admin"})).allowed
    verdict = engine.evaluate(username="u", roles=frozenset({"visitor"}))
    assert not verdict.allowed
    assert verdict.rule == "required_roles"


def test_access_window_blocks_outside_hours() -> None:
    engine = LoginRuleEngine(access_window_utc=(time(8, 0), time(18, 0)))
    inside = datetime(2026, 7, 18, 9, 30, tzinfo=timezone.utc)
    outside = datetime(2026, 7, 18, 22, 0, tzinfo=timezone.utc)
    assert engine.evaluate(username="u", roles=frozenset(), now=inside).allowed
    verdict = engine.evaluate(username="u", roles=frozenset(), now=outside)
    assert not verdict.allowed
    assert verdict.rule == "access_window_utc"


def test_overnight_access_window_wraps_midnight() -> None:
    engine = LoginRuleEngine(access_window_utc=(time(22, 0), time(6, 0)))
    late = datetime(2026, 7, 18, 23, 30, tzinfo=timezone.utc)
    midday = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)
    assert engine.evaluate(username="u", roles=frozenset(), now=late).allowed
    assert not engine.evaluate(username="u", roles=frozenset(), now=midday).allowed


def test_from_settings_parses_csv_and_window() -> None:
    settings = _RuleSettings()
    settings.login_rules_deny_usernames = "a@x.local, B@x.local"
    settings.login_rules_required_roles = "credit_officer,admin"
    settings.login_rules_access_window_utc = "08:00-18:00"
    engine = LoginRuleEngine.from_settings(settings)
    assert engine.deny_usernames == frozenset({"a@x.local", "b@x.local"})
    assert engine.required_roles == frozenset({"credit_officer", "admin"})
    assert engine.access_window_utc == (time(8, 0), time(18, 0))


def test_from_settings_rejects_malformed_window() -> None:
    settings = _RuleSettings()
    settings.login_rules_access_window_utc = "08:00"
    with pytest.raises(ValueError):
        LoginRuleEngine.from_settings(settings)
