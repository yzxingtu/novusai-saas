"""Task scheduling scheduler tests."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.enums.common import ResourceScopeEnum
from app.tasks.scheduler import (
    _build_all_tenants_task_definition_schedule,
    PLATFORM_SCHEDULE_SCOPES,
    _build_task_definition_schedule,
    _build_tenant_task_binding_schedule,
    load_task_schedules_from_db,
)
from app.tasks.task_scheduling import (
    ALL_TENANTS_TASK_DEFINITION_WRAPPER,
    TASK_DEFINITION_WRAPPER,
    TENANT_BINDING_WRAPPER,
)


def test_build_task_definition_schedule_uses_wrapper_task() -> None:
    definition = SimpleNamespace(
        id=11,
        code="system.health",
        scope=ResourceScopeEnum.ADMIN_ONLY.value,
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
        handler_path="app.ai.rag.processor.process_document",
        default_schedule_type="interval",
        default_cron_expression=None,
        default_interval_seconds=600,
    )

    with patch("app.tasks.scheduler.handler_supports_tenant_dispatch", return_value=True):
        schedule = _build_tenant_task_binding_schedule([(binding, definition)])

    assert "tenant_task_binding:7:42:tenant.sync" in schedule
    entry = schedule["tenant_task_binding:7:42:tenant.sync"]
    assert entry["task"] == TENANT_BINDING_WRAPPER
    assert entry["args"] == (7,)


def test_build_all_tenants_task_definition_schedule_uses_runtime_fanout_wrapper() -> None:
    definition = SimpleNamespace(
        id=18,
        code="tenant.everyone",
        handler_path="app.ai.rag.processor.process_document",
        scope=ResourceScopeEnum.ALL_TENANTS.value,
        default_schedule_type="interval",
        default_cron_expression=None,
        default_interval_seconds=300,
    )

    with patch("app.tasks.scheduler.handler_supports_tenant_dispatch", return_value=True):
        schedule = _build_all_tenants_task_definition_schedule([definition])

    assert "all_tenants_task_definition:18:tenant.everyone" in schedule
    entry = schedule["all_tenants_task_definition:18:tenant.everyone"]
    assert entry["task"] == ALL_TENANTS_TASK_DEFINITION_WRAPPER
    assert entry["args"] == (18,)


def test_load_task_schedules_keeps_hybrid_platform_definitions_and_tenant_bindings() -> None:
    definition_query = MagicMock()
    definition_query.filter.return_value = definition_query
    definition_query.all.return_value = [
        SimpleNamespace(
            id=11,
            code="system.hybrid",
            handler_path="app.ai.rag.processor.process_document",
            scope=ResourceScopeEnum.ADMIN_AND_SELECTED_TENANTS.value,
            default_schedule_type="interval",
            default_cron_expression=None,
            default_interval_seconds=300,
        )
    ]

    all_tenants_query = MagicMock()
    all_tenants_query.filter.return_value = all_tenants_query
    all_tenants_query.all.return_value = []

    binding_query = MagicMock()
    binding_query.join.return_value = binding_query
    binding_query.filter.return_value = binding_query
    binding_query.all.return_value = [
        (
            SimpleNamespace(
                id=7,
                tenant_id=42,
                schedule_type_override=None,
                cron_expression_override=None,
                interval_seconds_override=None,
            ),
            SimpleNamespace(
                code="system.hybrid",
                handler_path="app.ai.rag.processor.process_document",
                scope=ResourceScopeEnum.ADMIN_AND_SELECTED_TENANTS.value,
                default_schedule_type="interval",
                default_cron_expression=None,
                default_interval_seconds=300,
            ),
        )
    ]

    session = MagicMock()
    session.query.side_effect = [definition_query, all_tenants_query, binding_query]

    with patch("app.tasks.scheduler.sync_session_factory", return_value=session), patch(
        "app.tasks.scheduler.handler_supports_tenant_dispatch",
        return_value=True,
    ):
        schedules = load_task_schedules_from_db()

    assert "task_definition:11:system.hybrid" in schedules
    assert "tenant_task_binding:7:42:system.hybrid" in schedules


def test_load_task_schedules_includes_all_tenants_definitions_without_bindings() -> None:
    definition_query = MagicMock()
    definition_query.filter.return_value = definition_query
    definition_query.all.return_value = []

    all_tenants_query = MagicMock()
    all_tenants_query.filter.return_value = all_tenants_query
    all_tenants_query.all.return_value = [
        SimpleNamespace(
            id=18,
            code="tenant.everyone",
            handler_path="app.ai.rag.processor.process_document",
            scope=ResourceScopeEnum.ALL_TENANTS.value,
            default_schedule_type="interval",
            default_cron_expression=None,
            default_interval_seconds=600,
        )
    ]

    binding_query = MagicMock()
    binding_query.join.return_value = binding_query
    binding_query.filter.return_value = binding_query
    binding_query.all.return_value = []

    session = MagicMock()
    session.query.side_effect = [definition_query, all_tenants_query, binding_query]

    with patch("app.tasks.scheduler.sync_session_factory", return_value=session), patch(
        "app.tasks.scheduler.handler_supports_tenant_dispatch",
        return_value=True,
    ):
        schedules = load_task_schedules_from_db()

    assert "all_tenants_task_definition:18:tenant.everyone" in schedules
def test_platform_schedule_scopes_match_current_platform_scopes() -> None:
    assert PLATFORM_SCHEDULE_SCOPES == (
        ResourceScopeEnum.ADMIN_ONLY.value,
        ResourceScopeEnum.GLOBAL_SHARED.value,
        ResourceScopeEnum.ADMIN_AND_SELECTED_TENANTS.value,
    )
