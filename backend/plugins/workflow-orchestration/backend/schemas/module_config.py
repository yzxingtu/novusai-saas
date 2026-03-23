from typing import Any

from pydantic import Field

from app.core.base_schema import BaseCreateSchema, BaseResponseSchema


class ModuleGlobalSettingsSchema(BaseCreateSchema):
    max_parallel_runs: int = 20
    run_timeout_minutes: int = 30
    artifact_preview_budget: int = 16384
    tenant_agentic_enabled_default: bool = False


class ModuleTenantDefaultsSchema(BaseCreateSchema):
    simple_builder_enabled: bool = True
    template_editor_enabled: bool = True
    agentic_builder_enabled: bool = False
    max_agentic_steps: int = 8


class DeferredCapabilitySchema(BaseCreateSchema):
    code: str
    reason: str
    current_workaround: str


class ZeroHostBoundarySchema(BaseCreateSchema):
    storage_scope: str
    uses_host_backend_files: bool
    uses_host_frontend_files: bool
    uses_host_plugin_config_channel: bool
    notes: list[str] = Field(default_factory=list)
    deferred_capabilities: list[DeferredCapabilitySchema] = Field(default_factory=list)


class ModuleSettingsBundleSchema(BaseCreateSchema):
    global_settings: ModuleGlobalSettingsSchema
    tenant_defaults: ModuleTenantDefaultsSchema
    environment_profiles: list[dict[str, Any]] = Field(default_factory=list)
    zero_host_boundary: ZeroHostBoundarySchema


class UpdateModuleSettingsRequestSchema(BaseCreateSchema):
    global_settings: ModuleGlobalSettingsSchema | None = None
    tenant_defaults: ModuleTenantDefaultsSchema | None = None
    notes: str | None = None


class WorkflowModuleConfigSchema(BaseResponseSchema):
    config_scope: str
    config_key: str
    tenant_id: int | None = None
    version: int
    settings_json: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None
    created_by: int | None = None
    updated_by: int | None = None


__all__ = [
    "DeferredCapabilitySchema",
    "ModuleGlobalSettingsSchema",
    "ModuleSettingsBundleSchema",
    "ModuleTenantDefaultsSchema",
    "UpdateModuleSettingsRequestSchema",
    "WorkflowModuleConfigSchema",
    "ZeroHostBoundarySchema",
]

