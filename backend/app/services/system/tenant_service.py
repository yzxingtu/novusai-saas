"""
企业服务 / Tenant Service

提供企业的业务逻辑
Provides tenant business logic.
"""

import secrets
import string
from datetime import datetime
from typing import Any

from sqlalchemy import select

from app.core.base_service import GlobalService
from app.core.i18n import _
from app.core.logging import LogManager
from app.core.security import get_password_hash
from app.enums import ErrorCode, RoleType
from app.exceptions import BusinessException, NotFoundException
from app.models.auth.tenant_user_role import TenantUserRole
from app.models.org import TenantOrgNode
from app.models.tenant.tenant import Tenant
from app.models.tenant.tenant_admin import TenantAdmin
from app.models.tenant.tenant_plan import TenantPlan
from app.plugins.tenant_plan_preflight import run_tenant_plan_preflight
from app.repositories.system.tenant_repository import TenantRepository
from app.services.system.tenant_domain_service import TenantDomainService

logger = LogManager.get_logger("app")


class TenantService(GlobalService[Tenant, TenantRepository]):
    """
    企业服务 / Tenant service.

    提供企业特有的业务方法（全局级别，由平台管理员操作）
    """

    model = Tenant
    repository_class = TenantRepository

    async def _get_plan_preflight_snapshot(
        self,
        plan_id: int,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Load plan features/quota snapshot for preflight.
        / 为前置校验加载套餐 features/quota 快照。
        """
        result = await self.db.execute(
            select(TenantPlan).where(
                TenantPlan.id == plan_id,
                TenantPlan.is_deleted.is_(False),
            )
        )
        plan = result.scalar_one_or_none()
        if plan is None:
            raise NotFoundException(message=_("tenant_plan.not_found"))

        return dict(plan.features or {}), dict(plan.quota or {})

    async def _run_plan_preflight(
        self,
        *,
        operation: str,
        plan_id: int,
        tenant_id: int | None,
        features: dict[str, Any],
        quota: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> None:
        """Run host-level tenant plan preflight and raise on denial.
        / 运行宿主级套餐前置校验，若被拒绝则抛异常。
        """
        result = await run_tenant_plan_preflight(
            {
                "operation": operation,
                "plan_id": plan_id,
                "tenant_id": tenant_id,
                "features": dict(features or {}),
                "quota": dict(quota or {}),
                "context": dict(context or {}),
            }
        )
        if result.get("allowed", True):
            return

        raise BusinessException(
            message=result.get("message") or _("common.failed"),
            data={
                "reason_code": result.get("reason_code") or "preflight_denied",
                "details": result.get("details") or {},
                "operation": operation,
                "plan_id": plan_id,
                "tenant_id": tenant_id,
            },
        )

    async def get_by_code(self, code: str) -> Tenant | None:
        """
        根据编码获取企业 / Get tenant by code.

        Args:
            code: 企业编码

        Returns:
            企业实例或 None
        """
        return await self.repo.get_by_code(code)

    async def _generate_tenant_code(self) -> str:
        """
        生成唯一的企业编码 / Generate unique tenant code.

        格式: t + 8位小写字母数字（如 t3a8k2m9x）

        Returns:
            唯一的企业编码
        """
        charset = string.ascii_lowercase + string.digits
        max_attempts = 10

        for _attempt in range(max_attempts):
            # 生成 t + 8位随机字符 / Generate t + 8 random chars
            random_part = ''.join(secrets.choice(charset) for _ in range(8))
            code = f"t{random_part}"

            # 检查是否已存在 / Check exists
            if not await self.repo.code_exists(code):
                return code

        # 极端情况：多次尝试后仍重复，加长随机部分 / Rare: still duplicate after retries; lengthen random part
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
        创建企业 / Create tenant.

        Args:
            name: 企业名称
            admin_username: 企业超级管理员用户名
            admin_email: 企业超级管理员邮箱
            admin_password: 企业超级管理员密码
            contact_name: 联系人姓名
            contact_phone: 联系人电话
            contact_email: 联系人邮箱
            plan_id: 套餐 ID（新版）
            plan: 套餐类型（已废弃，保留向后兼容）
            quota: 配额配置（可覆盖套餐默认值）
            expires_at: 到期时间
            remark: 备注

        Returns:
            创建的企业
        """
        # 自动生成企业编码 / Auto-generate tenant code
        code = await self._generate_tenant_code()

        if plan_id is not None:
            plan_features, plan_quota = await self._get_plan_preflight_snapshot(plan_id)
            await self._run_plan_preflight(
                operation="tenant_create",
                plan_id=plan_id,
                tenant_id=None,
                features=plan_features,
                quota=plan_quota,
                context={"tenant_code": code, "tenant_name": name},
            )

        # 创建企业 / Create tenant
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

        # 创建默认域名 / Create default domain
        domain_service = TenantDomainService(self.db)
        await domain_service.create_default_domain(tenant.id, tenant.code)

        # 创建企业组织架构根节点 / Create tenant org root node
        root_node = await self._create_tenant_root_node(tenant.id, tenant.name)

        # 创建企业超级管理员（owner）
        await self._create_tenant_owner(
            tenant_id=tenant.id,
            username=admin_username,
            email=admin_email,
            password=admin_password,
            phone=contact_phone,
            root_node=root_node,
        )

        # 异步发送欢迎邮件（失败不阻塞创建流程） / Async welcome email (failure does not block create)
        self._send_welcome_email(
            tenant_name=name,
            admin_name=admin_username,
            admin_email=admin_email,
            tenant_id=tenant.id,
        )

        # 创建默认用户角色 / Create default user roles
        await self._create_default_user_role(tenant.id)

        # 自动绑定插件（scope=global/all_tenants 的已启用插件）
        await self._provision_tenant_plugins(tenant.id)

        return tenant

    @staticmethod
    def _send_welcome_email(
        tenant_name: str,
        admin_name: str,
        admin_email: str,
        tenant_id: int,
    ) -> None:
        """
        发送企业欢迎邮件（通过统一通知系统）/ Send tenant welcome email (via notification system).

        走 notification 队列异步发送，失败不影响企业创建流程。
        """
        _ = admin_email
        try:
            from app.services.common.email_templates import render_welcome_email
            from app.services.common.notification_service import notify_sync

            login_url = "/tenant/login"
            subject, html_body, text_body = render_welcome_email(
                tenant_name=tenant_name,
                admin_name=admin_name,
                login_url=login_url,
            )
            notify_sync(
                template_code="system.tenant_welcome",
                recipients=[("tenant_admin", 0)],
                data={"tenant_name": tenant_name, "admin_name": admin_name},
                tenant_id=tenant_id,
                email_html=html_body,
                email_subject=subject,
                email_text=text_body,
            )
        except Exception as e:
            logger.warning("Failed to send welcome notification: {}", str(e))

    async def _create_tenant_root_node(self, tenant_id: int, tenant_name: str) -> TenantOrgNode:
        """
        为企业创建组织架构根节点 / Create org root node for tenant.

        Args:
            tenant_id: 企业 ID
            tenant_name: 企业名称（用作根节点名称）

        Returns:
            创建的根节点
        """
        root_node = TenantOrgNode(
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
        root_node: TenantOrgNode,
        phone: str | None = None,
    ) -> TenantAdmin:
        """
        为企业创建超级管理员（owner）/ Create tenant super admin (owner).

        Args:
            tenant_id: 企业 ID
            username: 用户名
            email: 邮箱
            password: 明文密码
            root_node: 企业根节点
            phone: 手机号

        Returns:
            创建的管理员
        """
        owner = TenantAdmin(
            tenant_id=tenant_id,
            username=username,
            email=email,
            phone=phone,
            password_hash=get_password_hash(password),
            is_active=True,
            is_owner=True,
            role_id=None,
            org_node_id=root_node.id,
        )

        self.db.add(owner)
        await self.db.flush()

        # 设置根节点的负责人为 owner
        root_node.leader_id = owner.id
        await self.db.flush()

        return owner

    async def _create_default_user_role(self, tenant_id: int) -> TenantUserRole:
        """
        为新企业创建默认用户角色 / Create default user role for new tenant.

        创建 code='default_user' 的系统内置角色，作为用户注册时的默认角色。
        该角色 is_system=True，不可被企业管理员删除。

        Args:
            tenant_id: 企业 ID

        Returns:
            创建的默认用户角色
        """
        default_role = TenantUserRole(
            tenant_id=tenant_id,
            name=_("role.default_user_name"),
            code="default_user",
            description=_("role.default_user_description"),
            is_system=True,
            is_active=True,
            sort_order=0,
        )

        self.db.add(default_role)
        await self.db.flush()

        logger.info(
            "Created default user role (id={}) for tenant {}",
            default_role.id, tenant_id,
        )

        # 将默认角色 ID 写入企业配置
        from app.configs.service import ConfigService
        config_service = ConfigService(self.db)
        await config_service.set_tenant_config(
            tenant_id,
            "user_default_role_id",
            default_role.id,
        )

        return default_role

    async def _provision_tenant_plugins(self, tenant_id: int) -> None:
        """
        插件绑定由管理员在管理端自行配置，新建企业不自动绑定。
        Plugin binding is configured by admins in the admin panel; new tenants are not auto-bound.
        """
        pass

    async def reset_owner_password(
        self,
        tenant_id: int,
        new_password: str,
    ) -> TenantAdmin:
        """
        重置企业超级管理员密码 / Reset tenant owner password.

        Args:
            tenant_id: 企业 ID
            new_password: 新密码（明文）

        Returns:
            更新后的管理员

        Raises:
            NotFoundException: 企业或超级管理员不存在
        """
        from sqlalchemy import select

        # 检查企业是否存在 / Check tenant exists
        tenant = await self.get_by_id(tenant_id)
        if not tenant:
            raise NotFoundException(
                message=_("tenant.not_found"),
            )

        # 查找企业的超级管理员（owner）
        result = await self.db.execute(
            select(TenantAdmin).where(
                TenantAdmin.tenant_id == tenant_id,
                TenantAdmin.is_owner.is_(True),
                TenantAdmin.is_deleted.is_(False),
            )
        )
        owner = result.scalar_one_or_none()

        if not owner:
            raise NotFoundException(
                message=_("tenant.owner_not_found"),
            )

        # 更新密码 / Update password
        owner.password_hash = get_password_hash(new_password)
        await self.db.flush()

        # 异步发送密码重置通知邮件（失败不阻塞重置流程） / Async password-reset email (failure does not block reset)
        if owner.email:
            self._send_password_reset_notification(
                user_name=owner.username,
                user_email=owner.email,
                tenant_id=tenant_id,
            )

        return owner

    @staticmethod
    def _send_password_reset_notification(
        user_name: str,
        user_email: str,
        tenant_id: int,
    ) -> None:
        """
        发送密码重置通知（通过统一通知系统）/ Send password reset notification (via notification system).

        走 notification 队列异步发送。
        """
        _ = user_email
        try:
            from app.services.common.email_templates import render_password_reset_email
            from app.services.common.notification_service import notify_sync

            login_url = "/tenant/login"
            subject, html_body, text_body = render_password_reset_email(
                user_name=user_name,
                reset_url=login_url,
                expire_minutes=0,
            )
            notify_sync(
                template_code="system.password_reset",
                recipients=[("tenant_admin", 0)],
                data={"user_name": user_name},
                tenant_id=tenant_id,
                email_html=html_body,
                email_subject=subject,
                email_text=text_body,
            )
        except Exception as e:
            logger.warning("Failed to send password reset notification: {}", str(e))

    async def update_tenant(
        self,
        tenant_id: int,
        data: dict[str, Any],
    ) -> Tenant:
        """
        更新企业 / Update tenant.

        Args:
            tenant_id: 企业 ID
            data: 更新数据

        Returns:
            更新后的企业

        Raises:
            NotFoundException: 企业不存在
            BusinessException: 编码已存在
        """
        tenant = await self.get_by_id(tenant_id)
        if not tenant:
            raise NotFoundException(
                message=_("tenant.not_found"),
            )

        # 如果要更新编码，检查是否已被占用 / If updating code, check not already taken
        if (
            "code" in data
            and data["code"]
            and data["code"] != tenant.code
            and await self.repo.code_exists(data["code"], exclude_id=tenant_id)
        ):
            raise BusinessException(
                message=_("tenant.code_exists"),
                code=ErrorCode.DUPLICATE_ENTRY,
            )

        new_plan_id = data.get("plan_id")
        if "plan_id" in data and new_plan_id != tenant.plan_id and new_plan_id is not None:
            plan_features, plan_quota = await self._get_plan_preflight_snapshot(new_plan_id)
            await self._run_plan_preflight(
                operation="tenant_plan_switch",
                plan_id=new_plan_id,
                tenant_id=tenant_id,
                features=plan_features,
                quota=plan_quota,
                context={
                    "tenant_code": tenant.code,
                    "tenant_name": tenant.name,
                    "previous_plan_id": tenant.plan_id,
                },
            )

        result = await self.update(tenant_id, data)
        if not result:
            raise NotFoundException(message=_("tenant.not_found"))
        return result

    async def enable_tenant(self, tenant_id: int) -> Tenant:
        """
        启用企业 / Enable tenant.

        Args:
            tenant_id: 企业 ID

        Returns:
            更新后的企业

        Raises:
            NotFoundException: 企业不存在
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
        禁用企业 / Disable tenant.

        Args:
            tenant_id: 企业 ID

        Returns:
            更新后的企业

        Raises:
            NotFoundException: 企业不存在
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
        切换企业状态 / Toggle tenant status.

        Args:
            tenant_id: 企业 ID
            is_active: 是否启用

        Returns:
            更新后的企业

        Raises:
            NotFoundException: 企业不存在
        """
        if is_active:
            return await self.enable_tenant(tenant_id)
        else:
            return await self.disable_tenant(tenant_id)


__all__ = ["TenantService"]
