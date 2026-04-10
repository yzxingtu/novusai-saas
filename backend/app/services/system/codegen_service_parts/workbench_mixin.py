"""Workbench concerns for CodegenService. / CodegenService 工作台职责。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.codegen.constants import CODEGEN_PROJECT_ROOT as _PROJECT_ROOT
from app.codegen.manifest import ManifestManager
from app.core.i18n import _
from app.enums.codegen import CodegenConfigStatusEnum
from app.exceptions import ConflictException, NotFoundException
from app.models.system.codegen_config import CodegenConfig

from .types import CodegenDeleteGuard, CodegenWorkbenchEntry


class CodegenWorkbenchMixin:
    """Workbench mixin / 工作台混入。"""

    @staticmethod
    def build_delete_guard(
        config: CodegenConfig,
        *,
        manifest_present: bool,
    ) -> CodegenDeleteGuard:
        """Build delete guard info from config state / 根据配置状态构建删除保护信息."""
        status = str(config.status or "")
        if manifest_present:
            return CodegenDeleteGuard(
                allowed=False,
                reason_code="manifest_present",
                message=_("codegen.delete_guard.manifest_present"),
            )
        if status == CodegenConfigStatusEnum.ROLLED_BACK.value:
            return CodegenDeleteGuard(allowed=True)
        if status in {
            CodegenConfigStatusEnum.GENERATED.value,
            CodegenConfigStatusEnum.APPLIED.value,
        }:
            return CodegenDeleteGuard(
                allowed=False,
                reason_code="generated_state",
                message=_("codegen.delete_guard.generated_state"),
            )
        if (
            config.generated_files
            or config.last_generated_at
            or (config.generation_count or 0) > 0
        ):
            return CodegenDeleteGuard(
                allowed=False,
                reason_code="generation_history_present",
                message=_("codegen.delete_guard.generation_history_present"),
            )
        return CodegenDeleteGuard(allowed=True)

    @staticmethod
    def _has_manifest_entry(
        config: CodegenConfig,
        *,
        manifest_resources: set[str],
        manifest_config_ids: set[int],
    ) -> bool:
        """判断配置是否存在 manifest 条目 / Check whether config has a manifest entry."""
        if config.resource and config.resource in manifest_resources:
            return True
        return config.id in manifest_config_ids

    @classmethod
    def build_workbench_summary(
        cls,
        items: list[CodegenConfig],
        *,
        manifest_resources: set[str],
        manifest_config_ids: set[int],
        focus_limit: int = 6,
    ) -> dict[str, Any]:
        """构建 codegen 工作台摘要 / Build codegen workbench summary."""
        stats = {
            "draft": 0,
            "generated": 0,
            "applied": 0,
            "rollback": 0,
            "attention": 0,
            "total": len(items),
        }
        sections: dict[str, list[CodegenWorkbenchEntry]] = {
            "draft": [],
            "generated": [],
            "applied": [],
            "rollback": [],
            "attention": [],
        }

        for item in items:
            manifest_present = cls._has_manifest_entry(
                item,
                manifest_resources=manifest_resources,
                manifest_config_ids=manifest_config_ids,
            )
            guard = cls.build_delete_guard(item, manifest_present=manifest_present)
            entry = CodegenWorkbenchEntry(
                config=item,
                manifest_present=manifest_present,
                delete_guard=guard,
            )
            status = str(item.status or "")

            if status in {"draft", "generated", "applied"}:
                stats[status] += 1
                if len(sections[status]) < focus_limit:
                    sections[status].append(entry)

            if manifest_present:
                stats["rollback"] += 1
                if len(sections["rollback"]) < focus_limit:
                    sections["rollback"].append(entry)

            needs_attention = bool(item.last_error) or not guard.allowed
            if needs_attention:
                stats["attention"] += 1
                if len(sections["attention"]) < focus_limit:
                    sections["attention"].append(entry)

        return {
            "stats": stats,
            "sections": sections,
        }

    async def get_workbench_summary(
        self,
        *,
        project_root: Path | None = None,
        focus_limit: int = 6,
    ) -> dict[str, Any]:
        """获取工作台摘要 / Get workbench summary."""
        root = project_root or _PROJECT_ROOT
        items = await self.repo.list_workbench_rows()
        manifest = ManifestManager(root)
        manifest_resources, manifest_config_ids = manifest.manifest_index()
        return self.build_workbench_summary(
            items,
            manifest_resources=manifest_resources,
            manifest_config_ids=manifest_config_ids,
            focus_limit=focus_limit,
        )

    async def get_delete_guard(
        self,
        config_id: int,
        *,
        project_root: Path | None = None,
    ) -> CodegenDeleteGuard:
        """Get delete guard info for a config / 获取配置删除保护信息."""
        config = await self.get_by_id(config_id)
        if not config:
            raise NotFoundException(message=_("codegen.config_not_found"))
        root = project_root or _PROJECT_ROOT
        manifest = ManifestManager(root)
        manifest_present = (
            manifest.find_entry_for_config(config.resource, config.id) is not None
        )
        return self.build_delete_guard(config, manifest_present=manifest_present)

    async def assert_can_delete(
        self,
        config_id: int,
        *,
        project_root: Path | None = None,
    ) -> CodegenDeleteGuard:
        """Raise when deleting is unsafe / 删除不安全时抛出异常."""
        guard = await self.get_delete_guard(config_id, project_root=project_root)
        if guard.allowed:
            return guard
        raise ConflictException(
            message=guard.message or _("common.failed"),
            data={
                "reason_code": guard.reason_code,
            },
        )

