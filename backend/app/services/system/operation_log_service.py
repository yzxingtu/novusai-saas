"""
操作日志服务

提供操作日志的业务逻辑
"""

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_service import GlobalService
from app.core.database import async_session_factory
from app.core.logging import LoggerMixin
from app.models.system.operation_log import OperationLog
from app.repositories.system.operation_log_repository import OperationLogRepository
from app.schemas.common.query import QuerySpec


# 日志辅助类（用于模块级函数中的日志记录）
class _ModuleLogger(LoggerMixin):
    """operation_log_service 模块日志器"""
    pass

_module_logger = _ModuleLogger()

if TYPE_CHECKING:
    from app.models.system.admin import Admin
    from app.models.tenant.tenant_admin import TenantAdmin


class OperationLogService(GlobalService[OperationLog, OperationLogRepository]):
    """
    操作日志服务

    提供操作日志的业务方法，包括：
    - 异步写入日志
    - 平台端日志查询
    - 租户端日志查询（自动隔离）
    - 批量删除日志
    """

    model = OperationLog
    repository_class = OperationLogRepository

    async def create_log(
        self,
        tenant_id: int | None,
        user_type: str,
        user_id: int | None,
        username: str | None,
        module: str | None,
        action: str | None,
        resource: str | None,
        method: str,
        path: str,
        query_params: dict | None = None,
        request_body: dict | None = None,
        status_code: int | None = None,
        response_code: int | None = None,
        response_message: str | None = None,
        ip: str | None = None,
        user_agent: str | None = None,
        duration_ms: int | None = None,
        nickname: str | None = None,
    ) -> OperationLog:
        """
        创建操作日志记录

        Args:
            tenant_id: 租户 ID（平台操作为 None）
            user_type: 用户类型
            user_id: 用户 ID
            username: 用户名
            module: 业务模块
            action: 操作类型
            resource: 资源标识
            method: HTTP 方法
            path: 请求路径
            query_params: 查询参数
            request_body: 请求体摘要（已脱敏）
            status_code: HTTP 状态码
            response_code: 业务响应码
            response_message: 响应消息
            ip: 客户端 IP
            user_agent: User-Agent
            duration_ms: 请求耗时（毫秒）
            nickname: 用户昵称

        Returns:
            创建的日志实例
        """
        data = {
            "tenant_id": tenant_id,
            "user_type": user_type,
            "user_id": user_id,
            "username": username,
            "nickname": nickname,
            "module": module,
            "action": action,
            "resource": resource,
            "method": method,
            "path": path,
            "query_params": query_params,
            "request_body": request_body,
            "status_code": status_code,
            "response_code": response_code,
            "response_message": response_message,
            "ip": ip,
            "user_agent": user_agent,
            "duration_ms": duration_ms,
        }

        return await self.repo.create_log(data)

    async def query_admin_logs(
        self,
        spec: QuerySpec,
    ) -> tuple[list[OperationLog], int]:
        """
        平台端查询日志

        平台管理员可查看所有日志

        Args:
            spec: 查询规格

        Returns:
            (日志列表, 总数)
        """
        return await self.query_list(spec, scope="admin")

    async def query_tenant_logs(
        self,
        tenant_id: int,
        spec: QuerySpec,
    ) -> tuple[list[OperationLog], int]:
        """
        租户端查询日志

        自动添加租户隔离

        Args:
            tenant_id: 租户 ID
            spec: 查询规格

        Returns:
            (日志列表, 总数)
        """
        return await self.repo.query_tenant_logs(tenant_id, spec)

    async def delete_logs(
        self,
        ids: list[int],
        soft: bool = True,
    ) -> int:
        """
        批量删除日志

        Args:
            ids: 日志 ID 列表
            soft: 是否软删除

        Returns:
            删除的记录数
        """
        return await self.repo.delete_logs_by_ids(ids, soft=soft)

    async def get_stats_by_module(
        self,
        tenant_id: int | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """
        按模块统计日志

        Args:
            tenant_id: 租户 ID（可选）
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            统计结果列表
        """
        return await self.repo.get_stats_by_module(
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
        )

    async def get_stats_by_action(
        self,
        tenant_id: int | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """
        按操作类型统计日志

        Args:
            tenant_id: 租户 ID（可选）
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            统计结果列表
        """
        return await self.repo.get_stats_by_action(
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
        )

    # ==================== 基于权限的查询方法 ====================

    async def query_admin_logs_by_permission(
        self,
        admin: "Admin",
        spec: QuerySpec,
    ) -> tuple[list[OperationLog], int]:
        """
        平台端基于权限的日志查询

        - 超级管理员: 可查看所有平台端日志
        - 普通管理员: 只能查看自己及其角色子树下用户的日志

        Args:
            admin: 当前平台管理员
            spec: 查询规格

        Returns:
            (日志列表, 总数)
        """
        if admin.is_super:
            # 超级管理员可查看所有平台端日志
            return await self.repo.query_admin_logs_with_hierarchy(
                spec=spec,
                is_super=True,
            )

        # 普通管理员：获取下属用户 ID 列表
        subordinate_ids = await self._get_subordinate_admin_ids(admin)

        return await self.repo.query_admin_logs_with_hierarchy(
            spec=spec,
            is_super=False,
            subordinate_user_ids=subordinate_ids,
        )

    async def query_tenant_logs_by_permission(
        self,
        tenant_admin: "TenantAdmin",
        spec: QuerySpec,
    ) -> tuple[list[OperationLog], int]:
        """
        租户端基于权限的日志查询

        - 租户所有者: 可查看本租户所有日志
        - 普通管理员: 只能查看自己及其角色子树下用户的日志

        Args:
            tenant_admin: 当前租户管理员
            spec: 查询规格

        Returns:
            (日志列表, 总数)
        """
        if tenant_admin.is_owner:
            # 租户所有者可查看本租户所有日志
            return await self.repo.query_tenant_logs_with_hierarchy(
                tenant_id=tenant_admin.tenant_id,
                spec=spec,
                is_owner=True,
            )

        # 普通管理员：获取下属用户 ID 列表
        subordinate_ids = await self._get_subordinate_tenant_admin_ids(tenant_admin)

        return await self.repo.query_tenant_logs_with_hierarchy(
            tenant_id=tenant_admin.tenant_id,
            spec=spec,
            is_owner=False,
            subordinate_user_ids=subordinate_ids,
        )

    async def get_admin_operators(self) -> list[dict]:
        """
        获取平台端操作日志中的去重操作人列表（含头像）

        Returns:
            操作人列表 [{user_id, user_type, username, nickname, avatar}]
        """
        from app.models.system.admin import Admin as AdminModel

        # 按 user_id + user_type 去重，取最新的 username/nickname
        distinct_q = (
            select(
                OperationLog.user_id,
                OperationLog.user_type,
                func.max(OperationLog.username).label("username"),
                func.max(OperationLog.nickname).label("nickname"),
            )
            .where(
                OperationLog.is_deleted.is_(False),
                OperationLog.user_id.isnot(None),
                OperationLog.tenant_id.is_(None),
            )
            .group_by(
                OperationLog.user_id,
                OperationLog.user_type,
            )
        )
        result = await self.db.execute(distinct_q)
        rows = result.all()

        if not rows:
            return []

        # 批量查询 admin 头像
        admin_ids = [r[0] for r in rows if r[1] == "admin" and r[0]]
        avatar_map: dict[int, str | None] = {}
        if admin_ids:
            avatar_q = select(AdminModel.id, AdminModel.avatar).where(
                AdminModel.id.in_(admin_ids)
            )
            avatar_result = await self.db.execute(avatar_q)
            for aid, avatar in avatar_result.all():
                avatar_map[aid] = avatar

        operators = []
        for user_id, user_type, username, nickname in rows:
            operators.append({
                "user_id": user_id,
                "user_type": user_type,
                "username": username or "",
                "nickname": nickname,
                "avatar": avatar_map.get(user_id),
            })
        return operators

    async def get_tenant_operators(self, tenant_id: int) -> list[dict]:
        """
        获取租户端操作日志中的去重操作人列表（含头像）

        Args:
            tenant_id: 租户 ID

        Returns:
            操作人列表
        """
        from app.models.tenant.tenant_admin import TenantAdmin as TenantAdminModel

        # 按 user_id + user_type 去重，取最新的 username/nickname
        distinct_q = (
            select(
                OperationLog.user_id,
                OperationLog.user_type,
                func.max(OperationLog.username).label("username"),
                func.max(OperationLog.nickname).label("nickname"),
            )
            .where(
                OperationLog.is_deleted.is_(False),
                OperationLog.user_id.isnot(None),
                OperationLog.tenant_id == tenant_id,
            )
            .group_by(
                OperationLog.user_id,
                OperationLog.user_type,
            )
        )
        result = await self.db.execute(distinct_q)
        rows = result.all()

        if not rows:
            return []

        # 批量查询 tenant_admin 头像
        ta_ids = [r[0] for r in rows if r[1] == "tenant_admin" and r[0]]
        avatar_map: dict[int, str | None] = {}
        if ta_ids:
            avatar_q = select(TenantAdminModel.id, TenantAdminModel.avatar).where(
                TenantAdminModel.id.in_(ta_ids)
            )
            avatar_result = await self.db.execute(avatar_q)
            for aid, avatar in avatar_result.all():
                avatar_map[aid] = avatar

        operators = []
        for user_id, user_type, username, nickname in rows:
            operators.append({
                "user_id": user_id,
                "user_type": user_type,
                "username": username or "",
                "nickname": nickname,
                "avatar": avatar_map.get(user_id),
            })
        return operators

    async def _get_subordinate_admin_ids(self, admin: "Admin") -> list[int]:
        """
        获取平台管理员的下属用户 ID 列表

        包含:
        - 当前用户自己
        - 当前角色子树下所有角色的成员

        Args:
            admin: 当前平台管理员

        Returns:
            下属用户 ID 列表
        """
        from app.models.auth.admin_role import AdminRole
        from app.models.system.admin import Admin as AdminModel

        # 总是包含自己
        user_ids = [admin.id]

        # 如果没有角色，只能看自己的日志
        if not admin.role_id or not admin.role:
            return user_ids

        # 获取当前角色的 path
        current_role_path = admin.role.path or f"/{admin.role_id}/"

        # 查询所有子角色（path 以当前角色 path 开头的）
        child_roles_query = select(AdminRole.id).where(
            AdminRole.is_deleted.is_(False),
            AdminRole.path.like(f"{current_role_path}%"),
        )
        result = await self.db.execute(child_roles_query)
        child_role_ids = [row[0] for row in result.all()]

        # 如果有子角色，查询这些角色下的所有成员
        if child_role_ids:
            admins_query = select(AdminModel.id).where(
                AdminModel.is_deleted.is_(False),
                AdminModel.role_id.in_(child_role_ids),
            )
            result = await self.db.execute(admins_query)
            for row in result.all():
                if row[0] not in user_ids:
                    user_ids.append(row[0])

        return user_ids

    async def _get_subordinate_tenant_admin_ids(
        self,
        tenant_admin: "TenantAdmin",
    ) -> list[int]:
        """
        获取租户管理员的下属用户 ID 列表

        包含:
        - 当前用户自己
        - 当前角色子树下所有角色的成员

        Args:
            tenant_admin: 当前租户管理员

        Returns:
            下属用户 ID 列表
        """
        from app.models.auth.tenant_admin_role import TenantAdminRole
        from app.models.tenant.tenant_admin import TenantAdmin as TenantAdminModel

        # 总是包含自己
        user_ids = [tenant_admin.id]

        # 如果没有角色，只能看自己的日志
        if not tenant_admin.role_id or not tenant_admin.role:
            return user_ids

        # 获取当前角色的 path
        current_role_path = tenant_admin.role.path or f"/{tenant_admin.role_id}/"

        # 查询同租户内所有子角色（path 以当前角色 path 开头的）
        child_roles_query = select(TenantAdminRole.id).where(
            TenantAdminRole.is_deleted.is_(False),
            TenantAdminRole.tenant_id == tenant_admin.tenant_id,
            TenantAdminRole.path.like(f"{current_role_path}%"),
        )
        result = await self.db.execute(child_roles_query)
        child_role_ids = [row[0] for row in result.all()]

        # 如果有子角色，查询这些角色下的所有成员
        if child_role_ids:
            admins_query = select(TenantAdminModel.id).where(
                TenantAdminModel.is_deleted.is_(False),
                TenantAdminModel.tenant_id == tenant_admin.tenant_id,
                TenantAdminModel.role_id.in_(child_role_ids),
            )
            result = await self.db.execute(admins_query)
            for row in result.all():
                if row[0] not in user_ids:
                    user_ids.append(row[0])

        return user_ids


# ==================== 异步写入工具函数 ====================

async def _write_log_async(log_data: dict[str, Any]) -> None:
    """
    异步写入日志的内部实现

    使用独立的数据库会话，不阻塞主请求

    Args:
        log_data: 日志数据字典
    """
    try:
        async with async_session_factory() as db:
            # 如果 username/nickname 为空但 user_id 存在，查询用户信息
            if (not log_data.get("username") or not log_data.get("nickname")) and log_data.get("user_id"):
                user_info = await _fetch_user_info(
                    db,
                    user_type=log_data.get("user_type"),
                    user_id=log_data.get("user_id"),
                )
                if user_info:
                    if not log_data.get("username") and user_info.get("username"):
                        log_data["username"] = user_info["username"]
                    if not log_data.get("nickname") and user_info.get("nickname"):
                        log_data["nickname"] = user_info["nickname"]

            service = OperationLogService(db)
            await service.create_log(**log_data)
            await db.commit()
    except Exception as e:
        # 日志写入失败不应影响主业务
        # 记录到文件日志
        _module_logger.logger.error(f"Failed to write operation log: {e}")


async def _fetch_user_info(
    db: AsyncSession,
    user_type: str | None,
    user_id: int | None,
) -> dict[str, str | None] | None:
    """
    根据用户类型和 ID 查询用户信息

    Args:
        db: 数据库会话
        user_type: 用户类型
        user_id: 用户 ID

    Returns:
        包含 username 和 nickname 的字典，或 None
    """
    from sqlalchemy import select

    from app.enums.log import UserTypeEnum

    if not user_type or not user_id:
        return None

    try:
        if user_type == UserTypeEnum.ADMIN.value:
            from app.models import Admin
            result = await db.execute(
                select(Admin.username, Admin.nickname).where(Admin.id == user_id)
            )
            row = result.first()
            if row:
                return {"username": row[0], "nickname": row[1]}

        elif user_type == UserTypeEnum.TENANT_ADMIN.value:
            from app.models import TenantAdmin
            result = await db.execute(
                select(TenantAdmin.username, TenantAdmin.nickname).where(TenantAdmin.id == user_id)
            )
            row = result.first()
            if row:
                return {"username": row[0], "nickname": row[1]}

        elif user_type == UserTypeEnum.TENANT_USER.value:
            from app.models import TenantUser
            result = await db.execute(
                select(TenantUser.username, TenantUser.nickname).where(TenantUser.id == user_id)
            )
            row = result.first()
            if row:
                return {"username": row[0], "nickname": row[1]}

    except Exception:
        pass

    return None


def create_log_async(
    tenant_id: int | None,
    user_type: str,
    user_id: int | None,
    username: str | None,
    module: str | None,
    action: str | None,
    resource: str | None,
    method: str,
    path: str,
    query_params: dict | None = None,
    request_body: dict | None = None,
    status_code: int | None = None,
    response_code: int | None = None,
    response_message: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    duration_ms: int | None = None,
    nickname: str | None = None,
) -> None:
    """
    异步创建操作日志（不阻塞当前请求）

    使用 asyncio.create_task 在后台写入日志

    Args:
        tenant_id: 租户 ID（平台操作为 None）
        user_type: 用户类型
        user_id: 用户 ID
        username: 用户名
        module: 业务模块
        action: 操作类型
        resource: 资源标识
        method: HTTP 方法
        path: 请求路径
        query_params: 查询参数
        request_body: 请求体摘要（已脱敏）
        status_code: HTTP 状态码
        response_code: 业务响应码
        response_message: 响应消息
        ip: 客户端 IP
        user_agent: User-Agent
        duration_ms: 请求耗时（毫秒）
        nickname: 用户昵称

    Example:
        from app.services.system.operation_log_service import create_log_async

        create_log_async(
            tenant_id=None,
            user_type="admin",
            user_id=1,
            username="admin",
            module="auth",
            action="login",
            resource="auth:login",
            method="POST",
            path="/admin/auth/login",
            ip="127.0.0.1",
        )
    """
    log_data = {
        "tenant_id": tenant_id,
        "user_type": user_type,
        "user_id": user_id,
        "username": username,
        "nickname": nickname,
        "module": module,
        "action": action,
        "resource": resource,
        "method": method,
        "path": path,
        "query_params": query_params,
        "request_body": request_body,
        "status_code": status_code,
        "response_code": response_code,
        "response_message": response_message,
        "ip": ip,
        "user_agent": user_agent,
        "duration_ms": duration_ms,
    }

    # 获取当前事件循环并创建任务
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_write_log_async(log_data))
    except RuntimeError:
        # 如果没有运行的事件循环，同步执行（不常见）
        asyncio.run(_write_log_async(log_data))


__all__ = [
    "OperationLogService",
    "create_log_async",
]
