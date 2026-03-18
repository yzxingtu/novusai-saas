"""
文件写入器测试 / File Writer tests.

测试 atomic_write、conflict、backup、SmartAppender 幂等、merge_json
Tests atomic_write, conflict, backup, SmartAppender idempotency, merge_json.
"""

import json
from pathlib import Path

import pytest

from app.codegen.file_writer import FileWriter, SmartAppender, WriteResult
from app.codegen.generator import GeneratedFile


# ============================================================
# FileWriter atomic_write
# ============================================================


def test_atomic_write_creates_new_files(tmp_path: Path) -> None:
    """原子写入新建文件."""
    dest_dir = tmp_path / "subdir"
    dest_dir.mkdir(parents=True, exist_ok=True)
    files = [
        GeneratedFile(path="subdir/new_file.py", content="print('hello')", action="create"),
    ]
    writer = FileWriter(project_root=tmp_path)
    result = writer.write_atomic(files, project_root=tmp_path)

    assert result.success is True
    assert len(result.files_created) >= 1
    dest = tmp_path / "subdir" / "new_file.py"
    assert dest.exists()
    assert dest.read_text() == "print('hello')"


def test_atomic_write_conflict_when_file_exists(tmp_path: Path) -> None:
    """文件已存在时记录 conflict 并备份后覆盖."""
    existing = tmp_path / "existing.py"
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_text("original")

    files = [
        GeneratedFile(path="existing.py", content="overridden", action="create"),
    ]
    writer = FileWriter(project_root=tmp_path)
    result = writer.write_atomic(files, project_root=tmp_path)

    assert result.success is True
    assert any(c.get("reason") == "file_exists" for c in result.conflicts)
    assert "existing.py" in result.files_modified or str(existing) in result.files_modified
    assert existing.read_text() == "overridden"
    assert result.backup_dir


# ============================================================
# SmartAppender
# ============================================================


def test_smart_appender_import_idempotent(tmp_path: Path) -> None:
    """append_python_import 幂等：重复调用不重复追加."""
    target = tmp_path / "models" / "__init__.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("from .base import Base\n")

    first = SmartAppender.append_python_import(
        target, "from .category import Category", all_export=None
    )
    assert first is True

    second = SmartAppender.append_python_import(
        target, "from .category import Category", all_export=None
    )
    assert second is False

    content = target.read_text()
    assert content.count("from .category import Category") == 1


def test_smart_appender_ts_export_idempotent(tmp_path: Path) -> None:
    """append_ts_export 幂等."""
    target = tmp_path / "api" / "index.ts"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("// api\n")

    SmartAppender.append_ts_export(target, "export * from './category';")
    SmartAppender.append_ts_export(target, "export * from './category';")

    content = target.read_text()
    assert content.count("export * from './category';") == 1


def test_smart_appender_merge_json(tmp_path: Path) -> None:
    """merge_json 深度合并并返回新增 key."""
    target = tmp_path / "locales" / "zh-CN.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('{"common": {"ok": "确定"}}\n', encoding="utf-8")

    added = SmartAppender.merge_json(target, {"codegen": {"title": "代码生成"}})
    assert "codegen" in added

    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["common"]["ok"] == "确定"
    assert data["codegen"]["title"] == "代码生成"


def test_smart_appender_merge_json_deep_merge(tmp_path: Path) -> None:
    """merge_json 深度合并嵌套对象."""
    target = tmp_path / "config.json"
    target.write_text('{"a": {"b": 1, "c": 2}}\n', encoding="utf-8")

    SmartAppender.merge_json(target, {"a": {"c": 3, "d": 4}})

    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["a"]["b"] == 1
    assert data["a"]["c"] == 3
    assert data["a"]["d"] == 4


# ============================================================
# FileWriter append / merge_json actions
# ============================================================


def test_atomic_write_append_action(tmp_path: Path) -> None:
    """append 操作追加内容."""
    target = tmp_path / "routers" / "admin.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("router = APIRouter()\n")

    files = [
        GeneratedFile(
            path="routers/admin.py",
            content="",
            action="append",
            appended_content="router.include_router(category_router, prefix='/categories')",
        ),
    ]
    writer = FileWriter(project_root=tmp_path)
    result = writer.write_atomic(files, project_root=tmp_path)

    assert result.success is True
    content = target.read_text()
    assert "include_router" in content


def test_atomic_write_merge_json_action(tmp_path: Path) -> None:
    """merge_json 操作合并 JSON."""
    target = tmp_path / "locales" / "codegen.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("{}", encoding="utf-8")

    files = [
        GeneratedFile(
            path="locales/codegen.json",
            content="",
            action="merge_json",
            merged_keys=["category"],
        ),
    ]
    writer = FileWriter(project_root=tmp_path)
    result = writer.write_atomic(files, project_root=tmp_path)

    assert result.success is True
    data = json.loads(target.read_text(encoding="utf-8"))
    assert "category" in data
