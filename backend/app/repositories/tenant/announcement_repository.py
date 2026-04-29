"""
公告管理仓储 / Announcement management repositories.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select, update
from sqlalchemy.orm import selectinload

from app.core.base_model import utc_now
from app.core.base_repository import BaseRepository, TenantRepository
from app.models.common.notification import Notification
from app.models.system.admin import Admin
from app.models.tenant.announcement import Announcement
from app.models.tenant.announcement_delivery import AnnouncementDelivery
from app.models.tenant.announcement_response import AnnouncementResponse
from app.models.tenant.tenant_admin import TenantAdmin


class AdminAnnouncementRepository(BaseRepository[Announcement]):
    """公告管理仓储（管理端跨租户）/ Admin announcement repository."""

    model = Announcement

    async def list_active_platform_admin_ids(self) -> list[int]:
        result = await self.db.execute(
            select(Admin.id).where(
                Admin.is_active.is_(True),
                Admin.is_deleted.is_(False),
            )
        )
        return list(result.scalars().all())


class AnnouncementRepository(TenantRepository[Announcement]):
    """公告管理仓储 / Tenant announcement repository."""

    model = Announcement

    async def list_active_tenant_admin_ids(self) -> list[int]:
        result = await self.db.execute(
            select(TenantAdmin.id).where(
                TenantAdmin.tenant_id == self.tenant_id,
                TenantAdmin.is_active.is_(True),
                TenantAdmin.is_deleted.is_(False),
            )
        )
        return list(result.scalars().all())


class AnnouncementDeliveryRepository(BaseRepository[AnnouncementDelivery]):
    """公告投递仓储 / Announcement delivery repository."""

    model = AnnouncementDelivery

    async def create_for_recipients(
        self,
        *,
        announcement_id: int,
        tenant_id: int,
        recipient_type: str,
        recipient_ids: Sequence[int],
        form_schema_version: int = 1,
    ) -> list[AnnouncementDelivery]:
        deliveries = [
            AnnouncementDelivery(
                announcement_id=announcement_id,
                tenant_id=tenant_id,
                recipient_type=recipient_type,
                recipient_id=recipient_id,
                status="pending",
                form_schema_version=form_schema_version,
            )
            for recipient_id in recipient_ids
        ]
        self.db.add_all(deliveries)
        await self.db.flush()
        return deliveries

    async def list_for_announcement(
        self,
        announcement_id: int,
        *,
        tenant_id: int | None = None,
    ) -> list[AnnouncementDelivery]:
        stmt = (
            select(AnnouncementDelivery)
            .where(
                AnnouncementDelivery.announcement_id == announcement_id,
                AnnouncementDelivery.is_deleted.is_(False),
            )
            .options(selectinload(AnnouncementDelivery.response))
            .order_by(AnnouncementDelivery.id.asc())
        )
        if tenant_id is not None:
            stmt = stmt.where(AnnouncementDelivery.tenant_id == tenant_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_for_recipient(
        self,
        *,
        announcement_id: int,
        recipient_type: str,
        recipient_id: int,
        tenant_id: int,
    ) -> AnnouncementDelivery | None:
        result = await self.db.execute(
            select(AnnouncementDelivery)
            .where(
                AnnouncementDelivery.announcement_id == announcement_id,
                AnnouncementDelivery.recipient_type == recipient_type,
                AnnouncementDelivery.recipient_id == recipient_id,
                AnnouncementDelivery.tenant_id == tenant_id,
                AnnouncementDelivery.is_deleted.is_(False),
            )
            .options(
                selectinload(AnnouncementDelivery.announcement),
                selectinload(AnnouncementDelivery.response),
            )
        )
        return result.scalar_one_or_none()

    async def list_pending_for_recipient(
        self,
        *,
        recipient_type: str,
        recipient_id: int,
        tenant_id: int,
    ) -> list[AnnouncementDelivery]:
        result = await self.db.execute(
            select(AnnouncementDelivery)
            .join(Announcement)
            .where(
                AnnouncementDelivery.recipient_type == recipient_type,
                AnnouncementDelivery.recipient_id == recipient_id,
                AnnouncementDelivery.tenant_id == tenant_id,
                AnnouncementDelivery.status == "pending",
                AnnouncementDelivery.is_deleted.is_(False),
                Announcement.status == "published",
                Announcement.is_deleted.is_(False),
            )
            .options(selectinload(AnnouncementDelivery.announcement))
            .order_by(Announcement.published_at.asc(), Announcement.id.asc())
        )
        return list(result.scalars().all())

    async def set_notification_id(
        self,
        delivery: AnnouncementDelivery,
        notification_id: int | None,
    ) -> None:
        delivery.notification_id = notification_id
        await self.db.flush()

    async def mark_submitted(self, delivery: AnnouncementDelivery) -> None:
        delivery.status = "submitted"
        delivery.read_at = delivery.read_at or utc_now()
        delivery.submitted_at = utc_now()
        await self.db.flush()

    async def mark_read(self, delivery: AnnouncementDelivery) -> None:
        delivery.status = "read"
        delivery.read_at = utc_now()
        await self.db.flush()


class AnnouncementResponseRepository(BaseRepository[AnnouncementResponse]):
    """公告回执仓储 / Announcement response repository."""

    model = AnnouncementResponse

    async def exists_for_delivery(self, delivery_id: int) -> bool:
        result = await self.db.execute(
            select(func.count(AnnouncementResponse.id)).where(
                AnnouncementResponse.delivery_id == delivery_id,
                AnnouncementResponse.is_deleted.is_(False),
            )
        )
        return bool(result.scalar() or 0)

    async def create_response(
        self,
        *,
        announcement_id: int,
        delivery_id: int,
        tenant_id: int,
        recipient_type: str,
        recipient_id: int,
        answers: dict,
    ) -> AnnouncementResponse:
        response = AnnouncementResponse(
            announcement_id=announcement_id,
            delivery_id=delivery_id,
            tenant_id=tenant_id,
            recipient_type=recipient_type,
            recipient_id=recipient_id,
            answers=answers,
        )
        self.db.add(response)
        await self.db.flush()
        await self.db.refresh(response)
        return response

    async def count_for_announcement(self, announcement_id: int) -> int:
        result = await self.db.execute(
            select(func.count(AnnouncementResponse.id)).where(
                AnnouncementResponse.announcement_id == announcement_id,
                AnnouncementResponse.is_deleted.is_(False),
            )
        )
        return int(result.scalar() or 0)

    async def mark_notification_read_for_delivery(
        self,
        *,
        delivery: AnnouncementDelivery,
    ) -> None:
        if delivery.notification_id:
            await self.db.execute(
                update(Notification)
                .where(
                    Notification.id == delivery.notification_id,
                    Notification.recipient_type == delivery.recipient_type,
                    Notification.recipient_id == delivery.recipient_id,
                    Notification.is_deleted.is_(False),
                )
                .values(is_read=True, read_at=utc_now())
            )
            return

        return


__all__ = [
    "AdminAnnouncementRepository",
    "AnnouncementDeliveryRepository",
    "AnnouncementRepository",
    "AnnouncementResponseRepository",
]
