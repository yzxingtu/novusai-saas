"""
租户端 AI 表策略管理控制器

提供租户管理员查看和覆盖 AI 表策略的接口。
覆盖只能收紧（限制更多），不能放开。
"""

from __future__ import annotations

from fastapi import Request

from app.core.base_controller import TenantController
from app.core.deps import ActiveTenantAdmin, DbSession, QueryParams
from app.core.response import deleted, success
from app.rbac.decorators import permission_resource, action_read, action_update, action_delete
from app.schemas.ai.table_policy_override import AITablePolicyOverrideUpdate
from app.services.ai.table_policy_override_service import AITablePolicyOverrideService


@permission_resource(
    resource="ai_table_policy_override",
    name="AI 表策略覆盖",
)
class TenantAITablePolicyController(TenantController):
    """租户端 AI 表策略管理"""

    prefix = "/ai/table-policies"
    tags = ["Tenant AI Table Policies"]

    def _register_routes(self) -> None:
        """注册路由"""
        router = self.router

        @router.get("", summary="获取有效策略列表")
        @action_read()
        async def list_effective(
            request: Request,
            db: DbSession,
            tenant_admin: ActiveTenantAdmin,
            params: QueryParams,
        ):
            """获取当前租户的有效策略列表（全局 + 租户覆盖合并）"""
            service = self.get_service(db, tenant_admin.tenant_id)
            policies = await service.get_effective_policies()
            return success(data=policies)

        @router.put("/{policy_id}/override", summary="创建/更新策略覆盖")
        @action_update()
        async def upsert_override(
            request: Request,
            db: DbSession,
            policy_id: int,
            data: AITablePolicyOverrideUpdate,
            tenant_admin: ActiveTenantAdmin,
        ):
            """创建或更新租户策略覆盖（仅允许收紧）"""
            service = self.get_service(db, tenant_admin.tenant_id)
            override = await service.create_or_update_override(
                policy_id=policy_id,
                data=data.model_dump(exclude_unset=True),
            )
            await db.commit()

            # 清除 Redis 缓存
            from app.ai.constants import schema_cache_key
            from app.core.cache import redis_manager
            cache_key = schema_cache_key(tenant_admin.tenant_id)
            await redis_manager.delete(cache_key)

            return success(data={"id": override.id})

        @router.delete("/{policy_id}/override", summary="删除策略覆盖")
        @action_delete()
        async def remove_override(
            request: Request,
            db: DbSession,
            policy_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """删除租户策略覆盖（恢复到全局策略）"""
            service = self.get_service(db, tenant_admin.tenant_id)
            await service.remove_override(policy_id)
            await db.commit()

            # 清除 Redis 缓存
            from app.ai.constants import schema_cache_key
            from app.core.cache import redis_manager
            cache_key = schema_cache_key(tenant_admin.tenant_id)
            await redis_manager.delete(cache_key)

            return deleted()

    @staticmethod
    def get_service(db, tenant_id: int) -> AITablePolicyOverrideService:
        return AITablePolicyOverrideService(db, tenant_id)


router = TenantAITablePolicyController.get_router()

__all__ = ["TenantAITablePolicyController", "router"]
