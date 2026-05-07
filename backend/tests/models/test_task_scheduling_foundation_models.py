"""Task scheduling foundation model registration tests."""

from app.core.base_model import Base
from app.models import TaskDefinition, TaskRun, TenantTaskBinding


def test_task_scheduling_foundation_tables_registered_in_metadata() -> None:
    tables = Base.metadata.tables

    assert "task_definitions" in tables
    assert "tenant_task_bindings" in tables
    assert "task_runs" in tables


def test_task_scheduling_foundation_models_exported() -> None:
    assert TaskDefinition.__tablename__ == "task_definitions"
    assert TenantTaskBinding.__tablename__ == "tenant_task_bindings"
    assert TaskRun.__tablename__ == "task_runs"


def test_task_definition_has_default_broker_priority_column() -> None:
    assert "default_priority" in TaskDefinition.__table__.columns
    assert any(
        constraint.name == "ck_task_definitions_default_priority_range"
        for constraint in TaskDefinition.__table__.constraints
    )


def test_task_run_has_business_run_key_unique_index() -> None:
    assert "run_key" in TaskRun.__table__.columns
    index = next(
        idx for idx in TaskRun.__table__.indexes if idx.name == "ix_task_runs_run_key"
    )
    assert index.unique is True
