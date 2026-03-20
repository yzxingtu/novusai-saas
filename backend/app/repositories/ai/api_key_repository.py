"""
AI 供应商密钥 Repository / AI API Key Repository

处理 AI API Key 数据访问 / Handles AI API key data access.
"""

from sqlalchemy import and_, select

from app.core.base_model import utc_now
from app.core.base_repository import BaseRepository
from app.enums.common import ResourceScopeEnum
from app.models.ai import ProviderApiKey

# 企业端可回退使用的平台密钥（非 admin_only）/ Platform keys visible to tenant-side AI
_TENANT_PLATFORM_KEY_SCOPES: frozenset[str] = frozenset({
    ResourceScopeEnum.GLOBAL_SHARED.value,
    ResourceScopeEnum.ALL_TENANTS.value,  # legacy DB rows / 历史数据
})


class ProviderApiKeyRepository(BaseRepository[ProviderApiKey]):
    """
    AI API Key Repository / AI API Key 数据访问.

    提供 AI API Key 的数据访问操作
    """

    model = ProviderApiKey

    async def get_available_key(
        self,
        provider_id: int,
        tenant_id: int | None = None
    ) -> ProviderApiKey | None:
        """
        获取可用的 API Key / Get available API Key (tenant first, then platform fallback).

        优先使用企业自己的 Key，否则回退到平台 Key

        Args:
            provider_id: 供应商 ID
            tenant_id: 企业 ID

        Returns:
            ProviderApiKey 对象或 None
        """
        # 先查找企业级 Key
        if tenant_id:
            stmt = select(ProviderApiKey).where(
                ProviderApiKey.provider_id == provider_id,
                ProviderApiKey.owner_tenant_id == tenant_id,
                ProviderApiKey.is_active.is_(True),
                ProviderApiKey.is_deleted.is_(False)
            ).order_by(
                ProviderApiKey.created_at.desc()
            )
            result = await self.db.execute(stmt)
            key = result.scalar_one_or_none()

            if key and key.is_available():
                return key

        # 回退到平台级 Key：企业上下文排除 admin_only；平台上下文可使用含 admin_only 的密钥
        fallback_conditions = [
            ProviderApiKey.provider_id == provider_id,
            ProviderApiKey.owner_tenant_id.is_(None),
            ProviderApiKey.is_active.is_(True),
            ProviderApiKey.is_deleted.is_(False),
        ]
        if tenant_id is not None:
            fallback_conditions.append(
                ProviderApiKey.scope.in_(_TENANT_PLATFORM_KEY_SCOPES),
            )

        stmt = select(ProviderApiKey).where(
            *fallback_conditions
        ).order_by(
            ProviderApiKey.created_at.desc()
        )

        result = await self.db.execute(stmt)
        key = result.scalar_one_or_none()

        if key and key.is_available():
            return key

        return None

    async def get_available_keys_with_load_balancing(
        self,
        provider_id: int,
        tenant_id: int | None = None
    ) -> list[ProviderApiKey]:
        """
        获取所有可用的 API Key（用于负载均衡）/ Get all available API Keys (for load balancing).

        Args:
            provider_id: 供应商 ID
            tenant_id: 企业 ID

        Returns:
            ProviderApiKey 列表（按使用次数升序，实现负载均衡）
        """
        base_conditions = [
            ProviderApiKey.provider_id == provider_id,
            ProviderApiKey.is_active.is_(True),
            ProviderApiKey.is_deleted.is_(False),
        ]

        if tenant_id:
            # 优先使用企业级 Key
            tenant_conditions = base_conditions + [
                ProviderApiKey.owner_tenant_id == tenant_id,
            ]
            stmt = select(ProviderApiKey).where(
                and_(*tenant_conditions)
            ).order_by(
                ProviderApiKey.usage_count.asc(),
                ProviderApiKey.created_at.desc()
            )
            result = await self.db.execute(stmt)
            keys = [key for key in result.scalars().all() if key.is_available()]
            if keys:
                return keys

            # 回退到平台级 Key（排除 admin_only） / Fallback to platform key (exclude admin_only)
            platform_conditions = base_conditions + [
                ProviderApiKey.owner_tenant_id.is_(None),
                ProviderApiKey.scope.in_(_TENANT_PLATFORM_KEY_SCOPES),
            ]
            stmt = select(ProviderApiKey).where(
                and_(*platform_conditions)
            ).order_by(
                ProviderApiKey.usage_count.asc(),
                ProviderApiKey.created_at.desc()
            )
            result = await self.db.execute(stmt)
            return [key for key in result.scalars().all() if key.is_available()]
        else:
            # 平台级调用，只使用平台级 Key
            conditions = base_conditions + [
                ProviderApiKey.owner_tenant_id.is_(None),
            ]
            stmt = select(ProviderApiKey).where(
                and_(*conditions)
            ).order_by(
                ProviderApiKey.usage_count.asc(),
                ProviderApiKey.created_at.desc()
            )
            result = await self.db.execute(stmt)
            return [key for key in result.scalars().all() if key.is_available()]

    async def get_keys_by_provider(
        self,
        provider_id: int,
        tenant_id: int | None = None,
        include_deleted: bool = False
    ) -> list[ProviderApiKey]:
        """
        获取供应商的所有 API Key / Get all API Keys for provider.

        Args:
            provider_id: 供应商 ID
            tenant_id: 企业 ID（None 表示获取所有 Key）
            include_deleted: 是否包含已删除的记录

        Returns:
            ProviderApiKey 列表
        """
        conditions = [
            ProviderApiKey.provider_id == provider_id
        ]

        if not include_deleted:
            conditions.append(ProviderApiKey.is_deleted.is_(False))

        if tenant_id is not None:
            conditions.append(ProviderApiKey.owner_tenant_id == tenant_id)

        stmt = select(ProviderApiKey).where(
            and_(*conditions)
        ).order_by(
            ProviderApiKey.created_at.desc()
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_next_available_key(
        self,
        provider_id: int,
        exclude_key_id: int,
        tenant_id: int | None = None,
    ) -> ProviderApiKey | None:
        """
        获取下一个可用 Key（排除当前 Key，用于重试轮换）/ Get next available key (exclude current, for retry rotation).

        Args:
            provider_id: 供应商 ID
            exclude_key_id: 排除的 Key ID
            tenant_id: 企业 ID

        Returns:
            ProviderApiKey 对象或 None
        """
        if tenant_id:
            stmt = select(ProviderApiKey).where(
                ProviderApiKey.provider_id == provider_id,
                ProviderApiKey.id != exclude_key_id,
                ProviderApiKey.is_active.is_(True),
                ProviderApiKey.is_deleted.is_(False),
                (
                    (ProviderApiKey.owner_tenant_id == tenant_id)
                    | (
                        ProviderApiKey.owner_tenant_id.is_(None)
                        & ProviderApiKey.scope.in_(_TENANT_PLATFORM_KEY_SCOPES)
                    )
                ),
            ).order_by(ProviderApiKey.created_at.desc())
        else:
            stmt = select(ProviderApiKey).where(
                ProviderApiKey.provider_id == provider_id,
                ProviderApiKey.id != exclude_key_id,
                ProviderApiKey.owner_tenant_id.is_(None),
                ProviderApiKey.is_active.is_(True),
                ProviderApiKey.is_deleted.is_(False),
            ).order_by(ProviderApiKey.created_at.desc())

        result = await self.db.execute(stmt)
        next_key = result.scalar_one_or_none()

        if next_key and next_key.is_available():
            return next_key

        return None

    async def update_usage_count(
        self,
        key_id: int,
        increment: int = 1
    ) -> None:
        """
        更新 API Key 使用次数 / Update API Key usage count.

        Args:
            key_id: API Key ID
            increment: 增量
        """
        key = await self.get_by_id(key_id)
        if key:
            key.usage_count += increment
            key.last_used_at = utc_now()
            await self.db.commit()


__all__ = [
    "ProviderApiKeyRepository",
]
