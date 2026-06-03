"""DB session lifecycle regression tests / 数据库会话生命周期回归测试。"""

from __future__ import annotations

import asyncio

import pytest

import app.core.database as database_module
import app.core.deps as deps_module


class _DummySession:
    def __init__(self, *, commit_exc: BaseException | None = None) -> None:
        self.commit_exc = commit_exc
        self.commit_calls = 0
        self.rollback_calls = 0
        self.close_calls = 0
        self._in_transaction = True

    async def commit(self) -> None:
        self.commit_calls += 1
        if self.commit_exc is not None:
            raise self.commit_exc
        self._in_transaction = False

    async def rollback(self) -> None:
        self.rollback_calls += 1
        self._in_transaction = False

    async def close(self) -> None:
        self.close_calls += 1

    def in_transaction(self) -> bool:
        return self._in_transaction


class _DummySessionContext:
    def __init__(self, session: _DummySession) -> None:
        self.session = session

    async def __aenter__(self) -> _DummySession:
        return self.session

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        _ = (exc_type, exc, tb)
        await self.session.close()
        return False


@pytest.mark.asyncio
async def test_dependency_session_rolls_back_cancelled_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _DummySession(commit_exc=asyncio.CancelledError())
    monkeypatch.setattr(
        database_module,
        "async_session_factory",
        lambda: _DummySessionContext(session),
    )

    db_gen = deps_module.get_db()
    yielded = await anext(db_gen)

    assert yielded is session

    with pytest.raises(asyncio.CancelledError):
        await db_gen.asend(None)

    assert session.commit_calls == 1
    assert session.rollback_calls == 1
    assert session.close_calls == 1


@pytest.mark.asyncio
async def test_db_context_rolls_back_cancelled_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _DummySession()
    monkeypatch.setattr(
        database_module,
        "async_session_factory",
        lambda: _DummySessionContext(session),
    )

    with pytest.raises(asyncio.CancelledError):
        async with database_module.get_db_context():
            raise asyncio.CancelledError()

    assert session.commit_calls == 0
    assert session.rollback_calls == 1
    assert session.close_calls == 1
