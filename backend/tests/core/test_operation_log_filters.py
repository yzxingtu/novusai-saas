from __future__ import annotations

from app.repositories.system.operation_log_repository import OperationLogRepository


def test_operation_log_trace_id_is_allowed_for_admin_and_tenant_scope() -> None:
    repo = OperationLogRepository(db=None)  # type: ignore[arg-type]

    admin_fields = repo.get_allowed_fields("admin")
    tenant_fields = repo.get_allowed_fields("tenant")

    assert "trace_id" in admin_fields
    assert "trace_id" in tenant_fields
    assert "status_code" in admin_fields
    assert "status_code" in tenant_fields
