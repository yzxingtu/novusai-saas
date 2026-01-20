"""
租户服务

提供租户的业务逻辑
"""

import secrets
import string
from datetime import datetime
from typing import Any

from app.core.base_service import GlobalService
from app.core.i18n import _
from app.core.security import get_password_hash
from app.enums import ErrorCode, RoleType
from app.exceptions import BusinessException, NotFoundException
from app.models.tenant.tenant import Tenant
from app.models.tenant.tenant_admin import TenantAdmin
from app.models.auth.tenant_admin_role import TenantAdminRole
from app.repositories.system.tenant_repository import TenantRepository
from app.services.tenant.tenant_domain_service import TenantDomainService


class TenantService(GlobalService[Tenant, TenantRepository]):
    """
    租户服务
    
    提供租户特有的业务方法（全局级别，由平台管理员操作）
    """
    
    model = Tenant
    repository_class = TenantRepository
    
    async def get_by_code(self, code: str) -> Tenant | None:
        """
        根据编码获取租户
        
        Args:
            code: 租户编码
        
        Returns:
            租户实例或 None
        """
        return await self.repo.get_by_code(code)
    
    async def _generate_tenant_code(self) -> str:
        """
        生成唯一的租户编码
        
        格式: t + 8位小写字母数字（如 t3a8k2m9x）
        
        Returns:
            唯一的租户编码
        """
        charset = string.ascii_lowercase + string.digits
        max_attempts = 10
        
        for _ in range(max_attempts):
            # 生成 t + 8位随机字符
            random_part = ''.join(secrets.choice(charset) for _ in range(8))
            code = f"t{random_part}"
            
            # 检查是否已存在
            if not await self.repo.code_exists(code):
                return code
        
        # 极端情况：多次尝试后仍重复，加长随机部分
        random_part = ''.join(secrets.choice(charset) for _ in range(12))
        return f"t{random_part}"
    
    async def create_tenant(
        self,
        name: str,
        admin_username: str,
        admin_email: str,
        admin_password: str,
        contact_name: str | None = None,
        contact_phone: str | None = None,
        contact_email: str | None = None,
        plan_id: int | None = None,
        plan: str | None = None,
        quota: dict | None = None,
        expires_at: datetime | None = None,
        remark: str | None = None,
    ) -> Tenant:
        """
        创建租户
        
        Args:
            name: 租户名称
            admin_username: 租户超级管理员用户名
            admin_email: 租户超级管理员邮箱
            admin_password: 租户超级管理员密码
            contact_name: 联系人姓名
            contact_phone: 联系人电话
            contact_email: 联系人邮箱
            plan_id: 套餐 ID（新版）
            plan: 套餐类型（已废弃，保留向后兼容）
            quota: 配额配置（可覆盖套餐默认值）
            expires_at: 到期时间
            remark: 备注
        
        Returns:
            创建的租户
        """
        # 自动生成租户编码
        code = await self._generate_tenant_code()
        
        # 创建租户
        data = {
            "code": code,
            "name": name,
            "contact_name": contact_name,
            "contact_phone": contact_phone,
            "contact_email": contact_email,
            "plan_id": plan_id,
            "plan": plan,
            "quota": quota,
            "expires_at": expires_at,
            "remark": remark,
            "is_active": True,
        }
        
        tenant = await self.create(data)
        
        # 创建默认域名
        domain_service = TenantDomainService(self.db)
        await domain_service.create_default_domain(tenant.id, tenant.code)
        
        # 创建租户组织架构根节点
        root_node = await self._create_tenant_root_node(tenant.id, tenant.name)
        
        # 创建租户超级管理员（owner）
        await self._create_tenant_owner(
            tenant_id=tenant.id,
            username=admin_username,
            email=admin_email,
            password=admin_password,
            root_node=root_node,
        )
        
        return tenant
    
    async def _create_tenant_root_node(self, tenant_id: int, tenant_name: str) -> TenantAdminRole:
        """
        为租户创建组织架构根节点
        
        Args:
            tenant_id: 租户 ID
            tenant_name: 租户名称（用作根节点名称）
        
        Returns:
            创建的根节点
        """
        root_node = TenantAdminRole(
            tenant_id=tenant_id,
            name=tenant_name,
            code="tenant_root",
            description=_("role.tenant_root_description"),
            is_system=True,
            is_active=True,
            sort_order=0,
            parent_id=None,
            level=1,
            type=RoleType.DEPARTMENT.value,
            allow_members=True,
        )
        
        self.db.add(root_node)
        await self.db.flush()
        
        # 更新 path
        root_node.path = f"/{root_node.id}/"
        await self.db.flush()
        
        return root_node
    
    async def _create_tenant_owner(
        self,
        tenant_id: int,
        username: str,
        email: str,
        password: str,
        root_node: TenantAdminRole,
    ) -> TenantAdmin:
        """
        为租户创建超级管理员（owner）
        
        Args:
            tenant_id: 租户 ID
            username: 用户名
            email: 邮箱
            password: 明文密码
            root_node: 租户根节点
        
        Returns:
            创建的管理员
        """
        owner = TenantAdmin(
            tenant_id=tenant_id,
            username=username,
            email=email,
            password_hash=get_password_hash(password),
            is_active=True,
            is_owner=True,
            role_id=root_node.id,
        )
        
        self.db.add(owner)
        await self.db.flush()
        
        # 设置根节点的负责人为 owner
        root_node.leader_id = owner.id
        await self.db.flush()
        
        return owner
    
    async def update_tenant(
        self,
        tenant_id: int,
        data: dict[str, Any],
    ) -> Tenant:
        """
        更新租户
        
        Args:
            tenant_id: 租户 ID
            data: 更新数据
        
        Returns:
            更新后的租户
        
        Raises:
            NotFoundException: 租户不存在
            BusinessException: 编码已存在
        """
        tenant = await self.get_by_id(tenant_id)
        if not tenant:
            raise NotFoundException(
                message=_("tenant.not_found"),
            )
        
        # 如果要更新编码，检查是否已被占用
        if "code" in data and data["code"]:
            if data["code"] != tenant.code:
                if await self.repo.code_exists(data["code"], exclude_id=tenant_id):
                    raise BusinessException(
                        message=_("tenant.code_exists"),
                        code=ErrorCode.DUPLICATE_ENTRY,
                    )
        
        result = await self.update(tenant_id, data)
        if not result:
            raise NotFoundException(message=_("tenant.not_found"))
        return result
    
    async def enable_tenant(self, tenant_id: int) -> Tenant:
        """
        启用租户
        
        Args:
            tenant_id: 租户 ID
        
        Returns:
            更新后的租户
        
        Raises:
            NotFoundException: 租户不存在
        """
        tenant = await self.get_by_id(tenant_id)
        if not tenant:
            raise NotFoundException(
                message=_("tenant.not_found"),
            )
        
        result = await self.update(tenant_id, {"is_active": True})
        if not result:
            raise NotFoundException(message=_("tenant.not_found"))
        return result
    
    async def disable_tenant(self, tenant_id: int) -> Tenant:
        """
        禁用租户
        
        Args:
            tenant_id: 租户 ID
        
        Returns:
            更新后的租户
        
        Raises:
            NotFoundException: 租户不存在
        """
        tenant = await self.get_by_id(tenant_id)
        if not tenant:
            raise NotFoundException(
                message=_("tenant.not_found"),
            )
        
        result = await self.update(tenant_id, {"is_active": False})
        if not result:
            raise NotFoundException(message=_("tenant.not_found"))
        return result
    
    async def toggle_status(self, tenant_id: int, is_active: bool) -> Tenant:
        """
        切换租户状态
        
        Args:
            tenant_id: 租户 ID
            is_active: 是否启用
        
        Returns:
            更新后的租户
        
        Raises:
            NotFoundException: 租户不存在
        """
        if is_active:
            return await self.enable_tenant(tenant_id)
        else:
            return await self.disable_tenant(tenant_id)


__all__ = ["TenantService"]
