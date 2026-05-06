"""Periodic task schema validation tests."""

import pytest
from pydantic import ValidationError

from app.schemas.system.periodic_task import (
    PeriodicTaskBindingSyncRequest,
    PeriodicTaskBindingUpdateRequest,
    PeriodicTaskCreateRequest,
    PeriodicTaskUpdateRequest,
)


def test_periodic_task_create_request_allows_selected_scope_without_tenant_ids() -> (
    None
):
    payload = PeriodicTaskCreateRequest.model_validate(
        {
            "name": "Tenant Pending",
            "task_path": "app.tasks.demo.handle_tenant",
            "schedule_type": "interval",
            "interval_seconds": 60,
            "scope": "selected_tenants",
        }
    )

    assert payload.scope == "selected_tenants"
    assert payload.tenant_ids == []


def test_periodic_task_update_request_rejects_invalid_scope() -> None:
    with pytest.raises(ValidationError, match="invalid scope"):
        PeriodicTaskUpdateRequest.model_validate({"scope": "platform_only"})


def test_periodic_task_binding_sync_request_rejects_invalid_scope() -> None:
    with pytest.raises(ValidationError, match="invalid scope"):
        PeriodicTaskBindingSyncRequest.model_validate(
            {"scope": "legacy_scope", "tenant_ids": [1, 2]}
        )


def test_periodic_task_binding_sync_request_keeps_tenant_ids_when_scope_is_omitted() -> (
    None
):
    payload = PeriodicTaskBindingSyncRequest.model_validate({"tenant_ids": [1, 2]})

    assert payload.scope is None
    assert payload.tenant_ids == [1, 2]


def test_periodic_task_binding_sync_request_accepts_binding_payloads() -> None:
    payload = PeriodicTaskBindingSyncRequest.model_validate(
        {
            "scope": "selected_tenants",
            "tenant_ids": [1],
            "bindings": [
                {
                    "tenant_id": 1,
                    "is_enabled": False,
                    "disabled_reason": "tenant paused",
                    "kwargs_override": {"mode": "quiet"},
                }
            ],
        }
    )

    assert payload.bindings[0].tenant_id == 1
    assert payload.bindings[0].is_enabled is False
    assert payload.bindings[0].kwargs_override == {"mode": "quiet"}


def test_periodic_task_binding_update_request_accepts_disable_reason_and_overrides() -> (
    None
):
    payload = PeriodicTaskBindingUpdateRequest.model_validate(
        {
            "is_enabled": False,
            "disabled_reason": "tenant opted out",
            "schedule_type_override": "interval",
            "interval_seconds_override": 300,
            "kwargs_override": {"mode": "quiet"},
            "config_override": {"limit": 3},
        }
    )

    assert payload.is_enabled is False
    assert payload.disabled_reason == "tenant opted out"
    assert payload.interval_seconds_override == 300
    assert payload.kwargs_override == {"mode": "quiet"}


def test_periodic_task_binding_update_request_rejects_invalid_schedule_type() -> None:
    with pytest.raises(ValidationError, match="invalid schedule_type_override"):
        PeriodicTaskBindingUpdateRequest.model_validate(
            {"schedule_type_override": "monthly"}
        )
