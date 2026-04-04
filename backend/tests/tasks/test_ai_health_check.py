from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.failover import FailoverService
from app.tasks.ai_health_check import (
    _check_provider_health,
    _provider_needs_responses_tool_probe,
    _send_base_health_probe,
)


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeDB:
    def __init__(self, *results):
        self._results = list(results)

    def execute(self, stmt):
        _ = stmt
        return _ScalarResult(self._results.pop(0))


class _FakeRedis:
    def __init__(self):
        self.values: dict[str, str] = {}
        self.history: dict[str, dict[str, float]] = {}

    def get(self, key: str):
        return self.values.get(key)

    def setex(self, key: str, ttl: int, value: str) -> None:
        _ = ttl
        self.values[key] = value

    def zadd(self, key: str, mapping: dict[str, float]) -> None:
        self.history.setdefault(key, {}).update(mapping)

    def zremrangebyscore(self, key: str, min_score: float, max_score: float) -> None:
        _ = (key, min_score, max_score)

    def expire(self, key: str, ttl: int) -> None:
        _ = (key, ttl)


def _healthy_probe(**_kwargs):
    return (True, None)


def _failed_tool_probe(**_kwargs):
    return (False, "responses tool probe failed")


def test_check_provider_health_records_tool_probe_failure(monkeypatch) -> None:
    provider = SimpleNamespace(
        id=10,
        code="provider_1",
        name="响应云",
        type="openai_compatible",
        base_url="https://api.example.com",
        config={"wire_api": "responses"},
    )
    api_key = SimpleNamespace(decrypt_key=MagicMock(return_value="sk-test"))
    tool_model = SimpleNamespace(code="gpt-5.4-xhigh", supports_function_calling=True)
    redis_client = _FakeRedis()

    monkeypatch.setattr(
        "app.tasks.ai_health_check._send_base_health_probe",
        _healthy_probe,
    )
    monkeypatch.setattr(
        "app.tasks.ai_health_check._send_responses_tool_probe",
        _failed_tool_probe,
    )

    _check_provider_health(
        provider=provider,
        db=_FakeDB(api_key, tool_model),
        redis_client=redis_client,
    )

    payload = json.loads(redis_client.values["ai:provider:10:health"])
    assert payload["wire_api"] == "responses"
    assert payload["base_connectivity_healthy"] is True
    assert payload["tool_calling_healthy"] is False
    assert payload["tool_probe_model"] == "gpt-5.4"
    assert payload["tool_probe_reasoning_effort"] == "xhigh"
    assert payload["tool_probe_error_message"] == "responses tool probe failed"
    assert payload["is_healthy"] is False
    assert payload["error_message"] == "responses tool probe failed"


def test_check_provider_health_skips_responses_tool_probe_when_disabled(
    monkeypatch,
) -> None:
    provider = SimpleNamespace(
        id=12,
        code="provider_2",
        name="响应云",
        type="openai_compatible",
        base_url="https://api.example.com",
        config={
            "wire_api": "responses",
            "responses_tool_probe_enabled": False,
        },
    )
    api_key = SimpleNamespace(decrypt_key=MagicMock(return_value="sk-test"))
    tool_model = SimpleNamespace(code="gpt-5.4-xhigh", supports_function_calling=True)
    redis_client = _FakeRedis()
    probe_called = {"tool_probe": 0}

    monkeypatch.setattr(
        "app.tasks.ai_health_check._send_base_health_probe",
        _healthy_probe,
    )

    def _fake_tool_probe(**kwargs):
        _ = kwargs
        probe_called["tool_probe"] += 1
        return (False, "should not be called")

    monkeypatch.setattr(
        "app.tasks.ai_health_check._send_responses_tool_probe",
        _fake_tool_probe,
    )

    _check_provider_health(
        provider=provider,
        db=_FakeDB(api_key, tool_model),
        redis_client=redis_client,
    )

    payload = json.loads(redis_client.values["ai:provider:12:health"])
    assert probe_called["tool_probe"] == 0
    assert payload["wire_api"] == "responses"
    assert payload["base_connectivity_healthy"] is True
    assert payload["tool_probe_model"] == "gpt-5.4"
    assert payload["tool_calling_healthy"] is None
    assert payload["tool_probe_reasoning_effort"] == "xhigh"
    assert payload["is_healthy"] is True
    assert payload["error_message"] is None


def test_check_provider_health_keeps_base_health_when_no_tool_probe_model(
    monkeypatch,
) -> None:
    provider = SimpleNamespace(
        id=13,
        code="provider_3",
        name="基础探测云",
        type="openai_compatible",
        base_url="https://api.example.com",
        config={"wire_api": "responses"},
    )
    api_key = SimpleNamespace(decrypt_key=MagicMock(return_value="sk-test"))
    redis_client = _FakeRedis()
    probe_called = {"tool_probe": 0}

    monkeypatch.setattr(
        "app.tasks.ai_health_check._send_base_health_probe",
        _healthy_probe,
    )

    def _fake_tool_probe(**kwargs):
        _ = kwargs
        probe_called["tool_probe"] += 1
        return (False, "should not be called")

    monkeypatch.setattr(
        "app.tasks.ai_health_check._send_responses_tool_probe",
        _fake_tool_probe,
    )

    _check_provider_health(
        provider=provider,
        db=_FakeDB(api_key, None),
        redis_client=redis_client,
    )

    payload = json.loads(redis_client.values["ai:provider:13:health"])
    assert probe_called["tool_probe"] == 0
    assert payload["base_connectivity_healthy"] is True
    assert payload["tool_probe_model"] is None
    assert payload["tool_calling_healthy"] is None
    assert payload["is_healthy"] is True
    assert payload["error_message"] is None


def test_provider_needs_responses_tool_probe_honors_false_string_flag() -> None:
    provider = SimpleNamespace(
        config={
            "wire_api": "responses",
            "responses_tool_probe_enabled": "0",
        }
    )
    tool_model = SimpleNamespace(supports_function_calling=True)
    assert _provider_needs_responses_tool_probe(provider, tool_model) is False


def test_send_base_health_probe_rejects_non_json_models_payload(monkeypatch) -> None:
    response = SimpleNamespace(
        status_code=200,
        headers={"content-type": "text/html"},
        json=lambda: None,
    )
    monkeypatch.setattr(
        "app.tasks.ai_health_check.httpx.get",
        lambda *_args, **_kwargs: response,
    )

    is_healthy, error_message = _send_base_health_probe(
        api_key="sk-test",
        base_url="https://api.example.com/v1",
    )

    assert is_healthy is False
    assert "non-JSON" in str(error_message)


def test_send_base_health_probe_accepts_models_list_json_shape(monkeypatch) -> None:
    response = SimpleNamespace(
        status_code=200,
        headers={"content-type": "application/json"},
        json=lambda: {"data": [{"id": "gpt-5.4"}]},
    )
    monkeypatch.setattr(
        "app.tasks.ai_health_check.httpx.get",
        lambda *_args, **_kwargs: response,
    )

    is_healthy, error_message = _send_base_health_probe(
        api_key="sk-test",
        base_url="https://api.example.com/v1",
    )

    assert is_healthy is True
    assert error_message is None


@pytest.mark.asyncio
async def test_failover_service_prefers_is_healthy(monkeypatch) -> None:
    redis = SimpleNamespace(
        get=AsyncMock(
            return_value=json.dumps(
                {
                    "is_available": True,
                    "is_healthy": False,
                }
            )
        )
    )

    async def _fake_get_redis():
        return redis

    monkeypatch.setattr("app.ai.failover.get_redis", _fake_get_redis)

    service = FailoverService(db=MagicMock())

    assert await service.is_provider_healthy(10) is False
