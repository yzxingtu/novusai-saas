from __future__ import annotations

from types import SimpleNamespace

import pytest


class DummyModel:
    id = None
    name = None

    def __init__(self, id=None, name=None):
        self.id = id
        self.name = name


def test_resolve_model_missing_contract_raises_dependency_error(load_plugin_backend_module, monkeypatch: pytest.MonkeyPatch) -> None:
    model_access = load_plugin_backend_module("runtime.model_access")
    errors = load_plugin_backend_module("runtime.errors")
    original_loader = model_access.load_plugin_module

    def fake_loader(plugin_name: str, dotted_path: str):
        if dotted_path == "runtime.errors":
            return original_loader(plugin_name, dotted_path)
        return None

    model_access.resolve_model.cache_clear()
    monkeypatch.setattr(model_access, "load_plugin_module", fake_loader)

    with pytest.raises(errors.WorkflowDependencyError):
        model_access.resolve_model("workflow_run")

    assert model_access.try_resolve_model("workflow_run") is None


def test_filter_and_assign_model_values_respects_known_fields(load_plugin_backend_module) -> None:
    model_access = load_plugin_backend_module("runtime.model_access")
    model_access.model_field_names.cache_clear()

    filtered = model_access.filter_model_values(
        DummyModel,
        {"id": 1, "name": "alpha", "unknown": "ignored"},
    )
    instance = model_access.instantiate_model(DummyModel, filtered)
    model_access.assign_model_values(instance, {"name": "beta", "missing": "noop"})

    assert filtered == {"id": 1, "name": "alpha"}
    assert instance.id == 1
    assert instance.name == "beta"


def test_resolve_runtime_models_from_models_runtime(load_plugin_backend_module) -> None:
    model_access = load_plugin_backend_module("runtime.model_access")
    model_access.resolve_model.cache_clear()

    assert model_access.resolve_model("tenant_workflow").__name__ == "TenantWorkflow"
    assert model_access.resolve_model("workflow_run").__name__ == "WorkflowRun"
    assert model_access.resolve_model("execution_artifact").__name__ == "WorkflowArtifact"


def test_serialize_run_and_artifact_add_contract_fields(load_plugin_backend_module) -> None:
    serializer = load_plugin_backend_module("runtime.serializer")

    run = SimpleNamespace(
        id=9,
        code="run-9",
        tenant_id=2,
        workflow_id=14,
        workflow_version_id=4,
        initiated_from="manual",
        mode="hybrid",
        status="running",
        started_by_type="tenant_admin",
        initiated_by=7,
        current_node_key="draft",
        input_payload_json={"topic": "weekly"},
        output_payload_json={"ok": True},
        cost_summary_json={"total_amount": 3.5},
        control_envelope_json={"workflow_snapshot": {"nodes": []}},
        risk_snapshot_json={"level": "medium"},
    )
    node_run = SimpleNamespace(status="running")

    artifact = SimpleNamespace(
        id=6,
        run_id=9,
        node_run_id=12,
        workflow_id=14,
        workflow_version_id=4,
        artifact_type="report",
        status="ready",
        name="Weekly Report",
        content_text="hello world",
        content_hash="abc123",
        visibility_scope="tenant_visible",
        feedback_summary={"decision": "adopted"},
    )

    run_payload = serializer.serialize_run(run, node_runs=[node_run])
    artifact_payload = serializer.serialize_artifact(artifact)

    assert run_payload["name"] == "run-9"
    assert run_payload["workflow_id"] == 14
    assert run_payload["workflow_version_id"] == 4
    assert run_payload["input_payload_json"] == {"topic": "weekly"}
    assert run_payload["can_pause"] is True
    assert run_payload["can_terminate"] is True
    assert run_payload["cost_amount"] == 3.5
    assert artifact_payload["preview_text"] == "hello world"
    assert artifact_payload["workflow_id"] == 14
    assert artifact_payload["hash"] == "abc123"
    assert artifact_payload["can_feedback"] is True
    assert artifact_payload["can_download"] is True
    assert artifact_payload["feedback_count"] == 1


def test_serialize_tenant_workflow_marks_builder_mode(load_plugin_backend_module) -> None:
    serializer = load_plugin_backend_module("runtime.serializer")

    workflow = SimpleNamespace(
        id=3,
        tenant_id=8,
        source_template_id=21,
        name="Follow-up",
        description="desc",
        mode="deterministic",
        status="draft",
        editable_level="managed_partial",
        is_simple_builder=True,
        summary_json={"risk_level": "medium"},
    )

    payload = serializer.serialize_tenant_workflow(workflow)

    assert payload["builder_mode"] == "copied_from_template"
    assert payload["risk_level"] == "medium"
