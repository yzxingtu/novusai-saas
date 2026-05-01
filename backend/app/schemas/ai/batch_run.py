"""
批量运行相关 Schema / Batch Run Schema

定义批量执行的请求和响应数据结构
Defines batch execution request and response data structures.
"""

from datetime import datetime

from pydantic import Field, model_validator

from app.core.base_schema import (
    BaseCreateSchema,
    TenantResponseSchema,
)
from app.core.i18n import _
from app.schemas.ai.retired_page_awareness import (
    ensure_no_retired_page_awareness_input,
)


class BatchRunCreate(BaseCreateSchema):
    """提交批量运行请求 / Submit batch run request."""

    items: list[dict] = Field(
        ...,
        min_length=1,
        max_length=1000,
        description=_("enum.batch_run.input_items"),
    )
    max_workers: int = Field(
        5, ge=1, le=20, description=_("enum.batch_run.max_workers")
    )

    @model_validator(mode="after")
    def reject_retired_page_awareness_inputs(self) -> "BatchRunCreate":
        for item in self.items:
            ensure_no_retired_page_awareness_input(item)
            for nested_key in ("variables", "input_variables"):
                nested = item.get(nested_key)
                if isinstance(nested, dict):
                    ensure_no_retired_page_awareness_input(nested)
        return self


class BatchRunResponse(TenantResponseSchema):
    """批量运行响应 / Batch run response schema."""

    agent_id: int = Field(..., description=_("enum.batch_run.agent_id"))
    status: str = Field(..., description=_("enum.batch_run.status"))
    total_items: int = Field(..., description=_("enum.batch_run.total_items"))
    completed_items: int = Field(..., description=_("enum.batch_run.completed_items"))
    failed_items: int = Field(..., description=_("enum.batch_run.failed_items"))
    max_workers: int = Field(..., description=_("enum.batch_run.max_workers"))
    results: list | None = Field(None, description=_("enum.batch_run.results"))
    errors: list | None = Field(None, description=_("enum.batch_run.errors"))
    started_at: datetime | None = Field(
        None, description=_("enum.batch_run.started_at")
    )
    completed_at: datetime | None = Field(
        None, description=_("enum.batch_run.completed_at")
    )
    created_by: int | None = Field(None, description=_("enum.batch_run.created_by"))


class BatchRunProgress(TenantResponseSchema):
    """批量运行进度（轻量） / Batch run progress (lightweight)."""

    status: str
    total_items: int
    completed_items: int
    failed_items: int
    started_at: datetime | None = None
    completed_at: datetime | None = None


__all__ = [
    "BatchRunCreate",
    "BatchRunResponse",
    "BatchRunProgress",
]
