"""
租户用户仓储

提供租户业务用户的数据访问操作（租户隔离）
"""

from sqlalchemy import or_, select

from app.core.base_repository import TenantRepository
from app.models.tenant.tenant_user import TenantUser


class TenantUserRepository(TenantRepository[TenantUser]):
    """
    租户用户仓储

    提供租户用户特有的数据访问方法，自动过滤租户 ID
    """

    model = TenantUser

    _scope_fields = {
        "tenant": {
            "id", "username", "email", "phone",
            "is_active", "nickname", "role_id", "gender",
            "approval_status", "created_at", "updated_at",
            "last_login_at",
        },
    }

    async def get_by_username(self, username: str) -> TenantUser | None:
        """根据用户名获取租户用户（租户内）"""
        return await self.get_one_by(username=username, tenant_id=self.tenant_id)

    async def get_by_email(self, email: str) -> TenantUser | None:
        """根据邮箱获取租户用户（租户内）"""
        return await self.get_one_by(email=email, tenant_id=self.tenant_id)

    async def get_by_username_or_email(
        self,
        username_or_email: str,
    ) -> TenantUser | None:
        """根据用户名或邮箱获取租户用户（用于登录）"""
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
        """检查用户名是否已存在（租户内唯一）"""
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
        """检查邮箱是否已存在（租户内唯一）"""
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
        """检查手机号是否已存在（租户内唯一）"""
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


__all__ = ["TenantUserRepository"]
