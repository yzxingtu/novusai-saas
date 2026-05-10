"""中文: 任务调度基础模型注册契约测试。

EN: Task scheduling foundation model registration contract tests.

Test type: structural
"""

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


def test_task_definition_has_tenant_entitlement_requirement_columns() -> None:
    assert "required_feature_codes" in TaskDefinition.__table__.columns
    assert "required_plugin_names" in TaskDefinition.__table__.columns


def test_task_run_has_business_run_key_unique_index() -> None:
    assert "run_key" in TaskRun.__table__.columns
    index = next(
        idx for idx in TaskRun.__table__.indexes if idx.name == "ix_task_runs_run_key"
    )
    assert index.unique is True


def test_task_run_has_dispatch_truth_columns_and_indexes() -> None:
    columns = TaskRun.__table__.columns
    assert "priority" in columns
    assert "trigger_slot" in columns
    assert "trigger_id" in columns
    assert "retry_of_run_id" in columns
    assert "retry_of_task_id" in columns
    assert any(
        index.name == "ix_task_runs_definition_trigger_slot"
        for index in TaskRun.__table__.indexes
    )
    assert any(
        index.name == "ix_task_runs_retry_of_run_id"
        for index in TaskRun.__table__.indexes
    )
