from .enums import (
    BuilderSurfaceEnum,
    EnvironmentScopeEnum,
    EnvironmentStatusEnum,
)

DEFAULT_GLOBAL_SETTINGS = {
    "max_parallel_runs": 20,
    "run_timeout_minutes": 30,
    "artifact_preview_budget": 16384,
    "tenant_agentic_enabled_default": False,
}

DEFAULT_TENANT_DEFAULTS = {
    "simple_builder_enabled": True,
    "template_editor_enabled": True,
    "agentic_builder_enabled": False,
    "max_agentic_steps": 8,
}

DEFAULT_ENVIRONMENT_PROFILES = [
    {
        "code": "draft_env",
        "name": "Draft Environment",
        "description": "Design-time editing and draft validation.",
        "scope": EnvironmentScopeEnum.PLATFORM.value,
        "status": EnvironmentStatusEnum.PROVISIONED.value,
        "sort_order": 10,
        "is_system": True,
        "capability_boundary_json": {
            "automatic_triggers_allowed": False,
            "external_write_allowed": False,
            "target_surfaces": [BuilderSurfaceEnum.PLATFORM_WORKFLOW_STUDIO.value],
        },
        "rollout_policy_json": {
            "release_allowed": False,
            "observability_required": False,
        },
    },
    {
        "code": "test_env",
        "name": "Test Environment",
        "description": "Static validation, dry-run, and contract verification.",
        "scope": EnvironmentScopeEnum.PLATFORM.value,
        "status": EnvironmentStatusEnum.ACTIVATED.value,
        "sort_order": 20,
        "is_system": True,
        "capability_boundary_json": {
            "automatic_triggers_allowed": False,
            "external_write_allowed": False,
            "target_surfaces": [BuilderSurfaceEnum.PLATFORM_WORKFLOW_STUDIO.value],
        },
        "rollout_policy_json": {
            "release_allowed": False,
            "observability_required": True,
        },
    },
    {
        "code": "staging_env",
        "name": "Staging Environment",
        "description": "Pre-production validation and staged rollout rehearsal.",
        "scope": EnvironmentScopeEnum.PLATFORM.value,
        "status": EnvironmentStatusEnum.PILOT.value,
        "sort_order": 30,
        "is_system": True,
        "capability_boundary_json": {
            "automatic_triggers_allowed": True,
            "external_write_allowed": False,
            "target_surfaces": [BuilderSurfaceEnum.PLATFORM_WORKFLOW_STUDIO.value],
        },
        "rollout_policy_json": {
            "release_allowed": True,
            "observability_required": True,
        },
    },
    {
        "code": "prod_env",
        "name": "Production Environment",
        "description": "Formal production release and execution.",
        "scope": EnvironmentScopeEnum.PLATFORM.value,
        "status": EnvironmentStatusEnum.LIVE.value,
        "sort_order": 40,
        "is_system": True,
        "capability_boundary_json": {
            "automatic_triggers_allowed": True,
            "external_write_allowed": True,
            "target_surfaces": [BuilderSurfaceEnum.PLATFORM_WORKFLOW_STUDIO.value],
        },
        "rollout_policy_json": {
            "release_allowed": True,
            "observability_required": True,
        },
    },
    {
        "code": "tenant_sandbox",
        "name": "Tenant Sandbox",
        "description": "Tenant validation, sample runs, and training demonstrations.",
        "scope": EnvironmentScopeEnum.TENANT.value,
        "status": EnvironmentStatusEnum.PROVISIONED.value,
        "sort_order": 50,
        "is_system": True,
        "capability_boundary_json": {
            "automatic_triggers_allowed": False,
            "external_write_allowed": False,
            "target_surfaces": [
                BuilderSurfaceEnum.TENANT_TEMPLATE_EDITOR.value,
                BuilderSurfaceEnum.TENANT_SIMPLE_BUILDER.value,
            ],
        },
        "rollout_policy_json": {
            "release_allowed": False,
            "observability_required": False,
        },
    },
    {
        "code": "tenant_pilot",
        "name": "Tenant Pilot",
        "description": "Small-scale tenant pilot with real low-risk traffic.",
        "scope": EnvironmentScopeEnum.TENANT.value,
        "status": EnvironmentStatusEnum.PILOT.value,
        "sort_order": 60,
        "is_system": True,
        "capability_boundary_json": {
            "automatic_triggers_allowed": True,
            "external_write_allowed": False,
            "target_surfaces": [
                BuilderSurfaceEnum.TENANT_TEMPLATE_EDITOR.value,
                BuilderSurfaceEnum.TENANT_SIMPLE_BUILDER.value,
            ],
        },
        "rollout_policy_json": {
            "release_allowed": True,
            "observability_required": True,
        },
    },
    {
        "code": "tenant_prod",
        "name": "Tenant Production",
        "description": "Tenant formal production execution.",
        "scope": EnvironmentScopeEnum.TENANT.value,
        "status": EnvironmentStatusEnum.LIVE.value,
        "sort_order": 70,
        "is_system": True,
        "capability_boundary_json": {
            "automatic_triggers_allowed": True,
            "external_write_allowed": True,
            "target_surfaces": [
                BuilderSurfaceEnum.TENANT_TEMPLATE_EDITOR.value,
                BuilderSurfaceEnum.TENANT_SIMPLE_BUILDER.value,
            ],
        },
        "rollout_policy_json": {
            "release_allowed": True,
            "observability_required": True,
        },
    },
]

ZERO_HOST_BOUNDARY = {
    "storage_scope": "plugin_tables_only",
    "uses_host_backend_files": False,
    "uses_host_frontend_files": False,
    "uses_host_plugin_config_channel": False,
    "notes": [
        "All workflow-orchestration business state persists in plugin-owned px_workflow_orchestration_* tables.",
        "Host plugin config tables are not used for workflow design-time settings in this delivery.",
    ],
}

DEFERRED_CAPABILITIES = [
    {
        "code": "generic_host_plugin_settings_ui",
        "reason": "Using host plugin config storage would violate the plugin-owned persistence boundary.",
        "current_workaround": "Admin settings are exposed through plugin APIs backed by px_workflow_orchestration_module_configs.",
    },
    {
        "code": "hosted_trigger_execution_entrypoints",
        "reason": "Webhook, event, and automatic trigger execution need runtime handlers and background tasks.",
        "current_workaround": "Trigger records and snapshots are modeled now, but execution entrypoints are deferred.",
    },
]

MODULE_SETTINGS_KEY = "module_settings"

__all__ = [
    "DEFAULT_ENVIRONMENT_PROFILES",
    "DEFAULT_GLOBAL_SETTINGS",
    "DEFAULT_TENANT_DEFAULTS",
    "DEFERRED_CAPABILITIES",
    "MODULE_SETTINGS_KEY",
    "ZERO_HOST_BOUNDARY",
]
