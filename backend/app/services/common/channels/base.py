"""
通知渠道基类 / Notification Channel Base

定义所有通知渠道必须实现的接口。
Defines the interface all notification channels must implement.
新增渠道只需继承此基类并注册到 CHANNEL_REGISTRY。
New channels just inherit this base and register to CHANNEL_REGISTRY.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


class NotificationChannel(ABC):
    """
    通知渠道抽象基类 / Notification channel abstract base.

    每个渠道实现三个核心方法：
    - channel_code: 渠道标识码
    - is_enabled(): 检查全局是否启用
    - deliver(): 投递通知
    """

    @property
    @abstractmethod
    def channel_code(self) -> str:
        """渠道标识码，如 'ws', 'inbox', 'email', 'webhook' / Channel code (e.g. ws, inbox, email, webhook)."""
        ...

    @property
    def channel_name(self) -> str:
        """渠道显示名称（供前端展示，默认等于 code） / Channel display name (defaults to code)."""
        return self.channel_code

    @abstractmethod
    async def is_enabled(self) -> bool:
        """检查该渠道是否全局启用 / Check if channel is globally enabled."""
        ...

    @abstractmethod
    async def deliver(
        self,
        db: AsyncSession,
        user_type: str,
        user_id: int,
        title: str,
        body: str | None,
        data: dict[str, Any] | None,
        link: str | None,
        priority: str,
        template_code: str,
        tenant_id: int | None = None,
        **kwargs: Any,
    ) -> bool:
        """
        投递通知到该渠道 / Deliver notification to this channel.

        Args:
            db: 数据库会话（收件箱渠道需要）
            user_type: 用户类型 (admin/tenant_admin/tenant_user)
            user_id: 用户 ID
            title: 通知标题
            body: 通知正文
            data: 业务数据
            link: 跳转链接
            priority: 优先级 (low/normal/high/urgent)
            template_code: 模板编码
            tenant_id: 企业 ID
            **kwargs: 扩展参数（如 email_html, email_subject）

        Returns:
            True = 投递成功, False = 投递失败/跳过
        """
        ...


__all__ = ["NotificationChannel"]
