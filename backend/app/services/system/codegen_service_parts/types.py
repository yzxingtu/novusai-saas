"""Codegen service shared types. / Codegen 服务共享类型。"""

from __future__ import annotations

from dataclasses import dataclass

from app.codegen.file_writer import WriteResult
from app.models.system.codegen_config import CodegenConfig


@dataclass
class GenerateOutput:
    """Generate 输出，包含 WriteResult 与配置元数据 / Generate output with result and config metadata."""

    result: WriteResult
    config_id: int | None = None
    resource: str | None = None
    module: str | None = None
    table_name: str | None = None


@dataclass(frozen=True)
class CodegenDeleteGuard:
    """Delete guard result / 删除保护判断结果。"""

    allowed: bool
    reason_code: str | None = None
    message: str | None = None


@dataclass(frozen=True)
class CodegenWorkbenchEntry:
    """Workbench entry / 工作台条目。"""

    config: CodegenConfig
    manifest_present: bool
    delete_guard: CodegenDeleteGuard

