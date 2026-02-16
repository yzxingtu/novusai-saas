"""
CRUD 代码生成记录 — Dev-only API 控制器

仅在 APP_ENV=development 时注册。
端点:
  GET    /admin/dev/crud/records            — 分页查询生成记录
  GET    /admin/dev/crud/records/statistics  — 获取统计信息
  GET    /admin/dev/crud/records/:id         — 获取记录详情
  GET    /admin/dev/crud/records/:id/config  — 获取记录配置快照
  DELETE /admin/dev/crud/records/:id         — 删除记录
  POST   /admin/dev/crud/records/delete-files — 批量删除生成文件
  POST   /admin/dev/crud/records/rollback    — 回滚生成记录
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Body, Path
from pydantic import BaseModel, Field

from app.core.deps import DbSession, SuperAdmin, QueryParams
from app.exceptions import NotFoundException, ValidationException
from app.core.i18n import _
from app.core.response import success, deleted, paginated
from app.rbac.decorators import auth_only
from app.plugins.crud_generator.models.crud_generation_record import CrudGenerationRecord
from app.plugins.crud_generator.services.crud_generation_record_service import (
    CrudGenerationRecordService,
)

router = APIRouter(prefix="/dev/crud/records", tags=["Dev - CRUD Generation Records"])

_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "..")
)


# ============================================================
# 请求模型
# ============================================================


class DeleteFilesRequest(BaseModel):
    mode: str = Field("record", description="删除模式: record | entity")
    record_id: int | None = Field(None, description="记录 ID (mode=record 时必填)")
    module_name: str | None = Field(None, description="模块名 (mode=entity 时必填)")
    table_name: str | None = Field(None, description="表名 (mode=entity 时必填)")
    config: dict[str, object] | None = Field(None, description="配置 (mode=entity 时可选)")
    dry_run: bool = Field(True, description="仅预览不删除")


class RollbackRequest(BaseModel):
    record_id: int = Field(..., ge=1, description="记录 ID")
    file_paths: list[str] | None = Field(None, description="部分回滚的文件路径列表")
    force: bool = Field(False, description="跳过 hash 校验")


# ============================================================
# 响应 Schema
# ============================================================


class RecordListItem(BaseModel):
    """生成记录列表项"""
    id: int
    operator_id: int | None = None
    operator_name: str | None = None
    operation_type: str
    module_name: str | None = None
    table_name: str | None = None
    file_count: int = 0
    status: str
    duration_ms: int | None = None
    parent_record_id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class RecordDetail(RecordListItem):
    """生成记录详情（含配置快照、文件清单等）"""
    config_snapshot: dict[str, Any] | None = None
    file_manifest: list[dict[str, Any]] | None = None
    error_detail: str | None = None
    metadata: dict[str, Any] | None = Field(None, alias="metadata_")

    model_config = {"from_attributes": True, "populate_by_name": True}


# ============================================================
# 端点
# ============================================================


@router.get("")
@auth_only
async def list_records(
    _admin: SuperAdmin,
    db: DbSession,
    query: QueryParams,
) -> dict[str, object]:
    """分页查询生成记录

    支持 JSON:API 风格筛选:
    - filter[operation_type][eq]=generate
    - filter[status][eq]=success
    - filter[module_name][ilike]=user
    - filter[table_name][ilike]=user
    - filter[created_at][gte]=2026-01-01
    - sort=-created_at
    - page[number]=1&page[size]=20
    """
    service = CrudGenerationRecordService(db)
    items, total = await service.query_list(spec=query)

    return paginated(
        items=[RecordListItem.model_validate(r).model_dump() for r in items],
        total=total,
        page=query.page,
        page_size=query.size,
    )


@router.get("/statistics")
@auth_only
async def get_statistics(
    _admin: SuperAdmin,
    db: DbSession,
) -> dict[str, object]:
    """获取生成记录统计信息"""
    service = CrudGenerationRecordService(db)
    stats = await service.get_statistics()
    return success(data=stats)


@router.get("/{record_id}")
@auth_only
async def get_record_detail(
    _admin: SuperAdmin,
    db: DbSession,
    record_id: int = Path(..., ge=1),
) -> dict[str, object]:
    """获取生成记录详情"""
    service = CrudGenerationRecordService(db)
    record = await service.get_record_detail(record_id)
    if record is None:
        raise NotFoundException(_("crud_generation_record.error.not_found"))
    return success(data=RecordDetail.model_validate(record).model_dump())


@router.get("/{record_id}/config")
@auth_only
async def get_record_config(
    _admin: SuperAdmin,
    db: DbSession,
    record_id: int = Path(..., ge=1),
) -> dict[str, object]:
    """获取记录的配置快照（用于恢复配置）"""
    service = CrudGenerationRecordService(db)
    config = await service.get_config_from_record(record_id)
    if config is None:
        raise NotFoundException(_("crud_generation_record.error.not_found"))
    return success(data=config)


@router.delete("/{record_id}")
@auth_only
async def delete_record(
    _admin: SuperAdmin,
    db: DbSession,
    record_id: int = Path(..., ge=1),
) -> dict[str, object]:
    """删除生成记录（软删除）"""
    service = CrudGenerationRecordService(db)
    result = await service.delete(record_id)
    if not result:
        raise NotFoundException(_("crud_generation_record.error.not_found"))
    await db.commit()
    return deleted()


# ============================================================
# 文件删除与回滚
# ============================================================


@router.post("/delete-files")
@auth_only
async def delete_generated_files(
    _admin: SuperAdmin,
    db: DbSession,
    req: DeleteFilesRequest = Body(...),
) -> dict[str, object]:
    """批量删除生成的文件"""
    from app.plugins.crud_generator.codegen.backup import BackupEngine

    if req.mode == "record":
        if not req.record_id:
            raise ValidationException(_("codegen.error.record_id_required"))

        service = CrudGenerationRecordService(db)
        record = await service.get_record_detail(req.record_id)
        if not record:
            raise NotFoundException(_("crud_generation_record.error.not_found"))

        manifest = record.file_manifest or []
        engine = BackupEngine(_PROJECT_ROOT)

        if req.dry_run:
            file_list = []
            for entry in manifest:
                path = entry.get("path", "")
                if not path:
                    continue
                abs_path = os.path.join(_PROJECT_ROOT, path)
                file_list.append({
                    "path": path,
                    "exists": os.path.exists(abs_path),
                    "operation": entry.get("operation", "preview"),
                })
            return success(data={
                "mode": "record",
                "record_id": req.record_id,
                "dry_run": True,
                "files": file_list,
                "total": len(file_list),
            })

        result = engine.rollback_by_manifest(manifest)
        return success(data={
            "mode": "record",
            "record_id": req.record_id,
            "dry_run": False,
            **result.to_dict(),
        })

    if req.mode == "entity":
        if not req.module_name or not req.table_name:
            raise ValidationException(_("codegen.error.entity_fields_required"))

        from app.plugins.crud_generator.codegen.generator import CrudGenerator
        from app.plugins.crud_generator.codegen.schemas import CrudConfig

        config_data = req.config
        if not config_data:
            service = CrudGenerationRecordService(db)
            config_data = await service.get_latest_config_by_entity(
                req.module_name, req.table_name
            )
            if not config_data:
                raise NotFoundException(
                    _("codegen.error.no_config_found")
                )

        crud_config = CrudConfig(**config_data)
        gen = CrudGenerator()
        files = gen.generate(crud_config)

        file_list: list[dict[str, object]] = []
        for path in files:
            if path.startswith("__") and path.endswith("__"):
                continue
            abs_path = os.path.join(_PROJECT_ROOT, path)
            exists = os.path.exists(abs_path)
            file_list.append({"path": path, "exists": exists})

        if req.dry_run:
            return success(data={
                "mode": "entity",
                "module_name": req.module_name,
                "table_name": req.table_name,
                "dry_run": True,
                "files": file_list,
                "total": len(file_list),
                "existing": sum(1 for f in file_list if f["exists"]),
            })

        existing_paths = [str(f["path"]) for f in file_list if f["exists"]]
        del_result = engine.delete_files_by_paths(existing_paths)

        return success(data={
            "mode": "entity",
            "module_name": req.module_name,
            "table_name": req.table_name,
            "dry_run": False,
            **del_result,
        })

    raise ValidationException(_("codegen.error.unknown_mode"))


@router.post("/rollback")
@auth_only
async def rollback_generation(
    _admin: SuperAdmin,
    db: DbSession,
    req: RollbackRequest = Body(...),
) -> dict[str, object]:
    """回滚生成记录（从备份恢复文件）"""
    from app.plugins.crud_generator.codegen.backup import BackupEngine

    engine = BackupEngine(_PROJECT_ROOT)
    result = engine.rollback_by_record(
        req.record_id,
        file_paths=set(req.file_paths) if req.file_paths else None,
        force=req.force,
    )

    return success(data={
        "record_id": req.record_id,
        **result.to_dict(),
    })
