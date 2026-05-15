"""Test type: structural
Scope: tenant user role recycle-bin repair migration.
Mock strategy: no mocks; static migration source inspection only.
"""

from __future__ import annotations

from pathlib import Path

CREATE_MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "migrations"
    / "versions"
    / "20260307_add_tenant_user_roles.py"
)
REPAIR_MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "migrations"
    / "versions"
    / "20260513_0045_tenant_user_role_recycle.py"
)


def test_tenant_user_roles_fresh_create_matches_tenant_model_recycle_contract() -> None:
    source = CREATE_MIGRATION.read_text(encoding="utf-8")

    for token in (
        '"deleted_at"',
        '"delete_level"',
        '"recycle_stage"',
        '"promoted_to_global_at"',
        "ix_tenant_user_roles_recycle_stage",
    ):
        assert token in source


def test_tenant_user_role_repair_migration_is_idempotent_and_ordered() -> None:
    source = REPAIR_MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260513_0045_tur_recycle"' in source
    assert (
        'down_revision: str | Sequence[str] | None = "20260513_0044_retire_llm_builtin"'
        in source
    )
    assert 'TABLE_NAME = "tenant_user_roles"' in source
    assert "_column_names" in source
    assert "_repair_columns" in source
    assert "op.add_column(TABLE_NAME, column)" in source
    assert "_index_names" in source
    assert (
        'op.create_index(INDEX_NAME, TABLE_NAME, ["recycle_stage"], unique=False)'
        in source
    )


def test_tenant_user_role_repair_migration_backfills_recycle_state() -> None:
    source = REPAIR_MIGRATION.read_text(encoding="utf-8")

    assert "is_deleted.is_(False)" in source
    assert 'delete_level == "admin"' in source
    assert 'recycle_stage="global"' in source
    assert 'delete_level == "tenant"' in source
    assert 'recycle_stage="module"' in source
    assert "sa.func.coalesce" in source
    assert "text(f" not in source
    assert 'f"""' not in source
    assert "def downgrade() -> None:\n    pass" in source
