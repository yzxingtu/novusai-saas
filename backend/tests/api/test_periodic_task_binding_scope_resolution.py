"""Periodic task binding scope resolution tests."""

from app.api.admin.periodic_tasks import AdminPeriodicTaskController


def test_resolve_binding_target_scope_preserves_explicit_current_scope() -> None:
    result = AdminPeriodicTaskController._resolve_binding_target_scope(
        current_scope="selected_tenants",
        requested_scope=None,
        tenant_ids=[1, 2],
    )

    assert result == "selected_tenants"


def test_resolve_binding_target_scope_infers_admin_selected_when_scope_omitted() -> None:
    result = AdminPeriodicTaskController._resolve_binding_target_scope(
        current_scope="admin_only",
        requested_scope=None,
        tenant_ids=[1, 2],
    )

    assert result == "admin_and_selected_tenants"
