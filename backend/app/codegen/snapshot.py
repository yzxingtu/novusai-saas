"""
BatchCrudProject 快照导入/导出

M58-T7: 支持将多表项目配置保存为可复用的快照（JSON），
并能恢复到 Wizard/生成器中继续编辑与生成。

快照格式：
{
    "snapshot_version": "1.0.0",
    "schema_version": "2.6.0",
    "created_at": "2026-02-14T20:00:00Z",
    "project": { ... BatchCrudProject JSON ... },
    "metadata": { "description": "...", "entity_count": N }
}
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from app.codegen.schema_guard import SCHEMA_VERSION, guard_batch_project


SNAPSHOT_VERSION = "1.0.0"
"""当前快照格式版本"""

COMPATIBLE_SNAPSHOT_VERSIONS = {"1.0.0"}
"""兼容的快照版本集合"""


# ============================================================
# 快照模型
# ============================================================


class SnapshotMetadata(BaseModel):
    """快照元数据"""

    description: str = Field("", description="快照描述")
    entity_count: int = Field(0, description="实体数量")
    created_by: str = Field("", description="创建者")


class ProjectSnapshot(BaseModel):
    """BatchCrudProject 快照"""

    snapshot_version: str = Field(SNAPSHOT_VERSION)
    schema_version: str = Field(SCHEMA_VERSION)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    project: dict[str, Any] = Field(..., description="BatchCrudProject JSON")
    metadata: SnapshotMetadata = Field(default_factory=SnapshotMetadata)


# ============================================================
# 导入校验结果
# ============================================================


class SnapshotImportError(BaseModel):
    """快照导入错误"""

    code: str = Field(..., description="错误码")
    message: str = Field(..., description="人类可读信息")
    details: dict[str, Any] = Field(default_factory=dict)


class SnapshotImportResult(BaseModel):
    """快照导入结果"""

    success: bool = Field(False)
    project: dict[str, Any] = Field(default_factory=dict)
    errors: list[SnapshotImportError] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    snapshot_version: str = Field("")
    schema_version: str = Field("")


# ============================================================
# 导出
# ============================================================


def export_snapshot(
    project_dict: dict[str, Any],
    description: str = "",
    created_by: str = "",
) -> str:
    """导出 BatchCrudProject 为快照 JSON 字符串

    Args:
        project_dict: BatchCrudProject JSON（已校验的）
        description: 快照描述
        created_by: 创建者标识

    Returns:
        JSON 字符串（格式化输出）
    """
    entity_count = len(project_dict.get("entities", []))

    snapshot = ProjectSnapshot(
        project=project_dict,
        metadata=SnapshotMetadata(
            description=description,
            entity_count=entity_count,
            created_by=created_by,
        ),
    )

    return snapshot.model_dump_json(indent=2)


def export_snapshot_dict(
    project_dict: dict[str, Any],
    description: str = "",
    created_by: str = "",
) -> dict[str, Any]:
    """导出为 dict（供 API 返回）"""
    entity_count = len(project_dict.get("entities", []))

    snapshot = ProjectSnapshot(
        project=project_dict,
        metadata=SnapshotMetadata(
            description=description,
            entity_count=entity_count,
            created_by=created_by,
        ),
    )

    return snapshot.model_dump(mode="json")


# ============================================================
# 导入
# ============================================================


def import_snapshot(raw: str | dict[str, Any]) -> SnapshotImportResult:
    """从 JSON 字符串或 dict 导入快照

    校验流程：
    1. 解析 JSON
    2. 检查 snapshot_version 兼容性
    3. 检查 schema_version（warning if different）
    4. 使用 schema guard 校验 project
    5. 返回 SnapshotImportResult

    Args:
        raw: JSON 字符串或 dict

    Returns:
        SnapshotImportResult
    """
    errors: list[SnapshotImportError] = []
    warnings: list[str] = []

    # 1. 解析
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            return SnapshotImportResult(
                errors=[SnapshotImportError(
                    code="INVALID_JSON",
                    message=f"Invalid JSON: {e}",
                )],
            )
    else:
        data = raw

    if not isinstance(data, dict):
        return SnapshotImportResult(
            errors=[SnapshotImportError(
                code="INVALID_FORMAT",
                message="Snapshot must be a JSON object",
            )],
        )

    # 2. 检查 snapshot_version
    snap_version = data.get("snapshot_version", "")
    if not snap_version:
        errors.append(SnapshotImportError(
            code="MISSING_VERSION",
            message="Missing snapshot_version field",
        ))
    elif snap_version not in COMPATIBLE_SNAPSHOT_VERSIONS:
        errors.append(SnapshotImportError(
            code="INCOMPATIBLE_VERSION",
            message=(
                f"Snapshot version '{snap_version}' is not compatible. "
                f"Supported: {', '.join(sorted(COMPATIBLE_SNAPSHOT_VERSIONS))}"
            ),
            details={"version": snap_version, "supported": sorted(COMPATIBLE_SNAPSHOT_VERSIONS)},
        ))

    if errors:
        return SnapshotImportResult(
            errors=errors,
            snapshot_version=snap_version,
        )

    # 3. 检查 schema_version
    schema_ver = data.get("schema_version", "")
    if schema_ver and schema_ver != SCHEMA_VERSION:
        warnings.append(
            f"Schema version mismatch: snapshot has '{schema_ver}', "
            f"current is '{SCHEMA_VERSION}'. Some fields may be ignored."
        )

    # 4. 提取 project
    project = data.get("project")
    if not project or not isinstance(project, dict):
        return SnapshotImportResult(
            errors=[SnapshotImportError(
                code="MISSING_PROJECT",
                message="Snapshot must contain a 'project' field with BatchCrudProject data",
            )],
            snapshot_version=snap_version,
            schema_version=schema_ver,
        )

    # 5. Schema guard 校验
    guard = guard_batch_project(project)
    if not guard.valid:
        project_errors = [
            SnapshotImportError(
                code=f.error_type.value,
                message=f.reason,
                details={"path": f.path, "input_value": f.input_value},
            )
            for f in guard.invalid_fields
        ]
        return SnapshotImportResult(
            errors=project_errors,
            warnings=warnings,
            snapshot_version=snap_version,
            schema_version=schema_ver,
        )

    return SnapshotImportResult(
        success=True,
        project=project,
        warnings=warnings,
        snapshot_version=snap_version,
        schema_version=schema_ver,
    )


__all__ = [
    "COMPATIBLE_SNAPSHOT_VERSIONS",
    "SNAPSHOT_VERSION",
    "ProjectSnapshot",
    "SnapshotImportError",
    "SnapshotImportResult",
    "SnapshotMetadata",
    "export_snapshot",
    "export_snapshot_dict",
    "import_snapshot",
]
