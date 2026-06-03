"""Plugin migration path resolution tests. / 插件迁移路径解析测试。"""

from __future__ import annotations

import ast
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

from app.core.database import should_skip_migration_subprocess
from app.plugins.migration_paths import (
    build_migration_version_locations,
    get_db_registered_plugin_names,
    purge_migration_bytecode,
    should_purge_migration_bytecode_for_startup,
)


def _prepare_backend_tree(tmp_path: Path) -> Path:
    backend_dir = tmp_path / "backend"
    (backend_dir / "migrations" / "versions").mkdir(parents=True, exist_ok=True)
    (
        backend_dir
        / "plugins"
        / "installed-plugin"
        / "backend"
        / "migrations"
        / "versions"
    ).mkdir(parents=True, exist_ok=True)
    (
        backend_dir
        / "plugins"
        / "disk-only-plugin"
        / "backend"
        / "migrations"
        / "versions"
    ).mkdir(parents=True, exist_ok=True)
    return backend_dir


def _prepare_plugin_db(tmp_path: Path, rows: list[dict[str, object]]) -> str:
    db_path = tmp_path / "plugins.sqlite"
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    with engine.begin() as conn:
        conn.execute(
            text("CREATE TABLE plugins (name TEXT NOT NULL, is_deleted BOOLEAN)")
        )
        for row in rows:
            conn.execute(
                text(
                    "INSERT INTO plugins (name, is_deleted) VALUES (:name, :is_deleted)"
                ),
                row,
            )
    engine.dispose()
    return f"sqlite:///{db_path.as_posix()}"


def test_get_db_registered_plugin_names_ignores_soft_deleted_rows(
    tmp_path: Path,
) -> None:
    db_url = _prepare_plugin_db(
        tmp_path,
        [
            {"name": "storage-billing", "is_deleted": False},
            {"name": "weather-widget", "is_deleted": True},
        ],
    )

    assert get_db_registered_plugin_names(db_url=db_url) == ["storage-billing"]


def test_build_migration_version_locations_uses_db_registered_plugins_only(
    tmp_path: Path,
) -> None:
    backend_dir = _prepare_backend_tree(tmp_path)
    db_url = _prepare_plugin_db(
        tmp_path,
        [
            {"name": "installed-plugin", "is_deleted": False},
            {"name": "missing-plugin", "is_deleted": False},
        ],
    )

    version_locations = build_migration_version_locations(
        backend_dir=backend_dir,
        db_url=db_url,
    )

    assert version_locations == [
        str(backend_dir / "migrations" / "versions").replace("\\", "/"),
        str(
            backend_dir
            / "plugins"
            / "installed-plugin"
            / "backend"
            / "migrations"
            / "versions"
        ).replace("\\", "/"),
    ]


def test_build_migration_version_locations_can_force_current_plugin_before_db_row_exists(
    tmp_path: Path,
) -> None:
    backend_dir = _prepare_backend_tree(tmp_path)
    db_url = _prepare_plugin_db(tmp_path, [])

    version_locations = build_migration_version_locations(
        backend_dir=backend_dir,
        db_url=db_url,
        include_plugin_names=["disk-only-plugin"],
    )

    assert version_locations == [
        str(backend_dir / "migrations" / "versions").replace("\\", "/"),
        str(
            backend_dir
            / "plugins"
            / "disk-only-plugin"
            / "backend"
            / "migrations"
            / "versions"
        ).replace("\\", "/"),
    ]


def test_build_migration_version_locations_gracefully_handles_missing_plugin_table(
    tmp_path: Path,
) -> None:
    backend_dir = _prepare_backend_tree(tmp_path)
    db_path = tmp_path / "plugins.sqlite"

    version_locations = build_migration_version_locations(
        backend_dir=backend_dir,
        db_url=f"sqlite:///{db_path.as_posix()}",
    )

    assert version_locations == [
        str(backend_dir / "migrations" / "versions").replace("\\", "/"),
    ]


def test_purge_migration_bytecode_removes_cached_files(tmp_path: Path) -> None:
    versions_dir = tmp_path / "versions"
    pycache_dir = versions_dir / "__pycache__"
    pycache_dir.mkdir(parents=True, exist_ok=True)

    stale_pyc = pycache_dir / "001_initial.cpython-312.pyc"
    stale_pyc.write_bytes(b"stale-bytecode")
    keep_txt = pycache_dir / "notes.txt"
    keep_txt.write_text("keep", encoding="utf-8")

    removed = purge_migration_bytecode([versions_dir])

    assert removed == [str(stale_pyc).replace("\\", "/")]
    assert not stale_pyc.exists()
    assert keep_txt.exists()


def test_should_purge_migration_bytecode_for_startup_skips_debug_mode() -> None:
    assert should_purge_migration_bytecode_for_startup(debug=True) is False
    assert should_purge_migration_bytecode_for_startup(debug=False) is True


def test_should_skip_migration_subprocess_when_db_already_at_heads() -> None:
    skip, reason = should_skip_migration_subprocess(
        current_stamps=["wo_002", "main_123"],
        expected_heads=["main_123", "wo_002"],
    )

    assert skip is True
    assert "already at current heads" in reason


def test_should_skip_migration_subprocess_when_db_stamps_differ() -> None:
    skip, reason = should_skip_migration_subprocess(
        current_stamps=["main_123"],
        expected_heads=["main_123", "wo_002"],
    )

    assert skip is False
    assert "differ from current heads" in reason


def test_storage_billing_plugin_revisions_load_via_alembic(tmp_path: Path) -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "plugins.sqlite"

    version_locations = build_migration_version_locations(
        backend_dir=backend_dir,
        db_url=f"sqlite:///{db_path.as_posix()}",
        include_plugin_names=["storage-billing"],
    )

    cfg = Config(str(backend_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir / "migrations"))
    cfg.set_main_option("version_locations", "\n".join(version_locations))

    script = ScriptDirectory.from_config(cfg)
    storage_billing_revision_ids = {
        "sb_001_init",
        "sb_002_bindings",
        "sb_003_period_fields",
    }
    storage_billing_heads = {
        head for head in script.get_heads() if str(head).startswith("sb_")
    }

    assert storage_billing_heads
    assert storage_billing_heads.issubset(storage_billing_revision_ids)


def test_plugin_branch_labels_are_unique_across_revision_map() -> None:
    plugins_root = Path(__file__).resolve().parents[1] / "plugins"

    labels_to_revisions: dict[str, list[str]] = {}

    for file_path in plugins_root.glob("*/backend/migrations/versions/*.py"):
        if file_path.name == "__init__.py":
            continue

        source = file_path.read_text(encoding="utf-8")
        module = ast.parse(source, filename=str(file_path))
        revision = None
        branch_labels = None

        for node in module.body:
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            target = node.targets[0]
            if not isinstance(target, ast.Name):
                continue
            if target.id == "revision":
                revision = ast.literal_eval(node.value)
            if target.id == "branch_labels":
                branch_labels = ast.literal_eval(node.value)

        if revision is None or branch_labels is None:
            continue

        if not branch_labels:
            continue

        for branch_label in branch_labels:
            labels_to_revisions.setdefault(str(branch_label), []).append(str(revision))

    duplicates = {
        branch_label: revisions
        for branch_label, revisions in labels_to_revisions.items()
        if len(revisions) > 1
    }

    assert duplicates == {}
