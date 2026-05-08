"""Task scheduling scheduler tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.celery_app import celery_app
from app.enums.common import ResourceScopeEnum
from app.exceptions import BusinessException
from app.services.system.task_binding_service import TaskBindingService
from app.services.system.task_definition_service import TaskDefinitionService
from app.tasks.base import TenantTask, register_task
from app.tasks.scheduler import (
    PLATFORM_SCHEDULE_SCOPES,
    _build_all_tenants_task_definition_schedule,
    _build_task_definition_schedule,
    _build_tenant_task_binding_schedule,
    load_task_schedules_from_db,
)
from app.tasks.task_scheduling import (
    ALL_TENANTS_TASK_DEFINITION_WRAPPER,
    TASK_DEFINITION_WRAPPER,
    TENANT_BINDING_WRAPPER,
    find_invalid_handler_kwargs,
    run_task_definition,
)

_TEST_TENANT_HANDLER = "tests.tasks.accepts_tenant_only"

if _TEST_TENANT_HANDLER not in celery_app.tasks:

    @register_task(name=_TEST_TENANT_HANDLER, base=TenantTask)
    def _accepts_tenant_only(self, tenant_id: int) -> dict[str, int]:
        _ = self
        return {"tenant_id": tenant_id}


def test_build_task_definition_schedule_uses_wrapper_task() -> None:
    definition = SimpleNamespace(
        id=11,
        code="system.health",
        scope=ResourceScopeEnum.ADMIN_ONLY.value,
        default_schedule_type="interval",
        default_cron_expression=None,
        default_interval_seconds=300,
        default_priority=3,
    )

    schedule = _build_task_definition_schedule([definition])

    assert "task_definition:11:system.health" in schedule
    entry = schedule["task_definition:11:system.health"]
    assert entry["task"] == TASK_DEFINITION_WRAPPER
    assert entry["args"] == (11,)
    assert entry["options"] == {"queue": "scheduled", "priority": 3}


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
        default_priority=8,
    )

    with patch(
        "app.tasks.scheduler.handler_supports_tenant_dispatch", return_value=True
    ):
        schedule = _build_tenant_task_binding_schedule([(binding, definition)])

    assert "tenant_task_binding:7:42:tenant.sync" in schedule
    entry = schedule["tenant_task_binding:7:42:tenant.sync"]
    assert entry["task"] == TENANT_BINDING_WRAPPER
    assert entry["args"] == (7,)
    assert entry["options"] == {"queue": "scheduled", "priority": 8}


def test_build_all_tenants_task_definition_schedule_uses_runtime_fanout_wrapper() -> (
    None
):
    definition = SimpleNamespace(
        id=18,
        code="tenant.everyone",
        handler_path="app.ai.rag.processor.process_document",
        scope=ResourceScopeEnum.ALL_TENANTS.value,
        default_schedule_type="interval",
        default_cron_expression=None,
        default_interval_seconds=300,
        default_priority=2,
    )

    with patch(
        "app.tasks.scheduler.handler_supports_tenant_dispatch", return_value=True
    ):
        schedule = _build_all_tenants_task_definition_schedule([definition])

    assert "all_tenants_task_definition:18:tenant.everyone" in schedule
    entry = schedule["all_tenants_task_definition:18:tenant.everyone"]
    assert entry["task"] == ALL_TENANTS_TASK_DEFINITION_WRAPPER
    assert entry["args"] == (18,)
    assert entry["options"] == {"queue": "scheduled", "priority": 2}


def test_load_task_schedules_keeps_hybrid_platform_definitions_and_tenant_bindings() -> (
    None
):
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

    with (
        patch("app.tasks.scheduler.sync_session_factory", return_value=session),
        patch(
            "app.tasks.scheduler.handler_supports_tenant_dispatch",
            return_value=True,
        ),
    ):
        schedules = load_task_schedules_from_db()

    assert "task_definition:11:system.hybrid" in schedules
    assert "tenant_task_binding:7:42:system.hybrid" in schedules
    assert binding_query.join.call_count >= 2


def test_load_task_schedules_includes_all_tenants_definitions_without_bindings() -> (
    None
):
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

    with (
        patch("app.tasks.scheduler.sync_session_factory", return_value=session),
        patch(
            "app.tasks.scheduler.handler_supports_tenant_dispatch",
            return_value=True,
        ),
    ):
        schedules = load_task_schedules_from_db()

    assert "all_tenants_task_definition:18:tenant.everyone" in schedules


def test_platform_schedule_scopes_match_current_platform_scopes() -> None:
    assert tuple(PLATFORM_SCHEDULE_SCOPES) == (
        ResourceScopeEnum.ADMIN_ONLY.value,
        ResourceScopeEnum.GLOBAL_SHARED.value,
        ResourceScopeEnum.ADMIN_AND_SELECTED_TENANTS.value,
    )


def test_registered_handler_kwargs_contract_rejects_unknown_kwargs() -> None:
    invalid_kwargs = find_invalid_handler_kwargs(
        "app.tasks.recycle_bin.cleanup_recycle_bin",
        {"retention_days": 30, "module_retention_days": 30},
    )

    assert invalid_kwargs == ["retention_days"]


def test_handler_kwargs_contract_imports_registered_task_before_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _LazyTask:
        def run(self, module_retention_days: int | None = None) -> None:
            _ = module_retention_days

    task = _LazyTask()
    imported: list[str] = []

    def _import_module(module_path: str):
        imported.append(module_path)
        return object()

    get_task = MagicMock(side_effect=[None, task])
    monkeypatch.setattr(
        "app.tasks.task_scheduling.importlib.import_module",
        _import_module,
    )
    monkeypatch.setattr(celery_app.tasks, "get", get_task)

    invalid_kwargs = find_invalid_handler_kwargs(
        "app.tasks.recycle_bin.cleanup_recycle_bin",
        {"retention_days": 30, "module_retention_days": 30},
    )

    assert imported == ["app.tasks.recycle_bin"]
    assert invalid_kwargs == ["retention_days"]


def test_registered_handler_kwargs_contract_accepts_stage_kwargs() -> None:
    invalid_kwargs = find_invalid_handler_kwargs(
        "app.tasks.recycle_bin.cleanup_recycle_bin",
        {"module_retention_days": 30, "global_retention_days": 30},
    )

    assert invalid_kwargs == []


def test_run_task_definition_rejects_invalid_kwargs_before_handler_dispatch() -> None:
    definition_query = MagicMock()
    definition_query.filter.return_value = definition_query
    definition_query.first.return_value = SimpleNamespace(
        id=44,
        handler_path="app.tasks.recycle_bin.cleanup_recycle_bin",
        default_args=None,
        default_kwargs={"retention_days": 30},
        is_enabled=True,
    )
    session = MagicMock()
    session.query.return_value = definition_query
    send_task = MagicMock()

    with (
        patch("app.tasks.task_scheduling.sync_session_factory", return_value=session),
        patch("app.tasks.task_scheduling.celery_app.send_task", send_task),
    ):
        result = run_task_definition.run(44)

    assert result == {
        "dispatched": False,
        "reason": "handler_kwargs_invalid",
        "task_definition_id": 44,
        "handler_path": "app.tasks.recycle_bin.cleanup_recycle_bin",
        "invalid_kwargs": ["retention_days"],
    }
    send_task.assert_not_called()


def test_run_task_definition_rejects_unregistered_handler_before_dispatch() -> None:
    definition_query = MagicMock()
    definition_query.filter.return_value = definition_query
    definition_query.first.return_value = SimpleNamespace(
        id=47,
        handler_path="app.tasks.scheduled.clean_expired_task_logs",
        default_args=None,
        default_kwargs={},
        is_enabled=True,
    )
    session = MagicMock()
    session.query.return_value = definition_query
    send_task = MagicMock()

    with (
        patch("app.tasks.task_scheduling.sync_session_factory", return_value=session),
        patch("app.tasks.task_scheduling.celery_app.send_task", send_task),
    ):
        result = run_task_definition.run(47)

    assert result == {
        "dispatched": False,
        "reason": "handler_not_registered",
        "task_definition_id": 47,
        "handler_path": "app.tasks.scheduled.clean_expired_task_logs",
    }
    send_task.assert_not_called()


@pytest.mark.asyncio
async def test_trigger_now_rejects_invalid_kwargs_before_wrapper_dispatch() -> None:
    service = TaskDefinitionService(MagicMock())
    definition = SimpleNamespace(
        id=45,
        code="task.cleanup_recycle_bin.09fba947",
        handler_path="app.tasks.recycle_bin.cleanup_recycle_bin",
        owner_tenant_id=None,
        scope=ResourceScopeEnum.ADMIN_ONLY.value,
        default_kwargs={"retention_days": 30},
        default_schedule_type="interval",
        default_cron_expression=None,
        default_interval_seconds=300,
    )
    service.get_by_id = AsyncMock(return_value=definition)

    with (
        pytest.raises(BusinessException) as exc_info,
        patch(
            "app.services.system.task_definition_service.celery_app.send_task",
        ) as send_task,
    ):
        await service.trigger_now(45)

    assert "retention_days" in exc_info.value.message
    send_task.assert_not_called()


@pytest.mark.asyncio
async def test_trigger_now_rejects_unregistered_handler_before_wrapper_dispatch() -> (
    None
):
    service = TaskDefinitionService(MagicMock())
    definition = SimpleNamespace(
        id=48,
        code="task.clean_expired_task_logs.81d841c7",
        handler_path="app.tasks.scheduled.clean_expired_task_logs",
        owner_tenant_id=None,
        scope=ResourceScopeEnum.ADMIN_ONLY.value,
        default_kwargs={},
        default_schedule_type="interval",
        default_cron_expression=None,
        default_interval_seconds=300,
    )
    service.get_by_id = AsyncMock(return_value=definition)

    with pytest.raises(BusinessException) as exc_info:
        await service.trigger_now(48)

    assert "clean_expired_task_logs" in exc_info.value.message


@pytest.mark.asyncio
async def test_task_binding_rejects_invalid_effective_kwargs_before_write() -> None:
    db = MagicMock()
    service = TaskBindingService(db)
    definition = SimpleNamespace(
        id=46,
        scope=ResourceScopeEnum.SELECTED_TENANTS.value,
        handler_path=_TEST_TENANT_HANDLER,
        default_kwargs={"retention_days": 30},
        is_deleted=False,
    )
    db.get = AsyncMock(return_value=definition)
    service.repo.create = AsyncMock()

    with (
        patch(
            "app.services.system.task_binding_service.TaskTenantEligibilityService.resolve_tenant_eligibility",
            return_value=SimpleNamespace(is_eligible=True, reason=None),
        ),
        pytest.raises(BusinessException) as exc_info,
    ):
        await service.upsert_tenant_binding(
            46,
            7,
            {"is_enabled": True},
        )

    assert "retention_days" in exc_info.value.message
    service.repo.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_task_binding_rejects_unregistered_handler_before_write() -> None:
    db = MagicMock()
    service = TaskBindingService(db)
    definition = SimpleNamespace(
        id=49,
        scope=ResourceScopeEnum.SELECTED_TENANTS.value,
        handler_path="app.tasks.scheduled.clean_expired_task_logs",
        default_kwargs={},
        is_deleted=False,
    )
    db.get = AsyncMock(return_value=definition)
    service.repo.create = AsyncMock()

    with (
        patch(
            "app.services.system.task_binding_service.TaskTenantEligibilityService.resolve_tenant_eligibility",
            return_value=SimpleNamespace(is_eligible=True, reason=None),
        ),
        pytest.raises(BusinessException) as exc_info,
    ):
        await service.upsert_tenant_binding(
            49,
            7,
            {"is_enabled": True},
        )

    assert "clean_expired_task_logs" in exc_info.value.message
    service.repo.create.assert_not_awaited()
