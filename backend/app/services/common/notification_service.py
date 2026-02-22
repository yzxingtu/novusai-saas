"""
通知投递服务

统一入口：send() 查询用户偏好，分发到三个渠道（WS / 收件箱 / 邮件）。
提供通知查询、已读、删除等操作。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select, update, delete as sa_delete, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_model import utc_now
from app.core.logging import LogManager
from app.models.common.notification import Notification
from app.models.common.notification_preference import NotificationPreference
from app.models.common.notification_template import NotificationTemplate

logger = LogManager.get_logger("app")


class NotificationService:
    """
    通知投递与管理服务

    使用方式：
        service = NotificationService(db)
        await service.send(
            template_code="ai.batch_complete",
            recipients=[("tenant_admin", 5)],
            data={"batch_id": 123, "total": 500},
        )
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ========================================
    # 投递
    # ========================================

    async def send(
        self,
        template_code: str,
        recipients: list[tuple[str, int]],
        data: dict[str, Any] | None = None,
        link: str | None = None,
        tenant_id: int | None = None,
        **kwargs: Any,
    ) -> int:
        """
        投递通知（统一入口）

        注意：收件箱通知通过 db.add() 写入 session，但不会自动 commit。
        调用方需要在合适的时机执行 await db.commit() 来持久化收件箱记录。
        WS 和邮件渠道不受此影响（WS 直接推送，邮件通过 Celery 异步发送）。

        Args:
            template_code: 通知模板编码（如 'ai.batch_complete'）
            recipients: 接收人列表 [(user_type, user_id), ...]
            data: 业务数据（用于模板渲染和前端展示）
            link: 点击跳转链接
            tenant_id: 租户 ID（平台级通知为 None）
            **kwargs: 渠道扩展参数
                - email_html: 自定义 HTML 邮件正文
                - email_subject: 自定义邮件主题
                - email_text: 自定义纯文本邮件正文

        Returns:
            成功投递数量
        """
        from app.services.common.channels import get_channel

        # 检查通知系统总开关
        try:
            from app.sio.ws_config import get_ws_config
            notification_enabled = await get_ws_config("notification_enabled")
            if not notification_enabled:
                return 0
        except Exception:
            pass

        # 查询模板
        template = await self._get_template(template_code)
        if not template:
            logger.warning("Notification template not found: %s", template_code)
            return 0

        # 渲染标题和正文
        title = self._render_template(template.title_template, data)
        body = self._render_template(template.body_template, data) if template.body_template else None
        template_channels = template.channels or ["ws", "inbox"]

        # force_all_channels 模式：绕过偏好和渠道开关（用于测试发送）
        force = kwargs.pop("force_all_channels", False)

        sent = 0
        for user_type, user_id in recipients:
            # 查询用户偏好（force 模式跳过）
            if not force:
                pref = await self._get_preference(user_type, user_id, template.category)
            else:
                pref = {}

            # 遍历模板定义的渠道
            for channel_code in template_channels:
                # 用户偏好检查（force 模式全部允许）
                if not force:
                    default_enabled = channel_code in ("ws", "inbox")
                    pref_key = f"channel_{channel_code}"
                    if not pref.get(pref_key, default_enabled):
                        continue

                # 获取渠道实例
                channel = get_channel(channel_code)
                if not channel:
                    continue

                # 渠道全局启用检查（force 模式跳过）
                if not force and not await channel.is_enabled():
                    continue

                # 投递
                await channel.deliver(
                    db=self.db,
                    user_type=user_type,
                    user_id=user_id,
                    title=title,
                    body=body,
                    data=data,
                    link=link,
                    priority=template.priority,
                    template_code=template_code,
                    tenant_id=tenant_id,
                    **kwargs,
                )

            sent += 1

        # inbox 渠道的数量限制
        for user_type, user_id in recipients:
            if "inbox" in template_channels:
                await self._enforce_max_per_user(user_type, user_id)

        logger.info(
            "Notification sent: template=%s recipients=%d sent=%d",
            template_code, len(recipients), sent,
        )
        return sent

    # ========================================
    # 查询
    # ========================================

    async def get_notifications(
        self,
        user_type: str,
        user_id: int,
        category: str | None = None,
        is_read: bool | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Notification], int]:
        """
        查询通知列表（分页）

        Returns:
            (items, total)
        """
        conditions = [
            Notification.recipient_type == user_type,
            Notification.recipient_id == user_id,
            Notification.is_deleted.is_(False),
        ]
        if category:
            conditions.append(Notification.category == category)
        if is_read is not None:
            conditions.append(Notification.is_read == is_read)

        # 总数
        count_q = select(func.count(Notification.id)).where(and_(*conditions))
        total = (await self.db.execute(count_q)).scalar() or 0

        # 列表
        offset = (page - 1) * page_size
        q = (
            select(Notification)
            .where(and_(*conditions))
            .order_by(Notification.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(q)
        items = list(result.scalars().all())

        return items, total

    async def get_unread_count(
        self,
        user_type: str,
        user_id: int,
    ) -> int:
        """获取未读通知总数"""
        q = select(func.count(Notification.id)).where(
            Notification.recipient_type == user_type,
            Notification.recipient_id == user_id,
            Notification.is_read.is_(False),
            Notification.is_deleted.is_(False),
        )
        return (await self.db.execute(q)).scalar() or 0

    # ========================================
    # 操作
    # ========================================

    async def mark_read(
        self,
        notification_id: int,
        user_type: str,
        user_id: int,
    ) -> bool:
        """标记单条通知已读"""
        result = await self.db.execute(
            update(Notification)
            .where(
                Notification.id == notification_id,
                Notification.recipient_type == user_type,
                Notification.recipient_id == user_id,
                Notification.is_deleted.is_(False),
            )
            .values(is_read=True, read_at=utc_now())
        )
        return result.rowcount > 0

    async def mark_all_read(
        self,
        user_type: str,
        user_id: int,
        category: str | None = None,
    ) -> int:
        """标记全部已读，返回更新数量"""
        conditions = [
            Notification.recipient_type == user_type,
            Notification.recipient_id == user_id,
            Notification.is_read.is_(False),
            Notification.is_deleted.is_(False),
        ]
        if category:
            conditions.append(Notification.category == category)

        result = await self.db.execute(
            update(Notification)
            .where(and_(*conditions))
            .values(is_read=True, read_at=utc_now())
        )
        return result.rowcount

    async def delete_notification(
        self,
        notification_id: int,
        user_type: str,
        user_id: int,
    ) -> bool:
        """软删除通知"""
        result = await self.db.execute(
            update(Notification)
            .where(
                Notification.id == notification_id,
                Notification.recipient_type == user_type,
                Notification.recipient_id == user_id,
            )
            .values(is_deleted=True, deleted_at=utc_now())
        )
        return result.rowcount > 0

    # ========================================
    # 内部方法
    # ========================================

    async def _get_template(self, code: str) -> NotificationTemplate | None:
        """查询通知模板"""
        result = await self.db.execute(
            select(NotificationTemplate).where(
                NotificationTemplate.code == code,
                NotificationTemplate.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()

    async def _get_preference(
        self,
        user_type: str,
        user_id: int,
        category: str,
    ) -> dict[str, bool]:
        """查询用户通知偏好，不存在则返回默认值"""
        result = await self.db.execute(
            select(NotificationPreference).where(
                NotificationPreference.user_type == user_type,
                NotificationPreference.user_id == user_id,
                NotificationPreference.category == category,
            )
        )
        pref = result.scalar_one_or_none()
        if pref:
            return {
                "channel_ws": pref.channel_ws,
                "channel_email": pref.channel_email,
                "channel_inbox": pref.channel_inbox,
            }
        # 默认：WS + 收件箱开，邮件关
        return {"channel_ws": True, "channel_email": False, "channel_inbox": True}

    async def _enforce_max_per_user(
        self,
        recipient_type: str,
        recipient_id: int,
    ) -> None:
        """
        执行每用户最大通知数限制

        超出 notification_max_per_user 时，物理删除最早的已读通知。
        """
        try:
            from app.sio.ws_config import get_ws_config
            max_per_user = await get_ws_config("notification_max_per_user")
            if not max_per_user:
                return

            max_per_user = int(max_per_user)

            # 查询当前通知总数
            count_q = select(func.count(Notification.id)).where(
                Notification.recipient_type == recipient_type,
                Notification.recipient_id == recipient_id,
                Notification.is_deleted.is_(False),
            )
            total = (await self.db.execute(count_q)).scalar() or 0

            if total <= max_per_user:
                return

            # 超出限制，删除最早的已读通知（优先清理已读的）
            overflow = total - max_per_user
            oldest_q = (
                select(Notification.id)
                .where(
                    Notification.recipient_type == recipient_type,
                    Notification.recipient_id == recipient_id,
                    Notification.is_deleted.is_(False),
                    Notification.is_read.is_(True),
                )
                .order_by(Notification.created_at.asc())
                .limit(overflow)
            )
            oldest_ids = [row[0] for row in (await self.db.execute(oldest_q)).all()]

            if oldest_ids:
                await self.db.execute(
                    update(Notification)
                    .where(Notification.id.in_(oldest_ids))
                    .values(is_deleted=True, deleted_at=utc_now())
                )
                logger.info(
                    "Notification overflow cleanup: type=%s user_id=%d deleted=%d",
                    recipient_type, recipient_id, len(oldest_ids),
                )
        except Exception as e:
            logger.warning("_enforce_max_per_user failed: %s", str(e))

    @staticmethod
    def _render_template(template: str | None, data: dict[str, Any] | None) -> str:
        """渲染模板变量"""
        if not template:
            return ""
        if not data:
            return template
        try:
            return template.format_map(data)
        except (KeyError, ValueError):
            return template


# ============================================
# 便捷函数
# ============================================

async def notify(
    db,
    template_code: str,
    recipients: list[tuple[str, int]],
    data: dict[str, Any] | None = None,
    link: str | None = None,
    tenant_id: int | None = None,
    **kwargs: Any,
) -> int:
    """
    异步便捷函数 — 一行投递通知

    用于 Controller / Service 等异步上下文。
    调用方仍需 await db.commit() 来持久化收件箱记录。

    示例::

        await notify(db, "ai.batch_complete", [("tenant_admin", 5)], {"total": 500})
    """
    service = NotificationService(db)
    return await service.send(
        template_code=template_code,
        recipients=recipients,
        data=data,
        link=link,
        tenant_id=tenant_id,
        **kwargs,
    )


def notify_sync(
    template_code: str,
    recipients: list[tuple[str, int]],
    data: dict[str, Any] | None = None,
    link: str | None = None,
    tenant_id: int | None = None,
    **kwargs: Any,
) -> int:
    """
    同步便捷函数 — 用于 Celery 任务等同步上下文

    内部创建同步事件循环和 DB session。

    示例::

        notify_sync("system.task_failure", [("admin", 1)], {"error": "timeout"})
    """
    import asyncio

    from app.core.database import async_session_factory

    async def _run() -> int:
        async with async_session_factory() as db:
            service = NotificationService(db)
            count = await service.send(
                template_code=template_code,
                recipients=recipients,
                data=data,
                link=link,
                tenant_id=tenant_id,
                **kwargs,
            )
            await db.commit()
            return count

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _run())
                return future.result(timeout=30)
        return loop.run_until_complete(_run())
    except RuntimeError:
        return asyncio.run(_run())


__all__ = ["NotificationService", "notify", "notify_sync"]
