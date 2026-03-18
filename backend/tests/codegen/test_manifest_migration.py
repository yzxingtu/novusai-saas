"""
Manifest migration_file 字段测试 / Manifest migration_file field tests.
"""

import json
from pathlib import Path

import pytest

from app.codegen.manifest import ManifestManager


def _setup_manifest(tmp_path: Path, entries: list[dict]) -> None:
    """写入 manifest 文件."""
    manifest_path = tmp_path / "codegen_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    data = {"entries": entries, "version": 1}
    manifest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def test_manifest_update_migration_file(tmp_path: Path) -> None:
    """update_migration_file 更新并持久化 migration_file."""
    _setup_manifest(
        tmp_path,
        [
            {
                "resource": "article",
                "module": "tenant",
                "generated_at": "2026-01-01T00:00:00Z",
                "config_id": 1,
                "config_hash": "abc",
                "files": [],
                "migration_file": None,
            }
        ],
    )
    manifest = ManifestManager(tmp_path)
    manifest.update_migration_file("article", "migrations/versions/20260319_xxx_codegen_auto.py")

    entry = manifest.get_entry("article")
    assert entry is not None
    assert entry.migration_file == "migrations/versions/20260319_xxx_codegen_auto.py"


def test_manifest_get_entry_returns_migration_file(tmp_path: Path) -> None:
    """get_entry 返回 migration_file 字段."""
    _setup_manifest(
        tmp_path,
        [
            {
                "resource": "notice",
                "module": "system",
                "generated_at": "2026-01-01T00:00:00Z",
                "config_id": 2,
                "config_hash": "def",
                "files": [{"path": "app/models/system/notice.py", "action": "create"}],
                "migration_file": "/abs/path/to/migrations/versions/20260319_yyy.py",
            }
        ],
    )
    manifest = ManifestManager(tmp_path)
    entry = manifest.get_entry("notice")
    assert entry is not None
    assert entry.migration_file == "/abs/path/to/migrations/versions/20260319_yyy.py"


def test_manifest_backward_compat_no_migration_file(tmp_path: Path) -> None:
    """旧 manifest 无 migration_file 时返回 None."""
    _setup_manifest(
        tmp_path,
        [
            {
                "resource": "category",
                "module": "system",
                "generated_at": "2026-01-01T00:00:00Z",
                "config_id": 1,
                "config_hash": "abc",
                "files": [],
            }
        ],
    )
    manifest = ManifestManager(tmp_path)
    entry = manifest.get_entry("category")
    assert entry is not None
    assert entry.migration_file is None


def test_rollback_result_no_manual_steps(tmp_path: Path) -> None:
    """回滚成功后 manual_steps 为空（自动化后不再需要手动步骤）."""
    created_file = tmp_path / "backend" / "app" / "models" / "system" / "test_res.py"
    created_file.parent.mkdir(parents=True, exist_ok=True)
    created_file.write_text("# generated\n")

    _setup_manifest(
        tmp_path,
        [
            {
                "resource": "test_res",
                "module": "system",
                "generated_at": "2026-01-01T00:00:00Z",
                "config_id": 1,
                "config_hash": "abc",
                "files": [{"path": "backend/app/models/system/test_res.py", "action": "create"}],
                "migration_file": None,
            }
        ],
    )

    from app.codegen.rollback import CodegenRollback

    rollback = CodegenRollback(project_root=tmp_path)
    result = rollback.rollback(resource="test_res")

    assert result.success is True
    assert result.manual_steps == []
