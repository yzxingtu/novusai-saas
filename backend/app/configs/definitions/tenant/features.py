"""
租户功能开关配置项

包含租户级的功能模块启用/禁用配置
"""

from app.configs.meta import ConfigMeta
from app.configs.definitions.groups import TENANT_FEATURES_GROUP
from app.enums.config import ConfigScope, ConfigValueType


# ==========================================
# 用户管理功能
# ==========================================

# 允许用户自助注册
TENANT_ALLOW_REGISTRATION = ConfigMeta(
    key="tenant_allow_registration",
    name_key="config.tenant.allow_registration.name",
    description_key="config.tenant.allow_registration.desc",
    scope=ConfigScope.TENANT,
    value_type=ConfigValueType.BOOLEAN,
    default_value=True,
    sort_order=10,
)

# 新用户需要审批
TENANT_REGISTRATION_APPROVAL = ConfigMeta(
    key="tenant_registration_approval",
    name_key="config.tenant.registration_approval.name",
    description_key="config.tenant.registration_approval.desc",
    scope=ConfigScope.TENANT,
    value_type=ConfigValueType.BOOLEAN,
    default_value=False,
    sort_order=20,
)

# 允许用户修改个人资料
TENANT_ALLOW_PROFILE_EDIT = ConfigMeta(
    key="tenant_allow_profile_edit",
    name_key="config.tenant.allow_profile_edit.name",
    description_key="config.tenant.allow_profile_edit.desc",
    scope=ConfigScope.TENANT,
    value_type=ConfigValueType.BOOLEAN,
    default_value=True,
    sort_order=30,
)


# ==========================================
# 通知功能
# ==========================================

# 启用邮件通知
TENANT_EMAIL_NOTIFICATION = ConfigMeta(
    key="tenant_email_notification",
    name_key="config.tenant.email_notification.name",
    description_key="config.tenant.email_notification.desc",
    scope=ConfigScope.TENANT,
    value_type=ConfigValueType.BOOLEAN,
    default_value=True,
    sort_order=40,
)

# 启用短信通知
TENANT_SMS_NOTIFICATION = ConfigMeta(
    key="tenant_sms_notification",
    name_key="config.tenant.sms_notification.name",
    description_key="config.tenant.sms_notification.desc",
    scope=ConfigScope.TENANT,
    value_type=ConfigValueType.BOOLEAN,
    default_value=False,
    sort_order=50,
)


# ==========================================
# 其他功能
# ==========================================

# 启用 API 访问
TENANT_API_ACCESS = ConfigMeta(
    key="tenant_api_access",
    name_key="config.tenant.api_access.name",
    description_key="config.tenant.api_access.desc",
    scope=ConfigScope.TENANT,
    value_type=ConfigValueType.BOOLEAN,
    default_value=True,
    sort_order=60,
)

# 启用文件上传
TENANT_FILE_UPLOAD = ConfigMeta(
    key="tenant_file_upload",
    name_key="config.tenant.file_upload.name",
    description_key="config.tenant.file_upload.desc",
    scope=ConfigScope.TENANT,
    value_type=ConfigValueType.BOOLEAN,
    default_value=True,
    sort_order=70,
)


# ==========================================
# 注册配置到分组
# ==========================================

TENANT_FEATURES_GROUP.configs = [
    TENANT_ALLOW_REGISTRATION,
    TENANT_REGISTRATION_APPROVAL,
    TENANT_ALLOW_PROFILE_EDIT,
    TENANT_EMAIL_NOTIFICATION,
    TENANT_SMS_NOTIFICATION,
    TENANT_API_ACCESS,
    TENANT_FILE_UPLOAD,
]


__all__ = [
    "TENANT_ALLOW_REGISTRATION",
    "TENANT_REGISTRATION_APPROVAL",
    "TENANT_ALLOW_PROFILE_EDIT",
    "TENANT_EMAIL_NOTIFICATION",
    "TENANT_SMS_NOTIFICATION",
    "TENANT_API_ACCESS",
    "TENANT_FILE_UPLOAD",
]
