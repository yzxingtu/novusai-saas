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
import re
from typing import Any

from fastapi import APIRouter, Body, Path, Query
from pydantic import BaseModel, Field, field_validator

from app.codegen.generator import CrudGenerator
from app.codegen.schemas import CrudConfig, ScopeType
from app.codegen.writer import ConflictAction, CrudWriter
from app.core.config import settings
from app.core.response import success, error
from app.core.deps import SuperAdmin

router = APIRouter(prefix="/dev/crud", tags=["Dev - CRUD Generator"])

# ============================================================
# 常量
# ============================================================

_TEMPLATES_STORAGE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "codegen",
    "config_templates",
)

_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "..")
)

_SAFE_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


# ============================================================
# 请求/响应模型
# ============================================================


class PreviewRequest(BaseModel):
    config: CrudConfig
    include_content: bool = Field(False, description="是否在文件列表中包含文件内容")


class GenerateRequest(BaseModel):
    config: CrudConfig
    confirmed: bool = Field(False, description="是否已确认写入磁盘（false 时仅预览不写入）")
    conflict_action: str = Field("skip", description="冲突处理: skip / overwrite / merge")
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
            raise ValueError("name must only contain letters, digits, hyphens, and underscores")
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


def _ensure_templates_dir() -> None:
    os.makedirs(_TEMPLATES_STORAGE_DIR, exist_ok=True)


def _validate_template_name(name: str) -> None:
    """校验模板名称安全性，防止路径遍历"""
    if not _SAFE_NAME_RE.match(name):
        from app.core.exceptions import ValidationException
        raise ValidationException("Template name must only contain letters, digits, hyphens, and underscores")


def _scope_warnings(config: CrudConfig) -> list[str]:
    """scope=both 时生成警告信息"""
    warnings: list[str] = []
    if config.scope == ScopeType.BOTH:
        warnings.append(
            "scope=both will generate files for both admin and tenant. "
            "Ensure controller/service layers are compatible with both scopes."
        )
        if config.has_status_toggle:
            warnings.append(
                "has_status_toggle with scope=both: toggle endpoint will be "
                "generated for both admin and tenant controllers."
            )
    return warnings


# ============================================================
# 端点
# ============================================================


@router.post("/preview")
async def preview_generate(
    _admin: SuperAdmin,
    req: PreviewRequest = Body(...),
) -> dict[str, Any]:
    """预览生成代码（不写入磁盘）

    返回将要生成的文件列表、冲突信息、warnings 和 DDL 预览。
    每个文件包含 path/size/exists/is_i18n/operation 字段。
    当 include_content=true 时还包含 content 字段。
    """
    gen = _get_generator()
    writer = _get_writer()
    warnings = _scope_warnings(req.config)

    files = gen.generate(req.config)
    preview_data = writer.preview(
        files,
        include_content=req.include_content,
        warnings=warnings,
    )

    return success(data=preview_data)


@router.post("/generate")
async def generate_code(
    _admin: SuperAdmin,
    req: GenerateRequest = Body(...),
) -> dict[str, Any]:
    """生成代码并写入磁盘

    当 confirmed=false 时，仅返回预览结果不写入磁盘。
    当 confirmed=true 时，执行实际写入。
    """
    gen = _get_generator()
    writer = _get_writer()
    warnings = _scope_warnings(req.config)

    files = gen.generate(req.config)

    # confirmed=false → 仅预览
    if not req.confirmed:
        preview_data = writer.preview(files, warnings=warnings)
        preview_data["confirmed"] = False
        return success(data=preview_data)

    # confirmed=true → 实际写入
    action_map = {
        "skip": ConflictAction.SKIP,
        "overwrite": ConflictAction.OVERWRITE,
        "merge": ConflictAction.MERGE,
    }
    action = action_map.get(req.conflict_action, ConflictAction.SKIP)

    result = writer.write(
        files,
        conflict_action=action,
        force_paths=set(req.force_paths) if req.force_paths else None,
    )

    result_data = result.to_dict()
    result_data["confirmed"] = True
    result_data["warnings"] = warnings

    return success(data=result_data)


@router.post("/conflicts")
async def check_conflicts(
    _admin: SuperAdmin,
    config: CrudConfig = Body(...),
) -> dict[str, Any]:
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
async def ddl_preview(
    _admin: SuperAdmin,
    config: CrudConfig = Body(...),
) -> dict[str, Any]:
    """DDL SQL 预览"""
    ddl = CrudGenerator.generate_ddl_preview(config)
    return success(data={"sql": ddl})


# ============================================================
# 配置模板 CRUD
# ============================================================


@router.get("/templates")
async def list_templates(
    _admin: SuperAdmin,
) -> dict[str, Any]:
    """列出所有配置模板"""

    def _list() -> list[dict[str, Any]]:
        _ensure_templates_dir()
        templates: list[dict[str, Any]] = []
        for filename in sorted(os.listdir(_TEMPLATES_STORAGE_DIR)):
            if not filename.endswith(".json"):
                continue
            filepath = os.path.join(_TEMPLATES_STORAGE_DIR, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                templates.append({
                    "name": data.get("name", filename[:-5]),
                    "description": data.get("description", ""),
                    "module": data.get("config", {}).get("module", ""),
                    "scope": data.get("config", {}).get("scope", ""),
                    "updated_at": os.path.getmtime(filepath),
                })
            except (json.JSONDecodeError, OSError):
                continue
        return templates

    templates = await asyncio.to_thread(_list)
    return success(data={"items": templates, "total": len(templates)})


@router.get("/templates/{name}")
async def get_template(
    _admin: SuperAdmin,
    name: str = Path(..., min_length=1),
) -> dict[str, Any]:
    """获取配置模板详情"""
    _validate_template_name(name)

    def _read() -> dict[str, Any] | None:
        _ensure_templates_dir()
        filepath = os.path.join(_TEMPLATES_STORAGE_DIR, f"{name}.json")
        if not os.path.exists(filepath):
            return None
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    data = await asyncio.to_thread(_read)
    if data is None:
        return error(message="Template not found", code=4040, status_code=404)
    return success(data=data)


@router.post("/templates")
async def save_template(
    _admin: SuperAdmin,
    req: TemplateSaveRequest = Body(...),
) -> dict[str, Any]:
    """保存配置模板"""
    data = {
        "name": req.name,
        "description": req.description,
        "tags": req.tags,
        "config": req.config.model_dump(mode="json"),
    }

    def _write() -> str:
        _ensure_templates_dir()
        filepath = os.path.join(_TEMPLATES_STORAGE_DIR, f"{req.name}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return filepath

    filepath = await asyncio.to_thread(_write)
    return success(data={"name": req.name, "path": filepath})


@router.put("/templates/{name}")
async def update_template(
    _admin: SuperAdmin,
    name: str = Path(..., min_length=1),
    req: TemplateUpdateRequest = Body(...),
) -> dict[str, Any]:
    """更新配置模板"""
    _validate_template_name(name)

    def _update() -> bool:
        _ensure_templates_dir()
        filepath = os.path.join(_TEMPLATES_STORAGE_DIR, f"{name}.json")
        if not os.path.exists(filepath):
            return False
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        if req.description is not None:
            data["description"] = req.description
        if req.tags is not None:
            data["tags"] = req.tags
        if req.config is not None:
            data["config"] = req.config.model_dump(mode="json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True

    found = await asyncio.to_thread(_update)
    if not found:
        return error(message="Template not found", code=4040, status_code=404)
    return success(data={"name": name, "updated": True})


@router.delete("/templates/{name}")
async def delete_template(
    _admin: SuperAdmin,
    name: str = Path(..., min_length=1),
) -> dict[str, Any]:
    """删除配置模板"""
    _validate_template_name(name)

    def _delete() -> bool:
        _ensure_templates_dir()
        filepath = os.path.join(_TEMPLATES_STORAGE_DIR, f"{name}.json")
        if not os.path.exists(filepath):
            return False
        os.remove(filepath)
        return True

    found = await asyncio.to_thread(_delete)
    if not found:
        return error(message="Template not found", code=4040, status_code=404)
    return success(data={"name": name, "deleted": True})


# ============================================================
# 项目知识图谱
# ============================================================


@router.get("/project-graph")
async def project_graph(
    _admin: SuperAdmin,
    refresh: bool = Query(False, description="强制刷新缓存"),
) -> dict[str, Any]:
    """项目知识图谱 — 返回所有 Model 元数据

    用于 AI 感知项目已有模块，避免生成重复表名。
    结果缓存在进程内存中，首次调用约 50ms。
    """
    from app.codegen.knowledge_graph import (
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
