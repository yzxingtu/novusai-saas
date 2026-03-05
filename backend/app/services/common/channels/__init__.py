"""
通知渠道注册表

管理所有可用的通知渠道。渠道在模块加载时自动注册。
支持动态扩展：插件可通过 register_channel() 注册自定义渠道。
"""

from __future__ import annotations

from app.core.logging import LogManager
from app.services.common.channels.base import NotificationChannel

logger = LogManager.get_logger("app")

# 渠道注册表：channel_code → channel class
CHANNEL_REGISTRY: dict[str, type[NotificationChannel]] = {}


def register_channel(channel_cls: type[NotificationChannel]) -> None:
    """注册通知渠道"""
    instance = channel_cls()
    code = instance.channel_code
    if code in CHANNEL_REGISTRY:
        logger.warning("Notification channel '%s' already registered, overwriting", code)
    CHANNEL_REGISTRY[code] = channel_cls
    logger.info("Notification channel registered: %s", code)


def get_channel(code: str) -> NotificationChannel | None:
    """获取渠道实例"""
    cls = CHANNEL_REGISTRY.get(code)
    return cls() if cls else None


def get_registered_channel_codes() -> list[str]:
    """获取所有已注册的渠道码（供前端动态渲染用）"""
    return list(CHANNEL_REGISTRY.keys())


def get_registered_channels_info() -> list[dict[str, str]]:
    """获取所有已注册渠道的基本信息"""
    result = []
    for _code, cls in CHANNEL_REGISTRY.items():
        instance = cls()
        result.append({
            "code": instance.channel_code,
            "name": instance.channel_name,
        })
    return result


# ============================================
# 内置渠道自动注册
# ============================================
def _register_builtin_channels() -> None:
    """注册内置渠道（模块加载时执行）"""
    from app.services.common.channels.email_channel import EmailChannel
    from app.services.common.channels.inbox_channel import InboxChannel
    from app.services.common.channels.webhook_channel import WebhookChannel
    from app.services.common.channels.ws_channel import WSChannel

    register_channel(InboxChannel)
    register_channel(WSChannel)
    register_channel(EmailChannel)
    register_channel(WebhookChannel)


_register_builtin_channels()


__all__ = [
    "NotificationChannel",
    "CHANNEL_REGISTRY",
    "register_channel",
    "get_channel",
    "get_registered_channel_codes",
    "get_registered_channels_info",
]
