"""
Codegen orchestration regression tests.

覆盖从 controller 下沉到 service parts 的生成/回滚编排，
确保 facade 变薄后，manifest 与配置状态同步仍然稳定。
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.codegen.file_writer import WriteResult
from app.codegen.generator import GeneratedFile
from app.codegen.manifest import ManifestManager
from app.codegen.rollback import RollbackResult
from app.enums.codegen import CodegenConfigStatusEnum
from app.services.system import codegen_service as codegen_service_module
from app.services.system.codegen_service import CodegenService, GenerateOutput


def _seed_manifest_entry(project_root: Path, *, config_id: int, resource: str) -> None:
    manifest = ManifestManager(project_root)
    manifest.add_entry(
        resource=resource,
        module="system",
        config_id=config_id,
        files=[
            GeneratedFile(
                path=f"backend/app/models/system/{resource}.py",
                content="# snapshot\n",
                action="create",
            )
        ],
    )


@pytest.mark.anyio
async def test_generate_with_auto_migrate_updates_manifest_and_status(
    tmp_path: Path,
) -> None:
    """auto_migrate 成功时应回填 migration 文件并把配置状态推进到 applied。"""
    _seed_manifest_entry(tmp_path, config_id=7, resource="article")
    service = CodegenService.create_standalone()
    service.generate = AsyncMock(  # type: ignore[method-assign]
        return_value=GenerateOutput(
            result=WriteResult(
                success=True,
                files_created=["backend/app/models/system/article.py"],
            ),
            config_id=7,
            resource="article",
            module="system",
            table_name="articles",
        )
    )
    service.update = AsyncMock()  # type: ignore[method-assign]

    with patch.object(
        CodegenService,
        "run_auto_migrate",
        return_value={
            "success": True,
            "migration_path": "backend/migrations/versions/20260411_article.py",
        },
    ):
        data = await service.generate_with_auto_migrate(
            {"resource": "article"},
            auto_migrate=True,
            project_root=tmp_path,
        )

    manifest_entry = ManifestManager(tmp_path).get_entry("article")
    assert manifest_entry is not None
    assert (
        manifest_entry.migration_file
        == "backend/migrations/versions/20260411_article.py"
    )
    assert data["success"] is True
    assert data["migration"]["success"] is True
    service.update.assert_awaited_once_with(
        7,
        {
            "status": CodegenConfigStatusEnum.APPLIED.value,
            "last_error": None,
        },
    )


@pytest.mark.anyio
async def test_generate_with_auto_migrate_promotes_error_when_migration_fails(
    tmp_path: Path,
) -> None:
    """auto_migrate 失败时应降回 generated 状态并把失败原因回写到 errors/last_error。"""
    service = CodegenService.create_standalone()
    service.generate = AsyncMock(  # type: ignore[method-assign]
        return_value=GenerateOutput(
            result=WriteResult(success=True),
            config_id=9,
            resource="invoice",
            module="system",
            table_name="invoices",
        )
    )
    service.update = AsyncMock()  # type: ignore[method-assign]

    with patch.object(
        CodegenService,
        "run_auto_migrate",
        return_value={
            "success": False,
            "phase": "post_upgrade",
            "error": "boom",
        },
    ):
        data = await service.generate_with_auto_migrate(
            {"resource": "invoice"},
            auto_migrate=True,
            project_root=tmp_path,
        )

    assert data["success"] is False
    assert data["errors"][-1] == "auto_migrate failed at post_upgrade: boom"
    service.update.assert_awaited_once_with(
        9,
        {
            "status": CodegenConfigStatusEnum.GENERATED.value,
            "last_error": "auto_migrate failed at post_upgrade: boom",
        },
    )


def test_list_manifest_history_uses_manifest_as_read_model(tmp_path: Path) -> None:
    """history 应直接投影 manifest 条目，并支持 resource 过滤。"""
    _seed_manifest_entry(tmp_path, config_id=3, resource="article")
    _seed_manifest_entry(tmp_path, config_id=4, resource="comment")
    service = CodegenService.create_standalone()

    all_items = service.list_manifest_history(project_root=tmp_path)
    comment_items = service.list_manifest_history(
        project_root=tmp_path,
        resource="comment",
    )

    assert {item["resource"] for item in all_items} == {"article", "comment"}
    assert len(comment_items) == 1
    assert comment_items[0]["resource"] == "comment"
    assert comment_items[0]["module"] == "system"
    assert comment_items[0]["config_id"] == 4
    assert comment_items[0]["file_count"] == 1
    assert isinstance(comment_items[0]["generated_at"], str)


def test_get_preset_detail_safe_rejects_path_traversal(monkeypatch) -> None:
    """非法 preset 名称不应触发 loader，也不应穿透到文件系统外。"""
    called = {"value": False}

    def _fake_loader(_name: str):
        called["value"] = True
        return {"name": _name}

    monkeypatch.setattr(
        codegen_service_module,
        "load_codegen_preset",
        _fake_loader,
    )

    assert CodegenService.get_preset_detail_safe("../escape") is None
    assert called["value"] is False


def test_get_preset_detail_safe_loads_known_preset(monkeypatch) -> None:
    """合法 preset 名称应通过安全守卫后再委托 loader。"""
    monkeypatch.setattr(
        codegen_service_module,
        "load_codegen_preset",
        lambda name: {"name": name, "ok": True},
    )

    assert CodegenService.get_preset_detail_safe("simple") == {
        "name": "simple",
        "ok": True,
    }


@pytest.mark.anyio
async def test_rollback_resource_with_cleanup_removes_manifest_and_syncs_status(
    tmp_path: Path,
) -> None:
    """按 resource 回滚成功后应删除 manifest 条目并把配置状态推进到 rolled_back。"""
    _seed_manifest_entry(tmp_path, config_id=7, resource="article")
    service = CodegenService.create_standalone()
    service.get_by_resource = AsyncMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(id=7)
    )
    service.update = AsyncMock()  # type: ignore[method-assign]

    rollback_result = RollbackResult(
        success=True,
        files_deleted=["backend/app/models/system/article.py"],
    )

    with patch(
        "app.services.system.codegen_service_parts.execution_mixin.CodegenRollback"
    ) as rollback_cls:
        rollback_cls.return_value.rollback.return_value = rollback_result
        with patch(
            "app.services.system.codegen_service_parts.execution_mixin.run_rollback_migration_cleanup",
            return_value=True,
        ):
            data = await service.rollback_resource_with_cleanup(
                "article",
                migration_file="backend/migrations/versions/20260411_article.py",
                project_root=tmp_path,
            )

    assert data["success"] is True
    assert data["migration_cleaned"] is True
    assert ManifestManager(tmp_path).get_entry("article") is None
    service.update.assert_awaited_once_with(
        7,
        {
            "status": CodegenConfigStatusEnum.ROLLED_BACK.value,
            "generated_files": None,
            "last_error": None,
        },
    )
