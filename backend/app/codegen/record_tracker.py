"""
CRUD 代码生成记录追踪器

在生成流程关键节点创建 CrudGenerationRecord，
与主流程解耦：记录创建失败仅打 warning 日志，不阻断生成。
"""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.codegen.schemas import CrudConfig
from app.core.logging import LogManager
from app.enums.codegen import CodegenOperationType, CodegenRecordStatus

logger = LogManager.get_logger("app")


def _build_file_manifest(
    files: dict[str, str],
    write_result: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """构建文件清单 JSON

    Args:
        files: Generator 输出的 {相对路径: 内容}
        write_result: Writer.write() 返回的 dict (可选)

    Returns:
        [{path, size, operation}]
    """
    _VIRTUAL = ("__ddl_preview__.sql", "__entity_file_map__.json")

    written_set: set[str] = set()
    merged_set: set[str] = set()
    skipped_set: set[str] = set()
    error_paths: set[str] = set()

    if write_result:
        written_set = set(write_result.get("written", []))
        merged_set = set(write_result.get("merged", []))
        skipped_set = set(write_result.get("skipped", []))
        error_paths = {e.get("path", "") for e in write_result.get("errors", [])}

    manifest: list[dict[str, Any]] = []
    for path, content in files.items():
        if path in _VIRTUAL:
            continue
        size = len(content.encode("utf-8"))
        if path in written_set:
            op = "written"
        elif path in merged_set:
            op = "merged"
        elif path in skipped_set:
            op = "skipped"
        elif path in error_paths:
            op = "error"
        else:
            op = "preview"
        manifest.append({"path": path, "size": size, "operation": op})
    return manifest


def _determine_status(write_result: dict[str, Any] | None) -> str:
    """根据写入结果判断记录状态"""
    if write_result is None:
        return CodegenRecordStatus.SUCCESS.value

    errors = write_result.get("errors", [])
    written = write_result.get("written", [])
    merged = write_result.get("merged", [])

    if errors and (written or merged):
        return CodegenRecordStatus.PARTIAL_FAILURE.value
    if errors and not written and not merged:
        return CodegenRecordStatus.FAILED.value
    return CodegenRecordStatus.SUCCESS.value


async def track_generation(
    db: AsyncSession,
    *,
    config: CrudConfig,
    files: dict[str, str],
    operation_type: str,
    operator_id: int | None = None,
    operator_name: str | None = None,
    write_result: dict[str, Any] | None = None,
    error_detail: str | None = None,
    duration_ms: int | None = None,
    parent_record_id: int | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> int | None:
    """追踪一次生成操作并持久化记录

    本函数使用独立事务，失败仅打 warning 日志。

    Args:
        db: 异步数据库会话
        config: 生成配置
        files: Generator 输出文件字典
        operation_type: 操作类型 (preview/generate/rollback/delete)
        operator_id: 操作人 ID
        operator_name: 操作人名称
        write_result: Writer.write() 的 to_dict() 结果
        error_detail: 错误详情
        duration_ms: 执行耗时(ms)
        parent_record_id: 关联父记录 ID
        extra_metadata: 扩展元数据

    Returns:
        记录 ID 或 None (失败时)
    """
    try:
        from app.services.system.crud_generation_record_service import (
            CrudGenerationRecordService,
        )

        manifest = _build_file_manifest(files, write_result)
        status = CodegenRecordStatus.SUCCESS.value
        if error_detail:
            status = CodegenRecordStatus.FAILED.value
        elif write_result:
            status = _determine_status(write_result)

        record_data: dict[str, Any] = {
            "operator_id": operator_id,
            "operator_name": operator_name,
            "operation_type": operation_type,
            "module_name": config.module if hasattr(config, "module") else None,
            "table_name": config.table_name if hasattr(config, "table_name") else None,
            "config_snapshot": config.model_dump(mode="json"),
            "file_manifest": manifest,
            "file_count": len(manifest),
            "status": status,
            "error_detail": error_detail,
            "duration_ms": duration_ms,
            "parent_record_id": parent_record_id,
            "metadata_": extra_metadata,
        }

        service = CrudGenerationRecordService(db)
        record = await service.create_record(record_data)
        await db.commit()
        return record.id

    except Exception as exc:
        logger.warning(
            "Failed to track generation record: %s",
            str(exc),
            exc_info=True,
        )
        try:
            await db.rollback()
        except Exception:
            pass
        return None


class GenerationTimer:
    """生成操作计时器上下文管理器"""

    def __init__(self) -> None:
        self._start: float = 0
        self.duration_ms: int = 0

    def __enter__(self) -> GenerationTimer:
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args: Any) -> None:
        elapsed = time.perf_counter() - self._start
        self.duration_ms = int(elapsed * 1000)


__all__ = [
    "GenerationTimer",
    "track_generation",
]
