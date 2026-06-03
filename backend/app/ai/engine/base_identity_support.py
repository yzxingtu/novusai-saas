"""Identity helpers extracted from BaseEngine for reuse/testability."""

from __future__ import annotations

from app.enums.common import UserRoleEnum
from app.enums.log import UserTypeEnum as LogUserTypeEnum


def log_user_type_for_call_log(user_role: str) -> str:
    """Map ExecutionRequest.user_role → call_log.user_type / 执行请求角色 → 调用日志用户类型."""
    if user_role == UserRoleEnum.PLATFORM_ADMIN.value:
        return LogUserTypeEnum.ADMIN.value
    if user_role == UserRoleEnum.TENANT_USER.value:
        return LogUserTypeEnum.TENANT_USER.value
    return LogUserTypeEnum.TENANT_ADMIN.value


__all__ = ["log_user_type_for_call_log"]
