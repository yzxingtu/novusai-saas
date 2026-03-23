from __future__ import annotations

from dataclasses import dataclass

from app.core.i18n import _


@dataclass(slots=True)
class WorkflowRuntimeError(Exception):
    message: str
    code: int = 4220
    status_code: int = 422

    def to_dict(self) -> dict[str, object]:
        return {
            "error": self.message,
            "code": self.code,
            "status_code": self.status_code,
        }


class WorkflowValidationError(WorkflowRuntimeError):
    def __init__(self, message: str | None = None) -> None:
        super().__init__(
            message=message or _("plugin.workflow-orchestration.error.invalid_request"),
            code=4001,
            status_code=400,
        )


class WorkflowNotFoundError(WorkflowRuntimeError):
    def __init__(self, message: str | None = None) -> None:
        super().__init__(
            message=message or _("plugin.workflow-orchestration.error.resource_not_found"),
            code=4040,
            status_code=404,
        )


class WorkflowPermissionError(WorkflowRuntimeError):
    def __init__(self, message: str | None = None) -> None:
        super().__init__(
            message=message or _("plugin.workflow-orchestration.error.permission_denied"),
            code=4030,
            status_code=403,
        )


class WorkflowDependencyError(WorkflowRuntimeError):
    def __init__(self, message: str | None = None) -> None:
        super().__init__(
            message=message
            or _("plugin.workflow-orchestration.error.runtime_dependency_missing"),
            code=5001,
            status_code=500,
        )


class WorkflowConflictError(WorkflowRuntimeError):
    def __init__(self, message: str | None = None) -> None:
        super().__init__(
            message=message or _("plugin.workflow-orchestration.error.invalid_state"),
            code=4220,
            status_code=422,
        )
