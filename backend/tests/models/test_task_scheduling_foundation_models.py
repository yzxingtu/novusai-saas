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
