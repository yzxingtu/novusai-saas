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

from typing import Any

from fastapi import APIRouter, Body, Path

from app.core.deps import DbSession, SuperAdmin, QueryParams
from app.core.response import success, deleted, paginated
from app.exceptions import NotFoundException
from app.core.i18n import _
from app.services.system.crud_generation_record_service import (
    CrudGenerationRecordService,
)

router = APIRouter(prefix="/dev/crud/records", tags=["Dev - CRUD Generation Records"])


def _serialize_record(record: Any) -> dict[str, Any]:
    """序列化生成记录为响应字典"""
    return {
        "id": record.id,
        "operator_id": record.operator_id,
        "operator_name": record.operator_name,
        "operation_type": record.operation_type,
        "module_name": record.module_name,
        "table_name": record.table_name,
        "file_count": record.file_count,
        "status": record.status,
        "duration_ms": record.duration_ms,
        "parent_record_id": record.parent_record_id,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }


def _serialize_record_detail(record: Any) -> dict[str, Any]:
    """序列化生成记录详情（含配置快照、文件清单等）"""
    data = _serialize_record(record)
    data["config_snapshot"] = record.config_snapshot
    data["batch_project_snapshot"] = record.batch_project_snapshot
    data["file_manifest"] = record.file_manifest
    data["error_detail"] = record.error_detail
    data["metadata"] = record.metadata_
    return data


# ============================================================
# 端点
# ============================================================


@router.get("")
async def list_records(
    _admin: SuperAdmin,
    db: DbSession,
    query: QueryParams,
) -> dict[str, Any]:
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
        items=[_serialize_record(r) for r in items],
        total=total,
        page=query.page,
        page_size=query.size,
    )


@router.get("/statistics")
async def get_statistics(
    _admin: SuperAdmin,
    db: DbSession,
) -> dict[str, Any]:
    """获取生成记录统计信息"""
    service = CrudGenerationRecordService(db)
    stats = await service.get_statistics()
    return success(data=stats)


@router.get("/{record_id}")
async def get_record_detail(
    _admin: SuperAdmin,
    db: DbSession,
    record_id: int = Path(..., ge=1),
) -> dict[str, Any]:
    """获取生成记录详情"""
    service = CrudGenerationRecordService(db)
    record = await service.get_record_detail(record_id)
    if record is None:
        raise NotFoundException(_("crud_generation_record.error.not_found"))
    return success(data=_serialize_record_detail(record))


@router.get("/{record_id}/config")
async def get_record_config(
    _admin: SuperAdmin,
    db: DbSession,
    record_id: int = Path(..., ge=1),
) -> dict[str, Any]:
    """获取记录的配置快照（用于恢复配置）"""
    service = CrudGenerationRecordService(db)
    config = await service.get_config_from_record(record_id)
    if config is None:
        raise NotFoundException(_("crud_generation_record.error.not_found"))
    return success(data=config)


@router.delete("/{record_id}")
async def delete_record(
    _admin: SuperAdmin,
    db: DbSession,
    record_id: int = Path(..., ge=1),
) -> dict[str, Any]:
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
async def delete_generated_files(
    _admin: SuperAdmin,
    db: DbSession,
    body: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    """批量删除生成的文件

    Body:
        mode: 'record' | 'entity'
        record_id: int (mode=record 时必填)
        module_name: str (mode=entity 时必填)
        table_name: str (mode=entity 时必填)
        dry_run: bool (默认 true)
    """
    import os
    from app.codegen.backup import BackupEngine

    mode = body.get("mode", "record")
    dry_run = body.get("dry_run", True)
    project_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..")
    )

    if mode == "record":
        record_id = body.get("record_id")
        if not record_id:
            return success(data={"error": "record_id is required for mode=record"})

        service = CrudGenerationRecordService(db)
        record = await service.get_record_detail(record_id)
        if not record:
            raise NotFoundException(_("crud_generation_record.error.not_found"))

        manifest = record.file_manifest or []
        engine = BackupEngine(project_root)

        if dry_run:
            file_list = []
            for entry in manifest:
                path = entry.get("path", "")
                if not path:
                    continue
                abs_path = os.path.join(project_root, path)
                file_list.append({
                    "path": path,
                    "exists": os.path.exists(abs_path),
                    "operation": entry.get("operation", "preview"),
                })
            return success(data={
                "mode": "record",
                "record_id": record_id,
                "dry_run": True,
                "files": file_list,
                "total": len(file_list),
            })

        result = engine.rollback_by_manifest(manifest)
        return success(data={
            "mode": "record",
            "record_id": record_id,
            "dry_run": False,
            **result.to_dict(),
        })

    elif mode == "entity":
        module_name = body.get("module_name", "")
        table_name = body.get("table_name", "")
        if not module_name or not table_name:
            return success(data={"error": "module_name and table_name required for mode=entity"})

        from app.codegen.generator import CrudGenerator
        from app.codegen.schemas import CrudConfig

        # Re-generate to get file paths
        config_data = body.get("config")
        if not config_data:
            # Try to find from latest record
            from sqlalchemy import text
            row = await db.execute(text(
                "SELECT config_snapshot FROM crud_generation_records "
                "WHERE module_name = :module AND table_name = :table "
                "AND is_deleted = false ORDER BY created_at DESC LIMIT 1"
            ), {"module": module_name, "table": table_name})
            r = row.fetchone()
            if r and r[0]:
                config_data = r[0]
            else:
                return success(data={"error": "No config found; provide 'config' in body or have a generation record"})

        crud_config = CrudConfig(**config_data)
        gen = CrudGenerator()
        files = gen.generate(crud_config)

        file_list = []
        for path in files:
            if path.startswith("__") and path.endswith("__"):
                continue
            abs_path = os.path.join(project_root, path)
            exists = os.path.exists(abs_path)
            file_list.append({"path": path, "exists": exists})

        if dry_run:
            return success(data={
                "mode": "entity",
                "module_name": module_name,
                "table_name": table_name,
                "dry_run": True,
                "files": file_list,
                "total": len(file_list),
                "existing": sum(1 for f in file_list if f["exists"]),
            })

        deleted_count = 0
        for f in file_list:
            if f["exists"]:
                try:
                    os.unlink(os.path.join(project_root, f["path"]))
                    deleted_count += 1
                except OSError:
                    pass

        return success(data={
            "mode": "entity",
            "module_name": module_name,
            "table_name": table_name,
            "dry_run": False,
            "total_deleted": deleted_count,
            "total_files": len(file_list),
        })

    return success(data={"error": f"Unknown mode: {mode}"})


@router.post("/rollback")
async def rollback_generation(
    _admin: SuperAdmin,
    db: DbSession,
    body: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    """回滚生成记录（从备份恢复文件）

    Body:
        record_id: int (必填)
        file_paths: list[str] (可选, 部分回滚)
        force: bool (默认 false, 跳过 hash 校验)
    """
    import os
    from app.codegen.backup import BackupEngine

    record_id = body.get("record_id")
    if not record_id:
        return success(data={"error": "record_id is required"})

    file_paths = body.get("file_paths")
    force = body.get("force", False)

    project_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..")
    )

    engine = BackupEngine(project_root)
    result = engine.rollback_by_record(
        record_id,
        file_paths=set(file_paths) if file_paths else None,
        force=force,
    )

    return success(data={
        "record_id": record_id,
        **result.to_dict(),
    })
