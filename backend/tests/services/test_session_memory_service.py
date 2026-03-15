"""SessionMemoryService 测试 / Test."""

from __future__ import annotations

import pytest

from app.services.ai.session_memory_service import SessionMemoryService


class _FakeRedis:
    def __init__(self):
        self.store: dict[str, str] = {}
        self.ttl: dict[str, int] = {}
        self.scan_keys: list[str] = []

    async def get(self, key: str):
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        self.store[key] = value
        if ex is not None:
            self.ttl[key] = ex
        return True

    async def setex(self, key: str, ttl: int, value: str):
        return await self.set(key, value, ex=ttl)

    async def delete(self, *keys):
        deleted = 0
        for k in keys:
            if k in self.store:
                del self.store[k]
                self.ttl.pop(k, None)
                deleted += 1
        return deleted

    async def scan(self, cursor=0, match: str | None = None, count: int = 100):
        _ = cursor, count
        if match == "mem:sess:1:*:*:*:*:100":
            keys = [k for k in self.store if k.startswith("mem:sess:1:") and k.endswith(":100")]
        else:
            keys = []
        return 0, keys

    async def watch(self, _key: str):
        return True

    async def unwatch(self):
        return True

    def pipeline(self, transaction=True):
        _ = transaction
        return _FakePipeline(self)


class _FakePipeline:
    def __init__(self, redis_obj: _FakeRedis):
        self.redis = redis_obj
        self.key = None
        self.value = None
        self.ex = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def watch(self, key):
        self.key = key
        return True

    async def unwatch(self):
        return True

    def multi(self):
        return True

    async def set(self, key, value, ex=None):
        self.key = key
        self.value = value
        self.ex = ex
        return True

    async def execute(self):
        await self.redis.set(self.key, self.value, ex=self.ex)
        return [True]

    async def reset(self):
        return True


@pytest.mark.asyncio
async def test_session_memory_upsert_and_idempotent(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr("app.services.ai.session_memory_service.get_redis_client", lambda: fake)

    svc = SessionMemoryService(tenant_id=1)
    state = await svc.upsert_state(
        channel="tenant_chat",
        source="ai_chat_page",
        agent_id=10,
        user_id=20,
        conversation_id=100,
        event_id="evt-1",
        delta={
            "preferences": ["以后用中文"],
            "constraints": ["回答不超过200字"],
            "task_states": ["继续当前任务"],
            "verified_facts": ["我是产品经理"],
        },
    )
    assert state["version"] == 1
    assert "以后用中文" in state["preferences"]

    # 同 event_id 幂等，不重复递增版本
    state2 = await svc.upsert_state(
        channel="tenant_chat",
        source="ai_chat_page",
        agent_id=10,
        user_id=20,
        conversation_id=100,
        event_id="evt-1",
        delta={"preferences": ["以后用中文"]},
    )
    assert state2["version"] == 1


@pytest.mark.asyncio
async def test_session_memory_clear_by_conversation(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr("app.services.ai.session_memory_service.get_redis_client", lambda: fake)

    # 准备两条同 conversation key
    fake.store["mem:sess:1:tenant_chat:ai_chat_page:10:20:100"] = "{}"
    fake.store["mem:sess:1:admin_chat:admin_chat:10:1:100"] = "{}"
    fake.store["mem:sess:1:tenant_chat:ai_chat_page:10:20:101"] = "{}"

    svc = SessionMemoryService(tenant_id=1)
    deleted = await svc.clear_conversation_memory(100)
    assert deleted == 2
    assert "mem:sess:1:tenant_chat:ai_chat_page:10:20:101" in fake.store
