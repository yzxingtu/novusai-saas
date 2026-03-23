from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_get_plugin_storage_uses_tenant_context_and_namespace(load_plugin_backend_module, monkeypatch: pytest.MonkeyPatch) -> None:
    storage_access = load_plugin_backend_module("runtime.storage_access")
    captured_paths: list[str] = []

    class FakeResolver:
        def __init__(self, _db) -> None:
            self.called_tenant_id = None

        async def resolve_context(self, tenant_id: int):
            self.called_tenant_id = tenant_id
            return "tenant", SimpleNamespace(driver="local"), True

        async def resolve_platform_config(self):
            return SimpleNamespace(driver="local")

    class FakeDriver:
        async def get(self, path: str):
            captured_paths.append(path)
            return b"payload"

        async def put(self, path: str, content, mime_type=None, **kwargs):
            captured_paths.append(path)
            return {"ok": True}

        async def delete(self, path: str):
            captured_paths.append(path)
            return True

        async def exists(self, path: str):
            captured_paths.append(path)
            return True

    monkeypatch.setattr(storage_access, "StorageConfigResolver", FakeResolver)
    monkeypatch.setattr(storage_access.storage_manager, "get_driver", lambda _config: FakeDriver())

    storage = await storage_access.get_plugin_storage(object(), tenant_id=12)
    await storage.put("artifact.bin", b"data")
    await storage.get("plugins/workflow-orchestration/already-prefixed.txt")

    assert captured_paths[0] == "plugins/workflow-orchestration/artifact.bin"
    assert captured_paths[1] == "plugins/workflow-orchestration/already-prefixed.txt"


@pytest.mark.asyncio
async def test_get_builder_capabilities_exposes_items(load_plugin_backend_module) -> None:
    service_module = load_plugin_backend_module("services.tenant_workflow_service")

    class FakeCtx:
        async def get_tenant_config(self, tenant_id: int):
            assert tenant_id == 2
            return {
                "simple_builder_enabled": True,
                "template_editor_enabled": False,
                "agentic_builder_enabled": True,
                "max_agentic_steps": 11,
            }

        async def get_config(self):
            return {"tenant_agentic_enabled_default": False}

    service = service_module.TenantWorkflowService(object(), 2, ctx=FakeCtx())
    payload = await service.get_builder_capabilities()

    assert payload["allowed_modes"] == ["deterministic", "hybrid", "agentic"]
    assert [item["code"] for item in payload["items"]] == [
        "tenant_simple_builder",
        "tenant_template_editor",
        "agentic_builder",
    ]
    assert payload["items"][2]["limit"] == 11


@pytest.mark.asyncio
async def test_get_tenant_run_detail_flattens_nested_payload(load_plugin_backend_module, monkeypatch: pytest.MonkeyPatch) -> None:
    service_module = load_plugin_backend_module("services.run_query_service")
    service = service_module.RunQueryService(object(), tenant_id=3)

    async def fake_get_run_detail(_run_id: int):
        return {
            "run": {
                "id": 4,
                "status": "waiting_approval",
                "workflow_name": "Weekly Follow-up",
                "trigger_source": "manual",
                "mode": "hybrid",
            },
            "node_runs": [
                {"id": 8, "status": "waiting_approval", "node_name": "Manager Approval"}
            ],
            "checkpoints": [{"id": 15}],
            "events": [{"id": "evt-1"}],
            "artifacts": [{"id": 16}],
            "execution_graph": {"nodes": [], "edges": []},
        }

    monkeypatch.setattr(service, "get_run_detail", fake_get_run_detail)

    payload = await service.get_tenant_run_detail(4)

    assert payload["node_runs"][0]["id"] == 8
    assert payload["artifacts"][0]["id"] == 16
    assert payload["approvals"][0]["status"] == "waiting_approval"
    assert payload["events"][0]["id"] == "evt-1"
    assert payload["contract_summary"] == "Weekly Follow-up / manual / hybrid"


@pytest.mark.asyncio
async def test_get_tenant_home_returns_frontend_ready_shape(load_plugin_backend_module, monkeypatch: pytest.MonkeyPatch) -> None:
    service_module = load_plugin_backend_module("services.run_query_service")
    service = service_module.RunQueryService(object(), tenant_id=5)

    counts = {
        ("runs", None): 12,
        ("runs", ("recovering", "running", "compensating")): 3,
        ("runs", ("paused", "waiting_approval", "waiting_human", "waiting_input")): 2,
        ("runs", ("failed", "partially_completed")): 1,
        ("workflows", ("published",)): 4,
        ("artifacts", ("ready",)): 5,
        ("runs", ("waiting_approval", "waiting_human")): 2,
    }

    async def fake_count_runs(criteria=None):
        key = tuple(sorted(criteria["status"])) if criteria else None
        return counts.get(("runs", key), 0)

    async def fake_count_workflows(criteria=None):
        key = tuple(sorted(criteria["status"])) if criteria else None
        return counts.get(("workflows", key), 0)

    async def fake_count_artifacts(criteria=None):
        key = tuple(sorted(criteria["status"])) if criteria else None
        return counts.get(("artifacts", key), 0)

    async def fake_recent_runs():
        return [SimpleNamespace(id=7)]

    async def fake_recent_artifacts():
        return [SimpleNamespace(id=9)]

    async def fake_serialize_run_record(_run, **kwargs):
        return {"id": 7, "status": "running", "workflow_name": "Ops"}

    async def fake_serialize_artifact_record(_artifact):
        return {"id": 9, "status": "ready", "title": "Artifact"}

    async def fake_highlighted_workflows(limit=4):
        assert limit == 4
        return [{"id": 3, "name": "Lead Enrichment"}]

    monkeypatch.setattr(service, "_count_runs", fake_count_runs)
    monkeypatch.setattr(service, "_count_workflows", fake_count_workflows)
    monkeypatch.setattr(service, "_count_artifacts", fake_count_artifacts)
    monkeypatch.setattr(service, "_recent_runs", fake_recent_runs)
    monkeypatch.setattr(service, "_recent_artifacts", fake_recent_artifacts)
    monkeypatch.setattr(service, "_serialize_run_record", fake_serialize_run_record)
    monkeypatch.setattr(service, "_serialize_artifact_record", fake_serialize_artifact_record)
    monkeypatch.setattr(service, "_highlighted_workflows", fake_highlighted_workflows)

    payload = await service.get_tenant_home(
        {"items": [{"code": "agentic_builder", "enabled": False}]}
    )

    assert payload["summary"]["pending_approvals"] == 2
    assert payload["latest_runs"][0]["id"] == 7
    assert payload["latest_artifacts"][0]["id"] == 9
    assert payload["highlighted_workflows"][0]["name"] == "Lead Enrichment"
    assert payload["builder_capabilities"][0]["code"] == "agentic_builder"
    assert payload["todos"][0]["category"] == "approval_todo"


@pytest.mark.asyncio
async def test_artifact_retention_uses_per_tenant_storage(load_plugin_backend_module, monkeypatch: pytest.MonkeyPatch) -> None:
    artifact_service_module = load_plugin_backend_module("services.artifact_service")

    # Fakes
    class FakeColumn:
        def is_not(self, _value):
            return self

        def __le__(self, _other):
            return self

    class FakeArtifactModel:
        expires_at = FakeColumn()
        tenant_id = None

    artifacts = [
        SimpleNamespace(id=1, tenant_id=10, storage_path="a.bin"),
        SimpleNamespace(id=2, tenant_id=None, storage_path="b.bin", run_id=20),
    ]
    runs = [SimpleNamespace(id=20, tenant_id=99)]

    class FakeResult:
        def __init__(self, data):
            self._data = data

        def scalars(self):
            return self

        def all(self):
            return self._data

        def scalar_one_or_none(self):
            return self._data[0] if self._data else None

    class FakeDB:
        def __init__(self):
            self.calls = 0

        async def execute(self, stmt):
            self.calls += 1
            # first call -> artifacts, second -> run lookup
            if self.calls == 1:
                return FakeResult(artifacts)
            return FakeResult(runs)

        async def flush(self):
            return None

    delete_calls: list[tuple[int | None, str]] = []

    class FakeStorage:
        def __init__(self, tenant_id):
            self.tenant_id = tenant_id

        async def delete(self, path: str):
            delete_calls.append((self.tenant_id, path))

    async def fake_get_plugin_storage(db, tenant_id=None):
        return FakeStorage(tenant_id)

    def fake_first_attr(obj, keys, default=None):
        for key in keys:
            if hasattr(obj, key):
                value = getattr(obj, key)
                if value is not None:
                    return value
        return default

    def fake_assign_model_values(obj, values: dict):
        for k, v in values.items():
            setattr(obj, k, v)

    # Patch runtime dependencies
    runtime_stub = {
        "executor": SimpleNamespace(create_event_instance=lambda *args, **kwargs: None),
        "model_access": SimpleNamespace(
            resolve_model=lambda name: FakeArtifactModel(),
            try_resolve_model=lambda name: SimpleNamespace(id="id", tenant_id="tenant_id") if name == "workflow_run" else None,
            first_attr=fake_first_attr,
            assign_model_values=fake_assign_model_values,
        ),
        "storage_access": SimpleNamespace(get_plugin_storage=fake_get_plugin_storage),
    }

    original_runtime = artifact_service_module._runtime
    original_select = artifact_service_module.select

    def fake_runtime(name: str):
        return runtime_stub[name]

    class FakeSelect:
        def where(self, *_args, **_kwargs):
            return self

    # select() is only used as an identity for FakeDB; bypass SQLAlchemy expectations
    monkeypatch.setattr(artifact_service_module, "select", lambda *_args, **_kwargs: FakeSelect())
    monkeypatch.setattr(artifact_service_module, "_runtime", fake_runtime)

    service = artifact_service_module.ArtifactService(FakeDB(), tenant_id=None)
    result = await service.cleanup_expired_artifacts()

    monkeypatch.setattr(artifact_service_module, "_runtime", original_runtime)
    monkeypatch.setattr(artifact_service_module, "select", original_select)

    assert set(delete_calls) == {(10, "a.bin"), (99, "b.bin")}
    assert result["processed_count"] == 2
    assert getattr(artifacts[0], "status") == "expired"
    assert getattr(artifacts[1], "status") == "expired"


@pytest.mark.asyncio
async def test_retry_run_handles_retry_scheduled_nodes(load_plugin_backend_module, monkeypatch: pytest.MonkeyPatch) -> None:
    recovery_service_module = load_plugin_backend_module("services.recovery_service")

    run = SimpleNamespace(status="failed", retry_count=0, id=7, last_heartbeat_at=None)
    nodes = [
        SimpleNamespace(status="retry_scheduled", attempt_no=1, id=1),
        SimpleNamespace(status="failed_retryable", attempt_no=0, id=2),
    ]

    class FakeErrors(Exception):
        pass

    runtime_stub = {
        "errors": SimpleNamespace(WorkflowConflictError=FakeErrors),
        "executor": SimpleNamespace(
            create_event_instance=lambda *args, **kwargs: None,
            synchronize_run_status=lambda _run, _nodes: "recovering",
            mark_run_status=lambda *args, **kwargs: None,
        ),
        "model_access": SimpleNamespace(
            first_attr=lambda obj, keys, default=None: getattr(obj, keys[0], default),
            assign_model_values=lambda obj, values: obj.__dict__.update(values),
        ),
        "serializer": SimpleNamespace(serialize_run=lambda run, node_runs=None: {"status": run.status, "nodes": node_runs}),
    }

    original_runtime = recovery_service_module._runtime

    def fake_runtime(name: str):
        return runtime_stub[name]

    monkeypatch.setattr(recovery_service_module, "_runtime", fake_runtime)

    class FakeDB:
        async def flush(self):
            return None

    service = recovery_service_module.RecoveryService(FakeDB(), tenant_id=None)
    service._get_run = AsyncMock(return_value=run)
    service._list_node_runs = AsyncMock(return_value=nodes)

    payload = await service.retry_run(7)

    monkeypatch.setattr(recovery_service_module, "_runtime", original_runtime)

    assert all(node.status == "ready" for node in nodes)
    assert all(node.attempt_no >= 1 for node in nodes)
    assert payload["status"] == "recovering"


@pytest.mark.asyncio
async def test_replay_run_reuses_original_version_and_snapshot(load_plugin_backend_module, monkeypatch: pytest.MonkeyPatch) -> None:
    recovery_service_module = load_plugin_backend_module("services.recovery_service")
    run_service_calls: dict[str, Any] = {}

    class FakeRunService:
        async def create_run_from_workflow(self, workflow_id: int, payload: dict[str, Any]):
            run_service_calls["workflow_id"] = workflow_id
            run_service_calls["payload"] = payload
            return {"ok": True}

    run = SimpleNamespace(
        id=3,
        workflow_id=10,
        workflow_version_id=55,
        entrypoint="manual",
        input_payload_json={"foo": "bar"},
        control_envelope_json={"workflow_snapshot": {"nodes": [{"id": "n1"}], "edges": [], "root_node_keys": ["n1"]}},
    )

    class FakeErrors(Exception):
        pass

    runtime_stub = {
        "errors": SimpleNamespace(WorkflowConflictError=FakeErrors),
        "model_access": SimpleNamespace(
            first_attr=lambda obj, keys, default=None: getattr(obj, keys[0], default)
        ),
    }

    original_runtime = recovery_service_module._runtime
    original_service = recovery_service_module._service

    def fake_runtime(name: str):
        return runtime_stub[name]

    def fake_service(name: str):
        return SimpleNamespace(RunService=lambda db, tenant_id, actor_type, actor_id: FakeRunService())

    monkeypatch.setattr(recovery_service_module, "_runtime", fake_runtime)
    monkeypatch.setattr(recovery_service_module, "_service", fake_service)

    service = recovery_service_module.RecoveryService(object(), tenant_id=8, actor_type="admin", actor_id=1)
    service._get_run = AsyncMock(return_value=run)

    await service.replay_run(3)

    monkeypatch.setattr(recovery_service_module, "_runtime", original_runtime)
    monkeypatch.setattr(recovery_service_module, "_service", original_service)

    assert run_service_calls["workflow_id"] == 10
    assert run_service_calls["payload"]["workflow_version_id"] == 55
    assert run_service_calls["payload"]["workflow_snapshot"]["root_node_keys"] == ["n1"]
