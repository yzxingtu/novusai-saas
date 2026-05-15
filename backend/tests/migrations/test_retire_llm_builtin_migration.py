"""Test type: structural
Scope: historical system chat/embedding skill package retirement migration.
Mock strategy: no mocks; static migration source inspection only.
"""

from __future__ import annotations

from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "migrations"
    / "versions"
    / "20260513_0044_retire_llm_builtin.py"
)


def test_retire_llm_builtin_migration_targets_legacy_catalog_rows() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260513_0044_retire_llm_builtin"' in source
    assert (
        'down_revision: str | Sequence[str] | None = "20260510_0043_task_run_truth"'
        in source
    )
    for table_name in (
        "skill_packages",
        "skills",
        "agent_skill_grants",
        "agents",
    ):
        assert table_name in source
    for token in (
        "系统聊天技能包",
        "系统向量化技能包",
        "系统核心技能包",
        "系统引擎技能包",
        "llm_chat",
        "llm_embedding",
        "system_chat_agent",
        "system_embedding_agent",
    ):
        assert token in source
    assert "enabled = false" in source
    assert "status = 'disabled'" in source
    assert "is_active = false" in source
    assert "is_deleted = true" in source
    assert "is_recommended = false" in source


def test_retire_llm_builtin_migration_is_parameterized_and_forward_only() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert "text(f" not in source
    assert 'f"""' not in source
    assert ":legacy_package_names" in source
    assert ":legacy_skill_names" in source
    assert ":legacy_agent_names" in source
    assert "_has_columns" in source
    assert "def downgrade() -> None:\n    pass" in source
