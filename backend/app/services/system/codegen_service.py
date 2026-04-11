"""
CRUD 代码生成服务 / Codegen Service

提供代码生成配置的业务逻辑
Provides codegen config business logic.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.codegen.generator import CodeGenerator
from app.codegen.preset_loader import get_preset as load_codegen_preset
from app.codegen.preset_loader import list_presets as list_codegen_presets
from app.core.base_service import GlobalService
from app.enums.codegen import CodegenConfigStatusEnum
from app.models.system.codegen_config import CodegenConfig
from app.repositories.system.codegen_config_repository import (
    CodegenConfigRepository,
)
from app.services.system.codegen_service_parts import (
    CodegenConfigSyncMixin,
    CodegenDeleteGuard,
    CodegenExecutionMixin,
    CodegenIntrospectionMixin,
    CodegenVersioningMixin,
    CodegenWorkbenchEntry,
    CodegenWorkbenchMixin,
    GenerateOutput,
)


class CodegenService(
    CodegenConfigSyncMixin,
    CodegenVersioningMixin,
    CodegenWorkbenchMixin,
    CodegenIntrospectionMixin,
    CodegenExecutionMixin,
    GlobalService[CodegenConfig, CodegenConfigRepository],
):
    """
    CRUD 代码生成服务 / Codegen service.

    平台级服务，无企业隔离。保留稳定 facade，对外兼容原有调用；
    复杂职责拆到 `codegen_service_parts` 内部模块。
    """

    model = CodegenConfig
    repository_class = CodegenConfigRepository

    @staticmethod
    def list_available_presets() -> list[dict[str, Any]]:
        """List available presets / 列出全部可用预设."""
        return list_codegen_presets()

    @staticmethod
    def get_preset_detail(name: str) -> dict[str, Any] | None:
        """Get preset detail / 获取预设详情."""
        return load_codegen_preset(name)

    @staticmethod
    def get_preset_detail_safe(name: str) -> dict[str, Any] | None:
        """Safely resolve preset detail by name with path traversal guard."""
        if not re.match(r"^[a-zA-Z0-9_-]+$", name):
            return None
        presets_dir = (
            Path(__file__).resolve().parent.parent.parent
            / "codegen"
            / "templates"
            / "presets"
        )
        path = (presets_dir / f"{name}.yaml").resolve()
        if not path.is_relative_to(presets_dir.resolve()):
            return None
        if not path.exists():
            return None
        return load_codegen_preset(name)

    @classmethod
    def create_standalone(cls) -> CodegenService:
        """
        创建无数据库依赖的轻量实例，仅用于 preview/validate。
        Create minimal instance for preview/validate without DB.
        """
        instance = cls.__new__(cls)
        instance.db = None  # type: ignore[assignment]
        instance.repo = None  # type: ignore[assignment]
        return instance

    @staticmethod
    def _make_generator() -> CodeGenerator:
        """Create the generator via the facade module for patch compatibility."""
        return CodeGenerator()

    async def get_by_resource(self, resource: str) -> CodegenConfig | None:
        """
        根据资源名获取配置 / Get config by resource name.

        Args:
            resource: 资源名

        Returns:
            配置实例或 None
        """
        return await self.repo.get_by_resource(resource)

    async def get_by_status(
        self,
        status: CodegenConfigStatusEnum | str,
    ) -> list[CodegenConfig]:
        """
        根据状态获取配置列表 / Get configs by status.

        Args:
            status: 状态枚举或字符串

        Returns:
            配置列表
        """
        status_val = status.value if hasattr(status, "value") else status
        return await self.repo.get_by_status(status_val)


__all__ = [
    "CodegenService",
    "CodeGenerator",
    "GenerateOutput",
    "CodegenDeleteGuard",
    "CodegenWorkbenchEntry",
]
