"""
公告管理服务 / Announcement management services.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.configs.service import PLATFORM_TENANT_ID
from app.core.base_model import utc_now
from app.core.base_service import GlobalService, TenantService
from app.core.i18n import _
from app.exceptions import BusinessException, NotFoundException
from app.models.tenant.announcement import Announcement
from app.models.tenant.announcement_delivery import AnnouncementDelivery
from app.repositories.tenant.announcement_repository import (
    AdminAnnouncementRepository,
    AnnouncementDeliveryRepository,
    AnnouncementRepository,
    AnnouncementResponseRepository,
)
from app.schemas.common.query import FilterRule, QuerySpec
from app.services.common.notification_service import NotificationService

ANNOUNCEMENT_TEMPLATE_CODE = "announcement.published"
ANNOUNCEMENT_PENDING_LIMIT = 20
SUPPORTED_RECIPIENT_TYPES = {"admin", "tenant_admin", "tenant_user"}


class AnnouncementBusinessMixin:
    """Shared announcement workflow logic for admin and tenant services."""

    db: Any
    repo: Any

    def _announcement_scope(self) -> str:
        raise NotImplementedError

    def _announcement_tenant_id(self) -> int:
        raise NotImplementedError

    def _notification_tenant_id(self) -> int | None:
        raise NotImplementedError

    def _recipient_type(self) -> str:
        raise NotImplementedError

    def _notification_link(self, announcement_id: int) -> str:
        raise NotImplementedError

    def _delivery_repo(self) -> AnnouncementDeliveryRepository:
        return AnnouncementDeliveryRepository(self.db)

    def _response_repo(self) -> AnnouncementResponseRepository:
        return AnnouncementResponseRepository(self.db)

    async def query_list(
        self,
        spec: QuerySpec,
        scope: str | None = None,
        forced_filters: list[FilterRule] | None = None,
    ) -> tuple[list[Announcement], int]:
        filters = [
            FilterRule(field="scope", value=self._announcement_scope()),
            FilterRule(field="tenant_id", value=self._announcement_tenant_id()),
        ]
        filters.extend(forced_filters or [])
        return await super().query_list(  # type: ignore[misc]
            spec,
            scope=scope,
            forced_filters=filters,
        )

    async def get_by_id(self, id: int) -> Announcement | None:
        item = await super().get_by_id(id)  # type: ignore[misc]
        if not item:
            return None
        if item.scope != self._announcement_scope():
            return None
        if item.tenant_id != self._announcement_tenant_id():
            return None
        return item

    async def _before_create(self, data: dict[str, Any]) -> None:
        self._normalize_write_data(data, create=True)
        data["scope"] = self._announcement_scope()
        data["tenant_id"] = self._announcement_tenant_id()
        await super()._before_create(data)  # type: ignore[misc]

    async def _before_update(self, id: int, data: dict[str, Any]) -> None:
        item = await self.get_by_id(id)
        if not item:
            raise NotFoundException(message=_("tenant.announcement.not_found"))

        self._normalize_write_data(data, create=False)
        if item.status == "published":
            locked_fields = {"content", "form_schema", "require_response"}
            if locked_fields.intersection(data):
                raise BusinessException(
                    message=_("tenant.announcement.error.published_locked")
                )
        await super()._before_update(id, data)  # type: ignore[misc]

    async def _before_delete(self, id: int) -> None:
        item = await self.get_by_id(id)
        if not item:
            raise NotFoundException(message=_("tenant.announcement.not_found"))
        if item.status != "draft":
            raise BusinessException(message=_("tenant.announcement.error.draft_only"))
        await super()._before_delete(id)  # type: ignore[misc]

    def _normalize_write_data(self, data: dict[str, Any], *, create: bool) -> None:
        for field in (
            "scope",
            "tenant_id",
            "status",
            "published_at",
            "recipient_count",
            "response_count",
        ):
            data.pop(field, None)

        if create:
            data.setdefault("status", "draft")
            data.setdefault("recipient_count", 0)
            data.setdefault("response_count", 0)
            data.setdefault("published_at", None)

        if "form_schema" in data:
            data["form_schema"] = self.validate_form_schema(data.get("form_schema"))

        require_response = data.get("require_response")
        if require_response is False and "form_schema" not in data:
            data["form_schema"] = []
        if require_response is True and not data.get("form_schema"):
            raise BusinessException(
                message=_("tenant.announcement.error.invalid_form_schema"),
                data={"errors": ["required_form_schema"]},
            )

    async def publish(self, id: int, _publisher_id: int) -> Announcement:
        announcement = await self.get_by_id(id)
        if not announcement:
            raise NotFoundException(message=_("tenant.announcement.not_found"))
        if announcement.status != "draft":
            raise BusinessException(message=_("tenant.announcement.error.draft_only"))

        announcement.form_schema = self.validate_form_schema(
            announcement.form_schema or []
        )
        if announcement.require_response and not announcement.form_schema:
            raise BusinessException(
                message=_("tenant.announcement.error.invalid_form_schema"),
                data={"errors": ["required_form_schema"]},
            )

        recipient_ids = await self._load_publish_recipient_ids()
        deliveries = await self._delivery_repo().create_for_recipients(
            announcement_id=announcement.id,
            tenant_id=self._announcement_tenant_id(),
            recipient_type=self._recipient_type(),
            recipient_ids=recipient_ids,
        )

        announcement.status = "published"
        announcement.published_at = datetime.now(timezone.utc)
        announcement.recipient_count = len(deliveries)
        announcement.response_count = 0
        announcement.updated_at = utc_now()

        await self._send_publish_notifications(announcement, deliveries)
        await self.db.flush()
        await self.db.refresh(announcement)
        return announcement

    async def _load_publish_recipient_ids(self) -> list[int]:
        raise NotImplementedError

    async def _send_publish_notifications(
        self,
        announcement: Announcement,
        deliveries: list[AnnouncementDelivery],
    ) -> None:
        notification_service = NotificationService(self.db)
        for delivery in deliveries:
            created_notifications: list[Any] = []
            data = {
                "announcement_id": announcement.id,
                "delivery_id": delivery.id,
                "require_response": announcement.require_response,
                "form_schema_version": delivery.form_schema_version,
                "title": announcement.title,
                "content": announcement.content or "",
                "priority": announcement.priority,
            }
            await notification_service.send(
                template_code=ANNOUNCEMENT_TEMPLATE_CODE,
                recipients=[(delivery.recipient_type, delivery.recipient_id)],
                data=data,
                link=self._notification_link(announcement.id),
                tenant_id=self._notification_tenant_id(),
                force_all_channels=True,
                created_notifications=created_notifications,
            )
            await self.db.flush()
            notification_id = (
                created_notifications[0].id if created_notifications else None
            )
            await self._delivery_repo().set_notification_id(delivery, notification_id)

    async def list_responses(self, announcement_id: int) -> list[AnnouncementDelivery]:
        announcement = await self.get_by_id(announcement_id)
        if not announcement:
            raise NotFoundException(message=_("tenant.announcement.not_found"))
        return await self._delivery_repo().list_for_announcement(
            announcement_id,
            tenant_id=self._announcement_tenant_id(),
        )

    async def list_pending_for_user(
        self,
        recipient_id: int,
        *,
        recipient_type: str | None = None,
        limit: int = ANNOUNCEMENT_PENDING_LIMIT,
    ) -> list[AnnouncementDelivery]:
        resolved_type = recipient_type or self._recipient_type()
        self._ensure_supported_recipient_type(resolved_type)
        if limit <= 0:
            return []
        return await self._delivery_repo().list_pending_for_recipient(
            recipient_type=resolved_type,
            recipient_id=recipient_id,
            tenant_id=self._announcement_tenant_id(),
            limit=min(limit, ANNOUNCEMENT_PENDING_LIMIT),
        )

    async def get_for_current_user(
        self,
        announcement_id: int,
        recipient_id: int,
        *,
        recipient_type: str | None = None,
    ) -> AnnouncementDelivery:
        resolved_type = recipient_type or self._recipient_type()
        self._ensure_supported_recipient_type(resolved_type)

        delivery = await self._delivery_repo().get_for_recipient(
            announcement_id=announcement_id,
            recipient_type=resolved_type,
            recipient_id=recipient_id,
            tenant_id=self._announcement_tenant_id(),
        )
        if not delivery or not delivery.announcement:
            raise NotFoundException(
                message=_("tenant.announcement.error.delivery_not_found")
            )

        announcement = delivery.announcement
        if (
            announcement.scope != self._announcement_scope()
            or announcement.tenant_id != self._announcement_tenant_id()
            or announcement.status != "published"
        ):
            raise NotFoundException(
                message=_("tenant.announcement.error.delivery_not_found")
            )
        return delivery

    async def submit_response(
        self,
        announcement_id: int,
        recipient_id: int,
        answers: dict[str, Any],
        *,
        recipient_type: str | None = None,
    ) -> AnnouncementDelivery:
        resolved_type = recipient_type or self._recipient_type()
        self._ensure_supported_recipient_type(resolved_type)

        delivery = await self._delivery_repo().get_for_recipient(
            announcement_id=announcement_id,
            recipient_type=resolved_type,
            recipient_id=recipient_id,
            tenant_id=self._announcement_tenant_id(),
        )
        if not delivery or not delivery.announcement:
            raise NotFoundException(
                message=_("tenant.announcement.error.delivery_not_found")
            )
        if delivery.status != "pending":
            raise BusinessException(
                message=_("tenant.announcement.error.already_submitted")
            )
        if await self._response_repo().exists_for_delivery(delivery.id):
            raise BusinessException(
                message=_("tenant.announcement.error.already_submitted")
            )

        announcement = delivery.announcement
        if announcement.status != "published":
            raise BusinessException(message=_("tenant.announcement.error.draft_only"))

        schema = announcement.form_schema or []
        sanitized_answers = self.validate_answers(schema, answers or {})
        await self._response_repo().create_response(
            announcement_id=announcement.id,
            delivery_id=delivery.id,
            tenant_id=self._announcement_tenant_id(),
            recipient_type=delivery.recipient_type,
            recipient_id=delivery.recipient_id,
            answers=sanitized_answers,
        )
        await self._delivery_repo().mark_submitted(delivery)
        await self._response_repo().mark_notification_read_for_delivery(
            delivery=delivery
        )

        announcement.response_count = (
            await self._response_repo().count_for_announcement(announcement.id)
        )
        announcement.updated_at = utc_now()
        await self.db.flush()
        await self.db.refresh(delivery)
        return delivery

    async def mark_read(
        self,
        announcement_id: int,
        recipient_id: int,
        *,
        recipient_type: str | None = None,
    ) -> AnnouncementDelivery:
        resolved_type = recipient_type or self._recipient_type()
        self._ensure_supported_recipient_type(resolved_type)

        delivery = await self._delivery_repo().get_for_recipient(
            announcement_id=announcement_id,
            recipient_type=resolved_type,
            recipient_id=recipient_id,
            tenant_id=self._announcement_tenant_id(),
        )
        if not delivery or not delivery.announcement:
            raise NotFoundException(
                message=_("tenant.announcement.error.delivery_not_found")
            )
        if delivery.status != "pending":
            raise BusinessException(
                message=_("tenant.announcement.error.already_submitted")
            )

        announcement = delivery.announcement
        if announcement.status != "published":
            raise BusinessException(message=_("tenant.announcement.error.draft_only"))
        if announcement.require_response:
            raise BusinessException(
                message=_("tenant.announcement.error.response_required")
            )

        await self._delivery_repo().mark_read(delivery)
        await self._response_repo().mark_notification_read_for_delivery(
            delivery=delivery
        )
        await self.db.flush()
        await self.db.refresh(delivery)
        return delivery

    @staticmethod
    def _ensure_supported_recipient_type(recipient_type: str) -> None:
        if recipient_type not in SUPPORTED_RECIPIENT_TYPES:
            raise BusinessException(
                message=_("tenant.announcement.error.unsupported_recipient_type")
            )

    @staticmethod
    def validate_form_schema(raw_schema: Any) -> list[dict[str, Any]]:
        if raw_schema in (None, ""):
            return []
        if not isinstance(raw_schema, list):
            raise BusinessException(
                message=_("tenant.announcement.error.invalid_form_schema"),
                data={"errors": ["schema_must_be_array"]},
            )

        seen_keys: set[str] = set()
        normalized: list[dict[str, Any]] = []
        errors: list[str] = []
        for index, raw_field in enumerate(raw_schema):
            if not isinstance(raw_field, dict):
                errors.append(f"{index}.field_must_be_object")
                continue

            key = str(raw_field.get("key") or "").strip()
            field_type = raw_field.get("type")
            label = str(raw_field.get("label") or "").strip()
            if not key:
                errors.append(f"{index}.key_required")
            if key in seen_keys:
                errors.append(f"{index}.key_duplicate")
            seen_keys.add(key)
            if field_type not in {"consent", "text", "radio", "checkbox"}:
                errors.append(f"{index}.type_invalid")
            if not label:
                errors.append(f"{index}.label_required")

            options = raw_field.get("options") or []
            normalized_options: list[dict[str, str]] = []
            if field_type in {"radio", "checkbox"}:
                if not isinstance(options, list) or not options:
                    errors.append(f"{index}.options_required")
                option_values: set[str] = set()
                for option_index, option in enumerate(options):
                    if not isinstance(option, dict):
                        errors.append(f"{index}.options.{option_index}.invalid")
                        continue
                    option_label = str(option.get("label") or "").strip()
                    option_value = str(option.get("value") or "").strip()
                    if not option_label or not option_value:
                        errors.append(f"{index}.options.{option_index}.required")
                        continue
                    if option_value in option_values:
                        errors.append(f"{index}.options.{option_index}.duplicate")
                    option_values.add(option_value)
                    normalized_options.append(
                        {"label": option_label, "value": option_value}
                    )

            field: dict[str, Any] = {
                "key": key,
                "type": field_type,
                "label": label,
                "required": bool(raw_field.get("required", False)),
            }
            placeholder = raw_field.get("placeholder")
            if placeholder:
                field["placeholder"] = str(placeholder)
            if normalized_options:
                field["options"] = normalized_options
            if field_type == "consent":
                field["must_be_true"] = bool(raw_field.get("must_be_true", False))
            normalized.append(field)

        if errors:
            raise BusinessException(
                message=_("tenant.announcement.error.invalid_form_schema"),
                data={"errors": errors},
            )
        return normalized

    @classmethod
    def validate_answers(
        cls,
        form_schema: list[dict[str, Any]],
        answers: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(answers, dict):
            raise BusinessException(
                message=_("tenant.announcement.error.invalid_answers"),
                data={"errors": ["answers_must_be_object"]},
            )

        schema_by_key = {
            field["key"]: field for field in cls.validate_form_schema(form_schema)
        }
        unknown_keys = sorted(set(answers) - set(schema_by_key))
        errors = [f"{key}.unknown" for key in unknown_keys]
        sanitized: dict[str, Any] = {}

        for key, field in schema_by_key.items():
            value = answers.get(key)
            field_type = field["type"]
            required = bool(field.get("required"))

            if field_type == "consent":
                if value is None:
                    if required or field.get("must_be_true"):
                        errors.append(f"{key}.required")
                    continue
                if not isinstance(value, bool):
                    errors.append(f"{key}.boolean_required")
                    continue
                if field.get("must_be_true") and value is not True:
                    errors.append(f"{key}.must_be_true")
                sanitized[key] = value
                continue

            if field_type == "text":
                if value in (None, ""):
                    if required:
                        errors.append(f"{key}.required")
                    continue
                if not isinstance(value, str):
                    errors.append(f"{key}.string_required")
                    continue
                text_value = value.strip()
                if required and not text_value:
                    errors.append(f"{key}.required")
                sanitized[key] = text_value
                continue

            allowed_values = {
                option["value"] for option in field.get("options", []) or []
            }
            if field_type == "radio":
                if value in (None, ""):
                    if required:
                        errors.append(f"{key}.required")
                    continue
                if not isinstance(value, str) or value not in allowed_values:
                    errors.append(f"{key}.invalid_option")
                    continue
                sanitized[key] = value
                continue

            if field_type == "checkbox":
                if value in (None, ""):
                    if required:
                        errors.append(f"{key}.required")
                    continue
                if not isinstance(value, list) or not all(
                    isinstance(item, str) for item in value
                ):
                    errors.append(f"{key}.array_required")
                    continue
                if required and not value:
                    errors.append(f"{key}.required")
                invalid = [item for item in value if item not in allowed_values]
                if invalid:
                    errors.append(f"{key}.invalid_option")
                    continue
                sanitized[key] = value

        if errors:
            raise BusinessException(
                message=_("tenant.announcement.error.invalid_answers"),
                data={"errors": errors},
            )
        return sanitized


class AdminAnnouncementService(
    AnnouncementBusinessMixin,
    GlobalService[Announcement, AdminAnnouncementRepository],
):
    """公告管理管理端服务 / Admin announcement service."""

    model = Announcement
    repository_class = AdminAnnouncementRepository

    def _announcement_scope(self) -> str:
        return "admin"

    def _announcement_tenant_id(self) -> int:
        return PLATFORM_TENANT_ID

    def _notification_tenant_id(self) -> int | None:
        return None

    def _recipient_type(self) -> str:
        return "admin"

    def _notification_link(self, announcement_id: int) -> str:
        return f"/admin/system/announcements?announcement_id={announcement_id}"

    async def _load_publish_recipient_ids(self) -> list[int]:
        return await self.repo.list_active_platform_admin_ids()


class AnnouncementService(
    AnnouncementBusinessMixin,
    TenantService[Announcement, AnnouncementRepository],
):
    """公告管理企业端服务 / Tenant announcement service."""

    model = Announcement
    repository_class = AnnouncementRepository

    def _announcement_scope(self) -> str:
        return "tenant"

    def _announcement_tenant_id(self) -> int:
        return int(self.tenant_id or 0)

    def _notification_tenant_id(self) -> int | None:
        return self._announcement_tenant_id()

    def _recipient_type(self) -> str:
        return "tenant_admin"

    def _notification_link(self, announcement_id: int) -> str:
        return f"/tenant/system/announcements?announcement_id={announcement_id}"

    async def _load_publish_recipient_ids(self) -> list[int]:
        return await self.repo.list_active_tenant_admin_ids()


__all__ = [
    "ANNOUNCEMENT_PENDING_LIMIT",
    "ANNOUNCEMENT_TEMPLATE_CODE",
    "SUPPORTED_RECIPIENT_TYPES",
    "AdminAnnouncementService",
    "AnnouncementService",
]
