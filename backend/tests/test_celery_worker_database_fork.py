"""中文: Celery worker fork 后数据库连接池安全测试。

EN: Celery worker database pool safety tests after worker forks.

Test type: structural / behavioral
"""

from __future__ import annotations


def test_dispose_database_engines_after_fork_recreates_pools(monkeypatch) -> None:
    from app.core import database

    calls: list[tuple[str, bool]] = []

    class _SyncEngine:
        def dispose(self, *, close: bool = True) -> None:
            calls.append(("sync", close))

    class _AsyncSyncEngine:
        def dispose(self, *, close: bool = True) -> None:
            calls.append(("async", close))

    class _AsyncEngine:
        sync_engine = _AsyncSyncEngine()

    monkeypatch.setattr(database, "sync_engine", _SyncEngine())
    monkeypatch.setattr(database, "async_engine", _AsyncEngine())

    database.dispose_database_engines_after_fork()

    assert calls == [("sync", False), ("async", False)]


def test_worker_process_init_disposes_inherited_database_pools(monkeypatch) -> None:
    from app import celery_app as celery_module

    calls: list[str] = []

    monkeypatch.setattr(
        "app.core.database.dispose_database_engines_after_fork",
        lambda: calls.append("disposed"),
    )
    monkeypatch.setattr(
        celery_module,
        "get_runtime_identity_tag",
        lambda: "test-runtime",
    )

    celery_module._log_worker_runtime_identity()

    assert calls == ["disposed"]
