"""Test type: structural
Scope: task definition entitlement requirement migration.
Mock strategy: no mocks; static migration contract inspection.
"""

from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "migrations"
    / "versions"
    / "20260510_0042_task_entitlements.py"
)


def test_task_definition_entitlement_migration_adds_required_columns() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    expected_down_revision = (
        'down_revision: str | Sequence[str] | None = "20260509_0041_log_pages"'
    )

    assert 'revision: str = "20260510_0042_task_entitlements"' in source
    assert "Revises: 20260509_0041_log_pages" in source
    assert expected_down_revision in source
    assert '"required_feature_codes"' in source
    assert '"required_plugin_names"' in source
    assert "sa.JSON()" in source
