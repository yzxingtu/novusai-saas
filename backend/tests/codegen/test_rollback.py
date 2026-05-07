"""
回滚引擎测试 / Rollback tests.

测试 rollback_created、rollback_appended、rollback_merged、
modified_file_warning、dry_run
Tests rollback_created, rollback_appended, rollback_merged,
modified_file_warning, dry_run.
"""

import json
from pathlib import Path

from app.codegen.manifest import ManifestManager
from app.codegen.rollback import CodegenRollback


def _setup_manifest(tmp_path: Path, resource: str, files: list[dict]) -> None:
    """写入 manifest 条目."""
    manifest_path = tmp_path / "codegen_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "entries": [
            {
                "resource": resource,
                "module": "system",
                "generated_at": "2026-01-01T00:00:00Z",
                "config_id": 1,
                "config_hash": "abc",
                "files": files,
            }
        ],
        "version": 1,
    }
    manifest_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def test_rollback_created_deletes_file(tmp_path: Path) -> None:
    """rollback create 操作删除生成的文件."""
    created_file = tmp_path / "backend" / "app" / "models" / "system" / "category.py"
    created_file.parent.mkdir(parents=True, exist_ok=True)
    created_file.write_text("# generated\n")

    _setup_manifest(
        tmp_path,
        "category",
        [{"path": "backend/app/models/system/category.py", "action": "create"}],
    )

    rollback = CodegenRollback(project_root=tmp_path)
    result = rollback.rollback(resource="category")

    assert result.success is True
    assert "backend/app/models/system/category.py" in result.files_deleted
    assert not created_file.exists()


def test_rollback_appended_removes_content(tmp_path: Path) -> None:
    """rollback append 操作移除追加的内容."""
    target = tmp_path / "backend" / "app" / "api" / "admin" / "__init__.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    appended = "router.include_router(category_router, prefix='/categories')"
    target.write_text(
        "from fastapi import APIRouter\n\nrouter = APIRouter()\n" + appended + "\n"
    )

    _setup_manifest(
        tmp_path,
        "category",
        [
            {
                "path": "backend/app/api/admin/__init__.py",
                "action": "append",
                "appended_content": appended,
            }
        ],
    )

    rollback = CodegenRollback(project_root=tmp_path)
    result = rollback.rollback(resource="category")

    assert result.success is True
    assert "backend/app/api/admin/__init__.py" in result.files_modified
    content = target.read_text()
    assert appended not in content
    assert "APIRouter" in content


def test_rollback_merged_removes_keys(tmp_path: Path) -> None:
    """rollback merge_json 操作移除合并的 key."""
    target = tmp_path / "frontend" / "locales" / "zh-CN" / "codegen.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        '{"common": {"ok": "确定"}, "category": {"title": "分类"}}\n',
        encoding="utf-8",
    )

    _setup_manifest(
        tmp_path,
        "category",
        [
            {
                "path": "frontend/locales/zh-CN/codegen.json",
                "action": "merge_json",
                "merged_keys": ["category"],
            }
        ],
    )

    rollback = CodegenRollback(project_root=tmp_path)
    result = rollback.rollback(resource="category")

    assert result.success is True
    assert "frontend/locales/zh-CN/codegen.json" in result.files_modified
    data = json.loads(target.read_text(encoding="utf-8"))
    assert "category" not in data
    assert data["common"]["ok"] == "确定"


def test_rollback_merged_nested_key_removes_subkey(tmp_path: Path) -> None:
    """merge_json 回滚支持嵌套 key 路径，如 tenant.article."""
    target = tmp_path / "messages.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    existing = {
        "tenant": {
            "article": {"not_found": "Article not found", "created": "Article created"},
            "other": {"not_found": "Other not found"},
        }
    }
    target.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    _setup_manifest(
        tmp_path,
        "article",
        [
            {
                "path": "messages.json",
                "action": "merge_json",
                "merged_keys": ["tenant.article"],
            }
        ],
    )

    rollback = CodegenRollback(project_root=tmp_path)
    result = rollback.rollback(resource="article")

    assert result.success is True
    assert "messages.json" in result.files_modified
    data = json.loads(target.read_text(encoding="utf-8"))
    assert "article" not in data.get("tenant", {})
    assert data["tenant"]["other"]["not_found"] == "Other not found"


def test_rollback_merged_multiple_nested_keys(tmp_path: Path) -> None:
    """merge_json 回滚支持多条嵌套 key，如 tenant.article 和 action.article."""
    target = tmp_path / "messages.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    existing = {
        "tenant": {"article": {"not_found": "Article not found"}},
        "action": {
            "article": {"list": "View Article", "create": "Create Article"},
            "notice": {"list": "View Notice"},
        },
    }
    target.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    _setup_manifest(
        tmp_path,
        "article",
        [
            {
                "path": "messages.json",
                "action": "merge_json",
                "merged_keys": ["tenant.article", "action.article"],
            }
        ],
    )

    rollback = CodegenRollback(project_root=tmp_path)
    result = rollback.rollback(resource="article")

    assert result.success is True
    assert "messages.json" in result.files_modified
    data = json.loads(target.read_text(encoding="utf-8"))
    assert "article" not in data.get("tenant", {})
    assert "article" not in data.get("action", {})
    assert data["action"]["notice"]["list"] == "View Notice"


def test_rollback_modified_file_warning_skips_append(tmp_path: Path) -> None:
    """当 append 内容已被修改时，跳过并记录 files_skipped，partial rollback 时 success=False."""
    target = tmp_path / "routers.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    original_append = "router.include_router(x)"
    target.write_text("router = APIRouter()\n# user edited this\n")  # 无 appended 内容

    _setup_manifest(
        tmp_path,
        "category",
        [
            {
                "path": "routers.py",
                "action": "append",
                "appended_content": original_append,
            }
        ],
    )

    rollback = CodegenRollback(project_root=tmp_path)
    result = rollback.rollback(resource="category")

    assert result.success is False  # partial rollback with files_skipped
    skipped = [s for s in result.files_skipped if s.get("path") == "routers.py"]
    assert len(skipped) == 1
    assert skipped[0].get("reason") == "appended_content_modified"


def test_rollback_dry_run_no_changes(tmp_path: Path) -> None:
    """dry_run 仅列出操作，不实际修改文件."""
    created_file = tmp_path / "generated.py"
    created_file.write_text("content")

    _setup_manifest(
        tmp_path, "category", [{"path": "generated.py", "action": "create"}]
    )

    rollback = CodegenRollback(project_root=tmp_path)
    result = rollback.rollback(resource="category", dry_run=True)

    assert result.success is True
    assert "generated.py" in result.files_deleted
    assert created_file.exists()
    assert created_file.read_text() == "content"


def test_rollback_no_entry_returns_error(tmp_path: Path) -> None:
    """无 manifest 条目时返回错误."""
    _setup_manifest(tmp_path, "other", [])

    rollback = CodegenRollback(project_root=tmp_path)
    result = rollback.rollback(resource="nonexistent")

    assert result.success is False
    assert len(result.errors) > 0
    assert "manifest" in " ".join(result.errors).lower()


def test_rollback_create_content_modified_skips_without_force(tmp_path: Path) -> None:
    """create 操作：文件被修改且无 content_hash 时可删除；有 content_hash 且不匹配时 force=false 则跳过."""
    import hashlib

    created_file = tmp_path / "backend" / "app" / "models" / "system" / "category.py"
    created_file.parent.mkdir(parents=True, exist_ok=True)
    created_file.write_text("# user modified\n")  # 与生成时不同

    orig_content = "# generated\n"
    orig_hash = hashlib.sha256(orig_content.encode("utf-8")).hexdigest()
    _setup_manifest(
        tmp_path,
        "category",
        [
            {
                "path": "backend/app/models/system/category.py",
                "action": "create",
                "content_hash": orig_hash,
            }
        ],
    )

    rollback = CodegenRollback(project_root=tmp_path)
    result = rollback.rollback(resource="category", force=False)

    assert result.success is False
    assert len(result.files_skipped) == 1
    assert result.files_skipped[0].get("reason") == "content_modified"
    assert created_file.exists()
    assert "# user modified" in created_file.read_text()


def test_rollback_create_content_modified_deletes_with_force(tmp_path: Path) -> None:
    """create 操作：文件被修改时 force=true 仍删除."""
    import hashlib

    created_file = tmp_path / "backend" / "app" / "models" / "system" / "category.py"
    created_file.parent.mkdir(parents=True, exist_ok=True)
    created_file.write_text("# user modified\n")

    orig_hash = hashlib.sha256(b"# generated\n").hexdigest()
    _setup_manifest(
        tmp_path,
        "category",
        [
            {
                "path": "backend/app/models/system/category.py",
                "action": "create",
                "content_hash": orig_hash,
            }
        ],
    )

    rollback = CodegenRollback(project_root=tmp_path)
    result = rollback.rollback(resource="category", force=True)

    assert result.success is True
    assert not created_file.exists()


def test_rollback_partial_never_removes_manifest(tmp_path: Path) -> None:
    """部分回滚（有 files_skipped）时保留 manifest，不报 success."""
    target = tmp_path / "routers.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("router = APIRouter()\n")
    manifest_path = tmp_path / "codegen_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_data = {
        "entries": [
            {
                "resource": "category",
                "module": "system",
                "generated_at": "2026-01-01T00:00:00Z",
                "config_id": 1,
                "files": [
                    {
                        "path": "routers.py",
                        "action": "append",
                        "appended_content": "router.include_router(x)",  # 不存在于文件中
                    }
                ],
            }
        ],
        "version": 1,
    }
    manifest_path.write_text(json.dumps(manifest_data, ensure_ascii=False, indent=2))

    rollback = CodegenRollback(project_root=tmp_path)
    result = rollback.rollback(resource="category", force=True)

    assert result.success is False
    assert len(result.files_skipped) > 0
    data = json.loads(manifest_path.read_text())
    assert len(data["entries"]) == 1
    assert data["entries"][0]["resource"] == "category"


def test_rollback_shared_file_skip_blocks_create_delete(tmp_path: Path) -> None:
    """共享文件回滚失败时，create 文件不应先被删除，避免留下坏引用."""
    created_file = tmp_path / "backend" / "app" / "models" / "system" / "category.py"
    created_file.parent.mkdir(parents=True, exist_ok=True)
    created_file.write_text("# generated\n", encoding="utf-8")

    router_init = tmp_path / "backend" / "app" / "api" / "admin" / "__init__.py"
    router_init.parent.mkdir(parents=True, exist_ok=True)
    router_init.write_text(
        "from fastapi import APIRouter\nadmin_router = APIRouter()\n", encoding="utf-8"
    )

    _setup_manifest(
        tmp_path,
        "category",
        [
            {
                "path": "backend/app/models/system/category.py",
                "action": "create",
            },
            {
                "path": "backend/app/api/admin/__init__.py",
                "action": "register_route",
                "route_meta": {"scope": "admin", "resource": "category"},
            },
        ],
    )

    rollback = CodegenRollback(project_root=tmp_path)
    result = rollback.rollback(resource="category")

    assert result.success is False
    assert created_file.exists()
    reasons = {item.get("reason") for item in result.files_skipped}
    assert "register_block_modified" in reasons
    assert "blocked_by_earlier_skip" in reasons


def test_rollback_register_route_ignores_legacy_hash_and_preserves_other_routes(
    tmp_path: Path,
) -> None:
    """旧 manifest 的整文件 hash 不应阻止共享路由文件按片段回滚."""
    target = tmp_path / "backend" / "app" / "api" / "admin" / "__init__.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "\n".join(
            [
                "from fastapi import APIRouter",
                "from app.api.admin.article import AdminArticleController",
                "from app.api.admin.article import router as article_router",
                "from app.api.admin.notice import AdminNoticeController",
                "from app.api.admin.notice import router as notice_router",
                "",
                "admin_router = APIRouter()",
                "# Codegen auto-registered: article",
                "admin_router.include_router(article_router)",
                "# Codegen auto-registered: notice",
                "admin_router.include_router(notice_router)",
                "",
                "__all__ = [",
                '    "AdminArticleController",',
                '    "AdminNoticeController",',
                "]",
                "",
            ]
        ),
        encoding="utf-8",
    )

    _setup_manifest(
        tmp_path,
        "article",
        [
            {
                "path": "backend/app/api/admin/__init__.py",
                "action": "register_route",
                "route_meta": {"scope": "admin", "resource": "article"},
                "content_hash": "stale-whole-file-hash",
            }
        ],
    )

    rollback = CodegenRollback(project_root=tmp_path)
    result = rollback.rollback(resource="article")

    assert result.success is True
    content = target.read_text(encoding="utf-8")
    assert "article_router" not in content
    assert "AdminArticleController" not in content
    assert "notice_router" in content
    assert "AdminNoticeController" in content


def test_rollback_success_marks_manifest_pending_migration_cleanup(
    tmp_path: Path,
) -> None:
    """文件回滚成功后仅标记 file_rollback_completed，等待 migration cleanup 再删 manifest."""
    created_file = tmp_path / "backend" / "app" / "models" / "system" / "category.py"
    created_file.parent.mkdir(parents=True, exist_ok=True)
    created_file.write_text("# generated\n", encoding="utf-8")
    _setup_manifest(
        tmp_path,
        "category",
        [{"path": "backend/app/models/system/category.py", "action": "create"}],
    )

    rollback = CodegenRollback(project_root=tmp_path)
    result = rollback.rollback(resource="category")

    assert result.success is True
    entry = ManifestManager(tmp_path).get_entry("category")
    assert entry is not None
    assert entry.file_rollback_completed is True
