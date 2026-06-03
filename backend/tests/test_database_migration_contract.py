"""Database migration startup contract tests. / 数据库启动迁移契约测试。

Test type: structural
Scope: Startup migration safety contracts and Alembic graph diagnostics.
"""

from __future__ import annotations

from pathlib import Path

from app.core import database


def test_overlapping_current_stamp_diagnostic_accepts_short_stale_parent() -> None:
    """中文: Alembic 短版本戳和后代 head 同时存在时给出明确诊断。

    EN: A short ancestor stamp together with a descendant head is diagnosed
    before Alembic emits its generic overlap error.
    """
    backend_dir = Path(__file__).resolve().parents[1]

    overlaps = database.resolve_overlapping_alembic_current_stamps(
        alembic_ini=backend_dir / "alembic.ini",
        backend_dir=backend_dir,
        db_url="postgresql://unused",
        version_locations=[str(backend_dir / "migrations" / "versions")],
        current_stamps=[
            "20260510_0042_task_ent",
            "20260510_0043_task_run_truth",
        ],
    )

    assert overlaps == [
        database.AlembicStampOverlap(
            ancestor_stamp="20260510_0042_task_ent",
            ancestor_revision="20260510_0042_task_entitlements",
            descendant_stamp="20260510_0043_task_run_truth",
            descendant_revision="20260510_0043_task_run_truth",
        )
    ]


def test_run_migrations_script_does_not_auto_stamp_or_auto_repair(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """中文: 启动迁移失败必须暴露真实错误，不能自动 stamp 或修库。

    EN: Startup migration failures must surface the real error, not auto-stamp
    or repair the database.
    """
    backend_dir = tmp_path
    migrations_dir = backend_dir / "migrations" / "versions"
    migrations_dir.mkdir(parents=True)
    (migrations_dir / "0001_init.py").write_text(
        "revision = '0001'\ndown_revision = None\n",
        encoding="utf-8",
    )
    (backend_dir / "alembic.ini").write_text("[alembic]\n", encoding="utf-8")

    monkeypatch.setattr(
        database,
        "__file__",
        str(backend_dir / "app" / "core" / "database.py"),
    )

    def _fake_version_locations(*, backend_dir: Path, db_url: str) -> list[str]:
        _ = db_url
        return [str(backend_dir / "migrations" / "versions")]

    monkeypatch.setattr(
        database,
        "build_migration_version_locations",
        _fake_version_locations,
    )

    def _fake_should_purge(*, debug: bool) -> bool:
        _ = debug
        return False

    monkeypatch.setattr(
        database,
        "should_purge_migration_bytecode_for_startup",
        _fake_should_purge,
    )
    monkeypatch.setattr(
        database,
        "resolve_expected_alembic_heads",
        lambda **_kwargs: ["0001"],
    )
    monkeypatch.setattr(
        database,
        "_read_alembic_version_rows",
        lambda _db_url: [],
    )

    captured: dict[str, str] = {}

    class _CompletedProcess:
        returncode = 1
        stdout = ""
        stderr = "sqlalchemy.exc.ProgrammingError: relation already exists"

    def _fake_run(cmd, **kwargs):  # noqa: ANN001
        script_path = Path(cmd[1])
        captured["script"] = script_path.read_text(encoding="utf-8")
        return _CompletedProcess()

    monkeypatch.setattr("subprocess.run", _fake_run)

    assert database.run_migrations() is False
    script = captured["script"]
    assert "command.stamp" not in script
    assert "DuplicateTable" not in script
    assert "already exists" not in script
    assert "maybe_recover_missing_main_branch_stamp" not in script
    assert "Purging orphaned stamp" not in script
    assert "command.upgrade(cfg, 'heads')" in script
    assert database.get_last_db_init_failure_reason()
