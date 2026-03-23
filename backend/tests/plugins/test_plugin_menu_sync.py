"""Plugin menu permission sync cleanup tests. / 插件菜单权限同步清理测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.rbac.registry import permission_registry


@pytest.fixture(autouse=True)
def _clear_permission_registry():
    permission_registry.clear()
    yield
    permission_registry.clear()


def _make_scalars_result(items: list[object]) -> MagicMock:
    result = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = items
    result.scalars.return_value = scalars
    return result


def _make_rows_result(rows: list[tuple[object, ...]]) -> MagicMock:
    result = MagicMock()
    result.all.return_value = rows
    return result


@pytest.mark.asyncio
async def test_sync_plugin_permissions_disables_stale_plugin_menu_records() -> None:
    from app.enums.rbac import PermissionScope, PermissionType
    from app.models.auth.permission import Permission
    from app.rbac.decorators import PermissionMeta
    from app.rbac.sync import PermissionSyncService

    current_meta = PermissionMeta(
        code="menu:admin.plugin_novusdoc_novusdoc-admin",
        name="novusdoc.novusdoc-admin.title",
        type=PermissionType.MENU,
        scope=PermissionScope.ADMIN,
        resource="menu",
        action="admin.plugin_novusdoc_novusdoc-admin",
        path="/admin/plugins/novusdoc",
        component="NovusDocAdminPage",
        sort_order=50,
    )
    permission_registry.register(current_meta)

    current_db = Permission(
        id=10,
        code=current_meta.code,
        name="old.current.title",
        type="menu",
        scope="admin",
        resource="menu",
        action=current_meta.action,
        path="/admin/plugins/novusdoc",
        component="LegacyCurrentPage",
        sort_order=10,
        hidden=False,
        is_enabled=False,
        is_deleted=False,
    )
    stale_db = Permission(
        id=11,
        code="menu:admin.plugin_novusdoc_novusdoc_admin",
        name="novusdoc.novusdoc_admin.title",
        type="menu",
        scope="admin",
        resource="menu",
        action="admin.plugin_novusdoc_novusdoc_admin",
        path="/admin/plugins/novusdoc",
        component="LegacyAliasPage",
        sort_order=10,
        hidden=False,
        is_enabled=True,
        is_deleted=False,
    )

    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _make_scalars_result([current_db, stale_db]),
            _make_rows_result([(current_db.code, current_db.id), (stale_db.code, stale_db.id)]),
        ],
    )
    db.flush = AsyncMock()
    db.add = MagicMock()

    affected = await PermissionSyncService(db).sync_plugin_permissions("novusdoc")

    assert affected == 2
    assert current_db.name == current_meta.name
    assert current_db.component == "NovusDocAdminPage"
    assert current_db.is_enabled is True
    assert current_db.is_deleted is False
    assert stale_db.is_enabled is False
    assert stale_db.is_deleted is False
    db.add.assert_not_called()
    assert db.flush.await_count >= 1
