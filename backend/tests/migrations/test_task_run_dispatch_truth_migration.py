"""Test type: structural
Scope: task run dispatch truth migration.
Mock strategy: no mocks; static migration contract inspection.
"""

from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "migrations"
    / "versions"
    / "20260510_0043_task_run_truth.py"
)


def test_task_run_dispatch_truth_migration_adds_required_columns() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    expected_down_revision = (
        'down_revision: str | Sequence[str] | None = "20260510_0042_task_entitlements"'
    )

    assert 'revision: str = "20260510_0043_task_run_truth"' in source
    assert "Revises: 20260510_0042_task_entitlements" in source
    assert expected_down_revision in source
    assert '"priority"' in source
    assert '"trigger_slot"' in source
    assert '"trigger_id"' in source
    assert '"retry_of_run_id"' in source
    assert '"retry_of_task_id"' in source
    assert "ix_task_runs_definition_trigger_slot" in source
    assert "fk_task_runs_retry_of_run_id_task_runs" in source
