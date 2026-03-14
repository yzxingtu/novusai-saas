"""
统一错误码枚举 / Unified Error Code Enum

所有业务错误码的统一定义，遵循 i18n 国际化规范。
Unified definition of all business error codes, following i18n conventions.

错误码编码规则 / Error code encoding rules:
- 4xxx: 客户端错误 / Client errors
  - 40xx: 通用验证错误 / Generic validation errors
  - 41xx: 角色/权限相关 / Role/permission related
  - 42xx: 企业/域名相关 / Tenant/domain related
  - 43xx: 认证相关 / Authentication related
- 5xxx: 服务端错误 / Server errors

每个错误码对应一个 i18n key / Each error code maps to an i18n key: error.{module}.{error_name}
"""

from enum import IntEnum


class ErrorCode(IntEnum):
    """
    Business Error Code Enum / 业务错误码枚举

    Usage / 使用示例：
        raise BusinessException(
            message=_(ErrorCode.ADMIN_USERNAME_EXISTS.message_key),
            code=ErrorCode.ADMIN_USERNAME_EXISTS,
        )
    """

    # ==================== Common Errors / 通用错误 (40xx) ====================
    # Data validation errors / 数据验证类错误
    VALIDATION_ERROR = 4001
    DUPLICATE_ENTRY = 4002
    INVALID_PARAMETER = 4003
    OLD_PASSWORD_INCORRECT = 4004

    # ==================== Auth Errors / 认证授权错误 (401x/403x) ====================
    UNAUTHORIZED = 4010
    TOKEN_EXPIRED = 4011
    TOKEN_INVALID = 4012

    FORBIDDEN = 4030
    PERMISSION_DENIED = 4031

    # Resource not found / 资源不存在
    NOT_FOUND = 4040

    # Resource conflict / 资源冲突
    CONFLICT = 4090

    # ==================== Role Errors / 角色相关错误 (41xx) ====================
    # Role operation errors / 角色操作错误
    ROLE_CANNOT_SET_SELF_AS_PARENT = 4101
    ROLE_CIRCULAR_REFERENCE = 4102
    ROLE_MAX_DEPTH_EXCEEDED = 4103
    ROLE_SYSTEM_CANNOT_CHANGE_PARENT = 4104
    ROLE_SYSTEM_CANNOT_DELETE = 4105
    ROLE_HAS_CHILDREN = 4106
    ROLE_HAS_USERS = 4107
    ROLE_INVALID_CHILD_TYPE = 4108
    ROLE_ONLY_DEPARTMENT_CAN_SET_LEADER = 4109
    ROLE_CANNOT_ADD_MEMBER = 4110
    ROLE_MEMBER_EXISTS = 4111
    ROLE_MEMBER_NOT_IN_NODE = 4112

    # ==================== Tenant/Domain Errors / 企业/域名相关错误 (42xx) ====================
    DOMAIN_CUSTOM_DISABLED = 4201
    DOMAIN_QUOTA_EXCEEDED = 4202
    DOMAIN_ALREADY_EXISTS = 4203

    # ==================== Admin Errors / 管理员相关错误 (43xx) ====================
    ADMIN_USERNAME_EXISTS = 4301
    ADMIN_EMAIL_EXISTS = 4302
    ADMIN_PHONE_EXISTS = 4303
    ADMIN_CANNOT_REMOVE_SUPER = 4304
    TENANT_ADMIN_CANNOT_REMOVE_OWNER = 4305

    # ==================== Config Errors / 配置相关错误 (44xx) ====================
    CONFIG_GROUP_NOT_FOUND = 4401
    CONFIG_INVALID_KEYS = 4402
    CONFIG_VALIDATION_FAILED = 4403

    # ==================== Server Errors / 服务端错误 (5xxx) ====================
    SERVER_ERROR = 5000
    EXTERNAL_SERVICE_ERROR = 5020
    SERVICE_UNAVAILABLE = 5030

    @property
    def message_key(self) -> str:
        """
        Get i18n message key for error code / 获取错误码对应的 i18n 消息 key

        Returns:
            i18n message key, e.g. "error.role.circular_reference" / i18n 消息 key
        """
        return ERROR_CODE_MESSAGES.get(self, "error.unknown")


# Error code to i18n key mapping / 错误码到 i18n key 的映射
ERROR_CODE_MESSAGES: dict[int, str] = {
    # Common errors / 通用错误
    ErrorCode.VALIDATION_ERROR: "error.common.validation_error",
    ErrorCode.DUPLICATE_ENTRY: "error.common.duplicate_entry",
    ErrorCode.INVALID_PARAMETER: "error.common.invalid_parameter",
    ErrorCode.OLD_PASSWORD_INCORRECT: "error.common.old_password_incorrect",

    # Auth / 认证授权
    ErrorCode.UNAUTHORIZED: "error.auth.unauthorized",
    ErrorCode.TOKEN_EXPIRED: "error.auth.token_expired",
    ErrorCode.TOKEN_INVALID: "error.auth.token_invalid",
    ErrorCode.FORBIDDEN: "error.auth.forbidden",
    ErrorCode.PERMISSION_DENIED: "error.auth.permission_denied",
    ErrorCode.NOT_FOUND: "error.common.not_found",
    ErrorCode.CONFLICT: "error.common.conflict",

    # Role related / 角色相关
    ErrorCode.ROLE_CANNOT_SET_SELF_AS_PARENT: "error.role.cannot_set_self_as_parent",
    ErrorCode.ROLE_CIRCULAR_REFERENCE: "error.role.circular_reference",
    ErrorCode.ROLE_MAX_DEPTH_EXCEEDED: "error.role.max_depth_exceeded",
    ErrorCode.ROLE_SYSTEM_CANNOT_CHANGE_PARENT: "error.role.system_cannot_change_parent",
    ErrorCode.ROLE_SYSTEM_CANNOT_DELETE: "error.role.system_cannot_delete",
    ErrorCode.ROLE_HAS_CHILDREN: "error.role.has_children",
    ErrorCode.ROLE_HAS_USERS: "error.role.has_users",
    ErrorCode.ROLE_INVALID_CHILD_TYPE: "error.role.invalid_child_type",
    ErrorCode.ROLE_ONLY_DEPARTMENT_CAN_SET_LEADER: "error.role.only_department_can_set_leader",
    ErrorCode.ROLE_CANNOT_ADD_MEMBER: "error.role.cannot_add_member",
    ErrorCode.ROLE_MEMBER_EXISTS: "error.role.member_exists",
    ErrorCode.ROLE_MEMBER_NOT_IN_NODE: "error.role.member_not_in_node",

    # Tenant/Domain related / 企业/域名相关
    ErrorCode.DOMAIN_CUSTOM_DISABLED: "error.domain.custom_disabled",
    ErrorCode.DOMAIN_QUOTA_EXCEEDED: "error.domain.quota_exceeded",
    ErrorCode.DOMAIN_ALREADY_EXISTS: "error.domain.already_exists",

    # Admin related / 管理员相关
    ErrorCode.ADMIN_USERNAME_EXISTS: "error.admin.username_exists",
    ErrorCode.ADMIN_EMAIL_EXISTS: "error.admin.email_exists",
    ErrorCode.ADMIN_PHONE_EXISTS: "error.admin.phone_exists",
    ErrorCode.ADMIN_CANNOT_REMOVE_SUPER: "error.admin.cannot_remove_super",
    ErrorCode.TENANT_ADMIN_CANNOT_REMOVE_OWNER: "error.tenant_admin.cannot_remove_owner",

    # Config related / 配置相关
    ErrorCode.CONFIG_GROUP_NOT_FOUND: "error.config.group_not_found",
    ErrorCode.CONFIG_INVALID_KEYS: "error.config.invalid_keys",
    ErrorCode.CONFIG_VALIDATION_FAILED: "error.config.validation_failed",

    # Server errors / 服务端错误
    ErrorCode.SERVER_ERROR: "error.server.internal_error",
    ErrorCode.EXTERNAL_SERVICE_ERROR: "error.server.external_service_error",
    ErrorCode.SERVICE_UNAVAILABLE: "error.server.service_unavailable",
}


__all__ = ["ErrorCode", "ERROR_CODE_MESSAGES"]
