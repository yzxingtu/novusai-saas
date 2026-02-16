"""
CRUD 代码生成器 — Dev-only API 控制器

仅在 APP_ENV=development 时注册。
端点:
  POST /admin/dev/crud/preview     — 预览生成代码（不写入磁盘）
  POST /admin/dev/crud/generate    — 生成并写入磁盘
  POST /admin/dev/crud/conflicts   — 检查文件冲突
  POST /admin/dev/crud/ddl         — DDL 预览
  GET  /admin/dev/crud/templates   — 列出配置模板
  GET  /admin/dev/crud/templates/{name} — 获取配置模板
  POST /admin/dev/crud/templates   — 保存配置模板
  PUT  /admin/dev/crud/templates/{name} — 更新配置模板
  DELETE /admin/dev/crud/templates/{name} — 删除配置模板
  GET  /admin/dev/crud/project-graph — 项目知识图谱（模型元数据）
"""

from __future__ import annotations

import asyncio
import json
import os
from fastapi import APIRouter, Body, Path, Query
from pydantic import BaseModel, Field, field_validator

from app.plugins.crud_generator.codegen.generator import CrudGenerator
from app.plugins.crud_generator.codegen.record_tracker import GenerationTimer, track_generation
from app.plugins.crud_generator.codegen.schemas import CrudConfig, ScopeType
from app.plugins.crud_generator.codegen.template_store import TemplateStore, _SAFE_NAME_RE
from app.plugins.crud_generator.codegen.writer import ConflictAction, CrudWriter
from app.core.deps import DbSession, SuperAdmin
from app.core.i18n import _
from app.core.response import success
from app.plugins.crud_generator.codegen.enums import CodegenOperationType
from app.rbac.decorators import auth_only

router = APIRouter(prefix="/dev/crud", tags=["Dev - CRUD Generator"])

# ============================================================
# 常量
# ============================================================

_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "..")
)


# ============================================================
# 请求/响应模型
# ============================================================


class PreviewRequest(BaseModel):
    config: CrudConfig
    include_content: bool = Field(False, description="是否在文件列表中包含文件内容")


class GenerateRequest(BaseModel):
    config: CrudConfig
    confirmed: bool = Field(False, description="是否已确认写入磁盘（false 时仅预览不写入）")
    conflict_action: ConflictAction = Field(ConflictAction.SKIP, description="冲突处理: skip / overwrite / merge")
    force_paths: list[str] = Field(default_factory=list, description="强制覆盖的文件路径列表")


class TemplateSaveRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="模板名称")
    description: str = Field("", description="模板描述")
    tags: list[str] = Field(default_factory=list, description="模板标签")
    config: CrudConfig

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not _SAFE_NAME_RE.match(v):
            raise ValueError(_("codegen.error.invalid_template_name"))
        return v


class TemplateUpdateRequest(BaseModel):
    description: str | None = Field(None, description="模板描述")
    tags: list[str] | None = Field(None, description="模板标签")
    config: CrudConfig | None = Field(None, description="配置（不传则保留原值）")


# ============================================================
# 辅助函数
# ============================================================


def _get_generator() -> CrudGenerator:
    return CrudGenerator()


def _get_writer() -> CrudWriter:
    return CrudWriter(_PROJECT_ROOT)


def _get_template_store() -> TemplateStore:
    return TemplateStore()


def _scope_warnings(config: CrudConfig) -> list[str]:
    """scope=both 时生成警告信息"""
    warnings: list[str] = []
    if config.scope == ScopeType.BOTH:
        warnings.append(
            _("codegen.warning.scope_both")
        )
        if config.has_status_toggle:
            warnings.append(
                _("codegen.warning.scope_both_status_toggle")
            )
    return warnings


# ============================================================
# 端点
# ============================================================


@router.post("/preview")
@auth_only
async def preview_generate(
    _admin: SuperAdmin,
    db: DbSession,
    req: PreviewRequest = Body(...),
) -> dict[str, object]:
    """预览生成代码（不写入磁盘）

    返回将要生成的文件列表、冲突信息、warnings 和 DDL 预览。
    每个文件包含 path/size/exists/is_i18n/operation 字段。
    当 include_content=true 时还包含 content 字段。
    """
    gen = _get_generator()
    writer = _get_writer()
    warnings = _scope_warnings(req.config)

    with GenerationTimer() as timer:
        files = gen.generate(req.config)
        preview_data = writer.preview(
            files,
            include_content=req.include_content,
            warnings=warnings,
        )

    await track_generation(
        db,
        config=req.config,
        files=files,
        operation_type=CodegenOperationType.PREVIEW.value,
        operator_id=_admin.id,
        operator_name=_admin.username,
        duration_ms=timer.duration_ms,
    )

    return success(data=preview_data)


@router.post("/generate")
@auth_only
async def generate_code(
    _admin: SuperAdmin,
    db: DbSession,
    req: GenerateRequest = Body(...),
) -> dict[str, object]:
    """生成代码并写入磁盘

    当 confirmed=false 时，仅返回预览结果不写入磁盘。
    当 confirmed=true 时，执行实际写入。
    """
    gen = _get_generator()
    writer = _get_writer()
    warnings = _scope_warnings(req.config)

    with GenerationTimer() as timer:
        files = gen.generate(req.config)

        # confirmed=false → 仅预览
        if not req.confirmed:
            preview_data = writer.preview(files, warnings=warnings)
            preview_data["confirmed"] = False
            return success(data=preview_data)

        # confirmed=true → 实际写入
        action = req.conflict_action

        result = writer.write(
            files,
            conflict_action=action,
            force_paths=set(req.force_paths) if req.force_paths else None,
        )

    result_data = result.to_dict()
    result_data["confirmed"] = True
    result_data["warnings"] = warnings

    await track_generation(
        db,
        config=req.config,
        files=files,
        operation_type=CodegenOperationType.GENERATE.value,
        operator_id=_admin.id,
        operator_name=_admin.username,
        write_result=result_data,
        duration_ms=timer.duration_ms,
    )

    return success(data=result_data)


@router.post("/conflicts")
@auth_only
async def check_conflicts(
    _admin: SuperAdmin,
    config: CrudConfig = Body(...),
) -> dict[str, object]:
    """检查文件冲突"""
    gen = _get_generator()
    writer = _get_writer()

    files = gen.generate(config)
    conflicts = writer.detect_conflicts(files)

    return success(data={
        "conflicts": [c.to_dict() for c in conflicts],
        "total": len(conflicts),
    })


@router.post("/ddl")
@auth_only
async def ddl_preview(
    _admin: SuperAdmin,
    config: CrudConfig = Body(...),
) -> dict[str, object]:
    """DDL SQL 预览"""
    ddl = CrudGenerator.generate_ddl_preview(config)
    return success(data={"sql": ddl})


# ============================================================
# 配置模板 CRUD
# ============================================================


@router.get("/templates")
@auth_only
async def list_templates(
    _admin: SuperAdmin,
) -> dict[str, object]:
    """列出所有配置模板"""
    store = _get_template_store()
    templates = await asyncio.to_thread(store.list_all)
    return success(data={"items": templates, "total": len(templates)})


@router.get("/templates/{name}")
@auth_only
async def get_template(
    _admin: SuperAdmin,
    name: str = Path(..., min_length=1),
) -> dict[str, object]:
    """获取配置模板详情"""
    store = _get_template_store()
    data = await asyncio.to_thread(store.get, name)
    return success(data=data)


@router.post("/templates")
@auth_only
async def save_template(
    _admin: SuperAdmin,
    req: TemplateSaveRequest = Body(...),
) -> dict[str, object]:
    """保存配置模板"""
    store = _get_template_store()
    data: dict[str, object] = {
        "name": req.name,
        "description": req.description,
        "tags": req.tags,
        "config": req.config.model_dump(mode="json"),
    }
    filepath = await asyncio.to_thread(store.save, req.name, data)
    return success(data={"name": req.name, "path": filepath})


@router.put("/templates/{name}")
@auth_only
async def update_template(
    _admin: SuperAdmin,
    name: str = Path(..., min_length=1),
    req: TemplateUpdateRequest = Body(...),
) -> dict[str, object]:
    """更新配置模板"""
    store = _get_template_store()
    await asyncio.to_thread(
        store.update, name,
        description=req.description, tags=req.tags, config=req.config,
    )
    return success(data={"name": name, "updated": True})


@router.delete("/templates/{name}")
@auth_only
async def delete_template(
    _admin: SuperAdmin,
    name: str = Path(..., min_length=1),
) -> dict[str, object]:
    """删除配置模板"""
    store = _get_template_store()
    await asyncio.to_thread(store.delete, name)
    return success(data={"name": name, "deleted": True})


# ============================================================
# 项目知识图谱
# ============================================================


@router.get("/project-graph")
@auth_only
async def project_graph(
    _admin: SuperAdmin,
    refresh: bool = Query(False, description="强制刷新缓存"),
) -> dict[str, object]:
    """项目知识图谱 — 返回所有 Model 元数据

    用于 AI 感知项目已有模块，避免生成重复表名。
    结果缓存在进程内存中，首次调用约 50ms。
    """
    from app.plugins.crud_generator.codegen.knowledge_graph import (
        get_graph_summary,
        get_project_graph_dict,
    )

    graph = get_project_graph_dict(force_refresh=refresh)
    summary = get_graph_summary(force_refresh=refresh)

    return success(data={
        "models": graph,
        "total": len(graph),
        "summary": summary,
    })
