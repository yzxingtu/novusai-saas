from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


def _first_attr(source, candidates, default=None):
    for name in candidates:
        if hasattr(source, name):
            return getattr(source, name)
    return default


class _FakeColumn:
    def in_(self, _values):
        return self

    def is_not(self, _value):
        return self

    def __le__(self, _other):
        return self

    def __eq__(self, _other):
        return self


class _FakeQuery:
    def where(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self


class _FakeExecuteResult:
    def __init__(self, payload):
        self.payload = payload

    def scalars(self):
        return self

    def all(self):
        return self.payload

    def scalar_one_or_none(self):
        return self.payload


@pytest.mark.asyncio
async def test_replay_run_preserves_original_workflow_version_and_snapshot(
    load_plugin_backend_module,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service_module = load_plugin_backend_module("services.recovery_service")
    errors_module = load_plugin_backend_module("runtime.errors")
    service = service_module.RecoveryService(object(), tenant_id=9, actor_type="tenant_admin", actor_id=42)

    original_run = SimpleNamespace(
        id=81,
        workflow_id=18,
        workflow_version_id=77,
        entrypoint="workflow_run",
        input_payload_json={"topic": "renewal"},
        control_envelope_json={"workflow_snapshot": {"nodes": [{"id": "draft"}], "edges": []}},
    )

    monkeypatch.setattr(service, "_get_run", AsyncMock(return_value=original_run))

    captured: dict[str, object] = {}

    class FakeRunService:
        def __init__(self, _db, tenant_id, *, actor_type, actor_id) -> None:
            captured["tenant_id"] = tenant_id
            captured["actor_type"] = actor_type
            captured["actor_id"] = actor_id

        async def create_run_from_workflow(self, workflow_id: int, payload: dict[str, object]) -> dict[str, object]:
            captured["workflow_id"] = workflow_id
            captured["payload"] = payload
            return {"id": 901}

    monkeypatch.setattr(
        service_module,
        "_runtime",
        lambda name: (
            SimpleNamespace(first_attr=_first_attr)
            if name == "model_access"
            else errors_module
        ),
    )
    monkeypatch.setattr(
        service_module,
        "_service",
        lambda name: SimpleNamespace(RunService=FakeRunService) if name == "run_service" else None,
    )

    payload = await service.replay_run(81)

    assert payload["id"] == 901
    assert captured["workflow_id"] == 18
    assert captured["tenant_id"] == 9
    replay_payload = captured["payload"]
    assert replay_payload["workflow_version_id"] == 77
    assert replay_payload["workflow_snapshot"] == {"nodes": [{"id": "draft"}], "edges": []}
    assert replay_payload["parent_run_id"] == 81


@pytest.mark.asyncio
async def test_resolve_executable_version_keeps_preferred_version_id_when_snapshot_fallback_enabled(
    load_plugin_backend_module,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service_module = load_plugin_backend_module("services.run_service")

    class FakeVersionModel:
        id = _FakeColumn()
        workflow_id = _FakeColumn()
        version_no = _FakeColumn()
        is_published = _FakeColumn()

    class FakeDb:
        async def execute(self, _stmt):
            return _FakeExecuteResult(None)

    monkeypatch.setattr(service_module, "select", lambda *_args, **_kwargs: _FakeQuery())
    monkeypatch.setattr(
        service_module,
        "_runtime",
        lambda name: SimpleNamespace(
            try_resolve_model=lambda model_key: FakeVersionModel if model_key == "tenant_workflow_version" else None,
            first_attr=_first_attr,
        )
        if name == "model_access"
        else None,
    )

    service = service_module.RunService(FakeDb(), tenant_id=5)
    version, resolved_version_id = await service._resolve_executable_version(
        SimpleNamespace(id=18),
        preferred_version_id=77,
        allow_snapshot_fallback=True,
    )

    assert version is None
    assert resolved_version_id == 77


@pytest.mark.asyncio
async def test_resolve_executable_version_does_not_silently_fallback_to_latest_when_preferred_version_is_missing(
    load_plugin_backend_module,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service_module = load_plugin_backend_module("services.run_service")

    class FakeVersionModel:
        id = _FakeColumn()
        workflow_id = _FakeColumn()
        version_no = _FakeColumn()
        is_published = _FakeColumn()

    class FakeDb:
        async def execute(self, _stmt):
            return _FakeExecuteResult(None)

    monkeypatch.setattr(service_module, "select", lambda *_args, **_kwargs: _FakeQuery())
    monkeypatch.setattr(
        service_module,
        "_runtime",
        lambda name: SimpleNamespace(
            try_resolve_model=lambda model_key: FakeVersionModel if model_key == "tenant_workflow_version" else None,
            first_attr=_first_attr,
        )
        if name == "model_access"
        else None,
    )

    service = service_module.RunService(FakeDb(), tenant_id=5)
    version, resolved_version_id = await service._resolve_executable_version(
        SimpleNamespace(id=18),
        preferred_version_id=77,
        allow_snapshot_fallback=False,
    )

    assert version is None
    assert resolved_version_id is None


@pytest.mark.asyncio
async def test_dispatch_retryable_runs_processes_recovering_run_with_retry_scheduled_nodes(
    load_plugin_backend_module,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service_module = load_plugin_backend_module("services.recovery_service")

    class FakeRunModel:
        status = _FakeColumn()
        updated_at = object()
        id = object()
        tenant_id = object()

    class FakeDb:
        async def execute(self, _stmt):
            return _FakeExecuteResult([SimpleNamespace(id=51, status="recovering")])

    monkeypatch.setattr(service_module, "select", lambda *_args, **_kwargs: _FakeQuery())
    monkeypatch.setattr(
        service_module,
        "_runtime",
        lambda name: SimpleNamespace(
            resolve_model=lambda model_key: FakeRunModel if model_key == "workflow_run" else None,
            first_attr=_first_attr,
        )
        if name == "model_access"
        else None,
    )

    service = service_module.RecoveryService(FakeDb(), tenant_id=None, actor_type="system", actor_id=None)
    monkeypatch.setattr(service, "_list_node_runs", AsyncMock(return_value=[SimpleNamespace(status="retry_scheduled")]))
    retry_mock = AsyncMock(return_value={"id": 51})
    monkeypatch.setattr(service, "retry_run", retry_mock)

    payload = await service.dispatch_retryable_runs(limit=10)

    retry_mock.assert_awaited_once_with(51)
    assert payload["processed_count"] == 1
    assert payload["run_ids"] == [51]


@pytest.mark.asyncio
async def test_artifact_retention_cleans_artifacts_with_per_artifact_storage_context(
    load_plugin_backend_module,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service_module = load_plugin_backend_module("services.artifact_service")

    class FakeArtifactModel:
        id = _FakeColumn()
        expires_at = _FakeColumn()

    class FakeRunModel:
        id = _FakeColumn()

    artifact_a = SimpleNamespace(id=1, tenant_id=11, run_id=501, storage_path="artifact-a.bin", status="ready")
    artifact_b = SimpleNamespace(id=2, tenant_id=None, run_id=777, storage_uri="artifact://artifact-b.bin", status="ready")
    run_b = SimpleNamespace(id=777, tenant_id=22)

    class FakeDb:
        def __init__(self) -> None:
            self._results = [
                _FakeExecuteResult([artifact_a, artifact_b]),
                _FakeExecuteResult(run_b),
            ]
            self.added: list[object] = []

        async def execute(self, _stmt):
            return self._results.pop(0)

        def add(self, instance):
            self.added.append(instance)

        async def flush(self):
            return None

    delete_calls: list[tuple[int | None, str]] = []
    storage_requests: list[int | None] = []

    class FakeStorage:
        def __init__(self, tenant_id: int | None) -> None:
            self.tenant_id = tenant_id

        async def delete(self, path: str):
            delete_calls.append((self.tenant_id, path))
            return True

    monkeypatch.setattr(service_module, "select", lambda *_args, **_kwargs: _FakeQuery())
    monkeypatch.setattr(
        service_module,
        "_runtime",
        lambda name: {
            "model_access": SimpleNamespace(
                resolve_model=lambda model_key: FakeArtifactModel if model_key == "execution_artifact" else None,
                try_resolve_model=lambda model_key: FakeRunModel if model_key == "workflow_run" else None,
                first_attr=_first_attr,
                assign_model_values=lambda instance, values: [setattr(instance, key, value) for key, value in values.items()],
            ),
            "executor": SimpleNamespace(create_event_instance=lambda *_args, **_kwargs: None),
            "storage_access": SimpleNamespace(
                get_plugin_storage=AsyncMock(
                    side_effect=lambda _db, tenant_id=None: storage_requests.append(tenant_id) or FakeStorage(tenant_id)
                )
            ),
        }[name],
    )

    service = service_module.ArtifactService(FakeDb(), tenant_id=None)
    payload = await service.cleanup_expired_artifacts()

    assert payload["processed_count"] == 2
    assert payload["artifact_ids"] == [1, 2]
    assert artifact_a.status == "expired"
    assert artifact_b.status == "expired"
    assert storage_requests == [11, 22]
    assert delete_calls == [(11, "artifact-a.bin"), (22, "artifact-b.bin")]
