from __future__ import annotations

from sqlalchemy import asc, select

from app.core.i18n import _
from app.exceptions.base import ValidationException

from ..models.enums import ConfigScopeEnum
from ..models.presets import (
    DEFAULT_ENVIRONMENT_PROFILES,
    DEFAULT_GLOBAL_SETTINGS,
    DEFAULT_TENANT_DEFAULTS,
    DEFERRED_CAPABILITIES,
    MODULE_SETTINGS_KEY,
    ZERO_HOST_BOUNDARY,
)
from ..models.release import WorkflowEnvironment, WorkflowModuleConfig
from ..schemas.module_config import (
    ModuleGlobalSettingsSchema,
    ModuleSettingsBundleSchema,
    ModuleTenantDefaultsSchema,
    UpdateModuleSettingsRequestSchema,
    WorkflowModuleConfigSchema,
    ZeroHostBoundarySchema,
)
from ..schemas.release import WorkflowEnvironmentSchema


async def _ensure_environment_profiles(db) -> list[WorkflowEnvironment]:
    codes = [item["code"] for item in DEFAULT_ENVIRONMENT_PROFILES]
    existing_rows = (
        await db.execute(
            select(WorkflowEnvironment).where(
                WorkflowEnvironment.code.in_(codes),
                WorkflowEnvironment.is_deleted.is_(False),
            )
        )
    ).scalars().all()
    existing_map = {row.code: row for row in existing_rows}

    created = False
    for payload in DEFAULT_ENVIRONMENT_PROFILES:
        if payload["code"] in existing_map:
            continue
        row = WorkflowEnvironment(
            code=payload["code"],
            name=payload["name"],
            description=payload["description"],
            scope=payload["scope"],
            status=payload["status"],
            sort_order=payload["sort_order"],
            is_system=payload["is_system"],
            capability_boundary_json=payload["capability_boundary_json"],
            rollout_policy_json=payload["rollout_policy_json"],
        )
        db.add(row)
        created = True

    if created:
        await db.flush()

    rows = (
        await db.execute(
            select(WorkflowEnvironment)
            .where(WorkflowEnvironment.is_deleted.is_(False))
            .order_by(asc(WorkflowEnvironment.sort_order), asc(WorkflowEnvironment.id))
        )
    ).scalars().all()
    return rows


async def _get_or_create_config(
    db,
    *,
    config_scope: str,
    default_payload: dict,
    user_id: int | None = None,
) -> WorkflowModuleConfig:
    row = (
        await db.execute(
            select(WorkflowModuleConfig).where(
                WorkflowModuleConfig.config_scope == config_scope,
                WorkflowModuleConfig.config_key == MODULE_SETTINGS_KEY,
                WorkflowModuleConfig.tenant_id.is_(None),
                WorkflowModuleConfig.is_deleted.is_(False),
            )
        )
    ).scalar_one_or_none()
    if row:
        return row

    row = WorkflowModuleConfig(
        config_scope=config_scope,
        config_key=MODULE_SETTINGS_KEY,
        tenant_id=None,
        version=1,
        settings_json=default_payload,
        created_by=user_id,
        updated_by=user_id,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return row


async def get_settings_bundle(db) -> dict:
    environments = await _ensure_environment_profiles(db)
    global_row = await _get_or_create_config(
        db,
        config_scope=ConfigScopeEnum.GLOBAL.value,
        default_payload=DEFAULT_GLOBAL_SETTINGS,
    )
    tenant_row = await _get_or_create_config(
        db,
        config_scope=ConfigScopeEnum.TENANT_DEFAULT.value,
        default_payload=DEFAULT_TENANT_DEFAULTS,
    )

    bundle = ModuleSettingsBundleSchema(
        global_settings=ModuleGlobalSettingsSchema.model_validate(global_row.settings_json),
        tenant_defaults=ModuleTenantDefaultsSchema.model_validate(tenant_row.settings_json),
        environment_profiles=[
            WorkflowEnvironmentSchema.model_validate(item).model_dump()
            for item in environments
        ],
        zero_host_boundary=ZeroHostBoundarySchema(
            **ZERO_HOST_BOUNDARY,
            deferred_capabilities=DEFERRED_CAPABILITIES,
        ),
    )
    return bundle.model_dump()


async def update_settings(
    db,
    payload: UpdateModuleSettingsRequestSchema,
    *,
    user_id: int | None,
) -> dict:
    environments = await _ensure_environment_profiles(db)
    global_row = await _get_or_create_config(
        db,
        config_scope=ConfigScopeEnum.GLOBAL.value,
        default_payload=DEFAULT_GLOBAL_SETTINGS,
        user_id=user_id,
    )
    tenant_row = await _get_or_create_config(
        db,
        config_scope=ConfigScopeEnum.TENANT_DEFAULT.value,
        default_payload=DEFAULT_TENANT_DEFAULTS,
        user_id=user_id,
    )

    if payload.global_settings is None and payload.tenant_defaults is None:
        raise ValidationException(message=_("At least one settings section is required."))

    if payload.global_settings is not None:
        global_row.settings_json = payload.global_settings.model_dump()
        global_row.version += 1
        global_row.updated_by = user_id
        global_row.notes = payload.notes

    if payload.tenant_defaults is not None:
        tenant_row.settings_json = payload.tenant_defaults.model_dump()
        tenant_row.version += 1
        tenant_row.updated_by = user_id
        tenant_row.notes = payload.notes

    await db.flush()

    return ModuleSettingsBundleSchema(
        global_settings=ModuleGlobalSettingsSchema.model_validate(global_row.settings_json),
        tenant_defaults=ModuleTenantDefaultsSchema.model_validate(tenant_row.settings_json),
        environment_profiles=[
            WorkflowEnvironmentSchema.model_validate(item).model_dump()
            for item in environments
        ],
        zero_host_boundary=ZeroHostBoundarySchema(
            **ZERO_HOST_BOUNDARY,
            deferred_capabilities=DEFERRED_CAPABILITIES,
        ),
    ).model_dump()


async def get_settings_overview(db) -> dict:
    environments = await _ensure_environment_profiles(db)
    rows = (
        await db.execute(
            select(WorkflowModuleConfig).where(
                WorkflowModuleConfig.config_key == MODULE_SETTINGS_KEY,
                WorkflowModuleConfig.is_deleted.is_(False),
            )
        )
    ).scalars().all()
    serialized = [WorkflowModuleConfigSchema.model_validate(item).model_dump() for item in rows]
    return {
        "config_rows": serialized,
        "environment_count": len(environments),
        "zero_host_boundary": {
            **ZERO_HOST_BOUNDARY,
            "deferred_capabilities": DEFERRED_CAPABILITIES,
        },
    }
