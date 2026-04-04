"""Plugin scheduler refresh helpers. / 插件调度刷新辅助。"""

from __future__ import annotations

from app.core.i18n import _
from app.core.logging import get_logger
from app.plugins.exceptions import PluginError

logger = get_logger(__name__)


def refresh_plugin_schedule_or_raise(plugin_name: str, *, action: str) -> None:
    """Refresh the in-process scheduler and fail closed when refresh breaks."""
    from app.tasks.scheduler import refresh_schedule

    try:
        refresh_schedule()
    except Exception as exc:
        logger.error(
            "Plugin {}: failed to refresh Celery schedule after {}: {}",
            plugin_name,
            action,
            exc,
        )
        raise PluginError(
            message=_("plugin.error.schedule_refresh_failed").format(
                plugin_name=plugin_name,
                action=action,
            ),
            data={
                "plugin_name": plugin_name,
                "schedule_action": action,
            },
        ) from exc
