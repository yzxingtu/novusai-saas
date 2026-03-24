"""Task scheduling scheduler tests."""

from types import SimpleNamespace

from app.tasks.scheduler import (
    _build_task_definition_schedule,
    _build_tenant_task_binding_schedule,
)
from app.tasks.task_scheduling import (
    TASK_DEFINITION_WRAPPER,
    TENANT_BINDING_WRAPPER,
)


def test_build_task_definition_schedule_uses_wrapper_task() -> None:
    definition = SimpleNamespace(
        id=11,
        code="system.health",
        default_schedule_type="interval",
        default_cron_expression=None,
        default_interval_seconds=300,
    )

    schedule = _build_task_definition_schedule([definition])

    assert "task_definition:11:system.health" in schedule
    entry = schedule["task_definition:11:system.health"]
    assert entry["task"] == TASK_DEFINITION_WRAPPER
    assert entry["args"] == (11,)


def test_build_tenant_task_binding_schedule_prefers_override_values() -> None:
    binding = SimpleNamespace(
        id=7,
        tenant_id=42,
        schedule_type_override="cron",
        cron_expression_override="0 2 * * *",
        interval_seconds_override=None,
    )
    definition = SimpleNamespace(
        code="tenant.sync",
        default_schedule_type="interval",
        default_cron_expression=None,
        default_interval_seconds=600,
    )

    schedule = _build_tenant_task_binding_schedule([(binding, definition)])

    assert "tenant_task_binding:7:42:tenant.sync" in schedule
    entry = schedule["tenant_task_binding:7:42:tenant.sync"]
    assert entry["task"] == TENANT_BINDING_WRAPPER
    assert entry["args"] == (7,)
