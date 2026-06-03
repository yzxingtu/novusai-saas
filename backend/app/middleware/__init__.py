"""
Middleware Module / 中间件模块
"""

from importlib import import_module

_LAZY_EXPORTS = {
    "AccessControlMiddleware": "app.middleware.access_control",
    "AuditLogMiddleware": "app.middleware.audit_log",
    "I18nMiddleware": "app.middleware.i18n",
    "MaintenanceMiddleware": "app.middleware.maintenance",
    "PermissionMiddleware": "app.middleware.permission",
    "PrometheusMetricsMiddleware": "app.middleware.prometheus_metrics",
}

__all__ = list(_LAZY_EXPORTS)


def __getattr__(name: str):
    module_path = _LAZY_EXPORTS.get(name)
    if not module_path:
        raise AttributeError(f"module 'app.middleware' has no attribute {name!r}")
    module = import_module(module_path)
    return getattr(module, name)


def __dir__() -> list[str]:
    return sorted(__all__)
