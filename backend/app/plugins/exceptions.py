"""
插件系统异常体系

继承项目已有的异常基类，提供插件专属的异常类型。
"""

from app.exceptions.base import (
    BusinessException,
    NotFoundException,
    ValidationException,
)


class PluginError(BusinessException):
    """插件通用错误"""

    code = 4230
    default_message = "plugin.error.general"


class PluginNotFoundError(NotFoundException):
    """插件不存在"""

    code = 4041
    default_message = "plugin.error.not_found"


class PluginManifestError(ValidationException):
    """插件清单解析/校验失败"""

    code = 4231
    default_message = "plugin.error.manifest_invalid"


class PluginDependencyError(PluginError):
    """插件依赖安装失败"""

    code = 4232
    default_message = "plugin.error.dependency_failed"


class PluginSecurityError(PluginError):
    """插件安全检查未通过"""

    code = 4233
    default_message = "plugin.error.security_violation"


class PluginLicenseError(PluginError):
    """插件许可证无效"""

    code = 4234
    default_message = "plugin.error.license_invalid"


class PluginConflictError(PluginError):
    """插件冲突"""

    code = 4235
    default_message = "plugin.error.conflict"


class PluginInstallError(PluginError):
    """插件安装失败"""

    code = 4236
    default_message = "plugin.error.install_failed"
