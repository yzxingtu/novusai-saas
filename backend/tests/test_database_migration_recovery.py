"""Database migration recovery guards. / 数据库迁移恢复保护测试。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.database import (
    MainSchemaCoverage,
    maybe_recover_missing_main_branch_stamp,
    should_auto_recover_missing_main_branch_stamp,
)


def _coverage(
    *,
    missing_tables: tuple[str, ...] = (),
    missing_columns_by_table: dict[str, tuple[str, ...]] | None = None,
    total_model_column_count: int = 200,
) -> MainSchemaCoverage:
    return MainSchemaCoverage(
        model_table_count=64,
        total_model_column_count=total_model_column_count,
        missing_tables=missing_tables,
        missing_columns_by_table=missing_columns_by_table or {},
    )


def test_should_auto_recover_missing_main_branch_stamp_accepts_plugin_only_stamps() -> (
    None
):
    ok, reason = should_auto_recover_missing_main_branch_stamp(
        current_stamps=["novusdoc_002_tid_nullable", "sm_001_init"],
        main_revision_ids={"0001", "20260325_skill_arch_foundation"},
        coverage=_coverage(
            missing_columns_by_table={"skill_packages": ("bind_mode",)},
        ),
    )

    assert ok is True
    assert "main branch stamp missing" in reason


def test_should_auto_recover_missing_main_branch_stamp_rejects_when_main_stamp_exists() -> (
    None
):
    ok, reason = should_auto_recover_missing_main_branch_stamp(
        current_stamps=["20260325_skill_arch_foundation", "sm_001_init"],
        main_revision_ids={"0001", "20260325_skill_arch_foundation"},
        coverage=_coverage(),
    )

    assert ok is False
    assert reason == "main branch stamp already present"


def test_should_auto_recover_missing_main_branch_stamp_rejects_missing_tables() -> None:
    ok, reason = should_auto_recover_missing_main_branch_stamp(
        current_stamps=["sm_001_init"],
        main_revision_ids={"0001", "20260325_skill_arch_foundation"},
        coverage=_coverage(missing_tables=("permissions",)),
    )

    assert ok is False
    assert reason.startswith("missing main tables:")


def test_should_auto_recover_missing_main_branch_stamp_rejects_large_column_gap() -> (
    None
):
    ok, reason = should_auto_recover_missing_main_branch_stamp(
        current_stamps=["sm_001_init"],
        main_revision_ids={"0001", "20260325_skill_arch_foundation"},
        coverage=_coverage(
            missing_columns_by_table={
                "permissions": ("a", "b"),
                "skill_packages": ("c", "d"),
            },
        ),
    )

    assert ok is False
    assert reason == "missing too many model columns: 4"


def test_maybe_recover_missing_main_branch_stamp_stamps_resolved_main_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.core.database._collect_revision_ids_from_dir",
        lambda _directory: {"0001", "20260325_skill_arch_foundation"},
    )
    monkeypatch.setattr(
        "app.core.database._read_alembic_version_rows",
        lambda _db_url: ["novusdoc_002_tid_nullable", "sm_001_init"],
    )
    monkeypatch.setattr(
        "app.core.database._inspect_main_schema_coverage",
        lambda _db_url: _coverage(
            missing_columns_by_table={"skill_packages": ("bind_mode",)},
        ),
    )
    monkeypatch.setattr(
        "app.core.database._resolve_main_head_revision",
        lambda _cfg, _main_revision_ids: "20260325_skill_arch_foundation",
    )

    stamped: list[str] = []

    def _fake_stamp(cfg, revision):  # noqa: ANN001
        stamped.append(revision)

    monkeypatch.setattr("alembic.command.stamp", _fake_stamp)

    recovered, reason = maybe_recover_missing_main_branch_stamp(
        cfg=SimpleNamespace(),
        db_url="postgresql://example",
        main_versions_dir="migrations/versions",
    )

    assert recovered is True
    assert stamped == ["20260325_skill_arch_foundation"]
    assert "Recovered missing main branch stamp" in reason
