from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


def _first_attr(source, candidates, default=None):
    for name in candidates:
        if hasattr(source, name):
            return getattr(source, name)
    return default


def _assign_model_values(instance, values):
    for key, value in values.items():
        if hasattr(instance, key):
            setattr(instance, key, value)
    return instance


def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class _FakeDb:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.flush = AsyncMock()

    def add(self, value) -> None:
        self.added.append(value)


class _FakeRequest:
    def __init__(self, run_id: int, payload: dict[str, object]) -> None:
        self.method = "POST"
        self.path_params = {"run_id": str(run_id)}
        self._payload = payload

    async def json(self) -> dict[str, object]:
        return self._payload


class _FakeCtx:
    def get_current_tenant_id(self) -> int:
        return 9

    def get_current_user_id(self) -> int:
        return 42


def _serializer_payload(run, node_runs):
    return {
        "id": run.id,
        "status": run.status,
        "current_node_key": getattr(run, "current_node_key", None),
        "node_statuses": [node.status for node in node_runs],
        "node_inputs": [getattr(node, "input_envelope_json", {}) for node in node_runs],
        "node_metrics": [getattr(node, "metrics_json", {}) for node in node_runs],
    }


def _patch_recovery_runtime(service_module, monkeypatch: pytest.MonkeyPatch) -> None:
    runtime_modules = {
        "errors": SimpleNamespace(
            WorkflowValidationError=service_module._runtime("errors").WorkflowValidationError,
            WorkflowConflictError=service_module._runtime("errors").WorkflowConflictError,
            WorkflowNotFoundError=service_module._runtime("errors").WorkflowNotFoundError,
        ),
        "model_access": SimpleNamespace(
            first_attr=_first_attr,
            assign_model_values=_assign_model_values,
        ),
        "serializer": SimpleNamespace(serialize_run=_serializer_payload),
        "executor": SimpleNamespace(
            create_event_instance=lambda event_type, values: {"event_type": event_type, **values},
        ),
    }
    monkeypatch.setattr(service_module, "_runtime", lambda name: runtime_modules[name])


@pytest.mark.asyncio
async def test_tenant_resume_run_routes_waiting_action_payload_to_new_service(
    load_plugin_backend_module,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runs_module = load_plugin_backend_module("api.runs")
    errors_module = load_plugin_backend_module("runtime.errors")

    resume_mock = AsyncMock(return_value={"mode": "resume"})
    submit_mock = AsyncMock(return_value={"mode": "waiting_action"})

    class FakeRecoveryService:
        def __init__(self, _db, tenant_id, *, actor_type, actor_id) -> None:
            assert tenant_id == 9
            assert actor_type == "tenant_admin"
            assert actor_id == 42

        async def resume_run(self, run_id: int, checkpoint_id=None):
            return await resume_mock(run_id, checkpoint_id=checkpoint_id)

        async def submit_waiting_action(self, run_id: int, payload: dict[str, object]):
            return await submit_mock(run_id, payload)

    payload = {"action": "approve", "comment": "ship it"}
    http_module = SimpleNamespace(
        require_tenant_id=lambda ctx: ctx.get_current_tenant_id(),
        safe_int=_safe_int,
        read_json_body=AsyncMock(return_value=payload),
    )
    monkeypatch.setattr(
        runs_module,
        "_module",
        lambda dotted_path: {
            "runtime.errors": errors_module,
            "runtime.http": http_module,
            "services.recovery_service": SimpleNamespace(RecoveryService=FakeRecoveryService),
        }[dotted_path],
    )

    result = await runs_module.tenant_resume_run(_FakeRequest(15, payload), object(), _FakeCtx())

    submit_mock.assert_awaited_once_with(15, payload)
    resume_mock.assert_not_called()
    assert result["mode"] == "waiting_action"


@pytest.mark.asyncio
async def test_tenant_resume_run_keeps_plain_resume_path_for_checkpoint_only_payload(
    load_plugin_backend_module,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runs_module = load_plugin_backend_module("api.runs")
    errors_module = load_plugin_backend_module("runtime.errors")

    resume_mock = AsyncMock(return_value={"mode": "resume"})
    submit_mock = AsyncMock(return_value={"mode": "waiting_action"})

    class FakeRecoveryService:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        async def resume_run(self, run_id: int, checkpoint_id=None):
            return await resume_mock(run_id, checkpoint_id=checkpoint_id)

        async def submit_waiting_action(self, run_id: int, payload: dict[str, object]):
            return await submit_mock(run_id, payload)

    payload = {"checkpoint_id": 88}
    http_module = SimpleNamespace(
        require_tenant_id=lambda ctx: ctx.get_current_tenant_id(),
        safe_int=_safe_int,
        read_json_body=AsyncMock(return_value=payload),
    )
    monkeypatch.setattr(
        runs_module,
        "_module",
        lambda dotted_path: {
            "runtime.errors": errors_module,
            "runtime.http": http_module,
            "services.recovery_service": SimpleNamespace(RecoveryService=FakeRecoveryService),
        }[dotted_path],
    )

    result = await runs_module.tenant_resume_run(_FakeRequest(15, payload), object(), _FakeCtx())

    resume_mock.assert_awaited_once_with(15, checkpoint_id=88)
    submit_mock.assert_not_called()
    assert result["mode"] == "resume"


@pytest.mark.asyncio
async def test_submit_waiting_action_records_approval_decision(
    load_plugin_backend_module,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service_module = load_plugin_backend_module("services.recovery_service")
    _patch_recovery_runtime(service_module, monkeypatch)

    db = _FakeDb()
    service = service_module.RecoveryService(db, tenant_id=9, actor_type="tenant_admin", actor_id=42)
    run = SimpleNamespace(id=51, tenant_id=9, status="waiting_approval", current_node_key="approve-node")
    node = SimpleNamespace(
        id=101,
        run_id=51,
        node_key="approve-node",
        status="waiting_approval",
        input_envelope_json={"context": "keep"},
        metrics_json={"existing": True},
        error_summary="stale",
        started_at="old",
        ended_at="old",
    )
    monkeypatch.setattr(service, "_get_run", AsyncMock(return_value=run))
    monkeypatch.setattr(service, "_list_node_runs", AsyncMock(return_value=[node]))

    payload = await service.submit_waiting_action(51, {"action": "approve", "comment": "ship it"})

    assert payload["status"] == "running"
    assert node.status == "ready"
    assert node.input_envelope_json["context"] == "keep"
    assert node.input_envelope_json["decision"] == "approved"
    assert node.input_envelope_json["waiting_action"]["action"] == "approve"
    assert node.input_envelope_json["waiting_action"]["comment"] == "ship it"
    assert node.metrics_json["waiting_action"]["node_status"] == "waiting_approval"
    assert db.added[0]["event_type"] == "recovery_completed"
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_submit_waiting_action_records_human_handover_payload(
    load_plugin_backend_module,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service_module = load_plugin_backend_module("services.recovery_service")
    _patch_recovery_runtime(service_module, monkeypatch)

    db = _FakeDb()
    service = service_module.RecoveryService(db, tenant_id=9, actor_type="tenant_admin", actor_id=7)
    run = SimpleNamespace(id=61, tenant_id=9, status="waiting_human", current_node_key="manual-node")
    node = SimpleNamespace(
        id=202,
        run_id=61,
        node_key="manual-node",
        status="waiting_human",
        input_envelope_json={},
        metrics_json={},
        error_summary=None,
        started_at=None,
        ended_at=None,
    )
    monkeypatch.setattr(service, "_get_run", AsyncMock(return_value=run))
    monkeypatch.setattr(service, "_list_node_runs", AsyncMock(return_value=[node]))

    payload = await service.submit_waiting_action(
        61,
        {
            "action": "handover",
            "comment": "manual review completed",
            "input_payload": {"resolution": "retry"},
        },
    )

    assert payload["status"] == "running"
    assert node.status == "ready"
    assert node.input_envelope_json["submitted_input"] == {"resolution": "retry"}
    assert node.input_envelope_json["waiting_action"]["action"] == "handover"
    assert node.metrics_json["waiting_action"]["actor_id"] == 7


@pytest.mark.asyncio
async def test_submit_waiting_action_records_waiting_input_submission(
    load_plugin_backend_module,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service_module = load_plugin_backend_module("services.recovery_service")
    _patch_recovery_runtime(service_module, monkeypatch)

    db = _FakeDb()
    service = service_module.RecoveryService(db, tenant_id=9, actor_type="tenant_admin", actor_id=3)
    run = SimpleNamespace(id=71, tenant_id=9, status="waiting_input", current_node_key="input-node")
    node = SimpleNamespace(
        id=303,
        run_id=71,
        node_key="input-node",
        status="waiting_input",
        input_envelope_json={"existing": "value"},
        metrics_json={"attempt": 1},
        error_summary=None,
        started_at=None,
        ended_at=None,
    )
    monkeypatch.setattr(service, "_get_run", AsyncMock(return_value=run))
    monkeypatch.setattr(service, "_list_node_runs", AsyncMock(return_value=[node]))

    payload = await service.submit_waiting_action(
        71,
        {"input_payload": {"approved_budget": 1000, "currency": "CNY"}},
    )

    assert payload["status"] == "running"
    assert node.status == "ready"
    assert node.input_envelope_json["existing"] == "value"
    assert node.input_envelope_json["approved_budget"] == 1000
    assert node.input_envelope_json["currency"] == "CNY"
    assert node.input_envelope_json["waiting_action"]["input_payload"] == {"approved_budget": 1000, "currency": "CNY"}
    assert node.metrics_json["waiting_action"]["node_status"] == "waiting_input"


@pytest.mark.asyncio
async def test_submit_waiting_action_rejects_ambiguous_waiting_nodes_without_selector(
    load_plugin_backend_module,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service_module = load_plugin_backend_module("services.recovery_service")
    errors_module = load_plugin_backend_module("runtime.errors")
    _patch_recovery_runtime(service_module, monkeypatch)

    db = _FakeDb()
    service = service_module.RecoveryService(db, tenant_id=9, actor_type="tenant_admin", actor_id=3)
    run = SimpleNamespace(id=81, tenant_id=9, status="waiting_approval", current_node_key=None)
    node_a = SimpleNamespace(
        id=401,
        run_id=81,
        node_key="approve-a",
        status="waiting_approval",
        input_envelope_json={},
        metrics_json={},
        error_summary=None,
        started_at=None,
        ended_at=None,
    )
    node_b = SimpleNamespace(
        id=402,
        run_id=81,
        node_key="approve-b",
        status="waiting_approval",
        input_envelope_json={},
        metrics_json={},
        error_summary=None,
        started_at=None,
        ended_at=None,
    )
    monkeypatch.setattr(service, "_get_run", AsyncMock(return_value=run))
    monkeypatch.setattr(service, "_list_node_runs", AsyncMock(return_value=[node_a, node_b]))

    with pytest.raises(errors_module.WorkflowConflictError):
        await service.submit_waiting_action(81, {"action": "approve"})


@pytest.mark.asyncio
async def test_resume_run_keeps_legacy_waiting_resume_behavior(
    load_plugin_backend_module,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service_module = load_plugin_backend_module("services.recovery_service")
    _patch_recovery_runtime(service_module, monkeypatch)

    db = _FakeDb()
    service = service_module.RecoveryService(db, tenant_id=9, actor_type="tenant_admin", actor_id=11)
    run = SimpleNamespace(id=91, tenant_id=9, status="waiting_approval", current_node_key="approve-node")
    node = SimpleNamespace(
        id=501,
        run_id=91,
        node_key="approve-node",
        status="waiting_approval",
        input_envelope_json={},
        metrics_json={},
        error_summary=None,
        started_at="old",
        ended_at="old",
    )
    monkeypatch.setattr(service, "_get_run", AsyncMock(return_value=run))
    monkeypatch.setattr(service, "_list_node_runs", AsyncMock(return_value=[node]))
    monkeypatch.setattr(service, "_resolve_checkpoint_node_key", AsyncMock(return_value="resume-node"))

    payload = await service.resume_run(91, checkpoint_id=77)

    assert payload["status"] == "running"
    assert node.status == "ready"
    assert run.current_node_key == "resume-node"
    assert db.added[0]["payload_json"] == {"checkpoint_id": 77}
