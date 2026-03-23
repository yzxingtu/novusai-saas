from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest


class FakeColumn:
    def __eq__(self, _other: Any) -> "FakeColumn":
        return self

    def is_(self, _other: Any) -> "FakeColumn":
        return self

    def desc(self) -> "FakeColumn":
        return self


class BaseFakeModel:
    def __init__(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


class FakeWorkflow(BaseFakeModel):
    id = FakeColumn()
    tenant_id = FakeColumn()


class FakeWorkflowVersion(BaseFakeModel):
    id = FakeColumn()
    workflow_id = FakeColumn()
    is_published = FakeColumn()
    version_no = FakeColumn()


class FakeRun(BaseFakeModel):
    id = FakeColumn()
    tenant_id = FakeColumn()


class FakeNodeRun(BaseFakeModel):
    id = FakeColumn()
    run_id = FakeColumn()


class FakeCheckpoint(BaseFakeModel):
    id = FakeColumn()


class FakeEvent(BaseFakeModel):
    id = FakeColumn()


class FakeArtifact(BaseFakeModel):
    id = FakeColumn()


class FakeModelAccess:
    def __init__(self) -> None:
        self._models = {
            "tenant_workflow": FakeWorkflow,
            "tenant_workflow_version": FakeWorkflowVersion,
            "workflow_run": FakeRun,
            "workflow_node_run": FakeNodeRun,
            "execution_checkpoint": FakeCheckpoint,
            "execution_event": FakeEvent,
            "execution_artifact": FakeArtifact,
        }

    def resolve_model(self, model_key: str) -> type[Any]:
        return self._models[model_key]

    def try_resolve_model(self, model_key: str) -> type[Any] | None:
        return self._models.get(model_key)

    def instantiate_model(self, model_cls: type[Any], values: dict[str, Any]) -> Any:
        return model_cls(**values)

    def assign_model_values(self, instance: Any, values: dict[str, Any]) -> Any:
        for key, value in values.items():
            setattr(instance, key, value)
        return instance

    def first_attr(self, source: Any, candidates: tuple[str, ...], default: Any = None) -> Any:
        for name in candidates:
            if hasattr(source, name):
                return getattr(source, name)
        return default


class FakeResult:
    def __init__(self, value: Any) -> None:
        self._value = value

    def scalar_one_or_none(self) -> Any:
        return self._value

    def scalars(self) -> "FakeResult":
        return self

    def all(self) -> list[Any]:
        if isinstance(self._value, list):
            return self._value
        return [] if self._value is None else [self._value]


class FakeDB:
    def __init__(self, query_results: Sequence[Any]) -> None:
        self._query_results = list(query_results)
        self.added: list[Any] = []
        self._next_id = 1

    async def execute(self, _stmt: Any) -> FakeResult:
        value = self._query_results.pop(0) if self._query_results else None
        return FakeResult(value)

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        for obj in self.added:
            if getattr(obj, "id", None) is None or isinstance(getattr(type(obj), "id", None), FakeColumn):
                current_id = getattr(obj, "id", None)
                if isinstance(current_id, FakeColumn) or current_id is None:
                    setattr(obj, "id", self._next_id)
                    self._next_id += 1


class FakeSelect:
    def where(self, *_args: Any, **_kwargs: Any) -> "FakeSelect":
        return self

    def order_by(self, *_args: Any, **_kwargs: Any) -> "FakeSelect":
        return self

    def limit(self, _value: int) -> "FakeSelect":
        return self


def _build_workflow_snapshot(node_definitions: list[dict[str, Any]], edges: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "nodes": node_definitions,
        "edges": edges or [],
    }


def _wire_runtime(load_plugin_backend_module, monkeypatch: pytest.MonkeyPatch):
    errors_module = load_plugin_backend_module("runtime.errors")
    executor_module = load_plugin_backend_module("runtime.executor")
    graph_module = load_plugin_backend_module("runtime.graph")
    serializer_module = load_plugin_backend_module("runtime.serializer")
    state_machine_module = load_plugin_backend_module("runtime.state_machine")
    run_service_module = load_plugin_backend_module("services.run_service")

    model_access = FakeModelAccess()

    monkeypatch.setattr(executor_module, "_model_access", lambda: model_access)
    monkeypatch.setattr(executor_module, "_graph", lambda: graph_module)
    monkeypatch.setattr(executor_module, "_state_machine", lambda: state_machine_module)
    monkeypatch.setattr(executor_module, "_errors", lambda: errors_module)

    monkeypatch.setattr(serializer_module, "_model_access", lambda: model_access)
    monkeypatch.setattr(serializer_module, "_state_machine", lambda: state_machine_module)

    runtime_modules = {
        "errors": errors_module,
        "executor": executor_module,
        "graph": graph_module,
        "model_access": model_access,
        "serializer": serializer_module,
    }
    monkeypatch.setattr(run_service_module, "_runtime", lambda name: runtime_modules[name])
    monkeypatch.setattr(run_service_module, "select", lambda *_args, **_kwargs: FakeSelect())
    return run_service_module


def _build_workflow_records(snapshot: dict[str, Any], *, workflow_id: int = 5, version_id: int = 11) -> tuple[FakeWorkflow, FakeWorkflowVersion]:
    workflow = FakeWorkflow(
        id=workflow_id,
        tenant_id=8,
        name="Execution Flow",
        status="published",
        mode="deterministic",
        active_version_id=version_id,
        workflow_json={},
        summary_json={},
        builder_surface="tenant_template_editor",
    )
    workflow_version = FakeWorkflowVersion(
        id=version_id,
        workflow_id=workflow_id,
        version_no=1,
        status="published",
        is_published=True,
        snapshot_json=snapshot,
    )
    return workflow, workflow_version


@pytest.mark.asyncio
async def test_create_run_from_workflow_executes_deterministic_chain(
    load_plugin_backend_module,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_service_module = _wire_runtime(load_plugin_backend_module, monkeypatch)

    snapshot = _build_workflow_snapshot(
        [
            {"node_key": "start", "node_type": "system"},
            {"node_key": "finish", "node_type": "system", "depends_on": ["start"]},
        ],
        [{"source": "start", "target": "finish"}],
    )
    workflow, workflow_version = _build_workflow_records(snapshot)
    db = FakeDB([workflow, workflow_version])
    service = run_service_module.RunService(db, tenant_id=8, actor_type="tenant_admin", actor_id=23)

    payload = await service.create_run_from_workflow(
        workflow.id,
        {"input_payload": {"topic": "weekly-report"}},
    )

    runs = [item for item in db.added if isinstance(item, FakeRun)]
    node_runs = [item for item in db.added if isinstance(item, FakeNodeRun)]
    checkpoints = [item for item in db.added if isinstance(item, FakeCheckpoint)]
    events = [item for item in db.added if isinstance(item, FakeEvent)]
    artifacts = [item for item in db.added if isinstance(item, FakeArtifact)]

    assert len(runs) == 1
    assert payload["status"] == "completed"
    assert payload["current_node_key"] is None
    assert runs[0].status == "completed"
    assert runs[0].output_payload_json["mode"] == "deterministic_fallback"
    assert [node.status for node in node_runs] == ["succeeded", "succeeded"]
    assert node_runs[0].output_envelope_json["mode"] == "deterministic_fallback"
    assert node_runs[1].input_envelope_json["upstream_outputs"]["start"]["mode"] == "deterministic_fallback"
    assert any(item.checkpoint_type == "node_output_checkpoint" for item in checkpoints)
    assert any(item.event_type == "node_status_changed" and item.status_to == "succeeded" for item in events)
    assert len(artifacts) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("node_type", "expected_node_status", "expected_run_status", "expected_checkpoint_type", "expected_artifacts"),
    [
        ("approval", "waiting_approval", "waiting_approval", "approval_wait_checkpoint", 1),
        ("human_review", "waiting_approval", "waiting_approval", "manual_handover_checkpoint", 1),
        ("input", "waiting_input", "waiting_input", "node_input_checkpoint", 0),
    ],
)
async def test_create_run_from_workflow_waits_for_human_gates(
    load_plugin_backend_module,
    monkeypatch: pytest.MonkeyPatch,
    node_type: str,
    expected_node_status: str,
    expected_run_status: str,
    expected_checkpoint_type: str,
    expected_artifacts: int,
) -> None:
    run_service_module = _wire_runtime(load_plugin_backend_module, monkeypatch)

    snapshot = _build_workflow_snapshot(
        [
            {
                "node_key": "gate",
                "node_type": node_type,
                "config": {"required_fields": ["approval_comment"]},
            },
        ],
    )
    workflow, workflow_version = _build_workflow_records(snapshot, workflow_id=6, version_id=12)
    db = FakeDB([workflow, workflow_version])
    service = run_service_module.RunService(db, tenant_id=8, actor_type="tenant_admin", actor_id=7)

    payload = await service.create_run_from_workflow(
        workflow.id,
        {"input_payload": {"requested_by": "ops"}},
    )

    node_runs = [item for item in db.added if isinstance(item, FakeNodeRun)]
    checkpoints = [item for item in db.added if isinstance(item, FakeCheckpoint)]
    events = [item for item in db.added if isinstance(item, FakeEvent)]
    artifacts = [item for item in db.added if isinstance(item, FakeArtifact)]

    assert len(node_runs) == 1
    assert payload["status"] == expected_run_status
    assert payload["current_node_key"] == "gate"
    assert payload["node_counts"]["running"] == 0
    assert node_runs[0].status == expected_node_status
    assert node_runs[0].status != "running"
    assert node_runs[0].started_at is not None
    assert node_runs[0].ended_at is None
    assert any(item.checkpoint_type == expected_checkpoint_type for item in checkpoints)
    assert any(item.event_type == "node_status_changed" and item.status_to == expected_node_status for item in events)
    assert len([item for item in artifacts if getattr(item, "node_run_id", None) == node_runs[0].id]) == expected_artifacts
