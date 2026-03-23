"""Plugin operator CLI regression tests. / 插件运维 CLI 回归测试。"""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace

from click.testing import CliRunner


def _install_fake_service(monkeypatch, fake_service_cls) -> None:
    @asynccontextmanager
    async def _fake_db_context():
        yield object()

    monkeypatch.setattr("app.core.database.get_db_context", _fake_db_context)
    monkeypatch.setattr(
        "app.services.system.plugin_service.PluginService",
        fake_service_cls,
    )


def test_plugin_sync_manifest_command_uses_service(monkeypatch) -> None:
    from app.cli import cli

    calls: dict[str, object] = {}

    class _FakeService:
        def __init__(self, db):
            calls["db"] = db

        async def get_by_name(self, name: str):
            calls["plugin_name"] = name
            return SimpleNamespace(id=7, name=name, version="1.0.0")

        async def sync_manifest(self, plugin_id: int):
            calls["sync_plugin_id"] = plugin_id
            return SimpleNamespace(name="workflow-orchestration", version="1.0.0")

    _install_fake_service(monkeypatch, _FakeService)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["plugin", "sync-manifest", "--plugin", "workflow-orchestration"],
    )

    assert result.exit_code == 0
    assert "Manifest synced: workflow-orchestration@1.0.0" in result.output
    assert calls["plugin_name"] == "workflow-orchestration"
    assert calls["sync_plugin_id"] == 7


def test_plugin_activate_license_command_uses_service(monkeypatch) -> None:
    from app.cli import cli

    calls: dict[str, object] = {}

    class _FakeService:
        def __init__(self, db):
            calls["db"] = db

        async def get_by_name(self, name: str):
            return SimpleNamespace(id=8, name=name)

        async def activate_license(self, plugin_id: int, license_key: str):
            calls["activate_args"] = (plugin_id, license_key)

    _install_fake_service(monkeypatch, _FakeService)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "plugin",
            "activate-license",
            "--plugin",
            "workflow-orchestration",
            "--key",
            "NOVUS-test-key",
        ],
    )

    assert result.exit_code == 0
    assert "License activated: workflow-orchestration" in result.output
    assert calls["activate_args"] == (8, "NOVUS-test-key")


def test_plugin_enable_command_uses_service(monkeypatch) -> None:
    from app.cli import cli

    calls: dict[str, object] = {}

    class _FakeService:
        def __init__(self, db):
            calls["db"] = db

        async def get_by_name(self, name: str):
            return SimpleNamespace(id=9, name=name)

        async def enable_plugin(self, plugin_id: int):
            calls["enable_plugin_id"] = plugin_id

    _install_fake_service(monkeypatch, _FakeService)
    init_calls: list[str] = []

    async def _fake_init():
        init_calls.append("init")

    async def _fake_close():
        init_calls.append("close")

    monkeypatch.setattr("app.core.redis.RedisManager.init", _fake_init)
    monkeypatch.setattr("app.core.redis.RedisManager.close", _fake_close)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["plugin", "enable", "--plugin", "workflow-orchestration"],
    )

    assert result.exit_code == 0
    assert "Plugin enabled: workflow-orchestration" in result.output
    assert "restart it or use the admin API enable path" in result.output
    assert calls["enable_plugin_id"] == 9
    assert init_calls == ["init", "close"]


def test_plugin_assign_tenant_command_uses_service(monkeypatch) -> None:
    from app.cli import cli

    calls: dict[str, object] = {}

    class _FakeService:
        def __init__(self, db):
            calls["db"] = db

        async def get_by_name(self, name: str):
            return SimpleNamespace(id=10, name=name)

        async def assign_tenants(self, plugin_id: int, tenant_ids: list[int]):
            calls["assign_args"] = (plugin_id, tenant_ids)
            return len(tenant_ids)

    _install_fake_service(monkeypatch, _FakeService)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "plugin",
            "assign-tenant",
            "--plugin",
            "workflow-orchestration",
            "--tenant-id",
            "11",
            "--tenant-id",
            "12",
        ],
    )

    assert result.exit_code == 0
    assert "Assigned 2 tenant(s): workflow-orchestration" in result.output
    assert calls["assign_args"] == (10, [11, 12])


def test_plugin_operator_command_fails_cleanly_when_plugin_missing(monkeypatch) -> None:
    from app.cli import cli

    class _FakeService:
        def __init__(self, db):
            self.db = db

        async def get_by_name(self, name: str):
            _ = name
            return None

    _install_fake_service(monkeypatch, _FakeService)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["plugin", "enable", "--plugin", "missing-plugin"],
    )

    assert result.exit_code == 1
    assert "Plugin 'missing-plugin' not found" in result.output
