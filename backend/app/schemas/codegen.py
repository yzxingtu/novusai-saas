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
    status: str = Field(
        ...,
        description="状态: draft=未生成, generated=文件已生成, applied=迁移已执行, rolled_back=已回滚 / Status lifecycle",
    )
    config_json: dict[str, Any] = Field(
        default_factory=dict,
        description="完整配置 JSON / Full config JSON",
    )
    last_generated_at: datetime | None = Field(
        None, description="上次生成时间 / Last generated at"
    )
    generation_count: int = Field(0, description="生成次数 / Generation count")
    generated_files: dict[str, Any] | None = Field(
        None,
        description="最近一次成功生成的文件摘要；成功回滚后清空 / Last successful generation file summary; cleared after rollback",
    )
    config_hash: str | None = Field(None, description="配置哈希 / Config hash")
    last_error: str | None = Field(None, description="上次生成错误 / Last error")
    manifest_present: bool = Field(
        False,
        description="仓库根目录 codegen_manifest.json 中是否存在可回滚条目 / Manifest entry exists for rollback",
    )
    delete_allowed: bool = Field(
        True,
        description="当前配置是否允许删除 / Whether delete is currently allowed",
    )
    delete_reason_code: str | None = Field(
        None,
        description="删除被阻止的原因码 / Reason code when delete is blocked",
    )
    delete_reason_message: str | None = Field(
        None,
        description="删除被阻止的提示文案 / Human-readable delete guard message",
    )

    @classmethod
    def from_model(
        cls,
        obj,
        *,
        manifest_present: bool = False,
        delete_allowed: bool = True,
        delete_reason_code: str | None = None,
        delete_reason_message: str | None = None,
    ) -> "CodegenConfigResponse":
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
            manifest_present=manifest_present,
            delete_allowed=delete_allowed,
            delete_reason_code=delete_reason_code,
            delete_reason_message=delete_reason_message,
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


class CodegenWorkbenchStatsSchema(BaseModel):
    """代码生成工作台统计 / Codegen workbench stats."""

    draft: int = Field(0, description="草稿数量 / Draft count")
    generated: int = Field(0, description="已生成数量 / Generated count")
    applied: int = Field(0, description="已应用数量 / Applied count")
    rollback: int = Field(0, description="可回滚数量 / Rollback-ready count")
    attention: int = Field(0, description="需关注数量 / Attention count")
    total: int = Field(0, description="总配置数 / Total config count")


class CodegenWorkbenchItemSchema(BaseModel):
    """工作台关注项 / Workbench focus item."""

    id: int = Field(..., description="配置 ID / Config ID")
    name: str = Field(..., description="配置名称 / Config name")
    resource: str = Field(..., description="资源名 / Resource")
    status: str = Field(..., description="状态 / Status")
    manifest_present: bool = Field(False, description="是否存在 manifest / Manifest exists")
    delete_allowed: bool = Field(True, description="是否允许删除 / Delete allowed")
    delete_reason_message: str | None = Field(
        None,
        description="删除阻断提示 / Delete guard message",
    )
    last_generated_at: datetime | None = Field(
        None,
        description="上次生成时间 / Last generated at",
    )
    generation_count: int = Field(0, description="生成次数 / Generation count")
    last_error: str | None = Field(None, description="最近错误 / Last error")


class CodegenWorkbenchSectionsSchema(BaseModel):
    """工作台各分区条目 / Workbench section items."""

    draft: list[CodegenWorkbenchItemSchema] = Field(default_factory=list)
    generated: list[CodegenWorkbenchItemSchema] = Field(default_factory=list)
    applied: list[CodegenWorkbenchItemSchema] = Field(default_factory=list)
    rollback: list[CodegenWorkbenchItemSchema] = Field(default_factory=list)
    attention: list[CodegenWorkbenchItemSchema] = Field(default_factory=list)


class CodegenWorkbenchSummarySchema(BaseModel):
    """代码生成工作台摘要 / Codegen workbench summary."""

    stats: CodegenWorkbenchStatsSchema = Field(default_factory=CodegenWorkbenchStatsSchema)
    sections: CodegenWorkbenchSectionsSchema = Field(
        default_factory=CodegenWorkbenchSectionsSchema
    )


# ============================================================
# 预览 / 生成 / 回滚 / 校验 / DB 内省 / Preview / Generate / Rollback / Validation / DB Introspect
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
    config_id: int | None = Field(None, description="配置 ID（未保存直接生成时新创建的）/ Config ID when created from unsaved config")
    resource: str | None = Field(None, description="资源名 / Resource name")
    module: str | None = Field(None, description="模块 / Module")
    table_name: str | None = Field(None, description="表名 / Table name")


class RollbackResultSchema(BaseModel):
    """回滚结果 / Rollback result."""

    success: bool = Field(..., description="是否成功 / Success")
    files_deleted: list[str] = Field(default_factory=list)
    files_modified: list[str] = Field(default_factory=list)
    files_skipped: list[dict] = Field(default_factory=list)
    manual_steps: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    migration_cleaned: bool = Field(
        False, description="是否已执行迁移回退并删除迁移文件 / Migration downgrade + file delete done"
    )


class CodegenValidateBodySchema(BaseModel):
    """Validate 请求体 / Request body for validate."""

    config_json: dict[str, Any] = Field(
        default_factory=dict,
        description="完整配置 JSON / Full config JSON",
    )
    mode: Literal["draft", "generate"] = Field(
        "generate",
        description="校验模式：draft=草稿保存，generate=生成前严格校验 / Validation mode",
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
    mode: Literal["draft", "generate"] = Field(
        "generate",
        description="本次校验使用的模式 / Validation mode used for this response",
    )


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


class PresetInfoSchema(BaseModel):
    """预设元数据 / Preset metadata."""

    name: str = Field(..., description="预设名 / Preset name")
    label_zh: str = Field(default="", description="中文名称 / Chinese label")
    label_en: str = Field(default="", description="英文名称 / English label")
    description_zh: str = Field(default="", description="中文描述 / Chinese description")
    description_en: str = Field(default="", description="英文描述 / English description")
    category: str = Field(default="", description="分类 / Category")
    tags: list[str] = Field(default_factory=list, description="标签 / Tags")
    recommended_for: list[str] = Field(default_factory=list, description="推荐场景 / Recommended use cases")
    sort_order: int = Field(default=999, description="排序 / Sort order")


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
    "PresetInfoSchema",
]
