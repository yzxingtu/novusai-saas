from __future__ import annotations

from functools import lru_cache
from typing import Any

from sqlalchemy.inspection import inspect as sa_inspect

from app.plugins.module_loader import load_plugin_module

PLUGIN_NAME = "workflow-orchestration"

MODEL_SPECS: dict[str, tuple[tuple[str, str], ...]] = {
    "workflow_template": (
        ("models", "WorkflowTemplate"),
        ("models.workflow_template", "WorkflowTemplate"),
        ("models.template", "WorkflowTemplate"),
    ),
    "workflow_template_version": (
        ("models", "WorkflowTemplateVersion"),
        ("models.workflow_template_version", "WorkflowTemplateVersion"),
        ("models.template", "WorkflowTemplateVersion"),
    ),
    "tenant_workflow": (
        ("models", "TenantWorkflow"),
        ("models.runtime", "TenantWorkflow"),
        ("models.tenant_workflow", "TenantWorkflow"),
    ),
    "tenant_workflow_version": (
        ("models", "TenantWorkflowVersion"),
        ("models.runtime", "TenantWorkflowVersion"),
        ("models.tenant_workflow_version", "TenantWorkflowVersion"),
    ),
    "workflow_run": (
        ("models", "WorkflowRun"),
        ("models.runtime", "WorkflowRun"),
        ("models.workflow_run", "WorkflowRun"),
    ),
    "workflow_node_run": (
        ("models", "WorkflowNodeRun"),
        ("models.runtime", "WorkflowNodeRun"),
        ("models.workflow_node_run", "WorkflowNodeRun"),
    ),
    "execution_checkpoint": (
        ("models", "WorkflowCheckpoint"),
        ("models.runtime", "WorkflowCheckpoint"),
        ("models.execution_checkpoint", "ExecutionCheckpoint"),
        ("models.checkpoint", "ExecutionCheckpoint"),
    ),
    "execution_event": (
        ("models", "WorkflowEvent"),
        ("models.runtime", "WorkflowEvent"),
        ("models.execution_event", "ExecutionEvent"),
        ("models.event", "ExecutionEvent"),
    ),
    "execution_artifact": (
        ("models", "WorkflowArtifact"),
        ("models.runtime", "WorkflowArtifact"),
        ("models.execution_artifact", "ExecutionArtifact"),
        ("models.artifact", "ExecutionArtifact"),
    ),
}


def _errors():
    module = load_plugin_module(PLUGIN_NAME, "runtime.errors")
    if module is None:
        raise RuntimeError("workflow runtime errors module is unavailable")
    return module


@lru_cache(maxsize=32)
def resolve_model(model_key: str) -> type[Any]:
    for module_path, class_name in MODEL_SPECS.get(model_key, ()):
        module = load_plugin_module(PLUGIN_NAME, module_path)
        if module is None:
            continue
        model_cls = getattr(module, class_name, None)
        if model_cls is not None:
            return model_cls
    raise _errors().WorkflowDependencyError(
        f"Model contract '{model_key}' is unavailable for plugin '{PLUGIN_NAME}'",
    )


def try_resolve_model(model_key: str) -> type[Any] | None:
    try:
        return resolve_model(model_key)
    except Exception:
        return None


@lru_cache(maxsize=64)
def model_field_names(model_cls: type[Any]) -> set[str]:
    try:
        mapper = sa_inspect(model_cls)
        return {attr.key for attr in mapper.attrs}
    except Exception:
        return {
            name
            for name in dir(model_cls)
            if not name.startswith("_") and not callable(getattr(model_cls, name, None))
        }


def filter_model_values(model_cls: type[Any], values: dict[str, Any]) -> dict[str, Any]:
    allowed = model_field_names(model_cls)
    return {key: value for key, value in values.items() if key in allowed}


def instantiate_model(model_cls: type[Any], values: dict[str, Any]) -> Any:
    return model_cls(**filter_model_values(model_cls, values))


def assign_model_values(instance: Any, values: dict[str, Any]) -> Any:
    allowed = model_field_names(type(instance))
    for key, value in values.items():
        if key in allowed:
            setattr(instance, key, value)
    return instance


def first_attr(source: Any, candidates: tuple[str, ...], default: Any = None) -> Any:
    for name in candidates:
        if hasattr(source, name):
            return getattr(source, name)
    return default
