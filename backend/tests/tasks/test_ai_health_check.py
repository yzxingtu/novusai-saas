"""Test type: behavioral
Scope: AI provider health projection and failover health reads.
Mocked dependencies: local fake Redis/DB and monkeypatched probes; no third-party APIs.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from redis.exceptions import RedisError

from app.ai.failover import FailoverService
from app.tasks.ai_health_check import (
    ai_provider_health_check,
    _check_provider_health,
    _provider_needs_responses_tool_probe,
    _send_base_health_probe,
)


def _responses_protocol_config(**extra):
    config = {
        "protocol_capabilities": {
            "primary_wire_api": "responses",
            "allowed_wire_apis": ["responses"],
        },
    }
    config.update(extra)
    return config


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
        result = self._results.pop(0)
        if hasattr(result, "scalars"):
            return result
        return _ScalarResult(result)

    def close(self):
        return None


class _FakeTaskQueryResult:
    def __init__(self, providers):
        self._providers = providers

    def scalars(self):
        return self

    def all(self):
        return list(self._providers)


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
        config=_responses_protocol_config(),
    )
    api_key = SimpleNamespace(decrypt_key=MagicMock(return_value="sk-test"))
    tool_model = SimpleNamespace(
        code="gpt-5.4",
        config={
            "runtime_overrides": {
                "openai_compatible": {
                    "responses": {"reasoning": {"effort": "xhigh"}},
                }
            }
        },
        supports_function_calling=True,
    )
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
    assert payload["primary_wire_api"] == "responses"
    assert payload["base_connectivity_healthy"] is True
    assert payload["tool_calling_healthy"] is False
    assert payload["tool_probe_model"] == "gpt-5.4"
    assert payload["tool_probe_reasoning_effort"] == "xhigh"
    assert payload["tool_probe_error_message"] == "responses tool probe failed"
    assert payload["is_healthy"] is False
    assert payload["error_message"] == "responses tool probe failed"
    history_payload = json.loads(
        next(iter(redis_client.history["ai:provider:10:health_history"]))
    )
    assert history_payload["primary_wire_api"] == "responses"


def test_check_provider_health_skips_responses_tool_probe_when_disabled(
    monkeypatch,
) -> None:
    provider = SimpleNamespace(
        id=12,
        code="provider_2",
        name="响应云",
        type="openai_compatible",
        base_url="https://api.example.com",
        config=_responses_protocol_config(responses_tool_probe_enabled=False),
    )
    api_key = SimpleNamespace(decrypt_key=MagicMock(return_value="sk-test"))
    tool_model = SimpleNamespace(
        code="gpt-5.4",
        config={
            "runtime_overrides": {
                "openai_compatible": {
                    "responses": {"reasoning": {"effort": "xhigh"}},
                }
            }
        },
        supports_function_calling=True,
    )
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
    assert payload["primary_wire_api"] == "responses"
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
        config=_responses_protocol_config(),
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


@pytest.mark.parametrize(
    "config, expected_field",
    [
        (
            {
                "wire_api": "responses",
                "protocol_capabilities": {
                    "primary_wire_api": "responses",
                    "allowed_wire_apis": ["responses"],
                },
            },
            "wire_api",
        ),
        (
            {
                "allow_adapter_cross_protocol_fallback": False,
                "protocol_capabilities": {
                    "primary_wire_api": "responses",
                    "allowed_wire_apis": ["responses"],
                },
            },
            "allow_adapter_cross_protocol_fallback",
        ),
        (
            {
                "protocol_capabilities": {
                    "primary_wire_api": "responses",
                    "allowed_wire_apis": ["responses"],
                    "allowed_cross_protocol_fallbacks": {},
                },
            },
            "allowed_cross_protocol_fallbacks",
        ),
    ],
)
def test_check_provider_health_records_invalid_protocol_config_without_crashing(
    config: dict,
    expected_field: str,
) -> None:
    provider = SimpleNamespace(
        id=14,
        code="provider_bad",
        name="旧协议云",
        type="openai_compatible",
        base_url="https://api.example.com",
        config=config,
    )
    redis_client = _FakeRedis()

    _check_provider_health(
        provider=provider,
        db=_FakeDB(),
        redis_client=redis_client,
    )

    payload = json.loads(redis_client.values["ai:provider:14:health"])
    assert payload["primary_wire_api"] is None
    assert payload["is_healthy"] is False
    assert "Retired provider protocol field" in payload["error_message"]
    assert expected_field in payload["error_message"]


def test_ai_provider_health_check_continues_after_single_provider_error(
    monkeypatch,
) -> None:
    providers = [
        SimpleNamespace(
            id=21,
            code="provider_bad",
            name="旧协议云",
            type="openai_compatible",
            base_url="https://api.example.com",
            config={"wire_api": "responses"},
        ),
        SimpleNamespace(
            id=22,
            code="provider_good",
            name="健康云",
            type="openai_compatible",
            base_url="https://api.example.com",
            config=_responses_protocol_config(),
        ),
    ]
    redis_client = _FakeRedis()
    seen_codes: list[str] = []

    monkeypatch.setattr(
        "app.tasks.ai_health_check.sync_session_factory",
        lambda: _FakeDB(_FakeTaskQueryResult(providers)),
    )
    monkeypatch.setattr(
        "app.tasks.ai_health_check._get_sync_redis",
        lambda: redis_client,
    )

    def _fake_check_provider_health(provider, db, redis):
        _ = (db, redis)
        seen_codes.append(provider.code)
        if provider.code == "provider_bad":
            raise RuntimeError("unexpected provider probe failure")

    monkeypatch.setattr(
        "app.tasks.ai_health_check._check_provider_health",
        _fake_check_provider_health,
    )

    result = ai_provider_health_check.run()

    assert seen_codes == ["provider_bad", "provider_good"]
    assert result == {
        "provider_count": 2,
        "provider_error_count": 1,
        "status": "completed",
    }


def test_provider_needs_responses_tool_probe_honors_false_string_flag() -> None:
    provider = SimpleNamespace(
        config=_responses_protocol_config(responses_tool_probe_enabled="0")
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


@pytest.mark.asyncio
async def test_failover_service_fails_closed_on_invalid_health_json(
    monkeypatch,
) -> None:
    redis = SimpleNamespace(get=AsyncMock(return_value="{not json"))

    async def _fake_get_redis():
        return redis

    monkeypatch.setattr("app.ai.failover.get_redis", _fake_get_redis)

    service = FailoverService(db=MagicMock())

    assert await service.is_provider_healthy(10) is False


@pytest.mark.asyncio
async def test_failover_service_fails_closed_when_redis_unavailable(
    monkeypatch,
) -> None:
    async def _fake_get_redis():
        raise RedisError("redis unavailable")

    monkeypatch.setattr("app.ai.failover.get_redis", _fake_get_redis)

    service = FailoverService(db=MagicMock())

    assert await service.is_provider_healthy(10) is False


@pytest.mark.asyncio
async def test_failover_service_uses_compatible_candidate_when_chain_missing(
    monkeypatch,
) -> None:
    original_model = SimpleNamespace(
        id=9,
        provider_id=10,
        tier="premium",
        fallback_model_id=None,
        is_active=True,
    )
    compatible_candidate = SimpleNamespace(
        id=2,
        name="deepseek-chat",
        provider_id=2,
        input_price_per_1k=0.1,
        context_window=1280000,
        tier=None,
    )

    service = FailoverService(db=MagicMock())
    service._model_repo = SimpleNamespace(
        get_active_with_provider=AsyncMock(return_value=original_model),
        get_by_id=AsyncMock(return_value=original_model),
        list_compatible_chat_models=AsyncMock(return_value=[compatible_candidate]),
    )

    async def _fake_is_provider_healthy(provider_id: int) -> bool:
        return provider_id != 10

    monkeypatch.setattr(service, "is_provider_healthy", _fake_is_provider_healthy)

    fallback = await service.get_fallback_model(
        9,
        needs_fc=True,
        min_context_window=128000,
    )

    assert fallback is compatible_candidate
    service._model_repo.list_compatible_chat_models.assert_awaited_once_with(
        exclude_model_ids=[9],
        needs_vision=False,
        needs_audio=False,
        needs_video=False,
        needs_function_calling=True,
        min_context_window=128000,
    )
