"""
Database-driven dynamic scheduler / 数据库驱动的动态调度器

Loads periodic task configuration from DB and registers with Celery Beat scheduler.
从数据库加载定时任务配置，注册到 Celery Beat 调度
Supports runtime dynamic addition/removal of schedules.
支持运行时动态添加/移除调度
"""

from __future__ import annotations

import time

from celery import __version__ as celery_version
from celery.beat import PersistentScheduler
from celery.schedules import crontab

from app.celery_app import celery_app
from app.core.database import sync_session_factory
from app.core.logging import LogManager
from app.enums.common import ResourceScopeEnum
from app.models.system.task_definition import TaskDefinition
from app.models.system.tenant_task_binding import TenantTaskBinding
from app.models.tenant.tenant import Tenant
from app.models.tenant.tenant_plan import TenantPlan
from app.services.system.task_tenant_eligibility_service import (
    TaskTenantEligibilityService,
)
from app.tasks.task_scheduling import (
    ALL_TENANTS_TASK_DEFINITION_WRAPPER,
    TASK_DEFINITION_WRAPPER,
    TENANT_BINDING_WRAPPER,
    handler_supports_tenant_dispatch,
)

logger = LogManager.get_logger("queue")

PLATFORM_SCHEDULE_SCOPES = (
    ResourceScopeEnum.ADMIN_ONLY.value,
    ResourceScopeEnum.GLOBAL_SHARED.value,
    ResourceScopeEnum.ADMIN_AND_SELECTED_TENANTS.value,
)

ALL_TENANTS_DYNAMIC_SCHEDULE_SCOPES = (ResourceScopeEnum.ALL_TENANTS.value,)

EXPLICIT_BINDING_SCHEDULE_SCOPES = (
    ResourceScopeEnum.SELECTED_TENANTS.value,
    ResourceScopeEnum.ADMIN_AND_SELECTED_TENANTS.value,
)


def parse_cron_expression(expression: str) -> crontab:
    """Parse cron expression string to Celery crontab object / 将 cron 表达式字符串解析为 Celery crontab 对象"""
    parts = expression.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expression: {expression}")

    return crontab(
        minute=parts[0],
        hour=parts[1],
        day_of_month=parts[2],
        month_of_year=parts[3],
        day_of_week=parts[4],
    )


def _apply_schedule_config(
    entry: dict[str, object],
    *,
    schedule_type: str | None,
    cron_expression: str | None,
    interval_seconds: int | None,
) -> bool:
    if schedule_type == "cron" and cron_expression:
        entry["schedule"] = parse_cron_expression(cron_expression)
        return True
    if schedule_type == "interval" and interval_seconds:
        entry["schedule"] = float(interval_seconds)
        return True
    return False


def _build_schedule_options(definition: TaskDefinition) -> dict[str, object]:
    options: dict[str, object] = {"queue": "scheduled"}
    priority = getattr(definition, "default_priority", None)
    if priority is not None:
        options["priority"] = int(priority)
    return options


def _build_task_definition_schedule(
    definitions: list[TaskDefinition],
) -> dict[str, dict]:
    schedule: dict[str, dict] = {}
    for definition in definitions:
        entry: dict[str, object] = {
            "task": TASK_DEFINITION_WRAPPER,
            "args": (definition.id,),
            "kwargs": {},
            "options": _build_schedule_options(definition),
        }
        if not _apply_schedule_config(
            entry,
            schedule_type=definition.default_schedule_type,
            cron_expression=definition.default_cron_expression,
            interval_seconds=definition.default_interval_seconds,
        ):
            logger.warning(
                "Skipping task definition '{}' due to missing schedule config",
                definition.code,
            )
            continue
        schedule[f"task_definition:{definition.id}:{definition.code}"] = entry
    return schedule


def _build_tenant_task_binding_schedule(
    bindings: list[tuple[TenantTaskBinding, TaskDefinition]],
) -> dict[str, dict]:
    schedule: dict[str, dict] = {}
    for binding, definition in bindings:
        entry: dict[str, object] = {
            "task": TENANT_BINDING_WRAPPER,
            "args": (binding.id,),
            "kwargs": {},
            "options": _build_schedule_options(definition),
        }
        if not handler_supports_tenant_dispatch(definition.handler_path):
            logger.warning(
                "Skipping tenant task binding '{}' because handler '{}' is not tenant-aware",
                binding.id,
                definition.handler_path,
            )
            continue
        schedule_type = (
            binding.schedule_type_override or definition.default_schedule_type
        )
        cron_expression = (
            binding.cron_expression_override or definition.default_cron_expression
        )
        interval_seconds = (
            binding.interval_seconds_override
            if binding.interval_seconds_override is not None
            else definition.default_interval_seconds
        )
        if not _apply_schedule_config(
            entry,
            schedule_type=schedule_type,
            cron_expression=cron_expression,
            interval_seconds=interval_seconds,
        ):
            logger.warning(
                "Skipping tenant task binding '{}' due to missing schedule config",
                binding.id,
            )
            continue
        schedule[
            f"tenant_task_binding:{binding.id}:{binding.tenant_id}:{definition.code}"
        ] = entry
    return schedule


def _build_all_tenants_task_definition_schedule(
    definitions: list[TaskDefinition],
) -> dict[str, dict]:
    schedule: dict[str, dict] = {}
    for definition in definitions:
        entry: dict[str, object] = {
            "task": ALL_TENANTS_TASK_DEFINITION_WRAPPER,
            "args": (definition.id,),
            "kwargs": {},
            "options": _build_schedule_options(definition),
        }
        if not handler_supports_tenant_dispatch(definition.handler_path):
            logger.warning(
                "Skipping all-tenant task definition '{}' because handler '{}' is not tenant-aware",
                definition.code,
                definition.handler_path,
            )
            continue
        if not _apply_schedule_config(
            entry,
            schedule_type=definition.default_schedule_type,
            cron_expression=definition.default_cron_expression,
            interval_seconds=definition.default_interval_seconds,
        ):
            logger.warning(
                "Skipping all-tenant task definition '{}' due to missing schedule config",
                definition.code,
            )
            continue
        schedule[f"all_tenants_task_definition:{definition.id}:{definition.code}"] = (
            entry
        )
    return schedule


def load_task_schedules_from_db(
    *,
    return_none_on_error: bool = False,
) -> dict | None:
    """Load task schedules from DB and return schedule dict / 从数据库加载任务调度并返回调度配置字典"""
    session = sync_session_factory()
    try:
        task_definitions = (
            session.query(TaskDefinition)
            .filter(
                TaskDefinition.is_enabled.is_(True),  # noqa: E712
                TaskDefinition.is_deleted.is_(False),  # noqa: E712
                TaskDefinition.owner_tenant_id.is_(None),
                TaskDefinition.scope.in_(PLATFORM_SCHEDULE_SCOPES),
            )
            .all()
        )
        all_tenants_definitions = (
            session.query(TaskDefinition)
            .filter(
                TaskDefinition.is_enabled.is_(True),  # noqa: E712
                TaskDefinition.is_deleted.is_(False),  # noqa: E712
                TaskDefinition.owner_tenant_id.is_(None),
                TaskDefinition.scope.in_(ALL_TENANTS_DYNAMIC_SCHEDULE_SCOPES),
            )
            .all()
        )
        tenant_bindings = (
            session.query(TenantTaskBinding, TaskDefinition)
            .join(
                TaskDefinition,
                TaskDefinition.id == TenantTaskBinding.task_definition_id,
            )
            .join(Tenant, Tenant.id == TenantTaskBinding.tenant_id)
            .join(
                TenantPlan,
                TaskTenantEligibilityService.eligible_tenant_join_condition(),
            )
            .filter(
                TenantTaskBinding.is_enabled.is_(True),  # noqa: E712
                TenantTaskBinding.is_deleted.is_(False),  # noqa: E712
                TaskDefinition.is_enabled.is_(True),  # noqa: E712
                TaskDefinition.is_deleted.is_(False),  # noqa: E712
                TaskDefinition.scope.in_(EXPLICIT_BINDING_SCHEDULE_SCOPES),
                *TaskTenantEligibilityService.eligible_tenant_filters(),
            )
            .all()
        )
        return {
            **_build_task_definition_schedule(task_definitions),
            **_build_all_tenants_task_definition_schedule(all_tenants_definitions),
            **_build_tenant_task_binding_schedule(tenant_bindings),
        }
    except Exception as e:
        logger.error(f"Failed to load periodic tasks from DB: {e}")
        if return_none_on_error:
            return None
        return {}
    finally:
        session.close()


class ReloadingPersistentScheduler(PersistentScheduler):
    """
    Persistent beat scheduler with DB auto-refresh / 支持数据库自动重载的持久化 Beat 调度器

    Keeps the last good DB-driven schedule when startup or refresh hits a
    transient DB outage, and retries on later ticks.
    启动或重载时如果数据库短暂不可用，会保留上一份可用调度，并在后续 tick 中重试。
    """

    db_schedule_reload_interval = 60.0

    def __init__(self, *args, **kwargs):
        self._db_entry_names: set[str] = set()
        self._last_db_schedule_reload_at: float | None = None
        super().__init__(*args, **kwargs)

    def _open_or_recover_schedule_store(self):
        try:
            store = self._open_schedule()
            store.keys()
            return store
        except Exception as exc:  # pylint: disable=broad-except  # 损坏调度文件容错 / tolerate corrupt schedule
            return self._destroy_open_corrupted_schedule(exc)

    def _initialize_schedule_store(self) -> None:
        self._create_schedule()
        tz = self.app.conf.timezone
        stored_tz = self._store.get("tz")
        if stored_tz is not None and stored_tz != tz:
            self._store.clear()
        utc = self.app.conf.enable_utc
        stored_utc = self._store.get("utc_enabled")
        if stored_utc is not None and stored_utc != utc:
            self._store.clear()

        self._store.setdefault("entries", {})
        self.update_from_dict(self.app.conf.beat_schedule or {})
        self.install_default_entries(self.schedule)
        self._store.update(
            {
                "__version__": celery_version,
                "tz": tz,
                "utc_enabled": utc,
            }
        )
        self.sync()

    def setup_schedule(self) -> None:
        self._store = self._open_or_recover_schedule_store()
        try:
            self._initialize_schedule_store()
        except Exception as exc:  # pylint: disable=broad-except  # 启动阶段损坏文件容错 / tolerate corrupt schedule during initialization
            logger.warning(
                "Beat schedule store init failed, rebuilding persistent store: type={} error={}",
                type(exc).__name__,
                str(exc),
            )
            self._store = self._destroy_open_corrupted_schedule(exc)
            self._initialize_schedule_store()

        static_names = set(self.app.conf.beat_schedule or {})
        if "celery.backend_cleanup" in self.schedule:
            static_names.add("celery.backend_cleanup")
        self._db_entry_names = set(self.schedule) - static_names

        self.refresh_db_schedule(force=True)

    def tick(self, *args, **kwargs):
        self.refresh_db_schedule()
        return super().tick(*args, **kwargs)

    def refresh_db_schedule(self, *, force: bool = False) -> None:
        now = time.monotonic()
        if (
            not force
            and self._last_db_schedule_reload_at is not None
            and (now - self._last_db_schedule_reload_at)
            < self.db_schedule_reload_interval
        ):
            return

        self._last_db_schedule_reload_at = now

        db_schedule = load_task_schedules_from_db(return_none_on_error=True)
        if db_schedule is None:
            return

        static_schedule = dict(self.app.conf.beat_schedule or {})
        if "celery.backend_cleanup" in self.schedule:
            static_schedule["celery.backend_cleanup"] = self.schedule[
                "celery.backend_cleanup"
            ]

        merged_schedule = {**static_schedule, **db_schedule}
        previous_db_entry_names = set(self._db_entry_names)

        self.merge_inplace(merged_schedule)
        self._db_entry_names = set(db_schedule)
        self.old_schedulers = None
        self._heap = None
        self.sync()

        if force or previous_db_entry_names != self._db_entry_names:
            logger.info(
                "Beat DB schedule refreshed: db_tasks={} total={}",
                len(self._db_entry_names),
                len(self.schedule),
            )


def setup_task_schedules() -> None:
    """Register DB task schedules to Celery Beat / 将数据库任务调度注册到 Celery Beat。"""
    db_schedule = load_task_schedules_from_db() or {}

    beat_schedule = (
        {**celery_app.conf.beat_schedule} if celery_app.conf.beat_schedule else {}
    )
    beat_schedule.update(db_schedule)
    celery_app.conf.beat_schedule = beat_schedule

    logger.info(
        f"Periodic tasks loaded: {len(db_schedule)} from DB, {len(beat_schedule)} total"
    )


def refresh_schedule() -> None:
    """Refresh periodic task schedule from DB / 从数据库刷新定时任务调度"""
    setup_task_schedules()
    logger.info("Periodic task schedule refreshed from DB")
