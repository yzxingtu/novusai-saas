"""AICallLog agent resource scope + strictly-zero validation tests"""

from app.models.ai.call_log import AICallLog
from app.schemas.ai.call_log import AICallLogResponse


def test_aicalllog_orm_has_agent_resource_scope() -> None:
    assert hasattr(AICallLog, "agent_resource_scope")
    assert not hasattr(AICallLog, "agent_distribution_mode")


def test_aicalllog_response_schema_has_agent_resource_scope() -> None:
    fields = AICallLogResponse.model_fields
    assert "agent_resource_scope" in fields
    assert "agent_distribution_mode" not in fields


def test_permission_endpoint_scope_alias() -> None:
    from app.enums.rbac import PermissionEndpointScope, PermissionScope

    assert PermissionEndpointScope is PermissionScope


def test_resource_scope_enum_has_five_canonical_values() -> None:
    from app.enums.common import ResourceScopeEnum

    expected = {"global_shared", "admin_only", "all_tenants", "admin_and_selected_tenants", "selected_tenants"}
    actual = {e.value for e in ResourceScopeEnum}
    assert actual == expected


def test_permission_scope_has_canonical_endpoint_values() -> None:
    from app.enums.rbac import PermissionScope

    expected = {"admin", "tenant", "user", "both"}
    actual = {e.value for e in PermissionScope}
    assert actual == expected
    assert not hasattr(PermissionScope, "ADMIN_AND_ALL")


def test_crud_executor_only_accepts_canonical_scopes() -> None:
    from app.ai.tools.executors.crud_executor import _RESOURCE_SCOPE_NORMALIZE, _VALID_RESOURCE_SCOPES

    for key, val in _RESOURCE_SCOPE_NORMALIZE.items():
        assert key == val, f"Alias mapping found: {key!r} -> {val!r}; only identity mappings allowed"
    assert _VALID_RESOURCE_SCOPES == frozenset(_RESOURCE_SCOPE_NORMALIZE.values())


def test_manifest_no_legacy_scope_mapping() -> None:
    import app.plugins.manifest as manifest

    assert not hasattr(manifest, "_PLUGIN_ENDPOINT_SCOPE_LEGACY")
