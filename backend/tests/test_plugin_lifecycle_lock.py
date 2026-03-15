"""Regression tests for plugin lifecycle distributed lock safety. / 插件"""

from __future__ import annotations

import pytest

from app.plugins.exceptions import PluginError
from app.plugins.lifecycle import _plugin_lock


class _FakeRedisClient:
    def __init__(self) -> None:
        self._kv: dict[str, str] = {}
        self.eval_calls: list[tuple[str, int, str, str]] = []

    async def set(
        self,
        key: str,
        value: str,
        nx: bool = False,
        ex: int | None = None,
    ) -> bool:
        _ = ex
        if nx and key in self._kv:
            return False
        self._kv[key] = value
        return True

    async def eval(self, script: str, numkeys: int, key: str, token: str) -> int:
        self.eval_calls.append((script, numkeys, key, token))
        if self._kv.get(key) == token:
            del self._kv[key]
            return 1
        return 0


@pytest.mark.asyncio
async def test_plugin_lock_uses_owner_token_on_release(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeRedisClient()
    monkeypatch.setattr('app.core.redis.get_redis_client', lambda: client)

    key = 'plugin:lifecycle:lock:101'
    owner_token = ''

    async with _plugin_lock(101):
        owner_token = client._kv[key]
        assert owner_token

    assert key not in client._kv
    assert client.eval_calls
    _, numkeys, eval_key, eval_token = client.eval_calls[-1]
    assert numkeys == 1
    assert eval_key == key
    assert eval_token == owner_token


@pytest.mark.asyncio
async def test_plugin_lock_does_not_delete_other_owner_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeRedisClient()
    monkeypatch.setattr('app.core.redis.get_redis_client', lambda: client)

    key = 'plugin:lifecycle:lock:202'

    async with _plugin_lock(202):
        # Simulate lock expired and re-acquired by another request
        client._kv[key] = 'other-owner-token'

    assert client._kv.get(key) == 'other-owner-token'


@pytest.mark.asyncio
async def test_plugin_lock_conflict_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeRedisClient()
    key = 'plugin:lifecycle:lock:303'
    client._kv[key] = 'already-held'
    monkeypatch.setattr('app.core.redis.get_redis_client', lambda: client)

    with pytest.raises(PluginError):
        async with _plugin_lock(303):
            pass
