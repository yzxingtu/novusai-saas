"""
Codegen Service 回归测试 / Codegen service regression tests.

测试 GenerateOutput 结构、duplicate config_json 同步、restore_version 顶层同步、
模板局部渲染失败时不写盘
"""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.codegen.file_writer import WriteResult
from app.codegen.generator import GenerateResult, GeneratedFile
from app.services.system.codegen_service import CodegenService, GenerateOutput


def test_generate_output_structure() -> None:
    """generate 返回 GenerateOutput，含 result、config_id、resource、module、table_name."""
    output = GenerateOutput(
        result=WriteResult(success=True),
        config_id=42,
        resource="test_item",
        module="system",
        table_name="test_items",
    )

    assert output.resource == "test_item"
    assert output.module == "system"
    assert output.table_name == "test_items"
    assert output.config_id == 42
    assert output.result.success is True


@pytest.mark.anyio
async def test_partial_render_failure_no_disk_write(tmp_path: Path) -> None:
    """模板局部渲染失败时禁止落盘，无 manifest 半成品."""
    config = {
        "module": "system",
        "resource": "partial_fail",
        "display_name": "Partial",
        "display_name_en": "Partial",
        "model": {"base_class": "TenantModel"},
        "fields": [{"name": "title", "type": "String(100)", "column": True, "form": "input"}],
        "endpoints": [{"scope": "admin", "data_mode": "tenant_only"}],
    }

    def mock_generate(*args, **kwargs):
        return GenerateResult(
            files=[
                GeneratedFile(
                    path="backend/app/models/system/partial_fail.py",
                    content="# would write",
                    action="create",
                )
            ],
            errors=["model: intentional render error"],
        )

    with patch("app.services.system.codegen_service.CodeGenerator") as MockGen:
        MockGen.return_value.generate = mock_generate
        svc = CodegenService(db=None)
        output = await svc.generate(config, force=True, project_root=tmp_path)

    assert output.result.success is False
    assert "intentional render error" in " ".join(output.result.errors)
    target = tmp_path / "backend" / "app" / "models" / "system" / "partial_fail.py"
    assert not target.exists(), "partial render failure must not write any file"
    manifest_path = tmp_path / "codegen_manifest.json"
    if manifest_path.exists():
        entries = json.loads(manifest_path.read_text()).get("entries", [])
        for e in entries:
            assert e.get("resource") != "partial_fail", "must not add manifest entry on render failure"


@pytest.mark.anyio
async def test_before_create_syncs_top_level_fields_from_config_json() -> None:
    """create 前统一以 config_json 同步顶层字段."""
    svc = CodegenService.create_standalone()
    data = {
        "name": "stale-name",
        "resource": "stale_resource",
        "module": "system",
        "display_name": "旧标题",
        "display_name_en": "Old Title",
        "config_json": {
            "name": "Category Builder",
            "resource": "category",
            "module": "business",
            "display_name": "分类",
            "display_name_en": "Category",
            "model": {"base_class": "BaseModel"},
            "fields": [{"name": "title", "type": "String(100)", "column": True, "form": "input"}],
            "endpoints": [{"scope": "admin", "data_mode": "independent"}],
        },
    }

    await svc._before_create(data)

    assert data["name"] == "Category Builder"
    assert data["resource"] == "category"
    assert data["module"] == "business"
    assert data["display_name"] == "分类"
    assert data["display_name_en"] == "Category"
    assert data["config_hash"]


@pytest.mark.anyio
async def test_before_update_pushes_top_level_changes_back_into_config_json() -> None:
    """仅更新顶层字段时，也要反写回 config_json，避免元数据漂移."""
    svc = CodegenService.create_standalone()
    svc.get_by_id = AsyncMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(
            config_json={
                "name": "Category",
                "resource": "category",
                "module": "system",
                "display_name": "分类",
                "display_name_en": "Category",
                "model": {"base_class": "BaseModel"},
                "fields": [{"name": "title", "type": "String(100)", "column": True, "form": "input"}],
                "endpoints": [{"scope": "admin", "data_mode": "independent"}],
            }
        )
    )
    data = {"display_name": "分类管理"}

    await svc._before_update(1, data)

    assert data["config_json"]["display_name"] == "分类管理"
    assert data["display_name"] == "分类管理"
    assert data["resource"] == "category"
    assert data["config_hash"]


def test_run_auto_migrate_accepts_non_create_table_operations(tmp_path: Path) -> None:
    """add_column/alter_column 等非 create_table 迁移也应判定成功."""
    backend_dir = tmp_path / "backend"
    versions_dir = backend_dir / "migrations" / "versions"
    versions_dir.mkdir(parents=True, exist_ok=True)
    migration_file = versions_dir / "20260319_add_column.py"
    migration_file.write_text(
        '\n'.join(
            [
                'revision = "abc123"',
                'down_revision = "prev123"',
                "",
                "def upgrade():",
                "    op.add_column('categories', sa.Column('code', sa.String(length=20), nullable=True))",
                "",
                "def downgrade():",
                "    op.drop_column('categories', 'code')",
                "",
            ]
        ),
        encoding="utf-8",
    )

    subprocess_results = [
        MagicMock(returncode=0, stdout="", stderr=""),
        MagicMock(returncode=0, stdout=f"Generating {migration_file}\n", stderr=""),
        MagicMock(returncode=0, stdout="", stderr=""),
    ]
    with patch("app.core.database.purge_orphaned_alembic_stamps", MagicMock()):
        with patch("subprocess.run", side_effect=subprocess_results):
            result = CodegenService.run_auto_migrate("category", tmp_path)

    assert result["success"] is True
    assert result["migration_path"] is not None


def test_run_auto_migrate_empty_migration_is_noop_when_table_already_exists(
    tmp_path: Path,
) -> None:
    """空迁移在表已存在时应视为 no-op，而不是误判失败."""
    backend_dir = tmp_path / "backend"
    versions_dir = backend_dir / "migrations" / "versions"
    versions_dir.mkdir(parents=True, exist_ok=True)
    migration_file = versions_dir / "20260319_noop.py"
    migration_file.write_text(
        '\n'.join(
            [
                'revision = "noop123"',
                'down_revision = "prev123"',
                "",
                "def upgrade():",
                "    pass",
                "",
                "def downgrade():",
                "    pass",
                "",
            ]
        ),
        encoding="utf-8",
    )

    subprocess_results = [
        MagicMock(returncode=0, stdout="", stderr=""),
        MagicMock(returncode=0, stdout=f"Generating {migration_file}\n", stderr=""),
    ]
    with patch("app.core.database.purge_orphaned_alembic_stamps", MagicMock()):
        with patch("subprocess.run", side_effect=subprocess_results):
            with patch.object(CodegenService, "_table_exists", return_value=True):
                result = CodegenService.run_auto_migrate("category", tmp_path)

    assert result["success"] is True
    assert result["phase"] == "noop"
    assert result["migration_path"] is None
    assert not migration_file.exists()
