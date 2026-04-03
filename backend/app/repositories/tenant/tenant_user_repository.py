"""
企业用户仓储 / Tenant User Repository

提供企业业务用户的数据访问操作（企业隔离）
Provides tenant business user data access operations (tenant-isolated).
"""

from sqlalchemy import or_, select

from app.core.base_repository import TenantRepository
from app.models.auth.tenant_user_role import TenantUserRole
from app.models.org import TenantOrgNode
from app.models.tenant.tenant_user import TenantUser


class TenantUserRepository(TenantRepository[TenantUser]):
    """
    企业用户仓储 / Tenant user repository.

    提供企业用户特有的数据访问方法，自动过滤企业 ID
    """

    model = TenantUser

    _scope_fields = {
        "tenant": {
            "id",
            "username",
            "email",
            "phone",
            "is_active",
            "nickname",
            "role_id",
            "org_node_id",
            "gender",
            "approval_status",
            "created_at",
            "updated_at",
            "last_login_at",
        },
    }

    async def get_by_username(self, username: str) -> TenantUser | None:
        """根据用户名获取企业用户（企业内） / Get tenant user by username (within tenant)."""
        return await self.get_one_by(username=username, tenant_id=self.tenant_id)

    async def get_by_email(self, email: str) -> TenantUser | None:
        """根据邮箱获取企业用户（企业内） / Get tenant user by email (within tenant)."""
        return await self.get_one_by(email=email, tenant_id=self.tenant_id)

    async def get_by_username_or_email(
        self,
        username_or_email: str,
    ) -> TenantUser | None:
        """根据用户名或邮箱获取企业用户（用于登录） / Get tenant user by username or email (for login)."""
        query = select(self.model).where(
            self.model.tenant_id == self.tenant_id,
            self.model.is_deleted.is_(False),
            or_(
                self.model.username == username_or_email,
                self.model.email == username_or_email,
            ),
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def username_exists(
        self,
        username: str,
        exclude_id: int | None = None,
    ) -> bool:
        """检查用户名是否已存在（企业内唯一） / Check if username already exists (unique within tenant)."""
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
        """检查邮箱是否已存在（企业内唯一） / Check if email already exists (unique within tenant)."""
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
        """检查手机号是否已存在（企业内唯一） / Check if phone already exists (unique within tenant)."""
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

    async def permission_role_exists(self, role_id: int) -> bool:
        """检查权限角色是否存在（企业内） / Check whether permission role exists within tenant."""
        query = select(TenantUserRole.id).where(
            TenantUserRole.id == role_id,
            TenantUserRole.tenant_id == self.tenant_id,
            TenantUserRole.is_deleted.is_(False),
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None

    async def org_node_exists(self, org_node_id: int) -> bool:
        """检查组织节点是否存在（企业内） / Check whether org node exists within tenant."""
        query = select(TenantOrgNode.id).where(
            TenantOrgNode.id == org_node_id,
            TenantOrgNode.tenant_id == self.tenant_id,
            TenantOrgNode.is_deleted.is_(False),
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None


__all__ = ["TenantUserRepository"]
