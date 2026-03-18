"""
CRUD 代码生成器 Schema / Codegen Schema

定义代码生成配置的请求和响应数据结构
Defines codegen config API request and response data structures.
"""

import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.core.base_schema import BaseCreateSchema, BaseResponseSchema, BaseUpdateSchema

# config_json 最大体积（约 2MB）/ Max config_json size (~2MB)
CONFIG_JSON_MAX_BYTES = 2 * 1024 * 1024
# config_json 最大嵌套深度 / Max nesting depth
CONFIG_JSON_MAX_DEPTH = 30


def _validate_config_json_size(v: dict[str, Any]) -> dict[str, Any]:
    """校验 config_json 体积与深度，防 DoS / Validate size & depth to prevent DoS."""
    try:
        serialized = json.dumps(v)
    except (TypeError, ValueError):
        raise ValueError("config_json invalid: not JSON serializable")
    if len(serialized.encode("utf-8")) > CONFIG_JSON_MAX_BYTES:
        raise ValueError(
            f"config_json too large (max {CONFIG_JSON_MAX_BYTES // 1024}KB)"
        )

    def _depth(obj: Any, d: int) -> int:
        if d >= CONFIG_JSON_MAX_DEPTH:
            raise ValueError(f"config_json too deep (max {CONFIG_JSON_MAX_DEPTH})")
        if isinstance(obj, dict):
            return 1 + max((_depth(x, d + 1) for x in obj.values()), default=0)
        if isinstance(obj, (list, tuple)):
            return 1 + max((_depth(x, d + 1) for x in obj), default=0)
        return 0

    _depth(v, 0)
    return v


class CodegenConfigResponse(BaseResponseSchema):
    """代码生成配置响应 / Codegen config response."""

    name: str = Field(..., description="配置名称 / Config name")
    resource: str = Field(..., description="资源名 / Resource name (snake_case)")
    module: str = Field(..., description="模块归属 / Module affiliation")
    display_name: str = Field(..., description="中文显示名 / Display name (Chinese)")
    display_name_en: str = Field(..., description="英文显示名 / Display name (English)")
    status: str = Field(..., description="状态 / Status")
    config_json: dict[str, Any] = Field(
        default_factory=dict,
        description="完整配置 JSON / Full config JSON",
    )
    last_generated_at: datetime | None = Field(
        None, description="上次生成时间 / Last generated at"
    )
    generation_count: int = Field(0, description="生成次数 / Generation count")
    generated_files: dict[str, Any] | None = Field(
        None, description="上次生成文件清单 / Last generated files"
    )
    config_hash: str | None = Field(None, description="配置哈希 / Config hash")
    last_error: str | None = Field(None, description="上次生成错误 / Last error")

    @classmethod
    def from_model(cls, obj) -> "CodegenConfigResponse":
        """从模型创建响应 / Build response from model."""
        return cls(
            id=obj.id,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
            name=obj.name,
            resource=obj.resource,
            module=obj.module,
            display_name=obj.display_name,
            display_name_en=obj.display_name_en,
            status=obj.status,
            config_json=obj.config_json or {},
            last_generated_at=obj.last_generated_at,
            generation_count=obj.generation_count,
            generated_files=obj.generated_files,
            config_hash=obj.config_hash,
            last_error=obj.last_error,
        )


class CodegenConfigCreate(BaseCreateSchema):
    """创建代码生成配置请求 / Create codegen config request."""

    name: str = Field(..., min_length=1, max_length=100, description="配置名称")
    resource: str = Field(..., min_length=1, max_length=100, description="资源名")
    module: str = Field(..., min_length=1, max_length=50, description="模块")
    display_name: str = Field(..., min_length=1, max_length=100, description="中文显示名")
    display_name_en: str = Field(
        ..., min_length=1, max_length=100, description="英文显示名"
    )
    config_json: dict[str, Any] = Field(
        default_factory=dict,
        description="完整配置 JSON",
    )

    @field_validator("config_json")
    @classmethod
    def validate_config_json_size(cls, v: dict[str, Any]) -> dict[str, Any]:
        return _validate_config_json_size(v)


class CodegenConfigUpdate(BaseUpdateSchema):
    """更新代码生成配置请求 / Update codegen config request."""

    name: str | None = Field(None, min_length=1, max_length=100, description="配置名称")
    resource: str | None = Field(None, min_length=1, max_length=100, description="资源名")
    module: str | None = Field(None, min_length=1, max_length=50, description="模块")
    display_name: str | None = Field(
        None, min_length=1, max_length=100, description="中文显示名"
    )
    display_name_en: str | None = Field(
        None, min_length=1, max_length=100, description="英文显示名"
    )
    config_json: dict[str, Any] | None = Field(None, description="完整配置 JSON")

    @field_validator("config_json")
    @classmethod
    def validate_config_json_size(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        if v is None:
            return None
        return _validate_config_json_size(v)


class CodegenVersionItemSchema(BaseModel):
    """配置版本项 / Config version item."""

    id: int = Field(..., description="版本 ID / Version ID")
    config_id: int = Field(..., description="配置 ID / Config ID")
    created_at: str | None = Field(None, description="创建时间 ISO8601 / Created at")
    note: str | None = Field(None, description="备注 / Note")


# ============================================================
# Preview / Generate / Rollback / Validation / DB Introspect
# ============================================================


class PreviewFileSchema(BaseModel):
    """预览文件 / Preview file."""

    path: str = Field(..., description="文件路径 / File path")
    type: str = Field(..., description="create | modify | append / Action type")
    language: str = Field(default="", description="python | typescript | yaml / Language")
    content: str = Field(default="", description="文件内容 / File content")
    line_count: int = Field(default=0, description="行数 / Line count")
    original_content: str | None = Field(None, description="原始内容(modify时) / Original for modify")
    new_content: str | None = Field(None, description="新内容(modify时) / New for modify")
    diff: str | None = Field(None, description="diff 片段 / Diff snippet")


class PreviewSummarySchema(BaseModel):
    """预览汇总 / Preview summary."""

    create_count: int = Field(0, description="新建文件数 / Create count")
    modify_count: int = Field(0, description="修改文件数 / Modify count")
    backend_files: int = Field(0, description="后端文件数 / Backend count")
    frontend_files: int = Field(0, description="前端文件数 / Frontend count")
    total_lines: int = Field(0, description="总行数 / Total lines")


class PreviewResultSchema(BaseModel):
    """预览结果 / Preview result."""

    success: bool = Field(..., description="是否成功 / Success")
    error: str | None = Field(None, description="解析/生成失败时的错误信息 / Error when parse or generate fails")
    files: list[PreviewFileSchema] = Field(default_factory=list)
    summary: PreviewSummarySchema = Field(default_factory=PreviewSummarySchema)
    warnings: list[str] = Field(default_factory=list)
    conflicts: list[dict[str, str]] = Field(default_factory=list)


class GenerateResultSchema(BaseModel):
    """生成结果 / Generate result."""

    success: bool = Field(..., description="是否成功 / Success")
    files_created: list[str] = Field(default_factory=list)
    files_modified: list[str] = Field(default_factory=list)
    conflicts: list[dict[str, str]] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    backup_dir: str | None = Field(None)
    migration: dict[str, Any] | None = Field(None, description="auto_migrate 执行结果 / auto_migrate result")


class RollbackResultSchema(BaseModel):
    """回滚结果 / Rollback result."""

    success: bool = Field(..., description="是否成功 / Success")
    files_deleted: list[str] = Field(default_factory=list)
    files_modified: list[str] = Field(default_factory=list)
    files_skipped: list[dict] = Field(default_factory=list)
    manual_steps: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class CodegenValidateBodySchema(BaseModel):
    """Validate 请求体 / Request body for validate."""

    config_json: dict[str, Any] = Field(
        default_factory=dict,
        description="完整配置 JSON / Full config JSON",
    )

    @field_validator("config_json")
    @classmethod
    def validate_config_json_size(cls, v: dict[str, Any]) -> dict[str, Any]:
        return _validate_config_json_size(v)


class CodegenPreviewBodySchema(BaseModel):
    """Preview / Preview Download 请求体 / Request body for preview."""

    config_json: dict[str, Any] = Field(
        default_factory=dict,
        description="完整配置 JSON / Full config JSON",
    )
    step: Literal["model", "controller", "frontend"] | None = Field(
        None, description="model | controller | frontend | None"
    )

    @field_validator("config_json")
    @classmethod
    def validate_config_json_size(cls, v: dict[str, Any]) -> dict[str, Any]:
        return _validate_config_json_size(v)


class CodegenGenerateBodySchema(BaseModel):
    """Generate 请求体 / Request body for generate."""

    config_id: int | None = Field(None, description="配置 ID / Config ID")
    config_json: dict[str, Any] | None = Field(
        None,
        description="完整配置 JSON（与 config_id 二选一）/ Full config JSON (alternative to config_id)",
    )
    force: bool = Field(False, description="强制覆盖已存在文件 / Force overwrite")
    auto_migrate: bool = Field(
        True,
        description="生成后自动执行 alembic autogenerate / Run alembic autogenerate after generate",
    )

    @field_validator("config_json")
    @classmethod
    def validate_config_json_size_when_present(
        cls, v: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        if v is not None:
            return _validate_config_json_size(v)
        return v


class ValidationErrorSchema(BaseModel):
    """校验错误 / Validation error."""

    code: str = Field(default="", description="错误码 / Error code")
    message: str = Field(..., description="错误消息 / Error message")
    path: str = Field(default="", description="配置路径 / Config path")
    field: str = Field(default="", description="字段名 / Field name")


class ValidationResultSchema(BaseModel):
    """校验结果 / Validation result."""

    valid: bool = Field(..., description="是否有效 / Valid")
    errors: list[ValidationErrorSchema] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class TableInfoSchema(BaseModel):
    """表信息 / Table info."""

    name: str = Field(..., description="表名 / Table name")
    comment: str | None = Field(None, description="注释 / Comment")
    row_count: int = Field(0, description="行数 / Row count")
    has_model: bool = Field(False, description="是否已有 ORM / Has ORM model")


class ColumnInfoSchema(BaseModel):
    """列信息(API) / Column info for API."""

    name: str = Field(..., description="列名 / Column name")
    type: str = Field(..., description="类型字符串 / Type string")
    nullable: bool = Field(False)
    default: str | None = Field(None)
    primary_key: bool = Field(False)
    unique: bool = Field(False)
    comment: str | None = Field(None)
    foreign_keys: list[dict] = Field(default_factory=list)
    suggested_config: dict[str, Any] = Field(default_factory=dict)


class TypeInfoSchema(BaseModel):
    """类型信息 / Type info."""

    type: str = Field(..., description="YAML 类型名 / YAML type name")
    python_type: str = Field(default="")
    ts_type: str = Field(default="")
    form_component: str = Field(default="")
    search_type: str | None = Field(None)


class ComponentInfoSchema(BaseModel):
    """组件信息 / Component info."""

    name: str = Field(..., description="组件名 / Component name")
    label: str = Field(default="", description="显示名 / Label")
    category: str = Field(default="", description="input | select | advanced / Category")


__all__ = [
    "CodegenConfigResponse",
    "CodegenConfigCreate",
    "CodegenConfigUpdate",
    "PreviewFileSchema",
    "PreviewResultSchema",
    "PreviewSummarySchema",
    "GenerateResultSchema",
    "RollbackResultSchema",
    "ValidationErrorSchema",
    "ValidationResultSchema",
    "TableInfoSchema",
    "ColumnInfoSchema",
    "TypeInfoSchema",
    "ComponentInfoSchema",
]
