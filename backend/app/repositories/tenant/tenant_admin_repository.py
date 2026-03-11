"""
租户管理员仓储 / Tenant Admin Repository

提供租户管理员的数据访问操作（租户隔离）
Provides tenant admin data access operations (tenant-isolated).
"""

from sqlalchemy import or_, select

from app.core.base_repository import TenantRepository
from app.models.tenant.tenant_admin import TenantAdmin


class TenantAdminRepository(TenantRepository[TenantAdmin]):
    """
    租户管理员仓储

    提供租户管理员特有的数据访问方法，自动过滤租户 ID
    """

    model = TenantAdmin

    # 按 scope 限制可过滤字段
    _scope_fields = {
        # 平台管理员查看租户管理员列表
        "admin": {
            "id", "tenant_id", "username", "email", "phone",
            "is_active", "is_owner", "nickname", "role_id",
            "created_at", "updated_at",
        },
        # 租户管理员查看本租户管理员列表
        "tenant": {
            "id", "username", "email", "phone",
            "is_active", "is_owner", "nickname", "role_id",
            "created_at", "updated_at",
        },
    }

    async def get_by_username(self, username: str) -> TenantAdmin | None:
        """
        根据用户名获取租户管理员（租户内）

        Args:
            username: 用户名

        Returns:
            租户管理员实例或 None
        """
        return await self.get_one_by(username=username, tenant_id=self.tenant_id)

    async def get_by_email(self, email: str) -> TenantAdmin | None:
        """
        根据邮箱获取租户管理员（租户内）

        Args:
            email: 邮箱

        Returns:
            租户管理员实例或 None
        """
        return await self.get_one_by(email=email, tenant_id=self.tenant_id)

    async def get_by_username_or_email(
        self,
        username_or_email: str,
    ) -> TenantAdmin | None:
        """
        根据用户名或邮箱获取租户管理员（用于登录）

        Args:
            username_or_email: 用户名或邮箱

        Returns:
            租户管理员实例或 None
        """
        query = select(self.model).where(
            self.model.tenant_id == self.tenant_id,
            self.model.is_deleted.is_(False),
            or_(
                self.model.username == username_or_email,
                self.model.email == username_or_email,
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def username_exists(
        self,
        username: str,
        exclude_id: int | None = None,
    ) -> bool:
        """
        检查用户名是否已存在（租户内唯一）

        Args:
            username: 用户名
            exclude_id: 排除的 ID（用于更新时排除自身）

        Returns:
            是否存在
        """
        query = select(self.model.id).where(
            self.model.tenant_id == self.tenant_id,
            self.model.username == username,
            self.model.is_deleted.is_(False),
        )
        if exclude_id:
            query = query.where(self.model.id != exclude_id)

        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None

    async def email_exists(
        self,
        email: str,
        exclude_id: int | None = None,
    ) -> bool:
        """
        检查邮箱是否已存在（租户内唯一）

        Args:
            email: 邮箱
            exclude_id: 排除的 ID

        Returns:
            是否存在
        """
        query = select(self.model.id).where(
            self.model.tenant_id == self.tenant_id,
            self.model.email == email,
            self.model.is_deleted.is_(False),
        )
        if exclude_id:
            query = query.where(self.model.id != exclude_id)

        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None

    async def phone_exists(
        self,
        phone: str,
        exclude_id: int | None = None,
    ) -> bool:
        """
        检查手机号是否已存在（租户内唯一）

        Args:
            phone: 手机号
            exclude_id: 排除的 ID

        Returns:
            是否存在
        """
        if not phone:
            return False

        query = select(self.model.id).where(
            self.model.tenant_id == self.tenant_id,
            self.model.phone == phone,
            self.model.is_deleted.is_(False),
        )
        if exclude_id:
            query = query.where(self.model.id != exclude_id)

        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None

    async def batch_load_user_info(
        self,
        user_ids: set[int],
    ) -> dict[int, dict]:
        """
        批量加载租户管理员摘要信息

        Args:
            user_ids: 用户 ID 集合

        Returns:
            {user_id: {"id", "username", "nickname", "avatar"}} 映射
        """
        if not user_ids:
            return {}
        stmt = select(
            TenantAdmin.id, TenantAdmin.username,
            TenantAdmin.nickname, TenantAdmin.avatar,
        ).where(
            TenantAdmin.id.in_(user_ids),
            TenantAdmin.is_deleted.is_(False),
        )
        result = await self.db.execute(stmt)
        return {
            row.id: {
                "id": row.id,
                "username": row.username,
                "nickname": row.nickname,
                "avatar": row.avatar,
            }
            for row in result.all()
        }

    async def get_owner(self) -> TenantAdmin | None:
        """
        获取租户所有者

        Returns:
            租户所有者或 None
        """
        return await self.get_one_by(is_owner=True, tenant_id=self.tenant_id)


__all__ = ["TenantAdminRepository"]
