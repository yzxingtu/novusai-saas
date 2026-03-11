"""
Plugin system framework providing core functionalities like plugin loading, lifecycle management, and extension point registration. / 插件系统框架，提供插件加载、生命周期管理、扩展点注册等核心功能。

导入方式（避免循环依赖）：
    from app.plugins.base import PluginBase
    from app.plugins.exceptions import PluginError, ...
    from app.plugins.manifest import PluginManifest
"""

__all__ = [
    "PluginBase",
    "PluginError",
    "PluginNotFoundError",
    "PluginManifestError",
    "PluginDependencyError",
    "PluginSecurityError",
    "PluginLicenseError",
    "PluginConflictError",
    "PluginInstallError",
]


def __getattr__(name: str):
    """Lazy import to avoid circular dependencies. / 延迟导入，避免循环依赖。"""
    if name == "PluginBase":
        from app.plugins.base import PluginBase
        return PluginBase

    _exception_names = {
        "PluginError", "PluginNotFoundError", "PluginManifestError",
        "PluginDependencyError", "PluginSecurityError", "PluginLicenseError",
        "PluginConflictError", "PluginInstallError",
    }
    if name in _exception_names:
        from app.plugins import exceptions
        return getattr(exceptions, name)

    raise AttributeError(f"module 'app.plugins' has no attribute {name!r}")
