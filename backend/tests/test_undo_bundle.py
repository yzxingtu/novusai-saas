"""
Undo Bundle — 单元测试

覆盖：
- Bundle 构建（created/modified）
- 安全路径检查
- 回滚计划生成
- 回滚执行（dry-run + 实际）
- 序列化/反序列化
- 摘要
"""

import json
import os

import pytest

from app.codegen.undo_bundle import (
    BUNDLE_VERSION,
    FileAction,
    RevertResult,
    UndoBundle,
    UndoFileEntry,
    apply_revert,
    build_undo_bundle,
    compute_revert_plan,
    export_bundle,
    import_bundle,
)


# ============================================================
# build_undo_bundle
# ============================================================


class TestBuildBundle:
    """Bundle 构建"""

    def test_basic_build(self):
        bundle = build_undo_bundle(
            base_dir="/project",
            written_files=[
                {
                    "path": "src/model.py",
                    "action": "created",
                    "new_content": "class Order: pass",
                },
                {
                    "path": "src/router.py",
                    "action": "modified",
                    "original_content": "# old",
                    "new_content": "# new",
                },
            ],
            run_id="test_run",
        )

        assert bundle.version == BUNDLE_VERSION
        assert bundle.run_id == "test_run"
        assert bundle.file_count() == 2
        assert len(bundle.created_files()) == 1
        assert len(bundle.modified_files()) == 1

    def test_created_file_no_original(self):
        bundle = build_undo_bundle(
            base_dir="/project",
            written_files=[{
                "path": "new_file.py",
                "action": "created",
                "new_content": "content",
            }],
        )
        entry = bundle.files[0]
        assert entry.action == FileAction.CREATED
        assert entry.original_content is None
        assert entry.hash_before is None
        assert entry.hash_after != ""

    def test_modified_file_has_original(self):
        bundle = build_undo_bundle(
            base_dir="/project",
            written_files=[{
                "path": "existing.py",
                "action": "modified",
                "original_content": "old content",
                "new_content": "new content",
            }],
        )
        entry = bundle.files[0]
        assert entry.action == FileAction.MODIFIED
        assert entry.original_content == "old content"
        assert entry.hash_before is not None

    def test_unsafe_path_filtered(self):
        """目录穿越路径被过滤"""
        bundle = build_undo_bundle(
            base_dir="/project",
            written_files=[{
                "path": "../../../etc/passwd",
                "action": "created",
                "new_content": "evil",
            }],
        )
        assert bundle.file_count() == 0

    def test_empty_path_skipped(self):
        bundle = build_undo_bundle(
            base_dir="/project",
            written_files=[{"path": "", "action": "created", "new_content": "x"}],
        )
        assert bundle.file_count() == 0

    def test_auto_run_id(self):
        bundle = build_undo_bundle("/project", [])
        assert len(bundle.run_id) == 12


# ============================================================
# compute_revert_plan
# ============================================================


class TestRevertPlan:
    """回滚计划"""

    def test_created_becomes_delete(self):
        bundle = build_undo_bundle(
            base_dir="/project",
            written_files=[{
                "path": "new.py",
                "action": "created",
                "new_content": "content",
            }],
        )
        plan = compute_revert_plan(bundle)
        assert len(plan) == 1
        assert plan[0]["action"] == "delete"
        assert plan[0]["path"] == "new.py"

    def test_modified_becomes_restore(self):
        bundle = build_undo_bundle(
            base_dir="/project",
            written_files=[{
                "path": "existing.py",
                "action": "modified",
                "original_content": "old",
                "new_content": "new",
            }],
        )
        plan = compute_revert_plan(bundle)
        assert len(plan) == 1
        assert plan[0]["action"] == "restore"
        assert plan[0]["content"] == "old"


# ============================================================
# apply_revert
# ============================================================


class TestApplyRevert:
    """回滚执行"""

    def test_dry_run(self):
        """无 write_fn/delete_fn → dry-run"""
        bundle = build_undo_bundle(
            base_dir="/project",
            written_files=[
                {"path": "a.py", "action": "created", "new_content": "x"},
                {"path": "b.py", "action": "modified", "original_content": "old", "new_content": "new"},
            ],
        )
        result = apply_revert(bundle)
        assert result.success is True
        assert len(result.reverted) == 2

    def test_actual_revert(self):
        """使用 mock write/delete"""
        written: dict[str, str] = {}
        deleted: list[str] = []

        def mock_write(path: str, content: str) -> None:
            written[path] = content

        def mock_delete(path: str) -> None:
            deleted.append(path)

        bundle = build_undo_bundle(
            base_dir="/project",
            written_files=[
                {"path": "new.py", "action": "created", "new_content": "x"},
                {"path": "old.py", "action": "modified", "original_content": "restored", "new_content": "changed"},
            ],
        )
        result = apply_revert(
            bundle,
            write_fn=mock_write,
            delete_fn=mock_delete,
        )

        assert result.success is True
        assert len(deleted) == 1
        assert "/project" in deleted[0] or "new.py" in deleted[0]
        assert any("restored" == v for v in written.values())

    def test_revert_no_original_content(self):
        """modified 但无 original_content → error"""
        bundle = UndoBundle(
            base_dir="/project",
            files=[UndoFileEntry(
                path="file.py",
                action=FileAction.MODIFIED,
                original_content=None,
                new_content="new",
                hash_after="abc",
            )],
        )
        result = apply_revert(bundle, write_fn=lambda p, c: None)
        assert result.success is False
        assert len(result.errors) == 1

    def test_revert_unsafe_path(self):
        """不安全路径 → error"""
        bundle = UndoBundle(
            base_dir="/project",
            files=[UndoFileEntry(
                path="../../../etc/passwd",
                action=FileAction.CREATED,
                new_content="evil",
                hash_after="abc",
            )],
        )
        result = apply_revert(bundle, delete_fn=lambda p: None)
        assert result.success is False


# ============================================================
# 序列化
# ============================================================


class TestSerialization:
    """序列化/反序列化"""

    def test_export_import_roundtrip(self):
        bundle = build_undo_bundle(
            base_dir="/project",
            written_files=[
                {"path": "a.py", "action": "created", "new_content": "content_a"},
                {"path": "b.py", "action": "modified", "original_content": "old_b", "new_content": "new_b"},
            ],
            run_id="test123",
        )

        exported = export_bundle(bundle)
        imported = import_bundle(exported)

        assert imported.run_id == "test123"
        assert imported.file_count() == 2
        assert imported.files[0].path == "a.py"
        assert imported.files[1].original_content == "old_b"

    def test_import_from_dict(self):
        data = {
            "version": BUNDLE_VERSION,
            "run_id": "abc",
            "base_dir": "/p",
            "files": [
                {"path": "x.py", "action": "created", "new_content": "c", "hash_after": "h"},
            ],
        }
        bundle = import_bundle(data)
        assert bundle.run_id == "abc"
        assert bundle.file_count() == 1


class TestSummary:
    """摘要"""

    def test_summary(self):
        bundle = build_undo_bundle(
            base_dir="/project",
            written_files=[
                {"path": "a.py", "action": "created", "new_content": "x"},
                {"path": "b.py", "action": "modified", "original_content": "o", "new_content": "n"},
            ],
            run_id="sum_test",
        )
        s = bundle.summary()
        assert s["run_id"] == "sum_test"
        assert s["file_count"] == 2
        assert s["created"] == 1
        assert s["modified"] == 1
