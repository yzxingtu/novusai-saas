"""
AI 表策略租户覆盖 Service
"""

from __future__ import annotations

from typing import Any

from app.core.i18n import _
from app.exceptions import NotFoundException
from app.models.ai.table_policy import AITablePolicy, AITablePolicyOverride
from app.repositories.ai.table_policy_override_repository import AITablePolicyOverrideRepository
from app.repositories.ai.table_policy_repository import AITablePolicyRepository
from app.core.base_service import TenantService


class AITablePolicyOverrideService(TenantService[AITablePolicyOverride, AITablePolicyOverrideRepository]):
    """AI 表策略租户覆盖服务"""

    repository_class = AITablePolicyOverrideRepository

    async def get_global_policies(self) -> list[AITablePolicy]:
        """获取所有活跃的全局策略"""
        repo = AITablePolicyRepository(self.db)
        return await repo.get_all_active()

    async def get_effective_policies(self) -> list[dict[str, Any]]:
        """获取当前租户的有效策略列表（全局 + 覆盖合并）"""
        global_policies = await self.get_global_policies()
        overrides = await self.repo.get_all_for_tenant()
        overrides_map = {ov.policy_id: ov for ov in overrides}

        result: list[dict[str, Any]] = []
        for gp in global_policies:
            ov = overrides_map.get(gp.id)
            effective = self._merge(gp, ov)
            effective["override_id"] = ov.id if ov else None
            effective["has_override"] = ov is not None
            result.append(effective)
        return result

    async def create_or_update_override(
        self,
        policy_id: int,
        data: dict[str, Any],
    ) -> AITablePolicyOverride:
        """创建或更新租户覆盖（仅允许收紧）"""
        # 验证全局策略存在
        repo = AITablePolicyRepository(self.db)
        global_policy = await repo.get_by_id(policy_id)
        if not global_policy:
            raise NotFoundException(message=_("ai_table_policy.not_found"))

        # 执行收紧校验
        self._validate_restrict_only(global_policy, data)

        existing = await self.repo.get_by_policy_id(policy_id)
        if existing:
            for key, value in data.items():
                setattr(existing, key, value)
            await self.db.flush()
            return existing
        else:
            override = AITablePolicyOverride(
                policy_id=policy_id,
                tenant_id=self.tenant_id,
                **data,
            )
            self.db.add(override)
            await self.db.flush()
            return override

    async def remove_override(self, policy_id: int) -> None:
        """删除租户覆盖（恢复到全局策略）"""
        existing = await self.repo.get_by_policy_id(policy_id)
        if not existing:
            raise NotFoundException(message=_("ai_table_policy_override.not_found"))
        await self.db.delete(existing)
        await self.db.flush()

    @staticmethod
    def _merge(gp: AITablePolicy, ov: AITablePolicyOverride | None) -> dict[str, Any]:
        """合并全局策略与租户覆盖（复用 SchemaProvider 的逻辑）"""
        from app.ai.data_intelligence.schema_provider import _merge_policy_with_override
        policy = _merge_policy_with_override(gp, ov)
        policy["id"] = gp.id
        return policy

    @staticmethod
    def _validate_restrict_only(gp: AITablePolicy, data: dict[str, Any]) -> None:
        """校验覆盖只能收紧，不能放开"""
        # bool 字段: 只能 True -> False
        for field in ("allow_read", "allow_create", "allow_update", "allow_delete", "is_active"):
            if field in data and data[field] is not None:
                global_val = getattr(gp, field)
                if not global_val and data[field]:
                    data[field] = None  # 不允许放开，清除覆盖

        # max_rows: 只能更小
        if "max_rows" in data and data["max_rows"] is not None:
            if data["max_rows"] > gp.max_rows:
                data["max_rows"] = None  # 不允许超过全局值


__all__ = ["AITablePolicyOverrideService"]
