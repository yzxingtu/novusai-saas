"""Internal lifecycle parts for PluginLifecycle facade composition."""

from .facade_modules import (
    LifecycleDependencyModule,
    LifecycleGuardModule,
    LifecyclePermissionModule,
)

__all__ = [
    "LifecycleDependencyModule",
    "LifecycleGuardModule",
    "LifecyclePermissionModule",
]
