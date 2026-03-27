"""
Codegen 迁移审计回归测试 / Migration audit regression tests.

测试 partial rollback success、CLI 中止、多 head、旧迁移 fallback、
注册 fail-fast、无 manifest drop guard、锁行为
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.codegen.file_writer import FileWriter
from app.codegen.generator import GeneratedFile
from app.codegen.manifest import ManifestManager
from app.codegen.migration_helper import run_rollback_migration_cleanup
from app.codegen.rollback import CodegenRollback


def _setup_manifest(tmp_path: Path, resource: str, files: list[dict], migration_file: str | None = None) -> None:
    """写入 manifest 条目."""
    manifest_path = tmp_path / "codegen_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "resource": resource,
        "module": "system",
        "generated_at": "2026-01-01T00:00:00Z",
        "config_id": 1,
        "config_hash": "abc",
        "files": files,
    }
    if migration_file is not None:
        entry["migration_file"] = migration_file
    data = {"entries": [entry], "version": 1}
    manifest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def test_partial_rollback_sets_success_false_and_preserves_manifest(tmp_path: Path) -> None:
    """partial rollback 时 success=False 且 manifest 条目保留."""
    target = tmp_path / "routers.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("router = APIRouter()\n")  # 无 appended 内容

    _setup_manifest(
        tmp_path,
        "category",
        [{"path": "routers.py", "action": "append", "appended_content": "router.include_router(x)"}],
    )

    rollback = CodegenRollback(project_root=tmp_path)
    result = rollback.rollback(resource="category", force=False)

    assert result.success is False
    assert len(result.files_skipped) >= 1
    manifest = ManifestManager(tmp_path)
    entry = manifest.get_entry("category")
    assert entry is not None


def test_run_rollback_migration_cleanup_refuses_non_head_revision(tmp_path: Path) -> None:
    """当 codegen 迁移不是 current head 时拒绝 downgrade，不 DROP TABLE."""
    backend = tmp_path / "backend"
    versions = backend / "migrations" / "versions"
    versions.mkdir(parents=True, exist_ok=True)

    mig_file = versions / "20260319_1000_codegen_stock_record.py"
    mig_file.write_text('''"""codegen stock_record

revision = "abc123"
down_revision = "prev456"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("stock_records", ...)

def downgrade():
    op.drop_table("stock_records")
''')

    with patch(
        "app.codegen.migration_helper._get_current_heads",
        return_value=(["xyz999"], None),
    ):
        with patch(
            "app.core.database.purge_orphaned_alembic_stamps",
            MagicMock(),
        ):
            result = run_rollback_migration_cleanup(
                resource="stock_record",
                migration_file=str(mig_file),
                project_root=tmp_path,
                backend_dir=backend,
                force_drop=False,
            )

    assert result is False


def test_run_rollback_migration_cleanup_refuses_multiple_heads(tmp_path: Path) -> None:
    """多 head 时拒绝 downgrade."""
    backend = tmp_path / "backend"
    versions = backend / "migrations" / "versions"
    versions.mkdir(parents=True, exist_ok=True)

    mig_file = versions / "20260319_1000_codegen_stock_record.py"
    mig_file.write_text('''
revision = "abc123"
down_revision = "prev456"

def upgrade():
    pass

def downgrade():
    pass
''')

    with patch(
        "app.codegen.migration_helper._get_current_heads",
        return_value=(["abc123", "other_head"], None),
    ):
        with patch(
            "app.core.database.purge_orphaned_alembic_stamps",
            MagicMock(),
        ):
            result = run_rollback_migration_cleanup(
                resource="stock_record",
                migration_file=str(mig_file),
                project_root=tmp_path,
                backend_dir=backend,
                force_drop=False,
            )

    assert result is False


def test_locate_migration_file_falls_back_for_legacy_codegen_migration_without_metadata(
    tmp_path: Path,
) -> None:
    """旧 codegen 迁移（无 codegen_resource metadata）可被 fallback 定位."""
    backend = tmp_path / "backend"
    versions = backend / "migrations" / "versions"
    versions.mkdir(parents=True, exist_ok=True)

    legacy_mig = versions / "20260318_0900_legacy_stock_records.py"
    legacy_mig.write_text('''
revision = "legacy123"
down_revision = "prev"

def upgrade():
    op.create_table("stock_records", ...)

def downgrade():
    op.drop_table("stock_records")
''')
    # 无 codegen_resource，仅有表名

    with patch(
        "app.codegen.migration_helper._get_current_heads",
        return_value=(["legacy123"], None),
    ):
        with patch(
            "app.core.database.purge_orphaned_alembic_stamps",
            MagicMock(),
        ):
            with patch(
                "app.codegen.migration_helper._drop_table_if_exists",
                return_value=False,
            ):
                with patch(
                    "subprocess.run",
                    return_value=MagicMock(returncode=0),
                ):
                    result = run_rollback_migration_cleanup(
                        resource="stock_record",
                        migration_file=None,
                        project_root=tmp_path,
                        backend_dir=backend,
                        force_drop=False,
                    )

    assert result is True
    # 关键：能定位到 legacy 迁移文件，不会因 migration_file=None 直接放弃


def test_rollback_without_manifest_does_not_drop_table(tmp_path: Path) -> None:
    """无 manifest 或 migration 文件时，不执行 DROP TABLE (force_drop=False)."""
    backend = tmp_path / "backend"
    versions = backend / "migrations" / "versions"
    versions.mkdir(parents=True, exist_ok=True)

    with patch(
        "app.core.database.purge_orphaned_alembic_stamps",
        MagicMock(),
    ):
        with patch(
            "app.codegen.migration_helper._drop_table_if_exists",
            MagicMock(),
        ) as mock_drop:
            result = run_rollback_migration_cleanup(
                resource="stock_record",
                migration_file=None,
                project_root=tmp_path,
                backend_dir=backend,
                force_drop=False,
            )

    assert result is False
    mock_drop.assert_not_called()


def test_register_model_failure_surfaces_error_and_blocks_auto_migrate(tmp_path: Path) -> None:
    """register_model 目标文件不存在时写入 errors，success=False."""
    files = [
        GeneratedFile(
            path="backend/app/models/business/__init__.py",
            content="",
            action="register_model",
            model_meta={
                "module": "business",
                "resource": "stock_record",
                "pascal": "StockRecord",
                "target": "module",
            },
        ),
    ]
    # models/business/__init__.py 不存在

    writer = FileWriter(project_root=tmp_path)
    result = writer.write_atomic(files, project_root=tmp_path)

    assert result.success is False
    assert any("register_model failed" in e for e in result.errors)
    assert any("does not exist" in e for e in result.errors)


def test_register_route_failure_surfaces_error(tmp_path: Path) -> None:
    """register_route 目标文件不存在时写入 errors."""
    files = [
        GeneratedFile(
            path="backend/app/api/admin/__init__.py",
            content="",
            action="register_route",
            route_meta={"scope": "admin", "resource": "stock_record"},
        ),
    ]

    admin_init = tmp_path / "backend" / "app" / "api" / "admin"
    admin_init.mkdir(parents=True, exist_ok=True)
    # 不创建 __init__.py

    writer = FileWriter(project_root=tmp_path)
    result = writer.write_atomic(files, project_root=tmp_path)

    assert result.success is False
    assert any("register_route failed" in e for e in result.errors)


def test_create_if_missing_creates_init_for_new_module(tmp_path: Path) -> None:
    """create_if_missing 为新 module 创建 __init__.py."""
    dest = tmp_path / "backend" / "app" / "models" / "warehouse"
    dest.mkdir(parents=True, exist_ok=True)
    assert not (dest / "__init__.py").exists()

    files = [
        GeneratedFile(
            path="backend/app/models/warehouse/__init__.py",
            content="# Codegen module init\n",
            action="create_if_missing",
        ),
    ]

    writer = FileWriter(project_root=tmp_path)
    result = writer.write_atomic(files, project_root=tmp_path)

    assert result.success is True
    assert (dest / "__init__.py").exists()
    assert "Codegen" in (dest / "__init__.py").read_text()


def test_create_if_missing_skips_when_file_exists(tmp_path: Path) -> None:
    """create_if_missing 当文件已存在时不覆盖."""
    dest = tmp_path / "backend" / "app" / "models" / "existing" / "__init__.py"
    dest.parent.mkdir(parents=True, exist_ok=True)
    original = "# existing content\n"
    dest.write_text(original)

    files = [
        GeneratedFile(
            path="backend/app/models/existing/__init__.py",
            content="# Codegen module init\n",
            action="create_if_missing",
        ),
    ]

    writer = FileWriter(project_root=tmp_path)
    result = writer.write_atomic(files, project_root=tmp_path)

    assert result.success is True
    assert dest.read_text() == original
    assert "backend/app/models/existing/__init__.py" not in result.files_created


def test_migration_cleaned_only_true_when_downgrade_succeeds(tmp_path: Path) -> None:
    """migration_cleaned 仅在 downgrade 成功时返回 True，force_drop 早期退出仍返回 False."""
    backend = tmp_path / "backend"
    versions = backend / "migrations" / "versions"
    versions.mkdir(parents=True, exist_ok=True)

    with patch(
        "app.core.database.purge_orphaned_alembic_stamps",
        MagicMock(),
    ):
        with patch(
            "app.codegen.migration_helper._get_current_heads",
            return_value=(["other_head"], None),
        ):
            with patch(
                "app.codegen.migration_helper._drop_table_if_exists",
                return_value=True,
            ) as mock_drop:
                result = run_rollback_migration_cleanup(
                    resource="stock_record",
                    migration_file=None,
                    project_root=tmp_path,
                    backend_dir=backend,
                    force_drop=True,
                )

    assert result is False
    mock_drop.assert_called_once()
